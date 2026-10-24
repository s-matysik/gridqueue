"""Quality control of the dataset: rules derived from statute and from the semantics of the process.

Each rule returns a NUMBER OF VIOLATIONS, not an exception.  A violation is not a bug
in the tool; it is a property of the disclosure, and that is exactly why this module exists.
The quality report is a scientific result: it tells how internally consistent
the statutory publication is.

Rules:
  R1  monotonicznosc_dat        : application <= conditions <= agreement <= energization
  R2  waznosc_warunkow_2lata    : connection conditions are valid for 2 years
                                   (Art. 7(8i)); the expiry date must not
                                   fall later than 2 years after they were determined
  R3  dopuszczalnosc_przejsc    : status must be consistent with the set of dates present
  R4  spojnosc_jednostek_mocy   : capacity values in kW must fall within the physical
                                   range of connections >1 kV (detects an MW/kW mix-up)
  R5  zakresy_wartosci          : capacities non-negative, dates in the 1990-2100 window
  R6  duplikaty_identyfikatorow : the same application_id in multiple rows
  R7  kompletnosc_rdzenia       : core of the ENTITY PROPER TO THE ROW: for APPLICATION
                                   4 fields non-empty plus at least one of the pair
                                   (capacity_withdrawn, capacity_injected); for NODE
                                   node_id plus at least one of the pair
                                   (capacity_available, constraint_flag)
  R8  slownik_kontrolowany      : resource_class and process_status from the dictionary
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

import pandas as pd
from typing import Any, Callable, Optional

from .schema import (CORE_ALTERNATIVES, CORE_BY_ENTITY, CORE_FIELDS, DEFAULT_ENTITY,
                     ENTITY_COLUMN, RESOURCE_CLASSES, STATUSES, core_complete_mask, _is_null)

__all__ = ["Rule", "RULES", "run_quality", "QualityReport"]


@dataclass
class Rule:
    code: str
    name: str
    basis: str
    fn: Callable[[Any], tuple[int, dict]] = field(repr=False)


@dataclass
class QualityReport:
    n_rows: int
    rules: list[dict]

    def as_dict(self) -> dict:
        return {"n_rows": self.n_rows,
                "n_rules": len(self.rules),
                "rules": self.rules,
                "violations_total": sum(r["violations"] for r in self.rules)}

    def as_frame(self):
        """One row per rule: kod, nazwa, naruszenia, udzial.

        The `details` column is deliberately omitted; its content differs
        structurally between rules, so in the dataframe it would be a column of objects.
        Full details are returned by `as_dict()`.
        """
        import pandas as pd

        return pd.DataFrame(
            [{"code": r["code"], "name": r["name"],
              "violations": r["violations"], "share": r["share"]}
             for r in self.rules]
        )


def _plus_years(d: _dt.date, n: int) -> _dt.date:
    """Date shifted by n years; 29 February in a non-leap year -> 28 February."""
    try:
        return d.replace(year=d.year + n)
    except ValueError:
        return d.replace(year=d.year + n, day=28)


def _d(v) -> Optional[_dt.date]:
    if _is_null(v):
        return None
    try:
        return _dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------


def r1_date_monotonicity(df) -> tuple[int, dict]:
    order = ["date_application", "date_conditions", "date_agreement", "date_energisation"]
    have = [c for c in order if c in df.columns]
    n_bad, pairs = 0, {}
    for i in range(len(have) - 1):
        a, b = have[i], have[i + 1]
        cnt = 0
        for va, vb in zip(df[a], df[b]):
            da, db = _d(va), _d(vb)
            if da and db and da > db:
                cnt += 1
        if cnt:
            pairs[f"{a}>{b}"] = cnt
    # row counted once
    mask = [False] * len(df)
    for i in range(len(have) - 1):
        a, b = have[i], have[i + 1]
        for j, (va, vb) in enumerate(zip(df[a], df[b])):
            da, db = _d(va), _d(vb)
            if da and db and da > db:
                mask[j] = True
    n_bad = sum(mask)
    return n_bad, {"pairs": pairs, "compared_fields": have}


def r2_condition_validity(df) -> tuple[int, dict]:
    """Connection conditions are valid for two years (Art. 7(8i)).

    If the publisher provides an expiry date, it must fall no later
    than two years after the date the conditions were determined.  We also check agreements
    concluded after two years have elapsed from the conditions that did not expire.
    """
    if "date_conditions" not in df.columns:
        return 0, {"note": "missing field date_conditions"}
    col_utr = "_date_expiry" if "_date_expiry" in df.columns else None
    n_expiry_bad = n_contract_bad = 0
    n_checked_utr = 0
    surpluses: list[int] = []
    for i in range(len(df)):
        dw = _d(df["date_conditions"].iloc[i])
        if not dw:
            continue
        limit = _plus_years(dw, 2)
        if col_utr:
            du = _d(df[col_utr].iloc[i])
            if du:
                n_checked_utr += 1
                if du > limit:
                    n_expiry_bad += 1
                    surpluses.append((du - limit).days)
        if "date_agreement" in df.columns:
            dm = _d(df["date_agreement"].iloc[i])
            if dm and dm > limit:
                n_contract_bad += 1
    det = {
        "expiry_later_than_2_years": n_expiry_bad,
        "checked_loss_dates": n_checked_utr,
        "contract_after_2_years_from_conditions": n_contract_bad,
    }
    if surpluses:
        surpluses.sort()
        det["surplus_days_median"] = surpluses[len(surpluses) // 2]
        det["surplus_days_min"] = surpluses[0]
        det["surplus_days_max"] = surpluses[-1]
        det["outside_tolerance_30_days"] = sum(1 for x in surpluses if x > 30)
        # The number MUST be computed, not hardcoded. Previously a literal
        # "334" stood here; that happened to be exactly how many came up on the panel of four
        # publishers, but the same string came back on EVERY call, including per publisher
        # and on the panel of six, where n_expiry_bad has a different value. The diagnostics
        # then reported a number inconsistent with the rule's own result.
        det["interpretation"] = (
            "a systematic shift by a constant number of days indicates an administrative "
            f"rule of the publisher, rather than {n_expiry_bad} independent "
            "violations of the deadline"
        )
    return n_expiry_bad + n_contract_bad, det


#: which dates MUST / MUST NOT exist for a given status
_STATUS_REQUIRES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # status: (required fields, forbidden fields)
    "CONDITIONS_ISSUED": (("date_conditions",), ("date_refusal",)),
    "REFUSED": (("date_refusal",), ("date_agreement", "date_energisation")),
    "AGREEMENT_IN_FORCE": (("date_agreement",), ("date_refusal",)),
    "CONNECTED": (("date_energisation",), ("date_refusal",)),
    "APPLICATION_FILED": ((), ("date_agreement", "date_energisation")),
    "UNDER_REVIEW": ((), ("date_agreement", "date_energisation")),
    "APPLICATION_INCOMPLETE": ((), ("date_agreement", "date_energisation")),
}


def r3_transition_admissibility(df) -> tuple[int, dict]:
    """Status must be consistent with the set of dates present.

    We apply the requirement that a date be present ONLY to fields that the given publisher
    actually discloses.  The British register does not publish any process dates; demanding
    "agreement date" from it is not a consistency check but a category error.
    We determine the disclosed fields empirically: a column with at least one non-empty
    value within the publisher.
    """
    if "process_status" not in df.columns:
        return 0, {}
    date_cols = [c for c in ("date_application", "date_conditions", "date_refusal",
                             "date_agreement", "date_energisation") if c in df.columns]
    global_rules = {c for c in date_cols if df[c].map(lambda v: not _is_null(v)).any()}
    if "publisher" in df.columns:
        disclosed = {}
        for pub, g in df.groupby("publisher"):
            disclosed[pub] = {c for c in date_cols if g[c].map(lambda v: not _is_null(v)).any()}
    else:
        disclosed = None
    details: dict[str, int] = {}
    n_bad = 0
    for i in range(len(df)):
        st = df["process_status"].iloc[i]
        spec = _STATUS_REQUIRES.get(st)
        if not spec:
            continue
        # The key may not exist: groupby skips the group with an empty publisher name,
        # so a row without that annotation has no entry of its own.  In that case we use the
        # global set instead of raising a KeyError and losing the whole rule.
        avail = (disclosed.get(df["publisher"].iloc[i], global_rules)
                if disclosed is not None else global_rules)
        required = tuple(c for c in spec[0] if c in avail)
        forbidden = spec[1]
        bad = False
        for c in required:
            if c in df.columns and _is_null(df[c].iloc[i]):
                details[f"{st}: missing {c}"] = details.get(f"{st}: missing {c}", 0) + 1
                bad = True
        for c in forbidden:
            if c in df.columns and not _is_null(df[c].iloc[i]):
                details[f"{st}: nieoczekiwane {c}"] = details.get(f"{st}: nieoczekiwane {c}", 0) + 1
                bad = True
        n_bad += bad
    return n_bad, {"details": dict(sorted(details.items(), key=lambda kv: -kv[1])[:20])}


#: physical range of connections >1 kV in kW.  The lower threshold of 1 kW rejects values
#: that were most likely given in MW instead of kW; the upper bound of 5 GW is
#: above the largest single generating unit in the KSE.
_CAPACITY_MIN_KW, _CAPACITY_MAX_KW = 1.0, 5_000_000.0


def r4_unit_consistency(df) -> tuple[int, dict]:
    cols = [c for c in ("capacity_injected", "capacity_withdrawn", "capacity_available",
                        "capacity_reserved") if c in df.columns]
    per: dict[str, int] = {}
    mask = [False] * len(df)
    for c in cols:
        cnt = 0
        for j, v in enumerate(df[c]):
            if _is_null(v) or not isinstance(v, (int, float)):
                continue
            if v == 0:
                continue
            if v < _CAPACITY_MIN_KW or v > _CAPACITY_MAX_KW:
                cnt += 1
                mask[j] = True
        if cnt:
            per[c] = cnt
    return sum(mask), {"per_field": per, "range_kw": [_CAPACITY_MIN_KW, _CAPACITY_MAX_KW]}


def r5_value_ranges(df) -> tuple[int, dict]:
    lo, hi = _dt.date(1990, 1, 1), _dt.date(2100, 1, 1)
    per: dict[str, int] = {}
    mask = [False] * len(df)
    for c in df.columns:
        if c.startswith("date_") or c.startswith("_date_"):
            cnt = 0
            for j, v in enumerate(df[c]):
                d = _d(v)
                if d and not (lo <= d <= hi):
                    cnt += 1
                    mask[j] = True
            if cnt:
                per[c] = cnt
        if c.startswith("capacity_"):
            cnt = 0
            for j, v in enumerate(df[c]):
                if isinstance(v, (int, float)) and not _is_null(v) and v < 0:
                    cnt += 1
                    mask[j] = True
            if cnt:
                per[c + " (ujemna)"] = cnt
    return sum(mask), {"per_field": per}


def r6_identifier_duplicates(df) -> tuple[int, dict]:
    if "application_id" not in df.columns:
        return 0, {}
    s = df["application_id"].dropna()
    vc = s.value_counts()
    dup = vc[vc > 1]
    return int(dup.sum() - len(dup)), {
        "n_unique": int(s.nunique()),
        "n_repeated_identifiers": int(len(dup)),
        "max_multiplicity": int(dup.max()) if len(dup) else 0,
    }


def r7_core_completeness(df) -> tuple[int, dict]:
    """Schema core: all CORE_FIELDS non-empty, and from each group of
    CORE_ALTERNATIVES at least one field non-empty.

    The alternative group exists because a connection application always declares a capacity,
    but not always the same one: a generation one declares export capacity, a consumption one
    import capacity, a bidirectional one both.  Requiring one specific field would turn a
    property of the schema into an apparent disclosure violation.
    """
    if ENTITY_COLUMN in df.columns:
        enc = df[ENTITY_COLUMN].map(
            lambda v: DEFAULT_ENTITY if _is_null(v) else str(v).upper())
    else:
        enc = pd.Series(DEFAULT_ENTITY, index=df.index)

    per: dict[str, int] = {}
    n_enc: dict[str, int] = {}
    for name, spec in CORE_BY_ENTITY.items():
        sub = df.loc[enc == name]
        if not len(sub):
            continue
        n_enc[name] = int(len(sub))
        for c in spec["required"]:
            if c not in sub.columns:
                per[f"{name}/{c}"] = int(len(sub))
                continue
            cnt = int(sum(1 for v in sub[c] if _is_null(v)))
            if cnt:
                per[f"{name}/{c}"] = cnt
        for group in spec["alternatives"]:
            current = [c for c in group if c in sub.columns]
            label = f"{name}/at least one of: " + ", ".join(group)
            if not current:
                per[label] = int(len(sub))
                continue
            cnt = int(sum(1 for _, row in sub[current].iterrows()
                          if all(_is_null(row[c]) for c in current)))
            if cnt:
                per[label] = cnt
    return int((~core_complete_mask(df)).sum()), {"per_field": per, "entity_rows": n_enc}


def r8_controlled_vocabulary(df) -> tuple[int, dict]:
    per = {}
    mask = [False] * len(df)
    for c, vocab in (("resource_class", RESOURCE_CLASSES), ("process_status", STATUSES)):
        if c not in df.columns:
            continue
        cnt = 0
        for j, v in enumerate(df[c]):
            if not _is_null(v) and v not in vocab:
                cnt += 1
                mask[j] = True
        if cnt:
            per[c] = cnt
    return sum(mask), {"per_field": per}


RULES: tuple[Rule, ...] = (
    Rule("R1", "monotonicity of process dates", "process semantics (Art. 7(8l), item 1)",
         r1_date_monotonicity),
    Rule("R2", "two-year validity of connection conditions", "Art. 7(8i)",
         r2_condition_validity),
    Rule("R3", "admissibility of process state given the dates", "process semantics",
         r3_transition_admissibility),
    Rule("R4", "consistency of capacity units", "Art. 7(8l) (network >1 kV)",
         r4_unit_consistency),
    Rule("R5", "value ranges", "technical control", r5_value_ranges),
    Rule("R6", "duplicate identifiers", "requirement for identifiability of records",
         r6_identifier_duplicates),
    Rule("R7", "completeness of the schema core", "Art. 7(8l), item 1/3/4",
         r7_core_completeness),
    Rule("R8", "controlled dictionary", "inter-operator harmonization",
         r8_controlled_vocabulary),
)


def run_quality(df, rules: Optional[tuple[Rule, ...]] = None) -> QualityReport:
    out = []
    for rule in (rules or RULES):
        try:
            n, det = rule.fn(df)
        except Exception as exc:  # a rule must not break the report
            n, det = -1, {"error": f"{type(exc).__name__}: {exc}"}
        out.append({
            "code": rule.code,
            "name": rule.name,
            "basis": rule.basis,
            "violations": int(n),
            "share": round(n / len(df), 6) if len(df) and n >= 0 else None,
            "details": det,
        })
    return QualityReport(int(len(df)), out)
