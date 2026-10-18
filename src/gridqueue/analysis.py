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
    "PRZEDROSTKI_STACJI",
    "normalizuj_nazwe",
    "station_node_map",
    "assign_to_nodes",
    "node_loading",
    "processing_time",
    "kaplan_meier",
    "KMResult",
]

#: Prefixes of station designations, removed before comparing names. They do not carry
#: object identity, and occur inconsistently on both sides of the join.
PRZEDROSTKI_STACJI: tuple[str, ...] = ("GPZ", "SE", "RS", "RPZ", "STACJA")

_NIEALFANUM = re.compile(r"[^a-z0-9 ]+")

#: Entries describing an object PLANNED ON A LINE between stations, rather than an object
#: at a node. Assigning them to a node would be arbitrary: the line connects two nodes,
#: and matching by name would pick whichever end happens to appear
#: in the station list. The full capacity of such an application does not load either of them
#: in full, so the entry remains unassigned and is explicitly flagged.
_RELACJA_LINII = re.compile(
    r"\b(w\s+lini(?:i|ach)|relacj(?:i|a)|odczep\s+z\s+lini)", re.IGNORECASE)

#: Letters whose canonical decomposition does NOT separate the diacritical mark: Unicode
#: treats them as separate letters, so NFKD does not decompose them, and naive cleaning
#: turns them into a space, splitting the word ("Białogard" -> "bia ogard").
_NIEROZKLADALNE = {"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O",
                   "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"}


def normalizuj_nazwe(v) -> str:
    """Station name reduced to a comparable form.

    Removes diacritical marks, converts to lowercase, drops designation
    prefixes and extraneous characters. The comparison is performed on TOKENS, not characters,
    so that "Kutno" does not match "Kutnowska".
    """
    if v is None or (isinstance(v, float) and v != v):
        return ""
    s = str(v)
    for znak, zamiennik in _NIEROZKLADALNE.items():
        s = s.replace(znak, zamiennik)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = _NIEALFANUM.sub(" ", s)
    tokeny = [t for t in s.split() if t and t.upper() not in PRZEDROSTKI_STACJI]
    return " ".join(tokeny)


def _tokeny(s: str) -> tuple[str, ...]:
    return tuple(s.split())


def _podciag(igla: Sequence[str], stog: Sequence[str]) -> bool:
    """Whether `igla` is a contiguous subsequence of the tokens of `stog`."""
    n, m = len(igla), len(stog)
    if n == 0 or n > m:
        return False
    return any(tuple(stog[i : i + n]) == tuple(igla) for i in range(m - n + 1))


def station_node_map(
    df: pd.DataFrame,
    kolumna_encji: str = "_encja",
    kolumna_grupy: str = "_nr_grupy",
    separator: str = ",",
) -> pd.DataFrame:
    """Mapping: station -> station group, read from WEZEL entity rows.

    A publisher that carries out point 2 of the duty by splitting stations into GROUPS
    lists the composition of the group in the location field. This is the only place where
    a station's membership in a node is disclosed at all, hence this function.

    The key is the GROUP, not the node-row identifier. The publisher
    issues the same group separately for the generation direction and the offtake direction, so
    mapping by row identifier would make every station
    ambiguous, which would be an artifact of the document layout, not a property of the network.
    When the group column is not present, the key becomes the node identifier.

    Returns a frame: publikujacy, grupa, nazwa_wezla, stacja, stacja_norm.
    """
    if kolumna_encji in df.columns:
        wez = df[df[kolumna_encji] == "WEZEL"]
    else:  # without entity annotation, we recognize a node by the presence of available capacity
        wez = df[df["moc_dostepna"].notna()] if "moc_dostepna" in df else df.iloc[0:0]
    klucz = kolumna_grupy if kolumna_grupy in df.columns else "id_wezla"
    wiersze = []
    for _, r in wez.iterrows():
        lista = r.get("lokalizacja_tekst")
        if lista is None or (isinstance(lista, float) and lista != lista):
            continue
        for czesc in str(lista).split(separator):
            nazwa = czesc.strip()
            if not nazwa:
                continue
            wiersze.append(
                {
                    "publikujacy": r.get("publikujacy"),
                    "grupa": r.get(klucz),
                    "nazwa_wezla": r.get("nazwa_wezla"),
                    "stacja": nazwa,
                    "stacja_norm": normalizuj_nazwe(nazwa),
                }
            )
    out = pd.DataFrame(wiersze)
    if not len(out):
        return out
    out = out[out["stacja_norm"] != ""]
    return out.drop_duplicates(["grupa", "stacja_norm"]).reset_index(drop=True)


