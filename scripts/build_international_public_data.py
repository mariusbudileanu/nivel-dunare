#!/usr/bin/env python3
"""Promote validated international candidates into an isolated public beta namespace."""

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


SOURCE_POLICY = {
    "de": {"source_id": "pegelonline_de", "status": "complete", "observations": True, "forecasts": True, "current": True, "label": "WSV PEGELONLINE"},
    "at": {"source_id": "viadonau_at", "status": "partial", "observations": True, "forecasts": True, "current": True, "label": "viadonau DoRIS", "note": "Public test source; a permanent DORIS_PARTNER_KEY is required for production."},
    "sk": {"source_id": "shmu_sk", "status": "partial", "observations": True, "forecasts": True, "current": True, "label": "SHMU", "note": "Usable beta data; suspect temperatures are excluded from latest valid values."},
    "hu": {"source_id": "hydroinfo_hu", "status": "complete", "observations": True, "forecasts": False, "current": True, "label": "OVF Hydroinfo"},
    "hr": {"source_id": "vodniputovi_hr", "status": "suspended", "observations": True, "forecasts": False, "current": False, "label": "Croatian waterways / DHMZ", "note": "Feed is stale; historical values are not current."},
    "bg": {"source_id": "appd_bg", "status": "partial", "observations": True, "forecasts": False, "current": True, "label": "APPD", "note": "Institutional station IDs and forecast semantics are not demonstrated."},
    "rs": {"source_id": "hidmet_rs", "status": "suspended", "observations": False, "forecasts": False, "current": False, "label": "RHMZ / Hidmet", "note": "Live access suspended after TLS certificate-chain validation failure; no request is made."},
}

SENSITIVE_QUERY_KEYS = {"viadonau_partner_key", "api_key", "apikey", "token", "access_token"}
EXPECTED_COUNTS = {"de": 18, "at": 9, "sk": 13, "hu": 25, "hr": 3, "bg": 20, "rs": 13}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def apply_coordinate_registry(stations: list[dict[str, Any]], registry_path: Path) -> None:
    if not registry_path.is_file():
        raise ValueError(f"Missing geocoding registry: {registry_path}")
    with registry_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["station_id"]: row for row in csv.DictReader(stream)}
    if len(rows) != 75:
        raise ValueError(f"Expected 75 geocoding registry rows, got {len(rows)}")
    station_ids = {station["station_id"] for station in stations}
    if not set(rows) <= station_ids:
        raise ValueError("Geocoding registry contains an unknown station_id")
    expected = {
        station["station_id"] for station in stations
        if station.get("latitude") is None or station.get("longitude") is None
        or station.get("is_exact_station_location") is False
    }
    if set(rows) != expected:
        raise ValueError("Geocoding registry does not match the 75 stations without official coordinates")
    for station in stations:
        has_official = (
            station.get("latitude") is not None and station.get("longitude") is not None
            and station["station_id"] not in rows
        )
        if has_official:
            station.update({
                "coordinate_method": "official_station_coordinate",
                "coordinate_provider": station.get("source_label") or station.get("source_id"),
                "coordinate_confidence": "high", "coordinate_review_status": "accepted",
                "is_exact_station_location": True, "mapped": True,
            })
            continue
        row = rows[station["station_id"]]
        accepted = row.get("review_status") == "accepted" and row.get("coordinate_confidence") in {"medium", "low"}
        latitude = float(row["latitude"]) if accepted and row.get("latitude") else None
        longitude = float(row["longitude"]) if accepted and row.get("longitude") else None
        station.update({
            "latitude": latitude, "longitude": longitude,
            "coordinate_method": "geocoded_locality",
            "coordinate_source": row.get("source_url") or None,
            "coordinate_provider": row.get("coordinate_provider") or None,
            "coordinate_confidence": row.get("coordinate_confidence") or "unresolved",
            "coordinate_review_status": row.get("review_status") or "required",
            "is_exact_station_location": False, "mapped": accepted,
        })


def sanitize_url(value: str | None) -> str | None:
    if not value:
        return value
    parts = urllib.parse.urlsplit(value)
    query = [(key, item) for key, item in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if key.casefold() not in SENSITIVE_QUERY_KEYS]
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), parts.fragment))


