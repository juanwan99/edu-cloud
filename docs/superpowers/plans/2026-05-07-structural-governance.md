# edu-cloud 结构纪律守护 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有元守体系中增加结构纪律守护维度，防止模块结构漂移，使新模块自动遵循标准模式。

**Architecture:** 有序注册表替代手工路由堆砌 + MODULE.md 扩展声明结构契约 + 棘轮式 hook 守护 + config 域分组。渐进迁移，不做 big bang。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Python importlib, YAML frontmatter, commit_guards hook dispatcher

---

## 现有资产盘点

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| 路由注册 | 33 个 router，6 platform + 27 module，batch for-loop 注册 | `src/edu_cloud/api/app.py:350-396` | 代码读取 |
| 模块声明 | 21 个 MODULE.md，全覆盖 | `src/edu_cloud/modules/*/MODULE.md` | aggregate_modules.py 零 debt |
| 聚合校验 | parse_module_md + 冲突检测 | `scripts/governance/aggregate_modules.py:24-84` | REQUIRED_FIELDS 8 个 |
| Hook 守护 | module_governance_guard F001/F003/F008/F009 | `~/.claude/hooks/module_governance_guard.py` | commit_guards 已注册 |
| 配置 | Settings 单类 28 字段平铺 | `src/edu_cloud/config.py:9-94` | 代码读取 |
| 模型注册 | 44 个 model import（app.py + alembic/env.py 双份） | `app.py:66-106`, `alembic/env.py:15-87` | 代码读取 |

## 增量 vs 新建论证

- 默认立场：增强已有代码
- MODULE.md 已全覆盖，扩展字段即可，无需新建声明系统
- aggregate_modules.py 已有 parse + validate，扩展 REQUIRED_FIELDS 即可
- commit_guards dispatcher 已有，加 check 函数即可，无需新 hook 文件
- app.py 的 batch for-loop 已经是半自动的，registry 是其自然演进

## 交付路径

- 目标目录：`src/edu_cloud/` + `scripts/` + `~/.claude/hooks/`
- 验证方式：pytest 全量测试 + 新增 registry 一致性测试
- 用户可见效果：新模块通过 `scripts/new-module` 创建，自动注册，hook 守护结构一致性

---

## Evidence Block

### Evidence: 路由注册方式选择有序注册表

**decision**: 有序显式注册表 + MODULE.md 一致性校验（非文件系统自动扫描）
**evidence_refs**:
  - `src/edu_cloud/modules/exam/router.py:22-23` — 一个文件两个 APIRouter（router + question_router）
  - `src/edu_cloud/modules/grading/router.py:27-28` — router 内部 include_router 子路由
  - `src/edu_cloud/api/app.py:387-396` — 当前 batch for-loop 有特定顺序
  - `tests/conftest.py:78-83` — TestClient 依赖完整 app，漏挂 = 全局 404
**Q1**: evidence_source: code-read + GPT-independent-review | evidence_state: verified
**Q2_excluded**:
  - 文件系统扫描 `modules/*/router.py`: 反证——exam 有 5 个 router 文件，grading 有 4 个，扫描无法确定哪些该注册、哪些是内部子路由
  - `__init__.py` 显式导出: 反证——当前 21 个模块的 `__init__.py` 全部为空，改造成本高且破坏现有导入模式
**impact_scope**: cross-module
**unknowns**: none
**followup_spike**: none

### Evidence: 胖文件阈值用棘轮模式

**decision**: 存量文件 max_router_loc 初始化为当前值（只降不升），新文件用 standard 350 / multi-router 600
**evidence_refs**:
  - `scan/pipeline_router.py` 1292 行, `grading/router.py` 1052 行 — 统一 400 行会让存量全部违规
  - GPT 独立审查确认当前 LOC 数据（threadId: 019e0252-60ba-7f02-bef3-ae8e772b427a）
**Q1**: evidence_source: wc-l + GPT-review | evidence_state: verified
**impact_scope**: module

---

## semantic_regression:

- ORC-001: 路由注册迁移后，所有现有 API 端点必须保持可达（route snapshot 测试锁住）
- ORC-002: MODULE.md 新字段对现有 CI 流程无破坏（aggregate_modules.py 向后兼容）
- ORC-003: config.py 分组后所有现有 `settings.XXX` 访问路径不变

---

### Task 1: Route Snapshot Test（锁住当前路由行为）

**Files:**
- Create: `tests/test_route_snapshot.py`

**目的:** 在改任何注册逻辑前，先用测试锁住当前全部 API 路径，防止迁移过程中丢路由。

- [ ] **Step 1: Write the route snapshot test**

