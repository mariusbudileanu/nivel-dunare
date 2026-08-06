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
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.build_international_public_data import EXPECTED_COUNTS, SOURCE_POLICY, build
from scripts.ingest_danube_sources import run_source
from scripts.validate_international_public_data import validate


ALL_SOURCES = ("de", "at", "sk", "hu", "hr", "bg", "rs")
SCHEDULED_SOURCES = ("de", "sk", "hu", "hr")
SOURCE_ID_TO_CODE = {value["source_id"]: key for key, value in SOURCE_POLICY.items()}
PUBLIC_ENRICHMENT_KEYS = {
    "country_code", "station_name", "station_name_local", "source_id",
    "source_status", "source_url", "current_usable", "stale",
}
ALLOWED_CRITICAL: dict[str, set[str]] = {}
OPERATIONAL_POLICY = {
    "de": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "source_validated", "validation_message_ro": "Date actualizate automat și validate.", "validation_message_en": "Automatically updated and validated."},
    "at": {"access_status": "available", "automation_status": "manual", "freshness_status": "current", "validation_status": "source_provisional", "validation_message_ro": "Cheia DoRIS nu este inclusă; actualizarea rămâne manuală până la configurarea unei chei permanente.", "validation_message_en": "The DoRIS key is not included; updates remain manual until a permanent key is configured."},
    "sk": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "source_provisional", "validation_message_ro": "Valorile oficiale sunt păstrate fără praguri locale de plauzibilitate.", "validation_message_en": "Official values are retained without local plausibility thresholds."},
    "hu": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "technical_validation_passed", "validation_message_ro": "Sursa oferă data și partea zilei; aplicația nu inventează ore sau fusuri.", "validation_message_en": "The source provides date and daypart; the application does not invent times or time zones."},
    "hr": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "stale", "validation_status": "technical_validation_passed", "validation_message_ro": "Date neactualizate. Fluxul este verificat automat zilnic, însă sursa oficială nu a publicat valori mai recente. Ultima observație disponibilă este din {date}. Valorile sunt afișate exact așa cum sunt furnizate de sursă.", "validation_message_en": "Data not updated. The feed is checked automatically every day, but the official source has not published more recent values. The latest available observation is dated {date}. Values are displayed exactly as provided by the source."},
    "bg": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "source_provisional", "validation_message_ro": "Fluxurile manuale și automate sunt identificate prin registrul RIS; prognozele rămân neactivate.", "validation_message_en": "Manual and automatic streams are identified through the RIS registry; forecasts remain inactive."},
    "rs": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "source_provisional", "validation_message_ro": "Date automate provizorii. Valorile sunt publicate exact așa cum sunt furnizate de RHMZ Serbia. Sursa precizează că datele nu sunt încă verificate și pot întârzia din cauza telemetriei sau a funcționării sistemului.", "validation_message_en": "Provisional automatic data. Values are published exactly as provided by RHMZ Serbia. The source states that the data have not yet been validated and may be delayed because of telemetry or system issues."},
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
                row.get("station_id"), row.get("source_stream_id") or row.get("source_stream_type"),
                row.get("parameter"), row.get("source_observation_date") or row.get("measurement_date"),
                row.get("observation_window") or row.get("observation_daypart") or row.get("measurement_time_original"),
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


