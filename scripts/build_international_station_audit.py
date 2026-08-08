"""Build the implementation station audit from the reviewed discovery inventory."""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date
from pathlib import Path

from scripts.sources.base import canonical_station_name, station_slug
from scripts.build_international_public_data import EXPECTED_COUNTS, apply_coordinate_registry

SOURCE_RULES = {
    "pegelonline_de": {
        "country": "de", "implementation_status": "complete", "latest_live_status": "complete",
        "observation_quality_summary": "validated candidate observations",
    },
    "viadonau_at": {
        "country": "at", "implementation_status": "complete", "latest_live_status": "partial",
        "observation_quality_summary": "observations valid; public test key prevents production readiness",
    },
    "shmu_sk": {
        "country": "sk", "implementation_status": "complete", "latest_live_status": "partial",
        "observation_quality_summary": "source-provided provisional quality is retained; official values are not reclassified by application plausibility thresholds",
    },
    "hydroinfo_hu": {
        "country": "hu", "implementation_status": "complete", "latest_live_status": "complete",
        "observation_quality_summary": "validated candidate observations",
    },
    "vodniputovi_hr": {
        "country": "hr", "implementation_status": "complete", "latest_live_status": "partial",
        "observation_quality_summary": "historical observations retained; latest feed is stale",
    },
    "appd_bg": {
        "country": "bg", "implementation_status": "complete", "latest_live_status": "partial",
        "observation_quality_summary": "RIS-identified manual and automatic streams retained; forecast semantics remain inactive",
    },
    "hidmet_rs": {
        "country": "rs", "implementation_status": "complete", "latest_live_status": "complete",
        "observation_quality_summary": "official daily values and source-declared provisional NRT values retained without reinterpretation",
    },
}

FIELDS = [
    "adapter", "implementation_status", "latest_live_status", "observation_quality_summary",
    "station_id", "source_station_id", "country_code", "station_name", "station_name_local",
    "station_slug", "river", "river_km", "latitude", "longitude", "coordinate_source",
    "coordinate_method", "coordinate_confidence", "source_url", "active", "last_verified_at",
    "station_type", "physical_station_id", "isrs_location_code", "source_stream_id", "source_stream_type", "is_primary_stream", "observation_frequency",
    "coordinate_provider", "coordinate_review_status", "is_exact_station_location", "coordinate_verified_at", "coordinate_notes",
    "source_coordinate_raw", "source_crs", "mapped", "workbook_filename", "workbook_sheet", "workbook_row", "workbook_version", "workbook_sha256",
    "included", "review_required", "review_reason",
]


