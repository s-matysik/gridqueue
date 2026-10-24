"""Adapter: ENERGA-OPERATOR S.A. (PL, DSO, six branches, northern area).

Energa is the only one, among those measured so far, of the publishers that
implements BOTH points of the duty in separate documents, and in both provides
data in tabular form:

  pt. 1), 3), 4): "Information published pursuant to Art. 7(8l) pt. 1), 3)
                   and 4) of the Energy Law act", PDF, 37 pages, 28 columns.
                   This is the same PTPiREE/PSE pattern as the PSE sheet (module
                   ``_ptpiree``), moved into a PDF.  APPLICATION entity.
  pt. 2)         : two documents "Information on the total value of available
                   {off-take|generation} connection capacity [MW]".  NODE entity.
                   THIS IS THE FIRST SOURCE IN THE PANEL THAT FILLS ``capacity_available``.

Geometry for pt. 1/3/4: the document has no ``line`` objects, but instead has 176
thin rectangles acting as grid lines; pdfplumber reports them as edges, so the
``ruled`` strategy works without changes.  The detailed header is composed of very
narrow columns with wrapped text; flat ``extract_text`` interleaves it between
columns and is useless, which is why we read the layout by assigning header words
to columns via geometry, rather than from the page text.

Geometry for pt. 2: tables 2.1 (composition of coherent node groups), 2.2
(dictionary of station abbreviations) and 2.3/2.4 (capacity values) also have a
vector grid.

Substantive resolution for the generation document: it contains TWO value tables.
Table 2.3 is the statutory disclosure; table 2.4 is, in the words of the document
itself, provided "additionally", for the analytical approach as in the expert
opinions under the Act on Offshore Wind Farms.  For ``capacity_available`` we take 2.3;
2.4 goes into the extension.  The opposite choice would overstate the disclosed
capacity without basis in the document.

Date discrepancy that must be reported, not smoothed over: the file for pt. 1/3/4
is named ``2026_08_31_pusop_wnioski_i_odmowy_eop.pdf`` and sits in the August
cycle, but its own header declares "Stan na 30.06.2026 r.".  We take
``date_published`` FROM THE DOCUMENT (30.06.2026), because it is the document
that is the disclosure, not the file name.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..layout import detect_ruled_columns, extract_ruled_page
from ..schema import canonical_power_kw
from . import _ptpiree as T
from .base import Adapter, ParseResult, norm_text

__all__ = ["EnergaAdapter"]

_RE_LP = re.compile(r"^\d+\.?$")
_RE_YEAR = re.compile(r"^(19|20)\d{2}$")


class EnergaAdapter(Adapter):
    publisher = "ENERGA-OPERATOR S.A."
    jurisdiction = "PL"
    declared_fields = T.DECLARED_FIELDS + ("node_id", "node_name", "capacity_available")
    declared_extensions = dict(
        T.DECLARED_EXTENSIONS,
        _direction="direction of available capacity: off-take or generation",
        _group_no="number of the coherent node group in the document",
        _group_stations="stations forming the group (network model for the base year)",
        _changes_by_year="changes in group composition in subsequent years (remarks column)",
        _branch="ENERGA-OPERATOR branch in whose area the group lies",
        _capacity_available_analytical="value from table 2.4 (analytical approach), base year [kW]",
    )
    detect_patterns = (r"energa", r"eop")

    #: years of the disclosure horizon for pt. 2
    HORIZON = ("2026", "2027", "2028", "2029", "2030", "2031", "2035")

    def __init__(self, publication_date: Optional[str] = None, base_year: str = "2026"):
        self.publication_date = publication_date
        self.base_year = base_year

    # ------------------------------------------------------------------
    def parse(self, source) -> ParseResult:
        import pandas as pd

        sources = [source] if isinstance(source, (str, bytes)) else list(source)
        frames, reports = [], []
        for src in sources:
            role = self._detect_role(src)
            if role == "applications":
                f, r = self._parse_applications(src)
            else:
                f, r = self._parse_nodes(src, direction=role)
            frames.append(f)
            reports.append(r)
        df = pd.concat(frames, ignore_index=True) if frames else self.blank_frame(0)
        report = {
            "publisher": self.publisher,
            "extraction_strategy": "ruled (grid of thin rectangles), header read via geometry",
            "pattern": "PTPiREE/PSE for pt. 1/3/4; IEn's own custom layout for pt. 2",
            "documents": reports,
            "n_rows": int(len(df)),
            "publication_date": self.publication_date,
        }
        return ParseResult(self.finalize(df, document="; ".join(map(str, sources))), report)

    # ------------------------------------------------------------------
    @staticmethod
    def _detect_role(src) -> str:
        import pdfplumber

        with pdfplumber.open(src) as pdf:
            t = norm_text(pdf.pages[0].extract_text() or "")
        if "dostepnej odbiorczej mocy" in t:
            return "demand"
        if "dostepnej wytworczej mocy" in t:
            return "generation"
        return "applications"

    # ------------------------------------------------------------------
    def _parse_applications(self, src):
        """pt. 1/3/4: PTPiREE pattern in a PDF with a vector grid."""
        import pandas as pd
        import pdfplumber

        rows: list[list[Optional[str]]] = []
        n_pages = 0
        n_cols_seen: set[int] = set()
        as_at = None
        with pdfplumber.open(src) as pdf:
            for page in pdf.pages:
                n_pages += 1
                if as_at is None:
                    as_at = T.parse_as_at(page.extract_text() or "")
                geom = detect_ruled_columns(page)
                if geom.n_cols < 10:
                    continue
                n_cols_seen.add(geom.n_cols)
                tbl = extract_ruled_page(page, geom)
                for row in tbl or []:
                    if row and _RE_LP.match((row[0] or "").strip()):
                        rows.append(row)
        if as_at and self.publication_date is None:
            self.publication_date = as_at

        width = max(T.ENERGA_PDF_LAYOUT) + 1
        raw = pd.DataFrame(index=range(len(rows)))
        padded = [(list(r) + [None] * width)[:width] for r in rows]
        for phys, logical in T.ENERGA_PDF_LAYOUT.items():
            raw[logical] = [p[phys] for p in padded]
        out = T.to_schema(raw, publisher_key="energa", publication_date=self.publication_date)
        return out, {
            "file_name": str(src),
            "entity": "APPLICATION",
            "pages": n_pages,
            "n_source_columns": sorted(n_cols_seen),
            "n_rows": int(len(out)),
            "parse_as_at": as_at,
            "note_date": "the file name indicates the 31.08.2026 cycle, the document declares "
                          f"as of {as_at}; the document's declaration was adopted",
        }

    # ------------------------------------------------------------------
    def _parse_nodes(self, src, *, direction: str):
        """pt. 2: values of the total available connection capacity per node group."""
        import pandas as pd
        import pdfplumber

        groups: dict[str, dict] = {}       # group no. -> composition
        values: dict[str, dict] = {}    # group no. -> {year: MW} from table 2.3
        analytical: dict[str, dict] = {}      # group no. -> {year: MW} from table 2.4
        current_branch = None
        as_at = None
        n_pages = 0

        with pdfplumber.open(src) as pdf:
            for page in pdf.pages:
                n_pages += 1
                txt = page.extract_text() or ""
                if as_at is None:
                    as_at = T.parse_as_at(txt)
                if len(page.rects) < 50:
                    continue
                geom = detect_ruled_columns(page)
                if geom.n_cols < 2:
                    continue
                tbl = extract_ruled_page(page, geom) or []
                caption = norm_text(" ".join(l for l in txt.split("\n")[:6]
                                             if l.strip().startswith("Tabela")))
                if caption.startswith("tabela 2.1"):
                    current_branch = self._collect_groups(tbl, groups, current_branch)
                elif caption.startswith("tabela 2.3"):
                    self._collect_values(tbl, values)
                elif caption.startswith("tabela 2.4"):
                    self._collect_values(tbl, analytical)

        if direction == "demand" and as_at and self.publication_date is None:
            self.publication_date = as_at

        nry = sorted(values, key=lambda s: int(s))
        out = pd.DataFrame(index=range(len(nry)))
        g = [groups.get(n, {}) for n in nry]
        out["application_id"] = None
        out["node_id"] = [f"energa:grupa110:{n}:{direction}" for n in nry]
        out["node_name"] = [values[n].get("_name") for n in nry]
        out["location_text"] = [
            gi.get("stations") or values[n].get("_name") for n, gi in zip(nry, g)
        ]
        out["voltage_level"] = "110 kV"
        # The capacity direction is not a kind of installation: the pt. 2 disclosure
        # concerns the NODE, not the resource.  For off-take capacity the class is
        # unambiguous (LOAD); for generation, the document does not indicate the
        # technology, so it remains as is.
        out["resource_class"] = "LOAD" if direction == "demand" else "UNSPECIFIED"
        out["process_status"] = "UNSPECIFIED"
        out["capacity_available"] = [
            canonical_power_kw(values[n].get(self.base_year), "MW") for n in nry
        ]
        out["date_published"] = as_at
        out["_entity"] = "NODE"
        out["_direction"] = direction
        out["_group_no"] = nry
        out["_group_stations"] = [gi.get("stations") for gi in g]
        out["_changes_by_year"] = [gi.get("changes") for gi in g]
        out["_branch"] = [gi.get("branch") for gi in g]
        for year in self.HORIZON:
            out[f"_capacity_available_{year}"] = [
                canonical_power_kw(values[n].get(year), "MW") for n in nry
            ]
        out["_capacity_available_analytical"] = [
            canonical_power_kw(analytical.get(n, {}).get(self.base_year), "MW") for n in nry
        ]
        for year in self.HORIZON:
            self.declared_extensions[f"_capacity_available_{year}"] = (
                f"available connection capacity in the {year} horizon [kW]"
            )
        return out, {
            "file_name": str(src),
            "entity": "NODE",
            "direction": direction,
            "pages": n_pages,
            "n_groups_with_values": len(nry),
            "n_groups_with_composition": len(groups),
            "n_analytical_groups": len(analytical),
            "horizon": list(self.HORIZON),
            "base_year": self.base_year,
            "n_rows": int(len(out)),
            "parse_as_at": as_at,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _collect_groups(tbl, groups: dict, branch: Optional[str]) -> Optional[str]:
        for row in tbl:
            cells = [(c or "").replace("\n", " ").strip() for c in row]
            if len(cells) < 3:
                continue
            joined = " ".join(cells).strip()
            if "Oddział" in joined and not re.match(r"^\d+$", cells[0]):
                m = re.search(r"Oddział\s+([\w\śółęąźżćń-]+)", joined)
                if m:
                    branch = m.group(1).strip()
                continue
            if not re.match(r"^\d+$", cells[0]):
                continue
            groups[cells[0]] = {
                "name": cells[1] or None,
                "stations": re.sub(r"\s+", " ", cells[2]) or None,
                "changes": (re.sub(r"\s+", " ", cells[3]) or None) if len(cells) > 3 else None,
                "branch": branch,
            }
        return branch

    @staticmethod
    def _collect_values(tbl, store: dict) -> None:
        years: list[str] = []
        for row in tbl:
            cells = [(c or "").replace("\n", " ").strip() for c in row]
            if not cells:
                continue
            candidates = [c for c in cells[2:] if _RE_YEAR.match(c)]
            if len(candidates) >= 3:
                years = [c if _RE_YEAR.match(c) else "" for c in cells[2:]]
                continue
            if not years or not re.match(r"^\d+$", cells[0]):
                continue
            rec = {"_name": cells[1] or None}
            for year, val in zip(years, cells[2:]):
                if year and val not in {"", "-"}:
                    rec[year] = val
            store[cells[0]] = rec
