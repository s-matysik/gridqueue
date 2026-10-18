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
                   THIS IS THE FIRST SOURCE IN THE PANEL THAT FILLS ``moc_dostepna``.

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
opinions under the Act on Offshore Wind Farms.  For ``moc_dostepna`` we take 2.3;
2.4 goes into the extension.  The opposite choice would overstate the disclosed
capacity without basis in the document.

Date discrepancy that must be reported, not smoothed over: the file for pt. 1/3/4
is named ``2026_08_31_pusop_wnioski_i_odmowy_eop.pdf`` and sits in the August
cycle, but its own header declares "Stan na 30.06.2026 r.".  We take
``data_publikacji`` FROM THE DOCUMENT (30.06.2026), because it is the document
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
    declared_fields = T.DECLARED_FIELDS + ("id_wezla", "nazwa_wezla", "moc_dostepna")
    declared_extensions = dict(
        T.DECLARED_EXTENSIONS,
        _kierunek="direction of available capacity: off-take or generation",
        _nr_grupy="number of the coherent node group in the document",
        _stacje_grupy="stations forming the group (network model for the base year)",
        _zmiany_w_latach="changes in group composition in subsequent years (remarks column)",
        _oddzial="ENERGA-OPERATOR branch in whose area the group lies",
        _moc_dostepna_analityczna="value from table 2.4 (analytical approach), base year [kW]",
    )
    detect_patterns = (r"energa", r"eop")

    #: years of the disclosure horizon for pt. 2
    HORYZONT = ("2026", "2027", "2028", "2029", "2030", "2031", "2035")

    def __init__(self, data_publikacji: Optional[str] = None, rok_bazowy: str = "2026"):
        self.data_publikacji = data_publikacji
        self.rok_bazowy = rok_bazowy

    # ------------------------------------------------------------------
    def parse(self, source) -> ParseResult:
        import pandas as pd

        sources = [source] if isinstance(source, (str, bytes)) else list(source)
        frames, reports = [], []
        for src in sources:
            rola = self._detect_role(src)
            if rola == "wnioski":
                f, r = self._parse_wnioski(src)
            else:
                f, r = self._parse_wezly(src, kierunek=rola)
            frames.append(f)
            reports.append(r)
        df = pd.concat(frames, ignore_index=True) if frames else self.blank_frame(0)
        report = {
            "publikujacy": self.publisher,
            "strategia_wydobycia": "ruled (grid of thin rectangles), header read via geometry",
            "wzorzec": "PTPiREE/PSE for pt. 1/3/4; IEn's own custom layout for pt. 2",
            "dokumenty": reports,
            "n_wierszy": int(len(df)),
            "data_publikacji": self.data_publikacji,
        }
        return ParseResult(self.finalize(df, document="; ".join(map(str, sources))), report)

    # ------------------------------------------------------------------
    @staticmethod
    def _detect_role(src) -> str:
        import pdfplumber

        with pdfplumber.open(src) as pdf:
            t = norm_text(pdf.pages[0].extract_text() or "")
        if "dostepnej odbiorczej mocy" in t:
            return "odbiorcza"
        if "dostepnej wytworczej mocy" in t:
            return "wytworcza"
        return "wnioski"

    # ------------------------------------------------------------------
    def _parse_wnioski(self, src):
        """pt. 1/3/4: PTPiREE pattern in a PDF with a vector grid."""
        import pandas as pd
        import pdfplumber

        rows: list[list[Optional[str]]] = []
        n_pages = 0
        n_cols_seen: set[int] = set()
        stan = None
        with pdfplumber.open(src) as pdf:
            for page in pdf.pages:
                n_pages += 1
                if stan is None:
                    stan = T.stan_na(page.extract_text() or "")
                geom = detect_ruled_columns(page)
                if geom.n_cols < 10:
                    continue
                n_cols_seen.add(geom.n_cols)
                tbl = extract_ruled_page(page, geom)
                for row in tbl or []:
                    if row and _RE_LP.match((row[0] or "").strip()):
                        rows.append(row)
        if stan and self.data_publikacji is None:
            self.data_publikacji = stan

        width = max(T.ENERGA_PDF_LAYOUT) + 1
        raw = pd.DataFrame(index=range(len(rows)))
        padded = [(list(r) + [None] * width)[:width] for r in rows]
        for phys, logical in T.ENERGA_PDF_LAYOUT.items():
            raw[logical] = [p[phys] for p in padded]
        out = T.to_schema(raw, publisher_key="energa", data_publikacji=self.data_publikacji)
        return out, {
            "plik": str(src),
            "encja": "WNIOSEK",
            "strony": n_pages,
            "n_kolumn_zrodlowych": sorted(n_cols_seen),
            "n_wierszy": int(len(out)),
            "stan_na": stan,
            "uwaga_data": "the file name indicates the 31.08.2026 cycle, the document declares "
                          f"as of {stan}; the document's declaration was adopted",
        }

    # ------------------------------------------------------------------
    def _parse_wezly(self, src, *, kierunek: str):
        """pt. 2: values of the total available connection capacity per node group."""
        import pandas as pd
        import pdfplumber

        grupy: dict[str, dict] = {}       # group no. -> composition
        wartosci: dict[str, dict] = {}    # group no. -> {year: MW} from table 2.3
        analit: dict[str, dict] = {}      # group no. -> {year: MW} from table 2.4
        oddzial_biezacy = None
        stan = None
        n_pages = 0

        with pdfplumber.open(src) as pdf:
            for page in pdf.pages:
                n_pages += 1
                txt = page.extract_text() or ""
                if stan is None:
                    stan = T.stan_na(txt)
                if len(page.rects) < 50:
                    continue
                geom = detect_ruled_columns(page)
                if geom.n_cols < 2:
                    continue
                tbl = extract_ruled_page(page, geom) or []
                caption = norm_text(" ".join(l for l in txt.split("\n")[:6]
                                             if l.strip().startswith("Tabela")))
                if caption.startswith("tabela 2.1"):
                    oddzial_biezacy = self._collect_grupy(tbl, grupy, oddzial_biezacy)
                elif caption.startswith("tabela 2.3"):
                    self._collect_wartosci(tbl, wartosci)
                elif caption.startswith("tabela 2.4"):
                    self._collect_wartosci(tbl, analit)

        if kierunek == "odbiorcza" and stan and self.data_publikacji is None:
            self.data_publikacji = stan

        nry = sorted(wartosci, key=lambda s: int(s))
        out = pd.DataFrame(index=range(len(nry)))
        g = [grupy.get(n, {}) for n in nry]
        out["id_wniosku"] = None
        out["id_wezla"] = [f"energa:grupa110:{n}:{kierunek}" for n in nry]
        out["nazwa_wezla"] = [wartosci[n].get("_nazwa") for n in nry]
        out["lokalizacja_tekst"] = [
            gi.get("stacje") or wartosci[n].get("_nazwa") for n, gi in zip(nry, g)
        ]
        out["poziom_napiecia"] = "110 kV"
        # The capacity direction is not a kind of installation: the pt. 2 disclosure
        # concerns the NODE, not the resource.  For off-take capacity the class is
        # unambiguous (ODB); for generation, the document does not indicate the
        # technology, so it remains as is.
        out["klasa_zasobu"] = "ODB" if kierunek == "odbiorcza" else "NIEOKRESLONA"
        out["status_procesu"] = "NIEOKRESLONY"
        out["moc_dostepna"] = [
            canonical_power_kw(wartosci[n].get(self.rok_bazowy), "MW") for n in nry
        ]
        out["data_publikacji"] = stan
        out["_encja"] = "WEZEL"
        out["_kierunek"] = kierunek
        out["_nr_grupy"] = nry
        out["_stacje_grupy"] = [gi.get("stacje") for gi in g]
        out["_zmiany_w_latach"] = [gi.get("zmiany") for gi in g]
        out["_oddzial"] = [gi.get("oddzial") for gi in g]
        for rok in self.HORYZONT:
            out[f"_moc_dostepna_{rok}"] = [
                canonical_power_kw(wartosci[n].get(rok), "MW") for n in nry
            ]
        out["_moc_dostepna_analityczna"] = [
            canonical_power_kw(analit.get(n, {}).get(self.rok_bazowy), "MW") for n in nry
        ]
        for rok in self.HORYZONT:
            self.declared_extensions[f"_moc_dostepna_{rok}"] = (
                f"available connection capacity in the {rok} horizon [kW]"
            )
        return out, {
            "plik": str(src),
            "encja": "WEZEL",
            "kierunek": kierunek,
            "strony": n_pages,
            "n_grup_z_wartosciami": len(nry),
            "n_grup_ze_skladem": len(grupy),
            "n_grup_analitycznych": len(analit),
            "horyzont": list(self.HORYZONT),
            "rok_bazowy": self.rok_bazowy,
            "n_wierszy": int(len(out)),
            "stan_na": stan,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _collect_grupy(tbl, grupy: dict, oddzial: Optional[str]) -> Optional[str]:
        for row in tbl:
            cells = [(c or "").replace("\n", " ").strip() for c in row]
            if len(cells) < 3:
                continue
            joined = " ".join(cells).strip()
            if "Oddział" in joined and not re.match(r"^\d+$", cells[0]):
                m = re.search(r"Oddział\s+([\w\śółęąźżćń-]+)", joined)
                if m:
                    oddzial = m.group(1).strip()
                continue
            if not re.match(r"^\d+$", cells[0]):
                continue
            grupy[cells[0]] = {
                "nazwa": cells[1] or None,
                "stacje": re.sub(r"\s+", " ", cells[2]) or None,
                "zmiany": (re.sub(r"\s+", " ", cells[3]) or None) if len(cells) > 3 else None,
                "oddzial": oddzial,
            }
        return oddzial

    @staticmethod
    def _collect_wartosci(tbl, store: dict) -> None:
        lata: list[str] = []
        for row in tbl:
            cells = [(c or "").replace("\n", " ").strip() for c in row]
            if not cells:
                continue
            kandydaci = [c for c in cells[2:] if _RE_YEAR.match(c)]
            if len(kandydaci) >= 3:
                lata = [c if _RE_YEAR.match(c) else "" for c in cells[2:]]
                continue
            if not lata or not re.match(r"^\d+$", cells[0]):
                continue
            rec = {"_nazwa": cells[1] or None}
            for rok, val in zip(lata, cells[2:]):
                if rok and val not in {"", "-"}:
                    rec[rok] = val
            store[cells[0]] = rec
