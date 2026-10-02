"""Wydobycie oparte na UKŁADZIE STRONY, nie na wyrażeniach regularnych.

Wyrażenie regularne działa na tekście spłaszczonym przez ekstraktor PDF: kolejność
słów jest kolejnością rysowania, a granice kolumn są odtwarzane ze spacji.  Gdy
komórka jest pusta albo zawiera spację, sąsiednie pola się zlewają i wartość wsiąka
do złego pola.  W poprzedniej wersji parsera TAURONA dotyczyło to 767 z 10 559
wierszy (7,3%).

Tu robimy odwrotnie: czytamy POŁOŻENIE każdego słowa (x0, x1, top, bottom) i
najpierw ustalamy geometrię tabeli, a dopiero potem przypisujemy słowa do komórek.
Dwie strategie, wybierane po tym, co dokument faktycznie zawiera:

  RULED  -- dokument ma linie siatki (pionowe krawędzie prostokątów).  Granice
            kolumn są WPROST narysowane przez wytwórcę dokumentu; pusta komórka
            nie może zlać się z sąsiednią, bo jest odgrodzona linią.
  BANDED -- dokument nie ma linii.  Granice wyprowadzamy z rozkładu pokrycia osi x
            przez słowa: kolumna to spójny przedział pokryty słowami, granica to
            pionowy korytarz bieli obecny na całej wysokości bloku tabeli.

Wybór pdfplumber zamiast camelot/tabula: camelot w trybie lattice wymaga Ghostscriptu
i konwersji do rastra (granice kolumn odtwarzane z obrazu, nie z wektorów), tabula
wymaga JVM.  pdfplumber daje bezpośredni dostęp do współrzędnych słów i krawędzi
wektorowych z pdfminer.six, więc granica kolumny jest liczbą z pliku, a nie wynikiem
detekcji krawędzi na bitmapie -- co jest dokładnie tą własnością, od której zależy
teza tego narzędzia.
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
# geometria kolumn
# --------------------------------------------------------------------------


@dataclass
class ColumnGeometry:
    """Granice kolumn na stronie: n+1 współrzędnych x dla n kolumn."""

    bounds: list[float]
    strategy: str                 # "ruled" | "banded"
    page_number: int = -1

    @property
    def n_cols(self) -> int:
        return max(0, len(self.bounds) - 1)

    def column_of(self, x0: float, x1: float) -> Optional[int]:
        """Kolumna, do której należy słowo o rozpiętości [x0, x1].

        Decyduje ŚRODEK słowa, nie jego lewa krawędź: słowo przycięte przez linię
        siatki (co zdarza się przy wąskich kolumnach) trafia tam, gdzie leży jego
        większa część.
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
    """Granice kolumn z pionowych krawędzi wektorowych strony.

    Krawędzie krótsze niż ``min_len`` to zwykle ozdobniki / ramki nagłówka, nie
    linie siatki.  Krawędzie odległe o mniej niż ``tol`` to dwie strony tej samej
    grubej linii -- scalane do średniej.
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
    """Granice kolumn z pionowych korytarzy bieli w bloku słów.

    Buduje wektor pokrycia osi x (czy jakiekolwiek słowo zajmuje daną pozycję),
    znajduje przerwy dłuższe niż ``min_gap`` i stawia granicę w ich środku.
    Używane, gdy dokument nie ma linii siatki.
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
# przypisanie słów do komórek
# --------------------------------------------------------------------------


def assign_words_to_columns(
    words: Iterable[dict],
    geom: ColumnGeometry,
    *,
    line_tol: float = 2.0,
) -> list[list[str]]:
    """Ułóż słowa w wiersze wizualne, a w wierszu -- w komórki wg geometrii kolumn."""
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
    """Scal wiersze wielolinijkowe.

    ``is_row_start`` rozstrzyga, czy linia rozpoczyna nowy rekord (u polskich
    publikujących: pierwsza komórka to numer porządkowy).  Linie pomiędzy są
    dopisywane do ostatniego rekordu, kolumna po kolumnie -- dzięki temu zawinięty
    adres nie przenosi się do sąsiedniego pola.
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
    """Wiersze strony z tabeli o narysowanej siatce.

    Granice pionowe podajemy jawnie (z ``detect_ruled_columns``), poziome zostawiamy
    detekcji linii -- dzięki temu komórka wielolinijkowa jest scalana przez samą
    siatkę, bez heurystyki ciągłości.
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
# audyt przesunięcia kolumn
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


