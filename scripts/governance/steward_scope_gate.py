"""Neutral Steward PR scope gate.

This gate resolves a `Steward-Scope: <id>` declaration from a pull request body,
loads `control/steward/scopes/<id>.yml`, and fails when changed files exceed the
declared scope.
"""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml


SCOPE_DECLARATION = re.compile(r"^\s*Steward-Scope:\s*([A-Za-z0-9._-]+)\s*$")
MISSING_SCOPE_MESSAGE = "PR must declare Steward-Scope: <id>"
VALID_STATUSES = {"active", "closed"}
KNOWN_FIELDS = {
    "schema",
    "scope_id",
    "owner",
    "allowed_paths",
    "forbidden_paths",
    "compatibility_paths",
    "status",
    "created_at",
    "expires_at",
}
FORBIDDEN_ROOT_OR_ESCAPE_PATHS = {"", ".", "*", "**", "/"}


def resolve_scope_id(event_path: str) -> str | None:
    event = json.loads(Path(event_path).read_text(encoding="utf-8-sig"))
    body = event.get("pull_request", {}).get("body") or ""
    if not isinstance(body, str):
        return None
    for line in body.splitlines():
        match = SCOPE_DECLARATION.match(line)
        if match:
            return match.group(1)
    return None


def load_and_validate(path: Path, *, require_filename: bool = True) -> tuple[dict, list[str]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}, ["scope must be a mapping"]

    filename_stem = path.stem if require_filename else None
    return data, validate_scope(data, filename_stem=filename_stem)


def validate_scope(data: dict, *, filename_stem: str | None = None) -> list[str]:
    errors: list[str] = []

    unknown_fields = sorted(set(data) - KNOWN_FIELDS)
    if unknown_fields:
        errors.append(f"unknown fields: {', '.join(unknown_fields)}")

    if data.get("schema") != "steward-pr-scope.v1":
        errors.append("schema must be steward-pr-scope.v1")

    if not _non_empty_string(data.get("scope_id")):
        errors.append("scope_id must be a non-empty string")
    elif filename_stem is not None and data["scope_id"] != filename_stem:
        errors.append("scope_id must match filename stem")

    if not _non_empty_string(data.get("owner")):
        errors.append("owner must be a non-empty string")

    allowed_paths = data.get("allowed_paths")
    if not isinstance(allowed_paths, list):
        errors.append("allowed_paths must be a list")
    else:
        errors.extend(_validate_path_list(allowed_paths, field="allowed_paths"))

    forbidden_paths = data.get("forbidden_paths", [])
    if not isinstance(forbidden_paths, list):
        errors.append("forbidden_paths must be a list")
    else:
        errors.extend(_validate_path_list(forbidden_paths, field="forbidden_paths"))

    compatibility_paths = data.get("compatibility_paths", [])
    if not isinstance(compatibility_paths, list):
        errors.append("compatibility_paths must be a list")
    else:
        for item in compatibility_paths:
            if not isinstance(item, dict):
                errors.append("compatibility_paths entries must be mappings")
                continue
            if not _non_empty_string(item.get("path")):
                errors.append("compatibility_paths entries must have path")
            if not _non_empty_string(item.get("reason")):
                errors.append("compatibility_paths entries must have reason")
            path_errors = _validate_path_list([item.get("path")], field="compatibility_paths")
            errors.extend(path_errors)

    if data.get("status") not in VALID_STATUSES:
        errors.append("status must be active or closed")

    if not _non_empty_string(data.get("created_at")):
        errors.append("created_at must be a non-empty string")

    if not _non_empty_string(data.get("expires_at")):
        errors.append("expires_at must be a non-empty string")

    return errors


def scope_check(changed_files: list[str], scope: dict) -> tuple[bool, list[str]]:
    allowed = _allowed_scope(scope)
    forbidden = _string_list(scope.get("forbidden_paths"))
    violations = [
        path
        for path in _normalize_all(changed_files)
        if path and (not _matches_any(path, allowed) or _matches_any(path, forbidden))
    ]
    return (False, violations) if violations else (True, [])


def _allowed_scope(scope: dict) -> list[str]:
    paths: list[str] = []
    paths.extend(_string_list(scope.get("allowed_paths")))
    for item in scope.get("compatibility_paths", []) or []:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            paths.append(item["path"])
    return _dedupe(_normalize(path) for path in paths if path)


