"""Adapter: ESB Networks (IE), network connection capacity map.

The publisher issues a single sheet covering **the entire network down to MV/LV
station level**, which makes it the most numerous source in the panel and also the
only one that goes below high-voltage station level. The row unit is a group of
transformers at a station.

Two units in one source
------------------------------
The publisher gives the **demand side in MVA** (apparent power), and the
**generation side in MW** (active power). The canonical unit of the schema is kW
of active power, so:

* generation values are converted (MW -> kW, the same physical quantity),
* demand values are **not converted** and go into extension fields
  with the unit explicitly recorded.

The `moc_dostepna` field therefore carries the available **firm generation**
capacity, not the sum of both sides. Summing MW with MVA would give a number with
no physical meaning, and choosing one side without saying so explicitly would be
hiding the decision.

The source gives coordinates and two separate constraint flags, for the demand
side and the generation side. The `ograniczenie_flaga` field receives the
**disjunction of both**, because the schema has a single field; both source values
remain in the extensions.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import Adapter, ParseResult

PUBLISHER = "ESB Networks DAC"
JURISDICTION = "IE"
ARKUSZ = "Heatmap data"

#: The header spans two rows; the proper names are in the second one.
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

#: The constraint columns carry the phrase "Constrained, otherwise capacity available = X kVA"
#: or are empty. We assume that an empty cell means NO constraint, not an absence of a
#: declaration: the column is a binary indicator, where a positive value carries an
#: explanation, and a negative one is expressed by emptiness. This is an INTERPRETATION, not
#: content of the source (the publisher nowhere describes this convention), so the raw
#: phrase remains in the extension, and the decision is recorded in the adapter report.
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
    """Constraint indicator; an empty cell means no constraint (see above)."""
    if v is None or str(v).strip() == "":
        return False
    s = str(v).strip().lower()
    if s in _TAK:
        return True
    if s in _NIE:
        return False
    return True if _FRAZA_OGRANICZENIA.search(s) else None


def _pojemnosc_bez_ograniczenia(v) -> float | None:
    """Extract X from the phrase 'Constrained, otherwise capacity available = X kVA'.

    The value is in kVA, i.e. apparent power, so it is NOT converted to kW
    and stays in the extension with the unit in the field name.
    """
    if v is None:
        return None
    m = _POJEMNOSC_W_FRAZIE.search(str(v))
    return _liczba(m.group(1)) if m else None


def _alternatywa(a: bool | None, b: bool | None) -> bool | None:
    """Disjunction preserving indeterminacy: None or False -> None, not False."""
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
        "_jednostka_mocy_odbiorczej": "unit of the demand side at the publisher (MVA)",
        "_klasa_napiecia": "voltage class per the publisher",
        "_konfiguracja_transformatorow": "configuration of the transformer group",
        "_moc_zainstalowana_mva": "installed capacity of the transformers",
        "_odbior_dostepna_mva": "available demand capacity",
        "_odbior_trwala_mva": "firm demand capacity",
        "_odbior_nadrzedna_mva": "available demand capacity of the parent station",
        "_odbior_ograniczenie": "constraint on the demand side",
        "_wytw_ograniczenie": "constraint on the generation side",
        "_odbior_ograniczenie_opis": "raw constraint phrase on the demand side",
        "_wytw_ograniczenie_opis": "raw constraint phrase on the generation side",
        "_odbior_bez_ograniczenia_kva": "demand capacity available if not for the constraint",
        "_wytw_bez_ograniczenia_kva": "generation capacity available if not for the constraint",
        "_wytw_dostepna_nietrwala_kw": "available non-firm generation capacity",
        "_wytw_zakontraktowana_kw": "total contracted generation capacity",
        "_wytw_trwala_kw": "firm generation capacity",
        "_zasilanie": "feeder line",
        "_stacja_nadrzedna": "parent station",
        "_styk_przesylowy": "station of interface with the transmission network",
        "_komentarz": "publisher's comment",
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
                # The generation side is in MW of active power, the only one that is convertible.
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
            "tryb_wydania": "spreadsheet on the publisher's website",
            "wierszy": int(len(df)),
            "wierszy_bez_wspolrzednych": bez_wspolrzednych,
            "wezlow_ograniczonych": ograniczonych,
            "interpretacja_pustej_flagi": (
                "empty cell of the constraint column read as NO constraint; "
                "the publisher does not describe this convention, raw phrase in the extension"
            ),
            "kolumny_nieznalezione": brakujace,
            "jednostka_strony_wytworczej": "MW",
            "jednostka_strony_odbiorczej": "MVA",
            "uwaga_jednostki": (
                "The moc_dostepna field carries the available firm GENERATION capacity, "
                "converted from MW to kW. The demand side is given in MVA (apparent power) "
                "and is not converted nor summed with the generation side; it remains in "
                "the extensions."
            ),
        }
        return ParseResult(frame=df, report=notes)
