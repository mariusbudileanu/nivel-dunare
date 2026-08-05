"""RHMZ Serbia daily/forecast and near-real-time fixture/live parser.

The adapter always relies on standard HTTPS verification. Production scheduling
remains disabled until that verification succeeds in GitHub Actions; no TLS
fallback, HTTP downgrade, or certificate bypass exists here.
"""

from __future__ import annotations

import re
import statistics
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timezone

from .base import (
    AdapterResult, ForecastRecord, ObservationRecord, SourceAdapter, SourceRequest,
    SourceStructureError, StationRecord, ValidationIssue, canonical_station_name,
    html_tables, parse_optional_float, payload_text, station_slug,
)
from .reference import apply_coordinate_override


class HidmetAdapter(SourceAdapter):
    source_id = "hidmet_rs"
    provider_id = "hidmet_rs"
    country_code = "RS"
    expected_min_stations = 13
    stale_after_days = 2
    daily_index_url = "https://www.hidmet.gov.rs/eng/osmotreni/stanje_voda.php"
    nrt_index_url = "https://www.hidmet.gov.rs/eng/osmotreni/nrt_index.php"
    nrt_period = 7

    def initial_requests(self) -> list[SourceRequest]:
        return [
            SourceRequest("daily-index", self.daily_index_url, "html", "text/html"),
            SourceRequest("nrt-index", self.nrt_index_url, "html", "text/html"),
        ]

    @staticmethod
    def _links(text: str) -> dict[str, tuple[str, str]]:
        links: dict[str, tuple[str, str]] = {}
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*(?:prognoza|bezprognoza|opseg)\.php\?[^"\']*hm_id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
            re.I | re.S,
        )
        for href, identifier, raw_name in pattern.findall(text):
            name = re.sub(r"<[^>]+>", " ", raw_name)
            name = re.sub(r"\s+", " ", name).strip()
            links[identifier] = (href, name)
        return links

    @staticmethod
    def _nrt_links(text: str) -> dict[str, str]:
        links: dict[str, str] = {}
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*nrt_tabela_grafik\.php\?[^"\']*hm_id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
            re.I | re.S,
        )
        for _href, identifier, raw_name in pattern.findall(text):
            name = re.sub(r"<[^>]+>", " ", raw_name)
            links[identifier] = re.sub(r"\s+", " ", name).strip()
        return links

    def additional_requests(self, payloads):
        daily = self._links(payload_text(payloads["daily-index"]))
        nrt = self._nrt_links(payload_text(payloads["nrt-index"]))
        requests = []
        for identifier, (href, _name) in sorted(daily.items()):
            requests.append(SourceRequest(
                f"daily-{identifier}", urllib.parse.urljoin(self.daily_index_url, href),
                "html", "text/html",
            ))
        for identifier in sorted(nrt):
            url = urllib.parse.urljoin(
                self.nrt_index_url,
                f"nrt_tabela_grafik.php?hm_id={identifier}&period={self.nrt_period}",
            )
            requests.append(SourceRequest(f"nrt-{identifier}", url, "html", "text/html"))
        return requests

    @staticmethod
    def _date(value: str) -> str:
        value = value.strip()
        for pattern in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(value, pattern).date().isoformat()
            except ValueError:
                pass
        raise SourceStructureError(f"Unrecognised RHMZ date: {value!r}")

    @staticmethod
    def _nrt_time(raw: str) -> tuple[str | None, str | None, str | None, str]:
        compact = re.sub(r"\s+", " ", raw.strip())
        candidate = compact.replace(" ", "T", 1).replace(" +", "+").replace(" -", "-")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            match = re.match(r"(\d{4}-\d{2}-\d{2})", compact)
            if not match:
                raise SourceStructureError(f"Unrecognised RHMZ NRT timestamp: {raw!r}")
            return None, None, None, match.group(1)
        if parsed.tzinfo is None:
            return parsed.isoformat(), None, None, parsed.date().isoformat()
        offset = parsed.strftime("%z")
        offset = f"{offset[:3]}:{offset[3:]}" if offset else None
        return parsed.isoformat(), parsed.astimezone(timezone.utc).isoformat(), offset, parsed.date().isoformat()

    def parse(self, payloads):
        daily_links = self._links(payload_text(payloads["daily-index"]))
        nrt_links = self._nrt_links(payload_text(payloads["nrt-index"]))
        if len(daily_links) != 13:
            raise SourceStructureError(f"RHMZ daily index must demonstrate 13 Danube stations, got {len(daily_links)}")
        if len(nrt_links) != 12:
            raise SourceStructureError(f"RHMZ NRT index must demonstrate 12 automatic stations, got {len(nrt_links)}")
        if not set(nrt_links) < set(daily_links):
            raise SourceStructureError("RHMZ NRT station ids must be a strict subset of the daily inventory")

        stations: list[StationRecord] = []
        observations: list[ObservationRecord] = []
        forecasts: list[ForecastRecord] = []
        issues: list[ValidationIssue] = []
        observations_by_nrt_station: dict[str, list[ObservationRecord]] = defaultdict(list)

        for identifier, (href, local_name) in sorted(daily_links.items()):
            sid = f"rs-{identifier}"
            has_nrt = identifier in nrt_links
            source_url = urllib.parse.urljoin(self.daily_index_url, href)
            station = apply_coordinate_override(StationRecord(
                station_id=sid, source_station_id=identifier, country_code="RS",
                station_name=canonical_station_name(local_name), station_name_local=local_name,
                station_slug=station_slug("RS", local_name), river_name="Danube",
                latitude=None, longitude=None, coordinate_source=None,
                coordinate_method="unresolved", coordinate_confidence="unavailable",
                source_url=source_url, active=True,
                last_verified_at=payloads["daily-index"].captured_at_utc[:10],
                operator_provider_id="hidmet_rs", source_provider_id="hidmet_rs",
                captured_via_provider_id="hidmet_rs",
                inclusion_reason="official RHMZ daily Danube index link",
                physical_station_id=sid,
                source_stream_id=f"{identifier}:{'nrt' if has_nrt else 'daily'}",
                source_stream_type="nrt" if has_nrt else "daily",
                is_primary_stream=True,
                observation_frequency="calculated from timestamps" if has_nrt else "daily",
            ))
            stations.append(station)
            daily_payload = payloads.get(f"daily-{identifier}")
            if daily_payload is None:
                raise SourceStructureError(f"RHMZ daily station page missing for {identifier}")
            tables = html_tables(daily_payload).tables
            for table in tables:
                if not table["rows"]:
                    continue
                header = [cell.casefold() for cell in table["rows"][0]]
                if len(header) >= 4 and header[:4] == ["date", "water level", "discharge", "water temperature"]:
                    for row in table["rows"][1:]:
                        if len(row) < 4:
                            continue
                        observed_date = self._date(row[0])
                        for parameter, raw_value, unit in (
                            ("water_level", row[1], "cm"),
                            ("discharge", row[2], "m3/s"),
                            ("water_temperature", row[3], "degC"),
                        ):
                            value = parse_optional_float(raw_value)
                            if value is None:
                                continue
                            observations.append(ObservationRecord(
                                station_id=sid, source_station_id=identifier,
                                operator_provider_id="hidmet_rs", source_provider_id="hidmet_rs",
                                captured_via_provider_id="hidmet_rs", parameter=parameter,
                                value=value, unit=unit, measurement_time_original=row[0],
                                measurement_timezone=None, measurement_datetime_local=None,
                                measurement_datetime_utc=None, measurement_date=observed_date,
                                source_file_sha256=daily_payload.sha256,
                                physical_station_id=sid, source_stream_id=f"{identifier}:daily",
                                source_stream_type="daily", is_primary_stream=not has_nrt or parameter != "water_level",
                                observation_frequency="daily", observation_time_precision="date",
                                source_observation_date=observed_date,
                                source_observation_time_raw=row[0], source_value_raw=raw_value,
                                source_quality_status="official_daily",
                            ))
                elif len(header) >= 4 and header[:4] == ["forecast date", "parameter", "value", "unit"]:
                    for row in table["rows"][1:]:
                        if len(row) < 4:
                            continue
                        target_date = self._date(row[0])
                        parameter = {"water level": "water_level", "discharge": "discharge"}.get(row[1].casefold())
                        unit = {"cm": "cm", "m3/s": "m3/s", "m³/s": "m3/s"}.get(row[3].strip())
                        value = parse_optional_float(row[2])
                        if parameter is None or unit is None or value is None:
                            raise SourceStructureError(f"RHMZ forecast semantics changed for {identifier}")
                        forecasts.append(ForecastRecord(
                            station_id=sid, source_station_id=identifier,
                            operator_provider_id="hidmet_rs", source_provider_id="hidmet_rs",
                            captured_via_provider_id="hidmet_rs", forecast_parameter=parameter,
                            forecast_value=value, forecast_unit=unit,
                            forecast_issue_time_original=None, forecast_issue_datetime_utc=None,
                            target_time_original=row[0], target_datetime_utc=None,
                            target_date=target_date, lead_hours=None,
                            source_file_sha256=daily_payload.sha256,
                            physical_station_id=sid, source_stream_id=f"{identifier}:forecast",
                            source_stream_type="forecast", source_quality_status="official_daily_forecast",
                        ))
                elif header and header[0] == "range date":
                    issues.append(ValidationIssue(
                        "warning", "range_not_point_forecast",
                        "Official opseg range retained as a detected range and not converted into a point forecast.", sid,
                    ))

            if has_nrt:
                nrt_payload = payloads.get(f"nrt-{identifier}")
                if nrt_payload is None:
                    raise SourceStructureError(f"RHMZ NRT page missing for {identifier}")
                nrt_tables = html_tables(nrt_payload).tables
                nrt_table = next((
                    table for table in nrt_tables
                    if table["rows"] and [cell.casefold() for cell in table["rows"][0]][:3]
                    == ["timestamp", "water level", "unit"]
                ), None)
                if nrt_table is None:
                    raise SourceStructureError(f"RHMZ NRT table missing for {identifier}")
                captured = datetime.fromisoformat(nrt_payload.captured_at_utc.replace("Z", "+00:00"))
                for row in nrt_table["rows"][1:]:
                    if len(row) < 3:
                        continue
                    local_time, utc_time, raw_offset, observed_date = self._nrt_time(row[0])
                    value = parse_optional_float(row[1])
                    if value is None or row[2].strip() != "cm":
                        raise SourceStructureError(f"RHMZ NRT level/unit changed for {identifier}")
                    delay = None
                    if utc_time:
                        delay = (captured.astimezone(timezone.utc) - datetime.fromisoformat(utc_time)).total_seconds()
                    observation = ObservationRecord(
                        station_id=sid, source_station_id=identifier,
                        operator_provider_id="hidmet_rs", source_provider_id="hidmet_rs",
                        captured_via_provider_id="hidmet_rs", parameter="water_level",
                        value=value, unit="cm", measurement_time_original=row[0],
                        measurement_timezone=raw_offset,
                        measurement_datetime_local=local_time,
                        measurement_datetime_utc=utc_time,
                        measurement_date=None if local_time else observed_date,
                        source_file_sha256=nrt_payload.sha256,
                        canonical_quality_flag="provisional",
                        physical_station_id=sid, source_stream_id=f"{identifier}:nrt",
                        source_stream_type="nrt", is_primary_stream=True,
                        observation_time_precision="timestamp" if local_time else "date",
                        source_observation_datetime=local_time,
                        source_observation_date=observed_date,
                        source_observation_time_raw=row[0], source_timezone_raw=raw_offset,
                        source_value_raw=row[1], source_quality_status="provisional",
                        capture_at=nrt_payload.captured_at_utc,
                        capture_delay_seconds=delay,
                    )
                    observations.append(observation)
                    observations_by_nrt_station[identifier].append(observation)

        for identifier, rows in observations_by_nrt_station.items():
            timestamps = sorted(
                datetime.fromisoformat(row.measurement_datetime_utc)
                for row in rows if row.measurement_datetime_utc
            )
            intervals = [
                (later - earlier).total_seconds() / 60
                for earlier, later in zip(timestamps, timestamps[1:]) if later > earlier
            ]
            frequency = f"{statistics.median(intervals):g} minutes" if intervals else "undetermined from available timestamps"
            for row in rows:
                row.observation_frequency = frequency

        result = AdapterResult(
            source_id=self.source_id, country_code="RS", status="complete",
            stations=stations, observations=observations, forecasts=forecasts,
            issues=issues, source_station_count=len(stations),
            notes=[
                "Daily and NRT streams share one physical_station_id; NRT is primary for level where available.",
                "Raw timestamps and explicit offsets are preserved; no timezone or clock time is invented.",
                f"NRT fixture/live requests use a controlled {self.nrt_period}-day overlap until a larger official period is demonstrated.",
                "TLS verification is standard-only. Scheduling stays disabled until GitHub Actions demonstrates valid official HTTPS access.",
            ],
        )
        return self.validate(result, self.capture_time(payloads))