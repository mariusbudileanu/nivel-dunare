"""Build the implementation station audit from the reviewed discovery inventory."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from scripts.sources.base import canonical_station_name, station_slug

SOURCE_RULES = {
    "pegelonline_de": {"country": "de", "status": "complete"},
    "viadonau_at": {"country": "at", "status": "partial"},
    "shmu_sk": {"country": "sk", "status": "complete"},
    "hydroinfo_hu": {"country": "hu", "status": "complete"},
    "vodniputovi_hr": {"country": "hr", "status": "suspended"},
    "appd_bg": {"country": "bg", "status": "partial"},
}

FIELDS = [
    "adapter", "implementation_status", "station_id", "source_station_id", "country_code",
    "station_name", "station_name_local", "station_slug", "river", "river_km", "latitude",
    "longitude", "coordinate_source", "coordinate_method", "coordinate_confidence",
    "source_url", "active", "last_verified_at", "station_type", "included",
    "review_required", "review_reason",
]


def select(rows):
    for source, rule in SOURCE_RULES.items():
        for row in rows:
            if row["provider_id"] != source or row["country_code"].lower() != rule["country"]:
                continue
            if source == "viadonau_at" and row["station_name_ascii"].casefold() == "schwedenbrucke":
                continue
            if source == "appd_bg" and row["station_type"] == "historical_document_index":
                continue
            yield source, rule, row


def transform(source, rule, row):
    country = row["country_code"].upper()
    local = row["station_name_original"]
    qualifier = None
    station_type = row["station_type"] or "gauge"
    if source == "appd_bg":
        qualifier = "automatic" if station_type == "automated" else "manual"
        application_id = station_slug(country, local, qualifier)
        source_id = ""
    else:
        source_id = row["source_station_uuid"] if source == "pegelonline_de" else row["source_station_id"]
        application_id = f"{country.lower()}-{source_id.lower()}"
    latitude, longitude = row["latitude"], row["longitude"]
    has_coordinates = bool(latitude and longitude)
    review_reasons = []
    if not source_id:
        review_reasons.append("official stable station identifier unavailable")
    if not has_coordinates:
        review_reasons.append("official WGS84 coordinates unavailable")
    if rule["status"] != "complete":
        review_reasons.append(f"adapter status {rule['status']}")
    coordinate_source = row["metadata_url"] if source == "pegelonline_de" else row["source_url"]
    return {
        "adapter": source, "implementation_status": rule["status"],
        "station_id": application_id, "source_station_id": source_id,
        "country_code": country, "station_name": canonical_station_name(local),
        "station_name_local": local, "station_slug": station_slug(country, local, qualifier),
        "river": "Danube", "river_km": row["river_km"], "latitude": latitude,
        "longitude": longitude, "coordinate_source": coordinate_source if has_coordinates else "",
        "coordinate_method": "official_rest_payload" if has_coordinates else "unavailable",
        "coordinate_confidence": "high" if has_coordinates else "unavailable",
        "source_url": row["source_url"], "active": row["active"],
        "last_verified_at": "2026-08-04", "station_type": station_type, "included": "yes",
        "review_required": "yes" if review_reasons else "no",
        "review_reason": "; ".join(review_reasons),
    }


def build(input_path: Path, output_path: Path) -> list[dict[str, str]]:
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = [transform(*item) for item in select(source_rows)]
    rows.sort(key=lambda row: (row["country_code"], row["adapter"], row["station_slug"]))
    if len(rows) != 88:
        raise ValueError(f"Expected 88 implemented primary station rows, got {len(rows)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("docs/DANUBE_STATION_INVENTORY.csv"))
    parser.add_argument("--output", type=Path, default=Path("docs/INTERNATIONAL_STATIONS_AUDIT.csv"))
    args = parser.parse_args(argv)
    rows = build(args.input, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
