"""Wspólny szablon PTPiREE/PSE dla ujawnień z art. 7 ust. 8l pkt 1), 3) i 4).

Odkrycie, które to uzasadnia: arkusz PSE ``Informacje_publikowane_zgodnie_z_Art_7_
ust_8l_ustawy_PE`` ma zakładkę "Listy rozwijane", a w niej listę wartości pola
"OSD/OSP": Energa-Operator S.A., ENEA Operator Sp. z o.o., TAURON Dystrybucja S.A.,
PGE Dystrybucja S.A., Stoen Operator Sp. z o.o., PSE S.A.  Szablon nie jest więc
formularzem jednego przedsiębiorstwa, tylko UZGODNIONYM WZORCEM BRANŻOWYM dla
sześciu największych operatorów.  Publikacja Energa-Operatora (PDF) realizuje ten
sam wzorzec, co arkusz PSE (XLSX) -- różni się nośnikiem i dwiema kolumnami
brzegowymi, nie treścią.

Kolumny logiczne poniżej są tym wzorcem.  Adapter konkretnego publikującego ma
jedno zadanie: powiedzieć, która kolumna FIZYCZNA jego dokumentu odpowiada której
kolumnie logicznej.  Odwzorowanie na 21-polowy schemat jest wspólne, więc różnica
między publikującymi zostaje tam, gdzie jest naprawdę -- w układzie dokumentu.

Zmierzone układy fizyczne (odczytane z nagłówków, nie założone):

  PSE  (XLSX, 27 kolumn):  id_obiektu, nazwa_obiektu, osd_osp, podmiot, ...
  ENERGA (PDF, 28 kolumn): lp, id_obiektu, osd_osp, podmiot, ...,  uwagi

Od kolumny "osd_osp" obie numeracje się pokrywają: PSE ma z przodu dwie kolumny
tożsamości (ID + nazwa obiektu), Energa jedną (ID) poprzedzoną liczbą porządkową,
a na końcu dokłada kolumnę "UWAGI".
"""

from __future__ import annotations

import re
from typing import Any, Optional

from ..schema import canonical_date, canonical_power_kw
from .base import harmonize_klasa, harmonize_status

__all__ = ["LOGICAL", "PSE_XLSX_LAYOUT", "ENERGA_PDF_LAYOUT", "to_schema", "stan_na"]

#: kolumny logiczne wzorca PTPiREE/PSE
LOGICAL: tuple[str, ...] = (
    "lp",
    "id_obiektu",
    "nazwa_obiektu",
    "osd_osp",
    "podmiot",
    "lokalizacja",
    "poziom_napiecia",
    "wiele_miejsc",
    "rodzaj",
    "moc_wprowadzana",
    "moc_pobierana",
    "mz_pv",
    "mz_fw",
    "mz_mee_rozladowania",
    "mz_mee_ladowania",
    "mz_odb",
    "mz_inne",
    "status",
    "data_zlozenia",
    "data_zaliczki",
    "data_warunkow",
    "data_odmowy",
    "uzasadnienie_odmowy",
    "data_utraty_waznosci",
    "data_umowy",
    "data_energizacji",
    "data_rozwiazania_umowy",
    "data_wygasniecia_umowy",
    "uwagi",
)

#: fizyczny indeks kolumny -> kolumna logiczna.  Arkusz PSE, 27 kolumn.
PSE_XLSX_LAYOUT: dict[int, str] = {
    0: "id_obiektu", 1: "nazwa_obiektu", 2: "osd_osp", 3: "podmiot",
    4: "lokalizacja", 5: "poziom_napiecia", 6: "wiele_miejsc", 7: "rodzaj",
    8: "moc_wprowadzana", 9: "moc_pobierana",
    10: "mz_pv", 11: "mz_fw", 12: "mz_mee_rozladowania", 13: "mz_mee_ladowania",
    14: "mz_odb", 15: "mz_inne",
    16: "status", 17: "data_zlozenia", 18: "data_zaliczki", 19: "data_warunkow",
    20: "data_odmowy", 21: "uzasadnienie_odmowy", 22: "data_utraty_waznosci",
    23: "data_umowy", 24: "data_energizacji", 25: "data_rozwiazania_umowy",
    26: "data_wygasniecia_umowy",
}

