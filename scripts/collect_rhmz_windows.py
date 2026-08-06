#!/usr/bin/env python3
"""Collect official RHMZ payloads with Windows curl/Schannel and parse candidates."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.sources.base import (
    USER_AGENT, FetchedPayload, SourceAccessError, SourceRequest,
    archive_payload, ensure_payload, write_result,
)
from scripts.sources.hidmet_rs import HidmetAdapter


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _last_header_block(raw: bytes) -> dict[str, str]:
    text = raw.decode("iso-8859-1", "replace").replace("\r\n", "\n")
    blocks = [block for block in text.split("\n\n") if block.lstrip().startswith("HTTP/")]
    if not blocks:
        return {}
    result: dict[str, str] = {}
    for line in blocks[-1].splitlines()[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def fetch_with_schannel(request: SourceRequest, timeout: int = 60) -> tuple[FetchedPayload, dict[str, Any]]:
    curl = shutil.which("curl.exe")
    if os.name != "nt" or not curl:
        raise SourceAccessError("RHMZ Schannel collection requires windows-latest and curl.exe")
    captured = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="rhmz-schannel-") as temporary:
        root = Path(temporary)
        body_path, header_path = root / "body.bin", root / "headers.bin"
        command = [
            curl, "--silent", "--show-error", "--location", "--max-redirs", "10",
            "--connect-timeout", "20", "--max-time", str(timeout),
            "--user-agent", USER_AGENT, "--header", f"Accept: {request.accept}",
            "--header", "Accept-Encoding: identity", "--output", str(body_path),
            "--dump-header", str(header_path),
            "--write-out", "%{http_code}\n%{url_effective}\n%{content_type}\n%{remote_ip}\n%{ssl_verify_result}\n%{http_version}",
            request.url,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 10, check=False)
        fields = completed.stdout.splitlines()
        if completed.returncode or len(fields) < 6:
            raise SourceAccessError(
                f"{request.label}: curl.exe/Schannel exit {completed.returncode}: {completed.stderr.strip()}"
            )
        status = int(fields[0])
        verify = fields[4].strip()
        if verify not in {"0", ""}:
            raise SourceAccessError(f"{request.label}: Schannel verification result {verify}")
        body = body_path.read_bytes()
        headers = _last_header_block(header_path.read_bytes())
        payload = FetchedPayload(
            request.label, fields[1], status, fields[2] or headers.get("Content-Type", ""),
            body, captured, headers,
        )
        transport = {
            "transport": "curl.exe/Schannel", "runner": os.environ.get("RUNNER_OS") or platform.system(),
            "request_made": True, "curl_exit_code": completed.returncode,
            "tls_verify_result": "success", "resolved_server_ip": fields[3],
            "http_version": fields[5], "url": request.url, "final_url": fields[1],
            "http_status": status, "content_type": payload.content_type,
            "payload_bytes": len(body), "sha256": payload.sha256,
        }
        return payload, transport


def collect(profile: str, period: int, output_root: Path, archive_root: Path) -> dict[str, Any]:
    adapter = HidmetAdapter()
    adapter.collection_profile = profile
    adapter.nrt_period = period
    payloads: dict[str, FetchedPayload] = {}
    archive: list[dict[str, Any]] = []
    transport: list[dict[str, Any]] = []
    for request in adapter.initial_requests():
        payload, metadata = fetch_with_schannel(request)
        payloads[request.label] = payload
        archive.append(archive_payload(payload, archive_root, adapter.source_id))
        transport.append(metadata)
        ensure_payload(payload, request.expected_format)
    for request in adapter.additional_requests(payloads):
        payload, metadata = fetch_with_schannel(request)
        payloads[request.label] = payload
        archive.append(archive_payload(payload, archive_root, adapter.source_id))
        transport.append(metadata)
        ensure_payload(payload, request.expected_format)
    result = adapter.parse(payloads)
    source_output = output_root / "rs"
    write_result(result, source_output)
    write_json(source_output / "archive_manifest.json", archive)
    collection = {
        "transport": "curl.exe/Schannel", "runner": os.environ.get("RUNNER_OS") or platform.system(),
        "request_made": True, "collection_profile": profile, "nrt_period": period,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(), "requests": transport,
    }
    write_json(source_output / "collection.json", collection)
    summary = {
        "source": "rs", "adapter": adapter.source_id, "status": result.status,
        "publishable": result.publishable, "station_count": len(result.stations),
        "included_station_count": sum(station.included for station in result.stations),
        "observation_count": len(result.observations),
        "usable_observation_count": len(result.usable_observations),
        "suspect_observation_count": len(result.observations) - len(result.usable_observations),
        "forecast_count": len(result.forecasts),
        "critical_issue_count": sum(issue.severity == "critical" for issue in result.issues),
        "output": str(source_output), **{key: collection[key] for key in ("transport", "runner", "request_made", "collection_profile", "nrt_period")},
    }
    write_json(output_root / "summary.json", {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "fixture_mode": False,
        "sources": [summary], "failed_sources": [],
        "non_publishable_sources": [] if result.publishable else ["rs"],
    })
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["all", "nrt", "daily", "forecast"], default="all")
    parser.add_argument("--period", choices=[7, 30], type=int, default=7)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = collect(args.profile, args.period, args.output_dir, args.archive_root)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
