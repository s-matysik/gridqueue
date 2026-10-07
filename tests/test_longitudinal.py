"""Testy porównania edycji i wielokrotnych komórek mocy."""

import pandas as pd
import pytest

from gridqueue import (compare_editions, linkage_audit, linkage_recall,
                       surrogate_key)
from gridqueue.adapters._ptpiree import _rozbij_moc


def _wiersz(**kw):
    baza = {"publikujacy": "PSE S.A.", "lokalizacja_tekst": "Kromolice",
            "poziom_napiecia": "400 kV", "klasa_zasobu": "BESS",
            "moc_wprowadzana": 1000.0, "moc_pobierana": 1000.0,
            "status_procesu": "W_TRAKCIE_ANALIZY"}
    baza.update(kw)
    return baza


class TestRozbijMoc:
    """Wiele miejsc przyłączenia w jednej komórce."""

    def test_zlamanie_linii_daje_skladowe(self):
        assert _rozbij_moc("129\n240") == ["129", "240"]

    def test_srednik_i_zlamanie_linii_razem(self):
        assert _rozbij_moc("129; \n240") == ["129", "240"]

    def test_trzy_skladowe(self):
        assert _rozbij_moc("27; \n45; \n21") == ["27", "45", "21"]

    def test_nie_rozbija_po_spacji(self):
        """Spacja jest u publikujących separatorem TYSIĘCZNYM, nie rozdzielaczem."""
        assert _rozbij_moc("129 240") == ["129 240"]

    def test_liczba_zwykla_to_jedna_skladowa(self):
        assert _rozbij_moc(1830.0) == ["1830.0"]

    def test_kreska_i_pustka_odrzucone(self):
        assert _rozbij_moc("-") == []
        assert _rozbij_moc(None) == []

    def test_regresja_sklejenia_trzech_rzedow_wielkosci(self):
        """Pinuje defekt z wersji 1.0: "129⏎240" sklejało się w 129 240 MW.

        Przyczyną było zamienianie złamania linii na spację przed konwersją,
        a spacja jest traktowana jako separator tysięczny. Poprawne odczytanie
        to dwie składowe sumujące się do 369 MW.
        """
        czesci = _rozbij_moc("129\n240")
        assert sum(float(c) for c in czesci) == 369.0
        assert "".join(czesci) == "129240"  # tak wyglądał błąd


class TestSurrogateKey:
    def test_identyczne_wiersze_daja_ten_sam_klucz(self):
        df = pd.DataFrame([_wiersz(), _wiersz()])
        k = surrogate_key(df)
        assert k.iloc[0] == k.iloc[1]

    def test_zmiana_mocy_rozjezdza_klucz(self):
        df = pd.DataFrame([_wiersz(), _wiersz(moc_pobierana=2000.0)])
        k = surrogate_key(df)
        assert k.iloc[0] != k.iloc[1]

    def test_status_nie_wchodzi_do_klucza(self):
        """Inaczej każda zmiana statusu wyglądałaby jak zniknięcie i pojawienie."""
        df = pd.DataFrame([_wiersz(), _wiersz(status_procesu="WARUNKI_WYDANE")])
        k = surrogate_key(df)
        assert k.iloc[0] == k.iloc[1]

    def test_brak_pol_klucza_jest_bledem(self):
        with pytest.raises(ValueError, match="żadne z pól klucza"):
            surrogate_key(pd.DataFrame({"cos_innego": [1]}), fields=("moc_dostepna",))


