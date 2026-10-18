"""Tests of the edition comparison and of multi-valued capacity cells."""

import pandas as pd
import pytest

from gridqueue import (NODE_KEY_FIELDS, compare_editions, linkage_audit,
                       linkage_recall, surrogate_key)
from gridqueue.adapters._ptpiree import _rozbij_moc


def _wiersz(**kw):
    baza = {"publikujacy": "PSE S.A.", "lokalizacja_tekst": "Kromolice",
            "poziom_napiecia": "400 kV", "klasa_zasobu": "BESS",
            "moc_wprowadzana": 1000.0, "moc_pobierana": 1000.0,
            "status_procesu": "W_TRAKCIE_ANALIZY"}
    baza.update(kw)
    return baza


class TestSplitCapacity:
    """Several connection points in a single cell."""

    def test_a_line_break_yields_components(self):
        assert _rozbij_moc("129\n240") == ["129", "240"]

    def test_a_semicolon_and_a_line_break_together(self):
        assert _rozbij_moc("129; \n240") == ["129", "240"]

    def test_three_components(self):
        assert _rozbij_moc("27; \n45; \n21") == ["27", "45", "21"]

    def test_it_does_not_split_on_a_space(self):
        """For these publishers a space is a THOUSANDS separator, not a delimiter."""
        assert _rozbij_moc("129 240") == ["129 240"]

    def test_a_plain_number_is_one_component(self):
        assert _rozbij_moc(1830.0) == ["1830.0"]

    def test_a_dash_and_an_empty_value_are_rejected(self):
        assert _rozbij_moc("-") == []
        assert _rozbij_moc(None) == []

    def test_regression_of_a_three_orders_of_magnitude_merge(self):
        """Pins the defect from version 1.0: "129⏎240" merged into 129 240 MW.

        The cause was replacing the line break with a space before the
        conversion, and a space is treated as a thousands separator. The correct
        reading is two components summing to 369 MW.
        """
        czesci = _rozbij_moc("129\n240")
        assert sum(float(c) for c in czesci) == 369.0
        assert "".join(czesci) == "129240"  # this is what the defect looked like


class TestSurrogateKey:
    def test_identical_rows_give_the_same_key(self):
        df = pd.DataFrame([_wiersz(), _wiersz()])
        k = surrogate_key(df)
        assert k.iloc[0] == k.iloc[1]

    def test_a_change_of_capacity_pulls_the_key_apart(self):
        df = pd.DataFrame([_wiersz(), _wiersz(moc_pobierana=2000.0)])
        k = surrogate_key(df)
        assert k.iloc[0] != k.iloc[1]

    def test_the_status_does_not_enter_the_key(self):
        """Otherwise every status change would look like a disappearance and an appearance."""
        df = pd.DataFrame([_wiersz(), _wiersz(status_procesu="WARUNKI_WYDANE")])
        k = surrogate_key(df)
        assert k.iloc[0] == k.iloc[1]

    def test_missing_key_fields_are_an_error(self):
        with pytest.raises(ValueError, match="none of the key fields"):
            surrogate_key(pd.DataFrame({"cos_innego": [1]}), fields=("moc_dostepna",))


