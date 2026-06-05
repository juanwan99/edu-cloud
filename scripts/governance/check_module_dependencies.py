#!/usr/bin/env python3
"""Check actual cross-module imports against a frozen dependency baseline.

This is a negative-delta gate: existing cross-module edges and cycles are allowed
as baseline debt, but newly introduced edges or cycles fail --check.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MODULES_REL = Path("src/edu_cloud/modules")
BASELINE_REL = Path("docs/governance/module-dependencies.yaml")


@dataclass
class Edge:
    source: str
    target: str
    occurrences: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        return self.source, self.target


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


def module_names(modules_dir: Path) -> set[str]:
    return {
        child.name
        for child in modules_dir.iterdir()
        if child.is_dir() and child.name != "__pycache__" and not child.name.startswith("_")
    }


def _package_for_file(rel: Path) -> list[str]:
    parts = ["edu_cloud", "modules", *rel.with_suffix("").parts]
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return parts


def _resolve_import_from(rel: Path, node: ast.ImportFrom) -> str | None:
    if node.level == 0:
        return node.module
    package = _package_for_file(rel)
    keep = max(0, len(package) - node.level + 1)
    parts = package[:keep]
    if node.module:
        parts.extend(node.module.split("."))
    return ".".join(parts)


def _target_from_module(module: str | None, modules: set[str], source: str) -> str | None:
    if not module or not module.startswith("edu_cloud.modules."):
        return None
    parts = module.split(".")
    if len(parts) < 3:
        return None
    target = parts[2]
    if target not in modules or target == source:
        return None
    return target


def scan_edges(repo: Path) -> dict[tuple[str, str], Edge]:
    modules_dir = repo / MODULES_REL
    modules = module_names(modules_dir)
    edges: dict[tuple[str, str], Edge] = {}

    def add(source: str, target: str, occurrence: str) -> None:
        edge = edges.setdefault((source, target), Edge(source=source, target=target))
        if len(edge.occurrences) < 8:
            edge.occurrences.append(occurrence)

    for py in sorted(modules_dir.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        rel = py.relative_to(modules_dir)
        source = rel.parts[0]
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = _target_from_module(alias.name, modules, source)
                    if target:
                        add(source, target, f"{py.relative_to(repo).as_posix()}:{node.lineno}")
            elif isinstance(node, ast.ImportFrom):
                module = _resolve_import_from(rel, node)
                target = _target_from_module(module, modules, source)
                if target:
                    add(source, target, f"{py.relative_to(repo).as_posix()}:{node.lineno}")
            elif isinstance(node, ast.Call):
                target = _target_from_dynamic_import(node, modules, source)
                if target:
                    add(source, target, f"{py.relative_to(repo).as_posix()}:{node.lineno}")
    return edges


def _target_from_dynamic_import(node: ast.Call, modules: set[str], source: str) -> str | None:
    func = node.func
    is_import_module = (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        or isinstance(func, ast.Name)
        and func.id == "__import__"
    )
    if not is_import_module or not node.args:
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    return _target_from_module(first.value, modules, source)


def _normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    min_i = min(range(len(cycle)), key=lambda i: cycle[i])
    return tuple(cycle[min_i:] + cycle[:min_i])


def find_cycles(edge_keys: set[tuple[str, str]]) -> set[tuple[str, ...]]:
    nodes = sorted({x for edge in edge_keys for x in edge})
    adjacency = {node: sorted(dst for src, dst in edge_keys if src == node) for node in nodes}
    cycles: set[tuple[str, ...]] = set()

    for start in nodes:
        def visit(node: str, path: list[str]) -> None:
            for nxt in adjacency.get(node, []):
                if nxt == start and len(path) > 1:
                    cycles.add(_normalize_cycle(path))
                elif nxt not in path and nxt >= start:
                    visit(nxt, path + [nxt])

        visit(start, [start])
    return cycles


def build_snapshot(repo: Path) -> dict[str, Any]:
    edges = scan_edges(repo)
    edge_keys = set(edges)
    cycles = find_cycles(edge_keys)
    return {
        "version": 1,
        "generated_by": "scripts/governance/check_module_dependencies.py --update",
        "modules": sorted(module_names(repo / MODULES_REL)),
        "edges": [
            {
                "from": edge.source,
                "to": edge.target,
                "occurrences": edge.occurrences,
            }
            for edge in sorted(edges.values(), key=lambda e: (e.source, e.target))
        ],
        "cycles": [
            {"path": list(cycle) + [cycle[0]]}
            for cycle in sorted(cycles)
        ],
    }


def load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Dependency baseline missing: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def edge_set(snapshot: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (item["from"], item["to"])
        for item in snapshot.get("edges", [])
    }


def cycle_set(snapshot: dict[str, Any]) -> set[tuple[str, ...]]:
    result: set[tuple[str, ...]] = set()
    for item in snapshot.get("cycles", []):
        path = list(item.get("path") or [])
        if len(path) >= 2 and path[0] == path[-1]:
            path = path[:-1]
        if path:
            result.add(_normalize_cycle(path))
    return result


def _import_aggregate_module(repo: Path):
    candidates = [
        repo / "scripts" / "governance" / "aggregate_modules.py",
        Path(__file__).resolve().parent / "aggregate_modules.py",
    ]
    for path in candidates:
        if not path.exists():
            continue
        module_name = f"_edu_cloud_aggregate_modules_{abs(hash(path.resolve()))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    raise ModuleNotFoundError(
        "aggregate_modules.py not found in repo or scripts/governance"
    )


def declared_edge_set(repo: Path) -> set[tuple[str, str]]:
    modules_dir = repo / MODULES_REL
    modules = module_names(modules_dir)
    declared: set[tuple[str, str]] = set()
    agg = _import_aggregate_module(repo)
    for module in sorted(modules):
        md = modules_dir / module / "MODULE.md"
        if not md.exists():
            continue
        data = agg.parse_module_md(md)
        for target in (data.get("depends_on") or {}).get("modules") or []:
            declared.add((module, str(target)))
    return declared


def compare_declared_dependencies(
    repo: Path, current: dict[str, Any]
) -> dict[str, list[tuple[str, str]]]:
    actual = edge_set(current)
    declared = declared_edge_set(repo)
    return {
        "missing_declarations": sorted(actual - declared),
        "stale_declarations": sorted(declared - actual),
    }


def compare(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    current_edges = edge_set(current)
    baseline_edges = edge_set(baseline)
    current_cycles = cycle_set(current)
    baseline_cycles = cycle_set(baseline)
    return {
        "new_edges": sorted(current_edges - baseline_edges),
        "removed_edges": sorted(baseline_edges - current_edges),
        "new_cycles": sorted(current_cycles - baseline_cycles),
        "removed_cycles": sorted(baseline_cycles - current_cycles),
    }


def write_baseline(repo: Path) -> None:
    path = repo / BASELINE_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot(repo)
    path.write_text(
        yaml.safe_dump(snapshot, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(
        f"Updated {path.relative_to(repo)}: "
        f"{len(snapshot['edges'])} edges, {len(snapshot['cycles'])} cycles"
    )


def check_baseline(repo: Path) -> int:
    baseline = load_baseline(repo / BASELINE_REL)
    current = build_snapshot(repo)
    diff = compare(current, baseline)
    if diff["new_edges"] or diff["new_cycles"]:
        print("Module dependency baseline worsened:")
        for source, target in diff["new_edges"]:
            print(f"  new edge: {source} -> {target}")
        for cycle in diff["new_cycles"]:
            print(f"  new cycle: {' -> '.join(cycle + (cycle[0],))}")
        print("If this is intentional, update the design and run:")
        print("  python scripts/governance/check_module_dependencies.py --update")
        return 1
    declaration_diff = compare_declared_dependencies(repo, current)
    if (
        declaration_diff["missing_declarations"]
        or declaration_diff["stale_declarations"]
    ):
        print("Module dependency declarations drifted from actual imports:")
        for source, target in declaration_diff["missing_declarations"]:
            print(f"  missing MODULE.md declaration: {source} -> {target}")
        for source, target in declaration_diff["stale_declarations"]:
            print(f"  stale MODULE.md declaration: {source} -> {target}")
        print("Update MODULE.md depends_on.modules and regenerate governance docs:")
        print("  python scripts/governance/aggregate_modules.py")
        return 1
    print(
        "Module dependency baseline clean: "
        f"{len(current['edges'])} edges, {len(current['cycles'])} cycles"
    )
    if diff["removed_edges"] or diff["removed_cycles"]:
        print(
            "Dependency debt improved; consider refreshing the baseline with "
            "`--update`."
        )
    return 0


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="Target repository path")
    parser.add_argument("--update", action="store_true", help="Rewrite dependency baseline")
    parser.add_argument("--check", action="store_true", help="Check current dependencies against baseline")
    args = parser.parse_args()

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
