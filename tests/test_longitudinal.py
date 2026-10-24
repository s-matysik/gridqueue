"""Tests of the edition comparison and of multi-valued capacity cells."""

import pandas as pd
import pytest

from gridqueue import (NODE_KEY_FIELDS, compare_editions, linkage_audit,
                       linkage_recall, surrogate_key)
from gridqueue.adapters._ptpiree import _split_capacity


def _row(**kw):
    base = {"publikujacy": "PSE S.A.", "lokalizacja_tekst": "Kromolice",
            "poziom_napiecia": "400 kV", "klasa_zasobu": "BESS",
            "moc_wprowadzana": 1000.0, "moc_pobierana": 1000.0,
            "status_procesu": "W_TRAKCIE_ANALIZY"}
    base.update(kw)
    return base


class TestSplitCapacity:
    """Several connection points in a single cell."""

    def test_a_line_break_yields_components(self):
        assert _split_capacity("129\n240") == ["129", "240"]

    def test_a_semicolon_and_a_line_break_together(self):
        assert _split_capacity("129; \n240") == ["129", "240"]

    def test_three_components(self):
        assert _split_capacity("27; \n45; \n21") == ["27", "45", "21"]

    def test_it_does_not_split_on_a_space(self):
        """For these publishers a space is a THOUSANDS separator, not a delimiter."""
        assert _split_capacity("129 240") == ["129 240"]

    def test_a_plain_number_is_one_component(self):
        assert _split_capacity(1830.0) == ["1830.0"]

    def test_a_dash_and_an_empty_value_are_rejected(self):
        assert _split_capacity("-") == []
        assert _split_capacity(None) == []

    def test_regression_of_a_three_orders_of_magnitude_merge(self):
        """Pins the defect from version 1.0: "129⏎240" merged into 129,240 MW.

        The cause was replacing the line break with a space before the
        conversion, and a space is treated as a thousands separator. The correct
        reading is two components summing to 369 MW.
        """
        parts = _split_capacity("129\n240")
        assert sum(float(c) for c in parts) == 369.0
        assert "".join(parts) == "129240"  # this is what the defect looked like


class TestSurrogateKey:
    def test_identical_rows_give_the_same_key(self):
        df = pd.DataFrame([_row(), _row()])
        k = surrogate_key(df)
        assert k.iloc[0] == k.iloc[1]

    def test_a_change_of_capacity_pulls_the_key_apart(self):
        df = pd.DataFrame([_row(), _row(moc_pobierana=2000.0)])
        k = surrogate_key(df)
        assert k.iloc[0] != k.iloc[1]

    def test_the_status_does_not_enter_the_key(self):
        """Otherwise every status change would look like a disappearance and an appearance."""
        df = pd.DataFrame([_row(), _row(status_procesu="WARUNKI_WYDANE")])
        k = surrogate_key(df)
        assert k.iloc[0] == k.iloc[1]

    def test_missing_key_fields_are_an_error(self):
        with pytest.raises(ValueError, match="none of the key fields"):
            surrogate_key(pd.DataFrame({"something_else": [1]}), fields=("moc_dostepna",))


class TestCompareEditions:
    def test_the_flows(self):
        a = pd.DataFrame([_row(lokalizacja_tekst="A"), _row(lokalizacja_tekst="B")])
        b = pd.DataFrame([_row(lokalizacja_tekst="B"), _row(lokalizacja_tekst="C")])
        d = compare_editions(a, b, "lipiec", "sierpien")
        assert (d.shared, d.new, d.gone) == (1, 1, 1)
        assert d.as_dict()["net_rows"] == 0

    def test_a_forward_transition_is_counted_as_forward(self):
        a = pd.DataFrame([_row(status_procesu="W_TRAKCIE_ANALIZY")])
        b = pd.DataFrame([_row(status_procesu="WARUNKI_WYDANE")])
        d = compare_editions(a, b)
        assert d.status_changes == 1
        assert d.forward_share == 1.0
        assert d.backward_transitions == 0

    def test_a_backward_transition_is_detected(self):
        a = pd.DataFrame([_row(status_procesu="UMOWA_OBOWIAZUJACA")])
        b = pd.DataFrame([_row(status_procesu="WARUNKI_WYDANE")])
        d = compare_editions(a, b)
        assert d.backward_transitions == 1
        assert d.forward_share == 0.0

    def test_a_refusal_is_counted_as_a_forward_closure(self):
        a = pd.DataFrame([_row(status_procesu="W_TRAKCIE_ANALIZY")])
        b = pd.DataFrame([_row(status_procesu="ODMOWA")])
        d = compare_editions(a, b)
        assert d.forward_share == 1.0

    def test_non_monotonicity_of_the_snapshot(self):
        """A new row already closed and a vanished row still active, both flags."""
        a = pd.DataFrame([_row(lokalizacja_tekst="X", status_procesu="WARUNKI_WYDANE")])
        b = pd.DataFrame([_row(lokalizacja_tekst="Y", status_procesu="WNIOSEK_WYCOFANY")])
        d = compare_editions(a, b).as_dict()
        assert d["new_closed"] == 1
        assert d["gone_active"] == 1
        assert d["monotone_snapshot"] is False

    def test_no_changes_give_a_share_of_none(self):
        a = pd.DataFrame([_row()])
        d = compare_editions(a, a.copy())
        assert d.status_changes == 0
        assert d.forward_share is None


