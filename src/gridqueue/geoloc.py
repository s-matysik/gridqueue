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
  NONE         : no match; the ``reason`` field says why

For publishers that give the location as an INTERNAL STATION CODE
(TAURON: "SKB3", "RCB4"), the resolver returns NONE with the reason
``station_code_without_dictionary``: it does not try to guess, because the operator does not publish
a code dictionary and any match would be confabulation.

Extension with coordinates (version 0.2)
----------------------------------------
The result now carries a point and a SECOND, independent level: ``accuracy``
(see :data:`ACCURACY`).  The two levels answer two different questions:

  ``confidence``    : how certain the IDENTIFICATION of the place name is,
  ``accuracy`` : how precisely the returned point represents that place.

They are disjoint by design: an EXACT match to a 6 km long street gives a point
with accuracy ``STREET_AXIS_POINT`` and a blur on the order of a kilometer, while a
UNIQUE_TOKEN match to a short street gives a better point.  The length of the matched
street's axis is returned in ``street_length_m`` for exactly this reason: so that the blur
can be computed, not merely declared.

The distinction is preserved between **failing to resolve the name**
(``pewnosc == "NONE"``) and **resolving the name without available geometry**
(``pewnosc != "NONE"``, ``dokladnosc == "BRAK_GEOMETRII"``,
``powod == "name_resolved_without_geometry"``): these are two different states of knowledge,
and mixing them would overstate or understate coverage.  Predicates:
``Resolution.rozwiazane`` (name) and ``Resolution.ma_wspolrzedne`` (point).

The house number is not interpolated along the street axis without a known numbering
range: that would be guessing.  ``point_for_number`` returns a point only
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
    "CONFIDENCE", "ACCURACY", "normalize", "tokens",
    "resolver_from_osm_json", "resolver_from_gazetteer_json", "geocode_frame",
]

CONFIDENCE = ("EXACT", "UNIQUE_TOKEN", "TOKEN_SUBSET", "REVERSED", "INTERSECTION", "NONE")

#: Level of placement ACCURACY (DOKLADNOSC): answers a different question than ``confidence``.
#: ``confidence`` says how certain the IDENTIFICATION of the name is; ``accuracy`` says
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
ACCURACY = (
    "ADDRESS_POINT", "INTERSECTION_POINT", "STREET_AXIS_POINT",
    "LOCALITY_CENTROID", "NO_GEOMETRY", "NO_POINT",
)

#: keys of gazetteers written for the first drafts of the package, read as their English names
GAZETTEER_LEGACY_KEYS = {"miejscowosci": "localities", "ulice": "streets", "nazwa": "name",
                         "dlugosc_m": "length_m", "os": "axis",
                         "punkty_adresowe": "address_points"}


