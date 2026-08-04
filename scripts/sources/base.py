"""Shared contracts and fail-closed validation for international adapters."""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import ssl
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

USER_AGENT = "NivelDunareMonitor/1.0 (+https://github.com/mariusbudileanu/nivel-dunare)"
ADAPTER_VERSION = "1.0.0"
BLOCK_MARKERS = (
    "attention required", "sorry, you have been blocked", "just a moment",
    "checking your browser", "enable javascript and cookies", "cf-mitigated",
)

COUNTRY_BOUNDS = {
    "DE": (47.0, 55.5, 5.0, 16.0),
    "AT": (46.0, 49.5, 9.0, 18.0),
    "SK": (47.5, 49.7, 16.5, 22.7),
    "HU": (45.5, 49.0, 16.0, 23.0),
    "HR": (42.0, 47.0, 13.0, 20.5),
    "BG": (41.0, 45.0, 22.0, 29.5),
    "RO": (43.0, 49.0, 20.0, 30.5),
    "RS": (41.5, 47.0, 18.0, 23.5),
}

CYRILLIC_MAP = str.maketrans({
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L",
    "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S",
    "Т": "T", "У": "U", "Ф": "F", "Х": "H", "Ц": "Ts", "Ч": "Ch",
    "Ш": "Sh", "Щ": "Sht", "Ъ": "A", "Ь": "", "Ю": "Yu", "Я": "Ya",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "sht", "ъ": "a", "ь": "", "ю": "yu", "я": "ya",
})


class AdapterError(RuntimeError):
    """Base exception for adapter failures."""


class SourceAccessError(AdapterError):
    """The source could not be downloaded safely."""


class SourceStructureError(AdapterError):
    """The response does not match the demonstrated structure."""


@dataclass(frozen=True)
class SourceRequest:
    label: str
    url: str
    expected_format: str
    accept: str


@dataclass(frozen=True)
class FetchedPayload:
    label: str
    url: str
    status: int
    content_type: str
    body: bytes
    captured_at_utc: str
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


@dataclass
class StationRecord:
    station_id: str
    source_station_id: str | None
    country_code: str
    station_name: str
    station_name_local: str
    station_slug: str
    river_name: str
    latitude: float | None
    longitude: float | None
    coordinate_source: str | None
    coordinate_method: str
    coordinate_confidence: str
    source_url: str
    active: bool | None
    last_verified_at: str
    operator_provider_id: str
    source_provider_id: str
    captured_via_provider_id: str
    river_km: float | None = None
    included: bool = True
    inclusion_reason: str = "official Danube station"
    station_type: str = "gauge"


@dataclass
class ObservationRecord:
    station_id: str
    source_station_id: str | None
    operator_provider_id: str
    source_provider_id: str
    captured_via_provider_id: str
    parameter: str
    value: float
    unit: str
    measurement_time_original: str
    measurement_timezone: str | None
    measurement_datetime_local: str | None
    measurement_datetime_utc: str | None
    measurement_date: str | None
    source_file_sha256: str
    source_quality_code: str | None = None
    canonical_quality_flag: str = "observed"
    variation_value: float | None = None
    variation_window_hours: int | None = None


@dataclass
class ForecastRecord:
    station_id: str
    source_station_id: str | None
    operator_provider_id: str
    source_provider_id: str
    captured_via_provider_id: str
    forecast_parameter: str | None
    forecast_value: float
    forecast_unit: str | None
    forecast_issue_time_original: str | None
    forecast_issue_datetime_utc: str | None
    target_time_original: str
    target_datetime_utc: str | None
    target_date: str | None
    lead_hours: int | None
    source_file_sha256: str
    forecast_min_value: float | None = None
    forecast_max_value: float | None = None


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    record_id: str | None = None


