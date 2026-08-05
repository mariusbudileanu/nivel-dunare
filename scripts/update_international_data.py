#!/usr/bin/env python3
"""Operational, fail-soft update of international Danube public data.

Each adapter is isolated. A failed source keeps its committed last-known-good
records while the attempt and error are recorded in the public source state.
Raw payloads and candidate outputs remain in the workflow artifact directory.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts.build_international_public_data import SOURCE_POLICY, build
from scripts.ingest_danube_sources import run_source
from scripts.validate_international_public_data import validate


ALL_SOURCES = ("de", "at", "sk", "hu", "hr", "bg", "rs")
SCHEDULED_SOURCES = ("de", "sk", "hu", "hr", "bg")
SOURCE_ID_TO_CODE = {value["source_id"]: key for key, value in SOURCE_POLICY.items()}
PUBLIC_ENRICHMENT_KEYS = {
    "country_code", "station_name", "station_name_local", "source_id",
    "source_status", "source_url", "current_usable", "stale",
}
ALLOWED_CRITICAL = {
    "bg": {"missing_institutional_station_ids", "missing_source_station_id"},
    "hr": {"stale_source"},
}
OPERATIONAL_POLICY = {
    "de": {
        "automation_status": "scheduled", "freshness_status": "current",
        "validation_status": "validated",
        "validation_message_ro": "Date actualizate automat și validate.",
        "validation_message_en": "Automatically updated and validated.",
    },
    "at": {
        "automation_status": "manual", "freshness_status": "current",
        "validation_status": "requires_review",
        "validation_message_ro": "Cheie publică DoRIS de test; este necesară o cheie permanentă de partener.",
        "validation_message_en": "Public DoRIS test key; permanent partner key required",
    },
    "sk": {
        "automation_status": "scheduled", "freshness_status": "current",
        "validation_status": "requires_review",
        "validation_message_ro": "Date actualizate automat; anumite valori necesită validare.",
        "validation_message_en": "Automatically updated; some values require validation.",
    },
    "hu": {
        "automation_status": "scheduled", "freshness_status": "current",
        "validation_status": "requires_review",
        "validation_message_ro": "Date actualizate automat; sursa furnizează data, dar nu ora observației.",
        "validation_message_en": "Automatically updated; the source provides the date but not the observation time.",
    },
    "hr": {
        "automation_status": "scheduled", "freshness_status": "stale",
        "validation_status": "requires_review",
        "validation_message_ro": "Flux verificat automat; sursa nu furnizează momentan date recente.",
        "validation_message_en": "The feed is checked automatically; the source currently provides no recent data.",
    },
    "bg": {
        "automation_status": "scheduled", "freshness_status": "current",
        "validation_status": "requires_review",
        "validation_message_ro": "Observații actualizate automat; identificatorii instituționali și prognozele nu sunt încă validați.",
        "validation_message_en": "Observations are updated automatically; institutional identifiers and forecasts are not yet validated.",
    },
    "rs": {
        "automation_status": "disabled", "freshness_status": "unavailable",
        "validation_status": "not_applicable",
        "validation_message_ro": "Sursă dezactivată: validarea lanțului TLS a eșuat; nu se efectuează cereri.",
        "validation_message_en": "Source disabled: TLS chain validation failed; no requests are made.",
    },
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def selected_sources(value: str) -> list[str]:
    if value == "all":
        return list(ALL_SOURCES)
    if value == "scheduled":
        return list(SCHEDULED_SOURCES)
    return [value]


def source_rows(public_root: Path, code: str) -> dict[str, list[dict[str, Any]]]:
    source_id = SOURCE_POLICY[code]["source_id"]
    country = code.upper()
    stations = [row for row in read_json(public_root / "stations.json", []) if row["country_code"] == country]
    observations = [row for row in read_json(public_root / "observations.json", []) if row.get("source_id") == source_id]
    forecasts = [row for row in read_json(public_root / "forecasts.json", []) if row.get("source_id") == source_id]
    issues = [row for row in read_json(public_root / "quality_issues.json", []) if row.get("source_id") == source_id]
    return {"stations": stations, "observations": observations, "forecasts": forecasts, "issues": issues}


def raw_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in PUBLIC_ENRICHMENT_KEYS}


def dedupe(rows: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    if kind == "observations":
        def key(row: dict[str, Any]) -> tuple[Any, ...]:
            return (
                row.get("station_id"), row.get("parameter"), row.get("value"), row.get("unit"),
                row.get("measurement_datetime_utc") or row.get("measurement_date") or row.get("measurement_time_original"),
                row.get("source_file_sha256"),
            )
    elif kind == "forecasts":
        def key(row: dict[str, Any]) -> tuple[Any, ...]:
            return (
                row.get("station_id"), row.get("forecast_parameter"), row.get("forecast_value"),
                row.get("target_datetime_utc") or row.get("target_date") or row.get("target_time_original"),
                row.get("source_file_sha256"),
            )
    else:
        def key(row: dict[str, Any]) -> tuple[Any, ...]:
            observation = row.get("observation") or {}
            return (
                row.get("code"), row.get("record_id") or row.get("station_id"),
                row.get("captured_at_utc"), row.get("historical"), observation.get("value"),
            )
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        unique[key(row)] = row
    return list(unique.values())


def latest_observation_date(rows: list[dict[str, Any]]) -> str | None:
    values = []
    for row in rows:
        value = row.get("measurement_datetime_utc") or row.get("measurement_datetime_local") or row.get("measurement_date")
        if value:
            values.append(str(value)[:10])
    return max(values) if values else None


def archive_details(folder: Path, archive_root: Path | None = None, source_id: str | None = None) -> dict[str, Any]:
    manifest = read_json(folder / "archive_manifest.json", [])
    if not manifest and archive_root and source_id:
        source_archive = archive_root / source_id
        manifest = [read_json(path) for path in sorted(source_archive.rglob("*.metadata.json"))] if source_archive.is_dir() else []
    captures = [item.get("captured_at_utc") for item in manifest if item.get("captured_at_utc")]
    return {
        "payload_count": len(manifest),
        "http_statuses": [item.get("http_status") for item in manifest],
        "content_types": [item.get("content_type") for item in manifest],
        "last_capture_at": max(captures) if captures else None,
        "payload_sha256": [item.get("content_sha256") for item in manifest],
    }


def default_state(public_root: Path, commit_sha: str | None) -> dict[str, Any]:
    previous_sources = {row["country_code"].lower(): row for row in read_json(public_root / "sources.json", [])}
    previous_status = read_json(public_root / "status.json", {})
    result: dict[str, Any] = {
        "contract_version": "1.0",
        "fixtures_run_id": previous_status.get("fixtures_run_id"),
        "live_run_id": previous_status.get("live_run_id"),
        "sources": {},
    }
    for code in ALL_SOURCES:
        prior = previous_sources.get(code, {})
        policy = OPERATIONAL_POLICY[code]
        capture = prior.get("last_capture_at") or prior.get("capture_datetime_utc")
        result["sources"][code] = {
            "source_status": SOURCE_POLICY[code]["status"],
            **policy,
            "last_attempt_at": prior.get("last_attempt_at"),
            "last_attempt_status": prior.get("last_attempt_status", "suspended" if code == "rs" else "unknown"),
            "last_success_at": prior.get("last_success_at") or capture,
            "last_success_capture_at": prior.get("last_success_capture_at") or capture,
            "last_capture_at": capture,
            "last_success_commit": prior.get("last_success_commit") or commit_sha,
            "last_error_code": prior.get("last_error_code"),
            "last_error_message": prior.get("last_error_message"),
            "last_error": prior.get("last_error"),
            "consecutive_failures": int(prior.get("consecutive_failures") or 0),
            "published_snapshot_date": prior.get("published_snapshot_date") or latest_observation_date(source_rows(public_root, code)["observations"]),
            "next_expected_update": prior.get("next_expected_update"),
            "update_frequency": "daily at 01:37 UTC" if policy["automation_status"] == "scheduled" else ("manual" if code == "at" else "disabled"),
        }
    return result


def next_scheduled(now: datetime) -> str:
    next_day = (now + timedelta(days=1)).date()
    return datetime(next_day.year, next_day.month, next_day.day, 1, 37, tzinfo=timezone.utc).isoformat()


def acceptable(code: str, summary: dict[str, Any], issues: list[dict[str, Any]]) -> tuple[bool, str | None]:
    if summary.get("status") == "failed":
        return False, str(summary.get("error") or "adapter failed")
    critical = {row.get("code") for row in issues if row.get("severity") == "critical"}
    unexpected = critical - ALLOWED_CRITICAL.get(code, set())
    if unexpected:
        return False, "unexpected critical issues: " + ", ".join(sorted(str(item) for item in unexpected))
    expected_statuses = {
        "de": {"complete"}, "at": {"complete", "partial"}, "sk": {"complete", "partial"},
        "hu": {"complete"}, "hr": {"complete", "suspended"}, "bg": {"partial"},
    }
    if summary.get("status") not in expected_statuses[code]:
        return False, f"unexpected adapter status {summary.get('status')!r}"
    if int(summary.get("station_count") or 0) <= 0:
        return False, "empty station set"
    if int(summary.get("observation_count") or 0) <= 0:
        return False, "empty observation set"
    return True, None


def materialize_candidates(public_root: Path, candidate_root: Path) -> dict[str, dict[str, list[dict[str, Any]]]]:
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    result = {}
    for code in ALL_SOURCES:
        if code == "rs":
            continue
        rows = source_rows(public_root, code)
        result[code] = rows
        folder = candidate_root / code
        for kind, values in rows.items():
            prepared = values if kind == "stations" else [raw_candidate(row) for row in values]
            write_json(folder / f"{kind}.json", prepared)
    return result


def replace_candidate(candidate_root: Path, code: str, new_folder: Path, previous: dict[str, list[dict[str, Any]]]) -> None:
    folder = candidate_root / code
    new_stations = read_json(new_folder / "stations.json", [])
    new_observations = read_json(new_folder / "observations.json", [])
    new_forecasts = read_json(new_folder / "forecasts.json", [])
    new_issues = read_json(new_folder / "issues.json", [])
    station_ids = {row["station_id"] for row in new_stations}
    old_observations = [raw_candidate(row) for row in previous["observations"] if row.get("station_id") in station_ids]
    old_forecasts = [raw_candidate(row) for row in previous["forecasts"] if row.get("station_id") in station_ids]
    old_issues = [raw_candidate(row) for row in previous["issues"] if row.get("historical")]
    write_json(folder / "stations.json", new_stations)
    write_json(folder / "observations.json", dedupe(old_observations + new_observations, "observations"))
    write_json(folder / "forecasts.json", [] if code == "bg" else dedupe(old_forecasts + new_forecasts, "forecasts"))
    write_json(folder / "issues.json", dedupe(old_issues + new_issues, "issues"))


def update_state(state: dict[str, Any], code: str, now: datetime, summary: dict[str, Any],
                 accepted: bool, error: str | None, details: dict[str, Any], latest_date: str | None,
                 commit_sha: str | None) -> None:
    item = state["sources"][code]
    item["last_attempt_at"] = now.isoformat()
    if item["automation_status"] == "scheduled":
        item["next_expected_update"] = next_scheduled(now)
    if code == "rs":
        item.update({
            "last_attempt_status": "suspended", "source_status": "suspended",
            "freshness_status": "unavailable", "validation_status": "not_applicable",
            "last_error_code": "tls_certificate_validation",
            "last_error_message": "TLS certificate-chain validation failed; no request was made.",
            "last_error": {"code": "tls_certificate_validation", "message": "No request was made."},
        })
        return
    if not accepted:
        message = error or "source capture rejected"
        item.update({
            "last_attempt_status": "failed", "last_error_code": summary.get("error_type") or "validation_failed",
            "validation_status": "failed",
            "last_error_message": message,
            "last_error": {"code": summary.get("error_type") or "validation_failed", "message": message},
            "consecutive_failures": int(item.get("consecutive_failures") or 0) + 1,
        })
        return
    stale = code == "hr" and summary.get("status") == "suspended"
    source_status = "suspended" if stale else SOURCE_POLICY[code]["status"]
    if code == "hr" and not stale:
        source_status = "complete"
    item.update({
        "source_status": source_status,
        "freshness_status": "stale" if stale else "current",
        "validation_status": OPERATIONAL_POLICY[code]["validation_status"],
        "last_attempt_status": "stale" if stale else ("partial" if source_status == "partial" else "success"),
        "last_success_at": now.isoformat(),
        "last_success_capture_at": details.get("last_capture_at"),
        "last_capture_at": details.get("last_capture_at"),
        "last_success_commit": commit_sha,
        "last_error_code": None, "last_error_message": None, "last_error": None,
        "consecutive_failures": 0,
        "published_snapshot_date": latest_date or item.get("published_snapshot_date"),
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["all", "scheduled", *ALL_SOURCES], default="scheduled")
    parser.add_argument("--mode", choices=["fixtures", "live"], default="live")
    parser.add_argument("--action", choices=["dry-run", "publish"], default="dry-run")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--fixture-root", type=Path, default=Path("tests/fixtures/international"))
    parser.add_argument("--public-root", type=Path, default=Path("data/public/international"))
    parser.add_argument("--mirror-root", type=Path, default=Path("public/data/international"))
    parser.add_argument("--operations-state", type=Path, default=Path("data/reference/international_source_operations.json"))
    parser.add_argument("--audit-csv", type=Path, default=Path("docs/INTERNATIONAL_STATIONS_AUDIT.csv"))
    parser.add_argument("--geocoding-registry", type=Path, default=Path("data/reference/international_station_geocoding.csv"))
    args = parser.parse_args(argv)
    if args.mode == "fixtures" and args.action == "publish":
        parser.error("fixture data cannot be published")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path("_diagnostics/international") / f"update-{stamp}"
    run_results = output_dir / "results"
    archive_root = output_dir / "raw-archive"
    candidates = output_dir / "combined-candidates"
    selected = selected_sources(args.source)
    commit_sha = os.environ.get("GITHUB_SHA") or os.environ.get("INTERNATIONAL_BASE_COMMIT")
    previous_status = read_json(args.public_root / "status.json", {})
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    state = read_json(args.operations_state) or default_state(args.public_root, commit_sha)
    previous = materialize_candidates(args.public_root, candidates)
    reports: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []

    fixture_root = args.fixture_root if args.mode == "fixtures" else None
    for code in ALL_SOURCES:
        prior_source = next((row for row in read_json(args.public_root / "sources.json", []) if row["country_code"] == code.upper()), {})
        if code not in selected:
            aggregate_rows.append({"source": code, "status": prior_source.get("adapter_live_status", "unavailable")})
            continue
        if code == "rs":
            summary = {"source": "rs", "status": "suspended", "publishable": False, "station_count": 13, "observation_count": 0, "forecast_count": 0}
            details = {"payload_count": 0, "http_statuses": [], "content_types": [], "last_capture_at": None, "payload_sha256": []}
            if args.mode == "live":
                update_state(state, code, now, summary, False, None, details, None, commit_sha)
            report = {**summary, **details, "accepted_for_publication": False, "request_made": False, "blocker": "TLS certificate-chain validation"}
            reports.append(report); aggregate_rows.append(summary)
            continue
        try:
            summary = run_source(code, run_results, archive_root, fixture_root)
        except Exception as exc:  # isolate an unexpected adapter defect to this source
            summary = {
                "source": code, "adapter": SOURCE_POLICY[code]["source_id"], "status": "failed",
                "publishable": False, "error_type": type(exc).__name__, "error": str(exc),
                "output": str(run_results / code),
            }
            write_json(run_results / code / "failure.json", summary)
        folder = run_results / code
        issues = read_json(folder / "issues.json", [])
        details = archive_details(folder, archive_root, SOURCE_POLICY[code]["source_id"])
        accepted, error = acceptable(code, summary, issues)
        observations = read_json(folder / "observations.json", []) if summary.get("status") != "failed" else []
        latest_date = latest_observation_date(observations)
        if accepted and args.mode == "live":
            replace_candidate(candidates, code, folder, previous[code])
        if args.mode == "live":
            update_state(state, code, now, summary, accepted, error, details, latest_date, commit_sha)
        report = {
            **summary, **details, "accepted_for_publication": accepted,
            "parser_status": "success" if summary.get("status") != "failed" else "failed",
            "validator_status": "accepted" if accepted else "failed",
            "publication_status": ("fixture-only" if args.mode == "fixtures" else ("candidate" if accepted else "last-known-good")),
            "latest_observation_date": latest_date, "warnings": [row for row in issues if row.get("severity") != "critical"],
            "blocker": error,
        }
        reports.append(report); aggregate_rows.append(summary)

    write_json(candidates / "summary.json", {
        "generated_at_utc": now.isoformat(), "fixture_mode": args.mode == "fixtures", "sources": aggregate_rows,
        "failed_sources": [row["source"] for row in reports if row.get("status") == "failed"],
        "non_publishable_sources": [row["source"] for row in reports if not row.get("accepted_for_publication")],
    })
    state_path = args.operations_state if args.action == "publish" else output_dir / "international_source_operations.preview.json"
    write_json(state_path, state)
    output_root = args.public_root if args.action == "publish" else output_dir / "public-preview"
    mirror_root = args.mirror_root if args.action == "publish" else output_dir / "public-preview-mirror"
    status = build(
        candidates, args.audit_csv, archive_root, output_root, mirror_root,
        fixtures_run_id=github_run_id if args.mode == "fixtures" else (previous_status.get("fixtures_run_id") or state.get("fixtures_run_id")),
        live_run_id=github_run_id if args.mode == "live" else (previous_status.get("live_run_id") or state.get("live_run_id")),
        geocoding_registry=args.geocoding_registry,
        operations_state=state_path,
    )
    validation = validate(output_root, mirror_root, args.geocoding_registry)
    final = {
        "generated_at_utc": now.isoformat(), "mode": args.mode, "action": args.action,
        "selected_sources": selected, "sources": reports, "public_status": status,
        "public_validation": validation, "output_root": str(output_root), "operations_state": str(state_path),
    }
    write_json(output_dir / "update-summary.json", final)
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
