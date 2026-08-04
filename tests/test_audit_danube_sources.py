from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from scripts.audit_danube_sources import (
    AuditResponse,
    classify_body,
    decode_text,
    endpoint_inventory,
    ensure_safe_output,
    extract_station_sample,
    fetch_url,
    generate_report,
    header_values,
    mask_ip,
    redact_headers,
    save_audit,
    sha256_bytes,
)


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        routes = {
            "/json": (200, "application/json", b'{"station":"Test","level":123}'),
            "/xml": (200, "application/xml", b'<root><station id="1"/></root>'),
            "/csv": (200, "text/csv", b"station,level\nTest,123\n"),
            "/html": (200, "text/html; charset=utf-8", b"<!doctype html><html><p>static</p></html>"),
            "/dynamic": (200, "text/html", b"<!doctype html><html><script>fetch('/api')</script></html>"),
            "/binary": (200, "application/octet-stream", b"\x00\xff\x01\x80"),
            "/wrong-type": (200, "text/plain", b'{"ok":true}'),
            "/charset": (200, "text/plain; charset=iso-8859-2", "Dunaj ž".encode("iso-8859-2")),
            "/403": (403, "text/html", b"<html>Access denied</html>"),
            "/404": (404, "text/plain", b"not found"),
            "/429": (429, "text/plain", b"slow down"),
            "/500": (500, "text/plain", b"server error"),
        }
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/json")
            self.end_headers()
            return
        if self.path == "/duplicate":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("X-Test", "one")
            self.send_header("X-Test", "two")
            self.end_headers()
            self.wfile.write(b"duplicate")
            return
        if self.path == "/timeout":
            time.sleep(0.2)
            try:
                self.send_response(200)
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        status, content_type, body = routes.get(self.path, routes["/404"])
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if status == 429:
            self.send_header("Retry-After", "60")
        self.end_headers()
        self.wfile.write(body)


class DanubeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def fetch(self, path: str, timeout: float = 2.0):
        return fetch_url(self.base + path, timeout=timeout)

    def test_json_response(self) -> None:
        response = self.fetch("/json")
        self.assertEqual(classify_body(response.status, response.headers, response.body), "json")

    def test_xml_response(self) -> None:
        response = self.fetch("/xml")
        self.assertEqual(classify_body(response.status, response.headers, response.body), "xml")

    def test_csv_response(self) -> None:
        response = self.fetch("/csv")
        self.assertEqual(classify_body(response.status, response.headers, response.body), "csv")

    def test_static_html_response(self) -> None:
        response = self.fetch("/html")
        self.assertEqual(classify_body(response.status, response.headers, response.body), "html-static")

    def test_dynamic_html_response(self) -> None:
        response = self.fetch("/dynamic")
        self.assertEqual(classify_body(response.status, response.headers, response.body), "html-shell")

    def test_redirect_is_recorded(self) -> None:
        response = self.fetch("/redirect")
        self.assertEqual(response.status, 200)
        self.assertEqual(len(response.redirect_chain), 1)
        self.assertTrue(response.effective_url.endswith("/json"))

    def test_403_is_saved_without_retry_or_loss(self) -> None:
        response = self.fetch("/403")
        self.assertEqual(response.status, 403)
        self.assertEqual(response.body, b"<html>Access denied</html>")
        self.assertEqual(classify_body(response.status, response.headers, response.body), "block-page")

    def test_404_is_recorded(self) -> None:
        self.assertEqual(self.fetch("/404").status, 404)

    def test_429_and_retry_after_are_recorded(self) -> None:
        response = self.fetch("/429")
        self.assertEqual(response.status, 429)
        self.assertEqual(header_values(response.headers, "Retry-After"), ["60"])

    def test_5xx_is_recorded(self) -> None:
        self.assertEqual(self.fetch("/500").status, 500)

    def test_timeout_is_nonfatal_audit_result(self) -> None:
        response = self.fetch("/timeout", timeout=0.05)
        self.assertEqual(response.status, 0)
        self.assertIn("timed out", (response.error or "").lower())

    def test_wrong_content_type_uses_body_sniffing(self) -> None:
        response = self.fetch("/wrong-type")
        self.assertEqual(classify_body(response.status, response.headers, response.body), "json")

    def test_declared_charset_roundtrip(self) -> None:
        response = self.fetch("/charset")
        text, encoding = decode_text(response.body, "text/plain; charset=iso-8859-2")
        self.assertEqual(text, "Dunaj ž")
        self.assertEqual(encoding, "iso-8859-2")

    def test_duplicate_headers_are_preserved(self) -> None:
        response = self.fetch("/duplicate")
        self.assertEqual(header_values(response.headers, "X-Test"), ["one", "two"])

    def test_binary_body_is_not_decoded_lossily(self) -> None:
        response = self.fetch("/binary")
        text, encoding = decode_text(response.body, "application/octet-stream")
        self.assertIsNone(text)
        self.assertIsNone(encoding)

    def test_sha256(self) -> None:
        self.assertEqual(sha256_bytes(b"abc"), hashlib.sha256(b"abc").hexdigest())

    def test_cookie_redaction_preserves_duplicate_names(self) -> None:
        headers = [("Set-Cookie", "sid=secret; HttpOnly"), ("Set-Cookie", "prefs=value; Secure")]
        self.assertEqual(redact_headers(headers), [("Set-Cookie", "sid=<redacted>; HttpOnly"), ("Set-Cookie", "prefs=<redacted>; Secure")])

    def test_ip_masking(self) -> None:
        self.assertEqual(mask_ip("198.51.100.42"), "198.51.100.xxx")
        self.assertTrue(mask_ip("2001:db8::1").endswith("xxxx:xxxx:xxxx:xxxx:xxxx"))

    def test_endpoint_inventory_is_official_but_not_overclaimed(self) -> None:
        rows = endpoint_inventory("hu")
        self.assertTrue(rows[0]["official"])
        self.assertFalse(rows[0]["documented"])

    def test_bulgaria_endpoint_inventory_separates_current_forecast_and_archive(self) -> None:
        rows = endpoint_inventory("bg")
        by_id = {row["endpoint_id"]: row for row in rows}
        self.assertEqual(
            set(by_id),
            {"bg-current-hydrology", "bg-forecast", "bg-open-data", "bg-legacy-exploration"},
        )
        self.assertEqual(by_id["bg-current-hydrology"]["endpoint_url"], "https://www.appd-bg.org/hidrology-en")
        self.assertEqual(by_id["bg-forecast"]["endpoint_url"], "https://www.appd-bg.org/forecasts-en")

    def test_static_inventories_are_referentially_consistent(self) -> None:
        docs = Path("docs")
        with (docs / "DANUBE_SOURCE_ENDPOINT_INVENTORY.csv").open(encoding="utf-8", newline="") as handle:
            endpoints = list(csv.DictReader(handle))
        with (docs / "DANUBE_STATION_INVENTORY.csv").open(encoding="utf-8", newline="") as handle:
            stations = list(csv.DictReader(handle))
        with (docs / "DANUBE_SOURCE_FIELD_MAPPING.csv").open(encoding="utf-8", newline="") as handle:
            mappings = list(csv.DictReader(handle))

        endpoint_ids = [row["endpoint_id"] for row in endpoints]
        self.assertEqual(len(endpoint_ids), len(set(endpoint_ids)))
        endpoint_urls = [row["endpoint_url"] for row in endpoints]
        self.assertEqual(len(endpoint_urls), len(set(endpoint_urls)))
        providers = {row["provider_id"] for row in endpoints}
        self.assertTrue(all(row["provider_id"] in providers for row in stations))
        self.assertTrue(all(row["endpoint_id"] in set(endpoint_ids) for row in mappings))

        station_keys = [
            (row["provider_id"], row["source_station_id"])
            for row in stations if row["source_station_id"]
        ]
        self.assertEqual(len(station_keys), len(set(station_keys)))
        self.assertTrue(all(row["human_review_required"] in {"yes", "no"} for row in stations))

        for row in mappings:
            self.assertNotEqual(row["conversion"].strip().lower(), "missing to zero")
            if row["required"] == "yes":
                self.assertNotEqual(row["source_field"], "unavailable")
                self.assertTrue(row["source_field"] or row["source_path"] or row["notes"])

    def test_bulgaria_station_classes_are_complete(self) -> None:
        with Path("docs/DANUBE_STATION_INVENTORY.csv").open(encoding="utf-8", newline="") as handle:
            rows = [row for row in csv.DictReader(handle) if row["provider_id"] == "appd_bg"]
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["station_type"]] = counts.get(row["station_type"], 0) + 1
        self.assertEqual(counts, {
            "hydrometeorological_main": 8,
            "automated": 12,
            "historical_document_index": 6,
        })
        self.assertTrue(all(not row["source_station_id"] for row in rows))

    def test_save_and_report_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            response = AuditResponse(
                requested_url="https://example.test/data", effective_url="https://example.test/data",
                status=200, reason="OK", headers=[("Content-Type", "application/json"), ("Set-Cookie", "sid=raw")],
                body=b'[{"uuid":"x","shortname":"Test"}]', elapsed_seconds=0.1, redirect_chain=[],
                http_version="1.1", accessed_at_utc="2026-08-04T00:00:00+00:00",
            )
            summary = save_audit("de", root / "de", response, "test-agent")
            self.assertEqual((root / "de" / "response_body.bin").read_bytes(), response.body)
            self.assertEqual(json.loads((root / "de" / "raw_sha256.json").read_text())["response_body.bin"], summary["body_sha256"])
            report = generate_report([root], root / "report.md")
            self.assertIn("pegelonline_de", report)
            self.assertNotIn("sid=raw", report)

    def test_serbian_danube_station_extraction(self) -> None:
        body = b'<table><tr><td>DUNAV</td><td><a href="prognoza.php?hm_id=42010"><span class="bold">BEZDAN</span></a></td></tr></table>'
        rows = extract_station_sample("rs", "html-static", body, "text/html; charset=utf-8")
        self.assertEqual(rows, [{"source_station_id": "42010", "station_name_original": "BEZDAN"}])
    def test_output_cannot_target_production_data(self) -> None:
        repository = Path.cwd()
        for relative in ("data/canonical/audit", "data/public/audit", "public/data/audit", "public/audit"):
            with self.subTest(relative=relative):
                with self.assertRaises(ValueError):
                    ensure_safe_output(repository / relative, repository)
        with tempfile.TemporaryDirectory() as temporary:
            ensure_safe_output(Path(temporary), repository)


if __name__ == "__main__":
    unittest.main()