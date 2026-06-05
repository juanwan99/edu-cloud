#!/usr/bin/env python3
"""Check backend/frontend RBAC mirror consistency."""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ONLY_ROLES = {
    "admin",
    "teacher",
    "head_teacher",
    "exam_coordinator",
    "observer",
}


@dataclass(frozen=True)
class FrontendMirror:
    role_permissions: dict[str, set[str]]
    canonical_roles: set[str]
    legacy_aliases: dict[str, str]


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"//.*", "", text)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _extract_balanced(text: str, marker: str, open_char: str, close_char: str) -> str:
    start = text.index(marker)
    open_index = text.index(open_char, start)
    depth = 0
    quote: str | None = None
    escape = False
    for index in range(open_index, len(text)):
        ch = text[index]
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[open_index + 1:index]
    raise ValueError(f"Could not find balanced block for {marker}")


def _split_top_level_entries(body: str) -> list[str]:
    entries: list[str] = []
    depth = 0
    quote: str | None = None
    escape = False
    start = 0
    for index, ch in enumerate(body):
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            entry = body[start:index].strip()
            if entry:
                entries.append(entry)
            start = index + 1
    tail = body[start:].strip()
    if tail:
        entries.append(tail)
    return entries


def _split_key_value(entry: str) -> tuple[str, str]:
    depth = 0
    quote: str | None = None
    escape = False
    for index, ch in enumerate(entry):
        if quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ":" and depth == 0:
            return entry[:index].strip(), entry[index + 1:].strip()
    raise ValueError(f"Invalid object entry: {entry}")


def _js_strings(text: str) -> list[str]:
    return [m.group(1) or m.group(2) for m in re.finditer(r"'([^']*)'|\"([^\"]*)\"", text)]


def _parse_permission_expr(expr: str, teacher_base: set[str]) -> set[str]:
    expr = expr.strip()
    expr_compact = re.sub(r"\s+", "", expr)
    if expr_compact.startswith("_TEACHER_BASE.filter"):
        permissions = set(teacher_base)
        exclusions = set(re.findall(r"p\s*!==\s*'([^']+)'", expr))
        permissions -= exclusions
        if ".concat" in expr:
            concat = expr.split(".concat", 1)[1]
            permissions |= set(_js_strings(concat))
        return permissions
    if expr.startswith("["):
        permissions = set(_js_strings(expr))
        if "..._TEACHER_BASE" in expr:
            permissions |= set(teacher_base)
        return permissions
    raise ValueError(f"Unsupported permission expression: {expr}")


def parse_frontend_mirror(repo: Path) -> FrontendMirror:
    permissions_text = _strip_js_comments(
        (repo / "frontend/src/config/permissions.js").read_text(encoding="utf-8")
    )
    roles_text = _strip_js_comments(
        (repo / "frontend/src/config/roles.js").read_text(encoding="utf-8")
    )

    teacher_base = set(
        _js_strings(_extract_balanced(permissions_text, "const _TEACHER_BASE", "[", "]"))
    )
    role_permissions: dict[str, set[str]] = {}
    roles_body = _extract_balanced(
        permissions_text, "export const ROLE_PERMISSIONS", "{", "}"
    )
    for entry in _split_top_level_entries(roles_body):
        key, value = _split_key_value(entry)
        role_permissions[key] = _parse_permission_expr(value, teacher_base)

    canonical_roles = set(
        _js_strings(_extract_balanced(roles_text, "export const CANONICAL_ROLES", "[", "]"))
    )
    alias_body = _extract_balanced(roles_text, "export const LEGACY_ALIAS_MAP", "{", "}")
    legacy_aliases: dict[str, str] = {}
    for entry in _split_top_level_entries(alias_body):
        key, value = _split_key_value(entry)
        strings = _js_strings(value)
        if not strings:
            raise ValueError(f"Invalid alias value for {key}: {value}")
        legacy_aliases[key] = strings[0]

    return FrontendMirror(
        role_permissions=role_permissions,
        canonical_roles=canonical_roles,
        legacy_aliases=legacy_aliases,
    )


def load_backend_permissions(repo: Path) -> tuple[set[str], dict[str, set[str]]]:
    path = repo / "src/edu_cloud/core/permissions.py"
    spec = importlib.util.spec_from_file_location("_edu_cloud_permissions", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    permission_values = {permission.value for permission in module.Permission}
    role_permissions = {
        role: {permission.value for permission in permissions}
        for role, permissions in module.ROLE_PERMISSIONS.items()
    }
    return permission_values, role_permissions


def check_repo(repo: Path) -> list[str]:
    backend_values, backend_roles = load_backend_permissions(repo)
    frontend = parse_frontend_mirror(repo)
    messages: list[str] = []

    frontend_values = set().union(*frontend.role_permissions.values())
    missing_values = sorted(backend_values - frontend_values)
    extra_values = sorted(frontend_values - backend_values)
    if missing_values:
        messages.append(f"Frontend permission values missing: {missing_values}")
    if extra_values:
        messages.append(f"Frontend permission values unknown to backend: {extra_values}")

    expected_frontend_roles = set(backend_roles) - BACKEND_ONLY_ROLES
    missing_roles = sorted(expected_frontend_roles - frontend.canonical_roles)
    extra_roles = sorted(frontend.canonical_roles - expected_frontend_roles)
    if missing_roles:
        messages.append(f"Frontend canonical roles missing: {missing_roles}")
    if extra_roles:
        messages.append(f"Frontend canonical roles unknown to backend: {extra_roles}")

    permission_roles = set(frontend.role_permissions)
    missing_permission_roles = sorted(frontend.canonical_roles - permission_roles)
    extra_permission_roles = sorted(permission_roles - frontend.canonical_roles)
    if missing_permission_roles:
        messages.append(f"ROLE_PERMISSIONS missing roles: {missing_permission_roles}")
    if extra_permission_roles:
        messages.append(f"ROLE_PERMISSIONS has non-canonical roles: {extra_permission_roles}")

    for role in sorted(frontend.canonical_roles & set(backend_roles)):
        backend = backend_roles[role]
        frontend_perms = frontend.role_permissions.get(role, set())
        missing = sorted(backend - frontend_perms)
        extra = sorted(frontend_perms - backend)
        if missing or extra:
            messages.append(
                f"Role permission drift for {role}: missing={missing} extra={extra}"
            )

    for alias, target in sorted(frontend.legacy_aliases.items()):
        if alias not in backend_roles:
            messages.append(f"Frontend alias {alias} missing in backend roles")
            continue
        if target not in backend_roles:
            messages.append(f"Frontend alias target {target} missing in backend roles")
            continue
        if backend_roles[alias] != backend_roles[target]:
            messages.append(
                f"Frontend alias {alias}->{target} does not mirror backend permissions"
            )

    return messages


def resolve_repo(repo_arg: str | None = None) -> Path:
    return Path(repo_arg or ".").resolve()


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="Target repository path")
    args = parser.parse_args(argv)
    repo = resolve_repo(args.repo)
    messages = check_repo(repo)
    if messages:
        print("Permission mirror drift detected:")
        for message in messages:
            print(f"  - {message}")
        return 1
    print("Permission mirror clean")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
