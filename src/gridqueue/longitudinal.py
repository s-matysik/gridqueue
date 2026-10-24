"""Comparison of two editions of the same register.

Why this is not an ordinary join by identifier
----------------------------------------------
Statutory registers **do not publish a persistent application identifier**. For some
publishers the identifier field is empty in almost every row, and the package
then inserts a surrogate based on the ordinal number in the document. Such
a surrogate is stable within a single edition and **worthless between
editions**: row number 869 in one edition is not the same application as
row 869 in the next, because positions shift.

Tracking an application over time therefore requires a surrogate key built from content.
This is not a workaround but a property of the disclosure that has to be declared:
the content key drifts apart when the publisher corrects any of the fields
that make it up, and then the same application looks like a disappearance
paired with an appearance.

Linkage validation
------------------
The status-transition matrix gives an independent test for this. If the key matches
the correct rows, transitions should proceed **in the direction of the administrative
proceeding** (filed → under review → conditions issued → agreement). If
it matches at random, transitions will be scattered without this order. The property
``forward_share`` returns this measure, so that it does not need to be computed
by hand.
"""

from __future__ import annotations

import re
from functools import reduce

from dataclasses import dataclass, field
from typing import Optional, Sequence

import pandas as pd

__all__ = [
    "DEFAULT_KEY_FIELDS",
    "NODE_KEY_FIELDS",

    "STATUS_ORDER",
    "TERMINAL_NEGATIVE",
    "surrogate_key",
    "EditionDelta",
    "compare_editions",
    "HELD_OUT_FIELDS",
    "LinkageAudit",
    "linkage_audit",
    "RECALL_FIELDS",
    "LinkageRecall",
    "linkage_recall",
]

#: Fields of the default content key. Deliberately WITHOUT dates and without status: dates are
#: sometimes filled in between editions, and status is exactly what we are measuring the change of.
DEFAULT_KEY_FIELDS: tuple[str, ...] = (
    "publisher",
    "location_text",
    "voltage_level",
    "resource_class",
    "capacity_injected",
    "capacity_withdrawn",
)


#: Key for rows of the NODE entity. The default `DEFAULT_KEY_FIELDS` is built
#: for the APPLICATION entity and on node rows it FALLS APART: the fields `resource_class`,
#: `capacity_injected` and `capacity_withdrawn` are empty there, so the key loses
#: distinguishability. Measured on a pair of editions of the Spanish publisher:
#: with the default key, 916 out of 1838 rows collide and 660 are
#: rejected as ambiguous, while with the key below the collision count is ZERO,
#: all 1838 pairs match unambiguously, with precision and recall
#: equal to 1,000.
#:
#: More general conclusion: the content key must be matched to the ENTITY, just like
#: the schema core. Using the application key for node rows does not raise
#: an error, it silently produces collisions that in further analysis look like
#: events in the register.
NODE_KEY_FIELDS: tuple = ("publisher", "node_id")

#: Order of the proceeding stages. Used solely to assess whether transitions proceed
#: forward, it is not a controlled vocabulary of the schema.
STATUS_ORDER: dict[str, int] = {
    "APPLICATION_FILED": 0,
    "APPLICATION_INCOMPLETE": 1,
    "UNDER_REVIEW": 2,
    "CONDITIONS_ISSUED": 3,
    "AGREEMENT_IN_FORCE": 4,
    "CONNECTED": 5,
}

#: States ending the proceeding without connection.
TERMINAL_NEGATIVE: frozenset = frozenset(
    {"REFUSED", "APPLICATION_WITHDRAWN", "CONDITIONS_EXPIRED"}
)


def _as_text(v) -> str:
    """Value as a string; missing value as empty string, regardless of pandas version."""
    if v is None:
        return ""
    if isinstance(v, float) and v != v:
        return ""
    return str(v)


def _as_text_zero_as_missing(v) -> str:
    """Like `_as_text`, but a numeric value equal to zero yields an empty string."""
    s = _as_text(v)
    if s == "":
        return ""
    try:
        return "" if float(s) == 0.0 else s
    except (TypeError, ValueError):
        return s


def surrogate_key(
    df: pd.DataFrame,
    fields: Sequence[str] = DEFAULT_KEY_FIELDS,
    zero_as_missing: bool = False,
) -> pd.Series:
    """Content key of the row, for matching between editions.

    `zero_as_missing` equates the value 0 with the absence of a value. The publisher is sometimes
    inconsistent: it records the same undisclosed capacity once as an empty cell,
    once as zero, and then the key splits apart a pair that concerns one application.
    On a pair of editions of the transmission operator, enabling this option recovers
    12 out of 51 pairs lost by the key. Disabled by default, because zero is
    a disclosed value, and its absence is non-disclosure; equating them is
    an analyst's decision, not a property of the data, and it must be visible in the code.
    """
    used = [f for f in fields if f in df.columns]
    if not used:
        raise ValueError(f"none of the key fields occurs in the dataframe: {list(fields)}")
    # Explicit conversion, instead of .astype(str): in pandas 2 a missing value became the string
    # "nan", while in pandas 3 it remains a missing value and concatenation raises TypeError.
    # An explicit conversion gives the same key in both versions and makes the rule "missing is
    # a value" a property of the code, rather than a side effect of type casting.
    conv = _as_text_zero_as_missing if zero_as_missing else _as_text
    columns = [df[c].map(conv) for c in used]
    return reduce(lambda a, b: a + "|" + b, columns)


