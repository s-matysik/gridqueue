import math

import pandas as pd
import pytest

from gridqueue.schema import (
    CORE_FIELDS, FIELDS, GROUPS, OPTIONAL_FIELDS, SCHEMA,
    canonical_date, canonical_power_kw, empty_frame, schema_table,
    validate_frame, validate_instance,
)


def test_schema_ma_21_pol_i_5_polowy_rdzen():
    assert len(SCHEMA) == 21
    assert len(FIELDS) == len(set(FIELDS)) == 21
    assert set(CORE_FIELDS) == {
        "id_wniosku", "lokalizacja_tekst", "klasa_zasobu", "moc_pobierana",
        "status_procesu",
    }
    assert len(OPTIONAL_FIELDS) == 16


def test_kazde_pole_ma_podstawe_prawna_i_grupe():
    for f in SCHEMA:
        assert f.podstawa, f.name
        assert f.group in {"tozsamosc", "moc", "proces"}, f.name
    assert sum(len(v) for v in GROUPS.values()) == 21


def test_jednostka_kanoniczna_mocy_to_kw():
    for f in SCHEMA:
        if f.name.startswith("moc_"):
            assert f.unit == "kW", f.name


@pytest.mark.parametrize("raw,unit,expected", [
    ("0,7", "MW", 700.0),
    ("12 000", "kW", 12000.0),
    ("1\u00a0234,5", "kW", 1234.5),
    (0.189525, "MW", 189.525),
    ("", "kW", None),
    ("brak", "MW", None),
    (None, "MW", None),
])
def test_canonical_power_kw(raw, unit, expected):
    got = canonical_power_kw(raw, unit)
    if expected is None:
        assert got is None
    else:
        assert math.isclose(got, expected, rel_tol=1e-9)


@pytest.mark.parametrize("raw,expected", [
    ("04.05.2026", "2026-05-04"),
    ("2026-05-04", "2026-05-04"),
    ("31 sierpnia 2026", None),
    ("-------------", None),
    ("Nie dotyczy", None),
    ("", None),
])
def test_canonical_date(raw, expected):
    assert canonical_date(raw) == expected


def test_canonical_power_odrzuca_nieznana_jednostke():
    with pytest.raises(ValueError):
        canonical_power_kw("1", "GW")


def test_validate_instance_wykrywa_brak_rdzenia():
    row = {"id_wniosku": "X1", "lokalizacja_tekst": "Warszawa, Grochowska"}
    problems = validate_instance(row)
    assert any("klasa_zasobu" in p for p in problems)
    assert any("moc_pobierana" in p for p in problems)
    assert any("status_procesu" in p for p in problems)


def test_validate_instance_przepuszcza_poprawny_wiersz():
    row = {
        "id_wniosku": "X1", "lokalizacja_tekst": "Warszawa, Grochowska",
        "klasa_zasobu": "ODB", "moc_pobierana": 12000.0,
        "status_procesu": "WNIOSEK_ZLOZONY", "data_wniosku": "2026-06-29",
        "wspolrzedne": (52.25, 21.07), "_adnotacja": "dowolna",
    }
    assert validate_instance(row, strict_vocab=True) == []


def test_validate_instance_wykrywa_pole_spoza_schematu():
    row = {c: "x" for c in CORE_FIELDS}
    row["moc_pobierana"] = 1.0
    row["nieistniejace_pole"] = 1
    assert any("spoza schematu" in p for p in validate_instance(row))


def test_validate_instance_wykrywa_zly_typ_i_zly_geopoint():
    row = {c: "x" for c in CORE_FIELDS}
    row["moc_pobierana"] = "dużo"
    row["wspolrzedne"] = (999.0, 0.0)
    problems = validate_instance(row)
    assert any("moc_pobierana" in p for p in problems)
    assert any("wspolrzedne" in p for p in problems)


def test_validate_frame_liczy_wypelnienie_i_rdzen():
    df = pd.DataFrame({
        "id_wniosku": ["a", "b"],
        "lokalizacja_tekst": ["x", None],
        "klasa_zasobu": ["PV", "PV"],
        "moc_pobierana": [1.0, 2.0],
        "status_procesu": ["ODMOWA", "ODMOWA"],
    })
    rep = validate_frame(df)
    assert rep["n_wierszy"] == 2
    assert rep["wiersze_z_kompletnym_rdzeniem"] == 1
    assert rep["wypelnienie"]["lokalizacja_tekst"] == 0.5
    assert rep["wypelnienie"]["data_umowy"] == 0.0


def test_empty_frame_i_schema_table():
    ef = empty_frame()
    assert list(ef.columns)[:21] == list(FIELDS)
    st = schema_table()
    assert len(st) == 21
    assert st["rdzen"].sum() == 5
