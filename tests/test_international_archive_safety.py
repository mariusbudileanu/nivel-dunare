from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.ingest_danube_sources import run_source
from scripts.sources.base import FetchedPayload, archive_payload


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
