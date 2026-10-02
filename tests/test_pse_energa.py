"""Testy adapterów PSE S.A. i ENERGA-OPERATOR S.A.

Testy regresyjne pilnują trzech defektów wykrytych POMIAREM na wzorcu odczytanym
wzrokowo -- każdy z nich przechodził niezauważony przez testy jednostkowe, bo
każdy dawał wynik pusty albo pozornie sensowny, nie wyjątek.
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


# --- rejestr -------------------------------------------------------------

def test_adaptery_zarejestrowane():
    assert "pl_pse" in REGISTRY
    assert "pl_energa" in REGISTRY
    assert get_adapter("pl_pse").publisher == "PSE S.A."
    assert get_adapter("pl_energa").publisher == "ENERGA-OPERATOR S.A."


# --- regresja 1: pusty identyfikator ------------------------------------

def test_blank_lapie_nan():
    """``nan`` jest w Pythonie prawdziwe -- ``if v`` nie wystarcza."""
    assert T._blank(float("nan")) is True
    assert T._blank(None) is True
    assert T._blank("  ") is True
    assert T._blank("0") is False


def test_zastepnik_identyfikatora_dziala_gdy_id_puste():
    raw = pd.DataFrame({"id_obiektu": [None, "X-1", float("nan")], "lp": ["1.", "2.", None]})
    out = T.to_schema(raw, publisher_key="pse", data_publikacji="2026-08-31")
    assert out["id_wniosku"].tolist() == ["pse:poz:1", "X-1", "pse:poz:3"]


# --- regresja 2: poziom napięcia klasowy --------------------------------

def test_poziom_napiecia_klasowy_bez_jednostki():
    """"SN" to klasa napięcia, nie liczba kilowoltów -- "SN kV" nic nie znaczy."""
    assert T._volt("SN") == "SN"
    assert T._volt("sn") == "SN"
    assert T._volt("110") == "110 kV"
    assert T._volt("110; 400") == "110; 400 kV"


# --- regresja 3: data z komórki arkusza ---------------------------------

def test_daty_przechodza_przez_typ_timestamp():
    """openpyxl zwraca daty jako Timestamp; ``str()`` na nich gubił wszystkie daty."""
    raw = pd.DataFrame({
        "id_obiektu": ["A"],
        "data_zlozenia": [pd.Timestamp("2023-08-07")],
        "data_warunkow": [dt.date(2024, 3, 18)],
        "data_energizacji": ["po 30.06.2026"],
    })
    out = T.to_schema(raw, publisher_key="pse", data_publikacji=None)
    assert out["data_wniosku"].iloc[0] == "2023-08-07"
    assert out["data_warunkow"].iloc[0] == "2024-03-18"
    # nierówność nie jest datą: pole schematu puste, treść zachowana w rozszerzeniu
    assert out["data_energizacji"].iloc[0] is None
    assert out["_energizacja_tekst"].iloc[0] == "po 30.06.2026"


# --- regresja 4: status rozwiązanej umowy -------------------------------

def test_umowa_rozwiazana_nie_jest_obowiazujaca():
    """Lista rozwijana wspólnego szablonu deklaruje oba statusy osobno."""
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE rozwiązana") == "UMOWA_ROZWIAZANA"
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE obowiązująca") == "UMOWA_OBOWIAZUJACA"
    assert harmonize_status("UMOWA O PRZYŁĄCZENIE - obiekt przyłączony") == "PRZYLACZONY"


def test_slownik_szablonu_odwzorowany_w_calosci():
    """Każda wartość listy rozwijanej szablonu musi dać znany token, nie NIEOKRESLONY."""
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
    # szablon deklaruje BG jako BLOK GAZOWY, nie biogaz -- wbrew intuicji nazwy
    assert harmonize_klasa("BG") == "GAZ"


# --- testy na dokumentach źródłowych ------------------------------------

@pytest.mark.skipif(not _ma("pse_art7_8l_20260831.xlsx"), reason="brak dokumentu PSE")
def test_pse_pelny_przebieg():
    r = get_adapter("pl_pse").parse([
        os.path.join(DANE, "pse_art7_8l_20260831.xlsx"),
        os.path.join(DANE, "pse_lista_rozdzielni_brak_mozliwosci_20260204.xlsx"),
    ])
    f = r.frame
    assert (f["_encja"] == "WNIOSEK").sum() == 876
    assert (f["_encja"] == "WEZEL").sum() == 69
    # odnośniki przypisów odcięte od treści, nie wklejone w nią
    assert not f["lokalizacja_tekst"].astype(str).str.fullmatch(r"WYPM|CPKK").any()
    assert f["_przypisy"].notna().sum() == 69
    # PSE ujawnia pkt 2) jako LICZBĘ MIEJSC, nie moc -- pole mocy zostaje puste
    assert f.loc[f["_encja"] == "WEZEL", "moc_dostepna"].isna().all()
    assert f.loc[f["_encja"] == "WEZEL", "_liczba_dostepnych_miejsc"].notna().any()


@pytest.mark.skipif(not _ma("energa_wnioski_odmowy_20260831.pdf"), reason="brak dokumentu Energi")
def test_energa_pelny_przebieg():
    r = get_adapter("pl_energa").parse([
        os.path.join(DANE, "energa_wnioski_odmowy_20260831.pdf"),
        os.path.join(DANE, "energa_moc_dostepna_odbiorcza_20260831.pdf"),
        os.path.join(DANE, "energa_moc_dostepna_wytworcza_20260831.pdf"),
    ])
    f = r.frame
    wnioski = f[f["_encja"] == "WNIOSEK"]
    assert len(wnioski) == 5286
    # liczby porządkowe dokumentu odtworzone bez luk i bez powtórzeń
    lp = pd.to_numeric(wnioski["_lp_dokumentu"].str.rstrip("."), errors="coerce")
    assert lp.notna().all()
    assert sorted(lp.astype(int)) == list(range(1, 5287))
    # Energa jest pierwszym źródłem w panelu wypełniającym moc_dostepna
    wezly = f[f["_encja"] == "WEZEL"]
    assert len(wezly) == 96
    assert wezly["moc_dostepna"].notna().all()
    assert set(wezly["_kierunek"]) == {"odbiorcza", "wytworcza"}
    # data publikacji z DOKUMENTU, nie z nazwy pliku
    assert (wnioski["data_publikacji"] == "2026-06-30").all()
