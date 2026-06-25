"""Governance tool registry coverage tests."""

from __future__ import annotations

import fnmatch
from collections import Counter
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = PROJECT_ROOT / "docs" / "governance" / "governance-tools.yml"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

CANDIDATE_PATTERNS = (
    "codex-*",
    "meta-*",
    "guardian-*",
    "truth*",
    "*doctor*",
    "*verify*",
    "*check*",
    "db_migrate",
    "db_doctor.py",
)

REQUIRED_FIELDS = (
    "path",
    "owner",
    "authority_class",
    "is_completion_evidence",
    "writes_state",
    "why_insufficient",
    "test_command",
)


def _is_generated_artifact(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def _candidate_scripts() -> list[str]:
    return sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in SCRIPTS_DIR.rglob("*")
        if path.is_file()
        and not _is_generated_artifact(path)
        and any(fnmatch.fnmatch(path.name, pattern) for pattern in CANDIDATE_PATTERNS)
    )


def _load_registry() -> list[dict[str, object]]:
    assert REGISTRY_PATH.exists(), (
        f"{REGISTRY_PATH.relative_to(PROJECT_ROOT)} is missing"
    )
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    tools = data.get("tools")
    assert isinstance(tools, list), (
        "governance-tools.yml must contain a top-level tools list"
    )
    return tools


def test_governance_registry_covers_candidate_scripts() -> None:
    tools = _load_registry()
    paths = [entry.get("path") for entry in tools if isinstance(entry, dict)]
    counts = Counter(paths)
    duplicates = sorted(str(path) for path, count in counts.items() if count > 1)
    registered = {str(path) for path in paths if path}

    candidates = set(_candidate_scripts())
    missing = sorted(candidates - registered)
    stale = sorted(path for path in registered if not (PROJECT_ROOT / path).is_file())

    problems = []
    if missing:
        problems.append(
            "Missing governance tool registry entries:\n"
            + "\n".join(f"- {path}" for path in missing)
        )
    if duplicates:
        problems.append(
            "Duplicate governance tool registry entries:\n"
            + "\n".join(f"- {path}" for path in duplicates)
        )
    if stale:
        problems.append(
            "Stale governance tool registry entries:\n"
            + "\n".join(f"- {path}" for path in stale)
        )

    assert not problems, "\n\n".join(problems)


def test_governance_registry_entries_are_complete() -> None:
    tools = _load_registry()
    problems = []
    for index, entry in enumerate(tools):
        assert isinstance(entry, dict), f"tools[{index}] must be a mapping"
        path = str(entry.get("path") or f"tools[{index}]")
        for field in REQUIRED_FIELDS:
            if field not in entry:
                problems.append(f"{path}: missing {field}")
        for field in (
            "path",
            "owner",
            "authority_class",
            "why_insufficient",
            "test_command",
        ):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{path}: {field} must be a non-empty string")
        for field in ("is_completion_evidence", "writes_state"):
            if not isinstance(entry.get(field), bool):
                problems.append(f"{path}: {field} must be a boolean")

    assert not problems, (
        "Incomplete governance tool registry entries:\n"
        + "\n".join(f"- {problem}" for problem in problems)
    )
