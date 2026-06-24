from scripts.yuanqi.overlap_gate import check


def _task(task_id, module, **overrides):
    task = {
        "task_id": task_id,
        "mode": "module_writer",
        "owner": "claude",
        "allowed_paths": [f"src/edu_cloud/modules/{module}/**"],
        "exclusive_claims": [],
        "status": "active",
    }
    task.update(overrides)
    return task


def test_different_module_locks_allow():
    candidate = _task("candidate", "grading")
    active = [_task("active-knowledge", "knowledge")]

    assert check(candidate, active) == ("allow", [])


def test_same_module_locks_deny():
    candidate = _task("candidate", "grading")
    active = [_task("active-grading", "grading")]

    decision, conflicts = check(candidate, active)

    assert decision == "deny"
    assert conflicts == [
        {
            "task_id": "active-grading",
            "paths": ["src/edu_cloud/modules/grading/**"],
        }
    ]


def test_shared_layer_changed_path_overlap_denies():
    shared_path = "src/edu_cloud/services/effective_scores.py"
    candidate = _task(
        "candidate",
        "grading",
        changed_paths=[shared_path],
    )
    active = [
        _task(
            "active-knowledge",
            "knowledge",
            changed_paths=[shared_path],
        )
    ]

    decision, conflicts = check(candidate, active)

    assert decision == "deny"
    assert conflicts == [{"task_id": "active-knowledge", "paths": [shared_path]}]


def test_empty_read_only_lockset_allows_against_writer():
    candidate = {
        "task_id": "candidate",
        "mode": "read_only_audit",
        "owner": "codex",
        "allowed_paths": [],
        "exclusive_claims": [],
        "status": "active",
    }
    active = [_task("active-grading", "grading")]

    assert check(candidate, active) == ("allow", [])
