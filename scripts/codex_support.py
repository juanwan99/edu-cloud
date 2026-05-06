"""Shared helpers for Codex-native context and verification scripts."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWN_FAILURES = PROJECT_ROOT / ".quality" / "known-pytest-failures.txt"
SYSTEMD_SERVICES = ("edu-cloud", "llm-proxy", "edu-cloud-worker", "edu-cloud-guardian")
EXPECTED_PORTS = {
    9000: {"label": "edu-cloud API", "service": "edu-cloud", "required": True},
    8080: {"label": "Vite dev server", "service": None, "required": False},
    8100: {"label": "llm-proxy", "service": "llm-proxy", "required": False},
}


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
            data["backend_boot_time"] = parsed.get("boot_time")
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


def systemd_main_pids() -> dict[int, str]:
    services: dict[int, str] = {}
    for service in SYSTEMD_SERVICES:
        result = run(["systemctl", "show", service, "-p", "MainPID", "--value"], timeout=5)
        value = result.stdout.strip()
        if value.isdigit() and value != "0":
            services[int(value)] = service
    return services


def process_details(pid: int) -> dict[str, object]:
    result = run(["ps", "-p", str(pid), "-o", "ppid=,command="], timeout=5)
    if result.returncode != 0:
        return {"pid": pid, "ppid": None, "command": "", "cgroup": "", "cgroup_service": None}
    text = result.stdout.strip()
    if not text:
        return {"pid": pid, "ppid": None, "command": "", "cgroup": "", "cgroup_service": None}
    parts = text.split(maxsplit=1)
    ppid = int(parts[0]) if parts and parts[0].isdigit() else None
    command = parts[1] if len(parts) > 1 else ""
    cgroup = process_cgroup(pid)
    return {
        "pid": pid,
        "ppid": ppid,
        "command": command,
        "cgroup": cgroup,
        "cgroup_service": service_from_cgroup(cgroup),
    }


def process_cgroup(pid: int) -> str:
    path = Path("/proc") / str(pid) / "cgroup"
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def service_from_cgroup(cgroup: str) -> str | None:
    for service in SYSTEMD_SERVICES:
        if f"{service}.service" in cgroup:
            return service
    return None


def parse_ss_listeners(output: str) -> list[dict[str, object]]:
    listeners: list[dict[str, object]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 4:
            continue
        local = parts[3]
        if ":" not in local:
            continue
        bind, port_text = local.rsplit(":", 1)
        if not port_text.isdigit():
            continue
        pid_match = re.search(r"pid=(\d+)", stripped)
        process_match = re.search(r'users:\(\("([^"]+)"', stripped)
        listeners.append({
            "port": int(port_text),
            "bind": bind,
            "pid": int(pid_match.group(1)) if pid_match else None,
            "process": process_match.group(1) if process_match else None,
            "raw": stripped,
        })
    return listeners


def _api_version_for_port(port: int) -> dict[str, object]:
    result = run(["curl", "-sf", f"http://127.0.0.1:{port}/api/v1/version"], timeout=2)
    if result.returncode != 0:
        return {}
    try:
        parsed = json.loads(result.stdout)
    except Exception:
        return {"version_status": "unreadable"}
    return {
        "version_status": "ok",
        "version_hash": parsed.get("git_hash"),
        "version_source_dirty": parsed.get("source_dirty"),
        "version_pid": parsed.get("pid"),
        "version_boot_time": parsed.get("boot_time"),
    }


def collect_ports() -> dict[str, object]:
    result = run(["ss", "-H", "-tlnp"], timeout=10)
    if result.returncode != 0:
        return {"status": "failed", "returncode": result.returncode, "listeners": []}
    services = systemd_main_pids()
    listeners = parse_ss_listeners(result.stdout)
    for listener in listeners:
        pid = listener.get("pid")
        if isinstance(pid, int):
            details = process_details(pid)
            listener["ppid"] = details.get("ppid")
            listener["command"] = details.get("command")
            listener["cgroup"] = details.get("cgroup")
            listener["service"] = services.get(pid) or details.get("cgroup_service")
            command = str(listener.get("command") or "")
            if "edu_cloud.api.app" in command:
                listener.update(_api_version_for_port(int(listener["port"])))
    expected = {
        str(port): {**meta, "present": any(item.get("port") == port for item in listeners)}
        for port, meta in EXPECTED_PORTS.items()
    }
    return {"status": "ok", "listeners": listeners, "expected": expected}


def collect_processes() -> dict[str, object]:
    service_pids = systemd_main_pids()
    service_by_name = {service: pid for pid, service in service_pids.items()}
    processes: list[dict[str, object]] = []
    current_pid = os.getpid()
    result = run([
        "pgrep",
        "-af",
        r"edu_cloud\.api\.app|scripts/run-arq-worker|guardian-watch|llm_proxy\.app|edu_cloud\.worker|arq.*worker",
    ], timeout=10)
    if result.returncode in (0, 1):
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            pid_text, _, command = stripped.partition(" ")
            if not pid_text.isdigit():
                continue
            pid = int(pid_text)
            if pid == current_pid:
                continue
            if "codex-consult-claude" in command or "--no-session-persistence" in command:
                continue
            if "guardian-watch --once" in command:
                continue
            details = process_details(pid)
            processes.append({
                "pid": pid,
                "ppid": details.get("ppid"),
                "command": command,
                "cgroup": details.get("cgroup"),
                "service": service_pids.get(pid) or details.get("cgroup_service"),
                "is_systemd_main": pid in service_pids,
            })
    return {
        "status": "ok" if result.returncode in (0, 1) else "failed",
        "services": service_by_name,
        "project_processes": processes,
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
