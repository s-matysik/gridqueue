"""Adapter: ENERGA-OPERATOR S.A. (PL, OSD, sześć oddziałów, obszar północny).

Energa jest jedynym z dotychczas zmierzonych publikujących, który realizuje OBA
punkty obowiązku w rozłącznych dokumentach i w obu podaje dane w postaci tabelarycznej:

  pkt 1), 3), 4) -- "Informacje publikowane zgodnie z Art. 7 ust. 8l pkt 1), 3)
                    i 4) ustawy Prawo energetyczne", PDF, 37 stron, 28 kolumn.
                    To jest ten sam wzorzec PTPiREE/PSE co arkusz PSE (moduł
                    ``_ptpiree``), przeniesiony do PDF-a.  Encja WNIOSEK.
  pkt 2)         -- dwa dokumenty "Informacja o wartości łącznej dostępnej
                    {odbiorczej|wytwórczej} mocy przyłączeniowej [MW]".  Encja WĘZEŁ.
                    TO JEST PIERWSZE ŹRÓDŁO W PANELU, KTÓRE WYPEŁNIA ``moc_dostepna``.

Geometria pkt 1/3/4: dokument nie ma obiektów ``line``, ma natomiast 176 cienkich
prostokątów pełniących rolę linii siatki; pdfplumber wystawia je jako krawędzie, więc
strategia ``ruled`` działa bez zmian.  Nagłówek szczegółowy jest złożony z bardzo
wąskich kolumn ze zawijanym tekstem -- płaski ``extract_text`` przeplata go między
kolumnami i jest bezużyteczny, dlatego układ odczytujemy przez przypisanie słów
nagłówka do kolumn geometrią, a nie z tekstu strony.

Geometria pkt 2: tabele 2.1 (skład grup węzłów koherentnych), 2.2 (słownik skrótów
stacji) i 2.3/2.4 (wartości mocy) też mają siatkę wektorową.

Rozstrzygnięcie merytoryczne przy dokumencie wytwórczym: są w nim DWIE tabele
wartości.  Tabela 2.3 jest ujawnieniem ustawowym; tabela 2.4 jest -- słowami samego
dokumentu -- podana "dodatkowo", dla podejścia analitycznego jak w ekspertyzach wg
ustawy o morskich farmach wiatrowych.  Do ``moc_dostepna`` bierzemy 2.3; 2.4 trafia
do rozszerzenia.  Odwrotny wybór zawyżałby ujawnioną moc bez podstawy w dokumencie.

Rozbieżność dat, którą trzeba zgłosić, a nie wygładzić: plik pkt 1/3/4 nazywa się
``2026_08_31_pusop_wnioski_i_odmowy_eop.pdf`` i wisi w cyklu sierpniowym, ale jego
własny nagłówek deklaruje "Stan na 30.06.2026 r.".  ``data_publikacji`` bierzemy
z DOKUMENTU (30.06.2026), bo to on jest ujawnieniem, a nie nazwa pliku.
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
        _kierunek="kierunek mocy dostępnej: odbiorcza albo wytwórcza",
        _nr_grupy="numer grupy węzłów koherentnych w dokumencie",
        _stacje_grupy="stacje wchodzące w skład grupy (model sieci na rok bazowy)",
        _zmiany_w_latach="zmiany składu grupy w kolejnych latach (kolumna uwag)",
        _oddzial="oddział ENERGA-OPERATOR, w którego obszarze leży grupa",
        _moc_dostepna_analityczna="wartość z tabeli 2.4 (podejście analityczne), rok bazowy [kW]",
    )
    detect_patterns = (r"energa", r"eop")

    #: lata horyzontu ujawnienia pkt 2
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
            "strategia_wydobycia": "ruled (siatka z cienkich prostokątów), nagłówek odczytany geometrią",
            "wzorzec": "PTPiREE/PSE dla pkt 1/3/4; autorski układ IEn dla pkt 2",
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
        """pkt 1/3/4 -- wzorzec PTPiREE w PDF-ie z siatką wektorową."""
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
            "uwaga_data": "nazwa pliku wskazuje cykl 31.08.2026, dokument deklaruje "
                          f"stan na {stan}; przyjęto deklarację dokumentu",
        }

    # ------------------------------------------------------------------
    def _parse_wezly(self, src, *, kierunek: str):
        """pkt 2 -- wartości łącznej dostępnej mocy przyłączeniowej per grupa węzłów."""
        import pandas as pd
        import pdfplumber

        grupy: dict[str, dict] = {}       # nr grupy -> skład
        wartosci: dict[str, dict] = {}    # nr grupy -> {rok: MW} z tabeli 2.3
        analit: dict[str, dict] = {}      # nr grupy -> {rok: MW} z tabeli 2.4
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
        # Kierunek mocy nie jest rodzajem instalacji: ujawnienie pkt 2 dotyczy
        # WĘZŁA, nie zasobu.  Dla mocy odbiorczej klasa jest jednoznaczna (ODB),
        # dla wytwórczej dokument nie wskazuje technologii -- i tak zostaje.
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
                f"dostępna moc przyłączeniowa w horyzoncie {rok} [kW]"
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
