from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.diagnose_afdj_access import (
    CapturedResponse,
    decode_body_losslessly,
    generate_comparative_report,
    report_headers,
    save_response_artifacts,
    sha256_bytes,
)


class AfdjDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.environment = {
            "environment_label": "unit-local",
            "is_github_actions": False,
            "operating_system": "TestOS",
        }
        self.dns = {"hostname": "afdj.ro", "addresses": [{"family": "IPv4", "address": "192.0.2.1"}]}
        self.egress = {
            "normalized": [{
                "source": "test", "ip": "198.51.100.42", "ip_version": "4",
                "asn": "AS64500", "provider": "Example", "country": "RO", "region": "B",
            }]
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def capture(
        self,
        status: int,
        body: bytes,
        headers: list[tuple[str, str]],
        *,
        profile: str = "transparent-minimal",
    ) -> CapturedResponse:
        reason = "OK" if status == 200 else "Forbidden"
        status_line = f"HTTP/2 {status} {reason}".encode("ascii")
        header_block = b"\r\n".join(
            [status_line] + [f"{name}: {value}".encode("latin-1") for name, value in headers]
        ) + b"\r\n\r\n"
        return CapturedResponse(
            status_line=status_line,
            header_block=header_block,
            all_header_blocks=header_block,
            headers=headers,
            body=body,
            verbose=b"> GET / HTTP/2\r\n> Accept: */*\r\n< HTTP/2 response\r\n",
            timings={"http_code": status, "http_version": "2", "url_effective": "https://afdj.ro/test", "curl_exit_code": 0},
            network={"remote_ip": "192.0.2.1", "remote_port": 443, "http_version": "2", "tls_version": "TLSv1.3", "tls_cipher": "TEST"},
            request={"url": "https://afdj.ro/test", "client": "test-client", "profile": profile},
        )

    def save(self, capture: CapturedResponse, name: str = "result") -> tuple[Path, dict]:
        directory = self.root / name
        summary = save_response_artifacts(directory, capture, self.environment, self.dns, self.egress)
        return directory, summary

    def test_saves_complete_200_xml_response(self) -> None:
        body = b'<?xml version="1.0"?><response><item/><item/></response>'
        capture = self.capture(200, body, [("Content-Type", "application/xml; charset=UTF-8")])
        directory, summary = self.save(capture)
        self.assertEqual((directory / "response_body.bin").read_bytes(), body)
        self.assertEqual((directory / "response_body.txt").read_text(encoding="utf-8"), body.decode())
        self.assertEqual(summary["http_status"], 200)
        self.assertEqual(summary["xml"]["station_count"], 2)
        self.assertTrue(summary["xml"]["well_formed"])

    def test_saves_entire_403_html_and_duplicate_headers(self) -> None:
        body = b"<html><title>Attention Required</title><p>Cloudflare Ray ID</p></html>"
        headers = [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Set-Cookie", "first=secret-a; Secure"),
            ("Set-Cookie", "second=secret-b; Secure"),
            ("CF-RAY", "abc-OTP"),
            ("Server", "cloudflare"),
        ]
        capture = self.capture(403, body, headers)
        directory, summary = self.save(capture)
        raw_headers = (directory / "response_headers.txt").read_bytes()
        self.assertEqual(raw_headers.count(b"Set-Cookie:"), 2)
        self.assertEqual((directory / "response_body.bin").read_bytes(), body)
        self.assertIn("Attention Required", (directory / "response_body.txt").read_text(encoding="utf-8"))
        self.assertEqual(summary["body_size"], len(body))
        self.assertIn(summary["response_classification"], {"cloudflare-403-undetermined", "cloudflare-challenge-page"})

    def test_binary_body_is_preserved_without_lossy_text_file(self) -> None:
        body = bytes(range(256))
        capture = self.capture(403, body, [("Content-Type", "application/octet-stream")])
        directory, _summary = self.save(capture)
        self.assertEqual((directory / "response_body.bin").read_bytes(), body)
        self.assertFalse((directory / "response_body.txt").exists())

    def test_declared_charset_is_decoded_losslessly(self) -> None:
        text = "Příliš žluťoučký kůň"
        body = text.encode("iso-8859-2")
        decoded, charset = decode_body_losslessly(body, "text/plain; charset=iso-8859-2")
        self.assertEqual(decoded, text)
        self.assertEqual(charset, "iso-8859-2")
        directory, summary = self.save(self.capture(403, body, [("Content-Type", "text/plain; charset=iso-8859-2")]))
        self.assertEqual((directory / "response_body.txt").read_text(encoding="utf-8"), text)
        self.assertEqual(summary["decoded_charset"], "iso-8859-2")

    def test_sha256_values_cover_body_and_full_response(self) -> None:
        body = b"forbidden-body"
        capture = self.capture(403, body, [("Content-Type", "text/plain")])
        directory, summary = self.save(capture)
        hashes = json.loads((directory / "sha256.json").read_text(encoding="utf-8"))
        full = (directory / "response_full.txt").read_bytes()
        self.assertEqual(hashes["response_body"]["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(hashes["response_full"]["sha256"], hashlib.sha256(full).hexdigest())
        self.assertEqual(summary["body_sha256"], sha256_bytes(body))

    def test_cookie_values_are_redacted_only_in_report_metadata(self) -> None:
        cookie = "__cf_bm=reusable-looking-value; Path=/; Secure"
        capture = self.capture(403, b"blocked", [("Content-Type", "text/plain"), ("Set-Cookie", cookie)])
        directory, summary = self.save(capture)
        self.assertIn(cookie.encode("latin-1"), (directory / "response_headers.txt").read_bytes())
        self.assertEqual(summary["cloudflare_headers"]["Set-Cookie"], "__cf_bm=<redacted>")
        self.assertEqual(report_headers(capture.headers)["Set-Cookie"], "__cf_bm=<redacted>")

    def test_response_full_is_status_headers_blank_line_and_raw_body(self) -> None:
        body = b"<html>exact</html>"
        capture = self.capture(403, body, [("X-One", "1"), ("X-One", "2"), ("Content-Type", "text/html")])
        directory, _summary = self.save(capture)
        expected = capture.header_block + body
        self.assertEqual((directory / "response_full.txt").read_bytes(), expected)

    def test_raw_body_survives_when_text_copy_exists(self) -> None:
        body = "Cloudflare — răspuns integral".encode("utf-8")
        directory, _summary = self.save(self.capture(403, body, [("Content-Type", "text/html; charset=utf-8")]))
        self.assertEqual((directory / "response_body.bin").read_bytes(), body)
        self.assertEqual((directory / "response_body.txt").read_text(encoding="utf-8").encode("utf-8"), body)

    def test_comparative_report_deduplicates_identical_403_bodies(self) -> None:
        body = b"<html>Sorry, you have been blocked - Cloudflare</html>"
        first_capture = self.capture(403, body, [("Content-Type", "text/html; charset=utf-8"), ("Server", "cloudflare"), ("CF-RAY", "one-OTP")])
        first_dir, _ = self.save(first_capture, "first")
        second_environment = dict(self.environment, environment_label="github-ubuntu", is_github_actions=True, operating_system="Linux")
        second_capture = self.capture(403, body, [("Content-Type", "text/html; charset=utf-8"), ("Server", "cloudflare"), ("CF-RAY", "two-OTP")], profile="production-profile")
        second_dir = self.root / "second"
        save_response_artifacts(second_dir, second_capture, second_environment, self.dns, self.egress)
        report_path = self.root / "report.md"
        report = generate_comparative_report([first_dir, second_dir], report_path)
        self.assertEqual(report.count("### Body SHA-256"), 1)
        self.assertIn("unit-local / transparent-minimal", report)
        self.assertIn("github-ubuntu / production-profile", report)
        self.assertIn("one-OTP", report)
        self.assertIn("two-OTP", report)
        self.assertEqual(report.count(body.decode()), 1)
        self.assertIn("### Demonstrated", report)
        self.assertIn("### Probable", report)
        self.assertIn("### Unknown without AFDJ/Cloudflare access", report)


if __name__ == "__main__":
    unittest.main()