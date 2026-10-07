"""Analizy badawcze na zharmonizowanym panelu.

Dwie rodziny funkcji, obie wyprowadzone z pytań, które rejestr pozwala zadać
dopiero po harmonizacji:

* **obciążenie węzła** — zestawienie mocy objętej wnioskami z ujawnioną mocą
  dostępną w węźle. Jest to policzalna wersja kryterium „dostępna moc
  przyłączeniowa", które przeglądy literatury opisują jako niemierzalne
  z powodu braku danych. Wymaga publikującego, który ujawnia JEDNOCZEŚNIE moc
  dostępną w węźle i skład stacji wchodzących do węzła;
* **czas rozpatrywania z cenzurowaniem** — wnioski bez daty rozstrzygnięcia nie
  są brakiem danych, tylko obserwacjami uciętymi na dacie publikacji. Liczenie
  mediany wyłącznie na przypadkach kompletnych ZANIŻA ją, i to tym silniej, im
  dłuższy jest rzeczywisty czas rozpatrywania.

Żadna z tych funkcji nie jest specyficzna dla publikującego: specyficzne są
adaptery, a to jest warstwa nad schematem.
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

#: Przedrostki oznaczeń stacji, usuwane przed porównaniem nazw. Nie niosą
#: tożsamości obiektu, a występują niekonsekwentnie po obu stronach złączenia.
PRZEDROSTKI_STACJI: tuple[str, ...] = ("GPZ", "SE", "RS", "RPZ", "STACJA")

_NIEALFANUM = re.compile(r"[^a-z0-9 ]+")

#: Wpisy opisujące obiekt PLANOWANY NA LINII między stacjami, a nie obiekt
#: w węźle. Przypisanie ich do węzła byłoby arbitralne: linia łączy dwa węzły,
#: a dopasowanie po nazwie wybrałoby ten koniec, który akurat występuje
#: w wykazie stacji. Pełna moc takiego wniosku nie obciąża żadnego z nich
#: w całości, więc wpis zostaje nieprzypisany i jawnie oznaczony.
_RELACJA_LINII = re.compile(
    r"\b(w\s+lini(?:i|ach)|relacj(?:i|a)|odczep\s+z\s+lini)", re.IGNORECASE)

#: Litery, których rozkład kanoniczny NIE oddziela znaku diakrytycznego: Unicode
#: traktuje je jako osobne litery, więc NFKD ich nie rozkłada i naiwne czyszczenie
#: zamienia je na spację, rozcinając wyraz ("Białogard" -> "bia ogard").
_NIEROZKLADALNE = {"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O",
                   "ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"}


def normalizuj_nazwe(v) -> str:
    """Nazwa stacji sprowadzona do postaci porównywalnej.

    Usuwa znaki diakrytyczne, sprowadza do małych liter, odrzuca przedrostki
    oznaczeń i zbędne znaki. Porównanie odbywa się na TOKENACH, nie na znakach,
    żeby „Kutno" nie pasowało do „Kutnowska".
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
    """Czy `igla` jest ciągłym podciągiem tokenów `stog`."""
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
    """Odwzorowanie stacja → grupa stacji, odczytane z wierszy encji WEZEL.

    Publikujący, który realizuje punkt 2 obowiązku w podziale na GRUPY stacji,
    wymienia skład grupy w polu lokalizacji. To jedyne miejsce, w którym
    przynależność stacji do węzła jest w ogóle ujawniona — stąd ta funkcja.

    Kluczem jest GRUPA, nie identyfikator wiersza węzłowego. Publikujący
    wystawia tę samą grupę osobno dla kierunku wytwórczego i odbiorczego, więc
    odwzorowanie po identyfikatorze wiersza czyniłoby każdą stację
    dwuznaczną — co byłoby artefaktem układu dokumentu, nie własnością sieci.
    Gdy kolumna grupy nie występuje, kluczem staje się identyfikator węzła.

    Zwraca ramkę: publikujacy, grupa, nazwa_wezla, stacja, stacja_norm.
    """
    if kolumna_encji in df.columns:
        wez = df[df[kolumna_encji] == "WEZEL"]
    else:  # bez anotacji encji rozpoznajemy węzeł po obecności mocy dostępnej
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
    """Przypisuje wiersze wnioskowe do grup stacji przez nazwę stacji.

    Przypisanie jest NAZWOWE, nie topologiczne: opiera się na zgodności nazw
    ujawnionych przez publikującego, a nie na modelu sieci. Jego trafność nie
    jest tu walidowana wobec zewnętrznego wzorca, bo taki nie istnieje.

    Zwracany status rozróżnia cztery przypadki, bo brak przypisania
    i przypisanie niepewne to nie to samo:

    ``EXACT``      nazwa stacji równa lokalizacji wniosku po normalizacji
    ``EXTENDED``   lokalizacja zawiera nazwę stacji jako ciągły podciąg tokenów
    ``LINE``       obiekt planowany na linii między stacjami — nie w węźle
    ``AMBIGUOUS``  pasuje więcej niż jedna grupa — przypisania nie dokonujemy
    ``NONE``       brak trafienia albo brak lokalizacji

    Dodaje kolumny `_grupa`, `_grupa_nazwa`, `_grupa_dopasowanie`.
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
    """Obciążenie węzła: moc czynnej kolejki wobec ujawnionej mocy dostępnej.

    Iloraz większy od jedności oznacza, że sama kolejka przekracza moc, którą
    publikujący deklaruje jako dostępną. Jest to policzalna postać kryterium
    „dostępna moc przyłączeniowa".

    Wymaga ramki po `assign_to_nodes`. Gdy publikujący podaje moc dostępną
    osobno dla kierunku wytwórczego i odbiorczego, `kierunek` wybiera właściwe
    wiersze węzłowe; domyślnie wyprowadzany jest z `pole_mocy`.

    Węzły o zerowej mocy dostępnej zwracane są z ilorazem ``NaN`` i flagą
    `moc_dostepna_zero`: iloraz jest tam NIEOKREŚLONY, a nie nieskończony,
    i uśrednianie go byłoby błędem. Wiersz zachowuje jednak moc wnioskowaną,
    bo kolejka do węzła bez wolnej mocy jest informacją, nie brakiem danych.
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
    """Czas rozpatrywania wraz z klasyfikacją cenzurowania.

    Wniosek bez daty rozstrzygnięcia NIE jest brakiem danych: jest obserwacją
    uciętą na dacie publikacji edycji. Funkcja zwraca kolumnę `czas_dni` dla
    obu rodzajów obserwacji oraz `zdarzenie` równe 1 dla rozstrzygniętych i 0
    dla uciętych — w postaci, której oczekuje estymator przeżycia.

    `na_dzien` domyślnie bierze maksimum z pola daty publikacji, a gdy go brak —
    maksimum z dat rozstrzygnięć.
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
    """Krzywa przeżycia Kaplana-Meiera z przedziałem Greenwooda."""

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
    """Estymator Kaplana-Meiera z wariancją Greenwooda.

    Zaimplementowany wprost, żeby nie wprowadzać zależności od biblioteki
    analizy przeżycia dla jednego estymatora. Przedział dla mediany wyznaczany
    jest metodą odwrócenia przedziału krzywej: granicami są skrajne czasy, dla
    których pas ufności krzywej obejmuje poziom 0,5.
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
