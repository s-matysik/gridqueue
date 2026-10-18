"""Tests of the resolver extension with coordinates and an accuracy level."""

import pytest

from gridqueue.geoloc import (
    DOKLADNOSC,
    LocationResolver,
    MultiLocalityResolver,
    Resolution,
)

# gazetteer in its extended form: an entry carries a point, a length and an axis
GAZ_WAW = {
    "Grochowska": {"lat": 52.24, "lon": 21.09, "dlugosc_m": 5200.0,
                   "os": [[52.245, 21.05], [52.235, 21.13]]},
    "Marszałkowska": {"lat": 52.22, "lon": 21.012, "dlugosc_m": 3000.0,
                      "os": [[52.205, 21.012], [52.240, 21.012]]},
    "Świętokrzyska": {"lat": 52.235, "lon": 21.01, "dlugosc_m": 1500.0,
                      "os": [[52.235, 20.995], [52.235, 21.030]]},
    # an entry with NO geometry: the name is resolvable, the point is not there
    "Bezgeometryczna": None,
}
GAZ_PIASECZNO = {
    "Grochowska": {"lat": 52.07, "lon": 21.03, "dlugosc_m": 400.0},
    "Puławska": {"lat": 52.08, "lon": 21.02, "dlugosc_m": 900.0},
}

MIEJSC = {
    "WARSZAWA": {"nazwa": "Warszawa", "lat": 52.2319, "lon": 21.0067, "ulice": GAZ_WAW},
    "PIASECZNO": {"nazwa": "Piaseczno", "lat": 52.0747, "lon": 21.0271, "ulice": GAZ_PIASECZNO},
    "SĘKOCIN NOWY": {"nazwa": "Sękocin Nowy", "lat": 52.1172, "lon": 20.8928, "ulice": {}},
    "SĘKOCIN STARY": {"nazwa": "Sękocin Stary", "lat": 52.1124, "lon": 20.8814, "ulice": {}},
}


@pytest.fixture
def mr():
    return MultiLocalityResolver(MIEJSC)


# --- the accuracy level is a separate field ------------------------------

def test_the_accuracy_comes_from_a_controlled_vocabulary(mr):
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.dokladnosc in DOKLADNOSC


def test_a_point_on_the_street_axis(mr):
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.pewnosc == "EXACT"
    assert r.dokladnosc == "PUNKT_NA_OSI_ULICY"
    assert (r.lat, r.lon) == (52.24, 21.09)
    assert r.ma_wspolrzedne and r.rozwiazane
    assert r.dlugosc_ulicy_m == 5200.0


def test_confidence_and_accuracy_are_independent(mr):
    """EXACT on a long street does not mean an exact point; the blur is explicit."""
    dluga = mr.resolve("WARSZAWA, Grochowska")
    krotka = mr.resolve("PIASECZNO, Puławska")
    assert dluga.pewnosc == krotka.pewnosc == "EXACT"
    assert dluga.dokladnosc == krotka.dokladnosc == "PUNKT_NA_OSI_ULICY"
    assert dluga.dlugosc_ulicy_m > krotka.dlugosc_ulicy_m


# --- the distinction: no name vs no geometry -----------------------------

def test_a_name_resolved_without_geometry(mr):
    r = mr.resolve("WARSZAWA, Bezgeometryczna")
    assert r.rozwiazane is True           # the name has been identified
    assert r.ma_wspolrzedne is False      # but there is no point
    assert r.dokladnosc == "BRAK_GEOMETRII"
    assert r.powod == "nazwa_rozwiazana_bez_geometrii"


def test_an_unresolved_name_is_a_different_state_than_missing_geometry(mr):
    r = mr.resolve("WARSZAWA, Nieistniejąca")
    assert r.rozwiazane is False
    assert r.ma_wspolrzedne is False
    assert r.dokladnosc == "BRAK"
    assert r.powod != "nazwa_rozwiazana_bez_geometrii"


# --- the principle: a gap with a reason instead of a guess ---------------

def test_a_station_code_is_still_not_guessed(mr):
    r = mr.resolve("SKB3")
    assert r.pewnosc == "NONE" and r.powod == "kod_stacji_bez_slownika"
    assert r.lat is None and r.lon is None


