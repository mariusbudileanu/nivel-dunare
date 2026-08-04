import csv
import json
import unittest
from pathlib import Path

from scripts.afdj_core import validate_repository


ROOT = Path(__file__).resolve().parents[1]


class PublicOutputTests(unittest.TestCase):
    def test_repository_outputs(self):
        result = validate_repository(ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["stations"], 23)
        forecasts_per_issue = result["stations"] * 5
        self.assertGreaterEqual(result["forecasts"], forecasts_per_issue)
        self.assertEqual(result["forecasts"] % forecasts_per_issue, 0)

    def test_station_lazy_files_exist(self):
        with (ROOT / "data/public/stations.csv").open(encoding="utf-8-sig", newline="") as stream:
            stations = list(csv.DictReader(stream))
        for station in stations:
            slug = station["slug"]
            for suffix in ("observations.json", "forecasts.json", "forecast-scores.json"):
                path = ROOT / f"data/public/station/{slug}-{suffix}"
                self.assertTrue(path.is_file(), path)
                json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__": unittest.main()
