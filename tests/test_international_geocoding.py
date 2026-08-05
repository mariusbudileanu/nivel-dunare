from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_international_public_data import apply_coordinate_registry
from scripts.geocode_international_stations import (
    CACHE_VERSION,
    FIELDS,
    PROVIDER,
    build_query,
    classify_results,
    run,
)
from scripts.validate_international_public_data import validate


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / "tests/fixtures/international/geocoding/nominatim_results.json").read_text(encoding="utf-8"))


def station(station_id="sk-test", name="Iza", local="Iža", country="SK"):
    return {
        "station_id": station_id,
        "station_name": name,
        "station_name_local": local,
        "country_code": country,
        "mapped": False,
    }


class InternationalGeocodingTests(unittest.TestCase):
    def classify(self, fixture_name, row=None):
        return classify_results(row or station(), FIXTURE[fixture_name], "2026-08-04T12:00:00Z", "https://nominatim.example/search?q=test")

    def test_valid_locality_is_medium_with_complete_provenance(self):
        result = self.classify("valid_locality")
        self.assertEqual((result["review_status"], result["coordinate_confidence"]), ("accepted", "medium"))
        self.assertEqual((result["latitude"], result["longitude"]), ("47.750348", "18.2235858"))
        self.assertEqual(result["coordinate_provider"], PROVIDER)
        self.assertEqual(result["coordinate_method"], "geocoded_locality")
        self.assertTrue(result["source_url"].startswith("https://"))

    def test_wrong_country_is_rejected(self):
        result = self.classify("wrong_country")
        self.assertEqual(result["coordinate_confidence"], "unresolved")
        self.assertIn("wrong_country", result["review_notes"])

    def test_outside_danube_sector_is_rejected(self):
        result = self.classify("outside_danube_sector")
        self.assertEqual(result["review_status"], "required")
        self.assertIn("outside_danube_sector_envelope", result["review_notes"])

    def test_non_locality_is_rejected(self):
        result = self.classify("non_locality")
        self.assertIn("not_a_locality", result["review_notes"])
        self.assertFalse(result["latitude"])

    def test_ambiguous_homonyms_require_review_and_are_not_mapped(self):
        row = station(name="Testovce", local="Testovce")
        result = self.classify("ambiguous_homonyms", row)
        self.assertEqual((result["coordinate_confidence"], result["review_status"]), ("low", "required"))
        self.assertIn("ambiguous", result["review_notes"])
        self.assertFalse(result["latitude"])

    def test_query_cleans_only_documented_technical_suffix(self):
        row = station("sk-5138", "Cunovo - horna hladina", "Čunovo - horná hladina")
        self.assertEqual(build_query(row), "Čunovo, Slovakia")
        self.assertEqual(row["station_name_local"], "Čunovo - horná hladina")

    def test_cache_resume_does_not_call_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            stations = root / "stations.json"
            registry = root / "registry.csv"
            cache = root / "cache.json"
            row = station()
            stations.write_text(json.dumps([row]), encoding="utf-8")
            query = build_query(row)
            cache.write_text(json.dumps({
                "cache_version": CACHE_VERSION,
                "provider": PROVIDER,
                "queries": {"sk|iza slovakia": {
                    "query": query, "country_code": "SK", "requested_at_utc": "2026-08-04T12:00:00Z",
                    "request_url": "https://nominatim.example/search?q=iza", "results": FIXTURE["valid_locality"],
                }},
            }), encoding="utf-8")
            with patch("scripts.geocode_international_stations.request_results", side_effect=AssertionError("network called")):
                report = run(stations, registry, cache, live=True)
            self.assertEqual(report["requests_made"], 0)
            self.assertEqual(report["accepted"], 1)

    def test_registry_never_overwrites_official_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "registry.csv"
            targets = []
            rows = []
            for index in range(75):
                station_id = f"sk-{index}"
                targets.append({"station_id": station_id, "latitude": None, "longitude": None})
                rows.append({key: "" for key in FIELDS} | {
                    "station_id": station_id, "country_code": "SK", "station_name": f"S{index}",
                    "station_name_local": f"S{index}", "coordinate_method": "geocoded_locality",
                    "coordinate_confidence": "unresolved", "review_status": "required",
                })
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=FIELDS)
                writer.writeheader(); writer.writerows(rows)
            official = {"station_id": "de-official", "latitude": 48.1, "longitude": 11.1, "coordinate_source": "official"}
            all_stations = [official, *targets]
            apply_coordinate_registry(all_stations, path)
            self.assertEqual((official["latitude"], official["longitude"]), (48.1, 11.1))
            self.assertTrue(official["is_exact_station_location"])
            self.assertEqual(official["coordinate_method"], "official_station_coordinate")

    def test_committed_public_contract_separates_coordinate_types(self):
        result = validate(ROOT / "data/public/international", ROOT / "public/data/international")
        self.assertEqual((result["official_coordinates"], result["manually_verified_coordinates"], result["approximate_coordinates"], result["unmapped"]), (50, 15, 36, 0))
        stations = json.loads((ROOT / "data/public/international/stations.json").read_text(encoding="utf-8"))
        approximate = [row for row in stations if row["mapped"] and not row["is_exact_station_location"]]
        unresolved = [row for row in stations if not row["mapped"]]
        self.assertTrue(all(row["coordinate_review_status"] == "accepted" for row in approximate))
        self.assertTrue(all(row["coordinate_review_status"] == "required" for row in unresolved))

    def test_frontend_has_filter_warning_shape_and_overlap_mechanism(self):
        index = (ROOT / "public/index.html").read_text(encoding="utf-8")
        i18n = (ROOT / "public/assets/js/i18n.js").read_text(encoding="utf-8")
        css = (ROOT / "public/assets/css/app.css").read_text(encoding="utf-8")
        map_js = (ROOT / "public/assets/js/map-beta.js").read_text(encoding="utf-8")
        self.assertIn('id="coordinate-filter"', index)
        self.assertIn("Poziție aproximativă la nivelul localității; nu reprezintă amplasamentul exact al mirei sau senzorului.", i18n)
        self.assertIn("Approximate locality-level position; not the exact gauge or sensor location.", i18n)
        self.assertIn(".station-marker.approximate", css)
        self.assertIn("sharedLocalityStations", map_js)
        self.assertIn("group.visibleProperties", map_js)


if __name__ == "__main__":
    unittest.main()
