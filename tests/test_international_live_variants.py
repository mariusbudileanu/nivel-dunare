from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.sources import get_adapter
from scripts.sources.base import SourceStructureError, load_fixture_payloads, write_result

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

    def test_appd_automatic_station_missing_reading_keeps_station_without_inventing_values(self):
        # Observed live on 2026-08-07: Malak Preslavets' automatic row had only
        # name+km ("<tr><td>Malak Preslavets</td><td>413.90</td></tr>"), missing
        # level/diff-icon/temperature entirely - not a station gained or lost,
        # just today's reading absent. The old len(row) >= 5 filter silently
        # dropped the whole row, tripping the "< 12" station-loss guard.
        adapter = get_adapter("bg")
        payloads = load_fixture_payloads(FIXTURES / "bg")
        payload = payloads["current"]
        body = payload.body.replace(
            b'<tr><td>Malak Preslavets</td><td>453.6</td><td>-170</td>'
            b'<td><img src="images/nav/nochange.gif"></td><td>27.0</td></tr>',
            b'<tr><td>Malak Preslavets</td><td>453.6</td></tr>',
        )
        self.assertNotEqual(body, payload.body, "fixture row text did not match; test would be vacuous")
        payloads["current"] = replace(payload, body=body)
        result = adapter.parse(payloads)
        self.assertEqual(0, len([i for i in result.issues if i.severity == "critical"]))
        automatic_stations = [s for s in result.stations if s.station_type == "automatic"]
        self.assertEqual(12, len(automatic_stations))
        preslavets = next(s for s in automatic_stations if s.station_name_local == "Malak Preslavets")
        preslavets_observations = [row for row in result.observations if row.station_id == preslavets.station_id]
        self.assertEqual([], preslavets_observations, "no value should be invented for the missing reading")
        # The station listed right after Malak Preslavets in the source table
        # must keep its own correct trend direction, not the one meant for a
        # different row shifted in by the gap.
        silistra = next(s for s in automatic_stations if "силистра" in s.station_name_local.casefold())
        silistra_level = next(
            row for row in result.observations
            if row.station_id == silistra.station_id and row.parameter == "water_level"
        )
        self.assertEqual("up", silistra_level.trend)

    def test_appd_automatic_row_entirely_removed_still_fails_closed(self):
        # A missing-reading row (kept, tested above) must stay distinct from an
        # actually removed station (still rejected): the count guard exists to
        # catch a real roster shrink, and a lenient row filter must not defeat it.
        adapter = get_adapter("bg")
        payloads = load_fixture_payloads(FIXTURES / "bg")
        payload = payloads["current"]
        body = payload.body.replace(
            b'<tr><td>Malak Preslavets</td><td>453.6</td><td>-170</td>'
            b'<td><img src="images/nav/nochange.gif"></td><td>27.0</td></tr>',
            b"",
        )
        self.assertNotEqual(body, payload.body, "fixture row text did not match; test would be vacuous")
        payloads["current"] = replace(payload, body=body)
        with self.assertRaises(SourceStructureError):
            adapter.parse(payloads)

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
