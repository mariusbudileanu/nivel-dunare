"""Croatian waterways/DHMZ JSON adapter for the Danube gauges."""

from __future__ import annotations

from datetime import datetime

from .base import (
    AdapterResult, ObservationRecord, SourceAdapter, SourceRequest, SourceStructureError,
    StationRecord, canonical_station_name, json_load, parse_optional_float, station_slug,
)
from .reference import apply_ris_reference


class VodniputoviAdapter(SourceAdapter):
    source_id = "vodniputovi_hr"
    provider_id = "vodniputovi_hr"
    country_code = "HR"
    expected_min_stations = 3
    stale_after_days = 7
    stale_status = "partial"
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
        for source_key, (source_id, local_name) in self.station_metadata.items():
            series = document.get(source_key)
            if not isinstance(series, list) or not series:
                raise SourceStructureError(f"Croatian station {source_key!r} is missing or empty")
            sid = f"hr-{source_id}"
            station = apply_ris_reference(StationRecord(
                station_id=sid, source_station_id=source_id, country_code="HR",
                station_name=canonical_station_name(local_name),
                station_name_local=local_name, station_slug=station_slug("HR", local_name),
                river_name="Danube", latitude=None, longitude=None, coordinate_source=None,
                coordinate_method="unresolved", coordinate_confidence="unavailable",
                source_url=self.current_url, active=True, last_verified_at=payload.captured_at_utc[:10],
                operator_provider_id="dhmz_hr", source_provider_id="vodniputovi_hr",
                captured_via_provider_id="vodniputovi_hr",
                inclusion_reason="official Croatian waterways feed identifies the three Danube gauges",
                source_stream_type="daily", observation_frequency="daily",
            ))
            stations.append(station)
            for item in series:
                if not isinstance(item, dict) or "datum" not in item:
                    raise SourceStructureError(f"Unexpected record for Croatian station {source_key!r}")
                observed_date = self._date(str(item["datum"]))
                level = parse_optional_float(item.get("vodostaj"))
                if level is None:
                    continue
                observations.append(ObservationRecord(
                    station_id=sid, source_station_id=source_id,
                    operator_provider_id="dhmz_hr", source_provider_id="vodniputovi_hr",
                    captured_via_provider_id="vodniputovi_hr", parameter="water_level",
                    value=level, unit="cm", measurement_time_original=str(item["datum"]),
                    measurement_timezone=None, measurement_datetime_local=None,
                    measurement_datetime_utc=None, measurement_date=observed_date,
                    source_file_sha256=payload.sha256,
                    physical_station_id=station.physical_station_id,
                    source_stream_id=station.source_stream_id,
                    source_stream_type="daily", is_primary_stream=True,
                    observation_frequency="daily", observation_time_precision="date",
                    source_observation_date=observed_date,
                    source_observation_time_raw=str(item["datum"]),
                ))

        result = AdapterResult(
            source_id=self.source_id, country_code="HR", status="complete",
            stations=stations, observations=observations, forecasts=[],
            source_station_count=len(document),
            notes=[
                "The source exposes dates but no observation time or timezone; neither is inferred.",
                "Coordinates and RIS identifiers come from the versioned Croatian RIS Index registry.",
                "A feed older than seven days remains available as stale last-known-good data and is not presented as current.",
                "No numeric forecast is published because the feed does not demonstrate forecast values.",
            ],
        )
        return self.validate(result, self.capture_time(payloads))
