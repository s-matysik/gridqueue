import json

import pandas as pd
import pytest

from gridqueue.adapters.base import Adapter, harmonize_klasa, harmonize_status, norm_text
from gridqueue.adapters.pl_stoen import detect_layout
from gridqueue.adapters.uk_nationalgrid import NationalGridAdapter, _as_bool
from gridqueue.cli import build_parser, main
from gridqueue.registry import REGISTRY, declarations, get_adapter
from gridqueue.schema import FIELDS, META_COLUMNS


def test_rejestr_ma_szesc_adapterow():
    assert set(REGISTRY) == {"pl_tauron", "pl_stoen", "pl_boryszew", "uk_nationalgrid",
                             "pl_pse", "pl_energa"}


def test_deklaracje_pol_sa_podzbiorem_schematu():
    for d in declarations():
        assert set(d["pola_deklarowane"]) <= set(FIELDS), d["publikujacy"]
        assert all(k.startswith("_") for k in d["rozszerzenia"]), d["publikujacy"]


def test_kazdy_adapter_deklaruje_rdzen():
    rdzen = {"id_wniosku", "lokalizacja_tekst", "klasa_zasobu", "moc_pobierana",
             "status_procesu"}
    for key in REGISTRY:
        a = get_adapter(key)
        assert rdzen <= set(a.declared_fields), key


def test_get_adapter_odrzuca_nieznany_klucz():
    with pytest.raises(KeyError):
        get_adapter("pl_nieistniejacy")


@pytest.mark.parametrize("raw,expected", [
    ("PV", "PV"), ("Elektrownia fotowoltaiczna", "PV"), ("Solar", "PV"),
    ("FW", "FW"), ("Wind", "FW"), ("MEE", "BESS"), ("Magazyn energii", "BESS"),
    ("BESS", "BESS"), ("ODB", "ODB"), ("Instalacja odbiorcza", "ODB"),
    ("Demand", "ODB"), ("OSDn", "SIEC"), ("Stacja transformatorowa", "SIEC"),
    ("", "NIEOKRESLONA"),
])
def test_harmonize_klasa(raw, expected):
    assert harmonize_klasa(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("UMOWA O PRZYŁĄCZENIE obowiązująca", "UMOWA_OBOWIAZUJACA"),
    ("WARUNKI PRZYŁĄCZENIA wydane", "WARUNKI_WYDANE"),
    ("WARUNKI PRZYŁĄCZENIA utraciły ważność", "WARUNKI_WYGASLE"),
    ("WNIOSEK niekompletny", "WNIOSEK_NIEKOMPLETNY"),
    ("WNIOSEK wycofany", "WNIOSEK_WYCOFANY"),
    ("OBIEKT przyłączony", "PRZYLACZONY"),
    ("Accepted not yet Connected", "UMOWA_OBOWIAZUJACA"),
    ("Recently Connected", "PRZYLACZONY"),
    ("", "NIEOKRESLONY"),
])
def test_harmonize_status(raw, expected):
    assert harmonize_status(raw) == expected


def test_norm_text_usuwa_diakrytyki():
    assert norm_text("Świętego  Wincentego\n") == "swietego wincentego"


def test_detect_layout_stoen():
    assert detect_layout("Lp. Rodzaj klienta ... Status rozpatrywania wniosku") == "wnioski"
    assert detect_layout("... Odmowa przyłączenia Data odmowy") == "odmowy"
    assert detect_layout("... Data zawarcia umowy Data rozpoczęcia dostarczania") == "podmioty"
    assert detect_layout("cokolwiek innego") is None


def test_finalize_ustawia_kolejnosc_i_metadane():
    a = get_adapter("pl_tauron")
    df = a.finalize(pd.DataFrame({"id_wniosku": ["x"], "_extra": [1]}), document="d.pdf")
    assert list(df.columns)[:21] == list(FIELDS)
    assert list(df.columns)[21:24] == list(META_COLUMNS)
    assert df["publikujacy"].iloc[0] == "TAURON Dystrybucja S.A."
    assert df["jurysdykcja"].iloc[0] == "PL"
    assert df["dokument_zrodlowy"].iloc[0] == "d.pdf"


def test_as_bool():
    assert _as_bool("True") is True and _as_bool("false") is False
    assert _as_bool(None) is None and _as_bool("maybe") is None


def test_nationalgrid_mapuje_ramke_bez_sieci():
    raw = pd.DataFrame({
        "Licence Area": ["South Wales"], "GSP": ["Aberthaw Power Station"],
        "TANM": [False], "DANM": [True], "Status": ["Accepted not yet Connected"],
        "Bus Number": [502401], "Bus Name": ["EAST3_MAIN2"], "Site ID": [241],
        "Application ID": [1], "Site Export Capacity (MW)": [20.0],
        "Site Import Capacity (MW)": [0.05], "Machine Export Capacity (MW)": [20.0],
        "Machine Import Capacity (MW)": [None], "Fuel type": ["Solar"],
        "Machine ID": ["PA"], "Position": [99],
    })
    out = NationalGridAdapter().parse(raw).frame
    assert len(out) == 1
    r = out.iloc[0]
    assert r["id_wniosku"] == "nged:241:1:PA"
    assert r["moc_wprowadzana"] == 20000.0
    assert r["moc_pobierana"] == 50.0
    assert r["klasa_zasobu"] == "PV"
    assert r["status_procesu"] == "UMOWA_OBOWIAZUJACA"
    assert bool(r["ograniczenie_flaga"]) is True
    assert r["pozycja_w_kolejce"] == 99.0
    assert r["jurysdykcja"] == "UK"


def test_adapter_bazowy_nie_implementuje_parse():
    with pytest.raises(NotImplementedError):
        Adapter().parse("x")


def test_cli_schema_i_adapters(capsys, tmp_path):
    assert main(["schema", "--out", str(tmp_path / "s.csv")]) == 0
    assert len(pd.read_csv(tmp_path / "s.csv")) == 21
    capsys.readouterr()
    assert main(["adapters"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 6


def test_cli_validate_i_export(tmp_path, capsys):
    p = tmp_path / "a.csv"
    pd.DataFrame({
        "id_wniosku": ["a", "b"], "lokalizacja_tekst": ["x", "y"],
        "klasa_zasobu": ["PV", "PV"], "moc_pobierana": [1.0, 2.0],
        "status_procesu": ["ODMOWA", "ODMOWA"], "data_odmowy": ["2026-01-01", "2026-01-02"],
    }).to_csv(p, index=False)
    assert main(["validate", str(p), "--out", str(tmp_path / "rep.json")]) == 0
    rep = json.loads((tmp_path / "rep.json").read_text())
    assert rep["schemat"]["n_wierszy"] == 2
    assert rep["jakosc"]["n_regul"] == 8
    out = tmp_path / "panel.parquet"
    assert main(["export", str(p), str(p), "--out", str(out), "--only-schema"]) == 0
    assert len(pd.read_parquet(out)) == 4


def test_cli_parser_wymaga_podkomendy():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
