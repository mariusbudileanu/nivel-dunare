from __future__ import annotations

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

    def test_bg_dedicated_exact_minute_gate_workflow_was_retired(self):
        # P4: the 09:15/21:15 Europe/Sofia exact-minute gate was fragile
        # against GitHub Actions scheduling delays of an hour or more
        # (observed directly on this repo). BG is fetched by the same
        # unconditional shared daily cron as DE/SK/HU/HR/AT now, so a delayed
        # run still collects data - there is no time check left to miss.
        self.assertFalse(BG_WORKFLOW.exists(), "update-bg-danube-streams.yml should be removed, not left dormant")
        self.assertNotIn("TZ=Europe/Sofia", self.workflow)
        self.assertNotIn("09:15", self.workflow)
        self.assertNotIn("21:15", self.workflow)

    def test_rs_windows_handoff_schedules_and_write_boundary(self):
        for cron in ("17 */3 * * *", "47 0 * * *", "20 8 * * *", "20 9 * * *", "35 10 * * *", "35 11 * * *"):
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

    def test_rs_windows_job_installs_tzdata_before_zoneinfo_use(self):
        # windows-latest has no OS-level IANA database; Python's zoneinfo needs the
        # tzdata PyPI package there or ZoneInfo('Europe/Belgrade') raises
        # ZoneInfoNotFoundError. Every scheduled run of this step failed with
        # exactly that error (confirmed via `gh run view`) until an install step
        # was added ahead of it.
        self.assertIn("ZoneInfo('Europe/Belgrade')", self.rs_workflow)
        before_resolve = self.rs_workflow.split("Resolve DST-safe Serbia collection profile", 1)[0]
        self.assertIn("pip install", before_resolve)
        self.assertIn("tzdata", before_resolve)
        self.assertIn("Configured DoRIS secret found in persisted output", self.workflow)
        self.assertIn("path.unlink()", self.workflow)
        self.assertIn("raw, candidates, issues, logs and validated product", self.workflow)

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
        permissions = health_job.split("permissions:", 1)[1].split("steps:", 1)[0]
        self.assertIn("issues: write", permissions)
        self.assertNotIn("contents: write", permissions)
        self.assertIn("ref: main", health_job)
        self.assertIn("python -m scripts.check_source_health", health_job)
        publish_start = self.workflow.index("\n  publish:\n")
        health_start = self.workflow.index("\n  check-source-health:\n")
        self.assertLess(publish_start, health_start, "check-source-health must be defined after publish")

    def test_source_health_verification_modes_use_isolated_label_and_never_touch_prod_label_alone(self):
        # The verification path must be reachable without a real publish
        # (workflow_dispatch, health_check_mode != off), must be able to
        # print without any GitHub call (dry-run), and its real-call variant
        # must use a distinct label/title so it can never collide with the
        # production "source-health" issue.
        self.assertIn("health_check_mode:", self.workflow)
        self.assertIn("options: [off, dry-run, live-test]", self.workflow)
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
