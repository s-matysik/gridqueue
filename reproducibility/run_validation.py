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

ROOT = Path(__file__).resolve().parent


def check_sums(catalog: Path) -> dict:
    """Compare the SHA-256 of the documents in the given directory with the manifest."""
    man = pd.read_csv(ROOT / "manifest.csv")
    result = {"matching": [], "different": [], "missing": []}
    for _, r in man.iterrows():
        p = catalog / r["file_name"]
        if not p.exists():
            result["missing"].append(r["file_name"])
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        (result["matching"] if h == r["sha256"] else result["different"]).append(r["file_name"])
    return result


def field_coverage(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pub, sub in panel.groupby("publisher"):
        d = {"publisher": pub, "n_rows": int(len(sub))}
        for f in FIELDS:
            s = sub[f] if f in sub.columns else pd.Series([None] * len(sub))
            nn = s.notna() & s.astype(str).str.strip().ne("") & s.astype(str).ne("nan")
            d[f] = round(float(nn.mean()), 4)
        rows.append(d)
    d = {"publisher": "PANEL TOTAL", "n_rows": int(len(panel))}
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
    outdir = Path(argv[2]) if len(argv) > 2 else ROOT / "result"
    outdir.mkdir(parents=True, exist_ok=True)

    panel = (pd.read_parquet(panel_path) if panel_path.suffix == ".parquet"
             else pd.read_csv(panel_path, low_memory=False))

    cov = field_coverage(panel)
    cov.to_csv(outdir / "field_coverage.csv", index=False)

    rules = []
    for pub, sub in panel.groupby("publisher"):
        for x in run_quality(sub.reset_index(drop=True)).as_dict()["rules"]:
            rules.append({"publisher": pub, "code": x["code"], "name": x["name"],
                           "violations": x["violations"], "share": x["share"]})
    rep_panel = run_quality(panel).as_dict()
    for x in rep_panel["rules"]:
        rules.append({"publisher": "PANEL TOTAL", "code": x["code"], "name": x["name"],
                       "violations": x["violations"], "share": x["share"]})
    how = pd.DataFrame(rules)
    how.to_csv(outdir / "quality_rules.csv", index=False)

    # consistency check: the sum over publishers has to equal the panel figure
    after_publication = (how[how["publisher"] != "PANEL TOTAL"]
               .groupby("code")["violations"].sum())
    panel_values = (how[how["publisher"] == "PANEL TOTAL"]
                .set_index("code")["violations"])
    inconsistent = {k: (int(after_publication[k]), int(panel_values[k]))
                 for k in panel_values.index if int(after_publication[k]) != int(panel_values[k])}

    filled_fields = int(sum(
        1 for f in FIELDS
        if float(cov.loc[cov["publisher"] == "PANEL TOTAL", f].iloc[0]) > 0))

    summary = {
        "gridqueue": __version__,
        "schema_version": SCHEMA_VERSION,
        "panel_rows": int(len(panel)),
        "panel_columns": int(panel.shape[1]),
        "publishers": int(panel["publisher"].nunique()),
        "filled_schema_fields": f"{filled_fields}/{len(FIELDS)}",
        "rows_with_complete_core": int(core_complete_mask(panel).sum()),
        "violations_total": int(sum(x["violations"] for x in rep_panel["rules"])),
        "mismatch_sum_vs_panel": inconsistent,
    }
    (outdir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    # Comparison with the values expected for this release. The package version
    # number is deliberately left out: we check whether the NUMBERS agree, not
    # whether somebody ran exactly the same tag.
    expected_file = Path(__file__).parent / "expected" / "expected_panel_stats.json"
    mismatch: dict = {}
    if expected_file.exists():
        expected = json.loads(expected_file.read_text(encoding="utf-8"))
        for k, v in expected.items():
            if k in {"gridqueue", "mismatch_sum_vs_panel"}:
                continue
            if summary.get(k) != v:
                mismatch[k] = {"expected": v, "received": summary.get(k)}

    for k, v in summary.items():
        print(f"{k}: {v}")
    if mismatch:
        print("\nERROR: the result does not match the values expected for this release.",
              file=sys.stderr)
        for k, v in mismatch.items():
            print(f"  {k}: expected {v['expected']}, got {v['received']}",
                  file=sys.stderr)
        return 1
    if expected_file.exists():
        print("\nagreement with expected/expected_panel_stats.json: OK")
    if inconsistent:
        print("\nWARNING: the sum of violations over publishers does not close to the panel.",
              file=sys.stderr)
        return 1
    print(f"\nsaved to: {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
