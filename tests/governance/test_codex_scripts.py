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


def test_codex_context_no_network_outputs_project_sections():
    result = run_script("codex-context", "--no-network")

    assert result.returncode == 0, result.stderr
    assert "Codex Context" in result.stdout
    assert "元守双核心" in result.stdout
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
    assert "元守双核心" in model_text
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
    assert "元守双核心" in agents_text
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


def test_yuanshou_name_has_no_old_active_doc_aliases():
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
        assert "元守双核心" in normalized or path.name == "SAFETY_MATRIX.md"
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


def test_guardian_model_review_is_read_only_and_rate_limited(tmp_path):
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
        return subprocess.CompletedProcess(cmd, 0, "readonly review", "")

    config = module.WatchConfig(
        model_review=True,
        model_review_interval=3600,
        model_review_dir=tmp_path,
    )

    first = module.maybe_run_model_review(snapshot, state, config, now=1000, runner=fake_runner)
    second = module.maybe_run_model_review(snapshot, state, config, now=1001, runner=fake_runner)

    assert first["status"] == "ran"
    assert second["status"] == "skipped"
    assert len(calls) == 1
    command_text = " ".join(str(part) for part in calls[0])
    assert "scripts/codex-consult-claude" in command_text
    assert "risk" in command_text
    assert "dangerously-skip-permissions" not in command_text
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
    assert {"EVIDENCE_MATRIX", "CLAUDE_REVIEW", "IMPLEMENT_AND_VERIFY"} <= obligations
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
                            {"code": "CLAUDE_REVIEW", "summary": "review"},
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

    assert any(issue["issue_code"] == "TASK_CONTRACT_DRIFT" for issue in issues)


def test_meta_runtime_write_state_is_atomic_and_readable(tmp_path):
    module = load_meta_runtime_module()
    state_file = tmp_path / "meta-state.json"
    snapshot = module.build_snapshot(project_root=PROJECT_ROOT, task="测试写入状态", include_git=False)

    module.write_state(state_file, snapshot)

    parsed = json.loads(state_file.read_text(encoding="utf-8"))
    assert parsed["schema"] == "meta.state.v1"
    assert parsed["latest_snapshot"]["schema"] == "meta.core.v1"
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
    assert "Meta Core task contract" in result.stdout
    assert "Do not edit files" in result.stdout


def test_codex_consult_claude_injects_meta_state_obligations(monkeypatch, tmp_path):
    module = load_codex_consult_module()
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "meta-state.json").write_text(
        json.dumps(
            {
                "schema": "meta.state.v1",
                "latest_snapshot": {
                    "overall": "green",
                    "task_contract": {
                        "obligations": [
                            {"code": "EVIDENCE_MATRIX", "summary": "produce evidence-backed findings"},
                            {"code": "CLAUDE_REVIEW", "summary": "run read-only review"},
                        ]
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)

    prompt = module.build_user_prompt("review", "check meta core")

    assert "Current Meta Core task contract" in prompt
    assert "EVIDENCE_MATRIX" in prompt
    assert "CLAUDE_REVIEW" in prompt


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
    assert "scripts/meta-check --strict" in result.stdout
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
        "python -m py_compile scripts/codex_support.py scripts/codex-context scripts/codex-check scripts/codex-consult-claude scripts/codex-verify scripts/meta_runtime.py scripts/meta-check scripts/guardian_runtime.py scripts/guardian-watch scripts/run-arq-worker",
        "python -m py_compile scripts/governance/aggregate_modules.py scripts/governance/check_ai_tool_modules.py scripts/governance/check_module_dependencies.py scripts/governance/check_permission_mirror.py scripts/governance/module_governance_guard.py",
        "python -m pytest tests/governance/test_codex_scripts.py -q",
        "python -m pytest tests/governance/test_aggregate_modules.py tests/governance/test_ai_tool_modules.py tests/governance/test_module_dependencies.py tests/governance/test_module_governance_guard.py tests/governance/test_permission_mirror.py tests/governance/test_portal_contract.py tests/governance/test_tenant_static.py -q",
        "python scripts/governance/aggregate_modules.py --check",
        "python scripts/governance/check_ai_tool_modules.py",
        "python scripts/governance/check_module_dependencies.py --check",
        "python scripts/governance/check_permission_mirror.py",
        "python scripts/governance/module_governance_guard.py --git-hook-mode --repo \"$(pwd)\"",
        "scripts/codex-check --no-network",
        "scripts/meta-check --json --strict",
        "scripts/codex-context --no-network",
        "scripts/codex-consult-claude --dry-run review CI smoke",
        "scripts/codex-verify safety --repo-wide",
        "scripts/codex-verify full --dry-run --schema --no-network",
        "python -m pytest tests/test_alembic_migration.py -q",
        "cd frontend && npm run build",
    ):
        assert command in text
