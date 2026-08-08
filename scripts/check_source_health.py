#!/usr/bin/env python3
"""Detect international sources that have stopped delivering and keep a
single tracking issue in sync - never a duplicate, always reflecting the
current state.

Reuses each adapter's own stale_after_days (already reviewed, already used
for the source's own freshness warning) as the "stale recently" threshold.
A uniform CHRONIC_AFTER_DAYS distinguishes a normal operational hiccup from
a source that has genuinely stopped publishing for a long time (the
Croatia case: frozen since 2026-03-12, past its 7-day threshold within a
week, but nobody was alerted for 148 days because nothing watched for it).

Scope: the 7 international adapters only (data/public/international). AFDJ
runs on separate Hetzner infrastructure outside this repo's automation and
is intentionally not read here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from scripts.sources.registry import ADAPTERS

CHRONIC_AFTER_DAYS = 30
ISSUE_LABEL = "source-health"
ISSUE_MARKER = "<!-- source-health-monitor: managed automatically, do not edit -->"
ISSUE_TITLE = "Surse internaționale cu probleme de livrare"


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


def render_issue(problems: list[SourceProblem], today: date) -> tuple[str, str]:
    """Pure function: builds the exact issue title/body text. No I/O."""
    if not problems:
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
    args = parser.parse_args(argv)

    sources = json.loads(args.sources.read_text(encoding="utf-8"))
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    problems = evaluate_sources(sources, today)
    title, body = render_issue(problems, today)
    if args.title:
        title = args.title

    if args.dry_run:
        print(json.dumps({
            "has_problems": bool(problems),
            "problem_codes": [p.code for p in problems],
            "title": title, "body": body,
        }, indent=2, ensure_ascii=False))
        return 0

    client = GhCliClient(args.repo)
    action = sync_issue(client, args.label, title, body, bool(problems))
    print(json.dumps({"action": action, "has_problems": bool(problems), "problem_codes": [p.code for p in problems]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
