from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_international_public_data import EXPECTED_COUNTS, SOURCE_POLICY, build
from scripts.validate_international_public_data import FILES, observation_identity, validate


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = ROOT / "data" / "public" / "international"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class InternationalPublicDataTests(unittest.TestCase):
    def test_committed_public_contract_and_mirror(self):
        result = validate(PUBLIC_ROOT, ROOT / "public" / "data" / "international")
        self.assertTrue(result["ok"])
        self.assertEqual((result["stations"], result["mapped"], result["unmapped"]), (101, 101, 0))

    def test_publication_policy_is_explicit_and_isolated_from_afdj(self):
        self.assertEqual(SOURCE_POLICY["de"]["status"], "complete")
        self.assertEqual(SOURCE_POLICY["at"]["status"], "partial")
        self.assertEqual(SOURCE_POLICY["sk"]["status"], "partial")
        self.assertEqual(SOURCE_POLICY["hr"]["status"], "partial")
        self.assertFalse(SOURCE_POLICY["hr"]["current"])
        self.assertFalse(SOURCE_POLICY["bg"]["forecasts"])
        self.assertFalse(SOURCE_POLICY["rs"]["observations"])
        self.assertTrue((ROOT / "data" / "public" / "latest.geojson").is_file())
        self.assertTrue((PUBLIC_ROOT / "stations.geojson").is_file())

    def test_public_data_quality_mapping_and_references(self):
        stations = load_json(PUBLIC_ROOT / "stations.json")
        observations = load_json(PUBLIC_ROOT / "observations.json")
        latest = load_json(PUBLIC_ROOT / "latest.json")
        forecasts = load_json(PUBLIC_ROOT / "forecasts.json")
        issues = load_json(PUBLIC_ROOT / "quality_issues.json")
        features = load_json(PUBLIC_ROOT / "stations.geojson")["features"]
        unmapped = load_json(PUBLIC_ROOT / "unmapped_stations.json")
        ids = {row["station_id"] for row in stations}
        self.assertEqual(len(ids), 101)
        self.assertTrue({row["station_id"] for row in observations + forecasts + latest} <= ids)
        self.assertEqual(len(features), 93)
        self.assertEqual(len(unmapped), 0)
        self.assertEqual(sum(feature["properties"]["is_exact_station_location"] for feature in features), 57)
        self.assertEqual(sum(not feature["properties"]["is_exact_station_location"] for feature in features), 36)
        self.assertFalse(any(row["country_code"] == "HR" for row in latest))
        self.assertFalse(any(row["source_id"] == "appd_bg" for row in forecasts))
        self.assertEqual(len([row for row in stations if row["country_code"] == "RS"]), 13)
        self.assertFalse(any(row["country_code"] == "RS" for row in observations + forecasts))
        self.assertFalse(any(row["canonical_quality_flag"] == "suspect" for row in observations))
        high = [row for row in observations if row["country_code"] == "SK" and row["parameter"] == "water_temperature" and float(row["value"]) > 45]
        self.assertTrue(high)
        self.assertTrue(all(row["canonical_quality_flag"] == "provisional" and row["current_usable"] for row in high))
        legacy = [row for row in issues if row.get("quality_origin") == "legacy_application_rule"]
        self.assertTrue(any(row.get("observation", {}).get("value") == 46.2 for row in legacy))
        self.assertTrue(all(row.get("historical") and row.get("active") is False for row in legacy))
        self.assertTrue(all(row.get("source_url") and row.get("source_file_sha256") and row.get("captured_at_utc") for row in observations))

    def test_builder_round_trip_from_candidate_shape(self):
        public_stations = load_json(PUBLIC_ROOT / "stations.json")
        public_observations = load_json(PUBLIC_ROOT / "observations.json")
        public_forecasts = load_json(PUBLIC_ROOT / "forecasts.json")
        public_issues = load_json(PUBLIC_ROOT / "quality_issues.json")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            candidates = root / "candidate"
            archive = root / "archive"
            historical = root / "historical"
            historical_archive = root / "historical-archive"
            archive.mkdir(parents=True)
            historical.mkdir(parents=True)
            historical_archive.mkdir(parents=True)
            summaries = []
            for country in ("de", "at", "sk", "hu", "hr", "bg"):
                country_code = country.upper()
                target = candidates / country
                target.mkdir(parents=True)
                stations = [row for row in public_stations if row["country_code"] == country_code]
                observations = [row for row in public_observations if row["country_code"] == country_code]
                forecasts = [row for row in public_forecasts if row["country_code"] == country_code]
                issues = [row for row in public_issues if row.get("source_id") == SOURCE_POLICY[country]["source_id"]]
                self.assertEqual(len(stations), EXPECTED_COUNTS[country])
                for name, value in (("stations.json", stations), ("observations.json", observations), ("forecasts.json", forecasts), ("issues.json", issues)):
                    (target / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                summaries.append({"source": country, "status": "complete" if country not in {"at", "hr", "bg"} else "partial"})
            (candidates / "summary.json").write_text(json.dumps({"sources": summaries}), encoding="utf-8")

            seen = set()
            for index, row in enumerate(public_observations + public_forecasts):
                sha = row.get("source_file_sha256")
                captured = row.get("captured_at_utc")
                source = row.get("source_id")
                if not sha or not captured or (sha, source) in seen:
                    continue
                seen.add((sha, source))
                (archive / f"{index}.metadata.json").write_text(json.dumps({"content_sha256": sha, "captured_at_utc": captured, "source": source}), encoding="utf-8")

            historical_issue = next(row for row in public_issues if row.get("historical") and row.get("observation", {}).get("value") == 46.2)
            historical_observation = historical_issue["observation"]
            (historical / "observations.json").write_text(json.dumps([historical_observation]), encoding="utf-8")
            (historical / "issues.json").write_text(json.dumps([{"record_id": historical_observation["station_id"], "code": "outside_plausible_water_temperature_range"}]), encoding="utf-8")
            (historical_archive / "capture.metadata.json").write_text(json.dumps({
                "content_sha256": historical_observation["source_file_sha256"],
                "captured_at_utc": historical_issue["captured_at_utc"],
                "source": "shmu_sk",
            }), encoding="utf-8")

            output = root / "output"
            mirror = root / "mirror"
            status = build(
                candidates,
                ROOT / "docs" / "INTERNATIONAL_STATIONS_AUDIT.csv",
                archive,
                output,
                mirror,
                historical,
                historical_archive,
                "fixture-test",
                "live-test",
            )
            self.assertEqual(status["station_count"], 101)
            self.assertEqual(set(path.name for path in output.iterdir()), set(FILES))
            self.assertTrue(validate(output, mirror)["ok"])
            output_text = "\n".join((output / name).read_text(encoding="utf-8") for name in FILES)
            self.assertNotIn("viadonau_partner_key=", output_text.casefold())


if __name__ == "__main__":
    unittest.main()