```python
"""Route snapshot — 迁移前锁住全部 API 路径，任何路由丢失立刻 FAIL。"""
import pytest
from httpx import ASGITransport, AsyncClient

from edu_cloud.api.app import create_app

EXPECTED_PREFIXES = [
    "/api/v1/auth",
    "/api/v1/schools",
    "/api/v1/exams",
    "/api/v1/questions",
    "/api/v1/joint-exams",
    "/api/v1/grading",
    "/api/v1/marking",
    "/api/v1/analytics",
    "/api/v1/knowledge",
    "/api/v1/pipeline",
    "/api/v1/studio",
    "/api/v1/calendar",
    "/api/v1/notifications",
    "/api/v1/homework",
    "/api/v1/profile",
    "/api/v1/bank",
    "/api/v1/knowledge-tree",
    "/api/v1/scan",
    "/api/v1/cards",
    "/api/v1/conduct",
    "/api/v1/menus",
    "/api/v1/academic",
    "/api/v1/ai",
    "/api/v1/dashboard",
    "/api/v1/health",
    "/api/v1/version",
    "/api/v1/students",
    "/api/v1/teachers",
    "/api/v1/impersonate",
    "/api/v1/client-logs",
]


@pytest.fixture
def app():
    return create_app()


def _collect_prefixes(app) -> set[str]:
    prefixes = set()
    for route in app.routes:
        if hasattr(route, "path"):
            parts = route.path.strip("/").split("/")
            if len(parts) >= 3:
                prefixes.add("/" + "/".join(parts[:3]))
    return prefixes


def test_all_expected_prefixes_registered(app):
    registered = _collect_prefixes(app)
    missing = [p for p in EXPECTED_PREFIXES if p not in registered]
    assert not missing, f"Missing route prefixes after migration: {missing}"


def test_no_unexpected_prefix_removal(app):
    """Guard against accidentally removing routes during refactor."""
    registered = _collect_prefixes(app)
    assert len(registered) >= len(EXPECTED_PREFIXES), (
        f"Route count dropped: expected >= {len(EXPECTED_PREFIXES)}, got {len(registered)}"
    )
```

- [ ] **Step 2: Run test to verify it passes with current code**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/test_route_snapshot.py -v`
Expected: PASS (both tests green — current code has all these prefixes)

- [ ] **Step 3: Commit**

```bash
git add tests/test_route_snapshot.py
git commit -m "test: add route snapshot test before registry migration"
```

---

### Task 2: Router Registry Module

**Files:**
- Create: `src/edu_cloud/api/router_registry.py`
- Create: `tests/test_router_registry.py`

**目的:** 创建有序注册表，将当前 app.py 的 33 个 import + for-loop 提取为独立模块。平台路由和模块路由分开声明。

- [ ] **Step 1: Write the registry test**

```python
"""router_registry 单元测试。"""
import importlib
import pytest

from edu_cloud.api.router_registry import PLATFORM_ROUTERS, MODULE_ROUTERS, register_all


def test_all_entries_importable():
    """每个注册表条目必须能导入且有指定属性。"""
    for import_path, attr in PLATFORM_ROUTERS + MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr, None)
        assert router is not None, f"{import_path}.{attr} not found"


def test_all_routers_have_prefix():
    """每个 router 必须声明 prefix（不依赖 app 级覆盖）。"""
    for import_path, attr in PLATFORM_ROUTERS + MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr)
        assert router.prefix, f"{import_path}.{attr} has no prefix"


def test_no_duplicate_prefix():
    """不同注册表条目的 prefix 不重复（子路由由模块内部 include，不在注册表）。"""
    seen = {}
    for import_path, attr in PLATFORM_ROUTERS + MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr)
        prefix = router.prefix
        if prefix in seen:
            pytest.fail(f"Duplicate prefix '{prefix}': {seen[prefix]} vs {import_path}.{attr}")
        seen[prefix] = f"{import_path}.{attr}"


def test_register_all_attaches_routers(tmp_path):
    """register_all 应将所有 router 挂到 app。"""
    from edu_cloud.api.app import create_app
    app = create_app()
    prefixes = {r.prefix for r in app.router.routes if hasattr(r, 'prefix')}
    for import_path, attr in MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr)
        assert router.prefix in prefixes or any(
            router.prefix in str(getattr(r, 'path', '')) for r in app.routes
        ), f"{import_path}.{attr} prefix '{router.prefix}' not in app routes"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/test_router_registry.py -v`
Expected: FAIL with "No module named 'edu_cloud.api.router_registry'"

- [ ] **Step 3: Create router_registry.py**

```python
"""有序路由注册表 — 替代 app.py 中的手工 import 堆砌。

平台路由（auth/ai/dashboard 等）和模块路由分开声明。
每个条目 = (import_path, attr_name)，顺序决定注册顺序。
"""
import importlib
import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)

# (import_path, attr_name) — prefix/tags 已在各 router 文件中定义
PLATFORM_ROUTERS: list[tuple[str, str]] = [
    ("edu_cloud.api.auth", "router"),
    ("edu_cloud.api.impersonate", "router"),
    ("edu_cloud.api.client_logs", "router"),
    ("edu_cloud.api.dashboard", "router"),
    ("edu_cloud.api.ai", "router"),
    ("edu_cloud.api.compat_router", "router"),
]

