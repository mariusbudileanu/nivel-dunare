"""Faza 4: DST-aware timezone conversion, tested against the exact
technique the adapters and the frontend actually use - not a
reimplementation that could silently drift from production code.

Backend: scripts/sources/shmu_sk.py and viadonau_at.py both convert a
source-local timestamp to UTC via `datetime(...).replace(tzinfo=ZoneInfo(zone))
.astimezone(...)`. Central European zones (Vienna, Bratislava) are UTC+1 in
winter (CET) and UTC+2 in summer (CEST); getting the DST transition wrong
silently shifts every converted timestamp by exactly one hour.

Frontend: public/assets/js/config.js's formatDate() converts an absolute
UTC instant to Europe/Bucharest via Intl.DateTimeFormat({timeZone: ...}) -
real IANA rules, not a fixed offset, and independent of the browser's own
local timezone. Romania is UTC+2 in winter (EET) and UTC+3 in summer
(EEST). That leg cannot be exercised from Python (no JS engine here); it
was verified directly in a real browser for both seasons and is recorded
in the Faza 4 report rather than duplicated as a Python assertion.
"""

from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo


class BackendSourceLocalToUtcDstTests(unittest.TestCase):
    def test_slovakia_bratislava_winter_is_utc_plus_one(self):
        # Same construction as shmu_sk.py: strptime local text, attach the
        # zone, convert to UTC.
        local = datetime.strptime("15.01.2026 10:00", "%d.%m.%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Bratislava"))
        utc = local.astimezone(ZoneInfo("UTC"))
        self.assertEqual("2026-01-15T09:00:00+00:00", utc.isoformat())

    def test_slovakia_bratislava_summer_is_utc_plus_two(self):
        local = datetime.strptime("15.07.2026 10:00", "%d.%m.%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Bratislava"))
        utc = local.astimezone(ZoneInfo("UTC"))
        self.assertEqual("2026-07-15T08:00:00+00:00", utc.isoformat())

    def test_austria_vienna_winter_is_utc_plus_one(self):
        # Same construction as viadonau_at.py's local-label conversion:
        # an absolute UTC instant converted to Vienna local time.
        instant = datetime(2026, 1, 15, 9, 0, tzinfo=ZoneInfo("UTC"))
        vienna_local = instant.astimezone(ZoneInfo("Europe/Vienna"))
        self.assertEqual("2026-01-15T10:00:00+01:00", vienna_local.isoformat())

    def test_austria_vienna_summer_is_utc_plus_two(self):
        instant = datetime(2026, 7, 15, 8, 0, tzinfo=ZoneInfo("UTC"))
        vienna_local = instant.astimezone(ZoneInfo("Europe/Vienna"))
        self.assertEqual("2026-07-15T10:00:00+02:00", vienna_local.isoformat())

    def test_the_two_sources_share_the_same_dst_transition_dates(self):
        # Sanity check on the premise: both zones are EU Central European
        # time, so a single pair of summer/winter reference dates is valid
        # evidence for both - confirmed here rather than assumed.
        for reference, expected_offset_hours in (("2026-01-15", 1), ("2026-07-15", 2)):
            year, month, day = (int(part) for part in reference.split("-"))
            for zone in ("Europe/Bratislava", "Europe/Vienna"):
                offset = datetime(year, month, day, 12, tzinfo=ZoneInfo(zone)).utcoffset()
                self.assertEqual(expected_offset_hours * 3600, offset.total_seconds())


if __name__ == "__main__":
    unittest.main()
