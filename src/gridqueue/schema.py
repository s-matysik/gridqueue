"""Common schema for connection-queue disclosures (statutory connection-queue disclosure).

The schema is derived from the STRUCTURE OF THE STATUTORY DUTY, not from the layout of a
particular document.  Article 7(8l) of the Act of 10 April 1997, the Energy Law,
imposes four separate disclosure duties on the distribution system operator:

  point 1  : entities applying for the connection of sources (who, where, how much capacity,
            what resource, at what stage)                     -> APPLICATION entity
  point 2  : total available connection capacity and its planned changes over the
            next 5 years, broken down by station or group of stations
                                                             -> NODE entity
  point 3  : applications filed for determination of connection conditions -> APPLICATION entity
  point 4  : refusals issued for determination of connection conditions     -> APPLICATION entity

From this follow three axes, which the schema maps as field groups:

  IDENTITY   : what is being connected and where (application_id, node_id, node_name,
                location_text, coordinates, voltage_level, resource_class)
  CAPACITY   : how much capacity, in which direction, and how much of it is still left
                (capacity_injected, capacity_withdrawn, capacity_available, capacity_reserved,
                 constraint_flag, queue_position)
  PROCESS    : where the case stands in the administrative proceedings
                (process_status, date_application, date_conditions, date_refusal,
                 refusal_reason, date_agreement, date_energisation, date_published)

The PROCESS axis is a direct mapping of the statute's procedural path: application ->
(advance payment) -> connection conditions or refusal -> connection agreement ->
start of energy supply.  Connection conditions are valid for two years
(Article 7(8i)), which makes the pair (date_conditions, date_agreement) a checkable rule,
not just two columns.

The MANDATORY CORE (5 fields) is the minimum without which the disclosure fulfills
none of points 1/3/4: it is impossible to say whose application it is, where, for what,
how much capacity, and at what stage.

Canonical units: capacity in kW (not MW, publishers use both), dates in ISO
8601 (YYYY-MM-DD), coordinates in WGS84 as (lat, lon).
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

__all__ = [
    "Field",
    "SCHEMA",
    "FIELDS",
    "CORE_FIELDS",
    "OPTIONAL_FIELDS",
    "GROUPS",
    "canonical_power_kw",
    "canonical_date",
    "validate_instance",
    "validate_frame",
    "empty_frame",
    "LEGACY_COLUMNS",
    "LEGACY_CODES",
    "LEGACY_REASONS",
    "from_legacy_names",
]

# --------------------------------------------------------------------------
# normalization of canonical units
# --------------------------------------------------------------------------

_NUM_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def canonical_power_kw(value: Any, unit: str = "kW") -> Optional[float]:
    """Convert power to kW.  Returns None for empty/unparsable values.

    Accepts the Polish decimal separator (comma) and thousands spaces
    (also NBSP and narrow space, which PDF generators use).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        num = float(value)
    else:
        s = str(value).strip()
        s = s.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
        if s in {"", "-", "--", "---", "brak", "nie dotyczy", "n/d", "N/D"}:
            return None
        s = s.replace(",", ".")
        # allow for multiple thousands dots like 1.234.5 -> reject
        if not _NUM_RE.match(s.replace(".", "", max(0, s.count(".") - 1))):
            try:
                num = float(s)
            except ValueError:
                return None
        else:
            try:
                num = float(s)
            except ValueError:
                return None
    u = unit.strip().lower()
    if u in {"kw", "kilowat", "kilowatt"}:
        return num
    if u in {"mw", "megawat", "megawatt"}:
        return num * 1000.0
    if u in {"w", "wat", "watt"}:
        return num / 1000.0
    raise ValueError(f"unknown power unit: {unit!r}")


