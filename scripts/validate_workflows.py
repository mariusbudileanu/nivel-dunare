#!/usr/bin/env python3
"""Structural validator for .github/workflows/*.yml.

Not a general YAML parser - this project has no YAML library dependency
(stdlib-only Python 3.12, see requirements.txt), and adding one only to
validate seven small, hand-authored files would trade a real risk (a
parser bug of its own) for a narrow, already-understood one. Instead
this specifically and deterministically catches:

- A block scalar (`|`/`>`) whose content contains a line indented less
  than the block's own established indentation. This is the exact
  defect that silently broke update-serbia-data.yml for two days
  (P1 recovery, 2026-08-11): a real YAML parser terminates the block at
  that line and tries to parse the rest as top-level YAML, which fails
  with a ParserError - but nothing in this repo's test suite parsed the
  workflow files themselves, so it went undetected until the scheduled
  crons silently stopped firing.
- Every remaining line outside a block scalar has a shape YAML actually
  allows (mapping key, list item, comment, flow-collection close) -
  this is what would have caught the leaked Python lines directly.
- A top-level `on:` and `jobs:` block are present.
- Every `- cron: "..."` string has exactly 5 space-separated fields.
- Every `runs-on:` has a non-empty value.
- For any job with a `switch ('${{ github.event.schedule }}')` block:
  every cron string under `schedule:` has a matching branch, and every
  branch matches a real scheduled cron - checked in both directions, so
  an orphaned branch is caught too, not just a missing one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"

_BLOCK_KEY_RE = re.compile(r"^(?P<indent>[ ]*)(?:-\s+)?[^\s:#][^:]*:\s*[|>][+\-]?\s*(?:#.*)?$")
_LINE_SHAPE_RE = re.compile(
    r"^\s*("
    r"#.*"                       # comment
    r"|-\s*$"                    # bare list item start
    r"|-\s+\S.*"                 # list item with inline content
    r"|[^\s:#][^:]*:\s*(?:#.*)?$"  # mapping key, no inline value
    r"|[^\s:#][^:]*:\s+\S.*"     # mapping key with inline value
    r"|\}[,\s]*$"                # flow mapping close
    r"|\][,\s]*$"                # flow sequence close
    r"|\.\.\.\s*$"                # document end marker
    r"|---\s*$"                   # document start marker
    r")$"
)
_CRON_LINE_RE = re.compile(r'-\s*cron:\s*"([^"]*)"')
_RUNS_ON_RE = re.compile(r"^\s*runs-on:\s*(.*)$", re.MULTILINE)


class WorkflowValidationError(ValueError):
    pass


def find_block_scalars(lines: list[str]) -> list[tuple[int, int, int]]:
    """Returns (key_line_index, content_start_index, content_end_index)
    for every block scalar, using the same rule a real YAML parser uses:
    content indentation is set by the first non-blank line after the key,
    and continues until a non-blank line indented less than that appears."""
    spans = []
    i = 0
    while i < len(lines):
        match = _BLOCK_KEY_RE.match(lines[i])
        if not match:
            i += 1
            continue
        key_indent = len(match.group("indent"))
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        if j >= len(lines):
            spans.append((i, j, j))
            break
        block_indent = len(lines[j]) - len(lines[j].lstrip(" "))
        if block_indent <= key_indent:
            spans.append((i, j, j))
            i = j
            continue
        k = j
        while k < len(lines):
            if lines[k].strip() == "":
                k += 1
                continue
            this_indent = len(lines[k]) - len(lines[k].lstrip(" "))
            if this_indent < block_indent:
                break
            k += 1
        spans.append((i, j, k))
        i = k
    return spans


def find_block_scalar_indentation_violations(text: str) -> list[str]:
    """A block scalar's own content is opaque to YAML, so under-indented
    lines inside a *correctly bounded* block never trigger this - what
    it actually catches is content the author intended to be inside the
    block but wrote under-indented, which a real parser silently
    excludes rather than erroring on directly. That excluded content is
    then checked against _LINE_SHAPE_RE by the caller; this function
    only reports the sub-case where the block scalar has literally no
    content line at or above its own key's indentation."""
    lines = text.splitlines()
    violations = []
    for key_index, content_start, content_end in find_block_scalars(lines):
        if content_start == content_end and content_start < len(lines):
            violations.append(f"line {key_index + 1}: block scalar has no indented content")
    return violations


