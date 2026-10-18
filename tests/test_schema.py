import math

import pandas as pd
import pytest

from gridqueue.schema import (
    CORE_ALTERNATIVES, CORE_BY_ENTITY, CORE_FIELDS, ENTITY_COLUMN, FIELDS, GROUPS,
    OPTIONAL_FIELDS, SCHEMA, SCHEMA_VERSION, canonical_date, canonical_power_kw,
    core_complete_mask, empty_frame, schema_table, validate_frame, validate_instance,
)


def test_schema_has_21_fields_and_a_4_field_unconditional_core():
    assert len(SCHEMA) == 21
    assert len(FIELDS) == len(set(FIELDS)) == 21
    assert set(CORE_FIELDS) == {
        "id_wniosku", "lokalizacja_tekst", "klasa_zasobu", "status_procesu",
    }
    assert len(OPTIONAL_FIELDS) == 17
    assert SCHEMA_VERSION == "1.0"


def test_the_power_core_is_an_alternative_not_one_specific_field():
    # A power field cannot be required unconditionally: a purely generating
    # application declares export capacity, a demand one import capacity.
    assert "moc_pobierana" not in CORE_FIELDS
    assert "moc_wprowadzana" not in CORE_FIELDS
    assert CORE_ALTERNATIVES == (("moc_pobierana", "moc_wprowadzana"),)
    wspolny = {"id_wniosku": "X1", "lokalizacja_tekst": "Pozna\u0144", "klasa_zasobu": "PV",
               "status_procesu": "WNIOSEK_ZLOZONY"}
    df = pd.DataFrame([
        {**wspolny, "moc_wprowadzana": 1200.0, "moc_pobierana": None},   # generating
        {**wspolny, "moc_wprowadzana": None, "moc_pobierana": 90.0},     # demand
        {**wspolny, "moc_wprowadzana": 500.0, "moc_pobierana": 500.0},   # bidirectional
        {**wspolny, "moc_wprowadzana": None, "moc_pobierana": None},     # no capacity
    ])
    assert core_complete_mask(df).tolist() == [True, True, True, False]


def test_the_core_is_separate_for_each_entity_of_the_duty():
    # A WEZEL entity row must not be judged by the requirements of the WNIOSEK
    # entity: point 2 of the provision has a different subject than points 1/3/4.
    assert set(CORE_BY_ENTITY) == {"WNIOSEK", "WEZEL"}
    df = pd.DataFrame([
        {ENTITY_COLUMN: "WEZEL", "id_wezla": "SE-1", "moc_dostepna": 0.0},
        {ENTITY_COLUMN: "WEZEL", "id_wezla": "SE-2", "ograniczenie_flaga": True},
        {ENTITY_COLUMN: "WEZEL", "id_wezla": "SE-3"},
        {ENTITY_COLUMN: "WNIOSEK", "id_wniosku": "X1", "lokalizacja_tekst": "Gda\u0144sk",
         "klasa_zasobu": "BESS", "status_procesu": "WARUNKI_WYDANE", "moc_pobierana": 10.0},
    ])
    assert core_complete_mask(df).tolist() == [True, True, False, True]


def test_a_missing_entity_annotation_means_an_application():
    df = pd.DataFrame([{"id_wniosku": "X1", "lokalizacja_tekst": "\u0141\u00f3d\u017a",
                        "klasa_zasobu": "ODB", "status_procesu": "PRZYLACZONY",
                        "moc_pobierana": 40.0}])
    assert ENTITY_COLUMN not in df.columns
    assert core_complete_mask(df).tolist() == [True]


def test_every_field_has_a_legal_basis_and_a_group():
    for f in SCHEMA:
        assert f.podstawa, f.name
        assert f.group in {"tozsamosc", "moc", "proces"}, f.name
    assert sum(len(v) for v in GROUPS.values()) == 21


def test_the_canonical_power_unit_is_kw():
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


def test_canonical_power_rejects_an_unknown_unit():
    with pytest.raises(ValueError):
        canonical_power_kw("1", "GW")


def test_validate_instance_detects_a_missing_core():
    row = {"id_wniosku": "X1", "lokalizacja_tekst": "Warszawa, Grochowska"}
    problems = validate_instance(row)
    assert any("klasa_zasobu" in p for p in problems)
    assert any("status_procesu" in p for p in problems)
    # capacity is not a core field unconditionally, so its absence is not reported here
    assert not any("moc_pobierana" in p for p in problems)


def test_validate_instance_passes_a_correct_row():
    row = {
        "id_wniosku": "X1", "lokalizacja_tekst": "Warszawa, Grochowska",
        "klasa_zasobu": "ODB", "moc_pobierana": 12000.0,
        "status_procesu": "WNIOSEK_ZLOZONY", "data_wniosku": "2026-06-29",
        "wspolrzedne": (52.25, 21.07), "_adnotacja": "dowolna",
    }
    assert validate_instance(row, strict_vocab=True) == []


def test_validate_instance_detects_a_field_outside_the_schema():
    row = {c: "x" for c in CORE_FIELDS}
    row["moc_pobierana"] = 1.0
    row["nieistniejace_pole"] = 1
    assert any("fields outside the schema" in p for p in validate_instance(row))


def test_validate_instance_detects_a_wrong_type_and_a_wrong_geopoint():
    row = {c: "x" for c in CORE_FIELDS}
    row["moc_pobierana"] = "dużo"
    row["wspolrzedne"] = (999.0, 0.0)
    problems = validate_instance(row)
    assert any("moc_pobierana" in p for p in problems)
    assert any("wspolrzedne" in p for p in problems)


def test_validate_frame_counts_fill_rate_and_core():
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


def test_empty_frame_and_schema_table():
    ef = empty_frame()
    assert list(ef.columns)[:21] == list(FIELDS)
    st = schema_table()
    assert len(st) == 21
    assert st["rdzen"].sum() == 4
