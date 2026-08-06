from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import asdict
from datetime import date
from pathlib import Path

from scripts.sources.base import load_fixture_payloads, payload_text
from scripts.sources.hidmet_rs import HidmetAdapter
from scripts.update_international_data import dedupe


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "international" / "rs"


class RhmzSerbiaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text(encoding="utf-8"))
        cls.payloads = load_fixture_payloads(FIXTURE_ROOT)
        cls.adapter = HidmetAdapter()
        cls.result = cls.adapter.parse(cls.payloads)

    def test_real_fixture_provenance_and_hashes(self) -> None:
        provenance = json.loads((FIXTURE_ROOT / "provenance.json").read_text(encoding="utf-8"))
        self.assertTrue(provenance["generated_from_raw_archives"])
        self.assertEqual(28, len(provenance["payloads"]))
        for row in provenance["payloads"]:
            body = (FIXTURE_ROOT / row["file"]).read_bytes()
            self.assertEqual(row["bytes"], len(body))
            self.assertEqual(row["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(200, row["http_status"])
            self.assertTrue(row["url"].startswith("https://"))

    def test_daily_and_nrt_indexes_discover_only_danube(self) -> None:
        daily = self.adapter._links(payload_text(self.payloads["daily-index"]))
        nrt = self.adapter._nrt_links(payload_text(self.payloads["nrt-index"]))
        self.assertEqual(13, len(daily))
        self.assertEqual(12, len(nrt))
        self.assertEqual(set(daily) - set(nrt), {"42040"})
        self.assertEqual("SLANKAMEN", daily["42040"][1])

    def test_canonical_station_and_stream_counts(self) -> None:
        self.assertEqual(13, len(self.result.stations))
        self.assertEqual(12, sum(row.source_stream_type == "nrt" for row in self.result.stations))
        slankamen = next(row for row in self.result.stations if row.source_station_id == "42040")
        self.assertEqual(("daily", "42040:daily"), (slankamen.source_stream_type, slankamen.source_stream_id))
        self.assertEqual(13, len({row.physical_station_id for row in self.result.stations}))

    def test_daily_values_keep_negative_star_dash_and_declared_time(self) -> None:
        daily = [row for row in self.result.observations if row.source_stream_type == "daily"]
        self.assertEqual(39, len(daily))
        self.assertTrue(any(isinstance(row.value, float) and row.value < 0 for row in daily))
        unpublished = next(row for row in daily if row.value == "*")
        unavailable = next(row for row in daily if row.value == "-")
        self.assertEqual(("missing", "not_published"), (unpublished.canonical_quality_flag, unpublished.source_quality_code))
        self.assertEqual(("missing", "unavailable"), (unavailable.canonical_quality_flag, unavailable.source_quality_code))
        self.assertTrue(all(row.measurement_datetime_utc.endswith("T06:00:00+00:00") for row in daily))
        levels = [row for row in daily if row.parameter == "water_level"]
        self.assertTrue(all(row.variation_window_hours == 24 for row in levels))
        self.assertTrue(all(row.trend in {None, "stagnant", "rising", "falling"} for row in levels))

    def test_nrt_history_offset_frequency_delay_and_deduplication(self) -> None:
        nrt = [row for row in self.result.observations if row.source_stream_type == "nrt"]
        self.assertGreater(len(nrt), 10000)
        self.assertTrue(all(row.measurement_timezone == "+01:00" for row in nrt))
        self.assertTrue(all(row.measurement_datetime_local.endswith("+01:00") for row in nrt))
        self.assertTrue(all(row.measurement_datetime_utc.endswith("+00:00") for row in nrt))
        self.assertTrue(all(row.capture_delay_seconds is not None for row in nrt))
        frequencies = {row.observation_frequency for row in nrt}
        self.assertTrue(any(value == "60 minutes" or value.startswith("variable") for value in frequencies))
        duplicate = asdict(nrt[0])
        self.assertEqual(1, len(dedupe([duplicate, dict(duplicate)], "observations")))

    def test_maximum_official_backfill_is_thirty_days(self) -> None:
        self.assertEqual(30, self.manifest["maximum_official_nrt_period_days"])
        nrt_urls = [row["url"] for row in self.manifest["payloads"] if row["label"].startswith("nrt-") and row["label"] != "nrt-index"]
        self.assertEqual(12, len(nrt_urls))
        self.assertTrue(all("period=30" in url for url in nrt_urls))

    def test_central_forecast_is_primary_and_has_explicit_semantics(self) -> None:
        self.assertEqual(36, len(self.result.forecasts))
        self.assertEqual(9, len({row.station_id for row in self.result.forecasts}))
        self.assertEqual(4, len([row for row in self.result.forecasts if row.station_id == "rs-42040"]))
        self.assertTrue(all(row.forecast_parameter == "water_level" and row.forecast_unit == "cm" for row in self.result.forecasts))
        self.assertTrue(all(row.target_date and row.forecast_issue_time_original for row in self.result.forecasts))
        self.assertTrue(all("alert=" in row.forecast_issue_time_original for row in self.result.forecasts))

    def test_individual_forecast_no_forecast_and_range_semantics(self) -> None:
        points, point_issues = self.adapter.parse_individual_forecast(
            self.payloads["daily-42010"], "rs-42010", "42010", date(2026, 8, 6),
        )
        absent, absent_issues = self.adapter.parse_individual_forecast(
            self.payloads["daily-42040"], "rs-42040", "42040", date(2026, 8, 6),
        )
        ranged, range_issues = self.adapter.parse_individual_forecast(
            self.payloads["daily-42055"], "rs-42055", "42055", date(2026, 8, 6),
        )
        self.assertEqual(4, len(points))
        self.assertEqual(["range_not_point_forecast"], [row.code for row in point_issues])
        self.assertEqual(([], []), (absent, absent_issues))
        self.assertEqual([], ranged)
        self.assertEqual(["range_not_point_forecast"], [row.code for row in range_issues])

    def test_workflow_and_code_have_no_tls_bypass_or_plain_http(self) -> None:
        paths = [
            ROOT / "scripts" / "sources" / "hidmet_rs.py",
            ROOT / "scripts" / "diagnose_rhmz_access.py",
            ROOT / ".github" / "workflows" / "test-international-sources.yml",
            ROOT / ".github" / "workflows" / "update-serbia-data.yml",
            ROOT / "scripts" / "collect_rhmz_windows.py",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths).casefold()
        forbidden = ["verify" + "=false", "--" + "insecure", "curl " + "-k", "http:" + "//hidmet"]
        self.assertFalse(any(value in text for value in forbidden))
        self.assertIn("ubuntu-latest", text)
        self.assertIn("windows-latest", text)
        self.assertIn("invoke-webrequest", text)
        self.assertIn("openssl s_client", text)

    def test_collection_profiles_support_overlap_and_component_isolation(self) -> None:
        expected = {"all": (10076, 36), "nrt": (10037, 0), "daily": (39, 0), "forecast": (0, 36)}
        for profile, counts in expected.items():
            adapter = HidmetAdapter()
            adapter.collection_profile = profile
            result = adapter.parse(self.payloads)
            self.assertEqual(counts, (len(result.observations), len(result.forecasts)))
            self.assertEqual(13, len(result.stations))

    def test_windows_handoff_and_three_hour_workflow_are_explicit(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "update-serbia-data.yml").read_text(encoding="utf-8")
        collector = (ROOT / "scripts" / "collect_rhmz_windows.py").read_text(encoding="utf-8")
        self.assertIn("runs-on: windows-latest", workflow)
        self.assertIn('cron: "17 */3 * * *"', workflow)
        self.assertIn("Europe/Belgrade", workflow)
        self.assertIn("serbia-schannel-handoff", workflow)
        self.assertIn("actions/download-artifact", workflow)
        self.assertIn("--precollected-root", workflow)
        self.assertIn("curl.exe/Schannel", collector)
        self.assertIn('"--location"', collector)
        self.assertIn('"--max-time"', collector)


if __name__ == "__main__":
    unittest.main()
