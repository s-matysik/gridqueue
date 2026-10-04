"""Adapter: Stoen Operator Sp. z o.o. (PL, obszar Warszawy).

Trzy rozłączne zestawienia, po jednym na punkt obowiązku:
  * pkt 1 -- podmioty ubiegające się o przyłączenie  (10 kolumn, ~29 stron)
  * pkt 3 -- złożone wnioski o określenie warunków   (10 kolumn)
  * pkt 4 -- wydane odmowy określenia warunków       (11 kolumn)

Wszystkie trzy mają pełną siatkę liniową i DWUPOZIOMOWY nagłówek powtarzany na
każdej stronie (drugi poziom rozbija "Lokalizacja" na miejscowość/adres oraz
"Moc przyłączeniowa [kW]" na Podstawa/Rezerwa).  Typ zestawienia rozpoznajemy po
treści nagłówka, nie po nazwie pliku.

Uwaga merytoryczna do zapisania w manuskrypcie: Stoen NIE rozróżnia kierunku mocy.
Kolumna "Podstawa" jest mocą przyłączeniową niezależnie od tego, czy instalacja
jest odbiorcza czy wytwórcza.  Mapujemy ją na ``moc_pobierana`` (zgodnie ze
zmierzoną macierzą pokrycia) i deklarujemy brak rozróżnienia jako cechę źródła,
a nie jako lukę parsera.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..layout import detect_ruled_columns, extract_ruled_page
from ..schema import canonical_date, canonical_power_kw
from .base import Adapter, ParseResult, harmonize_klasa, harmonize_status, norm_text

_RE_LP = re.compile(r"^\d+\.?$")

LAYOUTS: dict[str, tuple[str, ...]] = {
    "podmioty": (
        "lp", "rodzaj_klienta", "miejscowosc", "adres", "moc_podstawa", "moc_rezerwa",
        "rodzaj_instalacji", "data_warunkow", "data_umowy", "data_energizacji",
    ),
    "wnioski": (
        "lp", "rodzaj_klienta", "miejscowosc", "adres", "moc_podstawa", "moc_rezerwa",
        "rodzaj_instalacji", "data_zlozenia", "data_zaliczki", "status_wniosku",
    ),
    "odmowy": (
        "lp", "rodzaj_klienta", "miejscowosc", "adres", "moc_podstawa", "moc_rezerwa",
        "rodzaj_instalacji", "data_zlozenia", "data_zaliczki", "powod_odmowy",
        "data_odmowy",
    ),
}


def detect_layout(header_text: str) -> Optional[str]:
    t = norm_text(header_text)
    if "odmowa przylaczenia" in t or "data odmowy" in t:
        return "odmowy"
    if "status rozpatrywania" in t:
        return "wnioski"
    if "data rozpoczecia" in t and "data zawarcia" in t:
        return "podmioty"
    return None


class StoenAdapter(Adapter):
    publisher = "Stoen Operator Sp. z o.o."
    jurisdiction = "PL"
    declared_fields = (
        "id_wniosku", "lokalizacja_tekst", "klasa_zasobu", "moc_pobierana",
        "moc_zarezerwowana", "status_procesu", "data_wniosku", "data_warunkow",
        "data_odmowy", "powod_odmowy", "data_umowy", "data_energizacji",
        "data_publikacji",
    )
    declared_extensions = {
        "_data_zaliczki": "data wpłaty zaliczki",
        "_rodzaj_podmiotu": "rodzaj klienta (osoba prawna / fizyczna)",
        "_miejscowosc": "miejscowość wydzielona z lokalizacji",
        "_adres": "adres wydzielony z lokalizacji",
        "_zestawienie": "który punkt art. 7 ust. 8l realizuje dany wiersz",
        "_rodzaj_instalacji_raw": "rodzaj instalacji tak, jak w dokumencie",
        "_status_raw": "status rozpatrywania wniosku tak, jak w dokumencie",
    }
    detect_patterns = (r"stoen",)

    def __init__(self, data_publikacji: Optional[str] = None):
        self.data_publikacji = data_publikacji

    # ------------------------------------------------------------------
    def parse(self, source) -> ParseResult:
        """``source``: ścieżka do jednego PDF albo lista ścieżek."""
        import pandas as pd

        sources = [source] if isinstance(source, (str, bytes)) or hasattr(source, "read") \
            else list(source)
        frames, reports = [], []
        for src in sources:
            f, r = self._parse_one(src)
            frames.append(f)
            reports.append(r)
        df = pd.concat(frames, ignore_index=True) if frames else self.blank_frame(0)
        report = {
            "publikujacy": self.publisher,
            "strategia_wydobycia": "ruled (siatka wektorowa), nagłówek dwupoziomowy",
            "dokumenty": reports,
            "n_wierszy": int(len(df)),
            "data_publikacji": self.data_publikacji,
        }
        return ParseResult(self.finalize(df, document="; ".join(map(str, sources))), report)

    # ------------------------------------------------------------------
    def _parse_one(self, src):
        import pandas as pd
        import pdfplumber

        rows: list[list[Optional[str]]] = []
        layout = None
        n_pages = 0
        with pdfplumber.open(src) as pdf:
            for page in pdf.pages:
                n_pages += 1
                geom = detect_ruled_columns(page)
                if geom.n_cols < 2:
                    continue
                tbl = extract_ruled_page(page, geom)
                if not tbl:
                    continue
                if layout is None:
                    layout = detect_layout(" ".join(
                        (c or "") for r in tbl[:2] for c in r))
                for row in tbl:
                    if row and _RE_LP.match((row[0] or "").strip()):
                        rows.append(row)
                if self.data_publikacji is None:
                    self.data_publikacji = _stan_na(page.extract_text() or "")
        if layout is None:
            raise ValueError(f"nie rozpoznano układu zestawienia Stoen w {src!r}")

        cols = LAYOUTS[layout]
        raw = pd.DataFrame(
            [(r + [None] * len(cols))[: len(cols)] for r in rows], columns=cols
        ).map(lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v)

        out = pd.DataFrame(index=raw.index)
        out["id_wniosku"] = [f"stoen:{layout}:{i + 1}" for i in range(len(raw))]
        miejsc = raw["miejscowosc"].fillna("")
        adres = raw["adres"].fillna("")
        out["lokalizacja_tekst"] = [
            ", ".join(x for x in (m.strip(), a.strip()) if x) or None
            for m, a in zip(miejsc, adres)
        ]
        out["klasa_zasobu"] = raw["rodzaj_instalacji"].map(harmonize_klasa)
        out["moc_pobierana"] = raw["moc_podstawa"].map(lambda v: canonical_power_kw(v, "kW"))
        out["moc_zarezerwowana"] = raw["moc_rezerwa"].map(lambda v: canonical_power_kw(v, "kW"))
        for c in ("data_wniosku", "data_warunkow", "data_odmowy", "data_umowy",
                  "data_energizacji"):
            out[c] = None
        if layout == "podmioty":
            out["data_warunkow"] = raw["data_warunkow"].map(canonical_date)
            out["data_umowy"] = raw["data_umowy"].map(canonical_date)
            out["data_energizacji"] = raw["data_energizacji"].map(canonical_date)
            _ok = lambda v: v is not None and not (isinstance(v, float) and v != v)
            out["status_procesu"] = [
                "PRZYLACZONY" if _ok(e) else ("UMOWA_OBOWIAZUJACA" if _ok(u) else
                                              ("WARUNKI_WYDANE" if _ok(w) else "NIEOKRESLONY"))
                for e, u, w in zip(out["data_energizacji"], out["data_umowy"],
                                   out["data_warunkow"])
            ]
            out["_status_raw"] = None
        elif layout == "wnioski":
            out["data_wniosku"] = raw["data_zlozenia"].map(canonical_date)
            out["_data_zaliczki"] = raw["data_zaliczki"].map(canonical_date)
            out["status_procesu"] = raw["status_wniosku"].map(harmonize_status)
            out["_status_raw"] = raw["status_wniosku"].replace("", None)
        else:  # odmowy
            out["data_wniosku"] = raw["data_zlozenia"].map(canonical_date)
            out["data_odmowy"] = raw["data_odmowy"].map(canonical_date)
            out["_data_zaliczki"] = raw["data_zaliczki"].map(canonical_date)
            out["powod_odmowy"] = raw["powod_odmowy"].replace("", None)
            out["status_procesu"] = "ODMOWA"
            out["_status_raw"] = raw["powod_odmowy"].replace("", None)
        out["data_publikacji"] = self.data_publikacji
        out["_rodzaj_podmiotu"] = raw["rodzaj_klienta"].replace("", None)
        out["_miejscowosc"] = miejsc.replace("", None)
        out["_adres"] = adres.replace("", None)
        out["_zestawienie"] = layout
        out["_rodzaj_instalacji_raw"] = raw["rodzaj_instalacji"].replace("", None)
        out["_lp_dokumentu"] = raw["lp"]

        return out, {
            "plik": str(src),
            "uklad": layout,
            "strony": n_pages,
            "n_kolumn_zrodlowych": len(cols),
            "n_wierszy": int(len(out)),
        }


def _stan_na(text: str) -> Optional[str]:
    m = re.search(r"[Ss]tan\s+na\s+(?:dzień\s+)?(\d{2}\.\d{2}\.\d{4})", text)
    return canonical_date(m.group(1)) if m else None
