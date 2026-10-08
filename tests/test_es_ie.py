"""Testy adapterów hiszpańskiego i irlandzkiego.

Obie rodziny testów pilnują decyzji o jednostkach, bo to w nich tkwi ryzyko
cichego błędu: źródła mieszają moc czynną z pozorną w obrębie jednego pliku.
"""

import openpyxl
import pandas as pd
import pytest

from gridqueue import core_complete_mask, get_adapter
from gridqueue.adapters.es_edistribucion import _liczba as _liczba_es
from gridqueue.adapters.es_edistribucion import _data_z_nazwy, _mw_na_kw
from gridqueue.adapters.ie_esbnetworks import (_alternatywa, _flaga,
                                               _pojemnosc_bez_ograniczenia)


class TestHiszpanskieLiczby:
    def test_przecinek_dziesietny_i_kropka_tysiecy(self):
        assert _liczba_es("37,7") == pytest.approx(37.7)
        assert _liczba_es("1.234,5") == pytest.approx(1234.5)
        assert _liczba_es("") is None and _liczba_es("-") is None

    def test_megawaty_przechodza_w_kilowaty(self):
        """MW i kW to ta sama wielkość fizyczna, więc przeliczenie jest dozwolone."""
        assert _mw_na_kw("37,7") == pytest.approx(37_700.0)
        assert _mw_na_kw(None) is None

    def test_data_bierze_sie_z_nazwy_pliku(self):
        assert _data_z_nazwy("EDRD_Capacidad_de_Acceso_2025_08_01.pdf") == "2025-08-01"
        assert _data_z_nazwy("bez_daty.pdf") is None


class TestIrlandzkieFlagi:
    def test_fraza_ograniczenia_daje_prawde(self):
        assert _flaga("Constrained, otherwise capacity available =122 kVA") is True

    def test_pusta_komorka_to_brak_ograniczenia(self):
        """Interpretacja, nie treść źródła — pinujemy ją, żeby zmiana była widoczna."""
        assert _flaga(None) is False
        assert _flaga("") is False

    def test_pojemnosc_wyjmowana_z_frazy_zostaje_w_kva(self):
        """kVA to moc pozorna, więc wartość NIE jest przeliczana na kW."""
        assert _pojemnosc_bez_ograniczenia(
            "Constrained, otherwise capacity available =122 kVA") == pytest.approx(122.0)
        assert _pojemnosc_bez_ograniczenia("Constrained") is None

    def test_alternatywa_zachowuje_nieokreslonosc(self):
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


class TestIrlandzkieOdwzorowanie:
    def _wiersz(self, **zm):
        w = {"Station Name": "ARDNACRUSHA", "Transformer GroupID": "T1",
             "Primary kV": "110 kV", "Voltage Class": "HV",
             "Installed Capacity MVA": 63.0, "Demand Available MVA": 12.0,
             "Gen Available Firm MW": 25.0, "Generation Total Committed MW": 5.0,
             "Latitude": 52.70, "Longitude": -8.60}
        w.update(zm)
        return w

    def test_moc_dostepna_bierze_strone_wytworcza_w_MW(self, tmp_path):
        """Strona odbiorcza jest w MVA i NIE wolno jej sumować ani przeliczać."""
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [self._wiersz()])).frame
        assert d.loc[0, "moc_dostepna"] == pytest.approx(25_000.0)
        assert d.loc[0, "_odbior_dostepna_mva"] == pytest.approx(12.0)
        assert d.loc[0, "_jednostka_mocy_odbiorczej"] == "MVA"

    def test_rdzen_wezla_spelniony(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [self._wiersz()])).frame
        assert bool(core_complete_mask(d).iloc[0]) is True
        assert d.loc[0, "_encja"] == "WEZEL"

    def test_identyfikator_rozroznia_grupy_tej_samej_stacji(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [
            self._wiersz(), self._wiersz(**{"Transformer GroupID": "T2"})])).frame
        assert d["id_wezla"].nunique() == 2

    def test_wspolrzedne_skladane_w_jedno_pole(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [self._wiersz()])).frame
        assert d.loc[0, "wspolrzedne"] == "52.7,-8.6"

    def test_brak_wspolrzednych_daje_brak_a_nie_zero(self, tmp_path):
        d = get_adapter("ie_esbnetworks").parse(_arkusz_ie(tmp_path, [
            self._wiersz(**{"Latitude": None, "Longitude": None})])).frame
        assert d.loc[0, "wspolrzedne"] is None
