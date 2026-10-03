"""Odtworzenie figur, które zależą wyłącznie od panelu.

Zakres
------
Odtwarzane są trzy figury wyliczane z panelu: pokrycie pól schematu, naruszenia
reguł kontroli jakości oraz wynik rozstrzygania lokalizacji.

Dwóch figur ten skrypt NIE odtwarza i jest to zamierzone:

* figura architektury jest schematem rysowanym ręcznie, bez danych wejściowych;
* figura walidacji zależy od **zbioru odniesienia odczytanego wzrokowo przez
  człowieka**, publikowanego jako osobny artefakt, a nie wyliczanego przez kod.

Uruchomienie::

    python reproducibility/run_figures.py <panel.parquet> [katalog_wyjściowy]
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

SKROT = {
    "TAURON Dystrybucja S.A.": "TAURON",
    "ENERGA-OPERATOR S.A.": "ENERGA",
    "Stoen Operator Sp. z o.o.": "Stoen",
    "PSE S.A.": "PSE",
    "National Grid Electricity Distribution": "National Grid",
    "Boryszew Green Energy&Gas Sp. z o.o.": "Boryszew",
}
BARWY = {"TAURON": "#1b5e8c", "ENERGA": "#2e8b78", "Stoen": "#c77a1e",
         "PSE": "#7a4b9c", "National Grid": "#6b7280", "Boryszew": "#a33b4e"}
SZARY = "#6b7280"


def _th(n: int) -> str:
    return f"{int(n):,}".replace(",", "\u00a0")


def fig_pokrycie(panel: pd.DataFrame, plik: Path) -> None:
    st = schema_table()
    pola = st["pole"].tolist()
    rdzen = dict(zip(st["pole"], st["rdzen"].astype(bool)))
    publ = sorted(panel["publikujacy"].unique(),
                  key=lambda p: -int((panel["publikujacy"] == p).sum()))
    Z = np.zeros((len(pola), len(publ)))
    for j, p in enumerate(publ):
        sub = panel[panel["publikujacy"] == p]
        for i, f in enumerate(pola):
            s = sub[f] if f in sub.columns else pd.Series([None] * len(sub))
            nn = s.notna() & s.astype(str).str.strip().ne("") & s.astype(str).ne("nan")
            Z[i, j] = float(nn.mean())

    fig, ax = plt.subplots(figsize=(6.3, 5.6))
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "cov", ["#f7f7f7", "#c9dcea", "#5b93b8", "#1b5e8c"])
    ax.imshow(Z, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(publ)))
    ax.set_xticklabels(
        [f"{SKROT.get(p, p)}\n{_th(int((panel['publikujacy'] == p).sum()))}" for p in publ],
        fontsize=6)
    ax.set_yticks(range(len(pola)))
    ax.set_yticklabels([("\u2022 " if rdzen[f] else "   ") + f for f in pola], fontsize=6)
    for i, f in enumerate(pola):
        if rdzen[f]:
            ax.get_yticklabels()[i].set_fontweight("bold")
    for i in range(len(pola)):
        for j in range(len(publ)):
            v = Z[i, j]
            txt = "\u2014" if v == 0 else ("<1" if v < 0.005 else
                                           ("100" if v >= 0.995 else f"{v*100:.0f}"))
            ax.text(j, i, txt, ha="center", va="center", fontsize=5.4,
                    color="#ffffff" if v > 0.62 else ("#999999" if v == 0 else "#222222"))
    ax.set_xticks(np.arange(-.5, len(publ), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(pola), 1), minor=True)
    ax.grid(which="minor", color="#ffffff", lw=0.8)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(axis="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    niepokryte = [f for i, f in enumerate(pola) if Z[i].max() == 0]
    tytul = (f"Każde z {len(pola)} pól schematu jest wypełnione przez co najmniej "
             "jednego publikującego" if not niepokryte else
             f"Pola niepokryte w panelu: {', '.join(niepokryte)}")
    ax.set_title(tytul, fontsize=8, pad=22)
    ax.text(0, -1.35, "pokrycie pola, % wierszy danego publikującego   "
            "\u2022 = pole rdzenia bezwarunkowego   \u2014 = pole nieujawniane",
            fontsize=6, color=SZARY, transform=ax.transData)
    fig.tight_layout()
    fig.savefig(plik, dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_jakosc(panel: pd.DataFrame, plik: Path) -> None:
    rows = []
    for p, sub in panel.groupby("publikujacy"):
        for x in run_quality(sub.reset_index(drop=True)).as_dict()["reguly"]:
            rows.append({"kod": x["kod"], "nazwa": x["nazwa"],
                         "pub": SKROT.get(p, p), "naruszenia": x["naruszenia"]})
    jak = pd.DataFrame(rows)
    piv = (jak.pivot_table(index=["kod", "nazwa"], columns="pub",
                           values="naruszenia", aggfunc="sum")
              .fillna(0).astype(int))
    kol = [p for p in BARWY if p in piv.columns]
    piv = piv[kol]
    piv["razem"] = piv.sum(axis=1)
    piv = piv.reset_index().sort_values("razem")
    n = len(panel)

    fig, ax = plt.subplots(figsize=(6.8, 2.9))
    y = np.arange(len(piv))
    left = np.zeros(len(piv))
    for p in kol:
        v = piv[p].values.astype(float)
        if v.sum() == 0:
            continue
        ax.barh(y, v, left=left, height=0.62, color=BARWY[p], label=p, zorder=2)
        left += v
    szer = max(piv["razem"].max(), 1)
    for yy, tot in zip(y, piv["razem"].values):
        if tot == 0:
            ax.plot([0], [yy], "o", ms=3.2, color="#444444", zorder=3)
            ax.text(szer * 0.012, yy, "0 naruszeń", va="center", fontsize=6, color=SZARY)
        else:
            ax.text(tot + szer * 0.012, yy,
                    f"{_th(tot)}  ({tot / n * 100:.3f} %)".replace(".", ","),
                    va="center", fontsize=6)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{k}  {nm}" for k, nm in zip(piv["kod"], piv["nazwa"])], fontsize=6.5)
    ax.set_xlim(0, szer * 1.45)
    ax.set_xlabel(f"wiersze naruszające regułę (panel {_th(n)} wierszy)", fontsize=7)
    ax.set_title("Reguły wykrywają jakość źródła, nie błąd narzędzia — "
                 "i wskazują, który publikujący ją obniża", fontsize=8, loc="left")
    ax.legend(loc="lower right", fontsize=6, ncol=2, frameon=False,
              handlelength=1.1, columnspacing=1.0)
    ax.margins(y=0.06)
    fig.savefig(plik, dpi=300, bbox_inches="tight")
    plt.close(fig)


def fig_lokalizacja(panel: pd.DataFrame, plik: Path) -> None:
    def kat(wsp, powod):
        if pd.notna(wsp):
            return "rozwiązane"
        s = str(powod)
        if "kod_stacji" in s:
            return "kod stacji bez słownika"
        if "brak_deklaracji_miejscowosci" in s:
            return "brak deklaracji miejscowości"
        if "pusty_opis" in s:
            return "pusty opis"
        if "poza_gazeterem" in s:
            return "miejscowość poza gazeterem"
        if "wiele_kandydatow" in s or "niejednoznaczna" in s:
            return "wiele kandydatów"
        return "inne"

    d = panel.copy()
    d["pub"] = d["publikujacy"].map(lambda p: SKROT.get(p, p))
    d["_kat"] = [kat(w, r) for w, r in zip(d["wspolrzedne"], d.get("_geo_powod", pd.Series([None] * len(d))))]
    KAT = ["rozwiązane", "kod stacji bez słownika", "brak deklaracji miejscowości",
           "pusty opis", "miejscowość poza gazeterem", "wiele kandydatów", "inne"]
    KK = {"rozwiązane": "#2e8b78", "kod stacji bez słownika": "#1b5e8c",
          "brak deklaracji miejscowości": "#8fb4cc", "pusty opis": "#cfd8dd",
          "miejscowość poza gazeterem": "#c77a1e", "wiele kandydatów": "#7a4b9c",
          "inne": "#aaaaaa"}
    CT = (d.groupby(["pub", "_kat"]).size().unstack(fill_value=0)
           .reindex(columns=[k for k in KAT if k in d["_kat"].unique()], fill_value=0))
    CT = CT.reindex([p for p in BARWY if p in CT.index])
    assert int(CT.values.sum()) == len(d), "kategorie nie pokrywają wszystkich wierszy"

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
        r = int(CT.loc[p, "rozwiązane"]) if "rozwiązane" in CT.columns else 0
        ax.text(101.5, yy, f"{_th(r)} / {_th(int(CT.loc[p].sum()))}", va="center", fontsize=6)
    ax.set_yticks(ypos)
    ax.set_yticklabels(CT.index, fontsize=6.5)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("udział wierszy publikującego, %", fontsize=7)
    ax.set_title("Żaden publikujący nie ujawnia współrzędnych;\n"
                 "brak jest zwracany z przyczyną, nie zgadywany", fontsize=8, loc="left", pad=8)
    ax.legend(loc="upper center", bbox_to_anchor=(0.46, -0.30), ncol=3, fontsize=5.7,
              frameon=False, handlelength=1.0, columnspacing=0.9, handletextpad=0.4)

    ax2 = fig.add_subplot(gs[1])
    pw = d.loc[d["wspolrzedne"].notna(), "_geo_pewnosc"].value_counts()
    opis = {"EXACT": "dokładne", "UNIQUE_TOKEN": "unikalny człon",
            "SKRZYZOWANIE": "skrzyżowanie", "REVERSED": "odwrócona kolejność",
            "TOKEN_SUBSET": "podzbiór członów"}
    klucze = [k for k in opis if k in pw.index]
    vv = [int(pw[k]) for k in klucze]
    yb = np.arange(len(klucze))[::-1]
    ax2.barh(yb, vv, height=0.6, color="#2e8b78", zorder=2)
    for yy, v in zip(yb, vv):
        ax2.text(v + max(vv) * 0.02, yy, f"{v}  ({v / sum(vv) * 100:.1f} %)".replace(".", ","),
                 va="center", fontsize=6)
    ax2.set_yticks(yb)
    ax2.set_yticklabels([opis[k] for k in klucze], fontsize=6)
    ax2.set_xlim(0, max(vv) * 1.40)
    ax2.set_xlabel("wiersze", fontsize=7)
    ax2.set_title(f"Poziom pewności {_th(sum(vv))} rozwiązań:\n"
                  f"{vv[0] / sum(vv) * 100:.1f} % to dopasowanie dokładne".replace(".", ","),
                  fontsize=8, loc="left", pad=8)
    fig.savefig(plik, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("użycie: python reproducibility/run_figures.py <panel.parquet> [katalog]",
              file=sys.stderr)
        return 2
    p = Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else Path(__file__).resolve().parent / "wynik"
    out.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p, low_memory=False)

    fig_pokrycie(panel, out / "rys_pokrycie.png")
    fig_jakosc(panel, out / "rys_jakosc.png")
    fig_lokalizacja(panel, out / "rys_lokalizacja.png")
    print(f"schemat {SCHEMA_VERSION}; rdzeń bezwarunkowy: {', '.join(CORE_FIELDS)}")
    print(f"pól schematu: {len(FIELDS)}; wierszy panelu: {_th(len(panel))}")
    print(f"zapisano trzy figury do: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
