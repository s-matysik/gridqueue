"""Command-line interface: ``gridqueue parse | validate | export | compare | plot``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__
from .layout import audit_column_shift
from .quality import run_quality
from .registry import REGISTRY, declarations, detect_publisher, get_adapter
from .schema import FIELDS, schema_table, validate_frame


def _read_table(path: str):
    import pandas as pd

    p = Path(path)
    if p.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    return pd.read_csv(p)


def _write_table(df, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() in {".parquet", ".pq"}:
        df.to_parquet(p, index=False)
    elif p.suffix.lower() in {".json", ".jsonl"}:
        df.to_json(p, orient="records", force_ascii=False, indent=2)
    else:
        df.to_csv(p, index=False)


def cmd_parse(args) -> int:
    import pandas as pd

    key = args.adapter or (detect_publisher(args.source[0]) if args.source else None)
    if key is None:
        print("publisher not recognized; provide --adapter", file=sys.stderr)
        return 2
    adapter = get_adapter(key)
    source = args.source if len(args.source) > 1 else (args.source[0] if args.source else None)
    res = adapter.parse(source)
    _write_table(res.frame, args.out)
    audit = audit_column_shift(res.frame)
    report = {
        "adapter": key,
        "deklaracja": adapter.declaration(),
        "raport_wydobycia": res.report,
        "audyt_przesuniecia_kolumn": audit.as_dict(),
        "wyjscie": args.out,
        "n_wierszy": int(len(res.frame)),
    }
    if args.report:
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "raport_wydobycia"},
                     ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_validate(args) -> int:
    df = _read_table(args.input)
    schema_rep = validate_frame(df)
    qual = run_quality(df).as_dict()
    audit = audit_column_shift(df).as_dict()
    out = {"schemat": schema_rep, "jakosc": qual, "przesuniecie_kolumn": audit}
    text = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def cmd_export(args) -> int:
    import pandas as pd

    frames = [_read_table(p) for p in args.input]
    df = pd.concat(frames, ignore_index=True)
    if args.only_schema:
        keep = [c for c in FIELDS if c in df.columns] + \
               [c for c in ("publikujacy", "jurysdykcja", "dokument_zrodlowy") if c in df.columns]
        df = df[keep]
    _write_table(df, args.out)
    print(json.dumps({"wierszy": int(len(df)), "kolumn": int(df.shape[1]),
                      "wyjscie": args.out}, ensure_ascii=False, indent=2))
    return 0


def cmd_compare(args) -> int:
    from .longitudinal import (NODE_KEY_FIELDS, DEFAULT_KEY_FIELDS, compare_editions,
                               linkage_audit, linkage_recall)

    a, b = _read_table(args.edition_a), _read_table(args.edition_b)
    fields = NODE_KEY_FIELDS if args.node_key else DEFAULT_KEY_FIELDS
    delta = compare_editions(a, b, args.label_a, args.label_b, fields=fields)
    out = {"klucz": list(fields), "porownanie": delta.as_dict(),
           "audyt_dopasowania": linkage_audit(a, b, fields=fields).as_dict(),
           "czulosc_dopasowania": linkage_recall(a, b, fields=fields).as_dict()}
    text = json.dumps(out, ensure_ascii=False, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    if args.transitions:
        delta.przejscia.to_csv(args.transitions)
    print(text)
    return 0


def cmd_plot(args) -> int:
    try:
        from .plots import save_all
    except ImportError as e:  # pragma: no cover
        print(str(e), file=sys.stderr)
        return 2
    df = _read_table(args.input)
    b = _read_table(args.edition_b) if args.edition_b else None
    saved = save_all(df, args.out, edition_b=b, labels=(args.label_a, args.label_b),
                     formats=[f.strip() for f in args.format.split(",") if f.strip()],
                     dpi=args.dpi, min_n=args.min_n, min_coverage=args.min_coverage)
    skipped = saved.pop("_skipped", [])
    print(json.dumps({"zapisane": {k: [str(p) for p in v] for k, v in saved.items()},
                      "pominiete": skipped}, ensure_ascii=False, indent=2))
    return 0


def cmd_schema(args) -> int:
    t = schema_table()
    if args.out:
        _write_table(t, args.out)
    print(t.to_string(index=False, max_colwidth=60))
    return 0


def cmd_adapters(args) -> int:
    print(json.dumps(declarations(), ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="gridqueue",
        description="Harmonizer of statutory connection disclosures (Art. 7(8l) of the Energy Law)")
    ap.add_argument("--version", action="version", version=f"gridqueue {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="parse a publisher document into the schema")
    p.add_argument("source", nargs="*", help="path(s) to the document; none = fetch from the network")
    p.add_argument("--adapter", choices=sorted(REGISTRY), help="force an adapter")
    p.add_argument("--out", required=True, help="output file (.csv/.parquet/.json)")
    p.add_argument("--report", help="JSON report file")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("validate", help="validate a dataset against the schema and quality rules")
    p.add_argument("input")
    p.add_argument("--out", help="JSON report file")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("export", help="assemble a panel from multiple datasets")
    p.add_argument("input", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--only-schema", action="store_true",
                   help="omit extensions (columns with the _ prefix)")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("compare", help="compare two editions of one register (flows, transitions, "
                                       "linkage precision and sensitivity)")
    p.add_argument("edition_a", help="earlier edition (.parquet/.csv in the schema)")
    p.add_argument("edition_b", help="later edition")
    p.add_argument("--label-a", default="A")
    p.add_argument("--label-b", default="B")
    p.add_argument("--node-key", action="store_true",
                   help="use the node key (publikujacy, id_wezla) for NODE-entity registers")
    p.add_argument("--out", help="JSON report file")
    p.add_argument("--transitions", help="CSV file for the status transition matrix")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("plot", help="draw every chart the dataset supports (needs matplotlib)")
    p.add_argument("input", help="dataset in the schema (.parquet/.csv)")
    p.add_argument("--edition-b", help="a later edition: adds the edition-comparison chart")
    p.add_argument("--label-a", default="A")
    p.add_argument("--label-b", default="B")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--format", default="png", help="comma-separated: png,svg,pdf")
    p.add_argument("--dpi", type=int, default=200)
    p.add_argument("--min-n", type=int, default=30,
                   help="minimum group size for the processing-time curves")
    p.add_argument("--min-coverage", type=float, default=0.8,
                   help="minimum share of applications carrying both dates (default 0.8)")
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("schema", help="print the schema specification")
    p.add_argument("--out")
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("adapters", help="print adapter declarations")
    p.set_defaults(func=cmd_adapters)
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
