from pathlib import Path

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
