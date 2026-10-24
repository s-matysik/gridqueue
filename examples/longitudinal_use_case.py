"""Research example: flows in the connection queue between editions.

Research question
-----------------
How does the connection queue change between two editions of the same register,
and does the register behave like a **monotone snapshot**, that is, do cases
enter it and leave it in step with the course of the proceedings, or do they
also appear and disappear outside that order?

Why this question is a precondition of any longitudinal analysis on this source:
if the register is not monotone, then the difference between editions is not the
same thing as a change in the state of the queue, and that has to be declared
rather than silently assumed.

Running::

    python examples/longitudinal_use_case.py <edition_A.xlsx> <edition_B.xlsx> \\
        [label_A] [label_B] [output_directory]

Produces::

    queue_flows.csv           summary of the flows
    status_transitions.csv    matrix of status transitions
    status_transitions.png    figure of the transition matrix
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from gridqueue import (SCHEMA_VERSION, STATUS_ORDER, TERMINAL_NEGATIVE,
                       __version__, compare_editions, detect_publisher,
                       get_adapter, linkage_audit)

DESCRIPTION = {
    "WNIOSEK_ZLOZONY": "application lodged",
    "WNIOSEK_NIEKOMPLETNY": "application incomplete",
    "W_TRAKCIE_ANALIZY": "under analysis",
    "WARUNKI_WYDANE": "conditions issued",
    "UMOWA_OBOWIAZUJACA": "agreement in force",
    "PRZYLACZONY": "connected",
    "ODMOWA": "refusal",
    "WNIOSEK_WYCOFANY": "application withdrawn",
    "WARUNKI_WYGASLE": "conditions expired",
}


def load(path: Path) -> pd.DataFrame:
    """Load an edition, recognising the publisher from the document."""
    key = detect_publisher(str(path))
    if key is None:
        raise SystemExit(f"publisher not recognised for {path}")
    return get_adapter(key).parse(str(path)).frame


def fig(tr: pd.DataFrame, file_name: Path, labels: tuple[str, str]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    order = [s for s in list(STATUS_ORDER) + sorted(TERMINAL_NEGATIVE)]
    idx = [s for s in order if s in tr.index]
    col = [s for s in order if s in tr.columns]
    M = tr.reindex(index=idx, columns=col, fill_value=0).astype(int).values
    Mz = M.copy()
    for i, a in enumerate(idx):
        for j, b in enumerate(col):
            if a == b:
                Mz[i, j] = 0

    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    ax.imshow(Mz, cmap="Blues", aspect="auto",
              vmin=0, vmax=max(1, Mz.max()))
    for i in range(len(idx)):
        for j in range(len(col)):
            if M[i, j] == 0:
                continue
            ongoing = idx[i] == col[j]
            ax.text(j, i, f"{M[i, j]}", ha="center", va="center", fontsize=6.5,
                    color="#9aa5ad" if ongoing else
                    ("#ffffff" if Mz[i, j] > Mz.max() * 0.6 else "#222222"))
    ax.set_xticks(range(len(col)))
    ax.set_xticklabels([DESCRIPTION.get(s, s) for s in col], rotation=40,
                       ha="right", fontsize=6.5)
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([DESCRIPTION.get(s, s) for s in idx], fontsize=6.5)
    ax.set_xlabel(f"status in edition {labels[1]}", fontsize=7.5)
    ax.set_ylabel(f"status in edition {labels[0]}", fontsize=7.5)
    ax.set_title("Status transitions run in step with the order of the proceedings,\n"
                 "which independently confirms the linkage by the content key",
                 fontsize=8, loc="left")
    ax.set_xticks(np.arange(-.5, len(col), 1), minor=True)
    ax.set_yticks(np.arange(-.5, len(idx), 1), minor=True)
    ax.grid(which="minor", color="#ffffff", lw=0.8)
    ax.tick_params(which="minor", length=0)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    fig.savefig(file_name, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    pa, pb = Path(argv[1]), Path(argv[2])
    ea = argv[3] if len(argv) > 3 else pa.stem
    eb = argv[4] if len(argv) > 4 else pb.stem
    out = Path(argv[5]) if len(argv) > 5 else Path(".")
    out.mkdir(parents=True, exist_ok=True)

    a, b = load(pa), load(pb)
    d = compare_editions(a, b, ea, eb)
    summary = d.as_dict()
    summary["gridqueue"] = __version__
    summary["schema_version"] = SCHEMA_VERSION

    audit = linkage_audit(a, b)
    summary.update({f"audit_{k}": v for k, v in audit.as_dict().items() if k != "pairs"})
    audit.discrepancies.to_csv(out / "linkage_audit_discrepancies.csv", index=False)

    pd.DataFrame([summary]).to_csv(out / "queue_flows.csv", index=False)
    d.transitions.to_csv(out / "status_transitions.csv")
    fig(d.transitions, out / "status_transitions.png", (ea, eb))

    for k, v in summary.items():
        print(f"{k}: {v}")
    print()
    print("Interpretation:")
    u = d.forward_share
    if u is not None:
        print(f"  {u * 100:.2f}% of transitions run in step with the order of the "
              "proceedings; this is an independent test of the linkage by the content "
              "key, because a key that linked at random would not produce that order.")
    if not summary["monotone_snapshot"]:
        print(f"  The register is NOT a monotone snapshot: {summary['new_closed']} "
              f"rows appear already in a closed state, and {summary['gone_active']} "
              "rows with an active status disappear. The difference between editions "
              "must not be read as a change in the state of the queue alone.")
    pa = audit.precision_lower * 100
    pg = audit.precision_upper * 100
    print(f"  Linkage precision assessed on the fields EXCLUDED from the key "
          f"(entity name, object name, application date, breakdown of capacity by technology) "
          f"is {pa:.2f}-{pg:.2f}% over all {audit.pairs} pairs: "
          f"{audit.confirmed} confirmed, {audit.uncertain} uncertain, "
          f"{audit.false_matches} false. This is not validation against an external truth, "
          f"because there is none for this register; the key does not force these fields "
          f"to agree, so their agreement is independent evidence.")
    print(f"  Rows dropped from the linkage as ambiguous: "
          f"{summary['rejected_as_ambiguous_a']} and "
          f"{summary['rejected_as_ambiguous_b']}; "
          f"in key collision there stand {summary['rows_in_collision_a']} and "
          f"{summary['rows_in_collision_b']} rows respectively.")

    print(f"\nsaved to: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