def test_a_short_street_name_in_capitals_is_not_a_station_code():
    """Regression: in "WARSZAWA, MARSA" the street member matches the station code pattern.

    A station code is decided on the FULL description; the member after the comma
    is by definition a street name.  Measured: 25 false gaps on 1,236 rows.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"nazwa": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "ulice": {"Marsa": {"lat": 52.25, "lon": 21.13, "dlugosc_m": 2000.0}}}})
    r = m.resolve("WARSZAWA, MARSA")
    assert r.pewnosc == "EXACT" and r.matched == "Marsa"
    assert r.ma_wspolrzedne
    # and the station code on its own is still rejected
    assert m.resolve("SKB3").powod == "kod_stacji_bez_slownika"


def test_a_locality_outside_the_gazetteer_is_a_separate_reason(mr):
    r = mr.resolve("KRAKÓW, Grochowska")
    assert r.pewnosc == "NONE"
    assert r.powod == "miejscowosc_poza_gazeterem"
    assert r.lat is None


def test_the_same_name_in_two_localities_is_not_conflated(mr):
    """Separation of name spaces: 'Grochowska' exists in both and gives different points."""
    a = mr.resolve("WARSZAWA, Grochowska")
    b = mr.resolve("PIASECZNO, Grochowska")
    assert a.pewnosc == b.pewnosc == "EXACT"
    assert (a.lat, a.lon) != (b.lat, b.lon)


def test_an_ambiguous_locality_is_not_settled_at_random(mr):
    """'SĘKOCIN' matches both Nowy and Stary: an explicit gap, not a hit-or-miss choice."""
    r = mr.resolve("SĘKOCIN, Jakakolwiek")
    assert r.pewnosc == "NONE"
    assert r.powod.startswith("miejscowosc_niejednoznaczna")
    assert r.lat is None


def test_with_no_declared_locality_it_does_not_guess(mr):
    """A description with no locality member is not matched against a city gazetteer.

    A regression measured on the panel: when a default locality was substituted,
    the TAURON descriptions "Stacja projektowana" matched the Warsaw street
    "ul. Projektowana", and "Wrzoski (planowany)" matched the road feature
    "planowany łącznik": 21 false resolutions on 11,649 rows of publishers with
    no locality member.
    """
    for opis in ["Stacja projektowana", "Wrzoski (planowany)", "Langage B"]:
        r = mr.resolve(opis)
        assert r.pewnosc == "NONE", opis
        assert r.powod == "brak_deklaracji_miejscowosci"
        assert r.lat is None and r.lon is None


def test_the_default_locality_works_when_it_is_switched_on_explicitly():
    m = MultiLocalityResolver(MIEJSC, domyslna="WARSZAWA")
    r = m.resolve("Grochowska")
    assert r.pewnosc == "EXACT" and r.ma_wspolrzedne


def test_the_locality_centroid_only_on_an_explicit_request(mr):
    bez = mr.resolve("PIASECZNO, Nieistniejąca")
    assert bez.lat is None
    z = mr.resolve("PIASECZNO, Nieistniejąca", dopusc_centroid=True)
    assert z.dokladnosc == "CENTROID_MIEJSCOWOSCI"
    assert (z.lat, z.lon) == (52.0747, 21.0271)
    assert z.rozwiazane is False          # the street name is still unresolved


# --- intersection: the crossing point of the axes ------------------------

def test_an_intersection_gives_the_crossing_point_of_the_axes(mr):
    r = mr.resolve("WARSZAWA, Marszałkowska/Świętokrzyska")
    assert r.pewnosc == "SKRZYZOWANIE"
    assert r.dokladnosc == "PUNKT_SKRZYZOWANIA"
    # axes: Marszałkowska lon=21.012 (vertical), Świętokrzyska lat=52.235 (horizontal)
    assert abs(r.lat - 52.235) < 1e-3
    assert abs(r.lon - 21.012) < 1e-3


# --- the house number is not interpolated --------------------------------

def test_a_house_number_without_an_index_is_not_guessed(mr):
    r = mr.resolve("WARSZAWA, Grochowska", numer="12")
    assert r.dokladnosc == "PUNKT_NA_OSI_ULICY"   # NOT PUNKT_ADRESOWY
    assert (r.lat, r.lon) == (52.24, 21.09)


def test_a_house_number_with_an_index_of_address_points(mr):
    res_waw = mr.resolvery["warszawa"]
    res_waw.punkty_adresowe = {("grochowska", "12"): (52.2411, 21.0912)}
    r = mr.resolve("WARSZAWA, Grochowska", numer="12")
    assert r.dokladnosc == "PUNKT_ADRESOWY"
    assert (r.lat, r.lon) == (52.2411, 21.0912)
    del res_waw.punkty_adresowe


# --- token coverage threshold: a verbal description is not a street name -

def test_a_verbal_description_is_not_matched_to_a_street():
    """Measured on the panel: "Bezpośrednie sąsiedztwo Lotniska Chopina w Warszawie"
    matched "Fryderyka Chopina" through the token "chopina" alone, so the point
    fell in the city centre instead of next to the airport.  1 false resolution
    on 1,218.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"nazwa": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "ulice": {"Fryderyka Chopina": {"lat": 52.2228, "lon": 21.0221,
                                                     "dlugosc_m": 700.0}}}})
    r = m.resolve("WARSZAWA, Bezpośrednie sąsiedztwo Lotniska Chopina w Warszawie")
    assert r.pewnosc == "NONE"
    assert r.powod == "opis_slowny_nie_nazwa_ulicy"
    assert r.lat is None


