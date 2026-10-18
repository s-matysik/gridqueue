"""Shared PTPiREE/PSE template for statutory disclosures under art. 7 ust. 8l pkt 1), 3) i 4).

The discovery that justifies this: the PSE spreadsheet ``Informacje_publikowane_zgodnie_z_Art_7_
ust_8l_ustawy_PE`` has a tab "Listy rozwijane", and on it a list of values for the field
"OSD/OSP": Energa-Operator S.A., ENEA Operator Sp. z o.o., TAURON Dystrybucja S.A.,
PGE Dystrybucja S.A., Stoen Operator Sp. z o.o., PSE S.A.  The template is therefore not
a form for a single company, but an AGREED INDUSTRY TEMPLATE for the six largest
operators.  The Energa-Operator publication (PDF) implements the same template as the PSE
spreadsheet (XLSX): it differs in medium and two boundary columns, not in content.

The logical columns below are this template.  The adapter for a given publisher has
one task: to say which PHYSICAL column of its document corresponds to which logical
column.  The mapping onto the 21-field schema is shared, so the difference
between publishers stays where it really is: in the document layout.

Measured physical layouts (read from headers, not assumed):

  PSE  (XLSX, 27 kolumn):  id_obiektu, nazwa_obiektu, osd_osp, podmiot, ...
  ENERGA (PDF, 28 kolumn): lp, id_obiektu, osd_osp, podmiot, ...,  uwagi

From the "osd_osp" column onward both numberings coincide: PSE has two identity
columns at the front (ID + object name), Energa one (ID) preceded by a sequence
number, and at the end adds the "UWAGI" column.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..schema import canonical_date, canonical_power_kw
from .base import harmonize_klasa, harmonize_status


#: Separators for multiple connection points within a single capacity cell.
_ROZDZ_MOC = re.compile(r"[\n\r;]+")


def _rozbij_moc(value: Any) -> list[str]:
    """Split a capacity cell into components for multiple connection points.

    A plain number is returned as a single component. A string is split on
    line breaks and semicolons, and NOT on spaces, because publishers use the
    space as the thousands separator.
    """
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [] if (isinstance(value, float) and value != value) else [str(value)]
    czesci = [c.strip() for c in _ROZDZ_MOC.split(str(value))]
    return [c for c in czesci if c and c not in {"-", "--", "---"}]

__all__ = ["LOGICAL", "PSE_XLSX_LAYOUT", "ENERGA_PDF_LAYOUT", "to_schema", "stan_na"]

#: logical columns of the PTPiREE/PSE template
LOGICAL: tuple[str, ...] = (
    "lp",
    "id_obiektu",
    "nazwa_obiektu",
    "osd_osp",
    "podmiot",
    "lokalizacja",
    "poziom_napiecia",
    "wiele_miejsc",
    "rodzaj",
    "moc_wprowadzana",
    "moc_pobierana",
    "mz_pv",
    "mz_fw",
    "mz_mee_rozladowania",
    "mz_mee_ladowania",
    "mz_odb",
    "mz_inne",
    "status",
    "data_zlozenia",
    "data_zaliczki",
    "data_warunkow",
    "data_odmowy",
    "uzasadnienie_odmowy",
    "data_utraty_waznosci",
    "data_umowy",
    "data_energizacji",
    "data_rozwiazania_umowy",
    "data_wygasniecia_umowy",
    "uwagi",
)

#: physical column index -> logical column.  PSE spreadsheet, 27 columns.
PSE_XLSX_LAYOUT: dict[int, str] = {
    0: "id_obiektu", 1: "nazwa_obiektu", 2: "osd_osp", 3: "podmiot",
    4: "lokalizacja", 5: "poziom_napiecia", 6: "wiele_miejsc", 7: "rodzaj",
    8: "moc_wprowadzana", 9: "moc_pobierana",
    10: "mz_pv", 11: "mz_fw", 12: "mz_mee_rozladowania", 13: "mz_mee_ladowania",
    14: "mz_odb", 15: "mz_inne",
    16: "status", 17: "data_zlozenia", 18: "data_zaliczki", 19: "data_warunkow",
    20: "data_odmowy", 21: "uzasadnienie_odmowy", 22: "data_utraty_waznosci",
    23: "data_umowy", 24: "data_energizacji", 25: "data_rozwiazania_umowy",
    26: "data_wygasniecia_umowy",
}

#: physical column index -> logical column.  Energa-Operator PDF, 28 columns.
ENERGA_PDF_LAYOUT: dict[int, str] = {
    0: "lp", 1: "id_obiektu", 2: "osd_osp", 3: "podmiot",
    4: "lokalizacja", 5: "poziom_napiecia", 6: "wiele_miejsc", 7: "rodzaj",
    8: "moc_wprowadzana", 9: "moc_pobierana",
    10: "mz_pv", 11: "mz_fw", 12: "mz_mee_rozladowania", 13: "mz_mee_ladowania",
    14: "mz_odb", 15: "mz_inne",
    16: "status", 17: "data_zlozenia", 18: "data_zaliczki", 19: "data_warunkow",
    20: "data_odmowy", 21: "uzasadnienie_odmowy", 22: "data_utraty_waznosci",
    23: "data_umowy", 24: "data_energizacji", 25: "data_rozwiazania_umowy",
    26: "data_wygasniecia_umowy", 27: "uwagi",
}

#: optional schema fields that the template populates for EVERY publisher
DECLARED_FIELDS: tuple[str, ...] = (
    "id_wniosku", "lokalizacja_tekst", "poziom_napiecia", "klasa_zasobu",
    "moc_wprowadzana", "moc_pobierana", "status_procesu", "data_wniosku",
    "data_warunkow", "data_odmowy", "powod_odmowy", "data_umowy",
    "data_energizacji", "data_publikacji",
)

#: extensions beyond the 21-field schema, shared by the template
DECLARED_EXTENSIONS: dict[str, str] = {
    "_podmiot": "name of the entity applying for connection",
    "_osd_osp": "operator indicated in the document (template field)",
    "_nazwa_obiektu": "proper name of the object (PSE only)",
    "_wiele_miejsc": "whether the application concerns multiple connection points / voltage levels",
    "_rodzaj_raw": "installation type as given in the document",
    "_status_raw": "project stage status as given in the document",
    "_data_zaliczki": "date the deposit was paid",
    "_data_utraty_waznosci": "date the connection conditions expired / were withdrawn",
    "_data_rozwiazania_umowy": "date the agreement was terminated / cancelled / withdrawn from",
    "_data_wygasniecia_umowy": "date the agreement expired by operation of law",
    "_mz_pv": "installed PV capacity [kW]",
    "_mz_fw": "installed FW capacity [kW]",
    "_mz_mee_rozladowania": "installed storage capacity: discharge [kW]",
    "_mz_mee_ladowania": "installed storage capacity: charge [kW]",
    "_mz_odb": "installed consumption capacity [kW]",
    "_mz_inne": "installed capacity of other sources [kW]",
    "_uwagi": "UWAGI column (Energa only)",
    "_lp_dokumentu": "sequence number in the source document",
    "_encja": "WNIOSEK or WEZEL: which entity of the duty the row implements",
}

_NULLISH = {"", "-", "--", "---", "nan", "none", "brak", "nie dotyczy", "n/d"}


def _blank(v: Any) -> bool:
    """Whether the value is blank.  ``nan`` is truthy, so ``if v`` is not enough."""
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    return isinstance(v, str) and not v.strip()


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return None if s.lower() in _NULLISH else s


def _volt(v: Any) -> Optional[str]:
    """Voltage level in canonical form "<value> kV".

    The template allows MULTIPLICITY ("110; 220; 400"): that is what the drop-down
    list of the PSE spreadsheet provides for.  We record the full content, because
    choosing a single value would lose data; the consequence is that the
    contradiction detector of type (``looks_like_voltage``) flags such rows; and
    that is how it should be, because the metric must remain COMPARABLE with
    earlier measurements, not convenient.

    CLASS values ("SN", "nn", "WN") are not numbers of kilovolts and must not have
    a unit appended to them: "SN kV" means nothing.  The panel of the four
    publishers so far records them as plain "SN", so we keep the same convention;
    otherwise the same voltage level would have two different forms within a single
    panel and the field would stop being comparable between publishers.
    """
    s = _clean(v)
    if s is None:
        return None
    if re.fullmatch(r"(?:nn|sn|wn|nN|SN|WN)", s.strip(), re.IGNORECASE):
        return s.strip().upper() if s.strip().lower() != "nn" else "nn"
    s = s.replace("\n", " ")
    s = re.sub(r"\s*kV\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s*;\s*", "; ", s)
    s = re.sub(r"\s+", " ", s).strip(" ;")
    if not s:
        return None
    # integers without ".0" after going through pandas/openpyxl
    s = re.sub(r"\b(\d+)\.0\b", r"\1", s)
    return f"{s} kV"


def stan_na(text: str) -> Optional[str]:
    """The date as of which the publisher prepared the disclosure.

    The form varies even within a single publisher: "Stan na 30.06.2026 r."
    in the list of applications and "(STAN NA DZIEŃ 31.08.2026 ROKU)" in capitals on
    the title page of the node disclosure: hence the case-insensitive match.
    """
    m = re.search(r"stan\s+na\s+(?:dzie[nń]\s+)?(\d{1,2}\.\d{1,2}\.\d{4})",
                  text or "", re.IGNORECASE)
    return canonical_date(m.group(1)) if m else None


def to_schema(raw, *, publisher_key: str, data_publikacji: Optional[str]):
    """Map a frame in the template's logical columns onto the 21-field schema.

    ``raw`` has columns from ``LOGICAL`` (missing ones may not be present).  The
    capacity unit in the template is MW: we convert to canonical kW.
    """
    import pandas as pd

    def col(name: str):
        if name in raw.columns:
            return raw[name].map(_clean)
        return pd.Series([None] * len(raw), index=raw.index, dtype="object")

    def mw(name: str):
        """Capacity from the RAW column, with support for multiple connection points.

        The trap that inflated one row by three orders of magnitude: when an
        application concerns several connection points (column "Wiele miejsc
        przyłączenia" = TAK), the publisher enters into a single cell several
        values separated by a LINE BREAK, sometimes additionally by a semicolon.
        ``_clean`` turned the line break into a space, and ``canonical_power_kw``
        treats a space as the thousands separator, so "129⏎240" (129 MW + 240 MW)
        became 129 240 MW.  In the edition where the publisher added semicolons,
        the same cell did not convert at all and the field stayed blank, meaning
        the same defect produced an absurdity in one case, and a silent gap in the
        other.

        We return the SUM of the components, because the schema field describes
        the capacity of the application, and there is one application. We keep the
        components in the extension, so as not to lose the breakdown by
        connection point.
        """
        if name not in raw.columns:
            return (pd.Series([None] * len(raw), index=raw.index, dtype="object"),
                    pd.Series([None] * len(raw), index=raw.index, dtype="object"))
        sumy, skladowe = [], []
        for v in raw[name]:
            czesci = _rozbij_moc(v)
            vals = [canonical_power_kw(c, "MW") for c in czesci]
            vals = [x for x in vals if x is not None]
            if not vals:
                sumy.append(None)
                skladowe.append(None)
            elif len(vals) == 1:
                sumy.append(vals[0])
                skladowe.append(None)
            else:
                sumy.append(float(sum(vals)))
                skladowe.append("; ".join(f"{x / 1000.0:g}" for x in vals))
        return (pd.Series(sumy, index=raw.index, dtype="object"),
                pd.Series(skladowe, index=raw.index, dtype="object"))

    def dcol(name: str):
        """Date from the RAW column, without going through ``_clean``.

        The trap that cost all the PSE dates: the PSE medium is XLSX, and
        openpyxl returns date cells as ``Timestamp``.  ``_clean`` calls ``str()``
        on the value, so a Timestamp turned into "2023-08-07 00:00:00", and
        ``canonical_date`` has ANCHORED patterns and does not match such a string:
        it returned None.  Effect: the ``data_*`` fields went empty for the entire
        publisher, and quality rules R1 and R2 (date monotonicity, the two-year
        validity of conditions) had nothing to work on and showed zero violations.
        ``canonical_date`` itself handles ``datetime``/``date``, so it is enough to
        pass it the untouched value.
        """
        if name not in raw.columns:
            return pd.Series([None] * len(raw), index=raw.index, dtype="object")
        return raw[name].map(lambda v: None if _blank(v) else canonical_date(v))

    out = pd.DataFrame(index=raw.index)
    ident = col("id_obiektu")
    lp = col("lp")
    # Watch out for the trap: ``Series.map`` turns a returned ``None`` into ``nan``,
    # and ``nan`` is TRUTHY in Python.  The emptiness test must be explicit, otherwise
    # the identifier fallback never runs, and 866 of 876 PSE rows
    # (those with "-" in the ID Obiektu field) are left without an identifier.
    out["id_wniosku"] = [
        i if not _blank(i)
        else f"{publisher_key}:poz:{(str(l).rstrip('.') if not _blank(l) else str(k + 1))}"
        for k, (i, l) in enumerate(zip(ident, lp))
    ]
    out["lokalizacja_tekst"] = col("lokalizacja")
    out["poziom_napiecia"] = col("poziom_napiecia").map(_volt)
    out["klasa_zasobu"] = col("rodzaj").map(harmonize_klasa)
    out["moc_wprowadzana"], _skl_wpr = mw("moc_wprowadzana")
    out["moc_pobierana"], _skl_pob = mw("moc_pobierana")
    out["status_procesu"] = col("status").map(harmonize_status)
    out["data_wniosku"] = dcol("data_zlozenia")
    out["data_warunkow"] = dcol("data_warunkow")
    out["data_odmowy"] = dcol("data_odmowy")
    out["powod_odmowy"] = col("uzasadnienie_odmowy")
    out["data_umowy"] = dcol("data_umowy")
    # Energa records the planned energization as an INEQUALITY ("po 30.06.2026"),
    # not a date.  ``canonical_date`` is anchored at the start of the string, so it
    # rightly returns None: recording 2026-06-30 would lose the word "po" and turn
    # a lower bound into an exact date.  However, to avoid losing the data, the raw
    # text goes into the extension, and the schema field remains blank.
    _energ = col("data_energizacji")
    out["data_energizacji"] = dcol("data_energizacji")
    out["_energizacja_tekst"] = [
        t if (not _blank(t) and canonical_date(t) is None) else None for t in _energ
    ]
    out["data_publikacji"] = data_publikacji

    out["_encja"] = "WNIOSEK"
    out["_podmiot"] = col("podmiot")
    out["_osd_osp"] = col("osd_osp")
    out["_nazwa_obiektu"] = col("nazwa_obiektu")
    out["_wiele_miejsc"] = col("wiele_miejsc")
    out["_rodzaj_raw"] = col("rodzaj")
    out["_status_raw"] = col("status")
    out["_data_zaliczki"] = dcol("data_zaliczki")
    out["_data_utraty_waznosci"] = dcol("data_utraty_waznosci")
    out["_data_rozwiazania_umowy"] = dcol("data_rozwiazania_umowy")
    out["_data_wygasniecia_umowy"] = dcol("data_wygasniecia_umowy")
    for src, dst in (("mz_pv", "_mz_pv"), ("mz_fw", "_mz_fw"),
                     ("mz_mee_rozladowania", "_mz_mee_rozladowania"),
                     ("mz_mee_ladowania", "_mz_mee_ladowania"),
                     ("mz_odb", "_mz_odb"), ("mz_inne", "_mz_inne")):
        out[dst], _ = mw(src)
    out["_uwagi"] = col("uwagi")
    out["_moc_wprowadzana_skladowe_mw"] = _skl_wpr
    out["_moc_pobierana_skladowe_mw"] = _skl_pob
    out["_lp_dokumentu"] = lp
    return out
