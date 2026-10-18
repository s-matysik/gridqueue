"""Research example: processing time of a connection application.

Research question
-----------------
Does the time from lodging a connection application to the issue of connection
conditions differ between resource classes and between publishers?

What this example shows about the tool
--------------------------------------
Adapters are source specific, but **the research analysis is not**. The code
below contains not a single branch that depends on the publisher: it works only
on the fields of the common schema (`data_wniosku`, `data_warunkow`,
`klasa_zasobu`, `publikujacy`) and runs identically on the output of every
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

    czas_rozpatrywania.csv   the result table (one row per publisher and class)
    czas_rozpatrywania.png   the figure
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from gridqueue import SCHEMA_VERSION, __version__, core_complete_mask

#: Minimum group size below which we do not report medians.
MIN_N = 30

#: Readable names of the resource classes from the controlled vocabulary of the schema.
NAZWY_KLAS = {
    "ODB": "demand",
    "PV": "photovoltaics",
    "FW": "wind",
    "BESS": "energy storage",
    "GAZ": "gas",
    "EW": "hydro",
    "MIX": "mixed installation",
    "SIEC": "network",
    "BIOGAZ": "biogas",
}


def wczytaj_panel(sciezka: Path) -> pd.DataFrame:
    if sciezka.suffix == ".parquet":
        return pd.read_parquet(sciezka)
    return pd.read_csv(sciezka, low_memory=False)


def czas_rozpatrywania(panel: pd.DataFrame) -> pd.DataFrame:
    """Time from lodging the application to the issue of conditions, in days."""
    df = panel.copy()
    for kol in ("data_wniosku", "data_warunkow"):
        df[kol] = pd.to_datetime(df[kol], errors="coerce")
    df["czas_dni"] = (df["data_warunkow"] - df["data_wniosku"]).dt.days
    return df


def zestawienie(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Medians and interquartile ranges per publisher and resource class.

    Rows with a negative date difference are dropped and counted separately: an
    inconsistency in the order of dates is detected by quality rule R1 and should
    not enter the descriptive statistics as a negative value.
    """
    policzalne = df["czas_dni"].notna()
    ujemne = policzalne & (df["czas_dni"] < 0)
    ok = df.loc[policzalne & ~ujemne]

    tab = (ok.groupby(["publikujacy", "klasa_zasobu"])["czas_dni"]
             .agg(n="size", mediana="median",
                  kwartyl_1=lambda s: s.quantile(0.25),
                  kwartyl_3=lambda s: s.quantile(0.75))
             .reset_index())
    tab = tab.loc[tab["n"] >= MIN_N].copy()
    tab["rozstep_cwiartkowy"] = tab["kwartyl_3"] - tab["kwartyl_1"]
    tab["klasa_opis"] = tab["klasa_zasobu"].map(NAZWY_KLAS).fillna(tab["klasa_zasobu"])
    tab = tab.sort_values(["publikujacy", "mediana"]).reset_index(drop=True)

    meta = {
        "gridqueue": __version__,
        "schema_version": SCHEMA_VERSION,
        "wierszy_panelu": int(len(df)),
        "wierszy_z_kompletnym_rdzeniem": int(core_complete_mask(df).sum()),
        "wierszy_z_policzalnym_czasem": int(len(ok)),
        "odrzucone_ujemne": int(ujemne.sum()),
        "grup_ponizej_progu_pominieto": int(
            ok.groupby(["publikujacy", "klasa_zasobu"]).size().lt(MIN_N).sum()),
        "min_n_grupy": MIN_N,
        "mediana_ogolem_dni": float(ok["czas_dni"].median()),
    }
    return tab, meta


def rysunek(tab: pd.DataFrame, plik: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # The colour is bound to the NAME of the publisher, not to the position in the
    # sorted list: otherwise adding a publisher would repaint the others and the
    # figure would drift away from the other figures of the project. A regression
    # from release 1.1.0, restored here.
    BARWY = {
        "TAURON Dystrybucja S.A.": "#1b5e8c",
        "ENERGA-OPERATOR S.A.": "#2e8b78",
        "Stoen Operator Sp. z o.o.": "#c77a1e",
        "PSE S.A.": "#7a4b9c",
        "National Grid Electricity Distribution": "#6b7280",
        "Boryszew Green Energy&Gas Sp. z o.o.": "#a33b4e",
    }
    ZAPAS = "#555555"
    fig, ax = plt.subplots(figsize=(6.6, 0.30 * len(tab) + 1.7))
    for i, (_, r) in enumerate(tab.iterrows()):
        ax.plot([r["kwartyl_1"], r["kwartyl_3"]], [i, i], lw=3.2, alpha=0.35,
                color=BARWY.get(r["publikujacy"], ZAPAS),
                solid_capstyle="butt")
        ax.plot([r["mediana"]], [i], "o", ms=5, color=BARWY.get(r["publikujacy"], ZAPAS))
        ax.text(r["kwartyl_3"] + 8, i, f"{r['mediana']:.0f} d  (n={int(r['n'])})",
                va="center", fontsize=7)
    ax.set_yticks(list(range(len(tab))))
    ax.set_yticklabels([f"{r['klasa_opis']}, {r['publikujacy'].split()[0]}"
                        for _, r in tab.iterrows()], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, tab["kwartyl_3"].max() * 1.30)
    ax.set_xlabel("days: application → conditions\n"
                  "dot = median, band = interquartile range", fontsize=8)
    ax.set_title("Demand connections are processed faster than generation ones",
                 fontsize=9, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(plik, dpi=200)


def main(argv: list[str]) -> int:
    panel_path = Path(argv[1]) if len(argv) > 1 else Path("gridqueue_panel.parquet")
    outdir = Path(argv[2]) if len(argv) > 2 else Path(".")
    if not panel_path.exists():
        print(f"No panel: {panel_path}\n"
              f"Build it with: gridqueue parse <documents...> --out {panel_path}",
              file=sys.stderr)
        return 2
    outdir.mkdir(parents=True, exist_ok=True)

    df = czas_rozpatrywania(wczytaj_panel(panel_path))
    tab, meta = zestawienie(df)

    csv_path = outdir / "czas_rozpatrywania.csv"
    tab.to_csv(csv_path, index=False)
    rysunek(tab, outdir / "czas_rozpatrywania.png")

    for k, v in meta.items():
        print(f"{k}: {v}")
    print()
    kolumny = ["publikujacy", "klasa_opis", "n", "mediana", "kwartyl_1", "kwartyl_3"]
    print(tab[kolumny].to_string(index=False))
    print(f"\nsaved: {csv_path} and {outdir / 'czas_rozpatrywania.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