class TestCompareEditions:
    def test_przeplywy(self):
        a = pd.DataFrame([_wiersz(lokalizacja_tekst="A"), _wiersz(lokalizacja_tekst="B")])
        b = pd.DataFrame([_wiersz(lokalizacja_tekst="B"), _wiersz(lokalizacja_tekst="C")])
        d = compare_editions(a, b, "lipiec", "sierpien")
        assert (d.wspolnych, d.nowych, d.ubylych) == (1, 1, 1)
        assert d.as_dict()["wierszy_netto"] == 0

    def test_przejscie_w_przod_liczone_jako_w_przod(self):
        a = pd.DataFrame([_wiersz(status_procesu="W_TRAKCIE_ANALIZY")])
        b = pd.DataFrame([_wiersz(status_procesu="WARUNKI_WYDANE")])
        d = compare_editions(a, b)
        assert d.zmian_statusu == 1
        assert d.udzial_przejsc_w_przod == 1.0
        assert d.przejscia_wstecz == 0

    def test_przejscie_wstecz_wykryte(self):
        a = pd.DataFrame([_wiersz(status_procesu="UMOWA_OBOWIAZUJACA")])
        b = pd.DataFrame([_wiersz(status_procesu="WARUNKI_WYDANE")])
        d = compare_editions(a, b)
        assert d.przejscia_wstecz == 1
        assert d.udzial_przejsc_w_przod == 0.0

    def test_odmowa_liczona_jako_zakonczenie_w_przod(self):
        a = pd.DataFrame([_wiersz(status_procesu="W_TRAKCIE_ANALIZY")])
        b = pd.DataFrame([_wiersz(status_procesu="ODMOWA")])
        d = compare_editions(a, b)
        assert d.udzial_przejsc_w_przod == 1.0

    def test_niemonotonicznosc_migawki(self):
        """Nowy wiersz od razu zamknięty i ubyły wiersz czynny — obie flagi."""
        a = pd.DataFrame([_wiersz(lokalizacja_tekst="X", status_procesu="WARUNKI_WYDANE")])
        b = pd.DataFrame([_wiersz(lokalizacja_tekst="Y", status_procesu="WNIOSEK_WYCOFANY")])
        d = compare_editions(a, b).as_dict()
        assert d["nowe_zamkniete"] == 1
        assert d["ubyle_czynne"] == 1
        assert d["migawka_monotoniczna"] is False

    def test_brak_zmian_daje_udzial_none(self):
        a = pd.DataFrame([_wiersz()])
        d = compare_editions(a, a.copy())
        assert d.zmian_statusu == 0
        assert d.udzial_przejsc_w_przod is None


