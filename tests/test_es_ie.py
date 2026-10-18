"""Tests of the Spanish and the Irish adapter.

Both families of tests guard the decisions about units, because that is where the
risk of a silent error sits: the sources mix active and apparent power within one file.
"""

import openpyxl
import pandas as pd
import pytest

from gridqueue import core_complete_mask, get_adapter
from gridqueue.adapters.es_edistribucion import _liczba as _liczba_es
from gridqueue.adapters.es_edistribucion import (_data_z_nazwy, _mw_na_kw,
                                                 suma_skladnikow_mocy_zajetej)
from gridqueue.adapters.ie_esbnetworks import (_alternatywa, _flaga,
                                               _pojemnosc_bez_ograniczenia)


class TestSpanishNumbers:
    def test_decimal_comma_and_thousands_dot(self):
        assert _liczba_es("37,7") == pytest.approx(37.7)
        assert _liczba_es("1.234,5") == pytest.approx(1234.5)
        assert _liczba_es("") is None and _liczba_es("-") is None

    def test_megawatts_are_converted_into_kilowatts(self):
        """MW and kW are the same physical quantity, so the conversion is allowed."""
        assert _mw_na_kw("37,7") == pytest.approx(37_700.0)
        assert _mw_na_kw(None) is None

    def test_the_date_is_taken_from_the_file_name(self):
        assert _data_z_nazwy("EDRD_Capacidad_de_Acceso_2025_08_01.pdf") == "2025-08-01"
        assert _data_z_nazwy("bez_daty.pdf") is None


class TestIrishFlags:
    def test_the_constraint_phrase_yields_true(self):
        assert _flaga("Constrained, otherwise capacity available =122 kVA") is True

    def test_an_empty_cell_means_no_constraint(self):
        """An interpretation, not the content of the source; we pin it so that a change is visible."""
        assert _flaga(None) is False
        assert _flaga("") is False

    def test_the_capacity_taken_from_the_phrase_stays_in_kva(self):
        """kVA is apparent power, so the value is NOT converted into kW."""
        assert _pojemnosc_bez_ograniczenia(
            "Constrained, otherwise capacity available =122 kVA") == pytest.approx(122.0)
        assert _pojemnosc_bez_ograniczenia("Constrained") is None

    def test_the_alternative_preserves_indeterminacy(self):
        assert _alternatywa(True, None) is True
        assert _alternatywa(False, False) is False
        assert _alternatywa(None, False) is None
        assert _alternatywa(None, None) is None


def _arkusz_ie(tmp_path, wiersze):
    kol = ["Station Name", "Transformer GroupID", "Primary kV", "Secondary voltage(s)",
           "Voltage Class", "Transformer Configuration", "Installed Capacity MVA",
           "Demand Data", "Demand FirmCapacity MVA", "Demand Available MVA",
           "Parent Available MVA", "Demand Parent Constraint", "Generation Data",
           "Generation Firm Capacity MW", "Generation NonFirm Capacity MW",
           "Generation Total Committed MW", "Gen Available Firm MW",
           "Gen Available NonFirm MW", "Generation Parent Constraint", "General Data",
           "Parent Feeder", "Parent Station", "TSO Interface Station", "Comment",
           "Latitude", "Longitude"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Heatmap data"
    ws.append([None] * len(kol))
    ws.append(kol)
    for w in wiersze:
        ws.append([w.get(k) for k in kol])
    p = tmp_path / "customer-heatmap-download.xlsx"
    wb.save(p)
    return p


class TestIrishMapping:
    def _wiersz(self, **zm):
        w = {"Station Name": "ARDNACRUSHA", "Transformer GroupID": "T1",
             "Primary kV": "110 kV", "Voltage Class": "HV",
             "Installed Capacity MVA": 63.0, "Demand Available MVA": 12.0,
             "Gen Available Firm MW": 25.0, "Generation Total Committed MW": 5.0,
             "Latitude": 52.70, "Longitude": -8.60}
        w.update(zm)
        return w

    def test_available_capacity_takes_the_generation_side_in_MW(self, tmp_path):
        """The demand side is in MVA and must NOT be summed or converted."""
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [self._wiersz()])).frame
        assert d.loc[0, "moc_dostepna"] == pytest.approx(25_000.0)
        assert d.loc[0, "_odbior_dostepna_mva"] == pytest.approx(12.0)
        assert d.loc[0, "_jednostka_mocy_odbiorczej"] == "MVA"

    def test_the_node_core_is_satisfied(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [self._wiersz()])).frame
        assert bool(core_complete_mask(d).iloc[0]) is True
        assert d.loc[0, "_encja"] == "WEZEL"

    def test_the_identifier_distinguishes_groups_of_the_same_station(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [
            self._wiersz(), self._wiersz(**{"Transformer GroupID": "T2"})])).frame
        assert d["id_wezla"].nunique() == 2

    def test_the_coordinates_are_combined_into_one_field(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [self._wiersz()])).frame
        assert d.loc[0, "wspolrzedne"] == "52.7,-8.6"

    def test_missing_coordinates_give_a_gap_not_a_zero(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [
            self._wiersz(**{"Latitude": None, "Longitude": None})])).frame
        assert d.loc[0, "wspolrzedne"] is None


class TestArithmeticIdentity:
    """The sum of eleven subcolumns closes to the occupied capacity.

    For this publisher there is no reference set read independently of the
    parser, so arithmetic closure is the only checkable evidence that the
    reading is consistent. The test pins the contract of the function, not a
    value from the document.
    """

    def _wiersz(self, laczna, pozycje=(), z_pozwoleniem="", w_toku=""):
        w = [""] * 29
        w[0] = "01 - Andalucía"
        w[8] = laczna
        for i, v in enumerate(pozycje):
            w[9 + i] = v
        w[18], w[19] = z_pozwoleniem, w_toku
        return w

    def test_both_groups_are_components_and_not_alternatives(self):
        """A row with BOTH groups filled in closes only on their sum."""
        w = self._wiersz("97,3", pozycje=("24,6",), z_pozwoleniem="72,7")
        assert suma_skladnikow_mocy_zajetej([w]) == (1, 1)

    def test_the_positions_alone_also_close(self):
        assert suma_skladnikow_mocy_zajetej(
            [self._wiersz("40,4", pozycje=("40,0",), w_toku="0,4")]) == (1, 1)

    def test_a_row_that_does_not_close_is_detected(self):
        assert suma_skladnikow_mocy_zajetej(
            [self._wiersz("100,0", pozycje=("10,0",))]) == (0, 1)

    def test_a_row_without_a_total_value_is_not_counted(self):
        assert suma_skladnikow_mocy_zajetej([self._wiersz("")]) == (0, 0)
