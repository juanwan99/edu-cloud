"""Scope enforcement gate for Yuanqi task-window changed files."""

from __future__ import annotations

import argparse
import sys
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from scripts.yuanqi.lock_map import expand_exclusive
from scripts.yuanqi.task_schema import load_and_validate


def scope_check(changed_files: list[str], task: dict) -> tuple[bool, list[str]]:
    """Return whether every changed file stays inside the task write scope."""
    allowed = _allowed_scope(task)
    violations = [
        path
        for path in _normalize_all(changed_files)
        if path and not _matches_any(path, allowed)
    ]
    return (False, violations) if violations else (True, [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fail when changed files exceed a Yuanqi task scope.",
    )
    parser.add_argument("--changed", required=True, help="Path to changed-files.txt")
    parser.add_argument("--task", required=True, help="Path to Yuanqi task YAML")
    args = parser.parse_args(argv)

    task, errors = load_and_validate(args.task)
    if errors:
        for error in errors:
            print(f"task schema error: {error}", file=sys.stderr)
        return 2

    changed_files = _read_changed_files(args.changed)
    ok, violations = scope_check(changed_files, task)
    if ok:
        return 0

    print("scope violations:", file=sys.stderr)
    for path in violations:
        print(path, file=sys.stderr)
    return 1


def _allowed_scope(task: dict) -> list[str]:
    paths: list[str] = []
    paths.extend(_string_list(task.get("allowed_paths")))
    for claim in _string_list(task.get("exclusive_claims")):
        paths.extend(expand_exclusive(claim))
    return _dedupe(_normalize(path) for path in paths if path)


def _read_changed_files(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _normalize_all(paths: list[str]) -> list[str]:
    return [_normalize(path) for path in paths if isinstance(path, str)]


def _normalize(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if len(normalized) > 1 and normalized.endswith("/") and not normalized.endswith("/**"):
        normalized = normalized.rstrip("/")
    return normalized


def _dedupe(paths) -> list[str]:
    return sorted(dict.fromkeys(paths))


if __name__ == "__main__":
    raise SystemExit(main())
