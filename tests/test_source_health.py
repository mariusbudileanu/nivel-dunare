from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.check_source_health import (
    CHRONIC_AFTER_DAYS,
    GhIssue,
    evaluate_sources,
    main,
    render_issue,
    stale_after_days_by_code,
    sync_issue,
)


def source(country_code, last_source_observation_at, **overrides):
    row = {
        "country_code": country_code, "label": overrides.pop("label", f"Label-{country_code}"),
        "last_source_observation_at": last_source_observation_at,
        "consecutive_failures": 0, "last_error_message": None,
    }
    row.update(overrides)
    return row


class FakeIssueClient:
    """In-memory stand-in for GhCliClient - no real GitHub calls are ever made."""

    def __init__(self):
        self.issues: dict[int, GhIssue] = {}
        self.next_number = 1
        self.create_calls = 0
        self.update_calls = 0
        self.close_calls = 0
        self.closed_numbers: list[int] = []

    def find_open(self, label):
        if not self.issues:
            return None
        return next(iter(self.issues.values()))

    def create(self, label, title, body):
        self.create_calls += 1
        issue = GhIssue(number=self.next_number, title=title, body=body)
        self.issues[issue.number] = issue
        self.next_number += 1
        return issue

    def update_body(self, number, body):
        self.update_calls += 1
        self.issues[number].body = body

    def close(self, number, comment):
        self.close_calls += 1
        self.closed_numbers.append(number)
        del self.issues[number]


class EvaluateSourcesTests(unittest.TestCase):
    def test_all_sources_healthy_produces_no_problems(self):
        today = date(2026, 8, 8)
        sources = [
            source("DE", "2026-08-07"), source("AT", "2026-08-07"), source("SK", "2026-08-06"),
            source("HU", "2026-08-06"), source("BG", "2026-08-06"), source("RS", "2026-08-07"),
            source("HR", "2026-08-02"),  # HR's own threshold is 7 days, so 6 days old is fine
        ]
        self.assertEqual(evaluate_sources(sources, today), [])

    def test_one_source_crosses_its_own_threshold(self):
        today = date(2026, 8, 8)
        sources = [source("DE", "2026-08-07"), source("SK", "2026-08-04")]  # SK: 4 days, threshold 2
        problems = evaluate_sources(sources, today)
        self.assertEqual(["sk"], [p.code for p in problems])
        self.assertEqual(4, problems[0].age_days)
        self.assertEqual("recent", problems[0].tier)

    def test_chronic_tier_starts_past_the_uniform_threshold(self):
        today = date(2026, 8, 8)
        just_under = today.toordinal() - CHRONIC_AFTER_DAYS
        just_over = just_under - 2
        sources = [
            source("HR", date.fromordinal(just_under).isoformat()),
            source("BG", date.fromordinal(just_over).isoformat()),
        ]
        problems = {p.code: p for p in evaluate_sources(sources, today)}
        self.assertEqual("recent", problems["hr"].tier)
        self.assertEqual("chronic", problems["bg"].tier)

    def test_thresholds_come_from_each_adapter_not_invented(self):
        thresholds = stale_after_days_by_code()
        self.assertEqual(thresholds["hr"], 7)
        for code in ("de", "at", "sk", "hu", "bg", "rs"):
            self.assertEqual(thresholds[code], 2)

    def test_ro_afdj_is_never_evaluated(self):
        today = date(2026, 8, 8)
        sources = [source("RO", "2020-01-01")]
        self.assertEqual(evaluate_sources(sources, today), [])


class RenderIssueTests(unittest.TestCase):
    def test_no_problems_renders_empty_body(self):
        title, body = render_issue([], date(2026, 8, 8))
        self.assertEqual(title, "Surse internaționale cu probleme de livrare")
        self.assertEqual(body, "")

    def test_two_simultaneous_problems_both_appear_in_one_body(self):
        today = date(2026, 8, 8)
        sources = [source("SK", "2026-08-04"), source("BG", "2026-08-03", label="APPD")]
        problems = evaluate_sources(sources, today)
        title, body = render_issue(problems, today)
        self.assertIn("Label-SK", body)
        self.assertIn("APPD", body)
        self.assertEqual(1, body.count("## Stale recent"))

    def test_failure_context_is_included_when_present(self):
        today = date(2026, 8, 8)
        sources = [source("RS", "2026-08-01", consecutive_failures=14, last_error_message="ZoneInfoNotFoundError")]
        _, body = render_issue(evaluate_sources(sources, today), today)
        self.assertIn("14 încercări", body)
        self.assertIn("ZoneInfoNotFoundError", body)


