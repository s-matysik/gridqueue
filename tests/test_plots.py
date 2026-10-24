"""Charts: every function draws from constructed frames without raising, and the numbers
it puts on the chart are the numbers of the analysis it shows."""

import json

import pandas as pd
import pytest

pytest.importorskip("matplotlib")

from gridqueue import (compare_editions, kaplan_meier, kaplan_meier_by_group,  # noqa: E402
                       linkage_audit, linkage_recall)
from gridqueue import cli, plots  # noqa: E402
from gridqueue.analysis import assign_to_nodes, node_loading, station_node_map  # noqa: E402
from gridqueue.schema import empty_frame  # noqa: E402


def _frame(rows):
    return pd.DataFrame(rows).reindex(columns=list(empty_frame().columns) + [
        c for c in pd.DataFrame(rows).columns if c not in empty_frame().columns])


def _panel(n=80):
    rows = []
    for i in range(n):
        klasa = "PV" if i % 2 else "ODB"
        rows.append({
            "id_wniosku": f"A{i}", "lokalizacja_tekst": f"Stacja {i % 4}",
            "klasa_zasobu": klasa, "poziom_napiecia": "SN" if i % 3 else "110 kV",
            "moc_wprowadzana": 1000.0 + i if klasa == "PV" else None,
            "moc_pobierana": 500.0 + i if klasa == "ODB" else None,
            "status_procesu": "WARUNKI_WYDANE" if i % 5 else "WNIOSEK_ZLOZONY",
            "data_wniosku": f"2025-01-{1 + i % 28:02d}",
            "data_warunkow": f"2025-0{3 + i % 6}-15" if i % 5 else None,
            "data_publikacji": "2025-12-31",
            "publikujacy": "PSE S.A." if i < n // 2 else "ENERGA-OPERATOR S.A.",
        })
    return _frame(rows)


def _texts(fig):
    out = []
    for ax in fig.axes:
        out.append(ax.get_title(loc="left"))
        out += [t.get_text() for t in ax.texts]
    return " ".join(out)


@pytest.fixture(scope="module")
def panel():
    return _panel()


def test_every_panel_chart_draws(panel):
    for f in (plots.plot_field_coverage, plots.plot_quality, plots.plot_column_shift,
              plots.plot_status_distribution, plots.plot_capacity_by_class,
              plots.plot_processing_time, plots.plot_location_resolution,
              plots.plot_overview):
        fig = f(panel)
        assert fig.axes, f.__name__


def test_charts_tolerate_a_minimal_frame():
    df = _frame([{"id_wniosku": "X", "lokalizacja_tekst": "a", "klasa_zasobu": "ODB",
                  "status_procesu": "WNIOSEK_ZLOZONY", "moc_pobierana": 10.0}])
    for f in (plots.plot_field_coverage, plots.plot_quality, plots.plot_status_distribution,
              plots.plot_capacity_by_class, plots.plot_processing_time,
              plots.plot_location_resolution, plots.plot_overview):
        assert f(df).axes


def test_coverage_counts_fields_like_the_schema(panel):
    txt = plots.plot_field_coverage(panel).axes[0].get_title(loc="left")
    populated = sum(1 for c in plots.schema_table()["pole"] if panel[c].notna().any())
    assert f"{populated} of 21 fields populated" in txt


def test_quality_chart_total_matches_run_quality(panel):
    from gridqueue import run_quality

    fig = plots.plot_quality(panel, by=None)
    expected = {r["kod"]: r["naruszenia"] for r in run_quality(panel).as_dict()["reguly"]}
    shown = _texts(fig)
    for kod, n in expected.items():
        if n > 0:
            assert f"{n:,}  (" in shown, kod


def test_km_chart_legend_uses_the_estimator(panel):
    tab = kaplan_meier_by_group(panel, by="klasa_zasobu", min_n=10)
    fig = plots.plot_processing_time(panel, min_n=10)
    legend = " ".join(t.get_text() for t in fig.axes[0].get_legend().get_texts())
    for r in tab.itertuples():
        assert f"n={r.n:,}" in legend
        assert f"median {r.mediana:.0f} d" in legend


