#!/usr/bin/env python3
"""Audit AI tool module_code usage against school module switches."""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TOOLS_REL = Path("src/edu_cloud/ai/engine/tools")
SCHOOL_SETTINGS_REL = Path("src/edu_cloud/models/school_settings.py")
BASELINE_REL = Path("docs/governance/ai-tool-module-codes.yaml")

# Domains with unambiguous school-switch ownership. Student/action/system are
# intentionally absent: they are cross-cutting or currently exempt/base domains
# and need explicit product/governance decisions before being rebound.
DOMAIN_EXPECTED_MODULE_CODE = {
    "adaptive": "study_analytics",
    "analytics": "study_analytics",
    "bank": "research",
    "conduct": "conduct",
    "homework": "homework",
    "knowledge": "research",
    "profile": "study_analytics",
}


@dataclass(frozen=True)
class ToolMeta:
    name: str
    module_code: str
    domain: str
    file: str
    line: int

    @property
    def key(self) -> tuple[str, str, str, str]:
        return self.name, self.module_code, self.domain, self.file


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


def _literal_str(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def load_module_codes(repo: Path) -> set[str]:
    tree = ast.parse((repo / SCHOOL_SETTINGS_REL).read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "MODULE_CODES" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Dict):
            raise ValueError("MODULE_CODES must be a literal dict")
        codes = {_literal_str(key) for key in node.value.keys}
        if None in codes:
            raise ValueError("MODULE_CODES keys must be literal strings")
        return {str(code) for code in codes}
    raise ValueError(f"MODULE_CODES not found in {SCHOOL_SETTINGS_REL}")


def _is_edu_tool_call(decorator: ast.AST) -> bool:
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    return isinstance(func, ast.Name) and func.id == "edu_tool"


def _kw(call: ast.Call, name: str) -> ast.AST | None:
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def scan_tools(repo: Path) -> list[ToolMeta]:
    tools_dir = repo / TOOLS_REL
    result: list[ToolMeta] = []
    for py in sorted(tools_dir.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        tree = ast.parse(py.read_text(encoding="utf-8"))
        rel = py.relative_to(repo).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not _is_edu_tool_call(decorator):
                    continue
                call = decorator
                name = _literal_str(_kw(call, "name"))
                if name is None and call.args:
                    name = _literal_str(call.args[0])
                module_code = _literal_str(_kw(call, "module_code"))
                domain = _literal_str(_kw(call, "domain")) or ""
                if name is None:
                    name = node.name
                if module_code is None:
                    module_code = ""
                result.append(
                    ToolMeta(
                        name=name,
                        module_code=module_code,
                        domain=domain,
                        file=rel,
                        line=decorator.lineno,
                    )
                )
    return sorted(result, key=lambda item: item.key)


def build_snapshot(repo: Path) -> dict[str, Any]:
    module_codes = sorted(load_module_codes(repo))
    tools = scan_tools(repo)
    module_counts = Counter(tool.module_code for tool in tools)
    domain_module_counts = Counter((tool.domain, tool.module_code) for tool in tools)
    return {
        "version": 1,
        "generated_by": "scripts/governance/check_ai_tool_modules.py --update",
        "valid_module_codes": module_codes,
        "tool_count": len(tools),
        "module_counts": dict(sorted(module_counts.items())),
        "domain_module_counts": [
            {"domain": domain, "module_code": module_code, "count": count}
            for (domain, module_code), count in sorted(domain_module_counts.items())
        ],
        "tools": [
            {
                "name": tool.name,
                "module_code": tool.module_code,
                "domain": tool.domain,
                "file": tool.file,
                "line": tool.line,
            }
            for tool in tools
        ],
    }


def tool_key_set(snapshot: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    return {
        (item["name"], item["module_code"], item.get("domain") or "", item["file"])
        for item in snapshot.get("tools", [])
    }


def invalid_tools(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    valid = set(snapshot.get("valid_module_codes") or [])
    return [
        item
        for item in snapshot.get("tools", [])
        if not item.get("module_code") or item.get("module_code") not in valid
    ]


def semantic_mismatches(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for item in snapshot.get("tools", []):
        domain = item.get("domain") or ""
        expected = DOMAIN_EXPECTED_MODULE_CODE.get(domain)
        if expected and item.get("module_code") != expected:
            copy = dict(item)
            copy["expected_module_code"] = expected
            mismatches.append(copy)
    return mismatches


def _print_semantic_mismatches(mismatches: list[dict[str, Any]]) -> None:
    for item in mismatches:
        print(
            f"  {item['file']}:{item['line']} {item['name']} "
            f"domain={item.get('domain')!r} module_code={item.get('module_code')!r} "
            f"expected={item['expected_module_code']!r}"
        )


def load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"AI tool module baseline missing: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def compare(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    current_keys = tool_key_set(current)
    baseline_keys = tool_key_set(baseline)
    return {
        "new_tools": sorted(current_keys - baseline_keys),
        "removed_tools": sorted(baseline_keys - current_keys),
        "module_codes_changed": sorted(
            set(current.get("valid_module_codes") or [])
            ^ set(baseline.get("valid_module_codes") or [])
        ),
    }


def write_baseline(repo: Path) -> None:
    path = repo / BASELINE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot(repo)
    invalid = invalid_tools(snapshot)
    if invalid:
        print("Cannot write baseline; invalid AI tool module_code values:")
        for item in invalid:
            print(
                f"  {item['file']}:{item['line']} {item['name']} "
                f"module_code={item['module_code']!r}"
            )
        raise SystemExit(1)
    mismatches = semantic_mismatches(snapshot)
    if mismatches:
        print("Cannot write baseline; AI tool domain/module_code semantic mismatches:")
        _print_semantic_mismatches(mismatches)
        raise SystemExit(1)
    path.write_text(
        yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        f"Updated {path.relative_to(repo)}: "
        f"{snapshot['tool_count']} tools, {len(snapshot['module_counts'])} module codes"
    )


def check_baseline(repo: Path) -> int:
    current = build_snapshot(repo)
    invalid = invalid_tools(current)
    if invalid:
        print("Invalid AI tool module_code values:")
        for item in invalid:
            print(
                f"  {item['file']}:{item['line']} {item['name']} "
                f"module_code={item['module_code']!r}"
            )
        print(f"Valid codes: {current['valid_module_codes']}")
        return 1

    mismatches = semantic_mismatches(current)
    if mismatches:
        print("AI tool domain/module_code semantic mismatches:")
        _print_semantic_mismatches(mismatches)
        return 1

    baseline = load_baseline(repo / BASELINE_REL)
    diff = compare(current, baseline)
    if diff["module_codes_changed"] or diff["new_tools"] or diff["removed_tools"]:
        print("AI tool module baseline drifted:")
        for code in diff["module_codes_changed"]:
            print(f"  module code catalog changed: {code}")
        for name, module_code, domain, file in diff["new_tools"]:
            print(f"  new tool: {name} [{module_code}/{domain}] {file}")
        for name, module_code, domain, file in diff["removed_tools"]:
            print(f"  removed tool: {name} [{module_code}/{domain}] {file}")
        print("Review module ownership, then run:")
        print("  python scripts/governance/check_ai_tool_modules.py --update")
        return 1

    print(
        "AI tool module baseline clean: "
        f"{current['tool_count']} tools, counts={current['module_counts']}"
    )
    return 0


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="Target repository path")
    parser.add_argument("--update", action="store_true", help="Rewrite AI tool baseline")
    args = parser.parse_args(argv)
    repo = resolve_repo(args.repo)
    if args.update:
        write_baseline(repo)
        return 0
    try:
        return check_baseline(repo)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(_main())
