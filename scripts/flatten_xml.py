#!/usr/bin/env python3
"""Generează un CSV flat raw cu o coloană pentru fiecare leaf path XML."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.afdj_core import flatten_xml, write_csv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, columns = flatten_xml(args.xml.read_bytes())
    write_csv(args.output, columns, rows, gzip_output=args.output.suffix == ".gz")
    print(f"{len(rows)} stații, {len(columns)} căi leaf -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
