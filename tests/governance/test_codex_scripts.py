"""Codex-native migration script smoke tests."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
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


def load_codex_support_module():
    scripts_dir = PROJECT_ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    loader = SourceFileLoader("codex_support_test", str(scripts_dir / "codex_support.py"))
    spec = importlib.util.spec_from_loader("codex_support_test", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["codex_support_test"] = module
    spec.loader.exec_module(module)
    return module


def load_guardian_runtime_module():
    scripts_dir = PROJECT_ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    loader = SourceFileLoader("guardian_runtime_test", str(scripts_dir / "guardian_runtime.py"))
    spec = importlib.util.spec_from_loader("guardian_runtime_test", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["guardian_runtime_test"] = module
    spec.loader.exec_module(module)
    return module


def load_codex_consult_module():
    scripts_dir = PROJECT_ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    loader = SourceFileLoader("codex_consult_claude_test", str(scripts_dir / "codex-consult-claude"))
    spec = importlib.util.spec_from_loader("codex_consult_claude_test", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["codex_consult_claude_test"] = module
    spec.loader.exec_module(module)
    return module


def load_meta_runtime_module():
    scripts_dir = PROJECT_ROOT / "scripts"
    sys.path.insert(0, str(scripts_dir))
    loader = SourceFileLoader("meta_runtime_test", str(scripts_dir / "meta_runtime.py"))
    spec = importlib.util.spec_from_loader("meta_runtime_test", loader)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["meta_runtime_test"] = module
    spec.loader.exec_module(module)
    return module


def test_control_governance_policy_is_present_and_conservative():
    import yaml

    policy_path = PROJECT_ROOT / "control" / "governance.yaml"
    data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    governed = data["governed_paths"]
    high_risk = set(governed["high_risk"])
    low_risk = set(governed["low_risk"])

    assert high_risk
    assert isinstance(governed["low_risk"], list)
    assert {".github/**", "src/**", "frontend/src/**", "scripts/**", "tests/**"} <= high_risk
    assert {"docs/**", "README.md"} <= low_risk
    assert not (high_risk & low_risk)


def test_codex_context_no_network_outputs_project_sections():
    result = run_script("codex-context", "--no-network")

    assert result.returncode == 0, result.stderr
    assert "Codex Context" in result.stdout
    assert "双核治理" in result.stdout
    assert "Dual-Core Control Plane" not in result.stdout
    assert "Meta Core / 元控核" in result.stdout
    assert "Guardian Core / 守护核" in result.stdout
    assert "Claude read-only counter-review" in result.stdout
    assert "frontend/backend build-runtime consistency" in result.stdout
    assert "Git" in result.stdout
    assert "Dirty Summary" in result.stdout
    assert "Guardian Health" in result.stdout
    assert "overall:" in result.stdout
    assert "issues:" in result.stdout
    assert "Meta Runtime" in result.stdout
    assert "Guardian Runtime" in result.stdout
    assert "Verification Baseline" in result.stdout


def test_dual_core_governance_model_is_active_context():
    model = PROJECT_ROOT / "docs" / "context" / "GOVERNANCE_MODEL.md"
    active_index = PROJECT_ROOT / "docs" / "context" / "ACTIVE_INDEX.md"
    agents = PROJECT_ROOT / "AGENTS.md"

    model_text = model.read_text(encoding="utf-8")
    assert "双核治理" in model_text
    assert "EduCloud Dual-Core Control Plane" not in model_text
    assert "ECP-DualCore" not in model_text
    assert "Meta Core" in model_text
    assert "Guardian Core" in model_text
    assert "Meta Runtime" in model_text
    assert "Codex-led" in model_text
    assert "Claude-assisted" in model_text

    assert "docs/context/GOVERNANCE_MODEL.md" in active_index.read_text(encoding="utf-8")
    assert "docs/context/META_RUNTIME.md" in active_index.read_text(encoding="utf-8")
    agents_text = agents.read_text(encoding="utf-8")
    assert "双核治理" in agents_text
    assert "EduCloud Dual-Core Control Plane" not in agents_text
    assert "Meta Core / 元控核" in agents_text
    assert "Guardian Core / 守护核" in agents_text


def test_dual_core_responsibilities_are_formally_scoped():
    model_text = (PROJECT_ROOT / "docs" / "context" / "GOVERNANCE_MODEL.md").read_text(encoding="utf-8")
    agents_text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    meta_terms = [
        "direction",
        "facts",
        "task boundaries",
        "context",
        "Claude read-only counter-review",
        "completion evidence contract",
    ]
    guardian_terms = [
        "dirty state",
        "truthline",
        "DB/migration gates",
        "safety scanning",
        "frontend/backend build-runtime consistency",
        "environment hygiene",
    ]

    for text in (model_text, agents_text):
        for term in meta_terms:
            assert term in text
        for term in guardian_terms:
            assert term in text


def test_legacy_governance_name_has_no_old_active_doc_aliases():
    active_docs = [
        PROJECT_ROOT / "AGENTS.md",
        PROJECT_ROOT / "docs" / "context" / "GOVERNANCE_MODEL.md",
        PROJECT_ROOT / "docs" / "context" / "NOW.md",
        PROJECT_ROOT / "docs" / "context" / "ACTIVE_INDEX.md",
        PROJECT_ROOT / "docs" / "context" / "COMMANDS.md",
        PROJECT_ROOT / "docs" / "context" / "SAFETY_MATRIX.md",
    ]

    for path in active_docs:
        normalized = " ".join(path.read_text(encoding="utf-8").split())
        assert "双核治理" in normalized or path.name == "SAFETY_MATRIX.md"
        assert "EduCloud Dual-Core Control Plane" not in normalized
        assert "Dual-Core Control Plane" not in normalized
        assert "ECP-DualCore" not in normalized


def test_codex_check_no_network_is_read_only_preflight():
    result = run_script("codex-check", "--no-network")

    assert result.returncode == 0, result.stderr
    assert "Codex Check" in result.stdout
    assert "Start Here" in result.stdout
    assert "Safety Risks" in result.stdout


def test_codex_support_separates_active_sqlite_runtime(monkeypatch, tmp_path):
    module = load_codex_support_module()
    for name in ("edu_cloud.db-wal", "edu_cloud.db-shm", "data/.db_migrate.lock", ".codex"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        module,
        "path_has_open_handle",
        lambda path: path.name in {"edu_cloud.db-wal", "edu_cloud.db-shm"},
    )

    artifacts = module.collect_artifacts()

    assert artifacts["runtime_paths"] == ["edu_cloud.db-wal", "edu_cloud.db-shm"]
    assert "data/.db_migrate.lock" in artifacts["risky_paths"]
    assert ".codex" in artifacts["risky_paths"]
    assert "edu_cloud.db-wal" not in artifacts["risky_paths"]
    assert "edu_cloud.db-shm" not in artifacts["risky_paths"]


def test_codex_verify_help_lists_supported_modes():
    result = run_script("codex-verify", "--help")

    assert result.returncode == 0
    for mode in ("frontend", "github-ci", "backend", "schema", "safety", "full"):
        assert mode in result.stdout


def test_frontend_version_alignment_allows_docs_only_dist_lag(monkeypatch):
    module = load_codex_verify_module()
    calls = []

    def fake_classify(base, head):
        calls.append((base, head))
        return {"status": "docs_only", "paths": []}

    monkeypatch.setattr(module, "classify_hash_drift", fake_classify)

    errors = module.frontend_version_alignment_errors(
        local={"git_hash": "old123", "source_dirty": False},
        remote=None,
        head="new999",
    )

    assert errors == []
    assert calls == [("old123", "new999")]


def test_frontend_version_alignment_allows_docs_only_remote_lag(monkeypatch):
    module = load_codex_verify_module()
    calls = []

    def fake_classify(base, head):
        calls.append((base, head))
        return {"status": "docs_only", "paths": []}

    monkeypatch.setattr(module, "classify_hash_drift", fake_classify)

    errors = module.frontend_version_alignment_errors(
        local={"git_hash": "new999", "source_dirty": False},
        remote={"git_hash": "old123"},
        head="new999",
    )

    assert errors == []
    assert calls == [("old123", "new999")]


def test_frontend_version_alignment_blocks_runtime_dist_lag(monkeypatch):
    module = load_codex_verify_module()

    monkeypatch.setattr(
        module,
        "classify_hash_drift",
        lambda base, head: {"status": "runtime", "paths": ["frontend/src/App.tsx"]},
    )

    errors = module.frontend_version_alignment_errors(
        local={"git_hash": "old123", "source_dirty": False},
        remote=None,
        head="new999",
    )

    assert errors == [
        "local dist/version.json git_hash old123 does not match HEAD new999; "
        "runtime files changed: frontend/src/App.tsx"
    ]


def test_frontend_version_alignment_blocks_unknown_head():
    module = load_codex_verify_module()

    errors = module.frontend_version_alignment_errors(
        local={"git_hash": "old123", "source_dirty": False},
        remote=None,
        head="unknown",
    )

    assert errors == [
        "local dist/version.json git_hash old123 cannot be verified because HEAD is unknown"
    ]


def test_frontend_version_alignment_blocks_unknown_classification(monkeypatch):
    module = load_codex_verify_module()

    monkeypatch.setattr(
        module,
        "classify_hash_drift",
        lambda base, head: {"status": "unknown", "paths": []},
    )

    errors = module.frontend_version_alignment_errors(
        local={"git_hash": "old123", "source_dirty": False},
        remote=None,
        head="new999",
    )

    assert errors == [
        "local dist/version.json git_hash old123 does not match HEAD new999; "
        "drift classification unavailable, treated as runtime"
    ]


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


def test_guardian_runtime_builds_snapshot_from_existing_checks(monkeypatch, tmp_path):
    module = load_guardian_runtime_module()

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "collect_git", lambda: {
        "branch": "master",
        "head": "abc123",
        "upstream": "origin/master",
        "ahead": 0,
        "status_entries": 1,
        "backend_dirty": 1,
        "frontend_dirty": 0,
        "tests_dirty": 0,
        "docs_dirty": 0,
    })
    monkeypatch.setattr(module, "collect_artifacts", lambda: {
        "risky_paths": ["data/.db_migrate.lock"],
        "runtime_paths": ["edu_cloud.db-wal"],
        "backups_exists": True,
        "screenshots_exists": False,
    })
    monkeypatch.setattr(module, "collect_versions", lambda no_network=False: {"dist_hash": "abc123", "network": "skipped"})
    monkeypatch.setattr(module, "collect_ports", lambda: {"status": "ok", "listeners": [], "expected": {}})
    monkeypatch.setattr(module, "collect_processes", lambda: {"status": "ok", "project_processes": [], "services": {}})
    monkeypatch.setattr(module, "collect_db", lambda: {"status": "ok", "hard": 0, "warn": 0})
    monkeypatch.setattr(module, "collect_guardian_health", lambda: {
        "status": "ok",
        "overall": "yellow",
        "issue_count": 1,
        "red_count": 0,
        "yellow_count": 1,
        "issues": [
            {
                "issue_code": "GHOST_PROCESS",
                "severity": "yellow",
                "summary": "ghost worker",
                "blocks_completion": False,
                "command_hint": "inspect",
                "required_before": "session_end",
            }
        ],
    })
    monkeypatch.setattr(module, "safety_risks", lambda no_network=False: ["backend source dirty: 1 file(s)"])

    snapshot = module.build_snapshot(no_network=True)

    assert snapshot["schema"] == "guardian.watch.v1"
    assert snapshot["overall"] == "red"
    assert snapshot["git"]["backend_dirty"] == 1
    assert snapshot["artifacts"]["runtime_paths"] == ["edu_cloud.db-wal"]
    codes = {issue["issue_code"] for issue in snapshot["issues"]}
    assert {"BACKEND_DIRTY", "RISKY_ARTIFACT", "GHOST_PROCESS"} <= codes
    assert any(issue["blocks_completion"] for issue in snapshot["issues"] if issue["issue_code"] == "BACKEND_DIRTY")


def test_codex_support_parses_ss_listener_inventory():
    module = load_codex_support_module()
    sample = (
        'LISTEN 0 2048 0.0.0.0:9001 0.0.0.0:* users:(("python",pid=1234,fd=3))\n'
        'LISTEN 0 4096 127.0.0.1:9000 0.0.0.0:* users:(("python",pid=2222,fd=9))\n'
    )

    listeners = module.parse_ss_listeners(sample)

    assert listeners[0]["port"] == 9001
    assert listeners[0]["bind"] == "0.0.0.0"
    assert listeners[0]["pid"] == 1234
    assert listeners[1]["port"] == 9000
    assert listeners[1]["bind"] == "127.0.0.1"


def test_codex_support_no_network_still_checks_local_backend(monkeypatch, tmp_path):
    module = load_codex_support_module()
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "version.json").write_text('{"git_hash": "abc123", "source_dirty": false}', encoding="utf-8")
    calls = []

    def fake_run(args, timeout=10, cwd=None):
        calls.append(args)
        if "http://127.0.0.1:9000/api/v1/version" in args:
            return module.CommandResult(
                args=args,
                returncode=0,
                stdout='{"git_hash": "abc123", "source_dirty": false, "pid": 42, "boot_time": "t0"}',
                stderr="",
            )
        return module.CommandResult(args=args, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "run", fake_run)

    versions = module.collect_versions(no_network=True)

    assert versions["backend_hash"] == "abc123"
    assert versions["backend_pid"] == 42
    assert versions["backend_boot_time"] == "t0"
    assert not any("https://mcu.asia/version.json" in args for args in calls)


def test_codex_support_collects_worker_runtime_fingerprint(monkeypatch, tmp_path):
    module = load_codex_support_module()
    state_path = tmp_path / "logs" / "worker-runtime.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps({
            "schema": "edu-cloud.worker-runtime.v1",
            "service": "edu-cloud-worker",
            "process": "worker",
            "pid": 77,
            "boot_time": "2026-06-22T00:00:00Z",
            "recorded_at": "2026-06-22T00:00:01Z",
            "git_hash": "abc123",
            "source_dirty": False,
        }) + "\n",
        encoding="utf-8",
    )

    def fake_run(args, timeout=10, cwd=None):
        if args[:3] == ["systemctl", "show", "edu-cloud-worker"]:
            return module.CommandResult(args=args, returncode=0, stdout="77\n", stderr="")
        return module.CommandResult(args=args, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "run", fake_run)

    versions = module.collect_versions(no_network=True)

    assert versions["worker_status"] == "ok"
    assert versions["worker_hash"] == "abc123"
    assert versions["worker_pid"] == 77
    assert versions["worker_service_pid"] == 77
    assert versions["worker_boot_time"] == "2026-06-22T00:00:00Z"


def test_guardian_runtime_flags_parallel_backend_and_duplicate_worker(monkeypatch, tmp_path):
    module = load_guardian_runtime_module()

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "collect_git", lambda: {
        "branch": "master",
        "head": "abc123",
        "upstream": "origin/master",
        "ahead": 0,
        "status_entries": 0,
        "backend_dirty": 0,
        "frontend_dirty": 0,
        "tests_dirty": 0,
        "docs_dirty": 0,
    })
    monkeypatch.setattr(module, "collect_artifacts", lambda: {
        "risky_paths": [],
        "runtime_paths": [],
        "backups_exists": False,
        "screenshots_exists": False,
    })
    monkeypatch.setattr(module, "collect_versions", lambda no_network=False: {"dist_hash": "abc123", "network": "skipped"})
    monkeypatch.setattr(module, "collect_ports", lambda: {
        "status": "ok",
        "expected": {"9000": {"label": "edu-cloud API", "required": True, "present": True}},
        "listeners": [
            {
                "port": 9000,
                "bind": "127.0.0.1",
                "pid": 100,
                "service": "edu-cloud",
                "command": "python -m uvicorn edu_cloud.api.app:create_app --port 9000",
                "version_hash": "abc123",
                "version_source_dirty": False,
            },
            {
                "port": 9001,
                "bind": "0.0.0.0",
                "pid": 101,
                "service": None,
                "command": "python -m uvicorn edu_cloud.api.app:create_app --port 9001",
                "version_hash": "old999",
                "version_source_dirty": False,
            },
            {
                "port": 8081,
                "bind": "0.0.0.0",
                "pid": 102,
                "service": None,
                "command": "node /home/ops/projects/edu-cloud/frontend/node_modules/.bin/vite --host 0.0.0.0 --port 8081",
            },
        ],
    })
    monkeypatch.setattr(module, "collect_processes", lambda: {
        "status": "ok",
        "services": {"edu-cloud-worker": 200},
        "project_processes": [
            {"pid": 200, "service": "edu-cloud-worker", "command": "python scripts/run-arq-worker"},
            {"pid": 201, "service": None, "command": "python scripts/run-arq-worker"},
        ],
    })
    monkeypatch.setattr(module, "collect_db", lambda: {"status": "ok", "hard": 0, "warn": 0})
    monkeypatch.setattr(module, "collect_guardian_health", lambda: {"status": "ok", "issues": []})
    monkeypatch.setattr(module, "safety_risks", lambda no_network=False: [])

    snapshot = module.build_snapshot(no_network=True)
    codes = {issue["issue_code"] for issue in snapshot["issues"]}

    assert snapshot["ports"]["listeners"][1]["port"] == 9001
    assert {
        "PARALLEL_BACKEND_PROCESS",
        "PARALLEL_VERSION_DRIFT",
        "PARALLEL_FRONTEND_DEV_SERVER",
        "DUPLICATE_WORKER_PROCESS",
    } <= codes
    assert snapshot["overall"] == "red"


def test_guardian_runtime_flags_port_conflict_and_backend_hot_reload(monkeypatch, tmp_path):
    module = load_guardian_runtime_module()

    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(module, "collect_git", lambda: {
        "branch": "master",
        "head": "new999",
        "upstream": "origin/master",
        "ahead": 0,
        "status_entries": 0,
        "backend_dirty": 0,
        "frontend_dirty": 0,
        "tests_dirty": 0,
        "docs_dirty": 0,
    })
    monkeypatch.setattr(module, "collect_artifacts", lambda: {
        "risky_paths": [],
        "runtime_paths": [],
        "backups_exists": False,
        "screenshots_exists": False,
    })
    monkeypatch.setattr(module, "collect_versions", lambda no_network=False: {
        "dist_hash": "new999",
        "backend_hash": "new999",
        "backend_pid": 100,
        "backend_boot_time": "t1",
        "network": "skipped",
    })
    monkeypatch.setattr(module, "collect_ports", lambda: {
        "status": "ok",
        "expected": {"9000": {"label": "edu-cloud API", "required": True, "present": True}},
        "listeners": [
            {
                "port": 9000,
                "bind": "0.0.0.0",
                "pid": 101,
                "service": None,
                "command": "python -m uvicorn edu_cloud.api.app:create_app --port 9000",
                "version_hash": "new999",
                "version_source_dirty": False,
                "version_boot_time": "t1",
            },
            {
                "port": 9000,
                "bind": "127.0.0.1",
                "pid": 100,
                "service": "edu-cloud",
                "command": "python -m uvicorn edu_cloud.api.app:create_app --port 9000",
                "version_hash": "new999",
                "version_source_dirty": False,
                "version_boot_time": "t1",
            },
        ],
    })
    monkeypatch.setattr(module, "collect_processes", lambda: {"status": "ok", "project_processes": [], "services": {}})
    monkeypatch.setattr(module, "collect_db", lambda: {"status": "ok", "hard": 0, "warn": 0})
    monkeypatch.setattr(module, "collect_guardian_health", lambda: {"status": "ok", "issues": []})
    monkeypatch.setattr(module, "safety_risks", lambda no_network=False: [])

    state = {"backend_runtimes": {"9000": {"pid": 100, "git_hash": "old123", "boot_time": "t1"}}}
    config = module.WatchConfig(state_file=tmp_path / "guardian-state.json", jsonl_file=None)
    snapshot = module.run_once(config, state)
    codes = {issue["issue_code"] for issue in snapshot["issues"]}

    assert {"PORT_CONFLICT", "PORT_PUBLIC_BIND", "BACKEND_HOT_RELOAD"} <= codes
    assert state["backend_runtimes"]["9000"]["git_hash"] == "new999"


def test_guardian_watch_once_json_outputs_runtime_schema():
    result = run_script("guardian-watch", "--once", "--no-network", "--no-model-review", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "guardian.watch.v1"
    assert payload["mode"] == "once"
    assert "overall" in payload
    assert "issues" in payload


def test_guardian_claude_model_review_is_retired_and_does_not_call_runner(tmp_path):
    module = load_guardian_runtime_module()
    snapshot = {
        "schema": "guardian.watch.v1",
        "overall": "yellow",
        "issues": [{"issue_code": "GHOST_PROCESS", "severity": "yellow", "summary": "ghost", "blocks_completion": False}],
    }
    state = {}
    calls = []

    def fake_runner(cmd, cwd=None, capture_output=True, text=True, timeout=300):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "review", "")

    config = module.WatchConfig(
        model_review=True,
        model_review_backend="claude",
        model_review_interval=3600,
        model_review_dir=tmp_path,
    )

    result = module.maybe_run_model_review(snapshot, state, config, now=1000, runner=fake_runner)

    assert result["status"] == "disabled"
    assert result["reason"] == "claude_auxiliary_retired"
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_guardian_external_model_review_requires_explicit_command_and_rate_limits(tmp_path):
    module = load_guardian_runtime_module()
    snapshot = {
        "schema": "guardian.watch.v1",
        "overall": "yellow",
        "issues": [{"issue_code": "GHOST_PROCESS", "severity": "yellow", "summary": "ghost", "blocks_completion": False}],
    }
    state = {}
    calls = []

    def fake_runner(cmd, cwd=None, capture_output=True, text=True, timeout=300):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "external review", "")

    config = module.WatchConfig(
        model_review=True,
        model_review_backend="gpt",
        model_review_command="external-review --readonly",
        model_review_interval=3600,
        model_review_dir=tmp_path,
    )

    first = module.maybe_run_model_review(snapshot, state, config, now=1000, runner=fake_runner)
    second = module.maybe_run_model_review(snapshot, state, config, now=1001, runner=fake_runner)

    assert first["status"] == "ran"
    assert second["status"] == "skipped"
    assert len(calls) == 1
    command_text = " ".join(str(part) for part in calls[0])
    assert "external-review" in command_text
    assert "--readonly" in command_text
    assert "codex-consult-claude" not in command_text
    assert any(path.name.startswith("guardian-model-review-") for path in tmp_path.iterdir())

def test_guardian_fingerprint_ignores_worktree_dirty_count_noise():
    module = load_guardian_runtime_module()
    base = [
        {
            "issue_code": "WORKTREE_DIRTY",
            "severity": "yellow",
            "summary": "working tree dirty: 12 changed/untracked path(s)",
            "blocks_completion": False,
        },
        {
            "issue_code": "GHOST_PROCESS",
            "severity": "yellow",
            "summary": "ghost PID=2117898",
            "blocks_completion": False,
        },
    ]
    changed_count = [
        dict(base[0], summary="working tree dirty: 15 changed/untracked path(s)"),
        base[1],
    ]
    changed_pid = [
        base[0],
        dict(base[1], summary="ghost PID=2117999"),
    ]

    assert module.issue_fingerprint(base) == module.issue_fingerprint(changed_count)
    assert module.issue_fingerprint(base) == module.issue_fingerprint(changed_pid)


def test_guardian_systemd_template_is_present():
    runner = PROJECT_ROOT / "scripts" / "guardian-watch"
    unit = PROJECT_ROOT / "deploy" / "systemd" / "edu-cloud-guardian.service"

    runner_text = runner.read_text(encoding="utf-8")
    unit_text = unit.read_text(encoding="utf-8")

    assert "guardian_runtime" in runner_text
    assert "ExecStart=/home/ops/projects/edu-cloud/.venv/bin/python /home/ops/projects/edu-cloud/scripts/guardian-watch" in unit_text
    assert "--interval 15" in unit_text
    assert "Restart=on-failure" in unit_text
    assert "CPUQuota=25%" in unit_text
    assert "MemoryMax=512M" in unit_text


def test_meta_runtime_builds_snapshot_from_context():
    module = load_meta_runtime_module()

    snapshot = module.build_snapshot(task="升级元能力核心，双模型启动，基于实证深度挖掘")

    assert snapshot["schema"] == "meta.core.v1"
    assert snapshot["overall"] in {"green", "yellow", "red"}
    assert "task_contract" in snapshot
    obligations = {item["code"] for item in snapshot["task_contract"]["obligations"]}
    assert {"EVIDENCE_MATRIX", "INDEPENDENT_REVIEW_EVIDENCE", "IMPLEMENT_AND_VERIFY"} <= obligations
    assert "CLAUDE_REVIEW" not in obligations
    assert any(check["name"] == "active_docs" for check in snapshot["checks"])


def test_meta_runtime_detects_missing_active_doc(tmp_path):
    module = load_meta_runtime_module()
    context = tmp_path / "docs" / "context"
    context.mkdir(parents=True)
    (context / "ACTIVE_INDEX.md").write_text(
        """# Active Document Index

