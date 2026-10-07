"""Rejestr adapterów i wykrywanie publikującego."""

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
from .adapters.pt_eredes import EredesAdapter
from .adapters.uk_nationalgrid import NationalGridAdapter

__all__ = ["REGISTRY", "get_adapter", "detect_publisher", "declarations"]

REGISTRY: dict[str, Type[Adapter]] = {
    "pl_tauron": TauronAdapter,
    "pl_energa": EnergaAdapter,
    "pl_pse": PSEAdapter,
    "pl_stoen": StoenAdapter,
    "pl_boryszew": BoryszewAdapter,
    "pt_eredes": EredesAdapter,
    "uk_nationalgrid": NationalGridAdapter,
}


def get_adapter(key: str, **kwargs) -> Adapter:
    if key not in REGISTRY:
        raise KeyError(f"nieznany adapter {key!r}; dostępne: {sorted(REGISTRY)}")
    return REGISTRY[key](**kwargs)


def detect_publisher(source, *, sniff_bytes: int = 4000) -> Optional[str]:
    """Rozpoznaj publikującego po nazwie pliku, a jeśli trzeba -- po treści.

    Kolejność jest celowa: nazwa pliku jest tania i zwykle wystarcza, treść
    pierwszej strony rozstrzyga resztę.  Zwraca klucz rejestru albo None.
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
    """Deklaracje pól opcjonalnych wszystkich zarejestrowanych publikujących."""
    return [cls().declaration() for cls in REGISTRY.values()]
