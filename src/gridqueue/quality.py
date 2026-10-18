"""Quality control of the dataset: rules derived from statute and from the semantics of the process.

Each rule returns a NUMBER OF VIOLATIONS, not an exception.  A violation is not a bug
in the tool; it is a property of the disclosure, and that is exactly why this module exists.
The quality report is a scientific result: it tells how internally consistent
the statutory publication is.

Rules:
  R1  monotonicznosc_dat        : application <= conditions <= agreement <= energization
  R2  waznosc_warunkow_2lata    : connection conditions are valid for 2 years
                                   (art. 7 ust. 8i); the expiry date must not
                                   fall later than 2 years after they were determined
  R3  dopuszczalnosc_przejsc    : status must be consistent with the set of dates present
  R4  spojnosc_jednostek_mocy   : capacity values in kW must fall within the physical
                                   range of connections >1 kV (detects an MW/kW mix-up)
  R5  zakresy_wartosci          : capacities non-negative, dates in the 1990-2100 window
  R6  duplikaty_identyfikatorow : the same id_wniosku in multiple rows
  R7  kompletnosc_rdzenia       : core of the ENTITY PROPER TO THE ROW: for WNIOSEK
                                   4 fields non-empty plus at least one of the pair
                                   (moc_pobierana, moc_wprowadzana); for WEZEL
                                   id_wezla plus at least one of the pair
                                   (moc_dostepna, ograniczenie_flaga)
  R8  slownik_kontrolowany      : klasa_zasobu and status_procesu from the dictionary
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

import pandas as pd
from typing import Any, Callable, Optional

from .schema import (CORE_ALTERNATIVES, CORE_BY_ENTITY, CORE_FIELDS, DEFAULT_ENTITY,
                     ENTITY_COLUMN, KLASY_ZASOBU, STATUSY, core_complete_mask, _is_null)

__all__ = ["Rule", "RULES", "run_quality", "QualityReport"]


@dataclass
class Rule:
    kod: str
    nazwa: str
    podstawa: str
    fn: Callable[[Any], tuple[int, dict]] = field(repr=False)


@dataclass
class QualityReport:
    n_wierszy: int
    reguly: list[dict]

    def as_dict(self) -> dict:
        return {"n_wierszy": self.n_wierszy,
                "n_regul": len(self.reguly),
                "reguly": self.reguly,
                "naruszen_lacznie": sum(r["naruszenia"] for r in self.reguly)}

    def as_frame(self):
        """One row per rule: kod, nazwa, naruszenia, udzial.

        The `szczegoly` column is deliberately omitted; its content differs
        structurally between rules, so in the dataframe it would be a column of objects.
        Full details are returned by `as_dict()`.
        """
        import pandas as pd

        return pd.DataFrame(
            [{"kod": r["kod"], "nazwa": r["nazwa"],
              "naruszenia": r["naruszenia"], "udzial": r["udzial"]}
             for r in self.reguly]
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


def r1_monotonicznosc_dat(df) -> tuple[int, dict]:
    order = ["data_wniosku", "data_warunkow", "data_umowy", "data_energizacji"]
    have = [c for c in order if c in df.columns]
    n_bad, pary = 0, {}
    for i in range(len(have) - 1):
        a, b = have[i], have[i + 1]
        cnt = 0
        for va, vb in zip(df[a], df[b]):
            da, db = _d(va), _d(vb)
            if da and db and da > db:
                cnt += 1
        if cnt:
            pary[f"{a}>{b}"] = cnt
    # row counted once
    mask = [False] * len(df)
    for i in range(len(have) - 1):
        a, b = have[i], have[i + 1]
        for j, (va, vb) in enumerate(zip(df[a], df[b])):
            da, db = _d(va), _d(vb)
            if da and db and da > db:
                mask[j] = True
    n_bad = sum(mask)
    return n_bad, {"pary": pary, "porownywane_pola": have}


def r2_waznosc_warunkow(df) -> tuple[int, dict]:
    """Connection conditions are valid for two years (art. 7 ust. 8i).

    If the publisher provides an expiry date, it must fall no later
    than two years after the date the conditions were determined.  We also check agreements
    concluded after two years have elapsed from the conditions that did not expire.
    """
    if "data_warunkow" not in df.columns:
        return 0, {"uwaga": "missing field data_warunkow"}
    col_utr = "_data_utraty_waznosci" if "_data_utraty_waznosci" in df.columns else None
    n_utr_bad = n_umowa_bad = 0
    n_sprawdzonych_utr = 0
    nadwyzki: list[int] = []
    for i in range(len(df)):
        dw = _d(df["data_warunkow"].iloc[i])
        if not dw:
            continue
        limit = _plus_years(dw, 2)
        if col_utr:
            du = _d(df[col_utr].iloc[i])
            if du:
                n_sprawdzonych_utr += 1
                if du > limit:
                    n_utr_bad += 1
                    nadwyzki.append((du - limit).days)
        if "data_umowy" in df.columns:
            dm = _d(df["data_umowy"].iloc[i])
            if dm and dm > limit:
                n_umowa_bad += 1
    det = {
        "utrata_waznosci_pozniej_niz_2_lata": n_utr_bad,
        "sprawdzonych_dat_utraty": n_sprawdzonych_utr,
        "umowa_po_uplywie_2_lat_od_warunkow": n_umowa_bad,
    }
    if nadwyzki:
        nadwyzki.sort()
        det["nadwyzka_dni_mediana"] = nadwyzki[len(nadwyzki) // 2]
        det["nadwyzka_dni_min"] = nadwyzki[0]
        det["nadwyzka_dni_max"] = nadwyzki[-1]
        det["poza_tolerancja_30_dni"] = sum(1 for x in nadwyzki if x > 30)
        # The number MUST be computed, not hardcoded. Previously a literal
        # "334" stood here; that happened to be exactly how many came up on the panel of four
        # publishers, but the same string came back on EVERY call, including per publisher
        # and on the panel of six, where n_utr_bad has a different value. The diagnostics
        # then reported a number inconsistent with the rule's own result.
        det["interpretacja"] = (
            "a systematic shift by a constant number of days indicates an administrative "
            f"rule of the publisher, rather than {n_utr_bad} independent "
            "violations of the deadline"
        )
    return n_utr_bad + n_umowa_bad, det


#: which dates MUST / MUST NOT exist for a given status
_STATUS_WYMAGA: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # status: (required fields, forbidden fields)
    "WARUNKI_WYDANE": (("data_warunkow",), ("data_odmowy",)),
    "ODMOWA": (("data_odmowy",), ("data_umowy", "data_energizacji")),
    "UMOWA_OBOWIAZUJACA": (("data_umowy",), ("data_odmowy",)),
    "PRZYLACZONY": (("data_energizacji",), ("data_odmowy",)),
    "WNIOSEK_ZLOZONY": ((), ("data_umowy", "data_energizacji")),
    "W_TRAKCIE_ANALIZY": ((), ("data_umowy", "data_energizacji")),
    "WNIOSEK_NIEKOMPLETNY": ((), ("data_umowy", "data_energizacji")),
}


def r3_dopuszczalnosc_przejsc(df) -> tuple[int, dict]:
    """Status must be consistent with the set of dates present.

    We apply the requirement that a date be present ONLY to fields that the given publisher
    actually discloses.  The British register does not publish any process dates; demanding
    "agreement date" from it is not a consistency check but a category error.
    We determine the disclosed fields empirically: a column with at least one non-empty
    value within the publisher.
    """
    if "status_procesu" not in df.columns:
        return 0, {}
    date_cols = [c for c in ("data_wniosku", "data_warunkow", "data_odmowy",
                             "data_umowy", "data_energizacji") if c in df.columns]
    globalne = {c for c in date_cols if df[c].map(lambda v: not _is_null(v)).any()}
    if "publikujacy" in df.columns:
        ujawniane = {}
        for pub, g in df.groupby("publikujacy"):
            ujawniane[pub] = {c for c in date_cols if g[c].map(lambda v: not _is_null(v)).any()}
    else:
        ujawniane = None
    szczegoly: dict[str, int] = {}
    n_bad = 0
    for i in range(len(df)):
        st = df["status_procesu"].iloc[i]
        spec = _STATUS_WYMAGA.get(st)
        if not spec:
            continue
        # The key may not exist: groupby skips the group with an empty publisher name,
        # so a row without that annotation has no entry of its own.  In that case we use the
        # global set instead of raising a KeyError and losing the whole rule.
        dost = (ujawniane.get(df["publikujacy"].iloc[i], globalne)
                if ujawniane is not None else globalne)
        wymagane = tuple(c for c in spec[0] if c in dost)
        zakazane = spec[1]
        bad = False
        for c in wymagane:
            if c in df.columns and _is_null(df[c].iloc[i]):
                szczegoly[f"{st}: brak {c}"] = szczegoly.get(f"{st}: brak {c}", 0) + 1
                bad = True
        for c in zakazane:
            if c in df.columns and not _is_null(df[c].iloc[i]):
                szczegoly[f"{st}: nieoczekiwane {c}"] = szczegoly.get(f"{st}: nieoczekiwane {c}", 0) + 1
                bad = True
        n_bad += bad
    return n_bad, {"szczegoly": dict(sorted(szczegoly.items(), key=lambda kv: -kv[1])[:20])}


#: physical range of connections >1 kV in kW.  The lower threshold of 1 kW rejects values
#: that were most likely given in MW instead of kW; the upper bound of 5 GW is
#: above the largest single generating unit in the KSE.
_MOC_MIN_KW, _MOC_MAX_KW = 1.0, 5_000_000.0


def r4_spojnosc_jednostek(df) -> tuple[int, dict]:
    cols = [c for c in ("moc_wprowadzana", "moc_pobierana", "moc_dostepna",
                        "moc_zarezerwowana") if c in df.columns]
    per: dict[str, int] = {}
    mask = [False] * len(df)
    for c in cols:
        cnt = 0
        for j, v in enumerate(df[c]):
            if _is_null(v) or not isinstance(v, (int, float)):
                continue
            if v == 0:
                continue
            if v < _MOC_MIN_KW or v > _MOC_MAX_KW:
                cnt += 1
                mask[j] = True
        if cnt:
            per[c] = cnt
    return sum(mask), {"per_pole": per, "zakres_kw": [_MOC_MIN_KW, _MOC_MAX_KW]}


def r5_zakresy_wartosci(df) -> tuple[int, dict]:
    lo, hi = _dt.date(1990, 1, 1), _dt.date(2100, 1, 1)
    per: dict[str, int] = {}
    mask = [False] * len(df)
    for c in df.columns:
        if c.startswith("data_") or c.startswith("_data_"):
            cnt = 0
            for j, v in enumerate(df[c]):
                d = _d(v)
                if d and not (lo <= d <= hi):
                    cnt += 1
                    mask[j] = True
            if cnt:
                per[c] = cnt
        if c.startswith("moc_"):
            cnt = 0
            for j, v in enumerate(df[c]):
                if isinstance(v, (int, float)) and not _is_null(v) and v < 0:
                    cnt += 1
                    mask[j] = True
            if cnt:
                per[c + " (ujemna)"] = cnt
    return sum(mask), {"per_pole": per}


def r6_duplikaty_identyfikatorow(df) -> tuple[int, dict]:
    if "id_wniosku" not in df.columns:
        return 0, {}
    s = df["id_wniosku"].dropna()
    vc = s.value_counts()
    dup = vc[vc > 1]
    return int(dup.sum() - len(dup)), {
        "n_unikalnych": int(s.nunique()),
        "n_identyfikatorow_powtorzonych": int(len(dup)),
        "max_krotnosc": int(dup.max()) if len(dup) else 0,
    }


def r7_kompletnosc_rdzenia(df) -> tuple[int, dict]:
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
    for nazwa, spec in CORE_BY_ENTITY.items():
        sub = df.loc[enc == nazwa]
        if not len(sub):
            continue
        n_enc[nazwa] = int(len(sub))
        for c in spec["wymagane"]:
            if c not in sub.columns:
                per[f"{nazwa}/{c}"] = int(len(sub))
                continue
            cnt = int(sum(1 for v in sub[c] if _is_null(v)))
            if cnt:
                per[f"{nazwa}/{c}"] = cnt
        for grupa in spec["alternatywy"]:
            obecne = [c for c in grupa if c in sub.columns]
            etykieta = f"{nazwa}/at least one of: " + ", ".join(grupa)
            if not obecne:
                per[etykieta] = int(len(sub))
                continue
            cnt = int(sum(1 for _, row in sub[obecne].iterrows()
                          if all(_is_null(row[c]) for c in obecne)))
            if cnt:
                per[etykieta] = cnt
    return int((~core_complete_mask(df)).sum()), {"per_pole": per, "wierszy_encji": n_enc}


def r8_slownik_kontrolowany(df) -> tuple[int, dict]:
    per = {}
    mask = [False] * len(df)
    for c, vocab in (("klasa_zasobu", KLASY_ZASOBU), ("status_procesu", STATUSY)):
        if c not in df.columns:
            continue
        cnt = 0
        for j, v in enumerate(df[c]):
            if not _is_null(v) and v not in vocab:
                cnt += 1
                mask[j] = True
        if cnt:
            per[c] = cnt
    return sum(mask), {"per_pole": per}


RULES: tuple[Rule, ...] = (
    Rule("R1", "monotonicity of process dates", "process semantics (art. 7 ust. 8l pkt 1)",
         r1_monotonicznosc_dat),
    Rule("R2", "two-year validity of connection conditions", "art. 7 ust. 8i",
         r2_waznosc_warunkow),
    Rule("R3", "admissibility of process state given the dates", "process semantics",
         r3_dopuszczalnosc_przejsc),
    Rule("R4", "consistency of capacity units", "art. 7 ust. 8l (network >1 kV)",
         r4_spojnosc_jednostek),
    Rule("R5", "value ranges", "technical control", r5_zakresy_wartosci),
    Rule("R6", "duplicate identifiers", "requirement for identifiability of records",
         r6_duplikaty_identyfikatorow),
    Rule("R7", "completeness of the schema core", "art. 7 ust. 8l pkt 1/3/4",
         r7_kompletnosc_rdzenia),
    Rule("R8", "controlled dictionary", "inter-operator harmonization",
         r8_slownik_kontrolowany),
)


def run_quality(df, rules: Optional[tuple[Rule, ...]] = None) -> QualityReport:
    out = []
    for rule in (rules or RULES):
        try:
            n, det = rule.fn(df)
        except Exception as exc:  # a rule must not break the report
            n, det = -1, {"blad": f"{type(exc).__name__}: {exc}"}
        out.append({
            "kod": rule.kod,
            "nazwa": rule.nazwa,
            "podstawa": rule.podstawa,
            "naruszenia": int(n),
            "udzial": round(n / len(df), 6) if len(df) and n >= 0 else None,
            "szczegoly": det,
        })
    return QualityReport(int(len(df)), out)
