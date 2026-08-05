"""viadonau DoRIS gauge list/status adapter."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .base import (
    AdapterResult, ForecastRecord, ObservationRecord, SourceAdapter, SourceRequest,
    SourceStructureError, StationRecord, ValidationIssue, canonical_station_name,
    iso_from_milliseconds, json_load, parse_optional_float, station_slug,
)


class ViaDonauAdapter(SourceAdapter):
    source_id = "viadonau_at"
    provider_id = "viadonau_at"
    country_code = "AT"
    expected_min_stations = 9
    stale_after_days = 2
    base_url = "https://opendata2.doris-info.at/doris/api/1.0/gauge"

    def __init__(self, partner_key: str | None = None) -> None:
        self.partner_key = partner_key or os.environ.get("DORIS_PARTNER_KEY") or "opendata"

    def initial_requests(self) -> list[SourceRequest]:
        suffix = f"?VIADONAU_PARTNER_KEY={self.partner_key}"
        return [
            SourceRequest("gauge-list", f"{self.base_url}/list{suffix}", "json", "application/json"),
            SourceRequest("gauge-status", f"{self.base_url}/getStatus{suffix}", "json", "application/json"),
        ]

    def parse(self, payloads):
        list_payload = payloads["gauge-list"]
        status_payload = payloads["gauge-status"]
        listing = json_load(list_payload)
        statuses = json_load(status_payload)
        gauges = listing.get("gaugeList") if isinstance(listing, dict) else None
        status_list = statuses.get("gaugeStatusList") if isinstance(statuses, dict) else None
        if not isinstance(gauges, list) or not isinstance(status_list, list):
            raise SourceStructureError("DoRIS lost gaugeList/gaugeStatusList")

        by_id = {}
        for entry in status_list:
            current = entry.get("currentMeasure") or {}
            if current.get("objectID"):
                by_id[str(current["objectID"])] = entry

        stations: list[StationRecord] = []
        observations: list[ObservationRecord] = []
        forecasts: list[ForecastRecord] = []
        excluded = 0
        verified = status_payload.captured_at_utc[:10]
        vienna = ZoneInfo("Europe/Vienna")
        source_url = f"{self.base_url}/list"

        for gauge in gauges:
            object_id = str(gauge.get("objectID") or "")
            name = str(gauge.get("objectName") or "").strip()
            if not object_id or not name:
                raise SourceStructureError("DoRIS gauge lost objectID/objectName")
            if name.casefold() == "schwedenbrücke".casefold():
                excluded += 1
                continue
            sid = f"at-{object_id.lower()}"
            latitude = parse_optional_float(gauge.get("latitude"))
            longitude = parse_optional_float(gauge.get("longitude"))
            stations.append(StationRecord(
                station_id=sid, source_station_id=object_id, country_code="AT",
                station_name=canonical_station_name(name), station_name_local=name,
                station_slug=station_slug("AT", name), river_name="Danube",
                latitude=latitude, longitude=longitude,
                coordinate_source=source_url if latitude is not None else None,
                coordinate_method="official_station_coordinate" if latitude is not None else "unresolved",
                coordinate_confidence="high" if latitude is not None else "unavailable",
                source_url=source_url, active=True, last_verified_at=verified,
                operator_provider_id="viadonau_at", source_provider_id="viadonau_at",
                captured_via_provider_id="viadonau_at", river_km=parse_optional_float(gauge.get("riverKm")),
                inclusion_reason="DoRIS Danube gauge; Schwedenbrücke/Donaukanal excluded explicitly",
                physical_station_id=sid, source_stream_id=f"{object_id}:automatic",
                source_stream_type="automatic", is_primary_stream=True,
                observation_frequency="source status cadence",
                coordinate_provider="viadonau DoRIS" if latitude is not None else None,
                coordinate_review_status="accepted" if latitude is not None else "unresolved",
                is_exact_station_location=latitude is not None,
                coordinate_verified_at=verified if latitude is not None else None,
                source_coordinate_raw=(f"{latitude}|{longitude}" if latitude is not None else None),
                source_crs="EPSG:4326" if latitude is not None else None,
            ))
            status = by_id.get(object_id)
            if not status:
                continue
            current = status.get("currentMeasure") or {}
            millis = current.get("measureDate")
            if current.get("value") is not None and millis is not None:
                utc_iso = iso_from_milliseconds(millis)
                local_iso = datetime.fromtimestamp(float(millis) / 1000, timezone.utc).astimezone(vienna).isoformat()
                observations.append(ObservationRecord(
                    station_id=sid, source_station_id=object_id,
                    operator_provider_id="viadonau_at", source_provider_id="viadonau_at",
                    captured_via_provider_id="viadonau_at", parameter="water_level",
                    value=float(current["value"]), unit="cm",
                    measurement_time_original=str(millis), measurement_timezone="Europe/Vienna",
                    measurement_datetime_local=local_iso, measurement_datetime_utc=utc_iso,
                    measurement_date=None, source_file_sha256=status_payload.sha256,
                    variation_value=parse_optional_float(current.get("difference")),
                    variation_window_hours=24,
                ))
            for raw in status.get("forecast") or []:
                if not isinstance(raw, list) or len(raw) != 4:
                    raise SourceStructureError(f"DoRIS forecast shape changed for {object_id}")
                target, central, minimum, maximum = raw
                forecasts.append(ForecastRecord(
                    station_id=sid, source_station_id=object_id,
                    operator_provider_id="viadonau_at", source_provider_id="viadonau_at",
                    captured_via_provider_id="viadonau_at", forecast_parameter="water_level",
                    forecast_value=float(central), forecast_unit="cm",
                    forecast_issue_time_original=str(statuses.get("lastUpdated") or "") or None,
                    forecast_issue_datetime_utc=None,
                    target_time_original=str(target), target_datetime_utc=iso_from_milliseconds(target),
                    target_date=None, lead_hours=None, source_file_sha256=status_payload.sha256,
                    forecast_min_value=float(minimum), forecast_max_value=float(maximum),
                ))

        issues: list[ValidationIssue] = []
        status = "complete"
        if self.partner_key == "opendata":
            status = "partial"
            issues.append(ValidationIssue(
                "warning", "test_partner_key",
                "The public opendata key is for testing; production requires a permanent partner key.",
            ))
        result = AdapterResult(
            source_id=self.source_id, country_code=self.country_code, status=status,
            stations=stations, observations=observations, forecasts=forecasts, issues=issues,
            source_station_count=len(gauges), excluded_station_count=excluded,
            notes=["Schwedenbrücke is excluded because it is on Donaukanal, not the main Danube."],
        )
        return self.validate(result, self.capture_time(payloads))
