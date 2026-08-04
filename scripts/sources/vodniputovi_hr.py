"""Croatian waterways/DHMZ JSON adapter for the Danube gauges."""

from __future__ import annotations

from datetime import date, datetime, timezone

from .base import (
    AdapterResult, ObservationRecord, SourceAdapter, SourceRequest, SourceStructureError,
    StationRecord, ValidationIssue, json_load, parse_optional_float, station_slug,
)


class VodniputoviAdapter(SourceAdapter):
    source_id = "vodniputovi_hr"
    provider_id = "vodniputovi_hr"
    country_code = "HR"
    expected_min_stations = 3
    current_url = "https://vodniputovi.hr/dhmz_vodostaji/getwaterstuff.php"
    station_metadata = {
        "aljmas": ("5001", "Aljmaš"),
        "batina": ("5170", "Batina"),
        "vukovar": ("5070", "Vukovar"),
    }

    def initial_requests(self) -> list[SourceRequest]:
        return [SourceRequest("current", self.current_url, "json", "application/json")]

    @staticmethod
    def _date(value: str) -> str:
        for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), pattern).date().isoformat()
            except ValueError:
                pass
        raise SourceStructureError(f"Unrecognised Croatian observation date: {value!r}")

    def parse(self, payloads):
        payload = payloads["current"]
        document = json_load(payload)
        if not isinstance(document, dict):
            raise SourceStructureError("Croatian response must be a station-keyed object")

        stations: list[StationRecord] = []
        observations: list[ObservationRecord] = []
        latest_date: date | None = None
        for source_key, (source_id, local_name) in self.station_metadata.items():
            series = document.get(source_key)
            if not isinstance(series, list) or not series:
                raise SourceStructureError(f"Croatian station {source_key!r} is missing or empty")
            sid = f"hr-{source_id}"
            stations.append(StationRecord(
                station_id=sid, source_station_id=source_id, country_code="HR",
                station_name=station_slug("HR", local_name)[3:].replace("-", " ").title(),
                station_name_local=local_name, station_slug=station_slug("HR", local_name),
                river_name="Danube", latitude=None, longitude=None, coordinate_source=None,
                coordinate_method="unavailable", coordinate_confidence="unavailable",
                source_url=self.current_url, active=True, last_verified_at=payload.captured_at_utc[:10],
                operator_provider_id="dhmz_hr", source_provider_id="vodniputovi_hr",
                captured_via_provider_id="vodniputovi_hr",
                inclusion_reason="official Croatian waterways feed identifies the three Danube gauges",
            ))
            for item in series:
                if not isinstance(item, dict) or "datum" not in item:
                    raise SourceStructureError(f"Unexpected record for Croatian station {source_key!r}")
                observed_date = self._date(str(item["datum"]))
                level = parse_optional_float(item.get("vodostaj"))
                if level is None:
                    continue
                latest_date = max(latest_date or date.min, date.fromisoformat(observed_date))
                observations.append(ObservationRecord(
                    station_id=sid, source_station_id=source_id,
                    operator_provider_id="dhmz_hr", source_provider_id="vodniputovi_hr",
                    captured_via_provider_id="vodniputovi_hr", parameter="water_level",
                    value=level, unit="cm", measurement_time_original=str(item["datum"]),
                    measurement_timezone=None, measurement_datetime_local=None,
                    measurement_datetime_utc=None, measurement_date=observed_date,
                    source_file_sha256=payload.sha256,
                ))

        issues: list[ValidationIssue] = []
        status = "complete"
        capture_date = datetime.fromisoformat(payload.captured_at_utc.replace("Z", "+00:00")).date()
        if latest_date is None or (capture_date - latest_date).days > 7:
            status = "suspended"
            issues.append(ValidationIssue(
                "critical", "stale_source",
                f"Latest Croatian observation is {latest_date}; capture date is {capture_date}",
            ))
        result = AdapterResult(
            source_id=self.source_id, country_code="HR", status=status,
            stations=stations, observations=observations, forecasts=[], issues=issues,
            source_station_count=len(document),
            notes=[
                "The source exposes dates but no observation time or timezone; neither is inferred.",
                "Coordinates are absent from the audited official feed and remain unset.",
                "A feed older than seven days is suspended rather than published as current data.",
            ],
        )
        return self.validate(result)
