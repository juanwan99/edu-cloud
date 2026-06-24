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
