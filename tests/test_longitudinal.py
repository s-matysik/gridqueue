"""Testy porównania edycji i wielokrotnych komórek mocy."""

import pandas as pd
import pytest

from gridqueue import compare_editions, surrogate_key
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
