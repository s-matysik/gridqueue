"""Reproduction of the validation numbers from the panel.

What this script does and what it does not
------------------------------------------
It reproduces the **derived numbers**: field coverage, the quality control rules,
the column shift audit and core completeness. It does so from a finished panel,
so it checks the reproducibility of the computations, not the reproducibility of
the extraction.

It does not reproduce **accuracy against the reference set**; that requires a
reference read visually from the document by a human and is published as an
artefact rather than computed by code.

The source documents are not redistributed: some of them are covered by the
rights of their publishers, and all of them are replaced quarterly under the
statutory duty. ``manifest.csv`` gives the address, the download date and the
SHA-256 for each of them, so a person reproducing the work can download exactly
these files or find that the publisher has already issued a different edition,
and should then **expect different row counts**.

Running::

    python reproducibility/run_validation.py <panel.parquet> [output_directory]
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
    """Compare the SHA-256 of the documents in the given directory with the manifest."""
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

    # consistency check: the sum over publishers has to equal the panel figure
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

    # Comparison with the values expected for this release. The package version
    # number is deliberately left out: we check whether the NUMBERS agree, not
    # whether somebody ran exactly the same tag.
    oczek_plik = Path(__file__).parent / "expected" / "expected_panel_stats.json"
    rozjazd: dict = {}
    if oczek_plik.exists():
        oczek = json.loads(oczek_plik.read_text(encoding="utf-8"))
        for k, v in oczek.items():
            if k in {"gridqueue", "niezgodnosc_suma_vs_panel"}:
                continue
            if podsum.get(k) != v:
                rozjazd[k] = {"oczekiwano": v, "otrzymano": podsum.get(k)}

    for k, v in podsum.items():
        print(f"{k}: {v}")
    if rozjazd:
        print("\nERROR: the result does not match the values expected for this release.",
              file=sys.stderr)
        for k, v in rozjazd.items():
            print(f"  {k}: expected {v['oczekiwano']}, got {v['otrzymano']}",
                  file=sys.stderr)
        return 1
    if oczek_plik.exists():
        print("\nagreement with expected/expected_panel_stats.json: OK")
    if niezgodne:
        print("\nWARNING: the sum of violations over publishers does not close to the panel.",
              file=sys.stderr)
        return 1
    print(f"\nsaved to: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
