"""aggregate_modules.py 单元/端到端测试（P1-2 Task 3）。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 使 scripts/governance/ 可 import（无需改 pyproject.toml）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "governance"))

from aggregate_modules import (  # noqa: E402
    ModuleGovernanceError,
    aggregate_all,
    detect_conflicts,
    parse_module_md,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_module_md_returns_frontmatter():
    """parse_module_md 读取 MODULE.md 头部 YAML frontmatter。"""
    md_path = FIXTURES / "sample_module" / "MODULE.md"
    meta = parse_module_md(md_path)
    assert meta["name"] == "sample"
    assert meta["status"] == "active"
    assert "sample_tbl" in meta["owns_tables"]


def test_parse_module_md_missing_required_field_raises(tmp_path):
    """缺必填字段 → raise ModuleGovernanceError。"""
    bad = tmp_path / "bad_missing_name"
    bad.mkdir()
    (bad / "MODULE.md").write_text(
        "---\nstatus: active\n---\n# bad\n", encoding="utf-8"
    )
    with pytest.raises(ModuleGovernanceError, match="missing.*name"):
        parse_module_md(bad / "MODULE.md")


# --- G2-02 反退化：嵌套必填字段 ---
def _frontmatter_with(overrides: str) -> str:
    """返回仅在 exposes / depends_on 段被 overrides 定制的最小合法 frontmatter。"""
    return (
        "---\n"
        "name: x\n"
        "status: active\n"
        "owner: t\n"
        "layer: business\n"
        "owns_tables: []\n"
        "owns_routes: []\n"
        f"{overrides}"
        "---\n# x\n"
    )


def test_parse_module_md_missing_nested_exposes_services_raises(tmp_path):
    """G2-02: exposes 缺 services → raise。"""
    md = tmp_path / "MODULE.md"
    # exposes 为空 dict；depends_on 齐
    md.write_text(
        _frontmatter_with(
            "exposes: {}\n"
            "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModuleGovernanceError, match="exposes.services"):
        parse_module_md(md)


def test_parse_module_md_missing_nested_depends_on_modules_raises(tmp_path):
    """G2-02: depends_on 缺 modules → raise。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        _frontmatter_with(
            "exposes:\n  services: []\n"
            "depends_on:\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModuleGovernanceError, match="depends_on.modules"):
        parse_module_md(md)


def test_parse_module_md_nested_non_mapping_raises(tmp_path):
    """G2-02: exposes 不是 mapping → raise。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        _frontmatter_with(
            "exposes: []\n"
            "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModuleGovernanceError, match="exposes.*must be a mapping"):
        parse_module_md(md)


def test_detect_conflicts_finds_duplicate_owns_tables():
    """两个模块声明同一张表 → 返回冲突记录。"""
    modules = [
        {"name": "a", "owns_tables": ["shared_tbl"], "owns_routes": []},
        {"name": "b", "owns_tables": ["shared_tbl"], "owns_routes": []},
    ]
    conflicts = detect_conflicts(modules)
    assert any(
        c["kind"] == "duplicate_table" and c["value"] == "shared_tbl"
        for c in conflicts
    )


def test_detect_conflicts_finds_duplicate_owns_routes():
    """两模块同一路由前缀 → 冲突。"""
    modules = [
        {"name": "a", "owns_tables": [], "owns_routes": ["/api/x"]},
        {"name": "b", "owns_tables": [], "owns_routes": ["/api/x"]},
    ]
    conflicts = detect_conflicts(modules)
    assert any(
        c["kind"] == "duplicate_route" and c["value"] == "/api/x"
        for c in conflicts
    )


def test_aggregate_all_writes_yaml_and_debt_report(tmp_path):
    """aggregate_all 产出 modules.yaml + debt-report.md + dependency-graph.md。"""
    modules_dir = tmp_path / "modules"
    (modules_dir / "alpha").mkdir(parents=True)
    sample_text = (FIXTURES / "sample_module" / "MODULE.md").read_text(encoding="utf-8")
    alpha_text = (
        sample_text.replace("name: sample", "name: alpha")
        .replace("sample_tbl", "alpha_tbl")
        .replace("/api/sample", "/api/alpha")
    )
    (modules_dir / "alpha" / "MODULE.md").write_text(alpha_text, encoding="utf-8")

    (modules_dir / "beta").mkdir(parents=True)
    (modules_dir / "beta" / "__init__.py").touch()

    out_dir = tmp_path / "docs" / "governance"
    aggregate_all(modules_dir=modules_dir, out_dir=out_dir)

    assert (out_dir / "modules.yaml").exists()
    assert (out_dir / "debt-report.md").exists()
    assert (out_dir / "dependency-graph.md").exists()

    debt = (out_dir / "debt-report.md").read_text(encoding="utf-8")
    assert "beta" in debt  # 缺 MODULE.md 的模块被记录


def test_cli_entry_produces_outputs(tmp_path):
    """F004 修正: subprocess 跑 aggregate_modules.py 作为 CLI。

    验证 stdout + exit code + 产物文件，防打包路径/shebang/__main__ 回退。
    """
    import shutil
    import subprocess
    import sys as _sys

    repo = tmp_path
    (repo / "src/edu_cloud/modules/alpha").mkdir(parents=True)
    shutil.copy(
        FIXTURES / "sample_module" / "MODULE.md",
        repo / "src/edu_cloud/modules/alpha/MODULE.md",
    )
    p = repo / "src/edu_cloud/modules/alpha/MODULE.md"
    p.write_text(
        p.read_text(encoding="utf-8")
        .replace("name: sample", "name: alpha")
        .replace("sample_tbl", "alpha_tbl")
        .replace("/api/sample", "/api/alpha"),
        encoding="utf-8",
    )
    (repo / "docs/governance").mkdir(parents=True)
    script = _REPO_ROOT / "scripts" / "governance" / "aggregate_modules.py"
    result = subprocess.run(
        [_sys.executable, str(script)],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stderr={result.stderr} stdout={result.stdout}"
    assert (repo / "docs/governance/modules.yaml").exists()
    assert "Aggregated" in result.stdout
