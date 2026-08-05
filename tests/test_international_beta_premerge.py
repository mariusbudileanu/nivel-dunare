from __future__ import annotations

import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
DATA = ROOT / "data" / "public" / "international"
JS = PUBLIC / "assets" / "js"


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class _TranslationAuditParser(HTMLParser):
    TRANSLATED_ATTRIBUTES = {
        "aria-label": "data-i18n-aria-label",
        "placeholder": "data-i18n-placeholder",
        "title": "data-i18n-title",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[dict[str, str]] = []
        self.untranslated_attributes: list[tuple[str, str, str]] = []
        self.untranslated_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.stack.append(values)
        for attribute, translation_attribute in self.TRANSLATED_ATTRIBUTES.items():
            if values.get(attribute) and not values.get(translation_attribute):
                self.untranslated_attributes.append((tag, attribute, values[attribute]))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.stack:
            self.stack.pop()

    def handle_data(self, value):
        text = " ".join(value.split())
        if not text or not re.search(r"[A-Za-zĂÂÎȘȚăâîșț]", text):
            return
        parent = self.stack[-1] if self.stack else {}
        if parent.get("id") == "language-button":
            return
        if not parent.get("data-i18n"):
            self.untranslated_text.append(text)


class InternationalBetaPremergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i18n = (JS / "i18n.js").read_text(encoding="utf-8")
        cls.index = (PUBLIC / "index.html").read_text(encoding="utf-8")
        cls.scripts = {
            path.name: path.read_text(encoding="utf-8")
            for path in JS.glob("*.js")
        }

    def test_every_literal_translation_call_exists_in_both_catalogues(self):
        ro_block, en_block = self.i18n.split("  en: {", 1)
        key_pattern = r'(?:\{|,)\s*([A-Za-z][A-Za-z0-9]*):\s*"'
        ro_keys = set(re.findall(key_pattern, "{" + ro_block))
        en_keys = set(re.findall(key_pattern, "{" + en_block.split("\n  },\n};", 1)[0]))
        called = set()
        for source in self.scripts.values():
            called.update(re.findall(r'\bt\("([A-Za-z][A-Za-z0-9]*)"\)', source))
        self.assertEqual(ro_keys, en_keys)
        self.assertEqual(called - ro_keys, set())

    def test_static_html_text_and_accessibility_attributes_are_translatable(self):
        parser = _TranslationAuditParser()
        parser.feed(self.index)
        self.assertEqual(parser.untranslated_attributes, [])
        self.assertEqual(parser.untranslated_text, ["Nivelul Dunării"])

    def test_all_public_statuses_and_station_types_are_presented(self):
        beta = self.scripts["beta-ui.js"]
        css = (PUBLIC / "assets" / "css" / "app.css").read_text(encoding="utf-8")
        statuses = ("complete", "partial", "provisional", "suspect", "stale", "suspended", "unavailable")
        for status in statuses:
            self.assertIn(f'"{status}"', beta)
            self.assertIn(f'data-i18n="{status}"', self.index)
            marker_status = "international" if status == "complete" else status
            self.assertIn(f".status-tag.{status}", css)
            self.assertIn(f".station-marker.{marker_status}", css)
        for station_type in ("gauge", "hydrometric", "automatic", "manual"):
            self.assertIn(f"{station_type}:", self.i18n)
        self.assertIn("stationTypeLabel(value)", beta)

    def test_language_change_rerenders_open_and_dynamic_components(self):
        app = self.scripts["app.js"]
        map_beta = self.scripts["map-beta.js"]
        for call in ("renderStationOptions()", "renderDownloads()", "await renderCompare()"):
            self.assertIn(call, app)
        self.assertIn("refreshMapLanguage()", app)
        self.assertIn("bindOpenAnalysisButton", map_beta)
        self.assertIn("popup.setContent", map_beta)
        self.assertIn('stationTypeLabel(properties.station_type)', map_beta)
        self.assertIn('properties.forecast_count', map_beta)
        self.assertIn('austriaTestSourceWarning', map_beta)
        self.assertIn("applyTranslations", self.scripts["beta-ui.js"])

    def test_suspect_temperature_does_not_poison_valid_slovak_level(self):
        source = self.scripts["international.js"]
        self.assertIn('if (row.parameter === "water_level")', source)
        self.assertIn('if (row.parameter === "water_temperature" && row.canonical_quality_flag !== "suspect")', source)
        self.assertNotIn('if (row.canonical_quality_flag === "suspect") item.quality_flag = "suspect"', source)
        observations = load_json("observations.json")
        iza = [row for row in observations if row["station_id"] == "sk-6860"]
        self.assertTrue(any(row["parameter"] == "water_temperature" and row["canonical_quality_flag"] == "suspect" for row in iza))
        self.assertTrue(any(row["parameter"] == "water_level" and row["current_usable"] for row in iza))

    def test_contract_counts_quality_evidence_and_references(self):
        status = load_json("status.json")
        stations = load_json("stations.json")
        observations = load_json("observations.json")
        latest = load_json("latest.json")
        forecasts = load_json("forecasts.json")
        issues = load_json("quality_issues.json")
        station_ids = {row["station_id"] for row in stations}
        self.assertEqual(status["contract_version"], "1.2-beta")
        self.assertEqual((status["complete_source_count"], status["partial_source_count"], status["suspended_source_count"]), (2, 3, 2))
        self.assertEqual(status["observation_count"], len(observations))
        self.assertEqual(status["forecast_count"], len(forecasts))
        self.assertEqual(status["latest_valid_count"], len(latest))
        self.assertEqual(status["current_usable_observation_count"], sum(row["current_usable"] for row in observations))
        self.assertEqual(status["stale_observation_count"], sum(row["stale"] for row in observations))
        self.assertEqual(status["provisional_observation_count"], sum(row["canonical_quality_flag"] == "provisional" for row in observations))
        self.assertLess(status["current_usable_observation_count"], status["observation_count"])
        self.assertTrue({row["station_id"] for row in observations + latest + forecasts} <= station_ids)
        temperature_issues = [row for row in issues if row["code"] == "outside_plausible_water_temperature_range"]
        historical = next(row for row in temperature_issues if row["historical"] and row["observation"]["value"] == 46.2)
        suspect_observations = [row for row in observations if row["canonical_quality_flag"] == "suspect"]
        evidenced = {(
            row["observation"].get("station_id"), row["observation"].get("parameter"),
            row["observation"].get("value"), row["observation"].get("measurement_datetime_utc"),
            row["observation"].get("source_file_sha256"),
        ) for row in temperature_issues}
        self.assertTrue(suspect_observations)
        self.assertTrue(all((
            row.get("station_id"), row.get("parameter"), row.get("value"),
            row.get("measurement_datetime_utc"), row.get("source_file_sha256"),
        ) in evidenced for row in suspect_observations))
        self.assertEqual(historical["observation"]["canonical_quality_flag"], "suspect")
        self.assertFalse(historical["observation"].get("current_usable", False))

    def test_provenance_and_original_times_are_preserved(self):
        for row in load_json("observations.json"):
            self.assertTrue(row["source_url"])
            self.assertRegex(row["source_file_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(row["captured_at_utc"])
            self.assertTrue(row.get("measurement_time_original") or row.get("measurement_date"))
            self.assertTrue(row.get("measurement_datetime_utc") or row.get("measurement_datetime_local") or row.get("measurement_date"))
        for row in load_json("forecasts.json"):
            self.assertTrue(row["source_url"])
            self.assertRegex(row["source_file_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(row["captured_at_utc"])
            self.assertTrue(row.get("target_time_original") or row.get("target_date"))
            self.assertTrue(row.get("target_datetime_utc") or row.get("target_date"))

    def test_literal_javascript_id_references_exist_in_html(self):
        html_ids = set(re.findall(r'id="([A-Za-z][A-Za-z0-9_-]*)"', self.index))
        references = set()
        for source in self.scripts.values():
            references.update(re.findall(r'\$\("#([A-Za-z][A-Za-z0-9_-]*)"\)', source))
        self.assertEqual(references - html_ids, set())
        self.assertIn("const chartIds = {", self.scripts["app.js"])
    def test_no_mechanical_placeholders_or_null_rendering(self):
        combined = "\n".join(self.scripts.values())
        self.assertNotIn("+[char]", combined)
        self.assertNotIn("${null}", combined)
        self.assertNotIn("${undefined}", combined)
        self.assertNotIn("issue.message", self.scripts["app.js"])
        self.assertEqual(self.scripts["map.js"].strip().splitlines()[-1], 'export * from "./map-beta.js";')


if __name__ == "__main__":
    unittest.main()
