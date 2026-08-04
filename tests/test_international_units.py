import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from scripts.sources import get_adapter
from scripts.sources.base import AdapterResult, SourceStructureError, load_fixture_payloads


class InternationalUnitTests(unittest.TestCase):
    def test_normalized_unit_change_is_critical(self):
        adapter = get_adapter("de")
        fixtures = Path(__file__).parent / "fixtures" / "international" / "de"
        parsed = adapter.parse(load_fixture_payloads(fixtures))
        observation = deepcopy(parsed.observations[0])
        observation.unit = "m"
        result = AdapterResult("pegelonline_de", "DE", "complete", parsed.stations, [observation], [])
        validated = adapter.validate(result, datetime(2026, 8, 4, tzinfo=timezone.utc))
        self.assertIn("unit_change", {issue.code for issue in validated.issues})
        self.assertFalse(validated.publishable)

    def test_pegelonline_source_unit_change_is_rejected(self):
        adapter = get_adapter("de")
        fixtures = Path(__file__).parent / "fixtures" / "international" / "de"
        payloads = load_fixture_payloads(fixtures)
        payload = payloads["stations"]
        changed = payload.body.replace(b'"unit": "cm"', b'"unit": "m"', 1)
        payloads["stations"] = type(payload)(
            payload.label, payload.url, payload.status, payload.content_type,
            changed, payload.captured_at_utc, payload.headers,
        )
        with self.assertRaises(SourceStructureError):
            adapter.parse(payloads)


if __name__ == "__main__":
    unittest.main()
