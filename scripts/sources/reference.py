"""Versioned station-reference registries shared by international adapters."""

from __future__ import annotations

import csv
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .base import StationRecord

ROOT = Path(__file__).resolve().parents[2]
RIS_REGISTRY = ROOT / "data" / "reference" / "ris_station_registry.csv"
COORDINATE_OVERRIDES = ROOT / "data" / "reference" / "international_station_coordinate_overrides.json"


def _optional_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


@lru_cache(maxsize=1)
def ris_rows() -> tuple[dict[str, Any], ...]:
    with RIS_REGISTRY.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in (
            "waterway_km", "latitude", "longitude", "low_reference_cm",
            "high_reference_cm", "gauge_zero_cm",
        ):
            row[field] = _optional_float(row.get(field))
        row["workbook_row"] = int(row["workbook_row"])
        row["is_primary_stream"] = row["is_primary_stream"].lower() == "true"
        row["is_exact_station_location"] = row["is_exact_station_location"].lower() == "true"
    return tuple(rows)


@lru_cache(maxsize=1)
def coordinate_overrides() -> dict[str, dict[str, Any]]:
    payload = json.loads(COORDINATE_OVERRIDES.read_text(encoding="utf-8"))
    return {row["station_id"]: row for row in payload["coordinates"]}


def ris_station(station_id: str) -> dict[str, Any]:
    matches = [row for row in ris_rows() if row["station_id"] == station_id]
    if len(matches) != 1:
        raise KeyError(f"Expected one RIS registry row for {station_id!r}, found {len(matches)}")
    return matches[0]


def ris_country(country_code: str) -> list[dict[str, Any]]:
    return [row for row in ris_rows() if row["country_code"] == country_code]


def apply_coordinate_override(station: StationRecord) -> StationRecord:
    row = coordinate_overrides().get(station.station_id) or coordinate_overrides().get(station.physical_station_id or "")
    if row is None:
        return station
    station.latitude = float(row["latitude"])
    station.longitude = float(row["longitude"])
    station.coordinate_method = row["coordinate_method"]
    station.coordinate_source = row["coordinate_source"]
    station.coordinate_provider = row["coordinate_provider"]
    station.coordinate_confidence = row["coordinate_confidence"]
    station.coordinate_review_status = row["coordinate_review_status"]
    station.is_exact_station_location = bool(row["is_exact_station_location"])
    station.coordinate_verified_at = row["coordinate_verified_at"]
    station.coordinate_notes = row.get("coordinate_notes")
    station.source_coordinate_raw = row.get("source_coordinate_raw")
    station.source_crs = row.get("source_crs")
    station.aliases = list(row.get("aliases") or [])
    station.official_station_number = row.get("official_station_number")
    station.measuring_point_uid = row.get("measuring_point_uid")
    station.pnp_value_m = row.get("pnp_value_m")
    station.pnp_datum = row.get("pnp_datum")
    station.pnp_valid_from = row.get("pnp_valid_from")
    if row.get("river_km") is not None:
        station.river_km = float(row["river_km"])
    if row.get("station_name"):
        station.station_name = row["station_name"]
        station.station_name_local = row["station_name"]
    return station


def apply_ris_reference(station: StationRecord) -> StationRecord:
    row = ris_station(station.station_id)
    station.source_station_id = row["source_station_id"]
    station.physical_station_id = row["physical_station_id"]
    station.source_stream_id = row["source_stream_id"]
    station.source_stream_type = row["source_stream_type"]
    station.is_primary_stream = row["is_primary_stream"]
    station.isrs_location_code = row["isrs_location_code"]
    station.latitude = row["latitude"]
    station.longitude = row["longitude"]
    station.river_km = row["waterway_km"]
    station.coordinate_method = row["coordinate_method"]
    station.coordinate_source = row["coordinate_source"]
    station.coordinate_provider = row["coordinate_provider"]
    station.coordinate_confidence = row["coordinate_confidence"]
    station.coordinate_review_status = row["coordinate_review_status"]
    station.is_exact_station_location = row["is_exact_station_location"]
    station.coordinate_verified_at = row["coordinate_verified_at"]
    station.coordinate_notes = row["provenance_note"]
    station.source_coordinate_raw = row["source_coordinate_raw"]
    station.source_crs = row["source_crs"]
    return station