def _validate_path_list(paths: list[Any], *, field: str) -> list[str]:
    errors: list[str] = []
    for path in paths:
        if not isinstance(path, str) or not path.strip():
            errors.append(f"{field} entries must be non-empty strings")
            continue
        normalized = _normalize(path)
        if _is_root_or_escaping_path(path, normalized):
            errors.append(f"{field} contains forbidden root or escaping path: {path}")
        if field == "allowed_paths" and _is_legacy_yuanqi_path(normalized):
            errors.append(f"allowed_paths must not contain legacy Yuanqi path: {path}")
    return errors


def _read_changed_files(path: str) -> list[str]:
    return [entry_path for _, entry_path in _read_changed_entries(path)]


def _read_changed_entries(path: str) -> list[tuple[str | None, str]]:
    entries: list[tuple[str | None, str]] = []
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        parts = line.lstrip("\ufeff").split("\t")
        if len(parts) >= 2 and _looks_like_name_status(parts[0]):
            entries.append((parts[0][0], _normalize(parts[-1])))
        else:
            entries.append((None, _normalize(line)))
    return entries


def _looks_like_name_status(token: str) -> bool:
    return bool(token) and token[0] in {"A", "C", "D", "M", "R", "T", "U", "X", "B"}


def _scope_enforced_paths(changed_entries: list[tuple[str | None, str]]) -> list[str]:
    return [
        path
        for status, path in changed_entries
        if not (status == "D" and _is_legacy_yuanqi_path(path))
    ]


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(_matches(path, pattern) for pattern in patterns)


def _matches(path: str, pattern: str) -> bool:
    if "*" in pattern or "?" in pattern or "[" in pattern:
        return fnmatchcase(path, pattern)
    return path == pattern or path.startswith(pattern.rstrip("/") + "/")


def _normalize_all(paths: list[str]) -> list[str]:
    return [_normalize(path) for path in paths if isinstance(path, str)]


def _normalize(path: str) -> str:
    normalized = path.strip().replace("\\", "/").lstrip("\ufeff")
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
    normalized = path.replace("\\", "/")
    return len(normalized) >= 3 and normalized[1:3] == ":/" and normalized[0].isalpha()


def _is_legacy_yuanqi_path(normalized: str) -> bool:
    return normalized == ".yuanqi" or normalized.startswith(".yuanqi/")


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _dedupe(paths) -> list[str]:
    return sorted(dict.fromkeys(paths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate PR changed files against a Steward scope.")
    parser.add_argument("--event", required=True, help="Path to GitHub pull_request event JSON")
    parser.add_argument("--changed", required=True, help="Path to changed-files.txt")
    parser.add_argument(
        "--scopes-dir",
        default="control/steward/scopes",
        help="Directory containing steward-pr-scope YAML files",
    )
    args = parser.parse_args(argv)

    try:
        scope_id = resolve_scope_id(args.event)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{MISSING_SCOPE_MESSAGE}: {exc}", file=sys.stderr)
        return 1

    if not scope_id:
        print(MISSING_SCOPE_MESSAGE, file=sys.stderr)
        return 1

    scope_path = Path(args.scopes_dir) / f"{scope_id}.yml"
    try:
        scope, errors = load_and_validate(scope_path, require_filename=True)
    except OSError as exc:
        print(f"scope schema error: {exc}", file=sys.stderr)
        return 1
    except yaml.YAMLError as exc:
        print(f"scope schema error: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"scope schema error: {error}", file=sys.stderr)
        return 1

    if scope.get("status") != "active":
        print("scope status must be active for PR validation", file=sys.stderr)
        return 1

    changed_entries = _read_changed_entries(args.changed)
    changed_files = [path for _, path in changed_entries]
    scope_relpath = _normalize(str(Path(args.scopes_dir) / f"{scope_id}.yml"))
    if scope_relpath not in _normalize_all(changed_files):
        print("declared scope file must be changed in the PR", file=sys.stderr)
        return 1
    if not any(status == "A" and path == scope_relpath for status, path in changed_entries):
        print("declared scope file must be newly added in the PR", file=sys.stderr)
        return 1

    ok, violations = scope_check(_scope_enforced_paths(changed_entries), scope)
    if ok:
        return 0

    print("scope violations:", file=sys.stderr)
    for path in violations:
        print(path, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
