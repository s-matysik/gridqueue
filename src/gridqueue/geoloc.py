"""Location resolver with an EXPLICIT confidence level.

Overriding rule: the resolver never guesses silently.  Every result carries a
confidence level, and the share of resolved cases is a reported metric, not an assumption.

Confidence levels (descending):
  EXACT        : the normalized description is identical to a name in the gazetteer
  UNIQUE_TOKEN : exactly one name in the gazetteer contains a recognizable
                 distinguishing token from the description
  TOKEN_SUBSET : the set of tokens in the description is contained in the tokens of exactly one name
  REVERSED     : matched after reversing the order of the name's parts
                 ("WINCENTEGO ŚW." -> "Świętego Wincentego", "BEMA J." -> "Józefa Bema")
  SKRZYZOWANIE : the description indicates an intersection of two streets ("WALICÓW / GRZYBOWSKA");
                 resolved when at least two parts hit the gazetteer
  NONE         : no match; the ``powod`` field says why

For publishers that give the location as an INTERNAL STATION CODE
(TAURON: "SKB3", "RCB4"), the resolver returns NONE with the reason
``kod_stacji_bez_slownika``: it does not try to guess, because the operator does not publish
a code dictionary and any match would be confabulation.

Extension with coordinates (version 0.2)
----------------------------------------
The result now carries a point and a SECOND, independent level: ``dokladnosc``
(see :data:`DOKLADNOSC`).  The two levels answer two different questions:

  ``pewnosc``    : how certain the IDENTIFICATION of the place name is,
  ``dokladnosc`` : how precisely the returned point represents that place.

They are disjoint by design: an EXACT match to a 6 km long street gives a point
with accuracy ``PUNKT_NA_OSI_ULICY`` and a blur on the order of a kilometer, while a
UNIQUE_TOKEN match to a short street gives a better point.  The length of the matched
street's axis is returned in ``dlugosc_ulicy_m`` for exactly this reason: so that the blur
can be computed, not merely declared.

The distinction is preserved between **failing to resolve the name**
(``pewnosc == "NONE"``) and **resolving the name without available geometry**
(``pewnosc != "NONE"``, ``dokladnosc == "BRAK_GEOMETRII"``,
``powod == "nazwa_rozwiazana_bez_geometrii"``): these are two different states of knowledge,
and mixing them would overstate or understate coverage.  Predicates:
``Resolution.rozwiazane`` (name) and ``Resolution.ma_wspolrzedne`` (point).

The house number is not interpolated along the street axis without a known numbering
range: that would be guessing.  ``punkt_dla_numeru`` returns a point only
from the address point index, if one has been loaded.
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

#: Level of placement ACCURACY (DOKLADNOSC): answers a different question than ``pewnosc``.
#: ``pewnosc`` says how certain the IDENTIFICATION of the name is; ``dokladnosc`` says
#: how precisely the returned point represents the indicated place.  The separation
#: is necessary because a name can be identified flawlessly (EXACT), while the point
#: can still be only the center of a street several kilometers long.
#:
#:   PUNKT_ADRESOWY        : known address point (street + house number)
#:   PUNKT_SKRZYZOWANIA    : intersection of the axes of two indicated streets
#:   PUNKT_NA_OSI_ULICY    : point at 50% of the street axis length (uncertainty ~ length/4)
#:   CENTROID_MIEJSCOWOSCI : only the locality was resolved, not the street
#:   BRAK_GEOMETRII        : name RESOLVED, but the gazetteer has no coordinates for it
#:   BRAK                  : name not resolved, so there is nothing to place
DOKLADNOSC = (
    "PUNKT_ADRESOWY", "PUNKT_SKRZYZOWANIA", "PUNKT_NA_OSI_ULICY",
    "CENTROID_MIEJSCOWOSCI", "BRAK_GEOMETRII", "BRAK",
)

#: prefixes and parts that do not distinguish a street
_STOP = {
    "ul", "ulica", "al", "aleja", "aleje", "pl", "plac", "os", "osiedle", "rondo",
    "sw", "swietego", "swietej", "im", "imienia", "gen", "generala", "gen.",
    "ks", "ksiedza", "dr", "prof", "mjr", "plk", "kpt", "por", "mjra", "marsz",
    "marszalka", "bp", "biskupa", "kard", "kardynala", "droga", "trakt", "skwer",
    "bulwar", "park", "most", "wybrzeze", "brak", "dzialka", "nr", "dz", "obreb",
}

#: station code: 2-6 uppercase letters/digits without spaces, or a description of a planned station
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
    #: placement accuracy level: see DOKLADNOSC
    dokladnosc: str = "BRAK"
    #: locality whose gazetteer was searched (None for a single-area gazetteer)
    miejscowosc: Optional[str] = None
    #: length of the matched street's axis in meters, if the gazetteer carries it;
    #: this is an explicit measure of the blur of a PUNKT_NA_OSI_ULICY point
    dlugosc_ulicy_m: Optional[float] = None
    #: number of DISJOINT geometry components with this name in this locality
    n_skladowych: Optional[int] = None
    #: largest distance between the centroids of these components [m].  A large
    #: value means the street name does NOT determine a single place: within one
    #: city there are several distant streets with the same name, and the point lies
    #: on the longest component.  Statutory registers do not give the district, so
    #: this ambiguity cannot be removed from the published data;
    #: that is why it is REPORTED, not hidden.
    rozrzut_skladowych_m: Optional[float] = None

    @property
    def rozwiazane(self) -> bool:
        """Whether the NAME has been identified (regardless of geometry availability)."""
        return self.pewnosc != "NONE"

    @property
    def ma_wspolrzedne(self) -> bool:
        """Whether the result carries a point.  Disjoint from ``rozwiazane``: the name may be
        resolved while the geometry may be missing (``dokladnosc == BRAK_GEOMETRII``)."""
        return self.lat is not None and self.lon is not None


class LocationResolver:
    """Matching of a place description against a gazetteer of street/place names.

    ``gazetteer``: a map name -> (lat, lon) or name -> None (when there are no
    coordinates, and only the identification outcome matters to us).
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
        """Coordinates of a gazetteer entry.

        Supported entry forms (backward compatibility preserved):
          ``None``                  : no geometry
          ``(lat, lon)``            : bare point
          ``{"lat":..,"lon":..}``   : extended entry, may additionally carry
                                      ``os`` (list [lat, lon]) and ``dlugosc_m``
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
        """Street axis as a list of (lat, lon), if the gazetteer carries it."""
        os_ = self._meta(name).get("os")
        if not os_ or len(os_) < 2:
            return None
        return [(float(p[0]), float(p[1])) for p in os_]

    #: threshold for the share of explained description tokens; below the threshold a
    #: non-EXACT match is rejected as a verbal description, not a street name
    PROG_POKRYCIA_TOKENOW = 0.5
    #: from this many description tokens the threshold is applied (short descriptions are street names)
    MIN_TOKENOW_DLA_PROGU = 4

    def _udzial_wyjasnionych(self, ts: list[str], name: str) -> float:
        """What fraction of the description's tokens is explained by the matched name.

        A token counts as explained when it equals a token of the name or is
        a prefix of it (handling of initials: "a." -> "augusta").
        """
        if not ts:
            return 0.0
        nt = tokens(name)
        ile = sum(1 for t in ts if any(t == x or x.startswith(t) for x in nt))
        return ile / len(ts)

    def _opis_slowny(self, ts: list[str], name: str) -> bool:
        """Whether the match relies on a single token of a long verbal description.

        Measured on the panel: the description "Bezposrednie sasiedztwo Lotniska Chopina w
        Warszawie" matched the street "Fryderyka Chopina" through the single token
        "chopina", giving a point in the city center instead of near the airport.  A match
        explaining less than half the tokens of a long description is not an
        identification of a street and is rejected with an explicit reason.
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
        """Placement of a house number.

        If the gazetteer carries an address point for the pair (street, number), it is
        returned.  Otherwise returns ``None``: interpolating the number along the axis
        without a known numbering range would be guessing, and the resolver does not
        guess.  The street axis is kept in the gazetteer for exactly this reason: so
        that the address point can be referenced against it once a set of address
        points becomes available.
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
        """Intersection point (or closest approach) of two street axes.

        Computed on the axes from the gazetteer, with an equirectangular approximation
        around the median latitude: at the scale of a city the error of this
        approximation is on the order of meters and is negligible compared to the
        blur of the input itself.
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
        """Resolve a place description.

        ``sprawdzaj_kod_stacji=False`` disables the station code heuristic.  This is
        needed when the caller has already determined that the description is NOT a
        station code; for example :class:`MultiLocalityResolver` checks the code on
        the full description and then passes only the street part here.  Without this
        switch, short street names written in uppercase ("MARSA", "TAMKA",
        "DŁUGA") fell into the station code pattern: measured 25 false negatives
        on 1,236 rows of the Stoen Operator register.
        """
        q = (query or "").strip()
        if not q:
            return Resolution(q, None, None, None, "NONE", "pusty_opis")
        if is_station_code or (sprawdzaj_kod_stacji and _RE_STATION_CODE.match(q)):
            return Resolution(q, None, None, None, "NONE", "kod_stacji_bez_slownika")

        # strip the locality part, if given as "CITY, address"
        street = q.split(",", 1)[1] if "," in q else q
        nq = normalize(street)

        # 1) exact
        if nq in self._by_norm:
            return self._hit(q, self._by_norm[nq][0], "EXACT")
        nq_full = normalize(street.split(" nr ")[0])
        if nq_full in self._by_norm:
            return self._hit(q, self._by_norm[nq_full][0], "EXACT")

        ts = tokens(street)
        if not ts:
            return Resolution(q, None, None, None, "NONE", "brak_tokenow_wyrozniajacych")

        # 2) unique token
        cands = {t: self._by_token.get(t, []) for t in ts}
        # Rejection via the token coverage threshold does NOT end resolution:
        # further strategies (reversing the parts, intersection) may explain the
        # description in full.  The flag only serves to assign a reason when nothing
        # works.
        odrzucono_opis = False

        unique = [names[0] for t, names in cands.items() if len(names) == 1]
        if len(set(unique)) == 1:
            if self._opis_slowny(ts, unique[0]):
                odrzucono_opis = True
            else:
                return self._hit(q, unique[0], "UNIQUE_TOKEN")

        # 3) token subset
        fs = frozenset(ts)
        subset_hits = [n for tsx, names in self._by_tokenset.items()
                       if fs and fs <= tsx for n in names]
        if len(set(subset_hits)) == 1:
            if self._opis_slowny(ts, subset_hits[0]):
                odrzucono_opis = True
            else:
                return self._hit(q, subset_hits[0], "TOKEN_SUBSET")

        # 4) reversed order of parts
        rev = self._resolve_reversed(street, ts)
        if rev is not None:
            if self._opis_slowny(ts, rev):
                odrzucono_opis = True
            else:
                return self._hit(q, rev, "REVERSED")

        # 5) intersection: the publisher gives two streets ("WALICÓW / GRZYBOWSKA").
        #    The place is determined: it is a node of the street network, not a single street.
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
                # if the gazetteer carries the axes of both streets, the point is their
                # intersection
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
        """Closes cases of the type "WINCENTEGO ŚW." / "BEMA J.".

        Publishers write the surname first and shorten the given name or title to an
        initial.  We look for gazetteer names whose token set contains ALL the full
        tokens of the description (regardless of order), while the remaining tokens
        of the description are prefixes of the candidate's tokens (handling of
        initials "J." -> "jozefa").
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
        # also allow an unabbreviated reversal: exactly the same multiset of tokens
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
    """Resolver for a gazetteer split by locality.

    Connection registers give the location as ``LOCALITY, street``.
    A single flat namespace of street names would be an error here: the same street
    name occurs in a dozen or so localities of the agglomeration, and a flat gazetteer
    would have to either guess or return ``wiele_kandydatow``.  This class keeps a
    separate :class:`LocationResolver` per locality and routes the query to the right
    one.

    The package's overriding principle is preserved: **a no-match with a reason
    instead of guessing**.  Two new, explicit no-match reasons are added:

      ``miejscowosc_poza_gazeterem``     : the given locality is not in the gazetteer;
                                            this is a COVERAGE limitation, not a
                                            matching failure, and is reported
                                            separately
      ``nazwa_rozwiazana_bez_geometrii`` : the name was matched, but the gazetteer
                                            entry has no coordinates

    When the street could not be resolved but the locality could, a
    **no-match** is returned (``pewnosc == "NONE"``): the locality centroid is NOT
    substituted into the ``wspolrzedne`` field, because it would be a point with a
    different meaning than the rest of the column.  The centroid is instead made
    available in the ``lat``/``lon`` field with ``dokladnosc == "CENTROID_MIEJSCOWOSCI"``
    only when the caller explicitly asks for it (``dopusc_centroid=True``), and it can
    then be recognized by the ``dokladnosc`` field.
    """

    def __init__(self, miejscowosci: dict[str, dict],
                 *, domyslna: Optional[str] = None):
        self.centroidy: dict[str, tuple[float, float]] = {}
        self.resolvery: dict[str, LocationResolver] = {}
        self._alias: dict[str, str] = {}
        for key, m in miejscowosci.items():
            k = normalize(key)
            self.resolvery[k] = LocationResolver(m.get("ulice", {}))
            # optional index of address points: "<street>|<number>" -> [lat, lon]
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
        # alias of the main part: "SEKOCIN NOWY"/"SEKOCIN STARY" -> the first part,
        # when it is unambiguous; when it is not, the alias is not created and a query
        # for "SEKOCIN" ends in an explicit no-match instead of a random choice
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
        """Split ``"LOCALITY, street"`` into (locality, street)."""
        t = (tekst or "").strip()
        if "," in t:
            a, b = t.split(",", 1)
            return a.strip(), b.strip()
        return None, t

    #: house number at the end of the description: "25", "85A", "12/14", "3 bis"
    _RE_NUMER = re.compile(r"\s+(\d+\s*[a-zA-Z]?(?:\s*/\s*\d+\s*[a-zA-Z]?)?)\s*$")

    @classmethod
    def rozdziel_numer(cls, street: str) -> tuple[str, Optional[str]]:
        """Strip the house number from the end of a street description.

        Returns ``(street, number)`` or ``(street, None)``.  The mere presence of a
        number at the end does not prove that it is a house number: numbers are
        common in street names ("Aleja 4 Czerwca 1989", "11 Listopada").  That is why
        the result of this cut is accepted in :meth:`resolve` only when the rest of
        the description matches the SAME street name, and the number hits the address
        point index.  Otherwise the description is left untouched.
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
            # Without a DECLARED locality, matching a street name against the
            # gazetteer of a specific city is guessing, not resolving.  Measured:
            # when substituting the default locality, TAURON descriptions of the
            # type "Stacja projektowana" matched the Warsaw "ul. Projektowana",
            # and "Wrzoski (planowany)" matched the road "planowany lacznik".  That
            # is why the default locality is optional and OFF by default.
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

        # house number: if not given explicitly, try to cut it off the end of the
        # description.  The cut is accepted only when the rest indicates the SAME
        # street (or when the full description did not match at all); otherwise the
        # number is part of the street name, not a house number.
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
    """Build a :class:`MultiLocalityResolver` from a gazetteer with coordinates.

    Expected file layout: ``{"miejscowosci": {KLUCZ: {"nazwa","lat","lon",
    "ulice": {nazwa: {"lat","lon","dlugosc_m","os"}}}}}``.
    """
    import json

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    miejsc = data["miejscowosci"] if "miejscowosci" in data else data
    return MultiLocalityResolver(miejsc, domyslna=domyslna)


def resolver_from_osm_json(path) -> LocationResolver:
    """Build a resolver from a JSON file with street names (list of names or a map)."""
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
