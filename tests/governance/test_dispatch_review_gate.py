"""Tests for the Keel dispatch review gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.governance.check_dispatch_review import (
    resolve_integration_lane,
    validate_event,
    validate_event_with_warnings,
)


def _event(*, body: str, branch: str = "keel/demo-2026-06-29", draft: bool = False):
    return {
        "repository": {"full_name": "juanwan99/edu-cloud"},
        "pull_request": {
            "number": 99,
            "body": body,
            "draft": draft,
            "head": {"ref": branch},
            "user": {"login": "juanwan99"},
        }
    }


def _valid_body() -> str:
    return """Steward-Scope: demo
Codex-Dispatch-Review: CDR-2026-06-29-demo
Integration-Lane: guarded
Write-License: draft PR creation allowed; CI self-fix not allowed; stop after draft PR.
Worker-Model: codex-gpt-5
Reviewer-Model: claude-sonnet-4.5

## Summary

## Dispatch Review

- [x] Codex Dispatch Review evidence above was completed before implementation.
- [x] Branch was created from latest `origin/master`; no stale worktree or branch was reused.
- [x] Added one fresh scope file under `control/steward/scopes/`.
- [x] Changed files stay inside scope `allowed_paths`; no `forbidden_paths` were touched.
- [x] For file deletion or retirement, reachability was checked across `scripts/`, `tests/`, `.github/workflows/`, active docs, and governance registries.

## Independent Review

Reviewer / evidence URL: https://github.com/juanwan99/edu-cloud/pull/99#issuecomment-1234567890

