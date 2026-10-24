"""Tests of the resolver extension with coordinates and an accuracy level."""

import pytest

from gridqueue.geoloc import (
    ACCURACY,
    LocationResolver,
    MultiLocalityResolver,
    Resolution,
)

# gazetteer in its extended form: an entry carries a point, a length and an axis
GAZETTEER_WAW = {
    "Grochowska": {"lat": 52.24, "lon": 21.09, "length_m": 5200.0,
                   "axis": [[52.245, 21.05], [52.235, 21.13]]},
    "Marszałkowska": {"lat": 52.22, "lon": 21.012, "length_m": 3000.0,
                      "axis": [[52.205, 21.012], [52.240, 21.012]]},
    "Świętokrzyska": {"lat": 52.235, "lon": 21.01, "length_m": 1500.0,
                      "axis": [[52.235, 20.995], [52.235, 21.030]]},
    # an entry with NO geometry: the name is resolvable, the point is not there
    "Bezgeometryczna": None,
}
GAZETTEER_PIASECZNO = {
    "Grochowska": {"lat": 52.07, "lon": 21.03, "length_m": 400.0},
    "Puławska": {"lat": 52.08, "lon": 21.02, "length_m": 900.0},
}

LOCALITIES = {
    "WARSZAWA": {"name": "Warszawa", "lat": 52.2319, "lon": 21.0067, "streets": GAZETTEER_WAW},
    "PIASECZNO": {"name": "Piaseczno", "lat": 52.0747, "lon": 21.0271, "streets": GAZETTEER_PIASECZNO},
    "SĘKOCIN NOWY": {"name": "Sękocin Nowy", "lat": 52.1172, "lon": 20.8928, "streets": {}},
    "SĘKOCIN STARY": {"name": "Sękocin Stary", "lat": 52.1124, "lon": 20.8814, "streets": {}},
}


@pytest.fixture
def mr():
    return MultiLocalityResolver(LOCALITIES)


# --- the accuracy level is a separate field ------------------------------

def test_the_accuracy_comes_from_a_controlled_vocabulary(mr):
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.accuracy in ACCURACY


def test_a_point_on_the_street_axis(mr):
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.confidence == "EXACT"
    assert r.accuracy == "STREET_AXIS_POINT"
    assert (r.lat, r.lon) == (52.24, 21.09)
    assert r.has_coordinates and r.resolved
    assert r.street_length_m == 5200.0


def test_confidence_and_accuracy_are_independent(mr):
    """EXACT on a long street does not mean an exact point; the blur is explicit."""
    long = mr.resolve("WARSZAWA, Grochowska")
    short_res = mr.resolve("PIASECZNO, Puławska")
    assert long.confidence == short_res.confidence == "EXACT"
    assert long.accuracy == short_res.accuracy == "STREET_AXIS_POINT"
    assert long.street_length_m > short_res.street_length_m


# --- the distinction: no name vs no geometry -----------------------------

def test_a_name_resolved_without_geometry(mr):
    r = mr.resolve("WARSZAWA, Bezgeometryczna")
    assert r.resolved is True           # the name has been identified
    assert r.has_coordinates is False      # but there is no point
    assert r.accuracy == "NO_GEOMETRY"
    assert r.reason == "name_resolved_without_geometry"


def test_an_unresolved_name_is_a_different_state_than_missing_geometry(mr):
    r = mr.resolve("WARSZAWA, Nieistniejąca")
    assert r.resolved is False
    assert r.has_coordinates is False
    assert r.accuracy == "NO_POINT"
    assert r.reason != "name_resolved_without_geometry"


# --- the principle: a gap with a reason instead of a guess ---------------

def test_a_station_code_is_still_not_guessed(mr):
    r = mr.resolve("SKB3")
    assert r.confidence == "NONE" and r.reason == "station_code_without_dictionary"
    assert r.lat is None and r.lon is None


