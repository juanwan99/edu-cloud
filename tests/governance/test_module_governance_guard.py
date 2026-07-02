"""module_governance_guard.py 单元/入口级测试（P3 Task 6）。

覆盖:
- F001: hook 入口契约（data, session_state, staged_info）
- F002: 新旧判定用 git ls-tree HEAD（不用 MODULE.md 存在性近似）
- F004: 入口级测试
- F006: staged_info 真实结构 {"files", "diff"}
- F007: 工作区存在但未 staged 仍 block
- F008: staged MODULE.md 必须通过 parse_module_md 校验
- F009: 派生产物过期 → block
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

SCRIPTS_GOVERNANCE = Path(__file__).resolve().parents[2] / "scripts" / "governance"
# module_governance_guard 必须来自仓库内规则源；aggregate_modules 也从同目录提供。
sys.path.insert(0, str(SCRIPTS_GOVERNANCE))

import module_governance_guard as g  # noqa: E402


def test_guard_source_is_repo_local():
    assert Path(g.__file__).resolve() == (
        SCRIPTS_GOVERNANCE / "module_governance_guard.py"
    ).resolve()


def _git_init(repo: Path):
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)


def _valid_frontmatter(name: str) -> str:
    """最小合法 MODULE.md（通过 parse_module_md 校验）。"""
    return (
        f"---\n"
        f"name: {name}\n"
        f"status: active\n"
        f"owner: test\n"
        f"layer: business\n"
        f"owns_tables: []\n"
        f"owns_routes: []\n"
        f"exposes:\n  services: []\n  events: []\n"
        f"depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        f"---\n# {name}\n\n## 职责\ntest.\n"
    )


def _setup_aggregate_script(repo: Path):
    """为 F008 frontmatter 校验提供 aggregate_modules 脚本。"""
    scripts_dir = repo / "scripts" / "governance"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    real = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "governance"
        / "aggregate_modules.py"
    )
    if real.exists():
        (scripts_dir / "aggregate_modules.py").write_text(
            real.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (scripts_dir / "__init__.py").touch()


def _git_init_with_module(
    repo: Path, module_name: str, include_module_md: bool = False
):
    _git_init(repo)
    _setup_aggregate_script(repo)
    mdir = repo / "src/edu_cloud/modules" / module_name
    mdir.mkdir(parents=True)
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    if include_module_md:
        (mdir / "MODULE.md").write_text(
            _valid_frontmatter(module_name), encoding="utf-8"
        )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=repo, check=True)


def _sample_diff(path: str, added: int, deleted: int) -> str:
    """构造最小 unified diff。"""
    plus = "\n".join(f"+line{i}" for i in range(added))
    minus = "\n".join(f"-line{i}" for i in range(deleted))
    body = "\n".join([x for x in [plus, minus] if x])
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1 @@\n"
        f"{body}\n"
    )


# --- 单元：parse_diff_line_counts ---
def test_parse_diff_line_counts_basic():
    diff = _sample_diff("a/b.py", added=3, deleted=2)
    r = g.parse_diff_line_counts(diff)
    assert r["a/b.py"]["added"] == 3
    assert r["a/b.py"]["deleted"] == 2


def test_parse_diff_line_counts_multi_file():
    diff = _sample_diff("x.py", 5, 0) + _sample_diff("y.py", 0, 4)
    r = g.parse_diff_line_counts(diff)
    assert r["x.py"] == {"added": 5, "deleted": 0}
    assert r["y.py"] == {"added": 0, "deleted": 4}


def test_parse_diff_line_counts_ignores_headers():
    """+++/--- 头行不算 added/deleted。"""
    diff = _sample_diff("f.py", 2, 0)
    r = g.parse_diff_line_counts(diff)
    assert r["f.py"]["added"] == 2  # 不含 +++


# --- 单元：check_new_module（F002 + F007 + F008） ---
def test_new_module_without_module_md_blocks(tmp_path):
    _git_init(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    files = ["src/edu_cloud/modules/newmod/__init__.py"]
    result = g.check_new_module(files, tmp_path)
    assert result["decision"] == "block"
    assert "newmod" in result["reason"]


def test_new_module_with_valid_module_md_staged_passes(tmp_path):
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    (mdir / "MODULE.md").write_text(_valid_frontmatter("newmod"), encoding="utf-8")
    files = [
        "src/edu_cloud/modules/newmod/__init__.py",
        "src/edu_cloud/modules/newmod/MODULE.md",
    ]
    result = g.check_new_module(files, tmp_path)
    assert result is None


def test_new_module_module_md_in_workspace_but_not_staged_still_blocks(tmp_path):
    """F007 反退化: MODULE.md 在工作区但未 git add → 仍 block。"""
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    (tmp_path / "src/edu_cloud/modules/newmod/MODULE.md").write_text(
        _valid_frontmatter("newmod"), encoding="utf-8"
    )
    files = ["src/edu_cloud/modules/newmod/__init__.py"]  # MODULE.md 不在 staged
    result = g.check_new_module(files, tmp_path)
    assert result is not None, "F007 退化：工作区存在被误放行"
    assert result["decision"] == "block"


def test_new_module_with_invalid_module_md_missing_field_blocks(tmp_path):
    """F008: staged MODULE.md 缺必填字段 → block。"""
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    (mdir / "MODULE.md").write_text("---\nname: newmod\n---\n# x\n", encoding="utf-8")
    files = [
        "src/edu_cloud/modules/newmod/__init__.py",
        "src/edu_cloud/modules/newmod/MODULE.md",
    ]
    result = g.check_new_module(files, tmp_path)
    assert result is not None, "F008 退化：非法 frontmatter 被放行"
    assert result["decision"] == "block"
    assert "newmod" in result["reason"]


def test_new_module_with_invalid_yaml_blocks(tmp_path):
    """F008: staged MODULE.md YAML 语法错误 → block。"""
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    (mdir / "MODULE.md").write_text("---\nname: [unclosed\n---\n", encoding="utf-8")
    files = [
        "src/edu_cloud/modules/newmod/__init__.py",
        "src/edu_cloud/modules/newmod/MODULE.md",
    ]
    result = g.check_new_module(files, tmp_path)
    assert result is not None
    assert result["decision"] == "block"


def test_check_entry_blocks_on_invalid_existing_module_md(tmp_path):
    """F008 + G2-01: 存量模块 MODULE.md 非法 → loader 报错 → check() block。

    G2-01 修复后：坏版本必须是 staged 的（git add 过）才触发 loader 失败。
    """
    _git_init_with_module(tmp_path, "legacy", include_module_md=True)
    md = tmp_path / "src/edu_cloud/modules/legacy/MODULE.md"
    md.write_text("---\nname: legacy\n---\n", encoding="utf-8")  # 缺字段
    subprocess.run(["git", "add", "src/edu_cloud/modules/legacy/MODULE.md"], cwd=tmp_path, check=True)
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/legacy/MODULE.md"],
        "diff": _sample_diff("src/edu_cloud/modules/legacy/MODULE.md", 2, 0),
    }
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None
    assert result["decision"] == "block"
    assert "解析失败" in result["reason"] or "legacy" in result["reason"]


def test_legacy_module_without_module_md_not_blocked_by_new_check(tmp_path):
    """F002 反退化: 存量模块缺 MODULE.md 不应被 check_new_module 拦截。"""
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    files = ["src/edu_cloud/modules/legacy/service.py"]
    assert g.check_new_module(files, tmp_path) is None


# --- 单元：owns 冲突 ---
def test_duplicate_owns_tables_blocks():
    modules = [
        {"name": "a", "owns_tables": ["shared"], "owns_routes": []},
        {"name": "b", "owns_tables": ["shared"], "owns_routes": []},
    ]
    result = g.check_ownership_conflicts(modules)
    assert result["decision"] == "block"
    assert "shared" in result["reason"]


def test_same_module_duplicate_owns_not_conflict():
    modules = [{"name": "a", "owns_tables": ["t", "t"], "owns_routes": []}]
    assert g.check_ownership_conflicts(modules) is None


def _write_workflow_service(repo: Path, name: str):
    services_dir = repo / "src/edu_cloud/services"
    services_dir.mkdir(parents=True, exist_ok=True)
    (services_dir / f"{name}.py").write_text("# test workflow\n", encoding="utf-8")


def test_workflow_service_missing_owner_blocks(tmp_path):
    _write_workflow_service(tmp_path, "alpha_workflow")
    modules = [{"name": "alpha", "owns_services": []}]

    result = g.check_workflow_service_ownership(tmp_path, modules)

    assert result is not None
    assert result["decision"] == "block"
    assert "missing workflow owner" in result["reason"]
    assert "src/edu_cloud/services/alpha_workflow.py" in result["reason"]


def test_workflow_service_duplicate_owner_blocks(tmp_path):
    _write_workflow_service(tmp_path, "alpha_workflow")
    modules = [
        {
            "name": "alpha",
            "owns_services": ["src/edu_cloud/services/alpha_workflow.py"],
        },
        {
            "name": "beta",
            "owns_services": ["src/edu_cloud/services/alpha_workflow.py"],
        },
    ]

    result = g.check_workflow_service_ownership(tmp_path, modules)

    assert result is not None
    assert result["decision"] == "block"
    assert "duplicate workflow owner" in result["reason"]
    assert "alpha, beta" in result["reason"]


def test_workflow_service_single_owner_passes(tmp_path):
    _write_workflow_service(tmp_path, "alpha_workflow")
    modules = [{"name": "alpha", "owns_services": ["alpha_workflow"]}]

    assert g.check_workflow_service_ownership(tmp_path, modules) is None


def test_repository_workflow_service_ownership_passes():
    repo = Path(__file__).resolve().parents[2]

    assert g.check_workflow_service_ownership(repo) is None


# --- 单元：check_touched_legacy（files + diff 契约 F006） ---
def test_large_modification_without_module_md_blocks(tmp_path):
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    path = "src/edu_cloud/modules/legacy/service.py"
    diff = _sample_diff(path, added=40, deleted=20)
    result = g.check_touched_legacy([path], diff, tmp_path)
    assert result["decision"] == "block"
    assert "legacy" in result["reason"]


def test_small_modification_does_not_ask(tmp_path):
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    path = "src/edu_cloud/modules/legacy/service.py"
    diff = _sample_diff(path, added=3, deleted=2)
    assert g.check_touched_legacy([path], diff, tmp_path) is None


# --- 入口级（F001/F004/F006）：check() 消费真实 staged_info ---
def test_hook_entry_blocks_on_new_module_without_module_md(tmp_path):
    _git_init(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m test"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/newmod/__init__.py"],
        "diff": _sample_diff("src/edu_cloud/modules/newmod/__init__.py", 1, 0),
    }
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None
    assert result["decision"] == "block"
    assert "newmod" in result["reason"]


def test_hook_entry_blocks_on_large_legacy_touch(tmp_path):
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    path = "src/edu_cloud/modules/legacy/service.py"
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {"files": [path], "diff": _sample_diff(path, 40, 20)}
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None
    assert result["decision"] == "block"


def test_hook_entry_allows_non_edu_cloud_repo(tmp_path):
    data = {"cwd": "/some/other/repo", "tool_input": {"command": "git commit -m x"}}
    result = g.check(data, MagicMock(), staged_info={"files": [], "diff": ""})
    assert result is None


def test_hook_entry_allows_non_git_commit_command(tmp_path):
    _git_init(tmp_path)
    data = {"cwd": str(tmp_path), "tool_input": {"command": "ls -la"}}
    result = g.check(data, MagicMock(), staged_info={"files": ["x"], "diff": ""})
    assert result is None


# --- F009: 派生产物过期检测 ---
def test_derived_products_stale_blocks(tmp_path):
    """F009: MODULE.md 变更但 modules.yaml 未刷新 → block。"""
    _git_init_with_module(tmp_path, "alpha", include_module_md=True)
    out = tmp_path / "docs/governance"
    out.mkdir(parents=True, exist_ok=True)
    (out / "modules.yaml").write_text("stale: true\n", encoding="utf-8")
    (out / "dependency-graph.md").write_text("old\n", encoding="utf-8")
    (out / "debt-report.md").write_text("old\n", encoding="utf-8")
    files = ["src/edu_cloud/modules/alpha/MODULE.md"]
    result = g.check_derived_products_fresh(tmp_path, files)
    assert result is not None, "F009 退化：派生产物漂移未被检测"
    assert result["decision"] == "block"
    assert "modules.yaml" in result["reason"]


def test_derived_products_fresh_passes(tmp_path):
    """派生产物与 MODULE.md 同步 → allow。"""
    _git_init_with_module(tmp_path, "alpha", include_module_md=True)
    out = tmp_path / "docs/governance"
    out.mkdir(parents=True, exist_ok=True)
    import aggregate_modules  # noqa: E402 — 由 _setup_aggregate_script 放在 sys.path
    aggregate_modules.aggregate_all(tmp_path / "src/edu_cloud/modules", out)
    files = ["src/edu_cloud/modules/alpha/MODULE.md"]
    assert g.check_derived_products_fresh(tmp_path, files) is None


def test_derived_products_check_blocks_when_no_governance_dir(tmp_path):
    """docs/governance/ 不存在时无法证明派生产物 freshness → block。"""
    _git_init_with_module(tmp_path, "alpha", include_module_md=True)
    files = ["src/edu_cloud/modules/alpha/MODULE.md"]
    result = g.check_derived_products_fresh(tmp_path, files)
    assert result is not None
    assert result["decision"] == "block"
    assert "docs/governance" in result["reason"]


# --- G2-01 反退化: staged vs worktree 分叉（"只信 staged"） ---
def test_hook_entry_trusts_staged_blob_not_worktree_on_new_module(tmp_path):
    """G2-01: git add 合法 MODULE.md 后在 worktree 改坏 → 不 block（信 staged）。

    旧 guard 直接读 worktree 文件会误报 block；新 guard 从 checkout-index 快照读 → None。
    """
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    md = mdir / "MODULE.md"
    md.write_text(_valid_frontmatter("newmod"), encoding="utf-8")
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    out = tmp_path / "docs/governance"
    out.mkdir(parents=True, exist_ok=True)
    import aggregate_modules  # noqa: E402 — _setup_aggregate_script 已 setup
    aggregate_modules.aggregate_all(tmp_path / "src/edu_cloud/modules", out)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    # staged 合法；在 worktree 改坏（未 git add）
    md.write_text("---\ninvalid: true\n---\n", encoding="utf-8")
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": [
            "src/edu_cloud/modules/newmod/__init__.py",
            "src/edu_cloud/modules/newmod/MODULE.md",
        ],
        "diff": _sample_diff("src/edu_cloud/modules/newmod/MODULE.md", 11, 0),
    }
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is None, "G2-01 退化：guard 读 worktree 而非 staged index"


def test_hook_entry_blocks_when_staged_module_md_is_invalid(tmp_path):
    """G2-01 互补: staged 坏版本 + worktree 好版本 → block（仍信 staged）。"""
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    md = mdir / "MODULE.md"
    # 先写坏版本并 staged
    md.write_text("---\nname: newmod\n---\n", encoding="utf-8")  # 缺字段
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    # 随后在 worktree 写好版本（未 add）
    md.write_text(_valid_frontmatter("newmod"), encoding="utf-8")
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": [
            "src/edu_cloud/modules/newmod/__init__.py",
            "src/edu_cloud/modules/newmod/MODULE.md",
        ],
        "diff": _sample_diff("src/edu_cloud/modules/newmod/MODULE.md", 2, 0),
    }
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None, "G2-01 退化：guard 读 worktree 而非 staged，staged 坏版本被放过"
    assert result["decision"] == "block"


def test_hook_entry_derived_products_trust_staged_snapshot(tmp_path):
    """G2-01 + F009: staged MODULE.md 新版 + staged 派生产物旧版 + worktree 派生产物新版 → block。

    旧 guard 读 worktree: fresh(worktree) == worktree docs/governance → 放行（错过）。
    新 guard 读 snap: fresh(snap 新 MODULE.md) != snap 派生产物旧版 → block。
    """
    _git_init_with_module(tmp_path, "alpha", include_module_md=True)
    out = tmp_path / "docs/governance"
    out.mkdir(parents=True, exist_ok=True)
    # 1. 基线：生成 fresh 派生产物并 commit，使 HEAD 有正确基线
    import aggregate_modules  # noqa: E402 — _setup_aggregate_script 已 setup
    aggregate_modules.aggregate_all(tmp_path / "src/edu_cloud/modules", out)
    subprocess.run(["git", "add", "docs/governance"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "baseline derived", "-q"], cwd=tmp_path, check=True)

    # 2. 修改 alpha/MODULE.md（让重算后的 fresh 应变）
    md = tmp_path / "src/edu_cloud/modules/alpha/MODULE.md"
    new_text = md.read_text(encoding="utf-8").replace("owner: test", "owner: changed")
    md.write_text(new_text, encoding="utf-8")
    subprocess.run(
        ["git", "add", "src/edu_cloud/modules/alpha/MODULE.md"],
        cwd=tmp_path, check=True,
    )

    # 3. 在 worktree 重新跑 aggregate，让工作区派生产物与新 MODULE.md 一致（不 git add）
    aggregate_modules.aggregate_all(tmp_path / "src/edu_cloud/modules", out)

    # 此时：staged = {新 MODULE.md, 旧派生产物(HEAD 版)}
    #       worktree = {新 MODULE.md, 新派生产物}
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/alpha/MODULE.md"],
        "diff": _sample_diff("src/edu_cloud/modules/alpha/MODULE.md", 1, 1),
    }
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None, "G2-01 退化：派生产物 freshness 从 worktree 判断"
    assert result["decision"] == "block"
    assert "派生产物过期" in result["reason"]


# --- R2-NEW-01: _checkout_staged_index 非 git 目录 fail-safe ---
def test_checkout_staged_index_returns_false_in_non_git_dir(tmp_path):
    """R2-NEW-01: 非 git 目录 checkout-index 会返回 0 + 空 snapshot，helper 应显式 False。"""
    snap = tmp_path / "snap"
    snap.mkdir()
    # tmp_path 未 git init — 不在 git 工作树中
    assert g._checkout_staged_index(tmp_path, snap) is False


def test_check_blocks_when_staged_snapshot_export_fails(monkeypatch, tmp_path):
    """治理入口不能在 staged snapshot 不可用时退回读工作区。"""
    _git_init(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    monkeypatch.setattr(g, "_checkout_staged_index", lambda repo, snap: False)

    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/newmod/__init__.py"],
        "diff": _sample_diff("src/edu_cloud/modules/newmod/__init__.py", 1, 0),
    }

    result = g.check(data, MagicMock(), staged_info=staged_info)

    assert result is not None
    assert result["decision"] == "block"
    assert "staged index" in result["reason"]


def test_checkout_staged_index_returns_true_in_git_dir(tmp_path):
    """正向: git 工作树下 + 有 staged 内容 → 成功导出到 snap。"""
    _git_init(tmp_path)
    (tmp_path / "sample.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "sample.txt"], cwd=tmp_path, check=True)
    snap = tmp_path / "snap"
    snap.mkdir()
    assert g._checkout_staged_index(tmp_path, snap) is True
    assert (snap / "sample.txt").read_text(encoding="utf-8") == "hello"


# --- Kill switch ---
def test_kill_switch_disables_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("EDU_GOVERNANCE_GUARD_DISABLED", "1")
    _git_init(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/newmod/__init__.py"],
        "diff": _sample_diff("src/edu_cloud/modules/newmod/__init__.py", 1, 0),
    }
    assert g.check(data, MagicMock(), staged_info=staged_info) is None


# --- CLI git-hook mode ---
def test_git_hook_mode_blocks_new_module_without_module_md(tmp_path):
    _git_init(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_GOVERNANCE / "module_governance_guard.py"),
            "--git-hook-mode",
            "--repo",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 1
    assert "MODULE.md" in result.stderr


def test_git_hook_mode_allows_empty_index(tmp_path):
    _git_init(tmp_path)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_GOVERNANCE / "module_governance_guard.py"),
            "--git-hook-mode",
            "--repo",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
