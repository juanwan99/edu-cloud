#!/usr/bin/env python3
"""Fail-closed execution policy checks for CI cost and governance fallback risk."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = PROJECT_ROOT / "control" / "execution_policy.yaml"
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "test.yml"
MODULE_GUARD_PATH = PROJECT_ROOT / "scripts" / "governance" / "module_governance_guard.py"


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(PROJECT_ROOT)} must contain a YAML mapping")
    return data


def _as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def check_policy(policy: dict[str, Any], errors: list[str]) -> None:
    _require(policy.get("schema") == "edu.execution-policy.v1", "invalid execution policy schema", errors)

    ci = policy.get("ci_cost_control")
    _require(isinstance(ci, dict), "ci_cost_control is required", errors)
    if isinstance(ci, dict):
        _require(ci.get("local_first_required") is True, "CI policy must require local-first checks", errors)
        _require(
            ci.get("github_actions_role") == "post_push_external_final_gate",
            "GitHub Actions role must be final external gate, not routine iteration runner",
            errors,
        )
        _require(set(_as_list(ci.get("expensive_jobs"))) == {"backend", "frontend"}, "backend/frontend must be marked expensive", errors)
        change = ci.get("change_detection")
        _require(isinstance(change, dict), "change_detection policy is required", errors)
        if isinstance(change, dict):
            _require(change.get("job") == "changes", "change detection job must be named changes", errors)
            _require(change.get("fail_closed") is True, "change detection must fail closed", errors)
            _require(change.get("no_shell_error_masking") is True, "change detection must forbid shell error masking", errors)
        rerun = ci.get("manual_rerun")
        _require(isinstance(rerun, dict), "manual_rerun policy is required", errors)
        if isinstance(rerun, dict):
            _require(rerun.get("allowed_by_default") is False, "manual CI rerun must not be allowed by default", errors)

    fallback = policy.get("fallback_control")
    _require(isinstance(fallback, dict), "fallback_control is required", errors)
    if isinstance(fallback, dict):
        _require(fallback.get("silent_fallback") == "forbidden", "silent fallback must be forbidden", errors)
        _require(fallback.get("unknown_evidence") == "fail_closed", "unknown evidence must fail closed", errors)
        _require(
            fallback.get("worktree_as_staged_backup") == "forbidden",
            "worktree cannot be used as a backup for staged evidence",
            errors,
        )

    review = ((policy.get("review_policy") or {}).get("high_risk_governance_change") or {})
    _require(review.get("required") is True, "high-risk governance changes require review", errors)
    _require(review.get("review_type") == "code_review", "high-risk governance review_type must be code_review", errors)
    _require(review.get("reviewer_must_be_non_author") is True, "high-risk governance reviewer must be non-author", errors)


def check_workflow(workflow: dict[str, Any], text: str, errors: list[str]) -> None:
    _require("|| true" not in text, "CI workflow must not mask command failure with '|| true'", errors)
    _require("continue-on-error: true" not in text, "CI workflow must not use continue-on-error", errors)
    _require("Unable to resolve base commit" in text, "CI path filter must fail closed on missing base commit", errors)
    _require("Unable to resolve head commit" in text, "CI path filter must fail closed on missing head commit", errors)

    _require((workflow.get("concurrency") or {}).get("cancel-in-progress") is True, "CI concurrency must cancel in-progress runs", errors)
    jobs = workflow.get("jobs") or {}
    _require("changes" in jobs, "CI workflow must include a changes job", errors)
    _require("governance" in jobs, "CI workflow must include a governance job", errors)
    _require("backend" in jobs and "frontend" in jobs, "CI workflow must include backend and frontend jobs", errors)

    changes = jobs.get("changes") or {}
    outputs = changes.get("outputs") or {}
    _require(bool(outputs.get("backend")), "changes job must output backend decision", errors)
    _require(bool(outputs.get("frontend")), "changes job must output frontend decision", errors)

    backend = jobs.get("backend") or {}
    frontend = jobs.get("frontend") or {}
    _require(backend.get("needs") == "changes", "backend job must depend on changes job", errors)
    _require(frontend.get("needs") == "changes", "frontend job must depend on changes job", errors)
    _require(backend.get("if") == "needs.changes.outputs.backend == 'true'", "backend job must be path-gated", errors)
    _require(frontend.get("if") == "needs.changes.outputs.frontend == 'true'", "frontend job must be path-gated", errors)

    governance = jobs.get("governance") or {}
    _require("needs" not in governance, "governance job must not be hidden behind path detection", errors)
    _require("if" not in governance, "governance job must not be conditionally skipped", errors)
    _require("scripts/governance/check_execution_policy.py" in text, "governance job must run execution policy gate", errors)


def check_module_guard(text: str, errors: list[str]) -> None:
    _require("snap = real_repo" not in text, "module governance guard must not fall back from staged snapshot to worktree", errors)
    _require("无法导出 staged index" in text, "module governance guard must block when staged snapshot export fails", errors)
    _require("aggregate_modules 不可用" in text, "module governance guard must block when aggregate_modules is unavailable", errors)


def main() -> int:
    errors: list[str] = []
    policy = _load_yaml(POLICY_PATH)
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    workflow = _load_yaml(WORKFLOW_PATH)
    module_guard_text = MODULE_GUARD_PATH.read_text(encoding="utf-8")

    check_policy(policy, errors)
    check_workflow(workflow, workflow_text, errors)
    check_module_guard(module_guard_text, errors)

    if errors:
        print("execution policy check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print("execution policy check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