class TestLinkageAudit:
    """Assessment of the linkage on fields EXCLUDED from the key."""

    def _pair(self, **changes_b):
        a = pd.DataFrame([_row(_podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV Wyszki")])
        b_ = {"_podmiot": "Alfa Sp. z o.o.", "_nazwa_obiektu": "PV Wyszki"}
        b_.update(changes_b)
        return a, pd.DataFrame([_row(**b_)])

    def test_matching_held_out_fields_give_a_confirmation(self):
        a, b = self._pair()
        au = linkage_audit(a, b).as_dict()
        assert (au["pairs"], au["confirmed"], au["false_matches"]) == (1, 1, 0)
        assert au["precision_lower"] == 1.0

    def test_both_identity_fields_divergent_means_a_false_linkage(self):
        a, b = self._pair(_podmiot="Beta Sp. z o.o.", _nazwa_obiektu="PV Bulkowo")
        au = linkage_audit(a, b).as_dict()
        assert au["false_matches"] == 1
        assert au["precision_upper"] == 0.0

    def test_one_divergent_field_means_uncertain(self):
        a, b = self._pair(_nazwa_obiektu="PV Bulkowo")
        au = linkage_audit(a, b).as_dict()
        assert (au["uncertain"], au["false_matches"]) == (1, 0)
        assert au["precision_lower"] == 0.0 and au["precision_upper"] == 1.0

    def test_a_different_spelling_of_the_legal_form_is_the_same_entity(self):
        """The publisher changes the spelling of the legal form between editions."""
        a, b = self._pair(_podmiot="Alfa sp.z o.o.")
        au = linkage_audit(a, b).as_dict()
        assert au["confirmed"] == 1

    def test_an_extended_name_is_not_a_conflict(self):
        a, b = self._pair(_nazwa_obiektu="PV Wyszki - zm. WP")
        au = linkage_audit(a, b).as_dict()
        assert au["confirmed"] == 1

    def test_a_one_sided_completion_is_not_a_conflict(self):
        """Empty in one edition and filled in the other is an edit, not a different application."""
        a = pd.DataFrame([_row(_podmiot="Alfa Sp. z o.o.", data_wniosku=None)])
        b = pd.DataFrame([_row(_podmiot="Alfa Sp. z o.o.", data_wniosku="2026-07-31")])
        result = linkage_audit(a, b)
        assert result.as_dict()["confirmed"] == 1
        category = set(result.discrepancies["category"])
        assert category == {"one_sided_supplement"}

    def test_the_precision_bounds_do_not_cross(self):
        a = pd.DataFrame([_row(lokalizacja_tekst=f"M{i}", _podmiot="Alfa Sp. z o.o.",
                                  _nazwa_obiektu=f"PV {i}") for i in range(4)])
        b = pd.DataFrame([_row(lokalizacja_tekst="M0", _podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV 0"),
                          _row(lokalizacja_tekst="M1", _podmiot="Beta Sp. z o.o.", _nazwa_obiektu="PV X"),
                          _row(lokalizacja_tekst="M2", _podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV Y"),
                          _row(lokalizacja_tekst="M3", _podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV 3")])
        au = linkage_audit(a, b).as_dict()
        assert au["pairs"] == 4
        assert au["confirmed"] + au["uncertain"] + au["false_matches"] == 4
        assert au["precision_lower"] <= au["precision_upper"]


class TestKeyCollisions:
    def test_collisions_and_rejections_are_reported(self):
        """Rows with a repeated key are rejected and the count is explicit."""
        a = pd.DataFrame([_row(), _row(), _row(lokalizacja_tekst="Inna")])
        b = pd.DataFrame([_row()])
        d = compare_editions(a, b).as_dict()
        assert d["rows_in_collision_a"] == 2
        assert d["rejected_as_ambiguous_a"] == 1
        assert d["shared"] == 1


class TestPandasVersionCompatibility:
    """The key must not depend on the pandas version.

    A defect found when the Colab notebook was run on pandas 3: `.astype(str)`
    turned a missing value into the string "nan" in pandas 2, while in pandas 3
    it keeps the missing value, so joining the key components raised TypeError.
    The key is now built with an explicit conversion.
    """

    def test_a_missing_value_gives_an_empty_segment_with_no_exception(self):
        import numpy as np
        import pandas as pd

        from gridqueue import surrogate_key

        df = pd.DataFrame([_row(moc_pobierana=np.nan, poziom_napiecia=None)])
        k = surrogate_key(df).iloc[0]
        assert isinstance(k, str)
        assert "nan" not in k.lower(), k
        assert "None" not in k, k

    def test_gaps_match_gaps(self):
        """A row with a gap links only to a row that has the gap as well."""
        import numpy as np
        import pandas as pd

        from gridqueue import compare_editions

        a = pd.DataFrame([_row(moc_pobierana=np.nan)])
        b = pd.DataFrame([_row(moc_pobierana=np.nan)])
        c = pd.DataFrame([_row(moc_pobierana=1000.0)])
        assert compare_editions(a, b).shared == 1
        assert compare_editions(a, c).shared == 0


class TestLinkageRecall:
    """Recall of the key: the pairs the content key did NOT join."""

    def test_a_change_of_capacity_breaks_a_pair_and_it_is_recovered(self):
        a = pd.DataFrame([_row(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  moc_wprowadzana=1000.0)])
        b = pd.DataFrame([_row(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  moc_wprowadzana=1200.0)])
        d = compare_editions(a, b).as_dict()
        assert d["shared"] == 0 and d["new"] == 1 and d["gone"] == 1

        r = linkage_recall(a, b)
        assert r.recovered == 1
        assert r.recovered_keys.iloc[0]["different_key_fields"] == "moc_wprowadzana"
        assert r.key_sensitivity == 0.0  # zero pairs joined, one possible

    def test_the_identity_fields_must_be_disjoint_from_the_key(self):
        """A field shared with the key will not detect a pair broken by a change of that field."""
        a = pd.DataFrame([_row(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  lokalizacja_tekst="Stacja A")])
        b = pd.DataFrame([_row(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  lokalizacja_tekst="Stacja A - pole 12")])
        assert linkage_recall(a, b).recovered == 1
        broken = linkage_recall(a, b, identity_fields=("_podmiot", "lokalizacja_tekst"))
        assert broken.recovered == 0

    def test_an_ambiguous_identity_is_not_recovered(self):
        a = pd.DataFrame([_row(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=1.0),
                          _row(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=2.0)])
        b = pd.DataFrame([_row(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=3.0)])
        assert linkage_recall(a, b).recovered == 0

    def test_zero_as_a_gap_is_switched_off_by_default(self):
        """Zero is a disclosed value; treating it as a gap is the analyst's decision."""
        a = pd.DataFrame([_row(moc_pobierana=0.0)])
        b = pd.DataFrame([_row(moc_pobierana=None)])
        assert surrogate_key(a).iloc[0] != surrogate_key(b).iloc[0]
        assert (surrogate_key(a, zero_as_missing=True).iloc[0]
                == surrogate_key(b, zero_as_missing=True).iloc[0])


class TestNodeEntityKey:
    """The key has to be chosen to fit the entity, just as the schema core is.

    The application key on node rows reports no error; it silently produces
    collisions, because the application fields are empty there.
    """

    def _nodes(self):
        import pandas as pd
        return pd.DataFrame([
            {"publikujacy": "X", "id_wezla": "SUB_A|66", "_encja": "WEZEL",
             "lokalizacja_tekst": "Gmina", "poziom_napiecia": "66 kV",
             "klasa_zasobu": None, "moc_wprowadzana": None, "moc_pobierana": None},
            {"publikujacy": "X", "id_wezla": "SUB_A|15", "_encja": "WEZEL",
             "lokalizacja_tekst": "Gmina", "poziom_napiecia": "15 kV",
             "klasa_zasobu": None, "moc_wprowadzana": None, "moc_pobierana": None},
        ])

    def test_the_node_key_distinguishes_voltage_levels_of_the_same_station(self):
        d = self._nodes()
        assert surrogate_key(d, fields=NODE_KEY_FIELDS).nunique() == 2

    def test_the_application_key_on_nodes_produces_collisions(self):
        """Regression: this is the failure mode NODE_KEY_FIELDS exists for."""
        d = self._nodes().assign(poziom_napiecia="66 kV")
        assert surrogate_key(d).nunique() == 1
        assert surrogate_key(d, fields=NODE_KEY_FIELDS).nunique() == 2
