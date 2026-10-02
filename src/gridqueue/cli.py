"""Interfejs wiersza poleceń: ``gridqueue parse | validate | export``."""

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
        print("nie rozpoznano publikującego; podaj --adapter", file=sys.stderr)
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
        description="Harmonizator ustawowych ujawnień przyłączeniowych (art. 7 ust. 8l PE)")
    ap.add_argument("--version", action="version", version=f"gridqueue {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("parse", help="sparsuj dokument publikującego do schematu")
    p.add_argument("source", nargs="*", help="ścieżka(-i) do dokumentu; brak = pobierz z sieci")
    p.add_argument("--adapter", choices=sorted(REGISTRY), help="wymuś adapter")
    p.add_argument("--out", required=True, help="plik wyjściowy (.csv/.parquet/.json)")
    p.add_argument("--report", help="plik raportu JSON")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("validate", help="waliduj zbiór wobec schematu i reguł jakości")
    p.add_argument("input")
    p.add_argument("--out", help="plik raportu JSON")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("export", help="złóż panel z wielu zbiorów")
    p.add_argument("input", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--only-schema", action="store_true",
                   help="pomiń rozszerzenia (kolumny z przedrostkiem _)")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("schema", help="wypisz specyfikację schematu")
    p.add_argument("--out")
    p.set_defaults(func=cmd_schema)

    p = sub.add_parser("adapters", help="wypisz deklaracje adapterów")
    p.set_defaults(func=cmd_adapters)
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