# Publishers do not stick to their own [dd.mm.rrrr] pattern: in Stoena's register of
# applications there are dates with a single-digit day ("2.04.2026"), so the pattern
# must accept them, otherwise a correctly extracted date is lost at normalization.
_DATE_PATTERNS = (
    ("%d.%m.%Y", re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")),
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")),
    ("%d/%m/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
    ("%d-%m-%Y", re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$")),
)

_NULLISH = {
    "", "-", "--", "---", "----", "-----", "brak", "nie dotyczy", "nie wymagano",
    "n/d", "none", "nan", "--------", "---------", "----------",
    "-----------", "------------", "-------------", "--------------",
    "---------------",
}


def canonical_date(value: Any) -> Optional[str]:
    """Convert a date to ISO 8601 (YYYY-MM-DD).  None for empty/unparsable values."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    s = str(value).strip()
    if s.lower() in _NULLISH or set(s) == {"-"}:
        return None
    s = s.replace("r.", "").strip()
    for fmt, rx in _DATE_PATTERNS:
        if rx.match(s):
            try:
                return _dt.datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                return None
    return None


def _is_null(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip().lower() in _NULLISH:
        return True
    return False


# --------------------------------------------------------------------------
# field specification
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Field:
    name: str
    dtype: str                 # "string" | "number" | "date" | "boolean" | "geopoint"
    group: str                 # "tozsamosc" | "moc" | "proces"
    core: bool
    unit: Optional[str]
    basis: str              # which point of Article 7(8l) justifies the field
    description: str
    check: Optional[Callable[[Any], bool]] = field(default=None, repr=False)


def _num_nonneg(v: Any) -> bool:
    try:
        return float(v) >= 0.0
    except (TypeError, ValueError):
        return False


def _is_iso_date(v: Any) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(v))) and canonical_date(v) is not None


def _is_geopoint(v: Any) -> bool:
    if isinstance(v, (tuple, list)) and len(v) == 2:
        lat, lon = v
    elif isinstance(v, str) and "," in v:
        try:
            lat, lon = (float(x) for x in v.split(",", 1))
        except ValueError:
            return False
    else:
        return False
    try:
        return -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0
    except (TypeError, ValueError):
        return False


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool) or str(v).strip().lower() in {
        "true", "false", "tak", "nie", "0", "1"
    }


SCHEMA: tuple[Field, ...] = (
    # ---------------- IDENTITY ----------------
    Field("application_id", "string", "identity", True, None, "Art. 7(8l), item 1/3/4",
          "Identifier of the entry in the publisher's register; unique within the "
          "publication, not globally."),
    Field("node_id", "string", "identity", False, None, "Art. 7(8l), item 2",
          "Identifier of the electricity substation or its group, by "
          "which the statute requires the available capacity to be reported."),
    Field("node_name", "string", "identity", False, None, "Art. 7(8l), item 2",
          "Proper name of the station/supply point, if the publisher discloses it."),
    Field("location_text", "string", "identity", True, None, "Art. 7(8l), item 1/3/4",
          "Location of the connection point exactly as given by the publisher "
          "(address, locality, station code), without interpretation."),
    Field("coordinates", "geopoint", "identity", False, "WGS84", "Art. 7(8l), item 1/2",
          "Geographic coordinates (lat, lon); result of location resolution or "
          "source data.", _is_geopoint),
    Field("voltage_level", "string", "identity", False, None, "Art. 7(8l), item 1 (>1 kV)",
          "Voltage level of the connection; the duty applies to networks above 1 kV, so "
          "the field determines the scope of the disclosure."),
    Field("resource_class", "string", "identity", True, None, "Art. 7(8l), item 1/3/4",
          "Type of installation, equipment or network, harmonized to the controlled "
          "vocabulary (PV, FW, BESS, ODB, ...)."),
    # ---------------- CAPACITY ----------------
    Field("capacity_injected", "number", "capacity", False, "kW", "Art. 7(8l), item 1/3",
          "Connection capacity fed into the network (generation/export).", _num_nonneg),
    Field("capacity_withdrawn", "number", "capacity", False, "kW", "Art. 7(8l), item 1/3/4",
          "Connection capacity drawn from the network (consumption/import); for "
          "consumption applications this is the main quantity of the application.  It is "
          "not unconditionally a core field: the core requires AT LEAST ONE "
          "of the pair (capacity_withdrawn, capacity_injected), see CORE_ALTERNATIVES.", _num_nonneg),
    Field("capacity_available", "number", "capacity", False, "kW", "Art. 7(8l), item 2",
          "Total available connection capacity at the node.", _num_nonneg),
    Field("capacity_reserved", "number", "capacity", False, "kW", "Art. 7(8l), item 2",
          "Capacity taken up by issued and valid connection conditions / reservation.", _num_nonneg),
    Field("constraint_flag", "boolean", "capacity", False, None, "Art. 7(8l), item 2",
          "Whether there is a factor at the node limiting the connection.", _is_bool),
    Field("queue_position", "number", "capacity", False, None, "Art. 7(8l), item 1",
          "Position of the application in the connection queue, if the publisher maintains one."),
    # ---------------- PROCESS ----------------
    Field("process_status", "string", "process", True, None, "Art. 7(8l), item 1/3/4",
          "Stage of the proceedings, harmonized to the controlled vocabulary."),
    Field("date_application", "date", "process", False, "ISO-8601", "Art. 7(8l), item 3",
          "Date the application for determination of connection conditions was filed.", _is_iso_date),
    Field("date_conditions", "date", "process", False, "ISO-8601", "Art. 7(8l), item 1/3",
          "Date the connection conditions were determined; the start of the two-year "
          "validity period (Article 7(8i)).", _is_iso_date),
    Field("date_refusal", "date", "process", False, "ISO-8601", "Art. 7(8l), item 4",
          "Date the refusal to determine connection conditions was issued.", _is_iso_date),
    Field("refusal_reason", "string", "process", False, None, "Art. 7(8l), item 4",
          "Justification for the refusal (technical / economic / other reasons)."),
    Field("date_agreement", "date", "process", False, "ISO-8601", "Art. 7(8l), item 1",
          "Date the connection agreement was concluded.", _is_iso_date),
    Field("date_energisation", "date", "process", False, "ISO-8601", "Art. 7(8l), item 1",
          "Date electricity supply began.", _is_iso_date),
    Field("date_published", "date", "process", False, "ISO-8601", "Art. 7(8m)",
          "Status as of the date for which the publisher prepared the disclosure; "
          "the statute requires updates at least once per quarter.", _is_iso_date),
)

SCHEMA_VERSION: str = "1.0"

FIELDS: tuple[str, ...] = tuple(f.name for f in SCHEMA)
CORE_FIELDS: tuple[str, ...] = tuple(f.name for f in SCHEMA if f.core)
OPTIONAL_FIELDS: tuple[str, ...] = tuple(f.name for f in SCHEMA if not f.core)

# Conditional core, separate for each entity of the duty.
#
# The schema has two entities, because the provision has two points with a different
# subject, and the core of one of them is not a requirement for the other.  Assessing a
# NODE entity row against the requirements of the APPLICATION entity would measure entity
# mismatch, not disclosure gaps.
#
# In both entities, part of the requirements is an ALTERNATIVE, not a specific field.  A
# connection application always declares a capacity, but not always the same one: a
# generation application declares export capacity, a consumption application import
# capacity, a bidirectional one (e.g. storage) both.  Similarly, point 2 is sometimes
# implemented via the available capacity or via the number of free connection slots
# (in that case via the constraint flag); we have encountered both forms from different
# publishers.
ENTITY_COLUMN: str = "_entity"
DEFAULT_ENTITY: str = "APPLICATION"

CORE_BY_ENTITY: dict[str, dict[str, tuple]] = {
    "APPLICATION": {
        "required": CORE_FIELDS,
        "alternatives": (("capacity_withdrawn", "capacity_injected"),),
    },
    "NODE": {
        "required": ("node_id",),
        "alternatives": (("capacity_available", "constraint_flag"),),
    },
}

# kept for backward compatibility with 0.3.x; refers to the APPLICATION entity
CORE_ALTERNATIVES: tuple[tuple[str, ...], ...] = tuple(
    CORE_BY_ENTITY["APPLICATION"]["alternatives"])


def _mask_for_entity(df, sub_idx, spec):
    import pandas as _pd

    m = _pd.Series(True, index=sub_idx)
    for c in spec["required"]:
        if c not in df.columns:
            return _pd.Series(False, index=sub_idx)
        m &= df.loc[sub_idx, c].map(lambda v: not _is_null(v))
    for group in spec["alternatives"]:
        current = [c for c in group if c in df.columns]
        if not current:
            return _pd.Series(False, index=sub_idx)
        alt = _pd.Series(False, index=sub_idx)
        for c in current:
            alt |= df.loc[sub_idx, c].map(lambda v: not _is_null(v))
        m &= alt
    return m


def core_complete_mask(df):
    """Mask of rows with a complete core FOR THEIR OWN ENTITY.

    The entity is read from the annotation column ``_entity``; rows without this
    annotation are treated as ``APPLICATION`` (this is how rows are emitted by adapters that
    do not distinguish entities, because their publisher fulfills only points 1/3/4).  A
    missing required column is treated like an empty column: the core is a requirement on
    the ROW, not on the shape of the frame.
    """
    import pandas as _pd

    if ENTITY_COLUMN in df.columns:
        enc = df[ENTITY_COLUMN].map(
            lambda v: DEFAULT_ENTITY if _is_null(v) else str(v).upper())
    else:
        enc = _pd.Series(DEFAULT_ENTITY, index=df.index)

    mask = _pd.Series(False, index=df.index)
    for name, spec in CORE_BY_ENTITY.items():
        sub = enc.index[enc == name]
        if len(sub):
            mask.loc[sub] = _mask_for_entity(df, sub, spec).values
    return mask
BY_NAME: dict[str, Field] = {f.name: f for f in SCHEMA}
GROUPS: dict[str, tuple[str, ...]] = {
    g: tuple(f.name for f in SCHEMA if f.group == g)
    for g in ("identity", "capacity", "process")
}

# accompanying columns, not part of the schema (panel metadata / annotations)
META_COLUMNS: tuple[str, ...] = ("publisher", "jurisdiction", "source_document")
ANNOTATION_PREFIX = "_"

# controlled vocabularies
RESOURCE_CLASSES = (
    "PV", "WIND", "HYDRO", "BIOGAS", "GAS", "COAL", "BESS", "LOAD", "MIX", "GRID",
    "OTHER", "UNSPECIFIED",
)
STATUSES = (
    "APPLICATION_FILED", "APPLICATION_INCOMPLETE", "UNDER_REVIEW",
    "CONDITIONS_ISSUED", "CONDITIONS_EXPIRED", "REFUSED", "AGREEMENT_IN_FORCE",
    "AGREEMENT_TERMINATED", "CONNECTED", "APPLICATION_WITHDRAWN", "UNSPECIFIED",
)


# --------------------------------------------------------------------------
# instance validator
# --------------------------------------------------------------------------


def validate_instance(row: dict[str, Any], *, strict_vocab: bool = False) -> list[str]:
    """Return a list of violation messages for a single row.

    Empty list = row conforms to the schema.  The validator does NOT raise an exception:
    disclosures are sometimes incomplete through the publisher's fault, and that is a
    measurement result, not a runtime error.
    """
    problems: list[str] = []
    unknown = set(row) - set(FIELDS) - set(META_COLUMNS)
    unknown = {k for k in unknown if not k.startswith(ANNOTATION_PREFIX)}
    if unknown:
        problems.append(f"fields outside the schema: {sorted(unknown)}")
    for name in CORE_FIELDS:
        if name not in row or _is_null(row.get(name)):
            problems.append(f"missing core field: {name}")
    for name, value in row.items():
        f = BY_NAME.get(name)
        if f is None or _is_null(value):
            continue
        if f.dtype == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                problems.append(f"{name}: expected a number, got {type(value).__name__}")
                continue
        if f.check is not None and not f.check(value):
            problems.append(f"{name}: value does not pass the type check ({value!r})")
    if strict_vocab:
        kz = row.get("resource_class")
        if not _is_null(kz) and kz not in RESOURCE_CLASSES:
            problems.append(f"resource_class outside the vocabulary: {kz!r}")
        st = row.get("process_status")
        if not _is_null(st) and st not in STATUSES:
            problems.append(f"process_status outside the vocabulary: {st!r}")
    return problems


def validate_frame(df, *, strict_vocab: bool = True) -> dict[str, Any]:
    """Validation of the entire frame.  Returns a report (figures), not an exception."""
    import pandas as pd  # local import: schema.py is meant to be usable without pandas

    report: dict[str, Any] = {
        "n_rows": int(len(df)),
        "columns_outside_schema": sorted(
            set(df.columns) - set(FIELDS) - set(META_COLUMNS)
            - {c for c in df.columns if c.startswith(ANNOTATION_PREFIX)}
        ),
        "missing_core_columns": [c for c in CORE_FIELDS if c not in df.columns],
        "completion": {},
        "violation_type": {},
        "rows_with_complete_core": 0,
        "dictionary": {},
    }
    for c in FIELDS:
        if c in df.columns:
            s = df[c]
            nn = int(s.notna().sum() - sum(
                1 for v in s.dropna() if isinstance(v, str) and v.strip().lower() in _NULLISH
            ))
            report["completion"][c] = round(nn / len(df), 6) if len(df) else 0.0
        else:
            report["completion"][c] = 0.0
    for c in FIELDS:
        if c not in df.columns:
            continue
        f = BY_NAME[c]
        bad = 0
        for v in df[c]:
            if _is_null(v):
                continue
            if f.dtype == "number" and (not isinstance(v, (int, float)) or isinstance(v, bool)):
                bad += 1
            elif f.check is not None and not f.check(v):
                bad += 1
        if bad:
            report["violation_type"][c] = bad
    report["rows_with_complete_core"] = int(core_complete_mask(df).sum())
    report["schema_version"] = SCHEMA_VERSION
    if strict_vocab:
        for c, vocab in (("resource_class", RESOURCE_CLASSES), ("process_status", STATUSES)):
            if c in df.columns:
                bad = sorted({v for v in df[c].dropna().unique() if v not in vocab and not _is_null(v)})
                report["dictionary"][c] = bad
    return report


def empty_frame():
    """Empty frame in the schema (all 21 fields + metadata columns)."""
    import pandas as pd

    return pd.DataFrame({c: pd.Series(dtype="object") for c in FIELDS + META_COLUMNS})


def _entity_fields(name: str) -> str:
    """Entity in which the field occurs: APPLICATION, NODE, or obie.

    Derived from CORE_BY_ENTITY and from the field's membership in a point of the duty:
    point 2 describes the node, points 1, 3 and 4 describe the application.
    """
    nodal = {"node_id", "node_name", "capacity_available", "capacity_reserved",
               "constraint_flag"}
    both = {"coordinates", "date_published"}
    if name in both:
        return "both"
    return "NODE" if name in nodal else "APPLICATION"


def _core_status(name: str) -> str:
    """Three-valued status: unconditional core, core alternative, extension.

    The core is CONDITIONAL: a field unconditional for one entity need not be required
    for the other, and alternative pairs require at least one member to be filled in.
    The two-valued column `core` does not capture this, and that is why this second
    one exists.
    """
    for entity, spec in CORE_BY_ENTITY.items():
        if name in spec["required"]:
            return f"unconditional core ({entity})"
    for entity, spec in CORE_BY_ENTITY.items():
        for pair in spec["alternatives"]:
            if name in pair:
                return f"core alternative ({entity}: {' or '.join(pair)})"
    return "extension"


def schema_table():
    """Specification as a frame, an artifact for the manuscript."""
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "field": f.name,
                "kind": f.dtype,
                "group": f.group,
                "entity": _entity_fields(f.name),
                "core": f.core,
                "core_status": _core_status(f.name),
                "canonical_unit": f.unit or "",
                "legal_basis": f.basis,
                "description": f.description,
            }
            for f in SCHEMA
        ]
    )


# --------------------------------------------------------------------------
# names in the wording of the statute
# --------------------------------------------------------------------------

#: Column names in the Polish wording of the statute, as used by the first drafts of the
#: schema and by panels exported before the schema was written in English. Tables that use
#: them are read through :func:`from_legacy_names`; the Supplement gives the same table.
LEGACY_COLUMNS: dict[str, str] = {
    '_adres': '_address',
    '_danm': '_danm',
    '_data_rozwiazania': '_date_termination',
    '_data_rozwiazania_umowy': '_date_agreement_termination',
    '_data_utraty_waznosci': '_date_expiry',
    '_data_wygasniecia': '_date_lapse',
    '_data_wygasniecia_umowy': '_date_agreement_lapse',
    '_data_zaliczki': '_date_advance_payment',
    '_dystrykt': '_district',
    '_encja': '_entity',
    '_energizacja_tekst': '_energisation_text',
    '_geo_dokladnosc': '_geo_accuracy',
    '_geo_pewnosc': '_geo_confidence',
    '_geo_powod': '_geo_reason',
    '_gmina': '_municipality',
    '_gsp': '_gsp',
    '_jednostka_mocy_odbiorczej': '_demand_capacity_unit',
    '_jednostka_mocy_zrodlowa': '_source_capacity_unit',
    '_kierunek': '_direction',
    '_klasa_napiecia': '_voltage_class',
    '_komentarz': '_comment',
    '_konfiguracja_transformatorow': '_transformer_configuration',
    '_licence_area': '_licence_area',
    '_liczba_dostepnych_miejsc': '_free_slots',
    '_lp_dokumentu': '_document_item_no',
    '_machine_export_kw': '_machine_export_kw',
    '_machine_id': '_machine_id',
    '_machine_import_kw': '_machine_import_kw',
    '_miejscowosc': '_locality',
    '_moc_dostepna_2026': '_capacity_available_2026',
    '_moc_dostepna_2027': '_capacity_available_2027',
    '_moc_dostepna_2028': '_capacity_available_2028',
    '_moc_dostepna_2029': '_capacity_available_2029',
    '_moc_dostepna_2030': '_capacity_available_2030',
    '_moc_dostepna_2031': '_capacity_available_2031',
    '_moc_dostepna_2035': '_capacity_available_2035',
    '_moc_dostepna_analityczna': '_capacity_available_analytical',
    '_moc_dostepna_mva': '_capacity_available_mva',
    '_moc_pobierana_skladowe_mw': '_capacity_withdrawn_components_mw',
    '_moc_przyjeta_nierozstrzygnieta_kw': '_capacity_accepted_pending_kw',
    '_moc_przylaczona_mva': '_capacity_connected_mva',
    '_moc_w_potwierdzaniu_mva': '_capacity_being_confirmed_mva',
    '_moc_wprowadzana_skladowe_mw': '_capacity_injected_components_mw',
    '_moc_zainstalowana_kw': '_capacity_installed_kw',
    '_moc_zainstalowana_mva': '_capacity_installed_mva',
    '_moc_zajeta_w_toku_kw': '_capacity_occupied_in_progress_kw',
    '_moc_zajeta_z_pozwoleniem_kw': '_capacity_occupied_with_permit_kw',
    '_moc_zakontraktowana_mva': '_capacity_contracted_mva',
    '_mz_fw': '_ic_wind',
    '_mz_inne': '_ic_other',
    '_mz_mee_ladowania': '_ic_storage_charging',
    '_mz_mee_rozladowania': '_ic_storage_discharging',
    '_mz_odb': '_ic_load',
    '_mz_pv': '_ic_pv',
    '_nazwa_obiektu': '_facility_name',
    '_nr_grupy': '_group_no',
    '_nuts3': '_nuts3',
    '_odbior_bez_ograniczenia_kva': '_demand_unconstrained_kva',
    '_odbior_dostepna_mva': '_demand_available_mva',
    '_odbior_nadrzedna_mva': '_demand_upstream_mva',
    '_odbior_ograniczenie': '_demand_constraint',
    '_odbior_ograniczenie_opis': '_demand_constraint_description',
    '_odbior_trwala_mva': '_demand_firm_mva',
    '_oddzial': '_branch',
    '_osd_osp': '_dso_tso',
    '_plik_zrodlowy': '_source_file',
    '_podmiot': '_applicant',
    '_prowincja': '_province',
    '_przypisy': '_footnotes',
    '_rodzaj_instalacji_raw': '_installation_kind_raw',
    '_rodzaj_podmiotu': '_applicant_kind',
    '_rodzaj_raw': '_kind_raw',
    '_rozbicie_pozycyjne_kw': '_breakdown_by_item_kw',
    '_rozbicie_technologiczne_kw': '_breakdown_by_technology_kw',
    '_rozdzielnia': '_switchgear',
    '_sekcja': '_section',
    '_stacja_nadrzedna': '_upstream_station',
    '_stacje_grupy': '_group_stations',
    '_status_raw': '_status_raw',
    '_styk_przesylowy': '_transmission_interface',
    '_symbol_stacji': '_station_symbol',
    '_tanm': '_tanm',
    '_typ_instalacji': '_installation_type',
    '_uwaga_zrodlowa': '_source_note',
    '_uwagi': '_remarks',
    '_wezel_przesylowy': '_transmission_node',
    '_wezel_rnt': '_rnt_node',
    '_wiele_miejsc': '_multiple_points',
    '_wspolnota_autonomiczna': '_autonomous_community',
    '_wytw_bez_ograniczenia_kva': '_generation_unconstrained_kva',
    '_wytw_dostepna_nietrwala_kw': '_generation_available_non_firm_kw',
    '_wytw_ograniczenie': '_generation_constraint',
    '_wytw_ograniczenie_opis': '_generation_constraint_description',
    '_wytw_trwala_kw': '_generation_firm_kw',
    '_wytw_zakontraktowana_kw': '_generation_contracted_kw',
    '_zasilanie': '_supply',
    '_zestawienie': '_listing',
    '_zko_pse': '_pse_coordination_centre',
    '_zmiany_w_latach': '_changes_by_year',
    'data_energizacji': 'date_energisation',
    'data_odmowy': 'date_refusal',
    'data_publikacji': 'date_published',
    'data_umowy': 'date_agreement',
    'data_warunkow': 'date_conditions',
    'data_wniosku': 'date_application',
    'dokument_zrodlowy': 'source_document',
    'id_wezla': 'node_id',
    'id_wniosku': 'application_id',
    'jurysdykcja': 'jurisdiction',
    'klasa_zasobu': 'resource_class',
    'lokalizacja_tekst': 'location_text',
    'moc_dostepna': 'capacity_available',
    'moc_pobierana': 'capacity_withdrawn',
    'moc_wprowadzana': 'capacity_injected',
    'moc_zarezerwowana': 'capacity_reserved',
    'nazwa_wezla': 'node_name',
    'ograniczenie_flaga': 'constraint_flag',
    'powod_odmowy': 'refusal_reason',
    'poziom_napiecia': 'voltage_level',
    'pozycja_w_kolejce': 'queue_position',
    'publikujacy': 'publisher',
    'status_procesu': 'process_status',
    'wspolrzedne': 'coordinates',
}

#: Codes of the controlled vocabularies in the same wording, per (English) column.
LEGACY_CODES: dict[str, dict[str, str]] = {
    '_entity': {
        'WNIOSEK': 'APPLICATION',
        'WEZEL': 'NODE',
    },
    '_direction': {
        'wytworcza': 'generation',
        'odbiorcza': 'demand',
    },
    'process_status': {
        'WNIOSEK_ZLOZONY': 'APPLICATION_FILED',
        'WNIOSEK_NIEKOMPLETNY': 'APPLICATION_INCOMPLETE',
        'W_TRAKCIE_ANALIZY': 'UNDER_REVIEW',
        'WARUNKI_WYDANE': 'CONDITIONS_ISSUED',
        'WARUNKI_WYGASLE': 'CONDITIONS_EXPIRED',
        'ODMOWA': 'REFUSED',
        'UMOWA_OBOWIAZUJACA': 'AGREEMENT_IN_FORCE',
        'UMOWA_ROZWIAZANA': 'AGREEMENT_TERMINATED',
        'PRZYLACZONY': 'CONNECTED',
        'WNIOSEK_WYCOFANY': 'APPLICATION_WITHDRAWN',
        'NIEOKRESLONY': 'UNSPECIFIED',
    },
    'resource_class': {
        'FW': 'WIND',
        'EW': 'HYDRO',
        'BIOGAZ': 'BIOGAS',
        'GAZ': 'GAS',
        'WEGIEL': 'COAL',
        'ODB': 'LOAD',
        'SIEC': 'GRID',
        'INNE': 'OTHER',
        'NIEOKRESLONA': 'UNSPECIFIED',
    },
    '_geo_confidence': {
        'SKRZYZOWANIE': 'INTERSECTION',
        'ZRODLO': 'SOURCE',
    },
    '_geo_accuracy': {
        'PUNKT_ADRESOWY': 'ADDRESS_POINT',
        'PUNKT_SKRZYZOWANIA': 'INTERSECTION_POINT',
        'PUNKT_NA_OSI_ULICY': 'STREET_AXIS_POINT',
        'CENTROID_MIEJSCOWOSCI': 'LOCALITY_CENTROID',
        'BRAK_GEOMETRII': 'NO_GEOMETRY',
        'BRAK': 'NO_POINT',
    },
}

#: Reason codes of the location resolver in the same wording (a prefix of ``_geo_reason``).
LEGACY_REASONS: dict[str, str] = {
    'brak_deklaracji_miejscowosci': 'no_locality_declared',
    'brak_kandydatow': 'no_candidates',
    'brak_punktu': 'no_point',
    'brak_tokenow_wyrozniajacych': 'no_distinguishing_tokens',
    'kod_stacji_bez_slownika': 'station_code_without_dictionary',
    'miejscowosc_niejednoznaczna': 'ambiguous_locality',
    'miejscowosc_poza_gazeterem': 'locality_not_in_gazetteer',
    'nazwa_rozwiazana_bez_geometrii': 'name_resolved_without_geometry',
    'opis_slowny_nie_nazwa_ulicy': 'verbal_description_not_street_name',
    'pusty_opis': 'empty_description',
    'wiele_kandydatow': 'multiple_candidates',
    'numer_domu': 'house_number',
}


def from_legacy_names(df: "pd.DataFrame") -> "pd.DataFrame":
    """Return ``df`` with column names and codes in the English schema.

    Columns named in the wording of the statute (``id_wniosku``, ``moc_wprowadzana``, ...)
    are renamed, and the codes of the controlled vocabularies (``WNIOSEK``,
    ``WARUNKI_WYDANE``, ``FW``, ...) are translated. A frame already in English is returned
    unchanged, so the function can be applied to any table read from disk.
    """
    import re as _re

    import pandas as pd

    out = df.rename(columns={k: v for k, v in LEGACY_COLUMNS.items() if k in df.columns})
    for col, codes in LEGACY_CODES.items():
        if col in out.columns and not pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].map(lambda v: codes.get(v, v) if isinstance(v, str) else v)
    if "_geo_reason" in out.columns:
        rx = _re.compile(r"\b(" + "|".join(map(_re.escape, LEGACY_REASONS)) + r")\b")
        out["_geo_reason"] = out["_geo_reason"].map(
            lambda v: rx.sub(lambda m: LEGACY_REASONS[m.group(1)], v) if isinstance(v, str) else v)
    return out
