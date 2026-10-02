"""Adapter: TAURON Dystrybucja S.A. (PL).

Dokument: "Informacja o przyłączanych obiektach i wydanych odmowach", PDF ~99 stron,
tabela z pełną siatką liniową, 27 kolumn, nagłówek tylko na pierwszej stronie,
legenda rodzajów instalacji na stronie ostatniej.

Kluczowa własność: daty SĄ w dokumencie rozdzielone na osobne kolumny (złożenie,
zaliczka, warunki, odmowa, utrata ważności, umowa, energizacja, rozwiązanie,
wygaśnięcie).  Poprzedni parser regexowy zlewał je w jedno pole zbiorcze -- nie
dlatego, że dokument ich nie rozdziela, tylko dlatego, że spłaszczony tekst gubi
granice pustych komórek.  Wydobycie po siatce odzyskuje je wprost.

Lokalizacja jest podawana jako WEWNĘTRZNY KOD STACJI (np. "SKB3", "RCB4").
Słownika kodów TAURON nie publikuje, więc rozwiązywacz lokalizacji zwraca dla
tego publikującego brak z jawnym powodem -- nie zgadujemy.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..layout import ColumnGeometry, detect_ruled_columns, extract_ruled_page
from ..schema import canonical_date, canonical_power_kw
from .base import Adapter, ParseResult, harmonize_klasa, harmonize_status, norm_text

#: kolejność kolumn w dokumencie TAURONA (indeks -> znaczenie źródłowe)
COLUMNS = (
    "lp", "id_obiektu", "nazwa_osd", "rodzaj_podmiotu", "lokalizacja_stacja",
    "poziom_napiecia", "wiele_miejsc", "rodzaj_instalacji",
    "moc_wprowadzana_mw", "moc_pobierana_mw",
    "mz_pv_mw", "mz_fw_mw", "mz_mee_rozl_mw", "mz_mee_lad_mw", "mz_odb_mw", "mz_inne_mw",
    "status_etapu", "data_zlozenia", "data_zaliczki", "data_warunkow",
    "data_odmowy", "uzasadnienie_odmowy", "data_utraty_waznosci",
    "data_umowy", "data_energizacji", "data_rozwiazania", "data_wygasniecia",
)

_RE_LP = re.compile(r"^\d+$")
_RE_LEGEND = re.compile(r"^([A-ZĘÓŁŚŻŹĆŃ]{2,4})\s*[-–]\s*(.+)$")


class TauronAdapter(Adapter):
    publisher = "TAURON Dystrybucja S.A."
    jurisdiction = "PL"
    declared_fields = (
        "id_wniosku", "id_wezla", "lokalizacja_tekst", "poziom_napiecia",
        "klasa_zasobu", "moc_wprowadzana", "moc_pobierana", "status_procesu",
        "data_wniosku", "data_warunkow", "data_odmowy", "powod_odmowy",
        "data_umowy", "data_energizacji", "data_publikacji",
    )
    declared_extensions = {
        "_data_zaliczki": "data wpłaty zaliczki na poczet opłaty za przyłączenie",
        "_data_utraty_waznosci": "data utraty ważności lub rezygnacji z warunków",
        "_data_rozwiazania": "data rozwiązania/wypowiedzenia/odstąpienia od umowy",
        "_data_wygasniecia": "data wygaśnięcia umowy z mocy prawa",
        "_wiele_miejsc": "wniosek obejmuje wiele miejsc przyłączenia lub poziomów napięcia",
        "_rodzaj_podmiotu": "osoba prawna / osoba fizyczna",
        "_moc_zainstalowana_kw": "moc zainstalowana w rozbiciu na technologie (suma)",
        "_rodzaj_instalacji_raw": "oznaczenie rodzaju instalacji tak, jak w dokumencie",
        "_status_raw": "status etapu projektu tak, jak w dokumencie",
    }
    detect_patterns = (r"tauron", r"TAURON Dystrybucja")

    def __init__(self, data_publikacji: Optional[str] = None):
        self.data_publikacji = data_publikacji

    # ------------------------------------------------------------------
    def parse(self, source) -> ParseResult:
        import pandas as pd
        import pdfplumber

        raw_rows: list[list[Optional[str]]] = []
        legend: dict[str, str] = {}
        stats = {"strony": 0, "strony_bez_siatki": [], "geometrie": set()}
        with pdfplumber.open(source) as pdf:
            if self.data_publikacji is None:
                self.data_publikacji = _cover_date(pdf.pages[0].extract_text() or "")
            modal_geom: Optional[ColumnGeometry] = None
            for page in pdf.pages:
                stats["strony"] += 1
                geom = detect_ruled_columns(page)
                if geom.n_cols < 2:
                    stats["strony_bez_siatki"].append(page.page_number)
                    legend.update(_parse_legend(page.extract_text() or ""))
                    continue
                if modal_geom is None:
                    modal_geom = geom
                stats["geometrie"].add(tuple(round(x, 0) for x in geom.bounds))
                for row in extract_ruled_page(page, geom):
                    if row and _RE_LP.match((row[0] or "").strip()):
                        raw_rows.append(row)

        n_expected = len(COLUMNS)
        raw = pd.DataFrame(
            [(r + [None] * n_expected)[:n_expected] for r in raw_rows], columns=COLUMNS
        )
        raw = raw.map(lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v)

        out = pd.DataFrame(index=raw.index)
        out["id_wniosku"] = raw["id_obiektu"].replace("", None)
        out["id_wezla"] = raw["lokalizacja_stacja"].replace("", None)
        out["lokalizacja_tekst"] = raw["lokalizacja_stacja"].replace("", None)
        out["poziom_napiecia"] = raw["poziom_napiecia"].replace("", None)
        out["klasa_zasobu"] = raw["rodzaj_instalacji"].map(harmonize_klasa)
        out["moc_wprowadzana"] = raw["moc_wprowadzana_mw"].map(
            lambda v: canonical_power_kw(v, "MW"))
        out["moc_pobierana"] = raw["moc_pobierana_mw"].map(
            lambda v: canonical_power_kw(v, "MW"))
        out["status_procesu"] = raw["status_etapu"].map(harmonize_status)
        for dst, src in (
            ("data_wniosku", "data_zlozenia"),
            ("data_warunkow", "data_warunkow"),
            ("data_odmowy", "data_odmowy"),
            ("data_umowy", "data_umowy"),
            ("data_energizacji", "data_energizacji"),
        ):
            out[dst] = raw[src].map(canonical_date)
        out["powod_odmowy"] = raw["uzasadnienie_odmowy"].replace("", None)
        out["data_publikacji"] = self.data_publikacji

        # rozszerzenia deklarowane
        out["_data_zaliczki"] = raw["data_zaliczki"].map(canonical_date)
        out["_data_utraty_waznosci"] = raw["data_utraty_waznosci"].map(canonical_date)
        out["_data_rozwiazania"] = raw["data_rozwiazania"].map(canonical_date)
        out["_data_wygasniecia"] = raw["data_wygasniecia"].map(canonical_date)
        out["_wiele_miejsc"] = raw["wiele_miejsc"].replace("", None)
        out["_rodzaj_podmiotu"] = raw["rodzaj_podmiotu"].replace("", None)
        mz_cols = ["mz_pv_mw", "mz_fw_mw", "mz_mee_rozl_mw", "mz_mee_lad_mw",
                   "mz_odb_mw", "mz_inne_mw"]
        mz = raw[mz_cols].map(lambda v: canonical_power_kw(v, "MW"))
        out["_moc_zainstalowana_kw"] = mz.sum(axis=1, min_count=1)
        out["_rodzaj_instalacji_raw"] = raw["rodzaj_instalacji"].replace("", None)
        out["_status_raw"] = raw["status_etapu"].replace("", None)
        out["_lp_dokumentu"] = raw["lp"]

        report = {
            "publikujacy": self.publisher,
            "strategia_wydobycia": "ruled (siatka wektorowa)",
            "strony": stats["strony"],
            "strony_bez_siatki": stats["strony_bez_siatki"],
            "n_geometrii_kolumn": len(stats["geometrie"]),
            "n_kolumn_zrodlowych": n_expected,
            "n_wierszy": int(len(out)),
            "legenda_rodzajow": legend,
            "data_publikacji": self.data_publikacji,
        }
        return ParseResult(self.finalize(out, document=str(source)), report)


def _cover_date(text: str) -> Optional[str]:
    m = re.search(r"Stan\s+na\s+(\d{2}\.\d{2}\.\d{4})", text)
    return canonical_date(m.group(1)) if m else None


def _parse_legend(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _RE_LEGEND.match(line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out