def normalized_source_date(value: Any) -> str | None:
    text = str(value or "").strip()
    iso = re.search(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", text)
    if iso:
        return iso.group(1)
    european = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", text)
    if european:
        day, month, year = european.groups()
        return f"{year}-{month}-{day}"
    return None


def archive_details(folder: Path, archive_root: Path | None = None, source_id: str | None = None) -> dict[str, Any]:
    manifest = read_json(folder / "archive_manifest.json", [])
    if not manifest and archive_root and source_id:
        source_archive = archive_root / source_id
        manifest = [read_json(path) for path in sorted(source_archive.rglob("*.metadata.json"))] if source_archive.is_dir() else []
    captures = [item.get("captured_at_utc") for item in manifest if item.get("captured_at_utc")]
    collection = read_json(folder / "collection.json", {})
    return {
        "payload_count": len(manifest),
        "http_statuses": [item.get("http_status") for item in manifest],
        "content_types": [item.get("content_type") for item in manifest],
        "last_capture_at": max(captures) if captures else collection.get("captured_at_utc"),
        "payload_sha256": [item.get("content_sha256") for item in manifest],
        "transport": collection.get("transport"), "runner": collection.get("runner"),
        "request_made": collection.get("request_made") if collection else bool(manifest),
    }


def default_state(public_root: Path, commit_sha: str | None) -> dict[str, Any]:
    previous_sources = {row["country_code"].lower(): row for row in read_json(public_root / "sources.json", [])}
    previous_status = read_json(public_root / "status.json", {})
    result: dict[str, Any] = {
        "contract_version": "1.3-beta",
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
            "last_attempt_status": prior.get("last_attempt_status", "unknown"),
            "last_success_at": prior.get("last_success_at") or capture,
            "last_successful_fetch_at": prior.get("last_successful_fetch_at") or prior.get("last_success_at") or capture,
            "last_success_capture_at": prior.get("last_success_capture_at") or capture,
            "last_capture_at": capture,
            "last_success_commit": prior.get("last_success_commit") or commit_sha,
            "last_known_good_commit": prior.get("last_known_good_commit") or prior.get("last_success_commit") or commit_sha,
            "last_known_good_at": prior.get("last_known_good_at") or prior.get("last_success_at") or capture,
            "last_source_observation_at": prior.get("last_source_observation_at") or prior.get("published_snapshot_date"),
            "coordinate_status": prior.get("coordinate_status", "complete"),
            "last_error_code": prior.get("last_error_code"),
            "last_error_message": prior.get("last_error_message"),
            "last_error": prior.get("last_error"),
            "consecutive_failures": int(prior.get("consecutive_failures") or 0),
            "published_snapshot_date": prior.get("published_snapshot_date") or latest_observation_date(source_rows(public_root, code)["observations"]),
            "next_expected_update": prior.get("next_expected_update"),
            "update_frequency": ("every 3 hours plus daily/forecast Europe/Belgrade gates" if code == "rs" else ("09:15/21:15 Europe/Sofia by stream" if code == "bg" else ("daily at 01:37 UTC" if policy["automation_status"] == "scheduled" else ("manual" if code == "at" else "disabled")))),
            "transport": prior.get("transport"), "runner": prior.get("runner"),
            "request_made": prior.get("request_made"),
            "components": prior.get("components", {}) if code == "rs" else prior.get("components"),
        }
    return result


def next_scheduled(code: str, now: datetime) -> str:
    if code == "rs":
        candidate = now.replace(minute=17, second=0, microsecond=0)
        while candidate <= now or candidate.hour % 3:
            candidate += timedelta(hours=1)
            candidate = candidate.replace(minute=17)
        return candidate.isoformat()
    if code != "bg":
        next_day = (now + timedelta(days=1)).date()
        return datetime(next_day.year, next_day.month, next_day.day, 1, 37, tzinfo=timezone.utc).isoformat()
    sofia = ZoneInfo("Europe/Sofia")
    local_now = now.astimezone(sofia)
    candidates = []
    for day_offset in (0, 1):
        local_date = (local_now + timedelta(days=day_offset)).date()
        for hour in (9, 21):
            candidate = datetime(local_date.year, local_date.month, local_date.day, hour, 15, tzinfo=sofia)
            if candidate > local_now:
                candidates.append(candidate)
    return min(candidates).astimezone(timezone.utc).isoformat()


def acceptable(code: str, summary: dict[str, Any], issues: list[dict[str, Any]], stream: str = "all") -> tuple[bool, str | None]:
    if summary.get("status") == "failed":
        return False, str(summary.get("error") or "adapter failed")
    critical = {row.get("code") for row in issues if row.get("severity") == "critical"}
    unexpected = critical - ALLOWED_CRITICAL.get(code, set())
    if unexpected:
        return False, "unexpected critical issues: " + ", ".join(sorted(str(item) for item in unexpected))
    expected_statuses = {
        "de": {"complete"}, "at": {"complete", "partial"}, "sk": {"complete", "partial"},
        "hu": {"complete"}, "hr": {"complete", "partial", "suspended"}, "bg": {"complete", "partial"},
        "rs": {"complete"},
    }
    if summary.get("status") not in expected_statuses[code]:
        return False, f"unexpected adapter status {summary.get('status')!r}"
    station_count = int(summary.get("station_count") or 0)
    if station_count != EXPECTED_COUNTS[code]:
        return False, f"unexpected station count: expected {EXPECTED_COUNTS[code]}, got {station_count}"
    if code == "rs" and stream == "forecast":
        if int(summary.get("forecast_count") or 0) <= 0:
            return False, "empty forecast set"
    elif int(summary.get("observation_count") or 0) <= 0:
        return False, "empty observation set"
    return True, None


def materialize_candidates(public_root: Path, candidate_root: Path) -> dict[str, dict[str, list[dict[str, Any]]]]:
    if candidate_root.exists():
        shutil.rmtree(candidate_root)
    result = {}
    for code in ALL_SOURCES:
        rows = source_rows(public_root, code)
        result[code] = rows
        folder = candidate_root / code
        for kind, values in rows.items():
            prepared = values if kind == "stations" else [raw_candidate(row) for row in values]
            write_json(folder / f"{kind}.json", prepared)
    return result


def replace_candidate(candidate_root: Path, code: str, new_folder: Path,
                      previous: dict[str, list[dict[str, Any]]], stream: str = "all") -> None:
    folder = candidate_root / code
    new_stations = read_json(new_folder / "stations.json", [])
    new_observations = read_json(new_folder / "observations.json", [])
    new_forecasts = read_json(new_folder / "forecasts.json", [])
    new_issues = read_json(new_folder / "issues.json", [])
    if code == "bg" and stream != "all":
        if stream not in {"manual", "automatic"}:
            raise ValueError(f"Unsupported BG stream selector: {stream}")
        new_stations = [row for row in new_stations if row.get("source_stream_type") == stream]
        new_observations = [row for row in new_observations if row.get("source_stream_type") == stream]
        retained_stations = [row for row in previous["stations"] if row.get("source_stream_type") != stream]
        all_stations = retained_stations + new_stations
    else:
        all_stations = new_stations
    station_ids = {row["station_id"] for row in all_stations}
    old_observations = [raw_candidate(row) for row in previous["observations"] if row.get("station_id") in station_ids]
    old_forecasts = [raw_candidate(row) for row in previous["forecasts"] if row.get("station_id") in station_ids]
    if code == "rs":
        if stream not in {"all", "nrt", "daily", "forecast"}:
            raise ValueError(f"Unsupported RS stream selector: {stream}")
        if stream in {"nrt", "daily"}:
            retained = [row for row in old_observations if row.get("source_stream_type") != stream]
            observations = dedupe(retained + [row for row in old_observations if row.get("source_stream_type") == stream] + new_observations, "observations")
            forecasts = old_forecasts
        elif stream == "forecast":
            observations = old_observations
            forecasts = new_forecasts
        else:
            observations = dedupe(old_observations + new_observations, "observations")
            forecasts = new_forecasts
    else:
        observations = dedupe(old_observations + new_observations, "observations")
        forecasts = [] if code == "bg" else dedupe(old_forecasts + new_forecasts, "forecasts")
    old_issues = []
    for row in previous["issues"]:
        if row.get("historical"):
            old_issues.append(raw_candidate(row))
        elif row.get("quality_origin") == "legacy_application_rule":
            historical = raw_candidate(row)
            historical.update({"historical": True, "active": False})
            old_issues.append(historical)
    write_json(folder / "stations.json", all_stations)
    write_json(folder / "observations.json", observations)
    write_json(folder / "forecasts.json", forecasts)
    write_json(folder / "issues.json", dedupe(old_issues + new_issues, "issues"))


def update_state(state: dict[str, Any], code: str, now: datetime, summary: dict[str, Any],
                 accepted: bool, error: str | None, details: dict[str, Any], latest_date: str | None,
                 commit_sha: str | None, stream: str = "all") -> None:
    item = state["sources"][code]
    item["last_attempt_at"] = now.isoformat()
    if item["automation_status"] == "scheduled":
        item["next_expected_update"] = next_scheduled(code, now)
    component_names = ("nrt", "daily", "forecast") if code == "rs" and stream == "all" else ((stream,) if code == "rs" else ())
    if not accepted:
        message = error or "source capture rejected"
        item.update({
            "last_attempt_status": "failed", "last_error_code": summary.get("error_type") or "validation_failed",
            "validation_status": "technical_validation_failed",
            "last_error_message": message,
            "last_error": {"code": summary.get("error_type") or "validation_failed", "message": message},
            "consecutive_failures": int(item.get("consecutive_failures") or 0) + 1,
            "transport": details.get("transport") or item.get("transport"),
            "runner": details.get("runner") or item.get("runner"),
            "request_made": details.get("request_made", code != "rs"),
        })
        for component_name in component_names:
            component = item.setdefault("components", {}).setdefault(component_name, {})
            component.update({
                "last_attempt_at": now.isoformat(), "last_attempt_status": "failed", "last_error": message,
                "consecutive_failures": int(component.get("consecutive_failures") or 0) + 1,
                "transport": details.get("transport"), "runner": details.get("runner"),
                "request_made": details.get("request_made", True),
            })
        return
    stale = code == "hr" and summary.get("status") in {"partial", "suspended"}
    source_status = "partial" if stale else SOURCE_POLICY[code]["status"]
    item.update({
        "source_status": source_status,
        "freshness_status": "stale" if stale else "current",
        "validation_status": OPERATIONAL_POLICY[code]["validation_status"],
        "last_attempt_status": "stale" if stale else ("partial" if source_status == "partial" else "success"),
        "last_success_at": now.isoformat(),
        "last_successful_fetch_at": now.isoformat(),
        "last_success_capture_at": details.get("last_capture_at"),
        "last_capture_at": details.get("last_capture_at"),
        "last_success_commit": commit_sha, "last_known_good_commit": commit_sha,
        "last_known_good_at": now.isoformat(),
        "last_source_observation_at": latest_date,
        "last_error_code": None, "last_error_message": None, "last_error": None,
        "consecutive_failures": 0,
        "published_snapshot_date": latest_date or item.get("published_snapshot_date"),
        "transport": details.get("transport") or item.get("transport"),
        "runner": details.get("runner") or item.get("runner"),
        "request_made": details.get("request_made", code != "rs"),
    })
    if code == "rs":
        item["update_frequency"] = "every 3 hours plus daily/forecast Europe/Belgrade gates"
    for component_name in component_names:
        component = item.setdefault("components", {}).setdefault(component_name, {})
        component.update({
            "last_attempt_at": now.isoformat(), "last_attempt_status": "success",
            "last_success_at": now.isoformat(), "last_capture_at": details.get("last_capture_at"),
            "last_source_observation_at": details.get("component_last_source_observation_at", {}).get(component_name) or latest_date or details.get("last_capture_at"),
            "last_error": None, "consecutive_failures": 0,
            "transport": details.get("transport"), "runner": details.get("runner"),
            "request_made": details.get("request_made", True),
        })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["all", "scheduled", *ALL_SOURCES], default="scheduled")
    parser.add_argument("--mode", choices=["fixtures", "live"], default="live")
    parser.add_argument("--stream", choices=["all", "manual", "automatic", "nrt", "daily", "forecast"], default="all", help="BG or RS component selector")
    parser.add_argument("--rs-period", choices=[7, 30], type=int, default=7, help="RHMZ NRT overlap/backfill period")
    parser.add_argument("--action", choices=["dry-run", "publish"], default="dry-run")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--fixture-root", type=Path, default=Path("tests/fixtures/international"))
    parser.add_argument("--public-root", type=Path, default=Path("data/public/international"))
    parser.add_argument("--mirror-root", type=Path, default=Path("public/data/international"))
    parser.add_argument("--operations-state", type=Path, default=Path("data/reference/international_source_operations.json"))
    parser.add_argument("--audit-csv", type=Path, default=Path("docs/INTERNATIONAL_STATIONS_AUDIT.csv"))
    parser.add_argument("--geocoding-registry", type=Path, default=Path("data/reference/international_station_geocoding.csv"))
    parser.add_argument("--precollected-root", type=Path, help="Validated Windows candidate handoff (RS only)")
    parser.add_argument("--precollected-archive", type=Path, help="Raw Windows archive handoff (RS only)")
    args = parser.parse_args(argv)
    if args.source == "bg" and args.stream not in {"all", "manual", "automatic"}:
        parser.error("BG --stream must be all, manual, or automatic")
    if args.source == "rs" and args.stream not in {"all", "nrt", "daily", "forecast"}:
        parser.error("RS --stream must be all, nrt, daily, or forecast")
    if args.source not in {"bg", "rs"} and args.stream != "all":
        parser.error("--stream is valid only with --source bg or rs")
    if args.mode == "fixtures" and args.action == "publish":
        parser.error("fixture data cannot be published")
    if args.precollected_root and (args.source != "rs" or args.mode != "live"):
        parser.error("--precollected-root is valid only with --source rs --mode live")
    if bool(args.precollected_root) != bool(args.precollected_archive):
        parser.error("both precollected handoff paths are required")

    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path("_diagnostics/international") / f"update-{stamp}"
    run_results = output_dir / "results"
    archive_root = args.precollected_archive or (output_dir / "raw-archive")
    candidates = output_dir / "combined-candidates"
    selected = selected_sources(args.source)
    commit_sha = os.environ.get("GITHUB_SHA") or os.environ.get("INTERNATIONAL_BASE_COMMIT")
    previous_status = read_json(args.public_root / "status.json", {})
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    defaults = default_state(args.public_root, commit_sha)
    state = read_json(args.operations_state) or defaults
    state["contract_version"] = "1.3-beta"
    state.setdefault("sources", {})
    for code in ALL_SOURCES:
        item = state["sources"].setdefault(code, {})
        for key, value in defaults["sources"][code].items():
            item.setdefault(key, value)
        item.update(OPERATIONAL_POLICY[code])
        if code == "hr" and item.get("source_status") == "suspended":
            item["source_status"] = "partial"
    previous = materialize_candidates(args.public_root, candidates)
    reports: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []

    fixture_root = args.fixture_root if args.mode == "fixtures" else None
    for code in ALL_SOURCES:
        prior_source = next((row for row in read_json(args.public_root / "sources.json", []) if row["country_code"] == code.upper()), {})
        if code not in selected:
            aggregate_rows.append({"source": code, "status": prior_source.get("adapter_live_status", "unavailable")})
            continue
        try:
            if code == "rs" and args.precollected_root:
                run_results = args.precollected_root
                aggregate = read_json(run_results / "summary.json", {})
                summary = next((row for row in aggregate.get("sources", []) if row.get("source") == "rs"), None)
                if not summary:
                    raise ValueError("Precollected RS summary is missing")
            else:
                summary = run_source(
                    code, run_results, archive_root, fixture_root,
                    args.stream if code == "rs" else "all", args.rs_period,
                )
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
        accepted, error = acceptable(code, summary, issues, args.stream if code == "rs" else "all")
        observations = read_json(folder / "observations.json", []) if summary.get("status") != "failed" else []
        forecasts = read_json(folder / "forecasts.json", []) if summary.get("status") != "failed" else []
        latest_date = latest_observation_date(observations)
        if code == "rs":
            forecast_source_dates = [
                value for row in forecasts
                if (value := normalized_source_date(row.get("forecast_issue_datetime_utc") or row.get("forecast_issue_time_original")))
            ]
            details["component_last_source_observation_at"] = {
                "nrt": latest_observation_date([row for row in observations if row.get("source_stream_type") == "nrt"]),
                "daily": latest_observation_date([row for row in observations if row.get("source_stream_type") == "daily"]),
                "forecast": max(forecast_source_dates) if forecast_source_dates else None,
            }
        if accepted and args.mode == "live":
            replace_candidate(candidates, code, folder, previous[code], args.stream if code in {"bg", "rs"} else "all")
        if args.mode == "live":
            update_state(state, code, now, summary, accepted, error, details, latest_date, commit_sha, args.stream if code == "rs" else "all")
        report = {
            **summary, **details, "accepted_for_publication": accepted,
            "parser_status": "success" if summary.get("status") != "failed" else "failed",
            "validator_status": "accepted" if accepted else "failed",
            "publication_status": ("fixture-only" if args.mode == "fixtures" else ("candidate" if accepted else "last-known-good")),
            "latest_observation_date": latest_date, "warnings": [row for row in issues if row.get("severity") != "critical"],
            "blocker": error, "request_made": args.mode == "live",
            "transport": details.get("transport"), "runner": details.get("runner"),
            "collection_profile": args.stream if code == "rs" else "all",
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
