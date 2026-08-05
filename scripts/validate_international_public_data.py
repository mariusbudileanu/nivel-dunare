#!/usr/bin/env python3
"""Validate the isolated international public beta contract and its mirror."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from scripts.geocode_international_stations import COUNTRY_BOUNDS, validate_registry


FILES = (
    "stations.json", "observations.json", "latest.json", "forecasts.json", "sources.json",
    "status.json", "stations.geojson", "unmapped_stations.json", "quality_issues.json",
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


def validate(root: Path, mirror: Path | None = None, geocoding_registry: Path = Path("data/reference/international_station_geocoding.csv"), geocoding_cache: Path = Path("data/reference/international_station_geocoding_cache-v1.json")) -> dict[str, Any]:
    for name in FILES:
        require((root / name).is_file(), f"Missing {root / name}")
        if mirror:
            require((mirror / name).is_file(), f"Missing mirror {mirror / name}")
            require(hashlib.sha256((root / name).read_bytes()).digest() == hashlib.sha256((mirror / name).read_bytes()).digest(), f"Mirror mismatch: {name}")

    raw_text = "\n".join((root / name).read_text(encoding="utf-8") for name in FILES)
    for pattern in SECRET_PATTERNS:
        require(not pattern.search(raw_text), f"Secret-like value detected by {pattern.pattern}")

    stations = read_json(root / "stations.json")
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
    slugs = [row["station_slug"] for row in stations]
    require(len(stations) == 101 == status["station_count"], "Public registry must contain 101 stations")
    require(len(station_ids) == len(set(station_ids)), "Duplicate station_id")
    require(len(slugs) == len(set(slugs)), "Duplicate station_slug")
    station_id_set = set(station_ids)
    require({row["station_id"] for row in observations} <= station_id_set, "Orphan observation")
    require({row["station_id"] for row in forecasts} <= station_id_set, "Orphan forecast")
    require({row["station_id"] for row in latest} <= station_id_set, "Orphan latest record")

    features = geojson.get("features", [])
    mapped_ids = {feature["properties"]["station_id"] for feature in features}
    unmapped_ids = {row["station_id"] for row in unmapped}
    require(geojson.get("type") == "FeatureCollection", "Invalid GeoJSON type")
    require(len(features) == status["mapped_station_count"], "Mapped count mismatch")
    require(len(unmapped) == status["unmapped_station_count"], "Unmapped count mismatch")
    require(mapped_ids.isdisjoint(unmapped_ids) and mapped_ids | unmapped_ids == station_id_set, "Mapped/unmapped partition mismatch")
    require(status["official_coordinate_station_count"] == 26, "Expected 26 official station coordinates")
    require(status["approximate_coordinate_station_count"] == 67, "Expected 67 accepted locality coordinates")
    require(len(features) == 93 and len(unmapped) == 8, "Unexpected accepted coordinate totals")
    coordinate_groups: dict[tuple[float, float], list[dict[str, Any]]] = {}
    for station in stations:
        for key in ("coordinate_method", "coordinate_source", "coordinate_provider", "coordinate_confidence", "coordinate_review_status", "is_exact_station_location"):
            require(key in station, f"Missing {key} for {station['station_id']}")
        if station["mapped"]:
            latitude, longitude = station["latitude"], station["longitude"]
            require(isinstance(latitude, (int, float)) and isinstance(longitude, (int, float)), "Mapped coordinate is not numeric")
            require(math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180, "Invalid EPSG:4326 coordinate")
            require(station["country_code"] in COUNTRY_BOUNDS and COUNTRY_BOUNDS[station["country_code"]][0] <= latitude <= COUNTRY_BOUNDS[station["country_code"]][1] and COUNTRY_BOUNDS[station["country_code"]][2] <= longitude <= COUNTRY_BOUNDS[station["country_code"]][3], "Coordinate outside country bounds")
            coordinate_groups.setdefault((latitude, longitude), []).append(station)
            if station["is_exact_station_location"]:
                require(station["coordinate_method"] == "official_station_coordinate" and station["coordinate_confidence"] == "high", "Invalid official coordinate metadata")
            else:
                require(station["coordinate_method"] == "geocoded_locality", "Approximate coordinate has wrong method")
                require(station["coordinate_confidence"] in {"medium", "low"} and station["coordinate_review_status"] == "accepted", "Unreviewed locality coordinate leaked into GeoJSON")
        else:
            require(station["latitude"] is None and station["longitude"] is None, "Unmapped station exposes coordinates")
            require(station["coordinate_review_status"] == "required", "Unmapped geocoding result is not marked for review")
    for group in coordinate_groups.values():
        if len(group) > 1:
            require(len({row["station_name"] for row in group}) == 1, "Unexplained duplicate coordinates across different localities")
    for feature in features:
        station = next(row for row in stations if row["station_id"] == feature["properties"]["station_id"])
        require(feature["geometry"]["coordinates"] == [station["longitude"], station["latitude"]], "GeoJSON/station coordinate mismatch")
        require(feature["properties"]["coordinate_method"] == station["coordinate_method"], "GeoJSON coordinate metadata mismatch")

    latest_keys = {(row["station_id"], row["parameter"]) for row in latest}
    require(len(latest_keys) == len(latest), "Duplicate latest record")
    require(all(row["current_usable"] for row in latest), "Latest contains unusable observation")
    require(all(row["canonical_quality_flag"] not in {"suspect", "missing"} for row in latest), "Latest contains suspect observation")
    require(not any(row["source_id"] == "appd_bg" for row in forecasts), "BG forecasts must not be normalized publicly")

    rs = [row for row in stations if row["country_code"] == "RS"]
    require(len(rs) == 13 and all(row["source_status"] == "suspended" for row in rs), "RS audit registry mismatch")
    require(not any(row["country_code"] == "RS" for row in observations + forecasts), "RS must have no live data")
    hr = [row for row in observations if row["country_code"] == "HR"]
    hr_source = next(row for row in sources if row["country_code"] == "HR")
    if hr_source.get("freshness_status") == "stale":
        require(hr and all(row["stale"] and not row["current_usable"] for row in hr), "HR stale values must remain historical")
        require(not any(row["country_code"] == "HR" for row in latest), "HR stale data present in latest")
    else:
        require(hr_source.get("freshness_status") == "current", "HR freshness must be current or stale")

    suspect_observations = [row for row in observations if row["canonical_quality_flag"] == "suspect"]
    require(suspect_observations, "Expected a suspect live observation")
    require(all((row["station_id"], row["parameter"]) not in latest_keys for row in suspect_observations), "Suspect observation leaked into latest")
    suspect_issues = [row for row in issues if row.get("code") == "outside_plausible_water_temperature_range"]
    require(any(row.get("historical") and row.get("observation", {}).get("value") == 46.2 for row in suspect_issues), "Historical Iza 46.2 quality record missing")
    current_suspect_issues = [row for row in suspect_issues if not row.get("historical")]
    require(any(row.get("observation", {}).get("canonical_quality_flag") == "suspect" for row in current_suspect_issues), "Current suspect observation is not preserved structurally in quality issues")

    require(len(sources) == 7 and {row["country_code"] for row in sources} == {"DE", "AT", "SK", "HU", "HR", "BG", "RS"}, "Source registry mismatch")
    require(status.get("contract_version") == "1.2-beta", "Unexpected public contract version")
    operational_keys = {
        "source_status", "automation_status", "freshness_status", "validation_status",
        "last_attempt_at", "last_success_at", "last_capture_at", "next_expected_update",
        "update_frequency", "validation_message_ro", "validation_message_en", "last_error",
        "consecutive_failures",
    }
    for source in sources:
        require(operational_keys <= set(source), f"Operational metadata incomplete for {source['country_code']}")
        require(source["source_status"] in {"complete", "partial", "suspended", "unavailable"}, "Invalid source_status")
        require(source["automation_status"] in {"scheduled", "manual", "disabled"}, "Invalid automation_status")
        require(source["freshness_status"] in {"current", "stale", "unknown", "unavailable"}, "Invalid freshness_status")
        require(source["validation_status"] in {"validated", "requires_review", "failed", "not_applicable"}, "Invalid validation_status")
        require(isinstance(source["consecutive_failures"], int) and source["consecutive_failures"] >= 0, "Invalid failure count")
    automation = {row["country_code"]: row["automation_status"] for row in sources}
    require({code for code, value in automation.items() if value == "scheduled"} == {"DE", "SK", "HU", "HR", "BG"}, "Scheduled source set mismatch")
    require(automation["AT"] == "manual" and automation["RS"] == "disabled", "AT/RS automation policy mismatch")
    require(status["complete_source_count"] == sum(row["source_status"] == "complete" for row in sources), "Complete source count mismatch")
    require(status["partial_source_count"] == sum(row["source_status"] == "partial" for row in sources), "Partial source count mismatch")
    require(status["suspended_source_count"] == sum(row["source_status"] == "suspended" for row in sources), "Suspended source count mismatch")
    require(status["observation_count"] == len(observations), "Observation count mismatch")
    require(status["current_usable_observation_count"] == sum(row["current_usable"] for row in observations), "Current usable observation count mismatch")
    require(status["stale_observation_count"] == sum(row["stale"] for row in observations), "Stale observation count mismatch")
    require(status["provisional_observation_count"] == sum(row["canonical_quality_flag"] == "provisional" for row in observations), "Provisional observation count mismatch")
    require(status["forecast_count"] == len(forecasts), "Forecast count mismatch")
    require(status["latest_valid_count"] == len(latest), "Latest count mismatch")
    require(all(row.get("source_file_sha256") and row.get("source_url") and row.get("source_status") for row in observations), "Observation provenance incomplete")
    require(all(row.get("captured_at_utc") for row in observations), "Observation capture time missing")
    require(all(row.get("measurement_time_original") and (row.get("measurement_datetime_utc") or row.get("measurement_datetime_local") or row.get("measurement_date")) for row in observations), "Observation original time or normalized date/time missing")
    require(all(row.get("source_file_sha256") and row.get("source_url") and row.get("source_status") and row.get("captured_at_utc") for row in forecasts), "Forecast provenance incomplete")
    require(all(row.get("target_time_original") and (row.get("target_datetime_utc") or row.get("target_date")) for row in forecasts), "Forecast original or normalized target time missing")

    return {
        "ok": True, "stations": len(stations), "mapped": len(features), "unmapped": len(unmapped),
        "official_coordinates": status["official_coordinate_station_count"],
        "approximate_coordinates": status["approximate_coordinate_station_count"],
        "observations": len(observations), "latest": len(latest), "forecasts": len(forecasts),
        "quality_issues": len(issues), "suspect_observations": len(suspect_observations), "geocoding": geocoding,
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
