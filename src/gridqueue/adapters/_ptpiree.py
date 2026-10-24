"""Shared PTPiREE/PSE template for statutory disclosures under Art. 7(8l)(1), (3) and (4).

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

  PSE  (XLSX, 27 kolumn):  object_id, object_name, osd_osp, podmiot, ...
  ENERGA (PDF, 28 kolumn): lp, object_id, osd_osp, podmiot, ...,  uwagi

From the "osd_osp" column onward both numberings coincide: PSE has two identity
columns at the front (ID + object name), Energa one (ID) preceded by a sequence
number, and at the end adds the "UWAGI" column.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..schema import canonical_date, canonical_power_kw
from .base import harmonize_class, harmonize_status


#: Separators for multiple connection points within a single capacity cell.
_CAPACITY_SPLIT = re.compile(r"[\n\r;]+")


def _split_capacity(value: Any) -> list[str]:
    """Split a capacity cell into components for multiple connection points.

    A plain number is returned as a single component. A string is split on
    line breaks and semicolons, and NOT on spaces, because publishers use the
    space as the thousands separator.
    """
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [] if (isinstance(value, float) and value != value) else [str(value)]
    parts = [c.strip() for c in _CAPACITY_SPLIT.split(str(value))]
    return [c for c in parts if c and c not in {"-", "--", "---"}]

__all__ = ["LOGICAL", "PSE_XLSX_LAYOUT", "ENERGA_PDF_LAYOUT", "to_schema", "parse_as_at"]

#: logical columns of the PTPiREE/PSE template
LOGICAL: tuple[str, ...] = (
    "item_no",
    "object_id",
    "object_name",
    "osd_osp",
    "applicant",
    "location",
    "voltage_level",
    "multiple_places",
    "kind",
    "capacity_injected",
    "capacity_withdrawn",
    "mz_pv",
    "mz_fw",
    "mz_mee_discharging",
    "mz_mee_charging",
    "mz_odb",
    "mz_other",
    "status",
    "date_submission",
    "date_advance_payment",
    "date_conditions",
    "date_refusal",
    "refusal_justification",
    "date_expiry",
    "date_agreement",
    "date_energisation",
    "date_contract_termination",
    "date_contract_expiration",
    "notes",
)

#: physical column index -> logical column.  PSE spreadsheet, 27 columns.
PSE_XLSX_LAYOUT: dict[int, str] = {
    0: "object_id", 1: "object_name", 2: "osd_osp", 3: "applicant",
    4: "location", 5: "voltage_level", 6: "multiple_places", 7: "kind",
    8: "capacity_injected", 9: "capacity_withdrawn",
    10: "mz_pv", 11: "mz_fw", 12: "mz_mee_discharging", 13: "mz_mee_charging",
    14: "mz_odb", 15: "mz_other",
    16: "status", 17: "date_submission", 18: "date_advance_payment", 19: "date_conditions",
    20: "date_refusal", 21: "refusal_justification", 22: "date_expiry",
    23: "date_agreement", 24: "date_energisation", 25: "date_contract_termination",
    26: "date_contract_expiration",
}

#: physical column index -> logical column.  Energa-Operator PDF, 28 columns.
ENERGA_PDF_LAYOUT: dict[int, str] = {
    0: "item_no", 1: "object_id", 2: "osd_osp", 3: "applicant",
    4: "location", 5: "voltage_level", 6: "multiple_places", 7: "kind",
    8: "capacity_injected", 9: "capacity_withdrawn",
    10: "mz_pv", 11: "mz_fw", 12: "mz_mee_discharging", 13: "mz_mee_charging",
    14: "mz_odb", 15: "mz_other",
    16: "status", 17: "date_submission", 18: "date_advance_payment", 19: "date_conditions",
    20: "date_refusal", 21: "refusal_justification", 22: "date_expiry",
    23: "date_agreement", 24: "date_energisation", 25: "date_contract_termination",
    26: "date_contract_expiration", 27: "notes",
}

#: optional schema fields that the template populates for EVERY publisher
DECLARED_FIELDS: tuple[str, ...] = (
    "application_id", "location_text", "voltage_level", "resource_class",
    "capacity_injected", "capacity_withdrawn", "process_status", "date_application",
    "date_conditions", "date_refusal", "refusal_reason", "date_agreement",
    "date_energisation", "date_published",
)

#: extensions beyond the 21-field schema, shared by the template
DECLARED_EXTENSIONS: dict[str, str] = {
    "_applicant": "name of the entity applying for connection",
    "_dso_tso": "operator indicated in the document (template field)",
    "_facility_name": "proper name of the object (PSE only)",
    "_multiple_points": "whether the application concerns multiple connection points / voltage levels",
    "_kind_raw": "installation type as given in the document",
    "_status_raw": "project stage status as given in the document",
    "_date_advance_payment": "date the deposit was paid",
    "_date_expiry": "date the connection conditions expired / were withdrawn",
    "_date_agreement_termination": "date the agreement was terminated / cancelled / withdrawn from",
    "_date_agreement_lapse": "date the agreement expired by operation of law",
    "_ic_pv": "installed PV capacity [kW]",
    "_ic_wind": "installed FW capacity [kW]",
    "_ic_storage_discharging": "installed storage capacity: discharge [kW]",
    "_ic_storage_charging": "installed storage capacity: charge [kW]",
    "_ic_load": "installed consumption capacity [kW]",
    "_ic_other": "installed capacity of other sources [kW]",
    "_remarks": "UWAGI column (Energa only)",
    "_document_item_no": "sequence number in the source document",
    "_entity": "APPLICATION or NODE: which entity of the duty the row implements",
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


def parse_as_at(text: str) -> Optional[str]:
    """The date as of which the publisher prepared the disclosure.

    The form varies even within a single publisher: "Stan na 30.06.2026 r."
    in the list of applications and "(STAN NA DZIEŃ 31.08.2026 ROKU)" in capitals on
    the title page of the node disclosure: hence the case-insensitive match.
    """
    m = re.search(r"stan\s+na\s+(?:dzie[nń]\s+)?(\d{1,2}\.\d{1,2}\.\d{4})",
                  text or "", re.IGNORECASE)
    return canonical_date(m.group(1)) if m else None


def to_schema(raw, *, publisher_key: str, publication_date: Optional[str]):
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
        became 129,240 MW.  In the edition where the publisher added semicolons,
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
        totals, components = [], []
        for v in raw[name]:
            parts = _split_capacity(v)
            vals = [canonical_power_kw(c, "MW") for c in parts]
            vals = [x for x in vals if x is not None]
            if not vals:
                totals.append(None)
                components.append(None)
            elif len(vals) == 1:
                totals.append(vals[0])
                components.append(None)
            else:
                totals.append(float(sum(vals)))
                components.append("; ".join(f"{x / 1000.0:g}" for x in vals))
        return (pd.Series(totals, index=raw.index, dtype="object"),
                pd.Series(components, index=raw.index, dtype="object"))

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
    ident = col("object_id")
    item_no = col("item_no")
    # Watch out for the trap: ``Series.map`` turns a returned ``None`` into ``nan``,
    # and ``nan`` is TRUTHY in Python.  The emptiness test must be explicit, otherwise
    # the identifier fallback never runs, and 866 of 876 PSE rows
    # (those with "-" in the ID Obiektu field) are left without an identifier.
    out["application_id"] = [
        i if not _blank(i)
        else f"{publisher_key}:poz:{(str(l).rstrip('.') if not _blank(l) else str(k + 1))}"
        for k, (i, l) in enumerate(zip(ident, item_no))
    ]
    out["location_text"] = col("location")
    out["voltage_level"] = col("voltage_level").map(_volt)
    out["resource_class"] = col("kind").map(harmonize_class)
    out["capacity_injected"], _injection_component = mw("capacity_injected")
    out["capacity_withdrawn"], _withdrawal_component = mw("capacity_withdrawn")
    out["process_status"] = col("status").map(harmonize_status)
    out["date_application"] = dcol("date_submission")
    out["date_conditions"] = dcol("date_conditions")
    out["date_refusal"] = dcol("date_refusal")
    out["refusal_reason"] = col("refusal_justification")
    out["date_agreement"] = dcol("date_agreement")
    # Energa records the planned energization as an INEQUALITY ("po 30.06.2026"),
    # not a date.  ``canonical_date`` is anchored at the start of the string, so it
    # rightly returns None: recording 2026-06-30 would lose the word "po" and turn
    # a lower bound into an exact date.  However, to avoid losing the data, the raw
    # text goes into the extension, and the schema field remains blank.
    _energ = col("date_energisation")
    out["date_energisation"] = dcol("date_energisation")
    out["_energisation_text"] = [
        t if (not _blank(t) and canonical_date(t) is None) else None for t in _energ
    ]
    out["date_published"] = publication_date

    out["_entity"] = "APPLICATION"
    out["_applicant"] = col("applicant")
    out["_dso_tso"] = col("osd_osp")
    out["_facility_name"] = col("object_name")
    out["_multiple_points"] = col("multiple_places")
    out["_kind_raw"] = col("kind")
    out["_status_raw"] = col("status")
    out["_date_advance_payment"] = dcol("date_advance_payment")
    out["_date_expiry"] = dcol("date_expiry")
    out["_date_agreement_termination"] = dcol("date_contract_termination")
    out["_date_agreement_lapse"] = dcol("date_contract_expiration")
    for src, dst in (("mz_pv", "_ic_pv"), ("mz_fw", "_ic_wind"),
                     ("mz_mee_discharging", "_ic_storage_discharging"),
                     ("mz_mee_charging", "_ic_storage_charging"),
                     ("mz_odb", "_ic_load"), ("mz_other", "_ic_other")):
        out[dst], _ = mw(src)
    out["_remarks"] = col("notes")
    out["_capacity_injected_components_mw"] = _injection_component
    out["_capacity_withdrawn_components_mw"] = _withdrawal_component
    out["_document_item_no"] = item_no
    return out
