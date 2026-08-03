#!/usr/bin/env python3
"""Extrage semantic tabelul de prognoze din pagina HTML AFDJ."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.afdj_core import parse_html_forecasts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = parse_html_forecasts(args.html.read_bytes())
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
