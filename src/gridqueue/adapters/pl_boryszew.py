"""Adapter: Boryszew Green Energy&Gas Sp. z o.o. (Elana, Toruń), a small industrial DSO.

The publication is a 4-page prose document with tables WITHOUT A LINE GRID.
There is no structure here to recover from lines; column boundaries exist only
as vertical corridors of white space. Therefore this adapter uses the BANDED strategy:
it detects corridors in the x-axis coverage distribution, and merges multi-line rows by
the ordinal number in the first column.

The document implements all four points of Art. 7(8l) in separate sections
numbered in the text. Sections 1, 3 and 4 are the APPLICATION entity and go into the panel.
Section 2 is the NODE entity (available connection capacity per station for 6 years);
we return it separately in the report, because it has no application core and must not
be mixed with application rows without breaking schema validation.

This case is significant in the corpus as the lower bound of disclosure quality:
the same statutory duty, published without any machine-readable structure.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..layout import detect_banded_columns, assign_words_to_columns, merge_continuation_rows
from ..schema import canonical_date, canonical_power_kw
from .base import Adapter, ParseResult, harmonize_class, harmonize_status, norm_text

_RE_LP = re.compile(r"^\d+\.$")
_SECTIONS = (
    (1, re.compile(r"^1\.\s*Podmioty ubiegaj", re.I)),
    (2, re.compile(r"^2\.\s*Warto", re.I)),
    (3, re.compile(r"^3\.\s*Z(ł|l)o(ż|z)one wnioski", re.I)),
    (4, re.compile(r"^4\.\s*Wydane odmowy", re.I)),
    (5, re.compile(r"^5\.\s*Spos(ó|o)b", re.I)),
)

LAYOUTS = {
    1: ("item_no", "entity_kind", "location", "capacity_mw", "installation_kind",
        "date_conditions", "date_agreement", "date_energisation"),
    3: ("item_no", "entity_kind", "location", "capacity_mw", "installation_kind",
        "date_submission", "date_advance_payment", "application_status"),
    4: ("item_no", "location", "capacity_mw", "installation_kind", "date_submission",
        "date_advance_payment", "refusal_reason"),
}


class BoryszewAdapter(Adapter):
    publisher = "Boryszew Green Energy&Gas Sp. z o.o."
    jurisdiction = "PL"
    declared_fields = (
        "application_id", "location_text", "resource_class", "capacity_withdrawn",
        "process_status", "date_application", "date_conditions", "date_agreement",
        "date_energisation", "date_published",
    )
    declared_extensions = {
        "_applicant_kind": "description of the connected entity (legal person/natural person)",
        "_date_advance_payment": "date of the deposit payment",
        "_section": "the point of Art. 7(8l) that the row originates from",
        "_installation_kind_raw": "type of installation exactly as in the document",
        "_status_raw": "processing status exactly as in the document",
        "_source_note": "publisher's annotation (e.g. 'Nie dotyczy / istniejące przyłącze')",
    }
    detect_patterns = (r"boryszew", r"elana")

    def __init__(self, publication_date: Optional[str] = None):
        self.publication_date = publication_date

    # ------------------------------------------------------------------
    def parse(self, source) -> ParseResult:
        import pandas as pd
        import pdfplumber

        sec_lines: dict[int, list[list[dict]]] = {k: [] for k, _ in _SECTIONS}
        nodes_lines: list[list[dict]] = []
        full_text_parts: list[str] = []
        current = 0
        n_pages = 0
        with pdfplumber.open(source) as pdf:
            for page in pdf.pages:
                n_pages += 1
                full_text_parts.append(page.extract_text() or "")
                lines = _group_lines(page.extract_words())
                for ln in lines:
                    txt = " ".join(w["text"] for w in ln).strip()
                    for num, rx in _SECTIONS:
                        if rx.match(txt):
                            current = num
                            break
                    else:
                        if current in sec_lines:
                            sec_lines[current].append(ln)
                        continue
        full_text = "\n".join(full_text_parts)
        if self.publication_date is None:
            self.publication_date = _update_date(full_text)

        frames = []
        per_section = {}
        for sec in (1, 3, 4):
            f, n_raw = self._section_frame(sec, sec_lines[sec])
            per_section[sec] = {"raw_rows": n_raw, "result_rows": int(len(f))}
            if len(f):
                frames.append(f)
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        nodes = _parse_nodes(sec_lines[2])

        report = {
            "publisher": self.publisher,
            "extraction_strategy": "banded (white-space corridors; no line grid)",
            "pages": n_pages,
            "sections": per_section,
            "n_rows": int(len(df)),
            "nodes_pt2": nodes,
            "publication_date": self.publication_date,
        }
        return ParseResult(self.finalize(df, document=str(source)), report)

    # ------------------------------------------------------------------
    def _section_frame(self, sec: int, lines: list[list[dict]]):
        import pandas as pd

        cols = LAYOUTS[sec]
        # data lines: starting at the first one beginning with an ordinal number
        start = next((i for i, ln in enumerate(lines)
                      if ln and _RE_LP.match(ln[0]["text"])), None)
        if start is None:
            return pd.DataFrame(), 0
        data_lines = lines[start:]
        words = [w for ln in data_lines for w in ln]
        geom = detect_banded_columns(words, min_gap=6.0)
        cells = assign_words_to_columns(words, geom)
        rows = merge_continuation_rows(cells, lambda r: bool(r) and bool(_RE_LP.match(r[0])))
        n_raw = len(rows)
        width = max((len(r) for r in rows), default=0)
        if width != len(cols):
            # fit to the declared layout: append excess columns to the last one
            rows = [_fit(r, len(cols)) for r in rows]
        raw = pd.DataFrame([(r + [""] * len(cols))[: len(cols)] for r in rows], columns=cols)
        raw = raw.map(lambda v: re.sub(r"\s+", " ", str(v)).strip())
        # discard placeholder rows ("brak" in all fields except Lp.)
        body = raw.drop(columns=["item_no"])
        keep = ~body.map(lambda v: norm_text(v) in {"", "brak", "-"}).all(axis=1)
        raw = raw[keep].reset_index(drop=True)
        if raw.empty:
            return pd.DataFrame(), n_raw

        out = pd.DataFrame(index=raw.index)
        out["application_id"] = [f"boryszew:pkt{sec}:{i + 1}" for i in range(len(raw))]
        out["location_text"] = raw["location"].replace("", None)
        out["resource_class"] = raw["installation_kind"].map(harmonize_class)
        out["capacity_withdrawn"] = raw["capacity_mw"].map(lambda v: canonical_power_kw(v, "MW"))
        out["date_published"] = self.publication_date
        out["_section"] = f"Art. 7(8l), item {sec}"
        out["_installation_kind_raw"] = raw["installation_kind"].replace("", None)
        if "entity_kind" in raw:
            out["_applicant_kind"] = raw["entity_kind"].replace("", None)
        if sec == 1:
            out["date_conditions"] = raw["date_conditions"].map(canonical_date)
            out["date_agreement"] = raw["date_agreement"].map(canonical_date)
            out["date_energisation"] = raw["date_energisation"].map(canonical_date)
            out["_source_note"] = raw["date_agreement"].replace("", None)
            _ok = lambda v: v is not None and not (isinstance(v, float) and v != v)
            out["process_status"] = [
                "CONNECTED" if _ok(e) else ("AGREEMENT_IN_FORCE" if _ok(u) else
                                              ("CONDITIONS_ISSUED" if _ok(w) else "UNSPECIFIED"))
                for e, u, w in zip(out["date_energisation"], out["date_agreement"],
                                   out["date_conditions"])
            ]
        elif sec == 3:
            out["date_application"] = raw["date_submission"].map(canonical_date)
            out["_date_advance_payment"] = raw["date_advance_payment"].map(canonical_date)
            out["process_status"] = raw["application_status"].map(harmonize_status)
            out["_status_raw"] = raw["application_status"].replace("", None)
        else:
            out["date_application"] = raw["date_submission"].map(canonical_date)
            out["refusal_reason"] = raw["refusal_reason"].replace("", None)
            out["process_status"] = "REFUSED"
        out["_document_item_no"] = raw["item_no"]
        return out, n_raw


def _fit(row: list[str], n: int) -> list[str]:
    if len(row) <= n:
        return row + [""] * (n - len(row))
    return row[: n - 1] + [" ".join(x for x in row[n - 1:] if x)]


def _group_lines(words, tol: float = 2.5) -> list[list[dict]]:
    ws = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    out: list[list[dict]] = []
    for w in ws:
        if out and abs(w["top"] - out[-1][0]["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in out]


def _update_date(text: str) -> Optional[str]:
    m = re.search(r"Data aktualizacji publikacji:\s*(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    months = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
              "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9,
              "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12}
    if m and m.group(2).lower() in months:
        return f"{m.group(3)}-{months[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def _parse_nodes(lines: list[list[dict]]) -> list[dict]:
    """Section 2 (item 2): available connection capacity per station for 6 years."""
    out: list[dict] = []
    years: list[str] = []
    for ln in lines:
        toks = [w["text"] for w in ln]
        if len(toks) >= 4 and all(re.fullmatch(r"20\d{2}", t) for t in toks):
            years = toks
            continue
        if toks and toks[0].upper().startswith("STACJA"):
            name_toks, vals = [], []
            for w in ln:
                if re.fullmatch(r"-?\d+(?:[.,]\d+)?", w["text"]) and w["x0"] > 260:
                    vals.append(w["text"])
                else:
                    name_toks.append(w["text"])
            rec = {"node_name": " ".join(name_toks),
                   "available_capacity_kw": {}}
            for i, v in enumerate(vals):
                y = years[i] if i < len(years) else f"kol{i}"
                rec["available_capacity_kw"][y] = canonical_power_kw(v, "MW")
            out.append(rec)
    return out
