"""Tests for the neutral Steward PR scope gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from scripts.governance.steward_scope_gate import (
    resolve_scope_id,
    scope_check,
    validate_scope,
)


def _scope(**overrides):
    data = {
        "schema": "steward-pr-scope.v1",
        "scope_id": "demo",
        "owner": "codex",
        "allowed_paths": ["docs/governance/", "scripts/governance/steward_scope_gate.py"],
        "forbidden_paths": [".yuanqi/"],
        "compatibility_paths": [],
        "status": "active",
        "created_at": "2026-06-28T00:00:00+08:00",
        "expires_at": "2026-07-05T00:00:00+08:00",
    }
    data.update(overrides)
    return data


def test_resolve_scope_id_from_pr_body(tmp_path: Path):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"body": "hello\nSteward-Scope: demo\n"}}),
        encoding="utf-8",
    )

    assert resolve_scope_id(str(event)) == "demo"


def test_resolve_scope_id_accepts_utf8_bom_event(tmp_path: Path):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"body": "Steward-Scope: demo\n"}}),
        encoding="utf-8-sig",
    )

    assert resolve_scope_id(str(event)) == "demo"


def test_scope_check_accepts_declared_prefix():
    ok, violations = scope_check(["docs/governance/steward-hard-gates.md"], _scope())

    assert ok
    assert violations == []


def test_scope_check_rejects_out_of_scope_path():
    ok, violations = scope_check(["src/edu_cloud/core/auth.py"], _scope())

    assert not ok
    assert violations == ["src/edu_cloud/core/auth.py"]


def test_scope_check_rejects_forbidden_path_even_when_allowed():
    scope = _scope(allowed_paths=["docs/", ".yuanqi/"], forbidden_paths=[".yuanqi/"])

    ok, violations = scope_check([".yuanqi/tasks/demo.yml"], scope)

    assert not ok
    assert violations == [".yuanqi/tasks/demo.yml"]


def test_allowed_paths_rejects_legacy_yuanqi_path():
    errors = validate_scope(_scope(allowed_paths=[".yuanqi/tasks/demo.yml"]))

    assert "allowed_paths must not contain legacy Yuanqi path: .yuanqi/tasks/demo.yml" in errors


def test_cli_rejects_missing_steward_scope(tmp_path: Path):
    event = tmp_path / "event.json"
    changed = tmp_path / "changed-files.txt"
    scopes_dir = tmp_path / "scopes"
    scopes_dir.mkdir()
    event.write_text(json.dumps({"pull_request": {"body": ""}}), encoding="utf-8")
    changed.write_text("docs/governance/steward-hard-gates.md\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/steward_scope_gate.py",
            "--event",
            str(event),
            "--changed",
            str(changed),
            "--scopes-dir",
            str(scopes_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "PR must declare Steward-Scope: <id>" in result.stderr


def test_cli_rejects_closed_scope(tmp_path: Path):
    event = tmp_path / "event.json"
    changed = tmp_path / "changed-files.txt"
    scopes_dir = tmp_path / "scopes"
    scopes_dir.mkdir()
    (scopes_dir / "demo.yml").write_text(
        yaml.safe_dump(_scope(status="closed"), sort_keys=False),
        encoding="utf-8",
    )
    event.write_text(
        json.dumps({"pull_request": {"body": "Steward-Scope: demo\n"}}),
        encoding="utf-8",
    )
    changed.write_text("docs/governance/steward-hard-gates.md\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/steward_scope_gate.py",
            "--event",
            str(event),
            "--changed",
            str(changed),
            "--scopes-dir",
            str(scopes_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "scope status must be active for PR validation" in result.stderr


def test_cli_rejects_scope_file_not_changed(tmp_path: Path):
    event = tmp_path / "event.json"
    changed = tmp_path / "changed-files.txt"
    scopes_dir = tmp_path / "scopes"
    scopes_dir.mkdir()
    (scopes_dir / "demo.yml").write_text(
        yaml.safe_dump(_scope(), sort_keys=False),
        encoding="utf-8",
    )
    event.write_text(
        json.dumps({"pull_request": {"body": "Steward-Scope: demo\n"}}),
        encoding="utf-8",
    )
    changed.write_text("docs/governance/steward-hard-gates.md\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/steward_scope_gate.py",
            "--event",
            str(event),
            "--changed",
            str(changed),
            "--scopes-dir",
            str(scopes_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "declared scope file must be changed in the PR" in result.stderr


def test_cli_rejects_scope_file_modified_instead_of_added(tmp_path: Path):
    event = tmp_path / "event.json"
    changed = tmp_path / "changed-files.txt"
    scopes_dir = tmp_path / "scopes"
    scopes_dir.mkdir()
    scope_file = scopes_dir / "demo.yml"
    scope_file.write_text(
        yaml.safe_dump(_scope(), sort_keys=False),
        encoding="utf-8",
    )
    event.write_text(
        json.dumps({"pull_request": {"body": "Steward-Scope: demo\n"}}),
        encoding="utf-8",
    )
    changed.write_text(f"M\t{scope_file}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/governance/steward_scope_gate.py",
            "--event",
            str(event),
            "--changed",
            str(changed),
            "--scopes-dir",
            str(scopes_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "declared scope file must be newly added in the PR" in result.stderr
