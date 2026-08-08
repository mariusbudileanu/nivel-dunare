from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from scripts.ingest_danube_sources import run_source
from scripts.sources.base import (
    FetchedPayload, SourceAccessError, SourceRequest, archive_payload, ensure_payload, fetch_request,
)


class InternationalArchiveSafetyTests(unittest.TestCase):
    def test_partner_key_is_redacted_in_persistent_metadata(self):
        payload = FetchedPayload(
            "status", "https://example.invalid/status?VIADONAU_PARTNER_KEY=private-value&view=full",
            200, "application/json", b"{}", "2026-08-04T00:00:00+00:00",
        )
        with tempfile.TemporaryDirectory() as directory:
            saved = archive_payload(payload, Path(directory), "viadonau_at")
            metadata = json.loads(Path(saved["metadata_path"]).read_text(encoding="utf-8"))
            self.assertNotIn("private-value", metadata["url"])
            self.assertIn("VIADONAU_PARTNER_KEY=%5BREDACTED%5D", metadata["url"])
            self.assertIn("view=full", metadata["url"])

    def test_auth_failure_does_not_leak_the_doris_key_anywhere(self):
        # If DORIS_PARTNER_KEY is wrong or gets revoked, the resulting HTTP 401
        # must not surface the key in the exception message, and the archived
        # metadata for the failed request must still be redacted.
        request = SourceRequest(
            "gauge-list", "https://opendata2.doris-info.at/doris/api/1.0/gauge/list?VIADONAU_PARTNER_KEY=super-secret-value",
            "json", "application/json",
        )
        http_error = urllib.error.HTTPError(
            url=request.url, code=401, msg="Unauthorized",
            hdrs={"Content-Type": "application/json"}, fp=io.BytesIO(b'{"error":"invalid partner key"}'),
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            payload = fetch_request(request)
        self.assertIn("super-secret-value", payload.url)  # confirms the test actually exercises the leak path
        with self.assertRaises(SourceAccessError) as ctx:
            ensure_payload(payload, "json")
        self.assertNotIn("super-secret-value", str(ctx.exception))
        with tempfile.TemporaryDirectory() as directory:
            saved = archive_payload(payload, Path(directory), "viadonau_at")
            self.assertNotIn("super-secret-value", json.dumps(saved))
            self.assertNotIn(b"super-secret-value", Path(saved["raw_path"]).read_bytes())

    def test_network_failure_does_not_leak_the_doris_key_anywhere(self):
        request = SourceRequest(
            "gauge-status", "https://opendata2.doris-info.at/doris/api/1.0/gauge/getStatus?VIADONAU_PARTNER_KEY=super-secret-value",
            "json", "application/json",
        )
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("[Errno 11001] getaddrinfo failed")):
            with self.assertRaises(SourceAccessError) as ctx:
                fetch_request(request)
        self.assertNotIn("super-secret-value", str(ctx.exception))

    def test_invalid_http_response_is_archived_before_fail_closed_validation(self):
        payload = FetchedPayload(
            "stations", "https://www.pegelonline.wsv.de/example", 403, "text/html",
            b"<!doctype html><html>Forbidden</html>", "2026-08-04T00:00:00+00:00",
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.ingest_danube_sources.fetch_request", return_value=payload,
        ):
            root = Path(directory)
            summary = run_source("de", root / "out", root / "archive")
            self.assertEqual("failed", summary["status"])
            archives = list((root / "archive").rglob("*.raw.gz"))
            metadata = list((root / "archive").rglob("*.metadata.json"))
            self.assertEqual(1, len(archives))
            self.assertEqual(1, len(metadata))


if __name__ == "__main__":
    unittest.main()
