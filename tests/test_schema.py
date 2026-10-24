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
        "application_id", "location_text", "resource_class", "process_status",
    }
    assert len(OPTIONAL_FIELDS) == 17
    assert SCHEMA_VERSION == "1.0"


def test_the_power_core_is_an_alternative_not_one_specific_field():
    # A power field cannot be required unconditionally: a purely generating
    # application declares export capacity, a demand one import capacity.
    assert "capacity_withdrawn" not in CORE_FIELDS
    assert "capacity_injected" not in CORE_FIELDS
    assert CORE_ALTERNATIVES == (("capacity_withdrawn", "capacity_injected"),)
    shared = {"application_id": "X1", "location_text": "Pozna\u0144", "resource_class": "PV",
               "process_status": "APPLICATION_FILED"}
    df = pd.DataFrame([
        {**shared, "capacity_injected": 1200.0, "capacity_withdrawn": None},   # generating
        {**shared, "capacity_injected": None, "capacity_withdrawn": 90.0},     # demand
        {**shared, "capacity_injected": 500.0, "capacity_withdrawn": 500.0},   # bidirectional
        {**shared, "capacity_injected": None, "capacity_withdrawn": None},     # no capacity
    ])
    assert core_complete_mask(df).tolist() == [True, True, True, False]


def test_the_core_is_separate_for_each_entity_of_the_duty():
    # A NODE entity row must not be judged by the requirements of the APPLICATION
    # entity: point 2 of the provision has a different subject than points 1/3/4.
    assert set(CORE_BY_ENTITY) == {"APPLICATION", "NODE"}
    df = pd.DataFrame([
        {ENTITY_COLUMN: "NODE", "node_id": "SE-1", "capacity_available": 0.0},
        {ENTITY_COLUMN: "NODE", "node_id": "SE-2", "constraint_flag": True},
        {ENTITY_COLUMN: "NODE", "node_id": "SE-3"},
        {ENTITY_COLUMN: "APPLICATION", "application_id": "X1", "location_text": "Gda\u0144sk",
         "resource_class": "BESS", "process_status": "CONDITIONS_ISSUED", "capacity_withdrawn": 10.0},
    ])
    assert core_complete_mask(df).tolist() == [True, True, False, True]


def test_a_missing_entity_annotation_means_an_application():
    df = pd.DataFrame([{"application_id": "X1", "location_text": "\u0141\u00f3d\u017a",
                        "resource_class": "LOAD", "process_status": "CONNECTED",
                        "capacity_withdrawn": 40.0}])
    assert ENTITY_COLUMN not in df.columns
    assert core_complete_mask(df).tolist() == [True]


def test_every_field_has_a_legal_basis_and_a_group():
    for f in SCHEMA:
        assert f.basis, f.name
        assert f.group in {"identity", "capacity", "process"}, f.name
    assert sum(len(v) for v in GROUPS.values()) == 21


def test_the_canonical_power_unit_is_kw():
    for f in SCHEMA:
        if f.name.startswith("capacity_"):
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
    row = {"application_id": "X1", "location_text": "Warszawa, Grochowska"}
    problems = validate_instance(row)
    assert any("resource_class" in p for p in problems)
    assert any("process_status" in p for p in problems)
    # capacity is not a core field unconditionally, so its absence is not reported here
    assert not any("capacity_withdrawn" in p for p in problems)


def test_validate_instance_passes_a_correct_row():
    row = {
        "application_id": "X1", "location_text": "Warszawa, Grochowska",
        "resource_class": "LOAD", "capacity_withdrawn": 12000.0,
        "process_status": "APPLICATION_FILED", "date_application": "2026-06-29",
        "coordinates": (52.25, 21.07), "_annotation": "any_value",
    }
    assert validate_instance(row, strict_vocab=True) == []


def test_validate_instance_detects_a_field_outside_the_schema():
    row = {c: "x" for c in CORE_FIELDS}
    row["capacity_withdrawn"] = 1.0
    row["nonexistent_field"] = 1
    assert any("fields outside the schema" in p for p in validate_instance(row))


def test_validate_instance_detects_a_wrong_type_and_a_wrong_geopoint():
    row = {c: "x" for c in CORE_FIELDS}
    row["capacity_withdrawn"] = "dużo"
    row["coordinates"] = (999.0, 0.0)
    problems = validate_instance(row)
    assert any("capacity_withdrawn" in p for p in problems)
    assert any("coordinates" in p for p in problems)


def test_validate_frame_counts_fill_rate_and_core():
    df = pd.DataFrame({
        "application_id": ["a", "b"],
        "location_text": ["x", None],
        "resource_class": ["PV", "PV"],
        "capacity_withdrawn": [1.0, 2.0],
        "process_status": ["REFUSED", "REFUSED"],
    })
    rep = validate_frame(df)
    assert rep["n_rows"] == 2
    assert rep["rows_with_complete_core"] == 1
    assert rep["completion"]["location_text"] == 0.5
    assert rep["completion"]["date_agreement"] == 0.0


def test_empty_frame_and_schema_table():
    ef = empty_frame()
    assert list(ef.columns)[:21] == list(FIELDS)
    st = schema_table()
    assert len(st) == 21
    assert st["core"].sum() == 4
