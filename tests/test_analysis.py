"""Tests of the analytical layer: node loading and time with censoring."""

import pandas as pd
import pytest

from gridqueue import (assign_to_nodes, kaplan_meier, node_loading,
                       normalize_name, processing_time, station_node_map)


def _node(nr, name, stations, capacity, direction="wytworcza"):
    return {"_encja": "WEZEL", "_nr_grupy": nr, "_kierunek": direction,
            "id_wezla": f"g{nr}:{direction}", "nazwa_wezla": name,
            "lokalizacja_tekst": stations, "moc_dostepna": capacity,
            "poziom_napiecia": "110 kV", "publikujacy": "X",
            "status_procesu": None, "moc_wprowadzana": None, "moc_pobierana": None}


def _application(loc, capacity, status="WARUNKI_WYDANE"):
    return {"_encja": "WNIOSEK", "_nr_grupy": None, "_kierunek": None,
            "id_wezla": None, "nazwa_wezla": None, "lokalizacja_tekst": loc,
            "moc_dostepna": None, "poziom_napiecia": "110 kV", "publikujacy": "X",
            "status_procesu": status, "moc_wprowadzana": capacity, "moc_pobierana": None}


class TestNormalization:
    def test_the_barred_l_does_not_cut_the_word_in_two(self):
        """NFKD does not decompose 'ł'; without an explicit substitution the word would break at a space."""
        assert normalize_name("Białogard") == "bialogard"
        assert normalize_name("Łęczyca") == "leczyca"
        assert normalize_name("Kołobrzeg 6 Dywizji") == "kolobrzeg 6 dywizji"

    def test_a_designation_prefix_carries_no_identity(self):
        assert normalize_name("GPZ Kościerzyna") == normalize_name("Kościerzyna")
        assert normalize_name("SE Dunowo") == normalize_name("Dunowo")


class TestMapping:
    def test_the_group_not_the_row_is_the_key(self):
        """The same group in two directions is one object, not two."""
        df = pd.DataFrame([
            _node(1, "Alfa", "Stacja A, Stacja B", 1000.0, "wytworcza"),
            _node(1, "Alfa", "Stacja A, Stacja B", 2000.0, "odbiorcza"),
        ])
        mapping = station_node_map(df)
        assert mapping["group"].nunique() == 1
        assert len(mapping) == 2  # two stations, not four

    def test_an_object_on_a_line_is_not_assigned_to_a_node(self):
        """A station planned on a line lies BETWEEN nodes, so any assignment would be arbitrary."""
        df = pd.DataFrame([
            _node(1, "Alfa", "Stacja A", 1000.0),
            _application("planowany RS w linii 110 kV relacji Stacja A - Stacja C", 50.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        wn = out[out["_encja"] == "WNIOSEK"].iloc[0]
        assert wn["_group_match"] == "LINE"
        assert pd.isna(wn["_group"])

    def test_a_station_in_two_groups_is_ambiguous(self):
        df = pd.DataFrame([
            _node(1, "Alfa", "Ostrów", 1000.0),
            _node(2, "Beta", "Ostrów", 1000.0),
            _application("GPZ Ostrów", 10.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        assert out.iloc[-1]["_group_match"] == "AMBIGUOUS"
        assert pd.isna(out.iloc[-1]["_group"])


class TestLoading:
    def test_the_ratio_and_the_direction(self):
        df = pd.DataFrame([
            _node(1, "Alfa", "Stacja A", 100.0, "wytworcza"),
            _node(1, "Alfa", "Stacja A", 400.0, "odbiorcza"),
            _application("Stacja A", 250.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, capacity_field="moc_wprowadzana")
        assert len(L) == 1
        assert L.iloc[0]["loading"] == pytest.approx(2.5)
        assert L.iloc[0]["direction"] == "wytworcza"

    def test_zero_capacity_gives_an_undefined_not_an_infinite_result(self):
        """Division by zero in this domain does not mean 'infinitely much'."""
        df = pd.DataFrame([
            _node(1, "Alfa", "Stacja A", 0.0),
            _application("Stacja A", 10.0),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, capacity_field="moc_wprowadzana")
        assert bool(L.iloc[0]["available_capacity_zero"]) is True
        assert pd.isna(L.iloc[0]["loading"])
        assert L.iloc[0]["capacity_requested"] == 10.0  # the queue stays visible despite the absence of capacity

    def test_a_closed_status_does_not_load_the_node(self):
        df = pd.DataFrame([
            _node(1, "Alfa", "Stacja A", 100.0),
            _application("Stacja A", 50.0, status="ODMOWA"),
        ])
        out = assign_to_nodes(df, station_node_map(df))
        L = node_loading(out, capacity_field="moc_wprowadzana")
        assert L.iloc[0]["capacity_requested"] == 0.0


class TestTimeAndCensoring:
    def _frame(self):
        return pd.DataFrame([
            {"data_wniosku": "2026-01-01", "data_warunkow": "2026-01-31"},
            {"data_wniosku": "2026-01-01", "data_warunkow": None},
            {"data_wniosku": None, "data_warunkow": None},
            {"data_wniosku": "2026-03-01", "data_warunkow": "2026-02-01"},
        ])

    def test_a_pending_application_is_a_censored_observation_not_a_gap(self):
        d = processing_time(self._frame(), as_at="2026-06-30")
        assert d.loc[0, "event"] == 1 and d.loc[0, "time_days"] == 30
        assert d.loc[1, "event"] == 0 and d.loc[1, "time_days"] == 180
        assert pd.isna(d.loc[2, "event"])  # with no application date there is nothing to compute
        assert pd.isna(d.loc[3, "time_days"])   # a backdated value is rejected

    def test_dropping_the_censored_observations_lowers_the_median(self):
        """The property this function exists for."""
        time = [10, 20, 30, 400, 400, 400]
        ev = [1, 1, 1, 0, 0, 0]
        km = kaplan_meier(time, ev)
        complete = pd.Series([10, 20, 30]).median()
        assert km.censored == 3
        assert pd.isna(km.median) or km.median >= complete

    def test_km_without_censoring_gives_the_empirical_median(self):
        km = kaplan_meier([5, 10, 15, 20], [1, 1, 1, 1])
        assert km.median == 10  # the first time at which S <= 0.5
        assert km.events == 4 and km.censored == 0

    def test_an_empty_frame_raises_no_exception(self):
        km = kaplan_meier([], [])
        assert km.n == 0 and pd.isna(km.median)
