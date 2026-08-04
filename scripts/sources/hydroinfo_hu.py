"""OVF Hydroinfo HTML adapter, primary only for Hungarian stations."""

from __future__ import annotations

import html
import re

from .base import (
    AdapterResult, ObservationRecord, SourceAdapter, SourceRequest, SourceStructureError,
    StationRecord, canonical_station_name, html_tables, parse_optional_float, payload_text,
    station_slug,
)


class HydroinfoAdapter(SourceAdapter):
    source_id = "hydroinfo_hu"
    provider_id = "hydroinfo_hu"
    country_code = "HU"
    expected_min_stations = 25
    current_url = "https://www.hydroinfo.hu/tables/dunhif.html"
    forecast_url = "https://www.hydroinfo.hu/mobil/en/hydroinfo.php"

    def initial_requests(self) -> list[SourceRequest]:
        return [
            SourceRequest("current", self.current_url, "html", "text/html"),
            SourceRequest("forecast-narrative", self.forecast_url, "html", "text/html"),
        ]

    @staticmethod
    def _measurement_date(text: str) -> str:
        decoded = html.unescape(text)
        match = re.search(r"(20\d{2})\.\s*([A-Za-záéíóöőúüű]+)\s+(\d{1,2})\.", decoded, re.I)
        if not match:
            raise SourceStructureError("Hydroinfo observation date missing")
        months = {
            "január": 1, "február": 2, "március": 3, "április": 4, "május": 5,
            "június": 6, "július": 7, "augusztus": 8, "szeptember": 9,
            "október": 10, "november": 11, "december": 12,
        }
        month = months.get(match.group(2).casefold())
        if month is None:
            raise SourceStructureError(f"Unknown Hydroinfo month: {match.group(2)}")
        return f"{int(match.group(1)):04d}-{month:02d}-{int(match.group(3)):02d}"

    def parse(self, payloads):
        payload = payloads["current"]
        text = payload_text(payload)
        measurement_date = self._measurement_date(text)
        parser = html_tables(payload)
        rows = [
            row for table in parser.tables for row in table["rows"]
            if len(row) >= 10 and row[0].isdigit() and row[2].casefold() == "duna"
        ]
        if len(rows) < 90:
            raise SourceStructureError(f"Hydroinfo expected approximately 93 Danube rows, got {len(rows)}")

        stations: list[StationRecord] = []
        observations: list[ObservationRecord] = []
        excluded = 0
        for row in rows:
            code, local_name = row[0], row[1]
            if not code.startswith("4"):
                excluded += 1
                continue
            sid = f"hu-{code}"
            stations.append(StationRecord(
                station_id=sid, source_station_id=code, country_code="HU",
                station_name=canonical_station_name(local_name), station_name_local=local_name,
                station_slug=station_slug("HU", local_name), river_name="Danube",
                latitude=None, longitude=None, coordinate_source=None,
                coordinate_method="unavailable", coordinate_confidence="unavailable",
                source_url=self.current_url, active=True, last_verified_at=payload.captured_at_utc[:10],
                operator_provider_id="hydroinfo_hu", source_provider_id="hydroinfo_hu",
                captured_via_provider_id="hydroinfo_hu",
                inclusion_reason="station code prefix 4 identifies Hungarian primary rows; foreign rows remain validation-only",
            ))
            level = parse_optional_float(row[5])
            variation = parse_optional_float(row[6])
            discharge = parse_optional_float(row[7])
            temperature = parse_optional_float(row[8])
            for parameter, value, unit in (
                ("water_level", level, "cm"),
                ("discharge", discharge, "m3/s"),
                ("water_temperature", temperature, "degC"),
            ):
                if value is None:
                    continue
                observations.append(ObservationRecord(
                    station_id=sid, source_station_id=code,
                    operator_provider_id="hydroinfo_hu", source_provider_id="hydroinfo_hu",
                    captured_via_provider_id="hydroinfo_hu", parameter=parameter,
                    value=value, unit=unit, measurement_time_original=measurement_date,
                    measurement_timezone=None, measurement_datetime_local=None,
                    measurement_datetime_utc=None, measurement_date=measurement_date,
                    source_file_sha256=payload.sha256,
                    variation_value=variation if parameter == "water_level" else None,
                    variation_window_hours=24 if parameter == "water_level" and variation is not None else None,
                ))

        narrative = payload_text(payloads["forecast-narrative"])
        if "next six days" not in html.unescape(narrative).lower():
            raise SourceStructureError("Hydroinfo six-day forecast narrative marker missing")
        result = AdapterResult(
            source_id=self.source_id, country_code=self.country_code, status="complete",
            stations=stations, observations=observations, forecasts=[],
            source_station_count=len(rows), excluded_station_count=excluded,
            notes=[
                "Only station codes beginning with 4 are primary Hungarian rows; 68 foreign rows are excluded and may be used only for validation.",
                "The audited six-day page is a narrative forecast and exposes no per-station numeric series; no forecast values are invented.",
                "Coordinates are not present in the audited official HTML and remain unset.",
            ],
        )
        return self.validate(result)
