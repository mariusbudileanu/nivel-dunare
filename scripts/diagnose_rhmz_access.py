#!/usr/bin/env python3
"""Low-volume, standard-TLS diagnostics for the official RHMZ endpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_AGENT = "NivelDunareMonitor/1.0 (+https://github.com/mariusbudileanu/nivel-dunare)"
ENDPOINT_PATHS = (
    "/eng/osmotreni/stanje_voda.php",
    "/eng/osmotreni/nrt_index.php",
    "/eng/osmotreni/nrt_tabela_grafik.php?hm_id=42010&period=7",
    "/eng/prognoza/prognoza_voda.php",
    "/eng/hidrologija/izvestajne/prognoza.php?hm_id=42010",
    "/eng/hidrologija/izvestajne/bezprognoza.php?hm_id=42040",
    "/eng/hidrologija/izvestajne/opseg.php?hm_id=42055",
)
HOSTS = ("www.hidmet.gov.rs", "hidmet.gov.rs")


class RedirectRecorder(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.chain: list[dict[str, Any]] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        self.chain.append({"status": code, "from": req.full_url, "to": newurl})
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_name(url: str) -> str:
    return (
        url.removeprefix("https://").replace("?", "-").replace("&", "-")
        .replace("/", "-").replace("=", "-").strip("-")
    )


def body_facts(body: bytes) -> dict[str, Any]:
    prefix = body[:4096].decode("utf-8", "replace")
    return {
        "payload_bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "document_prefix": prefix[:500],
        "has_html": "<html" in prefix.casefold() or "<!doctype html" in prefix.casefold(),
        "has_expected_table": "<table" in prefix.casefold() or b"<table" in body[:65536].lower(),
    }


def save_response(root: Path, client: str, url: str, status: int | None,
                  headers: dict[str, str], body: bytes, details: dict[str, Any]) -> dict[str, Any]:
    folder = root / client / safe_name(url)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "response_body.bin").write_bytes(body)
    (folder / "response_headers.txt").write_text(
        "".join(f"{key}: {value}\n" for key, value in headers.items()), encoding="utf-8",
    )
    result = {"runner": platform.platform(), "client": client, "url": url,
              "http_status": status, **body_facts(body), **details}
    result["content_type"] = headers.get("Content-Type") or headers.get("content-type")
    write_json(folder / "result.json", result)
    return result


def urllib_probe(root: Path, url: str) -> dict[str, Any]:
    redirects = RedirectRecorder()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()), redirects,
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html", "Accept-Encoding": "identity"},
    )
    try:
        with opener.open(request, timeout=30) as response:
            return save_response(
                root, "python-urllib", url, response.status, dict(response.headers.items()),
                response.read(), {"redirect_chain": redirects.chain, "final_url": response.geturl(),
                                  "tls_verify_result": "success"},
            )
    except urllib.error.HTTPError as exc:
        return save_response(
            root, "python-urllib", url, exc.code, dict(exc.headers.items()), exc.read(),
            {"redirect_chain": redirects.chain, "final_url": exc.geturl(),
             "tls_verify_result": "success", "error": str(exc)},
        )
    except Exception as exc:  # diagnostic must retain the exact failure
        result = {"runner": platform.platform(), "client": "python-urllib", "url": url,
                  "http_status": None, "redirect_chain": redirects.chain,
                  "tls_verify_result": "failed", "error_type": type(exc).__name__, "error": str(exc)}
        write_json(root / "python-urllib" / safe_name(url) / "result.json", result)
        return result


def requests_probe(root: Path, url: str) -> dict[str, Any]:
    try:
        import certifi
        import requests
    except ImportError as exc:
        return {"runner": platform.platform(), "client": "python-requests-certifi", "url": url,
                "http_status": None, "tls_verify_result": "not_available", "error": str(exc)}
    try:
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=30,
            allow_redirects=True, verify=certifi.where(),
        )
        return save_response(
            root, "python-requests-certifi", url, response.status_code, dict(response.headers),
            response.content, {"redirect_chain": [
                {"status": item.status_code, "from": item.url, "to": item.headers.get("Location")}
                for item in response.history
            ], "final_url": response.url, "tls_verify_result": "success",
                "requests_version": requests.__version__, "certifi_version": certifi.__version__},
        )
    except Exception as exc:
        result = {"runner": platform.platform(), "client": "python-requests-certifi", "url": url,
                  "http_status": None, "tls_verify_result": "failed",
                  "error_type": type(exc).__name__, "error": str(exc)}
        write_json(root / "python-requests-certifi" / safe_name(url) / "result.json", result)
        return result


def curl_probe(root: Path, url: str) -> dict[str, Any]:
    executable = shutil.which("curl.exe") or shutil.which("curl")
    if not executable:
        return {"runner": platform.platform(), "client": "curl", "url": url,
                "http_status": None, "tls_verify_result": "not_available", "error": "curl not found"}
    folder = root / "curl" / safe_name(url)
    folder.mkdir(parents=True, exist_ok=True)
    body_path, header_path, verbose_path = folder / "response_body.bin", folder / "response_headers.txt", folder / "verbose.txt"
    command = [
        executable, "--location", "--silent", "--show-error", "--verbose",
        "--user-agent", USER_AGENT, "--header", "Accept: text/html", "--max-time", "30",
        "--dump-header", str(header_path), "--output", str(body_path),
        "--write-out", "%{json}", url,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=40, check=False)
    verbose_path.write_text(completed.stderr, encoding="utf-8")
    body = body_path.read_bytes() if body_path.is_file() else b""
    headers_text = header_path.read_text(encoding="utf-8", errors="replace") if header_path.is_file() else ""
    headers: dict[str, str] = {}
    for line in headers_text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
    try:
        metrics = json.loads(completed.stdout)
    except json.JSONDecodeError:
        metrics = {"raw_write_out": completed.stdout}
    status = metrics.get("http_code") or metrics.get("response_code")
    result = save_response(
        root, "curl", url, int(status) if status else None, headers, body,
        {"redirect_chain": metrics.get("url_effective"), "final_url": metrics.get("url_effective"),
         "resolved_server_ip": metrics.get("remote_ip"), "http_version": metrics.get("http_version"),
         "tls_verify_result": "success" if completed.returncode == 0 else "failed",
         "curl_exit_code": completed.returncode, "error": completed.stderr if completed.returncode else None},
    )
    write_json(folder / "curl_metrics.json", metrics)
    return result


def tls_probe(host: str, version: ssl.TLSVersion | None) -> dict[str, Any]:
    label = "default" if version is None else version.name
    context = ssl.create_default_context()
    if version is not None:
        context.minimum_version = version
        context.maximum_version = version
    try:
        with socket.create_connection((host, 443), timeout=20) as raw:
            with context.wrap_socket(raw, server_hostname=host) as secure:
                cert = secure.getpeercert()
                return {
                    "host": host, "profile": label, "tls_verify_result": "success",
                    "tls_version": secure.version(), "cipher": secure.cipher(),
                    "peer_ip": secure.getpeername()[0], "certificate_subject": cert.get("subject"),
                    "certificate_issuer": cert.get("issuer"), "certificate_san": cert.get("subjectAltName"),
                    "not_before": cert.get("notBefore"), "not_after": cert.get("notAfter"),
                }
    except Exception as exc:
        return {"host": host, "profile": label, "tls_verify_result": "failed",
                "error_type": type(exc).__name__, "error": str(exc)}


def environment() -> dict[str, Any]:
    return {
        "platform": platform.platform(), "system": platform.system(), "release": platform.release(),
        "architecture": platform.machine(), "python": sys.version, "openssl": ssl.OPENSSL_VERSION,
        "runner_name": os.environ.get("RUNNER_NAME"), "runner_os": os.environ.get("RUNNER_OS"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--environment-label", required=True)
    args = parser.parse_args(argv)
    root = args.output_dir
    root.mkdir(parents=True, exist_ok=True)
    env = {"environment_label": args.environment_label, "captured_at_utc": datetime.now(timezone.utc).isoformat(), **environment()}
    write_json(root / "environment.json", env)
    dns = {host: sorted({row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}) for host in HOSTS}
    write_json(root / "dns.json", dns)
    versions = [None, ssl.TLSVersion.TLSv1_2]
    if getattr(ssl, "HAS_TLSv1_3", False):
        versions.append(ssl.TLSVersion.TLSv1_3)
    tls = [tls_probe(host, version) for host in HOSTS for version in versions]
    write_json(root / "tls.json", tls)
    urls = [f"https://{host}{path}" for host in HOSTS for path in ENDPOINT_PATHS]
    results = [urllib_probe(root, url) for url in urls]
    # Repeat only the two host variants of the daily index across the other
    # clients; this demonstrates client/trust-store differences without
    # multiplying requests to every data page.
    transport_urls = [f"https://{host}{ENDPOINT_PATHS[0]}" for host in HOSTS]
    results.extend(requests_probe(root, url) for url in transport_urls)
    results.extend(curl_probe(root, url) for url in transport_urls)
    summary = {"environment": env, "dns": dns, "tls": tls, "requests": results,
               "successful_standard_https": any(row.get("http_status") == 200 and row.get("tls_verify_result") == "success" for row in results)}
    write_json(root / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all((root / name).is_file() for name in ("environment.json", "dns.json", "tls.json", "summary.json")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
