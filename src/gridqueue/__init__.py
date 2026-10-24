"""gridqueue -- harmonizer of statutory grid connection disclosures for the
electrical power network.

The tool brings publications of distribution system operators, required under
Article 7(8l) of the Energy Law Act, to a single processable schema.
The value of the tool is verifiable by inspection: either the document becomes
a set of rows of measured accuracy, or it does not.
"""

from .schema import (  # noqa: F401
    SCHEMA, SCHEMA_VERSION, FIELDS, CORE_FIELDS, OPTIONAL_FIELDS, GROUPS,
    CORE_ALTERNATIVES, CORE_BY_ENTITY, ENTITY_COLUMN, DEFAULT_ENTITY,
    META_COLUMNS, ANNOTATION_PREFIX, core_complete_mask,
    canonical_date, canonical_power_kw, validate_instance, validate_frame,
    empty_frame, schema_table, LEGACY_COLUMNS, LEGACY_CODES, LEGACY_REASONS, from_legacy_names,
)
from .layout import (  # noqa: F401
    ColumnGeometry, detect_ruled_columns, detect_banded_columns,
    extract_ruled_page, assign_words_to_columns, merge_continuation_rows,
    audit_column_shift, ShiftAudit,
)
from .geoloc import (LocationResolver, MultiLocalityResolver, Resolution,  # noqa: F401
                     geocode_frame, resolver_from_gazetteer_json, resolver_from_osm_json)
from .analysis import (  # noqa: F401
    STATION_PREFIXES, KMResult, assign_to_nodes, kaplan_meier, kaplan_meier_by_group,
    node_loading,
    normalize_name, processing_time, station_node_map,
)
from .quality import RULES, run_quality, QualityReport  # noqa: F401
from .longitudinal import (  # noqa: F401
    RECALL_FIELDS, NODE_KEY_FIELDS, LinkageRecall, linkage_recall,
    DEFAULT_KEY_FIELDS, STATUS_ORDER, TERMINAL_NEGATIVE,
    surrogate_key, EditionDelta, compare_editions,
    HELD_OUT_FIELDS, LinkageAudit, linkage_audit,
)
from .registry import (REGISTRY, get_adapter, detect_publisher, declarations,  # noqa: F401
                       parse_sources, split_editions)

# Charts live in `gridqueue.plots` and synthetic data in `gridqueue.examples`. Both are imported
# on first access, so that the core of the package does not require matplotlib:
#     from gridqueue import plots
_LAZY_SUBMODULES = ("plots", "examples")


def __getattr__(name):
    if name in _LAZY_SUBMODULES:
        import importlib

        return importlib.import_module(f".{name}", __name__)
    raise AttributeError(f"module 'gridqueue' has no attribute {name!r}")

__version__ = "1.0.0"
__all__ = [
    "NODE_KEY_FIELDS",
    "RECALL_FIELDS", "LinkageRecall", "linkage_recall",
    "STATION_PREFIXES", "KMResult", "assign_to_nodes", "kaplan_meier", "kaplan_meier_by_group",
    "node_loading", "normalize_name", "processing_time", "station_node_map",
    "SCHEMA", "SCHEMA_VERSION", "FIELDS", "CORE_FIELDS", "OPTIONAL_FIELDS", "GROUPS",
    "CORE_ALTERNATIVES", "CORE_BY_ENTITY", "ENTITY_COLUMN", "DEFAULT_ENTITY",
    "META_COLUMNS", "ANNOTATION_PREFIX", "core_complete_mask",
    "canonical_date", "canonical_power_kw", "validate_instance", "validate_frame",
    "empty_frame", "schema_table", "LEGACY_COLUMNS", "LEGACY_CODES", "LEGACY_REASONS",
    "from_legacy_names", "ColumnGeometry", "detect_ruled_columns",
    "detect_banded_columns", "extract_ruled_page", "assign_words_to_columns",
    "merge_continuation_rows", "audit_column_shift", "ShiftAudit",
    "LocationResolver", "Resolution", "resolver_from_osm_json", "resolver_from_gazetteer_json", "geocode_frame",
    "MultiLocalityResolver",
    "RULES", "run_quality", "QualityReport",
    "DEFAULT_KEY_FIELDS", "STATUS_ORDER", "TERMINAL_NEGATIVE",
    "surrogate_key", "EditionDelta", "compare_editions",
    "HELD_OUT_FIELDS", "LinkageAudit", "linkage_audit",
    "REGISTRY", "get_adapter", "detect_publisher", "declarations", "parse_sources", "split_editions", "__version__",
]
