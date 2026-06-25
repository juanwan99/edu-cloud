#!/usr/bin/env python3
"""Collect live governance facts without mutating project state."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "governance.live_facts.v1"

SYSTEMD_SERVICES = (
    "edu-cloud",
    "llm-proxy",
    "edu-cloud-worker",
    "edu-cloud-guardian",
)

EXPECTED_PORTS: dict[int, dict[str, Any]] = {
    9000: {"label": "edu-cloud API", "service": "edu-cloud", "required": True},
    8080: {"label": "Vite dev server", "service": None, "required": False},
    8100: {"label": "llm-proxy", "service": "llm-proxy", "required": False},
}

GHOST_PROCESS_PATTERN = re.compile(
    r"vite.*--port|nuxt dev|uvicorn.*--reload|http\.server|arq.*worker",
    re.IGNORECASE,
)

Runner = Callable[..., "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


def run_command(
    args: list[str],
    *,
    timeout: int = 10,
    cwd: Path | None = None,
) -> CommandResult:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(completed.returncode, completed.stdout, completed.stderr)
    except FileNotFoundError as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return CommandResult(124, exc.stdout or "", exc.stderr or "command timed out")
    except OSError as exc:
        return CommandResult(99, "", str(exc))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_pid_process(line: str) -> tuple[int | None, str | None]:
    match = re.search(r'\("([^"]+)",pid=(\d+)', line)
    if not match:
        return None, None
    return int(match.group(2)), match.group(1)


def _split_address_port(address: str) -> tuple[str, int | None]:
    if address.startswith("[") and "]:" in address:
        bind, port_text = address.rsplit(":", 1)
        return bind, _parse_int(port_text)

    if ":" not in address:
        return address, None

    bind, port_text = address.rsplit(":", 1)
    if bind == "":
        bind = "*"
    return bind, _parse_int(port_text)


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _is_public_bind(bind: str) -> bool:
    normalized = bind.strip().lower()
    return normalized in {"0.0.0.0", "*", "[::]", "::", ":::"}


def parse_ss_listeners(output: str) -> list[dict[str, Any]]:
    listeners: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        bind, port = _split_address_port(parts[3])
        pid, process = _parse_pid_process(line)
        listeners.append(
            {
                "bind": bind,
                "port": port,
                "pid": pid,
                "process": process,
                "public_bind": _is_public_bind(bind),
                "raw": line,
            }
        )
    return listeners


def _parse_key_value_lines(output: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _ps_process_details(pid: int, runner: Runner) -> tuple[int | None, str | None]:
    result = runner(["ps", "-p", str(pid), "-o", "ppid=,command="], timeout=5)
    if result.returncode != 0:
        return None, None
    text = result.stdout.strip()
    if not text:
        return None, None
    parts = text.split(maxsplit=1)
    ppid = _parse_int(parts[0])
    command = parts[1] if len(parts) > 1 else ""
    return ppid, command


def collect_systemd(runner: Runner = run_command) -> dict[str, Any]:
    services: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    command_available = False

    for service in SYSTEMD_SERVICES:
        active_result = runner(["systemctl", "is-active", service], timeout=5)
        show_result = runner(
            [
                "systemctl",
                "show",
                service,
                "-p",
                "MainPID",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "LoadState",
                "--no-page",
            ],
            timeout=5,
        )

        if active_result.returncode not in {0, 3, 4}:
            failures.append(
                {
                    "service": service,
                    "command": "is-active",
                    "returncode": active_result.returncode,
                    "stderr": active_result.stderr.strip(),
                }
            )
        if show_result.returncode != 0:
            failures.append(
                {
                    "service": service,
                    "command": "show",
                    "returncode": show_result.returncode,
                    "stderr": show_result.stderr.strip(),
                }
            )
        if active_result.returncode != 127 or show_result.returncode != 127:
            command_available = True

        show = _parse_key_value_lines(show_result.stdout)
        main_pid = _parse_int(show.get("MainPID"))
        if main_pid == 0:
            main_pid = None
        active_text = active_result.stdout.strip() or None

        services[service] = {
            "active": active_result.returncode == 0 and active_text == "active",
            "is_active": active_text,
            "main_pid": main_pid,
            "active_state": show.get("ActiveState") or active_text,
            "sub_state": show.get("SubState") or None,
            "load_state": show.get("LoadState") or None,
        }

    main_pids = {
        str(info["main_pid"]): service
        for service, info in services.items()
        if info.get("main_pid")
    }

    return {
        "status": "ok" if command_available else "failed",
        "services": services,
        "main_pids": main_pids,
        "failures": failures,
    }


def collect_ports(
    *,
    runner: Runner = run_command,
    systemd: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = runner(["ss", "-H", "-tlnp"], timeout=10)
    expected = _empty_expected_ports()
    if result.returncode != 0:
        return {
            "status": "failed",
            "listeners": [],
            "expected": expected,
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
        }

    main_pids = (systemd or {}).get("main_pids", {})
    listeners = parse_ss_listeners(result.stdout)
    for listener in listeners:
        pid = listener.get("pid")
        service = main_pids.get(str(pid)) if pid is not None else None
        ppid = None
        command = None
        if pid is not None:
            ppid, command = _ps_process_details(pid, runner)
        listener["ppid"] = ppid
        listener["command"] = command
        listener["service"] = service

    for port, metadata in EXPECTED_PORTS.items():
        matches = [listener for listener in listeners if listener.get("port") == port]
        expected[str(port)] = {
            **metadata,
            "present": bool(matches),
            "listener_count": len(matches),
            "public_bind": any(listener.get("public_bind") for listener in matches),
        }

    return {
        "status": "ok",
        "listeners": listeners,
        "expected": expected,
    }


def _empty_expected_ports() -> dict[str, dict[str, Any]]:
    return {
        str(port): {
            **metadata,
            "present": False,
            "listener_count": 0,
            "public_bind": False,
        }
        for port, metadata in EXPECTED_PORTS.items()
    }


def _parse_ps_aux_line(line: str) -> tuple[int | None, str | None]:
    parts = line.split(maxsplit=10)
    if len(parts) < 11:
        return None, None
    return _parse_int(parts[1]), parts[10]


def collect_ghost_processes(
    *,
    runner: Runner = run_command,
    systemd: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = runner(["ps", "aux"], timeout=10)
    if result.returncode != 0:
        return {
            "status": "failed",
            "processes": [],
            "suspects": [],
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
        }

    main_pids = (systemd or {}).get("main_pids", {})
    processes: list[dict[str, Any]] = []
    suspects: list[dict[str, Any]] = []

    for line in result.stdout.splitlines():
        if not GHOST_PROCESS_PATTERN.search(line):
            continue
        pid, command_from_aux = _parse_ps_aux_line(line)
        if pid is None:
            continue
        ppid, command = _ps_process_details(pid, runner)
        process = {
            "pid": pid,
            "ppid": ppid,
            "command": command or command_from_aux,
            "service": main_pids.get(str(pid)),
            "raw": line.strip(),
        }
        processes.append(process)
        if ppid == 1 and str(pid) not in main_pids:
            suspects.append(process)

    return {
        "status": "ok",
        "processes": processes,
        "suspects": suspects,
    }


def collect_dist(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    dist_dir = project_root / "frontend" / "dist"
    index_path = dist_dir / "index.html"
    version_path = dist_dir / "version.json"

    index_exists = index_path.exists()
    index_readable = False
    if index_exists:
        try:
            index_path.read_text(encoding="utf-8")
            index_readable = True
        except OSError:
            index_readable = False

    version: dict[str, Any] | None = None
    version_error: str | None = None
    if version_path.exists():
        try:
            version_data = json.loads(version_path.read_text(encoding="utf-8"))
            if isinstance(version_data, dict):
                version = version_data
            else:
                version_error = "version_json_not_object"
        except (json.JSONDecodeError, OSError) as exc:
            version_error = str(exc)

    if not dist_dir.exists() or not index_exists:
        status = "missing"
    elif not index_readable:
        status = "unreadable"
    elif version_error:
        status = "version_invalid"
    else:
        status = "ok"

    return {
        "status": status,
        "path": str(dist_dir),
        "index_exists": index_exists,
        "index_readable": index_readable,
        "version_path": str(version_path),
        "version": version,
        "version_error": version_error,
    }


def collect_db(
    *,
    project_root: Path = PROJECT_ROOT,
    runner: Runner = run_command,
) -> dict[str, Any]:
    doctor = project_root / "scripts" / "db_doctor.py"
    if not doctor.exists():
        return {"status": "doctor_missing", "path": str(doctor)}

    python_bin = project_root / ".venv" / "bin" / "python"
    python_command = str(python_bin) if python_bin.exists() else sys.executable
    result = runner(
        [python_command, "scripts/db_doctor.py", "--json"],
        timeout=30,
        cwd=project_root,
    )
    if result.returncode != 0:
        return {
            "status": "failed",
            "path": str(doctor),
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
            "stdout": result.stdout.strip(),
        }

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {
            "status": "invalid_json",
            "path": str(doctor),
            "error": str(exc),
            "stdout": result.stdout.strip(),
        }

    if not isinstance(payload, dict):
        return {
            "status": "invalid_json",
            "path": str(doctor),
            "error": "db_doctor_json_not_object",
        }

    return {
        "status": "ok",
        "path": str(doctor),
        "hard": payload.get("hard"),
        "warn": payload.get("warn"),
        "alembic_version": payload.get("alembic_version"),
        "orm_tables": payload.get("orm_tables"),
        "db_tables": payload.get("db_tables"),
        "raw": payload,
    }


def collect_live_facts(
    *,
    project_root: Path = PROJECT_ROOT,
    runner: Runner = run_command,
    now: Callable[[], str] = utc_now,
) -> dict[str, Any]:
    project_root = Path(project_root)
    systemd = collect_systemd(runner)
    return {
        "schema": SCHEMA,
        "generated_at": now(),
        "project_root": str(project_root),
        "systemd": systemd,
        "ports": collect_ports(runner=runner, systemd=systemd),
        "ghost_processes": collect_ghost_processes(runner=runner, systemd=systemd),
        "dist": collect_dist(project_root),
        "db": collect_db(project_root=project_root, runner=runner),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="project root to inspect",
    )
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation")
    args = parser.parse_args(argv)

    facts = collect_live_facts(project_root=args.project_root)
    print(json.dumps(facts, ensure_ascii=False, indent=args.indent, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
