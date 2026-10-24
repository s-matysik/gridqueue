"""Research example: processing time of a connection application.

Research question
-----------------
Does the time from lodging a connection application to the issue of connection
conditions differ between resource classes and between publishers?

What this example shows about the tool
--------------------------------------
Adapters are source specific, but **the research analysis is not**. The code
below contains not a single branch that depends on the publisher: it works only
on the fields of the common schema (`date_application`, `date_conditions`,
`resource_class`, `publisher`) and runs identically on the output of every
adapter. That, and not the mere fact that a document could be broken down into
rows, is what harmonisation produces.

Input data
----------
A panel produced by `gridqueue` (Parquet or CSV), by default
``gridqueue_panel.parquet`` in the current directory. The panel is built with::

    gridqueue parse <documents...> --out gridqueue_panel.parquet

Running::

    python examples/research_use_case.py [path_to_panel] [output_directory]

Produces::

    processing_time.csv   the result table (one row per publisher and class)
    processing_time.png   the figure
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from gridqueue import SCHEMA_VERSION, __version__, core_complete_mask

#: Minimum group size below which we do not report medians.
MIN_N = 30

#: Readable names of the resource classes from the controlled vocabulary of the schema.
CLASS_NAMES = {
    "LOAD": "demand",
    "PV": "photovoltaics",
    "WIND": "wind",
    "BESS": "energy storage",
    "GAS": "gas",
    "HYDRO": "hydro",
    "MIX": "mixed installation",
    "GRID": "network",
    "BIOGAS": "biogas",
}


def load_panel(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path, low_memory=False)


def processing_time(panel: pd.DataFrame) -> pd.DataFrame:
    """Time from lodging the application to the issue of conditions, in days."""
    df = panel.copy()
    for col in ("date_application", "date_conditions"):
        df[col] = pd.to_datetime(df[col], errors="coerce")
    df["time_days"] = (df["date_conditions"] - df["date_application"]).dt.days
    return df


def summary_table(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Medians and interquartile ranges per publisher and resource class.

    Rows with a negative date difference are dropped and counted separately: an
    inconsistency in the order of dates is detected by quality rule R1 and should
    not enter the descriptive statistics as a negative value.
    """
    countable = df["time_days"].notna()
    negative = countable & (df["time_days"] < 0)
    ok = df.loc[countable & ~negative]

    tab = (ok.groupby(["publisher", "resource_class"])["time_days"]
             .agg(n="size", median="median",
                  quartile_1=lambda s: s.quantile(0.25),
                  quartile_3=lambda s: s.quantile(0.75))
             .reset_index())
    tab = tab.loc[tab["n"] >= MIN_N].copy()
    tab["iqr"] = tab["quartile_3"] - tab["quartile_1"]
    tab["class_description"] = tab["resource_class"].map(CLASS_NAMES).fillna(tab["resource_class"])
    tab = tab.sort_values(["publisher", "median"]).reset_index(drop=True)

    meta = {
        "gridqueue": __version__,
        "schema_version": SCHEMA_VERSION,
        "panel_rows": int(len(df)),
        "rows_with_complete_core": int(core_complete_mask(df).sum()),
        "rows_with_countable_time": int(len(ok)),
        "rejected_negative": int(negative.sum()),
        "groups_below_threshold_skipped": int(
            ok.groupby(["publisher", "resource_class"]).size().lt(MIN_N).sum()),
        "min_n_group": MIN_N,
        "median_total_days": float(ok["time_days"].median()),
    }
    return tab, meta


def fig(tab: pd.DataFrame, file_name: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # The colour is bound to the NAME of the publisher, not to the position in the
    # sorted list: otherwise adding a publisher would repaint the others and the
    # figure would drift away from the other figures of the project.
    COLORS = {
        "TAURON Dystrybucja S.A.": "#1b5e8c",
        "ENERGA-OPERATOR S.A.": "#2e8b78",
        "Stoen Operator Sp. z o.o.": "#c77a1e",
        "PSE S.A.": "#7a4b9c",
        "National Grid Electricity Distribution": "#6b7280",
        "Boryszew Green Energy&Gas Sp. z o.o.": "#a33b4e",
    }
    RESERVE = "#555555"
    fig, ax = plt.subplots(figsize=(6.6, 0.30 * len(tab) + 1.7))
    for i, (_, r) in enumerate(tab.iterrows()):
        ax.plot([r["quartile_1"], r["quartile_3"]], [i, i], lw=3.2, alpha=0.35,
                color=COLORS.get(r["publisher"], RESERVE),
                solid_capstyle="butt")
        ax.plot([r["median"]], [i], "o", ms=5, color=COLORS.get(r["publisher"], RESERVE))
        ax.text(r["quartile_3"] + 8, i, f"{r['median']:.0f} d  (n={int(r['n'])})",
                va="center", fontsize=7)
    ax.set_yticks(list(range(len(tab))))
    ax.set_yticklabels([f"{r['class_description']}, {r['publisher'].split()[0]}"
                        for _, r in tab.iterrows()], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, tab["quartile_3"].max() * 1.30)
    ax.set_xlabel("days: application → conditions\n"
                  "dot = median, band = interquartile range", fontsize=8)
    ax.set_title("Demand connections are processed faster than generation ones",
                 fontsize=9, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(file_name, dpi=200)


def main(argv: list[str]) -> int:
    panel_path = Path(argv[1]) if len(argv) > 1 else Path("gridqueue_panel.parquet")
    outdir = Path(argv[2]) if len(argv) > 2 else Path(".")
    if not panel_path.exists():
        print(f"No panel: {panel_path}\n"
              f"Build it with: gridqueue parse <documents...> --out {panel_path}",
              file=sys.stderr)
        return 2
    outdir.mkdir(parents=True, exist_ok=True)

    df = processing_time(load_panel(panel_path))
    tab, meta = summary_table(df)

    csv_path = outdir / "processing_time.csv"
    tab.to_csv(csv_path, index=False)
    fig(tab, outdir / "processing_time.png")

    for k, v in meta.items():
        print(f"{k}: {v}")
    print()
    columns = ["publisher", "class_description", "n", "median", "quartile_1", "quartile_3"]
    print(tab[columns].to_string(index=False))
    print(f"\nsaved: {csv_path} and {outdir / 'processing_time.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
