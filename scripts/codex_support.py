"""Shared helpers for Codex-native context and verification scripts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWN_FAILURES = PROJECT_ROOT / ".quality" / "known-pytest-failures.txt"


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


def run(args: list[str], timeout: int = 10, cwd: Path | None = None) -> CommandResult:
    try:
        result = subprocess.run(
            args,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:  # pragma: no cover - defensive path
        return CommandResult(args=args, returncode=99, stdout="", stderr=str(exc))
    return CommandResult(args=args, returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)


def git(*args: str, timeout: int = 10) -> CommandResult:
    return run(["git", *args], timeout=timeout)


def git_text(*args: str, timeout: int = 10) -> str:
    result = git(*args, timeout=timeout)
    return result.stdout.strip() if result.returncode == 0 else ""


def status_entries() -> list[str]:
    out = git_text("status", "--porcelain=v1", "--untracked-files=all")
    return [line for line in out.splitlines() if line]


def dirty_paths(prefixes: tuple[str, ...]) -> list[str]:
    paths: list[str] = []
    for line in status_entries():
        if len(line) < 4:
            continue
        path = line[3:]
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if path.startswith(prefixes):
            paths.append(path)
    return paths


def count_known_failures() -> int:
    if not KNOWN_FAILURES.exists():
        return 0
    count = 0
    for line in KNOWN_FAILURES.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def collect_git() -> dict[str, object]:
    branch = git_text("branch", "--show-current") or "unknown"
    head = git_text("rev-parse", "--short", "HEAD") or "unknown"
    upstream = git_text("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") or "none"
    ahead = 0
    if upstream != "none":
        ahead_text = git_text("rev-list", "--count", f"{upstream}..HEAD")
        ahead = int(ahead_text) if ahead_text.isdigit() else 0
    entries = status_entries()
    return {
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "ahead": ahead,
        "status_entries": len(entries),
        "backend_dirty": len(dirty_paths(("src/",))),
        "frontend_dirty": len(dirty_paths((
            "frontend/src/",
            "frontend/public/",
            "frontend/package.json",
            "frontend/package-lock.json",
            "frontend/vite.config",
            "frontend/vitest.config",
            "frontend/index.html",
        ))),
        "tests_dirty": len(dirty_paths(("tests/", "test_"))),
        "docs_dirty": len(dirty_paths(("docs/", "AGENTS.md"))),
    }


def path_has_open_handle(path: Path) -> bool:
    if not shutil.which("fuser"):
        return False
    result = run(["fuser", str(path)], timeout=5)
    return result.returncode == 0


def collect_artifacts() -> dict[str, object]:
    risky = []
    runtime = []
    for name in ("edu_cloud.db-wal", "edu_cloud.db-shm"):
        path = PROJECT_ROOT / name
        if not path.exists():
            continue
        if path_has_open_handle(path):
            runtime.append(name)
        else:
            risky.append(name)
    for name in ("data/.db_migrate.lock", ".codex", "frontend/.codex"):
        if (PROJECT_ROOT / name).exists():
            risky.append(name)
    return {
        "risky_paths": risky,
        "runtime_paths": runtime,
        "backups_exists": (PROJECT_ROOT / "backups").exists(),
        "screenshots_exists": (PROJECT_ROOT / "screenshots").exists(),
    }


def collect_versions(no_network: bool = False) -> dict[str, object]:
    data: dict[str, object] = {"network": "skipped" if no_network else "enabled"}
    version_json = PROJECT_ROOT / "frontend" / "dist" / "version.json"
    if version_json.exists():
        try:
            parsed = json.loads(version_json.read_text(encoding="utf-8"))
            data["dist_hash"] = parsed.get("git_hash")
            data["dist_source_dirty"] = parsed.get("source_dirty")
            data["dist_build_time"] = parsed.get("build_time")
        except Exception:
            data["dist_hash"] = "unreadable"
    if not no_network:
        remote = run(["curl", "-sf", "https://mcu.asia/version.json"], timeout=5)
        if remote.returncode == 0:
            try:
                data["nginx_hash"] = json.loads(remote.stdout).get("git_hash")
            except Exception:
                data["nginx_hash"] = "unreadable"
        backend = run(["curl", "-sf", "http://127.0.0.1:9000/api/v1/version"], timeout=5)
        if backend.returncode == 0:
            try:
                parsed = json.loads(backend.stdout)
                data["backend_hash"] = parsed.get("git_hash")
                data["backend_source_dirty"] = parsed.get("source_dirty")
                data["backend_pid"] = parsed.get("pid")
            except Exception:
                data["backend_hash"] = "unreadable"
    return data


def collect_db() -> dict[str, object]:
    py = PROJECT_ROOT / ".venv" / "bin" / "python"
    if not py.exists():
        return {"status": "python_missing"}
    result = run([str(py), "scripts/db_doctor.py", "--json"], timeout=20)
    if result.returncode != 0:
        return {"status": "failed", "returncode": result.returncode}
    try:
        parsed = json.loads(result.stdout)
    except Exception:
        return {"status": "unreadable"}
    return {
        "status": "ok",
        "alembic_version": parsed.get("alembic_version"),
        "hard": parsed.get("hard"),
        "warn": parsed.get("warn"),
        "orm_tables": parsed.get("orm_tables"),
        "db_tables": parsed.get("db_tables"),
    }


def collect_guardian_health() -> dict[str, object]:
    result = run([str(PROJECT_ROOT / "scripts" / "truth-doctor.sh"), str(PROJECT_ROOT), "--json"], timeout=30)
    if result.returncode != 0:
        return {"status": "failed", "returncode": result.returncode}
    try:
        parsed = json.loads(result.stdout)
    except Exception:
        return {"status": "unreadable"}
    return {
        "status": "ok",
        "overall": parsed.get("overall"),
        "issue_count": parsed.get("issue_count", len(parsed.get("issues", []))),
        "red_count": parsed.get("red_count", 0),
        "yellow_count": parsed.get("yellow_count", 0),
        "issues": parsed.get("issues", []),
    }


def collect_guardian_runtime_state() -> dict[str, object]:
    state_file = PROJECT_ROOT / "logs" / "guardian-state.json"
    service = run(["systemctl", "is-active", "edu-cloud-guardian"], timeout=5)
    service_state = service.stdout.strip() if service.returncode == 0 else "inactive"
    if not state_file.exists():
        return {"status": "missing", "service": service_state, "state_file": str(state_file)}
    try:
        parsed = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unreadable", "service": service_state, "state_file": str(state_file)}
    latest = parsed.get("latest_snapshot") if isinstance(parsed, dict) else {}
    runtime_state = parsed.get("runtime_state") if isinstance(parsed, dict) else {}
    if not isinstance(latest, dict):
        latest = {}
    if not isinstance(runtime_state, dict):
        runtime_state = {}
    return {
        "status": "ok",
        "service": service_state,
        "state_file": str(state_file),
        "updated_at": parsed.get("updated_at") if isinstance(parsed, dict) else None,
        "snapshot_at": latest.get("generated_at"),
        "overall": latest.get("overall"),
        "red_count": latest.get("red_count"),
        "yellow_count": latest.get("yellow_count"),
        "fingerprint": latest.get("fingerprint"),
        "issue_count": len(latest.get("issues", [])) if isinstance(latest.get("issues"), list) else None,
        "model_review": latest.get("model_review"),
        "last_model_review": runtime_state.get("model_review"),
    }


def collect_meta_runtime_state() -> dict[str, object]:
    state_file = PROJECT_ROOT / "logs" / "meta-state.json"
    if not state_file.exists():
        return {"status": "missing", "state_file": str(state_file)}
    try:
        parsed = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unreadable", "state_file": str(state_file)}
    latest = parsed.get("latest_snapshot") if isinstance(parsed, dict) else {}
    if not isinstance(latest, dict):
        latest = {}
    contract = latest.get("task_contract")
    if not isinstance(contract, dict):
        contract = {}
    obligations = contract.get("obligations")
    if not isinstance(obligations, list):
        obligations = []
    return {
        "status": "ok",
        "state_file": str(state_file),
        "updated_at": parsed.get("updated_at") if isinstance(parsed, dict) else None,
        "snapshot_at": latest.get("generated_at"),
        "overall": latest.get("overall"),
        "red_count": latest.get("red_count"),
        "yellow_count": latest.get("yellow_count"),
        "issue_count": len(latest.get("issues", [])) if isinstance(latest.get("issues"), list) else None,
        "obligation_count": len(obligations),
    }


def safety_risks(no_network: bool = False) -> list[str]:
    git_info = collect_git()
    artifacts = collect_artifacts()
    versions = collect_versions(no_network=no_network)
    risks: list[str] = []
    if git_info["ahead"]:
        risks.append(f"branch is ahead of upstream by {git_info['ahead']} commit(s)")
    if git_info["backend_dirty"]:
        risks.append(f"backend source dirty: {git_info['backend_dirty']} file(s)")
    if git_info["frontend_dirty"]:
        risks.append(f"frontend build inputs dirty: {git_info['frontend_dirty']} file(s)")
    if artifacts["risky_paths"]:
        risks.append("risky local artifacts present: " + ", ".join(artifacts["risky_paths"]))
    if versions.get("backend_source_dirty") is True:
        risks.append("running backend reports source_dirty=true")
    return risks


def print_kv(label: str, value: object, indent: int = 2) -> None:
    print(" " * indent + f"{label}: {value}")
