from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.sources import get_adapter
from scripts.sources.base import load_fixture_payloads, write_result

FIXTURES = Path(__file__).parent / "fixtures" / "international"


class InternationalLiveVariantTests(unittest.TestCase):
    def test_shmu_station_without_temperature_column_keeps_level(self):
        adapter = get_adapter("sk")
        payloads = load_fixture_payloads(FIXTURES / "sk")
        payload = payloads["station-5141"]
        body = payload.body.replace(b"<td>201</td><td>46.2</td>", b"<td>201</td>")
        payloads["station-5141"] = replace(payload, body=body)
        result = adapter.parse(payloads)
        self.assertEqual("complete", result.status)
        station_observations = [row for row in result.observations if row.station_id == "sk-5141"]
        self.assertEqual(["water_level"], [row.parameter for row in station_observations])

    def test_shmu_high_temperature_is_preserved_without_local_threshold(self):
        adapter = get_adapter("sk")
        result = adapter.parse(load_fixture_payloads(FIXTURES / "sk"))
        observations = [
            row for row in result.observations
            if row.station_id == "sk-5141" and row.parameter == "water_temperature"
        ]
        self.assertEqual(1, len(observations))
        high = observations[0]
        self.assertEqual(46.2, high.value)
        self.assertEqual("provisional", high.canonical_quality_flag)
        self.assertNotEqual("outside_plausible_water_temperature_range", high.source_quality_code)
        self.assertNotIn(
            "outside_plausible_water_temperature_range",
            {issue.code for issue in result.issues},
        )
        self.assertEqual("complete", result.status)
        self.assertTrue(result.publishable)
        self.assertIn(high, result.usable_observations)
        self.assertTrue(any(
            row.station_id == "sk-5141" and row.parameter == "water_level"
            for row in result.usable_observations
        ))
        self.assertTrue(any(row.station_id == "sk-5141" for row in result.forecasts))
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            write_result(result, output)
            written_observations = json.loads((output / "observations.json").read_text(encoding="utf-8"))
            written_issues = json.loads((output / "issues.json").read_text(encoding="utf-8"))
        written = next(row for row in written_observations if row["station_id"] == "sk-5141" and row["parameter"] == "water_temperature")
        self.assertEqual(46.2, written["value"])
        self.assertEqual("provisional", written["canonical_quality_flag"])
        self.assertNotIn("outside_plausible_water_temperature_range", {issue["code"] for issue in written_issues})

    def test_hydroinfo_iso_8859_2_without_http_charset_is_lossless(self):
        adapter = get_adapter("hu")
        payloads = load_fixture_payloads(FIXTURES / "hu")
        payload = payloads["current"]
        text = payload.body.decode("utf-8")
        payloads["current"] = replace(
            payload, content_type="text/html", body=text.encode("iso-8859-2"),
        )
        result = adapter.parse(payloads)
        self.assertEqual("complete", result.status)
        self.assertIn("Gönyű", {station.station_name_local for station in result.stations})

    def test_appd_uses_demonstrated_official_hidrology_spelling(self):
        adapter = get_adapter("bg")
        self.assertEqual("https://www.appd-bg.org/hidrology-en", adapter.current_url)


if __name__ == "__main__":
    unittest.main()