def audit_date_from_metadata(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(r"Data auditului:\s*(\d{4}-\d{2}-\d{2})", text)
    if not match:
        raise ValueError(f"Audit date not found in {path}")
    return date.fromisoformat(match.group(1)).isoformat()


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


def transform(source, rule, row, verified_at):
    country = row["country_code"].upper()
    local = row["station_name_original"]
    canonical = row["station_name_ascii"].strip() or canonical_station_name(local)
    canonical = canonical_station_name(canonical)
    qualifier = None
    station_type = row["station_type"] or "gauge"
    if source == "appd_bg":
        qualifier = "automatic" if station_type == "automated" else "manual"
        application_id = station_slug(country, canonical, qualifier)
        source_id = ""
    else:
        source_id = row["source_station_uuid"] if source == "pegelonline_de" else row["source_station_id"]
        application_id = f"{country.lower()}-{source_id.lower()}"
    latitude, longitude = row["latitude"], row["longitude"]
    has_coordinates = bool(latitude and longitude)
    included = bool(rule.get("included", True))
    review_reasons = []
    if not source_id:
        review_reasons.append("official stable station identifier unavailable")
    if not has_coordinates:
        review_reasons.append("official WGS84 coordinates unavailable")
    if rule["latest_live_status"] != "complete":
        review_reasons.append(f"latest live status {rule['latest_live_status']}")
    coordinate_source = row["metadata_url"] if source == "pegelonline_de" else row["source_url"]
    return {
        "adapter": source,
        "implementation_status": rule["implementation_status"],
        "latest_live_status": rule["latest_live_status"],
        "observation_quality_summary": rule["observation_quality_summary"],
        "station_id": application_id,
        "source_station_id": source_id,
        "country_code": country,
        "station_name": canonical,
        "station_name_local": local,
        "station_slug": station_slug(country, canonical, qualifier),
        "river": "Danube",
        "river_km": row["river_km"],
        "latitude": latitude,
        "longitude": longitude,
        "coordinate_source": coordinate_source if has_coordinates else "",
        "coordinate_method": "official_rest_payload" if has_coordinates else "unavailable",
        "coordinate_confidence": "high" if has_coordinates else "unavailable",
        "source_url": row["source_url"],
        "active": row["active"],
        "last_verified_at": verified_at,
        "station_type": station_type,
        "physical_station_id": application_id,
        "source_stream_id": (f"{source_id}:daily" if source == "hidmet_rs" and source_id == "42040" else (f"{source_id}:nrt" if source == "hidmet_rs" else source_id)),
        "source_stream_type": ("daily" if source == "hidmet_rs" and source_id == "42040" else ("nrt" if source == "hidmet_rs" else "observed")),
        "is_primary_stream": True,
        "observation_frequency": ("daily after the official 10:00 local update" if source == "hidmet_rs" and source_id == "42040" else ("variable" if source == "hidmet_rs" else "")),
        "included": "yes" if included else "no",
        "review_required": "yes" if review_reasons or not included else "no",
        "review_reason": "; ".join(review_reasons),
    }


def build(
    input_path: Path,
    output_path: Path,
    verified_at: str | None = None,
    audit_metadata_path: Path = Path("docs/DANUBE_SOURCE_TECHNICAL_AUDIT.md"),
) -> list[dict[str, str]]:
    verified_at = date.fromisoformat(
        verified_at or audit_date_from_metadata(audit_metadata_path)
    ).isoformat()
    with input_path.open(encoding="utf-8-sig", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows = [transform(*item, verified_at) for item in select(source_rows)]
    apply_coordinate_registry(rows, Path("data/reference/international_station_geocoding.csv"))
    for row in rows:
        reasons = [reason for reason in row["review_reason"].split("; ") if reason and reason not in {"official stable station identifier unavailable", "official WGS84 coordinates unavailable"}]
        if not row.get("source_station_id"):
            reasons.insert(0, "official stable station identifier unavailable")
        if not row.get("latitude") or not row.get("longitude"):
            reasons.append("verified coordinates unavailable")
        row["review_reason"] = "; ".join(dict.fromkeys(reasons))
        row["review_required"] = "yes" if reasons or row["included"] == "no" else "no"
    rows.sort(key=lambda row: (row["country_code"], row["adapter"], row["station_slug"]))
    active_count = sum(row["included"] == "yes" for row in rows)
    suspended_count = sum(row["implementation_status"] == "suspended" for row in rows)
    expected_total = sum(EXPECTED_COUNTS.values())
    if (len(rows), active_count, suspended_count) != (expected_total, expected_total, 0):
        raise ValueError(
            f"Expected {expected_total} audited rows: {expected_total} active candidates and none suspended; "
            f"got total={len(rows)}, active={active_count}, suspended={suspended_count}"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("docs/DANUBE_STATION_INVENTORY.csv"))
    parser.add_argument("--output", type=Path, default=Path("docs/INTERNATIONAL_STATIONS_AUDIT.csv"))
    parser.add_argument("--verified-at", help="Explicit ISO date; otherwise read from --audit-metadata")
    parser.add_argument(
        "--audit-metadata", type=Path,
        default=Path("docs/DANUBE_SOURCE_TECHNICAL_AUDIT.md"),
    )
    args = parser.parse_args(argv)
    rows = build(args.input, args.output, args.verified_at, args.audit_metadata)
    active = sum(row["included"] == "yes" for row in rows)
    suspended = sum(row["implementation_status"] == "suspended" for row in rows)
    coordinates = sum(bool(row["latitude"] and row["longitude"]) for row in rows)
    print(
        f"Wrote {len(rows)} audited rows to {args.output}: "
        f"active_candidates={active}, suspended={suspended}, coordinates={coordinates}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())