def capture_index(archive_root: Path | None) -> tuple[dict[str, str], dict[str, str]]:
    by_sha: dict[str, str] = {}
    by_source: dict[str, str] = {}
    if not archive_root or not archive_root.exists():
        return by_sha, by_source
    for path in sorted(archive_root.rglob("*.metadata.json")):
        metadata = read_json(path)
        sha = metadata.get("content_sha256")
        captured = metadata.get("captured_at_utc")
        source = metadata.get("source")
        if sha and captured:
            by_sha[sha] = captured
        if source and captured and captured > by_source.get(source, ""):
            by_source[source] = captured
    return by_sha, by_source


def observation_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        row.get("measurement_datetime_utc")
        or row.get("measurement_date")
        or row.get("measurement_datetime_local")
        or row.get("measurement_time_original")
        or "",
        row.get("captured_at_utc") or "",
    )


def enrich_observation(row: dict[str, Any], station: dict[str, Any], policy: dict[str, Any], captures: dict[str, str]) -> dict[str, Any]:
    result = dict(row)
    quality = result.get("canonical_quality_flag") or "observed"
    current_usable = bool(policy["current"] and quality not in {"suspect", "missing"})
    result.update({
        "country_code": station["country_code"],
        "station_name": station["station_name"],
        "station_name_local": station["station_name_local"],
        "source_id": policy["source_id"],
        "source_status": policy["status"],
        "source_url": sanitize_url(station.get("source_url")),
        "captured_at_utc": captures.get(result.get("source_file_sha256", "")),
        "current_usable": current_usable,
        "stale": not policy["current"],
    })
    return result


def enrich_forecast(row: dict[str, Any], station: dict[str, Any], policy: dict[str, Any], captures: dict[str, str]) -> dict[str, Any]:
    result = dict(row)
    result.update({
        "country_code": station["country_code"],
        "station_name": station["station_name"],
        "station_name_local": station["station_name_local"],
        "source_id": policy["source_id"],
        "source_status": policy["status"],
        "source_url": sanitize_url(station.get("source_url")),
        "captured_at_utc": captures.get(result.get("source_file_sha256", "")),
    })
    return result


