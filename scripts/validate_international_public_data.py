#!/usr/bin/env python3
"""Validate the isolated international public beta contract and its mirror."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


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


def validate(root: Path, mirror: Path | None = None) -> dict[str, Any]:
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
    require(len(features) == 26 == status["mapped_station_count"], "Expected 26 mapped stations")
    require(len(unmapped) == 75 == status["unmapped_station_count"], "Expected 75 unmapped stations")
    require(mapped_ids.isdisjoint(unmapped_ids) and mapped_ids | unmapped_ids == station_id_set, "Mapped/unmapped partition mismatch")
    for feature in features:
        station = next(row for row in stations if row["station_id"] == feature["properties"]["station_id"])
        require(station["coordinate_method"] == "official_rest_payload" and station["coordinate_confidence"] == "high", "GeoJSON contains unverified coordinates")
        require(station["country_code"] in {"DE", "AT"}, "Only DE and AT may be mapped")

    latest_keys = {(row["station_id"], row["parameter"]) for row in latest}
    require(len(latest_keys) == len(latest), "Duplicate latest record")
    require(all(row["current_usable"] for row in latest), "Latest contains unusable observation")
    require(all(row["canonical_quality_flag"] not in {"suspect", "missing"} for row in latest), "Latest contains suspect observation")
    require(not any(row["country_code"] == "HR" for row in latest), "HR stale data present in latest")
    require(not any(row["source_id"] == "appd_bg" for row in forecasts), "BG forecasts must not be normalized publicly")

    rs = [row for row in stations if row["country_code"] == "RS"]
    require(len(rs) == 13 and all(row["source_status"] == "suspended" for row in rs), "RS audit registry mismatch")
    require(not any(row["country_code"] == "RS" for row in observations + forecasts), "RS must have no live data")
    hr = [row for row in observations if row["country_code"] == "HR"]
    require(hr and all(row["stale"] and not row["current_usable"] for row in hr), "HR values must be historical/stale")

    suspect_observations = [row for row in observations if row["canonical_quality_flag"] == "suspect"]
    require(suspect_observations, "Expected a suspect live observation")
    require(all((row["station_id"], row["parameter"]) not in latest_keys for row in suspect_observations), "Suspect observation leaked into latest")
    suspect_issues = [row for row in issues if row.get("code") == "outside_plausible_water_temperature_range"]
    require(any(row.get("historical") and row.get("observation", {}).get("value") == 46.2 for row in suspect_issues), "Historical Iza 46.2 quality record missing")
    require(any(not row.get("historical") for row in suspect_issues), "Current suspect quality record missing")

    require(len(sources) == 7 and {row["country_code"] for row in sources} == {"DE", "AT", "SK", "HU", "HR", "BG", "RS"}, "Source registry mismatch")
    require(status["observation_count"] == len(observations), "Observation count mismatch")
    require(status["forecast_count"] == len(forecasts), "Forecast count mismatch")
    require(status["latest_valid_count"] == len(latest), "Latest count mismatch")
    require(all(row.get("source_file_sha256") and row.get("source_url") and row.get("source_status") for row in observations), "Observation provenance incomplete")
    require(all(row.get("captured_at_utc") for row in observations), "Observation capture time missing")

    return {
        "ok": True, "stations": len(stations), "mapped": len(features), "unmapped": len(unmapped),
        "observations": len(observations), "latest": len(latest), "forecasts": len(forecasts),
        "quality_issues": len(issues), "suspect_observations": len(suspect_observations),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/public/international"))
    parser.add_argument("--mirror", type=Path, default=Path("public/data/international"))
    args = parser.parse_args(argv)
    print(json.dumps(validate(args.root, args.mirror), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