@dataclass
class AdapterResult:
    source_id: str
    country_code: str
    status: str
    stations: list[StationRecord]
    observations: list[ObservationRecord]
    forecasts: list[ForecastRecord]
    issues: list[ValidationIssue] = field(default_factory=list)
    source_station_count: int = 0
    excluded_station_count: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def publishable(self) -> bool:
        return self.status == "complete" and not any(i.severity == "critical" for i in self.issues)

    @property
    def usable_observations(self) -> list[ObservationRecord]:
        return [
            observation for observation in self.observations
            if observation.canonical_quality_flag not in {"suspect", "missing"}
        ]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["publishable"] = self.publishable
        result["usable_observation_count"] = len(self.usable_observations)
        result["suspect_observation_count"] = sum(
            observation.canonical_quality_flag == "suspect"
            for observation in self.observations
        )
        return result


def transliterate(value: str) -> str:
    value = value.translate(CYRILLIC_MAP)
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def canonical_station_name(value: str) -> str:
    clean = re.sub(r"\s+", " ", transliterate(html.unescape(value))).strip()
    return clean


def station_slug(country_code: str, value: str, qualifier: str | None = None) -> str:
    base = canonical_station_name(value).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    suffix = f"-{qualifier}" if qualifier else ""
    return f"{country_code.lower()}-{base}{suffix}"


def parse_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    text = html.unescape(str(value)).strip()
    if not text or text in {"//", "-", "—", "N/A", "n/a", "null"}:
        return None
    return float(text.replace(" ", "").replace(",", "."))


def iso_from_milliseconds(value: int | float) -> str:
    return datetime.fromtimestamp(float(value) / 1000.0, timezone.utc).isoformat()