def find_line_shape_violations(text: str) -> list[str]:
    lines = text.splitlines()
    block_content_ranges = [(start, end) for _, start, end in find_block_scalars(lines)]

    def inside_block(index: int) -> bool:
        return any(start <= index < end for start, end in block_content_ranges)

    violations = []
    for index, line in enumerate(lines):
        if inside_block(index) or line.strip() == "":
            continue
        if not _LINE_SHAPE_RE.match(line):
            violations.append(f"line {index + 1}: not a recognizable YAML line: {line!r}")
    return violations


def find_cron_syntax_errors(text: str) -> list[str]:
    errors = []
    on_block = text.split("\njobs:", 1)[0]
    for match in _CRON_LINE_RE.finditer(on_block):
        cron = match.group(1)
        fields = cron.split()
        if len(fields) != 5:
            errors.append(f'cron "{cron}" has {len(fields)} fields, expected 5')
    return errors


def find_runs_on_errors(text: str) -> list[str]:
    errors = []
    for match in _RUNS_ON_RE.finditer(text):
        value = match.group(1).strip().strip("'\"")
        if not value or value.startswith("${{") and not value.endswith("}}"):
            errors.append(f"runs-on has an empty or malformed value: {match.group(0)!r}")
    return errors


def find_schedule_switch_mismatches(text: str) -> list[str]:
    """For any `switch ('${{ github.event.schedule }}')` block: every
    scheduled cron must have a branch, and every branch must correspond
    to a real scheduled cron."""
    if "github.event.schedule" not in text:
        return []
    on_block = text.split("\npermissions:", 1)[0].split("\njobs:", 1)[0]
    scheduled_crons = {match.group(1) for match in _CRON_LINE_RE.finditer(on_block)}
    switch_block = text.split("github.event.schedule", 1)[1].split("default", 1)[0]
    switch_crons = set(re.findall(r"'([0-9*/, ]+ \* \* \*)'\s*\{", switch_block))
    errors = []
    for cron in sorted(scheduled_crons - switch_crons):
        errors.append(f'cron "{cron}" is scheduled but has no branch in the schedule switch')
    for cron in sorted(switch_crons - scheduled_crons):
        errors.append(f'schedule switch has a branch for "{cron}", which is not in the schedule block')
    return errors


@dataclass
class WorkflowReport:
    path: Path
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_workflow_text(text: str) -> list[str]:
    errors: list[str] = []
    errors.extend(find_block_scalar_indentation_violations(text))
    errors.extend(find_line_shape_violations(text))
    if not re.search(r"^on:\s*$", text, re.MULTILINE):
        errors.append("missing top-level 'on:' block")
    if not re.search(r"^jobs:\s*$", text, re.MULTILINE):
        errors.append("missing top-level 'jobs:' block")
    errors.extend(find_cron_syntax_errors(text))
    errors.extend(find_runs_on_errors(text))
    errors.extend(find_schedule_switch_mismatches(text))
    return errors


def validate_workflow_file(path: Path) -> WorkflowReport:
    text = path.read_text(encoding="utf-8")
    return WorkflowReport(path=path, errors=validate_workflow_text(text))


def validate_all(directory: Path = WORKFLOWS_DIR) -> list[WorkflowReport]:
    return [validate_workflow_file(path) for path in sorted(directory.glob("*.yml"))]


def main() -> int:
    reports = validate_all()
    failed = [report for report in reports if not report.ok]
    for report in reports:
        status = "ok" if report.ok else "INVALID"
        print(f"{report.path.name}: {status}")
        for error in report.errors:
            print(f"  - {error}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
