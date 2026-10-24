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
K_COMMUNITY, K_PROVINCE, K_MUNICIPALITY, K_SUBSTATION = 0, 1, 2, 3
K_LATITUDE, K_LONGITUDE, K_VOLTAGE = 4, 5, 6
K_AVAILABLE, K_OCCUPIED_TOTAL = 7, 8
K_ITEMS = tuple(range(9, 18))          # breakdown of occupied capacity by station position
K_OCCUPIED_WITH_PERMIT, K_OCCUPIED_IN_PROGRESS = 18, 19
K_ACCEPTED_TOTAL = 20                     # accepted and unresolved
K_TECHNOLOGIES = (21, 22, 23, 24, 25)
K_SCC, K_TRANSMISSION_NODE, K_COMMENT = 26, 27, 28
ROW_WIDTH = 29

_COMMUNITY = re.compile(r"^\d{2}\s*-\s*")


def _count(v) -> float | None:
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


def _mw_per_kw(v) -> float | None:
    """MW of active power -> kW of active power. A change of order of magnitude, not of physical quantity."""
    x = _count(v)
    return None if x is None else x * 1000.0


def _date_from_name(name: str) -> str | None:
    """'EDRD_Capacidad_de_Acceso_2025_08_01.pdf' -> '2025-08-01'.

    The date is taken from the file name, not from the title page, because the name is
    machine-readable and decidable, while the title page gives it in words, in Spanish.
    """
    m = re.search(r"(\d{4})[_-](\d{2})[_-](\d{2})", name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def total_occupied_capacity_components(rows) -> "tuple[int, int]":
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
    closed = 0
    for w in rows:
        if not w or len(w) != ROW_WIDTH:
            continue
        total_cap = _count(w[K_OCCUPIED_TOTAL])
        if total_cap is None:
            continue
        components = [_count(w[i]) or 0.0
                     for i in (*K_ITEMS, K_OCCUPIED_WITH_PERMIT, K_OCCUPIED_IN_PROGRESS)]
        if round(sum(components), 2) == round(total_cap, 2):
            closed += 1
    return closed, sum(1 for w in rows
                          if w and len(w) == ROW_WIDTH
                          and _count(w[K_OCCUPIED_TOTAL]) is not None)


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
        date_published = _date_from_name(path.name)

        raw, pages = [], 0
        with pdfplumber.open(path) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages:
                for table in page.extract_tables():
                    for row in table:
                        if (row and len(row) == ROW_WIDTH
                                and _COMMUNITY.match(str(row[K_COMMUNITY] or ""))):
                            raw.append(row)

        closed, checked = total_occupied_capacity_components(raw)
        records, limited, without_coordinates = [], 0, 0
        for w in raw:
            def kom(i):
                v = w[i]
                return None if v is None or str(v).strip() == "" else str(v).strip()

            lat, lon = _count(w[K_LATITUDE]), _count(w[K_LONGITUDE])
            if lat is None or lon is None:
                without_coordinates += 1
            scc = (kom(K_SCC) or "").upper()
            limit = {"SI": True, "SÍ": True, "NO": False}.get(scc)
            if limit:
                limited += 1
            voltage = kom(K_VOLTAGE)
            substation = kom(K_SUBSTATION)

            tech = {i: _mw_per_kw(w[i]) for i in K_TECHNOLOGIES}
            positions = {i: _mw_per_kw(w[i]) for i in K_ITEMS}

            records.append({
                # The identifier must distinguish between voltage levels of the same substation:
                # the publisher issues a separate row for each level.
                "id_wezla": f"{substation}|{voltage}" if substation and voltage else substation,
                "nazwa_wezla": substation,
                "lokalizacja_tekst": ", ".join(x for x in (kom(K_MUNICIPALITY), kom(K_PROVINCE)) if x) or None,
                "wspolrzedne": f"{lat},{lon}" if lat is not None and lon is not None else None,
                "poziom_napiecia": f"{voltage} kV" if voltage else None,
                "moc_dostepna": _mw_per_kw(w[K_AVAILABLE]),
                "moc_zarezerwowana": _mw_per_kw(w[K_OCCUPIED_TOTAL]),
                "ograniczenie_flaga": limit,
                "data_publikacji": date_published,
                "_encja": "WEZEL",
                "_wspolnota_autonomiczna": kom(K_COMMUNITY),
                "_prowincja": kom(K_PROVINCE),
                "_moc_przyjeta_nierozstrzygnieta_kw": _mw_per_kw(w[K_ACCEPTED_TOTAL]),
                "_moc_zajeta_z_pozwoleniem_kw": _mw_per_kw(w[K_OCCUPIED_WITH_PERMIT]),
                "_moc_zajeta_w_toku_kw": _mw_per_kw(w[K_OCCUPIED_IN_PROGRESS]),
                "_rozbicie_technologiczne_kw": ";".join(
                    f"{i}={v:.1f}" for i, v in tech.items() if v) or None,
                "_rozbicie_pozycyjne_kw": ";".join(
                    f"{i}={v:.1f}" for i, v in positions.items() if v) or None,
                "_wezel_przesylowy": kom(K_TRANSMISSION_NODE),
                "_komentarz": kom(K_COMMENT),
            })

        df = self.finalize(pd.DataFrame(records), document=path.name)
        notes = {
            "publisher": PUBLISHER,
            "jurisdiction": JURISDICTION,
            "release_mode": "document intended for print, monthly edition",
            "pages": pages,
            "rows": int(len(df)),
            "nodes_limited_by_Scc": limited,
            "rows_without_coordinates": without_coordinates,
            "source_capacity_unit": "MW",
            "recalculation": "MW -> kW, both quantities are active power",
            "data_publikacji": date_published,
            "identity_sum_occupied_capacity": f"{closed}/{checked}",
            "note_identity": (
                "The eleven subcolumns of occupied capacity sum up to the total value. "
                "This is evidence of the CONSISTENCY of reading, not a measurement of accuracy against "
                "a reference read independently of the parser; this publisher has no "
                "such reference."
            ),
        }
        return ParseResult(frame=df, report=notes)