def test_km_median_interval_is_ordered():
    # Regression: up to 1.5.2 the two bounds of the median interval were swapped.
    t = list(range(1, 201))
    e = [1] * 200
    km = kaplan_meier(t, e)
    assert km.mediana_dolna <= km.mediana <= km.mediana_gorna


def test_km_all_censored_group_does_not_raise():
    # Regression: a group with no event produced a frame without columns (KeyError 'S').
    km = kaplan_meier([10, 20, 30], [0, 0, 0])
    assert km.n == 3 and km.zdarzen == 0 and km.mediana != km.mediana


def test_km_by_group_respects_min_n(panel):
    assert kaplan_meier_by_group(panel, min_n=10_000).empty
    tab = kaplan_meier_by_group(panel, by=["publikujacy", "klasa_zasobu"], min_n=5)
    assert tab["grupa"].str.contains(" / ").all()


def _editions():
    a = _panel(40)
    b = a.copy()
    b.loc[b.index[:5], "status_procesu"] = "UMOWA_OBOWIAZUJACA"
    b = b.iloc[2:]
    return a, b


def test_edition_charts_show_the_delta():
    a, b = _editions()
    d = compare_editions(a, b, "A", "B")
    fig = plots.plot_edition_comparison(d, linkage_audit(a, b), linkage_recall(a, b))
    assert len(fig.axes) == 3
    txt = _texts(fig)
    assert f"{d.wspolnych:,} linked" in txt


def test_node_loading_chart_skips_zero_capacity():
    rows = [
        {"_encja": "WEZEL", "id_wezla": "G1", "nazwa_wezla": "Alfa", "_nr_grupy": 1,
         "lokalizacja_tekst": "Alfa, Beta", "moc_dostepna": 1000.0, "_kierunek": "wytworcza"},
        {"_encja": "WEZEL", "id_wezla": "G2", "nazwa_wezla": "Gamma", "_nr_grupy": 2,
         "lokalizacja_tekst": "Gamma", "moc_dostepna": 0.0, "_kierunek": "wytworcza"},
        {"_encja": "WNIOSEK", "lokalizacja_tekst": "Alfa", "moc_wprowadzana": 2500.0,
         "status_procesu": "WARUNKI_WYDANE"},
        {"_encja": "WNIOSEK", "lokalizacja_tekst": "Gamma", "moc_wprowadzana": 500.0,
         "status_procesu": "WARUNKI_WYDANE"},
    ]
    df = pd.DataFrame(rows)
    L = node_loading(assign_to_nodes(df, station_node_map(df)), pole_mocy="moc_wprowadzana")
    fig = plots.plot_node_loading(L)
    title = fig.axes[0].get_title(loc="left")
    assert "median 2.500" in title and "1 node with zero free capacity" in title


def test_save_all_and_cli_plot(tmp_path, panel, capsys):
    p = tmp_path / "panel.parquet"
    panel.to_parquet(p, index=False)
    assert cli.main(["plot", str(p), "--out", str(tmp_path / "figs"), "--format", "png,svg",
                     "--min-n", "10"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert "field_coverage" in out["zapisane"]
    assert (tmp_path / "figs" / "quality_rules.svg").exists()
    assert any("node_loading" in s for s in out["pominiete"])


def test_cli_compare(tmp_path, capsys):
    a, b = _editions()
    pa, pb = tmp_path / "a.parquet", tmp_path / "b.parquet"
    a.to_parquet(pa, index=False)
    b.to_parquet(pb, index=False)
    assert cli.main(["compare", str(pa), str(pb), "--transitions",
                     str(tmp_path / "tr.csv")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["porownanie"]["wspolnych"] == compare_editions(a, b).wspolnych
    assert (tmp_path / "tr.csv").exists()
