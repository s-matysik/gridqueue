"""Tests of the analytical layer: node loading and time with censoring."""

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


class TestNormalization:
    def test_the_barred_l_does_not_cut_the_word_in_two(self):
        """NFKD does not decompose 'ł'; without an explicit substitution the word would break at a space."""
        assert normalizuj_nazwe("Białogard") == "bialogard"
        assert normalizuj_nazwe("Łęczyca") == "leczyca"
        assert normalizuj_nazwe("Kołobrzeg 6 Dywizji") == "kolobrzeg 6 dywizji"

    def test_a_designation_prefix_carries_no_identity(self):
        assert normalizuj_nazwe("GPZ Kościerzyna") == normalizuj_nazwe("Kościerzyna")
        assert normalizuj_nazwe("SE Dunowo") == normalizuj_nazwe("Dunowo")


class TestMapping:
    def test_the_group_not_the_row_is_the_key(self):
        """The same group in two directions is one object, not two."""
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A, Stacja B", 1000.0, "wytworcza"),
            _wezel(1, "Alfa", "Stacja A, Stacja B", 2000.0, "odbiorcza"),
        ])
        mapa = station_node_map(df)
        assert mapa["grupa"].nunique() == 1
        assert len(mapa) == 2  # two stations, not four

    def test_an_object_on_a_line_is_not_assigned_to_a_node(self):
        """A station planned on a line lies BETWEEN nodes, so any assignment would be arbitrary."""
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A", 1000.0),
            _wniosek("planowany RS w linii 110 kV relacji Stacja A - Stacja C", 50.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        wn = out[out["_encja"] == "WNIOSEK"].iloc[0]
        assert wn["_grupa_dopasowanie"] == "LINE"
        assert pd.isna(wn["_grupa"])

    def test_a_station_in_two_groups_is_ambiguous(self):
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Ostrów", 1000.0),
            _wezel(2, "Beta", "Ostrów", 1000.0),
            _wniosek("GPZ Ostrów", 10.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        assert out.iloc[-1]["_grupa_dopasowanie"] == "AMBIGUOUS"
        assert pd.isna(out.iloc[-1]["_grupa"])


class TestLoading:
    def test_the_ratio_and_the_direction(self):
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

    def test_zero_capacity_gives_an_undefined_not_an_infinite_result(self):
        """Division by zero in this domain does not mean 'infinitely much'."""
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A", 0.0),
            _wniosek("Stacja A", 10.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, pole_mocy="moc_wprowadzana")
        assert bool(L.iloc[0]["moc_dostepna_zero"]) is True
        assert pd.isna(L.iloc[0]["obciazenie"])
        assert L.iloc[0]["moc_wnioskowana"] == 10.0  # the queue stays visible despite the absence of capacity

    def test_a_closed_status_does_not_load_the_node(self):
        df = pd.DataFrame([
            _wezel(1, "Alfa", "Stacja A", 100.0),
            _wniosek("Stacja A", 50.0, status="ODMOWA"),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, pole_mocy="moc_wprowadzana")
        assert L.iloc[0]["moc_wnioskowana"] == 0.0


class TestTimeAndCensoring:
    def _ramka(self):
        return pd.DataFrame([
            {"data_wniosku": "2026-01-01", "data_warunkow": "2026-01-31"},
            {"data_wniosku": "2026-01-01", "data_warunkow": None},
            {"data_wniosku": None, "data_warunkow": None},
            {"data_wniosku": "2026-03-01", "data_warunkow": "2026-02-01"},
        ])

    def test_a_pending_application_is_a_censored_observation_not_a_gap(self):
        d = processing_time(self._ramka(), na_dzien="2026-06-30")
        assert d.loc[0, "zdarzenie"] == 1 and d.loc[0, "czas_dni"] == 30
        assert d.loc[1, "zdarzenie"] == 0 and d.loc[1, "czas_dni"] == 180
        assert pd.isna(d.loc[2, "zdarzenie"])  # with no application date there is nothing to compute
        assert pd.isna(d.loc[3, "czas_dni"])   # a backdated value is rejected

    def test_dropping_the_censored_observations_lowers_the_median(self):
        """The property this function exists for."""
        czas = [10, 20, 30, 400, 400, 400]
        zdarz = [1, 1, 1, 0, 0, 0]
        km = kaplan_meier(czas, zdarz)
        kompletne = pd.Series([10, 20, 30]).median()
        assert km.cenzurowanych == 3
        assert pd.isna(km.mediana) or km.mediana >= kompletne

    def test_km_without_censoring_gives_the_empirical_median(self):
        km = kaplan_meier([5, 10, 15, 20], [1, 1, 1, 1])
        assert km.mediana == 10  # the first time at which S <= 0.5
        assert km.zdarzen == 4 and km.cenzurowanych == 0

    def test_an_empty_frame_raises_no_exception(self):
        km = kaplan_meier([], [])
        assert km.n == 0 and pd.isna(km.mediana)
