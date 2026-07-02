"""Keel dispatch review gate for governed pull requests."""

from __future__ import annotations

import argparse
import os
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Callable


SCOPE_DECLARATION = re.compile(r"^\ufeff?\s*Steward-Scope:\s*([A-Za-z0-9._-]+)\s*$")
REVIEW_DECLARATION = re.compile(r"^\ufeff?\s*Codex-Dispatch-Review:\s*(\S+)\s*$")
LANE_DECLARATION = re.compile(r"^\ufeff?\s*Integration-Lane:\s*(\S+)\s*$")
WRITE_LICENSE_DECLARATION = re.compile(r"^\ufeff?\s*Write-License:\s*(.*?)\s*$")
CDR_ID = re.compile(r"^CDR-\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9-]*[a-z0-9]$")
GITHUB_COMMENT_URL = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/(?:pull|issues)/\d+#issuecomment-\d+$"
)
GITHUB_COMMENT_URL_PARTS = re.compile(
    r"^https://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/(?:pull|issues)/"
    r"(?P<number>\d+)#issuecomment-(?P<id>\d+)$"
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
PLACEHOLDER_VALUES = {"PENDING", "REQUIRED", "TBD", "TODO"}
VALID_INTEGRATION_LANES = {"independent", "guarded", "exclusive"}
MIN_REVIEW_COMMENT_CHARS = 200
VERIFY_MODES = {"off", "warn", "enforce"}
FetchComment = Callable[[str, str | None], dict[str, Any]]


def validate_event(event: dict[str, Any]) -> list[str]:
    errors, _warnings = validate_event_with_warnings(event, verify_mode="off")
    return errors


def validate_event_with_warnings(
    event: dict[str, Any],
    *,
    verify_mode: str = "off",
    github_token: str | None = None,
    fetch_comment: FetchComment | None = None,
) -> tuple[list[str], list[str]]:
    pr = event.get("pull_request") or {}
    body_value = pr.get("body") or ""
    body = _normalize_newlines(body_value if isinstance(body_value, str) else "")
    is_draft = bool(pr.get("draft"))
    head = pr.get("head") if isinstance(pr.get("head"), dict) else {}
    head_ref = head.get("ref") or ""
    scope_id = _resolve_scope_id(body)
    review_evidence = _resolve_review_evidence(body)
    integration_lane = _resolve_integration_lane(body)
    write_license = _resolve_write_license(body)
    errors: list[str] = []
    warnings: list[str] = []
    verify_mode = _normalize_verify_mode(verify_mode)

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

    if not integration_lane:
        errors.append("PR body must declare Integration-Lane: independent|guarded|exclusive")
    elif integration_lane.upper() in PLACEHOLDER_VALUES:
        errors.append("PR body must replace Integration-Lane: REQUIRED with independent, guarded, or exclusive")
    elif integration_lane.lower() not in VALID_INTEGRATION_LANES:
        errors.append("Integration-Lane must be one of: independent, guarded, exclusive")

    if write_license is None or not write_license.strip():
        errors.append("PR body must declare Write-License with draft PR permission, CI self-fix permission, and stop condition")
    elif write_license.strip().upper() in PLACEHOLDER_VALUES:
        errors.append("PR body must replace Write-License: REQUIRED with the actual write license")
    else:
        errors.extend(_write_license_errors(write_license))

    if head_ref.startswith("batch/"):
        errors.append("governed PR branches must not use retired batch/* names")
    if scope_id and not head_ref.startswith("keel/"):
        errors.append("governed PR branches must use keel/<purpose>-<date>")

    section = _dispatch_section(body)
    if section is None:
        errors.append("PR body must include a ## Dispatch Review section")
        return errors, warnings

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
            return errors, warnings

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

        if verify_mode != "off" and reviewer_value and _valid_independent_review_evidence(reviewer_value):
            warnings.extend(
                _independent_review_evidence_warnings(
                    event,
                    reviewer_value,
                    github_token=github_token,
                    fetch_comment=fetch_comment,
                )
            )

    if verify_mode == "enforce":
        errors.extend(f"Independent Review evidence verification failed: {warning}" for warning in warnings)
        warnings = []

    return errors, warnings


def resolve_integration_lane(event: dict[str, Any]) -> str | None:
    pr = event.get("pull_request") or {}
    body_value = pr.get("body") or ""
    body = _normalize_newlines(body_value if isinstance(body_value, str) else "")
    lane = _resolve_integration_lane(body)
    return lane.lower() if lane else None


def _normalize_newlines(body: str) -> str:
    return body.replace("\r\n", "\n").replace("\r", "\n")


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


def _resolve_integration_lane(body: str) -> str | None:
    for line in body.splitlines():
        match = LANE_DECLARATION.match(line)
        if match:
            return match.group(1)
    return None


def _resolve_write_license(body: str) -> str | None:
    for line in body.splitlines():
        match = WRITE_LICENSE_DECLARATION.match(line)
        if match:
            return match.group(1)
    return None


def _write_license_errors(value: str) -> list[str]:
    normalized = value.lower()
    errors: list[str] = []
    if "draft" not in normalized:
        errors.append("Write-License must state draft PR permission")
    if "self-fix" not in normalized and "self fix" not in normalized:
        errors.append("Write-License must state CI self-fix permission")
    if "stop" not in normalized:
        errors.append("Write-License must state stop condition")
    return errors


def _valid_review_evidence(value: str) -> bool:
    return bool(CDR_ID.match(value) or GITHUB_COMMENT_URL.match(value))


def _valid_independent_review_evidence(value: str) -> bool:
    return bool(
        GITHUB_COMMENT_URL.match(value)
        or GITHUB_REVIEW_URL.match(value)
        or GITHUB_DISCUSSION_URL.match(value)
    )


def _normalize_verify_mode(value: str | None) -> str:
    mode = (value or "warn").strip().lower()
    return mode if mode in VERIFY_MODES else "warn"


def _independent_review_evidence_warnings(
    event: dict[str, Any],
    evidence_url: str,
    *,
    github_token: str | None = None,
    fetch_comment: FetchComment | None = None,
) -> list[str]:
    match = GITHUB_COMMENT_URL_PARTS.match(evidence_url)
    if not match:
        return ["only GitHub issuecomment evidence URLs can be API-verified in warn mode"]

    owner = match.group("owner")
    repo = match.group("repo")
    comment_id = match.group("id")
    expected_repo = _event_repo_full_name(event)
    expected_issue_url = _event_issue_url(event)
    pr_author = _event_pr_author(event)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{comment_id}"
    fetch = fetch_comment or _fetch_github_comment
    warnings: list[str] = []

    if expected_repo and expected_repo.lower() != f"{owner}/{repo}".lower():
        warnings.append("review evidence URL repository does not match the pull request repository")

    try:
        comment = fetch(api_url, github_token)
    except Exception as exc:  # pragma: no cover - exercised through CLI behavior
        return [f"could not fetch review evidence comment via GitHub API: {exc}"]

    issue_url = str(comment.get("issue_url") or "")
    if expected_issue_url and issue_url != expected_issue_url:
        warnings.append("review evidence comment does not belong to this pull request")
    elif not expected_issue_url:
        warnings.append("pull request number or repository was unavailable for evidence ownership verification")

    user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
    author = str(user.get("login") or "")
    if not author:
        warnings.append("review evidence comment has no GitHub author")
    elif pr_author and author.lower() == pr_author.lower():
        warnings.append("review evidence comment author is the pull request author")

    body = str(comment.get("body") or "")
    if len(body.strip()) < MIN_REVIEW_COMMENT_CHARS:
        warnings.append(f"review evidence comment body is shorter than {MIN_REVIEW_COMMENT_CHARS} characters")
    if "Verdict: PASS" not in body:
        warnings.append("review evidence comment body must include 'Verdict: PASS'")

    return warnings


def _event_repo_full_name(event: dict[str, Any]) -> str | None:
    repository = event.get("repository") if isinstance(event.get("repository"), dict) else {}
    full_name = repository.get("full_name")
    if isinstance(full_name, str) and full_name:
        return full_name
    pr = event.get("pull_request") if isinstance(event.get("pull_request"), dict) else {}
    base = pr.get("base") if isinstance(pr.get("base"), dict) else {}
    repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
    full_name = repo.get("full_name")
    return full_name if isinstance(full_name, str) and full_name else None


def _event_issue_url(event: dict[str, Any]) -> str | None:
    repo = _event_repo_full_name(event)
    pr = event.get("pull_request") if isinstance(event.get("pull_request"), dict) else {}
    number = pr.get("number")
    if repo and isinstance(number, int):
        return f"https://api.github.com/repos/{repo}/issues/{number}"
    return None


def _event_pr_author(event: dict[str, Any]) -> str | None:
    pr = event.get("pull_request") if isinstance(event.get("pull_request"), dict) else {}
    user = pr.get("user") if isinstance(pr.get("user"), dict) else {}
    login = user.get("login")
    return login if isinstance(login, str) and login else None


def _fetch_github_comment(api_url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "keel-dispatch-review-gate",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError("GitHub API response was not a JSON object")
    return data


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
    parser.add_argument("--print-integration-lane", action="store_true")
    args = parser.parse_args(argv)

    event = json.loads(Path(args.event).read_text(encoding="utf-8-sig"))
    if args.print_integration_lane:
        print(resolve_integration_lane(event) or "")
        return 0

    errors, warnings = validate_event_with_warnings(
        event,
        verify_mode=os.environ.get("KEEL_REVIEW_VERIFY", "warn"),
        github_token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
    )
    for warning in warnings:
        print(f"dispatch review warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"dispatch review error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
