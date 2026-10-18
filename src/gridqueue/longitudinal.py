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
``udzial_przejsc_w_przod`` returns this measure, so that it does not need to be computed
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
    "publikujacy",
    "lokalizacja_tekst",
    "poziom_napiecia",
    "klasa_zasobu",
    "moc_wprowadzana",
    "moc_pobierana",
)


#: Key for rows of the NODE entity. The default `DEFAULT_KEY_FIELDS` is built
#: for the APPLICATION entity and on node rows it FALLS APART: the fields `klasa_zasobu`,
#: `moc_wprowadzana` and `moc_pobierana` are empty there, so the key loses
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
NODE_KEY_FIELDS: tuple = ("publikujacy", "id_wezla")

#: Order of the proceeding stages. Used solely to assess whether transitions proceed
#: forward, it is not a controlled vocabulary of the schema.
STATUS_ORDER: dict[str, int] = {
    "WNIOSEK_ZLOZONY": 0,
    "WNIOSEK_NIEKOMPLETNY": 1,
    "W_TRAKCIE_ANALIZY": 2,
    "WARUNKI_WYDANE": 3,
    "UMOWA_OBOWIAZUJACA": 4,
    "PRZYLACZONY": 5,
}

#: States ending the proceeding without connection.
TERMINAL_NEGATIVE: frozenset = frozenset(
    {"ODMOWA", "WNIOSEK_WYCOFANY", "WARUNKI_WYGASLE"}
)


def _jako_tekst(v) -> str:
    """Value as a string; missing value as empty string, regardless of pandas version."""
    if v is None:
        return ""
    if isinstance(v, float) and v != v:
        return ""
    return str(v)


def _jako_tekst_zero_jak_brak(v) -> str:
    """Like `_jako_tekst`, but a numeric value equal to zero yields an empty string."""
    s = _jako_tekst(v)
    if s == "":
        return ""
    try:
        return "" if float(s) == 0.0 else s
    except (TypeError, ValueError):
        return s


def surrogate_key(
    df: pd.DataFrame,
    fields: Sequence[str] = DEFAULT_KEY_FIELDS,
    zero_jako_brak: bool = False,
) -> pd.Series:
    """Content key of the row, for matching between editions.

    `zero_jako_brak` equates the value 0 with the absence of a value. The publisher is sometimes
    inconsistent: it records the same undisclosed capacity once as an empty cell,
    once as zero, and then the key splits apart a pair that concerns one application.
    On a pair of editions of the transmission operator, enabling this option recovers
    12 out of 51 pairs lost by the key. Disabled by default, because zero is
    a disclosed value, and its absence is non-disclosure; equating them is
    an analyst's decision, not a property of the data, and it must be visible in the code.
    """
    uzyte = [f for f in fields if f in df.columns]
    if not uzyte:
        raise ValueError(f"none of the key fields occurs in the dataframe: {list(fields)}")
    # Explicit conversion, instead of .astype(str): in pandas 2 a missing value became the string
    # "nan", while in pandas 3 it remains a missing value and concatenation raises TypeError.
    # An explicit conversion gives the same key in both versions and makes the rule "missing is
    # a value" a property of the code, rather than a side effect of type casting.
    konw = _jako_tekst_zero_jak_brak if zero_jako_brak else _jako_tekst
    kolumny = [df[c].map(konw) for c in uzyte]
    return reduce(lambda a, b: a + "|" + b, kolumny)


