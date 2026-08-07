from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.update_international_data import (
    ALL_SOURCES,
    OPERATIONAL_POLICY,
    SCHEDULED_SOURCES,
    acceptable,
    archive_details,
    dedupe,
    main,
    next_scheduled,
    normalized_source_date,
    raw_candidate,
    replace_candidate,
    selected_sources,
    update_state,
)
from scripts.validate_international_public_data import observation_identity


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "public" / "international"
STATE = ROOT / "data" / "reference" / "international_source_operations.json"


def load_public(name: str):
    return json.loads((PUBLIC / name).read_text(encoding="utf-8"))


def operation_state(code: str) -> dict:
    policy = OPERATIONAL_POLICY[code]
    return {
        "contract_version": "1.3-beta",
        "sources": {
            code: {
                **policy,
                "source_status": "suspended" if code in {"hr", "rs"} else "partial",
                "last_attempt_at": "2026-08-01T00:00:00+00:00",
                "last_attempt_status": "success",
                "last_success_at": "2026-08-01T00:00:00+00:00",
                "last_success_capture_at": "2026-08-01T00:00:00+00:00",
                "last_capture_at": "2026-08-01T00:00:00+00:00",
                "last_success_commit": "abc123",
                "last_error_code": None,
                "last_error_message": None,
                "last_error": None,
                "consecutive_failures": 0,
                "published_snapshot_date": "2026-08-01",
                "next_expected_update": None,
                "update_frequency": "daily at 01:37 UTC",
            }
        },
    }


