"""Testy adaptera portugalskiego.

Najważniejszy z nich pilnuje rozstrzygnięcia o jednostkach: publikujący podaje
moc pozorną w MVA, schemat operuje mocą czynną w kW, więc pole mocy musi zostać
PUSTE. Wpisanie tam liczby z MVA byłoby cichym błędem jednostki — tej samej
klasy, co błędy, które projekt już raz wykrył pomiarem.
"""

import csv

import pandas as pd
import pytest

from gridqueue import core_complete_mask, get_adapter
from gridqueue.adapters.pt_eredes import SOURCE_POWER_UNIT

NAGLOWKI = [
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


def _plik(tmp_path, wiersze):
    p = tmp_path / "capacidade_rececao_rnd.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NAGLOWKI, delimiter=";")
        w.writeheader()
        for r in wiersze:
            w.writerow({k: r.get(k, "") for k in NAGLOWKI})
    return p


def _wiersz(**zmiany):
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
    r.update(zmiany)
    return r


class TestJednostki:
    def test_moc_dostepna_zostaje_pusta_bo_zrodlo_podaje_moc_pozorna(self, tmp_path):
        """Rdzeń rozstrzygnięcia: MVA to nie kW i nie wolno tego przeliczać."""
        d = get_adapter("pt_eredes").parse(_plik(tmp_path, [_wiersz()])).frame
        assert pd.isna(d.loc[0, "moc_dostepna"])
        assert pd.isna(d.loc[0, "moc_zarezerwowana"])
        assert d.loc[0, "_moc_dostepna_mva"] == pytest.approx(12.5)
        assert d.loc[0, "_jednostka_mocy_zrodlowa"] == SOURCE_POWER_UNIT

    def test_przecinek_dziesietny_zrodla_jest_odczytywany(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_plik(tmp_path, [_wiersz()])).frame
        assert d.loc[0, "_moc_przylaczona_mva"] == pytest.approx(11.5908)
        assert d.loc[0, "_moc_zakontraktowana_mva"] == pytest.approx(0.298)


class TestRdzen:
    def test_rdzen_wezla_spelnia_flaga_ograniczenia_a_nie_moc(self, tmp_path):
        """Alternatywa rdzenia encji WĘZEŁ działa, choć pole mocy jest puste."""
        d = get_adapter("pt_eredes").parse(_plik(tmp_path, [_wiersz()])).frame
        assert bool(core_complete_mask(d).iloc[0]) is True
        assert pd.isna(d.loc[0, "moc_dostepna"])

    def test_zerowa_zdolnosc_to_ograniczenie_a_nie_brak_danych(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_plik(
            tmp_path, [_wiersz(capacidade_de_recepcao_mt_at_mva_ultimo_trimestre="0")])).frame
        assert bool(d.loc[0, "ograniczenie_flaga"]) is True

    def test_brak_wartosci_zdolnosci_nie_jest_ograniczeniem(self, tmp_path):
        """Pusta komórka to nieujawnienie; oznaczenie jej jako ograniczenia byłoby zmyśleniem."""
        d = get_adapter("pt_eredes").parse(_plik(
            tmp_path, [_wiersz(capacidade_de_recepcao_mt_at_mva_ultimo_trimestre="")])).frame
        assert d.loc[0, "ograniczenie_flaga"] is None


class TestOdwzorowanie:
    def test_grupa_podstacji_trafia_w_pole_lokalizacji(self, tmp_path):
        """To samo pole, co lista stacji w wierszu węzłowym publikującego polskiego."""
        d = get_adapter("pt_eredes").parse(_plik(tmp_path, [_wiersz()])).frame
        assert d.loc[0, "lokalizacja_tekst"] == "Monchique, Aljezur"
        assert d.loc[0, "_encja"] == "WEZEL"

    def test_kwartal_zrodla_staje_sie_data_konca_kwartalu(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_plik(tmp_path, [_wiersz()])).frame
        assert d.loc[0, "data_publikacji"] == "2026-06-30"

    def test_nierozpoznany_zapis_kwartalu_daje_brak_a_nie_zgadywanie(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_plik(
            tmp_path, [_wiersz(data_ultimo_trimestre="wiosna")])).frame
        assert d.loc[0, "data_publikacji"] is None

    def test_poziom_napiecia_z_niezerowych_kolumn_zdolnosci(self, tmp_path):
        d = get_adapter("pt_eredes").parse(_plik(tmp_path, [_wiersz(
            **{"capacidade_de_recepcao_at_mva_ultimo_trimestre": "0",
               "capacidade_de_recepcao_mt_15kv_mva_ultimo_trimestre": "3,2"})])).frame
        assert d.loc[0, "poziom_napiecia"] == "15 kV"
