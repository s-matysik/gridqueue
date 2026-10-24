"""Extraction based on PAGE LAYOUT, not on regular expressions.

The regular expression operates on text flattened by the PDF extractor: word order
is drawing order, and column boundaries are reconstructed from spaces. When a
cell is empty or contains a space, adjacent fields merge together and the value
soaks into the wrong field. In the previous version of the TAURON parser this
affected 767 of 10,559 rows (7.3%).

Here we do the opposite: we read the POSITION of each word (x0, x1, top, bottom)
and first establish the geometry of the table, and only then assign words to
cells. Two strategies, chosen according to what the document actually contains:

  RULED  : the document has grid lines (vertical edges of rectangles). Column
           boundaries are drawn DIRECTLY by the document's producer; an empty
           cell cannot merge with its neighbour because it is fenced off by a
           line.
  BANDED : the document has no lines. Boundaries are derived from the distribution
           of x-axis coverage by the words: a column is a contiguous interval
           covered by words, a boundary is a vertical corridor of whitespace
           present across the entire height of the table block.

The choice of pdfplumber over camelot/tabula: camelot in lattice mode requires
Ghostscript and conversion to raster (column boundaries reconstructed from an
image, not from vectors), tabula requires a JVM. pdfplumber gives direct access
to word coordinates and vector edges from pdfminer.six, so a column boundary is
a number from the file, not the result of edge detection on a bitmap, which is
exactly the property on which this tool's thesis depends.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Sequence

__all__ = [
    "ColumnGeometry",
    "detect_ruled_columns",
    "detect_banded_columns",
    "extract_ruled_page",
    "assign_words_to_columns",
    "merge_continuation_rows",
    "ShiftAudit",
    "audit_column_shift",
]


# --------------------------------------------------------------------------
# column geometry
# --------------------------------------------------------------------------


@dataclass
class ColumnGeometry:
    """Column boundaries on the page: n+1 x coordinates for n columns."""

    bounds: list[float]
    strategy: str                 # "ruled" | "banded"
    page_number: int = -1

    @property
    def n_cols(self) -> int:
        return max(0, len(self.bounds) - 1)

    def column_of(self, x0: float, x1: float) -> Optional[int]:
        """The column to which a word with the span [x0, x1] belongs.

        The CENTER of the word decides, not its left edge: a word cut by a grid
        line (which happens with narrow columns) ends up where the larger part
        of it lies.
        """
        mid = 0.5 * (x0 + x1)
        for i in range(self.n_cols):
            if self.bounds[i] <= mid < self.bounds[i + 1]:
                return i
        if mid >= self.bounds[-1]:
            return self.n_cols - 1 if self.n_cols else None
        if mid < self.bounds[0]:
            return 0 if self.n_cols else None
        return None


def detect_ruled_columns(page, *, min_len: float = 5.0, tol: float = 1.5) -> ColumnGeometry:
    """Column boundaries from the page's vertical vector edges.

    Edges shorter than ``min_len`` are usually decorations / header frames, not
    grid lines. Edges less than ``tol`` apart are two sides of the same thick
    line, merged to their average.
    """
    xs = sorted(
        e["x0"] for e in page.edges
        if e.get("orientation") == "v" and (e["bottom"] - e["top"]) > min_len
    )
    merged: list[list[float]] = []
    for x in xs:
        if merged and x - merged[-1][-1] <= tol:
            merged[-1].append(x)
        else:
            merged.append([x])
    bounds = [float(statistics.fmean(g)) for g in merged]
    return ColumnGeometry(bounds, "ruled", getattr(page, "page_number", -1))


def detect_banded_columns(
    words: Sequence[dict],
    *,
    min_gap: float = 4.0,
    resolution: float = 0.5,
) -> ColumnGeometry:
    """Column boundaries from vertical corridors of whitespace in the word block.

    Builds an x-axis coverage vector (whether any word occupies a given position),
    finds gaps longer than ``min_gap`` and places a boundary at their center.
    Used when the document has no grid lines.
    """
    if not words:
        return ColumnGeometry([], "banded")
    x_min = min(w["x0"] for w in words)
    x_max = max(w["x1"] for w in words)
    n = max(1, int((x_max - x_min) / resolution) + 1)
    cover = bytearray(n)
    for w in words:
        a = int((w["x0"] - x_min) / resolution)
        b = min(n, int((w["x1"] - x_min) / resolution) + 1)
        for i in range(max(0, a), b):
            cover[i] = 1
    bounds = [x_min - 1.0]
    i = 0
    while i < n:
        if cover[i] == 0:
            j = i
            while j < n and cover[j] == 0:
                j += 1
            if (j - i) * resolution >= min_gap and i > 0 and j < n:
                bounds.append(x_min + (i + j) / 2.0 * resolution)
            i = j
        else:
            i += 1
    bounds.append(x_max + 1.0)
    return ColumnGeometry(bounds, "banded")


# --------------------------------------------------------------------------
# assigning words to cells
# --------------------------------------------------------------------------


def assign_words_to_columns(
    words: Iterable[dict],
    geom: ColumnGeometry,
    *,
    line_tol: float = 2.0,
) -> list[list[str]]:
    """Arrange words into visual rows, and within a row into cells according to column geometry."""
    ws = sorted(words, key=lambda w: (round(w["top"], 1), w["x0"]))
    lines: list[list[dict]] = []
    for w in ws:
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= line_tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    out: list[list[str]] = []
    for ln in lines:
        cells: list[list[str]] = [[] for _ in range(geom.n_cols)]
        for w in sorted(ln, key=lambda w: w["x0"]):
            ci = geom.column_of(w["x0"], w["x1"])
            if ci is not None:
                cells[ci].append(w["text"])
        out.append([" ".join(c).strip() for c in cells])
    return out


def merge_continuation_rows(
    lines: Sequence[Sequence[str]],
    is_row_start: Callable[[Sequence[str]], bool],
    *,
    joiner: str = " ",
) -> list[list[str]]:
    """Merge multi-line rows.

    ``is_row_start`` decides whether a line begins a new record (for Polish
    publishers: the first cell is a sequence number). Lines in between are
    appended to the last record, column by column: this way a wrapped
    address does not spill over into the neighbouring field.
    """
    rows: list[list[str]] = []
    for ln in lines:
        if is_row_start(ln) or not rows:
            rows.append(list(ln))
        else:
            for i, v in enumerate(ln):
                if i >= len(rows[-1]):
                    rows[-1].append(v)
                elif v:
                    rows[-1][i] = (rows[-1][i] + joiner + v).strip() if rows[-1][i] else v
    return rows


def extract_ruled_page(page, geom: Optional[ColumnGeometry] = None, *,
                       intersection_tolerance: float = 5.0) -> list[list[Optional[str]]]:
    """Rows of a page from a table with a drawn grid.

    Vertical boundaries are given explicitly (from ``detect_ruled_columns``), horizontal
    ones are left to line detection: this way a multi-line cell is merged by the
    grid itself, without a continuity heuristic.
    """
    if geom is None:
        geom = detect_ruled_columns(page)
    if geom.n_cols < 2:
        return []
    settings = {
        "vertical_strategy": "explicit",
        "explicit_vertical_lines": geom.bounds,
        "horizontal_strategy": "lines",
        "intersection_tolerance": intersection_tolerance,
    }
    tbl = page.extract_table(settings)
    return tbl or []


# --------------------------------------------------------------------------
# column shift audit
# --------------------------------------------------------------------------

_RE_DATE = re.compile(r"^\s*\d{2}[./-]\d{2}[./-]\d{4}\s*$|^\s*\d{4}-\d{2}-\d{2}\s*$")
_RE_NUM = re.compile(r"^\s*-?[\d \u00a0\u202f]*\d(?:[.,]\d+)?\s*$")
_RE_INT = re.compile(r"^\s*\d+\s*$")


def looks_like_date(v: Any) -> bool:
    return bool(_RE_DATE.match(str(v))) if v is not None else False


def looks_like_number(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    return bool(_RE_NUM.match(str(v)))


#: a number stuck onto the beginning of a text field: a trace of the neighbouring
#: numeric column soaking into the descriptive field (the most common form of column shift)
_RE_LEADING_NUM = re.compile(r"^\s*-?\d+(?:[.,]\d+)?(?:\s+-?\d+(?:[.,]\d+)?)*\s+\S")


def looks_like_text(v: Any) -> bool:
    """Whether the value can stand in a descriptive field.

    Rejects not only pure numbers and dates, but also strings that start with a
    numeric token before the text ("0.1 0.1 WARUNKI PRZYŁĄCZENIA ..."). This
    form is the signature of column shift in regex-based extraction: an empty
    capacity cell disappears from the flattened text and the capacity value
    sticks onto the status.
    """
    s = str(v).strip()
    if not s or looks_like_number(s) or looks_like_date(s):
        return False
    return not bool(_RE_LEADING_NUM.match(s))


#: voltage level is a field with a narrow, known domain: a class abbreviation (nn/SN/WN/NN)
#: or a value with a unit ("110 kV", "15 kV"). A number without a unit or a sentence
#: means that the content of the neighbouring column has soaked into the field.
_RE_VOLT = re.compile(
    r"^\s*(?:nn|sn|wn|nn/sn|sn/nn|nN)\s*$"
    r"|^\s*\d+(?:[.,]\d+)?\s*[kKmM]?[vV]\s*$"
    r"|^\s*\d+(?:[.,]\d+)?\s*[kKmM][vV]\s*/\s*\d+(?:[.,]\d+)?\s*[kKmM][vV]\s*$",
    re.IGNORECASE,
)


def looks_like_voltage(v: Any) -> bool:
    return bool(_RE_VOLT.match(str(v))) if v is not None else False


#: domain predicates for schema columns: "can this value stand in this field"
DOMAIN_PREDICATES: dict[str, Callable[[Any], bool]] = {
    "capacity_injected": looks_like_number,
    "capacity_withdrawn": looks_like_number,
    "capacity_available": looks_like_number,
    "capacity_reserved": looks_like_number,
    "date_application": looks_like_date,
    "date_conditions": looks_like_date,
    "date_refusal": looks_like_date,
    "date_agreement": looks_like_date,
    "date_energisation": looks_like_date,
    "date_published": looks_like_date,
    "process_status": looks_like_text,
    "resource_class": looks_like_text,
    "voltage_level": lambda v: looks_like_voltage(v),
    "location_text": lambda v: bool(str(v).strip()),
}


@dataclass
class ShiftAudit:
    """Result of the column shift audit."""

    n_rows: int
    n_shifted: int
    per_field: dict[str, int] = field(default_factory=dict)
    examples: list[dict] = field(default_factory=list)

    @property
    def share(self) -> float:
        return self.n_shifted / self.n_rows if self.n_rows else 0.0

    def as_dict(self) -> dict:
        return {
            "n_rows": self.n_rows,
            "n_shifted": self.n_shifted,
            "share": round(self.share, 6),
            "per_field": dict(sorted(self.per_field.items(), key=lambda kv: -kv[1])),
        }


def audit_column_shift(
    df,
    predicates: Optional[dict[str, Callable[[Any], bool]]] = None,
    *,
    nullish: Optional[set[str]] = None,
    n_examples: int = 5,
) -> ShiftAudit:
    """Count rows in which some non-empty value stands in a field it cannot
    belong to (a number in a date field, status text in a capacity field, etc.).

    This is the operational definition of a "shifted column": we do not compare
    against a reference, we only check an INTERNAL type contradiction. The same
    measure is computed for the old and the new extraction, so the comparison
    is fair.
    """
    preds = predicates if predicates is not None else DOMAIN_PREDICATES
    nl = nullish or {"", "-", "--", "---", "nan", "none", "brak", "nie dotyczy"}
    cols = [c for c in preds if c in df.columns]
    bad_rows = 0
    per_field: dict[str, int] = {}
    examples: list[dict] = []
    for idx, row in df.iterrows():
        offenders = []
        for c in cols:
            v = row[c]
            if v is None or (isinstance(v, float) and v != v):
                continue
            s = str(v).strip()
            if s.lower() in nl:
                continue
            if not preds[c](v):
                offenders.append((c, s))
        if offenders:
            bad_rows += 1
            for c, _ in offenders:
                per_field[c] = per_field.get(c, 0) + 1
            if len(examples) < n_examples:
                examples.append({"index": idx, "violations": offenders})
    return ShiftAudit(len(df), bad_rows, per_field, examples)