def test_a_short_street_name_in_capitals_is_not_a_station_code():
    """Regression: in "WARSZAWA, MARSA" the street member matches the station code pattern.

    A station code is decided on the FULL description; the member after the comma
    is by definition a street name.  Measured: 25 false gaps on 1,236 rows.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"name": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "streets": {"Marsa": {"lat": 52.25, "lon": 21.13, "length_m": 2000.0}}}})
    r = m.resolve("WARSZAWA, MARSA")
    assert r.confidence == "EXACT" and r.matched == "Marsa"
    assert r.has_coordinates
    # and the station code on its own is still rejected
    assert m.resolve("SKB3").reason == "station_code_without_dictionary"


def test_a_locality_outside_the_gazetteer_is_a_separate_reason(mr):
    r = mr.resolve("KRAKÓW, Grochowska")
    assert r.confidence == "NONE"
    assert r.reason == "locality_not_in_gazetteer"
    assert r.lat is None


def test_the_same_name_in_two_localities_is_not_conflated(mr):
    """Separation of name spaces: 'Grochowska' exists in both and gives different points."""
    a = mr.resolve("WARSZAWA, Grochowska")
    b = mr.resolve("PIASECZNO, Grochowska")
    assert a.confidence == b.confidence == "EXACT"
    assert (a.lat, a.lon) != (b.lat, b.lon)


def test_an_ambiguous_locality_is_not_settled_at_random(mr):
    """'SĘKOCIN' matches both Nowy and Stary: an explicit gap, not a hit-or-miss choice."""
    r = mr.resolve("SĘKOCIN, Jakakolwiek")
    assert r.confidence == "NONE"
    assert r.reason.startswith("ambiguous_locality")
    assert r.lat is None


def test_with_no_declared_locality_it_does_not_guess(mr):
    """A description with no locality member is not matched against a city gazetteer.

    A regression measured on the panel: when a default locality was substituted,
    the TAURON descriptions "Stacja projektowana" matched the Warsaw street
    "ul. Projektowana", and "Wrzoski (planowany)" matched the road feature
    "planowany łącznik": 21 false resolutions on 11,649 rows of publishers with
    no locality member.
    """
    for description in ["Stacja projektowana", "Wrzoski (planowany)", "Langage B"]:
        r = mr.resolve(description)
        assert r.confidence == "NONE", description
        assert r.reason == "no_locality_declared"
        assert r.lat is None and r.lon is None


def test_the_default_locality_works_when_it_is_switched_on_explicitly():
    m = MultiLocalityResolver(LOCALITIES, default_locality="WARSZAWA")
    r = m.resolve("Grochowska")
    assert r.confidence == "EXACT" and r.has_coordinates


def test_the_locality_centroid_only_on_an_explicit_request(mr):
    without = mr.resolve("PIASECZNO, Nieistniejąca")
    assert without.lat is None
    z = mr.resolve("PIASECZNO, Nieistniejąca", allow_centroid=True)
    assert z.accuracy == "LOCALITY_CENTROID"
    assert (z.lat, z.lon) == (52.0747, 21.0271)
    assert z.resolved is False          # the street name is still unresolved


# --- intersection: the crossing point of the axes ------------------------

def test_an_intersection_gives_the_crossing_point_of_the_axes(mr):
    r = mr.resolve("WARSZAWA, Marszałkowska/Świętokrzyska")
    assert r.confidence == "INTERSECTION"
    assert r.accuracy == "INTERSECTION_POINT"
    # axes: Marszałkowska lon=21.012 (vertical), Świętokrzyska lat=52.235 (horizontal)
    assert abs(r.lat - 52.235) < 1e-3
    assert abs(r.lon - 21.012) < 1e-3


# --- the house number is not interpolated --------------------------------

def test_a_house_number_without_an_index_is_not_guessed(mr):
    r = mr.resolve("WARSZAWA, Grochowska", number="12")
    assert r.accuracy == "STREET_AXIS_POINT"   # NOT PUNKT_ADRESOWY
    assert (r.lat, r.lon) == (52.24, 21.09)


def test_a_house_number_with_an_index_of_address_points(mr):
    res_waw = mr.resolvers["warszawa"]
    res_waw.address_points = {("grochowska", "12"): (52.2411, 21.0912)}
    r = mr.resolve("WARSZAWA, Grochowska", number="12")
    assert r.accuracy == "ADDRESS_POINT"
    assert (r.lat, r.lon) == (52.2411, 21.0912)
    del res_waw.address_points


# --- token coverage threshold: a verbal description is not a street name -

def test_a_verbal_description_is_not_matched_to_a_street():
    """Measured on the panel: "Bezpośrednie sąsiedztwo Lotniska Chopina w Warszawie"
    matched "Fryderyka Chopina" through the token "chopina" alone, so the point
    fell in the city centre instead of next to the airport.  1 false resolution
    on 1,218.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"name": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "streets": {"Fryderyka Chopina": {"lat": 52.2228, "lon": 21.0221,
                                                     "length_m": 700.0}}}})
    r = m.resolve("WARSZAWA, Bezpośrednie sąsiedztwo Lotniska Chopina w Warszawie")
    assert r.confidence == "NONE"
    assert r.reason == "verbal_description_not_street_name"
    assert r.lat is None


