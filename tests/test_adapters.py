import json

import pandas as pd
import pytest

from gridqueue.adapters.base import Adapter, harmonize_class, harmonize_status, norm_text
from gridqueue.adapters.pl_stoen import detect_layout
from gridqueue.adapters.uk_nationalgrid import NationalGridAdapter, _as_bool
from gridqueue.cli import build_parser, main
from gridqueue.registry import REGISTRY, declarations, get_adapter
from gridqueue.schema import FIELDS, META_COLUMNS


def test_the_registry_has_nine_adapters_in_five_jurisdictions():
    assert set(REGISTRY) == {"pl_tauron", "pl_stoen", "pl_boryszew", "pl_pse", "pl_energa",
                             "uk_nationalgrid", "pt_eredes", "es_edistribucion",
                             "ie_esbnetworks"}
    assert {get_adapter(k).jurisdiction for k in REGISTRY} == {"PL", "UK", "PT", "ES", "IE"}


def test_field_declarations_are_a_subset_of_the_schema():
    for d in declarations():
        assert set(d["declared_fields"]) <= set(FIELDS), d["publisher"]
        assert all(k.startswith("_") for k in d["extensions"]), d["publisher"]


def test_every_adapter_declares_the_core_of_ITS_OWN_entity():
    """The core is conditional per entity, so this check has to be conditional too.

    The previous version required the core of the APPLICATION entity from EVERY
    adapter. This is the same category error that was fixed in rule R7: a
    publisher carrying out point 2 of the duty alone discloses nodes, not
    applications, so it has neither an application identifier nor its capacity.
    The Portuguese adapter showed that the test carried an outdated contract.
    """
    application_core = {"application_id", "location_text", "resource_class", "process_status"}
    node_core = {"node_id"}
    for key in REGISTRY:
        fields = set(get_adapter(key).declared_fields)
        application = application_core <= fields
        node = node_core <= fields and bool({"capacity_available", "constraint_flag"} & fields)
        assert application or node, key


def test_get_adapter_rejects_an_unknown_key():
    with pytest.raises(KeyError):
        get_adapter("pl_nonexistent")


@pytest.mark.parametrize("raw,expected", [
    ("PV", "PV"), ("Elektrownia fotowoltaiczna", "PV"), ("Solar", "PV"),
    ("WIND", "WIND"), ("Wind", "WIND"), ("MEE", "BESS"), ("Magazyn energii", "BESS"),
    ("BESS", "BESS"), ("LOAD", "LOAD"), ("ODB", "LOAD"), ("FW", "WIND"), ("Instalacja odbiorcza", "LOAD"),
    ("Demand", "LOAD"), ("OSDn", "GRID"), ("Stacja transformatorowa", "GRID"),
    ("", "UNSPECIFIED"),
])
def test_harmonize_class(raw, expected):
    assert harmonize_class(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("UMOWA O PRZYŁĄCZENIE obowiązująca", "AGREEMENT_IN_FORCE"),
    ("WARUNKI PRZYŁĄCZENIA wydane", "CONDITIONS_ISSUED"),
    ("WARUNKI PRZYŁĄCZENIA utraciły ważność", "CONDITIONS_EXPIRED"),
    ("WNIOSEK niekompletny", "APPLICATION_INCOMPLETE"),
    ("WNIOSEK wycofany", "APPLICATION_WITHDRAWN"),
    ("OBIEKT przyłączony", "CONNECTED"),
    ("Accepted not yet Connected", "AGREEMENT_IN_FORCE"),
    ("Recently Connected", "CONNECTED"),
    ("", "UNSPECIFIED"),
])
def test_harmonize_status(raw, expected):
    assert harmonize_status(raw) == expected


def test_norm_text_strips_diacritics():
    assert norm_text("Świętego  Wincentego\n") == "swietego wincentego"


def test_detect_layout_stoen():
    assert detect_layout("Lp. Rodzaj klienta ... Status rozpatrywania wniosku") == "applications"
    assert detect_layout("... Odmowa przyłączenia Data odmowy") == "refusals"
    assert detect_layout("... Data zawarcia umowy Data rozpoczęcia dostarczania") == "applicants"
    assert detect_layout("cokolwiek innego") is None


def test_finalize_sets_the_column_order_and_the_metadata():
    a = get_adapter("pl_tauron")
    df = a.finalize(pd.DataFrame({"application_id": ["x"], "_extra": [1]}), document="d.pdf")
    assert list(df.columns)[:21] == list(FIELDS)
    assert list(df.columns)[21:24] == list(META_COLUMNS)
    assert df["publisher"].iloc[0] == "TAURON Dystrybucja S.A."
    assert df["jurisdiction"].iloc[0] == "PL"
    assert df["source_document"].iloc[0] == "d.pdf"


def test_as_bool():
    assert _as_bool("True") is True and _as_bool("false") is False
    assert _as_bool(None) is None and _as_bool("maybe") is None


def test_nationalgrid_maps_a_frame_with_no_network_access():
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
    assert r["application_id"] == "nged:241:1:PA"
    assert r["capacity_injected"] == 20000.0
    assert r["capacity_withdrawn"] == 50.0
    assert r["resource_class"] == "PV"
    assert r["process_status"] == "AGREEMENT_IN_FORCE"
    assert bool(r["constraint_flag"]) is True
    assert r["queue_position"] == 99.0
    assert r["jurisdiction"] == "UK"


def test_the_base_adapter_does_not_implement_parse():
    with pytest.raises(NotImplementedError):
        Adapter().parse("x")


def test_cli_schema_and_adapters(capsys, tmp_path):
    assert main(["schema", "--out", str(tmp_path / "s.csv")]) == 0
    assert len(pd.read_csv(tmp_path / "s.csv")) == 21
    capsys.readouterr()
    assert main(["adapters"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == len(REGISTRY)


def test_cli_validate_and_export(tmp_path, capsys):
    p = tmp_path / "a.csv"
    pd.DataFrame({
        "application_id": ["a", "b"], "location_text": ["x", "y"],
        "resource_class": ["PV", "PV"], "capacity_withdrawn": [1.0, 2.0],
        "process_status": ["REFUSED", "REFUSED"], "date_refusal": ["2026-01-01", "2026-01-02"],
    }).to_csv(p, index=False)
    assert main(["validate", str(p), "--out", str(tmp_path / "rep.json")]) == 0
    rep = json.loads((tmp_path / "rep.json").read_text())
    assert rep["schema"]["n_rows"] == 2
    assert rep["quality"]["n_rules"] == 8
    out = tmp_path / "panel.parquet"
    assert main(["export", str(p), str(p), "--out", str(out), "--only-schema"]) == 0
    assert len(pd.read_parquet(out)) == 4


def test_the_cli_parser_requires_a_subcommand():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])