#: liczba doklejona na początku pola tekstowego -- ślad wsiąknięcia sąsiedniej
#: kolumny liczbowej w pole opisowe (najczęstsza postać przesunięcia kolumn)
_RE_LEADING_NUM = re.compile(r"^\s*-?\d+(?:[.,]\d+)?(?:\s+-?\d+(?:[.,]\d+)?)*\s+\S")


def looks_like_text(v: Any) -> bool:
    """Czy wartość może stać w polu opisowym.

    Odrzuca nie tylko czyste liczby i daty, ale też ciągi rozpoczynające się od
    tokenu liczbowego przed tekstem ("0,1 0,1 WARUNKI PRZYŁĄCZENIA ...").  Ta
    postać jest podpisem przesunięcia kolumn w wydobyciu regexowym: pusta komórka
    mocy znika ze spłaszczonego tekstu i wartość mocy dokleja się do statusu.
    """
    s = str(v).strip()
    if not s or looks_like_number(s) or looks_like_date(s):
        return False
    return not bool(_RE_LEADING_NUM.match(s))


#: poziom napięcia jest polem o wąskiej, znanej dziedzinie: skrót klasy (nn/SN/WN/NN)
#: albo wartość z jednostką ("110 kV", "15 kV").  Liczba bez jednostki albo zdanie
#: oznaczają, że do pola wsiąkła treść sąsiedniej kolumny.
_RE_VOLT = re.compile(
    r"^\s*(?:nn|sn|wn|nn/sn|sn/nn|nN)\s*$"
    r"|^\s*\d+(?:[.,]\d+)?\s*[kKmM]?[vV]\s*$"
    r"|^\s*\d+(?:[.,]\d+)?\s*[kKmM][vV]\s*/\s*\d+(?:[.,]\d+)?\s*[kKmM][vV]\s*$",
    re.IGNORECASE,
)


def looks_like_voltage(v: Any) -> bool:
    return bool(_RE_VOLT.match(str(v))) if v is not None else False


#: predykaty dziedziny dla kolumn schematu -- "czy ta wartość MOŻE stać w tym polu"
DOMAIN_PREDICATES: dict[str, Callable[[Any], bool]] = {
    "moc_wprowadzana": looks_like_number,
    "moc_pobierana": looks_like_number,
    "moc_dostepna": looks_like_number,
    "moc_zarezerwowana": looks_like_number,
    "data_wniosku": looks_like_date,
    "data_warunkow": looks_like_date,
    "data_odmowy": looks_like_date,
    "data_umowy": looks_like_date,
    "data_energizacji": looks_like_date,
    "data_publikacji": looks_like_date,
    "status_procesu": looks_like_text,
    "klasa_zasobu": looks_like_text,
    "poziom_napiecia": lambda v: looks_like_voltage(v),
    "lokalizacja_tekst": lambda v: bool(str(v).strip()),
}


@dataclass
class ShiftAudit:
    """Wynik audytu przesunięcia kolumn."""

    n_wierszy: int
    n_przesunietych: int
    per_pole: dict[str, int] = field(default_factory=dict)
    przyklady: list[dict] = field(default_factory=list)

    @property
    def udzial(self) -> float:
        return self.n_przesunietych / self.n_wierszy if self.n_wierszy else 0.0

    def as_dict(self) -> dict:
        return {
            "n_wierszy": self.n_wierszy,
            "n_przesunietych": self.n_przesunietych,
            "udzial": round(self.udzial, 6),
            "per_pole": dict(sorted(self.per_pole.items(), key=lambda kv: -kv[1])),
        }


def audit_column_shift(
    df,
    predicates: Optional[dict[str, Callable[[Any], bool]]] = None,
    *,
    nullish: Optional[set[str]] = None,
    n_examples: int = 5,
) -> ShiftAudit:
    """Policz wiersze, w których jakaś niepusta wartość stoi w polu, do którego
    nie może należeć (liczba w polu daty, tekst statusu w polu mocy itd.).

    To jest operacyjna definicja "przesuniętej kolumny": nie porównujemy z wzorcem,
    tylko sprawdzamy WEWNĘTRZNĄ sprzeczność typu.  Ta sama miara jest liczona dla
    starego i nowego wydobycia, więc porównanie jest uczciwe.
    """
    preds = predicates if predicates is not None else DOMAIN_PREDICATES
    nl = nullish or {"", "-", "--", "---", "nan", "none", "brak", "nie dotyczy"}
    cols = [c for c in preds if c in df.columns]
    bad_rows = 0
    per_pole: dict[str, int] = {}
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
                per_pole[c] = per_pole.get(c, 0) + 1
            if len(examples) < n_examples:
                examples.append({"index": idx, "naruszenia": offenders})
    return ShiftAudit(len(df), bad_rows, per_pole, examples)
