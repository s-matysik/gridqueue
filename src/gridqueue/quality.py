"""Kontrola jakości zbioru: reguły z przepisu i z semantyki postępowania.

Każda reguła zwraca LICZBĘ NARUSZEŃ, nie wyjątek.  Naruszenie nie jest błędem
narzędzia -- jest własnością ujawnienia i właśnie po to ten moduł istnieje.
Raport jakości jest wynikiem naukowym: mówi, na ile publikacja ustawowa jest
wewnętrznie spójna.

Reguły:
  R1  monotonicznosc_dat        -- wniosek <= warunki <= umowa <= energizacja
  R2  waznosc_warunkow_2lata    -- warunki przyłączenia są ważne 2 lata
                                   (art. 7 ust. 8i); data utraty ważności nie może
                                   wypaść później niż 2 lata po ich określeniu
  R3  dopuszczalnosc_przejsc    -- status musi być zgodny z zestawem obecnych dat
  R4  spojnosc_jednostek_mocy   -- wartości mocy w kW muszą mieścić się w zakresie
                                   fizycznym przyłączeń >1 kV (wykrywa pomyłkę MW/kW)
  R5  zakresy_wartosci          -- moce nieujemne, daty w oknie 1990-2100
  R6  duplikaty_identyfikatorow -- ten sam id_wniosku w wielu wierszach
  R7  kompletnosc_rdzenia       -- 5 pól rdzenia niepustych
  R8  slownik_kontrolowany      -- klasa_zasobu i status_procesu ze słownika
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .schema import CORE_FIELDS, KLASY_ZASOBU, STATUSY, _is_null

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


def _plus_years(d: _dt.date, n: int) -> _dt.date:
    """Data przesunieta o n lat; 29 lutego w roku nieprzestepnym -> 28 lutego."""
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
    # wiersz liczony raz
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
    """Warunki przyłączenia są ważne dwa lata (art. 7 ust. 8i).

    Jeśli publikujący podaje datę utraty ważności, musi ona wypadać nie później
    niż dwa lata po dacie określenia warunków.  Sprawdzamy też umowy zawarte po
    upływie dwóch lat od warunków, które ich nie utraciły.
    """
    if "data_warunkow" not in df.columns:
        return 0, {"uwaga": "brak pola data_warunkow"}
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
        # Liczba MUSI byc policzona, nie wpisana. Wczesniej stala tu literalna
        # "334" -- akurat tyle wypadalo na panelu czterech publikujacych, ale
        # ten sam string wracal przy KAZDYM wywolaniu, takze per publikujacy
        # i na panelu szesciu, gdzie n_utr_bad ma inna wartosc. Diagnostyka
        # podawala wtedy liczbe niezgodna z wlasnym wynikiem reguly.
        det["interpretacja"] = (
            "systematyczne przesuniecie o stala liczbe dni wskazuje na regule "
            f"administracyjna publikujacego, a nie na {n_utr_bad} niezaleznych "
            "naruszen terminu"
        )
    return n_utr_bad + n_umowa_bad, det


#: jakie daty MUSZĄ / NIE MOGĄ istnieć przy danym statusie
_STATUS_WYMAGA: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    # status: (pola wymagane, pola zakazane)
    "WARUNKI_WYDANE": (("data_warunkow",), ("data_odmowy",)),
    "ODMOWA": (("data_odmowy",), ("data_umowy", "data_energizacji")),
    "UMOWA_OBOWIAZUJACA": (("data_umowy",), ("data_odmowy",)),
    "PRZYLACZONY": (("data_energizacji",), ("data_odmowy",)),
    "WNIOSEK_ZLOZONY": ((), ("data_umowy", "data_energizacji")),
    "W_TRAKCIE_ANALIZY": ((), ("data_umowy", "data_energizacji")),
    "WNIOSEK_NIEKOMPLETNY": ((), ("data_umowy", "data_energizacji")),
}


def r3_dopuszczalnosc_przejsc(df) -> tuple[int, dict]:
    """Status musi byc zgodny z zestawem obecnych dat.

    Wymog obecnosci daty stosujemy TYLKO do pol, ktore dany publikujacy w ogole
    ujawnia.  Brytyjski rejestr nie publikuje zadnych dat postepowania -- zadanie
    od niego "daty umowy" nie jest kontrola spojnosci, tylko bledem kategorii.
    Pola ujawniane wyznaczamy empirycznie: kolumna z co najmniej jedna wartoscia
    niepusta w obrebie publikujacego.
    """
    if "status_procesu" not in df.columns:
        return 0, {}
    date_cols = [c for c in ("data_wniosku", "data_warunkow", "data_odmowy",
                             "data_umowy", "data_energizacji") if c in df.columns]
    if "publikujacy" in df.columns:
        ujawniane = {}
        for pub, g in df.groupby("publikujacy"):
            ujawniane[pub] = {c for c in date_cols if g[c].map(lambda v: not _is_null(v)).any()}
    else:
        ujawniane = None
        globalne = {c for c in date_cols if df[c].map(lambda v: not _is_null(v)).any()}
    szczegoly: dict[str, int] = {}
    n_bad = 0
    for i in range(len(df)):
        st = df["status_procesu"].iloc[i]
        spec = _STATUS_WYMAGA.get(st)
        if not spec:
            continue
        dost = (ujawniane[df["publikujacy"].iloc[i]] if ujawniane is not None else globalne)
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


#: zakres fizyczny przyłączeń >1 kV w kW.  Dolny próg 1 kW odrzuca wartości,
#: które najpewniej podano w MW zamiast kW; górny 5 GW -- powyżej największej
#: pojedynczej jednostki wytwórczej w KSE.
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
    per = {}
    mask = [False] * len(df)
    for c in CORE_FIELDS:
        if c not in df.columns:
            per[c] = len(df)
            mask = [True] * len(df)
            continue
        cnt = 0
        for j, v in enumerate(df[c]):
            if _is_null(v):
                cnt += 1
                mask[j] = True
        if cnt:
            per[c] = cnt
    return sum(mask), {"per_pole": per}


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
    Rule("R1", "monotoniczność dat postępowania", "semantyka procesu (art. 7 ust. 8l pkt 1)",
         r1_monotonicznosc_dat),
    Rule("R2", "dwuletnia ważność warunków przyłączenia", "art. 7 ust. 8i",
         r2_waznosc_warunkow),
    Rule("R3", "dopuszczalność stanu procesu wobec dat", "semantyka procesu",
         r3_dopuszczalnosc_przejsc),
    Rule("R4", "spójność jednostek mocy", "art. 7 ust. 8l (sieć >1 kV)",
         r4_spojnosc_jednostek),
    Rule("R5", "zakresy wartości", "kontrola techniczna", r5_zakresy_wartosci),
    Rule("R6", "duplikaty identyfikatorów", "wymóg identyfikowalności pozycji",
         r6_duplikaty_identyfikatorow),
    Rule("R7", "kompletność rdzenia schematu", "art. 7 ust. 8l pkt 1/3/4",
         r7_kompletnosc_rdzenia),
    Rule("R8", "słownik kontrolowany", "harmonizacja międzyoperatorska",
         r8_slownik_kontrolowany),
)


def run_quality(df, rules: Optional[tuple[Rule, ...]] = None) -> QualityReport:
    out = []
    for rule in (rules or RULES):
        try:
            n, det = rule.fn(df)
        except Exception as exc:  # reguła nie może wywrócić raportu
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