## Active

| Path | Status | Use |
|---|---|---|
| `AGENTS.md` | active | entry |
| `docs/context/MISSING.md` | active | missing |

## Candidate Active Work
""",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("entry\n", encoding="utf-8")

    issues = module.check_active_docs(tmp_path)

    assert any(issue["issue_code"] == "ACTIVE_DOC_MISSING" for issue in issues)


def test_meta_runtime_ignores_historical_wildcards_in_active_index_intro(tmp_path):
    module = load_meta_runtime_module()
    context = tmp_path / "docs" / "context"
    context.mkdir(parents=True)
    (context / "ACTIVE_INDEX.md").write_text(
        """# Active Document Index

Anything not listed here, including `docs/plans/**`, is historical.

## Active

| Path | Status | Use |
|---|---|---|
| `AGENTS.md` | active | entry |

## Candidate Active Work
""",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("entry\n", encoding="utf-8")

    assert module.check_active_docs(tmp_path) == []


def test_meta_runtime_ignores_active_table_description_backticks(tmp_path):
    module = load_meta_runtime_module()
    context = tmp_path / "docs" / "context"
    context.mkdir(parents=True)
    (context / "ACTIVE_INDEX.md").write_text(
        """# Active Document Index

## Active

| Path | Status | Use |
|---|---|---|
| `AGENTS.md` | active | review-gap 16 commit (`3688f32..6b1bdd3`), 合同 `yc-20260614-39eac63d` |

