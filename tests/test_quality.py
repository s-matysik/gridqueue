import pandas as pd

from gridqueue.quality import RULES, run_quality


def test_there_are_eight_rules_and_each_has_a_basis():
    assert len(RULES) == 8
    assert {r.code for r in RULES} == {f"R{i}" for i in range(1, 9)}
    for r in RULES:
        assert r.basis


def test_r1_date_monotonicity():
    df = pd.DataFrame({
        "date_application": ["2026-01-01", "2026-05-01"],
        "date_conditions": ["2026-02-01", "2026-04-01"],   # second row reversed
        "date_agreement": ["2026-03-01", None],
        "date_energisation": [None, None],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R1")).as_dict()
    assert rep["rules"][0]["violations"] == 1
    assert rep["rules"][0]["details"]["pairs"]["date_application>date_conditions"] == 1


def test_r2_two_year_validity_of_the_conditions():
    df = pd.DataFrame({
        "date_conditions": ["2022-01-01", "2024-01-01"],
        "_date_expiry": ["2025-06-01", "2026-01-01"],  # the first one is more than 2 years
        "date_agreement": [None, None],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R2")).as_dict()
    d = rep["rules"][0]["details"]
    assert d["expiry_later_than_2_years"] == 1
    assert d["checked_loss_dates"] == 2


def test_r3_status_against_the_dates():
    df = pd.DataFrame({
        "process_status": ["REFUSED", "REFUSED", "CONNECTED"],
        "date_refusal": ["2026-01-01", None, None],
        "date_agreement": [None, None, None],
        "date_energisation": [None, None, "2026-02-01"],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R3")).as_dict()
    assert rep["rules"][0]["violations"] == 1


def test_r4_unit_consistency_detects_mw_instead_of_kw():
    df = pd.DataFrame({"capacity_withdrawn": [700.0, 0.7, 0.0, None]})
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R4")).as_dict()
    assert rep["rules"][0]["violations"] == 1
    assert rep["rules"][0]["details"]["per_field"]["capacity_withdrawn"] == 1


def test_r5_value_ranges():
    df = pd.DataFrame({"date_application": ["1900-01-01", "2026-01-01"],
                       "capacity_withdrawn": [-5.0, 10.0]})
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R5")).as_dict()
    assert rep["rules"][0]["violations"] == 1


def test_r6_duplicates():
    df = pd.DataFrame({"application_id": ["a", "a", "a", "b"]})
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R6")).as_dict()
    assert rep["rules"][0]["violations"] == 2
    assert rep["rules"][0]["details"]["n_unique"] == 2
    assert rep["rules"][0]["details"]["max_multiplicity"] == 3


def test_r7_core_completeness():
    df = pd.DataFrame({
        "application_id": ["a", "b"], "location_text": ["x", None],
        "resource_class": ["PV", "PV"], "capacity_withdrawn": [1.0, 2.0],
        "process_status": ["REFUSED", "REFUSED"],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R7")).as_dict()
    assert rep["rules"][0]["violations"] == 1


def test_r8_controlled_vocabulary():
    df = pd.DataFrame({"resource_class": ["PV", "PANELE"], "process_status": ["REFUSED", "REFUSED"]})
    rep = run_quality(df, tuple(r for r in RULES if r.code == "R8")).as_dict()
    assert rep["rules"][0]["violations"] == 1


def test_the_rules_do_not_raise_on_an_empty_frame():
    rep = run_quality(pd.DataFrame()).as_dict()
    assert rep["n_rows"] == 0
    assert all(r["violations"] >= 0 for r in rep["rules"])


def test_r7_does_not_penalise_a_generating_application_for_missing_import_capacity():
    """R7 measures gaps in disclosure, not a property of the schema.

    Before version 1.0 the core required `capacity_withdrawn` unconditionally, so every
    purely generating application was counted as a violation. Here we pin the new
    contract: the violation is the absence of ANY capacity.
    """
    import pandas as pd

    shared = {"application_id": "X", "location_text": "Szczecin",
               "resource_class": "WIND", "process_status": "CONDITIONS_ISSUED"}
    df = pd.DataFrame([
        {**shared, "capacity_injected": 3000.0, "capacity_withdrawn": None},
        {**shared, "capacity_injected": None, "capacity_withdrawn": None},
    ])
    r7 = [x for x in run_quality(df).as_dict()["rules"] if x["code"] == "R7"][0]
    assert r7["violations"] == 1
    key = "APPLICATION/at least one of: capacity_withdrawn, capacity_injected"
    assert r7["details"]["per_field"][key] == 1


def test_r7_judges_a_node_by_the_node_requirements():
    import pandas as pd

    from gridqueue.schema import ENTITY_COLUMN

    df = pd.DataFrame([
        {ENTITY_COLUMN: "NODE", "node_id": "SE-1", "capacity_available": 0.0},
        {ENTITY_COLUMN: "NODE", "node_id": "SE-2"},
    ])
    r7 = [x for x in run_quality(df).as_dict()["rules"] if x["code"] == "R7"][0]
    assert r7["violations"] == 1
    assert r7["details"]["entity_rows"] == {"NODE": 2}


def test_as_frame_returns_one_row_per_rule():
    """The documentation promised this method and the package did not have it.

    The defect only came out when the Colab notebook was run, because the
    notebook used the public API exactly as the documentation describes it.
    """
    import pandas as pd

    from gridqueue import RULES, run_quality

    df = pd.DataFrame([{"application_id": "A", "location_text": "Szczecin",
                        "resource_class": "WIND", "process_status": "CONDITIONS_ISSUED",
                        "capacity_injected": 1000.0}])
    frame = run_quality(df).as_frame()
    assert list(frame.columns) == ["code", "name", "violations", "share"]
    assert len(frame) == len(RULES)
    assert frame["share"].between(0, 1).all()


def test_r3_does_not_fall_over_on_an_empty_publisher():
    """R3 has to work when the publisher column is present but empty.

    `groupby` skips a group whose value is empty, so a row without that
    annotation has no entry of its own in the dictionary of disclosed fields.
    Before the fix, the lookup by key raised `KeyError`, the rule returned -1,
    and the total number of violations in the whole report became negative: a
    silent defect, found only by running the package on a hand-built frame.
    """
    import pandas as pd

    from gridqueue import empty_frame, run_quality

    df = pd.DataFrame([
        {"application_id": "A-1", "location_text": "Stacja A", "resource_class": "LOAD",
         "process_status": "CONDITIONS_ISSUED", "capacity_withdrawn": 1000.0,
         "date_application": "2024-01-10", "date_conditions": "2024-05-10"},
    ]).reindex(columns=list(empty_frame().columns))
    assert df["publisher"].isna().all()

    report = run_quality(df).as_dict()
    r3 = [r for r in report["rules"] if r["code"] == "R3"][0]

    assert r3["violations"] >= 0, r3["details"]
    assert "error" not in r3["details"]
    assert report["violations_total"] >= 0
