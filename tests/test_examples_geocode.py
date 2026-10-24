"""Synthetic examples and geocode_frame."""

import json

import gridqueue as G
from gridqueue import examples as X


def test_synthetic_panel_is_clean_and_complete():
    df = X.synthetic_panel(300, seed=3)
    assert set(df["publikujacy"].dropna()) <= set(X.SYNTHETIC_PUBLISHERS)
    assert G.run_quality(df).as_dict()["violations_total"] == 0
    assert (df["_encja"] == "WEZEL").sum() == 16
    assert len(G.kaplan_meier_by_group(df, min_n=20)) >= 2


def test_synthetic_panel_is_reproducible():
    a, b = X.synthetic_panel(50, seed=1), X.synthetic_panel(50, seed=1)
    assert a.equals(b)


def test_synthetic_editions_have_every_kind_of_flow():
    a, b = X.synthetic_editions(300)
    d = G.compare_editions(a, b, "A", "B")
    assert d.new > 0 and d.gone > 0 and d.status_changes > 0
    assert d.backward_transitions >= 1


def test_geocode_frame_writes_schema_points_and_reasons(tmp_path):
    p = tmp_path / "gaz.json"
    p.write_text(json.dumps(X.synthetic_gazetteer()), encoding="utf-8")
    res = G.resolver_from_gazetteer_json(p)
    df = X.synthetic_panel(200, seed=5, with_nodes=False)
    df["wspolrzedne"] = df["wspolrzedne"].astype(object)
    df.loc[df.index[0], "wspolrzedne"] = "50.0,20.0"
    out = G.geocode_frame(df, res)
    assert out.loc[out.index[0], "_geo_pewnosc"] == "ZRODLO"
    assert out.loc[out.index[0], "wspolrzedne"] == "50.0,20.0"
    placed = out["wspolrzedne"].notna()
    assert placed.sum() > 1
    assert (out.loc[~placed, "_geo_powod"].str.len() > 0).all()
    # every point is in the format the schema validates
    assert G.validate_frame(out)["n_rows"] == len(out)
    lat = out.loc[placed, "wspolrzedne"].str.split(",").str[0].astype(float)
    assert lat.between(-90, 90).all()