MODULE_ROUTERS: list[tuple[str, str]] = [
    # school
    ("edu_cloud.modules.school.router", "router"),
    ("edu_cloud.modules.school.settings_router", "router"),
    ("edu_cloud.modules.school.assignment_router", "router"),
    ("edu_cloud.modules.school.selection_router", "router"),
    ("edu_cloud.modules.school.capability_router", "router"),
    ("edu_cloud.modules.school.audit_router", "router"),
    # exam
    ("edu_cloud.modules.exam.router", "router"),
    ("edu_cloud.modules.exam.router", "question_router"),
    ("edu_cloud.modules.exam.joint_exam_router", "router"),
    ("edu_cloud.modules.exam.results_router", "router"),
    ("edu_cloud.modules.exam.workspace_router", "router"),
    ("edu_cloud.modules.exam.llm_config_router", "router"),
    # student
    ("edu_cloud.modules.student.router", "router"),
    ("edu_cloud.modules.student.teacher_router", "router"),
    # card
    ("edu_cloud.modules.card.router", "router"),
    ("edu_cloud.modules.card.template_router", "router"),
    # scan
    ("edu_cloud.modules.scan.router", "router"),
    ("edu_cloud.modules.scan.pipeline_router", "router"),
    # grading
    ("edu_cloud.modules.grading.router", "router"),
    ("edu_cloud.modules.grading.assignment_router", "router"),
    ("edu_cloud.modules.grading.quality_router", "router"),
    # marking
    ("edu_cloud.modules.marking.router", "router"),
    # analytics
    ("edu_cloud.modules.analytics.router", "router"),
    # knowledge
    ("edu_cloud.modules.knowledge.router", "router"),
    # knowledge_tree
    ("edu_cloud.modules.knowledge_tree.router", "router"),
    # pipeline
    ("edu_cloud.modules.pipeline.router", "router"),
    # studio
    ("edu_cloud.modules.studio.router", "router"),
    # calendar
    ("edu_cloud.modules.calendar.router", "router"),
    # notifications (platform-level but module-scoped)
    ("edu_cloud.api.notifications_api", "router"),
    # homework
    ("edu_cloud.modules.homework.router", "router"),
    # profile
    ("edu_cloud.modules.profile.router", "router"),
    # bank
    ("edu_cloud.modules.bank.router", "router"),
    # conduct
    ("edu_cloud.modules.conduct.parent_router", "router"),
    ("edu_cloud.modules.conduct.admin_router", "router"),
    ("edu_cloud.modules.conduct.notification_router", "router"),
    # menu
    ("edu_cloud.modules.menu.router", "router"),
    # academic
    ("edu_cloud.modules.academic.router", "router"),
]


def register_all(app: FastAPI) -> None:
    for import_path, attr in PLATFORM_ROUTERS + MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr)
        app.include_router(router)
        logger.debug("Registered %s.%s → %s", import_path, attr, router.prefix)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/test_router_registry.py -v`
Expected: PASS (all 4 tests green)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/router_registry.py tests/test_router_registry.py
git commit -m "feat: add router registry module (before app.py migration)"
```

---

### Task 3: Migrate app.py to Use Registry

**Files:**
- Modify: `src/edu_cloud/api/app.py:325-396` (delete 70 lines, add 3 lines)

**目的:** 将 app.py 的 37 行 import + 10 行 for-loop 替换为 registry 的一行调用。

- [ ] **Step 1: Replace router registration block in app.py**

删除 `app.py` lines 350-396 的全部 module router imports 和 for-loop，替换为：

```python
    # ── Module routers (from registry) ──
    from edu_cloud.api.router_registry import register_all
    register_all(app)
```

保留 lines 326-347 的 6 个 platform router（auth, impersonate, client_logs, dashboard, ai, compat）的手工注册不变。

**注意：** platform routers 也在 registry 里声明了，但 app.py 中保留它们的手工注册是为了可读性。register_all 需要跳过已注册的 platform routers，或者我们把 platform routers 也完全交给 registry。

**决定（简化）：** 全部交给 registry，删除 app.py 中所有手工 include_router。替换后 app.py 的路由注册段变为：

```python
    # ── Route registration (all routers from registry) ──
    from edu_cloud.api.router_registry import register_all
    register_all(app)

    # ── Static files ──
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
```

