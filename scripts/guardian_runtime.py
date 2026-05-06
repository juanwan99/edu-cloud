"""Realtime Guardian runtime for edu-cloud.

This module deliberately stays advisory by default: it observes, writes state,
and can schedule a read-only model review. It does not kill processes, mutate
git state, copy databases, or delete runtime artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from codex_support import (
    PROJECT_ROOT,
    collect_artifacts,
    collect_db,
    collect_git,
    collect_guardian_health,
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
    model_review_backend: str = "claude"
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


def issues_from_versions(versions: dict[str, Any], git_info: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    head = str(git_info.get("head") or "")
    dist_hash = versions.get("dist_hash")
    nginx_hash = versions.get("nginx_hash")
    backend_hash = versions.get("backend_hash")
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
            issue(
                "BUILD_DRIFT",
                "red",
                f"frontend dist hash {dist_hash} does not match HEAD {head}",
                "scripts/codex-verify frontend",
                blocks_completion=True,
                source="codex_support.collect_versions",
            )
        )
    if dist_hash and nginx_hash and nginx_hash not in {"unknown", "unreadable"} and nginx_hash != dist_hash:
        issues.append(
            issue(
                "NGINX_DRIFT",
                "red",
                f"nginx version hash {nginx_hash} does not match local dist {dist_hash}",
                "scripts/codex-verify frontend",
                blocks_completion=True,
                source="codex_support.collect_versions",
            )
        )
    if head and head != "unknown" and backend_hash and backend_hash not in {"unknown", "unreadable"} and backend_hash != head:
        issues.append(
            issue(
                "BACKEND_DRIFT",
                "red",
                f"backend hash {backend_hash} does not match HEAD {head}",
                "sudo systemctl restart edu-cloud",
                blocks_completion=True,
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


def issue_fingerprint(issues: list[dict[str, Any]]) -> str:
    payload = []
    for item in issues:
        code = item.get("issue_code")
        summary = item.get("summary")
        if code == "WORKTREE_DIRTY":
            summary = "working tree dirty"
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
    if config.model_review_backend == "gpt" and not config.model_review_command:
        return {
            "status": "failed",
            "reason": "gpt_command_missing",
            "hint": "pass --model-review-command with a read-only GPT review wrapper",
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
    if config.model_review_command:
        cmd = [*shlex.split(config.model_review_command), prompt]
    else:
        cmd = [
            str(PROJECT_ROOT / "scripts" / "codex-consult-claude"),
            "--timeout",
            str(config.model_review_timeout),
            "risk",
            prompt,
        ]

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
