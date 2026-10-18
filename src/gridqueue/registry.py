"""Adapter registry and publisher detection."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Type

from .adapters.base import Adapter
from .adapters.pl_boryszew import BoryszewAdapter
from .adapters.pl_energa import EnergaAdapter
from .adapters.pl_pse import PSEAdapter
from .adapters.pl_stoen import StoenAdapter
from .adapters.pl_tauron import TauronAdapter
from .adapters.es_edistribucion import EDistribucionAdapter
from .adapters.ie_esbnetworks import ESBNetworksAdapter
from .adapters.pt_eredes import EredesAdapter
from .adapters.uk_nationalgrid import NationalGridAdapter

__all__ = ["REGISTRY", "get_adapter", "detect_publisher", "declarations"]

REGISTRY: dict[str, Type[Adapter]] = {
    "pl_tauron": TauronAdapter,
    "pl_energa": EnergaAdapter,
    "pl_pse": PSEAdapter,
    "pl_stoen": StoenAdapter,
    "pl_boryszew": BoryszewAdapter,
    "es_edistribucion": EDistribucionAdapter,
    "ie_esbnetworks": ESBNetworksAdapter,
    "pt_eredes": EredesAdapter,
    "uk_nationalgrid": NationalGridAdapter,
}


def get_adapter(key: str, **kwargs) -> Adapter:
    if key not in REGISTRY:
        raise KeyError(f"unknown adapter {key!r}; available: {sorted(REGISTRY)}")
    return REGISTRY[key](**kwargs)


def detect_publisher(source, *, sniff_bytes: int = 4000) -> Optional[str]:
    """Recognize the publisher by file name, and if needed, by content.

    The order is intentional: the file name is cheap and usually sufficient, the content
    of the first page resolves the rest.  Returns the registry key or None.
    """
    name = str(source).lower()
    for key, cls in REGISTRY.items():
        for pat in cls.detect_patterns:
            if re.search(pat, name):
                return key
    p = Path(str(source))
    if p.suffix.lower() == ".pdf" and p.exists():
        try:
            import pdfplumber

            with pdfplumber.open(p) as pdf:
                text = (pdf.pages[0].extract_text() or "")[:sniff_bytes].lower()
        except Exception:
            return None
        for key, cls in REGISTRY.items():
            for pat in cls.detect_patterns:
                if re.search(pat, text):
                    return key
    return None


def declarations() -> list[dict]:
    """Declarations of optional fields of all registered publishers."""
    return [cls().declaration() for cls in REGISTRY.values()]