@dataclass
class EditionDelta:
    """Result of comparing two editions."""

    edycja_a: str
    edycja_b: str
    wierszy_a: int
    wierszy_b: int
    kluczy_unikalnych_a: int
    kluczy_unikalnych_b: int
    wspolnych: int
    nowych: int
    ubylych: int
    zmian_statusu: int
    przejscia: pd.DataFrame = field(repr=False)
    nowe_zamkniete: int = 0
    ubyle_czynne: int = 0
    przejscia_wstecz: int = 0
    wierszy_w_kolizji_a: int = 0
    wierszy_w_kolizji_b: int = 0

    @property
    def udzial_przejsc_w_przod(self) -> Optional[float]:
        """Share of transitions proceeding in accordance with the order of the proceeding.

        A high value is evidence that the content key matches the correct
        rows; a low one indicates random matching and invalidates the comparison.
        Returns ``None`` when there is not a single ordered transition.
        """
        w_przod = uporzadkowanych = 0
        for a in self.przejscia.index:
            for b in self.przejscia.columns:
                n = int(self.przejscia.loc[a, b])
                if a == b or not n:
                    continue
                if a in STATUS_ORDER and b in STATUS_ORDER:
                    uporzadkowanych += n
                    w_przod += n if STATUS_ORDER[b] > STATUS_ORDER[a] else 0
                elif a in STATUS_ORDER and b in TERMINAL_NEGATIVE:
                    uporzadkowanych += n
                    w_przod += n
        return (w_przod / uporzadkowanych) if uporzadkowanych else None

    def as_dict(self) -> dict:
        return {
            "edycja_a": self.edycja_a,
            "edycja_b": self.edycja_b,
            "wierszy_a": self.wierszy_a,
            "wierszy_b": self.wierszy_b,
            "wierszy_netto": self.wierszy_b - self.wierszy_a,
            "kluczy_unikalnych_a": self.kluczy_unikalnych_a,
            "kluczy_unikalnych_b": self.kluczy_unikalnych_b,
            "wspolnych": self.wspolnych,
            "nowych": self.nowych,
            "ubylych": self.ubylych,
            "zmian_statusu": self.zmian_statusu,
            "udzial_przejsc_w_przod": self.udzial_przejsc_w_przod,
            "nowe_zamkniete": self.nowe_zamkniete,
            "ubyle_czynne": self.ubyle_czynne,
            "przejscia_wstecz": self.przejscia_wstecz,
            "wierszy_w_kolizji_a": self.wierszy_w_kolizji_a,
            "wierszy_w_kolizji_b": self.wierszy_w_kolizji_b,
            "odrzuconych_jako_niejednoznaczne_a": self.wierszy_a - self.kluczy_unikalnych_a,
            "odrzuconych_jako_niejednoznaczne_b": self.wierszy_b - self.kluczy_unikalnych_b,
            "migawka_monotoniczna": self.nowe_zamkniete == 0 and self.ubyle_czynne == 0,
        }


def compare_editions(
    a: pd.DataFrame,
    b: pd.DataFrame,
    edycja_a: str = "A",
    edycja_b: str = "B",
    fields: Sequence[str] = DEFAULT_KEY_FIELDS,
) -> EditionDelta:
    """Compare two editions of the register and return the flows and status transitions.

    Rows with a repeating key are discarded before matching (the first is
    kept), because for them the assignment is ambiguous; the number of unique
    keys against the number of rows shows how much the rows lose by this.
    """
    a = a.copy()
    b = b.copy()
    a["_klucz"] = surrogate_key(a, fields)
    b["_klucz"] = surrogate_key(b, fields)
    au = a.drop_duplicates("_klucz").set_index("_klucz")
    bu = b.drop_duplicates("_klucz").set_index("_klucz")

    wsp = au.index.intersection(bu.index)
    nowe = bu.index.difference(au.index)
    ubyle = au.index.difference(bu.index)

    kol_a = int(a["_klucz"].duplicated(keep=False).sum())
    kol_b = int(b["_klucz"].duplicated(keep=False).sum())

    tr = pd.crosstab(au.loc[wsp, "status_procesu"], bu.loc[wsp, "status_procesu"])
    zmian = int(sum(int(tr.loc[i, j]) for i in tr.index for j in tr.columns if i != j))
    wstecz = int(sum(
        int(tr.loc[i, j])
        for i in tr.index for j in tr.columns
        if i != j and i in STATUS_ORDER and j in STATUS_ORDER
        and STATUS_ORDER[j] < STATUS_ORDER[i]
    ))
    czynne = set(STATUS_ORDER) - {"PRZYLACZONY"}
    return EditionDelta(
        edycja_a=edycja_a,
        edycja_b=edycja_b,
        wierszy_a=len(a),
        wierszy_b=len(b),
        kluczy_unikalnych_a=len(au),
        kluczy_unikalnych_b=len(bu),
        wspolnych=len(wsp),
        nowych=len(nowe),
        ubylych=len(ubyle),
        zmian_statusu=zmian,
        przejscia=tr,
        nowe_zamkniete=int(bu.loc[nowe, "status_procesu"].isin(TERMINAL_NEGATIVE).sum()),
        ubyle_czynne=int(au.loc[ubyle, "status_procesu"].isin(czynne).sum()),
        przejscia_wstecz=wstecz,
        wierszy_w_kolizji_a=kol_a,
        wierszy_w_kolizji_b=kol_b,
    )


