"""Wspólny schemat ujawnień przyłączeniowych (statutory connection-queue disclosure).

Schemat jest wyprowadzony ze STRUKTURY OBOWIĄZKU PRAWNEGO, nie z układu konkretnego
dokumentu.  Art. 7 ust. 8l ustawy z dnia 10 kwietnia 1997 r. -- Prawo energetyczne
nakłada na operatora systemu dystrybucyjnego cztery rozłączne obowiązki ujawnieniowe:

  pkt 1  -- podmioty ubiegające się o przyłączenie źródeł (kto, gdzie, jaka moc,
            jaki zasób, na jakim etapie)                     -> encja WNIOSEK
  pkt 2  -- łączna dostępna moc przyłączeniowa i jej planowane zmiany w okresie
            kolejnych 5 lat, w podziale na stacje lub ich grupy
                                                             -> encja WĘZEŁ
  pkt 3  -- złożone wnioski o określenie warunków przyłączenia -> encja WNIOSEK
  pkt 4  -- wydane odmowy określenia warunków przyłączenia     -> encja WNIOSEK

Z tego wynikają trzy osie, które schemat odwzorowuje jako grupy pól:

  TOŻSAMOŚĆ  -- co jest przyłączane i gdzie (id_wniosku, id_wezla, nazwa_wezla,
                lokalizacja_tekst, wspolrzedne, poziom_napiecia, klasa_zasobu)
  MOC        -- ile mocy w którą stronę i ile jej jeszcze jest
                (moc_wprowadzana, moc_pobierana, moc_dostepna, moc_zarezerwowana,
                 ograniczenie_flaga, pozycja_w_kolejce)
  PROCES     -- gdzie w postępowaniu administracyjnym stoi sprawa
                (status_procesu, data_wniosku, data_warunkow, data_odmowy,
                 powod_odmowy, data_umowy, data_energizacji, data_publikacji)

Oś PROCES jest bezpośrednim odwzorowaniem ścieżki proceduralnej ustawy: wniosek ->
(zaliczka) -> warunki przyłączenia albo odmowa -> umowa o przyłączenie ->
rozpoczęcie dostarczania energii.  Warunki przyłączenia są ważne dwa lata
(art. 7 ust. 8i), co czyni parę (data_warunkow, data_umowy) sprawdzalną regułą,
a nie tylko dwiema kolumnami.

RDZEŃ OBOWIĄZKOWY (5 pól) to minimum, bez którego ujawnienie nie realizuje
żadnego z pkt 1/3/4: nie da się powiedzieć, czyj to wniosek, gdzie, na co,
o jaką moc i na jakim etapie.

Jednostki kanoniczne: moc w kW (nie MW -- publikujący używają obu), daty w ISO
8601 (YYYY-MM-DD), współrzędne w WGS84 jako (lat, lon).
"""

from __future__ import annotations

import datetime as _dt
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

__all__ = [
    "Field",
    "SCHEMA",
    "FIELDS",
    "CORE_FIELDS",
    "OPTIONAL_FIELDS",
    "GROUPS",
    "canonical_power_kw",
    "canonical_date",
    "validate_instance",
    "validate_frame",
    "empty_frame",
]

# --------------------------------------------------------------------------
# normalizacja jednostek kanonicznych
# --------------------------------------------------------------------------

