"""Codex-native migration script smoke tests."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PROJECT_ROOT / "scripts" / name), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )


def load_codex_verify_module():
    scripts_dir = PROJECT_ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    loader = SourceFileLoader("codex_verify", str(scripts_dir / "codex-verify"))
    spec = importlib.util.spec_from_loader("codex_verify", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codex_context_no_network_outputs_project_sections():
    result = run_script("codex-context", "--no-network")

    assert result.returncode == 0, result.stderr
    assert "Codex Context" in result.stdout
    assert "Dual-Core Control Plane" in result.stdout
    assert "Meta Core" in result.stdout
    assert "Guardian Core" in result.stdout
    assert "Git" in result.stdout
    assert "Dirty Summary" in result.stdout
    assert "Guardian Health" in result.stdout
    assert "overall:" in result.stdout
    assert "issues:" in result.stdout
    assert "Verification Baseline" in result.stdout


def test_dual_core_governance_model_is_active_context():
    model = PROJECT_ROOT / "docs" / "context" / "GOVERNANCE_MODEL.md"
    active_index = PROJECT_ROOT / "docs" / "context" / "ACTIVE_INDEX.md"
    agents = PROJECT_ROOT / "AGENTS.md"

    model_text = model.read_text(encoding="utf-8")
    assert "EduCloud Dual-Core Control Plane" in model_text
    assert "Meta Core" in model_text
    assert "Guardian Core" in model_text
    assert "Codex-led" in model_text
    assert "Claude-assisted" in model_text

    assert "docs/context/GOVERNANCE_MODEL.md" in active_index.read_text(encoding="utf-8")
    agents_text = agents.read_text(encoding="utf-8")
    assert "EduCloud Dual-Core Control Plane" in agents_text
    assert "Meta Core prevents task drift" in agents_text
    assert "Guardian Core prevents operational accidents" in agents_text


def test_codex_check_no_network_is_read_only_preflight():
    result = run_script("codex-check", "--no-network")

    assert result.returncode == 0, result.stderr
    assert "Codex Check" in result.stdout
    assert "Start Here" in result.stdout
    assert "Safety Risks" in result.stdout


def test_codex_verify_help_lists_supported_modes():
    result = run_script("codex-verify", "--help")

    assert result.returncode == 0
    for mode in ("frontend", "backend", "schema", "safety", "full"):
        assert mode in result.stdout


def test_arq_worker_runner_and_systemd_template_are_present():
    runner = PROJECT_ROOT / "scripts" / "run-arq-worker"
    unit = PROJECT_ROOT / "deploy" / "systemd" / "edu-cloud-worker.service"

    runner_text = runner.read_text(encoding="utf-8")
    unit_text = unit.read_text(encoding="utf-8")

    assert "edu_cloud.worker" in runner_text
    assert "WorkerSettings" in runner_text
    assert "job_timeout" in runner_text
    assert "ExecStart=/home/ops/projects/edu-cloud/.venv/bin/python /home/ops/projects/edu-cloud/scripts/run-arq-worker" in unit_text
    assert "Restart=on-failure" in unit_text


def test_frontend_dev_server_binds_loopback_by_default():
    config = (PROJECT_ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

    assert "host: '127.0.0.1'" in config
    assert "host: '0.0.0.0'" not in config


def test_codex_consult_claude_help_lists_read_only_modes():
    result = run_script("codex-consult-claude", "--help")

    assert result.returncode == 0
    assert "read-only Claude Code auxiliary reviewer" in result.stdout
    for mode in ("review", "design", "history", "tests", "risk", "question"):
        assert mode in result.stdout


def test_codex_consult_claude_dry_run_is_read_only_and_stateless():
    result = run_script("codex-consult-claude", "--dry-run", "review", "check migration gates")

    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert "claude -p" in output
    assert "--no-session-persistence" in output
    assert "--permission-mode plan" in output
    assert "--tools Read,Grep,Glob,LS" in output
    assert "--disallowedTools Bash,Edit,Write,MultiEdit,NotebookEdit" in output
    assert "--add-dir " in output
    assert str(PROJECT_ROOT) in output
    assert "--continue" not in output
    assert "--resume" not in output
    assert "dangerously-skip-permissions" not in output


def test_codex_consult_claude_system_prompt_preserves_codex_authority():
    result = run_script("codex-consult-claude", "--print-system-prompt")

    assert result.returncode == 0
    assert "Codex is the orchestrator" in result.stdout
    assert "AGENTS.md is authoritative" in result.stdout
    assert "CLAUDE.md is historical" in result.stdout
    assert "Do not edit files" in result.stdout


def test_codex_verify_backend_target_args_are_marked_partial():
    result = run_script(
        "codex-verify",
        "backend",
        "--dry-run",
        "--",
        "tests/governance/test_codex_scripts.py",
        "-q",
    )

    assert result.returncode == 0
    assert "scripts/pytest_delta.py --ff tests/governance/test_codex_scripts.py -q" in result.stdout


def test_codex_verify_frontend_dry_run_lists_version_alignment_gate():
    result = run_script("codex-verify", "frontend", "--dry-run", "--allow-dirty-build")

    assert result.returncode == 0
    assert "frontend version alignment" in result.stdout
    assert "https://mcu.asia/version.json" in result.stdout


def test_frontend_version_alignment_reports_hash_and_dirty_errors():
    module = load_codex_verify_module()

    errors = module.frontend_version_alignment_errors(
        local={"git_hash": "abc123", "source_dirty": True},
        remote={"git_hash": "def456"},
        head="abc123",
        allow_dirty_build=False,
    )

    assert "local dist/version.json has source_dirty=true" in errors
    assert "remote version.json git_hash def456 does not match local dist abc123" in errors


def test_truth_status_returns_nonzero_when_diagnosis_is_broken(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "frontend" / "src").mkdir(parents=True)
    (project / "frontend" / "dist").mkdir(parents=True)
    (project / "src").mkdir()
    (project / "frontend" / "src" / "main.js").write_text("console.log('x')\n", encoding="utf-8")
    (project / "frontend" / "index.html").write_text("<div></div>\n", encoding="utf-8")
    (project / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    (project / "frontend" / "dist" / "index.html").write_text("<div></div>\n", encoding="utf-8")
    (project / "frontend" / "dist" / "version.json").write_text(
        '{"git_hash":"stale","build_time":"2026-05-06T00:00:00Z","source_dirty":false}\n',
        encoding="utf-8",
    )

    subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        """#!/usr/bin/env bash