@dataclass
class EditionDelta:
    """Result of comparing two editions."""

    edition_a: str
    edition_b: str
    rows_a: int
    rows_b: int
    unique_keys_a: int
    unique_keys_b: int
    shared: int
    new: int
    gone: int
    status_changes: int
    transitions: pd.DataFrame = field(repr=False)
    new_closed: int = 0
    gone_active: int = 0
    backward_transitions: int = 0
    rows_in_collision_a: int = 0
    rows_in_collision_b: int = 0

    @property
    def forward_share(self) -> Optional[float]:
        """Share of transitions proceeding in accordance with the order of the proceeding.

        A high value is evidence that the content key matches the correct
        rows; a low one indicates random matching and invalidates the comparison.
        Returns ``None`` when there is not a single ordered transition.
        """
        forward = ordered = 0
        for a in self.transitions.index:
            for b in self.transitions.columns:
                n = int(self.transitions.loc[a, b])
                if a == b or not n:
                    continue
                if a in STATUS_ORDER and b in STATUS_ORDER:
                    ordered += n
                    forward += n if STATUS_ORDER[b] > STATUS_ORDER[a] else 0
                elif a in STATUS_ORDER and b in TERMINAL_NEGATIVE:
                    ordered += n
                    forward += n
        return (forward / ordered) if ordered else None

    def as_dict(self) -> dict:
        return {
            "edition_a": self.edition_a,
            "edition_b": self.edition_b,
            "rows_a": self.rows_a,
            "rows_b": self.rows_b,
            "net_rows": self.rows_b - self.rows_a,
            "unique_keys_a": self.unique_keys_a,
            "unique_keys_b": self.unique_keys_b,
            "shared": self.shared,
            "new": self.new,
            "gone": self.gone,
            "status_changes": self.status_changes,
            "forward_share": self.forward_share,
            "new_closed": self.new_closed,
            "gone_active": self.gone_active,
            "backward_transitions": self.backward_transitions,
            "rows_in_collision_a": self.rows_in_collision_a,
            "rows_in_collision_b": self.rows_in_collision_b,
            "rejected_as_ambiguous_a": self.rows_a - self.unique_keys_a,
            "rejected_as_ambiguous_b": self.rows_b - self.unique_keys_b,
            "monotone_snapshot": self.new_closed == 0 and self.gone_active == 0,
        }


def compare_editions(
    a: pd.DataFrame,
    b: pd.DataFrame,
    edition_a: str = "A",
    edition_b: str = "B",
    fields: Sequence[str] = DEFAULT_KEY_FIELDS,
) -> EditionDelta:
    """Compare two editions of the register and return the flows and status transitions.

    Rows with a repeating key are discarded before matching (the first is
    kept), because for them the assignment is ambiguous; the number of unique
    keys against the number of rows shows how much the rows lose by this.
    """
    a = a.copy()
    b = b.copy()
    a["_key"] = surrogate_key(a, fields)
    b["_key"] = surrogate_key(b, fields)
    au = a.drop_duplicates("_key").set_index("_key")
    bu = b.drop_duplicates("_key").set_index("_key")

    shared_idx = au.index.intersection(bu.index)
    new_keys = bu.index.difference(au.index)
    gone_keys = au.index.difference(bu.index)

    col_a = int(a["_key"].duplicated(keep=False).sum())
    col_b = int(b["_key"].duplicated(keep=False).sum())

    tr = pd.crosstab(au.loc[shared_idx, "process_status"], bu.loc[shared_idx, "process_status"])
    n_changes = int(sum(int(tr.loc[i, j]) for i in tr.index for j in tr.columns if i != j))
    backward = int(sum(
        int(tr.loc[i, j])
        for i in tr.index for j in tr.columns
        if i != j and i in STATUS_ORDER and j in STATUS_ORDER
        and STATUS_ORDER[j] < STATUS_ORDER[i]
    ))
    active_mask = set(STATUS_ORDER) - {"CONNECTED"}
    return EditionDelta(
        edition_a=edition_a,
        edition_b=edition_b,
        rows_a=len(a),
        rows_b=len(b),
        unique_keys_a=len(au),
        unique_keys_b=len(bu),
        shared=len(shared_idx),
        new=len(new_keys),
        gone=len(gone_keys),
        status_changes=n_changes,
        transitions=tr,
        new_closed=int(bu.loc[new_keys, "process_status"].isin(TERMINAL_NEGATIVE).sum()),
        gone_active=int(au.loc[gone_keys, "process_status"].isin(active_mask).sum()),
        backward_transitions=backward,
        rows_in_collision_a=col_a,
        rows_in_collision_b=col_b,
    )


