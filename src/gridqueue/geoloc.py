"""Rozwiązywacz lokalizacji z JAWNYM poziomem pewności.

Reguła nadrzędna: rozwiązywacz nigdy nie zgaduje po cichu.  Każdy wynik niesie
poziom pewności, a odsetek rozwiązanych jest raportowaną metryką, nie założeniem.

Poziomy pewności (malejąco):
  EXACT        -- znormalizowany opis jest identyczny z nazwą w gazeterze
  UNIQUE_TOKEN -- dokładnie jedna nazwa w gazeterze zawiera rozpoznawalny token
                  wyróżniający z opisu
  TOKEN_SUBSET -- zbiór tokenów opisu zawiera się w tokenach dokładnie jednej nazwy
  REVERSED     -- dopasowanie po odwróceniu kolejności członów nazwy
                  ("WINCENTEGO ŚW." -> "Świętego Wincentego", "BEMA J." -> "Józefa Bema")
  SKRZYZOWANIE -- opis wskazuje skrzyżowanie dwóch ulic ("WALICÓW / GRZYBOWSKA");
                  rozwiązane, gdy co najmniej dwa człony trafiają w gazeter
  NONE         -- brak dopasowania; pole ``powod`` mówi dlaczego

Dla publikujących, którzy podają lokalizację jako WEWNĘTRZNY KOD STACJI
(TAURON: "SKB3", "RCB4"), rozwiązywacz zwraca NONE z powodem
``kod_stacji_bez_slownika`` -- nie próbuje zgadywać, bo operator nie publikuje
słownika kodów i każde dopasowanie byłoby konfabulacją.

Rozszerzenie o współrzędne (wersja 0.2)
---------------------------------------
Wynik niesie teraz punkt oraz DRUGI, niezależny poziom -- ``dokladnosc``
(patrz :data:`DOKLADNOSC`).  Dwa poziomy odpowiadają na dwa różne pytania:

  ``pewnosc``    -- jak pewna jest IDENTYFIKACJA nazwy miejsca,
  ``dokladnosc`` -- jak precyzyjnie zwrócony punkt reprezentuje to miejsce.

Są rozłączne z założenia: dopasowanie EXACT do ulicy o długości 6 km daje punkt
o dokładności ``PUNKT_NA_OSI_ULICY`` z rozmyciem rzędu kilometra, a dopasowanie
UNIQUE_TOKEN do krótkiej ulicy -- punkt lepszy.  Długość osi dopasowanej ulicy
jest zwracana w ``dlugosc_ulicy_m`` właśnie po to, by rozmycie dało się
policzyć, a nie tylko zadeklarować.

Zachowane jest rozróżnienie między **nierozwiązaniem nazwy**
(``pewnosc == "NONE"``) a **rozwiązaniem nazwy bez dostępnej geometrii**
(``pewnosc != "NONE"``, ``dokladnosc == "BRAK_GEOMETRII"``,
``powod == "nazwa_rozwiazana_bez_geometrii"``) -- to dwa różne stany wiedzy
i mieszanie ich zawyżałoby albo zaniżałoby pokrycie.  Predykaty:
``Resolution.rozwiazane`` (nazwa) i ``Resolution.ma_wspolrzedne`` (punkt).

Numer domu nie jest interpolowany wzdłuż osi ulicy bez znanego zakresu
numeracji -- byłoby to zgadywanie.  ``punkt_dla_numeru`` zwraca punkt wyłącznie
z indeksu punktów adresowych, jeśli taki jest wczytany.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

__all__ = [
    "Resolution", "LocationResolver", "MultiLocalityResolver",
    "PEWNOSC", "DOKLADNOSC", "normalize", "tokens",
    "resolver_from_osm_json", "resolver_from_gazeter_json",
]

PEWNOSC = ("EXACT", "UNIQUE_TOKEN", "TOKEN_SUBSET", "REVERSED", "SKRZYZOWANIE", "NONE")

#: Poziom DOKLADNOSCI UMIEJSCOWIENIA -- odpowiada na inne pytanie niz ``pewnosc``.
#: ``pewnosc`` mowi, jak pewna jest IDENTYFIKACJA nazwy; ``dokladnosc`` mowi,
#: jak precyzyjnie zwrocony punkt reprezentuje wskazane miejsce.  Rozdzielenie
#: jest konieczne, bo nazwa moze byc zidentyfikowana bezblednie (EXACT), a punkt
#: i tak byc tylko srodkiem kilkukilometrowej ulicy.
#:
#:   PUNKT_ADRESOWY        -- znany punkt adresowy (ulica + numer domu)
#:   PUNKT_SKRZYZOWANIA    -- przeciecie osi dwoch wskazanych ulic
#:   PUNKT_NA_OSI_ULICY    -- punkt w 50% dlugosci osi ulicy (niepewnosc ~ dlugosc/4)
#:   CENTROID_MIEJSCOWOSCI -- rozwiazano tylko miejscowosc, nie ulice
#:   BRAK_GEOMETRII        -- nazwa ROZWIAZANA, ale gazeter nie ma dla niej wspolrzednych
#:   BRAK                  -- nazwa nierozwiazana, wiec nie ma czego umiejscawiac
DOKLADNOSC = (
    "PUNKT_ADRESOWY", "PUNKT_SKRZYZOWANIA", "PUNKT_NA_OSI_ULICY",
    "CENTROID_MIEJSCOWOSCI", "BRAK_GEOMETRII", "BRAK",
)

#: przedrostki i człony, które nie wyróżniają ulicy
_STOP = {
    "ul", "ulica", "al", "aleja", "aleje", "pl", "plac", "os", "osiedle", "rondo",
    "sw", "swietego", "swietej", "im", "imienia", "gen", "generala", "gen.",
    "ks", "ksiedza", "dr", "prof", "mjr", "plk", "kpt", "por", "mjra", "marsz",
    "marszalka", "bp", "biskupa", "kard", "kardynala", "droga", "trakt", "skwer",
    "bulwar", "park", "most", "wybrzeze", "brak", "dzialka", "nr", "dz", "obreb",
}

#: kod stacji: 2-6 znaków wielkich liter/cyfr bez spacji, albo opis projektowanej stacji
_RE_STATION_CODE = re.compile(r"^[A-ZĄĆĘŁŃÓŚŻŹ]{2,5}\d{0,2}$")


_STROKE = str.maketrans({"ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ø": "o", "Ø": "O"})


def strip_diacritics(s: str) -> str:
    s = str(s).translate(_STROKE)
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    s = strip_diacritics(str(s)).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: Optional[str], *, drop_stop: bool = True) -> list[str]:
    t = [w for w in normalize(s).split() if w]
    if drop_stop:
        t = [w for w in t if w not in _STOP and not w.isdigit()]
    return t


@dataclass
class Resolution:
    query: str
    matched: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    pewnosc: str
    powod: str = ""
    #: poziom dokladnosci umiejscowienia -- patrz DOKLADNOSC
    dokladnosc: str = "BRAK"
    #: miejscowosc, w ktorej gazeterze szukano (None dla gazetera jednoobszarowego)
    miejscowosc: Optional[str] = None
    #: dlugosc osi dopasowanej ulicy w metrach, jesli gazeter ja niesie;
    #: jest to jawna miara rozmycia punktu PUNKT_NA_OSI_ULICY
    dlugosc_ulicy_m: Optional[float] = None
    #: liczba ROZLACZNYCH skladowych geometrii o tej nazwie w tej miejscowosci
    n_skladowych: Optional[int] = None
    #: najwieksza odleglosc miedzy centroidami tych skladowych [m].  Duza
    #: wartosc oznacza, ze nazwa ulicy NIE wyznacza jednego miejsca: w jednym
    #: miescie istnieje kilka odleglych ulic o tej samej nazwie, a punkt lezy
    #: na najdluzszej skladowej.  Rejestry ustawowe nie podaja dzielnicy, wiec
    #: tej niejednoznacznosci nie da sie usunac z danych opublikowanych --
    #: dlatego jest RAPORTOWANA, nie ukrywana.
    rozrzut_skladowych_m: Optional[float] = None

    @property
    def rozwiazane(self) -> bool:
        """Czy NAZWA zostala zidentyfikowana (niezaleznie od dostepnosci geometrii)."""
        return self.pewnosc != "NONE"

    @property
    def ma_wspolrzedne(self) -> bool:
        """Czy wynik niesie punkt.  Rozlaczne z ``rozwiazane``: nazwa moze byc
        rozwiazana, a geometrii moze nie byc (``dokladnosc == BRAK_GEOMETRII``)."""
        return self.lat is not None and self.lon is not None


class LocationResolver:
    """Dopasowanie opisu miejsca do gazetera nazw ulic/miejsc.

    ``gazetteer``: mapa nazwa -> (lat, lon) albo nazwa -> None (gdy współrzędnych
    nie ma, a interesuje nas samo rozstrzygnięcie identyfikacji).
    """

    def __init__(self, gazetteer: dict[str, Optional[tuple[float, float]]]):
        self.gazetteer = dict(gazetteer)
        self._by_norm: dict[str, list[str]] = defaultdict(list)
        self._by_tokenset: dict[frozenset, list[str]] = defaultdict(list)
        self._by_token: dict[str, list[str]] = defaultdict(list)
        for name in self.gazetteer:
            n = normalize(name)
            self._by_norm[n].append(name)
            ts = frozenset(tokens(name))
            if ts:
                self._by_tokenset[ts].append(name)
                for t in ts:
                    self._by_token[t].append(name)

    # ------------------------------------------------------------------
    def _coords(self, name: str) -> tuple[Optional[float], Optional[float]]:
        """Wspolrzedne wpisu gazetera.

        Obslugiwane postacie wpisu (zgodnosc wstecz zachowana):
          ``None``                  -- brak geometrii
          ``(lat, lon)``            -- goly punkt
          ``{"lat":..,"lon":..}``   -- wpis rozszerzony, moze dodatkowo niesc
                                       ``os`` (lista [lat, lon]) i ``dlugosc_m``
        """
        c = self.gazetteer.get(name)
        if isinstance(c, dict):
            lat, lon = c.get("lat"), c.get("lon")
            if lat is not None and lon is not None:
                return float(lat), float(lon)
            return None, None
        if isinstance(c, (tuple, list)) and len(c) == 2:
            return float(c[0]), float(c[1])
        return None, None

    def _meta(self, name: str) -> dict:
        c = self.gazetteer.get(name)
        return c if isinstance(c, dict) else {}

    def axis(self, name: str) -> Optional[list[tuple[float, float]]]:
        """Os ulicy jako lista (lat, lon), jesli gazeter ja niesie."""
        os_ = self._meta(name).get("os")
        if not os_ or len(os_) < 2:
            return None
        return [(float(p[0]), float(p[1])) for p in os_]

    #: prog udzialu wyjasnionych tokenow opisu; ponizej progu dopasowanie
    #: nie-EXACT jest odrzucane jako opis slowny, nie nazwa ulicy
    PROG_POKRYCIA_TOKENOW = 0.5
    #: od tylu tokenow opisu prog jest stosowany (krotkie opisy sa nazwami ulic)
    MIN_TOKENOW_DLA_PROGU = 4

    def _udzial_wyjasnionych(self, ts: list[str], name: str) -> float:
        """Jaka czesc tokenow opisu wyjasnia dopasowana nazwa.

        Token uchodzi za wyjasniony, gdy jest rowny tokenowi nazwy albo jest
        jego przedrostkiem (obsluga inicjalow: "a." -> "augusta").
        """
        if not ts:
            return 0.0
        nt = tokens(name)
        ile = sum(1 for t in ts if any(t == x or x.startswith(t) for x in nt))
        return ile / len(ts)

    def _opis_slowny(self, ts: list[str], name: str) -> bool:
        """Czy dopasowanie opiera sie na jednym tokenie dlugiego opisu slownego.

        Zmierzone na panelu: opis "Bezposrednie sasiedztwo Lotniska Chopina w
        Warszawie" trafial w ulice "Fryderyka Chopina" przez sam token
        "chopina", dajac punkt w srodmiesciu zamiast przy lotnisku.  Dopasowanie
        wyjasniajace mniej niz polowe tokenow dlugiego opisu nie jest
        identyfikacja ulicy i jest odrzucane z jawnym powodem.
        """
        if len(ts) < self.MIN_TOKENOW_DLA_PROGU:
            return False
        return self._udzial_wyjasnionych(ts, name) < self.PROG_POKRYCIA_TOKENOW

    def _hit(self, query: str, name: str, level: str,
             miejscowosc: Optional[str] = None) -> Resolution:
        lat, lon = self._coords(name)
        meta = self._meta(name)
        dokl = "PUNKT_NA_OSI_ULICY" if lat is not None else "BRAK_GEOMETRII"
        powod = "" if lat is not None else "nazwa_rozwiazana_bez_geometrii"
        return Resolution(query, name, lat, lon, level, powod,
                          dokladnosc=dokl, miejscowosc=miejscowosc,
                          dlugosc_ulicy_m=meta.get("dlugosc_m"),
                          n_skladowych=meta.get("n_skladowych"),
                          rozrzut_skladowych_m=meta.get("rozrzut_skladowych_m"))

    # ------------------------------------------------------------------
    def punkt_dla_numeru(self, name: str, numer: Optional[str]) -> Optional[tuple[float, float]]:
        """Umiejscowienie numeru domu.

        Jesli gazeter niesie punkt adresowy dla pary (ulica, numer) -- zwraca go.
        W przeciwnym razie zwraca ``None``: interpolacja numeru wzdluz osi bez
        znanego zakresu numeracji bylaby zgadywaniem, a rozwiazywacz nie zgaduje.
        Os ulicy jest zachowana w gazeterze wlasnie po to, by punkt adresowy dal
        sie do niej odniesc, gdy zbior punktow adresowych bedzie dostepny.
        """
        if not numer:
            return None
        idx = getattr(self, "punkty_adresowe", None)
        if not idx:
            return None
        key = (normalize(name), normalize(str(numer)))
        p = idx.get(key)
        return (float(p[0]), float(p[1])) if p else None

    @staticmethod
    def _przeciecie(a: list[tuple[float, float]],
                    b: list[tuple[float, float]]) -> Optional[tuple[float, float]]:
        """Punkt przeciecia (albo najmniejszego zblizenia) dwoch osi ulic.

        Liczone na osiach z gazetera, w przyblizeniu rownopolowym wokol
        szerokosci srodkowej -- na skali miasta blad tej aproksymacji jest
        rzedu metrow i nie ma znaczenia wobec rozmycia samego wejscia.
        """
        import math

        lat0 = math.radians(sum(p[0] for p in a + b) / len(a + b))
        kx = 111320.0 * math.cos(lat0)
        ky = 110540.0

        def xy(p):
            return (p[1] * kx, p[0] * ky)

        best = None
        for i in range(len(a) - 1):
            p1, p2 = xy(a[i]), xy(a[i + 1])
            for j in range(len(b) - 1):
                p3, p4 = xy(b[j]), xy(b[j + 1])
                d1 = (p2[0] - p1[0], p2[1] - p1[1])
                d2 = (p4[0] - p3[0], p4[1] - p3[1])
                den = d1[0] * d2[1] - d1[1] * d2[0]
                if abs(den) < 1e-9:
                    continue
                t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
                u = ((p3[0] - p1[0]) * d1[1] - (p3[1] - p1[1]) * d1[0]) / den
                if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
                    x, y = p1[0] + t * d1[0], p1[1] + t * d1[1]
                    cand = (y / ky, x / kx)
                    if best is None:
                        best = cand
                    return cand
        return best

    # ------------------------------------------------------------------
    def resolve(self, query: Optional[str], *, is_station_code: bool = False,
                sprawdzaj_kod_stacji: bool = True) -> Resolution:
        """Rozwiąż opis miejsca.

        ``sprawdzaj_kod_stacji=False`` wyłącza heurystykę kodu stacji.  Jest to
        potrzebne, gdy wywołujący już rozstrzygnął, że opis NIE jest kodem
        stacji -- na przykład :class:`MultiLocalityResolver` sprawdza kod na
        pełnym opisie, a potem przekazuje tu sam człon ulicy.  Bez tego
        przełącznika krótkie nazwy ulic zapisane wersalikami ("MARSA", "TAMKA",
        "DŁUGA") wpadały w wzorzec kodu stacji: zmierzone 25 fałszywych braków
        na 1 236 wierszach rejestru Stoen Operator.
        """
        q = (query or "").strip()
        if not q:
            return Resolution(q, None, None, None, "NONE", "pusty_opis")
        if is_station_code or (sprawdzaj_kod_stacji and _RE_STATION_CODE.match(q)):
            return Resolution(q, None, None, None, "NONE", "kod_stacji_bez_slownika")

        # odetnij człon miejscowości, jeśli podany jako "MIASTO, adres"
        street = q.split(",", 1)[1] if "," in q else q
        nq = normalize(street)

        # 1) dokładne
        if nq in self._by_norm:
            return self._hit(q, self._by_norm[nq][0], "EXACT")
        nq_full = normalize(street.split(" nr ")[0])
        if nq_full in self._by_norm:
            return self._hit(q, self._by_norm[nq_full][0], "EXACT")

        ts = tokens(street)
        if not ts:
            return Resolution(q, None, None, None, "NONE", "brak_tokenow_wyrozniajacych")

        # 2) unikalny token
        cands = {t: self._by_token.get(t, []) for t in ts}
        # Odrzucenie przez prog pokrycia tokenow NIE konczy rozwiazywania:
        # dalsze strategie (odwrocenie czlonow, skrzyzowanie) moga opis wyjasnic
        # w calosci.  Flaga sluzy tylko do nadania powodu, gdy nic nie zadziala.
        odrzucono_opis = False

        unique = [names[0] for t, names in cands.items() if len(names) == 1]
        if len(set(unique)) == 1:
            if self._opis_slowny(ts, unique[0]):
                odrzucono_opis = True
            else:
                return self._hit(q, unique[0], "UNIQUE_TOKEN")

        # 3) podzbiór tokenów
        fs = frozenset(ts)
        subset_hits = [n for tsx, names in self._by_tokenset.items()
                       if fs and fs <= tsx for n in names]
        if len(set(subset_hits)) == 1:
            if self._opis_slowny(ts, subset_hits[0]):
                odrzucono_opis = True
            else:
                return self._hit(q, subset_hits[0], "TOKEN_SUBSET")

        # 4) odwrócona kolejność członów
        rev = self._resolve_reversed(street, ts)
        if rev is not None:
            if self._opis_slowny(ts, rev):
                odrzucono_opis = True
            else:
                return self._hit(q, rev, "REVERSED")

        # 5) skrzyżowanie: publikujący podaje dwie ulice ("WALICÓW / GRZYBOWSKA").
        #    Miejsce jest określone -- to węzeł sieci ulic, nie jedna ulica.
        parts = [p for p in re.split(r"[/\\]", street) if p.strip()]
        if len(parts) > 1:
            hits = []
            for p in parts:
                sub = self.resolve(p, sprawdzaj_kod_stacji=sprawdzaj_kod_stacji)
                if sub.rozwiazane:
                    hits.append(sub)
            if len(hits) >= 2:
                lat, lon = hits[0].lat, hits[0].lon
                dokl = "PUNKT_NA_OSI_ULICY" if lat is not None else "BRAK_GEOMETRII"
                powod = f"dopasowano {len(hits)} z {len(parts)} członów"
                # jesli gazeter niesie osie obu ulic, punktem jest ich przeciecie
                ax = [self.axis(h.matched) for h in hits[:2]]
                if all(ax):
                    xp = self._przeciecie(ax[0], ax[1])
                    if xp is not None:
                        lat, lon = round(xp[0], 6), round(xp[1], 6)
                        dokl = "PUNKT_SKRZYZOWANIA"
                    else:
                        powod += "; osie się nie przecinają, punkt z pierwszego członu"
                return Resolution(q, " / ".join(h.matched for h in hits),
                                  lat, lon, "SKRZYZOWANIE", powod,
                                  dokladnosc=dokl)

        if odrzucono_opis:
            return Resolution(q, None, None, None, "NONE",
                              "opis_slowny_nie_nazwa_ulicy")
        if not any(cands.values()):
            return Resolution(q, None, None, None, "NONE", "brak_kandydatow")
        return Resolution(q, None, None, None, "NONE", "wiele_kandydatow")

    # ------------------------------------------------------------------
    def _resolve_reversed(self, street: str, ts: list[str]) -> Optional[str]:
        """Domyka przypadki typu "WINCENTEGO ŚW." / "BEMA J.".

        Publikujący zapisują nazwisko na początku i skracają imię lub tytuł do
        inicjału.  Szukamy nazw gazetera, których zbiór tokenów zawiera WSZYSTKIE
        pełne tokeny opisu (niezależnie od kolejności), a pozostałe tokeny opisu
        są przedrostkami tokenów kandydata (obsługa inicjałów "J." -> "jozefa").
        """
        full = [t for t in ts if len(t) > 2]
        inits = [t for t in ts if len(t) <= 2]
        if not full:
            return None
        pool: Optional[set[str]] = None
        for t in full:
            names = set(self._by_token.get(t, []))
            pool = names if pool is None else (pool & names)
            if not pool:
                return None
        if inits:
            pool = {
                n for n in pool
                if all(any(tok.startswith(i) for tok in tokens(n)) for i in inits)
            }
        # dopuść też nieskrócone odwrócenie: dokładnie ten sam multizbiór tokenów
        exact_rev = {n for n in pool if frozenset(tokens(n)) == frozenset(ts)}
        if len(exact_rev) == 1:
            return next(iter(exact_rev))
        if len(pool) == 1:
            return next(iter(pool))
        return None

    # ------------------------------------------------------------------
    def resolve_series(self, values: Iterable[Optional[str]], *,
                       is_station_code: bool = False) -> list[Resolution]:
        return [self.resolve(v, is_station_code=is_station_code) for v in values]

    @staticmethod
    def summarize(resolutions: list[Resolution]) -> dict:
        n = len(resolutions)
        per = {lvl: sum(1 for r in resolutions if r.pewnosc == lvl) for lvl in PEWNOSC}
        powody: dict[str, int] = {}
        for r in resolutions:
            if r.pewnosc == "NONE" and r.powod:
                powody[r.powod] = powody.get(r.powod, 0) + 1
        solved = n - per["NONE"]
        return {
            "n": n,
            "rozwiazane": solved,
            "odsetek_rozwiazanych": round(solved / n, 6) if n else 0.0,
            "per_pewnosc": per,
            "powody_braku": dict(sorted(powody.items(), key=lambda kv: -kv[1])),
        }


class MultiLocalityResolver:
    """Rozwiązywacz dla gazetera z podziałem na miejscowości.

    Rejestry przyłączeniowe podają lokalizację jako ``MIEJSCOWOŚĆ, ulica``.
    Jedna płaska przestrzeń nazw ulic byłaby tu błędem: ta sama nazwa ulicy
    występuje w kilkunastu miejscowościach aglomeracji i płaski gazeter musiałby
    albo zgadywać, albo zwracać ``wiele_kandydatow``.  Ta klasa trzyma osobny
    :class:`LocationResolver` na miejscowość i kieruje zapytanie do właściwego.

    Zachowana jest nadrzędna zasada pakietu: **brak z przyczyną zamiast
    zgadywania**.  Dochodzą dwa nowe, jawne powody braku:

      ``miejscowosc_poza_gazeterem``  -- podanej miejscowości nie ma w gazeterze;
                                         to ograniczenie ZASIĘGU, nie porażka
                                         dopasowania, i jest raportowane osobno
      ``nazwa_rozwiazana_bez_geometrii`` -- nazwa dopasowana, ale wpis gazetera
                                         nie ma współrzędnych

    Gdy ulicy nie udało się rozwiązać, a miejscowość owszem, zwracany jest
    **brak** (``pewnosc == "NONE"``) -- centroid miejscowości NIE jest
    podstawiany w pole ``wspolrzedne``, bo byłby punktem o innym znaczeniu niż
    reszta kolumny.  Centroid jest natomiast udostępniony w polu
    ``lat``/``lon`` z ``dokladnosc == "CENTROID_MIEJSCOWOSCI"`` tylko wtedy, gdy
    wywołujący jawnie poprosi (``dopusc_centroid=True``), i wtedy rozpoznaje go
    po polu ``dokladnosc``.
    """

    def __init__(self, miejscowosci: dict[str, dict],
                 *, domyslna: Optional[str] = None):
        self.centroidy: dict[str, tuple[float, float]] = {}
        self.resolvery: dict[str, LocationResolver] = {}
        self._alias: dict[str, str] = {}
        for key, m in miejscowosci.items():
            k = normalize(key)
            self.resolvery[k] = LocationResolver(m.get("ulice", {}))
            # opcjonalny indeks punktow adresowych: "<ulica>|<numer>" -> [lat, lon]
            pa = m.get("punkty_adresowe") or {}
            if pa:
                idx = {}
                for kk, vv in pa.items():
                    st, _, nr = str(kk).partition("|")
                    idx[(normalize(st), normalize(nr))] = (float(vv[0]), float(vv[1]))
                self.resolvery[k].punkty_adresowe = idx
            if m.get("lat") is not None and m.get("lon") is not None:
                self.centroidy[k] = (float(m["lat"]), float(m["lon"]))
            self._alias[k] = k
            self._alias.setdefault(normalize(m.get("nazwa") or key), k)
        # alias czlonu glownego: "SEKOCIN NOWY"/"SEKOCIN STARY" -> pierwszy czlon,
        # gdy jest jednoznaczny; gdy nie jest, alias nie powstaje i zapytanie
        # o "SEKOCIN" konczy sie jawnym brakiem zamiast wyborem na chybil trafil
        heads: dict[str, list[str]] = defaultdict(list)
        for k in list(self.resolvery):
            parts = k.split()
            if len(parts) > 1:
                heads[parts[0]].append(k)
        for h, ks in heads.items():
            if h not in self._alias and len(ks) == 1:
                self._alias[h] = ks[0]
            elif h not in self._alias:
                self._alias[h] = "\x00AMBIG\x00" + "|".join(sorted(ks))
        self.domyslna = normalize(domyslna) if domyslna else None

    # ------------------------------------------------------------------
    def rozdziel(self, tekst: Optional[str]) -> tuple[Optional[str], str]:
        """Rozdziel ``"MIEJSCOWOŚĆ, ulica"`` na (miejscowość, ulica)."""
        t = (tekst or "").strip()
        if "," in t:
            a, b = t.split(",", 1)
            return a.strip(), b.strip()
        return None, t

    #: numer domu na koncu opisu: "25", "85A", "12/14", "3 bis"
    _RE_NUMER = re.compile(r"\s+(\d+\s*[a-zA-Z]?(?:\s*/\s*\d+\s*[a-zA-Z]?)?)\s*$")

    @classmethod
    def rozdziel_numer(cls, street: str) -> tuple[str, Optional[str]]:
        """Odetnij numer domu z końca opisu ulicy.

        Zwraca ``(ulica, numer)`` albo ``(ulica, None)``.  Sama obecność liczby
        na końcu nie dowodzi, że to numer domu -- w nazwach ulic liczby są
        częste ("Aleja 4 Czerwca 1989", "11 Listopada").  Dlatego wynik tego
        cięcia jest w :meth:`resolve` przyjmowany tylko wtedy, gdy reszta opisu
        dopasowuje się do TEJ SAMEJ nazwy ulicy, a numer trafia w indeks
        punktów adresowych.  Inaczej opis pozostaje nietknięty.
        """
        m = cls._RE_NUMER.search(street or "")
        if not m:
            return street, None
        return street[: m.start()].strip(), re.sub(r"\s+", "", m.group(1))

    def resolve(self, query: Optional[str], *,
                miejscowosc: Optional[str] = None,
                numer: Optional[str] = None,
                is_station_code: bool = False,
                dopusc_centroid: bool = False) -> Resolution:
        q = (query or "").strip()
        if not q:
            return Resolution(q, None, None, None, "NONE", "pusty_opis")
        if is_station_code or _RE_STATION_CODE.match(q):
            return Resolution(q, None, None, None, "NONE", "kod_stacji_bez_slownika")

        m_txt, street = self.rozdziel(q)
        if miejscowosc:
            m_txt = miejscowosc
        if not m_txt:
            # Bez ZADEKLAROWANEJ miejscowosci dopasowanie nazwy ulicy do gazetera
            # konkretnego miasta jest zgadywaniem, nie rozwiazaniem.  Zmierzone:
            # przy podstawianiu domyslnej miejscowosci opisy TAURONA typu
            # "Stacja projektowana" trafialy w warszawska "ul. Projektowana",
            # a "Wrzoski (planowany)" w drogowe "planowany lacznik".  Dlatego
            # domyslna miejscowosc jest opcjonalna i domyslnie WYLACZONA.
            if not self.domyslna:
                return Resolution(q, None, None, None, "NONE",
                                  "brak_deklaracji_miejscowosci")
            key = self.domyslna
        else:
            key = self._alias.get(normalize(m_txt))
        if key is None:
            return Resolution(q, None, None, None, "NONE",
                              "miejscowosc_poza_gazeterem", miejscowosc=m_txt)
        if key.startswith("\x00AMBIG\x00"):
            warianty = key[len("\x00AMBIG\x00"):]
            return Resolution(q, None, None, None, "NONE",
                              f"miejscowosc_niejednoznaczna:{warianty}",
                              miejscowosc=m_txt)

        sub = self.resolvery[key]
        r = sub.resolve(street, sprawdzaj_kod_stacji=False)

        # numer domu: jesli nie podano wprost, spróbuj odciąć z końca opisu.
        # Cięcie jest przyjmowane tylko wtedy, gdy reszta wskazuje TĘ SAMĄ ulicę
        # (albo gdy pełny opis w ogóle się nie dopasował) -- inaczej liczba jest
        # częścią nazwy ulicy, nie numerem domu.
        num = numer
        if num is None:
            rest, kand = self.rozdziel_numer(street)
            if kand:
                r_rest = sub.resolve(rest, sprawdzaj_kod_stacji=False)
                if r_rest.rozwiazane and (not r.rozwiazane or r_rest.matched == r.matched):
                    num = kand
                    if not r.rozwiazane:
                        r = r_rest

        r.query = q
        r.miejscowosc = m_txt

        if r.rozwiazane and r.matched and num:
            pt = sub.punkt_dla_numeru(r.matched, num)
            if pt is not None:
                r.lat, r.lon = pt
                r.dokladnosc = "PUNKT_ADRESOWY"
                r.powod = f"numer_domu={num}"

        if not r.rozwiazane and dopusc_centroid and key in self.centroidy:
            lat, lon = self.centroidy[key]
            return Resolution(q, None, lat, lon, "NONE", r.powod,
                              dokladnosc="CENTROID_MIEJSCOWOSCI", miejscowosc=m_txt)
        return r

    def resolve_series(self, values: Iterable[Optional[str]], **kw) -> list[Resolution]:
        return [self.resolve(v, **kw) for v in values]

    @staticmethod
    def summarize(resolutions: list[Resolution]) -> dict:
        s = LocationResolver.summarize(resolutions)
        s["per_dokladnosc"] = {d: sum(1 for r in resolutions if r.dokladnosc == d)
                               for d in DOKLADNOSC}
        z = sum(1 for r in resolutions if r.ma_wspolrzedne)
        s["ze_wspolrzednymi"] = z
        s["odsetek_ze_wspolrzednymi"] = round(z / len(resolutions), 6) if resolutions else 0.0
        return s


def resolver_from_gazeter_json(path, *, domyslna: Optional[str] = None) -> MultiLocalityResolver:
    """Zbuduj :class:`MultiLocalityResolver` z gazetera ze współrzędnymi.

    Oczekiwany układ pliku: ``{"miejscowosci": {KLUCZ: {"nazwa","lat","lon",
    "ulice": {nazwa: {"lat","lon","dlugosc_m","os"}}}}}``.
    """
    import json

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    miejsc = data["miejscowosci"] if "miejscowosci" in data else data
    return MultiLocalityResolver(miejsc, domyslna=domyslna)


def resolver_from_osm_json(path) -> LocationResolver:
    """Zbuduj rozwiązywacz z pliku JSON z nazwami ulic (lista nazw albo mapa)."""
    import json

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        if "streets" in data:
            data = data["streets"]
        elif "ulice" in data:
            data = data["ulice"]
    if isinstance(data, dict):
        gaz = {k: (tuple(v) if isinstance(v, (list, tuple)) and len(v) == 2 else None)
               for k, v in data.items()}
    else:
        gaz = {}
        for item in data:
            if isinstance(item, str):
                gaz[item] = None
            elif isinstance(item, dict):
                nm = item.get("name") or item.get("nazwa")
                if nm:
                    lat, lon = item.get("lat"), item.get("lon")
                    gaz[nm] = (float(lat), float(lon)) if lat is not None and lon is not None else None
    return LocationResolver(gaz)