_NUM_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def canonical_power_kw(value: Any, unit: str = "kW") -> Optional[float]:
    """Sprowadź moc do kW.  Zwraca None dla pustych/nieparsowalnych wartości.

    Akceptuje polski separator dziesiętny (przecinek) i spacje tysięczne
    (także NBSP i wąską spację, których używają generatory PDF).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        num = float(value)
    else:
        s = str(value).strip()
        s = s.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
        if s in {"", "-", "--", "---", "brak", "nie dotyczy", "n/d", "N/D"}:
            return None
        s = s.replace(",", ".")
        # dopuść wielokrotne kropki tysięczne typu 1.234.5 -> odrzuć
        if not _NUM_RE.match(s.replace(".", "", max(0, s.count(".") - 1))):
            try:
                num = float(s)
            except ValueError:
                return None
        else:
            try:
                num = float(s)
            except ValueError:
                return None
    u = unit.strip().lower()
    if u in {"kw", "kilowat", "kilowatt"}:
        return num
    if u in {"mw", "megawat", "megawatt"}:
        return num * 1000.0
    if u in {"w", "wat", "watt"}:
        return num / 1000.0
    raise ValueError(f"nieznana jednostka mocy: {unit!r}")


# Publikujacy nie trzymaja sie wlasnego wzorca [dd.mm.rrrr]: w zestawieniu wnioskow
# Stoena wystepuja daty z jednocyfrowym dniem ("2.04.2026"), wiec wzorzec musi je
# przyjmowac -- inaczej poprawnie wydobyta data przepada na normalizacji.
_DATE_PATTERNS = (
    ("%d.%m.%Y", re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")),
    ("%Y-%m-%d", re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")),
    ("%d/%m/%Y", re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")),
    ("%d-%m-%Y", re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$")),
)

_NULLISH = {
    "", "-", "--", "---", "----", "-----", "brak", "nie dotyczy", "nie wymagano",
    "n/d", "none", "nan", "--------", "---------", "----------",
    "-----------", "------------", "-------------", "--------------",
    "---------------",
}


def canonical_date(value: Any) -> Optional[str]:
    """Sprowadź datę do ISO 8601 (YYYY-MM-DD).  None dla pustych/nieparsowalnych."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date().isoformat()
    if isinstance(value, _dt.date):
        return value.isoformat()
    s = str(value).strip()
    if s.lower() in _NULLISH or set(s) == {"-"}:
        return None
    s = s.replace("r.", "").strip()
    for fmt, rx in _DATE_PATTERNS:
        if rx.match(s):
            try:
                return _dt.datetime.strptime(s, fmt).date().isoformat()
            except ValueError:
                return None
    return None


