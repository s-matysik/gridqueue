"""Przykład badawczy: czas rozpatrywania wniosku przyłączeniowego.

Pytanie badawcze
----------------
Czy czas od złożenia wniosku o przyłączenie do wydania warunków różni się między
klasami zasobu i między publikującymi?

Sens tego przykładu dla oceny narzędzia
---------------------------------------
Adaptery są specyficzne dla źródła, ale **analiza badawcza już nie**. Poniższy
kod nie zawiera ani jednej gałęzi zależnej od publikującego: operuje wyłącznie
na polach wspólnego schematu (`data_wniosku`, `data_warunkow`, `klasa_zasobu`,
`publikujacy`) i wykonuje się identycznie na wyjściu każdego adaptera. Dokładnie
to jest produktem harmonizacji — nie sam fakt, że dokument dał się rozłożyć na
wiersze.

Dane wejściowe
--------------
Panel wyprodukowany przez `gridqueue` (Parquet albo CSV), domyślnie
``gridqueue_panel.parquet`` w katalogu bieżącym. Panel buduje się poleceniem::

    gridqueue parse <dokumenty...> --out gridqueue_panel.parquet

Uruchomienie::

    python examples/research_use_case.py [ścieżka_do_panelu] [katalog_wyjściowy]

Wytwarza::

    czas_rozpatrywania.csv   tabela wynikowa (jeden wiersz na publikującego i klasę)
    czas_rozpatrywania.png   figura
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from gridqueue import SCHEMA_VERSION, __version__, core_complete_mask

#: Minimalna liczebność grupy, poniżej której mediany nie raportujemy.
MIN_N = 30

#: Czytelne nazwy klas zasobu ze słownika kontrolowanego schematu.
NAZWY_KLAS = {
    "ODB": "odbiór",
    "PV": "fotowoltaika",
    "FW": "wiatr",
    "BESS": "magazyn energii",
    "GAZ": "gaz",
    "EW": "woda",
    "MIX": "instalacja mieszana",
    "SIEC": "sieć",
    "BIOGAZ": "biogaz",
}


def wczytaj_panel(sciezka: Path) -> pd.DataFrame:
    if sciezka.suffix == ".parquet":
        return pd.read_parquet(sciezka)
    return pd.read_csv(sciezka, low_memory=False)


def czas_rozpatrywania(panel: pd.DataFrame) -> pd.DataFrame:
    """Czas od złożenia wniosku do wydania warunków, w dniach."""
    df = panel.copy()
    for kol in ("data_wniosku", "data_warunkow"):
        df[kol] = pd.to_datetime(df[kol], errors="coerce")
    df["czas_dni"] = (df["data_warunkow"] - df["data_wniosku"]).dt.days
    return df


def zestawienie(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Mediany i rozstępy ćwiartkowe per publikujący i klasa zasobu.

    Wiersze z ujemną różnicą dat są odrzucane i zliczane osobno: niespójność
    kolejności dat wykrywa reguła R1 kontroli jakości i nie powinna wchodzić do
    statystyki opisowej jako wartość ujemna.
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

    # Barwa przypisana NAZWIE publikującego, nie pozycji w posortowanej liście:
    # inaczej dodanie publikującego przemalowałoby pozostałych, a figura rozeszłaby
    # się z pozostałymi figurami projektu. Regresja z wydania 1.1.0, przywrócona tu.
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
    ax.set_yticklabels([f"{r['klasa_opis']} — {r['publikujacy'].split()[0]}"
                        for _, r in tab.iterrows()], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlim(0, tab["kwartyl_3"].max() * 1.30)
    ax.set_xlabel("dni: wniosek → warunki\n"
                  "kropka = mediana, pasmo = rozstęp ćwiartkowy", fontsize=8)
    ax.set_title("Przyłączenia odbiorcze rozpatrywane są szybciej niż wytwórcze",
                 fontsize=9, loc="left")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    fig.savefig(plik, dpi=200)


def main(argv: list[str]) -> int:
    panel_path = Path(argv[1]) if len(argv) > 1 else Path("gridqueue_panel.parquet")
    outdir = Path(argv[2]) if len(argv) > 2 else Path(".")
    if not panel_path.exists():
        print(f"Brak panelu: {panel_path}\n"
              f"Zbuduj go: gridqueue parse <dokumenty...> --out {panel_path}",
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
    print(f"\nzapisano: {csv_path} oraz {outdir / 'czas_rozpatrywania.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