def test_the_coverage_threshold_does_not_cut_off_the_later_strategies():
    """A rejection by the threshold has to pass the description on to the intersection rule.

    Regression: "SOBIESKIEGO JANA III/ IDZIKOWSKIEGO" has 4 tokens, so the
    threshold applies; the token "idzikowskiego" is unique and explains 1 of the
    4 tokens. Returning a gap immediately lost the correct intersection.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"name": "Warszawa", "lat": 52.23, "lon": 21.0, "streets": {
            "Jana III Sobieskiego": {"lat": 52.20, "lon": 21.05, "length_m": 2000.0,
                                     "axis": [[52.19, 21.05], [52.21, 21.05]]},
            "Ludwika Idzikowskiego": {"lat": 52.20, "lon": 21.04, "length_m": 900.0,
                                      "axis": [[52.20, 21.03], [52.20, 21.07]]}}}})
    r = m.resolve("WARSZAWA, SOBIESKIEGO JANA III/ IDZIKOWSKIEGO")
    assert r.confidence == "INTERSECTION"
    assert r.accuracy == "INTERSECTION_POINT"


def test_a_short_description_is_not_subject_to_the_threshold(mr):
    """The threshold applies only to descriptions of 4 tokens or more; short descriptions are street names."""
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.confidence == "EXACT" and r.has_coordinates


# --- ambiguity of a name within one locality -----------------------------

def test_the_spread_of_the_components_is_reported():
    """A street name repeated in several parts of a city: the point lies on the
    longest component, and the spread of the components is returned as an
    explicit measure of risk. Statutory registers do not give the district, so
    this cannot be settled.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"name": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "streets": {"Leśna": {"lat": 52.24, "lon": 21.22, "length_m": 1800.0,
                                         "n_components": 3,
                                         "components_spread_m": 25993.4}}}})
    r = m.resolve("WARSZAWA, Leśna")
    assert r.has_coordinates
    assert r.n_components == 3
    assert r.components_spread_m == 25993.4


# --- backward compatibility ----------------------------------------------

def test_the_old_short_format_gazetteer_works():
    r = LocationResolver({"Grochowska": (52.24, 21.09)})
    res = r.resolve("WARSZAWA, Grochowska")
    assert (res.lat, res.lon) == (52.24, 21.09)
    assert res.accuracy == "STREET_AXIS_POINT"


def test_the_old_gazetteer_without_coordinates_works():
    r = LocationResolver({"Grochowska": None})
    res = r.resolve("WARSZAWA, Grochowska")
    assert res.confidence == "EXACT" and res.lat is None
    assert res.accuracy == "NO_GEOMETRY"


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
    assert s["resolved"] == 2
    assert s["with_coordinates"] == 1
    assert s["per_accuracy"]["STREET_AXIS_POINT"] == 1
    assert s["per_accuracy"]["NO_GEOMETRY"] == 1
    assert s["missing_reasons"]["station_code_without_dictionary"] == 1
    assert s["missing_reasons"]["locality_not_in_gazetteer"] == 1


def test_a_gazetteer_with_the_keys_of_the_first_drafts_is_read(tmp_path):
    import json

    from gridqueue import resolver_from_gazetteer_json

    legacy = {"miejscowosci": {"WARSZAWA": {"nazwa": "Warszawa", "lat": 52.23, "lon": 21.01,
              "ulice": {"Grochowska": {"lat": 52.24, "lon": 21.09, "dlugosc_m": 5200.0,
                                       "os": [[52.24, 21.08], [52.25, 21.10]]}}}}}
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps(legacy), encoding="utf-8")
    r = resolver_from_gazetteer_json(p).resolve("WARSZAWA, ul. Grochowska")
    assert r.matched == "Grochowska" and r.street_length_m == 5200.0
