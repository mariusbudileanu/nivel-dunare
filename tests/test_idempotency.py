import tempfile
import unittest
from pathlib import Path

from scripts.afdj_core import CORRECTION_FIELDS, OBSERVATION_FIELDS, read_csv, upsert_rows


class IdempotencyTests(unittest.TestCase):
    def test_same_logical_record_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "observations.csv"; corrections = root / "corrections.csv"
            record = {field: "" for field in OBSERVATION_FIELDS}
            record.update({"station_id": "uuid-1", "measurement_datetime": "2026-08-03T03:00:00+03:00", "level_cm": "10", "first_seen_at": "a", "last_seen_at": "a"})
            first = upsert_rows(path, OBSERVATION_FIELDS, [record], ("station_id", "measurement_datetime"), "observation", corrections, "a", "sha")
            second = upsert_rows(path, OBSERVATION_FIELDS, [record], ("station_id", "measurement_datetime"), "observation", corrections, "b", "sha")
            self.assertEqual(len(read_csv(path)), 1)
            self.assertEqual(first[:2], (1, 0))
            self.assertEqual(second, (0, 0, False))
            self.assertEqual(read_csv(corrections), [])

    def test_correction_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / "observations.csv"; corrections = root / "corrections.csv"
            base = {field: "" for field in OBSERVATION_FIELDS}; base.update({"station_id": "uuid-1", "measurement_datetime": "d", "level_cm": "10"})
            upsert_rows(path, OBSERVATION_FIELDS, [base], ("station_id", "measurement_datetime"), "observation", corrections, "a", "sha")
            changed = dict(base, level_cm="11")
            upsert_rows(path, OBSERVATION_FIELDS, [changed], ("station_id", "measurement_datetime"), "observation", corrections, "b", "sha2")
            rows = read_csv(corrections)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["field_name"], "level_cm")


if __name__ == "__main__": unittest.main()
