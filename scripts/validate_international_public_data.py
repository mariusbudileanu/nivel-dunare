#!/usr/bin/env python3
"""Validate contract 1.3-beta and the byte-identical public mirror."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from scripts.build_international_public_data import EXPECTED_COUNTS
from scripts.geocode_international_stations import COUNTRY_BOUNDS, validate_registry


FILES = (
    "stations.json", "streams.json", "observations.json", "latest.json", "forecasts.json",
    "sources.json", "status.json", "stations.geojson", "unmapped_stations.json", "quality_issues.json",
)
SECRET_PATTERNS = (
    re.compile(r"viadonau_partner_key=[^&\s\"]+", re.I),
    re.compile(r"(?:api[_-]?key|access[_-]?token|secret)\s*[:=]\s*[\"']?(?!\[REDACTED\])[^\s,\"']+", re.I),
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def observation_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("source_stream_id") or row.get("station_id"), row.get("parameter"), row.get("value"), row.get("unit"),
        row.get("measurement_datetime_utc"), row.get("measurement_datetime_local"),
        row.get("measurement_date"), row.get("measurement_time_original"), row.get("source_file_sha256"),
    )


def validate(root: Path, mirror: Path | None = None,
             geocoding_registry: Path = Path("data/reference/international_station_geocoding.csv"),
             geocoding_cache: Path = Path("data/reference/international_station_geocoding_cache-v1.json")) -> dict[str, Any]:
    for name in FILES:
        require((root / name).is_file(), f"Missing {root / name}")
        if mirror:
            require((mirror / name).is_file(), f"Missing mirror {mirror / name}")
            require(hashlib.sha256((root / name).read_bytes()).digest() == hashlib.sha256((mirror / name).read_bytes()).digest(), f"Mirror mismatch: {name}")
    raw_text = "\n".join((root / name).read_text(encoding="utf-8") for name in FILES)
    for pattern in SECRET_PATTERNS:
        require(not pattern.search(raw_text), f"Secret-like value detected by {pattern.pattern}")

    stations = read_json(root / "stations.json")
    streams = read_json(root / "streams.json")
    observations = read_json(root / "observations.json")
    latest = read_json(root / "latest.json")
    forecasts = read_json(root / "forecasts.json")
    sources = read_json(root / "sources.json")
    status = read_json(root / "status.json")
    geojson = read_json(root / "stations.geojson")
    unmapped = read_json(root / "unmapped_stations.json")
    issues = read_json(root / "quality_issues.json")
    geocoding = validate_registry(root / "stations.json", geocoding_registry, geocoding_cache)

    station_ids = [row["station_id"] for row in stations]
    station_id_set = set(station_ids)
    physical_ids = {row["physical_station_id"] for row in stations}
    stream_ids = [row["source_stream_id"] for row in streams]
    expected_station_count = sum(EXPECTED_COUNTS.values())
    # 12 streams beyond the one-per-station baseline (BG manual+automatic pairs,
    # RS nrt/daily/forecast components) - structurally independent of which
    # country's station count changes.
    expected_stream_count = expected_station_count + 12
    require(status.get("contract_version") == "1.3-beta", "Unexpected public contract version")
    require(len(stations) == expected_station_count == status["station_count"], f"Public registry must contain {expected_station_count} station streams")
    require(len(station_ids) == len(station_id_set), "Duplicate station_id")
    require(len({row["station_slug"] for row in stations}) == len(stations), "Duplicate station_slug")
    require(len(streams) == status["station_stream_count"] and len(streams) in {expected_station_count, expected_stream_count}, "Stream registry count mismatch")
    require(len(stream_ids) == len(set(stream_ids)), "Duplicate source_stream_id")
    require({row["station_id"] for row in streams} == station_id_set, "Stream/station reference mismatch")
    require({row["physical_station_id"] for row in streams} <= physical_ids, "Orphan stream physical_station_id")
    for rows, label in ((observations, "observation"), (forecasts, "forecast"), (latest, "latest")):
        require({row["station_id"] for row in rows} <= station_id_set, f"Orphan {label}")
        require({row["source_stream_id"] for row in rows} <= set(stream_ids) or label == "forecast", f"Orphan {label} stream")
        require({row["physical_station_id"] for row in rows} <= physical_ids, f"Orphan {label} physical station")

    require(status["mapped_station_count"] == expected_station_count and status["unmapped_station_count"] == 0, f"All {expected_station_count} station streams must be mapped")
    require(status["official_coordinate_station_count"] == 50, f"Expected 50 official coordinates, got {status['official_coordinate_station_count']}")
    require(status["manually_verified_coordinate_station_count"] == 15, "Expected 15 manually verified exact coordinates")
    require(status["approximate_coordinate_station_count"] == 37, "Expected 37 locality coordinates")
    require(not unmapped, "No international station should remain list-only")
    method_counts = {method: sum(row["coordinate_method"] == method for row in stations) for method in (
        "official_station_coordinate", "manually_verified_station_coordinate", "geocoded_locality", "unresolved"
    )}
    require(method_counts == {
        "official_station_coordinate": 50, "manually_verified_station_coordinate": 15,
        "geocoded_locality": 37, "unresolved": 0,
    }, "Coordinate-method distribution mismatch")
    for station in stations:
        for key in (
            "physical_station_id", "source_stream_id", "source_stream_type", "is_primary_stream",
            "coordinate_method", "coordinate_source", "coordinate_provider", "coordinate_confidence",
            "coordinate_review_status", "is_exact_station_location", "coordinate_verified_at", "coordinate_notes",
        ):
            require(key in station, f"Missing {key} for {station['station_id']}")
        lat, lon = station["latitude"], station["longitude"]
        require(isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and math.isfinite(lat) and math.isfinite(lon), f"Invalid coordinate for {station['station_id']}")
        bounds = COUNTRY_BOUNDS[station["country_code"]]
        require(bounds[0] <= lat <= bounds[1] and bounds[2] <= lon <= bounds[3], f"Coordinate outside country bounds: {station['station_id']}")
        if station["coordinate_method"] in {"official_station_coordinate", "manually_verified_station_coordinate"}:
            require(station["is_exact_station_location"] is True and station["coordinate_confidence"] == "high", "Exact coordinate metadata mismatch")
        else:
            require(station["coordinate_method"] == "geocoded_locality" and station["is_exact_station_location"] is False, "Approximate coordinate metadata mismatch")
            require(station["coordinate_review_status"] == "accepted", "Unaccepted locality leaked publicly")

    features = geojson.get("features", [])
    feature_physical_ids = [row["properties"]["physical_station_id"] for row in features]
    require(geojson.get("type") == "FeatureCollection", "Invalid GeoJSON type")
    require(len(features) == len(set(feature_physical_ids)) == status["mapped_physical_station_count"] == status["physical_station_count"], "Physical marker aggregation mismatch")
    require(len(features) == 94, "Expected 94 physical international markers")
    require(sum(row["properties"]["stream_count"] for row in features) == len(streams), "Marker stream aggregation lost observation streams")
    for feature in features:
        props = feature["properties"]
        members = [row for row in stations if row["physical_station_id"] == props["physical_station_id"]]
        member_streams = [row for row in streams if row["physical_station_id"] == props["physical_station_id"]]
        require(props["stream_count"] == len(member_streams) == len(props["streams"]), "Feature stream count mismatch")
        require(set(props["station_ids"]) == {row["station_id"] for row in members}, "Feature station membership mismatch")
        require({row["source_stream_id"] for row in props["streams"]} == {row["source_stream_id"] for row in member_streams}, "Feature stream membership mismatch")
        primary = next((row for row in members if row["is_primary_stream"]), members[0])
        require(feature["geometry"]["coordinates"] == [primary["longitude"], primary["latitude"]], "GeoJSON coordinate mismatch")

    latest_keys = {(row["source_stream_id"], row["parameter"]) for row in latest}
    require(len(latest_keys) == len(latest), "Duplicate latest stream/parameter record")
    require(all(row["current_usable"] and row.get("canonical_quality_flag") != "missing" for row in latest), "Latest contains a technically missing/stale record")
    require(not any(row["source_id"] == "appd_bg" for row in forecasts), "BG forecast candidates must not be public")
    # Application plausibility thresholds are forbidden: negative and high official values stay unchanged.
    require(all(row.get("source_value_raw") in (None, str(row["value"])) or row.get("source_value_raw") for row in observations), "Observation raw value missing")
    legacy = [row for row in issues if row.get("quality_origin") == "legacy_application_rule"]
    require(all(row.get("historical") and row.get("active") is False for row in legacy), "Legacy application-rule finding is active")
    for issue in legacy:
        identity = observation_identity(issue["observation"])
        matching = [row for row in observations if observation_identity(row) == identity]
        if matching:
            require(all(row.get("current_usable") for row in matching), "Legacy threshold excluded an official current value")

    rs = [row for row in stations if row["country_code"] == "RS"]
    rs_observations = [row for row in observations if row["country_code"] == "RS"]
    rs_forecasts = [row for row in forecasts if row["country_code"] == "RS"]
    rs_streams = [row for row in streams if row["country_code"] == "RS"]
    rs_active = bool(rs_observations)
    require(len(rs) == 13, "RS station inventory mismatch")
    if rs_active:
        require(all(row["source_status"] == "complete" for row in rs), "Active RS source status mismatch")
        require(len(rs_streams) == 25, "RS must publish 12 NRT and 13 daily observation streams")
        require(sum(row["source_stream_type"] == "nrt" for row in rs_streams) == 12, "RS NRT stream count mismatch")
        require(sum(row["source_stream_type"] == "daily" for row in rs_streams) == 13, "RS daily stream count mismatch")
        require(rs_forecasts, "RS central point forecasts missing")
        require(all(row.get("canonical_quality_flag") == "provisional" for row in rs_observations if row.get("source_stream_type") == "nrt"), "RS NRT quality must remain provisional")
        require(all(row.get("measurement_datetime_local", "").endswith("+01:00") for row in rs_observations if row.get("source_stream_type") == "nrt"), "RS source-declared NRT offset missing")
        require(any(float(row["value"]) < 0 for row in rs_observations if isinstance(row.get("value"), (int, float))), "RS negative official level was not preserved")
        require(any(row.get("source_value_raw") in {"*", "-"} for row in rs_observations), "RS missing markers were not preserved")
        require(not any(row.get("canonical_quality_flag") == "missing" for row in latest if row["country_code"] == "RS"), "RS missing value leaked into latest")
    else:
        require(all(row["source_status"] in {"suspended", "complete"} for row in rs), "Prepared RS inventory/status mismatch")
        require(not rs_forecasts and len(rs_streams) == 13, "Legacy RS disabled-data contract mismatch")
    hr = [row for row in observations if row["country_code"] == "HR"]
    hr_source = next(row for row in sources if row["country_code"] == "HR")
    require(hr_source["access_status"] == "available", "HR access must be represented independently from freshness")
    if hr_source["freshness_status"] == "stale":
        require(hr and all(row["stale"] and not row["current_usable"] for row in hr), "HR stale LKG policy mismatch")
        require(not any(row["country_code"] == "HR" for row in latest), "HR stale values leaked into latest")

    require(len(sources) == 7 and {row["country_code"] for row in sources} == {"DE", "AT", "SK", "HU", "HR", "BG", "RS"}, "Source registry mismatch")
    required_source_keys = {
        "implementation_status", "source_status", "access_status", "automation_status", "freshness_status",
        "validation_status", "coordinate_status", "last_attempt_at", "last_success_at", "last_capture_at",
        "last_source_observation_at", "last_known_good_commit", "next_expected_update", "update_frequency",
        "validation_message_ro", "validation_message_en", "last_error", "consecutive_failures",
    }
    for source in sources:
        require(required_source_keys <= set(source), f"Operational metadata incomplete for {source['country_code']}")
        require(source["automation_status"] in {"scheduled", "manual", "disabled"}, "Invalid automation status")
        require(source["freshness_status"] in {"current", "stale", "unknown", "unavailable"}, "Invalid freshness status")
    automation = {row["country_code"]: row["automation_status"] for row in sources}
    expected_scheduled = {"DE", "SK", "HU", "HR", "BG"} | ({"RS"} if automation["RS"] == "scheduled" else set())
    require({code for code, value in automation.items() if value == "scheduled"} == expected_scheduled, "Scheduled source set mismatch")
    require(automation["AT"] == "manual", "AT automation mismatch")
    require(automation["RS"] in {"scheduled", "disabled"}, "RS automation mismatch")

    require(status["observation_count"] == len(observations), "Observation count mismatch")
    require(status["current_usable_observation_count"] == sum(row["current_usable"] for row in observations), "Usable observation count mismatch")
    require(status["forecast_count"] == len(forecasts) and status["latest_valid_count"] == len(latest), "Forecast/latest count mismatch")
    require(all(row.get("source_file_sha256") and row.get("source_url") and row.get("captured_at_utc") for row in observations), "Observation provenance incomplete")
    require(all(row.get("measurement_time_original") and (row.get("measurement_datetime_utc") or row.get("measurement_datetime_local") or row.get("measurement_date")) for row in observations), "Observation time provenance incomplete")
    require(all(row.get("source_file_sha256") and row.get("source_url") and row.get("captured_at_utc") for row in forecasts), "Forecast provenance incomplete")
    return {
        "ok": True, "contract_version": status["contract_version"], "stations": len(stations),
        "streams": len(streams), "physical_stations": len(features), "mapped": status["mapped_station_count"],
        "unmapped": len(unmapped), "official_coordinates": method_counts["official_station_coordinate"],
        "manually_verified_coordinates": method_counts["manually_verified_station_coordinate"],
        "approximate_coordinates": method_counts["geocoded_locality"], "observations": len(observations),
        "latest": len(latest), "forecasts": len(forecasts), "quality_issues": len(issues), "geocoding": geocoding,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/public/international"))
    parser.add_argument("--mirror", type=Path, default=Path("public/data/international"))
    parser.add_argument("--geocoding-registry", type=Path, default=Path("data/reference/international_station_geocoding.csv"))
    parser.add_argument("--geocoding-cache", type=Path, default=Path("data/reference/international_station_geocoding_cache-v1.json"))
    args = parser.parse_args(argv)
    print(json.dumps(validate(args.root, args.mirror, args.geocoding_registry, args.geocoding_cache), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
