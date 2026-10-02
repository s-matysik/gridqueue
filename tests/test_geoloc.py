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


def test_normalize_i_tokens():
    assert normalize("Świętego Wincentego") == "swietego wincentego"
    assert tokens("ul. Świętego Wincentego 12") == ["wincentego"]


def test_exact(r):
    res = r.resolve("WARSZAWA, Grochowska")
    assert res.pewnosc == "EXACT"
    assert res.matched == "Grochowska"
    assert res.lat == 52.24 and res.lon == 21.09
    assert res.rozwiazane


def test_unique_token(r):
    res = r.resolve("Warszawa, al. Jerozolimskie 100")
    assert res.pewnosc in {"UNIQUE_TOKEN", "TOKEN_SUBSET"}
    assert res.matched == "Aleje Jerozolimskie"


def test_reversed_z_inicjalem(r):
    res = r.resolve("Warszawa, BEMA J.")
    assert res.pewnosc in {"UNIQUE_TOKEN", "REVERSED"}
    assert res.matched == "Józefa Bema"


def test_reversed_ze_skrotem_tytulu(r):
    res = r.resolve("Warszawa, WINCENTEGO ŚW.")
    assert res.pewnosc in {"UNIQUE_TOKEN", "REVERSED"}
    assert res.matched == "Świętego Wincentego"


def test_kod_stacji_nie_jest_zgadywany(r):
    res = r.resolve("SKB3")
    assert res.pewnosc == "NONE"
    assert res.powod == "kod_stacji_bez_slownika"
    assert res.matched is None


def test_kod_stacji_wymuszony_flaga(r):
    res = r.resolve("Grochowska", is_station_code=True)
    assert res.pewnosc == "NONE"
    assert res.powod == "kod_stacji_bez_slownika"


def test_pusty_opis(r):
    assert r.resolve(None).powod == "pusty_opis"
    assert r.resolve("   ").powod == "pusty_opis"


def test_brak_kandydatow(r):
    res = r.resolve("Warszawa, Nieistniejąca")
    assert res.pewnosc == "NONE"
    assert res.powod in {"brak_kandydatow", "wiele_kandydatow"}


def test_summarize_liczy_odsetek(r):
    rs = r.resolve_series(["Warszawa, Grochowska", "SKB3", "Warszawa, Nieistniejąca"])
    s = LocationResolver.summarize(rs)
    assert s["n"] == 3
    assert s["rozwiazane"] == 1
    assert abs(s["odsetek_rozwiazanych"] - 1 / 3) < 1e-6
    assert s["per_pewnosc"]["EXACT"] == 1
    assert s["powody_braku"]["kod_stacji_bez_slownika"] == 1


def test_skrzyzowanie(r):
    res = r.resolve("Warszawa, Marszałkowska/Nowy Świat")
    assert res.pewnosc == "SKRZYZOWANIE"
    assert res.matched is not None and "/" in res.matched
    assert res.rozwiazane


def test_skrzyzowanie_wymaga_dwoch_czlonow(r):
    res = r.resolve("Warszawa, Nieistniejąca/Takze Nieistniejąca")
    assert res.pewnosc == "NONE"
