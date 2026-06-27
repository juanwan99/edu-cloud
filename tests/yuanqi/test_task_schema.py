from pathlib import Path
import subprocess
import sys

import pytest

from scripts.yuanqi.task_schema import load_and_validate, validate_task


EXAMPLES_DIR = Path(__file__).resolve().parents[2] / ".yuanqi" / "tasks" / "examples"


def _valid_task(**overrides):
    task = {
        "task_id": "yq-20260624-test",
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


@pytest.mark.parametrize(
    "filename",
    [
        "module_writer.yml",
        "exclusive.yml",
        "read_only_audit.yml",
    ],
)
def test_examples_validate(filename):
    data, errors = load_and_validate(EXAMPLES_DIR / filename)

    assert data["task_id"]
    assert errors == []


def test_validate_task_requires_task_id():
    task = _valid_task()
    task.pop("task_id")

    errors = validate_task(task)

    assert "task_id must be a non-empty string" in errors


def test_validate_task_rejects_bad_mode():
    errors = validate_task(_valid_task(mode="writer"))

    assert (
        "mode must be one of: read_only_audit, planning_only, docs_local, "
        "frontend_only, module_writer, integration_writer, exclusive"
    ) in errors


def test_validate_task_rejects_invalid_status():
    errors = validate_task(_valid_task(status="running"))

    assert "status must be one of: active, closed" in errors


def test_validate_task_rejects_unknown_fields():
    errors = validate_task(_valid_task(evil_field="self-issued-pass"))

    assert "unknown fields: evil_field" in errors


def test_validate_task_rejects_human_waiver_field():
    errors = validate_task(_valid_task(human_waiver=True))

    assert "unknown fields: human_waiver" in errors


def test_validate_task_rejects_control_plane_allowed_paths():
    errors = validate_task(_valid_task(allowed_paths=[".yuanqi/tasks/**"]))

    assert "allowed_paths contains forbidden control-plane path: .yuanqi/tasks/**" in errors

def test_validate_task_accepts_registry_closeouts_list():
    errors = validate_task(_valid_task(registry_closeouts=["yq-20260625-old-task"]))

    assert errors == []


def test_validate_task_rejects_invalid_registry_closeouts():
    errors = validate_task(_valid_task(registry_closeouts="yq-20260625-old-task"))

    assert "registry_closeouts must be a list" in errors


@pytest.mark.parametrize(
    "allowed_path",
    [
        "",
        ".",
        "*",
        "**",
        "./**",
        "/",
        "/src/edu_cloud/modules/grading",
        "../outside",
        "src/../outside",
    ],
)
def test_validate_task_rejects_root_or_escaping_allowed_paths(allowed_path):
    errors = validate_task(_valid_task(allowed_paths=[allowed_path]))

    assert (
        f"allowed_paths contains forbidden root or escaping path: {allowed_path}"
        in errors
    )


def test_task_schema_cli_accepts_valid_task(tmp_path):
    task = _valid_task()
    task_path = tmp_path / f"{task['task_id']}.yml"
    task_path.write_text(_yaml(task), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/yuanqi/task_schema.py", str(task_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0


def test_task_schema_cli_rejects_invalid_task(tmp_path):
    task = _valid_task(mode="writer")
    task_path = tmp_path / f"{task['task_id']}.yml"
    task_path.write_text(_yaml(task), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/yuanqi/task_schema.py", str(task_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "mode must be one of" in result.stderr


def test_task_schema_cli_rejects_task_id_filename_mismatch(tmp_path):
    task_path = tmp_path / "different-file.yml"
    task_path.write_text(_yaml(_valid_task()), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "scripts/yuanqi/task_schema.py", str(task_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "task_id must match filename stem" in result.stderr


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
