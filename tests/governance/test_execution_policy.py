"""Execution policy regression tests."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_execution_policy_gate_passes():
    result = subprocess.run(
        [sys.executable, "scripts/governance/check_execution_policy.py"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "execution policy check ok" in result.stdout


def test_execution_policy_declares_ci_cost_and_fail_closed_rules():
    policy = yaml.safe_load(
        (PROJECT_ROOT / "control" / "execution_policy.yaml").read_text(encoding="utf-8")
    )

    ci = policy["ci_cost_control"]
    fallback = policy["fallback_control"]

    assert ci["local_first_required"] is True
    assert ci["github_actions_role"] == "post_push_external_final_gate"
    assert set(ci["expensive_jobs"]) == {"backend", "frontend"}
    assert ci["change_detection"]["fail_closed"] is True
    assert ci["manual_rerun"]["allowed_by_default"] is False
    assert fallback["silent_fallback"] == "forbidden"
    assert fallback["unknown_evidence"] == "fail_closed"
    assert fallback["worktree_as_staged_backup"] == "forbidden"


def test_ci_workflow_does_not_mask_path_filter_failures():
    text = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    assert "|| true" not in text
    assert "continue-on-error: true" not in text
    assert "Unable to resolve base commit" in text
    assert "Unable to resolve head commit" in text
    assert "scripts/governance/check_execution_policy.py" in text
