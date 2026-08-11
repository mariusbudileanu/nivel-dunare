#!/usr/bin/env python3
"""Detect international sources that have stopped delivering, AND detect
when a collection workflow itself has stopped running - two different
problems with two different causes, kept in one single tracking issue,
never a duplicate, always reflecting the current state.

Source staleness reuses each adapter's own stale_after_days (already
reviewed, already used for the source's own freshness warning). A uniform
CHRONIC_AFTER_DAYS distinguishes a normal operational hiccup from a source
that has genuinely stopped publishing for a long time (the Croatia case:
frozen since 2026-03-12, past its 7-day threshold within a week, but
nobody was alerted for 148 days because nothing watched for it).

Workflow-not-running detection was added after a real incident (P5,
collection-recovery, 2026-08-11) that source staleness alone could never
have caught: update-serbia-data.yml sat on main with invalid YAML for two
days - GitHub silently stopped honoring its schedule entirely, RHMZ kept
publishing normally, so from the source's own point of view nothing was
stale yet. Thresholds are derived from each workflow's own declared cron
cadence (worst-case gap between firings x2), not invented. A run whose
duration is suspiciously short (<=1s) is flagged on its own - the exact
signature GitHub leaves when a workflow file fails to parse at all.

Scope: the 7 international adapters only (data/public/international). AFDJ
runs on separate Hetzner infrastructure outside this repo's automation and
is intentionally not read here for source staleness - but its own
collection script (run via a Hetzner systemd timer, not a GitHub Actions
schedule) is also out of scope for workflow-not-running detection, since
that check is specifically about GitHub Actions' own schedule trigger.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

from scripts.sources.registry import ADAPTERS

CHRONIC_AFTER_DAYS = 30
ISSUE_LABEL = "source-health"
ISSUE_MARKER = "<!-- source-health-monitor: managed automatically, do not edit -->"
ISSUE_TITLE = "Surse internaționale cu probleme de livrare"
SHORT_RUN_SECONDS = 1
SAFETY_MULTIPLIER = 2


def stale_after_days_by_code() -> dict[str, int]:
    return {code: cls.stale_after_days for code, cls in ADAPTERS.items()}


@dataclass(frozen=True)
class SourceProblem:
    code: str
    country_code: str
    label: str
    age_days: int
    threshold_days: int
    tier: str  # "recent" or "chronic"
    last_source_observation_at: str | None
    consecutive_failures: int
    last_error_message: str | None


def evaluate_sources(
    sources: list[dict[str, Any]], today: date, thresholds: dict[str, int] | None = None,
) -> list[SourceProblem]:
    """Pure function: no I/O, no GitHub access. Returns the sources that have
    exceeded their own stale_after_days threshold, sorted worst-first."""
    thresholds = thresholds if thresholds is not None else stale_after_days_by_code()
    problems: list[SourceProblem] = []
    for source in sources:
        code = str(source.get("country_code", "")).lower()
        threshold = thresholds.get(code)
        if threshold is None:
            continue
        observed_at = source.get("last_source_observation_at")
        if not observed_at:
            continue
        observed_date = date.fromisoformat(str(observed_at)[:10])
        age_days = (today - observed_date).days
        if age_days <= threshold:
            continue
        tier = "chronic" if age_days > CHRONIC_AFTER_DAYS else "recent"
        problems.append(SourceProblem(
            code=code, country_code=source.get("country_code", code.upper()),
            label=source.get("label") or code.upper(), age_days=age_days, threshold_days=threshold,
            tier=tier, last_source_observation_at=str(observed_at),
            consecutive_failures=int(source.get("consecutive_failures") or 0),
            last_error_message=source.get("last_error_message"),
        ))
    problems.sort(key=lambda item: item.age_days, reverse=True)
    return problems


CRON_FIELD_RE = re.compile(r"^(\*|\d+)(?:/(\d+))?$")


def _cron_fire_minutes_of_day(cron: str) -> list[int]:
    """Every minute-of-day (0-1439) a daily cron fires at, for the two
    field shapes actually used in this repo's workflows: "M H * * *" and
    "M */N * * *". Not a general cron parser."""
    minute_field, hour_field = cron.split()[:2]
    minute = int(minute_field)
    if hour_field == "*":
        hours = list(range(24))
    elif hour_field.startswith("*/"):
        step = int(hour_field[2:])
        hours = list(range(0, 24, step))
    else:
        hours = [int(hour_field)]
    return sorted(hour * 60 + minute for hour in hours)


def max_gap_hours(crons: list[str]) -> float:
    """Worst-case gap, in hours, between consecutive firings of the given
    daily crons, wrapping around midnight - the same computation shown to
    and confirmed by the repo owner before this was implemented."""
    times = sorted({minute for cron in crons for minute in _cron_fire_minutes_of_day(cron)})
    if not times:
        raise ValueError("no cron fire times")
    gaps = [times[i + 1] - times[i] for i in range(len(times) - 1)]
    gaps.append(times[0] + 24 * 60 - times[-1])
    return max(gaps) / 60


@dataclass(frozen=True)
class WorkflowSpec:
    file: str
    label: str
    crons: tuple[str, ...]

    @property
    def threshold_hours(self) -> float:
        return max_gap_hours(list(self.crons)) * SAFETY_MULTIPLIER


WORKFLOW_SPECS = (
    WorkflowSpec(
        file="update-international-data.yml", label="Colectare internațională (DE/AT/SK/HU/HR/BG)",
        crons=("37 1 * * *", "35 8 * * *", "35 12 * * *"),
    ),
    WorkflowSpec(
        file="update-serbia-data.yml", label="Colectare Serbia (RHMZ)",
        crons=("17 */3 * * *", "47 0 * * *", "35 10 * * *", "35 12 * * *", "35 14 * * *", "20 12 * * *", "20 14 * * *", "20 16 * * *"),
    ),
)


@dataclass(frozen=True)
class WorkflowRunSummary:
    conclusion: str | None
    created_at: str
    duration_seconds: float | None


class RunLister(Protocol):
    def list_recent_runs(self, workflow_file: str, limit: int) -> list[WorkflowRunSummary]: ...


class GhCliRunLister:
    """Thin wrapper over `gh run list`."""

    def __init__(self, repo: str) -> None:
        self.repo = repo

    def list_recent_runs(self, workflow_file: str, limit: int) -> list[WorkflowRunSummary]:
        result = subprocess.run(
            ["gh", "run", "list", "--repo", self.repo, "--workflow", workflow_file,
             "--limit", str(limit), "--json", "conclusion,createdAt,startedAt,updatedAt,status"],
            capture_output=True, text=True, check=True,
        )
        rows = json.loads(result.stdout)
        summaries = []
        for row in rows:
            if row.get("status") != "completed":
                continue
            duration = None
            started, updated = row.get("startedAt"), row.get("updatedAt")
            if started and updated:
                try:
                    start = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    duration = (end - start).total_seconds()
                except ValueError:
                    duration = None
            summaries.append(WorkflowRunSummary(conclusion=row.get("conclusion"), created_at=row["createdAt"], duration_seconds=duration))
        return summaries


@dataclass(frozen=True)
class WorkflowProblem:
    file: str
    label: str
    kind: str  # "not_running" or "short_duration"
    hours_since_last_success: float | None
    threshold_hours: float
    short_run_created_at: str | None = None


def evaluate_workflow_health(
    specs: tuple[WorkflowSpec, ...], runs_by_file: dict[str, list[WorkflowRunSummary]], now: datetime,
) -> list[WorkflowProblem]:
    """Pure function: no I/O. `runs_by_file` must already be sorted newest
    first, as `gh run list` returns it."""
    problems: list[WorkflowProblem] = []
    for spec in specs:
        runs = runs_by_file.get(spec.file, [])
        last_success_at = None
        for run in runs:
            if run.conclusion == "success":
                last_success_at = run.created_at
                break
        hours_since = None
        if last_success_at:
            created = datetime.fromisoformat(str(last_success_at).replace("Z", "+00:00"))
            hours_since = (now - created).total_seconds() / 3600
        if hours_since is None or hours_since > spec.threshold_hours:
            problems.append(WorkflowProblem(
                file=spec.file, label=spec.label, kind="not_running",
                hours_since_last_success=hours_since, threshold_hours=spec.threshold_hours,
            ))
        for run in runs[:5]:
            if run.duration_seconds is not None and run.duration_seconds <= SHORT_RUN_SECONDS:
                problems.append(WorkflowProblem(
                    file=spec.file, label=spec.label, kind="short_duration",
                    hours_since_last_success=hours_since, threshold_hours=spec.threshold_hours,
                    short_run_created_at=run.created_at,
                ))
                break
    return problems


def render_issue(problems: list[SourceProblem], today: date, workflow_problems: list[WorkflowProblem] | None = None) -> tuple[str, str]:
    """Pure function: builds the exact issue title/body text. No I/O."""
    workflow_problems = workflow_problems or []
    if not problems and not workflow_problems:
        return ISSUE_TITLE, ""
    chronic = [p for p in problems if p.tier == "chronic"]
    recent = [p for p in problems if p.tier == "recent"]
    lines = [ISSUE_MARKER, "", f"_Verificare automată la {today.isoformat()}._", ""]

    def describe(problem: SourceProblem) -> list[str]:
        entry = [
            f"- **{problem.label} ({problem.country_code})** — ultima observație din "
            f"`{problem.last_source_observation_at}`, acum {problem.age_days} zile "
            f"(prag normal: {problem.threshold_days} zile).",
        ]
        if problem.consecutive_failures:
            entry.append(
                f"  - {problem.consecutive_failures} încercări consecutive de colectare eșuate. "
                f"Ultima eroare: `{problem.last_error_message}`",
            )
        return entry

    if workflow_problems:
        lines.append("## Colectarea nu rulează")
        lines.append("Sursa oficială poate publica normal - problema e că noi nu mai colectăm, nu că sursa nu publică.")
        lines.append("")
        for problem in workflow_problems:
            if problem.kind == "not_running":
                since = (
                    f"acum {problem.hours_since_last_success:.1f}h" if problem.hours_since_last_success is not None
                    else "niciodată (fără rulare reușită găsită)"
                )
                lines.append(
                    f"- **{problem.label}** (`{problem.file}`) — ultima rulare reușită {since} "
                    f"(prag: {problem.threshold_hours:.1f}h, derivat din propriul program).",
                )
            else:
                lines.append(
                    f"- **{problem.label}** (`{problem.file}`) — o rulare din `{problem.short_run_created_at}` "
                    f"a durat sub {SHORT_RUN_SECONDS}s, semn tipic că fișierul de workflow nu mai poate fi interpretat.",
                )
        lines.append("")
    if chronic:
        lines.append(f"## Stale de peste {CHRONIC_AFTER_DAYS} de zile")
        lines.append("Sursa oficială nu mai publică date de mult timp, nu doar o rulare ratată.")
        lines.append("")
        for problem in chronic:
            lines.extend(describe(problem))
        lines.append("")
    if recent:
        lines.append("## Stale recent")
        for problem in recent:
            lines.extend(describe(problem))
        lines.append("")
    return ISSUE_TITLE, "\n".join(lines)


@dataclass
class GhIssue:
    number: int
    title: str
    body: str


class IssueClient(Protocol):
    def find_open(self, label: str) -> GhIssue | None: ...
    def create(self, label: str, title: str, body: str) -> GhIssue: ...
    def update_body(self, number: int, body: str) -> None: ...
    def close(self, number: int, comment: str) -> None: ...


class GhCliClient:
    """Thin wrapper over the real `gh issue` subcommands."""

    def __init__(self, repo: str) -> None:
        self.repo = repo

    def find_open(self, label: str) -> GhIssue | None:
        result = subprocess.run(
            ["gh", "issue", "list", "--repo", self.repo, "--label", label, "--state", "open", "--json", "number,title,body", "--limit", "1"],
            capture_output=True, text=True, check=True,
        )
        rows = json.loads(result.stdout)
        if not rows:
            return None
        return GhIssue(number=rows[0]["number"], title=rows[0]["title"], body=rows[0]["body"])

    def create(self, label: str, title: str, body: str) -> GhIssue:
        result = subprocess.run(
            ["gh", "issue", "create", "--repo", self.repo, "--label", label, "--title", title, "--body", body],
            capture_output=True, text=True, check=True,
        )
        url = result.stdout.strip()
        number = int(url.rstrip("/").rsplit("/", 1)[-1])
        return GhIssue(number=number, title=title, body=body)

    def update_body(self, number: int, body: str) -> None:
        subprocess.run(["gh", "issue", "edit", str(number), "--repo", self.repo, "--body", body], check=True)

    def close(self, number: int, comment: str) -> None:
        subprocess.run(["gh", "issue", "comment", str(number), "--repo", self.repo, "--body", comment], check=True)
        subprocess.run(["gh", "issue", "close", str(number), "--repo", self.repo], check=True)


def sync_issue(client: IssueClient, label: str, title: str, body: str, has_problems: bool) -> str:
    """The only function that talks to GitHub (via `client`). Returns one of
    "created", "updated", "unchanged", "closed", "noop" - fully driven by
    `client`, so a fake in-memory client exercises this with zero real API
    calls."""
    existing = client.find_open(label)
    if has_problems:
        if existing is None:
            client.create(label, title, body)
            return "created"
        if existing.body != body:
            client.update_body(existing.number, body)
            return "updated"
        return "unchanged"
    if existing is not None:
        client.close(existing.number, "Toate sursele au revenit la normal la ultima verificare automată.")
        return "closed"
    return "noop"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("data/public/international/sources.json"))
    parser.add_argument("--repo", default="mariusbudileanu/nivel-dunare")
    parser.add_argument("--label", default=ISSUE_LABEL)
    parser.add_argument("--title", help="Override the issue title (e.g. to mark a verification run); defaults to the production title")
    parser.add_argument("--today", help="Override today's date (ISO 8601); defaults to the current UTC date")
    parser.add_argument("--dry-run", action="store_true", help="Print the computed report; never touch GitHub")
    parser.add_argument("--skip-workflow-check", action="store_true", help="Skip the gh run list-based workflow-not-running check (source staleness only)")
    args = parser.parse_args(argv)

    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc) if not args.today else datetime.fromisoformat(args.today).replace(tzinfo=timezone.utc)
    today = now.date()
    problems = evaluate_sources(sources, today)

    workflow_problems: list[WorkflowProblem] = []
    if not args.skip_workflow_check:
        lister = GhCliRunLister(args.repo)
        runs_by_file = {spec.file: lister.list_recent_runs(spec.file, 10) for spec in WORKFLOW_SPECS}
        workflow_problems = evaluate_workflow_health(WORKFLOW_SPECS, runs_by_file, now)

    title, body = render_issue(problems, today, workflow_problems)
    if args.title:
        title = args.title
    has_problems = bool(problems) or bool(workflow_problems)

    if args.dry_run:
        print(json.dumps({
            "has_problems": has_problems,
            "problem_codes": [p.code for p in problems],
            "workflow_problem_files": [p.file for p in workflow_problems],
            "title": title, "body": body,
        }, indent=2, ensure_ascii=False))
        return 0

    client = GhCliClient(args.repo)
    action = sync_issue(client, args.label, title, body, has_problems)
    print(json.dumps({
        "action": action, "has_problems": has_problems,
        "problem_codes": [p.code for p in problems],
        "workflow_problem_files": [p.file for p in workflow_problems],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
