"""gridqueue -- harmonizator ustawowych ujawnień przyłączeniowych do sieci
elektroenergetycznej.

Narzędzie sprowadza publikacje operatorów systemów dystrybucyjnych, wymagane
art. 7 ust. 8l ustawy -- Prawo energetyczne, do jednego przetwarzalnego schematu.
Wartość narzędzia jest sprawdzalna przez inspekcję: albo dokument staje się
zbiorem wierszy o zmierzonej dokładności, albo nie.
"""

from .schema import (  # noqa: F401
    SCHEMA, SCHEMA_VERSION, FIELDS, CORE_FIELDS, OPTIONAL_FIELDS, GROUPS,
    CORE_ALTERNATIVES, CORE_BY_ENTITY, ENTITY_COLUMN, DEFAULT_ENTITY,
    META_COLUMNS, ANNOTATION_PREFIX, core_complete_mask,
    canonical_date, canonical_power_kw, validate_instance, validate_frame,
    empty_frame, schema_table,
)
from .layout import (  # noqa: F401
    ColumnGeometry, detect_ruled_columns, detect_banded_columns,
    extract_ruled_page, assign_words_to_columns, merge_continuation_rows,
    audit_column_shift, ShiftAudit,
)
from .geoloc import LocationResolver, Resolution, resolver_from_osm_json  # noqa: F401
from .analysis import (  # noqa: F401
    PRZEDROSTKI_STACJI, KMResult, assign_to_nodes, kaplan_meier, node_loading,
    normalizuj_nazwe, processing_time, station_node_map,
)
from .quality import RULES, run_quality, QualityReport  # noqa: F401
from .longitudinal import (  # noqa: F401
    RECALL_FIELDS, LinkageRecall, linkage_recall,
    DEFAULT_KEY_FIELDS, STATUS_ORDER, TERMINAL_NEGATIVE,
    surrogate_key, EditionDelta, compare_editions,
    HELD_OUT_FIELDS, LinkageAudit, linkage_audit,
)
from .registry import REGISTRY, get_adapter, detect_publisher, declarations  # noqa: F401

__version__ = "1.3.0"
__all__ = [
    "RECALL_FIELDS", "LinkageRecall", "linkage_recall",
    "PRZEDROSTKI_STACJI", "KMResult", "assign_to_nodes", "kaplan_meier",
    "node_loading", "normalizuj_nazwe", "processing_time", "station_node_map",
    "SCHEMA", "SCHEMA_VERSION", "FIELDS", "CORE_FIELDS", "OPTIONAL_FIELDS", "GROUPS",
    "CORE_ALTERNATIVES", "CORE_BY_ENTITY", "ENTITY_COLUMN", "DEFAULT_ENTITY",
    "META_COLUMNS", "ANNOTATION_PREFIX", "core_complete_mask",
    "canonical_date", "canonical_power_kw", "validate_instance", "validate_frame",
    "empty_frame", "schema_table", "ColumnGeometry", "detect_ruled_columns",
    "detect_banded_columns", "extract_ruled_page", "assign_words_to_columns",
    "merge_continuation_rows", "audit_column_shift", "ShiftAudit",
    "LocationResolver", "Resolution", "resolver_from_osm_json",
    "RULES", "run_quality", "QualityReport",
    "DEFAULT_KEY_FIELDS", "STATUS_ORDER", "TERMINAL_NEGATIVE",
    "surrogate_key", "EditionDelta", "compare_editions",
    "HELD_OUT_FIELDS", "LinkageAudit", "linkage_audit",
    "REGISTRY", "get_adapter", "detect_publisher", "declarations", "__version__",
]
