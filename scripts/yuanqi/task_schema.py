"""Task registry schema validation for Yuanqi task windows."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import yaml


VALID_MODES = (
    "read_only_audit",
    "planning_only",
    "docs_local",
    "frontend_only",
    "module_writer",
    "integration_writer",
    "exclusive",
)
VALID_OWNERS = ("claude", "codex", "human")
VALID_STATUSES = ("active", "closed")
KNOWN_FIELDS = frozenset(
    {
        "task_id",
        "mode",
        "owner",
        "branch",
        "worktree",
        "allowed_paths",
        "exclusive_claims",
        "changed_paths",
        "ports",
        "status",
        "created_at",
        "expires_at",
    }
)
FORBIDDEN_ROOT_OR_ESCAPE_PATHS = frozenset({"", ".", "*", "**", "/"})


def validate_task(data: dict, *, filename_stem: str | None = None) -> list[str]:
    """Return schema validation errors for a Yuanqi task registry entry."""
    if not isinstance(data, dict):
        return ["task must be a mapping"]

    errors: list[str] = []

    unknown_fields = sorted(set(data) - KNOWN_FIELDS)
    if unknown_fields:
        errors.append(f"unknown fields: {', '.join(unknown_fields)}")

    if not _non_empty_string(data.get("task_id")):
        errors.append("task_id must be a non-empty string")
    elif filename_stem is not None and data["task_id"] != filename_stem:
        errors.append("task_id must match filename stem")

    if data.get("mode") not in VALID_MODES:
        errors.append(f"mode must be one of: {', '.join(VALID_MODES)}")

    if data.get("owner") not in VALID_OWNERS:
        errors.append(f"owner must be one of: {', '.join(VALID_OWNERS)}")

    allowed_paths = data.get("allowed_paths")
    if not isinstance(allowed_paths, list):
        errors.append("allowed_paths must be a list")
    else:
        errors.extend(_validate_allowed_paths(allowed_paths))

    if not isinstance(data.get("exclusive_claims"), list):
        errors.append("exclusive_claims must be a list")

    if data.get("status") not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(VALID_STATUSES)}")

    if not _non_empty_string(data.get("created_at")):
        errors.append("created_at must be a non-empty string")

    if not _non_empty_string(data.get("expires_at")):
        errors.append("expires_at must be a non-empty string")

    return errors


def load_and_validate(path, *, require_filename: bool = False) -> tuple[dict, list[str]]:
    """Load a YAML task registry entry and return its data plus validation errors."""
    task_path = Path(path)
    data = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}, ["task must be a mapping"]
    filename_stem = task_path.stem if require_filename else None
    return data, validate_task(data, filename_stem=filename_stem)


def _validate_allowed_paths(paths: list[Any]) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not isinstance(path, str):
            errors.append("allowed_paths entries must be non-empty strings")
            continue

        normalized = _normalize(path)
        if _is_root_or_escaping_path(path, normalized):
            errors.append(f"allowed_paths contains forbidden root or escaping path: {path}")
            continue
        if _is_control_plane_path(normalized):
            errors.append(f"allowed_paths contains forbidden control-plane path: {path}")
    return errors


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _normalize(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if len(normalized) > 1 and normalized.endswith("/") and not normalized.endswith("/**"):
        normalized = normalized.rstrip("/")
    return normalized


def _is_root_or_escaping_path(raw_path: str, normalized: str) -> bool:
    if raw_path.strip().startswith("/") or _looks_like_windows_absolute(raw_path.strip()):
        return True
    if normalized in FORBIDDEN_ROOT_OR_ESCAPE_PATHS:
        return True
    return ".." in normalized.split("/")


def _looks_like_windows_absolute(path: str) -> bool:
    return len(path) >= 3 and path[1:3] == ":/" and path[0].isalpha()


def _is_control_plane_path(normalized: str) -> bool:
    return normalized == ".yuanqi" or normalized.startswith(".yuanqi/")


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for validating a Yuanqi task registry file."""
    parser = argparse.ArgumentParser(description="Validate a Yuanqi task YAML file.")
    parser.add_argument("task", help="Path to the Yuanqi task YAML file.")
    parser.add_argument(
        "--require-filename",
        action="store_true",
        help="Require task_id to match the task file stem. Always enforced by the CLI.",
    )
    args = parser.parse_args(argv)

    try:
        _, errors = load_and_validate(args.task, require_filename=True)
    except OSError as exc:
        print(f"task schema error: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"task schema error: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"task schema error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