def assign_to_nodes(
    df: pd.DataFrame,
    mapa: pd.DataFrame,
    kolumna_encji: str = "_encja",
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

    Adds the columns `_grupa`, `_grupa_nazwa`, `_grupa_dopasowanie`.
    """
    if not len(mapa):
        out = df.copy()
        out["_grupa"] = None
        out["_grupa_nazwa"] = None
        out["_grupa_dopasowanie"] = "NONE"
        return out
    maska = df[kolumna_encji] != "WEZEL" if kolumna_encji in df.columns \
        else pd.Series(True, index=df.index)
    wykaz = (
        mapa.groupby("stacja_norm")
        .agg(grupa=("grupa", lambda s: tuple(dict.fromkeys(s))),
             nazwa=("nazwa_wezla", lambda s: tuple(dict.fromkeys(s))))
        .reset_index()
    )
    pary = [(s, _tokeny(s), g, n) for s, g, n in
            zip(wykaz["stacja_norm"], wykaz["grupa"], wykaz["nazwa"])]
    kol = {"_grupa": [], "_grupa_nazwa": [], "_grupa_dopasowanie": []}
    for idx, loc in df["lokalizacja_tekst"].items():
        if not maska.loc[idx]:
            kol["_grupa"].append(None); kol["_grupa_nazwa"].append(None)
            kol["_grupa_dopasowanie"].append(None); continue
        norm = normalizuj_nazwe(loc)
        if not norm:
            kol["_grupa"].append(None); kol["_grupa_nazwa"].append(None)
            kol["_grupa_dopasowanie"].append("NONE"); continue
        if _RELACJA_LINII.search(str(loc)):
            kol["_grupa"].append(None); kol["_grupa_nazwa"].append(None)
            kol["_grupa_dopasowanie"].append("LINE"); continue
        tok = _tokeny(norm)
        dokladne = [(g, n) for s, st, g, n in pary if s == norm]
        kandydaci = dokladne or [(g, n) for s, st, g, n in pary if _podciag(st, tok)]
        plaskie = list(dict.fromkeys(
            (g, n) for grupy, nazwy in kandydaci for g, n in zip(grupy, nazwy)))
        if not plaskie:
            kol["_grupa"].append(None); kol["_grupa_nazwa"].append(None)
            kol["_grupa_dopasowanie"].append("NONE")
        elif len({g for g, _ in plaskie}) > 1:
            kol["_grupa"].append(None); kol["_grupa_nazwa"].append(None)
            kol["_grupa_dopasowanie"].append("AMBIGUOUS")
        else:
            kol["_grupa"].append(plaskie[0][0]); kol["_grupa_nazwa"].append(plaskie[0][1])
            kol["_grupa_dopasowanie"].append("EXACT" if dokladne else "EXTENDED")
    out = df.copy()
    for k, v in kol.items():
        out[k] = v
    return out


def node_loading(
    df: pd.DataFrame,
    pole_mocy: str = "moc_wprowadzana",
    kierunek: str | None = None,
    kolumna_kierunku: str = "_kierunek",
    kolumna_grupy: str = "_nr_grupy",
    statusy_czynne: Iterable[str] | None = None,
    kolumna_encji: str = "_encja",
) -> pd.DataFrame:
    """Node loading: the capacity of the active queue against the disclosed available capacity.

    A ratio greater than one means that the queue alone exceeds the capacity that the
    publisher declares as available. This is a measurable form of the "available connection
    capacity" criterion.

    Requires a frame after `assign_to_nodes`. When the publisher reports available capacity
    separately for the generation direction and the offtake direction, `kierunek` selects the
    correct node rows; by default it is derived from `pole_mocy`.

    Nodes with zero available capacity are returned with a ``NaN`` ratio and the
    `moc_dostepna_zero` flag: the ratio there is UNDEFINED, not infinite,
    and averaging it would be an error. The row nonetheless retains the capacity applied for,
    because a queue at a node with no free capacity is information, not missing data.
    """
    if statusy_czynne is None:
        statusy_czynne = ("WNIOSEK_ZLOZONY", "WNIOSEK_NIEKOMPLETNY",
                          "W_TRAKCIE_ANALIZY", "WARUNKI_WYDANE", "UMOWA_OBOWIAZUJACA")
    if kierunek is None and kolumna_kierunku in df.columns:
        dostepne = set(df[kolumna_kierunku].dropna().unique())
        domysl = "wytworcza" if "wprowadzana" in pole_mocy else "odbiorcza"
        kierunek = domysl if domysl in dostepne else None
    jest_wezel = df[kolumna_encji] == "WEZEL" if kolumna_encji in df.columns \
        else df["moc_dostepna"].notna()
    wnioski = df[~jest_wezel]
    wnioski = wnioski[wnioski["status_procesu"].isin(set(statusy_czynne))]
    wnioski = wnioski[wnioski["_grupa"].notna()]
    suma = wnioski.groupby("_grupa")[pole_mocy].sum(min_count=1).rename("moc_wnioskowana")
    liczba = wnioski.groupby("_grupa").size().rename("wnioskow")
    wez = df[jest_wezel]
    wez = wez[wez["moc_dostepna"].notna()]
    if kierunek is not None and kolumna_kierunku in wez.columns:
        wez = wez[wez[kolumna_kierunku] == kierunek]
    klucz = kolumna_grupy if kolumna_grupy in wez.columns else "id_wezla"
    kolumny = [c for c in ("id_wezla", "nazwa_wezla", "moc_dostepna", "poziom_napiecia")
               if c in wez.columns]
    baza = wez.set_index(wez[klucz])[kolumny].join(suma).join(liczba)
    baza.index.name = "grupa"
    baza["moc_wnioskowana"] = baza["moc_wnioskowana"].fillna(0.0)
    baza["wnioskow"] = baza["wnioskow"].fillna(0).astype(int)
    baza["moc_dostepna_zero"] = baza["moc_dostepna"] == 0
    wolna = baza["moc_dostepna"].where(~baza["moc_dostepna_zero"])
    baza["obciazenie"] = baza["moc_wnioskowana"] / wolna
    baza["kierunek"] = kierunek
    return baza.reset_index()


def processing_time(
    df: pd.DataFrame,
    od: str = "data_wniosku",
    do: str = "data_warunkow",
    na_dzien=None,
) -> pd.DataFrame:
    """Processing time together with censoring classification.

    An application without a resolution date is NOT missing data: it is an observation
    censored at the edition's publication date. The function returns the column `czas_dni` for
    both kinds of observations, as well as `zdarzenie` equal to 1 for resolved ones and 0
    for censored ones, in the form expected by the survival estimator.

    `na_dzien` by default takes the maximum of the publication-date field, and when that is
    absent, the maximum of the resolution dates.
    """
    d = df.copy()
    for c in (od, do):
        d[c] = pd.to_datetime(d[c], errors="coerce")
    if na_dzien is None:
        if "data_publikacji" in d:
            na_dzien = pd.to_datetime(d["data_publikacji"], errors="coerce").max()
        if na_dzien is None or pd.isna(na_dzien):
            na_dzien = d[do].max()
    na_dzien = pd.to_datetime(na_dzien)
    ma_start = d[od].notna()
    zdarzenie = ma_start & d[do].notna()
    czas = pd.Series(pd.NA, index=d.index, dtype="Float64")
    czas[zdarzenie] = (d.loc[zdarzenie, do] - d.loc[zdarzenie, od]).dt.days
    uciete = ma_start & ~zdarzenie
    czas[uciete] = (na_dzien - d.loc[uciete, od]).dt.days
    d["czas_dni"] = czas
    d["zdarzenie"] = zdarzenie.astype(int).where(ma_start)
    d["na_dzien"] = na_dzien
    ujemne = d["czas_dni"] < 0
    d.loc[ujemne, ["czas_dni", "zdarzenie"]] = pd.NA
    return d


@dataclass
class KMResult:
    """Kaplan-Meier survival curve with the Greenwood interval."""

    tabela: pd.DataFrame = field(repr=False)
    mediana: float
    mediana_dolna: float
    mediana_gorna: float
    n: int
    zdarzen: int
    cenzurowanych: int

    def as_dict(self) -> dict:
        return {"n": self.n, "zdarzen": self.zdarzen, "cenzurowanych": self.cenzurowanych,
                "udzial_cenzurowanych": self.cenzurowanych / self.n if self.n else float("nan"),
                "mediana": self.mediana, "mediana_dolna": self.mediana_dolna,
                "mediana_gorna": self.mediana_gorna}


def kaplan_meier(czas, zdarzenie, alpha: float = 0.05) -> KMResult:
    """Kaplan-Meier estimator with Greenwood's variance.

    Implemented directly, so as not to introduce a dependency on a survival-analysis
    library for a single estimator. The interval for the median is determined
    by the curve-interval-inversion method: the bounds are the extreme times for
    which the curve's confidence band covers the level of 0.5.
    """
    d = pd.DataFrame({"t": pd.to_numeric(pd.Series(czas), errors="coerce"),
                      "e": pd.to_numeric(pd.Series(zdarzenie), errors="coerce")}).dropna()
    d = d[d["t"] >= 0]
    n0 = len(d)
    if n0 == 0:
        pusta = pd.DataFrame(columns=["t", "n_ryzyka", "zdarzen", "S", "S_dolne", "S_gorne"])
        return KMResult(pusta, float("nan"), float("nan"), float("nan"), 0, 0, 0)
    try:
        from scipy.stats import norm
        z = float(norm.ppf(1 - alpha / 2))
    except Exception:
        z = 1.959963984540054
    czasy = sorted(d.loc[d["e"] == 1, "t"].unique())
    S, kum_war, wiersze = 1.0, 0.0, []
    for t in czasy:
        n_ryz = int((d["t"] >= t).sum())
        zd = int(((d["t"] == t) & (d["e"] == 1)).sum())
        if n_ryz == 0:
            continue
        S *= 1 - zd / n_ryz
        if n_ryz > zd:
            kum_war += zd / (n_ryz * (n_ryz - zd))
        se = S * math.sqrt(kum_war) if S > 0 else 0.0
        wiersze.append({"t": float(t), "n_ryzyka": n_ryz, "zdarzen": zd, "S": S,
                        "S_dolne": max(0.0, S - z * se), "S_gorne": min(1.0, S + z * se)})
    tab = pd.DataFrame(wiersze)

    def pierwszy_ponizej(kol):
        pod = tab[tab[kol] <= 0.5]
        return float(pod["t"].iloc[0]) if len(pod) else float("nan")

    return KMResult(
        tabela=tab,
        mediana=pierwszy_ponizej("S"),
        mediana_dolna=pierwszy_ponizej("S_gorne"),
        mediana_gorna=pierwszy_ponizej("S_dolne"),
        n=n0,
        zdarzen=int((d["e"] == 1).sum()),
        cenzurowanych=int((d["e"] == 0).sum()),
    )