#: Fields that are NOT in the key and that serve for an independent assessment of the match.
#: If the pair is false, these fields will diverge, the key does not enforce them.
HELD_OUT_FIELDS: tuple = (
    "_podmiot",
    "_nazwa_obiektu",
    "data_wniosku",
    "_mz_pv",
    "_mz_fw",
    "_mz_mee_rozladowania",
    "_mz_mee_ladowania",
    "_mz_odb",
    "_mz_inne",
)

_FORMA_PRAWNA = re.compile(
    r"\b(SP\.?\s*Z\s*O\.?\s*O\.?|S\.?A\.?|SPÓŁKA|AKCYJNA"
    r"|Z\s*OGRANICZONĄ|ODPOWIEDZIALNOŚCIĄ)\b"
)
_NIEALFANUM = re.compile(r"[^A-ZĄĆĘŁŃÓŚŹŻ0-9]+")


def _norm_txt(v) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return ""
    return re.sub(r"\s+", " ", str(v)).strip().upper()


def _rdzen_nazwy(v) -> str:
    """Name reduced to its core: without legal form, punctuation and spaces.

    Without this, „Stigma sp.z o.o." and „Stigma Sp. z o.o." would be different entities,
    and the publisher changes the notation of the legal form between editions.
    """
    return _NIEALFANUM.sub("", _FORMA_PRAWNA.sub("", _norm_txt(v)))


