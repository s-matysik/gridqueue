"""Odtworzenie liczb walidacyjnych z panelu.

Co ten skrypt robi, a czego nie
-------------------------------
Odtwarza **liczby pochodne**: pokrycie pól, reguły kontroli jakości, audyt
przesunięcia kolumn i kompletność rdzenia. Robi to z gotowego panelu, więc
sprawdza odtwarzalność obliczeń, nie odtwarzalność wydobycia.

Nie odtwarza **dokładności wobec zbioru odniesienia** — ta wymaga wzorca
odczytanego wzrokowo z dokumentu przez człowieka i jest opublikowana jako
artefakt, a nie wyliczana przez kod.

Dokumenty źródłowe nie są redystrybuowane: część z nich jest objęta prawami
publikujących, a wszystkie są wymieniane kwartalnie na mocy obowiązku ustawowego.
``manifest.csv`` podaje dla każdego adres, datę pobrania i SHA-256, więc osoba
odtwarzająca pracę może pobrać dokładnie te pliki albo stwierdzić, że publikujący
wydał już inną edycję — i wtedy **powinna oczekiwać innych liczb wierszy**.

Uruchomienie::

    python reproducibility/run_validation.py <panel.parquet> [katalog_wyjściowy]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

from gridqueue import (FIELDS, SCHEMA_VERSION, __version__, core_complete_mask,
                       run_quality)

KOREN = Path(__file__).resolve().parent


def sprawdz_sumy(katalog: Path) -> dict:
    """Porównaj SHA-256 dokumentów w podanym katalogu z manifestem."""
    man = pd.read_csv(KOREN / "manifest.csv")
    wynik = {"zgodne": [], "rozne": [], "brakujace": []}
    for _, r in man.iterrows():
        p = katalog / r["plik"]
        if not p.exists():
            wynik["brakujace"].append(r["plik"])
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        (wynik["zgodne"] if h == r["sha256"] else wynik["rozne"]).append(r["plik"])
    return wynik


def pokrycie_pol(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pub, sub in panel.groupby("publikujacy"):
        d = {"publikujacy": pub, "n_wierszy": int(len(sub))}
        for f in FIELDS:
            s = sub[f] if f in sub.columns else pd.Series([None] * len(sub))
            nn = s.notna() & s.astype(str).str.strip().ne("") & s.astype(str).ne("nan")
            d[f] = round(float(nn.mean()), 4)
        rows.append(d)
    d = {"publikujacy": "PANEL RAZEM", "n_wierszy": int(len(panel))}
    for f in FIELDS:
        s = panel[f] if f in panel.columns else pd.Series([None] * len(panel))
        nn = s.notna() & s.astype(str).str.strip().ne("") & s.astype(str).ne("nan")
        d[f] = round(float(nn.mean()), 4)
    rows.append(d)
    return pd.DataFrame(rows)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    panel_path = Path(argv[1])
    outdir = Path(argv[2]) if len(argv) > 2 else KOREN / "wynik"
    outdir.mkdir(parents=True, exist_ok=True)

    panel = (pd.read_parquet(panel_path) if panel_path.suffix == ".parquet"
             else pd.read_csv(panel_path, low_memory=False))

    cov = pokrycie_pol(panel)
    cov.to_csv(outdir / "pokrycie_pol.csv", index=False)

    reguly = []
    for pub, sub in panel.groupby("publikujacy"):
        for x in run_quality(sub.reset_index(drop=True)).as_dict()["reguly"]:
            reguly.append({"publikujacy": pub, "kod": x["kod"], "nazwa": x["nazwa"],
                           "naruszenia": x["naruszenia"], "udzial": x["udzial"]})
    rep_panel = run_quality(panel).as_dict()
    for x in rep_panel["reguly"]:
        reguly.append({"publikujacy": "PANEL RAZEM", "kod": x["kod"], "nazwa": x["nazwa"],
                       "naruszenia": x["naruszenia"], "udzial": x["udzial"]})
    jak = pd.DataFrame(reguly)
    jak.to_csv(outdir / "reguly_jakosci.csv", index=False)

    # kontrola spójności: suma po publikujących musi równać się panelowi
    po_publ = (jak[jak["publikujacy"] != "PANEL RAZEM"]
               .groupby("kod")["naruszenia"].sum())
    panelowe = (jak[jak["publikujacy"] == "PANEL RAZEM"]
                .set_index("kod")["naruszenia"])
    niezgodne = {k: (int(po_publ[k]), int(panelowe[k]))
                 for k in panelowe.index if int(po_publ[k]) != int(panelowe[k])}

    pola_wypelnione = int(sum(
        1 for f in FIELDS
        if float(cov.loc[cov["publikujacy"] == "PANEL RAZEM", f].iloc[0]) > 0))

    podsum = {
        "gridqueue": __version__,
        "schema_version": SCHEMA_VERSION,
        "wierszy_panelu": int(len(panel)),
        "kolumn_panelu": int(panel.shape[1]),
        "publikujacych": int(panel["publikujacy"].nunique()),
        "pol_schematu_wypelnionych": f"{pola_wypelnione}/{len(FIELDS)}",
        "wierszy_z_kompletnym_rdzeniem": int(core_complete_mask(panel).sum()),
        "naruszen_lacznie": int(sum(x["naruszenia"] for x in rep_panel["reguly"])),
        "niezgodnosc_suma_vs_panel": niezgodne,
    }
    (outdir / "podsumowanie.json").write_text(
        json.dumps(podsum, ensure_ascii=False, indent=1), encoding="utf-8")

    for k, v in podsum.items():
        print(f"{k}: {v}")
    if niezgodne:
        print("\nUWAGA: suma naruszeń po publikujących nie domyka się do panelu.",
              file=sys.stderr)
        return 1
    print(f"\nzapisano do: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
