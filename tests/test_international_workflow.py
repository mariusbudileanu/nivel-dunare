from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.update_international_data import SCHEDULED_SOURCES


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "update-international-data.yml"
BG_WORKFLOW = ROOT / ".github" / "workflows" / "update-bg-danube-streams.yml"
RS_WORKFLOW = ROOT / ".github" / "workflows" / "update-serbia-data.yml"


class InternationalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.rs_workflow = RS_WORKFLOW.read_text(encoding="utf-8")

    def test_cron_contains_only_scheduled_source_selector(self):
        self.assertIn('- cron: "37 1 * * *"', self.workflow)
        self.assertIn('source="scheduled"', self.workflow)
        # AT joined once DORIS_PARTNER_KEY held a real permanent key (P3); BG
        # joined once its dedicated 09:15/21:15 Europe/Sofia exact-minute gate
        # was retired for the shared unconditional daily fetch (P4) - both
        # streams come from the one appd-bg.org page regardless of time of
        # day. RS keeps its own dedicated windows workflow.
        self.assertEqual(SCHEDULED_SOURCES, ("de", "sk", "hu", "hr", "at", "bg"))
        self.assertIn("at", SCHEDULED_SOURCES)
        self.assertIn("bg", SCHEDULED_SOURCES)
        self.assertNotIn("rs", SCHEDULED_SOURCES)

    def test_three_daily_attempts_cover_bg_and_hu_publication_lag(self):
        # P3 collection-recovery (2026-08-11): confirmed live that a
        # single 01:37 UTC attempt lands before BG's own ~09:15
        # Europe/Sofia morning publication (3/3 real scheduled runs
        # failed the fail-closed station-count guard; the live page had
        # a full manual table once actually checked after 09:15) and
        # before HU's own daily cutoff (last_source_observation_at was
        # exactly one day behind the run's own date on 3/3 real runs).
        # Every event_name==schedule firing runs the identical
        # source=scheduled batch (see the resolve step), so later
        # attempts give BG/HU a second and third chance without any
        # per-source branching.
        for cron in ("37 1 * * *", "35 8 * * *", "35 12 * * *"):
            self.assertIn(f'- cron: "{cron}"', self.workflow)
        self.assertEqual(3, self.workflow.count("- cron:"), "only the scheduled-batch crons should exist in this file")

    def test_bg_dedicated_exact_minute_gate_workflow_was_retired(self):
        # P4: the 09:15/21:15 Europe/Sofia exact-minute gate was fragile
        # against GitHub Actions scheduling delays of an hour or more
        # (observed directly on this repo). BG is fetched by the same
        # unconditional shared daily attempts as DE/SK/HU/HR/AT now (three
        # of them since P3 collection-recovery), so a delayed run still
        # collects data - there is no time-match check left to miss.
        self.assertFalse(BG_WORKFLOW.exists(), "update-bg-danube-streams.yml should be removed, not left dormant")
        self.assertNotIn("TZ=Europe/Sofia", self.workflow)

    def test_rs_windows_handoff_schedules_and_write_boundary(self):
        for cron in (
            "17 */3 * * *", "47 0 * * *",
            "35 10 * * *", "35 12 * * *", "35 14 * * *",
            "20 12 * * *", "20 14 * * *", "20 16 * * *",
        ):
            self.assertIn(f'- cron: "{cron}"', self.rs_workflow)
        self.assertIn("runs-on: windows-latest", self.rs_workflow)
        self.assertIn("curl.exe --version", self.rs_workflow)
        self.assertIn("serbia-schannel-handoff", self.rs_workflow)
        self.assertIn("--precollected-root", self.rs_workflow)
        before_publish, publish = self.rs_workflow.split("\n  publish:\n", 1)
        self.assertNotIn("contents: write", before_publish)
        self.assertIn("contents: write", publish)
        self.assertNotIn("--force", self.rs_workflow)

    def test_write_permissions_exist_only_in_publish_job(self):
        before_publish, publish = self.workflow.split("\n  publish:\n", 1)
        self.assertNotIn("contents: write", before_publish)
        self.assertNotIn("actions: write", before_publish)
        self.assertIn("permissions:\n      contents: read", before_publish)
        self.assertIn("permissions:\n      contents: write\n      actions: write", publish)
        self.assertNotIn("pages: write", self.workflow)

    def test_publish_requires_validated_live_publish_artifact(self):
        self.assertIn("needs: collect-and-validate", self.workflow)
        self.assertIn("if: needs.collect-and-validate.outputs.should_publish == 'true'", self.workflow)
        self.assertIn('if [[ "$mode" == "live" && "$action" == "publish" ]]', self.workflow)
        self.assertIn('if [[ "$mode" == "fixtures" && "$action" == "publish" ]]', self.workflow)
        for command in (
            "scripts.validate_repository", "scripts.validate_international_public_data",
            "scripts.geocode_international_stations --validate-only", "scripts.smoke_test_site",
            "unittest discover -s tests -v",
        ):
            self.assertIn(command, self.workflow)

    def test_staging_is_strictly_whitelisted(self):
        self.assertNotIn("git add .", self.workflow)
        staging = self.workflow.split("git add --", 1)[1].split("if git diff --cached", 1)[0]
        self.assertIn("data/public/international", staging)
        self.assertIn("public/data/international", staging)
        self.assertIn("data/reference/international_source_operations.json", staging)
        for forbidden in ("data/canonical", "scripts/run_hetzner_update.sh", "artifacts/", "public/assets"):
            self.assertNotIn(forbidden, staging)

    def test_push_has_one_retry_and_never_forces_or_resets(self):
        self.assertEqual(self.workflow.count("git push origin HEAD:main"), 2)
        self.assertIn("git rebase origin/main", self.workflow)
        self.assertIn("git rebase --abort", self.workflow)
        self.assertNotIn("--force", self.workflow)
        self.assertNotIn("reset --hard", self.workflow)
        self.assertIn("git merge-base --is-ancestor", self.workflow)

    def test_pages_dispatch_is_guarded_by_commit_and_push(self):
        expected = "if: steps.commit.outputs.committed == 'true' && steps.push.outputs.pushed == 'true'"
        self.assertIn(expected, self.workflow)
        self.assertIn("gh workflow run deploy-pages.yml --ref main", self.workflow)
        self.assertIn("if git diff --cached --quiet", self.workflow)
        self.assertIn("No real whitelisted change; no commit and no Pages dispatch.", self.workflow)

    def test_artifact_security_and_retention(self):
        self.assertIn("retention-days: 30", self.workflow)
        self.assertIn("Scan product and artifact for secrets", self.workflow)

    def test_international_workflow_artifact_and_secret_scan_details(self):
        self.assertIn("Configured DoRIS secret found in persisted output", self.workflow)
        self.assertIn("path.unlink()", self.workflow)
        self.assertIn("raw, candidates, issues, logs and validated product", self.workflow)

    def test_rs_no_longer_gates_on_local_wall_clock_or_needs_tzdata(self):
        # Faza 3: the old design computed Europe/Belgrade local wall-clock
        # time and skipped a run whose local hour didn't match the target -
        # fragile against GitHub Actions scheduling delay (confirmed live:
        # every scheduled run failed on ZoneInfoNotFoundError before P1,
        # and the DST-pair hour-match itself was never actually exercised).
        # No code path in this file needs the IANA database any more - RS's
        # own adapter (hidmet_rs.py) labels its data with a fixed UTC
        # offset parsed from the source text, not zoneinfo.
        self.assertNotIn("ZoneInfo", self.rs_workflow)
        self.assertNotIn("zoneinfo", self.rs_workflow)
        self.assertNotIn("tzdata", self.rs_workflow)
        self.assertNotIn("Europe/Belgrade International Danube", self.rs_workflow)  # sanity: no stray leftovers

    def test_rs_daily_and_forecast_check_todays_data_instead_of_the_clock(self):
        self.assertIn("Resolve idempotent Serbia collection profile", self.rs_workflow)
        resolve_step = self.rs_workflow.split("Resolve idempotent Serbia collection profile", 1)[1].split("- name:", 1)[0]
        self.assertIn("international_source_operations.json", resolve_step)
        self.assertIn("last_success_at", resolve_step)
        self.assertIn("datetime.datetime.now(datetime.timezone.utc).date()", resolve_step)
        self.assertIn("alreadyCollectedToday", resolve_step)
        self.assertIn("$shouldRun = 'false'", resolve_step)
        # P1 recovery: a multi-line python -c heredoc at column 0 inside
        # this indented `run: |` block scalar breaks yaml.safe_load - every
        # line of a block scalar must stay at/above its own indentation.
        # This broke the file for two days undetected (no test parsed the
        # workflow YAML itself). Must stay a single line.
        python_c_lines = [line for line in resolve_step.split("\n") if 'python -c "' in line]
        self.assertEqual(1, len(python_c_lines))
        self.assertIn('"', python_c_lines[0].split("python -c", 1)[1])
        self.assertTrue(python_c_lines[0].rstrip().endswith('"'), "the python -c command must open and close on the same line")
        # Every new cron string must be mapped to a profile in the switch.
        for cron in ("35 10 * * *", "35 12 * * *", "35 14 * * *"):
            self.assertIn(f"'{cron}' {{ $profile = 'daily' }}", resolve_step)
        for cron in ("20 12 * * *", "20 14 * * *", "20 16 * * *"):
            self.assertIn(f"'{cron}' {{ $profile = 'forecast' }}", resolve_step)

    def test_rs_schedule_margin_is_at_least_one_hour_past_the_tightest_target(self):
        # Daily target ~10:20 Europe/Belgrade; tightest (latest-UTC) case is
        # winter CET (UTC+1) = 09:20 UTC. Forecast target ~12:00; tightest
        # case is 11:00 UTC. The first attempt of each must fire at or after
        # target + 1h.
        from datetime import datetime
        daily_first = datetime.strptime("10:35", "%H:%M")
        daily_tightest_target = datetime.strptime("09:20", "%H:%M")
        self.assertGreaterEqual((daily_first - daily_tightest_target).total_seconds(), 3600)
        forecast_first = datetime.strptime("12:20", "%H:%M")
        forecast_tightest_target = datetime.strptime("11:00", "%H:%M")
        self.assertGreaterEqual((forecast_first - forecast_tightest_target).total_seconds(), 3600)

    def test_source_health_job_runs_only_after_a_real_publish_succeeds(self):
        # P5: must never fire on a workflow_dispatch dry-run/fixtures test of
        # the main publish flow (where the publish job is skipped, not
        # failed, and health_check_mode defaults to "off") and must never
        # write to repository contents - only to issues.
        self.assertIn("\n  check-source-health:\n", self.workflow)
        _, health_job = self.workflow.split("\n  check-source-health:\n", 1)
        self.assertIn("needs: [collect-and-validate, publish]", health_job.split("\n", 3)[0] + health_job.split("\n", 3)[1])
        self.assertIn("needs.collect-and-validate.result == 'success'", health_job)
        self.assertIn("needs.publish.result == 'success'", health_job)
        self.assertIn("inputs.health_check_mode != 'off'", health_job)
        # Observed live (runs 31303342588 and its predecessor): a job with
        # needs: is skipped whenever ANY needed job is skipped - even with a
        # custom if: referencing needs.*.result - unless the condition also
        # calls always(). publish is legitimately skipped on a verification
        # dispatch (should_publish stays false), so without always() this
        # job could never run in live-test/dry-run mode despite every
        # operand of the condition being individually correct.
        if_line = health_job.split("\n", 3)[1]
        self.assertIn("if:", if_line)
        self.assertIn("always()", if_line)
        permissions = health_job.split("permissions:", 1)[1].split("steps:", 1)[0]
        self.assertIn("issues: write", permissions)
        # P5 (collection-recovery): check_source_health.py now also calls
        # `gh run list` to detect a stopped workflow - discovered live
        # (run 31471407324) that this job lacked actions: read and would
        # have failed in production, not just in a test.
        self.assertIn("actions: read", permissions)
        self.assertNotIn("contents: write", permissions)
        self.assertIn("ref: main", health_job)
        self.assertIn("python -m scripts.check_source_health", health_job)
        publish_start = self.workflow.index("\n  publish:\n")
        health_start = self.workflow.index("\n  check-source-health:\n")
        self.assertLess(publish_start, health_start, "check-source-health must be defined after publish")

    def test_job_level_if_conditions_are_single_line_expressions(self):
        # Observed live on 2026-08-08: an `if: |` (literal block scalar) YAML
        # condition on check-source-health kept its embedded newline in the
        # string GitHub Actions evaluates, and the job was silently skipped
        # even though every operand was correct (run 31280392236) - `if:`
        # must never be a YAML block scalar (`|` or `>`), only a plain
        # single-line string. No YAML parser is available in this
        # stdlib-only project, so this checks the raw text directly.
        block_scalar_if = re.findall(r"^\s*if:\s*[|>]", self.workflow, re.MULTILINE)
        self.assertEqual([], block_scalar_if, "if: must not use a YAML block scalar (| or >)")

    def test_source_health_verification_modes_use_isolated_label_and_never_touch_prod_label_alone(self):
        # The verification path must be reachable without a real publish
        # (workflow_dispatch, health_check_mode != off), must be able to
        # print without any GitHub call (dry-run), and its real-call variant
        # must use a distinct label/title so it can never collide with the
        # production "source-health" issue.
        self.assertIn("health_check_mode:", self.workflow)
        self.assertIn('options: ["off", dry-run, live-test]', self.workflow)
        _, health_job = self.workflow.split("\n  check-source-health:\n", 1)
        self.assertIn("check_source_health --dry-run", health_job)
        self.assertIn('--label source-health-verification', health_job)
        self.assertIn('--title "[TEST] source-health-monitor verification', health_job)
        # The dry-run verification step must never carry GH_TOKEN - it must
        # be structurally incapable of calling the GitHub API.
        dry_run_step = health_job.split("Verification - dry run", 1)[1].split("Verification - live test", 1)[0]
        self.assertNotIn("GH_TOKEN", dry_run_step)

    def test_simulated_afdj_change_is_preserved_and_international_conflict_is_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            self._git(repo, "init", "-b", "main")
            self._git(repo, "config", "user.name", "test")
            self._git(repo, "config", "user.email", "test@example.invalid")
            international = repo / "data" / "public" / "international" / "sources.json"
            afdj = repo / "data" / "public" / "status.json"
            international.parent.mkdir(parents=True)
            international.write_text("base\n", encoding="utf-8")
            afdj.write_text("afdj-base\n", encoding="utf-8")
            self._git(repo, "add", "data")
            self._git(repo, "commit", "-m", "base")
            base = self._git(repo, "rev-parse", "HEAD").strip()

            self._git(repo, "switch", "-c", "collector")
            international.write_text("validated international\n", encoding="utf-8")
            self._git(repo, "add", "data/public/international")
            self._git(repo, "commit", "-m", "international")

            self._git(repo, "switch", "main")
            afdj.write_text("afdj concurrent update\n", encoding="utf-8")
            self._git(repo, "add", "data/public/status.json")
            self._git(repo, "commit", "-m", "AFDJ")
            changed = self._git(repo, "diff", "--name-only", base, "main", "--", "data/public/international")
            self.assertEqual(changed, "")

            self._git(repo, "switch", "collector")
            self._git(repo, "rebase", "main")
            self.assertEqual(afdj.read_text(encoding="utf-8"), "afdj concurrent update\n")
            self.assertEqual(international.read_text(encoding="utf-8"), "validated international\n")

            self._git(repo, "switch", "main")
            international.write_text("competing international\n", encoding="utf-8")
            self._git(repo, "add", "data/public/international")
            self._git(repo, "commit", "-m", "competing international")
            changed = self._git(repo, "diff", "--name-only", base, "main", "--", "data/public/international")
            self.assertEqual(changed.strip(), "data/public/international/sources.json")

    @staticmethod
    def _git(repo: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments], cwd=repo, check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return result.stdout


if __name__ == "__main__":
    unittest.main()
