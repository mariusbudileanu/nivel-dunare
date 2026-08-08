from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_international_public_data import EXPECTED_COUNTS, SOURCE_POLICY, _stream_rows, build, enrich_observation
from scripts.validate_international_public_data import FILES, observation_identity, validate


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = ROOT / "data" / "public" / "international"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class InternationalPublicDataTests(unittest.TestCase):
    def test_committed_public_contract_and_mirror(self):
        result = validate(PUBLIC_ROOT, ROOT / "public" / "data" / "international")
        self.assertTrue(result["ok"])
        self.assertEqual((result["stations"], result["mapped"], result["unmapped"]), (102, 102, 0))

    def test_publication_policy_is_explicit_and_isolated_from_afdj(self):
        self.assertEqual(SOURCE_POLICY["de"]["status"], "complete")
        self.assertEqual(SOURCE_POLICY["at"]["status"], "partial")
        self.assertEqual(SOURCE_POLICY["sk"]["status"], "partial")
        self.assertEqual(SOURCE_POLICY["hr"]["status"], "partial")
        self.assertFalse(SOURCE_POLICY["hr"]["current"])
        self.assertFalse(SOURCE_POLICY["bg"]["forecasts"])
        self.assertTrue(SOURCE_POLICY["rs"]["observations"])
        self.assertTrue(SOURCE_POLICY["rs"]["forecasts"])
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
        self.assertEqual(len(ids), 102)
        self.assertTrue({row["station_id"] for row in observations + forecasts + latest} <= ids)
        self.assertEqual(len(features), 94)
        self.assertEqual(len(unmapped), 0)
        self.assertEqual(sum(feature["properties"]["is_exact_station_location"] for feature in features), 57)
        self.assertEqual(sum(not feature["properties"]["is_exact_station_location"] for feature in features), 37)
        self.assertFalse(any(row["country_code"] == "HR" for row in latest))
        self.assertFalse(any(row["source_id"] == "appd_bg" for row in forecasts))
        rs_stations = [row for row in stations if row["country_code"] == "RS"]
        rs_observations = [row for row in observations if row["country_code"] == "RS"]
        rs_forecasts = [row for row in forecasts if row["country_code"] == "RS"]
        self.assertEqual(len(rs_stations), 13)
        if rs_observations:
            self.assertEqual(12, len({row["source_stream_id"] for row in rs_observations if row["source_stream_type"] == "nrt"}))
            self.assertEqual(13, len({row["station_id"] for row in rs_observations if row["source_stream_type"] == "daily"}))
            self.assertTrue(rs_forecasts)
            self.assertTrue(all(row["canonical_quality_flag"] == "provisional" for row in rs_observations if row["source_stream_type"] == "nrt"))
        else:
            self.assertFalse(rs_forecasts)
        self.assertFalse(any(row["canonical_quality_flag"] == "suspect" for row in observations))
        high = [row for row in observations if row["country_code"] == "SK" and row["parameter"] == "water_temperature" and float(row["value"]) > 45]
        self.assertTrue(high)
        self.assertTrue(all(row["canonical_quality_flag"] == "provisional" and row["current_usable"] for row in high))
        legacy = [row for row in issues if row.get("quality_origin") == "legacy_application_rule"]
        self.assertTrue(any(row.get("observation", {}).get("value") == 46.2 for row in legacy))
        self.assertTrue(all(row.get("historical") and row.get("active") is False for row in legacy))
        self.assertTrue(all(row.get("source_url") and row.get("source_file_sha256") and row.get("captured_at_utc") for row in observations))

    def test_sk_medvedov_station_5145_is_published_with_valid_coordinates(self):
        # SHMU added a 14th Dunaj-tagged station (source_station_id "5145",
        # "Medveďov - Dunaj") some time before 2026-08-06; confirmed live and not
        # a rename/duplicate of any existing SK station (see P2 investigation).
        stations = load_json(PUBLIC_ROOT / "stations.json")
        medvedov = next((row for row in stations if row["station_id"] == "sk-5145"), None)
        self.assertIsNotNone(medvedov, "sk-5145 (Medveďov) missing from published stations.json")
        self.assertEqual(medvedov["country_code"], "SK")
        self.assertEqual(medvedov["source_station_id"], "5145")
        self.assertIsNotNone(medvedov["latitude"])
        self.assertIsNotNone(medvedov["longitude"])
        self.assertTrue(-90 <= medvedov["latitude"] <= 90)
        self.assertTrue(-180 <= medvedov["longitude"] <= 180)
        features = load_json(PUBLIC_ROOT / "stations.geojson")["features"]
        self.assertTrue(any(f["properties"]["station_id"] == "sk-5145" for f in features))
        self.assertEqual(EXPECTED_COUNTS["sk"], 14)

    def test_stream_rows_do_not_duplicate_when_stream_id_format_changed(self):
        # The station's own (fresh) source_stream_id is the new "5127:observed"
        # format; an already-published observation still under the old bare
        # "5127" label must not be treated as a second, secondary stream.
        station = {
            "station_id": "sk-5127", "physical_station_id": "sk-5127", "source_stream_id": "5127:observed",
            "source_stream_type": "observed", "is_primary_stream": True, "observation_frequency": None,
            "country_code": "SK", "source_id": "shmu_sk",
        }
        old_format_observation = {
            "station_id": "sk-5127", "source_stream_id": "5127", "source_stream_type": "observed",
        }
        rows = _stream_rows([station], [old_format_observation], [])
        self.assertEqual(len(rows), 1)

    def test_enrich_observation_canonicalizes_stale_primary_stream_id(self):
        station = {
            "country_code": "SK", "station_name": "Devin", "station_name_local": "Devín",
            "physical_station_id": "sk-5127", "source_stream_id": "5127:observed",
            "source_stream_type": "observed", "is_primary_stream": True,
        }
        policy = {"source_id": "shmu_sk", "status": "partial", "current": True}
        stale_row = {"source_stream_id": "5127", "source_stream_type": "observed", "source_file_sha256": ""}
        result = enrich_observation(stale_row, station, policy, {})
        self.assertEqual(result["source_stream_id"], "5127:observed")

    def test_enrich_observation_keeps_a_genuinely_different_secondary_stream_id(self):
        station = {
            "country_code": "RS", "station_name": "Bezdan", "station_name_local": "Bezdan",
            "physical_station_id": "rs-42010", "source_stream_id": "42010:daily",
            "source_stream_type": "daily", "is_primary_stream": True,
        }
        policy = {"source_id": "hidmet_rs", "status": "complete", "current": True}
        nrt_row = {"source_stream_id": "42010:nrt", "source_stream_type": "nrt", "source_file_sha256": ""}
        result = enrich_observation(nrt_row, station, policy, {})
        self.assertEqual(result["source_stream_id"], "42010:nrt")

    def test_stream_rows_still_separates_distinct_stream_types(self):
        station = {
            "station_id": "rs-42010", "physical_station_id": "rs-42010", "source_stream_id": "42010:daily",
            "source_stream_type": "daily", "is_primary_stream": True, "observation_frequency": None,
            "country_code": "RS", "source_id": "hidmet_rs",
        }
        nrt_observation = {
            "station_id": "rs-42010", "source_stream_id": "42010:nrt", "source_stream_type": "nrt",
        }
        rows = _stream_rows([station], [nrt_observation], [])
        self.assertEqual(len(rows), 2)

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
            self.assertEqual(status["station_count"], 102)
            self.assertEqual(set(path.name for path in output.iterdir()), set(FILES))
            self.assertTrue(validate(output, mirror)["ok"])
            output_text = "\n".join((output / name).read_text(encoding="utf-8") for name in FILES)
            self.assertNotIn("viadonau_partner_key=", output_text.casefold())


if __name__ == "__main__":
    unittest.main()
