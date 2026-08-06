#!/usr/bin/env python3
"""Low-volume, read-only technical audit for official Danube data sources.

This module is intentionally independent from the production ingestion pipeline. It never
writes canonical/public data and does not attempt to bypass authentication or access controls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

DEFAULT_USER_AGENT = "NivelDunareResearchAudit/1.0 (+https://github.com/mariusbudileanu/nivel-dunare)"
DEFAULT_TIMEOUT = 25.0
DEFAULT_MAX_REQUESTS = 12
TEXT_LIMIT = 1024 * 1024
COUNTRY_ORDER = ("de", "at", "sk", "hu", "hr", "rs", "bg", "ro")
TEXT_MIMES = ("text/", "json", "xml", "csv", "javascript", "xhtml", "svg")
PRODUCTION_DIRS = (
    Path("data/canonical"), Path("data/public"), Path("public/data"), Path("public"),
)

SOURCES: dict[str, dict[str, Any]] = {
    "de": {
        "country_name": "Germany", "provider_id": "pegelonline_de",
        "provider_name": "Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV)",
        "url": "https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json?waters=DONAU&includeTimeseries=true&includeCurrentMeasurement=true",
        "initial_url": "https://www.pegelonline.wsv.de/gast/karte/standard",
        "endpoint_type": "official-rest-api", "documented": True,
        "evidence_url": "https://www.pegelonline.wsv.de/webservice/dokuRestapi",
        "terms_url": "https://www.pegelonline.wsv.de/webservice/faq",
        "license": "DL-DE-Zero-2.0", "authentication": "none",
    },
    "at": {
        "country_name": "Austria", "provider_id": "viadonau_at",
        "provider_name": "viadonau - Österreichische Wasserstraßen-Gesellschaft mbH",
        "url": "https://opendata2.doris-info.at/doris/api/1.0/gauge/list?VIADONAU_PARTNER_KEY=opendata",
        "initial_url": "https://www.doris.bmimi.gv.at/en/fairway-information/water-levels",
        "endpoint_type": "official-openapi", "documented": True,
        "evidence_url": "https://www.doris.bmimi.gv.at/services/ris-open-services",
        "terms_url": "https://www.doris.bmimi.gv.at/services/ris-open-services",
        "license": "open service disclaimer; permanent integration requires partner key",
        "authentication": "public portal test key; partner key for permanent use",
    },
    "sk": {
        "country_name": "Slovakia", "provider_id": "shmu_sk",
        "provider_name": "Slovenský hydrometeorologický ústav (SHMÚ)",
        "url": "https://www.shmu.sk/en/?id=hydro_vod_all&page=1&station_id=5140",
        "initial_url": "http://www.povodia.sk/dunaj/en/",
        "endpoint_type": "official-html", "documented": False,
        "evidence_url": "https://www.shmu.sk/en/?id=hydro_vod_all&page=1&station_id=5140",
        "terms_url": "https://www.shmu.sk/en/?page=1&id=kontakt",
        "license": "not established for automated republication",
        "authentication": "none observed",
    },
    "hu": {
        "country_name": "Hungary", "provider_id": "hydroinfo_hu",
        "provider_name": "Országos Vízügyi Főigazgatóság (OVF), Hungarian Hydrological Forecasting Service",
        "url": "https://www.hydroinfo.hu/tables/dunhif.html",
        "initial_url": "http://www.hydroinfo.hu/en/hidinfo/duna.html",
        "endpoint_type": "official-html-table", "documented": False,
        "evidence_url": "https://www.hydroinfo.hu/mobil/en/hydro.php",
        "terms_url": "https://www.ovf.hu/en/public",
        "license": "not established for automated republication",
        "authentication": "none observed",
    },
    "hr": {
        "country_name": "Croatia", "provider_id": "vodniputovi_hr",
        "provider_name": "Agencija za vodne putove / Hrvatske vode / DHMZ",
        "url": "https://vodniputovi.hr/dhmz_vodostaji/getwaterstuff.php",
        "initial_url": "https://www.vodniputovi.hr/en/services/waterlevels/",
        "endpoint_type": "official-dynamic-page", "documented": False,
        "evidence_url": "https://vodniputovi.hr/en/eu-projects/fairway/water-level-forecast-available-in-croatia/",
        "terms_url": "https://www.vodniputovi.hr/en/terms-of-use/",
        "license": "not established for automated republication",
        "authentication": "none observed",
    },
    "rs": {
        "country_name": "Serbia", "provider_id": "hidmet_rs",
        "provider_name": "Republic Hydrometeorological Service of Serbia (RHMZ)",
        "url": "https://www.hidmet.gov.rs/eng/hidrologija/izvestajne/index.php",
        "initial_url": "https://www.hidmet.gov.rs/",
        "endpoint_type": "official-html", "documented": False,
        "evidence_url": "https://www.hidmet.gov.rs/eng/hidrologija/naslovna_stanje.php",
        "terms_url": "https://www.hidmet.gov.rs/eng/o_nama/kontakt.php",
        "license": "not established for automated republication",
        "authentication": "none observed",
    },
    "bg": {
        "country_name": "Bulgaria", "provider_id": "appd_bg",
        "provider_name": "Executive Agency for Exploration and Maintenance of the Danube River (EAEMDR/APPD)",
        "url": "https://www.appd-bg.org/hidrology-en",
        "initial_url": "https://appd-bg.org/exploration#data_hydro-bg",
        "endpoint_type": "official-semantic-html", "documented": False,
        "evidence_url": "https://www.appd-bg.org/hidrology-en",
        "terms_url": "https://www.appd-bg.org/pages-en?id=opendata",
        "license": "EAEMDR Open Data reuse terms; attribution and transformation notice required",
        "authentication": "none observed",
    },
    "ro": {
        "country_name": "Romania", "provider_id": "afdj_ro",
        "provider_name": "Administrația Fluvială a Dunării de Jos R.A. Galați (AFDJ)",
        "url": "https://afdj.ro/ro/tabel_cotele_dunarii/xml",
        "initial_url": "https://afdj.ro/ro/cotele-dunarii",
        "endpoint_type": "official-xml-feed", "documented": False,
        "evidence_url": "https://afdj.ro/ro/cotele-dunarii",
        "terms_url": "https://afdj.ro/ro/termeni-si-conditii",
        "license": "not established for automated republication",
        "authentication": "none",
    },
}


@dataclass
class AuditResponse:
    requested_url: str
    effective_url: str
    status: int
    reason: str
    headers: list[tuple[str, str]]
    body: bytes
    elapsed_seconds: float
    redirect_chain: list[dict[str, Any]]
    http_version: str
    accessed_at_utc: str
    error: str | None = None
    network_metadata: dict[str, Any] | None = None


class TrackingRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.chain: list[dict[str, Any]] = []

    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> urllib.request.Request | None:
        self.chain.append({"status": code, "from": req.full_url, "to": newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def safe_text_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def header_values(headers: Iterable[tuple[str, str]], name: str) -> list[str]:
    wanted = name.casefold()
    return [value for key, value in headers if key.casefold() == wanted]


def first_header(headers: Iterable[tuple[str, str]], name: str) -> str:
    values = header_values(headers, name)
    return values[0] if values else ""


def redact_cookie(value: str) -> str:
    token = value.split(";", 1)[0]
    name = token.split("=", 1)[0].strip() or "cookie"
    suffix = ";" + value.split(";", 1)[1] if ";" in value else ""
    return f"{name}=<redacted>{suffix}"


def redact_headers(headers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    result = []
    for name, value in headers:
        if name.casefold() in {"set-cookie", "cookie", "authorization", "proxy-authorization"}:
            result.append((name, redact_cookie(value) if "cookie" in name.casefold() else "<redacted>"))
        else:
            result.append((name, value))
    return result


def mask_ip(value: str) -> str:
    try:
        parsed = ipaddress.ip_address(value.strip("[]"))
    except ValueError:
        return value
    if parsed.version == 4:
        parts = str(parsed).split(".")
        return ".".join(parts[:3] + ["xxx"])
    exploded = parsed.exploded.split(":")
    return ":".join(exploded[:3] + ["xxxx"] * 5)


def parse_content_type(value: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in (value or "").split(";")]
    mime = parts[0].casefold() if parts else ""
    charset = None
    for part in parts[1:]:
        match = re.match(r"(?i)charset\s*=\s*[\"']?([^\"';\s]+)", part)
        if match:
            charset = match.group(1)
            break
    return mime, charset


def decode_text(body: bytes, content_type: str) -> tuple[str | None, str | None]:
    mime, charset = parse_content_type(content_type)
    textual = mime.startswith("text/") or any(marker in mime for marker in TEXT_MIMES[1:])
    if not textual and b"\x00" in body[:4096]:
        return None, None
    encodings = [charset] if charset else []
    encodings += ["utf-8", "windows-1250", "iso-8859-2"]
    for encoding in dict.fromkeys(item for item in encodings if item):
        try:
            text = body.decode(encoding, errors="strict")
            if text.encode(encoding, errors="strict") == body:
                return text, encoding
        except (LookupError, UnicodeError):
            continue
    return None, None


def classify_body(status: int, headers: Iterable[tuple[str, str]], body: bytes) -> str:
    content_type = first_header(headers, "Content-Type")
    mime, _charset = parse_content_type(content_type)
    stripped = body.lstrip()
    lower = body[:200000].lower()
    if status in {401, 403} and any(term in lower for term in (b"cloudflare", b"access denied", b"blocked")):
        return "block-page"
    if b"just a moment" in lower or b"checking your browser" in lower:
        return "challenge"
    if status >= 400 and not body:
        return "error"
    try:
        json.loads(body.decode("utf-8"))
        return "json"
    except (UnicodeError, json.JSONDecodeError):
        pass
    try:
        ET.fromstring(body)
        return "xml"
    except ET.ParseError:
        pass
    if "csv" in mime or (b"," in body[:2048] and b"\n" in body[:2048] and b"<html" not in lower):
        return "csv"
    if "javascript" in mime or stripped.startswith((b"function ", b"const ", b"var ", b"let ")):
        return "javascript"
    if mime.startswith("image/"):
        return "image"
    if mime == "application/pdf" or body.startswith(b"%PDF-"):
        return "pdf"
    if b"<html" in lower or b"<!doctype html" in lower:
        dynamic_markers = (b"fetch(", b"xmlhttprequest", b"axios", b"__next_data__", b"ng-app", b"react")
        return "html-shell" if any(marker in lower for marker in dynamic_markers) else "html-static"
    if status >= 400:
        return "error"
    return "binary"


def infer_schema(classification: str, body: bytes, content_type: str) -> dict[str, Any]:
    schema: dict[str, Any] = {"classification": classification}
    text, encoding = decode_text(body, content_type)
    schema["encoding"] = encoding
    if classification == "json" and text is not None:
        parsed = json.loads(text)
        schema["root_type"] = type(parsed).__name__
        sample = parsed[0] if isinstance(parsed, list) and parsed else parsed
        schema["sample_fields"] = sorted(sample.keys()) if isinstance(sample, dict) else []
        schema["item_count"] = len(parsed) if isinstance(parsed, (list, dict)) else None
    elif classification == "xml":
        root = ET.fromstring(body)
        schema["root_tag"] = root.tag
        schema["child_tags"] = sorted({child.tag for child in root.iter() if child is not root})[:200]
        schema["item_count"] = len(list(root))
    elif classification == "csv" and text is not None:
        rows = list(csv.reader(text.splitlines()[:20]))
        schema["columns"] = rows[0] if rows else []
        schema["sample_row_count"] = max(0, len(rows) - 1)
    elif classification.startswith("html") and text is not None:
        schema["forms"] = len(re.findall(r"<form\b", text, flags=re.I))
        schema["iframes"] = re.findall(r"<iframe[^>]+src=[\"']([^\"']+)", text, flags=re.I)[:50]
        schema["scripts"] = re.findall(r"<script[^>]+src=[\"']([^\"']+)", text, flags=re.I)[:100]
    return schema


def extract_station_sample(country: str, classification: str, body: bytes, content_type: str) -> list[dict[str, Any]]:
    text, _encoding = decode_text(body, content_type)
    if classification == "json" and text:
        parsed = json.loads(text)
        if country == "de" and isinstance(parsed, list):
            return [{key: item.get(key) for key in ("uuid", "number", "shortname", "longname", "km", "longitude", "latitude", "agency", "water", "timeseries") if key in item} for item in parsed]
        if country == "at" and isinstance(parsed, dict):
            return list(parsed.get("gaugeList") or [])
        if country == "hr" and isinstance(parsed, dict):
            rows = []
            for slug, values in parsed.items():
                sample = values[0] if isinstance(values, list) and values else {}
                rows.append({"station_slug": slug, "source_station_id": sample.get("sifra"),
                             "latest_sample_date": sample.get("datum"), "latest_sample_level": sample.get("vodostaj"),
                             "returned_value_count": len(values) if isinstance(values, list) else 0})
            return rows
    if country == "ro" and classification == "xml":
        root = ET.fromstring(body)
        rows = []
        for item in list(root):
            row = {child.tag: (child.text or "").strip() for child in list(item)}
            if row:
                rows.append(row)
        return rows
    if country == "sk" and text:
        return [{"source_station_id": identifier, "station_name_original": re.sub(r"\s+-\s+Dunaj$", "", name)}
                for identifier, name in re.findall(r'<option value="(\d+)"[^>]*>([^<]+\s+-\s+Dunaj)</option>', text, flags=re.I)]
    if country == "hu" and text:
        from html.parser import HTMLParser
        class TableParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__(); self.in_td = False; self.cell = ""; self.row: list[str] = []; self.rows: list[list[str]] = []
            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if tag == "td": self.in_td = True; self.cell = ""
                elif tag == "tr": self.row = []
            def handle_data(self, data: str) -> None:
                if self.in_td: self.cell += data
            def handle_endtag(self, tag: str) -> None:
                if tag == "td": self.in_td = False; self.row.append(" ".join(self.cell.split()))
                elif tag == "tr" and self.row: self.rows.append(self.row.copy())
        parser = TableParser(); parser.feed(text)
        rows = []
        for cells in parser.rows:
            if len(cells) < 8 or cells[2].casefold() != "duna" or not cells[0].isdigit():
                continue
            rows.append({"source_station_id": cells[0], "station_name_original": cells[1],
                         "provider_role": "primary" if cells[0].startswith("4") else "republished",
                         "current_level_cm": cells[5] if len(cells) > 5 else None,
                         "variation_24h_cm": cells[6] if len(cells) > 6 else None,
                         "discharge_m3s": cells[7] if len(cells) > 7 else None,
                         "water_temperature_c": cells[8] if len(cells) > 8 else None})
        return rows
    if country == "rs" and text:
        rows = []
        for table_row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", text, flags=re.I | re.S):
            if "DUNAV" not in table_row.upper():
                continue
            identifier = re.search(r"hm_id=(\d+)", table_row, flags=re.I)
            name = re.search(r"<span\b[^>]*class=[\"']?bold[\"']?[^>]*>(.*?)</span>", table_row, flags=re.I | re.S)
            if not identifier or not name:
                continue
            station_name = html.unescape(re.sub(r"<[^>]+>", "", name.group(1))).strip()
            rows.append({"source_station_id": identifier.group(1), "station_name_original": station_name})
        return rows
    if country == "bg" and text:
        names = re.findall(r"Gauging station(?:<[^>]+>|&nbsp;|\s)*([A-Za-z ]+?)\s*(?:-|for)", text, flags=re.I)
        unique: dict[str, dict[str, str]] = {}
        for name in names:
            cleaned = " ".join(name.split()).title()
            if cleaned:
                unique[cleaned.casefold()] = {"station_name_original": cleaned}
        return list(unique.values())
    if text and classification.startswith("html"):
        candidates = []
        for match in re.finditer(r"(?:station_id|postajaID|stationId)[=\"'&:]*(\d+)", text, re.I):
            candidates.append({"source_station_id": match.group(1)})
        unique = {row["source_station_id"]: row for row in candidates}
        return list(unique.values())[:200]
    return []

def resolve_dns(url: str) -> dict[str, Any]:
    host = urllib.parse.urlparse(url).hostname or ""
    addresses: list[dict[str, str]] = []
    error = None
    started = time.perf_counter()
    try:
        for family, _socktype, _proto, _canonname, sockaddr in socket.getaddrinfo(host, None):
            address = sockaddr[0]
            entry = {"family": "IPv6" if family == socket.AF_INET6 else "IPv4", "address": address}
            if entry not in addresses:
                addresses.append(entry)
    except OSError as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {"hostname": host, "addresses": addresses, "duration_seconds": time.perf_counter() - started, "error": error}


def _parse_curl_headers(raw: bytes) -> tuple[str, int, str, list[tuple[str, str]], list[dict[str, Any]]]:
    normalized = raw.replace(b"\r\n", b"\n")
    blocks = [block for block in normalized.split(b"\n\n") if block.startswith(b"HTTP/")]
    parsed: list[tuple[str, int, str, list[tuple[str, str]]]] = []
    for block in blocks:
        lines = block.split(b"\n")
        status_text = lines[0].decode("latin-1", errors="replace")
        match = re.match(r"HTTP/([^ ]+)\s+(\d{3})(?:\s+(.*))?", status_text)
        if not match:
            continue
        headers: list[tuple[str, str]] = []
        for line in lines[1:]:
            if b":" not in line:
                continue
            name, value = line.split(b":", 1)
            headers.append((name.decode("latin-1").strip(), value.decode("latin-1").strip()))
        parsed.append((match.group(1), int(match.group(2)), match.group(3) or "", headers))
    if not parsed:
        return "unknown", 0, "", [], []
    redirects = []
    for _version, status, _reason, headers in parsed[:-1]:
        redirects.append({"status": status, "location": first_header(headers, "Location")})
    version, status, reason, headers = parsed[-1]
    return version, status, reason, headers, redirects


def fetch_url_curl(url: str, user_agent: str, timeout: float) -> AuditResponse:
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise FileNotFoundError("curl executable not found")
    accessed_at = utc_now_iso()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="danube-audit-") as temporary:
        temp = Path(temporary)
        headers_path = temp / "headers.bin"
        body_path = temp / "body.bin"
        command = [
            curl, "--disable", "--silent", "--show-error", "--verbose", "--location", "--max-redirs", "5",
            "--connect-timeout", str(min(10.0, timeout)), "--max-time", str(timeout),
            "--request", "GET", "--user-agent", user_agent,
            "--header", "Accept: application/json,application/xml,text/xml,text/csv,text/html;q=0.9,*/*;q=0.1",
            "--header", "Accept-Encoding: identity", "--dump-header", str(headers_path),
            "--output", str(body_path), "--write-out",
            "__AUDIT_META__%{http_code}\t%{url_effective}\t%{http_version}\t%{time_total}\t%{num_redirects}\t%{remote_ip}\t%{remote_port}\t%{time_namelookup}\t%{time_connect}\t%{time_appconnect}\t%{time_starttransfer}",
            url,
        ]
        completed = subprocess.run(command, capture_output=True, check=False, timeout=timeout + 5)
        raw_headers = headers_path.read_bytes() if headers_path.exists() else b""
        body = body_path.read_bytes() if body_path.exists() else b""
    version, parsed_status, reason, headers, redirects = _parse_curl_headers(raw_headers)
    output = completed.stdout.decode("utf-8", errors="replace")
    match = re.search(r"__AUDIT_META__(\d+)\t([^\t]*)\t([^\t]*)\t([^\t]*)\t(\d+)\t([^\t]*)\t([^\t]*)\t([^\t]*)\t([^\t]*)\t([^\t]*)\t([^\t]*)", output)
    status = int(match.group(1)) if match else parsed_status
    effective_url = match.group(2) if match and match.group(2) else url
    http_version = match.group(3) if match and match.group(3) else version
    elapsed = float(match.group(4)) if match else time.perf_counter() - started
    verbose = completed.stderr.decode("utf-8", errors="replace")
    verbose = re.sub(r"(?im)^(>\s*(?:authorization|proxy-authorization|cookie):\s*).*$", r"\1<redacted>", verbose)
    tls_match = re.search(r"SSL connection using\s+([^\s/]+)(?:\s*/\s*([^\r\n]+))?", verbose, flags=re.I)
    network = {
        "remote_ip": match.group(6) if match else "",
        "remote_port": match.group(7) if match else "",
        "time_namelookup_seconds": float(match.group(8)) if match and match.group(8) else None,
        "time_connect_seconds": float(match.group(9)) if match and match.group(9) else None,
        "time_tls_seconds": float(match.group(10)) if match and match.group(10) else None,
        "time_starttransfer_seconds": float(match.group(11)) if match and match.group(11) else None,
        "tls_version": tls_match.group(1) if tls_match else "not reported by curl",
        "tls_cipher": tls_match.group(2).strip() if tls_match and tls_match.group(2) else "not reported by curl",
        "curl_verbose": verbose,
    }
    error = None if completed.returncode == 0 else f"curl exit {completed.returncode}: {verbose.strip()}"
    return AuditResponse(url, effective_url, status, reason, headers, body, elapsed, redirects,
                         http_version, accessed_at, error=error, network_metadata=network)


def fetch_url_urllib(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: float = DEFAULT_TIMEOUT) -> AuditResponse:
    redirect = TrackingRedirectHandler()
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(redirect, urllib.request.HTTPSHandler(context=context))
    request = urllib.request.Request(url, method="GET", headers={
        "User-Agent": user_agent,
        "Accept": "application/json,application/xml,text/xml,text/csv,text/html;q=0.9,*/*;q=0.1",
        "Accept-Encoding": "identity",
    })
    started = time.perf_counter()
    accessed_at = utc_now_iso()
    try:
        response = opener.open(request, timeout=timeout)
        body = response.read()
        headers = list(response.headers.raw_items())
        version = {10: "1.0", 11: "1.1", 20: "2"}.get(getattr(response, "version", 0), str(getattr(response, "version", "unknown")))
        return AuditResponse(url, response.geturl(), response.status, response.reason or "", headers, body,
                             time.perf_counter() - started, redirect.chain, version, accessed_at)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        headers = list(exc.headers.raw_items()) if exc.headers else []
        version = {10: "1.0", 11: "1.1", 20: "2"}.get(getattr(exc, "version", 0), str(getattr(exc, "version", "unknown")))
        return AuditResponse(url, exc.geturl(), exc.code, exc.reason or "", headers, body,
                             time.perf_counter() - started, redirect.chain, version, accessed_at,
                             f"HTTPError: {exc.code}")
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return AuditResponse(url, url, 0, "", [], b"", time.perf_counter() - started,
                             redirect.chain, "unknown", accessed_at, f"{type(exc).__name__}: {exc}")


def fetch_url(url: str, user_agent: str = DEFAULT_USER_AGENT, timeout: float = DEFAULT_TIMEOUT) -> AuditResponse:
    if shutil.which("curl") or shutil.which("curl.exe"):
        return fetch_url_curl(url, user_agent, timeout)
    return fetch_url_urllib(url, user_agent, timeout)

def ensure_safe_output(path: Path, repository_root: Path | None = None) -> None:
    resolved = path.resolve()
    root = (repository_root or Path.cwd()).resolve()
    forbidden = [(root / relative).resolve() for relative in PRODUCTION_DIRS]
    for candidate in forbidden:
        try:
            resolved.relative_to(candidate)
        except ValueError:
            continue
        raise ValueError(f"Audit output may not be written under production path: {candidate}")


def endpoint_inventory(country: str) -> list[dict[str, Any]]:
    source = SOURCES[country]
    rows = [{
        "endpoint_id": "bg-current-hydrology" if country == "bg" else f"{country}-primary", "endpoint_url": source["url"],
        "official": True, "documented": bool(source["documented"]),
        "endpoint_type": source["endpoint_type"], "method": "GET",
        "authentication": source["authentication"], "evidence_url": source["evidence_url"],
    }]
    if country == "rs":
        rows.append({
            "endpoint_id": "rs-hydrology-overview", "endpoint_url": "https://www.hidmet.gov.rs/eng/hidrologija/naslovna_stanje.php",
            "official": True, "documented": False, "endpoint_type": "official-html-index",
            "method": "GET", "authentication": "none", "evidence_url": "https://www.hidmet.gov.rs/eng/hidrologija/naslovna_stanje.php",
        })
    if country == "hr":
        rows.append({
            "endpoint_id": "hr-waterlevels-page", "endpoint_url": "https://www.vodniputovi.hr/en/services/waterlevels/",
            "official": True, "documented": False, "endpoint_type": "official-dynamic-page",
            "method": "GET", "authentication": "none", "evidence_url": "https://www.vodniputovi.hr/en/services/waterlevels/",
        })
    if country == "bg":
        rows.extend([{
            "endpoint_id": "bg-forecast", "endpoint_url": "https://www.appd-bg.org/forecasts-en",
            "official": True, "documented": False, "endpoint_type": "official-semantic-html",
            "method": "GET", "authentication": "none", "evidence_url": "https://www.appd-bg.org/forecasts-en",
        }, {
            "endpoint_id": "bg-open-data", "endpoint_url": "https://www.appd-bg.org/pages-en?id=opendata",
            "official": True, "documented": False, "endpoint_type": "official-document-index",
            "method": "GET", "authentication": "none", "evidence_url": "https://www.appd-bg.org/pages-en?id=opendata",
        }, {
            "endpoint_id": "bg-legacy-exploration", "endpoint_url": "https://appd-bg.org/exploration#data_hydro-bg",
            "official": True, "documented": False, "endpoint_type": "legacy-route",
            "method": "GET", "authentication": "none", "evidence_url": "https://appd-bg.org/",
        }])
    if country == "at":
        rows.append({
            "endpoint_id": "at-gauge-list-no-key", "endpoint_url": "https://opendata2.doris-info.at/doris/api/1.0/gauge/list",
            "official": True, "documented": True, "endpoint_type": "official-openapi",
            "method": "GET", "authentication": "partner key required; 403 without key",
            "evidence_url": "https://opendata2.doris-info.at/v3/api-docs/Opendata",
        })
    if source["initial_url"] != source["url"] and country != "bg":
        rows.append({
            "endpoint_id": f"{country}-initial", "endpoint_url": source["initial_url"],
            "official": True, "documented": False, "endpoint_type": "landing-page",
            "method": "GET", "authentication": "none observed", "evidence_url": source["initial_url"],
        })
    return rows


def terms_summary(country: str) -> dict[str, Any]:
    source = SOURCES[country]
    return {
        "provider_id": source["provider_id"], "terms_url": source["terms_url"],
        "license_or_reuse_status": source["license"],
        "legal_notice": "Technical inventory only; not legal advice.",
        "recommendation": (
            "integration permitted under DL-DE-Zero-2.0" if country == "de" else
            "apply published attribution, transformation, period and scope conditions" if country == "bg" else
            "review explicit official terms before production republication"
        ),
        "accessed_at_utc": utc_now_iso(),
    }


def save_audit(country: str, directory: Path, response: AuditResponse, user_agent: str) -> dict[str, Any]:
    ensure_safe_output(directory)
    directory.mkdir(parents=True, exist_ok=True)
    content_type = first_header(response.headers, "Content-Type")
    classification = classify_body(response.status, response.headers, response.body)
    dns = resolve_dns(response.effective_url)
    request_meta = {
        "requested_url": response.requested_url, "effective_url": response.effective_url,
        "method": "GET", "headers_sent": {"User-Agent": user_agent, "Accept": "application/json,application/xml,text/xml,text/csv,text/html;q=0.9,*/*;q=0.1", "Accept-Encoding": "identity"},
        "client": "curl" if response.network_metadata is not None else "Python urllib", "http_version_requested": "client default negotiation",
        "redirect_policy": "follow, maximum 5",
        "redirect_count": len(response.redirect_chain), "redirect_chain": response.redirect_chain,
        "timeout_seconds": DEFAULT_TIMEOUT, "retry_count": 0,
        "no_retry_statuses": [401, 403, 429], "accessed_at_utc": response.accessed_at_utc,
        "read_only": True,
    }
    json_write(directory / "request.json", request_meta)
    header_lines = [f"HTTP/{response.http_version} {response.status} {response.reason}".rstrip()]
    header_lines += [f"{name}: {value}" for name, value in response.headers]
    safe_text_write(directory / "response_headers.txt", "\n".join(header_lines) + "\n")
    (directory / "response_body.bin").write_bytes(response.body)
    text, encoding = decode_text(response.body, content_type)
    if text is not None and len(response.body) <= TEXT_LIMIT:
        safe_text_write(directory / "response_body.txt", text)
    schema = infer_schema(classification, response.body, content_type)
    stations = extract_station_sample(country, classification, response.body, content_type)
    summary = {
        "country_code": country, "country_name": SOURCES[country]["country_name"],
        "provider_id": SOURCES[country]["provider_id"], "provider_name": SOURCES[country]["provider_name"],
        "requested_url": response.requested_url, "effective_url": response.effective_url,
        "http_status": response.status, "http_reason": response.reason,
        "content_type": content_type, "content_length_header": first_header(response.headers, "Content-Length"),
        "content_encoding": first_header(response.headers, "Content-Encoding"),
        "cache_control": first_header(response.headers, "Cache-Control"), "etag": first_header(response.headers, "ETag"),
        "last_modified": first_header(response.headers, "Last-Modified"), "server": first_header(response.headers, "Server"),
        "http_version": response.http_version, "tls_version": (response.network_metadata or {}).get("tls_version", "not exposed by urllib"),
        "elapsed_seconds": response.elapsed_seconds, "body_size": len(response.body),
        "body_sha256": sha256_bytes(response.body), "classification": classification,
        "text_encoding": encoding, "redirect_count": len(response.redirect_chain),
        "dns": {**dns, "addresses": [{**row, "address_masked": mask_ip(row["address"])} for row in dns["addresses"]]},
        "station_sample_count": len(stations), "error": response.error,
        "network": response.network_metadata or {},
        "audit_environment": {"os": platform.system(), "os_release": platform.release(), "python": sys.version.split()[0]},
    }
    if response.network_metadata and response.network_metadata.get("curl_verbose"):
        safe_text_write(directory / "curl_verbose.txt", str(response.network_metadata["curl_verbose"]))
    json_write(directory / "summary.json", summary)
    json_write(directory / "schema.json", schema)
    json_write(directory / "station_sample.json", stations)
    json_write(directory / "endpoint_inventory.json", endpoint_inventory(country))
    json_write(directory / "network_requests.json", [{
        "url": response.requested_url, "effective_url": response.effective_url, "method": "GET",
        "status": response.status, "content_type": content_type,
    }])
    json_write(directory / "terms_summary.json", terms_summary(country))
    json_write(directory / "raw_sha256.json", {
        "response_body.bin": sha256_bytes(response.body),
        "response_headers.txt": sha256_bytes((directory / "response_headers.txt").read_bytes()),
    })
    return summary


def public_summary(summary: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(summary))
    dns = value.get("dns") or {}
    for row in dns.get("addresses") or []:
        row.pop("address", None)
    network = value.get("network") or {}
    if network.get("remote_ip"):
        network["remote_ip_masked"] = mask_ip(network["remote_ip"])
    network.pop("remote_ip", None)
    network.pop("curl_verbose", None)
    return value


def generate_report(roots: Iterable[Path], output: Path) -> str:
    summaries: list[dict[str, Any]] = []
    for root in roots:
        for path in root.rglob("summary.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if value.get("country_code") in SOURCES:
                summaries.append(public_summary(value))
    summaries.sort(key=lambda row: COUNTRY_ORDER.index(row["country_code"]))
    lines = [
        "# Danube source HTTP audit report", "",
        f"Generated: `{utc_now_iso()}`", "",
        "This is a low-volume technical observation, not a statement of legal permission or endpoint stability.", "",
        "| country | provider | status | final URL | content type | class | bytes | SHA-256 | redirects |",
        "|---|---|---:|---|---|---|---:|---|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['country_code']} | {row['provider_id']} | {row['http_status']} | {row['effective_url']} | "
            f"{row['content_type']} | {row['classification']} | {row['body_size']} | `{row['body_sha256']}` | {row['redirect_count']} |"
        )
    lines += ["", "## Interpretation limits", "",
              "- HTTP success does not establish reuse permission or production stability.",
              "- An undocumented JSON endpoint remains an internal implementation detail until the provider documents it.",
              "- A 401/403/429 is recorded without retry or bypass attempts.", ""]
    report = "\n".join(lines)
    ensure_safe_output(output)
    safe_text_write(output, report)
    return report


def run_browser_audit(country: str, directory: Path, user_agent: str) -> dict[str, Any]:
    """One transparent Chromium navigation; no stealth, proxy, challenge handling, or cookie reuse."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is not installed; run HTTP-only or install the pinned audit dependency") from exc
    requests: list[dict[str, Any]] = []
    consoles: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    main: dict[str, Any] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()
        page.on("request", lambda req: requests.append({"url": req.url, "method": req.method, "resource_type": req.resource_type, "post_data": "<omitted>" if req.post_data else None}))
        page.on("response", lambda res: requests.append({"url": res.url, "method": res.request.method, "resource_type": res.request.resource_type, "status": res.status, "content_type": res.headers.get("content-type", "")}))
        page.on("requestfailed", lambda req: failures.append({"url": req.url, "error": str(req.failure)}))
        page.on("console", lambda msg: consoles.append({"type": msg.type, "text": msg.text[:2000]}))
        try:
            response = page.goto(SOURCES[country]["initial_url"], wait_until="domcontentloaded", timeout=int(DEFAULT_TIMEOUT * 1000))
            if response:
                body = response.body()
                main = {"url": response.url, "status": response.status, "headers": response.headers, "body_sha256": sha256_bytes(body), "body_size": len(body)}
        except Exception as exc:  # Playwright errors are evidence, not a failed audit run.
            error = f"{type(exc).__name__}: {exc}"
            failures.append({"url": SOURCES[country]["initial_url"], "error": error})
            main = {"url": SOURCES[country]["initial_url"], "status": 0, "error": error}
        finally:
            context.close()
            browser.close()
    json_write(directory / "browser_network_requests.json", requests)
    json_write(directory / "browser_console.json", consoles)
    json_write(directory / "browser_request_failures.json", failures)
    json_write(directory / "browser_main_response.json", main)
    return main


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--source", choices=COUNTRY_ORDER)
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--http-only", action="store_true")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--max-requests", type=int, default=DEFAULT_MAX_REQUESTS)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--report-from", type=Path, nargs="+")
    parser.add_argument("--report-output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.report_from:
        output = args.report_output or Path("docs/DANUBE_SOURCE_HTTP_AUDIT.md")
        generate_report(args.report_from, output)
        print(json.dumps({"report": str(output)}, ensure_ascii=False))
        return 0
    countries = list(COUNTRY_ORDER) if args.all else [args.source or "ro"]
    if args.max_requests < len(countries):
        raise SystemExit(f"--max-requests={args.max_requests} is below the {len(countries)} selected HTTP requests")
    output = args.output_dir or Path("_audit_source/danube_international") / timestamp_slug()
    ensure_safe_output(output)
    output.mkdir(parents=True, exist_ok=True)
    if args.browser and not args.http_only:
        browser_results = []
        for index, country in enumerate(countries):
            if index:
                time.sleep(1.0)
            browser_results.append({"country": country, **run_browser_audit(country, output / country, args.user_agent)})
        print(json.dumps({"output_dir": str(output), "browser_results": browser_results}, ensure_ascii=False, indent=2))
        return 0
    summaries = []
    for index, country in enumerate(countries):
        if index:
            time.sleep(1.0)
        response = fetch_url(SOURCES[country]["url"], args.user_agent, DEFAULT_TIMEOUT)
        country_dir = output / country
        summaries.append(save_audit(country, country_dir, response, args.user_agent))
        if args.browser and not args.http_only:
            run_browser_audit(country, country_dir, args.user_agent)
    comparison = {"generated_at_utc": utc_now_iso(), "request_count": len(countries),
                  "summaries": [public_summary(row) for row in summaries]}
    json_write(output / "comparison" / "summary.json", comparison)
    json_write(output / "manifests" / "run.json", {
        "countries": countries, "max_requests": args.max_requests, "user_agent": args.user_agent,
        "browser": bool(args.browser and not args.http_only), "generated_at_utc": utc_now_iso(),
    })
    print(json.dumps({"output_dir": str(output), "results": [{"country": row["country_code"], "status": row["http_status"], "classification": row["classification"]} for row in summaries]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())