class SyncIssueTests(unittest.TestCase):
    def test_all_healthy_creates_nothing(self):
        client = FakeIssueClient()
        action = sync_issue(client, "source-health", "t", "", has_problems=False)
        self.assertEqual("noop", action)
        self.assertEqual(0, client.create_calls)

    def test_one_source_over_threshold_creates_exactly_one_issue(self):
        client = FakeIssueClient()
        action = sync_issue(client, "source-health", "t", "body v1", has_problems=True)
        self.assertEqual("created", action)
        self.assertEqual(1, client.create_calls)
        self.assertEqual(1, len(client.issues))

    def test_same_source_still_stale_next_day_updates_in_place_not_duplicated(self):
        client = FakeIssueClient()
        sync_issue(client, "source-health", "t", "body day 1", has_problems=True)
        action = sync_issue(client, "source-health", "t", "body day 2 (older)", has_problems=True)
        self.assertEqual("updated", action)
        self.assertEqual(1, client.create_calls, "must never create a second issue")
        self.assertEqual(1, client.update_calls)
        self.assertEqual(1, len(client.issues))
        self.assertEqual("body day 2 (older)", next(iter(client.issues.values())).body)

    def test_identical_body_two_days_running_does_not_call_update(self):
        client = FakeIssueClient()
        sync_issue(client, "source-health", "t", "same body", has_problems=True)
        action = sync_issue(client, "source-health", "t", "same body", has_problems=True)
        self.assertEqual("unchanged", action)
        self.assertEqual(0, client.update_calls)

    def test_source_recovers_closes_the_issue(self):
        client = FakeIssueClient()
        sync_issue(client, "source-health", "t", "body", has_problems=True)
        action = sync_issue(client, "source-health", "t", "", has_problems=False)
        self.assertEqual("closed", action)
        self.assertEqual(1, client.close_calls)
        self.assertEqual(0, len(client.issues))

    def test_two_sources_fail_simultaneously_still_one_issue(self):
        today = date(2026, 8, 8)
        sources = [source("SK", "2026-08-04"), source("BG", "2026-08-03")]
        problems = evaluate_sources(sources, today)
        title, body = render_issue(problems, today)
        client = FakeIssueClient()
        sync_issue(client, "source-health", title, body, has_problems=bool(problems))
        self.assertEqual(1, client.create_calls)
        self.assertIn("sk".upper(), body.upper())
        self.assertIn("bg".upper(), body.upper())

    def test_reopening_after_recovery_creates_a_fresh_issue_not_reuses_closed_one(self):
        client = FakeIssueClient()
        sync_issue(client, "source-health", "t", "body", has_problems=True)
        sync_issue(client, "source-health", "t", "", has_problems=False)
        action = sync_issue(client, "source-health", "t", "body again", has_problems=True)
        self.assertEqual("created", action)
        self.assertEqual(2, client.create_calls)


class CroatiaRetroactiveTests(unittest.TestCase):
    def test_would_have_been_flagged_around_seven_days_not_148(self):
        # Real case: HR's last_source_observation_at was frozen at 2026-03-12
        # from that date onward (verified live in the P3 diagnostic). Walk
        # forward day by day and find the first day evaluate_sources would
        # have reported it.
        frozen_at = date(2026, 3, 12)
        first_flagged = None
        for offset in range(0, 200):
            today = date.fromordinal(frozen_at.toordinal() + offset)
            sources = [source("HR", frozen_at.isoformat())]
            if evaluate_sources(sources, today):
                first_flagged = offset
                break
        self.assertIsNotNone(first_flagged)
        self.assertEqual(8, first_flagged)  # HR threshold is 7 days -> flagged on day 8, age_days=8
        self.assertLess(first_flagged, 148)
        self.assertGreater(first_flagged, 5)


class MainTitleOverrideTests(unittest.TestCase):
    def test_dry_run_title_override_replaces_the_default_title_only(self):
        # A verification run must be able to use a title that unmistakably
        # marks it as a test, without the pure render_issue() logic (already
        # covered above) needing to know about that concern at all.
        with TemporaryDirectory() as folder:
            sources_path = Path(folder) / "sources.json"
            sources_path.write_text(json.dumps([source("HR", "2026-03-12")]), encoding="utf-8")
            captured = io.StringIO()
            with redirect_stdout(captured):
                exit_code = main([
                    "--sources", str(sources_path), "--dry-run", "--today", "2026-08-08",
                    "--title", "[TEST] source-health-monitor verification - safe to delete",
                ])
            self.assertEqual(0, exit_code)
            payload = json.loads(captured.getvalue())
            self.assertEqual("[TEST] source-health-monitor verification - safe to delete", payload["title"])
            self.assertIn("Label-HR", payload["body"])

    def test_dry_run_without_override_keeps_the_default_title(self):
        with TemporaryDirectory() as folder:
            sources_path = Path(folder) / "sources.json"
            sources_path.write_text(json.dumps([source("HR", "2026-03-12")]), encoding="utf-8")
            captured = io.StringIO()
            with redirect_stdout(captured):
                main(["--sources", str(sources_path), "--dry-run", "--today", "2026-08-08"])
            payload = json.loads(captured.getvalue())
            self.assertEqual("Surse internaționale cu probleme de livrare", payload["title"])


if __name__ == "__main__":
    unittest.main()
