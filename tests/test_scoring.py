import tempfile
import unittest
from pathlib import Path

from scripts.afdj_core import FORECAST_FIELDS, OBSERVATION_FIELDS, calculate_scores, write_csv


class ScoringTests(unittest.TestCase):
    def test_mae_rmse_bias_and_thresholds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "data/canonical").mkdir(parents=True)
            observations = []
            forecasts = []
            for index, (observed, forecast) in enumerate([(100, 105), (100, 90), (100, 120)], start=1):
                day = f"2026-08-0{index}"
                obs = {field: "" for field in OBSERVATION_FIELDS}; obs.update({"station_id": "s", "measurement_date": day, "level_cm": str(observed)})
                fc = {field: "" for field in FORECAST_FIELDS}; fc.update({"station_id": "s", "target_date": day, "lead_hours": "24", "forecast_level_cm": str(forecast), "forecast_available": "True"})
                observations.append(obs); forecasts.append(fc)
            write_csv(root / "data/canonical/observations.csv", OBSERVATION_FIELDS, observations)
            write_csv(root / "data/canonical/forecasts.csv", FORECAST_FIELDS, forecasts)
            rows = calculate_scores(root); score = next(row for row in rows if row["lead_hours"] == 24)
            self.assertEqual(score["n_pairs"], 3)
            self.assertAlmostEqual(float(score["mae_cm"]), 35 / 3, places=5)
            self.assertAlmostEqual(float(score["bias_cm"]), 5, places=5)
            self.assertAlmostEqual(float(score["within_5cm_pct"]), 100 / 3, places=5)
            self.assertEqual(score["maturity"], "Date insuficiente")


if __name__ == "__main__": unittest.main()
