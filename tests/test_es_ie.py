"""Tests of the Spanish and the Irish adapter.

Both families of tests guard the decisions about units, because that is where the
risk of a silent error sits: the sources mix active and apparent power within one file.
"""

import openpyxl
import pandas as pd
import pytest

from gridqueue import core_complete_mask, get_adapter
from gridqueue.adapters.es_edistribucion import _count as _count_es
from gridqueue.adapters.es_edistribucion import (_date_from_name, _mw_per_kw,
                                                 total_occupied_capacity_components)
from gridqueue.adapters.ie_esbnetworks import (_alternative, _flag,
                                               _unlimited_capacity)


class TestSpanishNumbers:
    def test_decimal_comma_and_thousands_dot(self):
        assert _count_es("37,7") == pytest.approx(37.7)
        assert _count_es("1.234,5") == pytest.approx(1234.5)
        assert _count_es("") is None and _count_es("-") is None

    def test_megawatts_are_converted_into_kilowatts(self):
        """MW and kW are the same physical quantity, so the conversion is allowed."""
        assert _mw_per_kw("37,7") == pytest.approx(37_700.0)
        assert _mw_per_kw(None) is None

    def test_the_date_is_taken_from_the_file_name(self):
        assert _date_from_name("EDRD_Capacidad_de_Acceso_2025_08_01.pdf") == "2025-08-01"
        assert _date_from_name("bez_daty.pdf") is None


class TestIrishFlags:
    def test_the_constraint_phrase_yields_true(self):
        assert _flag("Constrained, otherwise capacity available =122 kVA") is True

    def test_an_empty_cell_means_no_constraint(self):
        """An interpretation, not the content of the source; we pin it so that a change is visible."""
        assert _flag(None) is False
        assert _flag("") is False

    def test_the_capacity_taken_from_the_phrase_stays_in_kva(self):
        """kVA is apparent power, so the value is NOT converted into kW."""
        assert _unlimited_capacity(
            "Constrained, otherwise capacity available =122 kVA") == pytest.approx(122.0)
        assert _unlimited_capacity("Constrained") is None

    def test_the_alternative_preserves_indeterminacy(self):
        assert _alternative(True, None) is True
        assert _alternative(False, False) is False
        assert _alternative(None, False) is None
        assert _alternative(None, None) is None


def _sheet_ie(tmp_path, rows):
    col = ["Station Name", "Transformer GroupID", "Primary kV", "Secondary voltage(s)",
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
    ws.append([None] * len(col))
    ws.append(col)
    for w in rows:
        ws.append([w.get(k) for k in col])
    p = tmp_path / "customer-heatmap-download.xlsx"
    wb.save(p)
    return p


class TestIrishMapping:
    def _row(self, **zm):
        w = {"Station Name": "ARDNACRUSHA", "Transformer GroupID": "T1",
             "Primary kV": "110 kV", "Voltage Class": "HV",
             "Installed Capacity MVA": 63.0, "Demand Available MVA": 12.0,
             "Gen Available Firm MW": 25.0, "Generation Total Committed MW": 5.0,
             "Latitude": 52.70, "Longitude": -8.60}
        w.update(zm)
        return w

    def test_available_capacity_takes_the_generation_side_in_MW(self, tmp_path):
        """The demand side is in MVA and must NOT be summed or converted."""
        d = get_adapter("ie_esbnetworks").parse(_sheet_ie(tmp_path, [self._row()])).frame
        assert d.loc[0, "capacity_available"] == pytest.approx(25_000.0)
        assert d.loc[0, "_demand_available_mva"] == pytest.approx(12.0)
        assert d.loc[0, "_demand_capacity_unit"] == "MVA"

    def test_the_node_core_is_satisfied(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_sheet_ie(tmp_path, [self._row()])).frame
        assert bool(core_complete_mask(d).iloc[0]) is True
        assert d.loc[0, "_entity"] == "NODE"

    def test_the_identifier_distinguishes_groups_of_the_same_station(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_sheet_ie(tmp_path, [
            self._row(), self._row(**{"Transformer GroupID": "T2"})])).frame
        assert d["node_id"].nunique() == 2

    def test_the_coordinates_are_combined_into_one_field(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_sheet_ie(tmp_path, [self._row()])).frame
        assert d.loc[0, "coordinates"] == "52.7,-8.6"

    def test_missing_coordinates_give_a_gap_not_a_zero(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_sheet_ie(tmp_path, [
            self._row(**{"Latitude": None, "Longitude": None})])).frame
        assert d.loc[0, "coordinates"] is None


class TestArithmeticIdentity:
    """The sum of eleven subcolumns closes to the occupied capacity.

    For this publisher there is no reference set read independently of the
    parser, so arithmetic closure is the only checkable evidence that the
    reading is consistent. The test pins the contract of the function, not a
    value from the document.
    """

    def _row(self, total_cap, positions=(), with_permission="", in_progress=""):
        w = [""] * 29
        w[0] = "01 - Andalucía"
        w[8] = total_cap
        for i, v in enumerate(positions):
            w[9 + i] = v
        w[18], w[19] = with_permission, in_progress
        return w

    def test_both_groups_are_components_and_not_alternatives(self):
        """A row with BOTH groups filled in closes only on their sum."""
        w = self._row("97,3", positions=("24,6",), with_permission="72,7")
        assert total_occupied_capacity_components([w]) == (1, 1)

    def test_the_positions_alone_also_close(self):
        assert total_occupied_capacity_components(
            [self._row("40,4", positions=("40,0",), in_progress="0,4")]) == (1, 1)

    def test_a_row_that_does_not_close_is_detected(self):
        assert total_occupied_capacity_components(
            [self._row("100,0", positions=("10,0",))]) == (0, 1)

    def test_a_row_without_a_total_value_is_not_counted(self):
        assert total_occupied_capacity_components([self._row("")]) == (0, 0)
