import pandas as pd

from gridqueue.layout import (
    ColumnGeometry, assign_words_to_columns, audit_column_shift,
    detect_banded_columns, looks_like_date, looks_like_number, looks_like_text,
    looks_like_voltage, merge_continuation_rows,
)


def _w(text, x0, x1, top):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": top + 8}


def test_column_of_uzywa_srodka_slowa():
    g = ColumnGeometry([0.0, 10.0, 20.0, 30.0], "ruled")
    assert g.n_cols == 3
    assert g.column_of(1.0, 4.0) == 0
    assert g.column_of(9.0, 12.0) == 1      # środek 10.5 -> kolumna 1
    assert g.column_of(21.0, 29.0) == 2


def test_column_of_przycina_do_skrajnych_kolumn():
    g = ColumnGeometry([0.0, 10.0], "ruled")
    assert g.column_of(-5.0, -1.0) == 0
    assert g.column_of(50.0, 60.0) == 0


def test_detect_banded_columns_znajduje_korytarze_bieli():
    words = [_w("a", 0, 20, 0), _w("b", 40, 60, 0), _w("c", 80, 100, 0)]
    g = detect_banded_columns(words, min_gap=5.0)
    assert g.strategy == "banded"
    assert g.n_cols == 3
    cells = assign_words_to_columns(words, g)
    assert cells == [["a", "b", "c"]]


def test_detect_banded_columns_pusta_lista():
    assert detect_banded_columns([]).n_cols == 0


def test_assign_words_to_columns_pusta_komorka_zostaje_pusta():
    """Sedno metody: brak wartości w kolumnie nie przesuwa sąsiadów."""
    g = ColumnGeometry([0.0, 30.0, 60.0, 90.0], "ruled")
    words = [_w("PV", 1, 10, 0), _w("2026", 61, 80, 0)]   # środkowa kolumna pusta
    assert assign_words_to_columns(words, g) == [["PV", "", "2026"]]


def test_merge_continuation_rows_scala_zawiniety_adres():
    lines = [
        ["1.", "Toruń, ul. Marii", "0,150", "Elektrownia"],
        ["", "Skłodowskiej-", "", "fotowoltaiczna"],
        ["", "Curie 85A", "", ""],
        ["2.", "Toruń, ul. Równinna 8", "0,650", "Stacja"],
    ]
    rows = merge_continuation_rows(lines, lambda r: bool(r[0]))
    assert len(rows) == 2
    assert rows[0][1] == "Toruń, ul. Marii Skłodowskiej- Curie 85A"
    assert rows[0][2] == "0,150"
    assert rows[1][1] == "Toruń, ul. Równinna 8"


def test_predykaty_dziedziny():
    assert looks_like_date("04.05.2026") and looks_like_date("2026-05-04")
    assert not looks_like_date("maj 2026")
    assert looks_like_number("0,7") and looks_like_number("12 000") and looks_like_number(3)
    assert looks_like_text("WARUNKI PRZYŁĄCZENIA wydane")
    assert not looks_like_text("0,1 0,1 WARUNKI PRZYŁĄCZENIA utraciły ważność")
    assert looks_like_voltage("SN") and looks_like_voltage("110 kV")
    assert not looks_like_voltage("110") and not looks_like_voltage("Osoba prawna")


def test_audit_column_shift_wykrywa_moc_w_polu_statusu():
    df = pd.DataFrame({
        "status_procesu": ["UMOWA obowiązująca", "1,5 10,0 UMOWA O PRZYŁĄCZENIE"],
        "moc_pobierana": [1.0, None],
    })
    a = audit_column_shift(df)
    assert a.n_wierszy == 2
    assert a.n_przesunietych == 1
    assert a.per_pole == {"status_procesu": 1}
    assert 0.49 < a.udzial < 0.51


def test_audit_column_shift_ignoruje_puste():
    df = pd.DataFrame({"status_procesu": ["", "-", None], "moc_pobierana": [None] * 3})
    assert audit_column_shift(df).n_przesunietych == 0
