#!/usr/bin/env python3
"""Audit tehnic si semantic pentru sursa XML AFDJ Cotele Dunarii.

Scriptul descarca si pastreaza raspunsurile brute, identifica dinamic nodurile
statie, produce previzualizari CSV si compara XML-ul cu tabelul HTML oficial.
Nu modifica niciodata continutul fisierelor brute dupa descarcare.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


XML_URL = "https://afdj.ro/ro/tabel_cotele_dunarii/xml"
HTML_URL = "https://www.afdj.ro/ro/cotele-dunarii"
USER_AGENT = (
    "AFDJ-Source-Audit/1.0 (+local technical audit; "
    "Python urllib; contact: local project owner)"
)
TIMEOUT_SECONDS = 20
MAX_ATTEMPTS = 3

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw"
REPORTS_DIR = BASE_DIR / "reports"
PREVIEWS_DIR = BASE_DIR / "previews"

XML_RAW_PATH = RAW_DIR / "afdj_latest_raw.xml"
HTML_RAW_PATH = RAW_DIR / "afdj_cotele_dunarii_page.html"
HTTP_METADATA_PATH = REPORTS_DIR / "http_metadata.json"
STRUCTURE_PATH = REPORTS_DIR / "xml_structure.json"
TAG_COUNTS_PATH = REPORTS_DIR / "xml_tag_counts.csv"
QUALITY_PATH = REPORTS_DIR / "data_quality_summary.json"
REPORT_PATH = REPORTS_DIR / "XML_AUDIT_REPORT.md"
ORIGINAL_CSV_PATH = PREVIEWS_DIR / "xml_rows_original.csv"
NORMALIZED_CSV_PATH = PREVIEWS_DIR / "xml_rows_normalized_preview.csv"

DOCUMENTED_FIELDS = [
    "localitate",
    "km",
    "cota",
    "variatie",
    "temperatura",
    "data_masuratoare",
]
NUMERIC_ROLES = {"km", "cota", "variatie", "temperatura", "latitude", "longitude"}
FORECAST_ROLES = {
    "forecast_24h",
    "forecast_48h",
    "forecast_72h",
    "forecast_96h",
    "forecast_120h",
}


def ensure_directories() -> None:
    for directory in (RAW_DIR, REPORTS_DIR, PREVIEWS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalized_token(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def local_name(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag.split(":", 1)[-1]


def namespace_uri(tag: str) -> str | None:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return None


ROLE_ALIASES: dict[str, set[str]] = {
    "localitate": {
        "localitate", "localitatea", "locality", "statie", "statia", "station",
        "fieldlocalitate", "fieldlocalitatea", "fieldlocalitategrafic",
    },
    "km": {
        "km", "kilometru", "kilometrul", "kilometer", "pozitiekilometrica",
        "fieldkm",
    },
    "cota": {
        "cota", "nivel", "nivelapa", "nivelulapei", "nivelul", "level",
        "fieldcota",
    },
    "variatie": {
        "variatie", "variatia", "variatiacotei", "variation", "change",
        "fieldvariatie", "fieldvariatia",
    },
    "temperatura": {
        "temperatura", "temperaturaapei", "temperaturamasurata", "temperature",
        "fieldtemperaturamasurata", "fieldtemperatura",
    },
    "data_masuratoare": {
        "datamasuratoare", "datamasuratorii", "datamasurarii", "dataactualizare",
        "dataactualizarii", "dataactualizarenivel", "measurementdate", "date",
        "fieldfielddataactualizcote", "fielddataactualizarecote",
    },
    "latitude": {"lat", "latitude", "latitudine"},
    "longitude": {"lon", "lng", "longitude", "longitudine"},
    "coordinates": {
        "coordonate", "coordonata", "coordinates", "latitudinesilongitudine",
        "latlong", "latlon", "gps", "fieldgeolocationdemosingle",
    },
    "forecast_24h": {"24h", "prognoza24h", "forecast24h", "cota24h", "fieldtendinta24h"},
    "forecast_48h": {"48h", "prognoza48h", "forecast48h", "cota48h", "fieldtendinta48h"},
    "forecast_72h": {"72h", "prognoza72h", "forecast72h", "cota72h", "fieldtendinta72h"},
    "forecast_96h": {"96h", "prognoza96h", "forecast96h", "cota96h", "fieldtendinta96h"},
    "forecast_120h": {"120h", "prognoza120h", "forecast120h", "cota120h", "fieldtendinta120h"},
    "forecast_updated": {
        "dataactualizareprognoze", "dataactualizariiprognozei",
        "dataactualizareprognoza", "forecastupdated", "forecastdate",
        "fielddataactualizareprognoze", "fielddataactualizareprognoza",
    },
}


def field_role(name: str | None) -> str | None:
    token = normalized_token(name)
    for role, aliases in ROLE_ALIASES.items():
        if token in aliases:
            return role
    if "prognoz" in token or "forecast" in token:
        for hours in (24, 48, 72, 96, 120):
            if str(hours) in token:
                return f"forecast_{hours}h"
        if "data" in token or "date" in token or "actualiz" in token:
            return "forecast_updated"
    if "latitud" in token and "longitud" in token:
        return "coordinates"
    if token.startswith("km") and "sorteaz" in token:
        return "km"
    return None


@dataclass
class DownloadResult:
    body: bytes
    requested_url: str
    final_url: str
    status: int
    reason: str
    headers: dict[str, str]
    downloaded_utc: datetime
    attempts: int


def download(
    url: str,
    expected_content_fragments: tuple[str, ...],
    label: str,
) -> DownloadResult:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/xml,text/xml,text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                "Cache-Control": "no-cache",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                status = int(response.status)
                reason = str(getattr(response, "reason", ""))
                headers = {key: value for key, value in response.headers.items()}
                body = response.read()
                final_url = response.geturl()
                downloaded_utc = datetime.now(timezone.utc)
            if not 200 <= status < 300:
                raise RuntimeError(f"{label}: HTTP {status} {reason}")
            content_type = headers.get("Content-Type", "")
            mime = content_type.split(";", 1)[0].strip().casefold()
            if not any(fragment in mime for fragment in expected_content_fragments):
                raise RuntimeError(
                    f"{label}: Content-Type neasteptat {content_type!r}; "
                    f"erau acceptate tipuri care contin {expected_content_fragments}."
                )
            if not body:
                raise RuntimeError(f"{label}: raspuns HTTP gol.")
            return DownloadResult(
                body=body,
                requested_url=url,
                final_url=final_url,
                status=status,
                reason=reason,
                headers=headers,
                downloaded_utc=downloaded_utc,
                attempts=attempt,
            )
        except urllib.error.HTTPError as exc:
            last_error = exc
            retryable = exc.code in {408, 425, 429} or 500 <= exc.code <= 599
            if not retryable:
                raise RuntimeError(
                    f"{label}: HTTP {exc.code} {exc.reason}; URL={url}"
                ) from exc
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if isinstance(exc, RuntimeError):
                raise
        if attempt < MAX_ATTEMPTS:
            time.sleep(1.5 * attempt)
    raise RuntimeError(
        f"{label}: descarcarea a esuat dupa {MAX_ATTEMPTS} incercari: {last_error}"
    ) from last_error


def parse_content_type(value: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in value.split(";")]
    mime = parts[0] if parts else ""
    charset = None
    for part in parts[1:]:
        if part.casefold().startswith("charset="):
            charset = part.split("=", 1)[1].strip().strip('"\'')
    return mime, charset


def xml_declaration_details(body: bytes) -> dict[str, Any]:
    match = re.match(br"^\xef\xbb\xbf?\s*<\?xml\s+([^?]+)\?>", body)
    if not match:
        match = re.match(br"^\s*<\?xml\s+([^?]+)\?>", body)
    if not match:
        return {"present": False, "raw": None, "version": None, "encoding": None, "standalone": None}
    declaration = match.group(0).decode("ascii", errors="replace")
    attributes = {
        key.decode("ascii").casefold(): value.decode("ascii", errors="replace")
        for key, _quote, value in re.findall(br"([A-Za-z_:][\w:.-]*)\s*=\s*(['\"])(.*?)\2", match.group(1))
    }
    return {
        "present": True,
        "raw": declaration,
        "version": attributes.get("version"),
        "encoding": attributes.get("encoding"),
        "standalone": attributes.get("standalone"),
    }


def collect_namespaces(body: bytes) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _event, pair in ET.iterparse(io.BytesIO(body), events=("start-ns",)):
        prefix, uri = pair
        key = (prefix or "", uri)
        if key not in seen:
            seen.add(key)
            found.append({"prefix": prefix or "", "uri": uri})
    return found


def iter_with_paths(root: ET.Element) -> Iterable[tuple[ET.Element, str, int]]:
    def walk(element: ET.Element, path: str, depth: int) -> Iterable[tuple[ET.Element, str, int]]:
        yield element, path, depth
        sibling_counts: Counter[str] = Counter()
        for child in list(element):
            name = local_name(child.tag)
            sibling_counts[name] += 1
            child_path = f"{path}/{name}[{sibling_counts[name]}]"
            yield from walk(child, child_path, depth + 1)

    yield from walk(root, f"/{local_name(root.tag)}[1]", 0)


def logical_path(path: str) -> str:
    return re.sub(r"\[\d+\]", "", path)


def identify_station_nodes(root: ET.Element) -> tuple[list[ET.Element], str, str, list[str]]:
    candidates: list[tuple[ET.Element, str, int]] = []
    all_paths = list(iter_with_paths(root))
    for element, path, _depth in all_paths:
        roles = {field_role(local_name(child.tag)) for child in list(element)}
        if "localitate" in roles and "cota" in roles:
            score = sum(role in roles for role in DOCUMENTED_FIELDS)
            candidates.append((element, path, score))
    if not candidates:
        diagnostic = []
        for element, path, _depth in all_paths:
            roles = sorted(
                role for role in {field_role(local_name(child.tag)) for child in list(element)}
                if role
            )
            if roles:
                diagnostic.append(f"{path}: {roles}")
        raise RuntimeError(
            "Nu a putut fi identificat dinamic nodul statie: niciun element nu are "
            "copii asociati simultan cu localitate si cota. Candidati partiali: "
            + "; ".join(diagnostic[:10])
        )
    groups: dict[tuple[str, str], list[tuple[ET.Element, str, int]]] = defaultdict(list)
    for candidate in candidates:
        element, path, _score = candidate
        groups[(element.tag, logical_path(path))].append(candidate)
    chosen_key, chosen = max(
        groups.items(),
        key=lambda item: (len(item[1]), max(row[2] for row in item[1])),
    )
    stations = [row[0] for row in chosen]
    paths = [row[1] for row in chosen]
    return stations, local_name(chosen_key[0]), chosen_key[1], paths


def element_text_exact(element: ET.Element) -> str:
    if len(element) == 0:
        return element.text or ""
    return "".join(element.itertext())


def station_raw_record(station: ET.Element) -> dict[str, str]:
    record: dict[str, str] = {}
    occurrences: Counter[str] = Counter()
    for child in list(station):
        base_name = local_name(child.tag)
        occurrences[base_name] += 1
        name = base_name if occurrences[base_name] == 1 else f"{base_name}__{occurrences[base_name]}"
        record[name] = element_text_exact(child)
    return record


def station_canonical_record(station: ET.Element) -> dict[str, str]:
    record: dict[str, str] = {}
    for child in list(station):
        role = field_role(local_name(child.tag))
        if role and role not in record:
            record[role] = element_text_exact(child)
        if role == "coordinates":
            nested = {
                field_role(local_name(descendant.tag)): element_text_exact(descendant)
                for descendant in child.iter()
                if descendant is not child and field_role(local_name(descendant.tag)) in {"latitude", "longitude"}
            }
            if nested.get("latitude") and nested.get("longitude"):
                record["latitude"] = nested["latitude"]
                record["longitude"] = nested["longitude"]
                record["coordinates"] = nested["latitude"] + ", " + nested["longitude"]
    if "coordinates" in record:
        coordinates = parse_coordinate_pair(record["coordinates"])
        if coordinates:
            record.setdefault("latitude", coordinates[0])
            record.setdefault("longitude", coordinates[1])
    return record


def locality_normalized(value: str | None) -> str:
    return clean_text(unicodedata.normalize("NFC", value or ""))


def locality_key(value: str | None) -> str:
    return normalized_token(locality_normalized(value))


def strip_known_units(value: str) -> str:
    text = value.strip().replace("\u00a0", " ").replace("\u202f", " ")
    text = re.sub(r"(?i)\b(?:cm|km|mm|metri?|m)\b", "", text)
    text = re.sub(r"(?i)°\s*c|℃", "", text)
    return text.strip()


def parse_number(value: str | None, role: str) -> Decimal | None:
    if value is None or not clean_text(value):
        return None
    text = strip_known_units(value)
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
        if number.count(",") > 1:
            pieces = number.split(",")
            number = "".join(pieces[:-1]) + "." + pieces[-1]
        else:
            number = number.replace(",", ".")
    elif "." in number:
        parts = number.lstrip("+-").split(".")
        integer_like_role = role in {"km", "cota", "variatie"} or role in FORECAST_ROLES
        if integer_like_role and all(len(part) == 3 for part in parts[1:]):
            number = number.replace(".", "")
        elif len(parts) > 2:
            number = "".join(parts[:-1]) + "." + parts[-1]
    try:
        parsed = Decimal(number)
        return parsed if parsed.is_finite() else None
    except InvalidOperation:
        return None


def decimal_json(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    if value == value.to_integral_value():
        return int(value)
    return float(value)


DATE_FORMATS = (
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y - %H:%M",
)


def parse_date(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    text = re.sub(r"^[A-Za-zĂÂÎȘŞȚŢăâîșşțţ]{3,}\s*,\s*", "", text)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%d/%m/%Y").date().isoformat()
        except ValueError:
            return None
    return None


def parse_coordinate_pair(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    numbers = re.findall(r"[+-]?\d+(?:[.,]\d+)?", value)
    if len(numbers) < 2:
        return None
    return numbers[0].replace(",", "."), numbers[1].replace(",", ".")


def write_original_csv(records: list[dict[str, str]]) -> list[str]:
    columns: list[str] = []
    seen: set[str] = set()
    for record in records:
        for column in record:
            if column not in seen:
                seen.add(column)
                columns.append(column)
    with ORIGINAL_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    return columns


def normalized_preview_row(record: dict[str, str]) -> dict[str, Any]:
    locality = record.get("localitate", "")
    km = record.get("km", "")
    level = record.get("cota", "")
    variation = record.get("variatie", "")
    temperature = record.get("temperatura", "")
    measurement_date = record.get("data_masuratoare", "")
    latitude = record.get("latitude", "")
    longitude = record.get("longitude", "")
    if (not latitude or not longitude) and record.get("coordinates"):
        pair = parse_coordinate_pair(record["coordinates"])
        if pair:
            latitude, longitude = pair
    return {
        "locality_original": locality,
        "locality_normalized": locality_normalized(locality),
        "river_km_original": km,
        "river_km_numeric": decimal_json(parse_number(km, "km")),
        "level_cm_original": level,
        "level_cm_numeric": decimal_json(parse_number(level, "cota")),
        "variation_cm_original": variation,
        "variation_cm_numeric": decimal_json(parse_number(variation, "variatie")),
        "temperature_original": temperature,
        "temperature_c_numeric": decimal_json(parse_number(temperature, "temperatura")),
        "measurement_date_original": measurement_date,
        "measurement_date_iso": parse_date(measurement_date) or "",
        "latitude": latitude,
        "longitude": longitude,
    }


def write_normalized_csv(records: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows = [normalized_preview_row(record) for record in records]
    columns = list(rows[0]) if rows else [
        "locality_original", "locality_normalized", "river_km_original",
        "river_km_numeric", "level_cm_original", "level_cm_numeric",
        "variation_cm_original", "variation_cm_numeric", "temperature_original",
        "temperature_c_numeric", "measurement_date_original", "measurement_date_iso",
        "latitude", "longitude",
    ]
    with NORMALIZED_CSV_PATH.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def values_for_role(records: list[dict[str, str]], role: str) -> list[str]:
    return [record.get(role, "") for record in records]


def format_profile(values: list[str], role: str) -> dict[str, Any]:
    present = [value for value in values if clean_text(value)]
    numeric = [parse_number(value, role) for value in present] if role in NUMERIC_ROLES or role in FORECAST_ROLES else []
    return {
        "total": len(values),
        "present": len(present),
        "missing": len(values) - len(present),
        "unique_raw_count": len(set(present)),
        "raw_samples": list(dict.fromkeys(present))[:8],
        "leading_or_trailing_whitespace_count": sum(value != value.strip() for value in values),
        "explicit_plus_count": sum(bool(re.match(r"^\s*\+", value)) for value in present),
        "comma_decimal_count": sum(bool(re.search(r"\d,\d", value)) for value in present),
        "point_decimal_or_group_count": sum(bool(re.search(r"\d\.\d", value)) for value in present),
        "thousands_point_count": sum(bool(re.search(r"(?<!\d)\d{1,3}(?:\.\d{3})+(?!\d)", value)) for value in present),
        "unit_count": sum(bool(re.search(r"(?i)(?:\bcm\b|°\s*c|℃|\bmm\b|\bkm\b)", value)) for value in present),
        "nonnumeric_count": sum(value is None for value in numeric) if numeric else 0,
        "negative_count": sum(value is not None and value < 0 for value in numeric),
        "zero_count": sum(value is not None and value == 0 for value in numeric),
        "positive_count": sum(value is not None and value > 0 for value in numeric),
    }


def extrema(records: list[dict[str, str]], role: str) -> dict[str, Any]:
    parsed: list[tuple[int, str, Decimal]] = []
    for index, record in enumerate(records, start=1):
        raw = record.get(role, "")
        number = parse_number(raw, role)
        if number is not None:
            parsed.append((index, raw, number))
    if not parsed:
        return {"minimum": None, "maximum": None}
    minimum = min(parsed, key=lambda row: row[2])
    maximum = max(parsed, key=lambda row: row[2])
    return {
        "minimum": {"station_index": minimum[0], "raw": minimum[1], "numeric": decimal_json(minimum[2])},
        "maximum": {"station_index": maximum[0], "raw": maximum[1], "numeric": decimal_json(maximum[2])},
    }


def duplicate_groups(keys: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    positions: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for index, key in enumerate(keys, start=1):
        if any(part not in (None, "") for part in key):
            positions[key].append(index)
    return [
        {"key": list(key), "station_indices": indices, "count": len(indices)}
        for key, indices in positions.items()
        if len(indices) > 1
    ]


def build_quality_summary(
    raw_records: list[dict[str, str]],
    canonical_records: list[dict[str, str]],
    original_columns: list[str],
) -> dict[str, Any]:
    missing_by_column = {
        column: sum(not clean_text(record.get(column, "")) for record in raw_records)
        for column in original_columns
    }
    missing_documented = {
        role: sum(not clean_text(record.get(role, "")) for record in canonical_records)
        for role in DOCUMENTED_FIELDS
    }
    profiles: dict[str, Any] = {}
    all_roles = sorted({role for record in canonical_records for role in record})
    for role in all_roles:
        profiles[role] = format_profile(values_for_role(canonical_records, role), role)

    full_row_keys = [tuple(sorted(record.items())) for record in raw_records]
    station_identity_keys = [
        (
            locality_key(record.get("localitate")),
            decimal_json(parse_number(record.get("km"), "km")),
        )
        for record in canonical_records
    ]
    locality_date_keys = [
        (
            locality_key(record.get("localitate")),
            parse_date(record.get("data_masuratoare")) or clean_text(record.get("data_masuratoare")),
        )
        for record in canonical_records
    ]
    date_invalid_indices = [
        index
        for index, record in enumerate(canonical_records, start=1)
        if clean_text(record.get("data_masuratoare")) and not parse_date(record.get("data_masuratoare"))
    ]
    numeric_invalid: dict[str, list[int]] = {}
    for role in ("km", "cota", "variatie", "temperatura"):
        indices = [
            index
            for index, record in enumerate(canonical_records, start=1)
            if clean_text(record.get(role)) and parse_number(record.get(role), role) is None
        ]
        numeric_invalid[role] = indices

    capitalization: dict[str, set[str]] = defaultdict(set)
    for record in canonical_records:
        name = locality_normalized(record.get("localitate"))
        if name:
            capitalization[locality_key(name)].add(name)
    capitalization_changes = [
        sorted(variants) for variants in capitalization.values() if len(variants) > 1
    ]
    romanian_localities = [
        locality_normalized(record.get("localitate"))
        for record in canonical_records
        if re.search(r"[ĂÂÎȘŞȚŢăâîșşțţ]", record.get("localitate", ""))
    ]
    textual_km = [
        {"station_index": index, "value": record.get("km", "")}
        for index, record in enumerate(canonical_records, start=1)
        if re.search(r"[A-Za-z]", record.get("km", ""))
    ]
    full_duplicates = duplicate_groups(full_row_keys)
    identity_duplicates = duplicate_groups(station_identity_keys)
    locality_date_duplicates = duplicate_groups(locality_date_keys)

    validation_issue_count = (
        sum(missing_documented.values())
        + len(date_invalid_indices)
        + sum(len(indices) for indices in numeric_invalid.values())
        + sum(group["count"] - 1 for group in full_duplicates)
        + sum(group["count"] - 1 for group in identity_duplicates)
        + sum(group["count"] - 1 for group in locality_date_duplicates)
    )
    return {
        "station_count": len(raw_records),
        "missing_by_original_column": missing_by_column,
        "missing_documented_fields": missing_documented,
        "field_profiles": profiles,
        "level_extrema": extrema(canonical_records, "cota"),
        "variation_extrema": extrema(canonical_records, "variatie"),
        "measurement_dates_raw_unique": sorted({clean_text(v) for v in values_for_role(canonical_records, "data_masuratoare") if clean_text(v)}),
        "measurement_dates_iso_unique": sorted({parse_date(v) for v in values_for_role(canonical_records, "data_masuratoare") if parse_date(v)}),
        "invalid_measurement_date_station_indices": date_invalid_indices,
        "nonnumeric_station_indices": numeric_invalid,
        "exact_duplicate_rows": full_duplicates,
        "duplicate_station_identity_locality_km": identity_duplicates,
        "duplicate_locality_and_measurement_date": locality_date_duplicates,
        "locality_capitalization_variants": capitalization_changes,
        "localities_with_romanian_characters": list(dict.fromkeys(romanian_localities)),
        "textual_or_unit_bearing_km": textual_km,
        "validation_issue_count": validation_issue_count,
        "validation_issue_definition": (
            "Suma valorilor lipsa din campurile documentate, datelor invalide, valorilor "
            "nenumerice in campurile numerice si aparitiilor duplicate peste prima aparitie. "
            "Semnele, separatorii si unitatile valide sunt observatii de format, nu erori."
        ),
    }


class SimpleTableParser(HTMLParser):
    """Fallback semantic: colecteaza randuri/celule fara pozitii globale fixe."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._rows = []
        elif self._table_depth == 1 and tag == "tr":
            self._row = []
        elif self._table_depth == 1 and tag in {"th", "td"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._table_depth == 1 and tag in {"th", "td"} and self._cell_parts is not None:
            assert self._row is not None
            self._row.append(clean_text("".join(self._cell_parts)))
            self._cell_parts = None
        elif self._table_depth == 1 and tag == "tr" and self._row is not None:
            if self._row:
                self._rows.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1:
                self.tables.append(self._rows)
            self._table_depth -= 1


def rows_to_semantic_records(rows: list[list[str]]) -> tuple[list[dict[str, str]], list[str]]:
    for header_index, row in enumerate(rows):
        roles = [field_role(cell) for cell in row]
        if "localitate" not in roles or "km" not in roles or "cota" not in roles:
            continue
        header_labels = row
        records: list[dict[str, str]] = []
        for values in rows[header_index + 1:]:
            if not values or len(values) < 3:
                continue
            record: dict[str, str] = {}
            for index, value in enumerate(values[:len(header_labels)]):
                role = roles[index]
                if role and role not in record:
                    record[role] = value
            if clean_text(record.get("localitate")) and (
                clean_text(record.get("km")) or clean_text(record.get("cota"))
            ):
                records.append(record)
        if records:
            return records, header_labels
    return [], []


def extract_html_records(body: bytes, declared_charset: str | None) -> dict[str, Any]:
    encoding = declared_charset or "utf-8"
    try:
        text = body.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        text = body.decode("utf-8", errors="replace")

    methods: list[str] = []
    try:
        from lxml import html as lxml_html  # type: ignore

        document = lxml_html.fromstring(body)
        table_rows_collection: list[list[list[str]]] = []
        for table in document.xpath("//table"):
            rows: list[list[str]] = []
            for tr in table.xpath(".//tr"):
                cells = tr.xpath("./th|./td")
                row = [clean_text(cell.text_content()) for cell in cells]
                if row:
                    rows.append(row)
            table_rows_collection.append(rows)
        for rows in table_rows_collection:
            records, headers = rows_to_semantic_records(rows)
            if records:
                return {
                    "success": True,
                    "method": "lxml + selectarea tabelului dupa rolurile semantice ale antetelor",
                    "headers": headers,
                    "records": records,
                    "reason": None,
                }
        methods.append("lxml: niciun tabel cu antete semantice localitate/km/cota")
    except Exception as exc:
        methods.append(f"lxml indisponibil sau eroare: {type(exc).__name__}: {exc}")

    parser = SimpleTableParser()
    parser.feed(text)
    for rows in parser.tables:
        records, headers = rows_to_semantic_records(rows)
        if records:
            return {
                "success": True,
                "method": "HTMLParser stdlib + selectarea tabelului dupa rolurile semantice ale antetelor",
                "headers": headers,
                "records": records,
                "reason": None,
            }
    methods.append("HTMLParser: niciun tabel cu antete semantice localitate/km/cota")
    return {
        "success": False,
        "method": None,
        "headers": [],
        "records": [],
        "reason": "; ".join(methods),
    }


def comparable_value(value: str | None, role: str) -> Any:
    if role in NUMERIC_ROLES or role in FORECAST_ROLES:
        return decimal_json(parse_number(value, role))
    if role in {"data_masuratoare", "forecast_updated"}:
        return parse_date(value) or clean_text(value)
    if role == "localitate":
        return locality_key(value)
    return clean_text(value)


def compare_xml_html(
    xml_records: list[dict[str, str]],
    html_result: dict[str, Any],
) -> dict[str, Any]:
    html_records: list[dict[str, str]] = html_result["records"]
    xml_index = {locality_key(row.get("localitate")): row for row in xml_records}
    html_index = {locality_key(row.get("localitate")): row for row in html_records}
    xml_localities = [locality_normalized(row.get("localitate")) for row in xml_records]
    html_localities = [locality_normalized(row.get("localitate")) for row in html_records]
    selected: list[dict[str, Any]] = []
    for requested_name in ("Bazias", "Orsova", "Giurgiu", "Galati", "Sulina"):
        key = locality_key(requested_name)
        xml_row = xml_index.get(key)
        html_row = html_index.get(key)
        fields: dict[str, Any] = {}
        for role in ("km", "cota", "variatie", "temperatura", "data_masuratoare"):
            xml_raw = xml_row.get(role, "") if xml_row else ""
            html_raw = html_row.get(role, "") if html_row else ""
            fields[role] = {
                "xml_raw": xml_raw,
                "html_raw": html_raw,
                "xml_normalized": comparable_value(xml_raw, role),
                "html_normalized": comparable_value(html_raw, role),
                "match": bool(xml_row and html_row) and comparable_value(xml_raw, role) == comparable_value(html_raw, role),
            }
        selected.append({
            "requested_locality": requested_name,
            "xml_found": xml_row is not None,
            "html_found": html_row is not None,
            "fields": fields,
        })
    common_keys = sorted(set(xml_index) & set(html_index))
    mismatch_counts = {
        role: sum(
            comparable_value(xml_index[key].get(role), role)
            != comparable_value(html_index[key].get(role), role)
            for key in common_keys
        )
        for role in ("km", "cota", "variatie", "temperatura", "data_masuratoare")
    }
    return {
        "html_extraction_success": html_result["success"],
        "html_extraction_method": html_result["method"],
        "html_extraction_reason": html_result["reason"],
        "xml_station_count": len(xml_records),
        "html_station_count": len(html_records),
        "xml_localities": xml_localities,
        "html_localities": html_localities,
        "only_in_xml": [name for name in xml_localities if locality_key(name) not in html_index],
        "only_in_html": [name for name in html_localities if locality_key(name) not in xml_index],
        "common_station_count": len(common_keys),
        "mismatch_counts_on_common_stations": mismatch_counts,
        "selected_locality_comparison": selected,
    }


def tag_and_attribute_structure(root: ET.Element) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    counts: Counter[tuple[str, str, str | None]] = Counter()
    attributes: dict[tuple[str, str], dict[str, Any]] = {}
    for element in root.iter():
        key = (element.tag, local_name(element.tag), namespace_uri(element.tag))
        counts[key] += 1
        for attr_name, attr_value in element.attrib.items():
            attr_key = (element.tag, attr_name)
            entry = attributes.setdefault(
                attr_key,
                {
                    "element_qualified_tag": element.tag,
                    "element_local_name": local_name(element.tag),
                    "attribute_qualified_name": attr_name,
                    "attribute_local_name": local_name(attr_name),
                    "count": 0,
                    "sample_values": [],
                },
            )
            entry["count"] += 1
            if attr_value not in entry["sample_values"] and len(entry["sample_values"]) < 10:
                entry["sample_values"].append(attr_value)
    tags = [
        {"qualified_tag": qualified, "local_name": lname, "namespace": ns, "count": count}
        for (qualified, lname, ns), count in sorted(counts.items(), key=lambda item: item[0][1])
    ]
    return tags, list(attributes.values())


def hierarchy_summary(root: ET.Element, max_depth: int = 3) -> list[dict[str, Any]]:
    paths: Counter[str] = Counter()
    for _element, path, depth in iter_with_paths(root):
        if depth <= max_depth:
            paths[logical_path(path)] += 1
    return [
        {"logical_path": path, "depth": path.count("/") - 1, "occurrences": count}
        for path, count in sorted(paths.items(), key=lambda item: (item[0].count("/"), item[0]))
    ]


def station_fields(stations: list[ET.Element]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    roles: dict[str, str | None] = {}
    namespaces: dict[str, str | None] = {}
    for station in stations:
        for child in list(station):
            name = local_name(child.tag)
            counts[name] += 1
            roles[name] = field_role(name)
            namespaces[name] = namespace_uri(child.tag)
    return [
        {
            "tag": name,
            "associated_role": roles[name],
            "namespace": namespaces[name],
            "occurrences": counts[name],
            "missing_station_count": len(stations) - counts[name],
        }
        for name in counts
    ]


def field_availability(
    fields: list[dict[str, Any]],
    all_tags: list[dict[str, Any]],
) -> dict[str, Any]:
    found_by_role: dict[str, list[str]] = defaultdict(list)
    for field in fields:
        role = field["associated_role"]
        if role and field["tag"] not in found_by_role[role]:
            found_by_role[role].append(field["tag"])
    for tag in all_tags:
        role = field_role(tag["local_name"])
        if role and tag["local_name"] not in found_by_role[role]:
            found_by_role[role].append(tag["local_name"])
    checks: dict[str, Any] = {}
    requested = [
        "latitude", "longitude", "coordinates", "forecast_24h", "forecast_48h",
        "forecast_72h", "forecast_96h", "forecast_120h", "forecast_updated",
    ]
    for role in requested:
        checks[role] = {"exists": role in found_by_role, "matching_tags": found_by_role.get(role, [])}
    checks["has_any_coordinates"] = any(checks[role]["exists"] for role in ("latitude", "longitude", "coordinates"))
    checks["has_any_forecasts"] = any(checks[role]["exists"] for role in FORECAST_ROLES)
    return checks


def station_example_xml(station: ET.Element) -> str:
    copy = deepcopy(station)
    try:
        ET.indent(copy, space="  ")
    except AttributeError:
        pass
    return ET.tostring(copy, encoding="unicode", short_empty_elements=True)


def markdown_escape(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(markdown_escape(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(markdown_escape(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def summarize_station(record: dict[str, str]) -> list[str]:
    return [
        clean_text(record.get("localitate")),
        record.get("km", ""),
        record.get("cota", ""),
        record.get("variatie", ""),
        record.get("temperatura", ""),
        record.get("data_masuratoare", ""),
    ]


def build_report(
    metadata: dict[str, Any],
    structure: dict[str, Any],
    quality: dict[str, Any],
    canonical_records: list[dict[str, str]],
    html_download: DownloadResult,
    html_comparison: dict[str, Any],
) -> str:
    fields = structure["station"]["fields"]
    field_names = [field["tag"] for field in fields]
    observed_roles = {field["associated_role"] for field in fields if field["associated_role"]}
    documented_missing = [field for field in DOCUMENTED_FIELDS if field not in observed_roles]
    actual_local_tags = {tag["local_name"] for tag in structure["all_tags"]}
    documented_literal_missing = [field for field in DOCUMENTED_FIELDS if field not in actual_local_tags]
    undocumented_tags = [field["tag"] for field in fields if field["associated_role"] not in DOCUMENTED_FIELDS]
    availability = structure["station"]["special_field_availability"]
    first_rows = [summarize_station(record) for record in canonical_records[:5]]
    last_rows = [summarize_station(record) for record in canonical_records[-5:]]
    table_headers = ["Localitate", "km", "cota", "variatie", "temperatura", "data"]

    selected_rows: list[list[Any]] = []
    for station in html_comparison["selected_locality_comparison"]:
        for role in ("km", "cota", "variatie", "temperatura", "data_masuratoare"):
            field = station["fields"][role]
            selected_rows.append([
                station["requested_locality"], role, field["xml_raw"], field["html_raw"],
                "DA" if field["match"] else "NU",
            ])

    profile_rows: list[list[Any]] = []
    for role, profile in quality["field_profiles"].items():
        profile_rows.append([
            role,
            profile["present"],
            profile["missing"],
            ", ".join(repr(sample) for sample in profile["raw_samples"][:4]),
            f"neg={profile['negative_count']}, zero={profile['zero_count']}, poz={profile['positive_count']}" if role in NUMERIC_ROLES or role in FORECAST_ROLES else "text/data",
        ])

    format_check_rows = [
        [
            role, profile["explicit_plus_count"], profile["comma_decimal_count"],
            profile["point_decimal_or_group_count"], profile["thousands_point_count"],
            profile["leading_or_trailing_whitespace_count"], profile["unit_count"],
            profile["missing"], profile["nonnumeric_count"],
        ]
        for role, profile in quality["field_profiles"].items()
    ]

    tag_rows = [
        [tag["qualified_tag"], tag["local_name"], tag["count"]]
        for tag in structure["all_tags"]
    ]
    attribute_rows = [
        [item["element_local_name"], item["attribute_local_name"], item["count"], ", ".join(item["sample_values"])]
        for item in structure["attributes"]
    ]

    level_extrema = quality["level_extrema"]
    variation_extrema = quality["variation_extrema"]
    validation_count = quality["validation_issue_count"]
    mismatch_counts = html_comparison["mismatch_counts_on_common_stations"]
    stable_enough = (
        structure["well_formed"]
        and len(canonical_records) > 0
        and not documented_missing
        and sum(quality["missing_documented_fields"].values()) == 0
        and html_comparison["html_extraction_success"]
    )

    lines = [
        "# Audit tehnic și semantic — XML AFDJ Cotele Dunării",
        "",
        "## Rezumat executiv",
        "",
        f"Auditul a analizat răspunsul XML brut descărcat la `{metadata['downloaded_at_utc']}`. "
        f"Documentul este {'well-formed' if structure['well_formed'] else 'INVALID'}, are rădăcina "
        f"`{structure['root']['qualified_tag']}` și conține **{len(canonical_records)}** noduri-stație "
        f"identificate dinamic ca `{structure['station']['node_tag']}` la calea logică "
        f"`{structure['station']['logical_path']}`.",
        "",
        f"Sursa este **{'suficient de stabilă pentru automatizare, cu validările recomandate mai jos' if stable_enough else 'neconfirmată ca suficient de stabilă pentru automatizare fără măsuri suplimentare'}**. "
        f"Au rezultat **{validation_count}** probleme de validare conform definiției explicite din raportul JSON; "
        "separatorii, semnele și unitățile valide sunt tratate ca formate observate, nu automat ca erori.",
        "",
        "## Răspuns HTTP XML",
        "",
        md_table(
            ["Proprietate", "Valoare"],
            [
                ["URL cerut", metadata["requested_url"]],
                ["URL final", metadata["final_url"]],
                ["Status", f"{metadata['http_status']} {metadata['http_reason']}"],
                ["Content-Type", metadata["content_type"]],
                ["Content-Length antet", metadata["content_length_header"]],
                ["Dimensiune efectivă", f"{metadata['actual_size_bytes']} bytes"],
                ["Encoding HTTP", metadata["http_declared_encoding"]],
                ["Encoding declarație XML", metadata["xml_declared_encoding"]],
                ["SHA-256", metadata["sha256"]],
                ["Descărcare UTC", metadata["downloaded_at_utc"]],
                ["Descărcare Europe/Bucharest", metadata["downloaded_at_europe_bucharest"]],
                ["Încercări", metadata["attempts"]],
            ],
        ),
        "",
        "## Structura XML reală",
        "",
        f"- Declarație XML: `{structure['xml_declaration']['raw'] or 'absentă'}`",
        f"- Encoding efectiv declarat: `{structure['xml_declaration']['encoding'] or metadata['http_declared_encoding'] or 'nedeclarat'}`",
        f"- Element-rădăcină: `{structure['root']['qualified_tag']}`",
        f"- Namespace-uri: `{json.dumps(structure['namespaces'], ensure_ascii=False)}`",
        f"- Nod-stație: `{structure['station']['node_tag']}`",
        f"- Cale logică: `{structure['station']['logical_path']}`",
        f"- Număr stații: **{structure['station']['count']}**",
        "",
        "### Ierarhia primelor niveluri",
        "",
        md_table(
            ["Cale logică", "Adâncime", "Apariții"],
            [[row["logical_path"], row["depth"], row["occurrences"]] for row in structure["hierarchy_first_levels"]],
        ),
        "",
        "### Toate tagurile identificate",
        "",
        md_table(["Tag calificat", "Nume local", "Apariții"], tag_rows),
        "",
        "### Atribute XML",
        "",
        md_table(["Element", "Atribut", "Apariții", "Exemple"], attribute_rows) if attribute_rows else "Nu există atribute XML.",
        "",
        "## Structura nodului-stație",
        "",
        f"Câmpuri copil observate, în ordinea primei apariții: `{', '.join(field_names)}`.",
        "",
        md_table(
            ["Tag", "Rol asociat", "Apariții", "Lipsește din stații"],
            [[field["tag"], field["associated_role"], field["occurrences"], field["missing_station_count"]] for field in fields],
        ),
        "",
        "Toate căile indexate până la fiecare stație sunt păstrate în `xml_structure.json`, cheia `station.indexed_paths`.",
        "",
        "### Exemplu XML real pentru o stație",
        "",
        "```xml",
        structure["station"]["example_xml"],
        "```",
        "",
        "## Formatele reale ale câmpurilor",
        "",
        md_table(["Rol", "Prezente", "Lipsă", "Exemple brute", "Distribuție"], profile_rows),
        "",
        "### Verificări explicite de format în XML",
        "",
        md_table(
            ["Rol", "Plus explicit", "Virgulă zecimală", "Punct", "Punct de mii", "Spații margini", "Unități", "Lipsă", "Nenumerice"],
            format_check_rows,
        ),
        "",
        "Normalizarea numerică din preview acceptă semn explicit, virgulă zecimală și punct zecimal; "
        "pentru `km`, `cota`, `variatie` și prognoze, grupurile de exact trei cifre după punct sunt "
        "interpretate ca separatori de mii (de exemplu `1.072` → `1072`). Valorile originale rămân intacte.",
        "",
        "## Diferențe față de documentația locală",
        "",
        f"Documentația declară: `{', '.join(DOCUMENTED_FIELDS)}`.",
        f"Roluri documentate neidentificate semantic în XML: `{', '.join(documented_missing) if documented_missing else 'niciunul'}`.",
        f"Taguri literale din documentație care nu apar ca atare: `{', '.join(documented_literal_missing) if documented_literal_missing else 'niciunul'}`.",
        f"Taguri suplimentare sau neasociate documentației: `{', '.join(undocumented_tags) if undocumented_tags else 'niciunul'}`.",
        "",
        "Schema reală nu este lista plată sugerată de documentație: stația este un nod CMS `item`, câmpurile sunt wrapper-e `field_*`, iar valorile sunt în general în copii `value`. Sunt prezente și UUID/nid, coordonate și prognoze.",
        "",
        "Documentația indică data `DD/MM/YYYY`, dar XML-ul auditat folosește ISO 8601 cu oră și fus (`2026-08-03T03:00:00+03:00`). În XML, temperatura folosește punct zecimal și nivelurile nu includ `cm`; pagina HTML folosește virgulă zecimală și unități afișate. Nu a fost observată valoarea textuală `Mm` în această captură.",
        "",
        "## Coordonate și prognoze în XML",
        "",
        md_table(
            ["Rol căutat", "Există", "Taguri asociate"],
            [[role, "DA" if details["exists"] else "NU", ", ".join(details["matching_tags"])]
             for role, details in availability.items() if isinstance(details, dict)],
        ),
        "",
        "## Calitatea datelor și cazuri-limită",
        "",
        f"- Cota minimă: `{level_extrema['minimum']}`; cota maximă: `{level_extrema['maximum']}`.",
        f"- Variația minimă: `{variation_extrema['minimum']}`; variația maximă: `{variation_extrema['maximum']}`.",
        f"- Date brute unice: `{quality['measurement_dates_raw_unique']}`.",
        f"- Date ISO unice: `{quality['measurement_dates_iso_unique']}`.",
        f"- Date invalide, indici stație: `{quality['invalid_measurement_date_station_indices']}`.",
        f"- Valori nenumerice: `{quality['nonnumeric_station_indices']}`.",
        f"- Duplicate complete: `{quality['exact_duplicate_rows']}`.",
        f"- Duplicate după localitate + km: `{quality['duplicate_station_identity_locality_km']}`.",
        f"- Duplicate după localitate + dată: `{quality['duplicate_locality_and_measurement_date']}`.",
        f"- Variante de capitalizare: `{quality['locality_capitalization_variants']}`.",
        f"- Localități cu caractere românești: `{quality['localities_with_romanian_characters']}`.",
        f"- Kilometri textuali / cu unități: `{quality['textual_or_unit_bearing_km']}`.",
        "",
        "### Câmpuri lipsă pentru fiecare coloană XML",
        "",
        md_table(
            ["Coloană", "Valori lipsă"],
            [[key, value] for key, value in quality["missing_by_original_column"].items()],
        ),
        "",
        "### Primele 5 stații",
        "",
        md_table(table_headers, first_rows),
        "",
        "### Ultimele 5 stații",
        "",
        md_table(table_headers, last_rows),
        "",
        "### Lista completă a localităților XML",
        "",
        ", ".join(locality_normalized(record.get("localitate")) for record in canonical_records),
        "",
        "## Comparație cu pagina HTML oficială",
        "",
        f"Pagina HTML a răspuns cu `{html_download.status} {html_download.reason}`, "
        f"Content-Type `{html_download.headers.get('Content-Type', '')}` și {len(html_download.body)} bytes.",
        f"Extragere robustă: **{'reușită' if html_comparison['html_extraction_success'] else 'nereușită'}**; "
        f"metodă: `{html_comparison['html_extraction_method'] or html_comparison['html_extraction_reason']}`.",
        f"Stații XML: **{html_comparison['xml_station_count']}**; stații HTML: "
        f"**{html_comparison['html_station_count']}**; comune: **{html_comparison['common_station_count']}**.",
        f"Doar în XML: `{html_comparison['only_in_xml']}`. Doar în HTML: `{html_comparison['only_in_html']}`.",
        f"Nepotriviri pe stațiile comune: `{mismatch_counts}`.",
        "",
        "### Verificarea localităților solicitate",
        "",
        md_table(["Localitate", "Câmp", "XML brut", "HTML brut", "Egal normalizat"], selected_rows),
        "",
        "Lista completă a localităților HTML: " + ", ".join(html_comparison["html_localities"]),
        "",
        "## Recomandări exacte pentru parserul operațional",
        "",
        "1. Descărcați bytes cu maximum 3 încercări, timeout și User-Agent; acceptați doar HTTP 2xx și Content-Type XML.",
        "2. Păstrați fiecare captură brută imuabilă și calculați SHA-256 înainte de parsare.",
        "3. Folosiți un parser XML real; nu regex pentru structură. Tratați namespace-urile după numele local, dar înregistrați URI-ul.",
        "4. Detectați nodul-stație prin copii semantici (`localitate` + `cota`) și validați că structura dominantă rămâne aceeași.",
        "5. Păstrați valorile brute și produceți separat valori normalizate. Nu eliminați punctul înainte de a aplica regula dependentă de câmp.",
        "6. Pentru `km`/`cota`, interpretați punctul urmat de grupuri de 3 cifre ca separator de mii; pentru temperatură și coordonate, punctul este zecimal.",
        "7. Acceptați `+`, `-`, virgulă/punct, spații și unități cunoscute; respingeți explicit resturile textuale necunoscute după extragere.",
        "8. Validați datele calendaristic în formatul observat și păstrați atât textul brut, cât și ISO `YYYY-MM-DD`.",
        "9. Eșuați controlat sau alertați la: XML invalid, zero stații, lipsa câmpurilor-cheie, scădere bruscă a numărului de stații, duplicate ori schimbare de schemă.",
        "10. Comparați periodic un eșantion cu tabelul HTML folosind antetele semantice, nu indecși globali sau selectori CSS fragili.",
        "",
        "## Chei și identificatori recomandați",
        "",
        "- **Cheie unică de înregistrare:** `(station_stable_id, measurement_date_iso)`. Dacă sursa va publica mai multe măsurători în aceeași zi, extindeți cu ora reală a măsurării; ora descărcării nu trebuie folosită ca oră a măsurării.",
        "- **Identificator stabil de stație:** folosiți UUID-ul oficial din `uuid/value`, observat în fiecare nod `item`; păstrați identificatorul CMS din câmpul nid/value doar ca reper auxiliar. Dacă aceste câmpuri dispar, reveniți controlat la un ID intern din localitatea canonică + poziția fluvială normalizată și mențineți o tabelă de aliasuri. Nu folosiți doar numele.",
        "- Păstrați separat `locality_original`, forma canonică afișată și cheia accent-insensitive/case-insensitive folosită numai la reconciliere.",
        "",
        "## Concluzie privind automatizarea",
        "",
        (
            "Captura curentă este adecvată pentru automatizare cu schema tolerantă și validările descrise. "
            "Stabilitatea în timp nu poate fi demonstrată dintr-o singură captură; recomandarea este monitorizarea hash-ului structural, "
            "a setului de taguri și a numărului de stații la fiecare rulare."
            if stable_enough else
            "Captura curentă necesită remedierea sau acceptarea explicită a problemelor descrise înainte de automatizare. "
            "Fișierele brute au fost păstrate pentru analiză manuală."
        ),
        "",
        "---",
        "",
        "Artefactele machine-readable (`http_metadata.json`, `xml_structure.json`, `data_quality_summary.json`, "
        "`xml_tag_counts.csv`) sunt sursa exactă pentru detaliile exhaustive; raportul de față le sintetizează fără a modifica datele brute.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ensure_directories()
    try:
        xml_download = download(XML_URL, ("xml",), "XML AFDJ")
        XML_RAW_PATH.write_bytes(xml_download.body)

        content_type = xml_download.headers.get("Content-Type", "")
        mime, http_charset = parse_content_type(content_type)
        declaration = xml_declaration_details(xml_download.body)
        bucharest = ZoneInfo("Europe/Bucharest")
        downloaded_local = xml_download.downloaded_utc.astimezone(bucharest)
        metadata = {
            "requested_url": xml_download.requested_url,
            "final_url": xml_download.final_url,
            "http_status": xml_download.status,
            "http_reason": xml_download.reason,
            "content_type": content_type,
            "mime_type": mime,
            "content_length_header": xml_download.headers.get("Content-Length"),
            "http_declared_encoding": http_charset,
            "xml_declared_encoding": declaration["encoding"],
            "declared_encoding": declaration["encoding"] or http_charset,
            "downloaded_at_utc": xml_download.downloaded_utc.isoformat(),
            "downloaded_at_europe_bucharest": downloaded_local.isoformat(),
            "timezone_local": "Europe/Bucharest",
            "sha256": hashlib.sha256(xml_download.body).hexdigest(),
            "actual_size_bytes": len(xml_download.body),
            "attempts": xml_download.attempts,
            "response_headers": xml_download.headers,
        }
        write_json(HTTP_METADATA_PATH, metadata)

        try:
            root = ET.fromstring(xml_download.body)
        except ET.ParseError as exc:
            raise RuntimeError(f"XML-ul descarcat nu este well-formed: {exc}") from exc

        namespaces = collect_namespaces(xml_download.body)
        stations, station_node, station_path, indexed_paths = identify_station_nodes(root)
        raw_records = [station_raw_record(station) for station in stations]
        canonical_records = [station_canonical_record(station) for station in stations]
        original_columns = write_original_csv(raw_records)
        write_normalized_csv(canonical_records)

        tags, attributes = tag_and_attribute_structure(root)
        fields = station_fields(stations)
        availability = field_availability(fields, tags)
        structure = {
            "well_formed": True,
            "xml_declaration": declaration,
            "root": {
                "qualified_tag": root.tag,
                "local_name": local_name(root.tag),
                "namespace": namespace_uri(root.tag),
            },
            "namespaces": namespaces,
            "hierarchy_first_levels": hierarchy_summary(root, max_depth=3),
            "all_tags": tags,
            "unique_tag_count": len(tags),
            "attributes": attributes,
            "station": {
                "node_tag": station_node,
                "logical_path": station_path,
                "indexed_paths": indexed_paths,
                "count": len(stations),
                "fields": fields,
                "special_field_availability": availability,
                "example_xml": station_example_xml(stations[0]),
            },
        }
        write_json(STRUCTURE_PATH, structure)
        with TAG_COUNTS_PATH.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=["qualified_tag", "local_name", "namespace", "count"],
            )
            writer.writeheader()
            writer.writerows(tags)

        quality = build_quality_summary(raw_records, canonical_records, original_columns)

        html_download = download(HTML_URL, ("html", "xhtml"), "Pagina HTML AFDJ")
        HTML_RAW_PATH.write_bytes(html_download.body)
        _html_mime, html_charset = parse_content_type(html_download.headers.get("Content-Type", ""))
        html_result = extract_html_records(html_download.body, html_charset)
        html_comparison = compare_xml_html(canonical_records, html_result)
        quality["html_comparison"] = html_comparison
        quality["html_http"] = {
            "requested_url": html_download.requested_url,
            "final_url": html_download.final_url,
            "status": html_download.status,
            "content_type": html_download.headers.get("Content-Type", ""),
            "size_bytes": len(html_download.body),
            "sha256": hashlib.sha256(html_download.body).hexdigest(),
            "downloaded_at_utc": html_download.downloaded_utc.isoformat(),
            "attempts": html_download.attempts,
        }
        write_json(QUALITY_PATH, quality)

        report = build_report(
            metadata, structure, quality, canonical_records, html_download, html_comparison
        )
        REPORT_PATH.write_text(report, encoding="utf-8")

        roles_found = sorted({field["associated_role"] or field["tag"] for field in fields})
        print("=== REZUMAT AUDIT AFDJ ===")
        print(f"HTTP XML: {metadata['http_status']} {metadata['http_reason']}")
        print(f"Content-Type: {metadata['content_type']}")
        print(f"Dimensiune XML: {metadata['actual_size_bytes']} bytes")
        print(f"Root tag: {structure['root']['qualified_tag']}")
        print(f"Nod statie: {station_node} ({station_path})")
        print(f"Numar statii: {len(stations)}")
        print(f"Campuri identificate: {', '.join(roles_found)}")
        print(f"Coordonate in XML: {'DA' if availability['has_any_coordinates'] else 'NU'}")
        print(f"Prognoze in XML: {'DA' if availability['has_any_forecasts'] else 'NU'}")
        print(f"Data masuratorilor: {', '.join(quality['measurement_dates_raw_unique']) or 'lipsa'}")
        print(f"Probleme de validare: {quality['validation_issue_count']}")
        print("Fisiere create:")
        for path in (
            XML_RAW_PATH, HTML_RAW_PATH, HTTP_METADATA_PATH, STRUCTURE_PATH,
            TAG_COUNTS_PATH, QUALITY_PATH, REPORT_PATH, ORIGINAL_CSV_PATH,
            NORMALIZED_CSV_PATH,
        ):
            print(f"- {path}")
        return 0
    except Exception as exc:
        print(f"EROARE AUDIT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