- [ ] **Step 2: Run route snapshot test**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/test_route_snapshot.py tests/test_router_registry.py -v`
Expected: PASS (route snapshot confirms no routes lost)

- [ ] **Step 3: Run full backend test suite**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest --tb=short -q --ignore=tests/governance -x 2>&1 | tail -20`
Expected: 2246 passed (same baseline, no regression)

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/api/app.py
git commit -m "refactor: migrate route registration to router_registry"
```

---

### Task 4: MODULE.md Schema Extension

**Files:**
- Modify: `scripts/governance/aggregate_modules.py` (add new fields + validation)
- Modify: `tests/governance/test_aggregate_modules.py` (add new field tests)

**目的:** 扩展 MODULE.md schema，增加 structure_pattern、max_router_loc、routers 字段。

- [ ] **Step 1: Write tests for new schema fields**

在 `tests/governance/test_aggregate_modules.py` 中添加：

```python
def test_structure_pattern_valid_values(tmp_path):
    """structure_pattern 只接受 standard / multi-router / service-only。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        "---\nname: t\nstatus: active\nowner: test\nlayer: business\n"
        "owns_tables: []\nowns_routes: []\n"
        "structure_pattern: invalid\nmax_router_loc: 400\nrouters: []\n"
        "exposes:\n  services: []\n  events: []\n"
        "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n---\n"
    )
    with pytest.raises(ModuleGovernanceError, match="structure_pattern"):
        parse_module_md(md)


def test_structure_pattern_standard(tmp_path):
    md = tmp_path / "MODULE.md"
    md.write_text(
        "---\nname: t\nstatus: active\nowner: test\nlayer: business\n"
        "owns_tables: []\nowns_routes: []\n"
        "structure_pattern: standard\nmax_router_loc: 350\nrouters: [router.py]\n"
        "exposes:\n  services: []\n  events: []\n"
        "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n---\n"
    )
    meta = parse_module_md(md)
    assert meta["structure_pattern"] == "standard"
    assert meta["max_router_loc"] == 350
    assert meta["routers"] == ["router.py"]


def test_max_router_loc_must_be_positive(tmp_path):
    md = tmp_path / "MODULE.md"
    md.write_text(
        "---\nname: t\nstatus: active\nowner: test\nlayer: business\n"
        "owns_tables: []\nowns_routes: []\n"
        "structure_pattern: standard\nmax_router_loc: -1\nrouters: []\n"
        "exposes:\n  services: []\n  events: []\n"
        "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n---\n"
    )
    with pytest.raises(ModuleGovernanceError, match="max_router_loc"):
        parse_module_md(md)


def test_backward_compat_old_module_md(tmp_path):
    """旧格式（无新字段）仍然通过校验——向后兼容。"""
    md = tmp_path / "MODULE.md"
    md.write_text(
        "---\nname: t\nstatus: active\nowner: test\nlayer: business\n"
        "owns_tables: []\nowns_routes: []\n"
        "exposes:\n  services: []\n  events: []\n"
        "depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n---\n"
    )
    meta = parse_module_md(md)
    assert "structure_pattern" not in meta  # optional, no default injected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/governance/test_aggregate_modules.py -v -k "structure_pattern or max_router_loc or backward_compat"`
Expected: FAIL (structure_pattern validation not yet implemented)

- [ ] **Step 3: Update aggregate_modules.py**

在 `scripts/governance/aggregate_modules.py` 中添加：

```python
VALID_STRUCTURE_PATTERN = {"standard", "multi-router", "service-only"}

# 在 parse_module_md 函数中，NESTED_REQUIRED 校验之后添加：

    # ── 结构治理字段（可选，向后兼容） ──
    if "structure_pattern" in meta:
        if meta["structure_pattern"] not in VALID_STRUCTURE_PATTERN:
            raise ModuleGovernanceError(
                f"{md_path}: invalid structure_pattern '{meta['structure_pattern']}' "
                f"(expected one of {VALID_STRUCTURE_PATTERN})"
            )
    if "max_router_loc" in meta:
        if not isinstance(meta["max_router_loc"], int) or meta["max_router_loc"] <= 0:
            raise ModuleGovernanceError(
                f"{md_path}: max_router_loc must be a positive integer"
            )
    if "routers" in meta:
        if not isinstance(meta["routers"], list):
            raise ModuleGovernanceError(
                f"{md_path}: routers must be a list"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/governance/test_aggregate_modules.py -v -k "structure_pattern or max_router_loc or backward_compat"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/governance/aggregate_modules.py tests/governance/test_aggregate_modules.py
git commit -m "feat: extend MODULE.md schema with structure_pattern, max_router_loc, routers"
```

---

### Task 5: Update All 21 MODULE.md Files

**Files:**
- Modify: `src/edu_cloud/modules/*/MODULE.md` (all 21 files)

**目的:** 为每个模块填入实际的 structure_pattern、max_router_loc（棘轮基准）、routers 列表。

- [ ] **Step 1: 按以下清单更新每个 MODULE.md**

在每个 MODULE.md 的 YAML frontmatter 中，`owns_routes:` 之后添加三个新字段。

**standard 模式（仅一个主 router，单 prefix）：**

| 模块 | structure_pattern | max_router_loc | routers |
|------|------------------|----------------|---------|
| knowledge | standard | 100 | [router.py] |
| knowledge_tree | standard | 200 | [router.py] |
| pipeline | standard | 50 | [router.py] |
| studio | standard | 250 | [router.py] |
| calendar | standard | 100 | [router.py] |
| homework | standard | 300 | [router.py] |
| profile | standard | 200 | [router.py] |
| bank | standard | 200 | [router.py] |
| menu | standard | 50 | [router.py] |

**multi-router 模式（多个 router 文件或多 prefix）：**

| 模块 | structure_pattern | max_router_loc | routers |
|------|------------------|----------------|---------|
| school | multi-router | 150 | [router.py, settings_router.py, assignment_router.py, selection_router.py, capability_router.py, audit_router.py] |
| exam | multi-router | 500 | [router.py, joint_exam_router.py, results_router.py, workspace_router.py, llm_config_router.py] |
| student | multi-router | 600 | [router.py, teacher_router.py] |
| card | multi-router | 850 | [router.py, template_router.py, card_template_router.py, card_export_router.py] |
| scan | multi-router | 1300 | [router.py, pipeline_router.py] |
| grading | multi-router | 1100 | [router.py, assignment_router.py, quality_router.py, grading_review_router.py] |
| marking | multi-router | 600 | [router.py] |
| analytics | multi-router | 650 | [router.py, analytics_report_router.py] |
| conduct | multi-router | 650 | [admin_router.py, parent_router.py, notification_router.py] |
| academic | multi-router | 300 | [router.py] |

**service-only 模式（无 router）：**

| 模块 | structure_pattern | max_router_loc | routers |
|------|------------------|----------------|---------|
| adaptive | service-only | 0 | [] |
| research | service-only | 0 | [] |

注意：max_router_loc 设为当前最大 router 文件的行数（向上取整到 50），作为棘轮基准。

- [ ] **Step 2: 验证所有 MODULE.md 校验通过**

Run: `cd /home/ops/projects/edu-cloud && python scripts/governance/aggregate_modules.py`
Expected: 0 conflicts, 0 errors, 21 modules parsed

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/modules/*/MODULE.md
git commit -m "feat: populate structure_pattern, max_router_loc, routers in all MODULE.md"
```

---

### Task 6: Scaffold Script

**Files:**
- Create: `scripts/new-module`

**目的:** 一键生成符合标准的新模块目录结构。

- [ ] **Step 1: Create the scaffold script**

```bash
#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: scripts/new-module <name> [--pattern standard|multi-router|service-only]"
    echo "Creates a new module under src/edu_cloud/modules/<name>/"
    exit 1
}

[[ $# -lt 1 ]] && usage
NAME="$1"
PATTERN="${3:-standard}"

if [[ "$2" == "--pattern" ]] 2>/dev/null; then
    PATTERN="$3"
elif [[ $# -eq 1 ]]; then
    PATTERN="standard"
fi

MODULE_DIR="src/edu_cloud/modules/$NAME"

if [[ -d "$MODULE_DIR" ]]; then
    echo "ERROR: $MODULE_DIR already exists"
    exit 1
fi

case "$PATTERN" in
    standard|multi-router|service-only) ;;
    *) echo "ERROR: invalid pattern '$PATTERN' (standard|multi-router|service-only)"; exit 1 ;;
esac

mkdir -p "$MODULE_DIR"
touch "$MODULE_DIR/__init__.py"

# MODULE.md
cat > "$MODULE_DIR/MODULE.md" << YAML
---
name: $NAME
status: active
owner: backend
layer: business
owns_tables: []
owns_routes: []
structure_pattern: $PATTERN
max_router_loc: 350
routers: $(if [[ "$PATTERN" == "service-only" ]]; then echo "[]"; else echo "[router.py]"; fi)
exposes:
  services: []
  events: []
depends_on:
  modules: []
  services: []
  ai_tools: []
created: $(date +%Y-%m-%d)
last_reviewed: $(date +%Y-%m-%d)
design_docs: []
---
# $NAME

## 职责

TODO: describe module responsibility.
YAML

# models.py
cat > "$MODULE_DIR/models.py" << 'PY'
"""Database models."""
PY

# service.py
cat > "$MODULE_DIR/service.py" << 'PY'
"""Business logic."""
import logging

logger = logging.getLogger(__name__)
PY

# router.py (skip for service-only)
if [[ "$PATTERN" != "service-only" ]]; then
cat > "$MODULE_DIR/router.py" << PY
"""REST API routes."""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/$NAME", tags=["$NAME"])
PY
fi

# test file
mkdir -p "tests/test_modules/test_$NAME"
touch "tests/test_modules/test_$NAME/__init__.py"
cat > "tests/test_modules/test_$NAME/test_${NAME}_service.py" << 'PY'
"""Service unit tests."""
PY

echo "Created module: $MODULE_DIR (pattern: $PATTERN)"
echo ""
echo "Next steps:"
echo "  1. Edit MODULE.md: fill owns_tables, owns_routes, depends_on"
echo "  2. Add router entry to src/edu_cloud/api/router_registry.py"
echo "  3. Add model imports to alembic/env.py (if new tables)"
echo "  4. Run: python scripts/governance/aggregate_modules.py"
```

- [ ] **Step 2: Make executable**

Run: `chmod +x /home/ops/projects/edu-cloud/scripts/new-module`

- [ ] **Step 3: Test it**

Run: `cd /home/ops/projects/edu-cloud && scripts/new-module test_scaffold --pattern standard && ls -la src/edu_cloud/modules/test_scaffold/ && cat src/edu_cloud/modules/test_scaffold/MODULE.md && rm -rf src/edu_cloud/modules/test_scaffold tests/test_modules/test_test_scaffold`
Expected: 目录结构完整，MODULE.md 格式正确，清理后无残留

- [ ] **Step 4: Commit**

```bash
git add scripts/new-module
git commit -m "feat: add new-module scaffold script"
```

---

### Task 7: Config Domain Grouping

**Files:**
- Modify: `src/edu_cloud/config.py`
- Create: `tests/test_config_compat.py`

**目的:** 将 Settings 平铺的 28 字段分组为域子类，但保持 `settings.XXX` 访问路径不变（ORC-003）。

- [ ] **Step 1: Write compatibility test**

```python
"""确保 config 重构后所有现有 settings.XXX 访问路径不变。"""
from edu_cloud.config import settings


def test_all_existing_attributes():
    """ORC-003: 所有现有字段仍可通过 settings.XXX 访问。"""
    attrs = [
        "DATABASE_URL", "REDIS_URL", "SECRET_KEY", "ENCRYPTION_KEY",
        "SEED_DEFAULT_PASSWORD", "ACCESS_TOKEN_EXPIRE_MINUTES", "ALGORITHM",
        "UPLOAD_DIR", "STORAGE_ROOT", "MAX_UPLOAD_SIZE_MB",
        "LOG_LEVEL", "LOG_DIR", "LOG_FILE_LEVEL",
        "CORS_ORIGINS",
        "LLM_API_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_SLOT",
        "LLM_TIMEOUT", "LLM_MAX_RETRIES",
        "GEMINI_API_KEY", "GEMINI_MODEL",
        "DEEPSEEK_API_KEY",
        "VERTEX_AI_PROJECT", "VERTEX_AI_LOCATION",
        "GRADING_BATCH_SIZE",
        "TIER_CONTEXT_THRESHOLDS", "MODEL_ROUTER_ADVANCED_KEYWORDS",
        "AI_SESSION_TTL",
        "KNOWLEDGE_BASE_DIR", "KNOWLEDGE_ENABLED", "KNOWLEDGE_DB_PATH",
        "KNOWLEDGE_DRAFT_VISIBLE",
        "PAPER_SKILL_URL",
    ]
    for attr in attrs:
        assert hasattr(settings, attr), f"settings.{attr} missing after refactor"
```

- [ ] **Step 2: Run test to verify it passes (before refactor)**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/test_config_compat.py -v`
Expected: PASS

- [ ] **Step 3: Refactor config.py with domain grouping**

```python
import logging
import warnings

from pydantic_settings import BaseSettings

_logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ── Database ──
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Security ──
    SECRET_KEY: str = "change-me"
    ENCRYPTION_KEY: str = "change-me-in-production"
    SEED_DEFAULT_PASSWORD: str = "change-me-seed-password"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    # ── Storage ──
    UPLOAD_DIR: str = "./uploads"
    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 10

    # ── Logging ──
    LOG_LEVEL: str = "DEBUG"
    LOG_DIR: str = "./logs"
    LOG_FILE_LEVEL: str = "INFO"

    # ── CORS ──
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # ── LLM (shared grading + agent) ──
    LLM_API_URL: str = "http://localhost:8100"
    LLM_API_KEY: str = "not-needed-for-local-proxy"
    LLM_MODEL: str = "gemini-3-pro-preview"
    LLM_SLOT: str = "grading-vision"
    LLM_TIMEOUT: int = 180
    LLM_MAX_RETRIES: int = 3

    # ── Gemini Official ──
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3-flash-preview"

    # ── DeepSeek ──
    DEEPSEEK_API_KEY: str = ""

    # ── Vertex AI ──
    VERTEX_AI_PROJECT: str = ""
    VERTEX_AI_LOCATION: str = "global"

    # ── Grading ──
    GRADING_BATCH_SIZE: int = 40

    # ── AI Agent ──
    TIER_CONTEXT_THRESHOLDS: list[int] = [100_000, 30_000]
    MODEL_ROUTER_ADVANCED_KEYWORDS: list[str] | None = None
    AI_SESSION_TTL: int = 7200

    # ── Knowledge ──
    KNOWLEDGE_BASE_DIR: str = "./edu-knowledge-base/subjects/biology_senior"
    KNOWLEDGE_ENABLED: bool = True
    KNOWLEDGE_DB_PATH: str = "./edu-knowledge-base/knowledge.db"
    KNOWLEDGE_DRAFT_VISIBLE: bool = True

    # ── Paper Skill ──
    PAPER_SKILL_URL: str = "http://localhost:9103"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.SECRET_KEY == "change-me":
            warnings.warn(
                "SECRET_KEY is using default value 'change-me'. "
                "Set SECRET_KEY in .env for production!",
                stacklevel=2,
            )
            _logger.warning("SECRET_KEY is using insecure default value")

    model_config = {"env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
```

注意：这一步只加注释分组，不改字段名或嵌套子类。原因：嵌套子类会破坏 `settings.XXX` 访问路径（ORC-003），需要 `model_validator` 做平铺兼容，复杂度不值得。注释分组已经解决了可读性问题。

- [ ] **Step 4: Run compatibility test + full suite**

Run: `cd /home/ops/projects/edu-cloud && python -m pytest tests/test_config_compat.py -v && python -m pytest --tb=short -q --ignore=tests/governance -x 2>&1 | tail -5`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/config.py tests/test_config_compat.py
git commit -m "refactor: organize config.py fields by domain with section comments"
```

---

### Task 8: Hook Guards — Fat File + App.py Protection

**Files:**
- Modify: `~/.claude/hooks/commit_guards.py` (add 2 check functions)
- Create: `~/.claude/hooks/structure_guard.py` (implementation)

**目的:** 在 commit_guards dispatcher 中加入结构守护检查。

- [ ] **Step 1: Create structure_guard.py**

```python
"""结构纪律守护 — commit_guards 子检查。

