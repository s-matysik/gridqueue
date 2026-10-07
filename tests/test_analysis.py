"""Testy warstwy analitycznej: obciążenie węzła i czas z cenzurowaniem."""

import pandas as pd
import pytest

from gridqueue import (assign_to_nodes, kaplan_meier, node_loading,
                       normalizuj_nazwe, processing_time, station_node_map)


def _wezel(nr, nazwa, stacje, moc, kierunek="wytworcza"):
    return {"_encja": "WEZEL", "_nr_grupy": nr, "_kierunek": kierunek,
            "id_wezla": f"g{nr}:{kierunek}", "nazwa_wezla": nazwa,
            "lokalizacja_tekst": stacje, "moc_dostepna": moc,
            "poziom_napiecia": "110 kV", "publikujacy": "X",
            "status_procesu": None, "moc_wprowadzana": None, "moc_pobierana": None}


def _wniosek(lok, moc, status="WARUNKI_WYDANE"):
    return {"_encja": "WNIOSEK", "_nr_grupy": None, "_kierunek": None,
            "id_wezla": None, "nazwa_wezla": None, "lokalizacja_tekst": lok,
            "moc_dostepna": None, "poziom_napiecia": "110 kV", "publikujacy": "X",
            "status_procesu": status, "moc_wprowadzana": moc, "moc_pobierana": None}


class TestNormalizacja:
    def test_litera_l_z_kreska_nie_rozcina_wyrazu(self):
        """NFKD nie rozkłada 'ł' — bez jawnej podmiany wyraz pękłby na spacji."""
        assert normalizuj_nazwe("Białogard") == "bialogard"
        assert normalizuj_nazwe("Łęczyca") == "leczyca"
        assert normalizuj_nazwe("Kołobrzeg 6 Dywizji") == "kolobrzeg 6 dywizji"

    def test_przedrostek_oznaczenia_nie_niesie_tozsamosci(self):
        assert normalizuj_nazwe("GPZ Kościerzyna") == normalizuj_nazwe("Kościerzyna")
        assert normalizuj_nazwe("SE Dunowo") == normalizuj_nazwe("Dunowo")


class TestOdwzorowanie:
    def test_grupa_a_nie_wiersz_jest_kluczem(self):
        """Ta sama grupa w dwóch kierunkach to jeden obiekt, nie dwa."""
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A, Stacja B", 1000.0, "wytworcza"),
            _wezel(1, "Alfa", "Stacja A, Stacja B", 2000.0, "odbiorcza"),
        ])
        mapa = station_node_map(df)
        assert mapa["grupa"].nunique() == 1
        assert len(mapa) == 2  # dwie stacje, nie cztery

    def test_obiekt_na_linii_nie_jest_przypisywany_do_wezla(self):
        """Stacja planowana na linii leży MIĘDZY węzłami — przypisanie byłoby arbitralne."""
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A", 1000.0),
            _wniosek("planowany RS w linii 110 kV relacji Stacja A - Stacja C", 50.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        wn = out[out["_encja"] == "WNIOSEK"].iloc[0]
        assert wn["_grupa_dopasowanie"] == "LINE"
        assert pd.isna(wn["_grupa"])

    def test_stacja_w_dwoch_grupach_jest_niejednoznaczna(self):
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Ostrów", 1000.0),
            _wezel(2, "Beta", "Ostrów", 1000.0),
            _wniosek("GPZ Ostrów", 10.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        assert out.iloc[-1]["_grupa_dopasowanie"] == "AMBIGUOUS"
        assert pd.isna(out.iloc[-1]["_grupa"])


class TestObciazenie:
    def test_iloraz_i_kierunek(self):
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A", 100.0, "wytworcza"),
            _wezel(1, "Alfa", "Stacja A", 400.0, "odbiorcza"),
            _wniosek("Stacja A", 250.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, pole_mocy="moc_wprowadzana")
        assert len(L) == 1
        assert L.iloc[0]["obciazenie"] == pytest.approx(2.5)
        assert L.iloc[0]["kierunek"] == "wytworcza"

    def test_zerowa_moc_daje_wynik_nieokreslony_a_nie_nieskonczony(self):
        """Dzielenie przez zero w tej dziedzinie nie znaczy 'nieskończenie dużo'."""
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A", 0.0),
            _wniosek("Stacja A", 10.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, pole_mocy="moc_wprowadzana")
        assert bool(L.iloc[0]["moc_dostepna_zero"]) is True
        assert pd.isna(L.iloc[0]["obciazenie"])
        assert L.iloc[0]["moc_wnioskowana"] == 10.0  # kolejka widoczna mimo braku mocy

    def test_status_zakonczony_nie_obciaza_wezla(self):
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A", 100.0),
            _wniosek("Stacja A", 50.0, status="ODMOWA"),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, pole_mocy="moc_wprowadzana")
        assert L.iloc[0]["moc_wnioskowana"] == 0.0


class TestCzasICenzurowanie:
    def _ramka(self):
        return pd.DataFrame([
            {"data_wniosku": "2026-01-01", "data_warunkow": "2026-01-31"},
            {"data_wniosku": "2026-01-01", "data_warunkow": None},
            {"data_wniosku": None, "data_warunkow": None},
            {"data_wniosku": "2026-03-01", "data_warunkow": "2026-02-01"},
        ])

    def test_wniosek_w_toku_jest_obserwacja_uciets_nie_brakiem(self):
        d = processing_time(self._ramka(), na_dzien="2026-06-30")
        assert d.loc[0, "zdarzenie"] == 1 and d.loc[0, "czas_dni"] == 30
        assert d.loc[1, "zdarzenie"] == 0 and d.loc[1, "czas_dni"] == 180
        assert pd.isna(d.loc[2, "zdarzenie"])  # bez daty wniosku nie ma czego liczyć
        assert pd.isna(d.loc[3, "czas_dni"])   # data wsteczna odrzucona

    def test_pominiecie_cenzurowanych_zanizza_mediane(self):
        """Właściwość, dla której ta funkcja istnieje."""
        czas = [10, 20, 30, 400, 400, 400]
        zdarz = [1, 1, 1, 0, 0, 0]
        km = kaplan_meier(czas, zdarz)
        kompletne = pd.Series([10, 20, 30]).median()
        assert km.cenzurowanych == 3
        assert pd.isna(km.mediana) or km.mediana >= kompletne

    def test_km_bez_cenzurowania_daje_mediane_empiryczna(self):
        km = kaplan_meier([5, 10, 15, 20], [1, 1, 1, 1])
        assert km.mediana == 10  # pierwszy czas, dla którego S <= 0,5
        assert km.zdarzen == 4 and km.cenzurowanych == 0

    def test_pusta_ramka_nie_rzuca_wyjatku(self):
        km = kaplan_meier([], [])
        assert km.n == 0 and pd.isna(km.mediana)
