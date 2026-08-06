"""Official RHMZ Serbia daily, NRT and forecast adapter.

All requests use HTTPS and the standard client trust store.  The adapter
discovers 13 Danube gauges from the daily index and 12 automatic streams from
the independent NRT index; it never invents an automatic Slankamen stream.
"""

from __future__ import annotations

import re
import statistics
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .base import (
    AdapterResult, FetchedPayload, ForecastRecord, ObservationRecord, SourceAdapter,
    SourceRequest, SourceStructureError, StationRecord, ValidationIssue,
    canonical_station_name, html_tables, parse_optional_float, payload_text,
    station_slug,
)
from .reference import apply_coordinate_override

DAILY_TIME_UTC = "06:00"
MISSING_CODES = {"*": "not_published", "-": "unavailable"}
PROVISIONAL_NOTE = (
    "Data is provisional, unchecked, and has not been validated to remove invalid values."
)


def _plain(value: str) -> str:
    value = re.sub(r"(?is)<script\b.*?</script>|<style\b.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value.replace("&nbsp;", " ")).strip()


def _danube_rows(text: str):
    for match in re.finditer(r"(?is)<tr\b[^>]*>(.*?)</tr>", text):
        row = match.group(1)
        cells = re.findall(r"(?is)<t[dh]\b[^>]*>(.*?)</t[dh]>", row)
        if cells and canonical_station_name(_plain(cells[0])).casefold() == "dunav":
            yield row


def _date_with_year(raw: str, reference: date) -> date:
    compact = re.sub(r"\s+", " ", raw.strip()).rstrip(".")
    for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(compact, pattern).date()
        except ValueError:
            pass
    match = re.fullmatch(r"(\d{1,2})\.(\d{1,2})", compact)
    if not match:
        raise SourceStructureError(f"Unrecognised RHMZ date: {raw!r}")
    day, month = map(int, match.groups())
    candidates = [date(reference.year + offset, month, day) for offset in (-1, 0, 1)]
    return min(candidates, key=lambda item: abs((item - reference).days))


def _value(raw: str) -> tuple[float | str, str, str]:
    compact = raw.strip()
    if compact in MISSING_CODES:
        return compact, "missing", MISSING_CODES[compact]
    parsed = parse_optional_float(compact)
    if parsed is None:
        raise SourceStructureError(f"Unexpected RHMZ numeric token: {raw!r}")
    return parsed, "observed", "official_daily"


class HidmetAdapter(SourceAdapter):
    source_id = provider_id = "hidmet_rs"
    country_code = "RS"
    expected_min_stations = 13
    stale_after_days = 2
    daily_index_url = "https://www.hidmet.gov.rs/eng/osmotreni/stanje_voda.php"
    nrt_index_url = "https://www.hidmet.gov.rs/eng/osmotreni/nrt_index.php"
    central_forecast_url = "https://www.hidmet.gov.rs/eng/prognoza/prognoza_voda.php"
    # The NRT page advertises 7 and 30. Routine overlap is 7; backfill sets 30.
    nrt_period = 7
    collection_profile = "all"

    def initial_requests(self) -> list[SourceRequest]:
        requests = [SourceRequest("daily-index", self.daily_index_url, "html", "text/html")]
        if self.collection_profile in {"all", "nrt"}:
            requests.append(SourceRequest("nrt-index", self.nrt_index_url, "html", "text/html"))
        if self.collection_profile in {"all", "forecast"}:
            requests.append(SourceRequest(
                "central-forecast", self.central_forecast_url, "html", "text/html",
            ))
        return requests

    @staticmethod
    def _links(text: str) -> dict[str, tuple[str, str, str]]:
        result = {}
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*(prognoza|bezprognoza|opseg)\.php\?[^"\']*hm_id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
            re.I | re.S,
        )
        for row in _danube_rows(text):
            match = pattern.search(row)
            if match:
                href, page_type, identifier, name = match.groups()
                result[identifier] = (href, _plain(name), page_type.casefold())
        return result

    @staticmethod
    def _nrt_links(text: str) -> dict[str, tuple[str, str]]:
        result = {}
        pattern = re.compile(
            r'<a[^>]+href=["\']([^"\']*nrt_tabela_grafik\.php\?[^"\']*hm_id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>',
            re.I | re.S,
        )
        for row_match in re.finditer(r"(?is)<tr\b[^>]*>(.*?)</tr>", text):
            row = row_match.group(1)
            cells = [
                canonical_station_name(_plain(value)).casefold()
                for value in re.findall(r"(?is)<t[dh]\b[^>]*>(.*?)</t[dh]>", row)
            ]
            if not any(value == "dunav" or value.endswith(": dunav") for value in cells):
                continue
            match = pattern.search(row)
            if match:
                href, identifier, name = match.groups()
                result[identifier] = (href, _plain(name))
        return result

    def additional_requests(self, payloads: dict[str, FetchedPayload]) -> list[SourceRequest]:
        daily = self._links(payload_text(payloads["daily-index"]))
        nrt_payload = payloads.get("nrt-index", payloads["daily-index"])
        nrt = self._nrt_links(payload_text(nrt_payload))
        requests = [
            SourceRequest(
                f"daily-{identifier}", urllib.parse.urljoin(self.daily_index_url, href),
                "html", "text/html",
            )
            for identifier, (href, _name, _page_type) in sorted(daily.items())
            if self.collection_profile in {"all", "daily"}
        ]
        requests.extend(
            SourceRequest(
                f"nrt-{identifier}",
                urllib.parse.urljoin(
                    self.nrt_index_url,
                    f"nrt_tabela_grafik.php?hm_id={identifier}&period={self.nrt_period}",
                ),
                "html", "text/html",
            )
            for identifier in sorted(nrt)
            if self.collection_profile in {"all", "nrt"}
        )
        return requests

    @staticmethod
    def _daily_date(text: str) -> date:
        values = re.findall(r"(?i)(\d{1,2}\.\d{1,2}\.\d{4})\.?", text)
        if not values:
            raise SourceStructureError("RHMZ daily page has no demonstrated full date")
        return datetime.strptime(values[0], "%d.%m.%Y").date()

    @staticmethod
    def _trend(text: str) -> str | None:
        names = re.findall(r"repository/ikonice/interf/([a-z]+)\.gif", text, re.I)
        mapping = {"stag": "stagnant", "rast": "rising", "pad": "falling"}
        return next((mapping[name.casefold()] for name in reversed(names) if name.casefold() in mapping), None)

    def parse_daily_page(self, payload, station_id, identifier, has_nrt):
        text = payload_text(payload)
        observed = self._daily_date(text)
        table = next((
            item for item in html_tables(payload).tables
            if any(row and row[0].casefold().startswith("water stage") for row in item["rows"])
        ), None)
        if table is None:
            raise SourceStructureError(f"RHMZ daily table missing for {identifier}")
        header = next(
            i for i, row in enumerate(table["rows"])
            if row and row[0].casefold().startswith("water stage")
        )
        if header + 1 >= len(table["rows"]) or len(table["rows"][header + 1]) < 4:
            raise SourceStructureError(f"RHMZ daily value row missing for {identifier}")
        values = table["rows"][header + 1]
        original = f"{observed.strftime('%d.%m.%Y')} {DAILY_TIME_UTC} UTC"
        utc = f"{observed.isoformat()}T{DAILY_TIME_UTC}:00+00:00"
        variation = parse_optional_float(values[1]) if values[1].strip() not in MISSING_CODES else None
        rows = []
        for index, parameter, unit in (
            (0, "water_level", "cm"), (2, "discharge", "m3/s"),
            (3, "water_temperature", "degC"),
        ):
            value, quality, code = _value(values[index])
            rows.append(ObservationRecord(
                station_id=station_id, source_station_id=identifier,
                operator_provider_id=self.provider_id, source_provider_id=self.provider_id,
                captured_via_provider_id=self.provider_id, parameter=parameter,
                value=value, unit=unit, measurement_time_original=original,
                measurement_timezone="UTC", measurement_datetime_local=None,
                measurement_datetime_utc=utc, measurement_date=observed.isoformat(),
                source_file_sha256=payload.sha256, source_quality_code=code,
                canonical_quality_flag=quality,
                variation_value=variation if parameter == "water_level" else None,
                variation_window_hours=24 if parameter == "water_level" and variation is not None else None,
                physical_station_id=station_id, source_stream_id=f"{identifier}:daily",
                source_stream_type="daily", is_primary_stream=not has_nrt,
                observation_frequency="daily after the official 10:00 local update",
                observation_time_precision="declared_time", source_observation_datetime=utc,
                source_observation_date=observed.isoformat(), source_observation_time_raw=original,
                source_timezone_raw="UTC", capture_at=payload.captured_at_utc,
                source_quality_status=code, source_value_raw=values[index],
                trend=self._trend(text) if parameter == "water_level" else None,
            ))
        points, issues = self.parse_individual_forecast(payload, station_id, identifier, observed)
        return rows, points, issues

    def parse_individual_forecast(self, payload, station_id, identifier, reference):
        table = next((
            item for item in html_tables(payload).tables if item["rows"] and item["rows"][0]
            and item["rows"][0][0].casefold().startswith("water stage forecast")
        ), None)
        if table is None:
            return [], []  # bezprognoza is valid and produces no forecast.
        dates = next((r for r in table["rows"] if r and r[0].casefold().startswith("date")), None)
        values = next((r for r in table["rows"] if r and r[0].casefold().startswith("water stage") and not r[0].casefold().startswith("water stage forecast")), None)
        if not dates or not values or len(dates) != len(values):
            raise SourceStructureError(f"RHMZ individual forecast changed for {identifier}")
        forecasts, issues = [], []
        for raw_date, raw_value in zip(dates[1:], values[1:]):
            if "÷" in raw_date or "÷" in raw_value:
                issues.append(ValidationIssue(
                    "information", "range_not_point_forecast",
                    f"Official range retained as evidence: {raw_date} = {raw_value} cm", station_id,
                ))
                continue
            value = parse_optional_float(raw_value)
            if value is None:
                continue
            target = _date_with_year(raw_date, reference)
            forecasts.append(ForecastRecord(
                station_id=station_id, source_station_id=identifier,
                operator_provider_id=self.provider_id, source_provider_id=self.provider_id,
                captured_via_provider_id=self.provider_id, forecast_parameter="water_level",
                forecast_value=value, forecast_unit="cm",
                forecast_issue_time_original=reference.isoformat(), forecast_issue_datetime_utc=None,
                target_time_original=raw_date, target_datetime_utc=None, target_date=target.isoformat(),
                lead_hours=None, source_file_sha256=payload.sha256,
                physical_station_id=station_id, source_stream_id=f"{identifier}:forecast",
                source_stream_type="forecast", capture_at=payload.captured_at_utc,
                source_quality_status="official_individual_forecast",
            ))
        return forecasts, issues

    @staticmethod
    def _nrt_offset(text: str) -> timezone:
        match = re.search(r"UTC\s*([+-])\s*(\d{1,2})(?::(\d{2}))?", text, re.I)
        if not match:
            raise SourceStructureError("RHMZ NRT page does not declare a UTC offset")
        delta = timedelta(hours=int(match.group(2)), minutes=int(match.group(3) or 0))
        return timezone(delta if match.group(1) == "+" else -delta)

    def parse_nrt_page(self, payload, station_id, identifier):
        offset = self._nrt_offset(payload_text(payload))
        raw_offset = datetime(2000, 1, 1, tzinfo=offset).strftime("%z")
        raw_offset = f"{raw_offset[:3]}:{raw_offset[3:]}"
        table = next((
            item for item in html_tables(payload).tables if item["rows"]
            and len(item["rows"][0]) >= 2
            and item["rows"][0][0].casefold() == "date and time"
            and item["rows"][0][1].casefold().startswith("water stage")
        ), None)
        if table is None:
            raise SourceStructureError(f"RHMZ NRT table missing for {identifier}")
        captured = datetime.fromisoformat(payload.captured_at_utc.replace("Z", "+00:00"))
        result, seen = [], set()
        for row in table["rows"][1:]:
            if len(row) < 2 or not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}", row[0]):
                continue
            measured = datetime.strptime(row[0], "%d.%m.%Y %H:%M").replace(tzinfo=offset)
            local, utc = measured.isoformat(), measured.astimezone(timezone.utc).isoformat()
            if local in seen:
                continue
            seen.add(local)
            value = parse_optional_float(row[1])
            if value is None:
                raise SourceStructureError(f"RHMZ NRT value changed for {identifier}: {row[1]!r}")
            result.append(ObservationRecord(
                station_id=station_id, source_station_id=identifier,
                operator_provider_id=self.provider_id, source_provider_id=self.provider_id,
                captured_via_provider_id=self.provider_id, parameter="water_level",
                value=value, unit="cm", measurement_time_original=row[0],
                measurement_timezone=raw_offset, measurement_datetime_local=local,
                measurement_datetime_utc=utc, measurement_date=measured.date().isoformat(),
                source_file_sha256=payload.sha256, source_quality_code="provisional_unvalidated",
                canonical_quality_flag="provisional", physical_station_id=station_id,
                source_stream_id=f"{identifier}:nrt", source_stream_type="nrt", is_primary_stream=True,
                observation_time_precision="minute", source_observation_datetime=local,
                source_observation_date=measured.date().isoformat(), source_observation_time_raw=row[0],
                source_timezone_raw=raw_offset, capture_at=payload.captured_at_utc,
                source_quality_status="provisional_unvalidated", source_value_raw=row[1],
                capture_delay_seconds=(captured.astimezone(timezone.utc) - measured.astimezone(timezone.utc)).total_seconds(),
            ))
        if not result:
            raise SourceStructureError(f"RHMZ NRT table has no observations for {identifier}")
        stamps = sorted(datetime.fromisoformat(row.measurement_datetime_utc) for row in result)
        intervals = [int((b - a).total_seconds() // 60) for a, b in zip(stamps, stamps[1:]) if b > a]
        if not intervals:
            frequency = "unknown"
        elif len(set(intervals)) == 1:
            frequency = f"{intervals[0]} minutes"
        else:
            frequency = f"variable (median {statistics.median(intervals):g} minutes)"
        for row in result:
            row.observation_frequency = frequency
        return result

    def parse_central_forecast(self, payload, station_by_name):
        text = payload_text(payload)
        issue = re.search(r"Water level forecast:.*?(\d{1,2}\.\d{1,2}\.\d{4})", text, re.I | re.S)
        if not issue:
            raise SourceStructureError("RHMZ central forecast issue date missing")
        issue_date = datetime.strptime(issue.group(1), "%d.%m.%Y").date()
        table = next((
            item for item in html_tables(payload).tables if item["rows"] and item["rows"][0]
            and item["rows"][0][0].casefold() == "river"
            and any("water level forecast" in cell.casefold() for cell in item["rows"][0])
        ), None)
        if table is None:
            raise SourceStructureError("RHMZ central forecast table missing")
        date_row = next((
            row for row in table["rows"][:6]
            if len(row) >= 7 and any(re.fullmatch(r"\d{2}\.\d{2}\.", cell) for cell in row)
        ), None)
        if date_row is None:
            raise SourceStructureError("RHMZ central forecast target dates missing")
        targets = [_date_with_year(value, issue_date) for value in date_row[2:7]]
        result = []
        for row in table["rows"]:
            if len(row) < 9 or canonical_station_name(row[0]).casefold() != "dunav":
                continue
            station = station_by_name.get(canonical_station_name(row[1]).casefold())
            if not station:
                raise SourceStructureError(f"Unknown Danube station in central forecast: {row[1]!r}")
            station_id, identifier = station
            alert_note = f"first alert={row[7]} cm; second alert={row[8]} cm"
            # The source labels column 2 current; columns 3..6 are forecasts.
            for target, raw_value in zip(targets[1:], row[3:7]):
                value = parse_optional_float(raw_value)
                if value is None:
                    continue
                result.append(ForecastRecord(
                    station_id=station_id, source_station_id=identifier,
                    operator_provider_id=self.provider_id, source_provider_id=self.provider_id,
                    captured_via_provider_id=self.provider_id, forecast_parameter="water_level",
                    forecast_value=value, forecast_unit="cm",
                    forecast_issue_time_original=f"{issue.group(1)}; {alert_note}",
                    forecast_issue_datetime_utc=None, target_time_original=target.strftime("%d.%m.%Y"),
                    target_datetime_utc=None, target_date=target.isoformat(), lead_hours=None,
                    source_file_sha256=payload.sha256, physical_station_id=station_id,
                    source_stream_id=f"{identifier}:forecast", source_stream_type="forecast",
                    capture_at=payload.captured_at_utc,
                    source_quality_status="official_central_forecast",
                ))
        if not result:
            raise SourceStructureError("RHMZ central forecast has no Danube point forecasts")
        return result

    def parse(self, payloads: dict[str, FetchedPayload]) -> AdapterResult:
        daily = self._links(payload_text(payloads["daily-index"]))
        nrt_payload = payloads.get("nrt-index", payloads["daily-index"])
        nrt = self._nrt_links(payload_text(nrt_payload))
        if len(daily) != 13:
            raise SourceStructureError(f"RHMZ daily index must demonstrate 13 Danube stations, got {len(daily)}")
        if len(nrt) != 12:
            raise SourceStructureError(f"RHMZ indexes must demonstrate 12 automatic stations, got {len(nrt)}")
        if not set(nrt) < set(daily):
            raise SourceStructureError("RHMZ NRT ids must be a strict subset of the daily inventory")

        stations, observations, issues = [], [], []
        individual = defaultdict(list)
        station_by_name = {}
        for identifier, (href, local_name, _page_type) in sorted(daily.items()):
            sid, has_nrt = f"rs-{identifier}", identifier in nrt
            station = apply_coordinate_override(StationRecord(
                station_id=sid, source_station_id=identifier, country_code="RS",
                station_name=canonical_station_name(local_name), station_name_local=local_name,
                station_slug=station_slug("RS", local_name), river_name="Danube",
                latitude=None, longitude=None, coordinate_source=None,
                coordinate_method="unresolved", coordinate_confidence="unavailable",
                source_url=urllib.parse.urljoin(self.daily_index_url, href), active=True,
                last_verified_at=payloads["daily-index"].captured_at_utc[:10],
                operator_provider_id=self.provider_id, source_provider_id=self.provider_id,
                captured_via_provider_id=self.provider_id,
                inclusion_reason="official RHMZ daily Danube index link",
                physical_station_id=sid, source_stream_id=f"{identifier}:{'nrt' if has_nrt else 'daily'}",
                source_stream_type="nrt" if has_nrt else "daily", is_primary_stream=True,
                observation_frequency="derived from source timestamps" if has_nrt else "daily",
            ))
            stations.append(station)
            station_by_name[station.station_name.casefold()] = (sid, identifier)
            daily_payload = payloads.get(f"daily-{identifier}")
            if self.collection_profile in {"all", "daily"}:
                if daily_payload is None:
                    raise SourceStructureError(f"RHMZ daily page missing for {identifier}")
                daily_rows, point_rows, page_issues = self.parse_daily_page(
                    daily_payload, sid, identifier, has_nrt,
                )
                observations.extend(daily_rows)
                individual[identifier].extend(point_rows)
                issues.extend(page_issues)
            if has_nrt and self.collection_profile in {"all", "nrt"}:
                nrt_payload = payloads.get(f"nrt-{identifier}")
                if nrt_payload is None:
                    raise SourceStructureError(f"RHMZ NRT page missing for {identifier}")
                nrt_rows = self.parse_nrt_page(nrt_payload, sid, identifier)
                observations.extend(nrt_rows)
                station.observation_frequency = nrt_rows[0].observation_frequency

        forecasts = []
        if self.collection_profile in {"all", "forecast"} and "central-forecast" in payloads:
            forecasts = self.parse_central_forecast(payloads["central-forecast"], station_by_name)
            central_ids = {row.source_station_id for row in forecasts}
            for identifier, rows in individual.items():
                if identifier not in central_ids:
                    forecasts.extend(rows)
        result = AdapterResult(
            source_id=self.source_id, country_code="RS", status="complete",
            stations=stations, observations=observations, forecasts=forecasts,
            issues=issues, source_station_count=len(stations),
            notes=[
                "Thirteen physical Danube gauges are discovered from the official daily index.",
                "Twelve NRT streams are discovered independently; Slankamen has no invented NRT stream.",
                "The source advertises a 7-day overlap and a 30-day maximum backfill; payload URLs preserve the requested period.",
                f"Collection profile: {self.collection_profile}.",
                PROVISIONAL_NOTE,
                "Daily time is the declared 06:00 UTC; NRT retains the declared page offset.",
                "Central forecasts are primary; individual point forecasts are fallback evidence; ranges stay non-point.",
                "Standard TLS and hostname verification only; no downgrade or bypass is implemented.",
            ],
        )
        return self.validate(result, self.capture_time(payloads))
