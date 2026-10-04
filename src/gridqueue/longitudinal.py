"""Porównanie dwóch edycji tego samego rejestru.

Dlaczego to nie jest zwykłe złączenie po identyfikatorze
--------------------------------------------------------
Rejestry ustawowe **nie publikują trwałego identyfikatora wniosku**. U części
publikujących pole identyfikatora jest puste w niemal każdym wierszu, a pakiet
wstawia wtedy zastępnik oparty na liczbie porządkowej w dokumencie. Taki
zastępnik jest stabilny w obrębie jednej edycji i **bezwartościowy między
edycjami**: wiersz numer 869 w jednej edycji nie jest tym samym wnioskiem co
wiersz 869 w następnej, bo pozycje się przesuwają.

Śledzenie wniosku w czasie wymaga więc klucza zastępczego zbudowanego z treści.
Nie jest to obejście, lecz właściwość ujawnienia, którą trzeba zadeklarować:
klucz treściowy rozjeżdża się, gdy publikujący skoryguje którekolwiek z pól
wchodzących w jego skład, i wtedy ten sam wniosek wygląda jak zniknięcie
w parze z pojawieniem.

Walidacja dopasowania
---------------------
Macierz przejść statusu daje na to niezależny test. Jeśli klucz dopasowuje
właściwe wiersze, przejścia powinny biec **zgodnie z kierunkiem postępowania
administracyjnego** (złożony → w analizie → warunki wydane → umowa). Jeśli
dopasowuje losowo, przejścia będą rozłożone bez tego porządku. Własność
``udzial_przejsc_w_przod`` zwraca tę miarę, żeby nie trzeba jej było liczyć
ręcznie.
"""

from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Optional, Sequence

import pandas as pd

__all__ = [
    "DEFAULT_KEY_FIELDS",
    "STATUS_ORDER",
    "TERMINAL_NEGATIVE",
    "surrogate_key",
    "EditionDelta",
    "compare_editions",
    "HELD_OUT_FIELDS",
    "LinkageAudit",
    "linkage_audit",
]

#: Pola domyślnego klucza treściowego. Celowo BEZ dat i bez statusu: daty bywają
#: uzupełniane między edycjami, a status jest właśnie tym, czego zmianę mierzymy.
DEFAULT_KEY_FIELDS: tuple[str, ...] = (
    "publikujacy",
    "lokalizacja_tekst",
    "poziom_napiecia",
    "klasa_zasobu",
    "moc_wprowadzana",
    "moc_pobierana",
)

#: Porządek etapów postępowania. Służy wyłącznie do oceny, czy przejścia biegną
#: w przód — nie jest słownikiem kontrolowanym schematu.
STATUS_ORDER: dict[str, int] = {
    "WNIOSEK_ZLOZONY": 0,
    "WNIOSEK_NIEKOMPLETNY": 1,
    "W_TRAKCIE_ANALIZY": 2,
    "WARUNKI_WYDANE": 3,
    "UMOWA_OBOWIAZUJACA": 4,
    "PRZYLACZONY": 5,
}

#: Stany kończące postępowanie bez przyłączenia.
TERMINAL_NEGATIVE: frozenset = frozenset(
    {"ODMOWA", "WNIOSEK_WYCOFANY", "WARUNKI_WYGASLE"}
)


def surrogate_key(
    df: pd.DataFrame, fields: Sequence[str] = DEFAULT_KEY_FIELDS
) -> pd.Series:
    """Klucz treściowy wiersza, do dopasowania między edycjami."""
    uzyte = [f for f in fields if f in df.columns]
    if not uzyte:
        raise ValueError(f"żadne z pól klucza nie występuje w ramce: {list(fields)}")
    return df[uzyte].astype(str).apply(lambda r: "|".join(r.values), axis=1)


@dataclass
class EditionDelta:
    """Wynik porównania dwóch edycji."""

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
        """Udział przejść biegnących zgodnie z porządkiem postępowania.

        Wysoka wartość jest dowodem, że klucz treściowy dopasowuje właściwe
        wiersze; niska oznacza dopasowanie losowe i unieważnia porównanie.
        Zwraca ``None``, gdy nie ma ani jednego uporządkowanego przejścia.
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
    """Porównaj dwie edycje rejestru i zwróć przepływy oraz przejścia statusu.

    Wiersze o powtarzającym się kluczu są odrzucane przed dopasowaniem (pierwszy
    zachowany), bo dla nich przypisanie jest niejednoznaczne; liczba kluczy
    unikalnych wobec liczby wierszy pokazuje, ile wiersze na tym tracą.
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


#: Pola, których NIE ma w kluczu i które służą do niezależnej oceny dopasowania.
#: Jeśli para jest fałszywa, te pola się rozjadą — klucz ich nie wymusza.
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
    """Nazwa sprowadzona do rdzenia: bez formy prawnej, interpunkcji i spacji.

    Bez tego „Stigma sp.z o.o." i „Stigma Sp. z o.o." byłyby różnymi podmiotami,
    a publikujący zmienia zapis formy prawnej między edycjami.
    """
    return _NIEALFANUM.sub("", _FORMA_PRAWNA.sub("", _norm_txt(v)))


@dataclass
class LinkageAudit:
    """Ocena dopasowania par na polach WYŁĄCZONYCH z klucza.

    Nie jest to walidacja wobec prawdy zewnętrznej, bo takiej dla tego rejestru
    nie ma — jest to test wewnętrznej spójności: klucz nie wymusza zgodności
    tych pól, więc ich zgodność jest niezależnym świadectwem, że para dotyczy
    tego samego wniosku. Zgłaszamy obie granice, bo przypadki niepewne nie
    rozstrzygają się same.
    """

    par: int
    potwierdzonych: int
    niepewnych: int
    falszywych: int
    rozbieznosci: pd.DataFrame = field(repr=False)

    @property
    def precyzja_dolna(self) -> float:
        """Niepewne liczone jako błędne."""
        return self.potwierdzonych / self.par if self.par else float("nan")

    @property
    def precyzja_gorna(self) -> float:
        """Niepewne liczone jako trafne."""
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
    """Oceń dopasowanie kluczem treściowym na polach z klucza wyłączonych.

    Para jest klasyfikowana jako:

    * **fałszywa** — rdzeń nazwy podmiotu ORAZ rdzeń nazwy obiektu są rozbieżne
      i żaden nie zawiera się w drugim; to dwa różne wnioski, które przypadkiem
      dzielą lokalizację, napięcie, klasę i obie moce;
    * **niepewna** — rozbieżny jest dokładnie jeden z tych dwóch;
    * **potwierdzona** — oba zgodne albo nieobecne.

    Pola uzupełnione jednostronnie (puste w jednej edycji, wypełnione w drugiej)
    nie są liczone jako rozbieżność, bo publikujący uzupełnia rekordy między
    edycjami i jest to zmiana TEGO SAMEGO wniosku, nie świadectwo innego.
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