## Candidate Active Work
""",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("entry\n", encoding="utf-8")

    # The descriptive Use column carries a contract id and a commit range in
    # backticks; neither must be treated as an active document path.
    paths = module.active_index_paths((context / "ACTIVE_INDEX.md").read_text(encoding="utf-8"))
    assert paths == ["AGENTS.md"]
    assert "3688f32..6b1bdd3" not in paths
    assert "yc-20260614-39eac63d" not in paths

    assert module.check_active_docs(tmp_path) == []


def test_meta_runtime_still_detects_missing_first_column_path_with_descriptor_noise(tmp_path):
    module = load_meta_runtime_module()
    context = tmp_path / "docs" / "context"
    context.mkdir(parents=True)
    (context / "ACTIVE_INDEX.md").write_text(
        """# Active Document Index

## Active

| Path | Status | Use |
|---|---|---|
| `AGENTS.md` | active | entry |
| `docs/context/MISSING.md` | active | range `3688f32..6b1bdd3` 合同 `yc-20260614-39eac63d` |

## Candidate Active Work
""",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("entry\n", encoding="utf-8")

    issues = module.check_active_docs(tmp_path)

    missing = [issue for issue in issues if issue["issue_code"] == "ACTIVE_DOC_MISSING"]
    # Only the real first-column path is missing; descriptor backticks add none.
    assert len(missing) == 1
    assert "docs/context/MISSING.md" in missing[0]["summary"]
    assert not any("3688f32" in issue["summary"] for issue in issues)
    assert not any("yc-20260614" in issue["summary"] for issue in issues)


def test_meta_runtime_now_timestamp_is_machine_parseable():
    module = load_meta_runtime_module()
    text = (PROJECT_ROOT / "docs" / "context" / "NOW.md").read_text(encoding="utf-8")
    match = re.search(
        r"Last refreshed:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+Asia/Shanghai", text
    )
    assert match, "docs/context/NOW.md needs 'Last refreshed: YYYY-MM-DD HH:MM Asia/Shanghai'"
    refreshed = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M").replace(
        tzinfo=timezone(timedelta(hours=8))
    )

    # One hour after the recorded refresh is fresh -> no STALE_FACTS issue, and
    # in particular the "no parseable Last refreshed timestamp" false positive
    # must be gone regardless of wall-clock time.
    issues = module.check_now_freshness(PROJECT_ROOT, now=refreshed + timedelta(hours=1))
    assert not any(
        "no parseable Last refreshed timestamp" in issue["summary"] for issue in issues
    )
    assert issues == []


def test_meta_runtime_detects_plan_without_evidence():
    module = load_meta_runtime_module()

    issues = module.check_plan_contract(
        Path("docs/superpowers/plans/demo-plan.md"),
        "# Demo Implementation Plan\n\n**Goal:** Build it.\n\n**Architecture:** New thing.\n",
    )

    assert any(issue["issue_code"] == "PLAN_EVIDENCE_GAP" for issue in issues)


def test_meta_runtime_detects_empty_evidence_section_without_file_reference():
    module = load_meta_runtime_module()

    issues = module.check_plan_contract(
        Path("docs/superpowers/plans/demo-plan.md"),
        "# Demo Implementation Plan\n\n## Evidence\n\nEvidence: TBD.\n",
    )

    assert any(issue["issue_code"] == "PLAN_EVIDENCE_GAP" for issue in issues)


def test_meta_runtime_checks_recent_committed_plan_contracts(tmp_path):
    module = load_meta_runtime_module()
    plan = tmp_path / "docs" / "superpowers" / "plans" / "recent-plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Recent Plan\n\n## Architecture\n\nNew subsystem.\n", encoding="utf-8")

    issues = module.check_recent_plan_contracts(
        tmp_path,
        recent_paths=["docs/superpowers/plans/recent-plan.md"],
    )

    assert any(issue["issue_code"] == "PLAN_EVIDENCE_GAP" for issue in issues)


def test_meta_runtime_detects_task_contract_drift(tmp_path):
    module = load_meta_runtime_module()
    baseline = tmp_path / "meta-state.json"
    baseline.write_text(
        json.dumps(
            {
                "schema": "meta.state.v1",
                "latest_snapshot": {
                    "task_contract": {
                        "obligations": [
                            {"code": "EVIDENCE_MATRIX", "summary": "evidence"},
                            {"code": "INDEPENDENT_REVIEW_EVIDENCE", "summary": "review"},
                        ]
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    issues = module.check_task_contract_drift(
        baseline,
        current_obligations=[{"code": "EVIDENCE_MATRIX", "summary": "evidence"}],
    )

    drift = [issue for issue in issues if issue["issue_code"] == "TASK_CONTRACT_DRIFT"]
    assert drift
    assert "advisory state obligation" in drift[0]["summary"]
    assert "baseline" not in drift[0]["summary"].lower()
    assert "advisory state cache" in drift[0]["command_hint"]

    missing_issues = module.check_task_contract_drift(
        tmp_path / "missing-state.json", current_obligations=[]
    )
    assert missing_issues[0]["issue_code"] == "TASK_CONTRACT_DRIFT"
    assert "advisory state cache" in missing_issues[0]["summary"]
    assert "refresh advisory diagnostics" in missing_issues[0]["command_hint"]


def test_meta_runtime_write_state_is_atomic_and_readable(tmp_path):
    module = load_meta_runtime_module()
    state_file = tmp_path / "meta-state.json"
    snapshot = module.build_snapshot(project_root=PROJECT_ROOT, task="测试写入状态", include_git=False)

    module.write_state(state_file, snapshot)

    parsed = json.loads(state_file.read_text(encoding="utf-8"))
    assert parsed["schema"] == "meta.state.v1"
    authority = parsed["state_authority"]
    assert authority["classification"] == "advisory_diagnostic_cache"
    assert authority["trust_baseline"] is False
    assert authority["completion_authority"] is False
    assert parsed["latest_snapshot"]["schema"] == "meta.core.v1"
    assert parsed["latest_snapshot"]["state_authority"]["trust_baseline"] is False
    assert not (tmp_path / "meta-state.json.tmp").exists()


def test_meta_runtime_reports_inconclusive_recent_plan_scan(monkeypatch, tmp_path):
    module = load_meta_runtime_module()

    def fake_run(cmd, cwd=None, capture_output=True, text=True, timeout=10):
        return subprocess.CompletedProcess(cmd, 128, "", "fatal: bad revision")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    issues = module.check_recent_plan_contracts(tmp_path)

    assert any(issue["issue_code"] == "PLAN_SCAN_INCONCLUSIVE" for issue in issues)


def test_meta_runtime_detects_stale_now_facts(tmp_path):
    module = load_meta_runtime_module()
    context = tmp_path / "docs" / "context"
    context.mkdir(parents=True)
    (context / "NOW.md").write_text(
        "# NOW\n\nLast refreshed: 2026-05-01 08:00 Asia/Shanghai\n",
        encoding="utf-8",
    )
    now = datetime(2026, 5, 6, 8, 0, tzinfo=timezone(timedelta(hours=8)))

    issues = module.check_now_freshness(tmp_path, now=now)

    stale = [issue for issue in issues if issue["issue_code"] == "STALE_FACTS"]
    assert stale
    assert stale[0]["severity"] == "red"
    assert stale[0]["blocks_completion"] is True


def test_meta_check_once_json_outputs_schema():
    result = run_script(
        "meta-check",
        "--json",
        "--task",
        "升级元能力核心，双模型启动，基于实证深度挖掘",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "meta.core.v1"
    assert payload["task_contract"]["task"]
    assert "issues" in payload


def test_meta_runtime_fail_on_blocking_passes_non_blocking_yellow():
    module = load_meta_runtime_module()
    yellow = {
        "overall": "yellow",
        "red_count": 0,
        "issues": [
            {"issue_code": "STALE_FACTS", "severity": "yellow", "blocks_completion": False},
        ],
    }
    # CI-safe gate lets a non-blocking yellow pass...
    assert module.decide_exit_code(yellow, strict=False, fail_on_blocking=True) == 0
    # ...while the legacy strict gate still fails the very same snapshot.
    assert module.decide_exit_code(yellow, strict=True, fail_on_blocking=False) == 1
    assert module.has_blocking_issue(yellow) is False


def test_meta_runtime_fail_on_blocking_fails_red_or_blocking():
    module = load_meta_runtime_module()
    red = {
        "overall": "red",
        "red_count": 1,
        "issues": [
            {"issue_code": "ACTIVE_DOC_MISSING", "severity": "red", "blocks_completion": True},
        ],
    }
    assert module.decide_exit_code(red, strict=False, fail_on_blocking=True) == 1
    # A yellow-severity issue that still blocks completion must also fail, even
    # when a caller hands us a snapshot whose red_count was not folded in.
    blocking_yellow = {
        "overall": "yellow",
        "red_count": 0,
        "issues": [
            {"issue_code": "TASK_CONTRACT_DRIFT", "severity": "yellow", "blocks_completion": True},
        ],
    }
    assert module.has_blocking_issue(blocking_yellow) is True
    assert module.decide_exit_code(blocking_yellow, strict=False, fail_on_blocking=True) == 1


def test_meta_runtime_green_snapshot_passes_both_modes():
    module = load_meta_runtime_module()
    green = {"overall": "green", "red_count": 0, "issues": []}
    assert module.decide_exit_code(green, strict=True, fail_on_blocking=False) == 0
    assert module.decide_exit_code(green, strict=False, fail_on_blocking=True) == 0


def test_meta_check_cli_accepts_fail_on_blocking_flag():
    module = load_meta_runtime_module()
    args = module.parse_args(["--json", "--fail-on-blocking"])
    assert args.fail_on_blocking is True
    assert args.strict is False
    # The legacy flag must remain available alongside the new one.
    legacy = module.parse_args(["--json", "--strict"])
    assert legacy.strict is True
    assert legacy.fail_on_blocking is False


def test_meta_check_fail_on_blocking_flag_is_wired_into_cli():
    result = run_script("meta-check", "--json", "--fail-on-blocking")
    # The flag must be accepted (an argparse error would exit 2) and still emit a
    # parseable snapshot. The gate result (0 or 1) tracks live NOW.md freshness,
    # so we assert it is a valid gate exit, not a fixed, time-dependent code.
    assert result.returncode in (0, 1), result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "meta.core.v1"


def test_meta_runtime_contract_and_lessons_are_active():
    lessons = (PROJECT_ROOT / "docs" / "context" / "LESSONS.md").read_text(encoding="utf-8")
    commands = (PROJECT_ROOT / "docs" / "context" / "COMMANDS.md").read_text(encoding="utf-8")
    model = (PROJECT_ROOT / "docs" / "context" / "GOVERNANCE_MODEL.md").read_text(encoding="utf-8")

    for lesson in ("L017", "L019", "L022"):
        assert lesson in lessons
    assert "scripts/meta-check" in commands
    assert "docs/context/META_RUNTIME.md" in model


def test_frontend_dev_server_binds_loopback_by_default():
    config = (PROJECT_ROOT / "frontend" / "vite.config.js").read_text(encoding="utf-8")

    assert "host: '127.0.0.1'" in config
    assert "host: '0.0.0.0'" not in config


def test_claude_auxiliary_is_not_active_ci_or_runtime_surface():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    guardian = (PROJECT_ROOT / "scripts" / "guardian_runtime.py").read_text(encoding="utf-8")
    module = load_meta_runtime_module()
    snapshot = module.build_snapshot(task="审查当前治理质量")
    obligations = {item["code"] for item in snapshot["task_contract"]["obligations"]}

    assert "scripts/codex-consult-claude" not in workflow
    assert "codex-consult-claude" not in guardian
    assert "CLAUDE_REVIEW" not in obligations
    assert "INDEPENDENT_REVIEW_EVIDENCE" in obligations
    assert any(check["name"] == "legacy_claude_auxiliary" for check in snapshot["checks"])

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


def test_codex_verify_backend_default_is_ci_aligned_profile():
    # D-07: with no explicit targets, the documented backend completion gate runs
    # the single CI-aligned pytest baseline profile, not a bare full pytest run.
    result = run_script("codex-verify", "backend", "--dry-run")

    assert result.returncode == 0
    out = result.stdout
    assert "scripts/pytest_delta.py" in out
    assert "--ignore=tests/governance" in out
    assert "--ignore=tests/test_services_exam/test_tql_renderer.py" in out
    assert "--ignore=tests/test_services_exam/test_card_e2e.py" in out
    assert (
        "not (test_alembic_migration or test_alembic_s1 or test_card_publish "
        "or test_grading_worker or test_objective_only_not_ready)"
    ) in out


def test_codex_verify_backend_profile_mirrors_ci_workflow():
    # The documented backend completion gate and the CI backend job must gate the
    # same single pytest baseline profile (D-07 unification). The codex-verify
    # CI_BACKEND_PROFILE is the in-script source; assert every token is mirrored
    # verbatim by the workflow so the two cannot silently drift apart.
    module = load_codex_verify_module()
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")

    for token in module.CI_BACKEND_PROFILE:
        if token == "-k":
            continue
        assert token in workflow, f"CI workflow missing backend profile token: {token!r}"


def test_codex_verify_frontend_profile_mirrors_ci_workflow():
    module = load_codex_verify_module()
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")
    dry_run = run_script("codex-verify", "frontend", "--dry-run", "--allow-dirty-build")

    assert dry_run.returncode == 0
    for command in module.CI_FRONTEND_COMMANDS:
        shell_command = module.shell_join(command)
        workflow_command = f"cd frontend && {shell_command}"
        assert workflow_command in workflow, f"CI workflow missing frontend command: {workflow_command!r}"
        assert shell_command in dry_run.stdout, f"codex-verify frontend missing command: {shell_command!r}"


def test_codex_verify_frontend_dry_run_lists_ci_and_version_alignment_gates():
    result = run_script("codex-verify", "frontend", "--dry-run", "--allow-dirty-build")

    assert result.returncode == 0
    assert "npm ci --ignore-scripts" in result.stdout
    assert "npx vitest run" in result.stdout
    assert "npm audit --audit-level=high" in result.stdout
    assert "frontend version alignment" in result.stdout
    assert "docs/governance/test/observability-only drift" in result.stdout
    assert "https://mcu.asia/version.json" in result.stdout


def test_codex_verify_github_ci_dry_run_binds_branch_and_head():
    result = run_script("codex-verify", "github-ci", "--dry-run", "--branch", "feature/test", "--head", "abc123")

    assert result.returncode == 0
    assert "gh run list" in result.stdout
    assert "--workflow Tests" in result.stdout
    assert "--branch feature/test" in result.stdout
    assert "match headSha == abc123" in result.stdout


def test_github_ci_decision_is_fail_closed_for_missing_pending_and_failure():
    module = load_codex_verify_module()

    assert module.decide_github_ci_run([], "abc123") == ("missing", None)

    pending = {"headSha": "abc123", "status": "in_progress", "conclusion": "", "databaseId": 1}
    outcome, match = module.decide_github_ci_run([pending], "abc123")
    assert outcome == "pending"
    assert match == pending

    failed = {"headSha": "abc123", "status": "completed", "conclusion": "failure", "databaseId": 2}
    outcome, match = module.decide_github_ci_run([failed], "abc123")
    assert outcome == "failure"
    assert match == failed


def test_github_ci_decision_requires_exact_head_success():
    module = load_codex_verify_module()
    old_green = {"headSha": "old456", "status": "completed", "conclusion": "success", "databaseId": 1}
    current_green = {"headSha": "abc123", "status": "completed", "conclusion": "success", "databaseId": 2}

    outcome, match = module.decide_github_ci_run([old_green, current_green], "abc123")

    assert outcome == "success"
    assert match == current_green


def test_github_ci_run_loader_fails_closed_on_gh_and_json_errors(monkeypatch):
    module = load_codex_verify_module()

    class Result:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Result(2, stderr="gh failed"))
    rc, runs, error = module._load_github_runs(["gh", "run", "list"])
    assert rc == 2
    assert runs is None
    assert "gh failed" in error

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Result(0, stdout="not-json"))
    rc, runs, error = module._load_github_runs(["gh", "run", "list"])
    assert rc == 1
    assert runs is None
    assert "invalid gh JSON" in error

    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Result(0, stdout='{"not":"a-list"}'))
    rc, runs, error = module._load_github_runs(["gh", "run", "list"])
    assert rc == 1
    assert runs is None
    assert "expected a list" in error


def test_github_ci_verification_reports_auth_diagnostic_when_listing_fails(monkeypatch, capsys):
    module = load_codex_verify_module()

    class Args:
        repo = "juanwan99/edu-cloud"
        workflow = "Tests"
        branch = "feature/test"
        head = "abc123"
        limit = 20
        dry_run = False
        wait = False
        interval = 10

    class Result:
        returncode = 1
        stdout = ""
        stderr = "The token in default is invalid."

    monkeypatch.setattr(
        module,
        "_load_github_runs",
        lambda _cmd: (1, None, "HTTP 404: Not Found"),
    )
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: Result())

    rc = module.verify_github_ci(Args())

    out = capsys.readouterr().out
    assert rc == 1
    assert "GitHub CI verification failed: cannot list workflow runs." in out
    assert "GitHub CLI authentication diagnostic:" in out
    assert "The token in default is invalid." in out
    assert "gh auth login -h github.com" in out


def test_frontend_audit_security_versions_are_persistently_pinned():
    package_json = json.loads((PROJECT_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((PROJECT_ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))

    assert package_json["dependencies"]["dompurify"] == "^3.4.11"
    assert package_json["overrides"]["undici"] == "7.28.0"
    assert package_lock["packages"][""]["dependencies"]["dompurify"] == "^3.4.11"
    assert package_lock["packages"]["node_modules/dompurify"]["version"] == "3.4.11"
    assert package_lock["packages"]["node_modules/undici"]["version"] == "7.28.0"


def test_frontend_version_alignment_reports_hash_and_dirty_errors():
    module = load_codex_verify_module()

    errors = module.frontend_version_alignment_errors(
        local={"git_hash": "abc123", "source_dirty": True},
        remote={"git_hash": "def456"},
        head="abc123",
        allow_dirty_build=False,
    )

    assert "local dist/version.json has source_dirty=true" in errors
    assert any(
        error.startswith("remote version.json git_hash def456 does not match local dist abc123")
        and "drift classification unavailable, treated as runtime" in error
        for error in errors
    )

    remote_dirty_errors = module.frontend_version_alignment_errors(
        local={"git_hash": "abc123", "source_dirty": False},
        remote={"git_hash": "abc123", "source_dirty": True},
        head="abc123",
        allow_dirty_build=False,
    )
    assert remote_dirty_errors == ["remote version.json has source_dirty=true"]


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
    assert "scripts/meta-check --fail-on-blocking" in result.stdout
    assert "scripts/meta-check --strict" not in result.stdout
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
        "python -m py_compile scripts/codex_support.py scripts/codex-context scripts/codex-check scripts/codex-verify scripts/guardian_runtime.py scripts/guardian-watch scripts/run-arq-worker",
        "python -m py_compile scripts/governance/aggregate_modules.py scripts/governance/check_ai_tool_modules.py scripts/governance/check_execution_policy.py scripts/governance/check_module_dependencies.py scripts/governance/check_permission_mirror.py scripts/governance/module_governance_guard.py",
        "python -m py_compile scripts/yuanqi/legacy_quarantine_gate.py",
        "python scripts/governance/check_execution_policy.py",
        "python -m pytest tests/governance/test_codex_scripts.py -q",
        "python -m pytest tests/governance/test_aggregate_modules.py tests/governance/test_ai_tool_modules.py tests/governance/test_execution_policy.py tests/governance/test_module_dependencies.py tests/governance/test_module_governance_guard.py tests/governance/test_permission_mirror.py tests/governance/test_portal_contract.py tests/governance/test_tenant_static.py -q",
        "python scripts/governance/aggregate_modules.py --check",
        "python scripts/governance/check_ai_tool_modules.py",
        "python scripts/governance/check_module_dependencies.py --check",
        "python scripts/governance/check_permission_mirror.py",
        "python scripts/governance/module_governance_guard.py --git-hook-mode --repo \"$(pwd)\"",
        "scripts/codex-check --no-network",
        "scripts/codex-context --no-network",
        "scripts/codex-verify safety --repo-wide",
        "scripts/codex-verify full --dry-run --schema --no-network",
        "python -m pytest tests/yuanqi -q",
        "python -m pytest tests/test_alembic_migration.py -q",
        "cd frontend && npm ci --ignore-scripts",
        "cd frontend && npx vitest run",
        "cd frontend && npm run build",
        "cd frontend && npm audit --audit-level=high",
    ):
        assert command in text


def test_ci_governance_job_does_not_run_meta_check_gate():
    workflow = PROJECT_ROOT / ".github" / "workflows" / "test.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "scripts/meta-check --json --fail-on-blocking" not in text
    assert "scripts/meta-check --json --strict" not in text


def test_ci_backend_job_has_pytest_observability():
    workflow = PROJECT_ROOT / ".github" / "workflows" / "test.yml"
    text = workflow.read_text(encoding="utf-8")

    # Backend main suite must surface slow tests and cap its wall-clock runtime.
    assert "--durations=25" in text
    assert "timeout-minutes:" in text


# ── P0E-1: Guardian/Truthline observability semantics ──────────────────────


def test_classify_hash_drift_separates_docs_from_runtime(monkeypatch):
    module = load_codex_support_module()

    def docs_git(*args, timeout=10):
        if args[0] == "cat-file":
            return module.CommandResult(args=list(args), returncode=0, stdout="", stderr="")
        if args[0] == "diff":
            return module.CommandResult(
                args=list(args),
                returncode=0,
                stdout="docs/context/NOW.md\nAGENTS.md\nscripts/codex-verify\n"
                "tests/governance/test_codex_scripts.py\nfrontend/vitest.config.ts\n"
                ".quality/known-pytest-failures.txt\n",
                stderr="",
            )
        return module.CommandResult(args=list(args), returncode=1, stdout="", stderr="")

    monkeypatch.setattr(module, "git", docs_git)
    docs = module.classify_hash_drift("06c5483", "42b388e")
    assert docs["status"] == "docs_only"
    assert docs["paths"] == []

    def runtime_git(*args, timeout=10):
        if args[0] == "cat-file":
            return module.CommandResult(args=list(args), returncode=0, stdout="", stderr="")
        if args[0] == "diff":
            return module.CommandResult(
                args=list(args),
                returncode=0,
                stdout="src/edu_cloud/api/app.py\ndocs/context/NOW.md\nfrontend/src/main.js\n",
                stderr="",
            )
        return module.CommandResult(args=list(args), returncode=1, stdout="", stderr="")

    monkeypatch.setattr(module, "git", runtime_git)
    runtime = module.classify_hash_drift("06c5483", "42b388e")
    assert runtime["status"] == "runtime"
    assert "src/edu_cloud/api/app.py" in runtime["paths"]
    assert "frontend/src/main.js" in runtime["paths"]
    assert "docs/context/NOW.md" not in runtime["paths"]


def test_classify_hash_drift_unknown_when_ref_missing(monkeypatch):
    module = load_codex_support_module()

    def missing_git(*args, timeout=10):
        # cat-file fails -> ref unresolvable -> conservative "unknown".
        return module.CommandResult(args=list(args), returncode=1, stdout="", stderr="")

    monkeypatch.setattr(module, "git", missing_git)
    drift = module.classify_hash_drift("deadbee", "42b388e")
    assert drift["status"] == "unknown"
    # Equal hashes are trivially docs-only without touching git.
    assert module.classify_hash_drift("42b388e", "42b388e")["status"] == "docs_only"


def test_guardian_version_docs_only_drift_is_non_blocking_yellow(monkeypatch):
    module = load_guardian_runtime_module()
    monkeypatch.setattr(module, "classify_hash_drift", lambda base, head: {"status": "docs_only", "paths": []})

    issues = module.issues_from_versions(
        {
            "dist_hash": "06c5483",
            "backend_hash": "06c5483",
            "nginx_hash": "06c5483",
            "worker_service_pid": 77,
            "worker_status": "ok",
            "worker_hash": "06c5483",
            "worker_pid": 77,
        },
        {"head": "42b388e"},
    )
    codes = {issue["issue_code"] for issue in issues}
    assert {"BUILD_DRIFT_DOCS", "BACKEND_DRIFT_DOCS", "WORKER_DRIFT_DOCS"} <= codes
    assert "BUILD_DRIFT" not in codes
    assert "BACKEND_DRIFT" not in codes
    assert "WORKER_DRIFT" not in codes
    assert all(issue["severity"] == "yellow" for issue in issues)
    assert all(not issue["blocks_completion"] for issue in issues)


def test_guardian_version_runtime_drift_stays_blocking_red(monkeypatch):
    module = load_guardian_runtime_module()
    monkeypatch.setattr(
        module,
        "classify_hash_drift",
        lambda base, head: {"status": "runtime", "paths": ["src/edu_cloud/api/app.py"]},
    )

    issues = module.issues_from_versions(
        {"dist_hash": "06c5483", "backend_hash": "06c5483"},
        {"head": "42b388e"},
    )
    build = next(issue for issue in issues if issue["issue_code"] == "BUILD_DRIFT")
    backend = next(issue for issue in issues if issue["issue_code"] == "BACKEND_DRIFT")
    assert build["severity"] == "red" and build["blocks_completion"] is True
    assert backend["severity"] == "red" and backend["blocks_completion"] is True
    assert "src/edu_cloud/api/app.py" in build["summary"]


def test_guardian_version_unknown_drift_stays_blocking_red(monkeypatch):
    module = load_guardian_runtime_module()
    monkeypatch.setattr(module, "classify_hash_drift", lambda base, head: {"status": "unknown", "paths": []})

    issues = module.issues_from_versions({"backend_hash": "old999"}, {"head": "42b388e"})
    backend = next(issue for issue in issues if issue["issue_code"] == "BACKEND_DRIFT")
    assert backend["severity"] == "red" and backend["blocks_completion"] is True


def test_guardian_worker_fingerprint_missing_blocks_when_service_active():
    module = load_guardian_runtime_module()

    issues = module.issues_from_versions(
        {"worker_service_pid": 77, "worker_status": "missing", "worker_status_path": "logs/worker-runtime.json"},
        {"head": "42b388e"},
    )

    worker = next(issue for issue in issues if issue["issue_code"] == "WORKER_VERSION_MISSING")
    assert worker["severity"] == "red"
    assert worker["blocks_completion"] is True


def test_guardian_worker_runtime_drift_stays_blocking_red(monkeypatch):
    module = load_guardian_runtime_module()
    monkeypatch.setattr(
        module,
        "classify_hash_drift",
        lambda base, head: {"status": "runtime", "paths": ["src/edu_cloud/worker.py"]},
    )

    issues = module.issues_from_versions(
        {"worker_service_pid": 77, "worker_status": "ok", "worker_hash": "old999", "worker_pid": 77},
        {"head": "42b388e"},
    )

    worker = next(issue for issue in issues if issue["issue_code"] == "WORKER_DRIFT")
    assert worker["severity"] == "red" and worker["blocks_completion"] is True
    assert "src/edu_cloud/worker.py" in worker["summary"]


def test_guardian_worker_stale_pid_blocks_completion():
    module = load_guardian_runtime_module()

    issues = module.issues_from_versions(
        {
            "worker_service_pid": 77,
            "worker_status": "ok",
            "worker_hash": "42b388e",
            "worker_pid": 12,
            "worker_pid_mismatch": True,
        },
        {"head": "42b388e"},
    )

    worker = next(issue for issue in issues if issue["issue_code"] == "WORKER_STATUS_STALE")
    assert worker["severity"] == "red" and worker["blocks_completion"] is True


def test_guardian_parallel_version_docs_drift_is_non_blocking(monkeypatch):
    module = load_guardian_runtime_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", PROJECT_ROOT)
    monkeypatch.setattr(module, "classify_hash_drift", lambda base, head: {"status": "docs_only", "paths": []})

    ports = {
        "status": "ok",
        "expected": {"9000": {"label": "edu-cloud API", "required": True, "present": True}},
        "listeners": [
            {
                "port": 9000,
                "bind": "127.0.0.1",
                "pid": 100,
                "service": "edu-cloud",
                "command": "python -m uvicorn edu_cloud.api.app:create_app --port 9000",
                "version_hash": "06c5483",
                "version_source_dirty": False,
            }
        ],
    }
    issues = module.issues_from_ports(ports, {"head": "42b388e"})
    codes = {issue["issue_code"] for issue in issues}
    assert "PARALLEL_VERSION_DRIFT_DOCS" in codes
    assert "PARALLEL_VERSION_DRIFT" not in codes
    docs = next(issue for issue in issues if issue["issue_code"] == "PARALLEL_VERSION_DRIFT_DOCS")
    assert docs["severity"] == "yellow"
    assert docs["blocks_completion"] is False


def test_is_claude_cli_process_only_matches_real_sessions():
    module = load_codex_support_module()

    # Real Claude Code CLI invocations.
    assert module.is_claude_cli_process("/home/ops/.npm-global/bin/claude --dangerously-skip-permissions")
    assert module.is_claude_cli_process("claude -p 'hello'")
    assert module.is_claude_cli_process("node /opt/lib/@anthropic-ai/claude-code/cli.js")

    # References / wrappers that merely contain the word "claude" must NOT count.
    assert not module.is_claude_cli_process(
        "bash -c cd /home/ops/legacy-governance && readlink -f /home/ops/.claude/hooks"
    )
    assert not module.is_claude_cli_process(
        "/usr/bin/ssh -o SendEnv=GIT_PROTOCOL git@github-legacy-governance git-upload-pack 'juanwan99/claude-meta.git'"
    )
    assert not module.is_claude_cli_process(
        "bash /home/ops/legacy-governance/scripts/legacy_governance_claude start --project edu-cloud --mode writer"
    )
    assert not module.is_claude_cli_process("rg -n pattern /home/ops/.claude/projects/x.jsonl")
    assert not module.is_claude_cli_process("")


def test_count_claude_cli_processes_excludes_references_and_consult(monkeypatch):
    module = load_codex_support_module()
    sample = "\n".join(
        [
            "39345 bash -c readlink -f /home/ops/.claude/hooks",
            "39349 /usr/bin/ssh git@github-legacy-governance juanwan99/claude-meta.git",
            "2800620 bash /home/ops/legacy-governance/scripts/legacy_governance_claude start --project edu-cloud",
            "2800666 /home/ops/.npm-global/bin/claude --dangerously-skip-permissions",
            "2900001 claude -p review --no-session-persistence --permission-mode plan",
        ]
    )

    def fake_run(args, timeout=10, cwd=None):
        return module.CommandResult(args=args, returncode=0, stdout=sample + "\n", stderr="")

    monkeypatch.setattr(module, "run", fake_run)
    # Only the single real interactive Claude CLI counts; the consult reviewer
    # (--no-session-persistence) and the .claude/claude-meta/legacy_governance_claude
    # references do not.
    assert module.count_claude_cli_processes() == 1


def test_truth_doctor_json_does_not_flag_claude_references_as_sessions():
    # The live system frequently has many commands that merely reference a
    # `.claude` path; truth-doctor must not raise CLAUDE_SESSION_RISK off them.
    result = run_script("truth", "doctor", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    claude_risks = [issue for issue in data["issues"] if issue["issue_code"] == "CLAUDE_SESSION_RISK"]
    for risk in claude_risks:
        # If raised at all it must reflect a real count >5, never the dozens of
        # `.claude`/claude-meta/legacy_governance_claude reference lines pgrep returns.
        match = re.search(r"(\d+) Claude processes", risk["summary"])
        assert match and int(match.group(1)) <= 50


def test_collect_meta_runtime_state_marks_stale_snapshot(monkeypatch, tmp_path):
    module = load_codex_support_module()
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "meta-state.json").write_text(
        json.dumps(
            {
                "schema": "meta.state.v1",
                "updated_at": "2026-06-15T14:37:13Z",
                "latest_snapshot": {
                    "generated_at": "2026-06-15T14:37:13Z",
                    "overall": "red",
                    "red_count": 4,
                    "yellow_count": 1,
                    "issues": [1, 2, 3, 4, 5],
                    "task_contract": {"obligations": [{"code": "EVIDENCE_MATRIX"}]},
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)

    # Two days later: a red snapshot must be reported but flagged stale, not as
    # current truth.
    stale = module.collect_meta_runtime_state(
        now=datetime(2026, 6, 17, 14, 37, 13, tzinfo=timezone.utc)
    )
    assert stale["status"] == "ok"
    assert stale["overall"] == "red"
    assert stale["stale"] is True
    assert stale["age_seconds"] > 3600
    assert stale["age_label"] != "unknown"

    # Five minutes after the snapshot it is still fresh.
    fresh = module.collect_meta_runtime_state(
        now=datetime(2026, 6, 15, 14, 42, 13, tzinfo=timezone.utc)
    )
    assert fresh["stale"] is False


def test_codex_context_labels_meta_runtime_freshness():
    result = run_script("codex-context", "--no-network")
    assert result.returncode == 0, result.stderr
    meta_section = result.stdout.split("Meta Runtime", 1)[1].split("Guardian Health", 1)[0]
    if "state: ok" in meta_section:
        # The persisted snapshot is always presented with an age and an explicit
        # freshness verdict, never as bare current truth.
        assert " ago, " in meta_section
        assert ("fresh" in meta_section) or ("STALE" in meta_section)


def test_truth_status_treats_docs_only_drift_as_aligned(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "frontend" / "src").mkdir(parents=True)
    (project / "frontend" / "dist").mkdir(parents=True)
    (project / "src").mkdir()
    (project / "docs" / "context").mkdir(parents=True)
    (project / "frontend" / "src" / "main.js").write_text("console.log('x')\n", encoding="utf-8")
    (project / "frontend" / "index.html").write_text("<div></div>\n", encoding="utf-8")
    (project / "frontend" / "package.json").write_text("{}\n", encoding="utf-8")
    (project / "frontend" / "dist" / "index.html").write_text("<div></div>\n", encoding="utf-8")
    (project / "docs" / "context" / "NOW.md").write_text("rev A\n", encoding="utf-8")

    def git(*args):
        subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True)

    git("init")
    git("add", ".")
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-m", "A"],
        cwd=project, check=True, capture_output=True, text=True,
    )
    head_a = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=project, capture_output=True, text=True
    ).stdout.strip()

    # The deployed build/backend/nginx were all fingerprinted at commit A.
    (project / "frontend" / "dist" / "version.json").write_text(
        json.dumps({"git_hash": head_a, "build_time": "2026-06-17T00:00:00Z", "source_dirty": False}) + "\n",
        encoding="utf-8",
    )

    # HEAD advances by a docs-only commit -> no build input / source changed.
    (project / "docs" / "context" / "NOW.md").write_text("rev B\n", encoding="utf-8")
    git("add", ".")
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", "commit", "-m", "B docs only"],
        cwd=project, check=True, capture_output=True, text=True,
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        f"""#!/usr/bin/env bash
args="$*"
if [[ "$args" == *"-w"* ]]; then
  printf "200"
