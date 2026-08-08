#!/usr/bin/env python3
"""Controlled, resumable locality geocoding for international Danube stations.

Live access is always explicit (``--live``). Builds and tests only consume the
versioned cache/registry and never contact a geocoder.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


PROVIDER = "OpenStreetMap Nominatim"
PROVIDER_URL = "https://nominatim.openstreetmap.org/search"
CACHE_VERSION = 1
USER_AGENT = "NivelDunareInternationalGeocoder/1.0 (+https://github.com/mariusbudileanu/nivel-dunare)"
COUNTRY_NAMES = {"DE": "Germany", "SK": "Slovakia", "HU": "Hungary", "HR": "Croatia", "BG": "Bulgaria", "RS": "Serbia"}
COUNTRY_BOUNDS = {
    "DE": (47.2, 55.2, 5.5, 15.6), "AT": (46.2, 49.1, 9.3, 17.2), "SK": (47.7, 49.7, 16.7, 22.7),
    "HU": (45.7, 48.7, 16.0, 23.0), "HR": (42.3, 46.7, 13.3, 19.6),
    "BG": (41.2, 44.3, 22.3, 28.7), "RS": (42.1, 46.3, 18.7, 23.1),
}
# Conservative envelopes used only to reject obviously unrelated localities.
# They are not river geometry and must never be used for distance calculations.
DANUBE_SECTOR_BOUNDS = {
    "DE": (47.7, 49.3, 8.0, 13.9), "SK": (47.7, 48.6, 16.7, 18.9),
    "HU": (45.6, 48.3, 16.7, 19.4), "HR": (45.1, 46.1, 18.4, 19.5),
    "BG": (43.4, 44.3, 22.4, 28.2), "RS": (44.0, 46.3, 18.6, 22.9),
}
LOCALITY_TYPES = {"city", "town", "village", "municipality", "hamlet", "suburb", "quarter", "neighbourhood", "locality", "isolated_dwelling"}
QUERY_LOCALITY_OVERRIDES = {
    # Query-only locality clarifications. Canonical IDs/names remain unchanged.
    "bg-kozloduj-automatic": "Kozloduy",
    "bg-novo-selo-automatic": "Novo Selo, Vidin",
    "bg-novo-selo-manual": "Novo Selo, Vidin",
    "de-560cf185-0052-4e40-832b-7792b52dd343": "Kachlet, Passau",
    "hr-5170": "Batina, Osijek-Baranja County",
    "hu-442708": "Doborgaz, Gyor-Moson-Sopron",
    "sk-6870": "Radvan nad Dunajom",
}
TECHNICAL_SUFFIXES = (
    r"\s*[-–—]\s*(?:horn[aá]\s+hladina|horna\s+hladina|upper\s+level|lower\s+level|upstream|downstream)\s*$",
    r"\s+(?:wehr\s+up|wehr\s+down|gauge|hydrometric\s+station|automatic|manual)\s*$",
)
FIELDS = (
    "station_id", "country_code", "station_name", "station_name_local", "geocoding_query",
    "latitude", "longitude", "coordinate_method", "coordinate_source", "coordinate_provider",
    "geocoder_result_label", "geocoder_result_type", "coordinate_confidence", "review_status",
    "review_notes", "geocoded_at", "source_url",
)


def normalize_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def locality_name(station: dict[str, Any]) -> str:
    if station.get("station_id") in QUERY_LOCALITY_OVERRIDES:
        return QUERY_LOCALITY_OVERRIDES[station["station_id"]]
    local = (station.get("station_name_local") or "").strip()
    # Nominatim result language is English; reuse the audited canonical Latin
    # spelling for a Cyrillic-only official label while preserving both names.
    value = local if local and normalize_name(local) else (station.get("station_name") or local).strip()
    for pattern in TECHNICAL_SUFFIXES:
        value = re.sub(pattern, "", value, flags=re.I).strip()
    return value


def build_query(station: dict[str, Any]) -> str:
    country = station["country_code"].upper()
    return f"{locality_name(station)}, {COUNTRY_NAMES[country]}"


def query_key(query: str, country: str) -> str:
    return f"{country.casefold()}|{normalize_name(query)}"


def inside(bounds: tuple[float, float, float, float], lat: float, lon: float) -> bool:
    return bounds[0] <= lat <= bounds[1] and bounds[2] <= lon <= bounds[3]


def result_names(result: dict[str, Any]) -> list[str]:
    namedetails = result.get("namedetails") or {}
    values = [str(result.get("name") or ""), str(result.get("display_name") or "").split(",", 1)[0]]
    values.extend(str(value) for key, value in namedetails.items() if key == "name" or key.startswith("name:"))
    return [value for value in values if value]


def name_score(expected: str, result: dict[str, Any]) -> float:
    target = normalize_name(expected)
    scores = []
    for value in result_names(result):
        candidate = normalize_name(value)
        if not candidate:
            continue
        scores.append(1.0 if candidate == target else SequenceMatcher(None, target, candidate).ratio())
    return max(scores, default=0.0)


def classify_results(station: dict[str, Any], results: list[dict[str, Any]], geocoded_at: str, source_url: str) -> dict[str, str]:
    country = station["country_code"].upper()
    expected = locality_name(station)
    candidates: list[tuple[float, int, dict[str, Any], list[str]]] = []
    rejected: list[str] = []
    for result in results:
        reasons: list[str] = []
        try:
            lat, lon = float(result["lat"]), float(result["lon"])
        except (KeyError, TypeError, ValueError):
            rejected.append("non_finite_coordinates")
            continue
        if not math.isfinite(lat) or not math.isfinite(lon): reasons.append("non_finite_coordinates")
        result_country = str((result.get("address") or {}).get("country_code") or "").upper()
        if result_country != country: reasons.append("wrong_country")
        if not inside(COUNTRY_BOUNDS[country], lat, lon): reasons.append("outside_country_bounds")
        if not inside(DANUBE_SECTOR_BOUNDS[country], lat, lon): reasons.append("outside_danube_sector_envelope")
        result_type = str(result.get("addresstype") or result.get("type") or "").casefold()
        if result_type not in LOCALITY_TYPES: reasons.append("not_a_locality")
        score = name_score(expected, result)
        if score < 0.72: reasons.append("insufficient_name_match")
        if reasons:
            rejected.extend(reasons)
        else:
            # Prefer an inhabited-place object over an administrative boundary
            # with the same name; this avoids choosing a municipality centroid.
            place_priority = 1 if str(result.get("category") or "").casefold() == "place" else 0
            candidates.append((score, place_priority, result, reasons))
    base = {
        "station_id": station["station_id"], "country_code": country,
        "station_name": station.get("station_name") or "", "station_name_local": station.get("station_name_local") or "",
        "geocoding_query": build_query(station), "latitude": "", "longitude": "",
        "coordinate_method": "geocoded_locality", "coordinate_source": "OpenStreetMap locality result via Nominatim",
        "coordinate_provider": PROVIDER, "geocoder_result_label": "", "geocoder_result_type": "",
        "coordinate_confidence": "unresolved", "review_status": "required",
        "review_notes": "", "geocoded_at": geocoded_at, "source_url": source_url,
    }
    if not candidates:
        base["review_notes"] = "unresolved: " + (",".join(sorted(set(rejected))) if rejected else "no_result")
        return base
    candidates.sort(key=lambda item: (-item[1], -item[0], -float(item[2].get("importance") or 0), int(item[2].get("place_id") or 0)))
    best_score, best_priority, best, _ = candidates[0]
    distinct = {(round(float(item[2]["lat"]), 5), round(float(item[2]["lon"]), 5)) for item in candidates if item[1] == best_priority and item[0] >= best_score - 0.03}
    if len(distinct) > 1:
        base["coordinate_confidence"] = "low"
        base["review_notes"] = f"ambiguous: {len(distinct)} similarly named locality results"
        return base
    base.update({
        "latitude": str(float(best["lat"])), "longitude": str(float(best["lon"])),
        "geocoder_result_label": str(best.get("display_name") or ""),
        "geocoder_result_type": str(best.get("addresstype") or best.get("type") or ""),
        "coordinate_confidence": "medium" if best_score >= 0.9 else "low",
        "review_status": "accepted" if best_score >= 0.9 else "required",
        "review_notes": f"name_match={best_score:.3f}; country and conservative Danube-sector checks passed",
    })
    return base


def read_registry(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return {row["station_id"]: row for row in csv.DictReader(stream)}


def write_registry(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in FIELDS} for row in rows)


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"cache_version": CACHE_VERSION, "provider": PROVIDER, "queries": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("cache_version") != CACHE_VERSION or data.get("provider") != PROVIDER:
        raise ValueError("Unsupported geocoding cache version/provider")
    return data


def write_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_registry(stations_path: Path, registry_path: Path, cache_path: Path) -> dict[str, Any]:
    """Validate the immutable locality registry without overriding higher-priority coordinates."""
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    stations_by_id = {row["station_id"]: row for row in stations}
    rows = read_registry(registry_path)
    if len(rows) != 76 or not set(rows) <= set(stations_by_id):
        raise ValueError("Geocoding registry must contain 76 known legacy locality targets")
    cache = load_cache(cache_path)
    accepted = 0
    coordinate_groups: dict[tuple[float, float], list[dict[str, str]]] = {}
    for station_id, row in rows.items():
        country = row.get("country_code", "").upper()
        if country not in COUNTRY_NAMES or country != stations_by_id[station_id]["country_code"]:
            raise ValueError(f"{station_id}: invalid country_code")
        if row.get("coordinate_method") != "geocoded_locality" or row.get("coordinate_provider") != PROVIDER:
            raise ValueError(f"{station_id}: incomplete coordinate method/provider")
        if not row.get("geocoding_query") or query_key(row["geocoding_query"], country) not in cache["queries"]:
            raise ValueError(f"{station_id}: query missing from versioned cache")
        if row.get("review_status") not in {"accepted", "required", "rejected"}:
            raise ValueError(f"{station_id}: invalid review_status")
        confidence = row.get("coordinate_confidence")
        has_latitude, has_longitude = bool(row.get("latitude")), bool(row.get("longitude"))
        if has_latitude != has_longitude:
            raise ValueError(f"{station_id}: partial coordinate pair")
        latitude = longitude = None
        if has_latitude:
            latitude, longitude = float(row["latitude"]), float(row["longitude"])
            if not math.isfinite(latitude) or not math.isfinite(longitude) or not inside(COUNTRY_BOUNDS[country], latitude, longitude) or not inside(DANUBE_SECTOR_BOUNDS[country], latitude, longitude):
                raise ValueError(f"{station_id}: coordinate outside validation bounds")
            if not all(row.get(key) for key in ("coordinate_source", "geocoder_result_label", "geocoder_result_type", "geocoded_at", "source_url")):
                raise ValueError(f"{station_id}: coordinate provenance incomplete")
        if row["review_status"] == "accepted":
            if confidence not in {"medium", "low"} or latitude is None or longitude is None:
                raise ValueError(f"{station_id}: accepted result lacks coordinates/confidence")
            coordinate_groups.setdefault((latitude, longitude), []).append(row)
            accepted += 1
        elif confidence == "unresolved" and has_latitude:
            raise ValueError(f"{station_id}: unresolved result must not expose coordinates")
    for group in coordinate_groups.values():
        if len(group) > 1 and len({normalize_name(row["station_name"]) for row in group}) != 1:
            raise ValueError("Duplicate accepted coordinates across different locality names")
    active_locality_ids = {row["station_id"] for row in stations if row.get("coordinate_method") == "geocoded_locality"}
    if active_locality_ids != {station_id for station_id, row in rows.items() if row.get("review_status") == "accepted" and station_id in active_locality_ids}:
        raise ValueError("An active locality coordinate is absent from the accepted registry")
    return {
        "ok": True, "stations": len(rows), "active_locality_coordinates": len(active_locality_ids),
        "accepted": accepted, "medium": sum(row["coordinate_confidence"] == "medium" for row in rows.values()),
        "low": sum(row["coordinate_confidence"] == "low" for row in rows.values()),
        "unresolved": sum(row["coordinate_confidence"] == "unresolved" for row in rows.values()),
        "review_required": sum(row["review_status"] == "required" for row in rows.values()),
        "cache_queries": len(cache["queries"]),
    }


def request_results(query: str, country: str, timeout: float) -> tuple[list[dict[str, Any]], str]:
    params = urllib.parse.urlencode({
        "q": query, "countrycodes": country.casefold(), "format": "jsonv2", "addressdetails": 1,
        "namedetails": 1, "limit": 5, "dedupe": 1, "accept-language": "en",
    })
    url = f"{PROVIDER_URL}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8")), url


def run(stations_path: Path, registry_path: Path, cache_path: Path, *, live: bool = False,
        throttle_seconds: float = 1.1, timeout: float = 30.0, overwrite_reviewed: bool = False,
        limit: int | None = None) -> dict[str, Any]:
    stations = json.loads(stations_path.read_text(encoding="utf-8"))
    targets = [row for row in stations if row.get("is_exact_station_location") is False or ("is_exact_station_location" not in row and not row.get("mapped"))]
    if limit is not None:
        targets = targets[:limit]
    cache = load_cache(cache_path)
    existing = read_registry(registry_path)
    requested = 0
    last_request_at = 0.0
    for station in targets:
        query = build_query(station)
        key = query_key(query, station["country_code"])
        if key in cache["queries"] or not live:
            continue
        wait = throttle_seconds - (time.monotonic() - last_request_at)
        if wait > 0:
            time.sleep(wait)
        results, url = request_results(query, station["country_code"], timeout)
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        cache["queries"][key] = {"query": query, "country_code": station["country_code"], "requested_at_utc": now, "request_url": url, "results": results}
        write_cache(cache_path, cache)
        requested += 1
        last_request_at = time.monotonic()
    rows: list[dict[str, str]] = []
    target_ids = set()
    for station in targets:
        target_ids.add(station["station_id"])
        prior = existing.get(station["station_id"])
        if prior and prior.get("review_status") in {"accepted", "rejected"} and not overwrite_reviewed:
            rows.append(prior)
            continue
        query = build_query(station)
        entry = cache["queries"].get(query_key(query, station["country_code"]))
        if entry:
            rows.append(classify_results(station, entry.get("results", []), entry.get("requested_at_utc", ""), entry.get("request_url", "")))
        else:
            rows.append(classify_results(station, [], "", ""))
    # The registry is immutable history: a station that was geocoded here and later
    # upgraded to an official/RIS/manual coordinate drops out of `targets`, but its
    # row must stay - validate_registry() enforces a fixed row count for exactly
    # this reason.
    for station_id, prior in existing.items():
        if station_id not in target_ids:
            rows.append(prior)
    rows.sort(key=lambda row: (row["country_code"], row["station_name"], row["station_id"]))
    write_registry(registry_path, rows)
    report = {
        "target_station_count": len(targets), "unique_query_count": len({query_key(build_query(row), row["country_code"]) for row in targets}),
        "requests_made": requested, "requests_made_this_run": requested, "cache_query_count": len(cache["queries"]),
        "accepted": sum(row["review_status"] == "accepted" for row in rows),
        "medium": sum(row["coordinate_confidence"] == "medium" for row in rows),
        "low": sum(row["coordinate_confidence"] == "low" for row in rows),
        "unresolved": sum(row["coordinate_confidence"] == "unresolved" for row in rows),
        "review_required": sum(row["review_status"] == "required" for row in rows),
        "ambiguous_station_ids": [row["station_id"] for row in rows if row["review_notes"].startswith("ambiguous:")],
        "review_required_station_ids": [row["station_id"] for row in rows if row["review_status"] == "required"],
        "provider": PROVIDER, "cache": str(cache_path), "registry": str(registry_path),
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stations", type=Path, default=Path("data/public/international/stations.json"))
    parser.add_argument("--registry", type=Path, default=Path("data/reference/international_station_geocoding.csv"))
    parser.add_argument("--cache", type=Path, default=Path("data/reference/international_station_geocoding_cache-v1.json"))
    parser.add_argument("--live", action="store_true", help="Explicitly allow one-time network requests")
    parser.add_argument("--throttle-seconds", type=float, default=1.1)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--overwrite-reviewed", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.throttle_seconds < 1.0:
        parser.error("--throttle-seconds must be at least 1.0 for the public Nominatim service")
    report = validate_registry(args.stations, args.registry, args.cache) if args.validate_only else run(
        args.stations, args.registry, args.cache, live=args.live, throttle_seconds=args.throttle_seconds,
        timeout=args.timeout, overwrite_reviewed=args.overwrite_reviewed, limit=args.limit,
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
