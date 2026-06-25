import subprocess
import sys

from scripts.yuanqi.overlap_gate import check


def _task(task_id, module, **overrides):
    task = {
        "task_id": task_id,
        "mode": "module_writer",
        "owner": "claude",
        "allowed_paths": [f"src/edu_cloud/modules/{module}/**"],
        "exclusive_claims": [],
        "status": "active",
        "created_at": "2026-06-24T18:00:00+08:00",
        "expires_at": "2026-06-25T18:00:00+08:00",
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


def test_overlap_gate_cli_allows_non_overlapping_tasks(tmp_path):
    candidate = _task("candidate-grading", "grading")
    active = _task("active-knowledge", "knowledge")
    candidate_path = tmp_path / "candidate.yml"
    active_path = tmp_path / "active.yml"
    candidate_path.write_text(_yaml(candidate), encoding="utf-8")
    active_path.write_text(_yaml(active), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/yuanqi/overlap_gate.py",
            "--candidate",
            str(candidate_path),
            "--tasks-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0


def test_overlap_gate_cli_denies_overlapping_tasks(tmp_path):
    candidate = _task("candidate-grading", "grading")
    active = _task("active-grading", "grading")
    candidate_path = tmp_path / "candidate.yml"
    active_path = tmp_path / "active.yml"
    candidate_path.write_text(_yaml(candidate), encoding="utf-8")
    active_path.write_text(_yaml(active), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/yuanqi/overlap_gate.py",
            "--candidate",
            str(candidate_path),
            "--tasks-dir",
            str(tmp_path),
            "--pr",
            "123",
            "--head",
            "abc123",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "active-grading" in result.stderr
    assert "src/edu_cloud/modules/grading/**" in result.stderr


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
