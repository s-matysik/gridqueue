"""Research analyses on the harmonized panel.

Two families of functions, both derived from questions that the register allows to ask
only after harmonization:

* **node loading**, a comparison of the capacity covered by applications against the disclosed
  available capacity at the node. This is a measurable version of the "available connection
  capacity" criterion, which literature reviews describe as unmeasurable
  due to lack of data. It requires a publisher who discloses SIMULTANEOUSLY the capacity
  available at the node and the composition of stations making up the node;
* **processing time with censoring**, applications without a resolution date are
  not missing data, only observations censored at the publication date. Computing the
  median using only complete cases UNDERSTATES it, and does so more strongly, the
  longer the actual processing time is.

Neither of these functions is specific to the publisher: adapters are specific,
and this is a layer on top of the schema.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable, Sequence

import pandas as pd

__all__ = [
    "STATION_PREFIXES",
    "normalize_name",
    "station_node_map",
    "assign_to_nodes",
    "node_loading",
    "processing_time",
    "kaplan_meier",
    "kaplan_meier_by_group",
    "KMResult",
]

#: Prefixes of station designations, removed before comparing names. They do not carry
#: object identity, and occur inconsistently on both sides of the join.
STATION_PREFIXES: tuple[str, ...] = ("GPZ", "SE", "RS", "RPZ", "STACJA")

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")

#: Entries describing an object PLANNED ON A LINE between stations, rather than an object
#: at a node. Assigning them to a node would be arbitrary: the line connects two nodes,
#: and matching by name would pick whichever end happens to appear
#: in the station list. The full capacity of such an application does not load either of them
#: in full, so the entry remains unassigned and is explicitly flagged.
_LINE_RELATION = re.compile(
    r"\b(w\s+lini(?:i|ach)|relacj(?:i|a)|odczep\s+z\s+lini)", re.IGNORECASE)

#: Letters whose canonical decomposition does NOT separate the diacritical mark: Unicode
#: treats them as separate letters, so NFKD does not decompose them, and naive cleaning
#: turns them into a space, splitting the word ("Białogard" -> "bia ogard").
_INDECOMPOSABLE = {"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O",
                   "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"}


def normalize_name(v) -> str:
    """Station name reduced to a comparable form.

    Removes diacritical marks, converts to lowercase, drops designation
    prefixes and extraneous characters. The comparison is performed on TOKENS, not characters,
    so that "Kutno" does not match "Kutnowska".
    """
    if v is None or (isinstance(v, float) and v != v):
        return ""
    s = str(v)
    for mark, replacement in _INDECOMPOSABLE.items():
        s = s.replace(mark, replacement)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = _NON_ALNUM.sub(" ", s)
    tokens = [t for t in s.split() if t and t.upper() not in STATION_PREFIXES]
    return " ".join(tokens)


def _tokens(s: str) -> tuple[str, ...]:
    return tuple(s.split())


def _substring(needle: Sequence[str], haystack: Sequence[str]) -> bool:
    """Whether `needle` is a contiguous subsequence of the tokens of `haystack`."""
    n, m = len(needle), len(haystack)
    if n == 0 or n > m:
        return False
    return any(tuple(haystack[i : i + n]) == tuple(needle) for i in range(m - n + 1))


def station_node_map(
    df: pd.DataFrame,
    entity_column: str = "_entity",
    group_column: str = "_group_no",
    separator: str = ",",
) -> pd.DataFrame:
    """Mapping: station -> station group, read from NODE entity rows.

    A publisher that carries out point 2 of the duty by splitting stations into GROUPS
    lists the composition of the group in the location field. This is the only place where
    a station's membership in a node is disclosed at all, hence this function.

    The key is the GROUP, not the node-row identifier. The publisher
    issues the same group separately for the generation direction and the offtake direction, so
    mapping by row identifier would make every station
    ambiguous, which would be an artifact of the document layout, not a property of the network.
    When the group column is not present, the key becomes the node identifier.

    Returns a frame: publisher, group, node_name, station, station_norm.
    """
    if entity_column in df.columns:
        nodes_df = df[df[entity_column] == "NODE"]
    else:  # without entity annotation, we recognize a node by the presence of available capacity
        nodes_df = df[df["capacity_available"].notna()] if "capacity_available" in df else df.iloc[0:0]
    key = group_column if group_column in df.columns else "node_id"
    rows = []
    for _, r in nodes_df.iterrows():
        item_list = r.get("location_text")
        if item_list is None or (isinstance(item_list, float) and item_list != item_list):
            continue
        for part in str(item_list).split(separator):
            name = part.strip()
            if not name:
                continue
            rows.append(
                {
                    "publisher": r.get("publisher"),
                    "group": r.get(key),
                    "node_name": r.get("node_name"),
                    "station": name,
                    "station_norm": normalize_name(name),
                }
            )
    out = pd.DataFrame(rows)
    if not len(out):
        return out
    out = out[out["station_norm"] != ""]
    return out.drop_duplicates(["group", "station_norm"]).reset_index(drop=True)


def assign_to_nodes(
    df: pd.DataFrame,
    mapping: pd.DataFrame,
    entity_column: str = "_entity",
) -> pd.DataFrame:
    """Assigns application rows to station groups by station name.

    The assignment is BY NAME, not topological: it relies on the match of names
    disclosed by the publisher, rather than on a network model. Its accuracy is not
    validated here against an external reference, because none exists.

    The returned status distinguishes four cases, because no assignment
    and an uncertain assignment are not the same thing:

    ``EXACT``      station name equal to the application's location after normalization
    ``EXTENDED``   location contains the station name as a contiguous subsequence of tokens
    ``LINE``       object planned on a line between stations, not at a node
    ``AMBIGUOUS``  more than one group matches, no assignment is made
    ``NONE``       no match, or no location

    Adds the columns `_group`, `_group_name`, `_group_match`.
    """
    if not len(mapping):
        out = df.copy()
        out["_group"] = None
        out["_group_name"] = None
        out["_group_match"] = "NONE"
        return out
    mask = df[entity_column] != "NODE" if entity_column in df.columns \
        else pd.Series(True, index=df.index)
    listing = (
        mapping.groupby("station_norm")
        .agg(group=("group", lambda s: tuple(dict.fromkeys(s))),
             name=("node_name", lambda s: tuple(dict.fromkeys(s))))
        .reset_index()
    )
    pairs = [(s, _tokens(s), g, n) for s, g, n in
            zip(listing["station_norm"], listing["group"], listing["name"])]
    col = {"_group": [], "_group_name": [], "_group_match": []}
    for idx, loc in df["location_text"].items():
        if not mask.loc[idx]:
            col["_group"].append(None); col["_group_name"].append(None)
            col["_group_match"].append(None); continue
        norm = normalize_name(loc)
        if not norm:
            col["_group"].append(None); col["_group_name"].append(None)
            col["_group_match"].append("NONE"); continue
        if _LINE_RELATION.search(str(loc)):
            col["_group"].append(None); col["_group_name"].append(None)
            col["_group_match"].append("LINE"); continue
        tok = _tokens(norm)
        precise = [(g, n) for s, st, g, n in pairs if s == norm]
        candidates = precise or [(g, n) for s, st, g, n in pairs if _substring(st, tok)]
        flat = list(dict.fromkeys(
            (g, n) for groups, names in candidates for g, n in zip(groups, names)))
        if not flat:
            col["_group"].append(None); col["_group_name"].append(None)
            col["_group_match"].append("NONE")
        elif len({g for g, _ in flat}) > 1:
            col["_group"].append(None); col["_group_name"].append(None)
            col["_group_match"].append("AMBIGUOUS")
        else:
            col["_group"].append(flat[0][0]); col["_group_name"].append(flat[0][1])
            col["_group_match"].append("EXACT" if precise else "EXTENDED")
    out = df.copy()
    for k, v in col.items():
        out[k] = v
    return out


def node_loading(
    df: pd.DataFrame,
    capacity_field: str = "capacity_injected",
    direction: str | None = None,
    direction_column: str = "_direction",
    group_column: str = "_group_no",
    active_statuses: Iterable[str] | None = None,
    entity_column: str = "_entity",
    voltage: str | None = None,
) -> pd.DataFrame:
    """Node loading: the capacity of the active queue against the disclosed available capacity.

    A ratio greater than one means that the queue alone exceeds the capacity that the
    publisher declares as available. This is a measurable form of the "available connection
    capacity" criterion.

    Requires a frame after `assign_to_nodes`. When the publisher reports available capacity
    separately for the generation direction and the offtake direction, `direction` selects the
    correct node rows; by default it is derived from `capacity_field`.

    Nodes with zero available capacity are returned with a ``NaN`` ratio and the
    `available_capacity_zero` flag: the ratio there is UNDEFINED, not infinite,
    and averaging it would be an error. The row nonetheless retains the capacity applied for,
    because a queue at a node with no free capacity is information, not missing data.

    ``voltage`` keeps only applications whose ``voltage_level`` contains the given text.
    The base variant of the article counts the 110 kV queue (``napiecie="110"``), because the
    available capacity a distribution operator discloses for a node is the capacity of its
    high-voltage busbars; the default (``None``) counts applications at every voltage level,
    which is the article's upper variant.
    """
    if active_statuses is None:
        active_statuses = ("APPLICATION_FILED", "APPLICATION_INCOMPLETE",
                          "UNDER_REVIEW", "CONDITIONS_ISSUED", "AGREEMENT_IN_FORCE")
    if direction is None and direction_column in df.columns:
        available = set(df[direction_column].dropna().unique())
        default = "generation" if "injected" in capacity_field else "demand"
        direction = default if default in available else None
    is_node = df[entity_column] == "NODE" if entity_column in df.columns \
        else df["capacity_available"].notna()
    applications = df[~is_node]
    applications = applications[applications["process_status"].isin(set(active_statuses))]
    if voltage is not None and "voltage_level" in applications.columns:
        applications = applications[applications["voltage_level"].astype("string")
                          .str.contains(voltage, regex=False, na=False)]
    applications = applications[applications["_group"].notna()]
    total = applications.groupby("_group")[capacity_field].sum(min_count=1).rename("capacity_requested")
    count = applications.groupby("_group").size().rename("applications")
    nodes_df = df[is_node]
    nodes_df = nodes_df[nodes_df["capacity_available"].notna()]
    if direction is not None and direction_column in nodes_df.columns:
        nodes_df = nodes_df[nodes_df[direction_column] == direction]
    key = group_column if group_column in nodes_df.columns else "node_id"
    columns = [c for c in ("node_id", "node_name", "capacity_available", "voltage_level")
               if c in nodes_df.columns]
    base = nodes_df.set_index(nodes_df[key])[columns].join(total).join(count)
    base.index.name = "group"
    base["capacity_requested"] = base["capacity_requested"].fillna(0.0)
    base["applications"] = base["applications"].fillna(0).astype(int)
    base["available_capacity_zero"] = base["capacity_available"] == 0
    free = base["capacity_available"].where(~base["available_capacity_zero"])
    base["loading"] = base["capacity_requested"] / free
    base["direction"] = direction
    return base.reset_index()


def processing_time(
    df: pd.DataFrame,
    start: str = "date_application",
    end: str = "date_conditions",
    as_at=None,
) -> pd.DataFrame:
    """Processing time together with censoring classification.

    An application without a resolution date is NOT missing data: it is an observation
    censored at the edition's publication date. The function returns the column `time_days` for
    both kinds of observations, as well as `event` equal to 1 for resolved ones and 0
    for censored ones, in the form expected by the survival estimator.

    By default (``na_dzien=None``) every open application is censored at the publication
    date of ITS OWN row (``date_published``), so that a panel of several publishers, or a
    publisher whose node and application documents carry different as-at dates, censors
    each application at the date its document describes. Rows without a publication date
    are censored at the latest publication date of the application rows, and failing that
    at the latest resolution date. A date given explicitly applies to every row.

    The censoring date is taken per row and not as the single latest publication date of the
    whole frame: for ENERGA-OPERATOR (applications as at 30 June, nodes as at 31 August 2026)
    the latter would lengthen every censored time by two months.
    """
    d = df.copy()
    for c in (start, end):
        d[c] = pd.to_datetime(d[c], errors="coerce")
    if as_at is None:
        own = pd.to_datetime(d["date_published"], errors="coerce") \
            if "date_published" in d else pd.Series(pd.NaT, index=d.index)
        applications = d["_entity"].fillna("APPLICATION").astype(str).str.upper() != "NODE" \
            if "_entity" in d else pd.Series(True, index=d.index)
        reserve = own[applications].max()
        if pd.isna(reserve):
            reserve = d[end].max()
        as_at = own.fillna(reserve)
    else:
        as_at = pd.Series(pd.to_datetime(as_at), index=d.index)
    has_start = d[start].notna()
    event = has_start & d[end].notna()
    time = pd.Series(pd.NA, index=d.index, dtype="Float64")
    time[event] = (d.loc[event, end] - d.loc[event, start]).dt.days
    truncated = has_start & ~event
    time[truncated] = (as_at[truncated] - d.loc[truncated, start]).dt.days
    d["time_days"] = time
    d["event"] = event.astype(int).where(has_start)
    d["as_at"] = as_at
    negative = d["time_days"] < 0
    d.loc[negative, ["time_days", "event"]] = pd.NA
    return d


@dataclass
class KMResult:
    """Kaplan-Meier survival curve with the Greenwood interval."""

    table: pd.DataFrame = field(repr=False)
    median: float
    median_lower: float
    median_upper: float
    n: int
    events: int
    censored: int

    def as_dict(self) -> dict:
        return {"n": self.n, "events": self.events, "censored": self.censored,
                "censored_share": self.censored / self.n if self.n else float("nan"),
                "median": self.median, "median_lower": self.median_lower,
                "median_upper": self.median_upper}


def kaplan_meier(time, event, alpha: float = 0.05) -> KMResult:
    """Kaplan-Meier estimator with Greenwood's variance.

    Implemented directly, so as not to introduce a dependency on a survival-analysis
    library for a single estimator. The interval for the median is determined
    by the curve-interval-inversion method: the bounds are the extreme times for
    which the curve's confidence band covers the level of 0.5.
    """
    d = pd.DataFrame({"t": pd.to_numeric(pd.Series(time), errors="coerce"),
                      "e": pd.to_numeric(pd.Series(event), errors="coerce")}).dropna()
    d = d[d["t"] >= 0]
    n0 = len(d)
    if n0 == 0:
        empty = pd.DataFrame(columns=["t", "n_at_risk", "events", "S", "S_lower", "S_upper"])
        return KMResult(empty, float("nan"), float("nan"), float("nan"), 0, 0, 0)
    try:
        from scipy.stats import norm
        z = float(norm.ppf(1 - alpha / 2))
    except Exception:
        z = 1.959963984540054
    times = sorted(d.loc[d["e"] == 1, "t"].unique())
    S, cumulative_value, rows = 1.0, 0.0, []
    for t in times:
        at_risk = int((d["t"] >= t).sum())
        zd = int(((d["t"] == t) & (d["e"] == 1)).sum())
        if at_risk == 0:
            continue
        S *= 1 - zd / at_risk
        if at_risk > zd:
            cumulative_value += zd / (at_risk * (at_risk - zd))
        se = S * math.sqrt(cumulative_value) if S > 0 else 0.0
        rows.append({"t": float(t), "n_at_risk": at_risk, "events": zd, "S": S,
                        "S_lower": max(0.0, S - z * se), "S_upper": min(1.0, S + z * se)})
    # Explicit columns: a group in which every observation is censored has no event time,
    # and a frame built from an empty list would have no columns at all (KeyError: 'S').
    tab = pd.DataFrame(rows, columns=["t", "n_at_risk", "events", "S", "S_lower", "S_upper"])

    def first_below(col):
        under = tab[tab[col] <= 0.5]
        return float(under["t"].iloc[0]) if len(under) else float("nan")

    # The lower band reaches 0.5 FIRST, so it gives the LOWER bound of the median; the upper
    # band reaches it last and gives the upper bound; with the two swapped the interval would
    # come out as median_lower > median > median_upper.
    return KMResult(
        table=tab,
        median=first_below("S"),
        median_lower=first_below("S_lower"),
        median_upper=first_below("S_upper"),
        n=n0,
        events=int((d["e"] == 1).sum()),
        censored=int((d["e"] == 0).sum()),
    )


def kaplan_meier_by_group(
    df: pd.DataFrame,
    by: str | Sequence[str] | None = "resource_class",
    start: str = "date_application",
    end: str = "date_conditions",
    min_n: int = 30,
    as_at=None,
) -> pd.DataFrame:
    """Kaplan-Meier summary per group: size, events, censoring, median and its interval.

    Combines :func:`processing_time` and :func:`kaplan_meier`. A group enters the table
    when it has at least ``min_n`` measurable applications (start date present, time not
    negative); this is the inclusion criterion of the article, fixed before the result is
    computed. ``by`` may be a column, a list of columns (joined with ``" / "``) or ``None``
    for the whole frame. Sorted by group size, largest first.
    """
    cols = ["group", "n", "events", "censored", "censored_share",
            "median", "median_lower", "median_upper"]
    if start not in df.columns or end not in df.columns:
        return pd.DataFrame(columns=cols)
    pt = processing_time(df, start=start, end=end, as_at=as_at)
    if by is None:
        key = pd.Series("all", index=pt.index)
    else:
        col = [by] if isinstance(by, str) else list(by)
        if any(k not in pt.columns for k in col):
            return pd.DataFrame(columns=cols)
        key = pt[col].astype("string").fillna("(empty)").agg(" / ".join, axis=1)
    rows = []
    for g, sub in pt.groupby(key, sort=False):
        km = kaplan_meier(sub["time_days"].astype("float64"), sub["event"].astype("float64"))
        if km.n >= min_n:
            rows.append({"group": str(g), **km.as_dict()})
    out = pd.DataFrame(rows, columns=cols)
    return out.sort_values("n", ascending=False, kind="stable").reset_index(drop=True)
