import json
import unittest
from collections import Counter
from pathlib import Path

from scripts.ingest_danube_sources import load_fixture_payloads
from scripts.sources import get_adapter
from scripts.sources.base import parse_optional_float
from scripts.sources.reference import ris_rows


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "international"
PUBLIC = ROOT / "data" / "public" / "international"


def public_json(name):
    return json.loads((PUBLIC / name).read_text(encoding="utf-8"))


class InternationalConsolidationV2Tests(unittest.TestCase):
    def test_value_policy_keeps_negative_and_missing_distinct(self):
        result = get_adapter("bg").parse(load_fixture_payloads(FIXTURES / "bg"))
        negative = next(row for row in result.observations if row.value == -60.0)
        self.assertEqual("-60.0", negative.source_value_raw)
        self.assertEqual("observed", negative.canonical_quality_flag)
        self.assertIsNone(parse_optional_float("x"))
        self.assertIsNone(parse_optional_float(""))

    def test_kachlet_is_one_physical_location_with_official_identity(self):
        stations = [row for row in public_json("stations.json") if "KACHLET" in row["station_name"]]
        self.assertEqual(2, len(stations))
        self.assertEqual(1, len({row["physical_station_id"] for row in stations}))
        canonical = next(row for row in stations if row["measuring_point_uid"] == row["source_station_id"])
        self.assertEqual("10090708", canonical["official_station_number"])
        self.assertEqual(2230.3, canonical["river_km"])
        self.assertEqual(289.98, canonical["pnp_value_m"])
        self.assertEqual("EPSG:25832", canonical["source_crs"])
        self.assertEqual(["KACHLET WEHR UP", "KACHLET LOCK UP"], canonical["aliases"])
        features = [row for row in public_json("stations.geojson")["features"] if row["properties"]["physical_station_id"] == canonical["physical_station_id"]]
        self.assertEqual(1, len(features))
        self.assertEqual(2, features[0]["properties"]["stream_count"])

    def test_manual_coordinate_overrides_are_exact_not_official(self):
        stations = {row["station_id"]: row for row in public_json("stations.json")}
        expected = {
            "sk-5128": (48.16942482732829, 16.984682498131868),
            "hu-442708": (47.969843702830005, 17.364096053534677),
            "hu-442532": (47.46083962001721, 19.0672091142404),
        }
        for station_id, coordinates in expected.items():
            row = stations[station_id]
            self.assertEqual("manually_verified_station_coordinate", row["coordinate_method"])
            self.assertTrue(row["is_exact_station_location"])
            self.assertAlmostEqual(coordinates[0], row["latitude"])
            self.assertAlmostEqual(coordinates[1], row["longitude"])

    def test_hungary_fixture_has_three_dayparts_without_invented_time(self):
        result = get_adapter("hu").parse(load_fixture_payloads(FIXTURES / "hu"))
        rows = [row for row in result.observations if row.station_id == "hu-4000" and row.parameter == "water_level"]
        self.assertEqual(["morning", "evening", "morning"], [row.observation_daypart for row in rows])
        self.assertEqual(3, len({(row.source_observation_date, row.observation_daypart) for row in rows}))
        self.assertTrue(all(row.measurement_datetime_utc is None and row.measurement_datetime_local is None for row in rows))
        self.assertTrue(all(row.observation_time_precision == "daypart" for row in rows))

    def test_ris_registry_has_all_official_hr_and_bg_streams(self):
        rows = ris_rows()
        self.assertEqual({"HR": 3, "BG": 20}, dict(Counter(row["country_code"] for row in rows)))
        hr = {row["station_id"]: row for row in rows if row["country_code"] == "HR"}
        self.assertEqual("HRALJ00001G000413803", hr["hr-5001"]["isrs_location_code"])
        self.assertEqual("HRBAT00001G000514246", hr["hr-5170"]["isrs_location_code"])
        self.assertEqual("HRVUK00001G000213334", hr["hr-5070"]["isrs_location_code"])
        self.assertTrue(all(row["workbook_sha256"] and row["workbook_sheet"] == "RIS Index" for row in rows))

    def test_bulgaria_has_twenty_streams_thirteen_locations_no_public_forecast(self):
        stations = [row for row in public_json("stations.json") if row["country_code"] == "BG"]
        self.assertEqual(20, len(stations))
        self.assertEqual(13, len({row["physical_station_id"] for row in stations}))
        self.assertEqual({"manual", "automatic"}, {row["source_stream_type"] for row in stations})
        self.assertTrue(all(row["coordinate_method"] == "official_station_coordinate" for row in stations))
        self.assertFalse(any(row["country_code"] == "BG" for row in public_json("forecasts.json")))
        nikopol = [row for row in stations if row["station_name"] == "Nikopol"]
        self.assertEqual(1, len({row["source_station_id"] for row in nikopol}))

    def test_serbia_fixture_combines_daily_nrt_and_demonstrated_forecasts(self):
        result = get_adapter("rs").parse(load_fixture_payloads(FIXTURES / "rs"))
        self.assertEqual((13, 75, 32), (len(result.stations), len(result.observations), len(result.forecasts)))
        self.assertEqual(12, sum(row.source_stream_type == "nrt" for row in result.stations))
        station_rows = [row for row in result.observations if row.station_id == "rs-42010"]
        self.assertEqual({"daily", "nrt"}, {row.source_stream_type for row in station_rows})
        self.assertTrue(any(row.measurement_datetime_utc and row.source_observation_time_raw for row in station_rows))
        self.assertTrue(all(row.forecast_parameter and row.forecast_unit for row in result.forecasts))

    def test_public_operational_contract_has_independent_dimensions(self):
        required = {
            "access_status", "source_status", "automation_status", "freshness_status", "validation_status",
            "coordinate_status", "last_attempt_at", "last_success_at", "last_capture_at",
            "last_source_observation_at", "next_expected_update", "update_frequency",
            "source_observation_frequency", "consecutive_failures", "last_error", "last_known_good_at",
            "validation_message_ro", "validation_message_en", "data_policy_ro", "data_policy_en",
        }
        sources = public_json("sources.json")
        self.assertEqual(7, len(sources))
        self.assertTrue(all(required <= row.keys() for row in sources))
        hr = next(row for row in sources if row["country_code"] == "HR")
        self.assertEqual(("available", "scheduled", "stale", "partial"), (hr["access_status"], hr["automation_status"], hr["freshness_status"], hr["source_status"]))
        rs = next(row for row in sources if row["country_code"] == "RS")
        self.assertEqual(("tls_failed", "disabled", "unavailable", "technical_validation_failed"), (rs["access_status"], rs["automation_status"], rs["freshness_status"], rs["validation_status"]))


if __name__ == "__main__":
    unittest.main()
