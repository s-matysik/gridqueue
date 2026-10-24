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

__all__ = ["REGISTRY", "get_adapter", "detect_publisher", "declarations", "parse_sources"]

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



def parse_sources(sources, adapter: Optional[str] = None):
    """Parse any number of documents, of one or several publishers, into one panel.

    Each file is assigned to a publisher by :func:`detect_publisher` (or to ``adapter`` when
    given) and parsed **on its own, by a fresh adapter instance**, so that every document keeps
    the as-at date it states. This matters twice: a publisher that splits one edition into
    several documents (ENERGA-OPERATOR's applications as at 30 June and node capacities as at
    31 August 2026) keeps both dates, and two editions of one register dropped together are
    never stamped with a single date. The node and application rows of one publisher still end
    up in one panel, which is all that :func:`~gridqueue.analysis.station_node_map` needs.

    Returns ``(frame, reports)``: the concatenated frame in the schema and one
    ``{"adapter", "files", "rows", "date_published", "report"}`` entry per file. A file no
    adapter recognises raises ``ValueError`` naming it, rather than being skipped silently.
    """
    import pandas as pd

    paths = [sources] if isinstance(sources, (str, Path)) else list(sources)
    keys = []
    for p in paths:
        key = adapter or detect_publisher(p)
        if key is None:
            raise ValueError(f"no adapter recognised {Path(str(p)).name!r}; keep the file "
                             f"name the publisher gave it, or choose the adapter explicitly")
        keys.append(key)
    frames, reports = [], []
    for key, p in zip(keys, paths):
        res = get_adapter(key).parse(p)
        frames.append(res.frame)
        dates = res.frame["date_published"].dropna().astype(str).unique().tolist() \
            if "date_published" in res.frame else []
        reports.append({"adapter": key, "files": [Path(str(p)).name], "rows": int(len(res.frame)),
                        "date_published": dates[0] if len(dates) == 1 else dates,
                        "report": dict(res.report)})
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return frame, reports


def split_editions(df):
    """Split a panel into editions of one register by the as-at date of its application rows.

    Returns ``[(date, frame), ...]`` ordered by date when the panel holds exactly one
    publisher whose application rows carry two or more publication dates; otherwise a
    single ``(None, df)``. Node rows (``_entity == "NODE"``) go to the edition whose
    application date is nearest to their own, later on a tie, because a publisher may date its
    node and application documents of one edition differently.
    """
    import pandas as pd

    if "date_published" not in df or df.empty:
        return [(None, df)]
    is_node = df["_entity"].astype("string").fillna("APPLICATION").str.upper().eq("NODE") \
        if "_entity" in df else pd.Series(False, index=df.index)
    pubs = df["publisher"].dropna().unique() if "publisher" in df else []
    dates = sorted(df.loc[~is_node, "date_published"].dropna().astype(str).unique())
    if len(pubs) != 1 or len(dates) < 2:
        return [(None, df)]
    d = pd.to_datetime(pd.Series(dates))
    own = df["date_published"].astype(str)

    def edition_of(v):
        if v in dates:
            return v
        t = pd.to_datetime(v, errors="coerce")
        if pd.isna(t):
            return dates[-1]
        gap = (d - t).abs()
        return dates[max(i for i in range(len(dates)) if gap[i] == gap.min())]

    lab = own.map(edition_of)
    return [(x, df[lab == x].reset_index(drop=True)) for x in dates]
