"""Overlap deny gate for Yuanqi parallel task windows."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any

from scripts.yuanqi.lock_map import expand_exclusive


READ_ONLY_MODES = {"read_only_audit", "planning_only"}


def check(candidate: dict, active_tasks: list[dict]) -> tuple[str, list]:
    """Return whether a candidate task can run beside active Yuanqi tasks."""
    candidate_locks = _lockset(candidate)
    if not candidate_locks:
        return "allow", []

    conflicts = []
    for task in active_tasks:
        if task.get("status") != "active":
            continue
        if task.get("task_id") == candidate.get("task_id"):
            continue

        other_locks = _lockset(task)
        if not other_locks:
            continue

        hit = _glob_intersections(candidate_locks, other_locks)
        if hit and not _has_human_waiver(candidate, task):
            conflicts.append({"task_id": task.get("task_id"), "paths": hit})

    return ("deny", conflicts) if conflicts else ("allow", [])


def _lockset(task: dict) -> list[str]:
    paths: list[str] = []
    paths.extend(_string_list(task.get("allowed_paths")))
    paths.extend(_string_list(task.get("changed_paths")))

    for claim in _string_list(task.get("exclusive_claims")):
        paths.extend(expand_exclusive(claim))

    if task.get("mode") in READ_ONLY_MODES and not paths:
        return []
    return _dedupe(_normalize(path) for path in paths if path)


def _glob_intersections(left: list[str], right: list[str]) -> list[str]:
    hits: list[str] = []
    for left_path in left:
        for right_path in right:
            hit = _intersecting_path(left_path, right_path)
            if hit:
                hits.append(hit)
    return _dedupe(hits)


def _intersecting_path(left: str, right: str) -> str | None:
    if left == right:
        return left

    left_is_glob = _is_glob(left)
    right_is_glob = _is_glob(right)

    if left_is_glob and not right_is_glob and fnmatchcase(right, left):
        return right
    if right_is_glob and not left_is_glob and fnmatchcase(left, right):
        return left
    if not left_is_glob and not right_is_glob:
        return None

    left_prefix = _literal_prefix(left)
    right_prefix = _literal_prefix(right)
    if left_prefix and right_prefix:
        if left_prefix.startswith(right_prefix):
            return _more_specific(left, right, left_prefix, right_prefix)
        if right_prefix.startswith(left_prefix):
            return _more_specific(right, left, right_prefix, left_prefix)

    return None


def _literal_prefix(pattern: str) -> str:
    glob_positions = [pos for char in "*?[" if (pos := pattern.find(char)) != -1]
    if not glob_positions:
        return pattern

    prefix = pattern[: min(glob_positions)]
    if "/" not in prefix:
        return ""
    return prefix.rsplit("/", 1)[0] + "/"


def _more_specific(
    first_pattern: str,
    second_pattern: str,
    first_prefix: str,
    second_prefix: str,
) -> str:
    if len(first_prefix) > len(second_prefix):
        return first_pattern
    if len(second_prefix) > len(first_prefix):
        return second_pattern
    return min(first_pattern, second_pattern)


def _has_human_waiver(candidate: dict, other: dict) -> bool:
    other_id = other.get("task_id")
    waiver = candidate.get("human_waiver")
    if waiver is True or waiver == "human":
        return True
    if isinstance(waiver, dict):
        targets = _string_list(waiver.get("task_ids") or waiver.get("tasks"))
        return waiver.get("approved_by") == "human" and (
            not targets or "*" in targets or other_id in targets
        )

    waivers = candidate.get("human_waivers")
    if isinstance(waivers, list):
        return "*" in waivers or other_id in waivers

    return False


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _normalize(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if len(normalized) > 1 and normalized.endswith("/") and not normalized.endswith("/**"):
        normalized = normalized.rstrip("/")
    return normalized


def _is_glob(path: str) -> bool:
    return any(char in path for char in "*?[")


def _dedupe(paths) -> list[str]:
    return sorted(dict.fromkeys(paths))
