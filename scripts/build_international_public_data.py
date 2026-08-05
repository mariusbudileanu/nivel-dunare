#!/usr/bin/env python3
"""Build the versioned international Danube public beta contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.sources.reference import coordinate_overrides, ris_rows


SOURCE_POLICY = {
    "de": {"source_id": "pegelonline_de", "status": "complete", "observations": True, "forecasts": True, "current": True, "label": "WSV PEGELONLINE"},
    "at": {"source_id": "viadonau_at", "status": "partial", "observations": True, "forecasts": True, "current": True, "label": "viadonau DoRIS", "note": "Public test access; production requires a permanent DoRIS partner key."},
    "sk": {"source_id": "shmu_sk", "status": "partial", "observations": True, "forecasts": True, "current": True, "label": "SHMU", "note": "Official values are reproduced without application plausibility thresholds; source provisional flags are preserved."},
    "hu": {"source_id": "hydroinfo_hu", "status": "complete", "observations": True, "forecasts": False, "current": True, "label": "OVF Hydroinfo"},
    "hr": {"source_id": "vodniputovi_hr", "status": "partial", "observations": True, "forecasts": False, "current": False, "label": "Croatian waterways / DHMZ", "note": "Access remains available; the last official observations are stale and retained as last-known-good."},
    "bg": {"source_id": "appd_bg", "status": "partial", "observations": True, "forecasts": False, "current": True, "label": "APPD", "note": "Twenty RIS-identified streams at thirteen physical gauges; forecast candidates are not public until semantics are demonstrated."},
    "rs": {"source_id": "hidmet_rs", "status": "suspended", "observations": False, "forecasts": False, "current": False, "label": "RHMZ / Hidmet", "note": "Production access is disabled after standard TLS validation failed; no scheduled request is made."},
}

EXPECTED_COUNTS = {"de": 18, "at": 9, "sk": 13, "hu": 25, "hr": 3, "bg": 20, "rs": 13}
SENSITIVE_QUERY_KEYS = {"viadonau_partner_key", "api_key", "apikey", "token", "access_token"}
DEFAULT_OPERATIONAL_FIELDS = {
    "de": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "source_validated"},
    "at": {"access_status": "available", "automation_status": "manual", "freshness_status": "current", "validation_status": "source_provisional"},
    "sk": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "source_provisional"},
    "hu": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "technical_validation_passed"},
    "hr": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "stale", "validation_status": "technical_validation_passed"},
    "bg": {"access_status": "available", "automation_status": "scheduled", "freshness_status": "current", "validation_status": "source_provisional"},
    "rs": {"access_status": "tls_failed", "automation_status": "disabled", "freshness_status": "unavailable", "validation_status": "technical_validation_failed"},
}
OPERATIONAL_KEYS = (
    "access_status", "automation_status", "freshness_status", "validation_status", "coordinate_status",
    "last_attempt_at", "last_attempt_status", "last_success_at", "last_successful_fetch_at",
    "last_capture_at", "last_source_observation_at", "last_known_good_commit", "last_success_commit",
    "last_error_code", "last_error_message", "last_error", "consecutive_failures",
    "published_snapshot_date", "next_expected_update", "update_frequency", "source_observation_frequency",
    "last_known_good_at", "validation_message_ro", "validation_message_en", "data_policy_ro", "data_policy_en",
)
DATA_POLICY = {
    "ro": "Valorile sunt reproduse conform surselor oficiale și nu sunt corectate sau reinterpretate de această aplicație.",
    "en": "Values are reproduced as provided by the official sources and are not corrected or reinterpreted by this application.",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sanitize_url(value: str | None) -> str | None:
    if not value:
        return value
    parts = urllib.parse.urlsplit(value)
    query = [(key, item) for key, item in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if key.casefold() not in SENSITIVE_QUERY_KEYS]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment))


def capture_index(root: Path | None) -> tuple[dict[str, str], dict[str, str]]:
    by_sha: dict[str, str] = {}
    by_source: dict[str, str] = {}
    if not root or not root.exists():
        return by_sha, by_source
    for path in sorted(root.rglob("*.metadata.json")):
        item = read_json(path)
        sha, captured, source = item.get("content_sha256"), item.get("captured_at_utc"), item.get("source")
        if sha and captured:
            by_sha[sha] = captured
        if source and captured and captured > by_source.get(source, ""):
            by_source[source] = captured
    return by_sha, by_source


def _geocoding_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Missing geocoding registry: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["station_id"]: row for row in csv.DictReader(handle)}


def _apply_reference_row(station: dict[str, Any], row: dict[str, Any]) -> None:
    for key in (
        "physical_station_id", "source_station_id", "source_stream_id", "source_stream_type", "is_primary_stream",
        "isrs_location_code", "coordinate_method", "coordinate_source", "coordinate_provider",
        "coordinate_confidence", "coordinate_review_status", "is_exact_station_location",
        "coordinate_verified_at", "coordinate_notes", "source_coordinate_raw", "source_crs",
        "aliases", "official_station_number", "measuring_point_uid", "pnp_value_m", "pnp_datum", "pnp_valid_from",
        "workbook_filename", "workbook_sheet", "workbook_row", "workbook_version", "workbook_sha256",
    ):
        if key in row and row[key] is not None:
            station[key] = row[key]
    for key in ("latitude", "longitude", "river_km"):
        if row.get(key) is not None:
            station[key] = float(row[key])
    if row.get("station_name"):
        station["station_name"] = row["station_name"]
        station["station_name_local"] = row["station_name"]


def apply_coordinate_registry(stations: list[dict[str, Any]], registry_path: Path) -> None:
    """Apply references in official > manually verified > locality order."""
    geocoded = _geocoding_rows(registry_path)
    ids = {row["station_id"] for row in stations}
    unknown = set(geocoded) - ids
    if unknown:
        raise ValueError(f"Geocoding registry contains unknown station IDs: {sorted(unknown)}")
    ris = {row["station_id"]: row for row in ris_rows()}
    overrides = coordinate_overrides()
    for station in stations:
        station.setdefault("physical_station_id", station["station_id"])
        station.setdefault("source_stream_id", station.get("source_station_id") or station["station_id"])
        station.setdefault("source_stream_type", "observed")
        station.setdefault("is_primary_stream", True)
        station.setdefault("observation_frequency", None)
        if station["station_id"] in {"de-560cf185-0052-4e40-832b-7792b52dd343", "de-0fd56e0a-e32e-4b56-9cda-e0ce93d715c4"}:
            station["physical_station_id"] = "de-560cf185-0052-4e40-832b-7792b52dd343"
            station["is_primary_stream"] = station["station_id"] == "de-0fd56e0a-e32e-4b56-9cda-e0ce93d715c4"
        if station["station_id"] in ris:
            row = dict(ris[station["station_id"]])
            row["river_km"] = row.get("waterway_km")
            row["coordinate_notes"] = row.get("provenance_note")
            _apply_reference_row(station, row)
        override = overrides.get(station["station_id"]) or overrides.get(station.get("physical_station_id"))
        if override:
            _apply_reference_row(station, override)
        has_exact = station.get("latitude") is not None and station.get("longitude") is not None and (
            bool(station.get("is_exact_station_location"))
            or station.get("coordinate_method") in {"official_station_coordinate", "official_rest_payload"}
            or station.get("coordinate_source") == "official"
        )
        if has_exact:
            if station.get("coordinate_method") not in {"official_station_coordinate", "manually_verified_station_coordinate"}:
                station["coordinate_method"] = "official_station_coordinate"
            station["coordinate_confidence"] = "high"
            station["coordinate_review_status"] = "accepted"
            station["is_exact_station_location"] = True
        if not has_exact:
            row = geocoded.get(station["station_id"])
            accepted = bool(row and row.get("review_status") == "accepted" and row.get("latitude") and row.get("longitude"))
            if accepted:
                station.update({
                    "latitude": float(row["latitude"]), "longitude": float(row["longitude"]),
                    "coordinate_method": "geocoded_locality", "coordinate_source": row.get("source_url") or row.get("coordinate_source"),
                    "coordinate_provider": row.get("coordinate_provider"), "coordinate_confidence": row.get("coordinate_confidence") or "medium",
                    "coordinate_review_status": "accepted", "is_exact_station_location": False,
                    "coordinate_verified_at": row.get("geocoded_at"), "coordinate_notes": row.get("review_notes"),
                })
            elif not has_exact:
                station.update({
                    "latitude": None, "longitude": None, "coordinate_method": "unresolved",
                    "coordinate_confidence": "unresolved", "coordinate_review_status": "required",
                    "is_exact_station_location": False,
                })
        station.setdefault("coordinate_provider", station.get("source_label") or station.get("source_id"))
        station.setdefault("coordinate_review_status", "accepted" if station.get("latitude") is not None else "required")
        station.setdefault("coordinate_verified_at", station.get("last_verified_at"))
        station.setdefault("coordinate_notes", "Coordinate metadata retained from the validated source adapter.")
        station.setdefault("source_coordinate_raw", None)
        station.setdefault("source_crs", "EPSG:4326" if station.get("latitude") is not None else None)
        station["mapped"] = station.get("latitude") is not None and station.get("longitude") is not None


def observation_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        row.get("measurement_datetime_utc") or row.get("measurement_date") or row.get("measurement_datetime_local") or row.get("measurement_time_original") or "",
        row.get("captured_at_utc") or row.get("capture_at") or "",
    )


def enrich_observation(row: dict[str, Any], station: dict[str, Any], policy: dict[str, Any], captures: dict[str, str]) -> dict[str, Any]:
    result = dict(row)
    quality = result.get("canonical_quality_flag") or "observed"
    result.update({
        "country_code": station["country_code"], "station_name": station["station_name"],
        "station_name_local": station["station_name_local"], "source_id": policy["source_id"],
        "source_status": policy["status"], "source_url": sanitize_url(station.get("source_url")),
        "physical_station_id": result.get("physical_station_id") or station["physical_station_id"],
        "source_stream_id": result.get("source_stream_id") or station["source_stream_id"],
        "source_stream_type": result.get("source_stream_type") or station["source_stream_type"],
        "is_primary_stream": result.get("is_primary_stream", station["is_primary_stream"]),
        "observation_frequency": result.get("observation_frequency") or station.get("observation_frequency"),
        "captured_at_utc": captures.get(result.get("source_file_sha256", "")) or result.get("captured_at_utc") or result.get("capture_at"),
        "current_usable": bool(policy["current"] and quality != "missing"), "stale": not policy["current"],
    })
    return result


def enrich_forecast(row: dict[str, Any], station: dict[str, Any], policy: dict[str, Any], captures: dict[str, str]) -> dict[str, Any]:
    result = dict(row)
    result.update({
        "country_code": station["country_code"], "station_name": station["station_name"],
        "station_name_local": station["station_name_local"], "source_id": policy["source_id"],
        "source_status": policy["status"], "source_url": sanitize_url(station.get("source_url")),
        "physical_station_id": result.get("physical_station_id") or station["physical_station_id"],
        "source_stream_id": result.get("source_stream_id") or f"{station['source_stream_id']}:forecast",
        "captured_at_utc": captures.get(result.get("source_file_sha256", "")) or result.get("captured_at_utc") or result.get("capture_at"),
    })
    return result


def historical_quality_issues(candidate_root: Path | None, archive_root: Path | None, stations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep prior application-rule findings as inactive audit evidence only."""
    if not candidate_root or not candidate_root.exists():
        return []
    captures, _ = capture_index(archive_root)
    observations = read_json(candidate_root / "observations.json")
    issues = read_json(candidate_root / "issues.json")
    result: list[dict[str, Any]] = []
    for issue in issues:
        if issue.get("code") not in {"outside_plausible_water_temperature_range", "impossible_value"}:
            continue
        for observation in observations:
            if observation.get("station_id") != issue.get("record_id") or observation.get("parameter") != "water_temperature":
                continue
            station = stations.get(observation["station_id"])
            if not station:
                continue
            evidence = dict(observation)
            evidence["quality_origin"] = "legacy_application_rule"
            result.append({
                "source_id": "shmu_sk", "source_status": "partial", "station_id": station["station_id"],
                "station_name": station["station_name"], "station_name_local": station["station_name_local"],
                "severity": "information", "code": issue["code"], "historical": True, "active": False,
                "quality_origin": "legacy_application_rule", "message": "Inactive historical application-rule finding; it does not alter or exclude the official value.",
                "captured_at_utc": captures.get(observation.get("source_file_sha256", "")), "observation": evidence,
            })
    return result