class InternationalAutomationTests(unittest.TestCase):
    def test_schedule_selection_excludes_manual_at_and_disabled_rs(self):
        self.assertEqual(SCHEDULED_SOURCES, ("de", "sk", "hu", "hr"))
        self.assertEqual(selected_sources("scheduled"), list(SCHEDULED_SOURCES))
        self.assertEqual(selected_sources("all"), list(ALL_SOURCES))
        self.assertNotIn("at", SCHEDULED_SOURCES)
        self.assertNotIn("rs", SCHEDULED_SOURCES)

    def test_next_schedule_uses_dst_safe_bg_windows(self):
        summer = datetime(2026, 8, 5, 15, 10, tzinfo=timezone.utc)
        winter = datetime(2026, 1, 5, 7, 0, tzinfo=timezone.utc)
        self.assertEqual(next_scheduled("bg", summer), "2026-08-05T18:15:00+00:00")
        self.assertEqual(next_scheduled("bg", winter), "2026-01-05T07:15:00+00:00")
        self.assertEqual(next_scheduled("de", summer), "2026-08-06T01:37:00+00:00")
        self.assertEqual(next_scheduled("rs", summer), "2026-08-05T15:17:00+00:00")
    def test_operational_policy_keeps_dimensions_separate(self):
        self.assertEqual(OPERATIONAL_POLICY["at"]["automation_status"], "manual")
        self.assertEqual(OPERATIONAL_POLICY["rs"]["automation_status"], "scheduled")
        self.assertEqual(OPERATIONAL_POLICY["hr"]["freshness_status"], "stale")
        self.assertEqual(OPERATIONAL_POLICY["de"]["validation_status"], "source_validated")

    def test_rs_component_state_is_fail_soft_and_records_transport(self):
        state = operation_state("rs")
        now = datetime(2026, 8, 6, 9, 0, tzinfo=timezone.utc)
        details = {"last_capture_at": now.isoformat(), "transport": "curl.exe/Schannel", "runner": "Windows", "request_made": True, "component_last_source_observation_at": {"nrt": "2026-08-06", "daily": "2026-08-05", "forecast": "2026-08-06"}}
        update_state(state, "rs", now, {"status": "complete"}, True, None, details, "2026-08-06", "base", "nrt")
        nrt = state["sources"]["rs"]["components"]["nrt"]
        self.assertEqual((nrt["last_attempt_status"], nrt["transport"], nrt["runner"], nrt["request_made"]), ("success", "curl.exe/Schannel", "Windows", True))
        self.assertEqual("2026-08-06", nrt["last_source_observation_at"])
        self.assertEqual("every 3 hours plus daily/forecast Europe/Belgrade gates", state["sources"]["rs"]["update_frequency"])
        update_state(state, "rs", now, {"status": "failed", "error_type": "SourceAccessError"}, False, "forecast unavailable", details, None, "base", "forecast")
        components = state["sources"]["rs"]["components"]
        self.assertEqual("success", components["nrt"]["last_attempt_status"])
        self.assertEqual("failed", components["forecast"]["last_attempt_status"])
        self.assertEqual(1, components["forecast"]["consecutive_failures"])

    def test_rs_source_dates_are_normalized_without_inventing_time(self):
        self.assertEqual("2026-08-06", normalized_source_date("06.08.2026; first alert=500 cm"))
        self.assertEqual("2026-08-06", normalized_source_date("2026-08-06T06:00:00+00:00"))
        self.assertIsNone(normalized_source_date("unknown"))

    def test_public_refresh_preserves_stream_provenance(self):
        public_row = {
            "station_id": "rs-42010", "country_code": "RS", "station_name": "Bezdan",
            "source_id": "rhmz_rs", "source_status": "complete", "current_usable": True,
            "physical_station_id": "rs-42010", "source_stream_id": "42010:daily",
            "source_stream_type": "daily", "is_primary_stream": False,
            "parameter": "water_level", "canonical_quality_flag": "observed",
        }
        candidate = raw_candidate(public_row)
        self.assertNotIn("country_code", candidate)
        self.assertNotIn("station_name", candidate)
        self.assertEqual("rs-42010", candidate["physical_station_id"])
        self.assertEqual("42010:daily", candidate["source_stream_id"])
        self.assertEqual("daily", candidate["source_stream_type"])
        self.assertFalse(candidate["is_primary_stream"])

    def test_failed_attempt_preserves_last_known_good(self):
        state = operation_state("de")
        previous = dict(state["sources"]["de"])
        update_state(
            state, "de", datetime(2026, 8, 5, tzinfo=timezone.utc),
            {"status": "failed", "error_type": "SourceAccessError"}, False,
            "HTTP 503", {"last_capture_at": None}, None, "new-base",
        )
        current = state["sources"]["de"]
        for key in ("last_success_at", "last_success_capture_at", "last_capture_at", "last_success_commit", "published_snapshot_date"):
            self.assertEqual(current[key], previous[key])
        self.assertEqual(current["last_attempt_status"], "failed")
        self.assertEqual(current["validation_status"], "technical_validation_failed")
        self.assertEqual(current["consecutive_failures"], 1)
        self.assertEqual(current["last_error_code"], "SourceAccessError")

    def test_hr_stale_then_recovers_without_erasing_history(self):
        state = operation_state("hr")
        now = datetime(2026, 8, 5, tzinfo=timezone.utc)
        update_state(state, "hr", now, {"status": "suspended"}, True, None,
                     {"last_capture_at": now.isoformat()}, "2025-06-01", "base")
        item = state["sources"]["hr"]
        self.assertEqual((item["source_status"], item["freshness_status"], item["last_attempt_status"]),
                         ("partial", "stale", "stale"))
        update_state(state, "hr", now, {"status": "complete"}, True, None,
                     {"last_capture_at": now.isoformat()}, "2026-08-05", "base")
        item = state["sources"]["hr"]
        self.assertEqual((item["source_status"], item["freshness_status"], item["last_attempt_status"]),
                         ("partial", "current", "partial"))
        self.assertEqual(item["published_snapshot_date"], "2026-08-05")

    def test_sk_suspect_warning_does_not_block_source(self):
        accepted, error = acceptable(
            "sk", {"status": "partial", "station_count": 14, "observation_count": 26},
            [{"severity": "warning", "code": "outside_plausible_water_temperature_range"}],
        )
        self.assertTrue(accepted)
        self.assertIsNone(error)

    def test_unexpected_station_addition_is_fail_soft(self):
        # EXPECTED_COUNTS["sk"] is 14 (SHMU added station 5145/Medvedov in
        # August 2026, confirmed legitimate and integrated); a further,
        # still-unexpected addition must still be rejected fail-soft.
        accepted, error = acceptable(
            "sk", {"status": "complete", "station_count": 15, "observation_count": 27}, [],
        )
        self.assertFalse(accepted)
        self.assertEqual(error, "unexpected station count: expected 14, got 15")

    def test_dedupe_treats_old_and_new_stream_id_format_as_the_same_stream(self):
        # SHMU's adapter code once emitted bare source_stream_id values ("5127")
        # and now emits "5127:observed"; SK's already-published observations
        # still carry the bare form. A source_stream_id format change must not
        # make dedupe() treat the same underlying reading as two streams.
        old_format = {
            "station_id": "sk-5127", "source_stream_id": "5127", "source_stream_type": "observed",
            "parameter": "water_level", "source_observation_date": "2026-08-07", "value": 205,
        }
        new_format = {
            "station_id": "sk-5127", "source_stream_id": "5127:observed", "source_stream_type": "observed",
            "parameter": "water_level", "source_observation_date": "2026-08-07", "value": 206,
        }
        merged = dedupe([old_format, new_format], "observations")
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["value"], 206)  # the later (new-format) row wins

    def test_dedupe_still_keeps_distinct_stream_types_for_the_same_station(self):
        # RS reports daily and nrt as genuinely different streams for the same
        # station_id; a fix for the SK format drift must not merge these.
        daily = {
            "station_id": "rs-42010", "source_stream_id": "42010:daily", "source_stream_type": "daily",
            "parameter": "water_level", "source_observation_date": "2026-08-07", "value": 100,
        }
        nrt = {
            "station_id": "rs-42010", "source_stream_id": "42010:nrt", "source_stream_type": "nrt",
            "parameter": "water_level", "source_observation_date": "2026-08-07", "value": 101,
        }
        merged = dedupe([daily, nrt], "observations")
        self.assertEqual(len(merged), 2)

    def test_empty_observation_set_cannot_replace_lkg(self):
        accepted, error = acceptable("de", {"status": "complete", "station_count": 18, "observation_count": 0}, [])
        self.assertFalse(accepted)
        self.assertEqual(error, "empty observation set")

    def test_bg_candidate_never_publishes_forecasts_or_invents_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            incoming = root / "incoming"
            incoming.mkdir()
            station = {"station_id": "bg-example", "source_station_id": None, "station_name": "Example"}
            (incoming / "stations.json").write_text(json.dumps([station]), encoding="utf-8")
            (incoming / "observations.json").write_text("[]", encoding="utf-8")
            (incoming / "forecasts.json").write_text(json.dumps([{"station_id": "bg-example", "forecast_value": 1}]), encoding="utf-8")
            (incoming / "issues.json").write_text("[]", encoding="utf-8")
            replace_candidate(candidate, "bg", incoming, {"observations": [], "forecasts": [], "issues": []})
            stations = json.loads((candidate / "bg" / "stations.json").read_text(encoding="utf-8"))
            forecasts = json.loads((candidate / "bg" / "forecasts.json").read_text(encoding="utf-8"))
            self.assertIsNone(stations[0]["source_station_id"])
            self.assertEqual(forecasts, [])

    def test_resolved_suspect_issue_is_preserved_as_historical_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incoming = root / "incoming"
            incoming.mkdir()
            station = {"station_id": "sk-6860", "source_station_id": "6860"}
            for name, rows in (
                ("stations.json", [station]), ("observations.json", []),
                ("forecasts.json", []), ("issues.json", []),
            ):
                (incoming / name).write_text(json.dumps(rows), encoding="utf-8")
            observation = {
                "station_id": "sk-6860", "parameter": "water_temperature", "value": 45.3,
                "unit": "degC", "measurement_datetime_utc": "2026-08-04T16:30:00+00:00",
                "source_file_sha256": "a" * 64, "canonical_quality_flag": "suspect",
            }
            issue = {
                "code": "outside_plausible_water_temperature_range", "record_id": "sk-6860",
                "historical": True, "active": False, "quality_origin": "legacy_application_rule", "observation": observation,
            }
            replace_candidate(root / "candidate", "sk", incoming,
                              {"observations": [], "forecasts": [], "issues": [issue]})
            stored = json.loads((root / "candidate" / "sk" / "issues.json").read_text(encoding="utf-8"))
            self.assertEqual(len(stored), 1)
            self.assertTrue(stored[0]["historical"])
            self.assertEqual(observation_identity(stored[0]["observation"]), observation_identity(observation))

    def test_http_failure_metadata_is_reported_from_raw_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "archive" / "pegelonline_de" / "2026" / "08"
            archive.mkdir(parents=True)
            metadata = {
                "captured_at_utc": "2026-08-05T01:37:00+00:00", "http_status": 503,
                "content_type": "text/html", "content_sha256": "a" * 64,
            }
            (archive / "failure.metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            details = archive_details(root / "result", root / "archive", "pegelonline_de")
            self.assertEqual(details["payload_count"], 1)
            self.assertEqual(details["http_statuses"], [503])
            self.assertEqual(details["content_types"], ["text/html"])

    def test_rs_path_makes_standard_adapter_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state_path = root / "state.json"
            previous = {"rs": {"stations": [], "observations": [], "forecasts": [], "issues": []}}
            adapter_summary = {
                "source": "rs", "adapter": "hidmet_rs", "status": "complete", "publishable": True,
                "station_count": 13, "observation_count": 100, "forecast_count": 36,
                "output": str(root / "output" / "results" / "rs"),
            }
            with patch("scripts.update_international_data.materialize_candidates", return_value=previous), \
                 patch("scripts.update_international_data.run_source", return_value=adapter_summary) as run_source, \
                 patch("scripts.update_international_data.replace_candidate") as replace_candidate, \
                 patch("scripts.update_international_data.build", return_value={"station_count": 101}), \
                 patch("scripts.update_international_data.validate", return_value={"ok": True}), \
                 contextlib.redirect_stdout(io.StringIO()):
                result = main([
                    "--source", "rs", "--mode", "live", "--action", "dry-run",
                    "--output-dir", str(root / "output"), "--public-root", str(root / "public"),
                    "--mirror-root", str(root / "mirror"), "--operations-state", str(state_path),
                ])
            self.assertEqual(result, 0)
            run_source.assert_called_once()
            self.assertEqual(run_source.call_args.args[-2:], ("all", 7))
            replace_candidate.assert_called_once()
            summary = json.loads((root / "output" / "update-summary.json").read_text(encoding="utf-8"))
            rs = summary["sources"][0]
            self.assertTrue(rs["request_made"])
            self.assertEqual(rs["collection_profile"], "all")

    def test_unexpected_adapter_failure_is_isolated_and_keeps_lkg(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            previous = {"de": {"stations": [], "observations": [], "forecasts": [], "issues": []}}
            with patch("scripts.update_international_data.materialize_candidates", return_value=previous), \
                 patch("scripts.update_international_data.run_source", side_effect=RuntimeError("parser defect")), \
                 patch("scripts.update_international_data.replace_candidate") as replace, \
                 patch("scripts.update_international_data.build", return_value={}), \
                 patch("scripts.update_international_data.validate", return_value={"ok": True}), \
                 contextlib.redirect_stdout(io.StringIO()):
                result = main([
                    "--source", "de", "--mode", "live", "--action", "dry-run",
                    "--output-dir", str(output), "--public-root", str(root / "public"),
                    "--mirror-root", str(root / "mirror"), "--operations-state", str(root / "state.json"),
                ])
            self.assertEqual(result, 0)
            replace.assert_not_called()
            summary = json.loads((output / "update-summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["sources"][0]["publication_status"], "last-known-good")
            self.assertEqual(summary["sources"][0]["blocker"], "parser defect")

    def test_public_contract_has_operational_metadata_for_every_source(self):
        required = {
            "implementation_status", "source_status", "access_status", "automation_status", "freshness_status", "validation_status", "coordinate_status",
            "last_attempt_at", "last_success_at", "last_successful_fetch_at", "last_capture_at", "last_source_observation_at", "last_known_good_commit", "next_expected_update",
            "update_frequency", "validation_message_ro", "validation_message_en", "last_error",
            "consecutive_failures",
        }
        sources = load_public("sources.json")
        self.assertEqual({row["country_code"] for row in sources}, {code.upper() for code in ALL_SOURCES})
        for source in sources:
            self.assertEqual(required - source.keys(), set())
            self.assertNotIn("status", source)

    def test_current_public_quality_and_date_only_rules(self):
        observations = load_public("observations.json")
        latest = load_public("latest.json")
        high_temperatures = [row for row in observations if row["country_code"] == "SK" and row["parameter"] == "water_temperature" and float(row["value"]) > 45]
        self.assertTrue(high_temperatures)
        self.assertTrue(all(row["canonical_quality_flag"] == "provisional" and row["current_usable"] for row in high_temperatures))
        self.assertFalse(any(row["canonical_quality_flag"] == "suspect" for row in observations + latest))
        hu = [row for row in observations if row["country_code"] == "HU"]
        self.assertTrue(hu)
        self.assertTrue(all(row.get("measurement_date") and not row.get("measurement_datetime_utc") for row in hu))

    def test_suspect_record_identity_does_not_exclude_later_valid_value_for_series(self):
        suspect = {
            "station_id": "sk-6860", "parameter": "water_temperature", "value": 45.3,
            "unit": "degC", "measurement_datetime_utc": "2026-08-04T16:30:00+00:00",
            "source_file_sha256": "a" * 64,
        }
        later_valid = {
            **suspect, "value": 42.3,
            "measurement_datetime_utc": "2026-08-05T09:00:00+00:00",
            "source_file_sha256": "b" * 64,
        }
        self.assertEqual((suspect["station_id"], suspect["parameter"]),
                         (later_valid["station_id"], later_valid["parameter"]))
        self.assertNotEqual(observation_identity(suspect), observation_identity(later_valid))
        self.assertEqual(observation_identity(suspect), observation_identity(dict(suspect)))

    def test_versioned_operation_state_contains_last_known_good_fields(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        required = {
            "last_attempt_at", "last_attempt_status", "last_success_at", "last_success_capture_at",
            "last_capture_at", "last_success_commit", "last_known_good_commit", "last_source_observation_at", "last_error_code", "last_error_message",
            "consecutive_failures", "published_snapshot_date",
        }
        self.assertEqual(set(state["sources"]), set(ALL_SOURCES))
        for source in state["sources"].values():
            self.assertEqual(required - source.keys(), set())


if __name__ == "__main__":
    unittest.main()
