#!/usr/bin/env python3
"""Generate Keel no-shell worker profiles for every backend module."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


MODULES_REL = Path("src/edu_cloud/modules")
OUTPUT_REL = Path("control/steward/worker-profiles")
MODULE_OUTPUT_REL = OUTPUT_REL / "modules"
MANIFEST_REL = OUTPUT_REL / "manifest.json"
MANIFEST_SCHEMA = "keel-worker-profile-manifest.v1"
GENERATED_BY = "scripts/governance/gen_worker_profile.py"
MODULE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHELL_DENIES = ("Bash", "PowerShell")
SELF_MODIFY_DENY_PATHS = (".claude/**",)
CENTRAL_DENY_PATHS = (
    "src/edu_cloud/ai/**",
    "src/edu_cloud/api/app.py",
    "src/edu_cloud/api/router_registry.py",
    "src/edu_cloud/core/**",
    "src/edu_cloud/models/school_settings.py",
    "alembic/**",
    ".github/**",
    "control/**",
    "deploy/**",
    "AGENTS.md",
    "CLAUDE.md",
)


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    source: str


def resolve_repo(repo_arg: str | None = None) -> Path:
    if repo_arg:
        return Path(repo_arg).resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return Path(result.stdout.strip()).resolve()
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return Path.cwd().resolve()


def discover_modules(repo: Path) -> list[ModuleInfo]:
    modules_dir = repo / MODULES_REL
    if not modules_dir.is_dir():
        raise FileNotFoundError(f"module directory missing: {MODULES_REL.as_posix()}")

    modules: list[ModuleInfo] = []
    for child in sorted(modules_dir.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.name == "__pycache__" or child.name.startswith("_"):
            continue
        if not MODULE_NAME_RE.match(child.name):
            raise ValueError(f"unsupported module directory name: {child.name}")
        module_md = child / "MODULE.md"
        source = module_md if module_md.exists() else child
        modules.append(ModuleInfo(child.name, source.relative_to(repo).as_posix()))
    return modules


def module_write_paths(module: str) -> list[str]:
    return [
        f"src/edu_cloud/modules/{module}/**",
        f"tests/test_modules/test_{module}/**",
        f"tests/test_{module}/**",
        f"tests/test_api_{module}/**",
        f"tests/test_services_{module}/**",
    ]


def build_allow(module: str) -> list[str]:
    allow = ["Read(**)"]
    for path in module_write_paths(module):
        allow.append(f"Edit({path})")
        allow.append(f"Write({path})")
    return allow


def _deny_write_patterns(paths: list[str] | tuple[str, ...]) -> list[str]:
    return [f"{tool}({path})" for path in paths for tool in WRITE_TOOLS]


def build_deny(module: str, modules: list[ModuleInfo]) -> list[str]:
    sibling_paths = [
        f"src/edu_cloud/modules/{other.name}/**"
        for other in modules
        if other.name != module
    ]
    deny = list(SHELL_DENIES)
    deny.extend(_deny_write_patterns(SELF_MODIFY_DENY_PATHS))
    deny.extend(_deny_write_patterns(sibling_paths))
    deny.extend(_deny_write_patterns(CENTRAL_DENY_PATHS))
    return deny


def build_profile(module: ModuleInfo, modules: list[ModuleInfo]) -> dict[str, Any]:
    return {
        "permissions": {
            "defaultMode": "dontAsk",
            "disableBypassPermissionsMode": "disable",
            "allow": build_allow(module.name),
            "deny": build_deny(module.name, modules),
        },
    }


def build_manifest(modules: list[ModuleInfo]) -> dict[str, Any]:
    return {
        "schema": MANIFEST_SCHEMA,
        "generatedBy": GENERATED_BY,
        "profile": "windows_no_shell_worker",
        "moduleCount": len(modules),
        "modules": [
            {
                "name": module.name,
                "source": module.source,
                "settingsPath": (MODULE_OUTPUT_REL / f"{module.name}.settings.json").as_posix(),
                "writePaths": module_write_paths(module.name),
            }
            for module in modules
        ],
        "permissions": {
            "defaultMode": "dontAsk",
            "disableBypassPermissionsMode": "disable",
            "shellDeny": list(SHELL_DENIES),
            "centralDenyPaths": list(CENTRAL_DENY_PATHS),
            "selfModifyDenyPaths": list(SELF_MODIFY_DENY_PATHS),
        },
        "startup": {
            "requiredFlags": [
                "--safe-mode",
                "--no-session-persistence",
                "--settings",
            ],
            "forbiddenFlags": [
                "--permission-mode",
                "--dangerously-skip-permissions",
                "--allow-dangerously-skip-permissions",
            ],
            "toolSet": [
                "Read",
                "Edit",
                "Write",
            ],
        },
        "workerContract": {
            "laneDefault": "module_writer",
            "noShell": True,
            "mayRunShell": False,
            "mayRunTests": False,
            "mayRunGit": False,
            "requiresBoundaryProbe": True,
            "boundaryProbeEvidence": "Paste the denied out-of-scope write output into the PR.",
        },
    }


def desired_files(repo: Path) -> dict[Path, str]:
    modules = discover_modules(repo)
    files: dict[Path, str] = {
        MANIFEST_REL: _json(build_manifest(modules)),
    }
    for module in modules:
        files[MODULE_OUTPUT_REL / f"{module.name}.settings.json"] = _json(
            build_profile(module, modules)
        )
    return files


def check_profiles(repo: Path) -> list[str]:
    expected = desired_files(repo)
    errors: list[str] = []

    for relpath, content in expected.items():
        path = repo / relpath
        if not path.exists():
            errors.append(f"missing generated file: {relpath.as_posix()}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != content:
            errors.append(f"stale generated file: {relpath.as_posix()}")

    output_dir = repo / OUTPUT_REL
    if output_dir.exists():
        expected_relpaths = {path.as_posix() for path in expected}
        for stale in sorted(output_dir.rglob("*.json")):
            relpath = stale.relative_to(repo).as_posix()
            if relpath not in expected_relpaths:
                errors.append(f"stale unexpected generated file: {relpath}")

    return errors


def write_profiles(repo: Path) -> None:
    expected = desired_files(repo)
    for relpath, content in expected.items():
        path = repo / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    output_dir = repo / OUTPUT_REL
    expected_relpaths = {path.as_posix() for path in expected}
    if output_dir.exists():
        for stale in sorted(output_dir.rglob("*.json")):
            relpath = stale.relative_to(repo).as_posix()
            if relpath not in expected_relpaths:
                stale.unlink()


def _json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", help="Target repository path")
    parser.add_argument("--write", action="store_true", help="Write generated profiles")
    parser.add_argument("--check", action="store_true", help="Check generated profiles")
    args = parser.parse_args(argv)

    repo = resolve_repo(args.repo)
    if args.write == args.check:
        parser.error("choose exactly one of --write or --check")

    if args.write:
        write_profiles(repo)
        print(f"Generated worker profiles under {OUTPUT_REL.as_posix()}")
        return 0

    errors = check_profiles(repo)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(
            "Regenerate with: python scripts/governance/gen_worker_profile.py --write",
            file=sys.stderr,
        )
        return 1
    print("Worker profiles are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
