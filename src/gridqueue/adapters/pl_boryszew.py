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
from .base import Adapter, ParseResult, harmonize_klasa, harmonize_status, norm_text

_RE_LP = re.compile(r"^\d+\.$")
_SECTIONS = (
    (1, re.compile(r"^1\.\s*Podmioty ubiegaj", re.I)),
    (2, re.compile(r"^2\.\s*Warto", re.I)),
    (3, re.compile(r"^3\.\s*Z(ł|l)o(ż|z)one wnioski", re.I)),
    (4, re.compile(r"^4\.\s*Wydane odmowy", re.I)),
    (5, re.compile(r"^5\.\s*Spos(ó|o)b", re.I)),
)

LAYOUTS = {
    1: ("lp", "rodzaj_podmiotu", "lokalizacja", "moc_mw", "rodzaj_instalacji",
        "data_warunkow", "data_umowy", "data_energizacji"),
    3: ("lp", "rodzaj_podmiotu", "lokalizacja", "moc_mw", "rodzaj_instalacji",
        "data_zlozenia", "data_zaliczki", "status_wniosku"),
    4: ("lp", "lokalizacja", "moc_mw", "rodzaj_instalacji", "data_zlozenia",
        "data_zaliczki", "powod_odmowy"),
}


class BoryszewAdapter(Adapter):
    publisher = "Boryszew Green Energy&Gas Sp. z o.o."
    jurisdiction = "PL"
    declared_fields = (
        "id_wniosku", "lokalizacja_tekst", "klasa_zasobu", "moc_pobierana",
        "status_procesu", "data_wniosku", "data_warunkow", "data_umowy",
        "data_energizacji", "data_publikacji",
    )
    declared_extensions = {
        "_rodzaj_podmiotu": "description of the connected entity (legal person/natural person)",
        "_data_zaliczki": "date of the deposit payment",
        "_sekcja": "the point of Art. 7(8l) that the row originates from",
        "_rodzaj_instalacji_raw": "type of installation exactly as in the document",
        "_status_raw": "processing status exactly as in the document",
        "_uwaga_zrodlowa": "publisher's annotation (e.g. 'Nie dotyczy / istniejące przyłącze')",
    }
    detect_patterns = (r"boryszew", r"elana")

    def __init__(self, data_publikacji: Optional[str] = None):
        self.data_publikacji = data_publikacji

    # ------------------------------------------------------------------
    def parse(self, source) -> ParseResult:
        import pandas as pd
        import pdfplumber

        sec_lines: dict[int, list[list[dict]]] = {k: [] for k, _ in _SECTIONS}
        wezly_lines: list[list[dict]] = []
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
        if self.data_publikacji is None:
            self.data_publikacji = _data_aktualizacji(full_text)

        frames = []
        per_section = {}
        for sec in (1, 3, 4):
            f, n_raw = self._section_frame(sec, sec_lines[sec])
            per_section[sec] = {"wierszy_surowych": n_raw, "wierszy_wynikowych": int(len(f))}
            if len(f):
                frames.append(f)
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        wezly = _parse_wezly(sec_lines[2])

        report = {
            "publikujacy": self.publisher,
            "strategia_wydobycia": "banded (white-space corridors; no line grid)",
            "strony": n_pages,
            "sekcje": per_section,
            "n_wierszy": int(len(df)),
            "wezly_pkt2": wezly,
            "data_publikacji": self.data_publikacji,
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
        body = raw.drop(columns=["lp"])
        keep = ~body.map(lambda v: norm_text(v) in {"", "brak", "-"}).all(axis=1)
        raw = raw[keep].reset_index(drop=True)
        if raw.empty:
            return pd.DataFrame(), n_raw

        out = pd.DataFrame(index=raw.index)
        out["id_wniosku"] = [f"boryszew:pkt{sec}:{i + 1}" for i in range(len(raw))]
        out["lokalizacja_tekst"] = raw["lokalizacja"].replace("", None)
        out["klasa_zasobu"] = raw["rodzaj_instalacji"].map(harmonize_klasa)
        out["moc_pobierana"] = raw["moc_mw"].map(lambda v: canonical_power_kw(v, "MW"))
        out["data_publikacji"] = self.data_publikacji
        out["_sekcja"] = f"art. 7 ust. 8l pkt {sec}"
        out["_rodzaj_instalacji_raw"] = raw["rodzaj_instalacji"].replace("", None)
        if "rodzaj_podmiotu" in raw:
            out["_rodzaj_podmiotu"] = raw["rodzaj_podmiotu"].replace("", None)
        if sec == 1:
            out["data_warunkow"] = raw["data_warunkow"].map(canonical_date)
            out["data_umowy"] = raw["data_umowy"].map(canonical_date)
            out["data_energizacji"] = raw["data_energizacji"].map(canonical_date)
            out["_uwaga_zrodlowa"] = raw["data_umowy"].replace("", None)
            _ok = lambda v: v is not None and not (isinstance(v, float) and v != v)
            out["status_procesu"] = [
                "PRZYLACZONY" if _ok(e) else ("UMOWA_OBOWIAZUJACA" if _ok(u) else
                                              ("WARUNKI_WYDANE" if _ok(w) else "NIEOKRESLONY"))
                for e, u, w in zip(out["data_energizacji"], out["data_umowy"],
                                   out["data_warunkow"])
            ]
        elif sec == 3:
            out["data_wniosku"] = raw["data_zlozenia"].map(canonical_date)
            out["_data_zaliczki"] = raw["data_zaliczki"].map(canonical_date)
            out["status_procesu"] = raw["status_wniosku"].map(harmonize_status)
            out["_status_raw"] = raw["status_wniosku"].replace("", None)
        else:
            out["data_wniosku"] = raw["data_zlozenia"].map(canonical_date)
            out["powod_odmowy"] = raw["powod_odmowy"].replace("", None)
            out["status_procesu"] = "ODMOWA"
        out["_lp_dokumentu"] = raw["lp"]
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


def _data_aktualizacji(text: str) -> Optional[str]:
    m = re.search(r"Data aktualizacji publikacji:\s*(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    months = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5,
              "czerwca": 6, "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9,
              "października": 10, "pazdziernika": 10, "listopada": 11, "grudnia": 12}
    if m and m.group(2).lower() in months:
        return f"{m.group(3)}-{months[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
    return None


def _parse_wezly(lines: list[list[dict]]) -> list[dict]:
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
            rec = {"nazwa_wezla": " ".join(name_toks),
                   "moc_dostepna_kw": {}}
            for i, v in enumerate(vals):
                y = years[i] if i < len(years) else f"kol{i}"
                rec["moc_dostepna_kw"][y] = canonical_power_kw(v, "MW")
            out.append(rec)
    return out