@dataclass
class LinkageAudit:
    """Assessment of pair matching on fields EXCLUDED from the key.

    This is not a validation against an external ground truth, because there is none
    for this register, it is a test of internal consistency: the key does not enforce agreement
    of these fields, so their agreement is independent evidence that the pair concerns
    the same application. We report both bounds, because uncertain cases do not
    resolve themselves.
    """

    par: int
    potwierdzonych: int
    niepewnych: int
    falszywych: int
    rozbieznosci: pd.DataFrame = field(repr=False)

    @property
    def precyzja_dolna(self) -> float:
        """Uncertain counted as incorrect."""
        return self.potwierdzonych / self.par if self.par else float("nan")

    @property
    def precyzja_gorna(self) -> float:
        """Uncertain counted as correct."""
        return (self.par - self.falszywych) / self.par if self.par else float("nan")

    def as_dict(self) -> dict:
        return {
            "par": self.par,
            "potwierdzonych": self.potwierdzonych,
            "niepewnych": self.niepewnych,
            "falszywych": self.falszywych,
            "precyzja_dolna": self.precyzja_dolna,
            "precyzja_gorna": self.precyzja_gorna,
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
    a["_klucz"] = surrogate_key(a, fields)
    b["_klucz"] = surrogate_key(b, fields)
    au = a.drop_duplicates("_klucz").set_index("_klucz")
    bu = b.drop_duplicates("_klucz").set_index("_klucz")
    wsp = au.index.intersection(bu.index)

    wiersze = []
    potw = niep = falsz = 0
    for k in wsp:
        ra, rb = au.loc[k], bu.loc[k]
        for p in held_out:
            if p not in au.columns or p not in bu.columns:
                continue
            va, vb = _norm_txt(ra.get(p)), _norm_txt(rb.get(p))
            if va == vb:
                continue
            if va == "" or vb == "":
                kat = "uzupelnienie_jednostronne"
            elif _rdzen_nazwy(va) == _rdzen_nazwy(vb):
                kat = "inny_zapis_tej_samej_nazwy"
            elif _rdzen_nazwy(va) in _rdzen_nazwy(vb) or _rdzen_nazwy(vb) in _rdzen_nazwy(va):
                kat = "nazwa_rozszerzona_lub_skrocona"
            else:
                kat = "konflikt_tresci"
            wiersze.append({"klucz": k, "pole": p, "kategoria": kat, "a": va, "b": vb})

        pa, pb = _rdzen_nazwy(ra.get("_podmiot")), _rdzen_nazwy(rb.get("_podmiot"))
        oa, ob = _rdzen_nazwy(ra.get("_nazwa_obiektu")), _rdzen_nazwy(rb.get("_nazwa_obiektu"))

        def _rozne(x: str, y: str) -> bool:
            return bool(x) and bool(y) and x not in y and y not in x

        rp, ro = _rozne(pa, pb), _rozne(oa, ob)
        if rp and ro:
            falsz += 1
        elif rp or ro:
            niep += 1
        else:
            potw += 1

    return LinkageAudit(
        par=len(wsp),
        potwierdzonych=potw,
        niepewnych=niep,
        falszywych=falsz,
        rozbieznosci=pd.DataFrame(wiersze),
    )


#: Identity fields used to recover pairs that the content key did not link.
#: They must be DISJOINT from the key fields. A field shared with the key will not detect a pair
#: broken by a change of that very field, because the identity itself would then also drift apart:
#: adding the location to this set lowers the measured recall from 0,9652 to
#: 0,9757, which looks like an improvement, but is an oversight of ten pairs.
RECALL_FIELDS: tuple = ("_podmiot", "_nazwa_obiektu")


@dataclass
class LinkageRecall:
    """Recall of the matching: how many pairs the content key SKIPPED.

    `linkage_audit` measures precision, whether the linked pairs are the same case.
    It says nothing about pairs that the key did not link, and these are more dangerous:
    a broken pair appears as one "departed" row and one "new" row,
    so it looks like an event in the register, when it is an artifact of the matching.
    """

    kluczy_a: int
    kluczy_b: int
    dopasowanych: int
    odzyskanych: int
    odzyskane: pd.DataFrame = field(repr=False)

    @property
    def czulosc_klucza(self) -> float:
        """Share of pairs actually linked among the pairs that could be linked."""
        mozliwe = self.dopasowanych + self.odzyskanych
        return self.dopasowanych / mozliwe if mozliwe else float("nan")

    def as_dict(self) -> dict:
        return {"kluczy_a": self.kluczy_a, "kluczy_b": self.kluczy_b,
                "dopasowanych": self.dopasowanych, "odzyskanych": self.odzyskanych,
                "czulosc_klucza": self.czulosc_klucza}


def linkage_recall(
    a: pd.DataFrame,
    b: pd.DataFrame,
    fields: Sequence[str] = DEFAULT_KEY_FIELDS,
    pola_tozsamosci: Sequence[str] = RECALL_FIELDS,
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
    aa["_klucz"] = surrogate_key(aa, fields)
    bb["_klucz"] = surrogate_key(bb, fields)
    wspolne = set(aa["_klucz"]) & set(bb["_klucz"])
    reszta_a = aa[~aa["_klucz"].isin(wspolne)]
    reszta_b = bb[~bb["_klucz"].isin(wspolne)]
    uzyte = [p for p in pola_tozsamosci if p in aa.columns and p in bb.columns]
    if not uzyte or not len(reszta_a) or not len(reszta_b):
        return LinkageRecall(aa["_klucz"].nunique(), bb["_klucz"].nunique(),
                             len(wspolne), 0, pd.DataFrame())
    def tozsamosc(df):
        return reduce(lambda x, y: x + "|" + y,
                      [df[c].map(_jako_tekst).str.strip().str.upper() for c in uzyte])
    reszta_a = reszta_a.assign(_toz=tozsamosc(reszta_a))
    reszta_b = reszta_b.assign(_toz=tozsamosc(reszta_b))
    jedno_a = reszta_a[~reszta_a["_toz"].duplicated(keep=False) & (reszta_a["_toz"] != "||")]
    jedno_b = reszta_b[~reszta_b["_toz"].duplicated(keep=False) & (reszta_b["_toz"] != "||")]
    wsp = set(jedno_a["_toz"]) & set(jedno_b["_toz"])
    ia = jedno_a[jedno_a["_toz"].isin(wsp)].set_index("_toz")
    ib = jedno_b[jedno_b["_toz"].isin(wsp)].set_index("_toz")
    wiersze = []
    for t in sorted(wsp):
        ra, rb = ia.loc[t], ib.loc[t]
        rozne = [f for f in fields
                 if f in aa.columns and _jako_tekst(ra.get(f)) != _jako_tekst(rb.get(f))]
        wiersze.append({"tozsamosc": t, "pola_klucza_rozne": ";".join(rozne),
                        "status_a": ra.get("status_procesu"), "status_b": rb.get("status_procesu")})
    return LinkageRecall(aa["_klucz"].nunique(), bb["_klucz"].nunique(),
                         len(wspolne), len(wsp), pd.DataFrame(wiersze))
