"""Keel dispatch review gate for governed pull requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any


SCOPE_DECLARATION = re.compile(r"^\ufeff?\s*Steward-Scope:\s*([A-Za-z0-9._-]+)\s*$")
REVIEW_DECLARATION = re.compile(r"^\ufeff?\s*Codex-Dispatch-Review:\s*(\S+)\s*$")
CDR_ID = re.compile(r"^CDR-\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*[a-z0-9]$")
GITHUB_COMMENT_URL = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:pull|issues)/\d+#issuecomment-\d+$"
)
GITHUB_REVIEW_URL = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+#pullrequestreview-\d+$"
)
GITHUB_DISCUSSION_URL = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+#discussion_r\d+$"
)
SECTION_HEADING = re.compile(r"^##\s+Dispatch Review\s*$", re.MULTILINE)
INDEPENDENT_REVIEW_HEADING = re.compile(r"^##\s+Independent Review\s*$", re.MULTILINE)
NEXT_HEADING = re.compile(r"^##\s+", re.MULTILINE)
UNCHECKED_BOX = re.compile(r"(?m)^\s*[-*]\s+\[\s\]\s+")
INDEPENDENT_VERDICT = re.compile(r"(?im)^[ \t]*Verdict:[ \t]*(\S+)[ \t]*$")
INDEPENDENT_REVIEWER = re.compile(r"(?im)^[ \t]*Reviewer[ \t]*/[ \t]*evidence URL:[ \t]*(\S.*)$")


def validate_event(event: dict[str, Any]) -> list[str]:
    pr = event.get("pull_request") or {}
    body_value = pr.get("body") or ""
    body = body_value if isinstance(body_value, str) else ""
    is_draft = bool(pr.get("draft"))
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    head_ref = head.get("ref") or ""
    scope_id = _resolve_scope_id(body)
    review_evidence = _resolve_review_evidence(body)
    errors: list[str] = []

    if not scope_id:
        errors.append("PR body must declare Steward-Scope: <scope_id>")
    elif scope_id == "REQUIRED":
        errors.append("PR body must replace Steward-Scope: REQUIRED with the exact scope id")

    if not review_evidence:
        errors.append("PR body must declare Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>")
    elif review_evidence == "REQUIRED":
        errors.append("PR body must replace Codex-Dispatch-Review: REQUIRED with review evidence")
    elif not _valid_review_evidence(review_evidence):
        errors.append(
            "Codex-Dispatch-Review must be a CDR-YYYY-MM-DD-<slug> id or a GitHub issue/PR comment URL"
        )

    if head_ref.startswith("batch/"):
        errors.append("governed PR branches must not use retired batch/* names")
    if scope_id and not head_ref.startswith("keel/"):
        errors.append("governed PR branches must use keel/<purpose>-<date>")

    section = _dispatch_section(body)
    if section is None:
        errors.append("PR body must include a ## Dispatch Review section")
        return errors

    unchecked = [line.strip() for line in section.splitlines() if UNCHECKED_BOX.match(line)]
    if unchecked:
        errors.append("all Dispatch Review checklist items must be checked")

    required_phrases = [
        "Codex Dispatch Review evidence",
        "latest `origin/master`",
        "fresh scope file",
        "forbidden_paths",
        "reachability was checked",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in section]
    if missing:
        errors.append(f"Dispatch Review is missing required evidence: {', '.join(missing)}")

    if not is_draft:
        review_section = _section(body, INDEPENDENT_REVIEW_HEADING)
        if review_section is None:
            errors.append("PR body must include a ## Independent Review section")
            return errors

        reviewer_match = INDEPENDENT_REVIEWER.search(review_section)
        reviewer_value = reviewer_match.group(1).strip() if reviewer_match else ""
        if not reviewer_value or reviewer_value.upper() in {"PENDING", "REQUIRED"}:
            errors.append("Independent Review must include a non-placeholder Reviewer / evidence URL")
        elif not _valid_independent_review_evidence(reviewer_value):
            errors.append(
                "Independent Review evidence must be a GitHub PR comment, review, or review-thread URL"
            )

        verdict_match = INDEPENDENT_VERDICT.search(review_section)
        verdict = verdict_match.group(1).strip().upper() if verdict_match else ""
        if verdict != "PASS":
            errors.append("Independent Review verdict must be PASS before merge")

    return errors


def _resolve_scope_id(body: str) -> str | None:
    for line in body.splitlines():
        match = SCOPE_DECLARATION.match(line)
        if match:
            return match.group(1)
    return None


def _resolve_review_evidence(body: str) -> str | None:
    for line in body.splitlines():
        match = REVIEW_DECLARATION.match(line)
        if match:
            return match.group(1)
    return None


def _valid_review_evidence(value: str) -> bool:
    return bool(CDR_ID.match(value) or GITHUB_COMMENT_URL.match(value))


def _valid_independent_review_evidence(value: str) -> bool:
    return bool(
        GITHUB_COMMENT_URL.match(value)
        or GITHUB_REVIEW_URL.match(value)
        or GITHUB_DISCUSSION_URL.match(value)
    )


def _dispatch_section(body: str) -> str | None:
    return _section(body, SECTION_HEADING)


def _section(body: str, heading: re.Pattern[str]) -> str | None:
    match = heading.search(body)
    if not match:
        return None
    start = match.end()
    next_match = NEXT_HEADING.search(body, start)
    end = next_match.start() if next_match else len(body)
    return body[start:end]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, help="Path to the GitHub event JSON")
    args = parser.parse_args(argv)

    event = json.loads(Path(args.event).read_text(encoding="utf-8-sig"))
    errors = validate_event(event)
    if errors:
        for error in errors:
            print(f"dispatch review error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