args="$*"
if [[ "$args" == *"-w"* ]]; then
  printf "200"
elif [[ "$args" == *"mcu.asia/version.json"* ]]; then
  printf '{"git_hash":"stale"}'
elif [[ "$args" == *"127.0.0.1:9000"* ]]; then
  printf '{"git_hash":"stale","boot_time":"test","pid":1}'
fi
""",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"

    result = subprocess.run(
        [str(PROJECT_ROOT / "scripts" / "truth-status.sh"), str(project)],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert "BROKEN AT:" in result.stdout


def test_truth_doctor_json_outputs_guardian_issue_action_schema():
    result = run_script("truth", "doctor", "--json")

    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["schema"] == "guardian.doctor.v1"
    assert data["overall"] in {"green", "yellow", "red"}
    assert isinstance(data["issues"], list)
    assert isinstance(data["actions"], list)
    for issue in data["issues"]:
        assert {"issue_code", "severity", "summary", "blocks_completion", "command_hint"} <= set(issue)
    for action in data["actions"]:
        assert {"issue_code", "required_before", "command_hint", "blocks_completion"} <= set(action)


def test_truth_doctor_json_does_not_flag_active_systemd_main_pid_as_ghost():
    systemd_pids = set()
    for service in ("edu-cloud", "llm-proxy", "edu-cloud-worker"):
        active = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if active.stdout.strip() != "active":
            continue
        pid = subprocess.run(
            ["systemctl", "show", service, "-p", "MainPID", "--value"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        value = pid.stdout.strip()
        if value and value != "0":
            systemd_pids.add(value)

    if not systemd_pids:
        return

    result = run_script("truth", "doctor", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    ghost_summaries = [
        issue["summary"]
        for issue in data["issues"]
        if issue["issue_code"] == "GHOST_PROCESS"
    ]
    for pid in systemd_pids:
        assert not any(f"PID={pid}" in summary for summary in ghost_summaries)


def test_safety_matrix_has_numbered_dual_core_rules():
    text = (PROJECT_ROOT / "docs" / "context" / "SAFETY_MATRIX.md").read_text(encoding="utf-8")

    assert "| ID | Risk | Source | Current Defense | Completion Evidence | Gap |" in text
    for rule_id in ("S-001", "S-002", "S-011", "S-012", "S-013"):
        assert rule_id in text
    assert "Fix-loop" in text
    assert "Evidence-less decisions" in text
    assert "Existing asset bypass" in text


def test_codex_verify_full_schema_dry_run_lists_schema_gate_once():
    result = run_script("codex-verify", "full", "--dry-run", "--schema", "--no-network", "--allow-dirty-build")

    assert result.returncode == 0
    assert result.stdout.count("scripts/db_doctor.py --strict") == 1
    assert "scripts/pytest_delta.py" in result.stdout
    assert "npm run build" in result.stdout


def test_codex_verify_safety_scans_changed_scripts():
    result = run_script("codex-verify", "safety")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Safety scan" in result.stdout


def test_codex_verify_safety_supports_repo_wide_scan():
    result = run_script("codex-verify", "safety", "--repo-wide")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "repo-wide secret/db-copy scan" in result.stdout


def test_ci_governance_job_runs_codex_smoke_checks():
    workflow = PROJECT_ROOT / ".github" / "workflows" / "test.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "governance:" in text
    for command in (
        "python -m py_compile scripts/codex_support.py scripts/codex-context scripts/codex-check scripts/codex-consult-claude scripts/codex-verify scripts/run-arq-worker",
        "python -m pytest tests/governance/test_codex_scripts.py -q",
        "scripts/codex-check --no-network",
        "scripts/codex-context --no-network",
        "scripts/codex-consult-claude --dry-run review CI smoke",
        "scripts/codex-verify safety --repo-wide",
        "scripts/codex-verify full --dry-run --schema --no-network",
        "python -m pytest tests/test_alembic_migration.py -q",
        "cd frontend && npm run build",
    ):
        assert command in text
