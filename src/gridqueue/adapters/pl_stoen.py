"""Adapter: Stoen Operator Sp. z o.o. (PL, Warsaw area).

Three disjoint listings, one per item of the duty:
  * item 1: entities applying for connection (10 columns, ~29 pages)
  * item 3: submitted applications for determination of conditions (10 columns)
  * item 4: issued refusals to determine conditions (11 columns)

All three have a full ruled line grid and a TWO-LEVEL header repeated on
each page (the second level splits "Lokalizacja" into locality/address and
"Moc przyłączeniowa [kW]" into Podstawa/Rezerwa). We recognize the listing type by
the header content, not by the file name.

Substantive note to be recorded in the manuscript: Stoen does NOT distinguish the direction
of power. The "Podstawa" column is the connection capacity irrespective of whether the
installation is a demand-side or a generation installation. We map it to ``moc_pobierana``
(according to the measured coverage matrix) and declare the lack of distinction as a feature
of the source, not as a parser gap.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..layout import detect_ruled_columns, extract_ruled_page
from ..schema import canonical_date, canonical_power_kw
from .base import Adapter, ParseResult, harmonize_class, harmonize_status, norm_text

_RE_LP = re.compile(r"^\d+\.?$")

LAYOUTS: dict[str, tuple[str, ...]] = {
    "applicants": (
        "item_no", "customer_kind", "locality", "address", "capacity_base", "capacity_reserve",
        "installation_kind", "data_warunkow", "data_umowy", "data_energizacji",
    ),
    "applications": (
        "item_no", "customer_kind", "locality", "address", "capacity_base", "capacity_reserve",
        "installation_kind", "date_submission", "date_advance_payment", "application_status",
    ),
    "refusals": (
        "item_no", "customer_kind", "locality", "address", "capacity_base", "capacity_reserve",
        "installation_kind", "date_submission", "date_advance_payment", "powod_odmowy",
        "data_odmowy",
    ),
}


def detect_layout(header_text: str) -> Optional[str]:
    t = norm_text(header_text)
    if "odmowa przylaczenia" in t or "data odmowy" in t:
        return "refusals"
    if "status rozpatrywania" in t:
        return "applications"
    if "data rozpoczecia" in t and "data zawarcia" in t:
        return "applicants"
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
        "_data_zaliczki": "date the deposit was paid",
        "_rodzaj_podmiotu": "type of client (legal entity / natural person)",
        "_miejscowosc": "locality extracted from the location",
        "_adres": "address extracted from the location",
        "_zestawienie": "which item of Art. 7(8l) a given row implements",
        "_rodzaj_instalacji_raw": "installation type as given in the document",
        "_status_raw": "application processing status as given in the document",
    }
    detect_patterns = (r"stoen",)

    def __init__(self, publication_date: Optional[str] = None):
        self.publication_date = publication_date

    # ------------------------------------------------------------------
    def parse(self, source) -> ParseResult:
        """``source``: path to a single PDF or a list of paths."""
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
            "publisher": self.publisher,
            "extraction_strategy": "ruled (vector grid), two-level header",
            "documents": reports,
            "n_rows": int(len(df)),
            "publication_date": self.publication_date,
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
                if self.publication_date is None:
                    self.publication_date = _as_at(page.extract_text() or "")
        if layout is None:
            raise ValueError(f"could not recognize the Stoen listing layout in {src!r}")

        cols = LAYOUTS[layout]
        raw = pd.DataFrame(
            [(r + [None] * len(cols))[: len(cols)] for r in rows], columns=cols
        ).map(lambda v: re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v)

        out = pd.DataFrame(index=raw.index)
        out["id_wniosku"] = [f"stoen:{layout}:{i + 1}" for i in range(len(raw))]
        places = raw["locality"].fillna("")
        address = raw["address"].fillna("")
        out["lokalizacja_tekst"] = [
            ", ".join(x for x in (m.strip(), a.strip()) if x) or None
            for m, a in zip(places, address)
        ]
        out["klasa_zasobu"] = raw["installation_kind"].map(harmonize_class)
        out["moc_pobierana"] = raw["capacity_base"].map(lambda v: canonical_power_kw(v, "kW"))
        out["moc_zarezerwowana"] = raw["capacity_reserve"].map(lambda v: canonical_power_kw(v, "kW"))
        for c in ("data_wniosku", "data_warunkow", "data_odmowy", "data_umowy",
                  "data_energizacji"):
            out[c] = None
        if layout == "applicants":
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
        elif layout == "applications":
            out["data_wniosku"] = raw["date_submission"].map(canonical_date)
            out["_data_zaliczki"] = raw["date_advance_payment"].map(canonical_date)
            out["status_procesu"] = raw["application_status"].map(harmonize_status)
            out["_status_raw"] = raw["application_status"].replace("", None)
        else:  # odmowy
            out["data_wniosku"] = raw["date_submission"].map(canonical_date)
            out["data_odmowy"] = raw["data_odmowy"].map(canonical_date)
            out["_data_zaliczki"] = raw["date_advance_payment"].map(canonical_date)
            out["powod_odmowy"] = raw["powod_odmowy"].replace("", None)
            out["status_procesu"] = "ODMOWA"
            out["_status_raw"] = raw["powod_odmowy"].replace("", None)
        out["data_publikacji"] = self.publication_date
        out["_rodzaj_podmiotu"] = raw["customer_kind"].replace("", None)
        out["_miejscowosc"] = places.replace("", None)
        out["_adres"] = address.replace("", None)
        out["_zestawienie"] = layout
        out["_rodzaj_instalacji_raw"] = raw["installation_kind"].replace("", None)
        out["_lp_dokumentu"] = raw["item_no"]

        return out, {
            "file_name": str(src),
            "layout": layout,
            "pages": n_pages,
            "n_source_columns": len(cols),
            "n_rows": int(len(out)),
        }


def _as_at(text: str) -> Optional[str]:
    m = re.search(r"[Ss]tan\s+na\s+(?:dzień\s+)?(\d{2}\.\d{2}\.\d{4})", text)
    return canonical_date(m.group(1)) if m else None
