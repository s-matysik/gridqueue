"""Adapter: e-Distribución Redes Digitales (ES), connection capacity of nodes.

Why this source matters more to the package than another tabular file
---------------------------------------------------------------------
The manuscript identified as the strongest missing test **a second jurisdiction
publishing documents intended for print**: so far both foreign sources
published data that was already tabular, so portability was demonstrated on a case
easier than the Polish one. This source closes that gap. The publisher issues a **monthly
PDF**, in a series covering the years 2023-2025, pursuant to Art. 33(9)
of Act 24/2013, Art. 5(4) of Decree 1183/2020, and Art. 12 of CNMC Circular 1/2021,
so the legal construction is the same as in Poland: a statutory
duty, fixed frequency, format left to the publisher.

The page layout carries the vector lines of the table, so extraction relies on them,
not on the spacing between words.

Column semantics fixed by arithmetic, not by the header
---------------------------------------------------------
The header has cells merged across two levels and suggests that the columns „Con
permiso de AyC" and „En trámite con capacidad" belong to the group of accepted and
unresolved capacity. **This is misleading.** The arithmetic of the document is decisive:

* eleven subcolumns, nine station positions plus these two, **sum up to the
  OCCUPIED capacity**, exactly, in 1838 of 1838 rows, in both editions checked;
* the technology breakdown sums up to the **accepted and unresolved** capacity
  in all rows with a nonzero value.

Both groups are therefore COMPONENTS of the occupied capacity, not alternative
breakdowns of it: some nodes have only the positions filled in, some only the two
remaining ones, and some both, and only the sum of all eleven closes to
the total value.

This has value beyond the mapping of fields. For this publisher there **is no
reference set read independently of the parser**, so the accuracy of
extraction cannot be measured the way it was measured for the Polish
publishers. The arithmetic closure is here a substitute, weaker but checkable
piece of evidence: for the sum of eleven cells to match the twelfth, all
twelve must be read correctly. Over two editions this gives 3676
independent checks, all closed. This is evidence of consistency of
reading, NOT a measurement of accuracy against a reference, and it should be read as such.

Units
-----
The publisher states capacities in **MW of active power**, so converting to the canonical
kW is a plain change of order of magnitude, without assumptions. This differentiates this source from
the Portuguese one, which states apparent power in MVA and therefore does not populate the capacity field.

The source also provides **geographic coordinates for each substation**, which no
Polish publisher does.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import Adapter, ParseResult

PUBLISHER = "e-Distribución Redes Digitales S.L.U."
JURISDICTION = "ES"

#: Column indices in the extracted table. Fixed on the August 2025 edition
#: and verified by sums; see the module header.
K_WSPOLNOTA, K_PROWINCJA, K_GMINA, K_PODSTACJA = 0, 1, 2, 3
K_SZEROKOSC, K_DLUGOSC, K_NAPIECIE = 4, 5, 6
K_DOSTEPNA, K_ZAJETA_TOTAL = 7, 8
K_POZYCJE = tuple(range(9, 18))          # breakdown of occupied capacity by station position
K_ZAJETA_Z_POZWOLENIEM, K_ZAJETA_W_TOKU = 18, 19
K_PRZYJETA_TOTAL = 20                     # accepted and unresolved
K_TECHNOLOGIE = (21, 22, 23, 24, 25)
K_SCC, K_WEZEL_PRZESYLOWY, K_KOMENTARZ = 26, 27, 28
SZEROKOSC_WIERSZA = 29

_WSPOLNOTA = re.compile(r"^\d{2}\s*-\s*")


def _liczba(v) -> float | None:
    """Number in Spanish notation: decimal comma, thousands dot."""
    if v is None:
        return None
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s in {"", "-", "--"}:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _mw_na_kw(v) -> float | None:
    """MW of active power -> kW of active power. A change of order of magnitude, not of physical quantity."""
    x = _liczba(v)
    return None if x is None else x * 1000.0


def _data_z_nazwy(nazwa: str) -> str | None:
    """'EDRD_Capacidad_de_Acceso_2025_08_01.pdf' -> '2025-08-01'.

    The date is taken from the file name, not from the title page, because the name is
    machine-readable and decidable, while the title page gives it in words, in Spanish.
    """
    m = re.search(r"(\d{4})[_-](\d{2})[_-](\d{2})", nazwa)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def suma_skladnikow_mocy_zajetej(wiersze) -> "tuple[int, int]":
    """How many rows close the arithmetic identity of the document.

    The eleven subcolumns of occupied capacity (nine station positions plus "with
    permit" and "in progress") sum up to the total value. The function returns
    a pair (closed, total).

    What this is for: for this publisher there is no reference set read
    independently of the parser, so the accuracy of extraction cannot be measured against
    a reference. The arithmetic closure is a substitute piece of evidence of consistency of
    reading, weaker than a reference, but checkable on every edition, because it requires
    all twelve cells of the block to be read correctly.
    """
    domkniete = 0
    for w in wiersze:
        if not w or len(w) != SZEROKOSC_WIERSZA:
            continue
        laczna = _liczba(w[K_ZAJETA_TOTAL])
        if laczna is None:
            continue
        skladniki = [_liczba(w[i]) or 0.0
                     for i in (*K_POZYCJE, K_ZAJETA_Z_POZWOLENIEM, K_ZAJETA_W_TOKU)]
        if round(sum(skladniki), 2) == round(laczna, 2):
            domkniete += 1
    return domkniete, sum(1 for w in wiersze
                          if w and len(w) == SZEROKOSC_WIERSZA
                          and _liczba(w[K_ZAJETA_TOTAL]) is not None)


class EDistribucionAdapter(Adapter):
    publisher = PUBLISHER
    jurisdiction = JURISDICTION
    declared_fields = (
        "id_wezla", "nazwa_wezla", "lokalizacja_tekst", "wspolrzedne", "poziom_napiecia",
        "moc_dostepna", "moc_zarezerwowana", "ograniczenie_flaga", "data_publikacji",
    )
    declared_extensions = {
        "_wspolnota_autonomiczna": "autonomous community",
        "_prowincja": "province",
        "_moc_przyjeta_nierozstrzygnieta_kw": "capacity of accepted and unresolved applications",
        "_moc_zajeta_z_pozwoleniem_kw": "part of the occupied capacity covered by a connection permit",
        "_moc_zajeta_w_toku_kw": "part of the occupied capacity currently in proceedings",
        "_rozbicie_technologiczne_kw": "unresolved capacity broken down by technology",
        "_rozbicie_pozycyjne_kw": "occupied capacity broken down by station position",
        "_wezel_przesylowy": "transmission network node with the greatest impact",
        "_komentarz": "publisher's comment",
    }
    detect_patterns = (r"edrd[_ ]?capacidad", r"capacidad[_ ]de[_ ]acceso", r"e-?distribuci")

    def parse(self, source) -> ParseResult:
        import pandas as pd
        import pdfplumber

        path = Path(str(source))
        data_pub = _data_z_nazwy(path.name)

        surowe, stron = [], 0
        with pdfplumber.open(path) as pdf:
            stron = len(pdf.pages)
            for strona in pdf.pages:
                for tabela in strona.extract_tables():
                    for wiersz in tabela:
                        if (wiersz and len(wiersz) == SZEROKOSC_WIERSZA
                                and _WSPOLNOTA.match(str(wiersz[K_WSPOLNOTA] or ""))):
                            surowe.append(wiersz)

        domkniete, sprawdzonych = suma_skladnikow_mocy_zajetej(surowe)
        rekordy, ograniczonych, bez_wspolrzednych = [], 0, 0
        for w in surowe:
            def kom(i):
                v = w[i]
                return None if v is None or str(v).strip() == "" else str(v).strip()

            lat, lon = _liczba(w[K_SZEROKOSC]), _liczba(w[K_DLUGOSC])
            if lat is None or lon is None:
                bez_wspolrzednych += 1
            scc = (kom(K_SCC) or "").upper()
            ogr = {"SI": True, "SÍ": True, "NO": False}.get(scc)
            if ogr:
                ograniczonych += 1
            napiecie = kom(K_NAPIECIE)
            podstacja = kom(K_PODSTACJA)

            tech = {i: _mw_na_kw(w[i]) for i in K_TECHNOLOGIE}
            poz = {i: _mw_na_kw(w[i]) for i in K_POZYCJE}

            rekordy.append({
                # The identifier must distinguish between voltage levels of the same substation:
                # the publisher issues a separate row for each level.
                "id_wezla": f"{podstacja}|{napiecie}" if podstacja and napiecie else podstacja,
                "nazwa_wezla": podstacja,
                "lokalizacja_tekst": ", ".join(x for x in (kom(K_GMINA), kom(K_PROWINCJA)) if x) or None,
                "wspolrzedne": f"{lat},{lon}" if lat is not None and lon is not None else None,
                "poziom_napiecia": f"{napiecie} kV" if napiecie else None,
                "moc_dostepna": _mw_na_kw(w[K_DOSTEPNA]),
                "moc_zarezerwowana": _mw_na_kw(w[K_ZAJETA_TOTAL]),
                "ograniczenie_flaga": ogr,
                "data_publikacji": data_pub,
                "_encja": "WEZEL",
                "_wspolnota_autonomiczna": kom(K_WSPOLNOTA),
                "_prowincja": kom(K_PROWINCJA),
                "_moc_przyjeta_nierozstrzygnieta_kw": _mw_na_kw(w[K_PRZYJETA_TOTAL]),
                "_moc_zajeta_z_pozwoleniem_kw": _mw_na_kw(w[K_ZAJETA_Z_POZWOLENIEM]),
                "_moc_zajeta_w_toku_kw": _mw_na_kw(w[K_ZAJETA_W_TOKU]),
                "_rozbicie_technologiczne_kw": ";".join(
                    f"{i}={v:.1f}" for i, v in tech.items() if v) or None,
                "_rozbicie_pozycyjne_kw": ";".join(
                    f"{i}={v:.1f}" for i, v in poz.items() if v) or None,
                "_wezel_przesylowy": kom(K_WEZEL_PRZESYLOWY),
                "_komentarz": kom(K_KOMENTARZ),
            })

        df = self.finalize(pd.DataFrame(rekordy), document=path.name)
        notes = {
            "publikujacy": PUBLISHER,
            "jurysdykcja": JURISDICTION,
            "tryb_wydania": "document intended for print, monthly edition",
            "stron": stron,
            "wierszy": int(len(df)),
            "wezlow_ograniczonych_przez_Scc": ograniczonych,
            "wierszy_bez_wspolrzednych": bez_wspolrzednych,
            "jednostka_mocy_zrodlowa": "MW",
            "przeliczenie": "MW -> kW, both quantities are active power",
            "data_publikacji": data_pub,
            "tozsamosc_sumy_mocy_zajetej": f"{domkniete}/{sprawdzonych}",
            "uwaga_tozsamosc": (
                "The eleven subcolumns of occupied capacity sum up to the total value. "
                "This is evidence of the CONSISTENCY of reading, not a measurement of accuracy against "
                "a reference read independently of the parser; this publisher has no "
                "such reference."
            ),
        }
        return ParseResult(frame=df, report=notes)
