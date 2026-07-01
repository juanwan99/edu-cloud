"""Tests for the neutral Steward PR scope gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from scripts.governance.steward_scope_gate import (
    _is_scope_closeout_shape,
    _looks_like_name_status,
    _scope_closeout_errors,
    _scope_enforced_paths,
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
        "forbidden_paths": [".yuanqi/", "scripts/yuanqi/", "tests/yuanqi/"],
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


def test_resolve_scope_id_accepts_utf8_bom_in_body(tmp_path: Path):
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"body": "\ufeffSteward-Scope: demo\n"}}),
        encoding="utf-8",
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


def test_allowed_paths_rejects_legacy_yuanqi_script_path():
    errors = validate_scope(_scope(allowed_paths=["scripts/yuanqi/check.py"]))

    assert "allowed_paths must not contain legacy Yuanqi path: scripts/yuanqi/check.py" in errors


def test_validate_scope_accepts_missing_legacy_yuanqi_forbidden_paths():
    errors = validate_scope(_scope(forbidden_paths=[".yuanqi/"]))

    assert errors == []


def test_scope_check_rejects_legacy_yuanqi_path_by_default_forbidden_scope():
    scope = _scope(allowed_paths=["scripts/"], forbidden_paths=[])

    ok, violations = scope_check(["scripts/yuanqi/foo.py"], scope)

    assert not ok
    assert violations == ["scripts/yuanqi/foo.py"]


def test_scope_enforced_paths_exempts_legacy_yuanqi_deletions():
    changed_entries = [
        ("D", "scripts/yuanqi/foo.py"),
        ("M", "scripts/governance/steward_scope_gate.py"),
    ]

    assert _scope_enforced_paths(changed_entries) == [
        "scripts/governance/steward_scope_gate.py",
    ]


def test_allowed_paths_has_small_count_limit():
    errors = validate_scope(_scope(allowed_paths=[f"docs/path-{i}.md" for i in range(21)]))

    assert "allowed_paths must contain at most 20 entries" in errors


def test_owner_must_be_known():
    errors = validate_scope(_scope(owner="mallory"))

    assert "owner must be one of: claude, codex, liang" in errors


def test_active_scope_rejects_expired_expires_at():
    errors = validate_scope(_scope(expires_at="2020-01-01T00:00:00+00:00"))

    assert "active scope expires_at must be in the future" in errors


def test_scope_rejects_invalid_expires_at():
    errors = validate_scope(_scope(expires_at="not-a-date"))

    assert "expires_at must be an ISO 8601 datetime" in errors


def test_scope_status_parser_rejects_invalid_b_status():
    assert not _looks_like_name_status("B")


def test_scope_closeout_shape_requires_only_modified_declared_scope():
    scope_relpath = "control/steward/scopes/demo.yml"

    assert _is_scope_closeout_shape([("M", scope_relpath)], scope_relpath)
    assert not _is_scope_closeout_shape([("A", scope_relpath)], scope_relpath)
    assert not _is_scope_closeout_shape(
        [("M", scope_relpath), ("M", "scripts/governance/steward_scope_gate.py")],
        scope_relpath,
    )


def test_scope_closeout_allows_only_status_active_to_closed():
    scope_relpath = "control/steward/scopes/demo.yml"
    errors = _scope_closeout_errors(
        _scope(status="closed"),
        _scope(status="active"),
        scope_relpath,
    )

    assert errors == []


def test_scope_closeout_rejects_other_field_changes():
    scope_relpath = "control/steward/scopes/demo.yml"
    errors = _scope_closeout_errors(
        _scope(status="closed", allowed_paths=["docs/"]),
        _scope(status="active"),
        scope_relpath,
    )

    assert f"scope closeout may only change status active -> closed: {scope_relpath}" in errors


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


def test_cli_rejects_legacy_yuanqi_path_without_explicit_forbidden_path(tmp_path: Path):
    repo_root = Path.cwd()
    event = tmp_path / "event.json"
    changed = tmp_path / "changed-files.txt"
    scopes_dir = tmp_path / "control" / "steward" / "scopes"
    scopes_dir.mkdir(parents=True)
    scope_file = scopes_dir / "demo.yml"
    scope_relpath = Path("control/steward/scopes/demo.yml")
    scope_file.write_text(
        yaml.safe_dump(
            _scope(
                allowed_paths=[str(scope_relpath), "scripts/"],
                forbidden_paths=[],
            ),
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    event.write_text(
        json.dumps({"pull_request": {"body": "Steward-Scope: demo\n"}}),
        encoding="utf-8",
    )
    changed.write_text(
        f"A\t{scope_relpath}\nM\tscripts/yuanqi/foo.py\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts/governance/steward_scope_gate.py"),
            "--event",
            str(event),
            "--changed",
            str(changed),
            "--scopes-dir",
            "control/steward/scopes",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "scope violations:" in result.stderr
    assert "scripts/yuanqi/foo.py" in result.stderr