def _is_null(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and math.isnan(v):
        return True
    if isinstance(v, str) and v.strip().lower() in _NULLISH:
        return True
    return False


# --------------------------------------------------------------------------
# specyfikacja pól
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Field:
    name: str
    dtype: str                 # "string" | "number" | "date" | "boolean" | "geopoint"
    group: str                 # "tozsamosc" | "moc" | "proces"
    core: bool
    unit: Optional[str]
    podstawa: str              # który punkt art. 7 ust. 8l uzasadnia pole
    opis: str
    check: Optional[Callable[[Any], bool]] = field(default=None, repr=False)


def _num_nonneg(v: Any) -> bool:
    try:
        return float(v) >= 0.0
    except (TypeError, ValueError):
        return False


def _is_iso_date(v: Any) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", str(v))) and canonical_date(v) is not None


def _is_geopoint(v: Any) -> bool:
    if isinstance(v, (tuple, list)) and len(v) == 2:
        lat, lon = v
    elif isinstance(v, str) and "," in v:
        try:
            lat, lon = (float(x) for x in v.split(",", 1))
        except ValueError:
            return False
    else:
        return False
    try:
        return -90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0
    except (TypeError, ValueError):
        return False


def _is_bool(v: Any) -> bool:
    return isinstance(v, bool) or str(v).strip().lower() in {
        "true", "false", "tak", "nie", "0", "1"
    }


SCHEMA: tuple[Field, ...] = (
    # ---------------- TOŻSAMOŚĆ ----------------
    Field("id_wniosku", "string", "tozsamosc", True, None, "pkt 1/3/4",
          "Identyfikator pozycji w rejestrze publikującego; unikalny w obrębie "
          "publikacji, nie globalnie."),
    Field("id_wezla", "string", "tozsamosc", False, None, "pkt 2",
          "Identyfikator stacji elektroenergetycznej lub jej grupy, w podziale na "
          "które ustawa każe podawać dostępną moc."),
    Field("nazwa_wezla", "string", "tozsamosc", False, None, "pkt 2",
          "Nazwa własna stacji/punktu zasilania, jeśli publikujący ją ujawnia."),
    Field("lokalizacja_tekst", "string", "tozsamosc", True, None, "pkt 1/3/4",
          "Lokalizacja miejsca przyłączenia tak, jak ją podał publikujący "
          "(adres, miejscowość, kod stacji) -- bez interpretacji."),
    Field("wspolrzedne", "geopoint", "tozsamosc", False, "WGS84", "pkt 1/2",
          "Współrzędne geograficzne (lat, lon); wynik rozwiązania lokalizacji albo "
          "dana źródłowa.", _is_geopoint),
    Field("poziom_napiecia", "string", "tozsamosc", False, None, "pkt 1 (>1 kV)",
          "Poziom napięcia przyłączenia; obowiązek dotyczy sieci powyżej 1 kV, więc "
          "pole rozstrzyga o zakresie ujawnienia."),
    Field("klasa_zasobu", "string", "tozsamosc", True, None, "pkt 1/3/4",
          "Rodzaj instalacji, urządzeń lub sieci, zharmonizowany do słownika "
          "kontrolowanego (PV, FW, BESS, ODB, ...)."),
    # ---------------- MOC ----------------
    Field("moc_wprowadzana", "number", "moc", False, "kW", "pkt 1/3",
          "Moc przyłączeniowa wprowadzana do sieci (generacja/eksport).", _num_nonneg),
    Field("moc_pobierana", "number", "moc", True, "kW", "pkt 1/3/4",
          "Moc przyłączeniowa pobierana z sieci (odbiór/import); dla wniosków "
          "odbiorczych jest to główna wielkość wniosku.", _num_nonneg),
    Field("moc_dostepna", "number", "moc", False, "kW", "pkt 2",
          "Łączna dostępna moc przyłączeniowa w węźle.", _num_nonneg),
    Field("moc_zarezerwowana", "number", "moc", False, "kW", "pkt 2",
          "Moc zajęta wydanymi i ważnymi warunkami / rezerwą.", _num_nonneg),
    Field("ograniczenie_flaga", "boolean", "moc", False, None, "pkt 2",
          "Czy w węźle występuje czynnik ograniczający przyłączenie.", _is_bool),
    Field("pozycja_w_kolejce", "number", "moc", False, None, "pkt 1",
          "Pozycja wniosku w kolejce przyłączeniowej, jeśli publikujący ją prowadzi."),
    # ---------------- PROCES ----------------
    Field("status_procesu", "string", "proces", True, None, "pkt 1/3/4",
          "Etap postępowania, zharmonizowany do słownika kontrolowanego."),
    Field("data_wniosku", "date", "proces", False, "ISO-8601", "pkt 3",
          "Data złożenia wniosku o określenie warunków przyłączenia.", _is_iso_date),
    Field("data_warunkow", "date", "proces", False, "ISO-8601", "pkt 1/3",
          "Data określenia warunków przyłączenia; początek dwuletniego terminu "
          "ważności (art. 7 ust. 8i).", _is_iso_date),
    Field("data_odmowy", "date", "proces", False, "ISO-8601", "pkt 4",
          "Data wydania odmowy określenia warunków przyłączenia.", _is_iso_date),
    Field("powod_odmowy", "string", "proces", False, None, "pkt 4",
          "Uzasadnienie odmowy (przyczyny techniczne / ekonomiczne / inne)."),
    Field("data_umowy", "date", "proces", False, "ISO-8601", "pkt 1",
          "Data zawarcia umowy o przyłączenie.", _is_iso_date),
    Field("data_energizacji", "date", "proces", False, "ISO-8601", "pkt 1",
          "Data rozpoczęcia dostarczania energii elektrycznej.", _is_iso_date),
    Field("data_publikacji", "date", "proces", False, "ISO-8601", "art. 7 ust. 8m",
          "Stan na dzień, dla którego publikujący sporządził ujawnienie; "
          "ustawa wymaga aktualizacji co najmniej raz na kwartał.", _is_iso_date),
)

FIELDS: tuple[str, ...] = tuple(f.name for f in SCHEMA)
CORE_FIELDS: tuple[str, ...] = tuple(f.name for f in SCHEMA if f.core)
OPTIONAL_FIELDS: tuple[str, ...] = tuple(f.name for f in SCHEMA if not f.core)
BY_NAME: dict[str, Field] = {f.name: f for f in SCHEMA}
GROUPS: dict[str, tuple[str, ...]] = {
    g: tuple(f.name for f in SCHEMA if f.group == g)
    for g in ("tozsamosc", "moc", "proces")
}

# kolumny towarzyszące, nie należące do schematu (metadane panelu / anotacje)
META_COLUMNS: tuple[str, ...] = ("publikujacy", "jurysdykcja", "dokument_zrodlowy")
ANNOTATION_PREFIX = "_"

# słowniki kontrolowane
KLASY_ZASOBU = (
    "PV", "FW", "EW", "BIOGAZ", "GAZ", "WEGIEL", "BESS", "ODB", "MIX", "SIEC",
    "INNE", "NIEOKRESLONA",
)
STATUSY = (
    "WNIOSEK_ZLOZONY", "WNIOSEK_NIEKOMPLETNY", "W_TRAKCIE_ANALIZY",
    "WARUNKI_WYDANE", "WARUNKI_WYGASLE", "ODMOWA", "UMOWA_OBOWIAZUJACA",
    "UMOWA_ROZWIAZANA", "PRZYLACZONY", "WNIOSEK_WYCOFANY", "NIEOKRESLONY",
)


# --------------------------------------------------------------------------
# walidator instancji
# --------------------------------------------------------------------------


def validate_instance(row: dict[str, Any], *, strict_vocab: bool = False) -> list[str]:
    """Zwróć listę komunikatów o naruszeniach dla pojedynczego wiersza.

    Pusta lista = wiersz zgodny ze schematem.  Walidator NIE rzuca wyjątku --
    ujawnienia bywają niekompletne z winy publikującego i to jest wynik pomiaru,
    a nie błąd wykonania.
    """
    problems: list[str] = []
    unknown = set(row) - set(FIELDS) - set(META_COLUMNS)
    unknown = {k for k in unknown if not k.startswith(ANNOTATION_PREFIX)}
    if unknown:
        problems.append(f"pola spoza schematu: {sorted(unknown)}")
    for name in CORE_FIELDS:
        if name not in row or _is_null(row.get(name)):
            problems.append(f"brak pola rdzenia: {name}")
    for name, value in row.items():
        f = BY_NAME.get(name)
        if f is None or _is_null(value):
            continue
        if f.dtype == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                problems.append(f"{name}: oczekiwano liczby, jest {type(value).__name__}")
                continue
        if f.check is not None and not f.check(value):
            problems.append(f"{name}: wartość nie przechodzi kontroli typu ({value!r})")
    if strict_vocab:
        kz = row.get("klasa_zasobu")
        if not _is_null(kz) and kz not in KLASY_ZASOBU:
            problems.append(f"klasa_zasobu spoza słownika: {kz!r}")
        st = row.get("status_procesu")
        if not _is_null(st) and st not in STATUSY:
            problems.append(f"status_procesu spoza słownika: {st!r}")
    return problems


def validate_frame(df, *, strict_vocab: bool = True) -> dict[str, Any]:
    """Walidacja całej ramki.  Zwraca raport (liczby), nie wyjątek."""
    import pandas as pd  # lokalny import: schema.py ma być użyteczny bez pandas

    report: dict[str, Any] = {
        "n_wierszy": int(len(df)),
        "kolumny_spoza_schematu": sorted(
            set(df.columns) - set(FIELDS) - set(META_COLUMNS)
            - {c for c in df.columns if c.startswith(ANNOTATION_PREFIX)}
        ),
        "brakujace_kolumny_rdzenia": [c for c in CORE_FIELDS if c not in df.columns],
        "wypelnienie": {},
        "naruszenia_typu": {},
        "wiersze_z_kompletnym_rdzeniem": 0,
        "slownik": {},
    }
    for c in FIELDS:
        if c in df.columns:
            s = df[c]
            nn = int(s.notna().sum() - sum(
                1 for v in s.dropna() if isinstance(v, str) and v.strip().lower() in _NULLISH
            ))
            report["wypelnienie"][c] = round(nn / len(df), 6) if len(df) else 0.0
        else:
            report["wypelnienie"][c] = 0.0
    for c in FIELDS:
        if c not in df.columns:
            continue
        f = BY_NAME[c]
        bad = 0
        for v in df[c]:
            if _is_null(v):
                continue
            if f.dtype == "number" and (not isinstance(v, (int, float)) or isinstance(v, bool)):
                bad += 1
            elif f.check is not None and not f.check(v):
                bad += 1
        if bad:
            report["naruszenia_typu"][c] = bad
    core_present = [c for c in CORE_FIELDS if c in df.columns]
    if core_present:
        mask = pd.Series(True, index=df.index)
        for c in core_present:
            mask &= df[c].map(lambda v: not _is_null(v))
        report["wiersze_z_kompletnym_rdzeniem"] = int(mask.sum())
    if strict_vocab:
        for c, vocab in (("klasa_zasobu", KLASY_ZASOBU), ("status_procesu", STATUSY)):
            if c in df.columns:
                bad = sorted({v for v in df[c].dropna().unique() if v not in vocab and not _is_null(v)})
                report["slownik"][c] = bad
    return report


def empty_frame():
    """Pusta ramka w schemacie (wszystkie 21 pól + kolumny metadanych)."""
    import pandas as pd

    return pd.DataFrame({c: pd.Series(dtype="object") for c in FIELDS + META_COLUMNS})


def schema_table():
    """Specyfikacja jako ramka -- artefakt do manuskryptu."""
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "pole": f.name,
                "typ": f.dtype,
                "grupa": f.group,
                "rdzen": f.core,
                "jednostka_kanoniczna": f.unit or "",
                "podstawa_prawna": f.podstawa,
                "opis": f.opis,
            }
            for f in SCHEMA
        ]
    )