#: fizyczny indeks kolumny -> kolumna logiczna.  PDF Energa-Operatora, 28 kolumn.
ENERGA_PDF_LAYOUT: dict[int, str] = {
    0: "lp", 1: "id_obiektu", 2: "osd_osp", 3: "podmiot",
    4: "lokalizacja", 5: "poziom_napiecia", 6: "wiele_miejsc", 7: "rodzaj",
    8: "moc_wprowadzana", 9: "moc_pobierana",
    10: "mz_pv", 11: "mz_fw", 12: "mz_mee_rozladowania", 13: "mz_mee_ladowania",
    14: "mz_odb", 15: "mz_inne",
    16: "status", 17: "data_zlozenia", 18: "data_zaliczki", 19: "data_warunkow",
    20: "data_odmowy", 21: "uzasadnienie_odmowy", 22: "data_utraty_waznosci",
    23: "data_umowy", 24: "data_energizacji", 25: "data_rozwiazania_umowy",
    26: "data_wygasniecia_umowy", 27: "uwagi",
}

#: pola opcjonalne schematu, które wzorzec wypełnia u KAŻDEGO publikującego
DECLARED_FIELDS: tuple[str, ...] = (
    "id_wniosku", "lokalizacja_tekst", "poziom_napiecia", "klasa_zasobu",
    "moc_wprowadzana", "moc_pobierana", "status_procesu", "data_wniosku",
    "data_warunkow", "data_odmowy", "powod_odmowy", "data_umowy",
    "data_energizacji", "data_publikacji",
)

#: rozszerzenia poza 21-polowym schematem, wspólne dla wzorca
DECLARED_EXTENSIONS: dict[str, str] = {
    "_podmiot": "nazwa podmiotu ubiegającego się o przyłączenie",
    "_osd_osp": "operator wskazany w dokumencie (pole wzorca)",
    "_nazwa_obiektu": "nazwa własna obiektu (tylko PSE)",
    "_wiele_miejsc": "czy wniosek dotyczy wielu miejsc przyłączenia / poziomów napięć",
    "_rodzaj_raw": "rodzaj instalacji tak, jak w dokumencie",
    "_status_raw": "status etapu projektu tak, jak w dokumencie",
    "_data_zaliczki": "data wpłaty zaliczki",
    "_data_utraty_waznosci": "data utraty ważności / rezygnacji z warunków",
    "_data_rozwiazania_umowy": "data rozwiązania/wypowiedzenia/odstąpienia od umowy",
    "_data_wygasniecia_umowy": "data wygaśnięcia umowy z mocy prawa",
    "_mz_pv": "moc zainstalowana PV [kW]",
    "_mz_fw": "moc zainstalowana FW [kW]",
    "_mz_mee_rozladowania": "moc zainstalowana magazynu -- rozładowanie [kW]",
    "_mz_mee_ladowania": "moc zainstalowana magazynu -- ładowanie [kW]",
    "_mz_odb": "moc zainstalowana odbioru [kW]",
    "_mz_inne": "moc zainstalowana pozostałych źródeł [kW]",
    "_uwagi": "kolumna UWAGI (tylko Energa)",
    "_lp_dokumentu": "liczba porządkowa w dokumencie źródłowym",
    "_encja": "WNIOSEK albo WEZEL -- którą encję obowiązku realizuje wiersz",
}

_NULLISH = {"", "-", "--", "---", "nan", "none", "brak", "nie dotyczy", "n/d"}


def _blank(v: Any) -> bool:
    """Czy wartość jest pusta.  ``nan`` jest prawdziwe, więc ``if v`` nie wystarcza."""
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    return isinstance(v, str) and not v.strip()