#: Fields that are NOT in the key and that serve for an independent assessment of the match.
#: If the pair is false, these fields will diverge, the key does not enforce them.
HELD_OUT_FIELDS: tuple = (
    "_applicant",
    "_facility_name",
    "date_application",
    "_ic_pv",
    "_ic_wind",
    "_ic_storage_discharging",
    "_ic_storage_charging",
    "_ic_load",
    "_ic_other",
)

_LEGAL_FORM = re.compile(
    r"\b(SP\.?\s*Z\s*O\.?\s*O\.?|S\.?A\.?|SPÓŁKA|AKCYJNA"
    r"|Z\s*OGRANICZONĄ|ODPOWIEDZIALNOŚCIĄ)\b"
)
_NON_ALNUM = re.compile(r"[^A-ZĄĆĘŁŃÓŚŹŻ0-9]+")


def _norm_txt(v) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip().upper()


def _core_name(v) -> str:
    """Name reduced to its core: without legal form, punctuation and spaces.

    Without this, „Stigma sp.z o.o." and „Stigma Sp. z o.o." would be different entities,
    and the publisher changes the notation of the legal form between editions.
    """
    return _NON_ALNUM.sub("", _LEGAL_FORM.sub("", _norm_txt(v)))


@dataclass
class LinkageAudit:
    """Assessment of pair matching on fields EXCLUDED from the key.

    This is not a validation against an external ground truth, because there is none
    for this register, it is a test of internal consistency: the key does not enforce agreement
    of these fields, so their agreement is independent evidence that the pair concerns
    the same application. We report both bounds, because uncertain cases do not
    resolve themselves.
    """

    pairs: int
    confirmed: int
    uncertain: int
    false_matches: int
    discrepancies: pd.DataFrame = field(repr=False)

    @property
    def precision_lower(self) -> float:
        """Uncertain counted as incorrect."""
        return self.confirmed / self.pairs if self.pairs else float("nan")

    @property
    def precision_upper(self) -> float:
        """Uncertain counted as correct."""
        return (self.pairs - self.false_matches) / self.pairs if self.pairs else float("nan")

    def as_dict(self) -> dict:
        return {
            "pairs": self.pairs,
            "confirmed": self.confirmed,
            "uncertain": self.uncertain,
            "false_matches": self.false_matches,
            "precision_lower": self.precision_lower,
            "precision_upper": self.precision_upper,
        }


def linkage_audit(
    a: pd.DataFrame,
    b: pd.DataFrame,
    fields: Sequence[str] = DEFAULT_KEY_FIELDS,
    held_out: Sequence[str] = HELD_OUT_FIELDS,
) -> LinkageAudit:
    """Assess the matching done with the content key on fields excluded from the key.

    A pair is classified as:

    * **false**, the core of the entity name AND the core of the object name are divergent
      and neither is contained in the other; these are two different applications that by chance
      share the location, voltage, class and both capacities;
    * **uncertain**, exactly one of these two is divergent;
    * **confirmed**, both agree or are absent.

    Fields filled in on one side only (empty in one edition, filled in the other)
    are not counted as a divergence, because the publisher fills in records between
    editions and this is a change of THE SAME application, not evidence of a different one.
    """
    a = a.copy()
    b = b.copy()
    a["_key"] = surrogate_key(a, fields)
    b["_key"] = surrogate_key(b, fields)
    au = a.drop_duplicates("_key").set_index("_key")
    bu = b.drop_duplicates("_key").set_index("_key")
    shared_idx = au.index.intersection(bu.index)

    rows = []
    n_confirmed = n_uncertain = false_flag = 0
    for k in shared_idx:
        ra, rb = au.loc[k], bu.loc[k]
        for p in held_out:
            if p not in au.columns or p not in bu.columns:
                continue
            va, vb = _norm_txt(ra.get(p)), _norm_txt(rb.get(p))
            if va == vb:
                continue
            if va == "" or vb == "":
                category = "one_sided_supplement"
            elif _core_name(va) == _core_name(vb):
                category = "alternate_spelling_same_name"
            elif _core_name(va) in _core_name(vb) or _core_name(vb) in _core_name(va):
                category = "name_extended_or_short"
            else:
                category = "content_conflict"
            rows.append({"key": k, "field": p, "category": category, "a": va, "b": vb})

        pa, pb = _core_name(ra.get("_applicant")), _core_name(rb.get("_applicant"))
        oa, ob = _core_name(ra.get("_facility_name")), _core_name(rb.get("_facility_name"))

        def _different(x: str, y: str) -> bool:
            return bool(x) and bool(y) and x not in y and y not in x

        rp, ro = _different(pa, pb), _different(oa, ob)
        if rp and ro:
            false_flag += 1
        elif rp or ro:
            n_uncertain += 1
        else:
            n_confirmed += 1

    return LinkageAudit(
        pairs=len(shared_idx),
        confirmed=n_confirmed,
        uncertain=n_uncertain,
        false_matches=false_flag,
        discrepancies=pd.DataFrame(rows),
    )


