"""SHMÚ semantic HTML adapter for Slovak Danube stations."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .base import (
    AdapterResult, ForecastRecord, ObservationRecord, SourceAdapter, SourceRequest,
    SourceStructureError, StationRecord, canonical_station_name, html_tables,
    iso_from_milliseconds, parse_optional_float, payload_text, station_slug,
)
from .reference import apply_coordinate_override


class ShmuAdapter(SourceAdapter):
    source_id = "shmu_sk"
    provider_id = "shmu_sk"
    country_code = "SK"
    expected_min_stations = 13
    stale_after_days = 2
    base_url = "https://www.shmu.sk/en/?id=hydro_vod_all&page=1&station_id={station_id}"

    def initial_requests(self) -> list[SourceRequest]:
        return [SourceRequest("station-5140", self.base_url.format(station_id="5140"), "html", "text/html")]

    @staticmethod
    def discover(text: str) -> list[tuple[str, str]]:
        return [
            (identifier, re.sub(r"\s+-\s+Dunaj$", "", name, flags=re.I).strip())
            for identifier, name in re.findall(
                r'<option\s+value=["\'](\d+)["\'][^>]*>([^<]+\s+-\s+Dunaj)</option>',
                text, flags=re.I,
            )
        ]

    def additional_requests(self, payloads):
        first = next(iter(payloads.values()))
        requests = []
        for identifier, _name in self.discover(payload_text(first)):
            label = f"station-{identifier}"
            if label not in payloads:
                requests.append(SourceRequest(label, self.base_url.format(station_id=identifier), "html", "text/html"))
        return requests

    def parse(self, payloads):
        first = next(iter(payloads.values()))
        discovered = dict(self.discover(payload_text(first)))
        if len(discovered) < self.expected_min_stations:
            raise SourceStructureError(f"SHMÚ discovery returned only {len(discovered)} Dunaj stations")

        stations: list[StationRecord] = []
        observations: list[ObservationRecord] = []
        forecasts: list[ForecastRecord] = []
        bratislava = ZoneInfo("Europe/Bratislava")

        for identifier, name in discovered.items():
            label = f"station-{identifier}"
            payload = payloads.get(label)
            if payload is None:
                raise SourceStructureError(f"SHMÚ missing payload for station {identifier}")
            text = payload_text(payload)
            parser = html_tables(payload)
            table = next((table for table in parser.tables if "Merané hodnoty" in table["caption"]), None)
            if table is None or len(table["rows"]) < 2:
                raise SourceStructureError(f"SHMÚ measurement table missing for {identifier}")
            data_row = next((row for row in table["rows"] if len(row) >= 2 and re.match(r"\d{1,2}\.\d{1,2}\.\d{4}", row[0])), None)
            if data_row is None:
                raise SourceStructureError(f"SHMÚ latest measurement row missing for {identifier}")

            sid = f"sk-{identifier}"
            local_name = name
            url = self.base_url.format(station_id=identifier)
            station = apply_coordinate_override(StationRecord(
                station_id=sid, source_station_id=identifier, country_code="SK",
                station_name=canonical_station_name(local_name), station_name_local=local_name,
                station_slug=station_slug("SK", local_name), river_name="Danube",
                latitude=None, longitude=None, coordinate_source=None,
                coordinate_method="unresolved", coordinate_confidence="unavailable",
                source_url=url, active=True, last_verified_at=payload.captured_at_utc[:10],
                operator_provider_id="shmu_sk", source_provider_id="shmu_sk",
                captured_via_provider_id="shmu_sk",
                inclusion_reason="official station option suffix '- Dunaj'",
                physical_station_id=sid, source_stream_id=f"{identifier}:observed",
                source_stream_type="observed", is_primary_stream=True,
                observation_frequency="source timestamp cadence",
            ))
            stations.append(station)
            raw_time = data_row[0]
            parsed_time = datetime.strptime(raw_time, "%d.%m.%Y %H:%M").replace(tzinfo=bratislava)
            utc_time = parsed_time.astimezone(ZoneInfo("UTC")).isoformat()
            level = parse_optional_float(data_row[1])
            temperature = parse_optional_float(data_row[2]) if len(data_row) > 2 else None
            if level is not None:
                observations.append(ObservationRecord(
                    station_id=sid, source_station_id=identifier,
                    operator_provider_id="shmu_sk", source_provider_id="shmu_sk",
                    captured_via_provider_id="shmu_sk", parameter="water_level", value=level,
                    unit="cm", measurement_time_original=raw_time,
                    measurement_timezone="Europe/Bratislava", measurement_datetime_local=parsed_time.isoformat(),
                    measurement_datetime_utc=utc_time, measurement_date=None,
                    source_file_sha256=payload.sha256, canonical_quality_flag="provisional",
                    physical_station_id=station.physical_station_id,
                    source_stream_id=station.source_stream_id, source_stream_type="observed",
                    observation_frequency=station.observation_frequency,
                    source_quality_status="provisional", source_value_raw=str(level),
                ))
            if temperature is not None:
                observations.append(ObservationRecord(
                    station_id=sid, source_station_id=identifier,
                    operator_provider_id="shmu_sk", source_provider_id="shmu_sk",
                    captured_via_provider_id="shmu_sk", parameter="water_temperature", value=temperature,
                    unit="degC", measurement_time_original=raw_time,
                    measurement_timezone="Europe/Bratislava", measurement_datetime_local=parsed_time.isoformat(),
                    measurement_datetime_utc=utc_time, measurement_date=None,
                    source_file_sha256=payload.sha256, canonical_quality_flag="provisional",
                    physical_station_id=station.physical_station_id,
                    source_stream_id=station.source_stream_id, source_stream_type="observed",
                    observation_frequency=station.observation_frequency,
                    source_quality_status="provisional", source_value_raw=str(temperature),
                ))

            forecast_match = re.search(
                r"var\s+forecast_serie\s*=.*?data\s*:\s*(\[\[.*?\]\])\s*}", text, re.I | re.S,
            )
            if forecast_match:
                pairs = re.findall(r"\[(\d{12,13}),\s*(-?\d+(?:\.\d+)?)\]", forecast_match.group(1))
                for target, value in pairs:
                    forecasts.append(ForecastRecord(
                        station_id=sid, source_station_id=identifier,
                        operator_provider_id="shmu_sk", source_provider_id="shmu_sk",
                        captured_via_provider_id="shmu_sk", forecast_parameter="water_level",
                        forecast_value=float(value), forecast_unit="cm",
                        forecast_issue_time_original=None, forecast_issue_datetime_utc=None,
                        target_time_original=target, target_datetime_utc=iso_from_milliseconds(int(target)),
                        target_date=None, lead_hours=None, source_file_sha256=payload.sha256,
                        physical_station_id=station.physical_station_id,
                        source_stream_id=f"{identifier}:forecast",
                        source_quality_status="provisional",
                    ))

        result = AdapterResult(
            source_id=self.source_id, country_code=self.country_code, status="complete",
            stations=stations, observations=observations, forecasts=forecasts,
            source_station_count=len(discovered), excluded_station_count=0,
            notes=["The source-provided provisional status is preserved without local plausibility filtering; sk-5128 uses the manually verified exact coordinate override."],
        )
        return self.validate(result, self.capture_time(payloads))
