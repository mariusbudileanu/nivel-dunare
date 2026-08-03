import unittest
from datetime import timedelta

from scripts.afdj_core import BUCHAREST, parse_decimal, parse_source_datetime


class NormalizationTests(unittest.TestCase):
    def test_numeric_formats(self):
        cases = [
            ("-213", False, "-213"), ("+5", False, "5"), ("27,5 °C", False, "27.5"),
            (" 62 cm ", False, "62"), ("1.072", True, "1072"), ("2.510 cm", True, "2510"),
            ("0", False, "0"), ("", False, None), ("Mm", True, None),
        ]
        for raw, grouping, expected in cases:
            parsed = parse_decimal(raw, integer_grouping=grouping)
            self.assertEqual(None if parsed is None else str(parsed), expected)

    def test_iso_datetime_timezone(self):
        parsed = parse_source_datetime("2026-08-03T03:00:00+03:00")
        self.assertEqual(parsed.date().isoformat(), "2026-08-03")
        self.assertEqual(parsed.utcoffset(), timedelta(hours=3))

    def test_local_date_gets_bucharest_timezone(self):
        parsed = parse_source_datetime("03/08/2026")
        self.assertEqual(parsed.tzinfo, BUCHAREST)


if __name__ == "__main__": unittest.main()
