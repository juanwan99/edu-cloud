"""Tests for the Keel dispatch review gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.governance.check_dispatch_review import validate_event


def _event(*, body: str, branch: str = "keel/demo-2026-06-29"):
    return {
        "pull_request": {
            "body": body,
            "head": {"ref": branch},
        }
    }


def _valid_body() -> str:
    return """Steward-Scope: demo
Codex-Dispatch-Review: CDR-2026-06-29-demo

## Summary

## Dispatch Review

- [x] Codex Dispatch Review evidence above was completed before implementation.
- [x] Branch was created from latest `origin/master`; no stale worktree or branch was reused.
- [x] Added one fresh scope file under `control/steward/scopes/`.
- [x] Changed files stay inside scope `allowed_paths`; no `forbidden_paths` were touched.
- [x] For file deletion or retirement, reachability was checked across `scripts/`, `tests/`, `.github/workflows/`, active docs, and governance registries.
"""


def test_valid_dispatch_review_passes():
    assert validate_event(_event(body=_valid_body())) == []


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
