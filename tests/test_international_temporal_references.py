from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from scripts.sources import get_adapter
from scripts.sources.base import AdapterResult, load_fixture_payloads

FIXTURES = Path(__file__).parent / "fixtures" / "international"


class InternationalTemporalReferenceTests(unittest.TestCase):
    def parse(self, source: str):
        adapter = get_adapter(source)
        return adapter, adapter.parse(load_fixture_payloads(FIXTURES / source))

    def test_future_measurement_date_without_time_is_critical(self):
        adapter, parsed = self.parse("hr")
        observation = deepcopy(parsed.observations[0])
        observation.measurement_date = "2026-08-05"
        observation.measurement_datetime_utc = None
        result = AdapterResult(
            adapter.source_id, adapter.country_code, "complete",
            parsed.stations, [observation], [],
        )
        validated = adapter.validate(
            result, datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
        )
        self.assertIn("future_measurement_date", {issue.code for issue in validated.issues})
        self.assertEqual("partial", validated.status)
        self.assertIsNone(observation.measurement_datetime_utc)
        self.assertIsNone(observation.measurement_timezone)

    def test_staleness_threshold_is_configurable_per_adapter(self):
        adapter, parsed = self.parse("de")
        self.assertEqual(2, adapter.stale_after_days)
        result = AdapterResult(
            adapter.source_id, adapter.country_code, "complete",
            parsed.stations, parsed.observations, [],
        )
        validated = adapter.validate(
            result, datetime(2026, 8, 10, tzinfo=timezone.utc),
        )
        self.assertIn("stale_source", {issue.code for issue in validated.issues})
        self.assertEqual("partial", validated.status)

    def test_hr_staleness_uses_adapter_specific_suspended_status(self):
        adapter, parsed = self.parse("hr")
        self.assertEqual(7, adapter.stale_after_days)
        self.assertEqual("suspended", adapter.stale_status)
        result = AdapterResult(
            adapter.source_id, adapter.country_code, "complete",
            parsed.stations, parsed.observations, [],
        )
        validated = adapter.validate(
            result, datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
        self.assertIn("stale_source", {issue.code for issue in validated.issues})
        self.assertEqual("suspended", validated.status)

    def test_observation_and_forecast_references_must_resolve(self):
        adapter, parsed = self.parse("at")
        observation = deepcopy(parsed.observations[0])
        forecast = deepcopy(parsed.forecasts[0])
        observation.station_id = "at-missing-observation-station"
        forecast.station_id = "at-missing-forecast-station"
        result = AdapterResult(
            adapter.source_id, adapter.country_code, "complete",
            parsed.stations, [observation], [forecast],
        )
        validated = adapter.validate(
            result, datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
        )
        codes = {issue.code for issue in validated.issues}
        self.assertIn("orphan_observation", codes)
        self.assertIn("orphan_forecast", codes)
        self.assertEqual("partial", validated.status)


if __name__ == "__main__":
    unittest.main()
