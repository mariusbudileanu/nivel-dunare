import unittest
from pathlib import Path

from scripts.sources import get_adapter
from scripts.sources.base import load_fixture_payloads


class InternationalNoInferenceTests(unittest.TestCase):
    def test_bg_day_month_forecasts_do_not_invent_year_or_timezone(self):
        fixtures = Path(__file__).parent / "fixtures" / "international" / "bg"
        result = get_adapter("bg").parse(load_fixture_payloads(fixtures))
        self.assertEqual(30, len(result.forecasts))
        self.assertTrue(all(item.target_date is None for item in result.forecasts))
        self.assertTrue(all(item.target_datetime_utc is None for item in result.forecasts))
        self.assertTrue(all(item.forecast_parameter is None for item in result.forecasts))
        self.assertTrue(all(item.forecast_unit is None for item in result.forecasts))
        self.assertTrue(all(item.target_time_original.endswith(".08") for item in result.forecasts))


if __name__ == "__main__":
    unittest.main()
