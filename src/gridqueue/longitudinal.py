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
    )
