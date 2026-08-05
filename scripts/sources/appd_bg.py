"""Bulgarian APPD HTML adapter with explicit identifier limitations."""

from __future__ import annotations

import re
from .base import (
    AdapterResult, ForecastRecord, ObservationRecord, SourceAdapter, SourceRequest,
    SourceStructureError, StationRecord, ValidationIssue, canonical_station_name,
    html_tables, parse_optional_float, payload_text, station_slug,
)
from .reference import apply_ris_reference


class AppdAdapter(SourceAdapter):
    source_id = "appd_bg"
    provider_id = "appd_bg"
    country_code = "BG"
    expected_min_stations = 20
    stale_after_days = 2
    current_url = "https://www.appd-bg.org/hidrology-en"
    forecast_url = "https://www.appd-bg.org/forecasts-en"

    def initial_requests(self) -> list[SourceRequest]:
        return [
            SourceRequest("current", self.current_url, "html", "text/html"),
            SourceRequest("forecast", self.forecast_url, "html", "text/html"),
        ]

    @staticmethod
    def _station(local_name: str, kind: str, river_km, payload) -> StationRecord:
        canonical = canonical_station_name(local_name)
        application_id = station_slug("BG", local_name, kind)
        return apply_ris_reference(StationRecord(
            station_id=application_id, source_station_id=None, country_code="BG",
            station_name=canonical, station_name_local=local_name,
            station_slug=application_id, river_name="Danube", river_km=river_km,
            latitude=None, longitude=None, coordinate_source=None,
            coordinate_method="unresolved", coordinate_confidence="unavailable",
            source_url=payload.url, active=True, last_verified_at=payload.captured_at_utc[:10],
            operator_provider_id="appd_bg", source_provider_id="appd_bg",
            captured_via_provider_id="appd_bg", station_type=kind,
            inclusion_reason="official APPD Danube table linked to the versioned Bulgarian RIS gauge registry",
            source_stream_type=kind,
            observation_frequency="daily operational window" if kind == "manual" else "automatic operational window",
        ))

    @staticmethod
    def _edition_date(text: str) -> str:
        match = re.search(r"Danube river\s+(\d{2})\.(\d{2})\.(20\d{2})", text, re.I)
        if not match:
            raise SourceStructureError("APPD table edition date missing")
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"

    def parse(self, payloads):
        current = payloads["current"]
        current_text = payload_text(current)
        measurement_date = self._edition_date(current_text)
        tables = html_tables(current).tables
        candidate_tables = [t for t in tables if t["rows"] and "station" in " ".join(t["rows"][0]).lower()]
        if len(candidate_tables) < 2:
            raise SourceStructureError("APPD hydrometric and automatic station tables not found")
        main_rows = [r for r in candidate_tables[0]["rows"][1:] if len(r) >= 6]
        automatic_rows = [r for r in candidate_tables[1]["rows"][1:] if len(r) >= 5]
        if len(main_rows) < 8 or len(automatic_rows) < 12:
            raise SourceStructureError(f"APPD station loss: main={len(main_rows)}, automatic={len(automatic_rows)}")

        stations: list[StationRecord] = []
        observations: list[ObservationRecord] = []
        for row in main_rows:
            local_name, km = row[0], parse_optional_float(row[1])
            station = self._station(local_name, "manual", km, current)
            stations.append(station)
            values = (
                ("water_level", parse_optional_float(row[2]), "cm", parse_optional_float(row[4]), 24),
                ("discharge", parse_optional_float(row[3]), "m3/s", None, None),
                ("water_temperature", parse_optional_float(row[5]), "degC", None, None),
            )
            for parameter, value, unit, variation, window in values:
                if value is None:
                    continue
                observations.append(ObservationRecord(
                    station_id=station.station_id, source_station_id=station.source_station_id,
                    operator_provider_id="appd_bg", source_provider_id="appd_bg",
                    captured_via_provider_id="appd_bg", parameter=parameter, value=value,
                    unit=unit, measurement_time_original=measurement_date,
                    measurement_timezone=None, measurement_datetime_local=None,
                    measurement_datetime_utc=None, measurement_date=measurement_date,
                    source_file_sha256=current.sha256, variation_value=variation,
                    variation_window_hours=window, physical_station_id=station.physical_station_id,
                    source_stream_id=station.source_stream_id, source_stream_type="manual",
                    is_primary_stream=station.is_primary_stream,
                    observation_frequency=station.observation_frequency,
                    observation_daypart="morning", observation_time_precision="date",
                    observation_window="manual_morning_publication_window",
                    source_observation_date=measurement_date,
                    source_observation_time_raw=measurement_date,
                ))
        direction_by_row = re.findall(r'<img\s+src=["\'][^"\']*/(down|up|nochange)\.gif', current_text, re.I)
        for index, row in enumerate(automatic_rows):
            local_name, km = row[0], parse_optional_float(row[1])
            station = self._station(local_name, "automatic", km, current)
            stations.append(station)
            direction = direction_by_row[index].lower() if index < len(direction_by_row) else None
            direction = "no_change" if direction == "nochange" else direction
            for parameter, value, unit in (
                ("water_level", parse_optional_float(row[2]), "cm"),
                ("water_temperature", parse_optional_float(row[4]), "degC"),
            ):
                if value is None:
                    continue
                observations.append(ObservationRecord(
                    station_id=station.station_id, source_station_id=station.source_station_id,
                    operator_provider_id="appd_bg", source_provider_id="appd_bg",
                    captured_via_provider_id="appd_bg", parameter=parameter, value=value,
                    unit=unit, measurement_time_original=measurement_date,
                    measurement_timezone=None, measurement_datetime_local=None,
                    measurement_datetime_utc=None, measurement_date=measurement_date,
                    source_file_sha256=current.sha256,
                    variation_window_hours=6 if parameter == "water_level" else None,
                    physical_station_id=station.physical_station_id,
                    source_stream_id=station.source_stream_id, source_stream_type="automatic",
                    is_primary_stream=station.is_primary_stream,
                    observation_frequency=station.observation_frequency,
                    observation_daypart="evening", observation_time_precision="date",
                    observation_window="automatic_evening_publication_window",
                    source_observation_date=measurement_date,
                    source_observation_time_raw=measurement_date,
                    trend=direction if parameter == "water_level" else None,
                ))

        forecast_payload = payloads["forecast"]
        forecast_tables = html_tables(forecast_payload).tables
        forecast_text = payload_text(forecast_payload)
        headings = re.findall(r"<h3[^>]*>\s*([^<]+?)\s*</h3>\s*<canvas", forecast_text, re.I)
        series_tables = [t for t in forecast_tables if len(t["rows"]) >= 4 and t["rows"][0][0].lower() == "day"]
        if len(headings) != 5 or len(series_tables) != 5:
            raise SourceStructureError(f"APPD expected five forecast stations, got headings={len(headings)} tables={len(series_tables)}")
        main_by_name = {s.station_name.casefold(): s for s in stations if s.station_type == "manual"}
        forecasts: list[ForecastRecord] = []
        for heading, table in zip(headings, series_tables):
            station = main_by_name.get(canonical_station_name(heading).casefold())
            if not station:
                raise SourceStructureError(f"APPD forecast station not found in current table: {heading}")
            rows = table["rows"]
            if not all(len(row) == len(rows[0]) for row in rows[:4]):
                raise SourceStructureError(f"APPD forecast columns differ for {heading}")
            for day_raw, maximum, central, minimum in zip(rows[0][1:], rows[1][1:], rows[2][1:], rows[3][1:]):
                forecasts.append(ForecastRecord(
                    station_id=station.station_id, source_station_id=station.source_station_id,
                    operator_provider_id="appd_bg", source_provider_id="appd_bg",
                    captured_via_provider_id="appd_bg", forecast_parameter=None,
                    forecast_value=float(central), forecast_unit=None,
                    forecast_issue_time_original=None, forecast_issue_datetime_utc=None,
                    target_time_original=day_raw, target_datetime_utc=None,
                    target_date=None, lead_hours=None, source_file_sha256=forecast_payload.sha256,
                    physical_station_id=station.physical_station_id,
                    source_stream_id=f"{station.source_stream_id}:forecast-candidate",
                    source_quality_status="candidate_not_activated",
                    forecast_min_value=float(minimum), forecast_max_value=float(maximum),
                ))

        issues = [ValidationIssue(
            "warning", "forecast_not_activated",
            "APPD chart series remain diagnostic candidates because parameter, unit, target year, and issue semantics are not all demonstrated.",
        )]
        result = AdapterResult(
            source_id=self.source_id, country_code="BG", status="partial",
            stations=stations, observations=observations, forecasts=forecasts, issues=issues,
            source_station_count=len(stations),
            notes=[
                "The eight manual and twelve automatic streams are linked to 13 physical placements without artificial offsets.",
                "Official ISRS identifiers and coordinates come from the versioned Bulgarian RIS Index registry.",
                "Forecast targets remain raw DD.MM values; no year, time or timezone is inferred.",
                "APPD forecast candidates are diagnostic-only and public forecast_status is not_activated.",
            ],
        )
        return self.validate(result, self.capture_time(payloads))