def _rs_inventory(audit_csv: Path, policy: dict[str, Any]) -> list[dict[str, Any]]:
    with audit_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["country_code"] == "RS"]
    if len(rows) != EXPECTED_COUNTS["rs"]:
        raise ValueError(f"rs: expected 13 audited stations, got {len(rows)}")
    result = []
    for row in rows:
        result.append({
            "station_id": row["station_id"], "source_station_id": row["source_station_id"],
            "physical_station_id": row["station_id"], "source_stream_id": row["source_station_id"],
            "source_stream_type": "daily_manual", "is_primary_stream": True, "observation_frequency": "daily",
            "country_code": "RS", "station_name": row["station_name"], "station_name_local": row["station_name_local"],
            "station_slug": row["station_slug"], "river_name": row["river"], "river_km": None,
            "latitude": None, "longitude": None, "coordinate_source": None, "coordinate_method": "unresolved",
            "coordinate_confidence": "unresolved", "coordinate_review_status": "required", "is_exact_station_location": False,
            "source_url": sanitize_url(row["source_url"]), "active": None, "last_verified_at": row["last_verified_at"],
            "operator_provider_id": "hidmet_rs", "source_provider_id": "hidmet_rs", "captured_via_provider_id": "audit_only",
            "included": False, "inclusion_reason": row["review_reason"], "station_type": row["station_type"],
            "source_id": "hidmet_rs", "source_status": policy["status"], "source_label": policy["label"],
            "capture_datetime_utc": None, "has_current_data": False,
        })
    return result


