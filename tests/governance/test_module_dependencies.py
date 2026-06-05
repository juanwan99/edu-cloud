"""Tests for module dependency negative-delta governance."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "governance"))

from check_module_dependencies import (  # noqa: E402
    build_snapshot,
    check_baseline,
    compare,
    compare_declared_dependencies,
    scan_edges,
    write_baseline,
)


def _write_module_md(repo: Path, name: str, deps: list[str] | None = None) -> None:
    deps = deps or []
    path = repo / "src" / "edu_cloud" / "modules" / name
    path.mkdir(parents=True, exist_ok=True)
    if deps:
        module_deps = "\n".join(f"    - {dep}" for dep in deps)
        modules_block = f"  modules:\n{module_deps}\n"
    else:
        modules_block = "  modules: []\n"
    (path / "MODULE.md").write_text(
        (
            "---\n"
            f"name: {name}\n"
            "status: active\n"
            "owner: test\n"
            "layer: business\n"
            "owns_tables: []\n"
            "owns_routes: []\n"
            "exposes:\n"
            "  services: []\n"
            "  events: []\n"
            "depends_on:\n"
            f"{modules_block}"
            "  services: []\n"
            "  ai_tools: []\n"
            "---\n"
            f"# {name}\n\n"
            "## 职责\n"
            "test.\n"
        ),
        encoding="utf-8",
    )


def _module(repo: Path, name: str) -> Path:
    path = repo / "src" / "edu_cloud" / "modules" / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "__init__.py").write_text("", encoding="utf-8")
    if not (path / "MODULE.md").exists():
        _write_module_md(repo, name)
    return path


def _write(repo: Path, module: str, rel: str, text: str) -> None:
    path = _module(repo, module) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_edges_detects_absolute_cross_module_import(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    _write(tmp_path, "alpha", "service.py", "from edu_cloud.modules.beta.models import Thing\n")

    edges = scan_edges(tmp_path)

    assert ("alpha", "beta") in edges
    assert edges[("alpha", "beta")].occurrences == [
        "src/edu_cloud/modules/alpha/service.py:1"
    ]


def test_scan_edges_ignores_same_module_relative_import(tmp_path):
    _module(tmp_path, "alpha")
    _write(tmp_path, "alpha", "export/tool.py", "from ..models import Thing\n")

    edges = scan_edges(tmp_path)

    assert edges == {}


def test_write_baseline_and_check_clean(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    _write(tmp_path, "alpha", "service.py", "from edu_cloud.modules.beta.models import Thing\n")
    _write_module_md(tmp_path, "alpha", ["beta"])

    write_baseline(tmp_path)

    assert check_baseline(tmp_path) == 0


def test_new_edge_fails_against_baseline(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    _module(tmp_path, "gamma")
    _write(tmp_path, "alpha", "service.py", "from edu_cloud.modules.beta.models import Thing\n")
    _write_module_md(tmp_path, "alpha", ["beta"])
    write_baseline(tmp_path)

    _write(tmp_path, "alpha", "other.py", "from edu_cloud.modules.gamma.models import Other\n")

    assert check_baseline(tmp_path) == 1


def test_new_cycle_is_reported(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    _write(tmp_path, "alpha", "service.py", "from edu_cloud.modules.beta.models import Thing\n")
    baseline = build_snapshot(tmp_path)

    _write(tmp_path, "beta", "service.py", "from edu_cloud.modules.alpha.models import Thing\n")
    current = build_snapshot(tmp_path)
    diff = compare(current, baseline)

    assert ("beta", "alpha") in diff["new_edges"]
    assert ("alpha", "beta") in diff["new_cycles"]


def test_removed_edge_is_allowed(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    service = _module(tmp_path, "alpha") / "service.py"
    service.write_text("from edu_cloud.modules.beta.models import Thing\n", encoding="utf-8")
    _write_module_md(tmp_path, "alpha", ["beta"])
    write_baseline(tmp_path)

    service.write_text("# dependency removed\n", encoding="utf-8")
    _write_module_md(tmp_path, "alpha", [])

    assert check_baseline(tmp_path) == 0


def test_missing_module_declaration_fails_contract(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    _write(tmp_path, "alpha", "service.py", "from edu_cloud.modules.beta.models import Thing\n")
    write_baseline(tmp_path)

    assert check_baseline(tmp_path) == 1


def test_stale_module_declaration_fails_contract(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    _write_module_md(tmp_path, "alpha", ["beta"])
    write_baseline(tmp_path)

    assert check_baseline(tmp_path) == 1


def test_compare_declared_dependencies_reports_drift(tmp_path):
    _module(tmp_path, "alpha")
    _module(tmp_path, "beta")
    _module(tmp_path, "gamma")
    _write(tmp_path, "alpha", "service.py", "from edu_cloud.modules.beta.models import Thing\n")
    _write_module_md(tmp_path, "alpha", ["gamma"])

    diff = compare_declared_dependencies(tmp_path, build_snapshot(tmp_path))

    assert diff["missing_declarations"] == [("alpha", "beta")]
    assert diff["stale_declarations"] == [("alpha", "gamma")]
