import pytest

from gridqueue.geoloc import LocationResolver, normalize, tokens

GAZ = {
    "Grochowska": (52.24, 21.09),
    "Świętego Wincentego": (52.28, 21.06),
    "Józefa Bema": (52.23, 20.98),
    "Marszałkowska": (52.22, 21.01),
    "Aleje Jerozolimskie": (52.22, 21.00),
    "Puławska": (52.15, 21.02),
    "Nowy Świat": (52.23, 21.02),
}


@pytest.fixture
def r():
    return LocationResolver(GAZ)


def test_normalize_and_tokens():
    assert normalize("Świętego Wincentego") == "swietego wincentego"
    assert tokens("ul. Świętego Wincentego 12") == ["wincentego"]


def test_exact(r):
    res = r.resolve("WARSZAWA, Grochowska")
    assert res.confidence == "EXACT"
    assert res.matched == "Grochowska"
    assert res.lat == 52.24 and res.lon == 21.09
    assert res.resolved


def test_unique_token(r):
    res = r.resolve("Warszawa, al. Jerozolimskie 100")
    assert res.confidence in {"UNIQUE_TOKEN", "TOKEN_SUBSET"}
    assert res.matched == "Aleje Jerozolimskie"


def test_reversed_with_initial(r):
    res = r.resolve("Warszawa, BEMA J.")
    assert res.confidence in {"UNIQUE_TOKEN", "REVERSED"}
    assert res.matched == "Józefa Bema"


def test_reversed_with_title_abbreviation(r):
    res = r.resolve("Warszawa, WINCENTEGO ŚW.")
    assert res.confidence in {"UNIQUE_TOKEN", "REVERSED"}
    assert res.matched == "Świętego Wincentego"


def test_station_code_is_not_guessed(r):
    res = r.resolve("SKB3")
    assert res.confidence == "NONE"
    assert res.reason == "kod_stacji_bez_slownika"
    assert res.matched is None


def test_station_code_forced_by_a_flag(r):
    res = r.resolve("Grochowska", is_station_code=True)
    assert res.confidence == "NONE"
    assert res.reason == "kod_stacji_bez_slownika"


def test_empty_description(r):
    assert r.resolve(None).reason == "pusty_opis"
    assert r.resolve("   ").reason == "pusty_opis"


def test_no_candidates(r):
    res = r.resolve("Warszawa, Nieistniejąca")
    assert res.confidence == "NONE"
    assert res.reason in {"brak_kandydatow", "wiele_kandydatow"}


def test_summarize_computes_the_share(r):
    rs = r.resolve_series(["Warszawa, Grochowska", "SKB3", "Warszawa, Nieistniejąca"])
    s = LocationResolver.summarize(rs)
    assert s["n"] == 3
    assert s["resolved"] == 1
    assert abs(s["resolved_share"] - 1 / 3) < 1e-6
    assert s["per_confidence"]["EXACT"] == 1
    assert s["missing_reasons"]["kod_stacji_bez_slownika"] == 1


def test_intersection(r):
    res = r.resolve("Warszawa, Marszałkowska/Nowy Świat")
    assert res.confidence == "SKRZYZOWANIE"
    assert res.matched is not None and "/" in res.matched
    assert res.resolved


def test_intersection_requires_two_members(r):
    res = r.resolve("Warszawa, Nieistniejąca/Takze Nieistniejąca")
    assert res.confidence == "NONE"