def _clean(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return None if s.lower() in _NULLISH else s


def _volt(v: Any) -> Optional[str]:
    """Poziom napięcia w postaci kanonicznej "<wartość> kV".

    Wzorzec dopuszcza WIELOKROTNOŚĆ ("110; 220; 400") -- tak stanowi lista
    rozwijana arkusza PSE.  Zapisujemy pełną treść, bo wybranie jednej wartości
    byłoby utratą danej; konsekwencją jest to, że detektor sprzeczności typu
    (``looks_like_voltage``) oznacza takie wiersze -- i tak ma być, bo miara
    ma pozostać PORÓWNYWALNA z wcześniejszymi pomiarami, a nie wygodna.

    Wartości KLASOWE ("SN", "nn", "WN") nie są liczbami kilowoltów i nie wolno
    dopisywać im jednostki: "SN kV" nie znaczy nic.  Panel czterech dotychczasowych
    publikujących zapisuje je jako samo "SN", więc trzymamy tę samą konwencję --
    inaczej ten sam poziom napięcia miałby dwie różne postaci w jednym panelu
    i pole przestałoby być porównywalne między publikującymi.
    """
    s = _clean(v)
    if s is None:
        return None
    if re.fullmatch(r"(?:nn|sn|wn|nN|SN|WN)", s.strip(), re.IGNORECASE):
        return s.strip().upper() if s.strip().lower() != "nn" else "nn"
    s = s.replace("\n", " ")
    s = re.sub(r"\s*kV\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s*;\s*", "; ", s)
    s = re.sub(r"\s+", " ", s).strip(" ;")
    if not s:
        return None
    # liczby całkowite bez ".0" po przejściu przez pandas/openpyxl
    s = re.sub(r"\b(\d+)\.0\b", r"\1", s)
    return f"{s} kV"


def stan_na(text: str) -> Optional[str]:
    """Data, na którą publikujący sporządził ujawnienie.

    Postać bywa różna nawet u jednego publikującego: "Stan na 30.06.2026 r."
    w zestawieniu wniosków i "(STAN NA DZIEŃ 31.08.2026 ROKU)" wersalikami na
    stronie tytułowej ujawnienia węzłowego -- stąd dopasowanie bez rozróżniania
    wielkości liter.
    """
    m = re.search(r"stan\s+na\s+(?:dzie[nń]\s+)?(\d{1,2}\.\d{1,2}\.\d{4})",
                  text or "", re.IGNORECASE)
    return canonical_date(m.group(1)) if m else None


def to_schema(raw, *, publisher_key: str, data_publikacji: Optional[str]):
    """Odwzoruj ramkę w kolumnach logicznych wzorca na 21-polowy schemat.

    ``raw`` ma kolumny z ``LOGICAL`` (brakujące mogą nie występować).  Jednostka
    mocy we wzorcu to MW -- sprowadzamy do kanonicznych kW.
    """
    import pandas as pd

    def col(name: str):
        if name in raw.columns:
            return raw[name].map(_clean)
        return pd.Series([None] * len(raw), index=raw.index, dtype="object")

    def mw(name: str):
        return col(name).map(lambda v: canonical_power_kw(v, "MW"))

    def dcol(name: str):
        """Data z kolumny SUROWEJ, bez przejścia przez ``_clean``.

        Pułapka, która kosztowała wszystkie daty PSE: nośnikiem PSE jest XLSX,
        a openpyxl zwraca komórki daty jako ``Timestamp``.  ``_clean`` robi na
        wartości ``str()``, więc Timestamp zamieniał się w "2023-08-07 00:00:00",
        a ``canonical_date`` ma wzorce ZAKOTWICZONE i takiego łańcucha nie
        dopasowuje -- zwracał None.  Efekt: pola ``data_*`` pustoszały dla całego
        publikującego, a reguły jakości R1 i R2 (monotoniczność dat, dwuletnia
        ważność warunków) nie miały na czym pracować i pokazywały zero naruszeń.
        ``canonical_date`` sam obsługuje ``datetime``/``date``, więc wystarczy
        podać mu wartość nietkniętą.
        """
        if name not in raw.columns:
            return pd.Series([None] * len(raw), index=raw.index, dtype="object")
        return raw[name].map(lambda v: None if _blank(v) else canonical_date(v))

    out = pd.DataFrame(index=raw.index)
    ident = col("id_obiektu")
    lp = col("lp")
    # Uwaga na pułapkę: ``Series.map`` zamienia zwrócone ``None`` na ``nan``,
    # a ``nan`` jest w Pythonie PRAWDZIWE.  Test pustości musi być jawny, inaczej
    # zastępnik identyfikatora nigdy się nie uruchomi, a 866 z 876 wierszy PSE
    # (te z "-" w polu ID Obiektu) zostaje bez identyfikatora.
    out["id_wniosku"] = [
        i if not _blank(i)
        else f"{publisher_key}:poz:{(str(l).rstrip('.') if not _blank(l) else str(k + 1))}"
        for k, (i, l) in enumerate(zip(ident, lp))
    ]
    out["lokalizacja_tekst"] = col("lokalizacja")
    out["poziom_napiecia"] = col("poziom_napiecia").map(_volt)
    out["klasa_zasobu"] = col("rodzaj").map(harmonize_klasa)
    out["moc_wprowadzana"] = mw("moc_wprowadzana")
    out["moc_pobierana"] = mw("moc_pobierana")
    out["status_procesu"] = col("status").map(harmonize_status)
    out["data_wniosku"] = dcol("data_zlozenia")
    out["data_warunkow"] = dcol("data_warunkow")
    out["data_odmowy"] = dcol("data_odmowy")
    out["powod_odmowy"] = col("uzasadnienie_odmowy")
    out["data_umowy"] = dcol("data_umowy")
    # Energa zapisuje planowaną energizację NIERÓWNOŚCIĄ ("po 30.06.2026"), a nie
    # datą.  ``canonical_date`` jest zakotwiczony na początku łańcucha, więc słusznie
    # zwraca None -- zapisanie 2026-06-30 gubiłoby słowo "po" i zamieniało termin
    # dolny na termin dokładny.  Żeby jednak nie utracić danej, surowy tekst idzie
    # do rozszerzenia, a pole schematu zostaje puste.
    _energ = col("data_energizacji")
    out["data_energizacji"] = dcol("data_energizacji")
    out["_energizacja_tekst"] = [
        t if (not _blank(t) and canonical_date(t) is None) else None for t in _energ
    ]
    out["data_publikacji"] = data_publikacji

    out["_encja"] = "WNIOSEK"
    out["_podmiot"] = col("podmiot")
    out["_osd_osp"] = col("osd_osp")
    out["_nazwa_obiektu"] = col("nazwa_obiektu")
    out["_wiele_miejsc"] = col("wiele_miejsc")
    out["_rodzaj_raw"] = col("rodzaj")
    out["_status_raw"] = col("status")
    out["_data_zaliczki"] = dcol("data_zaliczki")
    out["_data_utraty_waznosci"] = dcol("data_utraty_waznosci")
    out["_data_rozwiazania_umowy"] = dcol("data_rozwiazania_umowy")
    out["_data_wygasniecia_umowy"] = dcol("data_wygasniecia_umowy")
    for src, dst in (("mz_pv", "_mz_pv"), ("mz_fw", "_mz_fw"),
                     ("mz_mee_rozladowania", "_mz_mee_rozladowania"),
                     ("mz_mee_ladowania", "_mz_mee_ladowania"),
                     ("mz_odb", "_mz_odb"), ("mz_inne", "_mz_inne")):
        out[dst] = mw(src)
    out["_uwagi"] = col("uwagi")
    out["_lp_dokumentu"] = lp
    return out
