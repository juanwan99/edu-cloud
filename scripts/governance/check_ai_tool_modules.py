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
INVALID_LITERAL = "<invalid-literal>"

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
    module_code: str | None
    domain: str
    file: str
    line: int
    requires_modules: tuple[str, ...]

    @property
    def key(self) -> tuple[str, str, str, str, tuple[str, ...]]:
        return self.name, _module_key(self.module_code), self.domain, self.file, self.requires_modules


def _module_key(module_code: str | None) -> str:
    return "__base__" if module_code is None else module_code


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


def _literal_module_code(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        if node.value is None:
            return None
        if isinstance(node.value, str):
            return node.value
    return INVALID_LITERAL


def _literal_str_sequence(node: ast.AST | None) -> tuple[str, ...] | None:
    if node is None:
        return ()
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "frozenset":
            if not node.args:
                return ()
            if len(node.args) == 1:
                return _literal_str_sequence(node.args[0])
        return None
    if not isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        return None
    values = []
    for item in node.elts:
        value = _literal_str(item)
        if value is None:
            return None
        values.append(value)
    return tuple(sorted(values))


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
                module_code = _literal_module_code(_kw(call, "module_code"))
                domain = _literal_str(_kw(call, "domain")) or ""
                requires_modules = _literal_str_sequence(_kw(call, "requires_modules"))
                if name is None:
                    name = node.name
                if requires_modules is None:
                    requires_modules = (INVALID_LITERAL,)
                result.append(
                    ToolMeta(
                        name=name,
                        module_code=module_code,
                        domain=domain,
                        file=rel,
                        line=decorator.lineno,
                        requires_modules=requires_modules,
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
        "module_counts": dict(sorted(module_counts.items(), key=lambda item: _module_key(item[0]))),
        "domain_module_counts": [
            {"domain": domain, "module_code": module_code, "count": count}
            for (domain, module_code), count in sorted(
                domain_module_counts.items(),
                key=lambda item: (item[0][0], _module_key(item[0][1])),
            )
        ],
        "tools": [
            {
                "name": tool.name,
                "module_code": tool.module_code,
                "domain": tool.domain,
                "file": tool.file,
                "line": tool.line,
                "requires_modules": list(tool.requires_modules),
            }
            for tool in tools
        ],
    }


def tool_key_set(snapshot: dict[str, Any]) -> set[tuple[str, str, str, str, tuple[str, ...]]]:
    return {
        (
            item["name"],
            _module_key(item.get("module_code")),
            item.get("domain") or "",
            item["file"],
            tuple(sorted(item.get("requires_modules") or [])),
        )
        for item in snapshot.get("tools", [])
    }


def invalid_tools(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    valid = set(snapshot.get("valid_module_codes") or [])
    invalid: list[dict[str, Any]] = []
    for item in snapshot.get("tools", []):
        reasons = []
        module_code = item.get("module_code")
        if module_code is not None and module_code not in valid:
            reasons.append(f"module_code={module_code!r}")
        for module in item.get("requires_modules") or []:
            if module not in valid:
                reasons.append(f"requires_modules contains {module!r}")
        if reasons:
            copy = dict(item)
            copy["_invalid_reasons"] = reasons
            invalid.append(copy)
    return invalid


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
                f"module_code={item.get('module_code')!r} "
                f"requires_modules={item.get('requires_modules')!r} "
                f"reasons={item.get('_invalid_reasons')!r}"
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
                f"module_code={item.get('module_code')!r} "
                f"requires_modules={item.get('requires_modules')!r} "
                f"reasons={item.get('_invalid_reasons')!r}"
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
        for name, module_code, domain, file, requires_modules in diff["new_tools"]:
            print(
                f"  new tool: {name} [{module_code}/{domain}] "
                f"requires_modules={list(requires_modules)} {file}"
            )
        for name, module_code, domain, file, requires_modules in diff["removed_tools"]:
            print(
                f"  removed tool: {name} [{module_code}/{domain}] "
                f"requires_modules={list(requires_modules)} {file}"
            )
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