def normalize_iso_datetime(value: str) -> tuple[str | None, str | None]:
    """Return local-with-offset and UTC; never invent an offset."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return value, None
    return parsed.isoformat(), parsed.astimezone(timezone.utc).isoformat()


class TableCollector(HTMLParser):
    """Small tolerant HTML table/select collector used by the HTML adapters."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[dict[str, Any]] = []
        self.options: list[tuple[str, str]] = []
        self._table: dict[str, Any] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._caption: list[str] | None = None
        self._option_value: str | None = None
        self._option_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            self._table = {"attrs": attributes, "caption": "", "rows": []}
        elif tag == "caption" and self._table is not None:
            self._caption = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag == "option":
            self._option_value = attributes.get("value") or ""
            self._option_text = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        if self._caption is not None:
            self._caption.append(data)
        if self._option_text is not None:
            self._option_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(re.sub(r"\s+", " ", "".join(self._cell)).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table["rows"].append(self._row)
            self._row = None
        elif tag == "caption" and self._caption is not None and self._table is not None:
            self._table["caption"] = re.sub(r"\s+", " ", "".join(self._caption)).strip()
            self._caption = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag == "option" and self._option_text is not None:
            text = re.sub(r"\s+", " ", "".join(self._option_text)).strip()
            self.options.append((self._option_value or "", text))
            self._option_value = None
            self._option_text = None


class SourceAdapter:
    source_id = "abstract"
    provider_id = "abstract"
    country_code = "XX"
    expected_min_stations = 1
    default_status = "complete"
    stale_after_days: int | None = None
    stale_status = "partial"

    def initial_requests(self) -> list[SourceRequest]:
        raise NotImplementedError

    def additional_requests(self, payloads: dict[str, FetchedPayload]) -> list[SourceRequest]:
        return []

    def parse(self, payloads: dict[str, FetchedPayload]) -> AdapterResult:
        raise NotImplementedError

    @staticmethod
    def capture_time(payloads: dict[str, FetchedPayload]) -> datetime:
        if not payloads:
            return datetime.now(timezone.utc)
        captured = [
            datetime.fromisoformat(payload.captured_at_utc.replace("Z", "+00:00"))
            for payload in payloads.values()
        ]
        return max(
            value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
            for value in captured
        )

    @staticmethod
    def _append_quality_code(current: str | None, code: str) -> str:
        codes = [item for item in (current or "").split(";") if item]
        if code not in codes:
            codes.append(code)
        return ";".join(codes)

    def validate(self, result: AdapterResult, now: datetime | None = None) -> AdapterResult:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
        issues = list(result.issues)
        included = [station for station in result.stations if station.included]
        if len(included) < self.expected_min_stations:
            issues.append(ValidationIssue("critical", "mass_station_loss", f"Expected at least {self.expected_min_stations} included stations, got {len(included)}"))

        seen_ids: set[str] = set()
        seen_slugs: set[tuple[str, str]] = set()
        for station in result.stations:
            if station.station_id in seen_ids:
                issues.append(ValidationIssue("critical", "duplicate_station_id", station.station_id, station.station_id))
            seen_ids.add(station.station_id)
            slug_key = (station.country_code, station.station_slug)
            if slug_key in seen_slugs:
                issues.append(ValidationIssue("critical", "duplicate_station_slug", station.station_slug, station.station_id))
            seen_slugs.add(slug_key)
            if station.country_code not in COUNTRY_BOUNDS:
                issues.append(ValidationIssue("critical", "invalid_country", station.country_code, station.station_id))
            if station.included and not station.source_station_id:
                issues.append(ValidationIssue("critical", "missing_source_station_id", "Official stable station identifier unavailable", station.station_id))
            if (station.latitude is None) != (station.longitude is None):
                issues.append(ValidationIssue("critical", "incomplete_coordinates", "Both latitude and longitude are required", station.station_id))
            if station.latitude is not None and station.longitude is not None:
                if not (-90 <= station.latitude <= 90 and -180 <= station.longitude <= 180):
                    issues.append(ValidationIssue("critical", "coordinate_range", "Coordinates outside EPSG:4326", station.station_id))
                bounds = COUNTRY_BOUNDS[station.country_code]
                if not (bounds[0] <= station.latitude <= bounds[1] and bounds[2] <= station.longitude <= bounds[3]):
                    issues.append(ValidationIssue("critical", "coordinate_country", "Coordinates incompatible with country bounds", station.station_id))

        observation_dates: list[date] = []
        for observation in result.observations:
            if observation.station_id not in seen_ids:
                issues.append(ValidationIssue(
                    "critical", "orphan_observation",
                    "Observation references a station_id absent from this adapter result",
                    observation.station_id,
                ))
            limits = {"water_level": (-5000, 5000), "discharge": (0, 100000), "water_temperature": (-5, 45)}
            canonical_units = {"water_level": "cm", "discharge": "m3/s", "water_temperature": "degC"}
            if observation.parameter not in limits:
                issues.append(ValidationIssue("critical", "unknown_parameter", observation.parameter, observation.station_id))
            else:
                low, high = limits[observation.parameter]
                if not low <= observation.value <= high:
                    if observation.parameter == "water_temperature":
                        quality_code = "outside_plausible_water_temperature_range"
                        observation.canonical_quality_flag = "suspect"
                        observation.source_quality_code = self._append_quality_code(
                            observation.source_quality_code, quality_code,
                        )
                        if not any(
                            issue.code == quality_code and issue.record_id == observation.station_id
                            for issue in issues
                        ):
                            issues.append(ValidationIssue(
                                "warning", quality_code,
                                f"water_temperature={observation.value} {observation.unit}; raw value preserved but excluded from usable current temperatures",
                                observation.station_id,
                            ))
                    else:
                        issues.append(ValidationIssue("critical", "impossible_value", f"{observation.parameter}={observation.value}", observation.station_id))
                if observation.unit != canonical_units[observation.parameter]:
                    issues.append(ValidationIssue("critical", "unit_change", f"Expected {canonical_units[observation.parameter]}, got {observation.unit}", observation.station_id))
            if observation.measurement_datetime_utc:
                try:
                    measured = datetime.fromisoformat(observation.measurement_datetime_utc.replace("Z", "+00:00"))
                    if measured.tzinfo is None:
                        raise ValueError("UTC datetime has no offset")
                    measured = measured.astimezone(timezone.utc)
                    observation_dates.append(measured.date())
                    if measured > now + timedelta(hours=24):
                        issues.append(ValidationIssue("critical", "future_timestamp", observation.measurement_datetime_utc, observation.station_id))
                except ValueError:
                    issues.append(ValidationIssue("critical", "invalid_measurement_datetime", observation.measurement_datetime_utc, observation.station_id))
            elif observation.measurement_date:
                try:
                    measured_date = date.fromisoformat(observation.measurement_date)
                    observation_dates.append(measured_date)
                    if measured_date > now.date():
                        issues.append(ValidationIssue("critical", "future_measurement_date", observation.measurement_date, observation.station_id))
                except ValueError:
                    issues.append(ValidationIssue("critical", "invalid_measurement_date", observation.measurement_date, observation.station_id))

        if self.stale_after_days is not None and observation_dates:
            latest_date = max(observation_dates)
            age_days = (now.date() - latest_date).days
            if age_days > self.stale_after_days:
                issues.append(ValidationIssue(
                    "critical", "stale_source",
                    f"Latest observation date {latest_date.isoformat()} is {age_days} days old; limit is {self.stale_after_days}",
                ))
                result.status = self.stale_status

        for forecast in result.forecasts:
            if forecast.station_id not in seen_ids:
                issues.append(ValidationIssue(
                    "critical", "orphan_forecast",
                    "Forecast references a station_id absent from this adapter result",
                    forecast.station_id,
                ))
            if forecast.forecast_parameter not in {"water_level", "discharge", None}:
                issues.append(ValidationIssue("critical", "unknown_forecast_parameter", str(forecast.forecast_parameter), forecast.station_id))
            if forecast.forecast_min_value is not None and forecast.forecast_min_value > forecast.forecast_value:
                issues.append(ValidationIssue("critical", "forecast_interval", "minimum exceeds central value", forecast.station_id))
            if forecast.forecast_max_value is not None and forecast.forecast_max_value < forecast.forecast_value:
                issues.append(ValidationIssue("critical", "forecast_interval", "maximum below central value", forecast.station_id))

        result.issues = issues
        if any(issue.severity == "critical" for issue in issues):
            result.status = "suspended" if result.status == "suspended" else "partial"
        return result


def ensure_payload(payload: FetchedPayload, expected_format: str) -> None:
    if payload.status != 200:
        raise SourceAccessError(f"{payload.label}: HTTP {payload.status}")
    if not payload.body:
        raise SourceAccessError(f"{payload.label}: empty response")
    prefix = payload.body[:4096].decode("utf-8", "ignore").lower()
    if any(marker in prefix for marker in BLOCK_MARKERS):
        raise SourceAccessError(f"{payload.label}: anti-bot/block page detected")
    stripped = payload.body.lstrip()
    if expected_format == "json" and not stripped.startswith((b"{", b"[")):
        raise SourceStructureError(f"{payload.label}: expected JSON, got {payload.content_type}")
    if expected_format == "html" and b"<html" not in stripped[:1000].lower() and b"<!doctype html" not in stripped[:1000].lower():
        raise SourceStructureError(f"{payload.label}: expected HTML, got {payload.content_type}")


def fetch_request(request: SourceRequest, timeout: float = 30.0) -> FetchedPayload:
    headers = {"User-Agent": USER_AGENT, "Accept": request.accept, "Accept-Encoding": "identity"}
    req = urllib.request.Request(request.url, headers=headers, method="GET")
    captured = datetime.now(timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
            payload = FetchedPayload(
                label=request.label, url=response.geturl(), status=response.status,
                content_type=response.headers.get("Content-Type", ""), body=response.read(),
                captured_at_utc=captured, headers=dict(response.headers.items()),
            )
    except urllib.error.HTTPError as exc:
        payload = FetchedPayload(request.label, exc.geturl(), exc.code, exc.headers.get("Content-Type", ""), exc.read(), captured, dict(exc.headers.items()))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SourceAccessError(f"{request.label}: {type(exc).__name__}: {exc}") from exc
    return payload


def redact_url(url: str) -> str:
    """Redact credential-like query values before persistent metadata is written."""
    parsed = urllib.parse.urlsplit(url)
    sensitive = {"viadonau_partner_key", "api_key", "apikey", "token", "access_token"}
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    redacted = [(key, "[REDACTED]" if key.casefold() in sensitive else value) for key, value in query]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment))


