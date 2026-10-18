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
from gridqueue.adapters.base import harmonize_klasa, harmonize_status
from gridqueue.registry import REGISTRY, get_adapter

DANE = os.environ.get("GRIDQUEUE_SRC_DOCS", "src_docs")


def _ma(plik: str) -> bool:
    return os.path.exists(os.path.join(DANE, plik))


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
    raw = pd.DataFrame({"id_obiektu": [None, "X-1", float("nan")], "lp": ["1.", "2.", None]})
    out = T.to_schema(raw, publisher_key="pse", data_publikacji="2026-08-31")
    assert out["id_wniosku"].tolist() == ["pse:poz:1", "X-1", "pse:poz:3"]


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
        "id_obiektu": ["A"],
        "data_zlozenia": [pd.Timestamp("2023-08-07")],
        "data_warunkow": [dt.date(2024, 3, 18)],
        "data_energizacji": ["po 30.06.2026"],
    })
    out = T.to_schema(raw, publisher_key="pse", data_publikacji=None)
    assert out["data_wniosku"].iloc[0] == "2023-08-07"
    assert out["data_warunkow"].iloc[0] == "2024-03-18"
    # an inequality is not a date: the schema field stays empty, the content is kept in an extension
    assert out["data_energizacji"].iloc[0] is None
    assert out["_energizacja_tekst"].iloc[0] == "po 30.06.2026"


# --- regression 4: status of a terminated agreement ----------------------

def test_a_terminated_agreement_is_not_an_effective_one():
    """The drop-down list of the shared template declares both statuses separately."""
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE rozwiązana") == "UMOWA_ROZWIAZANA"
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE obowiązująca") == "UMOWA_OBOWIAZUJACA"
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE - obiekt przyłączony") == "PRZYLACZONY"


def test_the_template_vocabulary_is_mapped_in_full():
    """Every value of the template drop-down list must yield a known token, not NIEOKRESLONY."""
    statusy = [
        "WNIOSEK w weryfikacji", "WNIOSEK kompletny - w trakcie analizy technicznej i ekonomicznej",
        "WNIOSEK niekompletny", "WNIOSEK wycofany", "WARUNKI PRZYŁĄCZENIA wydane",
        "ODMOWA PRZYŁĄCZENIA", "WARUNKI PRZYŁĄCZENIA utraciły ważność",
        "UMOWA O PRZYŁĄCZENIE obowiązująca", "UMOWA O PRZYŁĄCZENIE rozwiązana",
        "UMOWA O PRZYŁĄCZENIE - obiekt przyłączony",
    ]
    for s in statusy:
        assert harmonize_status(s) != "NIEOKRESLONY", s
    rodzaje = ["PV", "FW", "MEE", "EJ", "ESP", "JBM", "JW", "MFW", "BG", "BGP",
               "ODB", "OSD", "OSDn", "EW", "SG", "OGW", "JS", "MIX"]
    for r in rodzaje:
        assert harmonize_klasa(r) != "NIEOKRESLONA", r
    # the template declares BG as BLOK GAZOWY, a gas unit, not biogas, against the intuition of the name
    assert harmonize_klasa("BG") == "GAZ"


# --- tests against the source documents ----------------------------------

@pytest.mark.skipif(not _ma("pse_art7_8l_20260831.xlsx"), reason="PSE document not present")
def test_pse_full_run():
    r = get_adapter("pl_pse").parse([
        os.path.join(DANE, "pse_art7_8l_20260831.xlsx"),
        os.path.join(DANE, "pse_lista_rozdzielni_brak_mozliwosci_20260204.xlsx"),
    ])
    f = r.frame
    assert (f["_encja"] == "WNIOSEK").sum() == 876
    assert (f["_encja"] == "WEZEL").sum() == 69
    # footnote markers cut off from the content, not pasted into it
    assert not f["lokalizacja_tekst"].astype(str).str.fullmatch(r"WYPM|CPKK").any()
    assert f["_przypisy"].notna().sum() == 69
    # PSE discloses point 2) as a NUMBER OF SLOTS, not a capacity, so the capacity field stays empty
    assert f.loc[f["_encja"] == "WEZEL", "moc_dostepna"].isna().all()
    assert f.loc[f["_encja"] == "WEZEL", "_liczba_dostepnych_miejsc"].notna().any()


@pytest.mark.skipif(not _ma("energa_wnioski_odmowy_20260831.pdf"), reason="Energa document not present")
def test_energa_full_run():
    r = get_adapter("pl_energa").parse([
        os.path.join(DANE, "energa_wnioski_odmowy_20260831.pdf"),
        os.path.join(DANE, "energa_moc_dostepna_odbiorcza_20260831.pdf"),
        os.path.join(DANE, "energa_moc_dostepna_wytworcza_20260831.pdf"),
    ])
    f = r.frame
    wnioski = f[f["_encja"] == "WNIOSEK"]
    assert len(wnioski) == 5286
    # the ordinal numbers of the document reconstructed with no gaps and no repetitions
    lp = pd.to_numeric(wnioski["_lp_dokumentu"].str.rstrip("."), errors="coerce")
    assert lp.notna().all()
    assert sorted(lp.astype(int)) == list(range(1, 5287))
    # Energa is the first source in the panel that fills moc_dostepna
    wezly = f[f["_encja"] == "WEZEL"]
    assert len(wezly) == 96
    assert wezly["moc_dostepna"].notna().all()
    assert set(wezly["_kierunek"]) == {"odbiorcza", "wytworcza"}
    # publication date from the DOCUMENT, not from the file name
    assert (wnioski["data_publikacji"] == "2026-06-30").all()