elif [[ "$args" == *"mcu.asia/version.json"* ]]; then
  printf '{{"git_hash":"{head_a}"}}'
elif [[ "$args" == *"127.0.0.1:9000"* ]]; then
  printf '{{"git_hash":"{head_a}","boot_time":"test","pid":1}}'
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

    assert result.returncode == 0, result.stdout + result.stderr
    # A docs-only trail is not a break, but the diagnosis must not falsely claim
    # the deployed hash matches HEAD; it reports FUNCTIONALLY ALIGNED instead.
    assert "BROKEN AT:" not in result.stdout
    assert "FUNCTIONALLY ALIGNED" in result.stdout
    assert "trails HEAD only by docs/governance/test/observability commits" in result.stdout
    assert "ALL ALIGNED — source, build, nginx, backend versions match" not in result.stdout
    assert "docs/governance-only" in result.stdout


def test_tests_workflow_has_cost_guardrails_for_expensive_jobs():
    """Backend/frontend CI should not run for every docs/governance-only push."""
    import yaml

    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "test.yml"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = yaml.safe_load(workflow_text)

    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert workflow["jobs"]["changes"]["outputs"]["backend"]
    assert workflow["jobs"]["changes"]["outputs"]["frontend"]

    backend = workflow["jobs"]["backend"]
    frontend = workflow["jobs"]["frontend"]

    assert backend["needs"] == "changes"
    assert frontend["needs"] == "changes"
    assert backend["if"] == "needs.changes.outputs.backend == 'true'"
    assert frontend["if"] == "needs.changes.outputs.frontend == 'true'"
    assert '"Dockerfile"' in workflow_text
    assert '"deploy/"' in workflow_text
    assert "|| true" not in workflow_text
    assert "continue-on-error: true" not in workflow_text
    assert "scripts/governance/check_execution_policy.py" in workflow_text
