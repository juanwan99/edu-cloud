"""Lock source expansion helpers for Yuanqi parallel overlap gates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULES_FILE = _REPO_ROOT / "docs/governance/modules.yaml"
_PARALLEL_FILE = _REPO_ROOT / "docs/context/PARALLEL_DEVELOPMENT.md"
_EXCLUSIVE_KEYWORDS = {
    "db_migration": "db migrations",
    "permissions": "permission and module-gating core",
    "runtime": "runtime and deployment",
    "central_docs": "central context and entrypoint files",
    "foundation": "shared foundation modules",
}


def module_paths(module: str) -> list[str]:
    """Return source and existing test path locks for a registered module."""
    _module_record(module)

    paths = [f"src/edu_cloud/modules/{module}/**"]
    tests_root = _REPO_ROOT / "tests"
    if tests_root.exists():
        for path in tests_root.rglob("*"):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            rel_path = path.relative_to(_REPO_ROOT)
            if not _matches_module_path(rel_path, module):
                continue
            rel = rel_path.as_posix()
            paths.append(f"{rel}/**" if path.is_dir() else rel)

    return _dedupe(paths)


def module_tables(module: str) -> list[str]:
    """Return table locks owned by a registered module."""
    tables = _module_record(module).get("owns_tables") or []
    if not isinstance(tables, list):
        raise ValueError(f"owns_tables must be a list for module: {module}")
    return [str(table) for table in tables]


def expand_exclusive(lock_name: str) -> list[str]:
    """Expand an exclusive lock name from the documented source section."""
    bullet = _exclusive_bullet(lock_name)
    lower_bullet = bullet.lower()
    paths: list[str] = []

    if lock_name == "db_migration":
        if "db migrations" in lower_bullet:
            _add_existing(paths, "alembic/**")
        paths.extend(_resolve_backticked_paths(bullet))
    elif lock_name == "permissions":
        paths.extend(_resolve_backticked_paths(bullet))
        if "permissions.py" in bullet:
            _add_existing(paths, "src/edu_cloud/core/permissions.py")
            _add_existing(paths, "src/edu_cloud/api/permissions.py")
        if "frontend permission" in lower_bullet:
            _add_existing(paths, "frontend/src/config/permissions.js")
        if "authguard" in lower_bullet or "route guards" in lower_bullet:
            _add_existing(paths, "frontend/src/router/index.js")
            _add_existing(paths, "frontend/src/config/routeAccess.js")
            _add_existing(paths, "frontend/src/stores/auth.js")
        if "module middleware" in lower_bullet:
            _add_existing(paths, "src/edu_cloud/api/module_middleware.py")
    elif lock_name == "runtime":
        if "systemd" in lower_bullet:
            _add_existing(paths, "deploy/systemd/**")
        if "nginx" in lower_bullet:
            _add_existing(paths, "deploy/nginx/**")
        if "dist" in lower_bullet:
            _add_existing(paths, "frontend/dist/**")
    elif lock_name == "central_docs":
        paths.extend(_resolve_backticked_paths(bullet))
    elif lock_name == "foundation":
        for value in _backticked_values(bullet):
            if _is_registered_module(value):
                paths.extend(module_paths(value))
        if "school-module settings" in lower_bullet:
            _add_existing(paths, "src/edu_cloud/modules/school/settings_router.py")
            _add_existing(paths, "src/edu_cloud/models/school_settings.py")
            _add_existing(paths, "src/edu_cloud/services/school_settings_service.py")
    else:
        raise ValueError(f"unknown exclusive lock: {lock_name}")

    return _dedupe(paths)


def _load_modules() -> list[dict[str, Any]]:
    data = yaml.safe_load(_MODULES_FILE.read_text(encoding="utf-8")) or {}
    modules = data.get("modules") or []
    if not isinstance(modules, list):
        raise ValueError("modules.yaml must contain a modules list")
    return modules


def _module_record(module: str) -> dict[str, Any]:
    for record in _load_modules():
        if isinstance(record, dict) and record.get("name") == module:
            return record
    raise KeyError(f"unknown module: {module}")


def _is_registered_module(module: str) -> bool:
    try:
        _module_record(module)
    except KeyError:
        return False
    return True


def _matches_module_path(path: Path, module: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(module.lower())}(?![a-z0-9])"
    return re.search(pattern, path.as_posix().lower()) is not None


def _exclusive_bullet(lock_name: str) -> str:
    try:
        keyword = _EXCLUSIVE_KEYWORDS[lock_name]
    except KeyError as exc:
        raise ValueError(f"unknown exclusive lock: {lock_name}") from exc

    for bullet in _exclusive_bullets():
        if keyword in bullet.lower():
            return bullet
    raise ValueError(f"exclusive lock source not found: {lock_name}")


def _exclusive_bullets() -> list[str]:
    lines = _PARALLEL_FILE.read_text(encoding="utf-8").splitlines()
    in_section = False
    current: list[str] = []
    bullets: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if in_section and line.strip() != "## Exclusive Scopes":
                break
            in_section = line.strip() == "## Exclusive Scopes"
            continue
        if not in_section:
            continue
        if line.startswith("- "):
            if current:
                bullets.append(" ".join(current))
            current = [line[2:].strip()]
        elif current and line.strip():
            current.append(line.strip())

    if current:
        bullets.append(" ".join(current))
    if not bullets:
        raise ValueError("Exclusive Scopes section has no bullets")
    return bullets


def _backticked_values(text: str) -> list[str]:
    return re.findall(r"`([^`]+)`", text)


def _resolve_backticked_paths(text: str) -> list[str]:
    paths: list[str] = []
    for value in _backticked_values(text):
        if "/" in value or value.endswith("/**"):
            _add_existing(paths, value)
        else:
            paths.extend(_find_existing_files(value))
    return paths


def _find_existing_files(name: str) -> list[str]:
    ignored = {"__pycache__", ".git", "node_modules"}
    paths = []
    for path in _REPO_ROOT.rglob(name):
        if ignored.intersection(path.parts) or not path.is_file():
            continue
        paths.append(path.relative_to(_REPO_ROOT).as_posix())
    return sorted(paths)


def _add_existing(paths: list[str], pattern: str) -> None:
    concrete = pattern[:-3] if pattern.endswith("/**") else pattern
    if (_REPO_ROOT / concrete).exists():
        paths.append(pattern)


def _dedupe(paths: list[str]) -> list[str]:
    return sorted(dict.fromkeys(paths))
