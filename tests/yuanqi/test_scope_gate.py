import os
import subprocess
import sys

from scripts.yuanqi.scope_gate import scope_check


def _task(**overrides):
    task = {
        "task_id": "yq-20260624-scope",
        "mode": "module_writer",
        "owner": "claude",
        "allowed_paths": ["src/edu_cloud/modules/grading/**"],
        "exclusive_claims": [],
        "status": "active",
        "created_at": "2026-06-24T18:00:00+08:00",
        "expires_at": "2026-06-25T18:00:00+08:00",
    }
    task.update(overrides)
    return task


def test_changed_files_inside_allowed_paths_pass():
    ok, violations = scope_check(
        ["src/edu_cloud/modules/grading/rubric.py"],
        _task(),
    )

    assert ok is True
    assert violations == []


def test_changed_file_outside_allowed_paths_fails():
    outside = "src/edu_cloud/modules/scan/x.py"

    ok, violations = scope_check([outside], _task())

    assert ok is False
    assert violations == [outside]


def test_changed_files_inside_exclusive_claim_paths_pass():
    ok, violations = scope_check(
        ["alembic/versions/20260624_scope_gate.py"],
        _task(
            mode="exclusive",
            allowed_paths=[],
            exclusive_claims=["db_migration"],
        ),
    )

    assert ok is True
    assert violations == []


def test_own_task_file_is_control_plane_exception():
    ok, violations = scope_check(
        [".yuanqi/tasks/yq-20260624-scope.yml"],
        _task(),
    )

    assert ok is True
    assert violations == []


def test_other_task_file_remains_out_of_scope():
    outside = ".yuanqi/tasks/yq-20260624-other.yml"

    ok, violations = scope_check([outside], _task())

    assert ok is False
    assert violations == [outside]


def test_scope_gate_cli_rejects_out_of_scope_changed_file(tmp_path):
    outside = "src/edu_cloud/modules/scan/x.py"
    task_path = tmp_path / "yq-20260624-scope.yml"
    changed_path = tmp_path / "changed-files.txt"
    task_path.write_text(_yaml(_task()), encoding="utf-8")
    changed_path.write_text(outside + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/yuanqi/scope_gate.py",
            "--task",
            str(task_path),
            "--changed",
            str(changed_path),
        ],
        capture_output=True,
        env={**os.environ, "PYTHONPATH": os.getcwd()},
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "scope violations:" in result.stderr
    assert outside in result.stderr


def _yaml(task):
    lines = []
    for key, value in task.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f'{key}: "{value}"')
    return "\n".join(lines) + "\n"