Verdict: PASS
"""


def _matching_review_comment(_url: str, _token: str | None):
    return {
        "issue_url": "https://api.github.com/repos/juanwan99/edu-cloud/issues/99",
        "user": {"login": "jopfea796-dotcom"},
        "body": ("review evidence " * 20) + "\nVerdict: PASS\n",
    }


def test_valid_dispatch_review_passes():
    assert validate_event(_event(body=_valid_body())) == []


def test_integration_lane_parser_accepts_crlf_body():
    event = _event(body=_valid_body().replace("\n", "\r\n"))

    assert resolve_integration_lane(event) == "guarded"
    assert validate_event(event) == []


def test_missing_dispatch_review_section_fails():
    body = "Steward-Scope: demo\nCodex-Dispatch-Review: CDR-2026-06-29-demo\n"

    errors = validate_event(_event(body=body))

    assert "PR body must include a ## Dispatch Review section" in errors


def test_non_string_body_fails_closed():
    errors = validate_event({"pull_request": {"body": ["Steward-Scope: demo"], "head": {"ref": "keel/demo"}}})

    assert "PR body must declare Steward-Scope: <scope_id>" in errors


def test_unchecked_dispatch_review_item_fails():
    body = _valid_body().replace("- [x] Codex Dispatch Review", "- [ ] Codex Dispatch Review")

    errors = validate_event(_event(body=body))

    assert "all Dispatch Review checklist items must be checked" in errors


def test_batch_branch_name_fails():
    errors = validate_event(_event(body=_valid_body(), branch="batch/archive-old-plans"))

    assert "governed PR branches must not use retired batch/* names" in errors
    assert "governed PR branches must use keel/<purpose>-<date>" in errors


def test_non_keel_governed_branch_fails():
    errors = validate_event(_event(body=_valid_body(), branch="codex/demo"))

    assert "governed PR branches must use keel/<purpose>-<date>" in errors


def test_missing_required_evidence_fails():
    body = _valid_body().replace(
        "Codex Dispatch Review evidence above was completed before implementation.",
        "Reviewer looked.",
    )

    errors = validate_event(_event(body=body))

    assert any("Codex Dispatch Review evidence" in error for error in errors)


def test_missing_independent_review_section_fails():
    body = _valid_body().replace(
        "\n## Independent Review\n\nReviewer / evidence URL: https://github.com/juanwan99/edu-cloud/pull/99#issuecomment-1234567890\n\nVerdict: PASS\n",
        "",
    )

    errors = validate_event(_event(body=body))

    assert "PR body must include a ## Independent Review section" in errors


def test_independent_review_pending_verdict_fails():
    body = _valid_body().replace("Verdict: PASS", "Verdict: PENDING")

    errors = validate_event(_event(body=body))

    assert "Independent Review verdict must be PASS before merge" in errors


def test_independent_review_missing_evidence_fails():
    body = _valid_body().replace(
        "Reviewer / evidence URL: https://github.com/juanwan99/edu-cloud/pull/99#issuecomment-1234567890",
        "Reviewer / evidence URL:",
    )

    errors = validate_event(_event(body=body))

    assert "Independent Review must include a non-placeholder Reviewer / evidence URL" in errors


def test_independent_review_malformed_evidence_url_fails():
    body = _valid_body().replace(
        "Reviewer / evidence URL: https://github.com/juanwan99/edu-cloud/pull/99#issuecomment-1234567890",
        "Reviewer / evidence URL: looked-good",
    )

    errors = validate_event(_event(body=body))

    assert "Independent Review evidence must be a GitHub PR comment, review, or review-thread URL" in errors


def test_independent_review_github_review_url_passes():
    body = _valid_body().replace(
        "Reviewer / evidence URL: https://github.com/juanwan99/edu-cloud/pull/99#issuecomment-1234567890",
        "Reviewer / evidence URL: https://github.com/juanwan99/edu-cloud/pull/99#pullrequestreview-1234567890",
    )

    assert validate_event(_event(body=body)) == []


def test_draft_pr_allows_pending_independent_review():
    body = _valid_body().replace("Verdict: PASS", "Verdict: PENDING")

    assert validate_event(_event(body=body, draft=True)) == []


def test_draft_pr_skips_api_evidence_verification():
    body = _valid_body().replace("Verdict: PASS", "Verdict: PENDING")

    def fail_fetch(_url: str, _token: str | None):
        raise AssertionError("draft PRs must not fetch review evidence")

    errors, warnings = validate_event_with_warnings(
        _event(body=body, draft=True),
        verify_mode="warn",
        fetch_comment=fail_fetch,
    )

    assert errors == []
    assert warnings == []


def test_off_mode_skips_api_evidence_verification_for_non_draft_pr():
    def fail_fetch(_url: str, _token: str | None):
        raise AssertionError("off mode must not fetch review evidence")

    errors, warnings = validate_event_with_warnings(
        _event(body=_valid_body()),
        verify_mode="off",
        fetch_comment=fail_fetch,
    )

    assert errors == []
    assert warnings == []


def test_independent_review_issue_comment_api_warning_passes_when_comment_matches():
    def fetch_comment(url: str, token: str | None):
        assert url == "https://api.github.com/repos/juanwan99/edu-cloud/issues/comments/1234567890"
        assert token == "token"
        return _matching_review_comment(url, token)

    errors, warnings = validate_event_with_warnings(
        _event(body=_valid_body()),
        verify_mode="warn",
        github_token="token",
        fetch_comment=fetch_comment,
    )

    assert errors == []
    assert warnings == []


def test_model_declarations_warn_cases_without_blocking():
    cases = [
        (_valid_body(), False, []),
        (
            _valid_body().replace("Worker-Model: codex-gpt-5\nReviewer-Model: claude-sonnet-4.5\n", ""),
            False,
            [
                "Worker-Model declaration is missing or placeholder",
                "Reviewer-Model declaration is missing or placeholder",
            ],
        ),
        (
            _valid_body().replace("Reviewer-Model: claude-sonnet-4.5", "Reviewer-Model: codex-gpt-5"),
            False,
            ["Worker-Model and Reviewer-Model should differ for independent review"],
        ),
        (
            _valid_body().replace("Worker-Model: codex-gpt-5\nReviewer-Model: claude-sonnet-4.5\n", ""),
            True,
            [],
        ),
    ]
    for body, draft, expected_warnings in cases:
        errors, warnings = validate_event_with_warnings(
            _event(body=body, draft=draft),
            verify_mode="warn",
            fetch_comment=_matching_review_comment,
        )
        assert errors == []
        for expected in expected_warnings:
            assert expected in warnings
        if not expected_warnings:
            assert warnings == []


def test_independent_review_issue_comment_api_warns_on_wrong_pr_short_body_and_missing_pass():
    def fetch_comment(_url: str, _token: str | None):
        return {
            "issue_url": "https://api.github.com/repos/juanwan99/edu-cloud/issues/100",
            "user": {"login": "reviewer"},
            "body": "looked good",
        }

    errors, warnings = validate_event_with_warnings(
        _event(body=_valid_body()),
        verify_mode="warn",
        fetch_comment=fetch_comment,
    )

    assert errors == []
    assert "review evidence comment does not belong to this pull request" in warnings
    assert "review evidence comment body is shorter than 200 characters" in warnings
    assert "review evidence comment body must include 'Verdict: PASS'" in warnings


def test_independent_review_issue_comment_api_warns_when_comment_author_is_pr_author():
    def fetch_comment(_url: str, _token: str | None):
        return {
            "issue_url": "https://api.github.com/repos/juanwan99/edu-cloud/issues/99",
            "user": {"login": "juanwan99"},
            "body": ("review evidence " * 20) + "\nVerdict: PASS\n",
        }

    _errors, warnings = validate_event_with_warnings(
        _event(body=_valid_body()),
        verify_mode="warn",
        fetch_comment=fetch_comment,
    )

    assert "review evidence comment author is the pull request author" in warnings


def test_independent_review_issue_comment_api_enforce_turns_warnings_into_errors():
    def fetch_comment(_url: str, _token: str | None):
        return {
            "issue_url": "https://api.github.com/repos/juanwan99/edu-cloud/issues/99",
            "user": {"login": "juanwan99"},
            "body": "Verdict: PASS",
        }

    errors, warnings = validate_event_with_warnings(
        _event(body=_valid_body()),
        verify_mode="enforce",
        fetch_comment=fetch_comment,
    )

    assert warnings == []
    assert any(error.startswith("Independent Review evidence verification failed:") for error in errors)


def test_scope_placeholder_fails():
    body = _valid_body().replace("Steward-Scope: demo", "Steward-Scope: REQUIRED")

    errors = validate_event(_event(body=body))

    assert "PR body must replace Steward-Scope: REQUIRED with the exact scope id" in errors


def test_missing_codex_dispatch_review_evidence_fails():
    body = _valid_body().replace("Codex-Dispatch-Review: CDR-2026-06-29-demo\n", "")

    errors = validate_event(_event(body=body))

    assert "PR body must declare Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>" in errors


def test_codex_dispatch_review_placeholder_fails():
    body = _valid_body().replace(
        "Codex-Dispatch-Review: CDR-2026-06-29-demo",
        "Codex-Dispatch-Review: REQUIRED",
    )

    errors = validate_event(_event(body=body))

    assert "PR body must replace Codex-Dispatch-Review: REQUIRED with review evidence" in errors


def test_malformed_codex_dispatch_review_evidence_fails():
    body = _valid_body().replace(
        "Codex-Dispatch-Review: CDR-2026-06-29-demo",
        "Codex-Dispatch-Review: looked-good",
    )

    errors = validate_event(_event(body=body))

    assert any("Codex-Dispatch-Review must be" in error for error in errors)


def test_github_comment_url_evidence_passes():
    body = _valid_body().replace(
        "Codex-Dispatch-Review: CDR-2026-06-29-demo",
        "Codex-Dispatch-Review: https://github.com/juanwan99/edu-cloud/pull/99#issuecomment-1234567890",
    )

    assert validate_event(_event(body=body)) == []


def test_missing_integration_lane_fails():
    body = _valid_body().replace("Integration-Lane: guarded\n", "")

    errors = validate_event(_event(body=body))

    assert "PR body must declare Integration-Lane: independent|guarded|exclusive" in errors


def test_integration_lane_placeholder_fails():
    body = _valid_body().replace("Integration-Lane: guarded", "Integration-Lane: REQUIRED")

    errors = validate_event(_event(body=body))

    assert "PR body must replace Integration-Lane: REQUIRED with independent, guarded, or exclusive" in errors


def test_malformed_integration_lane_fails():
    body = _valid_body().replace("Integration-Lane: guarded", "Integration-Lane: parallel")

    errors = validate_event(_event(body=body))

    assert "Integration-Lane must be one of: independent, guarded, exclusive" in errors


def test_missing_write_license_fails():
    body = _valid_body().replace(
        "Write-License: draft PR creation allowed; CI self-fix not allowed; stop after draft PR.\n",
        "",
    )

    errors = validate_event(_event(body=body))

    assert (
        "PR body must declare Write-License with draft PR permission, CI self-fix permission, and stop condition"
        in errors
    )


def test_write_license_placeholder_fails():
    body = _valid_body().replace(
        "Write-License: draft PR creation allowed; CI self-fix not allowed; stop after draft PR.",
        "Write-License: REQUIRED",
    )

    errors = validate_event(_event(body=body))

    assert "PR body must replace Write-License: REQUIRED with the actual write license" in errors


def test_write_license_missing_terms_fails():
    body = _valid_body().replace(
        "Write-License: draft PR creation allowed; CI self-fix not allowed; stop after draft PR.",
        "Write-License: draft PR creation allowed.",
    )

    errors = validate_event(_event(body=body))

    assert "Write-License must state CI self-fix permission" in errors
    assert "Write-License must state stop condition" in errors


def test_cli_reports_errors(tmp_path: Path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps(_event(body="Steward-Scope: demo\n")), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/governance/check_dispatch_review.py", "--event", str(event)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "dispatch review error" in result.stderr


def test_cli_prints_integration_lane_from_crlf_body(tmp_path: Path):
    event = tmp_path / "event.json"
    event.write_text(json.dumps(_event(body=_valid_body().replace("\n", "\r\n"))), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/check_dispatch_review.py",
            "--event",
            str(event),
            "--print-integration-lane",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "guarded"