class TestLinkageAudit:
    """Ocena dopasowania na polach WYŁĄCZONYCH z klucza."""

    def _para(self, **zmiany_b):
        a = pd.DataFrame([_wiersz(_podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV Wyszki")])
        b_ = {"_podmiot": "Alfa Sp. z o.o.", "_nazwa_obiektu": "PV Wyszki"}
        b_.update(zmiany_b)
        return a, pd.DataFrame([_wiersz(**b_)])

    def test_zgodne_pola_wstrzymane_daja_potwierdzenie(self):
        a, b = self._para()
        au = linkage_audit(a, b).as_dict()
        assert (au["par"], au["potwierdzonych"], au["falszywych"]) == (1, 1, 0)
        assert au["precyzja_dolna"] == 1.0

    def test_oba_pola_tozsamosci_rozbiezne_to_falszywe_dopasowanie(self):
        a, b = self._para(_podmiot="Beta Sp. z o.o.", _nazwa_obiektu="PV Bulkowo")
        au = linkage_audit(a, b).as_dict()
        assert au["falszywych"] == 1
        assert au["precyzja_gorna"] == 0.0

    def test_jedno_pole_rozbiezne_to_niepewne(self):
        a, b = self._para(_nazwa_obiektu="PV Bulkowo")
        au = linkage_audit(a, b).as_dict()
        assert (au["niepewnych"], au["falszywych"]) == (1, 0)
        assert au["precyzja_dolna"] == 0.0 and au["precyzja_gorna"] == 1.0

    def test_inny_zapis_formy_prawnej_to_ten_sam_podmiot(self):
        """Publikujący zmienia zapis formy prawnej miedzy edycjami."""
        a, b = self._para(_podmiot="Alfa sp.z o.o.")
        au = linkage_audit(a, b).as_dict()
        assert au["potwierdzonych"] == 1

    def test_nazwa_rozszerzona_nie_jest_konfliktem(self):
        a, b = self._para(_nazwa_obiektu="PV Wyszki - zm. WP")
        au = linkage_audit(a, b).as_dict()
        assert au["potwierdzonych"] == 1

    def test_uzupelnienie_jednostronne_nie_jest_konfliktem(self):
        """Puste w jednej edycji, wypelnione w drugiej — to redakcja, nie inny wniosek."""
        a = pd.DataFrame([_wiersz(_podmiot="Alfa Sp. z o.o.", data_wniosku=None)])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa Sp. z o.o.", data_wniosku="2026-07-31")])
        wynik = linkage_audit(a, b)
        assert wynik.as_dict()["potwierdzonych"] == 1
        kat = set(wynik.rozbieznosci["kategoria"])
        assert kat == {"uzupelnienie_jednostronne"}

    def test_granice_precyzji_sie_nie_krzyzuja(self):
        a = pd.DataFrame([_wiersz(lokalizacja_tekst=f"M{i}", _podmiot="Alfa Sp. z o.o.",
                                  _nazwa_obiektu=f"PV {i}") for i in range(4)])
        b = pd.DataFrame([_wiersz(lokalizacja_tekst="M0", _podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV 0"),
                          _wiersz(lokalizacja_tekst="M1", _podmiot="Beta Sp. z o.o.", _nazwa_obiektu="PV X"),
                          _wiersz(lokalizacja_tekst="M2", _podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV Y"),
                          _wiersz(lokalizacja_tekst="M3", _podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV 3")])
        au = linkage_audit(a, b).as_dict()
        assert au["par"] == 4
        assert au["potwierdzonych"] + au["niepewnych"] + au["falszywych"] == 4
        assert au["precyzja_dolna"] <= au["precyzja_gorna"]


class TestKolizjeKlucza:
    def test_kolizje_i_odrzucenia_sa_raportowane(self):
        """Wiersze o powtarzajacym sie kluczu sa odrzucane, a liczba jest jawna."""
        a = pd.DataFrame([_wiersz(), _wiersz(), _wiersz(lokalizacja_tekst="Inna")])
        b = pd.DataFrame([_wiersz()])
        d = compare_editions(a, b).as_dict()
        assert d["wierszy_w_kolizji_a"] == 2
        assert d["odrzuconych_jako_niejednoznaczne_a"] == 1
        assert d["wspolnych"] == 1


class TestZgodnoscZWersjaPandas:
    """Klucz nie moze zalezec od wersji pandas.

    Defekt wykryty przy uruchomieniu notatnika Colab na pandas 3: `.astype(str)`
    zamienialo brak na lancuch "nan" w pandas 2, a w pandas 3 zachowuje wartosc
    brakujaca, wiec zlaczenie skladowych klucza rzucalo TypeError. Klucz buduje
    sie teraz jawna konwersja.
    """

    def test_brak_wartosci_daje_pusty_segment_bez_wyjatku(self):
        import numpy as np
        import pandas as pd

        from gridqueue import surrogate_key

        df = pd.DataFrame([_wiersz(moc_pobierana=np.nan, poziom_napiecia=None)])
        k = surrogate_key(df).iloc[0]
        assert isinstance(k, str)
        assert "nan" not in k.lower(), k
        assert "None" not in k, k

    def test_braki_dopasowuja_sie_do_brakow(self):
        """Wiersz z brakiem laczy sie tylko z wierszem, w ktorym brak tez jest."""
        import numpy as np
        import pandas as pd

        from gridqueue import compare_editions

        a = pd.DataFrame([_wiersz(moc_pobierana=np.nan)])
        b = pd.DataFrame([_wiersz(moc_pobierana=np.nan)])
        c = pd.DataFrame([_wiersz(moc_pobierana=1000.0)])
        assert compare_editions(a, b).wspolnych == 1
        assert compare_editions(a, c).wspolnych == 0


class TestLinkageRecall:
    """Czułość klucza: pary, których klucz treściowy NIE połączył."""

    def test_zmiana_mocy_rozrywa_pare_i_jest_odzyskiwana(self):
        a = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  moc_wprowadzana=1000.0)])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  moc_wprowadzana=1200.0)])
        d = compare_editions(a, b).as_dict()
        assert d["wspolnych"] == 0 and d["nowych"] == 1 and d["ubylych"] == 1

        r = linkage_recall(a, b)
        assert r.odzyskanych == 1
        assert r.odzyskane.iloc[0]["pola_klucza_rozne"] == "moc_wprowadzana"
        assert r.czulosc_klucza == 0.0  # zero par połączonych, jedna możliwa

    def test_pola_tozsamosci_musza_byc_rozlaczne_z_kluczem(self):
        """Pole wspólne z kluczem nie wykryje pary rozerwanej zmianą tego pola."""
        a = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  lokalizacja_tekst="Stacja A")])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  lokalizacja_tekst="Stacja A - pole 12")])
        assert linkage_recall(a, b).odzyskanych == 1
        zepsute = linkage_recall(a, b, pola_tozsamosci=("_podmiot", "lokalizacja_tekst"))
        assert zepsute.odzyskanych == 0

    def test_niejednoznaczna_tozsamosc_nie_jest_odzyskiwana(self):
        a = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=1.0),
                          _wiersz(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=2.0)])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=3.0)])
        assert linkage_recall(a, b).odzyskanych == 0

    def test_zero_jako_brak_jest_wylaczone_domyslnie(self):
        """Zero jest wartością ujawnioną; zrównanie go z brakiem to decyzja analityka."""
        a = pd.DataFrame([_wiersz(moc_pobierana=0.0)])
        b = pd.DataFrame([_wiersz(moc_pobierana=None)])
        assert surrogate_key(a).iloc[0] != surrogate_key(b).iloc[0]
        assert (surrogate_key(a, zero_jako_brak=True).iloc[0]
                == surrogate_key(b, zero_jako_brak=True).iloc[0])