def _stream_rows(stations: list[dict[str, Any]], observations: list[dict[str, Any]], forecasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    obs_count = defaultdict(int)
    forecast_count = defaultdict(int)
    for row in observations:
        obs_count[row["source_stream_id"]] += 1
    for row in forecasts:
        forecast_count[row["source_stream_id"]] += 1
    return [{
        "station_id": row["station_id"], "physical_station_id": row["physical_station_id"],
        "source_stream_id": row["source_stream_id"], "source_stream_type": row["source_stream_type"],
        "is_primary_stream": row["is_primary_stream"], "observation_frequency": row.get("observation_frequency"),
        "country_code": row["country_code"], "source_id": row["source_id"],
        "observation_count": obs_count[row["source_stream_id"]], "forecast_count": forecast_count[row["source_stream_id"]],
    } for row in stations]


def build(candidate_root: Path, audit_csv: Path, archive_root: Path, output_root: Path, mirror_root: Path | None = None,
          historical_quality_root: Path | None = None, historical_archive_root: Path | None = None,
          fixtures_run_id: str | None = None, live_run_id: str | None = None,
          geocoding_registry: Path = Path("data/reference/international_station_geocoding.csv"),
          operations_state: Path | None = None) -> dict[str, Any]:
    captures, source_captures = capture_index(archive_root)
    operations = read_json(operations_state) if operations_state and operations_state.is_file() else {"sources": {}}
    operations_by_code = operations.get("sources", {})
    aggregate = read_json(candidate_root / "summary.json")
    aggregate_by_source = {item["source"]: item for item in aggregate.get("sources", [])}
    policies: dict[str, dict[str, Any]] = {}
    for code, base in SOURCE_POLICY.items():
        operational = {**DEFAULT_OPERATIONAL_FIELDS[code], **operations_by_code.get(code, {})}
        policies[code] = {**base, "status": operational.get("source_status", base["status"]), "current": operational.get("freshness_status") == "current"}

    stations: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    forecasts: list[dict[str, Any]] = []
    quality_issues: list[dict[str, Any]] = []
    for code, policy in policies.items():
        if code == "rs":
            continue
        folder = candidate_root / code
        source_stations = read_json(folder / "stations.json")
        if len(source_stations) != EXPECTED_COUNTS[code]:
            raise ValueError(f"{code}: expected {EXPECTED_COUNTS[code]} stations, got {len(source_stations)}")
        for row in source_stations:
            item = dict(row)
            item.update({
                "source_id": policy["source_id"], "source_status": policy["status"], "source_label": policy["label"],
                "source_url": sanitize_url(row.get("source_url")), "capture_datetime_utc": source_captures.get(policy["source_id"]) or row.get("capture_datetime_utc"),
                "has_current_data": bool(policy["current"]),
            })
            item["physical_station_id"] = item.get("physical_station_id") or item["station_id"]
            item["source_stream_id"] = item.get("source_stream_id") or item.get("source_station_id") or item["station_id"]
            item["source_stream_type"] = item.get("source_stream_type") or "observed"
            item["is_primary_stream"] = item.get("is_primary_stream", True)
            stations.append(item)
        current_lookup = {row["station_id"]: row for row in stations}
        if policy["observations"]:
            observations.extend(enrich_observation(row, current_lookup[row["station_id"]], policy, captures) for row in read_json(folder / "observations.json"))
        if policy["forecasts"]:
            forecasts.extend(enrich_forecast(row, current_lookup[row["station_id"]], policy, captures) for row in read_json(folder / "forecasts.json"))
        for issue in read_json(folder / "issues.json"):
            quality_issues.append({**issue, "source_id": policy["source_id"], "source_status": policy["status"], "captured_at_utc": source_captures.get(policy["source_id"]) or issue.get("captured_at_utc"), "historical": issue.get("historical", False)})
    stations.extend(_rs_inventory(audit_csv, policies["rs"]))
    apply_coordinate_registry(stations, geocoding_registry)
    station_lookup = {row["station_id"]: row for row in stations}
    if len(station_lookup) != 101:
        raise ValueError(f"Expected 101 unique station streams, got {len(station_lookup)}")

    # Coordinate references may have changed physical/stream IDs after enrichment.
    for row in observations:
        station = station_lookup[row["station_id"]]
        row["physical_station_id"] = station["physical_station_id"]
        row["source_stream_id"] = station["source_stream_id"]
        row["source_stream_type"] = station["source_stream_type"]
        row["is_primary_stream"] = station["is_primary_stream"]
    for row in forecasts:
        station = station_lookup[row["station_id"]]
        row["physical_station_id"] = station["physical_station_id"]
        row.setdefault("source_stream_id", f"{station['source_stream_id']}:forecast")
    quality_issues.extend(historical_quality_issues(historical_quality_root, historical_archive_root, station_lookup))
    # Migrate application-only plausibility findings into inactive audit evidence.
    # The underlying official observations remain publishable and source-provisional.
    for row in observations:
        if row.get("source_id") == "shmu_sk" and row.get("canonical_quality_flag") == "suspect" and row.get("source_quality_code") == "outside_plausible_water_temperature_range":
            row["canonical_quality_flag"] = "provisional"
            row["source_quality_code"] = "provisional"
            row["source_quality_status"] = "provisional"
            row["current_usable"] = not row.get("stale", False)
    known_observations = {observation_sort_key(row) + (row.get("station_id"), row.get("parameter"), row.get("value")) for row in observations}
    for issue in quality_issues:
        if issue.get("code") not in {"outside_plausible_water_temperature_range", "impossible_value"}:
            continue
        issue.update({"historical": True, "active": False, "severity": "information", "quality_origin": "legacy_application_rule"})
        issue["message"] = "Inactive historical application-rule finding; it does not alter or exclude the official value."
        evidence = issue.get("observation")
        if not evidence or not issue.get("station_id"):
            continue
        evidence = dict(evidence)
        evidence["canonical_quality_flag"] = "provisional"
        evidence["source_quality_code"] = "provisional"
        evidence["source_quality_status"] = "provisional"
        station = station_lookup[issue["station_id"]]
        migrated = enrich_observation(evidence, station, policies[station["country_code"].lower()], captures)
        migrated["captured_at_utc"] = migrated.get("captured_at_utc") or issue.get("captured_at_utc")
        migrated["current_usable"] = not migrated["stale"]
        identity = observation_sort_key(migrated) + (migrated.get("station_id"), migrated.get("parameter"), migrated.get("value"))
        if identity not in known_observations:
            observations.append(migrated)
            known_observations.add(identity)
        issue["observation"] = migrated
    for issue in quality_issues:
        station = station_lookup.get(issue.get("record_id") or issue.get("station_id"))
        if station:
            issue.setdefault("station_id", station["station_id"])
            issue.setdefault("station_name", station["station_name"])
            issue.setdefault("station_name_local", station["station_name_local"])

    latest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in observations:
        if not row["current_usable"]:
            continue
        key = (row["source_stream_id"], row["parameter"])
        if key not in latest_by_key or observation_sort_key(row) > observation_sort_key(latest_by_key[key]):
            latest_by_key[key] = row
    latest = list(latest_by_key.values())

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for station in stations:
        grouped[station["physical_station_id"]].append(station)
    latest_per_stream = defaultdict(dict)
    for row in latest:
        latest_per_stream[row["source_stream_id"]][row["parameter"]] = row
    features = []
    for physical_id, group in sorted(grouped.items()):
        mapped_group = [row for row in group if row["mapped"]]
        if not mapped_group:
            continue
        primary = next((row for row in mapped_group if row["is_primary_stream"]), mapped_group[0])
        properties = {key: primary.get(key) for key in (
            "station_id", "station_slug", "station_name", "station_name_local", "country_code", "river_name", "river_km",
            "station_type", "source_id", "source_label", "source_status", "source_url", "capture_datetime_utc",
            "coordinate_method", "coordinate_source", "coordinate_provider", "coordinate_confidence",
            "coordinate_review_status", "is_exact_station_location", "coordinate_verified_at", "coordinate_notes",
        )}
        properties.update({
            "physical_station_id": physical_id, "station_ids": [row["station_id"] for row in group],
            "stream_count": len(group), "streams": [{
                "station_id": row["station_id"], "source_stream_id": row["source_stream_id"],
                "source_stream_type": row["source_stream_type"], "is_primary_stream": row["is_primary_stream"],
                "observation_frequency": row.get("observation_frequency"), "latest": latest_per_stream[row["source_stream_id"]],
            } for row in group],
        })
        for parameter in ("water_level", "discharge", "water_temperature", "ice_condition"):
            properties[parameter] = latest_per_stream[primary["source_stream_id"]].get(parameter)
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [primary["longitude"], primary["latitude"]]}, "properties": properties})

    unmapped = [row for row in stations if not row["mapped"]]
    streams = _stream_rows(stations, observations, forecasts)
    sources = []
    for code, policy in policies.items():
        operational = {**DEFAULT_OPERATIONAL_FIELDS[code], **operations_by_code.get(code, {})}
        source = {
            "country_code": code.upper(), "source_id": policy["source_id"], "label": policy["label"],
            "implementation_status": SOURCE_POLICY[code]["status"], "source_status": policy["status"],
            "capture_datetime_utc": source_captures.get(policy["source_id"]) or operational.get("last_capture_at"),
            "station_count": EXPECTED_COUNTS[code], "physical_station_count": len({row["physical_station_id"] for row in stations if row["country_code"] == code.upper()}),
            "observation_count": sum(row["source_id"] == policy["source_id"] for row in observations),
            "forecast_count": sum(row["source_id"] == policy["source_id"] for row in forecasts),
            "adapter_live_status": aggregate_by_source.get(code, {}).get("status", "suspended" if code == "rs" else "unavailable"),
            "note": policy.get("note"), "live_run_id": live_run_id,
        }
        for key in OPERATIONAL_KEYS:
            source[key] = operational.get(key)
        frequencies = sorted({str(row["observation_frequency"]) for row in stations if row["country_code"] == code.upper() and row.get("observation_frequency")})
        source["source_observation_frequency"] = operational.get("source_observation_frequency") or frequencies
        source["last_known_good_at"] = operational.get("last_known_good_at") or operational.get("last_success_at")
        source["data_policy_ro"] = operational.get("data_policy_ro") or DATA_POLICY["ro"]
        source["data_policy_en"] = operational.get("data_policy_en") or DATA_POLICY["en"]
        source["coordinate_status"] = "complete" if all(row["mapped"] for row in stations if row["country_code"] == code.upper()) else "partial"
        sources.append(source)

    method_counts = defaultdict(int)
    for row in stations:
        method_counts[row["coordinate_method"]] += 1
    status = {
        "beta": True, "contract_version": "1.3-beta", "data_policy": DATA_POLICY,
        "generated_from_capture_utc": max([value for value in source_captures.values()] + [""]) or None,
        "fixtures_run_id": fixtures_run_id, "live_run_id": live_run_id,
        "station_count": len(stations), "station_stream_count": len(streams), "physical_station_count": len(grouped),
        "mapped_station_count": sum(row["mapped"] for row in stations), "mapped_physical_station_count": len(features),
        "unmapped_station_count": len(unmapped), "official_coordinate_station_count": method_counts["official_station_coordinate"],
        "manually_verified_coordinate_station_count": method_counts["manually_verified_station_coordinate"],
        "approximate_coordinate_station_count": method_counts["geocoded_locality"],
        "current_station_count": len({row["physical_station_id"] for row in latest}),
        "observation_count": len(observations), "current_usable_observation_count": sum(row["current_usable"] for row in observations),
        "stale_observation_count": sum(row["stale"] for row in observations),
        "provisional_observation_count": sum(row.get("canonical_quality_flag") == "provisional" for row in observations),
        "latest_valid_count": len(latest), "forecast_count": len(forecasts),
        "quality_issue_count": len(quality_issues), "active_quality_issue_count": sum(row.get("active", True) for row in quality_issues),
        "complete_source_count": sum(row["source_status"] == "complete" for row in sources),
        "partial_source_count": sum(row["source_status"] == "partial" for row in sources),
        "suspended_source_count": sum(row["source_status"] == "suspended" for row in sources),
    }

    stations.sort(key=lambda row: (row["country_code"], row["station_name"], row["station_id"]))
    streams.sort(key=lambda row: (row["country_code"], row["physical_station_id"], row["source_stream_id"]))
    observations.sort(key=lambda row: (row["country_code"], row["source_stream_id"], row["parameter"], observation_sort_key(row)))
    forecasts.sort(key=lambda row: (row["country_code"], row["source_stream_id"], row.get("target_datetime_utc") or row.get("target_date") or row.get("target_time_original") or ""))
    latest.sort(key=lambda row: (row["country_code"], row["source_stream_id"], row["parameter"]))
    unmapped.sort(key=lambda row: (row["country_code"], row["station_name"], row["station_id"]))
    quality_issues.sort(key=lambda row: (row.get("source_id", ""), row.get("station_id") or row.get("record_id") or "", row.get("code", "")))
    payloads = {
        "stations.json": stations, "streams.json": streams, "observations.json": observations,
        "latest.json": latest, "forecasts.json": forecasts, "sources.json": sources, "status.json": status,
        "stations.geojson": {"type": "FeatureCollection", "features": features},
        "unmapped_stations.json": unmapped, "quality_issues.json": quality_issues,
    }
    if output_root.exists():
        shutil.rmtree(output_root)
    for name, value in payloads.items():
        write_json(output_root / name, value)
    if mirror_root:
        if mirror_root.exists():
            shutil.rmtree(mirror_root)
        shutil.copytree(output_root, mirror_root)
        for path in output_root.iterdir():
            if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256((mirror_root / path.name).read_bytes()).digest():
                raise ValueError(f"Mirror mismatch for {path.name}")
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--audit-csv", type=Path, default=Path("docs/INTERNATIONAL_STATIONS_AUDIT.csv"))
    parser.add_argument("--output-root", type=Path, default=Path("data/public/international"))
    parser.add_argument("--mirror-root", type=Path, default=Path("public/data/international"))
    parser.add_argument("--historical-quality-root", type=Path)
    parser.add_argument("--historical-archive-root", type=Path)
    parser.add_argument("--fixtures-run-id")
    parser.add_argument("--live-run-id")
    parser.add_argument("--geocoding-registry", type=Path, default=Path("data/reference/international_station_geocoding.csv"))
    parser.add_argument("--operations-state", type=Path)
    args = parser.parse_args(argv)
    status = build(args.candidate_root, args.audit_csv, args.archive_root, args.output_root, args.mirror_root,
                   args.historical_quality_root, args.historical_archive_root, args.fixtures_run_id, args.live_run_id,
                   args.geocoding_registry, args.operations_state)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
