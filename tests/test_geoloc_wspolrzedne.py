"""Testy rozszerzenia rozwiązywacza o współrzędne i poziom dokładności."""

import pytest

from gridqueue.geoloc import (
    DOKLADNOSC,
    LocationResolver,
    MultiLocalityResolver,
    Resolution,
)

# gazeter w postaci rozszerzonej: wpis niesie punkt, długość i oś
GAZ_WAW = {
    "Grochowska": {"lat": 52.24, "lon": 21.09, "dlugosc_m": 5200.0,
                   "os": [[52.245, 21.05], [52.235, 21.13]]},
    "Marszałkowska": {"lat": 52.22, "lon": 21.012, "dlugosc_m": 3000.0,
                      "os": [[52.205, 21.012], [52.240, 21.012]]},
    "Świętokrzyska": {"lat": 52.235, "lon": 21.01, "dlugosc_m": 1500.0,
                      "os": [[52.235, 20.995], [52.235, 21.030]]},
    # wpis BEZ geometrii -- nazwa rozwiązywalna, punktu nie ma
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


# --- poziom dokładności jest osobnym polem -------------------------------

def test_dokladnosc_jest_z_kontrolowanego_slownika(mr):
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.dokladnosc in DOKLADNOSC


def test_punkt_na_osi_ulicy(mr):
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.pewnosc == "EXACT"
    assert r.dokladnosc == "PUNKT_NA_OSI_ULICY"
    assert (r.lat, r.lon) == (52.24, 21.09)
    assert r.ma_wspolrzedne and r.rozwiazane
    assert r.dlugosc_ulicy_m == 5200.0


def test_pewnosc_i_dokladnosc_sa_niezalezne(mr):
    """EXACT na długiej ulicy nie oznacza dokładnego punktu -- rozmycie jest jawne."""
    dluga = mr.resolve("WARSZAWA, Grochowska")
    krotka = mr.resolve("PIASECZNO, Puławska")
    assert dluga.pewnosc == krotka.pewnosc == "EXACT"
    assert dluga.dokladnosc == krotka.dokladnosc == "PUNKT_NA_OSI_ULICY"
    assert dluga.dlugosc_ulicy_m > krotka.dlugosc_ulicy_m


# --- rozróżnienie: brak nazwy vs brak geometrii --------------------------

def test_nazwa_rozwiazana_bez_geometrii(mr):
    r = mr.resolve("WARSZAWA, Bezgeometryczna")
    assert r.rozwiazane is True           # nazwa zidentyfikowana
    assert r.ma_wspolrzedne is False      # ale punktu nie ma
    assert r.dokladnosc == "BRAK_GEOMETRII"
    assert r.powod == "nazwa_rozwiazana_bez_geometrii"


def test_nazwa_nierozwiazana_to_inny_stan_niz_brak_geometrii(mr):
    r = mr.resolve("WARSZAWA, Nieistniejąca")
    assert r.rozwiazane is False
    assert r.ma_wspolrzedne is False
    assert r.dokladnosc == "BRAK"
    assert r.powod != "nazwa_rozwiazana_bez_geometrii"


# --- zasada: brak z przyczyną zamiast zgadywania -------------------------

def test_kod_stacji_nadal_nie_jest_zgadywany(mr):
    r = mr.resolve("SKB3")
    assert r.pewnosc == "NONE" and r.powod == "kod_stacji_bez_slownika"
    assert r.lat is None and r.lon is None


def test_krotka_nazwa_ulicy_wersalikami_nie_jest_kodem_stacji():
    """Regresja: "WARSZAWA, MARSA" -- człon ulicy pasuje do wzorca kodu stacji.

    Kod stacji jest rozstrzygany na PEŁNYM opisie; człon po przecinku jest z
    definicji nazwą ulicy.  Zmierzone: 25 fałszywych braków na 1 236 wierszach.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"nazwa": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "ulice": {"Marsa": {"lat": 52.25, "lon": 21.13, "dlugosc_m": 2000.0}}}})
    r = m.resolve("WARSZAWA, MARSA")
    assert r.pewnosc == "EXACT" and r.matched == "Marsa"
    assert r.ma_wspolrzedne
    # a sam kod stacji nadal jest odrzucany
    assert m.resolve("SKB3").powod == "kod_stacji_bez_slownika"


def test_miejscowosc_poza_gazeterem_jest_osobnym_powodem(mr):
    r = mr.resolve("KRAKÓW, Grochowska")
    assert r.pewnosc == "NONE"
    assert r.powod == "miejscowosc_poza_gazeterem"
    assert r.lat is None


def test_ta_sama_nazwa_w_dwoch_miejscowosciach_nie_jest_mieszana(mr):
    """Rozdzielenie przestrzeni nazw: 'Grochowska' istnieje w obu i daje różne punkty."""
    a = mr.resolve("WARSZAWA, Grochowska")
    b = mr.resolve("PIASECZNO, Grochowska")
    assert a.pewnosc == b.pewnosc == "EXACT"
    assert (a.lat, a.lon) != (b.lat, b.lon)


def test_niejednoznaczna_miejscowosc_nie_jest_rozstrzygana_losowo(mr):
    """'SĘKOCIN' pasuje do Nowego i Starego -- jawny brak, nie wybór na chybił trafił."""
    r = mr.resolve("SĘKOCIN, Jakakolwiek")
    assert r.pewnosc == "NONE"
    assert r.powod.startswith("miejscowosc_niejednoznaczna")
    assert r.lat is None


def test_bez_zadeklarowanej_miejscowosci_nie_zgaduje(mr):
    """Opis bez członu miejscowości nie jest dopasowywany do gazetera miasta.

    Regresja zmierzona na panelu: przy podstawianiu domyślnej miejscowości opisy
    TAURONA "Stacja projektowana" trafiały w warszawską "ul. Projektowana",
    a "Wrzoski (planowany)" w drogowe "planowany łącznik" -- 21 fałszywych
    rozwiązań na 11 649 wierszy publikujących bez członu miejscowości.
    """
    for opis in ["Stacja projektowana", "Wrzoski (planowany)", "Langage B"]:
        r = mr.resolve(opis)
        assert r.pewnosc == "NONE", opis
        assert r.powod == "brak_deklaracji_miejscowosci"
        assert r.lat is None and r.lon is None


def test_domyslna_miejscowosc_dziala_gdy_jawnie_wlaczona():
    m = MultiLocalityResolver(MIEJSC, domyslna="WARSZAWA")
    r = m.resolve("Grochowska")
    assert r.pewnosc == "EXACT" and r.ma_wspolrzedne


def test_centroid_miejscowosci_tylko_na_jawne_zadanie(mr):
    bez = mr.resolve("PIASECZNO, Nieistniejąca")
    assert bez.lat is None
    z = mr.resolve("PIASECZNO, Nieistniejąca", dopusc_centroid=True)
    assert z.dokladnosc == "CENTROID_MIEJSCOWOSCI"
    assert (z.lat, z.lon) == (52.0747, 21.0271)
    assert z.rozwiazane is False          # nazwa ulicy nadal nierozwiązana


# --- skrzyżowanie: punkt przecięcia osi ----------------------------------

def test_skrzyzowanie_daje_punkt_przeciecia_osi(mr):
    r = mr.resolve("WARSZAWA, Marszałkowska/Świętokrzyska")
    assert r.pewnosc == "SKRZYZOWANIE"
    assert r.dokladnosc == "PUNKT_SKRZYZOWANIA"
    # osie: Marszałkowska lon=21.012 (pion), Świętokrzyska lat=52.235 (poziom)
    assert abs(r.lat - 52.235) < 1e-3
    assert abs(r.lon - 21.012) < 1e-3


# --- numer domu nie jest interpolowany ----------------------------------

def test_numer_domu_bez_indeksu_nie_jest_zgadywany(mr):
    r = mr.resolve("WARSZAWA, Grochowska", numer="12")
    assert r.dokladnosc == "PUNKT_NA_OSI_ULICY"   # NIE PUNKT_ADRESOWY
    assert (r.lat, r.lon) == (52.24, 21.09)


def test_numer_domu_z_indeksem_punktow_adresowych(mr):
    res_waw = mr.resolvery["warszawa"]
    res_waw.punkty_adresowe = {("grochowska", "12"): (52.2411, 21.0912)}
    r = mr.resolve("WARSZAWA, Grochowska", numer="12")
    assert r.dokladnosc == "PUNKT_ADRESOWY"
    assert (r.lat, r.lon) == (52.2411, 21.0912)
    del res_waw.punkty_adresowe


# --- próg pokrycia tokenów: opis słowny nie jest nazwą ulicy -------------

def test_opis_slowny_nie_jest_dopasowywany_do_ulicy():
    """Zmierzone na panelu: "Bezpośrednie sąsiedztwo Lotniska Chopina w Warszawie"
    trafiało w "Fryderyka Chopina" przez sam token "chopina" -- punkt wypadał
    w Śródmieściu zamiast przy lotnisku.  1 fałszywe rozwiązanie na 1 218.
    """
    m = MultiLocalityResolver({
        "WARSZAWA": {"nazwa": "Warszawa", "lat": 52.23, "lon": 21.0,
                     "ulice": {"Fryderyka Chopina": {"lat": 52.2228, "lon": 21.0221,
                                                     "dlugosc_m": 700.0}}}})
    r = m.resolve("WARSZAWA, Bezpośrednie sąsiedztwo Lotniska Chopina w Warszawie")
    assert r.pewnosc == "NONE"
    assert r.powod == "opis_slowny_nie_nazwa_ulicy"
    assert r.lat is None


def test_prog_pokrycia_nie_przerywa_dalszych_strategii():
    """Odrzucenie po progu musi przepuścić opis do reguły skrzyżowań.

    Regresja: "SOBIESKIEGO JANA III/ IDZIKOWSKIEGO" ma 4 tokeny, więc próg się
    stosuje; token "idzikowskiego" jest unikalny i wyjaśnia 1 z 4 tokenów.
    Natychmiastowy zwrot braku gubił poprawne skrzyżowanie.
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


def test_krotki_opis_nie_podlega_progowi(mr):
    """Próg dotyczy tylko opisów od 4 tokenów -- krótkie opisy to nazwy ulic."""
    r = mr.resolve("WARSZAWA, Grochowska")
    assert r.pewnosc == "EXACT" and r.ma_wspolrzedne


# --- niejednoznaczność nazwy w obrębie miejscowości ----------------------

def test_rozrzut_skladowych_jest_raportowany():
    """Nazwa ulicy powtórzona w kilku częściach miasta: punkt leży na najdłuższej
    składowej, a rozrzut składowych jest zwracany jako jawna miara ryzyka.
    Rejestry ustawowe nie podają dzielnicy, więc tego nie da się rozstrzygnąć.
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


# --- zgodność wstecz -----------------------------------------------------

def test_stary_gazeter_krotkiego_formatu_dziala():
    r = LocationResolver({"Grochowska": (52.24, 21.09)})
    res = r.resolve("WARSZAWA, Grochowska")
    assert (res.lat, res.lon) == (52.24, 21.09)
    assert res.dokladnosc == "PUNKT_NA_OSI_ULICY"


def test_stary_gazeter_bez_wspolrzednych_dziala():
    r = LocationResolver({"Grochowska": None})
    res = r.resolve("WARSZAWA, Grochowska")
    assert res.pewnosc == "EXACT" and res.lat is None
    assert res.dokladnosc == "BRAK_GEOMETRII"


# --- podsumowanie --------------------------------------------------------

def test_summarize_rozdziela_rozwiazane_od_ze_wspolrzednymi(mr):
    rs = mr.resolve_series([
        "WARSZAWA, Grochowska",          # EXACT + punkt
        "WARSZAWA, Bezgeometryczna",     # EXACT bez punktu
        "SKB3",                          # kod stacji
        "KRAKÓW, Grochowska",            # poza gazeterem
    ])
    s = MultiLocalityResolver.summarize(rs)
    assert s["n"] == 4
    assert s["rozwiazane"] == 2
    assert s["ze_wspolrzednymi"] == 1
    assert s["per_dokladnosc"]["PUNKT_NA_OSI_ULICY"] == 1
    assert s["per_dokladnosc"]["BRAK_GEOMETRII"] == 1
    assert s["powody_braku"]["kod_stacji_bez_slownika"] == 1
    assert s["powody_braku"]["miejscowosc_poza_gazeterem"] == 1
