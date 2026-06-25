"""Realtime Guardian runtime for edu-cloud.

This module deliberately stays advisory by default: it observes, writes state,
and can schedule a read-only model review. It does not kill processes, mutate
git state, copy databases, or delete runtime artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from codex_support import (
    PROJECT_ROOT,
    classify_hash_drift,
    collect_artifacts,
    collect_db,
    collect_git,
    collect_guardian_health,
    collect_ports,
    collect_processes,
    collect_versions,
    safety_risks,
)


SCHEMA = "guardian.watch.v1"
STATE_SCHEMA = "guardian.state.v1"
JSONL_MAX_BYTES = 10 * 1024 * 1024
JSONL_BACKUPS = 5


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass
class WatchConfig:
    interval: int = 15
    no_network: bool = False
    state_file: Path = PROJECT_ROOT / "logs" / "guardian-state.json"
    jsonl_file: Path | None = PROJECT_ROOT / "logs" / "guardian-watch.jsonl"
    model_review: bool = False
    model_review_backend: str = "off"
    model_review_interval: int = 3600
    model_review_dir: Path = PROJECT_ROOT / "logs"
    model_review_timeout: int = 300
    model_review_command: str | None = None
    strict: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def severity_rank(value: str) -> int:
    return {"green": 0, "yellow": 1, "red": 2}.get(value, 1)


def issue(
    code: str,
    severity: str,
    summary: str,
    command_hint: str,
    *,
    blocks_completion: bool = False,
    required_before: str = "completion",
    source: str = "guardian-watch",
) -> dict[str, Any]:
    return {
        "issue_code": code,
        "severity": severity,
        "summary": summary,
        "blocks_completion": blocks_completion,
        "required_before": required_before,
        "command_hint": command_hint,
        "source": source,
    }


def normalize_truth_issue(raw: dict[str, Any]) -> dict[str, Any]:
    code = str(raw.get("issue_code") or raw.get("code") or "TRUTH_DOCTOR_ISSUE")
    severity = str(raw.get("severity") or ("red" if raw.get("blocks_completion") else "yellow"))
    if severity not in {"green", "yellow", "red"}:
        severity = "yellow"
    return issue(
        code,
        severity,
        str(raw.get("summary") or code),
        str(raw.get("command_hint") or "scripts/truth doctor --json"),
        blocks_completion=bool(raw.get("blocks_completion")),
        required_before=str(raw.get("required_before") or "completion"),
        source="truth-doctor",
    )


def issues_from_safety_risks(risks: list[str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for risk in risks:
        lower = risk.lower()
        if "ahead of upstream" in lower:
            issues.append(
                issue(
                    "UNPUSHED_COMMITS",
                    "yellow",
                    risk,
                    "git status --short --branch && git push",
                    blocks_completion=False,
                    required_before="handoff",
                    source="codex_support.safety_risks",
                )
            )
        elif "backend source dirty" in lower:
            issues.append(
                issue(
                    "BACKEND_DIRTY",
                    "red",
                    risk,
                    "git status --short -- src tests alembic.ini pyproject.toml",
                    blocks_completion=True,
                    source="codex_support.safety_risks",
                )
            )
        elif "frontend build inputs dirty" in lower:
            issues.append(
                issue(
                    "FRONTEND_DIRTY",
                    "red",
                    risk,
                    "git status --short -- frontend",
                    blocks_completion=True,
                    source="codex_support.safety_risks",
                )
            )
        elif "source_dirty=true" in lower:
            issues.append(
                issue(
                    "BACKEND_RUNTIME_DIRTY",
                    "red",
                    risk,
                    "scripts/truth-status.sh /home/ops/projects/edu-cloud",
                    blocks_completion=True,
                    source="codex_support.safety_risks",
                )
            )
        elif "risky local artifacts" in lower:
            issues.append(
                issue(
                    "RISKY_ARTIFACT",
                    "yellow",
                    risk,
                    "scripts/codex-context --no-network",
                    blocks_completion=False,
                    required_before="session_end",
                    source="codex_support.safety_risks",
                )
            )
        else:
            issues.append(
                issue(
                    "SAFETY_RISK",
                    "yellow",
                    risk,
                    "scripts/codex-check --strict",
                    blocks_completion=False,
                    source="codex_support.safety_risks",
                )
            )
    return issues


def issues_from_artifacts(artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    risky_paths = list(artifacts.get("risky_paths") or [])
    if not risky_paths:
        return []
    return [
        issue(
            "RISKY_ARTIFACT",
            "yellow",
            "risky local artifacts present: " + ", ".join(str(path) for path in risky_paths),
            "scripts/codex-context --no-network",
            blocks_completion=False,
            required_before="session_end",
            source="codex_support.collect_artifacts",
        )
    ]


def hash_drift_issue(
    code: str,
    deployed: str,
    reference: str,
    *,
    runtime_summary: str,
    docs_summary: str,
    command_hint: str,
    source: str,
    docs_command_hint: str | None = None,
) -> dict[str, Any]:
    """Build a drift issue whose severity reflects what actually changed.

    A docs/governance-only difference between the deployed hash and the
    reference hash is a non-blocking informational drift; a real source /
    build-input / dependency / deploy change (or an unresolvable diff) stays a
    blocking red runtime drift.
    """
    drift = classify_hash_drift(deployed, reference)
    if drift.get("status") == "docs_only":
        return issue(
            f"{code}_DOCS",
            "yellow",
            docs_summary,
            docs_command_hint or command_hint,
            blocks_completion=False,
            required_before="handoff",
            source=source,
        )
    paths_obj = drift.get("paths")
    paths = [str(path) for path in paths_obj] if isinstance(paths_obj, list) else []
    if drift.get("status") == "runtime" and paths:
        detail = f"; runtime files changed: {', '.join(paths[:5])}"
    else:
        detail = "; drift classification unavailable, treated as runtime"
    return issue(
        code,
        "red",
        runtime_summary + detail,
        command_hint,
        blocks_completion=True,
        source=source,
    )


def issues_from_versions(versions: dict[str, Any], git_info: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    head = str(git_info.get("head") or "")
    dist_hash = versions.get("dist_hash")
    nginx_hash = versions.get("nginx_hash")
    backend_hash = versions.get("backend_hash")
    worker_hash = versions.get("worker_hash")
    worker_service_pid = versions.get("worker_service_pid")
    if versions.get("dist_source_dirty") is True:
        issues.append(
            issue(
                "BUILD_DRIFT",
                "red",
                "frontend/dist/version.json has source_dirty=true",
                "cd frontend && npm run build",
                blocks_completion=True,
                source="codex_support.collect_versions",
            )
        )
    if head and head != "unknown" and dist_hash and dist_hash not in {"unknown", "unreadable"} and dist_hash != head:
        issues.append(
            hash_drift_issue(
                "BUILD_DRIFT",
                str(dist_hash),
                head,
                runtime_summary=f"frontend dist hash {dist_hash} does not match HEAD {head}",
                docs_summary=(
                    f"frontend dist hash {dist_hash} trails HEAD {head} by docs/governance-only "
                    "commits; no build input changed, deployed bundle is functionally current"
                ),
                command_hint="scripts/codex-verify frontend",
                source="codex_support.collect_versions",
            )
        )
    if dist_hash and nginx_hash and nginx_hash not in {"unknown", "unreadable"} and nginx_hash != dist_hash:
        issues.append(
            hash_drift_issue(
                "NGINX_DRIFT",
                str(nginx_hash),
                str(dist_hash),
                runtime_summary=f"nginx version hash {nginx_hash} does not match local dist {dist_hash}",
                docs_summary=(
                    f"nginx version hash {nginx_hash} trails local dist {dist_hash} by "
                    "docs/governance-only commits; served bundle is functionally current"
                ),
                command_hint="scripts/codex-verify frontend",
                source="codex_support.collect_versions",
            )
        )
    if head and head != "unknown" and backend_hash and backend_hash not in {"unknown", "unreadable"} and backend_hash != head:
        issues.append(
            hash_drift_issue(
                "BACKEND_DRIFT",
                str(backend_hash),
                head,
                runtime_summary=f"backend hash {backend_hash} does not match HEAD {head}",
                docs_summary=(
                    f"backend hash {backend_hash} trails HEAD {head} by docs/governance-only "
                    "commits; running backend is functionally current"
                ),
                command_hint="sudo systemctl restart edu-cloud",
                docs_command_hint="git log --oneline " + f"{backend_hash}..{head}",
                source="codex_support.collect_versions",
            )
        )
    if versions.get("backend_source_dirty") is True:
        issues.append(
            issue(
                "BACKEND_RUNTIME_DIRTY",
                "red",
                "backend /api/v1/version reports source_dirty=true",
                "scripts/truth-status.sh /home/ops/projects/edu-cloud",
                blocks_completion=True,
                source="codex_support.collect_versions",
            )
        )

    if worker_service_pid:
        worker_status = versions.get("worker_status")
        worker_path = versions.get("worker_status_path") or "logs/worker-runtime.json"
        if worker_status != "ok" or not worker_hash or worker_hash in {"unknown", "unreadable"}:
            issues.append(
                issue(
                    "WORKER_VERSION_MISSING",
                    "red",
                    f"edu-cloud-worker PID={worker_service_pid} has no readable runtime fingerprint at {worker_path}",
                    "sudo systemctl restart edu-cloud-worker && scripts/truth-status.sh /home/ops/projects/edu-cloud",
                    blocks_completion=True,
                    source="codex_support.collect_versions",
                )
            )
        elif versions.get("worker_pid_mismatch") is True:
            issues.append(
                issue(
                    "WORKER_STATUS_STALE",
                    "red",
                    f"worker runtime fingerprint PID={versions.get('worker_pid')} does not match service PID={worker_service_pid}",
                    "sudo systemctl restart edu-cloud-worker && scripts/truth-status.sh /home/ops/projects/edu-cloud",
                    blocks_completion=True,
                    source="codex_support.collect_versions",
                )
            )
        elif head and head != "unknown" and worker_hash != head:
            issues.append(
                hash_drift_issue(
                    "WORKER_DRIFT",
                    str(worker_hash),
                    head,
                    runtime_summary=f"worker hash {worker_hash} does not match HEAD {head}",
                    docs_summary=(
                        f"worker hash {worker_hash} trails HEAD {head} by docs/governance-only "
                        "commits; running worker is functionally current"
                    ),
                    command_hint="sudo systemctl restart edu-cloud-worker",
                    docs_command_hint="git log --oneline " + f"{worker_hash}..{head}",
                    source="codex_support.collect_versions",
                )
            )
        if versions.get("worker_source_dirty") is True:
            issues.append(
                issue(
                    "WORKER_RUNTIME_DIRTY",
                    "red",
                    "worker runtime fingerprint reports source_dirty=true",
                    "git diff -- src/ scripts/run-arq-worker pyproject.toml uv.lock; sudo systemctl restart edu-cloud-worker after clean deploy",
                    blocks_completion=True,
                    source="codex_support.collect_versions",
                )
            )
    return issues


def is_public_bind(bind: object) -> bool:
    value = str(bind or "")
    return value in {"0.0.0.0", "[::]", "::", "*"}


def issues_from_ports(ports: dict[str, Any], git_info: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if ports.get("status") not in {"ok", None}:
        return [
            issue(
                "PORT_INVENTORY_FAILED",
                "yellow",
                f"port inventory status={ports.get('status')}",
                "ss -tlnp",
                required_before="handoff",
                source="codex_support.collect_ports",
            )
        ]

    listeners = [item for item in ports.get("listeners", []) if isinstance(item, dict)]
    expected = ports.get("expected", {}) if isinstance(ports.get("expected"), dict) else {}
    for port_text, meta in expected.items():
        if not isinstance(meta, dict):
            continue
        if meta.get("required") and not meta.get("present"):
            issues.append(
                issue(
                    "EXPECTED_PORT_MISSING",
                    "red",
                    f"required port {port_text} ({meta.get('label')}) has no listener",
                    f"systemctl status {meta.get('service') or 'edu-cloud'}",
                    blocks_completion=True,
                    source="codex_support.collect_ports",
                )
            )

    listeners_by_port: dict[int, list[dict[str, Any]]] = {}
    for item in listeners:
        port = item.get("port")
        if isinstance(port, int):
            listeners_by_port.setdefault(port, []).append(item)
    for port, port_list in sorted(listeners_by_port.items()):
        guarded = str(port) in expected or any("edu_cloud.api.app" in str(item.get("command") or "") for item in port_list)
        if guarded and len(port_list) > 1:
            pids = ", ".join(str(item.get("pid") or "unknown") for item in port_list)
            issues.append(
                issue(
                    "PORT_CONFLICT",
                    "red" if port == 9000 else "yellow",
                    f"port {port} has {len(port_list)} listener(s): PID={pids}",
                    f"ss -tlnp 'sport = :{port}'",
                    blocks_completion=port == 9000,
                    required_before="handoff",
                    source="codex_support.collect_ports",
                )
            )

    head = str(git_info.get("head") or "")
    for item in listeners:
        port = item.get("port")
        bind = item.get("bind")
        command = str(item.get("command") or "")
        service = item.get("service")
        is_vite_dev = "vite" in command and "/edu-cloud/frontend/" in command
        public_bind = is_public_bind(bind)
        if (port in {9000, 8080, 8100} or is_vite_dev) and public_bind:
            issues.append(
                issue(
                    "PORT_PUBLIC_BIND",
                    "red" if port in {9000, 8080} or is_vite_dev else "yellow",
                    f"port {port} is bound to {bind}",
                    "scripts/truth doctor --json",
                    blocks_completion=port in {9000, 8080} or is_vite_dev,
                    source="codex_support.collect_ports",
                )
            )
        if is_vite_dev and port != 8080:
            issues.append(
                issue(
                    "PARALLEL_FRONTEND_DEV_SERVER",
                    "red" if public_bind else "yellow",
                    f"edu-cloud Vite dev server PID={item.get('pid')} on {bind}:{port}",
                    f"inspect PID {item.get('pid')} and stop the stale frontend dev server if not current",
                    blocks_completion=public_bind,
                    required_before="handoff",
                    source="codex_support.collect_ports",
                )
            )
        if "edu_cloud.api.app" in command and port != 9000:
            public = is_public_bind(bind)
            issues.append(
                issue(
                    "PARALLEL_BACKEND_PROCESS",
                    "red" if public else "yellow",
                    f"parallel edu-cloud backend PID={item.get('pid')} on {bind}:{port}",
                    f"inspect PID {item.get('pid')} and stop the debug backend if stale",
                    blocks_completion=public,
                    required_before="handoff",
                    source="codex_support.collect_ports",
                )
            )
        if port == 9000 and "edu_cloud.api.app" in command and service != "edu-cloud":
            issues.append(
                issue(
                    "PORT_OWNER_MISMATCH",
                    "red",
                    f"port 9000 is owned by {service}, expected edu-cloud",
                    "systemctl status edu-cloud",
                    blocks_completion=True,
                    source="codex_support.collect_ports",
                )
            )
        version_hash = item.get("version_hash")
        if head and version_hash and version_hash != head:
            issues.append(
                hash_drift_issue(
                    "PARALLEL_VERSION_DRIFT",
                    str(version_hash),
                    head,
                    runtime_summary=f"backend on port {port} reports {version_hash}, source HEAD is {head}",
                    docs_summary=(
                        f"backend on port {port} reports {version_hash}, trailing HEAD {head} by "
                        "docs/governance-only commits; running code is functionally current"
                    ),
                    command_hint=f"inspect PID {item.get('pid')} and restart/stop the stale backend",
                    docs_command_hint=f"git log --oneline {version_hash}..{head}",
                    source="codex_support.collect_ports",
                )
            )
        if item.get("version_source_dirty") is True:
            issues.append(
                issue(
                    "PARALLEL_RUNTIME_DIRTY",
                    "red",
                    f"backend on port {port} reports source_dirty=true",
                    f"inspect PID {item.get('pid')} and restart from clean source",
                    blocks_completion=True,
                    source="codex_support.collect_ports",
                )
            )
    return issues


def issues_from_processes(processes: dict[str, Any]) -> list[dict[str, Any]]:
    if processes.get("status") not in {"ok", None}:
        return [
            issue(
                "PROCESS_INVENTORY_FAILED",
                "yellow",
                f"process inventory status={processes.get('status')}",
                "pgrep -af 'edu_cloud|run-arq-worker|guardian-watch'",
                required_before="handoff",
                source="codex_support.collect_processes",
            )
        ]

    project_processes = [
        item for item in processes.get("project_processes", [])
        if isinstance(item, dict)
    ]
    issues: list[dict[str, Any]] = []
    workers = [
        item for item in project_processes
        if re.search(r"scripts/run-arq-worker|edu_cloud\.worker|arq.*worker", str(item.get("command") or ""))
    ]
    non_systemd_workers = [item for item in workers if item.get("service") != "edu-cloud-worker"]
    if len(workers) > 1 or non_systemd_workers:
        pids = ", ".join(str(item.get("pid")) for item in workers)
        issues.append(
            issue(
                "DUPLICATE_WORKER_PROCESS",
                "yellow",
                f"{len(workers)} edu-cloud worker process(es) detected: {pids}",
                "systemctl status edu-cloud-worker; inspect non-systemd workers before stopping",
                blocks_completion=False,
                required_before="session_end",
                source="codex_support.collect_processes",
            )
        )

    guardians = [item for item in project_processes if "guardian-watch" in str(item.get("command") or "")]
    non_systemd_guardians = [item for item in guardians if item.get("service") != "edu-cloud-guardian"]
    if len(guardians) > 1 or non_systemd_guardians:
        pids = ", ".join(str(item.get("pid")) for item in guardians)
        issues.append(
            issue(
                "DUPLICATE_GUARDIAN_PROCESS",
                "yellow",
                f"{len(guardians)} Guardian process(es) detected: {pids}",
                "systemctl status edu-cloud-guardian; inspect extra guardian processes",
                blocks_completion=False,
                required_before="session_end",
                source="codex_support.collect_processes",
            )
        )
    return issues


def backend_runtimes_from_snapshot(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ports = snapshot.get("ports") if isinstance(snapshot.get("ports"), dict) else {}
    runtimes: dict[str, dict[str, Any]] = {}
    for item in (ports.get("listeners", []) if isinstance(ports, dict) else []):
        if not isinstance(item, dict):
            continue
        command = str(item.get("command") or "")
        if "edu_cloud.api.app" not in command and item.get("version_status") != "ok":
            continue
        port = item.get("port")
        if not isinstance(port, int):
            continue
        runtime = {
            "port": port,
            "pid": item.get("version_pid") or item.get("pid"),
            "git_hash": item.get("version_hash"),
            "source_dirty": item.get("version_source_dirty"),
            "boot_time": item.get("version_boot_time"),
            "bind": item.get("bind"),
            "service": item.get("service"),
        }
        runtimes[str(port)] = runtime
    return runtimes


def issues_from_runtime_transitions(snapshot: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    previous = state.get("backend_runtimes")
    if not isinstance(previous, dict):
        return []
    current = backend_runtimes_from_snapshot(snapshot)
    issues: list[dict[str, Any]] = []
    for port, runtime in current.items():
        old = previous.get(port)
        if not isinstance(old, dict):
            continue
        old_pid = old.get("pid")
        new_pid = runtime.get("pid")
        old_hash = old.get("git_hash")
        new_hash = runtime.get("git_hash")
        old_boot = old.get("boot_time")
        new_boot = runtime.get("boot_time")
        if old_pid and new_pid and old_pid == new_pid and old_hash and new_hash and old_hash != new_hash:
            issues.append(
                issue(
                    "BACKEND_HOT_RELOAD",
                    "yellow",
                    f"backend port {port} kept PID={new_pid} but git hash changed {old_hash}->{new_hash}",
                    f"inspect PID {new_pid}; restart through systemd if this was not intentional",
                    blocks_completion=False,
                    required_before="handoff",
                    source="guardian-watch.runtime_state",
                )
            )
        if old_pid and new_pid and old_pid == new_pid and old_boot and new_boot and old_boot != new_boot:
            issues.append(
                issue(
                    "BACKEND_HOT_RELOAD",
                    "yellow",
                    f"backend port {port} kept PID={new_pid} but boot_time changed {old_boot}->{new_boot}",
                    f"inspect PID {new_pid}; restart through systemd if this was not intentional",
                    blocks_completion=False,
                    required_before="handoff",
                    source="guardian-watch.runtime_state",
                )
            )
    return issues


def dedupe_issues(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (str(item.get("issue_code")), str(item.get("summary")))
        current = by_key.get(key)
        if current is None or severity_rank(str(item.get("severity"))) > severity_rank(str(current.get("severity"))):
            by_key[key] = item
    return sorted(
        by_key.values(),
        key=lambda item: (
            -severity_rank(str(item.get("severity"))),
            str(item.get("issue_code")),
            str(item.get("summary")),
        ),
    )


def rebuild_issue_summary(snapshot: dict[str, Any]) -> None:
    issues = dedupe_issues([item for item in snapshot.get("issues", []) if isinstance(item, dict)])
    red_count = sum(1 for item in issues if item.get("severity") == "red" or item.get("blocks_completion"))
    yellow_count = sum(1 for item in issues if item.get("severity") == "yellow" and not item.get("blocks_completion"))
    snapshot["issues"] = issues
    snapshot["red_count"] = red_count
    snapshot["yellow_count"] = yellow_count
    snapshot["overall"] = "red" if red_count else "yellow" if yellow_count else "green"
    snapshot["fingerprint"] = issue_fingerprint(issues)
    snapshot["actions"] = [
        {
            "issue_code": item.get("issue_code"),
            "required_before": item.get("required_before", "completion"),
            "command_hint": item.get("command_hint"),
            "blocks_completion": bool(item.get("blocks_completion")),
        }
        for item in issues
    ]


def issue_fingerprint(issues: list[dict[str, Any]]) -> str:
    payload = []
    for item in issues:
        code = item.get("issue_code")
        summary = item.get("summary")
        if code == "WORKTREE_DIRTY":
            summary = "working tree dirty"
        if code in {"GHOST_PROCESS", "DUPLICATE_WORKER_PROCESS", "DUPLICATE_GUARDIAN_PROCESS", "PORT_CONFLICT", "WORKER_VERSION_MISSING", "WORKER_STATUS_STALE"}:
            summary = re.sub(r"\bPID=\d+", "PID=<pid>", str(summary))
            summary = re.sub(r"\bPID \d+", "PID <pid>", str(summary))
            summary = re.sub(r"\bpid=\d+", "pid=<pid>", str(summary))
        payload.append(
            {
                "issue_code": code,
                "severity": item.get("severity"),
                "summary": summary,
                "blocks_completion": item.get("blocks_completion"),
            }
        )
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def build_snapshot(*, no_network: bool = False, mode: str = "snapshot") -> dict[str, Any]:
    git_info = collect_git()
    artifacts = collect_artifacts()
    versions = collect_versions(no_network=no_network)
    ports = collect_ports()
    processes = collect_processes()
    db = collect_db()
    guardian = collect_guardian_health()
    risks = safety_risks(no_network=no_network)

    issues: list[dict[str, Any]] = []
    if int(git_info.get("status_entries") or 0) > 0:
        issues.append(
            issue(
                "WORKTREE_DIRTY",
                "yellow",
                f"working tree dirty: {git_info.get('status_entries')} changed/untracked path(s)",
                "git status --short --branch",
                blocks_completion=False,
                required_before="handoff",
                source="codex_support.collect_git",
            )
        )
    issues.extend(issues_from_safety_risks(risks))
    issues.extend(issues_from_artifacts(artifacts))
    issues.extend(issues_from_versions(versions, git_info))
    issues.extend(issues_from_ports(ports, git_info))
    issues.extend(issues_from_processes(processes))
    if guardian.get("status") == "ok":
        issues.extend(normalize_truth_issue(item) for item in guardian.get("issues", []) if isinstance(item, dict))
    elif guardian.get("status") != "ok":
        issues.append(
            issue(
                "GUARDIAN_DOCTOR_FAILED",
                "red",
                f"truth doctor status={guardian.get('status')}",
                "scripts/truth doctor --json",
                blocks_completion=True,
                source="guardian-watch",
            )
        )
    if db.get("status") not in {"ok", None}:
        issues.append(
            issue(
                "DB_DOCTOR_FAILED",
                "red",
                f"db doctor status={db.get('status')}",
                ".venv/bin/python scripts/db_doctor.py --json",
                blocks_completion=True,
                source="guardian-watch",
            )
        )

    merged = dedupe_issues(issues)
    red_count = sum(1 for item in merged if item.get("severity") == "red" or item.get("blocks_completion"))
    yellow_count = sum(1 for item in merged if item.get("severity") == "yellow" and not item.get("blocks_completion"))
    overall = "red" if red_count else "yellow" if yellow_count else "green"

    actions = [
        {
            "issue_code": item.get("issue_code"),
            "required_before": item.get("required_before", "completion"),
            "command_hint": item.get("command_hint"),
            "blocks_completion": bool(item.get("blocks_completion")),
        }
        for item in merged
    ]

    return {
        "schema": SCHEMA,
        "mode": mode,
        "generated_at": utc_now(),
        "project": str(PROJECT_ROOT),
        "overall": overall,
        "red_count": red_count,
        "yellow_count": yellow_count,
        "fingerprint": issue_fingerprint(merged),
        "git": git_info,
        "versions": versions,
        "ports": ports,
        "processes": processes,
        "db": db,
        "artifacts": artifacts,
        "guardian_health": guardian,
        "issues": merged,
        "actions": actions,
        "policy": {
            "auto_kill": False,
            "auto_delete_runtime_artifacts": False,
            "auto_git_cleanup": False,
            "model_review_read_only": True,
        },
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(parsed, dict):
        if parsed.get("schema") == STATE_SCHEMA:
            return dict(parsed.get("runtime_state") or {})
        return dict(parsed.get("runtime_state") or parsed)
    return {}


def write_state(path: Path, snapshot: dict[str, Any], runtime_state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": STATE_SCHEMA,
        "updated_at": utc_now(),
        "latest_snapshot": snapshot,
        "runtime_state": runtime_state,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path | None, snapshot: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= JSONL_MAX_BYTES:
        for index in range(JSONL_BACKUPS - 1, 0, -1):
            src = path.with_name(f"{path.name}.{index}")
            dst = path.with_name(f"{path.name}.{index + 1}")
            if src.exists():
                src.replace(dst)
        path.replace(path.with_name(f"{path.name}.1"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False, sort_keys=True) + "\n")


def model_review_prompt(snapshot: dict[str, Any]) -> str:
    issues = snapshot.get("issues", [])
    compact = [
        {
            "issue_code": item.get("issue_code"),
            "severity": item.get("severity"),
            "summary": item.get("summary"),
            "blocks_completion": item.get("blocks_completion"),
        }
        for item in issues
    ]
    return (
        "Read-only auxiliary Guardian Runtime review. Codex remains the operator. "
        "Do not edit files or run Bash. Review the current guardian.watch.v1 snapshot, "
        "identify urgent risks, false positives, and missing safe checks. "
        f"Overall={snapshot.get('overall')} fingerprint={snapshot.get('fingerprint')} "
        f"issues={json.dumps(compact, ensure_ascii=False)}"
    )


def maybe_run_model_review(
    snapshot: dict[str, Any],
    state: dict[str, Any],
    config: WatchConfig,
    *,
    now: float | None = None,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    if not config.model_review:
        return {"status": "disabled"}
    if snapshot.get("overall") == "green":
        return {"status": "skipped", "reason": "green"}
    if config.model_review_backend == "claude":
        return {
            "status": "disabled",
            "reason": "claude_auxiliary_retired",
            "hint": "use Yuanqi task evidence and human/GitHub review instead of the retired Claude auxiliary path",
        }
    if not config.model_review_command:
        return {
            "status": "failed",
            "reason": f"{config.model_review_backend}_command_missing",
            "hint": "pass --model-review-command with a vetted read-only external review wrapper",
        }

    current_time = time.time() if now is None else now
    fingerprint = str(snapshot.get("fingerprint") or issue_fingerprint(snapshot.get("issues", [])))
    review_state = state.setdefault("model_review", {})
    last_at = float(review_state.get("last_run_at") or 0)
    last_fingerprint = str(review_state.get("last_fingerprint") or "")
    if fingerprint == last_fingerprint and current_time - last_at < config.model_review_interval:
        return {
            "status": "skipped",
            "reason": "rate_limited",
            "last_run_at": last_at,
            "last_fingerprint": last_fingerprint,
        }

    prompt = model_review_prompt(snapshot)
    cmd = [*shlex.split(config.model_review_command), prompt]

    config.model_review_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromtimestamp(current_time, timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = config.model_review_dir / f"guardian-model-review-{stamp}-{fingerprint}.txt"
    started = utc_now()
    try:
        result = runner(
            cmd,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=config.model_review_timeout + 30,
        )
    except Exception as exc:
        report.write_text(f"status=failed\nstarted_at={started}\nerror={exc}\n", encoding="utf-8")
        review_state.update(
            {
                "last_run_at": current_time,
                "last_fingerprint": fingerprint,
                "last_status": "failed",
                "last_report": str(report),
            }
        )
        return {"status": "failed", "report": str(report), "error": str(exc)}

    report.write_text(
        "\n".join(
            [
                f"status={'ok' if result.returncode == 0 else 'failed'}",
                f"started_at={started}",
                f"finished_at={utc_now()}",
                f"returncode={result.returncode}",
                "command=" + " ".join(shlex.quote(str(part)) for part in cmd),
                "",
                "stdout:",
                result.stdout,
                "",
                "stderr:",
                result.stderr,
            ]
        ),
        encoding="utf-8",
    )
    status = "ran" if result.returncode == 0 else "failed"
    review_state.update(
        {
            "last_run_at": current_time,
            "last_fingerprint": fingerprint,
            "last_status": status,
            "last_report": str(report),
            "last_returncode": result.returncode,
        }
    )
    return {"status": status, "report": str(report), "returncode": result.returncode}


def run_once(config: WatchConfig, runtime_state: dict[str, Any] | None = None, *, mode: str = "once") -> dict[str, Any]:
    state = {} if runtime_state is None else runtime_state
    snapshot = build_snapshot(no_network=config.no_network, mode=mode)
    transition_issues = issues_from_runtime_transitions(snapshot, state)
    if transition_issues:
        snapshot["issues"] = [*snapshot.get("issues", []), *transition_issues]
        rebuild_issue_summary(snapshot)
    state["backend_runtimes"] = backend_runtimes_from_snapshot(snapshot)
    if config.model_review and snapshot.get("overall") != "green":
        snapshot["model_review"] = {"status": "pending"}
        write_state(config.state_file, snapshot, state)
    snapshot["model_review"] = maybe_run_model_review(snapshot, state, config)
    write_state(config.state_file, snapshot, state)
    append_jsonl(config.jsonl_file, snapshot)
    return snapshot


def print_human(snapshot: dict[str, Any]) -> None:
    print(f"Guardian Watch {snapshot['generated_at']} overall={snapshot['overall']}")
    print(f"fingerprint={snapshot['fingerprint']} red={snapshot['red_count']} yellow={snapshot['yellow_count']}")
    issues = snapshot.get("issues", [])
    if not issues:
        print("issues: none")
        return
    print("issues:")
    for item in issues[:20]:
        flag = " blocks_completion" if item.get("blocks_completion") else ""
        print(f"- {item.get('issue_code')} {item.get('severity')}{flag}: {item.get('summary')}")
        hint = item.get("command_hint")
        if hint:
            print(f"  hint: {hint}")
    if len(issues) > 20:
        print(f"... and {len(issues) - 20} more")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the edu-cloud Guardian realtime watcher.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Emit one Guardian snapshot and exit.")
    mode.add_argument("--watch", action="store_true", help="Run continuously until interrupted.")
    parser.add_argument("--interval", type=int, default=15, help="Watch interval in seconds.")
    parser.add_argument("--no-network", action="store_true", help="Skip network truthline calls where supported.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human output.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when the current snapshot is red.")
    parser.add_argument("--state-file", type=Path, default=WatchConfig.state_file, help="Latest state JSON path.")
    parser.add_argument("--jsonl-file", type=Path, default=WatchConfig.jsonl_file, help="Append-only snapshot JSONL path.")
    parser.add_argument("--no-jsonl", action="store_true", help="Do not append snapshot history.")
    parser.add_argument("--model-review", choices=("off", "claude", "gpt"), default="off", help="Schedule read-only model review.")
    parser.add_argument("--no-model-review", action="store_true", help="Alias for --model-review off.")
    parser.add_argument("--model-review-interval", type=int, default=3600, help="Minimum seconds between identical reviews.")
    parser.add_argument("--model-review-dir", type=Path, default=WatchConfig.model_review_dir, help="Model review log directory.")
    parser.add_argument("--model-review-timeout", type=int, default=300, help="Model review timeout in seconds.")
    parser.add_argument("--model-review-command", help="Advanced: alternate read-only review command prefix.")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> WatchConfig:
    model_review = args.model_review in {"claude", "gpt"} and not args.no_model_review
    return WatchConfig(
        interval=max(5, args.interval),
        no_network=args.no_network,
        state_file=args.state_file,
        jsonl_file=None if args.no_jsonl else args.jsonl_file,
        model_review=model_review,
        model_review_backend=args.model_review,
        model_review_interval=max(60, args.model_review_interval),
        model_review_dir=args.model_review_dir,
        model_review_timeout=max(30, args.model_review_timeout),
        model_review_command=args.model_review_command,
        strict=args.strict,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = config_from_args(args)
    watch = args.watch
    runtime_state = load_state(config.state_file)

    while True:
        snapshot = run_once(config, runtime_state, mode="watch" if watch else "once")
        if args.json:
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        else:
            print_human(snapshot)
        if not watch:
            return 1 if config.strict and snapshot.get("overall") == "red" else 0
        time.sleep(config.interval)


if __name__ == "__main__":
    raise SystemExit(main())