class TestCompareEditions:
    def test_the_flows(self):
        a = pd.DataFrame([_wiersz(lokalizacja_tekst="A"), _wiersz(lokalizacja_tekst="B")])
        b = pd.DataFrame([_wiersz(lokalizacja_tekst="B"), _wiersz(lokalizacja_tekst="C")])
        d = compare_editions(a, b, "lipiec", "sierpien")
        assert (d.wspolnych, d.nowych, d.ubylych) == (1, 1, 1)
        assert d.as_dict()["wierszy_netto"] == 0

    def test_a_forward_transition_is_counted_as_forward(self):
        a = pd.DataFrame([_wiersz(status_procesu="W_TRAKCIE_ANALIZY")])
        b = pd.DataFrame([_wiersz(status_procesu="WARUNKI_WYDANE")])
        d = compare_editions(a, b)
        assert d.zmian_statusu == 1
        assert d.udzial_przejsc_w_przod == 1.0
        assert d.przejscia_wstecz == 0

    def test_a_backward_transition_is_detected(self):
        a = pd.DataFrame([_wiersz(status_procesu="UMOWA_OBOWIAZUJACA")])
        b = pd.DataFrame([_wiersz(status_procesu="WARUNKI_WYDANE")])
        d = compare_editions(a, b)
        assert d.przejscia_wstecz == 1
        assert d.udzial_przejsc_w_przod == 0.0

    def test_a_refusal_is_counted_as_a_forward_closure(self):
        a = pd.DataFrame([_wiersz(status_procesu="W_TRAKCIE_ANALIZY")])
        b = pd.DataFrame([_wiersz(status_procesu="ODMOWA")])
        d = compare_editions(a, b)
        assert d.udzial_przejsc_w_przod == 1.0

    def test_non_monotonicity_of_the_snapshot(self):
        """A new row already closed and a vanished row still active, both flags."""
        a = pd.DataFrame([_wiersz(lokalizacja_tekst="X", status_procesu="WARUNKI_WYDANE")])
        b = pd.DataFrame([_wiersz(lokalizacja_tekst="Y", status_procesu="WNIOSEK_WYCOFANY")])
        d = compare_editions(a, b).as_dict()
        assert d["nowe_zamkniete"] == 1
        assert d["ubyle_czynne"] == 1
        assert d["migawka_monotoniczna"] is False

    def test_no_changes_give_a_share_of_none(self):
        a = pd.DataFrame([_wiersz()])
        d = compare_editions(a, a.copy())
        assert d.zmian_statusu == 0
        assert d.udzial_przejsc_w_przod is None


class TestLinkageAudit:
    """Assessment of the linkage on fields EXCLUDED from the key."""

    def _para(self, **zmiany_b):
        a = pd.DataFrame([_wiersz(_podmiot="Alfa Sp. z o.o.", _nazwa_obiektu="PV Wyszki")])
        b_ = {"_podmiot": "Alfa Sp. z o.o.", "_nazwa_obiektu": "PV Wyszki"}
        b_.update(zmiany_b)
        return a, pd.DataFrame([_wiersz(**b_)])

    def test_matching_held_out_fields_give_a_confirmation(self):
        a, b = self._para()
        au = linkage_audit(a, b).as_dict()
        assert (au["par"], au["potwierdzonych"], au["falszywych"]) == (1, 1, 0)
        assert au["precyzja_dolna"] == 1.0

    def test_both_identity_fields_divergent_means_a_false_linkage(self):
        a, b = self._para(_podmiot="Beta Sp. z o.o.", _nazwa_obiektu="PV Bulkowo")
        au = linkage_audit(a, b).as_dict()
        assert au["falszywych"] == 1
        assert au["precyzja_gorna"] == 0.0

    def test_one_divergent_field_means_uncertain(self):
        a, b = self._para(_nazwa_obiektu="PV Bulkowo")
        au = linkage_audit(a, b).as_dict()
        assert (au["niepewnych"], au["falszywych"]) == (1, 0)
        assert au["precyzja_dolna"] == 0.0 and au["precyzja_gorna"] == 1.0

    def test_a_different_spelling_of_the_legal_form_is_the_same_entity(self):
        """The publisher changes the spelling of the legal form between editions."""
        a, b = self._para(_podmiot="Alfa sp.z o.o.")
        au = linkage_audit(a, b).as_dict()
        assert au["potwierdzonych"] == 1

    def test_an_extended_name_is_not_a_conflict(self):
        a, b = self._para(_nazwa_obiektu="PV Wyszki - zm. WP")
        au = linkage_audit(a, b).as_dict()
        assert au["potwierdzonych"] == 1

    def test_a_one_sided_completion_is_not_a_conflict(self):
        """Empty in one edition and filled in the other is an edit, not a different application."""
        a = pd.DataFrame([_wiersz(_podmiot="Alfa Sp. z o.o.", data_wniosku=None)])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa Sp. z o.o.", data_wniosku="2026-07-31")])
        wynik = linkage_audit(a, b)
        assert wynik.as_dict()["potwierdzonych"] == 1
        kat = set(wynik.rozbieznosci["kategoria"])
        assert kat == {"uzupelnienie_jednostronne"}

    def test_the_precision_bounds_do_not_cross(self):
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


