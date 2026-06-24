"""Task registry schema validation for Yuanqi task windows."""

from __future__ import annotations

from pathlib import Path
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


def validate_task(data: dict) -> list[str]:
    """Return schema validation errors for a Yuanqi task registry entry."""
    if not isinstance(data, dict):
        return ["task must be a mapping"]

    errors: list[str] = []

    if not _non_empty_string(data.get("task_id")):
        errors.append("task_id must be a non-empty string")

    if data.get("mode") not in VALID_MODES:
        errors.append(f"mode must be one of: {', '.join(VALID_MODES)}")

    if data.get("owner") not in VALID_OWNERS:
        errors.append(f"owner must be one of: {', '.join(VALID_OWNERS)}")

    if not isinstance(data.get("allowed_paths"), list):
        errors.append("allowed_paths must be a list")

    if not isinstance(data.get("exclusive_claims"), list):
        errors.append("exclusive_claims must be a list")

    if data.get("status") not in VALID_STATUSES:
        errors.append(f"status must be one of: {', '.join(VALID_STATUSES)}")

    if not _non_empty_string(data.get("created_at")):
        errors.append("created_at must be a non-empty string")

    if not _non_empty_string(data.get("expires_at")):
        errors.append("expires_at must be a non-empty string")

    return errors


def load_and_validate(path) -> tuple[dict, list[str]]:
    """Load a YAML task registry entry and return its data plus validation errors."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}, ["task must be a mapping"]
    return data, validate_task(data)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""