def archive_payload(payload: FetchedPayload, archive_root: Path, source_id: str) -> dict[str, Any]:
    captured = datetime.fromisoformat(payload.captured_at_utc.replace("Z", "+00:00"))
    folder = archive_root / source_id / f"{captured.year:04d}" / f"{captured.month:02d}"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = captured.strftime("%Y%m%dT%H%M%SZ")
    safe_label = re.sub(r"[^a-z0-9-]+", "-", payload.label.lower()).strip("-")
    raw_path = folder / f"{stamp}-{safe_label}.raw.gz"
    metadata_path = folder / f"{stamp}-{safe_label}.metadata.json"
    with gzip.open(raw_path, "wb") as handle:
        handle.write(payload.body)
    metadata = {
        "source": source_id, "label": payload.label, "url": redact_url(payload.url),
        "captured_at_utc": payload.captured_at_utc, "http_status": payload.status,
        "content_type": payload.content_type, "content_sha256": payload.sha256,
        "content_bytes": len(payload.body), "adapter_version": ADAPTER_VERSION,
        "raw_file": raw_path.name,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**metadata, "raw_path": str(raw_path), "metadata_path": str(metadata_path)}


def write_result(result: AdapterResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    complete = result.to_dict()
    for name in ("stations", "observations", "forecasts", "issues"):
        value = complete.pop(name)
        (output_dir / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(complete, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_fixture_payloads(directory: Path) -> dict[str, FetchedPayload]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    payloads: dict[str, FetchedPayload] = {}
    for item in manifest["payloads"]:
        body = (directory / item["file"]).read_bytes()
        payloads[item["label"]] = FetchedPayload(
            label=item["label"], url=item["url"], status=item.get("status", 200),
            content_type=item["content_type"], body=body,
            captured_at_utc=manifest["captured_at_utc"], headers={},
        )
    return payloads


def json_load(payload: FetchedPayload) -> Any:
    ensure_payload(payload, "json")
    try:
        return json.loads(payload.body)
    except json.JSONDecodeError as exc:
        raise SourceStructureError(f"{payload.label}: invalid JSON: {exc}") from exc


def decode_payload_text(payload: FetchedPayload) -> str:
    charset_match = re.search(r"charset=([\w-]+)", payload.content_type, re.I)
    candidates = [charset_match.group(1)] if charset_match else []
    candidates.extend(["utf-8", "iso-8859-2"])
    last_error: UnicodeDecodeError | None = None
    for charset in dict.fromkeys(candidates):
        try:
            return payload.body.decode(charset, "strict")
        except UnicodeDecodeError as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def html_tables(payload: FetchedPayload) -> TableCollector:
    ensure_payload(payload, "html")
    text = decode_payload_text(payload)
    parser = TableCollector()
    parser.feed(text)
    return parser


def payload_text(payload: FetchedPayload) -> str:
    return decode_payload_text(payload)


def unique_by(items: Iterable[Any], key: Any) -> list[Any]:
    seen: set[Any] = set()
    result: list[Any] = []
    for item in items:
        value = key(item)
        if value not in seen:
            seen.add(value)
            result.append(item)
    return result
