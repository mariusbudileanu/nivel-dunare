#!/usr/bin/env python3
"""Capture reproducible, non-invasive HTTP diagnostics for the AFDJ XML endpoint."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo


DEFAULT_URL = "https://afdj.ro/ro/tabel_cotele_dunarii/xml"
PRODUCTION_URL = "https://www.afdj.ro/ro/tabel_cotele_dunarii/xml"
PRODUCTION_REFERER = "https://www.afdj.ro/ro/cotele-dunarii"
PRODUCTION_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)
TRANSPARENT_USER_AGENT = (
    "NivelDunareMonitor/1.0 "
    "(+https://github.com/mariusbudileanu/nivel-dunare)"
)
XML_ACCEPT = "application/xml,text/xml;q=0.9,*/*;q=0.1"
BUCHAREST = ZoneInfo("Europe/Bucharest")
TEXT_LIMIT = 1024 * 1024
ORIENTATION_TERMS = (
    "Cloudflare", "Attention Required", "Sorry, you have been blocked",
    "Just a moment", "Checking your browser", "Enable JavaScript and cookies",
    "Ray ID", "Access denied", "Forbidden", "Drupal", "nginx", "Apache",
)
CLOUDFLARE_FIELDS = (
    "Server", "CF-RAY", "CF-Cache-Status", "CF-Mitigated", "Content-Type",
    "Content-Length", "Location", "Retry-After", "Set-Cookie", "NEL",
    "Report-To", "X-Frame-Options", "X-Content-Type-Options",
)


@dataclass
class CapturedResponse:
    status_line: bytes
    header_block: bytes
    all_header_blocks: bytes
    headers: list[tuple[str, str]]
    body: bytes
    verbose: bytes
    timings: dict[str, Any]
    network: dict[str, Any]
    request: dict[str, Any]

    @property
    def status(self) -> int:
        match = re.search(rb"\s(\d{3})(?:\s|$)", self.status_line)
        return int(match.group(1)) if match else int(self.timings.get("http_code") or 0)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp_slug(value: datetime | None = None) -> str:
    return (value or utc_now()).strftime("%Y%m%dT%H%M%SZ")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def safe_label(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-") or "unknown"


def unique_result_dir(base: Path, profile: str, client: str) -> Path:
    stem = f"{timestamp_slug()}__{safe_label(profile)}__{safe_label(client)}"
    candidate = base / stem
    index = 2
    while candidate.exists():
        candidate = base / f"{stem}__{index}"
        index += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def parse_content_type(value: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in value.split(";")]
    mime = parts[0].casefold() if parts else ""
    charset = None
    for part in parts[1:]:
        match = re.match(r"(?i)charset\s*=\s*[\"']?([^\"';\s]+)", part)
        if match:
            charset = match.group(1)
            break
    return mime, charset


def is_textual_content_type(value: str) -> bool:
    mime, _charset = parse_content_type(value)
    return (
        mime.startswith("text/")
        or mime.endswith(("+xml", "+json"))
        or mime in {
            "application/xml", "application/json", "application/xhtml+xml",
            "application/javascript", "application/problem+json",
        }
    )


def decode_body_losslessly(body: bytes, content_type: str) -> tuple[str | None, str | None]:
    _mime, declared = parse_content_type(content_type)
    encodings = [declared] if declared else ["utf-8"]
    for encoding in encodings:
        if not encoding:
            continue
        try:
            text = body.decode(encoding, errors="strict")
            if text.encode(encoding, errors="strict") == body:
                return text, encoding
        except (LookupError, UnicodeError):
            continue
    return None, declared


def split_header_blocks(raw: bytes) -> list[bytes]:
    blocks: list[bytes] = []
    position = 0
    for match in re.finditer(rb"\r?\n\r?\n", raw):
        block = raw[position:match.end()]
        position = match.end()
        if block.lstrip().startswith(b"HTTP/"):
            blocks.append(block)
    tail = raw[position:]
    if tail.lstrip().startswith(b"HTTP/"):
        blocks.append(tail)
    return blocks


def normalize_header_block(block: bytes) -> bytes:
    if re.search(rb"\r?\n\r?\n$", block):
        return block
    newline = b"\r\n" if b"\r\n" in block else b"\n"
    return block.rstrip(b"\r\n") + newline + newline


def parse_header_block(block: bytes) -> tuple[bytes, list[tuple[str, str]]]:
    lines = re.split(rb"\r?\n", block.rstrip(b"\r\n"))
    status_line = lines[0] if lines else b"NO HTTP RESPONSE"
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if b":" not in line:
            continue
        name, value = line.split(b":", 1)
        headers.append((name.decode("latin-1"), value.lstrip().decode("latin-1")))
    return status_line, headers


def header_values(headers: Sequence[tuple[str, str]], name: str) -> list[str]:
    wanted = name.casefold()
    return [value for key, value in headers if key.casefold() == wanted]


def last_header(headers: Sequence[tuple[str, str]], name: str) -> str:
    values = header_values(headers, name)
    return values[-1] if values else ""


def redact_cookie_value(value: str) -> str:
    cookie_name = value.split("=", 1)[0].strip() or "cookie"
    return f"{cookie_name}=<redacted>"


def report_headers(headers: Sequence[tuple[str, str]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for field in CLOUDFLARE_FIELDS:
        values = header_values(headers, field)
        if field.casefold() == "set-cookie":
            values = [redact_cookie_value(value) for value in values]
        output[field] = values if len(values) > 1 else values[0] if values else ""
    return output


def redact_outbound_verbose(raw: bytes) -> bytes:
    text = raw.decode("utf-8", errors="replace")
    sensitive = re.compile(r"(?im)^(>\s*(?:authorization|proxy-authorization|cookie):)\s*.*$")
    text = sensitive.sub(r"\1 <redacted>", text)
    text = re.sub(r"(?i)(https?://)[^/@\s:]+:[^/@\s]+@", r"\1<redacted>@", text)
    return text.encode("utf-8")


def mask_ip(value: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return ""
    if isinstance(address, ipaddress.IPv4Address):
        parts = value.split(".")
        return ".".join(parts[:3] + ["xxx"])
    network = ipaddress.ip_network(f"{address}/48", strict=False)
    return f"{network.network_address.compressed}/48"

def collect_environment(label: str, curl_path: str | None) -> dict[str, Any]:
    curl_version = ""
    if curl_path:
        result = subprocess.run([curl_path, "--version"], capture_output=True, text=True, check=False)
        curl_version = result.stdout.strip() or result.stderr.strip()
    environment = {
        "environment_label": label,
        "is_github_actions": os.environ.get("GITHUB_ACTIONS", "").casefold() == "true",
        "operating_system": platform.system(),
        "system_release": platform.release(),
        "system_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "curl_path": curl_path or "",
        "curl_version": curl_version,
        "tls_backend": curl_version.splitlines()[0] if curl_version else "unknown",
        "runner_name": os.environ.get("RUNNER_NAME", ""),
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "runner_arch": os.environ.get("RUNNER_ARCH", ""),
        "runner_environment": os.environ.get("RUNNER_ENVIRONMENT", ""),
        "runner_image_os": os.environ.get("ImageOS", ""),
        "github_run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "github_sha": os.environ.get("GITHUB_SHA", ""),
        "github_repository": os.environ.get("GITHUB_REPOSITORY", ""),
        "collected_at_utc": utc_now().isoformat(),
        "available_region_metadata": {
            key: os.environ.get(key, "")
            for key in ("AZURE_HTTP_USER_AGENT", "AWS_REGION", "GOOGLE_CLOUD_REGION")
            if os.environ.get(key)
        },
    }
    return environment


def collect_dns(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    started = time.perf_counter()
    addresses: list[dict[str, str]] = []
    error = ""
    try:
        seen: set[tuple[str, str]] = set()
        for family, _socktype, _proto, _canonname, sockaddr in socket.getaddrinfo(hostname, port):
            address = str(sockaddr[0])
            family_name = "IPv6" if family == socket.AF_INET6 else "IPv4" if family == socket.AF_INET else str(family)
            if (family_name, address) not in seen:
                addresses.append({"family": family_name, "address": address})
                seen.add((family_name, address))
    except OSError as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {
        "hostname": hostname,
        "port": port,
        "addresses": addresses,
        "resolution_seconds_python": round(time.perf_counter() - started, 6),
        "error": error,
    }


def _fetch_json_once(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": TRANSPARENT_USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read()
        return {
            "source": url,
            "http_status": int(response.status),
            "data": json.loads(body.decode("utf-8")),
        }


def collect_egress_metadata() -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    for url in ("https://ipinfo.io/json", "https://ifconfig.co/json"):
        try:
            observations.append(_fetch_json_once(url))
        except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
            observations.append({"source": url, "error": f"{type(exc).__name__}: {exc}"})
    normalized: list[dict[str, str]] = []
    for item in observations:
        data = item.get("data") or {}
        ip = str(data.get("ip") or "")
        org = str(data.get("org") or data.get("asn_org") or "")
        asn = str(data.get("asn") or "")
        if not asn and org.upper().startswith("AS"):
            asn = org.split(" ", 1)[0]
        provider = org.split(" ", 1)[1] if org.upper().startswith("AS") and " " in org else org
        normalized.append({
            "source": str(item.get("source") or ""),
            "ip": ip,
            "ip_version": str(ipaddress.ip_address(ip).version) if ip else "",
            "asn": asn,
            "provider": provider,
            "country": str(data.get("country") or data.get("country_iso") or ""),
            "region": str(data.get("region") or data.get("region_name") or ""),
            "city": str(data.get("city") or ""),
            "error": str(item.get("error") or ""),
        })
    return {
        "sources_are_advisory": True,
        "observations": observations,
        "normalized": normalized,
        "collected_at_utc": utc_now().isoformat(),
    }


def shared_environment(base: Path, label: str, url: str, curl_path: str | None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    shared = base / "_shared"
    shared.mkdir(parents=True, exist_ok=True)
    environment_path = shared / "environment.json"
    dns_host = urllib.parse.urlparse(url).hostname or "unknown"
    dns_path = shared / f"dns-{safe_label(dns_host)}.json"
    egress_path = shared / "egress.json"
    environment = read_json(environment_path)
    if not environment:
        environment = collect_environment(label, curl_path)
        write_json(environment_path, environment)
    dns = read_json(dns_path)
    if not dns:
        dns = collect_dns(url)
        write_json(dns_path, dns)
    egress = read_json(egress_path)
    if not egress:
        egress = collect_egress_metadata()
        write_json(egress_path, egress)
    return environment, dns, egress


def parse_curl_write_out(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace")
    output: dict[str, Any] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {
            "time_namelookup", "time_connect", "time_appconnect",
            "time_starttransfer", "time_total", "size_download",
        }:
            try:
                output[key] = float(value)
            except ValueError:
                output[key] = value
        elif key in {"http_code", "remote_port", "local_port", "num_redirects", "ssl_verify_result"}:
            try:
                output[key] = int(value)
            except ValueError:
                output[key] = value
        else:
            output[key] = value
    return output


def parse_verbose_tls(verbose: bytes) -> dict[str, str]:
    text = verbose.decode("utf-8", errors="replace")
    tls_version = ""
    cipher = ""
    patterns = (
        r"SSL connection using\s+([^\s/]+)\s*/\s*([^\r\n]+)",
        r"SSL connection using\s+([^\s]+)\s+with cipher\s+([^\r\n]+)",
        r"Cipher is\s+([^\r\n]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        if len(match.groups()) >= 2:
            tls_version = match.group(1).strip()
            cipher = match.group(2).strip()
        else:
            cipher = match.group(1).strip()
        break
    if not tls_version:
        match = re.search(r"(?:TLSv|TLS )([0-9.]+)", text, re.IGNORECASE)
        if match:
            tls_version = "TLSv" + match.group(1)
    return {"tls_version": tls_version, "tls_cipher": cipher}


def parse_outbound_headers(verbose: bytes) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    current: list[tuple[str, str]] | None = None
    request_line = ""
    for line in verbose.decode("utf-8", errors="replace").splitlines():
        if re.match(r"^>\s+(?:GET|HEAD|POST|PUT|DELETE|OPTIONS|PATCH)\s+", line):
            if current is not None:
                requests.append({"request_line": request_line, "headers": current})
            request_line = line[2:].strip()
            current = []
        elif current is not None and line.startswith("> ") and ":" in line:
            name, value = line[2:].split(":", 1)
            if name.casefold() in {"cookie", "authorization", "proxy-authorization"}:
                value = " <redacted>"
            current.append((name, value.lstrip()))
        elif current is not None and line in {">", "> "}:
            requests.append({"request_line": request_line, "headers": current})
            current = None
    if current is not None:
        requests.append({"request_line": request_line, "headers": current})
    return requests


def inspect_xml_body(body: bytes) -> dict[str, Any]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        return {"well_formed": False, "station_count": None, "parse_error": str(exc)}
    station_count = sum(1 for child in list(root) if child.tag.split("}", 1)[-1] == "item")
    return {"well_formed": True, "root": root.tag.split("}", 1)[-1], "station_count": station_count}


def classify_response(status: int, headers: Sequence[tuple[str, str]], body: bytes) -> tuple[str, list[str]]:
    content_type = last_header(headers, "Content-Type")
    text, _encoding = decode_body_losslessly(body, content_type)
    searchable = text or body.decode("latin-1", errors="ignore")
    indicators = [term for term in ORIENTATION_TERMS if term.casefold() in searchable.casefold()]
    server = last_header(headers, "Server").casefold()
    mitigated = last_header(headers, "CF-Mitigated").casefold()
    if status == 403 and "challenge" in mitigated:
        return "cloudflare-challenge", indicators
    if status == 403 and "cloudflare" in server and any(term in indicators for term in ("Sorry, you have been blocked", "Access denied")):
        return "cloudflare-block-page", indicators
    if status in {403, 503} and "cloudflare" in server and any(term in indicators for term in ("Just a moment", "Checking your browser", "Enable JavaScript and cookies")):
        return "cloudflare-challenge-page", indicators
    if status == 403 and "cloudflare" in server:
        return "cloudflare-403-undetermined", indicators
    if 200 <= status < 300 and ("xml" in content_type.casefold() or body.lstrip().startswith(b"<")):
        xml = inspect_xml_body(body)
        return ("xml-well-formed" if xml.get("well_formed") else "xml-invalid"), indicators
    return f"http-{status or 'no-response'}-unclassified", indicators

def egress_summary(egress: dict[str, Any]) -> dict[str, str]:
    normalized = [item for item in egress.get("normalized", []) if item.get("ip")]
    first = normalized[0] if normalized else {}
    return {
        "public_ip": str(first.get("ip") or ""),
        "public_ip_masked": mask_ip(str(first.get("ip") or "")),
        "ip_version": str(first.get("ip_version") or ""),
        "asn": str(first.get("asn") or ""),
        "provider": str(first.get("provider") or ""),
        "country": str(first.get("country") or ""),
        "region": str(first.get("region") or ""),
    }


def save_response_artifacts(
    directory: Path,
    capture: CapturedResponse,
    environment: dict[str, Any],
    dns: dict[str, Any],
    egress: dict[str, Any],
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    header_block = normalize_header_block(capture.header_block)
    full_response = header_block + capture.body
    status_line_text = capture.status_line.decode("latin-1", errors="strict")
    content_type = last_header(capture.headers, "Content-Type")
    decoded_body, decoded_charset = decode_body_losslessly(capture.body, content_type)
    classification, indicators = classify_response(capture.status, capture.headers, capture.body)
    xml_details = inspect_xml_body(capture.body) if "xml" in content_type.casefold() or capture.body.lstrip().startswith(b"<") else {}

    status_newline = b"\r\n" if b"\r\n" in header_block else b"\n"
    (directory / "response_status.txt").write_bytes(capture.status_line + status_newline)
    (directory / "response_headers.txt").write_bytes(header_block)
    (directory / "response_headers_all.txt").write_bytes(capture.all_header_blocks)
    (directory / "response_body.bin").write_bytes(capture.body)
    if decoded_body is not None and is_textual_content_type(content_type):
        (directory / "response_body.txt").write_text(decoded_body, encoding="utf-8", newline="")
    (directory / "response_full.txt").write_bytes(full_response)
    (directory / "curl_verbose.txt").write_bytes(redact_outbound_verbose(capture.verbose))
    write_json(directory / "request.json", capture.request)
    write_json(directory / "environment.json", environment)
    write_json(directory / "dns.json", dns)
    network = dict(capture.network)
    network["egress"] = egress
    write_json(directory / "network.json", network)
    write_json(directory / "timings.json", capture.timings)
    hashes = {
        "response_body": {"sha256": sha256_bytes(capture.body), "size_bytes": len(capture.body)},
        "response_full": {"sha256": sha256_bytes(full_response), "size_bytes": len(full_response)},
        "response_headers": {"sha256": sha256_bytes(header_block), "size_bytes": len(header_block)},
        "curl_verbose": {"sha256": sha256_bytes(redact_outbound_verbose(capture.verbose)), "size_bytes": len(redact_outbound_verbose(capture.verbose))},
    }
    write_json(directory / "sha256.json", hashes)
    egress_fields = egress_summary(egress)
    summary = {
        "artifact_version": 1,
        "result_directory": directory.name,
        "environment_label": environment.get("environment_label", ""),
        "is_github_actions": environment.get("is_github_actions", False),
        "operating_system": environment.get("operating_system", ""),
        "client_profile": capture.request.get("profile", ""),
        "client_label": capture.request.get("client", ""),
        "requested_url": capture.request.get("url", ""),
        "final_url": capture.timings.get("url_effective", capture.request.get("url", "")),
        "http_status": capture.status,
        "status_line": status_line_text,
        "http_version": capture.network.get("http_version", capture.timings.get("http_version", "")),
        "tls_version": capture.network.get("tls_version", ""),
        "tls_cipher": capture.network.get("tls_cipher", ""),
        "resolved_server_ip": capture.network.get("remote_ip", ""),
        "resolved_server_port": capture.network.get("remote_port", ""),
        "content_type": content_type,
        "body_size": len(capture.body),
        "body_sha256": hashes["response_body"]["sha256"],
        "response_full_sha256": hashes["response_full"]["sha256"],
        "decoded_charset": decoded_charset or "",
        "response_classification": classification,
        "orientation_indicators": indicators,
        "cloudflare_headers": report_headers(capture.headers),
        "xml": xml_details,
        "curl_exit_code": capture.timings.get("curl_exit_code"),
        **egress_fields,
    }
    write_json(directory / "summary.json", summary)
    return summary


def _write_exact_403_to_log(directory: Path, summary: dict[str, Any]) -> None:
    if int(summary.get("http_status") or 0) != 403:
        return
    headers = (directory / "response_headers.txt").read_bytes()
    body = (directory / "response_body.bin").read_bytes()
    content_type = str(summary.get("content_type") or "")
    sys.stdout.write("===== BEGIN EXACT 403 RESPONSE HEADERS =====\n")
    sys.stdout.flush()
    sys.stdout.buffer.write(headers)
    if not headers.endswith((b"\n", b"\r")):
        sys.stdout.buffer.write(b"\n")
    sys.stdout.write("===== END EXACT 403 RESPONSE HEADERS =====\n")
    if is_textual_content_type(content_type) and len(body) <= TEXT_LIMIT:
        sys.stdout.write("===== BEGIN EXACT 403 RESPONSE BODY =====\n")
        sys.stdout.flush()
        sys.stdout.buffer.write(body)
        if not body.endswith((b"\n", b"\r")):
            sys.stdout.buffer.write(b"\n")
        sys.stdout.write("===== END EXACT 403 RESPONSE BODY =====\n")
    else:
        sys.stdout.write(
            "403 body not printed in full because it is non-textual or exceeds 1 MiB.\n"
            f"size_bytes={len(body)}\n"
            f"sha256={sha256_bytes(body)}\n"
            f"artifact_path={directory / 'response_body.bin'}\n"
            "===== BEGIN FIRST 4096 BYTES =====\n"
        )
        sys.stdout.flush()
        sys.stdout.buffer.write(body[:4096])
        sys.stdout.write("\n===== END FIRST 4096 BYTES =====\n===== BEGIN LAST 4096 BYTES =====\n")
        sys.stdout.flush()
        sys.stdout.buffer.write(body[-4096:])
        sys.stdout.write("\n===== END LAST 4096 BYTES =====\n")
    sys.stdout.flush()


def curl_write_out_template() -> str:
    fields = (
        ("http_code", "%{http_code}"), ("http_version", "%{http_version}"),
        ("url_effective", "%{url_effective}"), ("remote_ip", "%{remote_ip}"),
        ("remote_port", "%{remote_port}"), ("local_ip", "%{local_ip}"),
        ("local_port", "%{local_port}"), ("num_redirects", "%{num_redirects}"),
        ("ssl_verify_result", "%{ssl_verify_result}"),
        ("content_type", "%{content_type}"), ("size_download", "%{size_download}"),
        ("time_namelookup", "%{time_namelookup}"), ("time_connect", "%{time_connect}"),
        ("time_appconnect", "%{time_appconnect}"),
        ("time_starttransfer", "%{time_starttransfer}"), ("time_total", "%{time_total}"),
    )
    return "\n".join(f"{key}={value}" for key, value in fields) + "\n"


def curl_profile_configuration(profile: str, url_override: str | None) -> tuple[str, list[str], list[tuple[str, str]], dict[str, Any]]:
    if profile == "production-profile":
        url = url_override or PRODUCTION_URL
        headers = [
            ("User-Agent", PRODUCTION_USER_AGENT),
            ("Accept-Language", "ro-RO,ro;q=0.9,en;q=0.8"),
            ("Referer", PRODUCTION_REFERER),
            ("Accept", XML_ACCEPT),
        ]
        flags = [
            "--fail-with-body", "--show-error", "--silent", "--location", "--compressed",
            "--retry", "3", "--retry-all-errors", "--retry-delay", "2",
            "--connect-timeout", "15", "--max-time", "90",
        ]
        details = {
            "redirect_policy": "follow (--location)",
            "connect_timeout_seconds": 15,
            "total_timeout_seconds_per_attempt": 90,
            "retry_count": 3,
            "retry_total_possible_attempts": 4,
            "http_version_requested": "curl default; ALPN negotiation (no forced HTTP version)",
            "reproduces_exact_production_wire_profile": url == PRODUCTION_URL,
            "production_profile_differences": [
                "--fail-with-body replaces --fail so the diagnostic can retain an HTTP error body",
                "verbose/header/write-out capture flags are diagnostic-only and do not alter request headers",
            ],
        }
        return url, flags, headers, details
    if profile == "transparent-minimal":
        url = url_override or DEFAULT_URL
        headers = [("User-Agent", TRANSPARENT_USER_AGENT), ("Accept", XML_ACCEPT)]
        flags = ["--show-error", "--silent", "--location", "--connect-timeout", "15", "--max-time", "90"]
        details = {
            "redirect_policy": "follow (--location)",
            "connect_timeout_seconds": 15,
            "total_timeout_seconds": 90,
            "retry_count": 0,
            "http_version_requested": "curl default; ALPN negotiation (no forced HTTP version)",
            "reproduces_exact_production_wire_profile": False,
            "cookies": "none configured",
            "referer": "none configured",
        }
        return url, flags, headers, details
    raise ValueError(f"Unsupported curl profile: {profile}")


def run_curl_profile(
    base: Path,
    profile: str,
    environment_label: str,
    client_label: str,
    url_override: str | None,
    print_body: bool,
) -> tuple[Path, dict[str, Any]]:
    curl_path = shutil.which("curl") or shutil.which("curl.exe")
    if not curl_path:
        raise RuntimeError("curl is required but was not found on PATH")
    url, profile_flags, configured_headers, details = curl_profile_configuration(profile, url_override)
    environment, dns, egress = shared_environment(base, environment_label, url, curl_path)
    directory = unique_result_dir(base, profile, client_label)
    raw_headers_path = directory / ".curl_headers.raw"
    raw_body_path = directory / ".curl_body.raw"
    verbose_path = directory / ".curl_verbose.raw"
    started = utc_now()
    request_metadata = {
        "url": url,
        "method": "GET",
        "headers": [{"name": name, "value": value} for name, value in configured_headers],
        "user_agent": next(value for name, value in configured_headers if name.casefold() == "user-agent"),
        "client": client_label,
        "profile": profile,
        "started_at_utc": started.isoformat(),
        "started_at_europe_bucharest": started.astimezone(BUCHAREST).isoformat(),
        **details,
        "credentials_or_local_cookies_recorded": False,
    }
    command = [curl_path, *profile_flags, "--request", "GET", "--verbose"]
    command.extend(["--dump-header", str(raw_headers_path), "--output", str(raw_body_path), "--stderr", str(verbose_path)])
    for name, value in configured_headers:
        if name.casefold() == "user-agent":
            command.extend(["--user-agent", value])
        elif name.casefold() == "referer":
            command.extend(["--referer", value])
        else:
            command.extend(["--header", f"{name}: {value}"])
    command.extend(["--write-out", curl_write_out_template(), url])
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    raw_headers = raw_headers_path.read_bytes() if raw_headers_path.is_file() else b""
    body = raw_body_path.read_bytes() if raw_body_path.is_file() else b""
    verbose = verbose_path.read_bytes() if verbose_path.is_file() else completed.stderr
    blocks = split_header_blocks(raw_headers)
    final_block = normalize_header_block(blocks[-1]) if blocks else b"NO HTTP RESPONSE\r\n\r\n"
    status_line, headers = parse_header_block(final_block)
    timings = parse_curl_write_out(completed.stdout)
    timings["curl_exit_code"] = completed.returncode
    timings["curl_stderr_outside_verbose"] = completed.stderr.decode("utf-8", errors="replace")
    tls = parse_verbose_tls(verbose)
    network = {
        "hostname": urllib.parse.urlparse(url).hostname or "",
        "remote_ip": timings.get("remote_ip", ""),
        "remote_port": timings.get("remote_port", ""),
        "local_ip": timings.get("local_ip", ""),
        "local_port": timings.get("local_port", ""),
        "http_version": timings.get("http_version", ""),
        **tls,
    }
    request_metadata["observed_requests"] = parse_outbound_headers(verbose)
    capture = CapturedResponse(
        status_line=status_line,
        header_block=final_block,
        all_header_blocks=raw_headers,
        headers=headers,
        body=body,
        verbose=verbose,
        timings=timings,
        network=network,
        request=request_metadata,
    )
    summary = save_response_artifacts(directory, capture, environment, dns, egress)
    for temporary in (raw_headers_path, raw_body_path, verbose_path):
        temporary.unlink(missing_ok=True)
    if summary["http_status"] == 403:
        _write_exact_403_to_log(directory, summary)
    elif print_body and (directory / "response_body.txt").is_file():
        print((directory / "response_body.txt").read_text(encoding="utf-8"))
    return directory, summary

def run_playwright_profile(
    base: Path,
    environment_label: str,
    client_label: str,
    url_override: str | None,
    print_body: bool,
) -> tuple[Path, dict[str, Any]]:
    url = url_override or DEFAULT_URL
    curl_path = shutil.which("curl") or shutil.which("curl.exe")
    environment, dns, egress = shared_environment(base, environment_label, url, curl_path)
    directory = unique_result_dir(base, "playwright-chromium", client_label)
    try:
        from importlib.metadata import version as package_version
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is unavailable; install the pinned diagnostic dependency") from exc

    environment = dict(environment)
    environment["playwright_version"] = package_version("playwright")
    console_entries: list[dict[str, str]] = []
    request_failures: list[dict[str, str]] = []
    cdp_documents: list[dict[str, Any]] = []
    started = utc_now()
    request_metadata: dict[str, Any] = {
        "url": url,
        "method": "GET",
        "headers": [],
        "user_agent": "Chromium default; recorded after launch",
        "client": client_label,
        "profile": "playwright-chromium",
        "started_at_utc": started.isoformat(),
        "started_at_europe_bucharest": started.astimezone(BUCHAREST).isoformat(),
        "redirect_policy": "browser default",
        "navigation_timeout_seconds": 90,
        "retry_count": 0,
        "http_version_requested": "Chromium default; ALPN negotiation",
        "reproduces_exact_production_wire_profile": False,
        "browser_constraints": {
            "single_main_navigation": True,
            "fresh_context": True,
            "cookies_reused": False,
            "stealth_plugins": False,
            "proxy_configured": False,
            "fingerprint_modified": False,
            "challenge_interaction": False,
        },
        "credentials_or_local_cookies_recorded": False,
    }
    response = None
    body = b""
    headers: list[tuple[str, str]] = []
    status_line = b"NO HTTP RESPONSE"
    navigation_error = ""
    screenshot_error = ""
    elapsed = 0.0
    final_url = url
    cdp_response: dict[str, Any] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("console", lambda message: console_entries.append({"type": message.type, "text": message.text}))
        page.on(
            "requestfailed",
            lambda request: request_failures.append({
                "url": request.url,
                "method": request.method,
                "failure": str(request.failure or ""),
            }),
        )
        session = context.new_cdp_session(page)
        session.send("Network.enable")

        def on_response_received(event: dict[str, Any]) -> None:
            if event.get("type") == "Document":
                cdp_documents.append(event)

        session.on("Network.responseReceived", on_response_received)
        request_metadata["user_agent"] = page.evaluate("navigator.userAgent")
        timer = time.perf_counter()
        try:
            response = page.goto(url, wait_until="commit", timeout=90_000)
            elapsed = time.perf_counter() - timer
            if response is None:
                navigation_error = "page.goto returned no main response"
            else:
                final_url = response.url
                body = response.body()
                try:
                    response_header_array = response.headers_array()
                    headers = [(str(item["name"]), str(item["value"])) for item in response_header_array]
                except Exception:
                    headers = [(str(name), str(value)) for name, value in response.all_headers().items()]
                try:
                    request_headers = response.request.headers_array()
                    configured = []
                    for item in request_headers:
                        name = str(item["name"])
                        value = str(item["value"])
                        if name.casefold() in {"cookie", "authorization", "proxy-authorization"}:
                            value = "<redacted>"
                        configured.append({"name": name, "value": value})
                    request_metadata["headers"] = configured
                except Exception:
                    request_metadata["headers"] = [
                        {"name": str(name), "value": "<redacted>" if str(name).casefold() == "cookie" else str(value)}
                        for name, value in response.request.all_headers().items()
                    ]
                matching = [
                    event for event in cdp_documents
                    if str(event.get("response", {}).get("url", "")) == final_url
                ]
                cdp_response = (matching[-1] if matching else cdp_documents[-1] if cdp_documents else {}).get("response", {})
                protocol = str(cdp_response.get("protocol") or "HTTP/1.1")
                protocol_text = "HTTP/2" if protocol in {"h2", "http/2"} else "HTTP/3" if protocol in {"h3", "http/3"} else protocol.upper()
                status_line = f"{protocol_text} {response.status} {response.status_text}".strip().encode("latin-1", errors="replace")
                classification, _indicators = classify_response(response.status, headers, body)
                if response.status == 403 or "challenge" in classification or "block-page" in classification:
                    try:
                        page.wait_for_timeout(500)
                        page.screenshot(path=str(directory / "response_screenshot.png"), full_page=True)
                    except Exception as exc:
                        screenshot_error = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            elapsed = time.perf_counter() - timer
            navigation_error = f"{type(exc).__name__}: {exc}"
        finally:
            browser.close()

    newline = b"\r\n"
    header_lines = [status_line] + [f"{name}: {value}".encode("latin-1", errors="replace") for name, value in headers]
    header_block = newline.join(header_lines) + newline + newline
    security = cdp_response.get("securityDetails") or {}
    network = {
        "hostname": urllib.parse.urlparse(url).hostname or "",
        "remote_ip": cdp_response.get("remoteIPAddress", ""),
        "remote_port": cdp_response.get("remotePort", ""),
        "http_version": cdp_response.get("protocol", ""),
        "tls_version": security.get("protocol", ""),
        "tls_cipher": security.get("cipher", ""),
        "cdp_security_details": security,
    }
    timings = {
        "navigation_elapsed_seconds": round(elapsed, 6),
        "url_effective": final_url,
        "navigation_error": navigation_error,
        "screenshot_error": screenshot_error,
        "cdp_timing": cdp_response.get("timing", {}),
        "curl_exit_code": None,
    }
    request_metadata["finished_at_utc"] = utc_now().isoformat()
    capture = CapturedResponse(
        status_line=status_line,
        header_block=header_block,
        all_header_blocks=header_block,
        headers=headers,
        body=body,
        verbose=(
            "Playwright Chromium profile: curl verbose output is not applicable.\n"
            "See network.json, browser_console.json, and request_failures.json.\n"
        ).encode("utf-8"),
        timings=timings,
        network=network,
        request=request_metadata,
    )
    summary = save_response_artifacts(directory, capture, environment, dns, egress)
    write_json(directory / "browser_console.json", console_entries)
    write_json(directory / "request_failures.json", request_failures)
    write_json(directory / "cdp_document_responses.json", cdp_documents)
    if summary["http_status"] == 403:
        _write_exact_403_to_log(directory, summary)
    elif print_body and (directory / "response_body.txt").is_file():
        print((directory / "response_body.txt").read_text(encoding="utf-8"))
    return directory, summary

def discover_summaries(roots: Iterable[Path]) -> list[tuple[Path, dict[str, Any]]]:
    discovered: list[tuple[Path, dict[str, Any]]] = []
    seen: set[Path] = set()
    for root in roots:
        for path in root.rglob("summary.json"):
            resolved = path.resolve()
            if resolved in seen:
                continue
            summary = read_json(path)
            if isinstance(summary, dict) and "client_profile" in summary:
                discovered.append((path.parent, summary))
                seen.add(resolved)
    return sorted(discovered, key=lambda item: (str(item[1].get("environment_label")), str(item[1].get("client_profile"))))


def markdown_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value or "").replace("|", "\\|").replace("\n", " ")


def code_fence(text: str) -> str:
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def write_comparison_index(base: Path) -> dict[str, Any]:
    records = discover_summaries([base])
    body_groups: dict[str, list[str]] = {}
    for _directory, summary in records:
        body_groups.setdefault(str(summary.get("body_sha256") or ""), []).append(
            f"{summary.get('environment_label')} / {summary.get('client_profile')}"
        )
    output = {
        "generated_at_utc": utc_now().isoformat(),
        "result_count": len(records),
        "results": [summary for _directory, summary in records],
        "body_sha256_groups": body_groups,
    }
    write_json(base / "comparison_summary.json", output)
    return output


def generate_comparative_report(roots: Iterable[Path], output_path: Path) -> str:
    records = discover_summaries(roots)
    lines = [
        "# AFDJ 403 diagnostic report",
        "",
        f"Generated: `{utc_now().isoformat()}`",
        "",
        "This report is evidence-oriented. Body phrase detection is indicative and does not reveal the exact AFDJ/Cloudflare rule.",
        "",
        "## Comparative results",
        "",
        "| environment | operating_system | client_profile | public_ip_masked | asn | provider | resolved_server_ip | HTTP_status | HTTP_version | TLS_version | Server | CF-RAY | CF-Mitigated | CF-Cache-Status | Content-Type | body_size | body_sha256 | response_classification |",
        "|---|---|---|---|---|---|---|---:|---|---|---|---|---|---|---|---:|---|---|",
    ]
    for _directory, summary in records:
        cf = summary.get("cloudflare_headers") or {}
        values = (
            summary.get("environment_label"), summary.get("operating_system"), summary.get("client_profile"),
            summary.get("public_ip_masked"), summary.get("asn"), summary.get("provider"),
            summary.get("resolved_server_ip"), summary.get("http_status"), summary.get("http_version"),
            summary.get("tls_version"), cf.get("Server"), cf.get("CF-RAY"), cf.get("CF-Mitigated"),
            cf.get("CF-Cache-Status"), summary.get("content_type"), summary.get("body_size"),
            summary.get("body_sha256"), summary.get("response_classification"),
        )
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")

    lines.extend(["", "## Body identity and Ray IDs", ""])
    body_groups: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for item in records:
        body_groups.setdefault(str(item[1].get("body_sha256") or ""), []).append(item)
    for body_hash, group in sorted(body_groups.items()):
        environments = ", ".join(
            f"{summary.get('environment_label')} / {summary.get('client_profile')}"
            for _directory, summary in group
        )
        ray_ids = sorted({
            str((summary.get("cloudflare_headers") or {}).get("CF-RAY") or "")
            for _directory, summary in group
            if (summary.get("cloudflare_headers") or {}).get("CF-RAY")
        })
        lines.append(f"- `{body_hash}`: {environments}; CF-RAY: {', '.join(ray_ids) if ray_ids else 'not present'}")

    local_statuses = [int(summary.get("http_status") or 0) for _directory, summary in records if not summary.get("is_github_actions")]
    github_statuses = [int(summary.get("http_status") or 0) for _directory, summary in records if summary.get("is_github_actions")]
    lines.extend(["", "## Conclusions", "", "### Demonstrated", ""])
    if local_statuses:
        lines.append(f"- Local HTTP statuses captured: `{local_statuses}`.")
    if github_statuses:
        lines.append(f"- GitHub-hosted runner HTTP statuses captured: `{github_statuses}`.")
    if records:
        lines.append("- Every row above is backed by raw headers, `response_body.bin`, `response_full.txt`, timings, and SHA-256 files in the diagnostic artifacts.")
    else:
        lines.append("- No diagnostic result folders were supplied.")
    classifications = sorted({str(summary.get("response_classification") or "") for _directory, summary in records})
    if classifications:
        lines.append(f"- Observed response classifications: `{classifications}`.")

    lines.extend(["", "### Probable", ""])
    if local_statuses and github_statuses and any(200 <= status < 300 for status in local_statuses) and all(status == 403 for status in github_statuses):
        lines.append("- The observed difference is associated with the execution environment. IP/ASN reputation or provider classification is plausible, but not demonstrated by the HTTP response alone.")
    else:
        lines.append("- Any association with IP/ASN, client fingerprint, geography, or provider remains a hypothesis unless the comparative rows isolate that variable.")

    lines.extend([
        "",
        "### Unknown without AFDJ/Cloudflare access",
        "",
        "- The exact WAF rule, bot score, reputation signal, owner configuration, and corresponding Cloudflare Security Event.",
        "- Whether a geographic, ASN, datacenter, or client rule is decisive when multiple variables differ simultaneously.",
        "",
        "## Exact unique HTTP 403 responses",
        "",
    ])
    unique_403 = {
        body_hash: group for body_hash, group in body_groups.items()
        if any(int(summary.get("http_status") or 0) == 403 for _directory, summary in group)
    }
    if not unique_403:
        lines.append("No HTTP 403 body was present in the supplied artifacts.")
    for body_hash, group in sorted(unique_403.items()):
        group_403 = [(directory, summary) for directory, summary in group if int(summary.get("http_status") or 0) == 403]
        representative_dir, representative = group_403[0]
        environments = ", ".join(
            f"{summary.get('environment_label')} / {summary.get('client_profile')}"
            for _directory, summary in group_403
        )
        body = (representative_dir / "response_body.bin").read_bytes()
        content_type = str(representative.get("content_type") or "")
        body_text, encoding = decode_body_losslessly(body, content_type)
        lines.extend([
            "",
            f"### Body SHA-256 `{body_hash}`",
            "",
            f"- Environments: {environments}",
            f"- Size: `{len(body)}` bytes",
            f"- Decoding: `{encoding or 'not losslessly decodable'}`",
            "",
        ])
        header_variants: dict[str, tuple[Path, dict[str, Any]]] = {}
        for directory, summary in group_403:
            header_bytes = (directory / "response_headers.txt").read_bytes()
            header_variants.setdefault(sha256_bytes(header_bytes), (directory, summary))
        for header_hash, (directory, summary) in header_variants.items():
            header_text = (directory / "response_headers.txt").read_bytes().decode("latin-1")
            fence = code_fence(header_text)
            lines.extend([
                f"#### Header variant `{header_hash}` — {summary.get('environment_label')} / {summary.get('client_profile')}",
                "",
                fence + "http",
                header_text.rstrip("\r\n"),
                fence,
                "",
            ])
        if body_text is not None:
            fence = code_fence(body_text)
            lines.extend([fence + "html", body_text, fence, ""])
        else:
            lines.append("The raw body is binary and remains available byte-for-byte as `response_body.bin`; it is not embedded as altered text.")

    lines.extend([
        "",
        "## Reproduction",
        "",
        "```bash",
        "python -m scripts.diagnose_afdj_access \\",
        "  --environment-label <LABEL> \\",
        "  --output-dir <DIRECTOR>",
        "```",
        "",
        "Return the entire output directory, including `_shared`, every profile subfolder, and `comparison_summary.json`.",
    ])
    report = "\n".join(lines).rstrip() + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    return report


def write_failure_artifact(base: Path, profile: str, client: str, environment_label: str, exc: Exception) -> tuple[Path, dict[str, Any]]:
    directory = unique_result_dir(base, profile, client + "-failure")
    message = f"{type(exc).__name__}: {exc}"
    (directory / "diagnostic_error.txt").write_text(message + "\n", encoding="utf-8")
    summary = {
        "artifact_version": 1,
        "environment_label": environment_label,
        "is_github_actions": os.environ.get("GITHUB_ACTIONS", "").casefold() == "true",
        "operating_system": platform.system(),
        "client_profile": profile,
        "client_label": client,
        "http_status": 0,
        "body_size": 0,
        "body_sha256": sha256_bytes(b""),
        "response_classification": "diagnostic-client-unavailable",
        "diagnostic_error": message,
        "cloudflare_headers": report_headers([]),
    }
    write_json(directory / "summary.json", summary)
    return directory, summary


def validate_result_directory(directory: Path) -> dict[str, Any]:
    summary = read_json(directory / "summary.json")
    if not isinstance(summary, dict):
        raise ValueError(f"Missing or invalid summary.json in {directory}")
    if summary.get("response_classification") == "diagnostic-client-unavailable":
        if not (directory / "diagnostic_error.txt").is_file():
            raise ValueError(f"Failure summary lacks diagnostic_error.txt in {directory}")
        return {"directory": str(directory), "ok": True, "response_saved": False, "classification": summary.get("response_classification")}
    required = (
        "request.json", "environment.json", "dns.json", "network.json",
        "response_status.txt", "response_headers.txt", "response_body.bin",
        "response_full.txt", "curl_verbose.txt", "timings.json", "summary.json", "sha256.json",
    )
    missing = [name for name in required if not (directory / name).is_file()]
    if missing:
        raise ValueError(f"Missing required artifacts in {directory}: {missing}")
    hashes = read_json(directory / "sha256.json")
    body = (directory / "response_body.bin").read_bytes()
    headers = (directory / "response_headers.txt").read_bytes()
    full = (directory / "response_full.txt").read_bytes()
    if full != headers + body:
        raise ValueError(f"response_full.txt is not headers + body in {directory}")
    if hashes["response_body"]["sha256"] != sha256_bytes(body):
        raise ValueError(f"Body SHA-256 mismatch in {directory}")
    if hashes["response_full"]["sha256"] != sha256_bytes(full):
        raise ValueError(f"Full-response SHA-256 mismatch in {directory}")
    if int(hashes["response_body"]["size_bytes"]) != len(body):
        raise ValueError(f"Body size mismatch in {directory}")
    if str(summary.get("body_sha256")) != sha256_bytes(body):
        raise ValueError(f"Summary body SHA-256 mismatch in {directory}")
    return {
        "directory": str(directory), "ok": True, "response_saved": True,
        "http_status": summary.get("http_status"), "body_size": len(body),
        "body_sha256": sha256_bytes(body), "response_full_sha256": sha256_bytes(full),
    }


def validate_result_tree(root: Path, expected_count: int | None = None) -> dict[str, Any]:
    directories = sorted({path.parent for path in root.rglob("summary.json") if path.parent.name != "_shared"})
    results = [validate_result_directory(directory) for directory in directories]
    output = {"root": str(root), "ok": bool(results), "result_count": len(results), "results": results}
    if expected_count is not None and len(results) != expected_count:
        raise ValueError(f"Expected {expected_count} diagnostic result folders under {root}, found {len(results)}")
    if not results:
        raise ValueError(f"No diagnostic summary.json files found under {root}")
    return output

def default_output_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    return root / "_diagnostics" / "afdj" / "local" / timestamp_slug()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", help="Override the profile URL. Without it, production uses the exact workflow URL and the other profiles use the non-www endpoint.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--environment-label", default="local")
    parser.add_argument("--client-label", default="")
    parser.add_argument("--print-body", action="store_true")
    parser.add_argument("--profile", choices=("all", "production-profile", "transparent-minimal", "playwright-chromium"), default="all")
    parser.add_argument("--pause-seconds", type=float, default=5.0)
    parser.add_argument("--report-from", type=Path, nargs="+")
    parser.add_argument("--report-output", type=Path)
    parser.add_argument("--validate-root", type=Path)
    parser.add_argument("--expected-result-count", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate_root:
        result = validate_result_tree(args.validate_root.resolve(), args.expected_result_count)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.report_from:
        output = args.report_output or Path("docs/AFDJ_403_DIAGNOSTIC_REPORT.md")
        generate_comparative_report(args.report_from, output)
        print(json.dumps({"report": str(output), "inputs": [str(path) for path in args.report_from]}, indent=2))
        return 0

    base = (args.output_dir or default_output_dir()).resolve()
    base.mkdir(parents=True, exist_ok=True)
    profiles = [args.profile] if args.profile != "all" else [
        "production-profile", "transparent-minimal", "playwright-chromium",
    ]
    results: list[dict[str, Any]] = []
    for index, profile in enumerate(profiles):
        client = args.client_label or ("curl" if profile != "playwright-chromium" else "chromium")
        try:
            if profile == "playwright-chromium":
                directory, summary = run_playwright_profile(
                    base, args.environment_label, client, args.url, args.print_body,
                )
            else:
                directory, summary = run_curl_profile(
                    base, profile, args.environment_label, client, args.url, args.print_body,
                )
        except Exception as exc:
            directory, summary = write_failure_artifact(base, profile, client, args.environment_label, exc)
            print(f"Diagnostic profile {profile} could not capture a response: {exc}", file=sys.stderr)
        results.append({"directory": str(directory), "summary": summary})
        if index < len(profiles) - 1 and args.pause_seconds > 0:
            time.sleep(args.pause_seconds)
    index = write_comparison_index(base)
    print(json.dumps({"output_dir": str(base), "profiles": results, "comparison": index}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())