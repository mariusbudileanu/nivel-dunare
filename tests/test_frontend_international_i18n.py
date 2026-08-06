from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


class InternationalFrontendI18nTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i18n = (PUBLIC / "assets" / "js" / "i18n.js").read_text(encoding="utf-8")
        cls.index = (PUBLIC / "index.html").read_text(encoding="utf-8")
        cls.app = (PUBLIC / "assets" / "js" / "app.js").read_text(encoding="utf-8")
        cls.beta = (PUBLIC / "assets" / "js" / "beta-ui.js").read_text(encoding="utf-8")
        cls.map_beta = (PUBLIC / "assets" / "js" / "map-beta.js").read_text(encoding="utf-8")

    def test_language_default_url_priority_persistence_and_html_lang(self):
        self.assertIn('let language = "ro"', self.i18n)
        self.assertRegex(self.i18n, r"language = translations\[requested\] \? requested : translations\[stored\] \? stored : \"ro\"")
        self.assertIn('localStorage.setItem("nivel-dunare-language", language)', self.i18n)
        self.assertIn("document.documentElement.lang = language", self.i18n)
        self.assertIn('url.searchParams.set("lang", language)', self.i18n)

    def test_language_button_is_accessible_and_adjacent_to_info(self):
        info_position = self.index.index('id="info-button"')
        language_position = self.index.index('id="language-button"')
        self.assertLess(info_position, language_position)
        self.assertLess(language_position - info_position, 600)
        button = re.search(r'<button[^>]+id="language-button"[^>]*>', self.index).group(0)
        self.assertIn("aria-label", button)
        self.assertIn("title", button)
        self.assertIn('type="button"', button)
        self.assertIn('addEventListener("click", toggleLanguage)', self.app)

    def test_static_translation_keys_exist_in_both_catalogues(self):
        ro_block, en_block = self.i18n.split("  en: {", 1)
        ro_keys = set(re.findall(r"(?:\{|,)\s*([A-Za-z][A-Za-z0-9]*):\s*\"", "{" + ro_block))
        en_keys = set(re.findall(r"(?:\{|,)\s*([A-Za-z][A-Za-z0-9]*):\s*\"", "{" + en_block.split("\n  },\n};", 1)[0]))
        self.assertEqual(ro_keys, en_keys)
        html_keys = set(re.findall(r'data-i18n(?:-placeholder|-aria-label|-title)?="([A-Za-z][A-Za-z0-9]*)"', self.index))
        self.assertFalse(html_keys - ro_keys)

    def test_dynamic_map_filters_popups_and_unmapped_list_are_translated(self):
        for key in ("allCountries", "allSources", "allStatuses", "allTypes", "noFilteredStations"):
            self.assertIn(f't("{key}")', self.beta)
        for key in ("officialSource", "sourceStatus", "openAnalysis", "discharge"):
            self.assertIn(f't("{key}")', self.map_beta)
        self.assertIn("discharge_m3_s", (PUBLIC / "assets" / "js" / "international.js").read_text(encoding="utf-8"))
        self.assertIn("data.unmapped.filter(matchesFilters)", self.beta)
        self.assertIn("onLanguageChange", self.beta)
        self.assertIn("refreshMapLanguage", self.app)

    def test_international_resources_and_existing_afdj_are_loaded_separately(self):
        data_source = (PUBLIC / "assets" / "js" / "data.js").read_text(encoding="utf-8")
        international = (PUBLIC / "assets" / "js" / "international.js").read_text(encoding="utf-8")
        self.assertIn('getJson("latest.geojson")', data_source)
        self.assertIn("loadInternationalData", data_source)
        for name in ("stations.json", "latest.json", "forecasts.json", "stations.geojson", "unmapped_stations.json", "quality_issues.json"):
            self.assertIn(name, international)

    def test_serbia_active_popup_is_bilingual_and_stream_specific(self):
        ro = "Date automate provizorii. Valorile sunt publicate exact așa cum sunt furnizate de RHMZ Serbia. Sursa precizează că datele nu sunt încă verificate și pot întârzia din cauza telemetriei sau a funcționării sistemului."
        en = "Provisional automatic data. Values are published exactly as provided by RHMZ Serbia. The source states that the data have not yet been validated and may be delayed because of telemetry or system issues."
        self.assertIn(ro, self.i18n)
        self.assertIn(en, self.i18n)
        for value in ("stream_nrt", "captureDelayMinutes", "dailyObservation", "frequencyVariable", "frequencyRsSchedule"):
            self.assertIn(value, self.i18n)
        self.assertIn('properties.source_status === "suspended" ? "rsTlsSuspended" : "rsProvisionalData"', self.map_beta)
        self.assertIn("rsStreamLine", self.map_beta)
        self.assertIn("capture_delay_seconds", self.map_beta)
        self.assertIn('"every 3 hours plus daily/forecast Europe/Belgrade gates": "frequencyRsSchedule"', self.i18n)

    def test_user_visible_templates_coalesce_optional_values(self):
        self.assertIn("String(value ?? \"\")", self.beta)
        self.assertIn("String(value ?? \"\")", self.map_beta)
        self.assertNotRegex(self.index, r">\s*(?:undefined|null)\s*<")
        self.assertIn("@media (max-width: 760px)", (PUBLIC / "assets" / "css" / "app.css").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
