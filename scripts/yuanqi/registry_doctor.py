"""Stale-lock detection for Yuanqi task registry entries."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.yuanqi.task_schema import load_and_validate


DEFAULT_TASKS_DIR = ".yuanqi/tasks"


def find_stale(tasks: list[dict], now: str) -> list[dict]:
    """Return active tasks whose expiry timestamp is earlier than ``now``."""
    now_dt = _parse_timestamp(now)
    stale = []
    for task in tasks:
        if task.get("status") != "active":
            continue
        expires_at = task.get("expires_at")
        if not isinstance(expires_at, str) or not expires_at.strip():
            continue
        if _parse_timestamp(expires_at) < now_dt:
            stale.append(task)
    return stale


def scan(tasks_dir: str, now: str) -> dict:
    """Scan task YAML files and report stale, active, and total task counts."""
    tasks: list[dict[str, Any]] = []
    total = 0

    for path in _task_paths(Path(tasks_dir)):
        total += 1
        task, errors = load_and_validate(path)
        if errors:
            continue
        tasks.append(task)

    active = [task for task in tasks if task.get("status") == "active"]
    return {
        "stale": find_stale(active, now),
        "active": active,
        "total": total,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint: warn about stale active locks without mutating registry."""
    parser = argparse.ArgumentParser(
        description="Inspect Yuanqi task registry for stale active locks."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when stale active tasks are found.",
    )
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc).isoformat()
    result = scan(DEFAULT_TASKS_DIR, now)
    stale = result["stale"]

    if stale:
        print(f"STALE LOCK WARNING: {len(stale)} active task(s) expired.")
        for task in stale:
            print(
                "- "
                f"{task.get('task_id', '<unknown>')} "
                f"expired at {task.get('expires_at', '<missing expires_at>')}"
            )
        print("No registry entries were changed; confirm manually before closing locks.")
        if args.strict:
            return 1
    else:
        print(
            "registry doctor: no stale locks "
            f"({len(result['active'])} active / {result['total']} total)."
        )

    return 0


def _task_paths(tasks_dir: Path):
    if not tasks_dir.exists():
        return

    candidates = sorted(
        path
        for suffix in ("*.yml", "*.yaml")
        for path in tasks_dir.rglob(suffix)
        if path.is_file()
    )
    for path in candidates:
        relative = path.relative_to(tasks_dir)
        if "examples" in relative.parts:
            continue
        yield path


def _parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


if __name__ == "__main__":
    raise SystemExit(main())
