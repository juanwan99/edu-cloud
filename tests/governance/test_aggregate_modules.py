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
    check_outputs,
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


# --- 结构治理字段（structure_pattern / max_router_loc / routers）---


def test_structure_pattern_valid_values(tmp_path):
    """structure_pattern 只接受 standard / multi-router / service-only。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        _frontmatter_with(
            "structure_pattern: invalid\n"
            "max_router_loc: 400\n"
            "routers: []\n"
            "exposes:\n  services: []\n  events: []\n"
            "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModuleGovernanceError, match="structure_pattern"):
        parse_module_md(md)


def test_structure_pattern_standard(tmp_path):
    """合法 structure_pattern + max_router_loc + routers → 通过校验。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        _frontmatter_with(
            "structure_pattern: standard\n"
            "max_router_loc: 350\n"
            "routers: [router.py]\n"
            "exposes:\n  services: []\n  events: []\n"
            "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    meta = parse_module_md(md)
    assert meta["structure_pattern"] == "standard"
    assert meta["max_router_loc"] == 350
    assert meta["routers"] == ["router.py"]


def test_max_router_loc_must_be_non_negative(tmp_path):
    """max_router_loc 为负数 → raise。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        _frontmatter_with(
            "structure_pattern: standard\n"
            "max_router_loc: -1\n"
            "routers: []\n"
            "exposes:\n  services: []\n  events: []\n"
            "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModuleGovernanceError, match="max_router_loc"):
        parse_module_md(md)


def test_max_router_loc_rejects_bool(tmp_path):
    """max_router_loc: true (bool 是 int 子类) → raise。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        _frontmatter_with(
            "structure_pattern: standard\n"
            "max_router_loc: true\n"
            "routers: []\n"
            "exposes:\n  services: []\n  events: []\n"
            "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ModuleGovernanceError, match="max_router_loc"):
        parse_module_md(md)


def test_backward_compat_old_module_md(tmp_path):
    """旧格式（无新字段）仍然通过校验——向后兼容。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        _frontmatter_with(
            "exposes:\n  services: []\n  events: []\n"
            "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        ),
        encoding="utf-8",
    )
    meta = parse_module_md(md)
    assert "structure_pattern" not in meta  # optional, no default injected


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


def _write_sample_module(repo: Path, name: str, table: str | None = None, route: str | None = None):
    module_dir = repo / f"src/edu_cloud/modules/{name}"
    module_dir.mkdir(parents=True, exist_ok=True)
    sample_text = (FIXTURES / "sample_module" / "MODULE.md").read_text(encoding="utf-8")
    module_text = (
        sample_text.replace("name: sample", f"name: {name}")
        .replace("sample_tbl", table or f"{name}_tbl")
        .replace("/api/sample", route or f"/api/{name}")
    )
    (module_dir / "MODULE.md").write_text(module_text, encoding="utf-8")
    return module_dir


def _run_script(repo: Path, *args: str):
    import subprocess
    import sys as _sys

    script = _REPO_ROOT / "scripts" / "governance" / "aggregate_modules.py"
    return subprocess.run(
        [_sys.executable, str(script), *args, "--repo", str(repo)],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


def _git_init(repo: Path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)


def test_check_exit_0_clean(tmp_path):
    """--check exits 0 when derived products are fresh."""
    repo = tmp_path
    _write_sample_module(repo, "alpha")
    (repo / "docs/governance").mkdir(parents=True)
    assert _run_script(repo).returncode == 0

    result = _run_script(repo, "--check")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "stale': []" in result.stdout


def test_check_exit_1_stale_and_no_write(tmp_path):
    """--check reports stale products without rewriting them."""
    repo = tmp_path
    _write_sample_module(repo, "alpha")
    out_dir = repo / "docs/governance"
    out_dir.mkdir(parents=True)
    assert _run_script(repo).returncode == 0
    marker = "manual stale marker\n"
    (out_dir / "modules.yaml").write_text(marker, encoding="utf-8")

    result = _run_script(repo, "--check")

    assert result.returncode == 1
    assert (out_dir / "modules.yaml").read_text(encoding="utf-8") == marker


def test_check_outputs_reports_stale_without_writing(tmp_path):
    """Direct check_outputs also stays read-only."""
    repo = tmp_path
    _write_sample_module(repo, "alpha")
    out_dir = repo / "docs/governance"
    out_dir.mkdir(parents=True)
    assert _run_script(repo).returncode == 0
    marker = "old\n"
    (out_dir / "debt-report.md").write_text(marker, encoding="utf-8")

    code, result = check_outputs(repo)

    assert code == 1
    assert "debt-report.md" in result["stale"]
    assert (out_dir / "debt-report.md").read_text(encoding="utf-8") == marker


def test_check_exit_2_parse_error(tmp_path):
    """Invalid MODULE.md frontmatter is a parse-error check failure."""
    repo = tmp_path
    bad = repo / "src/edu_cloud/modules/bad"
    bad.mkdir(parents=True)
    (bad / "MODULE.md").write_text("---\nname: bad\n---\n# bad\n", encoding="utf-8")
    (repo / "docs/governance").mkdir(parents=True)

    result = _run_script(repo, "--check")

    assert result.returncode == 2
    assert "missing required field" in result.stderr


def test_check_exit_3_conflict(tmp_path):
    """Duplicate ownership is stronger than stale output."""
    repo = tmp_path
    _write_sample_module(repo, "alpha", table="shared_tbl")
    _write_sample_module(repo, "beta", table="shared_tbl")
    (repo / "docs/governance").mkdir(parents=True)

    result = _run_script(repo, "--check")

    assert result.returncode == 3
    assert "'conflicts': 1" in result.stdout


def test_check_exit_4_debt(tmp_path):
    """Missing MODULE.md is reported as governance debt."""
    repo = tmp_path
    _write_sample_module(repo, "alpha")
    debt_dir = repo / "src/edu_cloud/modules/beta"
    debt_dir.mkdir(parents=True)
    (debt_dir / "__init__.py").write_text("", encoding="utf-8")
    (repo / "docs/governance").mkdir(parents=True)

    result = _run_script(repo, "--check")

    assert result.returncode == 4
    assert "'debt': 1" in result.stdout


def test_check_staged_uses_index_not_working_tree(tmp_path):
    """--check --staged ignores unstaged worktree edits and trusts the index."""
    repo = tmp_path
    _git_init(repo)
    module_dir = _write_sample_module(repo, "alpha")
    (repo / "docs/governance").mkdir(parents=True)
    assert _run_script(repo).returncode == 0

    import subprocess

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    (module_dir / "MODULE.md").write_text("---\nname: alpha\n---\n# broken\n", encoding="utf-8")

    result = _run_script(repo, "--check", "--staged")

    assert result.returncode == 0, result.stderr + result.stdout


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
