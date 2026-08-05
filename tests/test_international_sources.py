from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from scripts.build_international_station_audit import build
from scripts.ingest_danube_sources import main, run_source
from scripts.sources import get_adapter
from scripts.sources.base import (
    AdapterResult, FetchedPayload, SourceAccessError, SourceStructureError,
    archive_payload, ensure_payload, load_fixture_payloads, transliterate,
)

FIXTURES = Path(__file__).parent / "fixtures" / "international"


class InternationalAdapterTests(unittest.TestCase):
    def parse(self, source: str):
        adapter = get_adapter(source)
        payloads = load_fixture_payloads(FIXTURES / source) if adapter.initial_requests() else {}
        return adapter, payloads, adapter.parse(payloads)

    def test_all_fixture_profiles_and_counts(self):
        expected = {
            "de": ("complete", 18, 18, 0),
            "at": ("partial", 9, 9, 1),
            "sk": ("complete", 13, 26, 26),
            "hu": ("complete", 25, 125, 0),
            "hr": ("complete", 3, 6, 0),
            "bg": ("partial", 20, 48, 30),
            "rs": ("complete", 13, 75, 32),
        }
        for source, values in expected.items():
            with self.subTest(source=source):
                _, _, result = self.parse(source)
                self.assertEqual(values, (result.status, len(result.stations), len(result.observations), len(result.forecasts)))

    def test_names_are_ascii_local_names_are_preserved_and_slugs_unique(self):
        for source in ("de", "at", "sk", "hu", "hr", "bg"):
            with self.subTest(source=source):
                _, _, result = self.parse(source)
                self.assertEqual(len(result.stations), len({s.station_slug for s in result.stations}))
                for station in result.stations:
                    station.station_name.encode("ascii")
                    self.assertTrue(station.station_name_local)
                    self.assertTrue(station.station_slug.startswith(station.country_code.lower() + "-"))
        _, _, sk = self.parse("sk")
        self.assertIn("Devín", {s.station_name_local for s in sk.stations})
        self.assertIn("Devin", {s.station_name for s in sk.stations})
        self.assertEqual("Silistra", transliterate("Силистра"))
        _, _, bg = self.parse("bg")
        self.assertIn(("Силистра", "Silistra"), {
            (station.station_name_local, station.station_name) for station in bg.stations
        })
        _, _, hr = self.parse("hr")
        self.assertIn(("Aljmaš", "Aljmas"), {
            (station.station_name_local, station.station_name) for station in hr.stations
        })

    def test_verified_coordinates_use_explicit_provenance_classes(self):
        expected = {
            "de": (17, "official_station_coordinate"),
            "at": (9, "official_station_coordinate"),
            "sk": (0, "manually_verified_station_coordinate"),
            "hu": (0, "manually_verified_station_coordinate"),
            "hr": (3, "official_station_coordinate"),
            "bg": (20, "official_station_coordinate"),
        }
        for source, (count, method) in expected.items():
            _, _, result = self.parse(source)
            with_coords = [row for row in result.stations if row.latitude is not None]
            self.assertEqual(count, len(with_coords), source)
            self.assertTrue(all(row.coordinate_method == method for row in with_coords), source)
            self.assertTrue(all(row.coordinate_confidence == "high" for row in with_coords), source)
            self.assertTrue(all(row.is_exact_station_location for row in with_coords), source)

    def test_primary_source_deduplication_rules(self):
        _, _, de = self.parse("de")
        self.assertEqual(18, len(de.stations))
        self.assertEqual(9, de.excluded_station_count)
        _, _, at = self.parse("at")
        self.assertEqual(1, at.excluded_station_count)
        _, _, hu = self.parse("hu")
        self.assertEqual(68, hu.excluded_station_count)

    def test_duplicate_station_is_critical(self):
        adapter, _, parsed = self.parse("de")
        duplicate = deepcopy(parsed.stations[0])
        result = AdapterResult("pegelonline_de", "DE", "complete", parsed.stations + [duplicate], [], [])
        validated = adapter.validate(result, datetime(2026, 8, 4, tzinfo=timezone.utc))
        self.assertIn("duplicate_station_id", {issue.code for issue in validated.issues})
        self.assertFalse(validated.publishable)

    def test_station_disappearance_is_fail_closed(self):
        adapter, _, parsed = self.parse("de")
        result = AdapterResult("pegelonline_de", "DE", "complete", parsed.stations[:2], [], [])
        validated = adapter.validate(result, datetime(2026, 8, 4, tzinfo=timezone.utc))
        self.assertIn("mass_station_loss", {issue.code for issue in validated.issues})
        self.assertEqual("partial", validated.status)

    def test_bg_ris_identifiers_and_streams_are_complete_but_forecasts_remain_candidate(self):
        _, _, result = self.parse("bg")
        self.assertFalse(result.publishable)
        self.assertTrue(all(station.source_station_id and station.isrs_location_code for station in result.stations))
        self.assertEqual({"manual", "automatic"}, {station.source_stream_type for station in result.stations})
        self.assertNotIn("missing_institutional_station_ids", {issue.code for issue in result.issues})
        self.assertIn("forecast_not_activated", {issue.code for issue in result.issues})

    def test_schema_change_is_detected(self):
        adapter, payloads, _ = self.parse("at")
        broken = dict(payloads)
        original = payloads["gauge-list"]
        broken["gauge-list"] = replace(original, body=b'{"gauges": []}')
        with self.assertRaises(SourceStructureError):
            adapter.parse(broken)

    def test_wrong_content_and_block_page_are_rejected(self):
        wrong = FetchedPayload("x", "https://example.invalid", 200, "text/html", b"<html>not json</html>", "2026-08-04T00:00:00+00:00")
        with self.assertRaises(SourceStructureError):
            ensure_payload(wrong, "json")
        blocked = replace(wrong, body=b"<!doctype html><html>Sorry, you have been blocked</html>")
        with self.assertRaises(SourceAccessError):
            ensure_payload(blocked, "html")

    def test_raw_archive_is_gzip_exact_and_has_metadata(self):
        payload = load_fixture_payloads(FIXTURES / "de")["stations"]
        with tempfile.TemporaryDirectory() as directory:
            metadata = archive_payload(payload, Path(directory), "pegelonline_de")
            with gzip.open(metadata["raw_path"], "rb") as handle:
                self.assertEqual(payload.body, handle.read())
            saved = json.loads(Path(metadata["metadata_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload.sha256, saved["content_sha256"])
            self.assertEqual(len(payload.body), saved["content_bytes"])
            self.assertEqual("1.0.0", saved["adapter_version"])

    def test_hr_stale_feed_is_partial_with_access_retained(self):
        adapter = get_adapter("hr")
        payloads = load_fixture_payloads(FIXTURES / "hr")
        payloads["current"] = replace(payloads["current"], captured_at_utc="2026-09-01T10:00:00+00:00")
        result = adapter.parse(payloads)
        self.assertEqual("partial", result.status)
        self.assertIn("stale_source", {issue.code for issue in result.issues})

    def test_runner_writes_isolated_outputs_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = run_source("de", root / "out", root / "archive", FIXTURES)
            self.assertTrue(summary["publishable"])
            self.assertTrue((root / "out" / "de" / "stations.json").is_file())
            self.assertTrue((root / "out" / "de" / "archive_manifest.json").is_file())
            exit_code = main(["--source", "rs", "--fixture-root", str(FIXTURES), "--output-dir", str(root / "rs"), "--archive-root", str(root / "archive")])
            self.assertEqual(0, exit_code)

    def test_comparative_station_audit_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "audit.csv"
            rows = build(Path("docs/DANUBE_STATION_INVENTORY.csv"), generated)
            self.assertEqual(101, len(rows))
            self.assertEqual(88, len([row for row in rows if row["included"] == "yes"]))
            self.assertEqual(13, len([row for row in rows if row["implementation_status"] == "suspended"]))
            self.assertEqual(101, len([row for row in rows if row["latitude"]]))
            self.assertEqual(
                Path("docs/INTERNATIONAL_STATIONS_AUDIT.csv").read_text(encoding="utf-8"),
                generated.read_text(encoding="utf-8"),
            )
            explicit = Path(directory) / "explicit-date.csv"
            explicit_rows = build(
                Path("docs/DANUBE_STATION_INVENTORY.csv"), explicit,
                verified_at="2026-08-05",
            )
            self.assertEqual({"2026-08-05"}, {row["last_verified_at"] for row in explicit_rows})

            sk_rows = [row for row in rows if row["country_code"] == "SK"]
            self.assertEqual({"complete"}, {row["implementation_status"] for row in sk_rows})
            self.assertEqual({"partial"}, {row["latest_live_status"] for row in sk_rows})
            self.assertTrue(all("source-provided provisional quality" in row["observation_quality_summary"] for row in sk_rows))

            rs_rows = [row for row in rows if row["country_code"] == "RS"]
            self.assertEqual(13, len(rs_rows))
            self.assertTrue(all(row["included"] == "no" for row in rs_rows))
            self.assertTrue(all(row["review_required"] == "yes" for row in rs_rows))
            self.assertTrue(all("TLS certificate-chain validation failed" in row["review_reason"] for row in rs_rows))
            self.assertIn(("Bačka Palanka", "Backa Palanka"), {
                (row["station_name_local"], row["station_name"]) for row in rs_rows
            })
            self.assertIn(("Veliko Gradište", "Veliko Gradiste"), {
                (row["station_name_local"], row["station_name"]) for row in rs_rows
            })

if __name__ == "__main__":
    unittest.main()