def test_the_coverage_threshold_does_not_cut_off_the_later_strategies():
    """A rejection by the threshold has to pass the description on to the intersection rule.

    Regression: "SOBIESKIEGO JANA III/ IDZIKOWSKIEGO" has 4 tokens, so the
    threshold applies; the token "idzikowskiego" is unique and explains 1 of the
    4 tokens. Returning a gap immediately lost the correct intersection.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"nazwa": "Warszawa", "lat": 52.23, "lon": 21.0, "ulice": {
            "Jana III Sobieskiego": {"lat": 52.20, "lon": 21.05, "dlugosc_m": 2000.0,
                                     "os": [[52.19, 21.05], [52.21, 21.05]]},
            "Ludwika Idzikowskiego": {"lat": 52.20, "lon": 21.04, "dlugosc_m": 900.0,
                                      "os": [[52.20, 21.03], [52.20, 21.07]]}}}})
    r = m.resolve("WARSZAWA, SOBIESKIEGO JANA III/ IDZIKOWSKIEGO")
    assert r.pewnosc == "SKRZYZOWANIE"
    assert r.dokladnosc == "PUNKT_SKRZYZOWANIA"


def test_a_short_description_is_not_subject_to_the_threshold(mr):
    """The threshold applies only to descriptions of 4 tokens or more; short descriptions are street names."""
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.pewnosc == "EXACT" and r.ma_wspolrzedne


# --- ambiguity of a name within one locality -----------------------------

def test_the_spread_of_the_components_is_reported():
    """A street name repeated in several parts of a city: the point lies on the
    longest component, and the spread of the components is returned as an
    explicit measure of risk. Statutory registers do not give the district, so
    this cannot be settled.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"nazwa": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "ulice": {"Leśna": {"lat": 52.24, "lon": 21.22, "dlugosc_m": 1800.0,
                                         "n_skladowych": 3,
                                         "rozrzut_skladowych_m": 25993.4}}}})
    r = m.resolve("WARSZAWA, Leśna")
    assert r.ma_wspolrzedne
    assert r.n_skladowych == 3
    assert r.rozrzut_skladowych_m == 25993.4


# --- backward compatibility ----------------------------------------------

def test_the_old_short_format_gazetteer_works():
    r = LocationResolver({"Grochowska": (52.24, 21.09)})
    res = r.resolve("WARSZAWA, Grochowska")
    assert (res.lat, res.lon) == (52.24, 21.09)
    assert res.dokladnosc == "PUNKT_NA_OSI_ULICY"


def test_the_old_gazetteer_without_coordinates_works():
    r = LocationResolver({"Grochowska": None})
    res = r.resolve("WARSZAWA, Grochowska")
    assert res.pewnosc == "EXACT" and res.lat is None
    assert res.dokladnosc == "BRAK_GEOMETRII"


# --- summary -------------------------------------------------------------

def test_summarize_separates_the_resolved_from_those_with_coordinates(mr):
    rs = mr.resolve_series([
        "WARSZAWA, Grochowska",          # EXACT + point
        "WARSZAWA, Bezgeometryczna",     # EXACT without a point
        "SKB3",                          # station code
        "KRAKÓW, Grochowska",            # outside the gazetteer
    ])
    s = MultiLocalityResolver.summarize(rs)
    assert s["n"] == 4
    assert s["rozwiazane"] == 2
    assert s["ze_wspolrzednymi"] == 1
    assert s["per_dokladnosc"]["PUNKT_NA_OSI_ULICY"] == 1
    assert s["per_dokladnosc"]["BRAK_GEOMETRII"] == 1
    assert s["powody_braku"]["kod_stacji_bez_slownika"] == 1
    assert s["powody_braku"]["miejscowosc_poza_gazeterem"] == 1