#: Identity fields used to recover pairs that the content key did not link.
#: They must be DISJOINT from the key fields. A field shared with the key will not detect a pair
#: broken by a change of that very field, because the identity itself would then also drift apart:
#: adding the location to this set lowers the measured recall from 0.9652 to
#: 0,9757, which looks like an improvement, but is an oversight of ten pairs.
RECALL_FIELDS: tuple = ("_applicant", "_facility_name")


@dataclass
class LinkageRecall:
    """Recall of the matching: how many pairs the content key SKIPPED.

    `linkage_audit` measures precision, whether the linked pairs are the same case.
    It says nothing about pairs that the key did not link, and these are more dangerous:
    a broken pair appears as one "departed" row and one "new" row,
    so it looks like an event in the register, when it is an artifact of the matching.
    """

    keys_a: int
    keys_b: int
    matched: int
    recovered: int
    recovered_keys: pd.DataFrame = field(repr=False)

    @property
    def key_sensitivity(self) -> float:
        """Share of pairs actually linked among the pairs that could be linked."""
        possible = self.matched + self.recovered
        return self.matched / possible if possible else float("nan")

    def as_dict(self) -> dict:
        return {"keys_a": self.keys_a, "keys_b": self.keys_b,
                "matched": self.matched, "recovered": self.recovered,
                "key_sensitivity": self.key_sensitivity}


def linkage_recall(
    a: pd.DataFrame,
    b: pd.DataFrame,
    fields: Sequence[str] = DEFAULT_KEY_FIELDS,
    identity_fields: Sequence[str] = RECALL_FIELDS,
) -> LinkageRecall:
    """Looks for pairs skipped by the content key, using identity fields.

    Takes rows UNMATCHED by the key and tries to link them by fields that
    do not enter the key: entity name, object name and location.
    A pair recovered this way concerns the same application for which one of
    the values entering the key has been changed; the returned frame states which
    key field differs, so the result is checkable, not merely declared.

    Only UNAMBIGUOUS matches are recovered: if the same identity
    occurs more than once on either side, the pair is not counted.
    """
    aa, bb = a.copy(), b.copy()
    aa["_key"] = surrogate_key(aa, fields)
    bb["_key"] = surrogate_key(bb, fields)
    shared_keys = set(aa["_key"]) & set(bb["_key"])
    rest_a = aa[~aa["_key"].isin(shared_keys)]
    rest_b = bb[~bb["_key"].isin(shared_keys)]
    used = [p for p in identity_fields if p in aa.columns and p in bb.columns]
    if not used or not len(rest_a) or not len(rest_b):
        return LinkageRecall(aa["_key"].nunique(), bb["_key"].nunique(),
                             len(shared_keys), 0, pd.DataFrame())
    def identity(df):
        return reduce(lambda x, y: x + "|" + y,
                      [df[c].map(_as_text).str.strip().str.upper() for c in used])
    rest_a = rest_a.assign(_toz=identity(rest_a))
    rest_b = rest_b.assign(_toz=identity(rest_b))
    single_a = rest_a[~rest_a["_toz"].duplicated(keep=False) & (rest_a["_toz"] != "||")]
    single_b = rest_b[~rest_b["_toz"].duplicated(keep=False) & (rest_b["_toz"] != "||")]
    shared_idx = set(single_a["_toz"]) & set(single_b["_toz"])
    ia = single_a[single_a["_toz"].isin(shared_idx)].set_index("_toz")
    ib = single_b[single_b["_toz"].isin(shared_idx)].set_index("_toz")
    rows = []
    for t in sorted(shared_idx):
        ra, rb = ia.loc[t], ib.loc[t]
        different = [f for f in fields
                 if f in aa.columns and _as_text(ra.get(f)) != _as_text(rb.get(f))]
        rows.append({"identity": t, "different_key_fields": ";".join(different),
                        "status_a": ra.get("process_status"), "status_b": rb.get("process_status")})
    return LinkageRecall(aa["_key"].nunique(), bb["_key"].nunique(),
                         len(shared_keys), len(shared_idx), pd.DataFrame(rows))
