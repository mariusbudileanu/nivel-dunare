from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.update_international_data import SCHEDULED_SOURCES


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "update-international-data.yml"


class InternationalWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_cron_contains_only_scheduled_source_selector(self):
        self.assertIn('- cron: "37 1 * * *"', self.workflow)
        self.assertIn('source="scheduled"', self.workflow)
        self.assertEqual(SCHEDULED_SOURCES, ("de", "sk", "hu", "hr", "bg"))
        self.assertNotIn("at", SCHEDULED_SOURCES)
        self.assertNotIn("rs", SCHEDULED_SOURCES)

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
        self.assertIn("Configured DoRIS secret found in persisted output", self.workflow)
        self.assertIn("path.unlink()", self.workflow)
        self.assertIn("raw, candidates, issues, logs and validated product", self.workflow)

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