def historical_quality_issues(candidate_root: Path | None, archive_root: Path | None, stations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    if not candidate_root or not candidate_root.exists():
        return []
    captures, _ = capture_index(archive_root)
    issues = read_json(candidate_root / "issues.json")
    observations = read_json(candidate_root / "observations.json")
    suspect_by_station = defaultdict(list)
    for observation in observations:
        if observation.get("parameter") == "water_temperature" and not -5 <= float(observation["value"]) <= 45:
            suspect_by_station[observation["station_id"]].append(observation)
    result = []
    for issue in issues:
        if issue.get("code") not in {"outside_plausible_water_temperature_range", "impossible_value"}:
            continue
        for observation in suspect_by_station.get(issue.get("record_id"), []):
            station = stations.get(observation["station_id"])
            if not station:
                continue
            item = dict(observation)
            item["canonical_quality_flag"] = "suspect"
            item["source_quality_code"] = "outside_plausible_water_temperature_range"
            result.append({
                "source_id": "shmu_sk", "source_status": "partial", "station_id": observation["station_id"],
                "station_name": station["station_name"], "station_name_local": station["station_name_local"],
                "severity": "warning", "code": "outside_plausible_water_temperature_range",
                "message": f"water_temperature={observation['value']} {observation['unit']}; preserved as historical quality evidence and not current",
                "captured_at_utc": captures.get(observation.get("source_file_sha256", "")),
                "historical": True, "observation": item,
            })
    return result


def build(candidate_root: Path, audit_csv: Path, archive_root: Path, output_root: Path, mirror_root: Path | None = None,
          historical_quality_root: Path | None = None, historical_archive_root: Path | None = None,
          fixtures_run_id: str | None = None, live_run_id: str | None = None,
          geocoding_registry: Path = Path("data/reference/international_station_geocoding.csv")) -> dict[str, Any]:
    captures, source_captures = capture_index(archive_root)
    aggregate = read_json(candidate_root / "summary.json")
    aggregate_by_source = {item["source"]: item for item in aggregate["sources"]}
    stations: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    forecasts: list[dict[str, Any]] = []
    quality_issues: list[dict[str, Any]] = []

    for country, policy in SOURCE_POLICY.items():
        if country == "rs":
            continue
        folder = candidate_root / country
        source_stations = read_json(folder / "stations.json")
        if len(source_stations) != EXPECTED_COUNTS[country]:
            raise ValueError(f"{country}: expected {EXPECTED_COUNTS[country]} stations, got {len(source_stations)}")
        for station in source_stations:
            item = dict(station)
            item.update({
                "source_id": policy["source_id"], "source_status": policy["status"],
                "source_label": policy["label"], "source_url": sanitize_url(station.get("source_url")),
                "capture_datetime_utc": source_captures.get(policy["source_id"]),
                "has_current_data": bool(policy["current"]),
                "mapped": station.get("latitude") is not None and station.get("longitude") is not None,
            })
            stations.append(item)
        station_lookup = {item["station_id"]: item for item in stations}
        published_source_observations = []
        if policy["observations"]:
            for row in read_json(folder / "observations.json"):
                enriched = enrich_observation(row, station_lookup[row["station_id"]], policy, captures)
                observations.append(enriched)
                published_source_observations.append(enriched)
        if policy["forecasts"]:
            for row in read_json(folder / "forecasts.json"):
                forecasts.append(enrich_forecast(row, station_lookup[row["station_id"]], policy, captures))
        for issue in read_json(folder / "issues.json"):
            public_issue = {
                **issue, "source_id": policy["source_id"], "source_status": policy["status"],
                "captured_at_utc": source_captures.get(policy["source_id"]), "historical": False,
            }
            if issue.get("code") == "outside_plausible_water_temperature_range":
                matching = [
                    row for row in published_source_observations
                    if row.get("station_id") == issue.get("record_id")
                    and row.get("parameter") == "water_temperature"
                    and row.get("canonical_quality_flag") == "suspect"
                ]
                if len(matching) != 1:
                    raise ValueError(f"{country}: suspect temperature issue must resolve to exactly one observation")
                public_issue["observation"] = matching[0]
            quality_issues.append(public_issue)

    with audit_csv.open(encoding="utf-8-sig", newline="") as stream:
        audit_rows = list(csv.DictReader(stream))
    rs_rows = [row for row in audit_rows if row["country_code"] == "RS"]
    if len(rs_rows) != EXPECTED_COUNTS["rs"]:
        raise ValueError(f"rs: expected 13 audited stations, got {len(rs_rows)}")
    for row in rs_rows:
        stations.append({
            "station_id": row["station_id"], "source_station_id": row["source_station_id"],
            "country_code": "RS", "station_name": row["station_name"], "station_name_local": row["station_name_local"],
            "station_slug": row["station_slug"], "river_name": row["river"], "river_km": None,
            "latitude": None, "longitude": None, "coordinate_source": None,
            "coordinate_method": "unavailable", "coordinate_confidence": "unavailable",
            "source_url": sanitize_url(row["source_url"]), "active": None, "last_verified_at": row["last_verified_at"],
            "operator_provider_id": "hidmet_rs", "source_provider_id": "hidmet_rs", "captured_via_provider_id": "audit_only",
            "included": False, "inclusion_reason": row["review_reason"], "station_type": row["station_type"],
            "source_id": "hidmet_rs", "source_status": "suspended", "source_label": SOURCE_POLICY["rs"]["label"],
            "capture_datetime_utc": None, "has_current_data": False, "mapped": False,
        })

    apply_coordinate_registry(stations, geocoding_registry)
    station_lookup = {station["station_id"]: station for station in stations}
    if len(station_lookup) != 101:
        raise ValueError(f"Expected 101 unique stations, got {len(station_lookup)}")
    quality_issues.extend(historical_quality_issues(historical_quality_root, historical_archive_root, station_lookup))
    for issue in quality_issues:
        station = station_lookup.get(issue.get("record_id") or issue.get("station_id"))
        if station:
            issue.setdefault("station_id", station["station_id"])
            issue.setdefault("station_name", station["station_name"])
            issue.setdefault("station_name_local", station["station_name_local"])

    latest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for observation in observations:
        if not observation["current_usable"]:
            continue
        key = (observation["station_id"], observation["parameter"])
        if key not in latest_by_key or observation_sort_key(observation) > observation_sort_key(latest_by_key[key]):
            latest_by_key[key] = observation
    latest = sorted(latest_by_key.values(), key=lambda item: (item["country_code"], item["station_id"], item["parameter"]))

    mapped = [station for station in stations if station["mapped"]]
    unmapped = [station for station in stations if not station["mapped"]]
    latest_per_station = defaultdict(dict)
    for row in latest:
        latest_per_station[row["station_id"]][row["parameter"]] = row
    features = []
    for station in mapped:
        values = latest_per_station[station["station_id"]]
        properties = {key: station.get(key) for key in (
            "station_id", "station_slug", "station_name", "station_name_local", "country_code", "river_name", "river_km",
            "station_type", "source_id", "source_label", "source_status", "source_url", "capture_datetime_utc",
            "coordinate_method", "coordinate_source", "coordinate_provider", "coordinate_confidence",
            "coordinate_review_status", "is_exact_station_location",
        )}
        for parameter in ("water_level", "discharge", "water_temperature"):
            properties[parameter] = values.get(parameter)
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [station["longitude"], station["latitude"]]}, "properties": properties})

    sources = []
    for country, policy in SOURCE_POLICY.items():
        run = aggregate_by_source.get(country, {})
        sources.append({
            "country_code": country.upper(), "source_id": policy["source_id"], "label": policy["label"],
            "status": policy["status"], "capture_datetime_utc": source_captures.get(policy["source_id"]),
            "station_count": EXPECTED_COUNTS[country], "observation_count": sum(row["source_id"] == policy["source_id"] for row in observations),
            "forecast_count": sum(row["source_id"] == policy["source_id"] for row in forecasts),
            "adapter_live_status": run.get("status", "suspended" if country == "rs" else "unavailable"),
            "note": policy.get("note"), "live_run_id": live_run_id,
        })
    status = {
        "beta": True, "contract_version": "1.1-beta", "generated_from_capture_utc": max(source_captures.values()),
        "fixtures_run_id": fixtures_run_id, "live_run_id": live_run_id,
        "station_count": len(stations), "mapped_station_count": len(mapped), "unmapped_station_count": len(unmapped),
        "official_coordinate_station_count": sum(station["is_exact_station_location"] for station in stations),
        "approximate_coordinate_station_count": sum(station["mapped"] and not station["is_exact_station_location"] for station in stations),
        "current_station_count": len({row["station_id"] for row in latest}),
        "complete_source_count": sum(source["status"] == "complete" for source in sources),
        "partial_source_count": sum(source["status"] == "partial" for source in sources),
        "suspended_source_count": sum(source["status"] == "suspended" for source in sources),
        "stale_station_count": sum(station["country_code"] == "HR" for station in stations),
        "suspended_station_count": sum(station["country_code"] in {"HR", "RS"} for station in stations),
        "observation_count": len(observations),
        "current_usable_observation_count": sum(row["current_usable"] for row in observations),
        "stale_observation_count": sum(row["stale"] for row in observations),
        "provisional_observation_count": sum(row["canonical_quality_flag"] == "provisional" for row in observations),
        "latest_valid_count": len(latest), "forecast_count": len(forecasts),
        "suspect_current_observation_count": sum(row["canonical_quality_flag"] == "suspect" for row in observations),
        "quality_issue_count": len(quality_issues),
    }

    stations.sort(key=lambda item: (item["country_code"], item["station_name"], item["station_id"]))
    observations.sort(key=lambda item: (item["country_code"], item["station_id"], item["parameter"], observation_sort_key(item)))
    forecasts.sort(key=lambda item: (item["country_code"], item["station_id"], item.get("target_datetime_utc") or item.get("target_date") or item.get("target_time_original") or ""))
    unmapped.sort(key=lambda item: (item["country_code"], item["station_name"], item["station_id"]))
    quality_issues.sort(key=lambda item: (item.get("source_id", ""), item.get("station_id") or item.get("record_id") or "", item.get("captured_at_utc") or "", item.get("code", "")))

    payloads = {
        "stations.json": stations, "observations.json": observations, "latest.json": latest,
        "forecasts.json": forecasts, "sources.json": sources, "status.json": status,
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
    args = parser.parse_args(argv)
    status = build(args.candidate_root, args.audit_csv, args.archive_root, args.output_root, args.mirror_root,
                   args.historical_quality_root, args.historical_archive_root, args.fixtures_run_id, args.live_run_id,
                   args.geocoding_registry)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
