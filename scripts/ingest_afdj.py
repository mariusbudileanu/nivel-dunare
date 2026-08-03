#!/usr/bin/env python3
"""Descarcă și ingerează o captură AFDJ."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.afdj_core import HTML_URL, XML_URL, download, project_root, run_ingestion, sha256_bytes


def file_result(path: Path, url: str, content_type: str) -> dict:
    body = path.read_bytes()
    return {
        "body": body, "requested_url": url, "final_url": url, "status": 200,
        "headers": {"Content-Type": content_type, "Content-Length": str(len(body))},
        "attempts": 0, "sha256": sha256_bytes(body), "size_bytes": len(body),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=project_root())
    parser.add_argument("--xml-file", type=Path)
    parser.add_argument("--html-file", type=Path)
    parser.add_argument("--source", default="live")
    args = parser.parse_args()
    xml_result = file_result(args.xml_file, XML_URL, "text/xml; charset=UTF-8") if args.xml_file else download(XML_URL, ("xml",))
    html_result = file_result(args.html_file, HTML_URL, "text/html; charset=UTF-8") if args.html_file else download(HTML_URL, ("html", "xhtml"))
    result = run_ingestion(args.root.resolve(), xml_result, html_result, source=args.source)
    print("Ingestie AFDJ reușită")
    for key in ("station_count", "observation_date", "forecast_issue_date", "ambiguous_zero_count", "xml_html_mismatch_count", "canonical_changed", "xml_archive_path"):
        print(f"{key}: {result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