def _gazetteer_keys(d: dict) -> dict:
    return {GAZETTEER_LEGACY_KEYS.get(k, k): v for k, v in d.items()}


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
    confidence: str
    reason: str = ""
    #: placement accuracy level: see DOKLADNOSC
    accuracy: str = "NO_POINT"
    #: locality whose gazetteer was searched (None for a single-area gazetteer)
    locality: Optional[str] = None
    #: length of the matched street's axis in meters, if the gazetteer carries it;
    #: this is an explicit measure of the blur of a PUNKT_NA_OSI_ULICY point
    street_length_m: Optional[float] = None
    #: number of DISJOINT geometry components with this name in this locality
    n_components: Optional[int] = None
    #: largest distance between the centroids of these components [m].  A large
    #: value means the street name does NOT determine a single place: within one
    #: city there are several distant streets with the same name, and the point lies
    #: on the longest component.  Statutory registers do not give the district, so
    #: this ambiguity cannot be removed from the published data;
    #: that is why it is REPORTED, not hidden.
    components_spread_m: Optional[float] = None

    @property
    def resolved(self) -> bool:
        """Whether the NAME has been identified (regardless of geometry availability)."""
        return self.confidence != "NONE"

    @property
    def has_coordinates(self) -> bool:
        """Whether the result carries a point.  Disjoint from ``resolved``: the name may be
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
                                      ``os`` (list [lat, lon]) and ``length_m``
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
        return _gazetteer_keys(c) if isinstance(c, dict) else {}

    def axis(self, name: str) -> Optional[list[tuple[float, float]]]:
        """Street axis as a list of (lat, lon), if the gazetteer carries it."""
        os_ = self._meta(name).get("axis")
        if not os_ or len(os_) < 2:
            return None
        return [(float(p[0]), float(p[1])) for p in os_]

    #: threshold for the share of explained description tokens; below the threshold a
    #: non-EXACT match is rejected as a verbal description, not a street name
    TOKEN_COVERAGE_THRESHOLD = 0.5
    #: from this many description tokens the threshold is applied (short descriptions are street names)
    MIN_TOKENS_FOR_THRESHOLD = 4

    def _share_explained(self, ts: list[str], name: str) -> float:
        """What fraction of the description's tokens is explained by the matched name.

        A token counts as explained when it equals a token of the name or is
        a prefix of it (handling of initials: "a." -> "augusta").
        """
        if not ts:
            return 0.0
        nt = tokens(name)
        n_found = sum(1 for t in ts if any(t == x or x.startswith(t) for x in nt))
        return n_found / len(ts)

    def _verbal_description(self, ts: list[str], name: str) -> bool:
        """Whether the match relies on a single token of a long verbal description.

        Measured on the panel: the description "Bezposrednie sasiedztwo Lotniska Chopina w
        Warszawie" matched the street "Fryderyka Chopina" through the single token
        "chopina", giving a point in the city center instead of near the airport.  A match
        explaining less than half the tokens of a long description is not an
        identification of a street and is rejected with an explicit reason.
        """
        if len(ts) < self.MIN_TOKENS_FOR_THRESHOLD:
            return False
        return self._share_explained(ts, name) < self.TOKEN_COVERAGE_THRESHOLD

    def _hit(self, query: str, name: str, level: str,
             locality: Optional[str] = None) -> Resolution:
        lat, lon = self._coords(name)
        meta = self._meta(name)
        acc = "STREET_AXIS_POINT" if lat is not None else "NO_GEOMETRY"
        reason = "" if lat is not None else "name_resolved_without_geometry"
        return Resolution(query, name, lat, lon, level, reason,
                          accuracy=acc, locality=locality,
                          street_length_m=meta.get("length_m"),
                          n_components=meta.get("n_components"),
                          components_spread_m=meta.get("components_spread_m"))

    # ------------------------------------------------------------------
    def point_for_number(self, name: str, number: Optional[str]) -> Optional[tuple[float, float]]:
        """Placement of a house number.

        If the gazetteer carries an address point for the pair (street, number), it is
        returned.  Otherwise returns ``None``: interpolating the number along the axis
        without a known numbering range would be guessing, and the resolver does not
        guess.  The street axis is kept in the gazetteer for exactly this reason: so
        that the address point can be referenced against it once a set of address
        points becomes available.
        """
        if not number:
            return None
        idx = getattr(self, "address_points", None)
        if not idx:
            return None
        key = (normalize(name), normalize(str(number)))
        p = idx.get(key)
        return (float(p[0]), float(p[1])) if p else None

    @staticmethod
    def _intersection(a: list[tuple[float, float]],
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
                check_station_code: bool = True) -> Resolution:
        """Resolve a place description.

        ``sprawdzaj_station_code=False`` disables the station code heuristic.  This is
        needed when the caller has already determined that the description is NOT a
        station code; for example :class:`MultiLocalityResolver` checks the code on
        the full description and then passes only the street part here.  Without this
        switch, short street names written in uppercase ("MARSA", "TAMKA",
        "DŁUGA") fell into the station code pattern: measured 25 false negatives
        on 1,236 rows of the Stoen Operator register.
        """
        q = (query or "").strip()
        if not q:
            return Resolution(q, None, None, None, "NONE", "empty_description")
        if is_station_code or (check_station_code and _RE_STATION_CODE.match(q)):
            return Resolution(q, None, None, None, "NONE", "station_code_without_dictionary")

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
            return Resolution(q, None, None, None, "NONE", "no_distinguishing_tokens")

        # 2) unique token
        cands = {t: self._by_token.get(t, []) for t in ts}
        # Rejection via the token coverage threshold does NOT end resolution:
        # further strategies (reversing the parts, intersection) may explain the
        # description in full.  The flag only serves to assign a reason when nothing
        # works.
        rejected_description = False

        unique = [names[0] for t, names in cands.items() if len(names) == 1]
        if len(set(unique)) == 1:
            if self._verbal_description(ts, unique[0]):
                rejected_description = True
            else:
                return self._hit(q, unique[0], "UNIQUE_TOKEN")

        # 3) token subset
        fs = frozenset(ts)
        subset_hits = [n for tsx, names in self._by_tokenset.items()
                       if fs and fs <= tsx for n in names]
        if len(set(subset_hits)) == 1:
            if self._verbal_description(ts, subset_hits[0]):
                rejected_description = True
            else:
                return self._hit(q, subset_hits[0], "TOKEN_SUBSET")

        # 4) reversed order of parts
        rev = self._resolve_reversed(street, ts)
        if rev is not None:
            if self._verbal_description(ts, rev):
                rejected_description = True
            else:
                return self._hit(q, rev, "REVERSED")

        # 5) intersection: the publisher gives two streets ("WALICÓW / GRZYBOWSKA").
        #    The place is determined: it is a node of the street network, not a single street.
        parts = [p for p in re.split(r"[/\\]", street) if p.strip()]
        if len(parts) > 1:
            hits = []
            for p in parts:
                sub = self.resolve(p, check_station_code=check_station_code)
                if sub.resolved:
                    hits.append(sub)
            if len(hits) >= 2:
                lat, lon = hits[0].lat, hits[0].lon
                acc = "STREET_AXIS_POINT" if lat is not None else "NO_GEOMETRY"
                reason = f"matched {len(hits)} of {len(parts)} parts"
                # if the gazetteer carries the axes of both streets, the point is their
                # intersection
                ax = [self.axis(h.matched) for h in hits[:2]]
                if all(ax):
                    xp = self._intersection(ax[0], ax[1])
                    if xp is not None:
                        lat, lon = round(xp[0], 6), round(xp[1], 6)
                        acc = "INTERSECTION_POINT"
                    else:
                        reason += "; the axes do not intersect, point taken from the first part"
                return Resolution(q, " / ".join(h.matched for h in hits),
                                  lat, lon, "INTERSECTION", reason,
                                  accuracy=acc)

        if rejected_description:
            return Resolution(q, None, None, None, "NONE",
                              "verbal_description_not_street_name")
        if not any(cands.values()):
            return Resolution(q, None, None, None, "NONE", "no_candidates")
        return Resolution(q, None, None, None, "NONE", "multiple_candidates")

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
        per = {lvl: sum(1 for r in resolutions if r.confidence == lvl) for lvl in CONFIDENCE}
        reasons: dict[str, int] = {}
        for r in resolutions:
            if r.confidence == "NONE" and r.reason:
                reasons[r.reason] = reasons.get(r.reason, 0) + 1
        solved = n - per["NONE"]
        return {
            "n": n,
            "resolved": solved,
            "resolved_share": round(solved / n, 6) if n else 0.0,
            "per_confidence": per,
            "missing_reasons": dict(sorted(reasons.items(), key=lambda kv: -kv[1])),
        }


class MultiLocalityResolver:
    """Resolver for a gazetteer split by locality.

    Connection registers give the location as ``LOCALITY, street``.
    A single flat namespace of street names would be an error here: the same street
    name occurs in a dozen or so localities of the agglomeration, and a flat gazetteer
    would have to either guess or return ``multiple_candidates``.  This class keeps a
    separate :class:`LocationResolver` per locality and routes the query to the right
    one.

    The package's overriding principle is preserved: **a no-match with a reason
    instead of guessing**.  Two new, explicit no-match reasons are added:

      ``locality_not_in_gazetteer``     : the given locality is not in the gazetteer;
                                            this is a COVERAGE limitation, not a
                                            matching failure, and is reported
                                            separately
      ``name_resolved_without_geometry`` : the name was matched, but the gazetteer
                                            entry has no coordinates

    When the street could not be resolved but the locality could, a
    **no-match** is returned (``pewnosc == "NONE"``): the locality centroid is NOT
    substituted into the ``coordinates`` field, because it would be a point with a
    different meaning than the rest of the column.  The centroid is instead made
    available in the ``lat``/``lon`` field with ``dokladnosc == "CENTROID_MIEJSCOWOSCI"``
    only when the caller explicitly asks for it (``dopusc_centroid=True``), and it can
    then be recognized by the ``accuracy`` field.
    """

    def __init__(self, localities: dict[str, dict],
                 *, default_locality: Optional[str] = None):
        self.centroids: dict[str, tuple[float, float]] = {}
        self.resolvers: dict[str, LocationResolver] = {}
        self._alias: dict[str, str] = {}
        for key, m in localities.items():
            m = _gazetteer_keys(m)
            k = normalize(key)
            self.resolvers[k] = LocationResolver(m.get("streets", {}))
            # optional index of address points: "<street>|<number>" -> [lat, lon]
            pa = m.get("address_points") or {}
            if pa:
                idx = {}
                for kk, vv in pa.items():
                    st, _, nr = str(kk).partition("|")
                    idx[(normalize(st), normalize(nr))] = (float(vv[0]), float(vv[1]))
                self.resolvers[k].address_points = idx
            if m.get("lat") is not None and m.get("lon") is not None:
                self.centroids[k] = (float(m["lat"]), float(m["lon"]))
            self._alias[k] = k
            self._alias.setdefault(normalize(m.get("name") or key), k)
        # alias of the main part: "SEKOCIN NOWY"/"SEKOCIN STARY" -> the first part,
        # when it is unambiguous; when it is not, the alias is not created and a query
        # for "SEKOCIN" ends in an explicit no-match instead of a random choice
        heads: dict[str, list[str]] = defaultdict(list)
        for k in list(self.resolvers):
            parts = k.split()
            if len(parts) > 1:
                heads[parts[0]].append(k)
        for h, ks in heads.items():
            if h not in self._alias and len(ks) == 1:
                self._alias[h] = ks[0]
            elif h not in self._alias:
                self._alias[h] = "\x00AMBIG\x00" + "|".join(sorted(ks))
        self.default_locality = normalize(default_locality) if default_locality else None

    # ------------------------------------------------------------------
    def split_number_part(self, text: Optional[str]) -> tuple[Optional[str], str]:
        """Split ``"LOCALITY, street"`` into (locality, street)."""
        t = (text or "").strip()
        if "," in t:
            a, b = t.split(",", 1)
            return a.strip(), b.strip()
        return None, t

    #: house number at the end of the description: "25", "85A", "12/14", "3 bis"
    _RE_NUMBER = re.compile(r"\s+(\d+\s*[a-zA-Z]?(?:\s*/\s*\d+\s*[a-zA-Z]?)?)\s*$")

    @classmethod
    def split_house_number(cls, street: str) -> tuple[str, Optional[str]]:
        """Strip the house number from the end of a street description.

        Returns ``(street, number)`` or ``(street, None)``.  The mere presence of a
        number at the end does not prove that it is a house number: numbers are
        common in street names ("Aleja 4 Czerwca 1989", "11 Listopada").  That is why
        the result of this cut is accepted in :meth:`resolve` only when the rest of
        the description matches the SAME street name, and the number hits the address
        point index.  Otherwise the description is left untouched.
        """
        m = cls._RE_NUMBER.search(street or "")
        if not m:
            return street, None
        return street[: m.start()].strip(), re.sub(r"\s+", "", m.group(1))

    def resolve(self, query: Optional[str], *,
                locality: Optional[str] = None,
                number: Optional[str] = None,
                is_station_code: bool = False,
                allow_centroid: bool = False) -> Resolution:
        q = (query or "").strip()
        if not q:
            return Resolution(q, None, None, None, "NONE", "empty_description")
        if is_station_code or _RE_STATION_CODE.match(q):
            return Resolution(q, None, None, None, "NONE", "station_code_without_dictionary")

        m_txt, street = self.split_number_part(q)
        if locality:
            m_txt = locality
        if not m_txt:
            # Without a DECLARED locality, matching a street name against the
            # gazetteer of a specific city is guessing, not resolving.  Measured:
            # when substituting the default locality, TAURON descriptions of the
            # type "Stacja projektowana" matched the Warsaw "ul. Projektowana",
            # and "Wrzoski (planowany)" matched the road "planowany lacznik".  That
            # is why the default locality is optional and OFF by default.
            if not self.default_locality:
                return Resolution(q, None, None, None, "NONE",
                                  "no_locality_declared")
            key = self.default_locality
        else:
            key = self._alias.get(normalize(m_txt))
        if key is None:
            return Resolution(q, None, None, None, "NONE",
                              "locality_not_in_gazetteer", locality=m_txt)
        if key.startswith("\x00AMBIG\x00"):
            variants = key[len("\x00AMBIG\x00"):]
            return Resolution(q, None, None, None, "NONE",
                              f"ambiguous_locality:{variants}",
                              locality=m_txt)

        sub = self.resolvers[key]
        r = sub.resolve(street, check_station_code=False)

        # house number: if not given explicitly, try to cut it off the end of the
        # description.  The cut is accepted only when the rest indicates the SAME
        # street (or when the full description did not match at all); otherwise the
        # number is part of the street name, not a house number.
        num = number
        if num is None:
            rest, cand = self.split_house_number(street)
            if cand:
                r_rest = sub.resolve(rest, check_station_code=False)
                if r_rest.resolved and (not r.resolved or r_rest.matched == r.matched):
                    num = cand
                    if not r.resolved:
                        r = r_rest

        r.query = q
        r.locality = m_txt

        if r.resolved and r.matched and num:
            pt = sub.point_for_number(r.matched, num)
            if pt is not None:
                r.lat, r.lon = pt
                r.accuracy = "ADDRESS_POINT"
                r.reason = f"house_number={num}"

        if not r.resolved and allow_centroid and key in self.centroids:
            lat, lon = self.centroids[key]
            return Resolution(q, None, lat, lon, "NONE", r.reason,
                              accuracy="LOCALITY_CENTROID", locality=m_txt)
        return r

    def resolve_series(self, values: Iterable[Optional[str]], **kw) -> list[Resolution]:
        return [self.resolve(v, **kw) for v in values]

    @staticmethod
    def summarize(resolutions: list[Resolution]) -> dict:
        s = LocationResolver.summarize(resolutions)
        s["per_accuracy"] = {d: sum(1 for r in resolutions if r.accuracy == d)
                               for d in ACCURACY}
        z = sum(1 for r in resolutions if r.has_coordinates)
        s["with_coordinates"] = z
        s["share_with_coordinates"] = round(z / len(resolutions), 6) if resolutions else 0.0
        return s


def resolver_from_gazetteer_json(path, *, default_locality: Optional[str] = None) -> MultiLocalityResolver:
    """Build a :class:`MultiLocalityResolver` from a gazetteer with coordinates.

    Expected file layout: ``{"localities": {KEY: {"name", "lat", "lon",
    "streets": {street name: {"lat", "lon", "length_m", "axis"}}}}}``. Gazetteers written
    with the keys of the first drafts (``miejscowosci``, ``ulice``, ``nazwa``,
    ``dlugosc_m``, ``os``, ``punkty_adresowe``) are read as well.
    """
    import json

    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    for top in ("localities", "miejscowosci"):
        if top in data:
            data = data[top]
            break
    places = data
    return MultiLocalityResolver(places, default_locality=default_locality)


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
        gaz_map = {k: (tuple(v) if isinstance(v, (list, tuple)) and len(v) == 2 else None)
               for k, v in data.items()}
    else:
        gaz_map = {}
        for item in data:
            if isinstance(item, str):
                gaz_map[item] = None
            elif isinstance(item, dict):
                nm = item.get("name") or item.get("nazwa")
                if nm:
                    lat, lon = item.get("lat"), item.get("lon")
                    gaz_map[nm] = (float(lat), float(lon)) if lat is not None and lon is not None else None
    return LocationResolver(gaz_map)


def geocode_frame(df, resolver, *, column: str = "location_text",
                  overwrite: bool = False, station_code_column: Optional[str] = None):
    """Resolve the place descriptions of a frame and write the result back to it.

    Returns a copy of ``df`` with ``coordinates`` filled as ``"lat,lon"`` (WGS84, the
    format the schema validates) and three diagnostic columns that keep what the resolver
    knows about each row: ``_geo_confidence`` (certainty of the name identification),
    ``_geo_accuracy`` (precision of the returned point) and ``_geo_reason`` (reason, when
    no point is returned). Coordinates disclosed by the publisher are kept unless
    ``overwrite=True``; such rows get ``_geo_confidence = "ZRODLO"``.

    ``resolver`` is a :class:`LocationResolver` or :class:`MultiLocalityResolver`, for
    example from :func:`resolver_from_gazetteer_json`. ``station_code_column`` names a boolean
    column marking descriptions that are station codes rather than place names.
    """
    import pandas as pd

    out = df.copy()
    if "coordinates" not in out.columns:
        out["coordinates"] = None
    src = out["coordinates"]
    have = src.notna() & src.astype(str).str.strip().ne("") & ~overwrite
    conf, acc_level, reason_, coords = [], [], [], []
    codes = out[station_code_column].fillna(False).astype(bool) \
        if station_code_column and station_code_column in out.columns else None
    for i, (idx, q) in enumerate(out[column].items()):
        if bool(have.loc[idx]):
            conf.append("SOURCE"); acc_level.append("SOURCE"); reason_.append(""); coords.append(src.loc[idx])
            continue
        kw = {"is_station_code": bool(codes.loc[idx])} if codes is not None else {}
        r = resolver.resolve(None if pd.isna(q) else str(q), **kw)
        conf.append(r.confidence)
        acc_level.append(getattr(r, "accuracy", "NO_POINT"))
        has_pt = r.lat is not None and r.lon is not None
        reason_.append(r.reason or ("" if has_pt else "no_point"))
        coords.append(f"{r.lat:.6f},{r.lon:.6f}" if has_pt else None)
    out["coordinates"] = pd.Series(coords, index=out.index, dtype=object)
    out["_geo_confidence"] = conf
    out["_geo_accuracy"] = acc_level
    out["_geo_reason"] = reason_
    return out
