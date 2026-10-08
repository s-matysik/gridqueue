"""Adapter: ESB Networks (IE) — mapa zdolności przyłączeniowej sieci.

Publikujący wydaje jeden arkusz obejmujący **całą sieć aż do poziomu stacji
SN/nn**, więc jest to najliczniejsze źródło w panelu i zarazem jedyne, które
schodzi poniżej poziomu stacji wysokiego napięcia. Jednostką wiersza jest grupa
transformatorów w stacji.

Dwie jednostki w jednym źródle
------------------------------
Publikujący podaje stronę **odbiorczą w MVA** (moc pozorna), a stronę
**wytwórczą w MW** (moc czynna). Jednostką kanoniczną schematu jest kW mocy
czynnej, więc:

* wartości wytwórcze są przeliczane (MW -> kW, ta sama wielkość fizyczna),
* wartości odbiorcze **nie są przeliczane** i trafiają do pól rozszerzenia
  z jawnie zapisaną jednostką.

Pole `moc_dostepna` niesie zatem dostępną moc **wytwórczą trwałą**, a nie sumę
obu stron. Zsumowanie MW z MVA dałoby liczbę bez sensu fizycznego, a wybór
jednej strony bez powiedzenia tego wprost byłby ukryciem decyzji.

Źródło podaje współrzędne oraz dwie osobne flagi ograniczenia — dla strony
odbiorczej i wytwórczej. Do pola `ograniczenie_flaga` wchodzi **alternatywa
obu**, bo pole schematu jest jedno; obie wartości źródłowe pozostają
w rozszerzeniach.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import Adapter, ParseResult

PUBLISHER = "ESB Networks DAC"
JURISDICTION = "IE"
ARKUSZ = "Heatmap data"

#: Nagłówek zajmuje dwa wiersze; nazwy właściwe są w drugim.
WIERSZ_NAGLOWKA = 2

KOL = {
    "stacja": "Station Name",
    "grupa": "Transformer GroupID",
    "napiecie_pierwotne": "Primary kV",
    "napiecie_wtorne": "Secondary voltage(s)",
    "klasa_napiecia": "Voltage Class",
    "konfiguracja": "Transformer Configuration",
    "moc_zainstalowana_mva": "Installed Capacity MVA",
    "odbior_trwala_mva": "Demand FirmCapacity MVA",
    "odbior_dostepna_mva": "Demand Available MVA",
    "odbior_nadrzedna_mva": "Parent Available MVA",
    "odbior_ograniczenie": "Demand Parent Constraint",
    "wytw_trwala_mw": "Generation Firm Capacity MW",
    "wytw_nietrwala_mw": "Generation NonFirm Capacity MW",
    "wytw_zakontraktowana_mw": "Generation Total Committed MW",
    "wytw_dostepna_trwala_mw": "Gen Available Firm MW",
    "wytw_dostepna_nietrwala_mw": "Gen Available NonFirm MW",
    "wytw_ograniczenie": "Generation Parent Constraint",
    "zasilanie": "Parent Feeder",
    "stacja_nadrzedna": "Parent Station",
    "styk_przesylowy": "TSO Interface Station",
    "komentarz": "Comment",
    "szerokosc": "Latitude",
    "dlugosc": "Longitude",
}

_TAK = {"yes", "y", "true", "constrained", "1"}
_NIE = {"no", "n", "false", "unconstrained", "0"}

#: Kolumny ograniczenia niosą frazę "Constrained, otherwise capacity available = X kVA"
#: albo są puste. Przyjmujemy, że pusta komórka oznacza BRAK ograniczenia, a nie brak
#: deklaracji: kolumna jest wskaźnikiem binarnym, w którym wartość dodatnia niesie
#: objaśnienie, a ujemna jest wyrażona pustką. Jest to INTERPRETACJA, nie treść źródła
#: -- publikujący nigdzie tej konwencji nie opisuje -- więc surowa fraza zostaje
#: w rozszerzeniu, a decyzja jest odnotowana w raporcie adaptera.
_FRAZA_OGRANICZENIA = re.compile(r"constrained", re.IGNORECASE)
_POJEMNOSC_W_FRAZIE = re.compile(r"=\s*([\d.,]+)\s*kVA", re.IGNORECASE)


def _liczba(v) -> float | None:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if s in {"", "-", "_", "n/a", "N/A", "None", "nan"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _mw_na_kw(v) -> float | None:
    x = _liczba(v)
    return None if x is None else x * 1000.0


def _flaga(v) -> bool | None:
    """Wskaźnik ograniczenia; pusta komórka to brak ograniczenia (patrz wyżej)."""
    if v is None or str(v).strip() == "":
        return False
    s = str(v).strip().lower()
    if s in _TAK:
        return True
    if s in _NIE:
        return False
    return True if _FRAZA_OGRANICZENIA.search(s) else None


def _pojemnosc_bez_ograniczenia(v) -> float | None:
    """Z frazy 'Constrained, otherwise capacity available = X kVA' wyjmij X.

    Wartość jest w kVA, czyli w mocy pozornej, więc NIE jest przeliczana na kW
    i zostaje w rozszerzeniu z jednostką w nazwie pola.
    """
    if v is None:
        return None
    m = _POJEMNOSC_W_FRAZIE.search(str(v))
    return _liczba(m.group(1)) if m else None


def _alternatywa(a: bool | None, b: bool | None) -> bool | None:
    """Alternatywa zachowująca nieokreśloność: None or False -> None, nie False."""
    if a is True or b is True:
        return True
    if a is False and b is False:
        return False
    return None


class ESBNetworksAdapter(Adapter):
    publisher = PUBLISHER
    jurisdiction = JURISDICTION
    declared_fields = (
        "id_wezla", "nazwa_wezla", "wspolrzedne", "poziom_napiecia",
        "moc_dostepna", "moc_zarezerwowana", "ograniczenie_flaga",
    )
    declared_extensions = {
        "_jednostka_mocy_odbiorczej": "jednostka strony odbiorczej u publikującego (MVA)",
        "_klasa_napiecia": "klasa napięcia wg publikującego",
        "_konfiguracja_transformatorow": "konfiguracja grupy transformatorów",
        "_moc_zainstalowana_mva": "moc zainstalowana transformatorów",
        "_odbior_dostepna_mva": "dostępna moc odbiorcza",
        "_odbior_trwala_mva": "trwała moc odbiorcza",
        "_odbior_nadrzedna_mva": "dostępna moc odbiorcza stacji nadrzędnej",
        "_odbior_ograniczenie": "ograniczenie po stronie odbiorczej",
        "_wytw_ograniczenie": "ograniczenie po stronie wytwórczej",
        "_odbior_ograniczenie_opis": "surowa fraza ograniczenia po stronie odbiorczej",
        "_wytw_ograniczenie_opis": "surowa fraza ograniczenia po stronie wytwórczej",
        "_odbior_bez_ograniczenia_kva": "moc odbiorcza dostępna, gdyby nie ograniczenie",
        "_wytw_bez_ograniczenia_kva": "moc wytwórcza dostępna, gdyby nie ograniczenie",
        "_wytw_dostepna_nietrwala_kw": "dostępna moc wytwórcza nietrwała",
        "_wytw_zakontraktowana_kw": "moc wytwórcza zakontraktowana łącznie",
        "_wytw_trwala_kw": "trwała moc wytwórcza",
        "_zasilanie": "linia zasilająca",
        "_stacja_nadrzedna": "stacja nadrzędna",
        "_styk_przesylowy": "stacja styku z siecią przesyłową",
        "_komentarz": "komentarz publikującego",
    }
    detect_patterns = (r"customer.?heatmap", r"esb.?networks", r"heatmap.?data")

    def parse(self, source) -> ParseResult:
        import openpyxl
        import pandas as pd

        path = Path(str(source))
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb[ARKUSZ] if ARKUSZ in wb.sheetnames else wb[wb.sheetnames[0]]
        it = ws.iter_rows(values_only=True)
        for _ in range(WIERSZ_NAGLOWKA - 1):
            next(it)
        naglowek = [str(c).strip() if c is not None else "" for c in next(it)]
        pozycja = {nazwa: naglowek.index(etykieta)
                   for nazwa, etykieta in KOL.items() if etykieta in naglowek}
        brakujace = sorted(set(KOL) - set(pozycja))

        rekordy, bez_wspolrzednych, ograniczonych = [], 0, 0
        for w in it:
            def g(nazwa):
                i = pozycja.get(nazwa)
                if i is None or i >= len(w):
                    return None
                v = w[i]
                return None if v is None or str(v).strip() in {"", "_", "-"} else v

            stacja = g("stacja")
            if stacja is None:
                continue
            grupa = g("grupa")
            lat, lon = _liczba(g("szerokosc")), _liczba(g("dlugosc"))
            if lat is None or lon is None:
                bez_wspolrzednych += 1
            s_odb, s_wyt = g("odbior_ograniczenie"), g("wytw_ograniczenie")
            f_odb, f_wyt = _flaga(s_odb), _flaga(s_wyt)
            ogr = _alternatywa(f_odb, f_wyt)
            if ogr:
                ograniczonych += 1
            nap = g("napiecie_pierwotne")

            rekordy.append({
                "id_wezla": f"{stacja}|{grupa}" if grupa else str(stacja),
                "nazwa_wezla": str(stacja).strip(),
                "wspolrzedne": f"{lat},{lon}" if lat is not None and lon is not None else None,
                "poziom_napiecia": str(nap).strip() if nap else None,
                # Strona wytwórcza jest w MW mocy czynnej -- jedyna przeliczalna.
                "moc_dostepna": _mw_na_kw(g("wytw_dostepna_trwala_mw")),
                "moc_zarezerwowana": _mw_na_kw(g("wytw_zakontraktowana_mw")),
                "ograniczenie_flaga": ogr,
                "_encja": "WEZEL",
                "_jednostka_mocy_odbiorczej": "MVA",
                "_klasa_napiecia": g("klasa_napiecia"),
                "_konfiguracja_transformatorow": g("konfiguracja"),
                "_moc_zainstalowana_mva": _liczba(g("moc_zainstalowana_mva")),
                "_odbior_dostepna_mva": _liczba(g("odbior_dostepna_mva")),
                "_odbior_trwala_mva": _liczba(g("odbior_trwala_mva")),
                "_odbior_nadrzedna_mva": _liczba(g("odbior_nadrzedna_mva")),
                "_odbior_ograniczenie": f_odb,
                "_wytw_ograniczenie": f_wyt,
                "_odbior_ograniczenie_opis": str(s_odb) if s_odb is not None else None,
                "_wytw_ograniczenie_opis": str(s_wyt) if s_wyt is not None else None,
                "_odbior_bez_ograniczenia_kva": _pojemnosc_bez_ograniczenia(s_odb),
                "_wytw_bez_ograniczenia_kva": _pojemnosc_bez_ograniczenia(s_wyt),
                "_wytw_dostepna_nietrwala_kw": _mw_na_kw(g("wytw_dostepna_nietrwala_mw")),
                "_wytw_zakontraktowana_kw": _mw_na_kw(g("wytw_zakontraktowana_mw")),
                "_wytw_trwala_kw": _mw_na_kw(g("wytw_trwala_mw")),
                "_zasilanie": g("zasilanie"),
                "_stacja_nadrzedna": g("stacja_nadrzedna"),
                "_styk_przesylowy": g("styk_przesylowy"),
                "_komentarz": g("komentarz"),
            })
        wb.close()

        df = self.finalize(pd.DataFrame(rekordy), document=path.name)
        notes = {
            "publikujacy": PUBLISHER,
            "jurysdykcja": JURISDICTION,
            "tryb_wydania": "arkusz kalkulacyjny na stronie publikującego",
            "wierszy": int(len(df)),
            "wierszy_bez_wspolrzednych": bez_wspolrzednych,
            "wezlow_ograniczonych": ograniczonych,
            "interpretacja_pustej_flagi": (
                "pusta komórka kolumny ograniczenia czytana jako BRAK ograniczenia; "
                "publikujący tej konwencji nie opisuje, surowa fraza w rozszerzeniu"
            ),
            "kolumny_nieznalezione": brakujace,
            "jednostka_strony_wytworczej": "MW",
            "jednostka_strony_odbiorczej": "MVA",
            "uwaga_jednostki": (
                "Pole moc_dostepna niesie dostępną moc WYTWÓRCZĄ trwałą, przeliczoną z MW "
                "na kW. Strona odbiorcza jest podana w MVA (moc pozorna) i nie jest "
                "przeliczana ani sumowana ze stroną wytwórczą; pozostaje w rozszerzeniach."
            ),
        }
        return ParseResult(frame=df, report=notes)
