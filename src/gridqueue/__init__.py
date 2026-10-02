"""gridqueue -- harmonizator ustawowych ujawnień przyłączeniowych do sieci
elektroenergetycznej.

Narzędzie sprowadza publikacje operatorów systemów dystrybucyjnych, wymagane
art. 7 ust. 8l ustawy -- Prawo energetyczne, do jednego przetwarzalnego schematu.
Wartość narzędzia jest sprawdzalna przez inspekcję: albo dokument staje się
zbiorem wierszy o zmierzonej dokładności, albo nie.
"""

from .schema import (  # noqa: F401
    SCHEMA, FIELDS, CORE_FIELDS, OPTIONAL_FIELDS, GROUPS,
    canonical_date, canonical_power_kw, validate_instance, validate_frame,
    empty_frame, schema_table,
)
from .layout import (  # noqa: F401
    ColumnGeometry, detect_ruled_columns, detect_banded_columns,
    extract_ruled_page, assign_words_to_columns, merge_continuation_rows,
    audit_column_shift, ShiftAudit,
)
from .geoloc import LocationResolver, Resolution, resolver_from_osm_json  # noqa: F401
from .quality import RULES, run_quality, QualityReport  # noqa: F401
from .registry import REGISTRY, get_adapter, detect_publisher, declarations  # noqa: F401

__version__ = "0.3.1"
__all__ = [
    "SCHEMA", "FIELDS", "CORE_FIELDS", "OPTIONAL_FIELDS", "GROUPS",
    "canonical_date", "canonical_power_kw", "validate_instance", "validate_frame",
    "empty_frame", "schema_table", "ColumnGeometry", "detect_ruled_columns",
    "detect_banded_columns", "extract_ruled_page", "assign_words_to_columns",
    "merge_continuation_rows", "audit_column_shift", "ShiftAudit",
    "LocationResolver", "Resolution", "resolver_from_osm_json",
    "RULES", "run_quality", "QualityReport",
    "REGISTRY", "get_adapter", "detect_publisher", "declarations", "__version__",
]
