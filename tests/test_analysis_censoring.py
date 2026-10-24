"""Censoring date per row and the voltage filter of node loading."""

import pandas as pd

import gridqueue as G


def test_censoring_uses_the_rows_own_publication_date():
    # Node rows published later must not lengthen the censored times of applications.
    df = pd.DataFrame([
        {"_entity": "APPLICATION", "date_application": "2026-01-01", "date_published": "2026-06-30"},
        {"_entity": "APPLICATION", "date_application": "2026-01-01", "date_conditions": "2026-03-01",
         "date_published": "2026-06-30"},
        {"_entity": "NODE", "date_published": "2026-08-31"},
    ])
    pt = G.processing_time(df)
    assert pt.loc[0, "time_days"] == (pd.Timestamp("2026-06-30") - pd.Timestamp("2026-01-01")).days
    assert pt.loc[0, "event"] == 0 and pt.loc[1, "event"] == 1


def test_censoring_per_publisher_in_a_panel():
    df = pd.DataFrame([
        {"publisher": "A", "date_application": "2026-01-01", "date_published": "2026-03-31"},
        {"publisher": "B", "date_application": "2026-01-01", "date_published": "2026-06-30"},
    ]).assign(date_conditions=None)
    pt = G.processing_time(df)
    assert list(pt["time_days"]) == [89, 180]


def test_explicit_as_at_date_applies_to_every_row():
    df = pd.DataFrame([{"date_application": "2026-01-01", "date_published": "2026-03-31",
                        "date_conditions": None}])
    assert G.processing_time(df, as_at="2026-01-11")["time_days"].iloc[0] == 10


def test_node_loading_voltage_filter():
    rows = [
        {"_entity": "NODE", "node_id": "G1", "node_name": "Alfa", "_group_no": 1,
         "location_text": "Alfa", "capacity_available": 1000.0, "_direction": "generation"},
        {"_entity": "APPLICATION", "location_text": "Alfa", "capacity_injected": 3000.0,
         "process_status": "CONDITIONS_ISSUED", "voltage_level": "110 kV"},
        {"_entity": "APPLICATION", "location_text": "Alfa", "capacity_injected": 500.0,
         "process_status": "CONDITIONS_ISSUED", "voltage_level": "SN"},
    ]
    df = pd.DataFrame(rows)
    assigned = G.assign_to_nodes(df, G.station_node_map(df))
    assert G.node_loading(assigned, voltage="110")["loading"].iloc[0] == 3.0
    assert G.node_loading(assigned)["loading"].iloc[0] == 3.5


def test_split_editions_by_application_date():
    from gridqueue import examples as X
    a, b = X.synthetic_editions(120)
    eds = G.split_editions(pd.concat([b, a], ignore_index=True))
    assert [x for x, _ in eds] == ["2026-05-31", "2026-06-30"]
    assert [len(f) for _, f in eds] == [len(a), len(b)]


def test_split_editions_keeps_one_edition_with_node_rows_of_another_date():
    df = pd.DataFrame([
        {"_entity": "APPLICATION", "publisher": "P", "date_published": "2026-06-30"},
        {"_entity": "NODE", "publisher": "P", "date_published": "2026-08-31"},
    ])
    eds = G.split_editions(df)
    assert len(eds) == 1 and eds[0][0] is None


def test_split_editions_assigns_node_rows_to_the_nearest_edition():
    df = pd.DataFrame([
        {"_entity": "APPLICATION", "publisher": "P", "date_published": "2026-03-31"},
        {"_entity": "APPLICATION", "publisher": "P", "date_published": "2026-06-30"},
        {"_entity": "NODE", "publisher": "P", "date_published": "2026-07-15"},
    ])
    eds = dict(G.split_editions(df))
    assert len(eds["2026-03-31"]) == 1 and len(eds["2026-06-30"]) == 2


def test_parse_sources_names_an_unrecognised_file(tmp_path):
    p = tmp_path / "unknown.txt"
    p.write_text("nothing here", encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="unknown.txt"):
        G.parse_sources([p])
