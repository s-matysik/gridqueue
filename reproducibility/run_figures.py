"""Reproduction of the figures that depend on the panel alone.

Scope
-----
Three figures computed from the panel are reproduced: coverage of the schema
fields, violations of the quality control rules, and the outcome of location
resolution.

Two figures this script does NOT reproduce, and that is deliberate:

* the architecture figure is a hand-drawn diagram with no input data;
* the validation figure depends on **a reference set read visually by a human**,
  published as a separate artefact rather than computed by code.

Running::

    python reproducibility/run_figures.py <panel.parquet> [output_directory]
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from gridqueue import (CORE_FIELDS, FIELDS, SCHEMA_VERSION, run_quality,
                       schema_table)

ABBREVIATION = {
    "TAURON Dystrybucja S.A.": "TAURON",
    "ENERGA-OPERATOR S.A.": "ENERGA",
    "Stoen Operator Sp. z o.o.": "Stoen",
    "PSE S.A.": "PSE",
    "National Grid Electricity Distribution": "National Grid",
    "Boryszew Green Energy&Gas Sp. z o.o.": "Boryszew",
}
COLORS = {"TAURON": "#1b5e8c", "ENERGA": "#2e8b78", "Stoen": "#c77a1e",
         "PSE": "#7a4b9c", "National Grid": "#6b7280", "Boryszew": "#a33b4e"}
GRAY = "#6b7280"


def _th(n: int) -> str:
    return f"{int(n):,}".replace(",", "\u00a0")


def fig_coverage(panel: pd.DataFrame, file_name: Path) -> None:
    st = schema_table()
    fields = st["field"].tolist()
    core = dict(zip(st["field"], st["core"].astype(bool)))
    publ = sorted(panel["publikujacy"].unique(),
                  key=lambda p: -int((panel["publikujacy"] == p).sum()))
    Z = np.zeros((len(fields), len(publ)))
    for j, p in enumerate(publ):
        sub = panel[panel["publikujacy"] == p]
        for i, f in enumerate(fields):
            s = sub[f] if f in sub.columns else pd.Series([None] * len(sub))
            nn = s.notna() & s.astype(str).str.strip().ne("") & s.astype(str).ne("nan")
            Z[i, j] = float(nn.mean())

    fig, ax = plt.subplots(figsize=(6.3, 5.6))
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "cov", ["#f7f7f7", "#c9dcea", "#5b93b8", "#1b5e8c"])
    ax.imshow(Z, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(publ)))
    ax.set_xticklabels(
        [f"{ABBREVIATION.get(p, p)}\n{_th(int((panel['publikujacy'] == p).sum()))}" for p in publ],
        fontsize=6)
    ax.set_yticks(range(len(fields)))
    ax.set_yticklabels([("\u2022 " if core[f] else "   ") + f for f in fields], fontsize=6)
    for i, f in enumerate(fields):
        if core[f]:
            ax.get_yticklabels()[i].set_fontweight("bold")
    for i in range(len(fields)):
        for j in range(len(publ)):
            v = Z[i, j]
            txt = "-" if v == 0 else ("<1" if v < 0.005 else
                                           ("100" if v >= 0.995 else f"{v*100:.0f}"))
            ax.text(j, i, txt, ha="center", va="center", fontsize=5.4,
                    color="#ffffff" if v > 0.62 else ("#999999" if v == 0 else "#222222"))
    ax.set_xticks(np.arange(-.5, len(publ), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(fields), 1), minor=True)
    ax.grid(which="minor", color="#ffffff", lw=0.8)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(axis="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    uncovered = [f for i, f in enumerate(fields) if Z[i].max() == 0]
    title = (f"Every one of the {len(fields)} schema fields is filled in by at least "
             "one publisher" if not uncovered else
             f"Fields not covered in the panel: {', '.join(uncovered)}")
    ax.set_title(title, fontsize=8, pad=22)
    ax.text(0, -1.35, "field coverage, % of the rows of a given publisher   "
            "\u2022 = unconditional core field   - = field not disclosed",
            fontsize=6, color=GRAY, transform=ax.transData)
    fig.tight_layout()
    fig.savefig(file_name, dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_quality(panel: pd.DataFrame, file_name: Path) -> None:
    rows = []
    for p, sub in panel.groupby("publikujacy"):
        for x in run_quality(sub.reset_index(drop=True)).as_dict()["rules"]:
            rows.append({"code": x["code"], "name": x["name"],
                         "pub": ABBREVIATION.get(p, p), "violations": x["violations"]})
    how = pd.DataFrame(rows)
    piv = (how.pivot_table(index=["code", "name"], columns="pub",
                           values="violations", aggfunc="sum")
              .fillna(0).astype(int))
    col = [p for p in COLORS if p in piv.columns]
    piv = piv[col]
    piv["total"] = piv.sum(axis=1)
    piv = piv.reset_index().sort_values("total")
    n = len(panel)

    fig, ax = plt.subplots(figsize=(6.8, 2.9))
    y = np.arange(len(piv))
    left = np.zeros(len(piv))
    for p in col:
        v = piv[p].values.astype(float)
        if v.sum() == 0:
            continue
        ax.barh(y, v, left=left, height=0.62, color=COLORS[p], label=p, zorder=2)
        left += v
    width = max(piv["total"].max(), 1)
    for yy, tot in zip(y, piv["total"].values):
        if tot == 0:
            ax.plot([0], [yy], "o", ms=3.2, color="#444444", zorder=3)
            ax.text(width * 0.012, yy, "0 violations", va="center", fontsize=6, color=GRAY)
        else:
            ax.text(tot + width * 0.012, yy,
                    f"{_th(tot)}  ({tot / n * 100:.3f}%)".replace(".", ","),
                    va="center", fontsize=6)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{k}  {nm}" for k, nm in zip(piv["code"], piv["name"])], fontsize=6.5)
    ax.set_xlim(0, width * 1.45)
    ax.set_xlabel(f"rows violating the rule (panel of {_th(n)} rows)", fontsize=7)
    ax.set_title("The rules detect the quality of the source, not an error of the tool, "
                 "and show which publisher lowers it", fontsize=8, loc="left")
    ax.legend(loc="lower right", fontsize=6, ncol=2, frameon=False,
              handlelength=1.1, columnspacing=1.0)
    ax.margins(y=0.06)
    fig.savefig(file_name, dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_location(panel: pd.DataFrame, file_name: Path) -> None:
    def category(coords, reason):
        if pd.notna(coords):
            return "resolved"
        s = str(reason)
        if "kod_stacji" in s:
            return "station code with no gazetteer"
        if "brak_deklaracji_miejscowosci" in s:
            return "no locality declared"
        if "pusty_opis" in s:
            return "empty description"
        if "poza_gazeterem" in s:
            return "locality outside the gazetteer"
        if "wiele_kandydatow" in s or "niejednoznaczna" in s:
            return "several candidates"
        return "other"

    d = panel.copy()
    d["pub"] = d["publikujacy"].map(lambda p: ABBREVIATION.get(p, p))
    d["_category"] = [category(w, r) for w, r in zip(d["wspolrzedne"], d.get("_geo_powod", pd.Series([None] * len(d))))]
    KAT = ["resolved", "station code with no gazetteer", "no locality declared",
           "empty description", "locality outside the gazetteer", "several candidates", "other"]
    KK = {"resolved": "#2e8b78", "station code with no gazetteer": "#1b5e8c",
          "no locality declared": "#8fb4cc", "empty description": "#cfd8dd",
          "locality outside the gazetteer": "#c77a1e", "several candidates": "#7a4b9c",
          "other": "#aaaaaa"}
    CT = (d.groupby(["pub", "_category"]).size().unstack(fill_value=0)
           .reindex(columns=[k for k in KAT if k in d["_category"].unique()], fill_value=0))
    CT = CT.reindex([p for p in COLORS if p in CT.index])
    assert int(CT.values.sum()) == len(d), "the categories do not cover all rows"

    fig = plt.figure(figsize=(7.1, 2.85))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.6, 1.0], wspace=0.45)
    ax = fig.add_subplot(gs[0])
    ypos = np.arange(len(CT))[::-1]
    frac = CT.div(CT.sum(axis=1), axis=0) * 100
    left = np.zeros(len(CT))
    for k in CT.columns:
        ax.barh(ypos, frac[k].values, left=left, height=0.62, color=KK[k], label=k, zorder=2)
        left += frac[k].values
    for yy, p in zip(ypos, CT.index):
        r = int(CT.loc[p, "resolved"]) if "resolved" in CT.columns else 0
        ax.text(101.5, yy, f"{_th(r)} / {_th(int(CT.loc[p].sum()))}", va="center", fontsize=6)
    ax.set_yticks(ypos)
    ax.set_yticklabels(CT.index, fontsize=6.5)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("share of the publisher's rows, %", fontsize=7)
    ax.set_title("No publisher discloses coordinates;\n"
                 "a gap is returned with a reason, not guessed", fontsize=8, loc="left", pad=8)
    ax.legend(loc="upper center", bbox_to_anchor=(0.46, -0.30), ncol=3, fontsize=5.7,
              frameon=False, handlelength=1.0, columnspacing=0.9, handletextpad=0.4)

    ax2 = fig.add_subplot(gs[1])
    pw = d.loc[d["wspolrzedne"].notna(), "_geo_pewnosc"].value_counts()
    description = {"EXACT": "exact", "UNIQUE_TOKEN": "unique member",
            "SKRZYZOWANIE": "intersection", "REVERSED": "reversed order",
            "TOKEN_SUBSET": "subset of members"}
    keys = [k for k in description if k in pw.index]
    vv = [int(pw[k]) for k in keys]
    yb = np.arange(len(keys))[::-1]
    ax2.barh(yb, vv, height=0.6, color="#2e8b78", zorder=2)
    for yy, v in zip(yb, vv):
        ax2.text(v + max(vv) * 0.02, yy, f"{v}  ({v / sum(vv) * 100:.1f}%)".replace(".", ","),
                 va="center", fontsize=6)
    ax2.set_yticks(yb)
    ax2.set_yticklabels([description[k] for k in keys], fontsize=6)
    ax2.set_xlim(0, max(vv) * 1.40)
    ax2.set_xlabel("rows", fontsize=7)
    ax2.set_title(f"Confidence level of {_th(sum(vv))} resolutions:\n"
                  f"{vv[0] / sum(vv) * 100:.1f}% are exact matches".replace(".", ","),
                  fontsize=8, loc="left", pad=8)
    fig.savefig(file_name, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python reproducibility/run_figures.py <panel.parquet> [directory]",
              file=sys.stderr)
        return 2
    p = Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent / "result"
    out.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p, low_memory=False)

    fig_coverage(panel, out / "fig_coverage.png")
    fig_quality(panel, out / "fig_quality.png")
    fig_location(panel, out / "fig_location.png")
    print(f"schema {SCHEMA_VERSION}; unconditional core: {', '.join(CORE_FIELDS)}")
    print(f"schema fields: {len(FIELDS)}; panel rows: {_th(len(panel))}")
    print(f"saved three figures to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
