"""Tests of the Portuguese adapter.

The most important of them guards the decision about units: the publisher gives
apparent power in MVA, the schema works with active power in kW, so the capacity
field has to stay EMPTY. Writing an MVA figure there would be a silent unit
error, of the same class as the errors this project has already caught once by
measurement.
"""

import csv

import pandas as pd
import pytest

from gridqueue import core_complete_mask, get_adapter
from gridqueue.adapters.pt_eredes import SOURCE_POWER_UNIT

HEADERS = [
    "codigo", "instalacao", "tipo_de_instalacao", "distrito", "concelho", "nut3",
    "grupo_de_subestacoes_rari", "data_ultimo_trimestre",
    "capacidade_de_recepcao_mt_at_mva_ultimo_trimestre",
    "capacidade_de_recepcao_at_mva_ultimo_trimestre",
    "capacidade_de_recepcao_mt_30kv_mva_ultimo_trimestre",
    "capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre",
    "capacidade_de_recepcao_mt_10kv_mva_ultimo_trimestre",
    "potencia_de_ligacao_ligado_mva_ultimo_trimestre",
    "potencia_de_ligacao_comprometido_mva_ultimo_trimestre",
    "potencia_de_ligacao_em_potwierdzaniu",
    "potencia_de_ligacao_em_confirmacao_mva_ultimo_trimestre",
    "ligacao_rnt_barramento_60kv_ultimo_trimestre",
]


def _file_name(tmp_path, rows):
    p = tmp_path / "capacidade_rececao_rnd.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in HEADERS})
    return p


def _row(**changes):
    r = {
        "codigo": "0809S5060500", "instalacao": "MONCHIQUE", "tipo_de_instalacao": "SE AT",
        "distrito": "Faro", "concelho": "Monchique", "nut3": "Algarve",
        "grupo_de_subestacoes_rari": "Monchique, Aljezur", "data_ultimo_trimestre": "2T2026",
        "capacidade_de_recepcao_mt_at_mva_ultimo_trimestre": "12,5",
        "capacidade_de_recepcao_at_mva_ultimo_trimestre": "12,5",
        "capacidade_de_recepcao_mt_30kv_mva_ultimo_trimestre": "0",
        "capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre": "0",
        "capacidade_de_recepcao_mt_10kv_mva_ultimo_trimestre": "0",
        "potencia_de_ligacao_ligado_mva_ultimo_trimestre": "11,5908",
        "potencia_de_ligacao_comprometido_mva_ultimo_trimestre": "0,298",
        "potencia_de_ligacao_em_confirmacao_mva_ultimo_trimestre": "0",
        "ligacao_rnt_barramento_60kv_ultimo_trimestre": "Portimão",
    }
    r.update(changes)
    return r


class TestUnits:
    def test_available_capacity_stays_empty_because_the_source_gives_apparent_power(self, tmp_path):
        """The heart of the decision: MVA is not kW and it must not be converted."""
        d = get_adapter("pt_eredes").parse(_file_name(tmp_path, [_row()])).frame
        assert pd.isna(d.loc[0, "moc_dostepna"])
        assert pd.isna(d.loc[0, "moc_zarezerwowana"])
        assert d.loc[0, "_moc_dostepna_mva"] == pytest.approx(12.5)
        assert d.loc[0, "_jednostka_mocy_zrodlowa"] == SOURCE_POWER_UNIT

    def test_the_decimal_comma_of_the_source_is_read(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_file_name(tmp_path, [_row()])).frame
        assert d.loc[0, "_moc_przylaczona_mva"] == pytest.approx(11.5908)
        assert d.loc[0, "_moc_zakontraktowana_mva"] == pytest.approx(0.298)


class TestCore:
    def test_the_node_core_is_satisfied_by_the_constraint_flag_not_by_capacity(self, tmp_path):
        """The core alternative of the WEZEL entity works although the capacity field is empty."""
        d = get_adapter("pt_eredes").parse(_file_name(tmp_path, [_row()])).frame
        assert bool(core_complete_mask(d).iloc[0]) is True
        assert pd.isna(d.loc[0, "moc_dostepna"])

    def test_zero_capability_is_a_constraint_and_not_missing_data(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_file_name(
            tmp_path, [_row(capacidade_de_recepcao_mt_at_mva_ultimo_trimestre="0")])).frame
        assert bool(d.loc[0, "ograniczenie_flaga"]) is True

    def test_a_missing_capability_value_is_not_a_constraint(self, tmp_path):
        """An empty cell is a non-disclosure; marking it as a constraint would be an invention."""
        d = get_adapter("pt_eredes").parse(_file_name(
            tmp_path, [_row(capacidade_de_recepcao_mt_at_mva_ultimo_trimestre="")])).frame
        assert d.loc[0, "ograniczenie_flaga"] is None


class TestMapping:
    def test_the_substation_group_goes_into_the_location_field(self, tmp_path):
        """The same field as the list of stations in the node row of the Polish publisher."""
        d = get_adapter("pt_eredes").parse(_file_name(tmp_path, [_row()])).frame
        assert d.loc[0, "lokalizacja_tekst"] == "Monchique, Aljezur"
        assert d.loc[0, "_encja"] == "WEZEL"

    def test_the_quarter_of_the_source_becomes_the_end_of_quarter_date(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_file_name(tmp_path, [_row()])).frame
        assert d.loc[0, "data_publikacji"] == "2026-06-30"

    def test_an_unrecognised_quarter_notation_gives_a_gap_and_not_a_guess(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_file_name(
            tmp_path, [_row(data_ultimo_trimestre="wiosna")])).frame
        assert d.loc[0, "data_publikacji"] is None

    def test_the_voltage_level_comes_from_the_non_zero_capability_columns(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_file_name(tmp_path, [_row(
            **{"capacidade_de_recepcao_at_mva_ultimo_trimestre": "0",
               "capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre": "3,2"})])).frame
        assert d.loc[0, "poziom_napiecia"] == "15 kV"