class TestKeyCollisions:
    def test_collisions_and_rejections_are_reported(self):
        """Rows with a repeated key are rejected and the count is explicit."""
        a = pd.DataFrame([_wiersz(), _wiersz(), _wiersz(lokalizacja_tekst="Inna")])
        b = pd.DataFrame([_wiersz()])
        d = compare_editions(a, b).as_dict()
        assert d["wierszy_w_kolizji_a"] == 2
        assert d["odrzuconych_jako_niejednoznaczne_a"] == 1
        assert d["wspolnych"] == 1


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

        df = pd.DataFrame([_wiersz(moc_pobierana=np.nan, poziom_napiecia=None)])
        k = surrogate_key(df).iloc[0]
        assert isinstance(k, str)
        assert "nan" not in k.lower(), k
        assert "None" not in k, k

    def test_gaps_match_gaps(self):
        """A row with a gap links only to a row that has the gap as well."""
        import numpy as np
        import pandas as pd

        from gridqueue import compare_editions

        a = pd.DataFrame([_wiersz(moc_pobierana=np.nan)])
        b = pd.DataFrame([_wiersz(moc_pobierana=np.nan)])
        c = pd.DataFrame([_wiersz(moc_pobierana=1000.0)])
        assert compare_editions(a, b).wspolnych == 1
        assert compare_editions(a, c).wspolnych == 0


class TestLinkageRecall:
    """Recall of the key: the pairs the content key did NOT join."""

    def test_a_change_of_capacity_breaks_a_pair_and_it_is_recovered(self):
        a = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  moc_wprowadzana=1000.0)])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  moc_wprowadzana=1200.0)])
        d = compare_editions(a, b).as_dict()
        assert d["wspolnych"] == 0 and d["nowych"] == 1 and d["ubylych"] == 1

        r = linkage_recall(a, b)
        assert r.odzyskanych == 1
        assert r.odzyskane.iloc[0]["pola_klucza_rozne"] == "moc_wprowadzana"
        assert r.czulosc_klucza == 0.0  # zero pairs joined, one possible

    def test_the_identity_fields_must_be_disjoint_from_the_key(self):
        """A field shared with the key will not detect a pair broken by a change of that field."""
        a = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  lokalizacja_tekst="Stacja A")])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV Wyszki",
                                  lokalizacja_tekst="Stacja A - pole 12")])
        assert linkage_recall(a, b).odzyskanych == 1
        zepsute = linkage_recall(a, b, pola_tozsamosci=("_podmiot", "lokalizacja_tekst"))
        assert zepsute.odzyskanych == 0

    def test_an_ambiguous_identity_is_not_recovered(self):
        a = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=1.0),
                          _wiersz(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=2.0)])
        b = pd.DataFrame([_wiersz(_podmiot="Alfa", _nazwa_obiektu="PV", moc_wprowadzana=3.0)])
        assert linkage_recall(a, b).odzyskanych == 0

    def test_zero_as_a_gap_is_switched_off_by_default(self):
        """Zero is a disclosed value; treating it as a gap is the analyst's decision."""
        a = pd.DataFrame([_wiersz(moc_pobierana=0.0)])
        b = pd.DataFrame([_wiersz(moc_pobierana=None)])
        assert surrogate_key(a).iloc[0] != surrogate_key(b).iloc[0]
        assert (surrogate_key(a, zero_jako_brak=True).iloc[0]
                == surrogate_key(b, zero_jako_brak=True).iloc[0])


class TestNodeEntityKey:
    """The key has to be chosen to fit the entity, just as the schema core is.

    The application key on node rows reports no error; it silently produces
    collisions, because the application fields are empty there.
    """

    def _wezly(self):
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
        d = self._wezly()
        assert surrogate_key(d, fields=NODE_KEY_FIELDS).nunique() == 2

    def test_the_application_key_on_nodes_produces_collisions(self):
        """Regression: this is the failure mode NODE_KEY_FIELDS exists for."""
        d = self._wezly().assign(poziom_napiecia="66 kV")
        assert surrogate_key(d).nunique() == 1
        assert surrogate_key(d, fields=NODE_KEY_FIELDS).nunique() == 2
