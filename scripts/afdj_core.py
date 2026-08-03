"""Nucleul pipeline-ului AFDJ: download, validare, arhivare și publicare.

Modulul folosește numai biblioteca standard Python pentru a rămâne ușor de
rulat în GitHub Actions și local. Valorile brute sunt păstrate separat de cele
normalizate, iar identificatorul stației este întotdeauna UUID-ul sursei.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import re
import shutil
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


XML_URL = "https://www.afdj.ro/ro/tabel_cotele_dunarii/xml"
HTML_URL = "https://www.afdj.ro/ro/cotele-dunarii"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 25
MAX_ATTEMPTS = 3
BUCHAREST = ZoneInfo("Europe/Bucharest")
LEAD_HOURS = (24, 48, 72, 96, 120)

CRITICAL_PATHS = (
    "uuid/value",
    "nid/value",
    "field_localitatea/value",
    "field_km/value",
    "field_cota/value",
    "field_variatia/value",
    "field_temperatura_masurata/value",
    "field_field_data_actualiz_cote/value",
    "field_geolocation_demo_single/lat",
    "field_geolocation_demo_single/lng",
    "field_data_actualizare_prognoze/value",
    "field_tendinta_24h/value",
    "field_tendinta_48h/value",
    "field_tendinta_72h/value",
    "field_tendinta_96h/value",
    "field_tendinta_120h/value",
)

STATION_FIELDS = [
    "station_id", "station_nid", "source_name", "display_name", "slug",
    "river_km", "latitude", "longitude", "path_alias", "first_seen_at",
    "last_seen_at", "active",
]
OBSERVATION_FIELDS = [
    "station_id", "station_nid", "source_name", "display_name",
    "river_km_raw", "river_km", "latitude", "longitude",
    "measurement_datetime_raw", "measurement_datetime", "measurement_date",
    "level_raw", "level_cm", "variation_raw", "variation_cm_24h",
    "temperature_raw", "water_temperature_c", "capture_datetime_utc",
    "capture_datetime_local", "source_changed_datetime", "record_hash",
    "first_seen_at", "last_seen_at", "normalization_source", "quality_flag",
]
FORECAST_FIELDS = [
    "station_id", "station_nid", "forecast_issue_datetime",
    "forecast_issue_date", "target_datetime", "target_date", "lead_hours",
    "forecast_level_raw", "forecast_level_cm", "forecast_available",
    "availability_source", "html_value_raw", "xml_html_match",
    "capture_datetime_utc", "capture_datetime_local", "forecast_run_hash",
    "first_seen_at", "last_seen_at", "quality_flag",
]
SCORE_FIELDS = [
    "station_id", "lead_hours", "n_pairs", "mean_signed_error_cm", "mae_cm",
    "rmse_cm", "bias_cm", "within_5cm_pct", "within_10cm_pct",
    "within_20cm_pct", "first_date", "last_date", "maturity",
]
CORRECTION_FIELDS = [
    "entity_type", "logical_key", "field_name", "old_value", "new_value",
    "detected_at_utc", "source_capture_sha256",
]
RUN_FIELDS = [
    "run_id", "started_at_utc", "capture_datetime_utc", "capture_datetime_local",
    "status", "source", "requested_xml_url", "final_xml_url", "xml_http_status",
    "xml_content_type", "xml_size_bytes", "xml_sha256", "xml_archive_path",
    "xml_archive_created", "html_http_status", "html_content_type",
    "html_size_bytes", "html_sha256", "html_parse_success", "station_count",
    "observation_date", "forecast_issue_date", "ambiguous_zero_count",
    "xml_html_mismatch_count", "schema_change", "canonical_changed", "message",
]
SCHEMA_CHANGE_FIELDS = [
    "detected_at_utc", "xml_sha256", "added_leaf_paths", "removed_leaf_paths",
    "added_tags", "removed_tags", "critical_removed", "severity",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def ensure_project_directories(root: Path) -> None:
    for relative in (
        "data/archive/raw_xml", "data/archive/flat_raw", "data/archive/diagnostics",
        "data/canonical", "data/daily", "data/station_csv", "data/schema",
        "data/public/station", "public/data",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def identity_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value)).casefold()
    return "".join(ch for ch in text if not unicodedata.combining(ch) and ch.isalnum())


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", clean_text(value)).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "statie"


def parse_decimal(value: Any, *, integer_grouping: bool = False) -> Decimal | None:
    text = clean_text(value).replace("\u00a0", " ")
    if not text:
        return None
    text = re.sub(r"(?i)°\s*c|℃|\b(?:cm|km|mm)\b", "", text).strip()
    match = re.search(r"[+-]?(?:\d[\d\s.,]*|[.,]\d+)", text)
    if not match:
        return None
    number = re.sub(r"\s+", "", match.group(0))
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):
            number = number.replace(".", "").replace(",", ".")
        else:
            number = number.replace(",", "")
    elif "," in number:
        parts = number.split(",")
        number = "".join(parts[:-1]) + "." + parts[-1] if len(parts) > 2 else number.replace(",", ".")
    elif "." in number and integer_grouping:
        unsigned = number.lstrip("+-")
        parts = unsigned.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            sign = "-" if number.startswith("-") else "+" if number.startswith("+") else ""
            number = sign + "".join(parts)
    try:
        parsed = Decimal(number)
        return parsed if parsed.is_finite() else None
    except InvalidOperation:
        return None


def number_text(value: Decimal | None) -> str:
    if value is None:
        return ""
    return str(int(value)) if value == value.to_integral_value() else format(value.normalize(), "f")


def number_json(value: Any) -> int | float | None:
    parsed = value if isinstance(value, Decimal) else parse_decimal(value)
    if parsed is None:
        return None
    return int(parsed) if parsed == parsed.to_integral_value() else float(parsed)


def parse_source_datetime(value: Any) -> datetime | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=BUCHAREST) if parsed.tzinfo is None else parsed
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=BUCHAREST)
        except ValueError:
            continue
    match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y").replace(tzinfo=BUCHAREST)
        except ValueError:
            return None
    return None


def download(url: str, expected_mime: tuple[str, ...]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/xml,text/xml,text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Referer": HTML_URL,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = response.read()
                status = int(response.status)
                headers = {key: value for key, value in response.headers.items()}
                final_url = response.geturl()
            content_type = headers.get("Content-Type", "")
            mime = content_type.split(";", 1)[0].strip().casefold()
            if not 200 <= status < 300:
                raise RuntimeError(f"HTTP {status} pentru {url}")
            if not any(fragment in mime for fragment in expected_mime):
                raise RuntimeError(f"Content-Type neașteptat {content_type!r} pentru {url}")
            if not body:
                raise RuntimeError(f"Răspuns gol pentru {url}")
            return {
                "body": body, "requested_url": url, "final_url": final_url,
                "status": status, "headers": headers, "attempts": attempt,
                "sha256": sha256_bytes(body), "size_bytes": len(body),
            }
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {408, 425, 429} and not 500 <= exc.code <= 599:
                raise RuntimeError(f"HTTP {exc.code} {exc.reason} pentru {url}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if isinstance(exc, RuntimeError) and "Content-Type" in str(exc):
                raise
        if attempt < MAX_ATTEMPTS:
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Descărcarea {url} a eșuat după {MAX_ATTEMPTS} încercări: {last_error}")


def element_value(parent: ET.Element, path: str) -> str:
    element = parent.find(path)
    return "" if element is None or element.text is None else element.text


def parse_xml(xml_bytes: bytes) -> tuple[ET.Element, list[ET.Element]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValueError(f"XML invalid: {exc}") from exc
    if local_name(root.tag) != "response":
        raise ValueError(f"Root XML neașteptat: {root.tag!r}; era așteptat 'response'")
    items = [child for child in list(root) if local_name(child.tag) == "item"]
    if not items:
        raise ValueError("XML-ul nu conține noduri /response/item")
    return root, items


def flatten_item(item: ET.Element) -> dict[str, str]:
    output: dict[str, str] = {}

    def walk(element: ET.Element, path: str) -> None:
        for attr_name, attr_value in element.attrib.items():
            output[f"{path}@{local_name(attr_name)}"] = attr_value
        children = list(element)
        if not children:
            output[path] = element.text or ""
            return
        totals = Counter(local_name(child.tag) for child in children)
        seen: Counter[str] = Counter()
        for child in children:
            name = local_name(child.tag)
            seen[name] += 1
            suffix = f"[{seen[name]}]" if totals[name] > 1 else ""
            walk(child, f"{path}/{name}{suffix}")

    walk(item, "item")
    return output


def flatten_xml(xml_bytes: bytes) -> tuple[list[dict[str, str]], list[str]]:
    _root, items = parse_xml(xml_bytes)
    rows = [flatten_item(item) for item in items]
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for column in row:
            if column not in seen:
                seen.add(column)
                columns.append(column)
    return rows, columns


def xml_schema(xml_bytes: bytes, rows: list[dict[str, str]], columns: list[str]) -> dict[str, Any]:
    root, items = parse_xml(xml_bytes)
    tag_counts = Counter(local_name(element.tag) for element in root.iter())
    attribute_counts: Counter[str] = Counter()
    for element in root.iter():
        for attribute in element.attrib:
            attribute_counts[f"{local_name(element.tag)}@{local_name(attribute)}"] += 1
    return {
        "schema_version": 1,
        "root": local_name(root.tag),
        "station_node": "item",
        "station_count": len(items),
        "leaf_paths": columns,
        "tag_counts": dict(sorted(tag_counts.items())),
        "attribute_counts": dict(sorted(attribute_counts.items())),
        "critical_paths": list(CRITICAL_PATHS),
        "critical_paths_present": {
            path: all(f"item/{path}" in row for row in rows) for path in CRITICAL_PATHS
        },
        "xml_sha256": sha256_bytes(xml_bytes),
    }


def compare_schemas(previous: dict[str, Any] | None, current: dict[str, Any], detected_at: str) -> dict[str, str]:
    if not previous:
        return {
            "detected_at_utc": detected_at,
            "xml_sha256": current["xml_sha256"],
            "added_leaf_paths": json.dumps(current["leaf_paths"], ensure_ascii=False),
            "removed_leaf_paths": "[]",
            "added_tags": json.dumps(sorted(current["tag_counts"]), ensure_ascii=False),
            "removed_tags": "[]",
            "critical_removed": "[]",
            "severity": "initial_schema",
        }
    old_paths = set(previous.get("leaf_paths", []))
    new_paths = set(current.get("leaf_paths", []))
    old_tags = set(previous.get("tag_counts", {}))
    new_tags = set(current.get("tag_counts", {}))
    removed = sorted(old_paths - new_paths)
    critical_removed = sorted(
        path for path in CRITICAL_PATHS if f"item/{path}" in old_paths and f"item/{path}" not in new_paths
    )
    return {
        "detected_at_utc": detected_at,
        "xml_sha256": current["xml_sha256"],
        "added_leaf_paths": json.dumps(sorted(new_paths - old_paths), ensure_ascii=False),
        "removed_leaf_paths": json.dumps(removed, ensure_ascii=False),
        "added_tags": json.dumps(sorted(new_tags - old_tags), ensure_ascii=False),
        "removed_tags": json.dumps(sorted(old_tags - new_tags), ensure_ascii=False),
        "critical_removed": json.dumps(critical_removed, ensure_ascii=False),
        "severity": "critical" if critical_removed else "warning" if removed else "info" if new_paths - old_paths else "unchanged",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]], *, gzip_output: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {"mode": "wt", "encoding": "utf-8-sig", "newline": ""}
    stream_context = gzip.open(path, **kwargs) if gzip_output else path.open(**kwargs)
    with stream_context as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def append_csv(path: Path, fields: list[str], row: dict[str, Any]) -> None:
    rows = read_csv(path)
    rows.append({key: "" if value is None else str(value) for key, value in row.items()})
    write_csv(path, fields, rows)


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=None if compact else 2, separators=(",", ":") if compact else None) + "\n",
        encoding="utf-8",
    )


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.depth = 0
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows = []
        elif self.depth == 1 and tag == "tr":
            self.row = []
        elif self.depth == 1 and tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.depth == 1 and tag in {"td", "th"} and self.cell is not None:
            assert self.row is not None
            self.row.append(clean_text("".join(self.cell)))
            self.cell = None
        elif self.depth == 1 and tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.depth:
            if self.depth == 1:
                self.tables.append(self.rows)
            self.depth -= 1


def header_role(value: str) -> str | None:
    token = identity_text(value)
    if token.startswith("localitat"):
        return "localitate"
    if token == "km" or token.startswith("kmsorteaz"):
        return "km"
    if token in {"nivelulapei", "cota", "nivel"}:
        return "cota"
    if token.startswith("variati"):
        return "variatie"
    if token.startswith("temperatur"):
        return "temperatura"
    if token.startswith("dataactualizareprognoz"):
        return "forecast_issue_date"
    if token.startswith("dataactualizarenivel"):
        return "measurement_date"
    for hours in LEAD_HOURS:
        if token == f"{hours}h":
            return f"forecast_{hours}h"
    return None


def parse_html_forecasts(html_bytes: bytes) -> dict[str, Any]:
    parser = TableParser()
    parser.feed(html_bytes.decode("utf-8", errors="replace"))
    for table in parser.tables:
        for header_index, headers in enumerate(table):
            roles = [header_role(header) for header in headers]
            if not {"localitate", "km", "cota"}.issubset(set(roles)):
                continue
            records: list[dict[str, str]] = []
            for cells in table[header_index + 1:]:
                record: dict[str, str] = {}
                for index, value in enumerate(cells[: len(roles)]):
                    role = roles[index]
                    if role:
                        record[role] = value
                if record.get("localitate"):
                    records.append(record)
            if records:
                return {
                    "success": True,
                    "method": "semantic_table_headers",
                    "headers": headers,
                    "records": records,
                    "reason": "",
                }
    return {
        "success": False,
        "method": "semantic_table_headers",
        "headers": [],
        "records": [],
        "reason": "Nu a fost găsit tabelul cu antete semantice localitate/km/cotă.",
    }


def forecast_availability(xml_raw: str, html_raw: str | None, html_parse_success: bool) -> dict[str, Any]:
    xml_number = parse_decimal(xml_raw, integer_grouping=True)
    html_number = parse_decimal(html_raw, integer_grouping=True) if html_raw is not None else None
    html_blank = html_raw is not None and clean_text(html_raw) == ""
    if not html_parse_success:
        if xml_number == 0:
            return {
                "forecast_available": False, "forecast_level_cm": "",
                "availability_source": "xml_zero_html_unavailable", "html_value_raw": "",
                "xml_html_match": "", "quality_flag": "ambiguous_xml_zero_html_unavailable",
            }
        return {
            "forecast_available": xml_number is not None,
            "forecast_level_cm": number_text(xml_number),
            "availability_source": "xml_only_html_unavailable", "html_value_raw": "",
            "xml_html_match": "", "quality_flag": "html_validation_unavailable",
        }
    if xml_number is not None and html_number is not None:
        if xml_number == html_number:
            return {
                "forecast_available": True, "forecast_level_cm": number_text(xml_number),
                "availability_source": "xml_html_confirmed", "html_value_raw": html_raw or "",
                "xml_html_match": True, "quality_flag": "valid",
            }
        return {
            "forecast_available": True, "forecast_level_cm": number_text(xml_number),
            "availability_source": "xml_with_html_mismatch", "html_value_raw": html_raw or "",
            "xml_html_match": False, "quality_flag": "xml_html_value_mismatch",
        }
    if html_blank and xml_number == 0:
        return {
            "forecast_available": False, "forecast_level_cm": "",
            "availability_source": "html_blank_xml_zero", "html_value_raw": "",
            "xml_html_match": "", "quality_flag": "missing_forecast_encoded_as_zero",
        }
    if html_blank and xml_number is not None:
        return {
            "forecast_available": False, "forecast_level_cm": "",
            "availability_source": "html_blank_xml_nonzero", "html_value_raw": "",
            "xml_html_match": False, "quality_flag": "xml_html_availability_mismatch",
        }
    return {
        "forecast_available": False, "forecast_level_cm": "",
        "availability_source": "unparseable_value", "html_value_raw": html_raw or "",
        "xml_html_match": False, "quality_flag": "unparseable_forecast",
    }


def display_names(root: Path) -> dict[str, str]:
    return load_json(root / "config/station_display_names.json", {}) or {}


def station_records(
    items: list[ET.Element], capture_utc: datetime, capture_local: datetime, root: Path,
    html_result: dict[str, Any], xml_sha: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    names = display_names(root)
    html_by_name = {
        identity_text(record.get("localitate", "")): record for record in html_result.get("records", [])
    }
    stations: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    forecasts: list[dict[str, Any]] = []
    warnings: list[str] = []
    ids: set[str] = set()
    for item in items:
        station_id = clean_text(element_value(item, "uuid/value"))
        station_nid = clean_text(element_value(item, "nid/value"))
        source_name = element_value(item, "field_localitatea/value")
        display_name = names.get(source_name, source_name)
        km_raw = element_value(item, "field_km/value")
        level_raw = element_value(item, "field_cota/value")
        variation_raw = element_value(item, "field_variatia/value")
        temperature_raw = element_value(item, "field_temperatura_masurata/value")
        measurement_raw = element_value(item, "field_field_data_actualiz_cote/value")
        issue_raw = element_value(item, "field_data_actualizare_prognoze/value")
        latitude_raw = element_value(item, "field_geolocation_demo_single/lat")
        longitude_raw = element_value(item, "field_geolocation_demo_single/lng")
        path_alias = element_value(item, "path/alias")
        source_changed = element_value(item, "changed/value")
        measurement_dt = parse_source_datetime(measurement_raw)
        issue_dt = parse_source_datetime(issue_raw)
        km = parse_decimal(km_raw, integer_grouping=True)
        level = parse_decimal(level_raw, integer_grouping=True)
        variation = parse_decimal(variation_raw, integer_grouping=True)
        temperature = parse_decimal(temperature_raw)
        latitude = parse_decimal(latitude_raw)
        longitude = parse_decimal(longitude_raw)
        missing = [
            name for name, value in {
                "uuid": station_id, "localitate": source_name, "km": km,
                "cota": level, "variatie": variation, "temperatura": temperature,
                "data_masuratoare": measurement_dt, "latitudine": latitude,
                "longitudine": longitude, "data_prognoza": issue_dt,
            }.items() if value in (None, "")
        ]
        if missing:
            raise ValueError(f"Câmpuri critice lipsă/neparseabile pentru {source_name or station_nid}: {', '.join(missing)}")
        assert measurement_dt and issue_dt and km is not None and level is not None
        assert variation is not None and temperature is not None and latitude is not None and longitude is not None
        if station_id in ids:
            raise ValueError(f"UUID duplicat în captură: {station_id}")
        ids.add(station_id)
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError(f"Coordonate invalide pentru {source_name}: {latitude}, {longitude}")
        now_text = iso_utc(capture_utc)
        station = {
            "station_id": station_id, "station_nid": station_nid,
            "source_name": source_name, "display_name": display_name,
            "slug": slugify(source_name), "river_km": number_text(km),
            "latitude": number_text(latitude), "longitude": number_text(longitude),
            "path_alias": path_alias, "first_seen_at": now_text,
            "last_seen_at": now_text, "active": True,
        }
        stations.append(station)
        observation_material = {
            "station_id": station_id, "measurement_datetime": measurement_dt.isoformat(),
            "level_cm": number_text(level), "variation_cm_24h": number_text(variation),
            "water_temperature_c": number_text(temperature), "river_km": number_text(km),
            "latitude": number_text(latitude), "longitude": number_text(longitude),
        }
        observations.append({
            "station_id": station_id, "station_nid": station_nid,
            "source_name": source_name, "display_name": display_name,
            "river_km_raw": km_raw, "river_km": number_text(km),
            "latitude": number_text(latitude), "longitude": number_text(longitude),
            "measurement_datetime_raw": measurement_raw,
            "measurement_datetime": measurement_dt.isoformat(),
            "measurement_date": measurement_dt.date().isoformat(),
            "level_raw": level_raw, "level_cm": number_text(level),
            "variation_raw": variation_raw, "variation_cm_24h": number_text(variation),
            "temperature_raw": temperature_raw,
            "water_temperature_c": number_text(temperature),
            "capture_datetime_utc": now_text,
            "capture_datetime_local": capture_local.isoformat(),
            "source_changed_datetime": source_changed,
            "record_hash": stable_hash(observation_material),
            "first_seen_at": now_text, "last_seen_at": now_text,
            "normalization_source": "AFDJ XML + reguli documentate",
            "quality_flag": "valid",
        })
        html_row = html_by_name.get(identity_text(source_name))
        if html_result.get("success") and html_row is None:
            warnings.append(f"Stația {source_name} lipsește din tabelul HTML")
        forecast_material: list[dict[str, Any]] = []
        for lead in LEAD_HOURS:
            raw = element_value(item, f"field_tendinta_{lead}h/value")
            html_raw = html_row.get(f"forecast_{lead}h", "") if html_row is not None else None
            availability = forecast_availability(raw, html_raw, bool(html_result.get("success")))
            target = issue_dt + timedelta(hours=lead)
            material = {
                "station_id": station_id, "issue": issue_dt.isoformat(),
                "lead": lead, "raw": raw, **availability,
            }
            forecast_material.append(material)
            forecasts.append({
                "station_id": station_id, "station_nid": station_nid,
                "forecast_issue_datetime": issue_dt.isoformat(),
                "forecast_issue_date": issue_dt.date().isoformat(),
                "target_datetime": target.isoformat(), "target_date": target.date().isoformat(),
                "lead_hours": lead, "forecast_level_raw": raw,
                "forecast_level_cm": availability["forecast_level_cm"],
                "forecast_available": availability["forecast_available"],
                "availability_source": availability["availability_source"],
                "html_value_raw": availability["html_value_raw"],
                "xml_html_match": availability["xml_html_match"],
                "capture_datetime_utc": now_text,
                "capture_datetime_local": capture_local.isoformat(),
                "forecast_run_hash": "", "first_seen_at": now_text,
                "last_seen_at": now_text, "quality_flag": availability["quality_flag"],
            })
        run_hash = stable_hash({"xml": xml_sha, "issue": issue_dt.isoformat(), "values": forecast_material})
        for row in forecasts[-len(LEAD_HOURS):]:
            row["forecast_run_hash"] = run_hash
    return stations, observations, forecasts, warnings


def upsert_rows(
    path: Path, fields: list[str], incoming: list[dict[str, Any]], key_fields: tuple[str, ...],
    entity_type: str, corrections_path: Path, detected_at: str, capture_sha: str,
) -> tuple[int, int, bool]:
    existing = read_csv(path)
    index = {tuple(row.get(field, "") for field in key_fields): row for row in existing}
    inserted = updated = 0
    changed = False
    corrections = read_csv(corrections_path)
    ignored = {"first_seen_at", "last_seen_at", "capture_datetime_utc", "capture_datetime_local"}
    for raw_row in incoming:
        row = {field: "" if raw_row.get(field) is None else str(raw_row.get(field)) for field in fields}
        key = tuple(row.get(field, "") for field in key_fields)
        old = index.get(key)
        if old is None:
            existing.append(row)
            index[key] = row
            inserted += 1
            changed = True
            continue
        material_changes = [field for field in fields if field not in ignored and old.get(field, "") != row.get(field, "")]
        if material_changes:
            for field in material_changes:
                corrections.append({
                    "entity_type": entity_type,
                    "logical_key": json.dumps(dict(zip(key_fields, key)), ensure_ascii=False, sort_keys=True),
                    "field_name": field, "old_value": old.get(field, ""),
                    "new_value": row.get(field, ""), "detected_at_utc": detected_at,
                    "source_capture_sha256": capture_sha,
                })
            first_seen = old.get("first_seen_at", row.get("first_seen_at", ""))
            old.update(row)
            if "first_seen_at" in fields:
                old["first_seen_at"] = first_seen
            updated += 1
            changed = True
    existing.sort(key=lambda row: tuple(row.get(field, "") for field in key_fields))
    write_csv(path, fields, existing)
    write_csv(corrections_path, CORRECTION_FIELDS, corrections)
    return inserted, updated, changed


def archive_html_diagnostic(root: Path, html_bytes: bytes, capture_utc: datetime, reason: str) -> str:
    filename = capture_utc.strftime("%Y-%m-%dT%H%M%SZ") + "-" + slugify(reason)[:48] + ".html.gz"
    path = root / "data/archive/diagnostics" / filename
    with gzip.open(path, "wb") as stream:
        stream.write(html_bytes)
    return str(path.relative_to(root)).replace("\\", "/")


def run_ingestion(
    root: Path, xml_result: dict[str, Any], html_result_http: dict[str, Any], *,
    source: str = "live", capture_utc: datetime | None = None,
) -> dict[str, Any]:
    ensure_project_directories(root)
    capture_utc = (capture_utc or utc_now()).astimezone(timezone.utc).replace(microsecond=0)
    capture_local = capture_utc.astimezone(BUCHAREST)
    captured_utc_text = iso_utc(capture_utc)
    run_id = capture_utc.strftime("%Y%m%dT%H%M%SZ") + "-" + xml_result["sha256"][:10]
    xml_bytes = xml_result["body"]
    html_bytes = html_result_http["body"]
    run_path = root / "data/canonical/ingestion_runs.csv"
    corrections_path = root / "data/canonical/corrections.csv"
    previous_runs = read_csv(run_path)
    previous_success = next((row for row in reversed(previous_runs) if row.get("status") == "success"), None)
    archive_created = not previous_success or previous_success.get("xml_sha256") != xml_result["sha256"]
    archive_relative = ""
    if archive_created:
        relative = Path("data/archive/raw_xml") / capture_utc.strftime("%Y/%m") / (capture_utc.strftime("%Y-%m-%dT%H%M%SZ") + ".xml.gz")
        archive_path = root / relative
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(archive_path, "wb") as stream:
            stream.write(xml_bytes)
        archive_relative = str(relative).replace("\\", "/")
    elif previous_success:
        archive_relative = previous_success.get("xml_archive_path", "")

    base_run: dict[str, Any] = {
        "run_id": run_id, "started_at_utc": captured_utc_text,
        "capture_datetime_utc": captured_utc_text,
        "capture_datetime_local": capture_local.isoformat(), "status": "failed",
        "source": source, "requested_xml_url": xml_result.get("requested_url", XML_URL),
        "final_xml_url": xml_result.get("final_url", XML_URL),
        "xml_http_status": xml_result.get("status", ""),
        "xml_content_type": xml_result.get("headers", {}).get("Content-Type", ""),
        "xml_size_bytes": len(xml_bytes), "xml_sha256": xml_result["sha256"],
        "xml_archive_path": archive_relative, "xml_archive_created": archive_created,
        "html_http_status": html_result_http.get("status", ""),
        "html_content_type": html_result_http.get("headers", {}).get("Content-Type", ""),
        "html_size_bytes": len(html_bytes), "html_sha256": html_result_http["sha256"],
        "html_parse_success": False, "station_count": 0, "observation_date": "",
        "forecast_issue_date": "", "ambiguous_zero_count": 0,
        "xml_html_mismatch_count": 0, "schema_change": "", "canonical_changed": False,
        "message": "",
    }
    try:
        _xml_root, items = parse_xml(xml_bytes)
        flat_rows, flat_columns = flatten_xml(xml_bytes)
        current_schema = xml_schema(xml_bytes, flat_rows, flat_columns)
        previous_schema = load_json(root / "data/schema/current_schema.json")
        schema_change = compare_schemas(previous_schema, current_schema, captured_utc_text)
        base_run["schema_change"] = schema_change["severity"]
        missing_critical = [path for path, present in current_schema["critical_paths_present"].items() if not present]
        if missing_critical:
            raise ValueError("Căi critice lipsă: " + ", ".join(missing_critical))
        if previous_success and clean_text(previous_success.get("station_count")):
            previous_count = int(previous_success["station_count"])
            if previous_count and len(items) < previous_count * 0.8:
                raise ValueError(f"Numărul stațiilor a scăzut de la {previous_count} la {len(items)} (>20%).")

        html_parsed = parse_html_forecasts(html_bytes)
        base_run["html_parse_success"] = html_parsed["success"]
        stations, observations, forecasts, warnings = station_records(
            items, capture_utc, capture_local, root, html_parsed, xml_result["sha256"]
        )
        if html_parsed["success"] and len(html_parsed["records"]) != len(stations):
            warnings.append(f"Număr stații diferit XML={len(stations)}, HTML={len(html_parsed['records'])}")
        ambiguous = sum(row["quality_flag"] in {"missing_forecast_encoded_as_zero", "ambiguous_xml_zero_html_unavailable"} for row in forecasts)
        mismatches = sum(row["quality_flag"] in {"xml_html_availability_mismatch", "xml_html_value_mismatch"} for row in forecasts)
        diagnostic_reasons = []
        if not html_parsed["success"]:
            diagnostic_reasons.append("html-parse-failed")
        if mismatches:
            diagnostic_reasons.append("xml-html-mismatch")
        if html_parsed["success"] and len(html_parsed["records"]) != len(stations):
            diagnostic_reasons.append("station-count-mismatch")
        if diagnostic_reasons:
            archive_html_diagnostic(root, html_bytes, capture_utc, "-".join(diagnostic_reasons))

        flat_path = root / "data/archive/flat_raw" / capture_local.strftime("%Y/%m") / (capture_local.strftime("%Y-%m-%d") + ".csv.gz")
        write_csv(flat_path, flat_columns, flat_rows, gzip_output=True)
        write_json(root / "data/schema/current_schema.json", {**current_schema, "updated_at_utc": captured_utc_text})
        write_csv(
            root / "data/schema/current_tag_counts.csv", ["tag", "count"],
            [{"tag": tag, "count": count} for tag, count in current_schema["tag_counts"].items()],
        )
        changes_path = root / "data/schema/schema_changes.csv"
        previous_changes = read_csv(changes_path)
        if not previous_changes:
            previous_changes.append(compare_schemas(None, current_schema, captured_utc_text))
        elif schema_change["severity"] != "unchanged":
            previous_changes.append(schema_change)
        write_csv(changes_path, SCHEMA_CHANGE_FIELDS, previous_changes)

        station_path = root / "data/canonical/stations.csv"
        existing_stations = read_csv(station_path)
        current_ids = {row["station_id"] for row in stations}
        for old in existing_stations:
            if old.get("station_id") not in current_ids:
                stale = dict(old)
                stale["active"] = False
                stations.append(stale)
        station_stats = upsert_rows(
            station_path, STATION_FIELDS, stations, ("station_id",), "station",
            corrections_path, captured_utc_text, xml_result["sha256"],
        )
        observation_stats = upsert_rows(
            root / "data/canonical/observations.csv", OBSERVATION_FIELDS, observations,
            ("station_id", "measurement_datetime"), "observation", corrections_path,
            captured_utc_text, xml_result["sha256"],
        )
        forecast_stats = upsert_rows(
            root / "data/canonical/forecasts.csv", FORECAST_FIELDS, forecasts,
            ("station_id", "forecast_issue_datetime", "lead_hours"), "forecast",
            corrections_path, captured_utc_text, xml_result["sha256"],
        )
        observation_date = max(row["measurement_date"] for row in observations)
        forecast_issue_date = max(row["forecast_issue_date"] for row in forecasts)
        daily_rows = [row for row in observations if row["measurement_date"] == observation_date]
        write_csv(root / f"data/daily/{observation_date}.csv", OBSERVATION_FIELDS, daily_rows)
        canonical_changed = any(stats[2] for stats in (station_stats, observation_stats, forecast_stats))
        base_run.update({
            "status": "success", "station_count": len(items),
            "observation_date": observation_date, "forecast_issue_date": forecast_issue_date,
            "ambiguous_zero_count": ambiguous, "xml_html_mismatch_count": mismatches,
            "canonical_changed": canonical_changed,
            "message": "; ".join(warnings) if warnings else "Captură procesată cu succes.",
        })
    except Exception as exc:
        archive_html_diagnostic(root, html_bytes, capture_utc, "ingestion-failed")
        base_run["message"] = f"{type(exc).__name__}: {exc}"
        append_csv(run_path, RUN_FIELDS, base_run)
        raise
    append_csv(run_path, RUN_FIELDS, base_run)
    return base_run


def calculate_scores(root: Path) -> list[dict[str, Any]]:
    observations = read_csv(root / "data/canonical/observations.csv")
    forecasts = read_csv(root / "data/canonical/forecasts.csv")
    observed = {
        (row["station_id"], row["measurement_date"]): parse_decimal(row["level_cm"])
        for row in observations if parse_decimal(row.get("level_cm")) is not None
    }
    errors: dict[tuple[str, str], list[tuple[str, Decimal]]] = defaultdict(list)
    for forecast in forecasts:
        if forecast.get("forecast_available", "").casefold() != "true":
            continue
        value = parse_decimal(forecast.get("forecast_level_cm"))
        actual = observed.get((forecast["station_id"], forecast["target_date"]))
        if value is not None and actual is not None:
            errors[(forecast["station_id"], forecast["lead_hours"])].append((forecast["target_date"], value - actual))
    station_ids = sorted({row["station_id"] for row in forecasts})
    rows: list[dict[str, Any]] = []
    for station_id in station_ids:
        for lead in LEAD_HOURS:
            values = errors.get((station_id, str(lead)), [])
            n = len(values)
            signed = [value for _target, value in values]
            mae = sum(abs(value) for value in signed) / n if n else None
            rmse = Decimal(str(math.sqrt(float(sum(value * value for value in signed) / n)))) if n else None
            bias = sum(signed) / n if n else None
            maturity = "Date insuficiente" if n < 10 else "Rezultate preliminare" if n < 30 else "Rezultate consolidate"
            rows.append({
                "station_id": station_id, "lead_hours": lead, "n_pairs": n,
                "mean_signed_error_cm": number_text(bias), "mae_cm": number_text(mae),
                "rmse_cm": number_text(rmse), "bias_cm": number_text(bias),
                "within_5cm_pct": number_text(Decimal(100 * sum(abs(v) <= 5 for v in signed)) / n if n else None),
                "within_10cm_pct": number_text(Decimal(100 * sum(abs(v) <= 10 for v in signed)) / n if n else None),
                "within_20cm_pct": number_text(Decimal(100 * sum(abs(v) <= 20 for v in signed)) / n if n else None),
                "first_date": min((target for target, _value in values), default=""),
                "last_date": max((target for target, _value in values), default=""),
                "maturity": maturity,
            })
    write_csv(root / "data/canonical/forecast_scores.csv", SCORE_FIELDS, rows)
    return rows


def json_record(row: dict[str, str], numeric_fields: set[str], boolean_fields: set[str] = set()) -> dict[str, Any]:
    output: dict[str, Any] = dict(row)
    for field in numeric_fields:
        if field in output:
            output[field] = number_json(output[field]) if clean_text(output[field]) else None
    for field in boolean_fields:
        if field in output:
            output[field] = output[field].casefold() == "true"
    return output


def build_public_data(root: Path) -> dict[str, Any]:
    ensure_project_directories(root)
    stations = read_csv(root / "data/canonical/stations.csv")
    observations = read_csv(root / "data/canonical/observations.csv")
    forecasts = read_csv(root / "data/canonical/forecasts.csv")
    scores = read_csv(root / "data/canonical/forecast_scores.csv")
    runs = read_csv(root / "data/canonical/ingestion_runs.csv")
    if not stations or not observations or not runs:
        raise ValueError("Date canonice insuficiente; rulați mai întâi ingest_afdj.py")
    latest_by_station: dict[str, dict[str, str]] = {}
    for row in observations:
        old = latest_by_station.get(row["station_id"])
        if old is None or row["measurement_datetime"] > old["measurement_datetime"]:
            latest_by_station[row["station_id"]] = row
    latest = sorted(latest_by_station.values(), key=lambda row: float(row["river_km"] or 0))
    public = root / "data/public"
    write_csv(public / "latest.csv", OBSERVATION_FIELDS, latest)
    write_csv(public / "observations.csv", OBSERVATION_FIELDS, observations)
    write_csv(public / "forecasts.csv", FORECAST_FIELDS, forecasts)
    write_csv(public / "stations.csv", STATION_FIELDS, stations)
    station_index = {row["station_id"]: row for row in stations}
    features = []
    for row in latest:
        station = station_index[row["station_id"]]
        features.append({
            "type": "Feature",
            "id": row["station_id"],
            "geometry": {"type": "Point", "coordinates": [float(row["longitude"]), float(row["latitude"])]},
            "properties": {
                "station_id": row["station_id"], "slug": station["slug"],
                "source_name": row["source_name"], "display_name": row["display_name"],
                "river_km": number_json(row["river_km"]), "level_cm": number_json(row["level_cm"]),
                "variation_cm_24h": number_json(row["variation_cm_24h"]),
                "water_temperature_c": number_json(row["water_temperature_c"]),
                "measurement_datetime": row["measurement_datetime"],
                "quality_flag": row["quality_flag"],
            },
        })
    write_json(public / "latest.geojson", {"type": "FeatureCollection", "features": features}, compact=True)
    latest_run = next(row for row in reversed(runs) if row.get("status") == "success")
    variations = [parse_decimal(row["variation_cm_24h"]) for row in latest]
    status = {
        "title": "Nivelul Dunării",
        "system_status": "operational" if latest_run.get("xml_html_mismatch_count", "0") == "0" else "warning",
        "station_count": len(latest),
        "rising_count": sum(value is not None and value > 0 for value in variations),
        "falling_count": sum(value is not None and value < 0 for value in variations),
        "stationary_count": sum(value == 0 for value in variations),
        "stale_or_missing_count": sum(row.get("quality_flag") != "valid" for row in latest),
        "latest_measurement_datetime": max(row["measurement_datetime"] for row in latest),
        "latest_measurement_date": max(row["measurement_date"] for row in latest),
        "latest_forecast_issue_datetime": max((row["forecast_issue_datetime"] for row in forecasts), default=""),
        "latest_forecast_issue_date": max((row["forecast_issue_date"] for row in forecasts), default=""),
        "last_capture_datetime_utc": latest_run["capture_datetime_utc"],
        "last_capture_datetime_local": latest_run["capture_datetime_local"],
        "archive_start_date": min(row["measurement_date"] for row in observations),
        "observation_count": len(observations), "forecast_count": len(forecasts),
        "ambiguous_zero_count": int(latest_run.get("ambiguous_zero_count") or 0),
        "xml_html_mismatch_count": int(latest_run.get("xml_html_mismatch_count") or 0),
        "source_xml": XML_URL, "source_html": HTML_URL,
        "timezone": "Europe/Bucharest",
        "disclaimer": "Aplicație informativă; nu înlocuiește comunicările oficiale AFDJ.",
    }
    write_json(public / "status.json", status, compact=True)
    download_entries = [
        {"label": "Situația curentă", "path": "latest.csv", "format": "CSV"},
        {"label": "Toate observațiile", "path": "observations.csv", "format": "CSV"},
        {"label": "Toate prognozele", "path": "forecasts.csv", "format": "CSV"},
        {"label": "Registrul stațiilor", "path": "stations.csv", "format": "CSV"},
        {"label": "Situația geospațială", "path": "latest.geojson", "format": "GeoJSON"},
    ]
    for station in stations:
        station_id = station["station_id"]
        slug = station["slug"]
        station_observations = [row for row in observations if row["station_id"] == station_id]
        station_forecasts = [row for row in forecasts if row["station_id"] == station_id]
        station_scores = [row for row in scores if row["station_id"] == station_id]
        observation_json = [json_record(row, {"river_km", "latitude", "longitude", "level_cm", "variation_cm_24h", "water_temperature_c"}) for row in station_observations]
        forecast_json = [json_record(row, {"lead_hours", "forecast_level_cm"}, {"forecast_available"}) for row in station_forecasts]
        score_json = [json_record(row, {"lead_hours", "n_pairs", "mean_signed_error_cm", "mae_cm", "rmse_cm", "bias_cm", "within_5cm_pct", "within_10cm_pct", "within_20cm_pct"}) for row in station_scores]
        write_json(public / f"station/{slug}-observations.json", observation_json, compact=True)
        write_json(public / f"station/{slug}-forecasts.json", forecast_json, compact=True)
        write_json(public / f"station/{slug}-forecast-scores.json", score_json, compact=True)
        combined_fields = ["record_type", "station_id", "display_name", "datetime", "date", "lead_hours", "level_cm", "variation_cm_24h", "water_temperature_c", "quality_flag"]
        combined: list[dict[str, Any]] = []
        combined.extend({
            "record_type": "observation", "station_id": row["station_id"],
            "display_name": row["display_name"], "datetime": row["measurement_datetime"],
            "date": row["measurement_date"], "lead_hours": "", "level_cm": row["level_cm"],
            "variation_cm_24h": row["variation_cm_24h"], "water_temperature_c": row["water_temperature_c"],
            "quality_flag": row["quality_flag"],
        } for row in station_observations)
        combined.extend({
            "record_type": "forecast", "station_id": row["station_id"],
            "display_name": station["display_name"], "datetime": row["target_datetime"],
            "date": row["target_date"], "lead_hours": row["lead_hours"],
            "level_cm": row["forecast_level_cm"], "variation_cm_24h": "",
            "water_temperature_c": "", "quality_flag": row["quality_flag"],
        } for row in station_forecasts)
        write_csv(public / f"station/{slug}.csv", combined_fields, combined)
        write_csv(root / f"data/station_csv/{slug}.csv", combined_fields, combined)
        download_entries.append({"label": f"{station['display_name']} — istoric combinat", "path": f"station/{slug}.csv", "format": "CSV"})
    write_json(public / "downloads.json", download_entries, compact=True)
    destination = root / "public/data"
    destination.mkdir(parents=True, exist_ok=True)
    for path in public.rglob("*"):
        if path.is_file():
            target = destination / path.relative_to(public)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return status


def validate_repository(root: Path) -> dict[str, Any]:
    required = [
        "public/index.html", "public/assets/css/app.css", "public/assets/js/app.js",
        "data/public/status.json", "data/public/latest.geojson",
        "data/public/stations.csv", "data/public/observations.csv",
        "data/public/forecasts.csv", "data/schema/current_schema.json",
    ]
    missing = [path for path in required if not (root / path).is_file()]
    if missing:
        raise ValueError("Fișiere obligatorii lipsă: " + ", ".join(missing))
    status = load_json(root / "data/public/status.json")
    geojson = load_json(root / "data/public/latest.geojson")
    if geojson.get("type") != "FeatureCollection":
        raise ValueError("latest.geojson nu este FeatureCollection")
    features = geojson.get("features", [])
    if len(features) != status.get("station_count"):
        raise ValueError("Numărul de stații diferă între status și GeoJSON")
    if any(feature.get("geometry", {}).get("coordinates") in (None, []) for feature in features):
        raise ValueError("Există stații fără coordonate în GeoJSON")
    observations = read_csv(root / "data/canonical/observations.csv")
    forecasts = read_csv(root / "data/canonical/forecasts.csv")
    if len({(r["station_id"], r["measurement_datetime"]) for r in observations}) != len(observations):
        raise ValueError("Observații canonice duplicate")
    if len({(r["station_id"], r["forecast_issue_datetime"], r["lead_hours"]) for r in forecasts}) != len(forecasts):
        raise ValueError("Prognoze canonice duplicate")
    downloads = load_json(root / "data/public/downloads.json", [])
    broken = [item["path"] for item in downloads if not (root / "data/public" / item["path"]).is_file()]
    if broken:
        raise ValueError("Linkuri de download invalide: " + ", ".join(broken))
    return {
        "ok": True, "stations": len(features), "observations": len(observations),
        "forecasts": len(forecasts), "downloads": len(downloads),
    }

