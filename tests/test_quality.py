import pandas as pd

from gridqueue.quality import RULES, run_quality


def test_jest_osiem_regul_i_kazda_ma_podstawe():
    assert len(RULES) == 8
    assert {r.kod for r in RULES} == {f"R{i}" for i in range(1, 9)}
    for r in RULES:
        assert r.podstawa


def test_r1_monotonicznosc_dat():
    df = pd.DataFrame({
        "data_wniosku": ["2026-01-01", "2026-05-01"],
        "data_warunkow": ["2026-02-01", "2026-04-01"],   # drugi wiersz odwrócony
        "data_umowy": ["2026-03-01", None],
        "data_energizacji": [None, None],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R1")).as_dict()
    assert rep["reguly"][0]["naruszenia"] == 1
    assert rep["reguly"][0]["szczegoly"]["pary"]["data_wniosku>data_warunkow"] == 1


def test_r2_dwuletnia_waznosc_warunkow():
    df = pd.DataFrame({
        "data_warunkow": ["2022-01-01", "2024-01-01"],
        "_data_utraty_waznosci": ["2025-06-01", "2026-01-01"],  # pierwszy > 2 lata
        "data_umowy": [None, None],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R2")).as_dict()
    d = rep["reguly"][0]["szczegoly"]
    assert d["utrata_waznosci_pozniej_niz_2_lata"] == 1
    assert d["sprawdzonych_dat_utraty"] == 2


def test_r3_status_wobec_dat():
    df = pd.DataFrame({
        "status_procesu": ["ODMOWA", "ODMOWA", "PRZYLACZONY"],
        "data_odmowy": ["2026-01-01", None, None],
        "data_umowy": [None, None, None],
        "data_energizacji": [None, None, "2026-02-01"],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R3")).as_dict()
    assert rep["reguly"][0]["naruszenia"] == 1


def test_r4_spojnosc_jednostek_wykrywa_mw_zamiast_kw():
    df = pd.DataFrame({"moc_pobierana": [700.0, 0.7, 0.0, None]})
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R4")).as_dict()
    assert rep["reguly"][0]["naruszenia"] == 1
    assert rep["reguly"][0]["szczegoly"]["per_pole"]["moc_pobierana"] == 1


def test_r5_zakresy_wartosci():
    df = pd.DataFrame({"data_wniosku": ["1900-01-01", "2026-01-01"],
                       "moc_pobierana": [-5.0, 10.0]})
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R5")).as_dict()
    assert rep["reguly"][0]["naruszenia"] == 1


def test_r6_duplikaty():
    df = pd.DataFrame({"id_wniosku": ["a", "a", "a", "b"]})
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R6")).as_dict()
    assert rep["reguly"][0]["naruszenia"] == 2
    assert rep["reguly"][0]["szczegoly"]["n_unikalnych"] == 2
    assert rep["reguly"][0]["szczegoly"]["max_krotnosc"] == 3


def test_r7_kompletnosc_rdzenia():
    df = pd.DataFrame({
        "id_wniosku": ["a", "b"], "lokalizacja_tekst": ["x", None],
        "klasa_zasobu": ["PV", "PV"], "moc_pobierana": [1.0, 2.0],
        "status_procesu": ["ODMOWA", "ODMOWA"],
    })
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R7")).as_dict()
    assert rep["reguly"][0]["naruszenia"] == 1


def test_r8_slownik_kontrolowany():
    df = pd.DataFrame({"klasa_zasobu": ["PV", "PANELE"], "status_procesu": ["ODMOWA", "ODMOWA"]})
    rep = run_quality(df, tuple(r for r in RULES if r.kod == "R8")).as_dict()
    assert rep["reguly"][0]["naruszenia"] == 1


def test_reguly_nie_rzucaja_na_pustej_ramce():
    rep = run_quality(pd.DataFrame()).as_dict()
    assert rep["n_wierszy"] == 0
    assert all(r["naruszenia"] >= 0 for r in rep["reguly"])


def test_r7_nie_karze_wniosku_wytworczego_za_brak_mocy_pobieranej():
    """R7 mierzy braki ujawnienia, nie własność schematu.

    Przed wersją 1.0 rdzeń wymagał `moc_pobierana` bezwarunkowo, więc każdy
    wniosek czysto wytwórczy był liczony jako naruszenie. Tu pinujemy nowy
    kontrakt: naruszeniem jest brak JAKIEJKOLWIEK mocy.
    """
    import pandas as pd

    wspolny = {"id_wniosku": "X", "lokalizacja_tekst": "Szczecin",
               "klasa_zasobu": "FW", "status_procesu": "WARUNKI_WYDANE"}
    df = pd.DataFrame([
        {**wspolny, "moc_wprowadzana": 3000.0, "moc_pobierana": None},
        {**wspolny, "moc_wprowadzana": None, "moc_pobierana": None},
    ])
    r7 = [x for x in run_quality(df).as_dict()["reguly"] if x["kod"] == "R7"][0]
    assert r7["naruszenia"] == 1
    klucz = "WNIOSEK/co najmniej jedno z: moc_pobierana, moc_wprowadzana"
    assert r7["szczegoly"]["per_pole"][klucz] == 1


def test_r7_ocenia_wezel_wymaganiami_wezla():
    import pandas as pd

    from gridqueue.schema import ENTITY_COLUMN

    df = pd.DataFrame([
        {ENTITY_COLUMN: "WEZEL", "id_wezla": "SE-1", "moc_dostepna": 0.0},
        {ENTITY_COLUMN: "WEZEL", "id_wezla": "SE-2"},
    ])
    r7 = [x for x in run_quality(df).as_dict()["reguly"] if x["kod"] == "R7"][0]
    assert r7["naruszenia"] == 1
    assert r7["szczegoly"]["wierszy_encji"] == {"WEZEL": 2}


def test_as_frame_zwraca_wiersz_na_regule():
    """Dokumentacja obiecywala te metode, a pakiet jej nie mial.

    Defekt wyszedl dopiero przy uruchomieniu notatnika Colab, ktory korzystal
    z publicznego API tak, jak opisuje je dokumentacja.
    """
    import pandas as pd

    from gridqueue import RULES, run_quality

    df = pd.DataFrame([{"id_wniosku": "A", "lokalizacja_tekst": "Szczecin",
                        "klasa_zasobu": "FW", "status_procesu": "WARUNKI_WYDANE",
                        "moc_wprowadzana": 1000.0}])
    ramka = run_quality(df).as_frame()
    assert list(ramka.columns) == ["kod", "nazwa", "naruszenia", "udzial"]
    assert len(ramka) == len(RULES)
    assert ramka["udzial"].between(0, 1).all()
