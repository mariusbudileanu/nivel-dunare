"""PEGELONLINE REST v2 adapter for German Danube stations."""

from __future__ import annotations

from .base import (
    AdapterResult, ObservationRecord, SourceAdapter, SourceRequest, SourceStructureError,
    StationRecord, canonical_station_name, json_load, normalize_iso_datetime,
    parse_optional_float, station_slug,
)


class PegelonlineAdapter(SourceAdapter):
    source_id = "pegelonline_de"
    provider_id = "pegelonline_de"
    country_code = "DE"
    expected_min_stations = 18
    url = (
        "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json"
        "?waters=DONAU&includeTimeseries=true&includeCurrentMeasurement=true"
    )

    def initial_requests(self) -> list[SourceRequest]:
        return [SourceRequest("stations", self.url, "json", "application/json")]

    def parse(self, payloads):
        payload = payloads["stations"]
        data = json_load(payload)
        if not isinstance(data, list):
            raise SourceStructureError("PEGELONLINE stations payload must be a JSON array")

        stations: list[StationRecord] = []
        observations: list[ObservationRecord] = []
        excluded = 0
        verified = payload.captured_at_utc[:10]
        parameter_map = {"W": "water_level", "Q": "discharge", "WT": "water_temperature"}

        for item in data:
            water = item.get("water") or {}
            if str(water.get("shortname", "")).upper() != "DONAU":
                excluded += 1
                continue
            if str(item.get("agency", "")).upper() == "VIA DONAU":
                excluded += 1
                continue
            source_id = str(item.get("uuid") or "").strip()
            local_name = str(item.get("longname") or item.get("shortname") or "").strip()
            if not source_id or not local_name:
                raise SourceStructureError("PEGELONLINE station lost uuid/name")
            canonical = canonical_station_name(local_name)
            sid = f"de-{source_id}"
            latitude = parse_optional_float(item.get("latitude"))
            longitude = parse_optional_float(item.get("longitude"))
            station_url = f"https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations/{source_id}.json"
            stations.append(StationRecord(
                station_id=sid, source_station_id=source_id, country_code="DE",
                station_name=canonical, station_name_local=local_name,
                station_slug=station_slug("DE", local_name), river_name="Danube",
                latitude=latitude, longitude=longitude,
                coordinate_source=station_url if latitude is not None else None,
                coordinate_method="official_rest_payload" if latitude is not None else "unavailable",
                coordinate_confidence="high" if latitude is not None else "unavailable",
                source_url=station_url, active=True, last_verified_at=verified,
                operator_provider_id="pegelonline_de", source_provider_id="pegelonline_de",
                captured_via_provider_id="pegelonline_de", river_km=parse_optional_float(item.get("km")),
                inclusion_reason="water.shortname=DONAU and agency is a German WSV office",
            ))
            for series in item.get("timeseries") or []:
                series_code = str(series.get("shortname", "")).upper()
                parameter = parameter_map.get(series_code)
                measurement = series.get("currentMeasurement") or {}
                if not parameter or measurement.get("value") is None:
                    continue
                timestamp = str(measurement.get("timestamp") or "")
                if not timestamp:
                    raise SourceStructureError(f"PEGELONLINE {source_id} measurement lost timestamp")
                local_time, utc_time = normalize_iso_datetime(timestamp)
                source_unit = str(series.get("unit") or "").strip()
                allowed_source_units = {"W": {"cm"}, "Q": {"m³/s", "m3/s"}, "WT": {"°C", "degC"}}
                if source_unit not in allowed_source_units[series_code]:
                    raise SourceStructureError(f"PEGELONLINE {source_id} unexpected {series_code} unit: {source_unit!r}")
                canonical_unit = {"W": "cm", "Q": "m3/s", "WT": "degC"}[series_code]
                observations.append(ObservationRecord(
                    station_id=sid, source_station_id=source_id,
                    operator_provider_id="pegelonline_de", source_provider_id="pegelonline_de",
                    captured_via_provider_id="pegelonline_de", parameter=parameter,
                    value=float(measurement["value"]), unit=canonical_unit,
                    measurement_time_original=timestamp, measurement_timezone="source ISO-8601 offset",
                    measurement_datetime_local=local_time, measurement_datetime_utc=utc_time,
                    measurement_date=None, source_file_sha256=payload.sha256,
                    source_quality_code=";".join(filter(None, [
                        f"source_unit={source_unit}",
                        str(measurement.get("stateMnwMhw") or ""),
                        str(measurement.get("stateNswHsw") or ""),
                    ])) or None,
                ))

        result = AdapterResult(
            source_id=self.source_id, country_code=self.country_code, status="complete",
            stations=stations, observations=observations, forecasts=[],
            source_station_count=len(data), excluded_station_count=excluded,
            notes=["Rows with agency=VIA DONAU are republished Austrian stations and are excluded from the German primary adapter."],
        )
        return self.validate(result)
