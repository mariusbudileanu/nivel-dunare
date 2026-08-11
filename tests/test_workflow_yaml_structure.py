"""P2 (collection-recovery incident): every workflow file must actually
parse. Before this test existed, update-serbia-data.yml sat on main with
a structural YAML defect for two days - 201 green tests, all validators
clean, and nothing checked the workflow files themselves. See
scripts/validate_workflows.py for what "parse" means here and why.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.validate_workflows import (
    WORKFLOWS_DIR,
    find_schedule_switch_mismatches,
    validate_all,
    validate_workflow_text,
)

# A minimal reproduction of the actual defect (P1 recovery report): a
# multi-line python -c heredoc at column 0 inside an indented `run: |`
# block scalar. Not the full file - just enough to exercise the same
# YAML rule (block scalar content must stay at/above its own
# indentation) that a real parser applies and that broke production.
CORRUPTED_BLOCK_SCALAR = """\
name: Sample
on:
  workflow_dispatch:
jobs:
  demo:
    runs-on: ubuntu-latest
    steps:
      - name: Run something
        shell: bash
        run: |
          echo "before"
          python -c "
import json
print(json.dumps({"a": 1}))
"
          echo "after"
"""

FIXED_BLOCK_SCALAR = """\
name: Sample
on:
  workflow_dispatch:
jobs:
  demo:
    runs-on: ubuntu-latest
    steps:
      - name: Run something
        shell: bash
        run: |
          echo "before"
          python -c "import json; print(json.dumps({'a': 1}))"
          echo "after"
"""


class ValidateWorkflowTextTests(unittest.TestCase):
    def test_corrupted_block_scalar_sample_is_rejected(self):
        errors = validate_workflow_text(CORRUPTED_BLOCK_SCALAR)
        self.assertTrue(errors, "the corrupted sample must be flagged as invalid")
        joined = "\n".join(errors)
        self.assertIn("import json", joined)

    def test_fixed_block_scalar_sample_is_accepted(self):
        self.assertEqual([], validate_workflow_text(FIXED_BLOCK_SCALAR))

    def test_missing_on_block_is_rejected(self):
        errors = validate_workflow_text("name: X\njobs:\n  a:\n    runs-on: ubuntu-latest\n")
        self.assertIn("missing top-level 'on:' block", errors)

    def test_cron_with_wrong_field_count_is_rejected(self):
        text = 'name: X\non:\n  schedule:\n    - cron: "17 */3 * *"\njobs:\n  a:\n    runs-on: ubuntu-latest\n'
        errors = validate_workflow_text(text)
        self.assertTrue(any("expected 5" in error for error in errors))

    def test_empty_runs_on_is_rejected(self):
        text = "name: X\non:\n  workflow_dispatch:\njobs:\n  a:\n    runs-on:\n"
        errors = validate_workflow_text(text)
        self.assertTrue(any("runs-on" in error for error in errors))

    def test_schedule_switch_missing_branch_is_rejected(self):
        text = """\
name: X
on:
  schedule:
    - cron: "1 2 * * *"
    - cron: "3 4 * * *"
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: |
          switch ('${{ github.event.schedule }}') {
            '1 2 * * *' { $x = 'a' }
            default { throw 'x' }
          }
"""
        errors = find_schedule_switch_mismatches(text)
        self.assertTrue(any('"3 4 * * *"' in error and "no branch" in error for error in errors))

    def test_schedule_switch_orphaned_branch_is_rejected(self):
        text = """\
name: X
on:
  schedule:
    - cron: "1 2 * * *"
jobs:
  a:
    runs-on: ubuntu-latest
    steps:
      - run: |
          switch ('${{ github.event.schedule }}') {
            '1 2 * * *' { $x = 'a' }
            '9 9 * * *' { $x = 'b' }
            default { throw 'x' }
          }
"""
        errors = find_schedule_switch_mismatches(text)
        self.assertTrue(any('"9 9 * * *"' in error and "not in the schedule block" in error for error in errors))


class AllRepositoryWorkflowsAreValidTests(unittest.TestCase):
    def test_every_workflow_file_parses(self):
        reports = validate_all()
        self.assertTrue(reports, "expected at least one workflow file under .github/workflows")
        failed = {report.path.name: report.errors for report in reports if not report.ok}
        self.assertEqual({}, failed)

    def test_serbia_workflow_specifically_has_no_leaked_heredoc_lines(self):
        # The exact regression: reproduces the P1 incident directly
        # against the real, currently-committed file.
        path = WORKFLOWS_DIR / "update-serbia-data.yml"
        errors = validate_workflow_text(path.read_text(encoding="utf-8"))
        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