检查 1 (fat_file_check): router/page 文件超过 MODULE.md 声明的 max_router_loc → ask
检查 2 (app_py_route_guard): app.py 新增 include_router → block
"""
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hook_lib import SessionState  # noqa: E402

ENFORCES = ["WF-021", "WF-022"]

PROJECT_DIR = Path.home() / "projects" / "edu-cloud"
MODULES_DIR = PROJECT_DIR / "src" / "edu_cloud" / "modules"


def _parse_max_loc(module_dir: Path) -> int | None:
    md = module_dir / "MODULE.md"
    if not md.exists():
        return None
    text = md.read_text(encoding="utf-8")
    m = re.search(r"max_router_loc:\s*(\d+)", text)
    return int(m.group(1)) if m else None


def fat_file_check(data: dict, session_state) -> dict | None:
    """ask 如果 staged router 文件超过模块声明的 max_router_loc。"""
    staged = data.get("staged_info", {}).get("files", [])
    if not staged:
        return None

    violations = []
    for f in staged:
        path = Path(f)
        if not str(path).startswith("src/edu_cloud/modules/"):
            continue
        if "router" not in path.name:
            continue
        parts = path.parts
        # src / edu_cloud / modules / <module_name> / <file>
        if len(parts) < 5:
            continue
        module_name = parts[3]
        module_dir = MODULES_DIR / module_name
        max_loc = _parse_max_loc(module_dir)
        if max_loc is None or max_loc <= 0:
            continue
        full_path = PROJECT_DIR / path
        if full_path.exists():
            loc = sum(1 for _ in full_path.open(encoding="utf-8", errors="ignore"))
            if loc > max_loc:
                violations.append(f"{path} ({loc} 行, 上限 {max_loc})")

    if violations:
        return {
            "decision": "ask",
            "reason": (
                f"[structure-guard] 胖路由器预警:\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n建议拆分为子路由器。继续提交？"
            ),
        }
    return None


def app_py_route_guard(data: dict, session_state) -> dict | None:
    """block 如果 app.py 的 diff 包含 include_router。"""
    diff = data.get("staged_info", {}).get("diff", "")
    if not diff:
        return None

    in_app_py = False
    for line in diff.split("\n"):
        if line.startswith("diff --git") and "api/app.py" in line:
            in_app_py = True
            continue
        if line.startswith("diff --git"):
            in_app_py = False
        if in_app_py and line.startswith("+") and "include_router" in line:
            if not line.startswith("+++"):
                return {
                    "decision": "block",
                    "reason": (
                        "[structure-guard] 禁止在 app.py 中手工追加 include_router。\n"
                        "请将路由条目添加到 src/edu_cloud/api/router_registry.py 的 MODULE_ROUTERS 列表。"
                    ),
                }
    return None
```

- [ ] **Step 2: Register in commit_guards.py**

在 `~/.claude/hooks/commit_guards.py` 的 CHECKS 列表中添加：

```python
import structure_guard  # noqa: E402

# 在 CHECKS 列表末尾添加：
    ("fat_file_check", structure_guard.fat_file_check),
    ("app_py_route_guard", structure_guard.app_py_route_guard),
```

- [ ] **Step 3: Test the guards manually**

Run: `echo '{"tool_name":"Bash","input":{"command":"git commit -m test"},"staged_info":{"files":["src/edu_cloud/api/app.py"],"diff":"diff --git a/src/edu_cloud/api/app.py\n+    app.include_router(new_router)"}}' | python3 ~/.claude/hooks/commit_guards.py`
Expected: `{"decision": "block", "reason": "...禁止在 app.py 中手工追加 include_router..."}`

- [ ] **Step 4: Update governance.yaml with new clauses**

在 `~/.claude/control/governance.yaml` 中添加：

```yaml
WF-021:
  name: fat-router-warning
  description: Router/page files exceeding MODULE.md max_router_loc trigger ask
  strength: ask
  consumer: structure_guard.fat_file_check
  domain: workflow

WF-022:
  name: app-py-route-guard
  description: Block direct include_router in app.py (must use router_registry)
  strength: hard_block
  consumer: structure_guard.app_py_route_guard
  domain: workflow
```

- [ ] **Step 5: Commit**

```bash
git -C ~/.claude add hooks/structure_guard.py hooks/commit_guards.py control/governance.yaml
git -C ~/.claude commit -m "feat: add structural governance guards (WF-021, WF-022)"
```

---

### Task 9: Guardian Collector Extension

**Files:**
- Modify: `~/.claude/guardian/collector.py` (add collect_structure function)

**目的:** Guardian 每 3 分钟扫描时增加结构一致性检测。

- [ ] **Step 1: Add collect_structure to collector.py**

在 `collector.py` 的 `collect_all()` 函数中，在 `collect_governance()` 调用后添加：

```python
def collect_structure(project_dir: Path) -> list[dict]:
    """检测模块结构漂移。"""
    issues = []
    modules_dir = project_dir / "src" / "edu_cloud" / "modules"
    registry_path = project_dir / "src" / "edu_cloud" / "api" / "router_registry.py"

    if not modules_dir.exists():
        return issues

    # 读取 registry 中声明的 import paths
    registry_modules = set()
    if registry_path.exists():
        text = registry_path.read_text(encoding="utf-8")
        for m in re.findall(r'"edu_cloud\.modules\.(\w+)\.\w+"', text):
            registry_modules.add(m)

    for mod_dir in sorted(modules_dir.iterdir()):
        if not mod_dir.is_dir() or mod_dir.name.startswith("_"):
            continue
        module_md = mod_dir / "MODULE.md"
        has_router = any(f.name.endswith("_router.py") or f.name == "router.py" for f in mod_dir.iterdir())

        # 检测 1: 有 router 文件但不在 registry 中
        if has_router and mod_dir.name not in registry_modules:
            issues.append({
                "issue_code": "ORPHAN_MODULE_ROUTER",
                "severity": "yellow",
                "message": f"模块 {mod_dir.name} 有 router 文件但未在 router_registry.py 中注册",
            })

        # 检测 2: MODULE.md 声明 service-only 但有 router 文件
        if module_md.exists():
            text = module_md.read_text(encoding="utf-8")
            pattern_match = re.search(r"structure_pattern:\s*(\S+)", text)
            if pattern_match and pattern_match.group(1) == "service-only" and has_router:
                issues.append({
                    "issue_code": "STRUCTURE_PATTERN_VIOLATION",
                    "severity": "yellow",
                    "message": f"模块 {mod_dir.name} 声明 service-only 但存在 router 文件",
                })

            # 检测 3: router 文件超过 max_router_loc
            loc_match = re.search(r"max_router_loc:\s*(\d+)", text)
            if loc_match:
                max_loc = int(loc_match.group(1))
                for f in mod_dir.iterdir():
                    if ("router" in f.name and f.suffix == ".py"):
                        actual = sum(1 for _ in f.open(encoding="utf-8", errors="ignore"))
                        if actual > max_loc:
                            issues.append({
                                "issue_code": "FAT_ROUTER",
                                "severity": "yellow",
                                "message": f"{mod_dir.name}/{f.name}: {actual} 行 > max_router_loc {max_loc}",
                            })

    return issues
```

- [ ] **Step 2: Wire into collect_all**

在 `collect_all()` 中添加调用并将 issues 合入 snapshot：

```python
    # 在 collect_governance() 之后
    structure_issues = collect_structure(project_dir)
    for issue in structure_issues:
        all_issues.append(issue)
```

- [ ] **Step 3: Test manually**

Run: `cd ~/.claude/guardian && python3 -c "from collector import collect_structure; from pathlib import Path; print(collect_structure(Path.home() / 'projects' / 'edu-cloud'))"`
Expected: 输出当前检测到的 issues 列表（可能有 FAT_ROUTER 因为存量文件）

- [ ] **Step 4: Commit**

```bash
git -C ~/.claude add guardian/collector.py
git -C ~/.claude commit -m "feat: guardian collect_structure — orphan module, pattern violation, fat router detection"
```

---

## 验收清单

完成所有 9 个 Task 后，执行以下验证：

1. **Route snapshot**: `python -m pytest tests/test_route_snapshot.py -v` → PASS
2. **Registry tests**: `python -m pytest tests/test_router_registry.py -v` → PASS
3. **Config compat**: `python -m pytest tests/test_config_compat.py -v` → PASS
4. **MODULE.md aggregate**: `python scripts/governance/aggregate_modules.py` → 0 errors
5. **Full backend**: `python -m pytest --tb=short -q --ignore=tests/governance -x` → baseline ± 0
6. **Hook test**: echo 测试 app_py_route_guard → block
7. **Guardian**: `python3 ~/.claude/guardian/collector.py` → snapshot 包含 structure issues
8. **Scaffold**: `scripts/new-module test_verify --pattern standard` → 目录结构正确 → 删除

## Contract Pack

### invariants
1. **INV-001**: 所有现有 API 端点在迁移后保持可达 — verification: tests/test_route_snapshot.py
2. **INV-002**: MODULE.md 新字段向后兼容（旧格式仍通过校验） — verification: test_backward_compat_old_module_md
3. **INV-003**: settings.XXX 访问路径不变 — verification: tests/test_config_compat.py

### counter_examples
1. **CE-001**: 删除 router_registry 中的一个条目 → test_all_expected_prefixes_registered FAIL; mitigation: route snapshot test
2. **CE-002**: 在 app.py 手工加 include_router → app_py_route_guard BLOCK; mitigation: hook enforcement

### risk_modules
- `src/edu_cloud/api/app.py` — 迁移改动最大的文件
- `src/edu_cloud/api/router_registry.py` — 新建的注册表
- `~/.claude/hooks/commit_guards.py` — 新增检查函数

### test_debt
- 无。所有 Task 都包含对应测试。
