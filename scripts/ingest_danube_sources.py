"""Run one or all independent international Danube source adapters.

The runner never writes canonical/public data. It archives raw payloads and emits
reviewable candidate records plus validation summaries.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.sources import ADAPTERS, get_adapter
from scripts.sources.base import (
    AdapterError, FetchedPayload, archive_payload, ensure_payload, fetch_request, load_fixture_payloads,
    write_result,
)


def _fetch_all(adapter, archive_root: Path) -> tuple[dict[str, FetchedPayload], list[dict[str, Any]]]:
    payloads: dict[str, FetchedPayload] = {}
    archive: list[dict[str, Any]] = []
    pending = adapter.initial_requests()
    for request in pending:
        payload = fetch_request(request)
        payloads[request.label] = payload
        archive.append(archive_payload(payload, archive_root, adapter.source_id))
        ensure_payload(payload, request.expected_format)
    additional = adapter.additional_requests(payloads)
    for request in additional:
        payload = fetch_request(request)
        payloads[request.label] = payload
        archive.append(archive_payload(payload, archive_root, adapter.source_id))
        ensure_payload(payload, request.expected_format)
    return payloads, archive


def run_source(source: str, output_root: Path, archive_root: Path, fixture_root: Path | None = None) -> dict[str, Any]:
    adapter = get_adapter(source)
    source_output = output_root / source
    source_output.mkdir(parents=True, exist_ok=True)
    try:
        if fixture_root and adapter.initial_requests():
            payloads = load_fixture_payloads(fixture_root / source)
            archive = [archive_payload(payload, archive_root, adapter.source_id) for payload in payloads.values()]
        elif fixture_root:
            payloads, archive = {}, []
        else:
            payloads, archive = _fetch_all(adapter, archive_root)
        result = adapter.parse(payloads)
        write_result(result, source_output)
        (source_output / "archive_manifest.json").write_text(
            json.dumps(archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        return {
            "source": source, "adapter": adapter.source_id, "status": result.status,
            "publishable": result.publishable, "station_count": len(result.stations),
            "included_station_count": len([s for s in result.stations if s.included]),
            "observation_count": len(result.observations), "usable_observation_count": len(result.usable_observations),
            "suspect_observation_count": len(result.observations) - len(result.usable_observations), "forecast_count": len(result.forecasts),
            "critical_issue_count": len([i for i in result.issues if i.severity == "critical"]),
            "output": str(source_output),
        }
    except (AdapterError, KeyError, ValueError, OSError, UnicodeError) as exc:
        failure = {
            "source": source, "adapter": adapter.source_id, "status": "failed",
            "publishable": False, "error_type": type(exc).__name__, "error": str(exc),
            "output": str(source_output),
        }
        (source_output / "failure.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        return failure


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["all", *ADAPTERS], default="all")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--archive-root", type=Path, default=Path("data/archive"))
    parser.add_argument("--fixture-root", type=Path)
    parser.add_argument("--require-publishable", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = args.output_dir or Path("_diagnostics/international") / stamp
    sources = list(ADAPTERS) if args.source == "all" else [args.source]
    summaries = [run_source(source, output_root, args.archive_root, args.fixture_root) for source in sources]
    aggregate = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture_mode": bool(args.fixture_root), "sources": summaries,
        "failed_sources": [item["source"] for item in summaries if item["status"] == "failed"],
        "non_publishable_sources": [item["source"] for item in summaries if not item["publishable"]],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "summary.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    if aggregate["failed_sources"]:
        return 2
    if args.require_publishable and aggregate["non_publishable_sources"]:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
