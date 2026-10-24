"""Tests of the PSE S.A. and ENERGA-OPERATOR S.A. adapters.

The regression tests guard three defects found by MEASUREMENT against a visually
read reference set; each of them passed unnoticed through the unit tests, because
each produced an empty or an apparently sensible result rather than an exception.
"""

from __future__ import annotations

import datetime as dt
import os

import pandas as pd
import pytest

from gridqueue.adapters import _ptpiree as T
from gridqueue.adapters.base import harmonize_class, harmonize_status
from gridqueue.registry import REGISTRY, get_adapter

DATA = os.environ.get("GRIDQUEUE_SRC_DOCS", "src_docs")


def _ma(file_name: str) -> bool:
    return os.path.exists(os.path.join(DATA, file_name))


# --- registry ------------------------------------------------------------

def test_the_adapters_are_registered():
    assert "pl_pse" in REGISTRY
    assert "pl_energa" in REGISTRY
    assert get_adapter("pl_pse").publisher == "PSE S.A."
    assert get_adapter("pl_energa").publisher == "ENERGA-OPERATOR S.A."


# --- regression 1: empty identifier -------------------------------------

def test_blank_catches_nan():
    """``nan`` is truthy in Python, so ``if v`` is not enough."""
    assert T._blank(float("nan")) is True
    assert T._blank(None) is True
    assert T._blank("  ") is True
    assert T._blank("0") is False


def test_the_identifier_surrogate_works_when_the_id_is_empty():
    raw = pd.DataFrame({"object_id": [None, "X-1", float("nan")], "item_no": ["1.", "2.", None]})
    out = T.to_schema(raw, publisher_key="pse", publication_date="2026-08-31")
    assert out["application_id"].tolist() == ["pse:poz:1", "X-1", "pse:poz:3"]


# --- regression 2: class voltage level -----------------------------------

def test_a_class_voltage_level_carries_no_unit():
    """"SN" is a voltage class, not a number of kilovolts, so "SN kV" means nothing."""
    assert T._volt("SN") == "SN"
    assert T._volt("sn") == "SN"
    assert T._volt("110") == "110 kV"
    assert T._volt("110; 400") == "110; 400 kV"


# --- regression 3: date from a spreadsheet cell --------------------------

def test_dates_survive_the_timestamp_type():
    """openpyxl returns dates as Timestamp; ``str()`` on them lost every date."""
    raw = pd.DataFrame({
        "object_id": ["A"],
        "date_submission": [pd.Timestamp("2023-08-07")],
        "date_conditions": [dt.date(2024, 3, 18)],
        "date_energisation": ["po 30.06.2026"],
    })
    out = T.to_schema(raw, publisher_key="pse", publication_date=None)
    assert out["date_application"].iloc[0] == "2023-08-07"
    assert out["date_conditions"].iloc[0] == "2024-03-18"
    # an inequality is not a date: the schema field stays empty, the content is kept in an extension
    assert out["date_energisation"].iloc[0] is None
    assert out["_energisation_text"].iloc[0] == "po 30.06.2026"


# --- regression 4: status of a terminated agreement ----------------------

def test_a_terminated_agreement_is_not_an_effective_one():
    """The drop-down list of the shared template declares both statuses separately."""
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE rozwiązana") == "AGREEMENT_TERMINATED"
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE obowiązująca") == "AGREEMENT_IN_FORCE"
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE - obiekt przyłączony") == "CONNECTED"


def test_the_template_vocabulary_is_mapped_in_full():
    """Every value of the template drop-down list must yield a known token, not UNSPECIFIED."""
    statuses = [
        "WNIOSEK w weryfikacji", "WNIOSEK kompletny - w trakcie analizy technicznej i ekonomicznej",
        "WNIOSEK niekompletny", "WNIOSEK wycofany", "WARUNKI PRZYŁĄCZENIA wydane",
        "ODMOWA PRZYŁĄCZENIA", "WARUNKI PRZYŁĄCZENIA utraciły ważność",
        "UMOWA O PRZYŁĄCZENIE obowiązująca", "UMOWA O PRZYŁĄCZENIE rozwiązana",
        "UMOWA O PRZYŁĄCZENIE - obiekt przyłączony",
    ]
    for s in statuses:
        assert harmonize_status(s) != "UNSPECIFIED", s
    kinds = ["PV", "WIND", "MEE", "EJ", "ESP", "JBM", "JW", "MFW", "BG", "BGP",
               "LOAD", "OSD", "OSDn", "HYDRO", "SG", "OGW", "JS", "MIX"]
    for r in kinds:
        assert harmonize_class(r) != "UNSPECIFIED", r
    # the template declares BG as BLOK GAZOWY, a gas unit, not biogas, against the intuition of the name
    assert harmonize_class("BG") == "GAS"


# --- tests against the source documents ----------------------------------

@pytest.mark.skipif(not _ma("pse_art7_8l_20260831.xlsx"), reason="PSE document not present")
def test_pse_full_run():
    r = get_adapter("pl_pse").parse([
        os.path.join(DATA, "pse_art7_8l_20260831.xlsx"),
        os.path.join(DATA, "pse_lista_rozdzielni_brak_mozliwosci_20260204.xlsx"),
    ])
    f = r.frame
    assert (f["_entity"] == "APPLICATION").sum() == 876
    assert (f["_entity"] == "NODE").sum() == 69
    # footnote markers cut off from the content, not pasted into it
    assert not f["location_text"].astype(str).str.fullmatch(r"WYPM|CPKK").any()
    assert f["_footnotes"].notna().sum() == 69
    # PSE discloses point 2) as a NUMBER OF SLOTS, not a capacity, so the capacity field stays empty
    assert f.loc[f["_entity"] == "NODE", "capacity_available"].isna().all()
    assert f.loc[f["_entity"] == "NODE", "_free_slots"].notna().any()


@pytest.mark.skipif(not _ma("energa_wnioski_odmowy_20260831.pdf"), reason="Energa document not present")
def test_energa_full_run():
    r = get_adapter("pl_energa").parse([
        os.path.join(DATA, "energa_wnioski_odmowy_20260831.pdf"),
        os.path.join(DATA, "energa_moc_dostepna_odbiorcza_20260831.pdf"),
        os.path.join(DATA, "energa_moc_dostepna_wytworcza_20260831.pdf"),
    ])
    f = r.frame
    applications = f[f["_entity"] == "APPLICATION"]
    assert len(applications) == 5286
    # the ordinal numbers of the document reconstructed with no gaps and no repetitions
    item_no = pd.to_numeric(applications["_document_item_no"].str.rstrip("."), errors="coerce")
    assert item_no.notna().all()
    assert sorted(item_no.astype(int)) == list(range(1, 5287))
    # Energa is the first source in the panel that fills capacity_available
    nodes = f[f["_entity"] == "NODE"]
    assert len(nodes) == 96
    assert nodes["capacity_available"].notna().all()
    assert set(nodes["_direction"]) == {"demand", "generation"}
    # publication date from the DOCUMENT, not from the file name
    assert (applications["date_published"] == "2026-06-30").all()
