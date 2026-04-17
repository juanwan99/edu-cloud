---
type: plan
topic: conduct-roadmap-batch1
created: 2026-04-14 06:39:01
status: draft
T-level: T3
design: docs/plans/2026-04-14-conduct-roadmap-design.md
gates: docs/plans/2026-04-14-conduct-roadmap-batch1-gates.json
state: docs/plans/2026-04-14-conduct-roadmap-batch1-state.json
---

# 德育板块治理最小集（批次 1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 本 plan 按 project CLAUDE.md T3 流程执行：每 Task 独立 commit → Gate 2 Code Review PASS → design.md 标 [实现完成]。

**Goal:** 消除德育板块 API 契约漂移（T2）+ 菜单入口治理债（T1+T3）+ 模块治理债（T4）+ 文档事实漂移（T5），为批次 2/3 扫清依赖。

**Architecture:** 5 个独立 Task 分两层——无依赖层（T1, T2, T4, T5）+ 依赖层（T3 依赖 T1）。执行顺序 T5 → T4 → T1 → T2 → T3，风险递增、test 增量递增。T1-T3 含 behavior_change（已 L017 批准），需 red 回归测试 + 审查清单。T4 纯 governance（非 behavior_change）。T5 纯文档。

**Tech Stack:** 后端 FastAPI + pydantic v2 + SQLAlchemy 2.0 async / 前端 Vue 3.5 + Naive UI + Pinia + Vue Router / 测试 pytest + pytest-asyncio + Vitest + @vue/test-utils + happy-dom

**基线（本会话 verified 2026-04-14）:**
- conduct 后端: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q` → 118 passed, 237.52s, exit 0
- services: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q` → 15 passed, 10s, exit 0
- frontend conduct 3 件套: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/sidebarConfig.conduct.test.js src/__tests__/AppSidebar.test.js src/pages/parent/__tests__/ParentRules.spec.js` → 13 passed (未在本会话跑)

**退出条件:**
- 5 Tasks 全部 completed，conduct 后端 ≥ 129 passed（R1-F006 入口级补齐后），frontend conduct ≥ 29 passed（R1-F006/F007 新增 1 入口级 + 1 治理）
- Gate 1 Plan Review PASS（本 plan commit 后触发）
- Gate 2 Code Review PASS（全部 Task commit 后触发）
- design.md §10 标 `[实现完成]`，CLAUDE.md 迁移到已完成设计段

**纪律约束（每 commit 前）:**
- `git reset HEAD` → 精确 `git add <文件列表>` → `git diff --cached --name-only` 验证 staged 只有本 Task 文件
- 禁止侵占跨 session 未 commit 文件（alembic / haofenshu-phase1 / migration-gate-repair 等）
- scope_guard.py 会校验 commit 文件范围，越界 block

---

## 文件结构（Task → Files 映射）

| Task | Create | Modify | Test |
|---|---|---|---|
| T5 文档数字修正 | — | `C:/Users/Administrator/edu-cloud/CLAUDE.md` + `docs/plans/2026-04-13-conduct-next-phase-handoff.md` | — |
| T4 conduct MODULE.md | `src/edu_cloud/modules/conduct/MODULE.md` | — | `tests/test_conduct/test_module_governance.py`（新） |
| T1 lesson_prep 权限回收 | — | `src/edu_cloud/core/permissions.py:240` + `frontend/src/config/permissions.js:59` | `tests/test_conduct/test_permissions.py` + `frontend/src/__tests__/permissions.lesson_prep.test.js`（新） |
| T2 AddPointsRequest rename | — | `src/edu_cloud/modules/conduct/schemas.py:2,38` + `admin_router.py:115,137`（`record_date=data.date` → `record_date=data.record_date`，R1-F001 修复） + `frontend/src/api/conduct.js` + `frontend/src/pages/conduct/ConductPoints.vue`。**admin_service.py 已 rename 为 `record_date` 参数（L254/271），无需改动** | `tests/test_conduct/test_admin_crud_api.py`（新增 3 测试，R1-F002 入口级 POST+readback） |
| T3 sidebar 按 permissions 派生 | — | `frontend/src/config/sidebarConfig.js`（重构 CONDUCT 部分） | `frontend/src/__tests__/sidebarConfig.conduct.test.js`（矩阵扩展） |

---

## Task 1: T5 文档数字修正（热身，2 commits）

**Files:**
- Modify: `C:/Users/Administrator/edu-cloud/CLAUDE.md`（德育条目 120 → 118）
- Modify: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-13-conduct-next-phase-handoff.md:151`（120 → 118）

**性质:** 纯文档修正，非 behavior_change。T1 级别，无测试契约要求。

**依赖:** 无

### Steps

- [ ] **Step 1.0: state.json 本 Task 置 in_progress（R1-F004，每 Task 必做）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '1':
        task['status'] = 'in_progress'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 1 -> in_progress')
"
```
（state.json 由 Planner 在 Gate 1 PASS 后 Step 0 创建，tasks 全 pending；此处仅 pending→in_progress。edit 未独立 commit，staged 后与 Step 1.6 commit 合并。）

- [ ] **Step 1.1: 预验证 baseline 仍是 118**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q --tb=no 2>&1 | tail -3
```
Expected: 最后一行 `118 passed in ...s, 1 warning`（退出码 0）。若不是 118，暂停本 plan 先排查。

- [ ] **Step 1.2: 定位 edu-cloud CLAUDE.md 的 120 位置**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && grep -n "120 conduct tests\|108 + 12" CLAUDE.md
```
Expected: 1-2 行匹配，位于"德育模块（conduct）[实现完成]"条目中。

- [ ] **Step 1.3: Edit edu-cloud CLAUDE.md**

使用 Edit 工具：
- old: `120 conduct tests（R2 基线 108 + 12 新增）`
- new: `118 conduct tests（R2 基线 108 + 10 新增）`

若该字串有 `replace_all` 场景（出现 ≥2 次），分次 Edit 或带更多上下文。

- [ ] **Step 1.4: Edit next-phase handoff L151**

使用 Edit 工具：
- 文件：`docs/plans/2026-04-13-conduct-next-phase-handoff.md`
- old: `# 期望: 120 passed (R3 收尾基线)`
- new: `# 期望: 118 passed (R3 收尾基线)`

- [ ] **Step 1.5: 回扫确认无残留 120 引用**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && grep -rn "120 passed\|108 + 12\|108+12" CLAUDE.md docs/plans/2026-04-*-conduct-* 2>/dev/null
```
Expected: 无输出（或仅匹配明确说明为历史的段落）。

- [ ] **Step 1.5a: state.json 本 Task 置 completed（R1-F004，每 Task commit 前必做）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '1':
        task['status'] = 'completed'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 1 -> completed')
"
```

- [ ] **Step 1.6: Commit**

```bash
cd C:/Users/Administrator/edu-cloud && git reset HEAD >/dev/null 2>&1 && \
  git add CLAUDE.md docs/plans/2026-04-13-conduct-next-phase-handoff.md docs/plans/2026-04-14-conduct-roadmap-batch1-state.json && \
  git diff --cached --name-only
# 验证 staged 3 个文件（2 doc + state.json）
```

再 commit：
```bash
git commit -m "$(cat <<'EOF'
docs(conduct): T5 修正 R3 测试计数漂移 120→118

CLAUDE.md 德育条目「120 conduct tests（108 + 12）」→「118（108 + 10）」；
next-phase handoff L151「期望: 120 passed」→「118」。
R3 handoff L171 原本就是 118，无需改。实测 118 passed 237.52s。

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

Expected: HEAD commit message 含 "T5 修正 R3 测试计数漂移"。

**审查清单:**
- ✓ CLAUDE.md 搜 "120 conduct" 无匹配
- ✓ next-phase handoff L151 是 "期望: 118 passed"
- ✗ R3 handoff (2026-04-12-conduct-module-review-handoff-batch1-r3.md) **不应改动**（原本就是 118）
- 关键行为：任何后续 planner 读 handoff 得到的基线数字与实跑一致

**边界条件:** N/A（纯文本替换）

**测试契约:** N/A（非 behavior_change，无代码变更）

---

## Task 2: T4 conduct MODULE.md 补全（governance，2 commits）

**Files:**
- Create: `src/edu_cloud/modules/conduct/MODULE.md`
- Test: `tests/test_conduct/test_module_governance.py`（新建，1 测试）

**性质:** 治理债添加，非 behavior_change。T2 级别。

**依赖:** 无。与 T1/T2/T3 平行。

### Steps

- [ ] **Step 2.0: state.json 本 Task 置 in_progress（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '2':
        task['status'] = 'in_progress'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 2 -> in_progress')
"
```

- [ ] **Step 2.1: 读取模板参考文件**

使用 Read 工具读 `src/edu_cloud/modules/grading/MODULE.md`（117 行模板）。记录 frontmatter 字段：name / status / owner / layer / owns_tables / owns_routes / exposes (services/events) / depends_on (modules/services/ai_tools) / created / last_reviewed / design_docs。

- [ ] **Step 2.2: 清点 conduct 实际 owns_tables（对 ORM 模型）**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && grep -n "__tablename__" src/edu_cloud/modules/conduct/models.py
```
Expected: 8 行匹配——`student_profiles` / `conduct_class_configs` / `conduct_rule_categories` / `conduct_rule_items` / `conduct_records` / `conduct_groups` / `conduct_group_members` / `conduct_semesters`。

- [ ] **Step 2.3: 清点 conduct 实际 AI tools**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && grep -n "name=\"" src/edu_cloud/ai/tools/conduct.py | grep -v description
```
Expected: 6 行匹配—— get_conduct_rankings / get_student_conduct_summary / get_conduct_records / add_conduct_points / get_conduct_rules / get_class_conduct_overview。

- [ ] **Step 2.4: Create src/edu_cloud/modules/conduct/MODULE.md**

使用 Write 工具，内容为：

```markdown
---
name: conduct
status: active
owner: backend+frontend
layer: business

owns_tables:
  - student_profiles
  - conduct_class_configs
  - conduct_rule_categories
  - conduct_rule_items
  - conduct_records
  - conduct_groups
  - conduct_group_members
  - conduct_semesters

owns_routes:
  - /api/v1/conduct

exposes:
  services:
    - AdminService      # admin_service.py: 班级配置 / 家长管理 / 积分记录 CRUD / 排行榜 / 小组 / 学期
    - ParentService     # parent_service.py: 家长注册 / 登录 / 绑定 / 孩子记录 / 排名 / 资料
    - RulesService      # rules_service.py: 班规分类 + 条目 CRUD（含跨模块 check_rule_item_class 守卫）
    - ExportService     # export_service.py: Excel 导出（records / rankings）
  events: []

depends_on:
  modules:
    - student   # Student / Class ORM
    - school    # RegisteredSchool / School（间接）
  services:
    - ai.registry        # ToolSpec 注册
    - ai.tool_context    # ToolContext / ToolResult
    - core.permissions   # Permission 枚举 + RBAC（5 VIEW/MANAGE/RULES/PARENTS/EXPORT）
    - api.deps           # require_permission JWT 守卫
    - api.permissions    # get_visible_class_ids scope 过滤
  ai_tools:
    - get_conduct_rankings          # L2_conduct read-only
    - get_student_conduct_summary   # L6_profile read-only
    - get_conduct_records           # L2_conduct read-only
    - add_conduct_points            # L2_conduct medium risk, allowed_roles 限定
    - get_conduct_rules             # L2_conduct read-only
    - get_class_conduct_overview    # L2_conduct read-only

created: 2026-04-12
last_reviewed: 2026-04-14
design_docs:
  - docs/plans/2026-04-12-conduct-module-design.md
  - docs/plans/2026-04-14-conduct-roadmap-design.md
---

# conduct 模块

## 职责

学生操行积分 / 德育管理 / 家长门户。覆盖班级积分记录、班规 CRUD、小组管理、学期切换、家长注册绑定查看、管理端 Excel 导出、AI Chat 6 工具。

## 边界

- **做什么**：
  - 积分记录 CRUD（单条 / 批量 / 学生过滤 / 日期过滤 / 删除）+ Excel 导出
  - 班规分类与条目 CRUD（class-scope 守卫 check_rule_item_class）
  - 排行榜（学生 / 小组，支持学期过滤）
  - 小组管理（CRUD + 成员批量增删，check_students_class 守卫）
  - 学期管理（创建 / 切换激活）
  - 家长门户（邀请码验证 → 注册 → 登录 → 身份验证绑定 → 孩子记录 / 排名 / 班规 / 资料）
  - AES-256-GCM PII 加密（student_profiles.id_card_number / verify_code）
  - 6 AI Agent 工具（含 F003 scope 守卫 _check_class_in_scope / _check_student_in_scope）
- **不做什么**：
  - 学生 Student / Class 基本信息 CRUD → `student` 模块
  - 学生成绩 / 考试 → `exam` / `analytics` 模块
  - 通知推送（班主任给家长发通知）→ `notifications` 模块
  - AI Chat 入口与会话管理 → `ai` 模块

## 使用方式

### 外部 / 上游

- **前端管理端** `pages/conduct/ConductDashboard.vue` 等 9 页面 → `GET/POST/PUT/DELETE /api/v1/conduct/classes/{class_id}/*`
- **前端家长端** `pages/parent/*.vue` 8 页面 → `POST /api/v1/conduct/parent/*` + `GET /api/v1/conduct/parent/children/*`（cp_token 独立认证）
- **AI Agent**：`ai/tools/conduct.py` 6 工具通过 `ai.registry` 注册供 AI Chat 调用

### 典型 API 使用

```bash
# 管理端：添加积分
POST /api/v1/conduct/classes/{class_id}/records
{ "student_ids": ["..."], "points": 5, "reason": "守时", "record_date": "2026-04-14" }

# 家长端：查看孩子记录
GET /api/v1/conduct/parent/children/{student_id}/records?page=1&page_size=20
Header: cp_token: ...

# AI Agent：查班级排行
tool: get_conduct_rankings
args: { "class_id": "...", "period": "this_month" }
```

## 数据流

```
用户操作（教师 UI / 家长 App / AI Chat）
       │
       ▼
FastAPI router（admin_router 28 端点 / parent_router 11 端点）
       │
       ▼  permissions.py 守卫（require_* + check_class_scope / check_rule_item_class / check_students_class）
       │
       ▼
service 层（AdminService / ParentService / RulesService / ExportService）
       │
       ▼
ORM 8 表（students_profiles ... conduct_semesters）
       │
       ▼（家长端 cp_token 独立 JWT 链路）
返回 JSON / Excel
```

## 变更历史

- 2026-04-12: 模块从 class-points 迁入 edu-cloud，8 表 + 39 端点 + 6 AI 工具（conduct-module 设计 R1+R2+R3 PASS）
- 2026-04-13: 默认上线 DEFAULT_ENABLED + sidebar 挂载补齐 (a117222 + d1bfd10)
- 2026-04-14: conduct-roadmap 批次 1 补 MODULE.md（T4）；同批次 T1 回收 lesson_prep_leader 权限 / T2 AddPointsRequest rename / T3 sidebar 按 permissions 派生
```

- [ ] **Step 2.5: 新增 governance 契约测试**

使用 Write 工具创建 `tests/test_conduct/test_module_governance.py`，内容：

```python
"""conduct MODULE.md 治理契约测试。

保证 MODULE.md 的 owns_tables / exposes.ai_tools 字段与实际代码一致。
任何新增 ORM 表或 AI 工具未同步 MODULE.md → 测试失败。
"""
from pathlib import Path

import yaml


MODULE_MD = (
    Path(__file__).resolve().parents[2]
    / "src" / "edu_cloud" / "modules" / "conduct" / "MODULE.md"
)


def _load_frontmatter() -> dict:
    """Extract YAML frontmatter from MODULE.md."""
    text = MODULE_MD.read_text(encoding="utf-8")
    assert text.startswith("---\n"), "MODULE.md must start with YAML frontmatter"
    _, fm, _ = text.split("---\n", 2)
    return yaml.safe_load(fm)


def test_module_md_exists():
    assert MODULE_MD.exists(), f"MODULE.md missing: {MODULE_MD}"


def test_owns_tables_matches_orm_definitions():
    """owns_tables must equal the __tablename__ values in models.py."""
    from edu_cloud.modules.conduct import models

    orm_tables = {
        cls.__tablename__
        for cls in vars(models).values()
        if isinstance(cls, type) and hasattr(cls, "__tablename__")
    }
    fm = _load_frontmatter()
    declared = set(fm.get("owns_tables") or [])
    assert declared == orm_tables, (
        f"owns_tables drift: declared={declared} actual={orm_tables}"
    )


def test_exposes_ai_tools_matches_registry():
    """exposes.ai_tools must equal the conduct-domain tools in ai.registry."""
    import edu_cloud.ai.tools  # noqa: F401 — trigger registration
    from edu_cloud.ai.registry import tools

    actual = {
        spec.name for spec in tools.get_all_specs()
        if spec.module_code == "conduct"
    }
    fm = _load_frontmatter()
    declared = set((fm.get("depends_on") or {}).get("ai_tools") or [])
    assert declared == actual, (
        f"ai_tools drift: declared={declared} actual={actual}"
    )
```

- [ ] **Step 2.6: 跑新测试，verify 3 passed**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/test_module_governance.py -v 2>&1 | tail -15
```
Expected: `3 passed` (test_module_md_exists / test_owns_tables_matches_orm_definitions / test_exposes_ai_tools_matches_registry)。若 fail，先 diff MODULE.md 的 owns_tables vs `grep __tablename__ models.py` 结果，补齐漏项。

- [ ] **Step 2.7: 跑 aggregate_modules 验证 conduct 进聚合产物**

Run（R1-F003 路径修正，真实脚本位于 governance 子目录）:
```bash
cd C:/Users/Administrator/edu-cloud && python scripts/governance/aggregate_modules.py 2>&1 | tail -20
```
Expected: 脚本退出码 0，产出 `modules.yaml` 含 conduct 条目；`debt-report.md` 中 conduct 不再出现在"缺 MODULE.md"列表。

- [ ] **Step 2.8: 跑 conduct 全量回归**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q --tb=no 2>&1 | tail -5
```
Expected: `121 passed`（118 基线 + 3 governance 新增）。

- [ ] **Step 2.8a: state.json 本 Task 置 completed（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '2':
        task['status'] = 'completed'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 2 -> completed')
"
```

- [ ] **Step 2.9: Commit**

```bash
cd C:/Users/Administrator/edu-cloud && git reset HEAD >/dev/null 2>&1 && \
  git add src/edu_cloud/modules/conduct/MODULE.md tests/test_conduct/test_module_governance.py docs/plans/2026-04-14-conduct-roadmap-batch1-state.json && \
  git diff --cached --name-only
# staged 应该 3 个文件（2 MODULE/test + state.json）
```

```bash
git commit -m "$(cat <<'EOF'
governance(conduct): T4 补 MODULE.md — owns_tables 8 + /api/v1/conduct + 6 AI tools

- 新建 src/edu_cloud/modules/conduct/MODULE.md (按 grading/pipeline 模板)
- 新增 tests/test_conduct/test_module_governance.py 3 测试：
  owns_tables 与 ORM __tablename__ 漂移检测；
  exposes.ai_tools 与 ai.registry 注册名漂移检测
- module_governance_guard 对 conduct commit 不再触发 ask

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

**审查清单:**
- ✓ `MODULE.md` frontmatter yaml 合法可 parse
- ✓ `owns_tables` 包含 8 表（student_profiles + 7 conduct_*）
- ✓ `depends_on.ai_tools` 列出 6 工具与注册名完全一致
- ✓ 3 governance 测试全通过
- ✗ owns_tables 漏 conduct_group_members → test_owns_tables_matches_orm_definitions FAIL
- ✗ ai_tools 漏 add_conduct_points → test_exposes_ai_tools_matches_registry FAIL
- 关键行为：后续改 conduct 代码时 module_governance_guard 静默通过（而非 ask）

**边界条件:**
- ORM 模型 `__tablename__` 是字符串字面量（非动态），测试用 `vars(models).values()` 遍历是可靠的
- `ai.registry` 必须先触发 `import edu_cloud.ai.tools` 完成注册，否则 `get_all_specs()` 为空
- `yaml.safe_load` 对 `#` 注释容错，但 frontmatter 里的 `#` 是行内注释必须保留（用作说明）——本 plan 的 yaml 示例里 `#` 在值之后，safe_load 会忽略

**测试契约:** N/A（非 behavior_change，是 contract 添加，用 governance 测试锁）

---

## Task 3: T1 lesson_prep_leader conduct 权限回收（后端 + 前端，3 commits）

**Files:**
- Modify: `src/edu_cloud/core/permissions.py:240`
- Modify: `frontend/src/config/permissions.js:59`
- Test: `tests/test_conduct/test_permissions.py`（新增 4 测试：lesson_prep 无 VIEW / 无 MANAGE / subject_teacher 未误伤 / homeroom 不变）
- Test: `tests/test_conduct/test_admin_crud_api.py`（**R1-F006 入口级**新增 1 测试：`test_lesson_prep_leader_cannot_call_conduct_api` → API 403）
- Test: `frontend/src/__tests__/permissions.lesson_prep.test.js`（新建 5 测试）

**性质:** behavior_change（已 L017 批准 R-T1 2026-04-14）。T2 级别（单文件 + 少量行）。

**依赖:** 无（后端独立）

### Steps

- [ ] **Step 3.0: state.json 本 Task 置 in_progress（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '3':
        task['status'] = 'in_progress'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 3 -> in_progress')
"
```

- [ ] **Step 3.1: 写失败后端测试（test_permissions.py 新增 4 测试）**

使用 Edit 工具在 `tests/test_conduct/test_permissions.py` 末尾追加：

```python


# ── T1 (2026-04-14): lesson_prep_leader conduct 权限回收 ──

def test_lesson_prep_leader_no_view_conduct():
    """T1: 备课组长不再拥有 VIEW_CONDUCT。"""
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("lesson_prep_leader", Permission.VIEW_CONDUCT) is False


def test_lesson_prep_leader_no_manage_conduct():
    """T1: 备课组长不再拥有 MANAGE_CONDUCT。"""
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("lesson_prep_leader", Permission.MANAGE_CONDUCT) is False


def test_subject_teacher_still_has_conduct():
    """T1: 科任教师 conduct 权限未被误伤（防止 _TEACHER_BASE 全体掉权）。"""
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("subject_teacher", Permission.VIEW_CONDUCT) is True
    assert has_permission("subject_teacher", Permission.MANAGE_CONDUCT) is True


def test_homeroom_teacher_still_has_conduct():
    """T1: 班主任 conduct 权限未被误伤。"""
    from edu_cloud.core.permissions import has_permission, Permission
    assert has_permission("homeroom_teacher", Permission.VIEW_CONDUCT) is True
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT) is True
    assert has_permission("homeroom_teacher", Permission.MANAGE_CONDUCT_RULES) is True
```

- [ ] **Step 3.2: 跑新测试确认 FAIL**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/test_permissions.py::test_lesson_prep_leader_no_view_conduct tests/test_conduct/test_permissions.py::test_lesson_prep_leader_no_manage_conduct -v 2>&1 | tail -10
```
Expected: 两个 test FAIL（assertion error：`True is not False`）。其他两个 test（subject_teacher/homeroom 仍有权限）应 PASS。

- [ ] **Step 3.3: 改 core/permissions.py L240**

使用 Edit 工具：
- 文件：`src/edu_cloud/core/permissions.py`
- old:
```python
    "lesson_prep_leader": _TEACHER_BASE.copy(),
```
- new:
```python
    "lesson_prep_leader": _TEACHER_BASE - {Permission.VIEW_CONDUCT, Permission.MANAGE_CONDUCT},
```

- [ ] **Step 3.4: 跑后端测试确认全 PASS**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/test_permissions.py -v 2>&1 | tail -15
```
Expected: 所有 test PASS（包括新增 4 个 T1 测试 + 原有测试）。

- [ ] **Step 3.4a: 新增 T1 入口级 API 403 测试（R1-F006 落到主 Steps）**

使用 Edit 工具在 `tests/test_conduct/test_admin_crud_api.py` 末尾追加：

```python


# ── T1 (R1-F006 入口级): lesson_prep_leader 调 conduct API 返回 403 ──

@pytest.mark.anyio
async def test_lesson_prep_leader_cannot_call_conduct_api(
    client, db, school_class_student,
):
    """T1 入口级: lesson_prep_leader 调 conduct API 返回 403（权限守卫层面，非仅 helper 单测）."""
    from edu_cloud.modules.student.models import UserRole, User
    from edu_cloud.shared.auth import create_access_token
    import uuid
    school, cls, _ = school_class_student

    user = User(
        id=str(uuid.uuid4()),
        username=f"lpl_{uuid.uuid4().hex[:8]}",
        hashed_password="x",
        display_name="备课组长",
    )
    db.add(user)
    await db.flush()
    role = UserRole(
        id=str(uuid.uuid4()),
        user_id=user.id,
        role="lesson_prep_leader",
        school_id=school.id,
        is_primary=True,
    )
    db.add(role)
    await db.commit()

    token = create_access_token({"sub": user.id, "active_role_id": role.id})
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rankings/students",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 3.4b: 跑入口级测试确认 PASS**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/test_admin_crud_api.py::test_lesson_prep_leader_cannot_call_conduct_api -v 2>&1 | tail -10
```
Expected: 1 test PASS（因 Step 3.3 已改 permissions.py，require_view_conduct 在 lesson_prep_leader 调 API 时直接 403）。

- [ ] **Step 3.5: 后端 commit（带 state.json in_progress）**

```bash
cd C:/Users/Administrator/edu-cloud && git reset HEAD >/dev/null 2>&1 && \
  git add src/edu_cloud/core/permissions.py tests/test_conduct/test_permissions.py tests/test_conduct/test_admin_crud_api.py docs/plans/2026-04-14-conduct-roadmap-batch1-state.json && \
  git diff --cached --name-only
# staged 4 个文件：permissions.py + 2 test file + state.json（in_progress 状态）
```
```bash
git commit -m "$(cat <<'EOF'
fix(permissions): T1 回收 lesson_prep_leader 的 conduct 权限（C 方案）

备课组长职责是学科教研，不涉及德育打分。R2 初版套用 _TEACHER_BASE
误给了 VIEW_CONDUCT + MANAGE_CONDUCT，本次回收。

- core/permissions.py:240 lesson_prep_leader 改为
  _TEACHER_BASE - {VIEW_CONDUCT, MANAGE_CONDUCT}
- 新增 4 个 helper 级红测：lesson_prep 无 VIEW/MANAGE，subject_teacher/homeroom 未误伤
- 新增 1 个入口级红测（R1-F006）：test_lesson_prep_leader_cannot_call_conduct_api → API 403

L017 behavior_change R-T1：用户 2026-04-14 明确批准（"备课组长和打分没关系"）

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

- [ ] **Step 3.6: 写失败前端测试**

使用 Write 工具创建 `frontend/src/__tests__/permissions.lesson_prep.test.js`：

```javascript
import { describe, it, expect } from 'vitest'
import { ROLE_PERMISSIONS, hasPermission } from '@/config/permissions'

describe('T1 — lesson_prep_leader conduct 权限回收', () => {
  it('lesson_prep_leader 不含 view_conduct', () => {
    expect(hasPermission('lesson_prep_leader', 'view_conduct')).toBe(false)
  })

  it('lesson_prep_leader 不含 manage_conduct', () => {
    expect(hasPermission('lesson_prep_leader', 'manage_conduct')).toBe(false)
  })

  it('subject_teacher 仍含 view_conduct / manage_conduct（未误伤）', () => {
    expect(hasPermission('subject_teacher', 'view_conduct')).toBe(true)
    expect(hasPermission('subject_teacher', 'manage_conduct')).toBe(true)
  })

  it('homeroom_teacher 仍含完整 conduct 5 权限', () => {
    const expected = [
      'view_conduct', 'manage_conduct',
      'manage_conduct_rules', 'manage_conduct_parents', 'export_conduct',
    ]
    for (const perm of expected) {
      expect(hasPermission('homeroom_teacher', perm)).toBe(true)
    }
  })

  it('lesson_prep_leader 其他教师基线权限保留（view_students 等）', () => {
    expect(hasPermission('lesson_prep_leader', 'view_students')).toBe(true)
    expect(hasPermission('lesson_prep_leader', 'view_homework')).toBe(true)
    expect(hasPermission('lesson_prep_leader', 'manage_homework')).toBe(true)
    expect(hasPermission('lesson_prep_leader', 'use_ai_chat')).toBe(true)
  })
})
```

- [ ] **Step 3.7: 跑前端测试确认 FAIL（2/5 应失败）**

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/permissions.lesson_prep.test.js 2>&1 | tail -20
```
Expected: 5 tests 中 2 个 FAIL（lesson_prep 无 view/manage）+ 3 PASS。

- [ ] **Step 3.8: 改 frontend/src/config/permissions.js L59**

使用 Edit 工具：
- 文件：`frontend/src/config/permissions.js`
- old:
```javascript
  lesson_prep_leader: [..._TEACHER_BASE],
```
- new:
```javascript
  // T1 (2026-04-14): 回收 view_conduct / manage_conduct，备课组长聚焦学科教研
  lesson_prep_leader: _TEACHER_BASE.filter(p => p !== 'view_conduct' && p !== 'manage_conduct'),
```

- [ ] **Step 3.9: 跑前端测试确认全 PASS**

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/permissions.lesson_prep.test.js 2>&1 | tail -10
```
Expected: 5 passed。

- [ ] **Step 3.9a: state.json 本 Task 置 completed（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '3':
        task['status'] = 'completed'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 3 -> completed')
"
```

- [ ] **Step 3.10: 前端 commit（带 state.json completed）**

```bash
cd C:/Users/Administrator/edu-cloud && git reset HEAD >/dev/null 2>&1 && \
  git add frontend/src/config/permissions.js frontend/src/__tests__/permissions.lesson_prep.test.js docs/plans/2026-04-14-conduct-roadmap-batch1-state.json && \
  git diff --cached --name-only
# staged 3 个文件：permissions.js + 1 test file + state.json（completed 状态）
```
```bash
git commit -m "$(cat <<'EOF'
fix(frontend): T1 镜像 lesson_prep_leader conduct 权限回收

frontend/src/config/permissions.js:59 改为 filter 掉 view_conduct/manage_conduct。
新增 permissions.lesson_prep.test.js 5 测试验证权限下降 + 其他角色未误伤。

与后端 commit 一起达成 T1 收尾。

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

- [ ] **Step 3.11: 跑 conduct 全量回归 + frontend 三件套**

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q --tb=no 2>&1 | tail -3
```
Expected: `125 passed`（118 基线 + 3 governance + 4 T1）。

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/sidebarConfig.conduct.test.js src/__tests__/AppSidebar.test.js src/pages/parent/__tests__/ParentRules.spec.js src/__tests__/permissions.lesson_prep.test.js 2>&1 | tail -5
```
Expected: `18 passed`（原 13 + 新 5）。

**审查清单:**
- ✓ `has_permission('lesson_prep_leader', Permission.VIEW_CONDUCT) is False`
- ✓ `hasPermission('lesson_prep_leader', 'view_conduct') === false`
- ✓ `has_permission('subject_teacher', Permission.VIEW_CONDUCT) is True`（未误伤）
- ✓ `has_permission('homeroom_teacher', Permission.MANAGE_CONDUCT_RULES) is True`（班主任不变）
- ✗ `_TEACHER_BASE` 未被整体回收（subject_teacher 若掉权则 bug）
- ✗ `subject_teacher` 如被误判为失去 view_conduct → 红测 3 PASS / 红测 4 FAIL 的极端顺序不允许
- 关键行为：AI Chat 调 conduct 工具时，lesson_prep_leader 的 ToolAccessResolver 过滤掉 6 conduct 工具

**边界条件:**
- 空输入（无该角色）：`has_permission('unknown_role', ...)` → `False`（参考 core/permissions.py L294 `ROLE_PERMISSIONS.get(role, set())`）
- 单元素（VIEW_CONDUCT 单独查）→ 返回 False
- 集合运算边界：`_TEACHER_BASE - set()` = `_TEACHER_BASE.copy()`，不会意外空集合
- 语义回归：`_TEACHER_BASE` 未来新增权限（如 view_ai_chat）lesson_prep_leader 自动继承，但永不拥有 conduct

**测试契约（5 字段，behavior_change R-T1）:**

1. **lesson_prep_leader 无 VIEW_CONDUCT（红测核心）**
   - 入口: `has_permission('lesson_prep_leader', Permission.VIEW_CONDUCT)` → False（Python 直接调用）
   - 反例: 错误实现仍然 `_TEACHER_BASE.copy()` → 返回 True → 本测试 AssertionError
   - 边界: 查 MANAGE_CONDUCT 也应 False；查 MANAGE_HOMEWORK 应 True（仍在 _TEACHER_BASE）
   - 回归: 防止后续任意改动重新加回 conduct 到 _TEACHER_BASE.copy() 模式
   - 命令: `python -m pytest tests/test_conduct/test_permissions.py::test_lesson_prep_leader_no_view_conduct -v`

2. **subject_teacher 未误伤（反例兜底）**
   - 入口: `has_permission('subject_teacher', Permission.VIEW_CONDUCT)` → True
   - 反例: 如果开发者错误地改 _TEACHER_BASE 本身（移除 VIEW_CONDUCT），subject_teacher 也掉权 → 本测试 FAIL
   - 边界: MANAGE_CONDUCT 同样保留
   - 回归: N/A（防一开始就犯错）
   - 命令: `python -m pytest tests/test_conduct/test_permissions.py::test_subject_teacher_still_has_conduct -v`

3. **前端镜像**
   - 入口: `hasPermission('lesson_prep_leader', 'view_conduct')` → false（JavaScript）
   - 反例: 错误实现仍 `[..._TEACHER_BASE]` → 返回 true → 本测试 FAIL
   - 边界: manage_conduct 同样 false
   - 回归: 防止前后端镜像重新漂移
   - 命令: `npx vitest run src/__tests__/permissions.lesson_prep.test.js`

4. **API 入口级拒绝（R1-F006 用户可触达入口）**
   - 入口: HTTP `GET /api/v1/conduct/classes/{class_id}/rankings/students` with JWT token of `lesson_prep_leader` → 403
   - 反例: 若 permissions.py 未改仅改了 helper 表达，lesson_prep_leader 持 JWT 仍 200 → API 403 断言 FAIL
   - 边界: token 为 subject_teacher/homeroom_teacher 应 200（未误伤）；token 为 anonymous 应 401 不是 403
   - 回归: 与 helper 红测联动，防守卫路径和角色映射分裂
   - 命令: `pytest tests/test_conduct/test_admin_crud_api.py::test_lesson_prep_leader_cannot_call_conduct_api -v`

---

## Task 4: T2 AddPointsRequest.date → record_date（后端 + 前端，1 commit）

**Files:**
- Modify: `src/edu_cloud/modules/conduct/schemas.py:2,38`（字段 `date: Optional[date]` → `record_date: Optional[_date_type]` + import rename）
- Modify: `src/edu_cloud/modules/conduct/admin_router.py:115,137`（**R1-F001 关键补充**：`record_date=data.date` → `record_date=data.record_date` 两处）
- **不改** `src/edu_cloud/modules/conduct/admin_service.py`：L254/271 已经用 `record_date: date_type | None = None`，历史重构已完成（verify only）
- Modify: `frontend/src/api/conduct.js`（若有 `date` body 字段则同步）
- Modify: `frontend/src/pages/conduct/ConductPoints.vue`（表单 v-model 字段同步）
- Test: `tests/test_conduct/test_admin_crud_api.py`（新增 3 测试，入口级 POST 200 + readback，替换原 plan 错误的 201+[{date}] 断言）

**性质:** behavior_change（已 L017 批准 R-T2 2026-04-14）。T2 级别。

**依赖:** 无。

**R1 修复说明（F001/F002）:**
- F001: 原 plan 遗漏 `admin_router.py:115,137` 的 `data.date` 读取点。service 层**已经**在早期重构中 rename 为 `record_date` 参数，router 层却仍读取 schema 的 `data.date` 属性（当字段 rename 后会 AttributeError）。Files 段已补齐。
- F002: 原 plan 测试假设返回 `201 + [{"date": ...}]`，真实入口返回 `200 + {"created_ids": [...]}`（见 `test_admin_crud_api.py:15-30`）。新测试改为"POST 200 + DB readback 或 GET list 读回"的入口级验证。

### Steps

- [ ] **Step 4.0: state.json 本 Task 置 in_progress（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '4':
        task['status'] = 'in_progress'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 4 -> in_progress')
"
```

- [ ] **Step 4.1: 审计所有 request.date 使用点**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && grep -rn "\.date\b" src/edu_cloud/modules/conduct/ | grep -v "\.date_type\|__date__\|ConductRecord.date\|Record\.date\|record\.date\|created_at"
```
记录所有 `AddPointsRequest(...).date` 或 `request.date` 的出现位置。预计在 admin_service.py 1-3 处 / admin_router.py 0-1 处。

Run:
```bash
cd C:/Users/Administrator/edu-cloud && grep -rn "\"date\"\\|'date'" frontend/src/api/conduct.js frontend/src/pages/conduct/ConductPoints.vue 2>/dev/null
```
记录前端所有 body 字段 `date` 使用。

- [ ] **Step 4.2: 写失败测试（tests/test_admin_api.py 新增 3 测试）**

使用 Edit 工具在 `tests/test_conduct/test_admin_api.py` 末尾追加（按现有 test 风格）：

```python


# ── T2 (2026-04-14, R1-F002 入口级 POST + DB readback): AddPointsRequest.date → record_date rename ──

@pytest.mark.anyio
async def test_add_points_with_record_date_field(
    client, db, school_class_student, homeroom_teacher, homeroom_headers,
):
    """T2: 传 record_date 字符串 → 200 + DB Record.date == 传入值（入口级 POST + DB readback）."""
    from sqlalchemy import select
    from edu_cloud.modules.conduct.models import ConductRecord

    school, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id],
            "points": 5,
            "reason": "T2 record_date 测试",
            "record_date": "2026-04-10",
        },
    )
    assert resp.status_code == 200, resp.text
    created_ids = resp.json()["created_ids"]
    assert len(created_ids) == 1

    rec = (await db.execute(
        select(ConductRecord).where(ConductRecord.id == created_ids[0])
    )).scalar_one()
    assert str(rec.date) == "2026-04-10"


@pytest.mark.anyio
async def test_add_points_without_record_date_defaults_today(
    client, db, school_class_student, homeroom_teacher, homeroom_headers,
):
    """T2: 不传 record_date → 200 + DB Record.date == today（维持原行为）."""
    from datetime import date as _date
    from sqlalchemy import select
    from edu_cloud.modules.conduct.models import ConductRecord

    school, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id],
            "points": 5,
            "reason": "T2 默认日期测试",
        },
    )
    assert resp.status_code == 200, resp.text
    created_ids = resp.json()["created_ids"]

    rec = (await db.execute(
        select(ConductRecord).where(ConductRecord.id == created_ids[0])
    )).scalar_one()
    assert rec.date == _date.today()


@pytest.mark.anyio
async def test_add_points_with_record_date_null_defaults_today(
    client, db, school_class_student, homeroom_teacher, homeroom_headers,
):
    """T2: 显式 record_date=null → 200 + DB Record.date == today."""
    from datetime import date as _date
    from sqlalchemy import select
    from edu_cloud.modules.conduct.models import ConductRecord

    school, cls, student = school_class_student
    resp = await client.post(
        f"/api/v1/conduct/classes/{cls.id}/records",
        headers=homeroom_headers,
        json={
            "student_ids": [student.id],
            "points": 5,
            "reason": "T2 null 日期测试",
            "record_date": None,
        },
    )
    assert resp.status_code == 200, resp.text
    created_ids = resp.json()["created_ids"]

    rec = (await db.execute(
        select(ConductRecord).where(ConductRecord.id == created_ids[0])
    )).scalar_one()
    assert rec.date == _date.today()
```

（Fixture 名 `homeroom_teacher` + `homeroom_headers` 来自 `tests/test_conduct/test_admin_crud_api.py:16`；测试文件从 `test_admin_api.py` 改为 `test_admin_crud_api.py` 以复用同套 fixture。3 个测试均采用"POST 200 + DB readback"的入口级契约验证，符合 review-templates test-gap 判定。）

- [ ] **Step 4.3: 跑新测试确认 FAIL**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/test_admin_crud_api.py -k "record_date" -v 2>&1 | tail -15
```
Expected: 3 test FAIL（当前 schema 字段名仍是 `date`，不识别 `record_date` 字段 → pydantic 静默忽略 extra 字段 → DB 用 today，断言 "2026-04-10" FAIL；或 AttributeError）。

- [ ] **Step 4.4: 改 schemas.py**

使用 Edit 工具：
- 文件：`src/edu_cloud/modules/conduct/schemas.py`
- old（L2）:
```python
from datetime import date
```
- new:
```python
from datetime import date as _date_type
```

然后再 Edit：
- old（L38，在 class AddPointsRequest 内）:
```python
    date: Optional[date] = None
```
- new:
```python
    record_date: Optional[_date_type] = None
```

然后 Edit L46 `PointsRecordResponse` 的 `date: date` 字段（保留，这是 response 字段用于返回 DB date 值）：
- old:
```python
    date: date
```
- new:
```python
    date: _date_type
```

- [ ] **Step 4.5: 改 admin_router.py（R1-F001 关键补充）**

审计 router 层实际的 `data.date` 使用：
```bash
cd C:/Users/Administrator/edu-cloud && grep -n "data\.date\|request\.date" src/edu_cloud/modules/conduct/admin_router.py src/edu_cloud/modules/conduct/admin_service.py
```
Expected: `admin_router.py:115` + `admin_router.py:137` 两处 `record_date=data.date`；`admin_service.py` 无匹配（service 层参数名已是 `record_date`，L254/271）。

对 admin_router.py 两处 Edit：
- 文件：`src/edu_cloud/modules/conduct/admin_router.py`
- 使用 Edit 工具 `replace_all=true`，将 `record_date=data.date,` → `record_date=data.record_date,` 两处统一替换

**不改 admin_service.py**：L254 `record_date: date_type | None = None` 已是目标状态；L271 `use_date = record_date or date_type.today()` 使用入参不走 request 属性访问。仅 verify 无残留即可。

**R1-F001 根因**：service 层 L254/271 在早前重构中已 rename 为 `record_date` 参数，但 router 层 L115/137 仍使用 `data.date` 读取 schema 字段值。schema rename 后 `data.date` 不再存在，造成 AttributeError。原 plan 把调用链审计集中到 service，遗漏 router 入口。

- [ ] **Step 4.6: 跑后端测试确认全 PASS**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/test_admin_crud_api.py -k "record_date or add_points" -v 2>&1 | tail -20
```
Expected: 3 新测试 PASS；其他既有 add_points 测试（用 today default）维持 PASS。

Run（全量 conduct 回归）:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q --tb=short 2>&1 | tail -10
```
Expected: `129 passed`（118 基线 + 3 T4 + 4 T1 helper + 1 T1 入口级 + 3 T2 入口级 = 129）。

- [ ] **Step 4.7: 前端同步**

Run 审计：
```bash
cd C:/Users/Administrator/edu-cloud && grep -rn "date" frontend/src/api/conduct.js frontend/src/pages/conduct/ConductPoints.vue | grep -v "new Date\|Date\.\|\.toLocaleDateString\|createdAt\|created_at\|成绩日期\|//"
```

若找到 body 字段 `date: ...`（发送到后端的请求体里），使用 Edit 工具改为 `record_date`。

典型位置：
- `frontend/src/api/conduct.js` 的 `addPoints` / `batchAddPoints` 函数 body 参数
- `frontend/src/pages/conduct/ConductPoints.vue` 的 `<n-date-picker v-model:value="form.date">` → `form.record_date`，以及表单提交时的 `body: { ..., date: form.date }` → `record_date: form.recordDate`（若存在）

（说明：如果前端目前 **根本没传** date 字段（即从未使用此功能），跳过前端改动，仅在 commit 注释说明。本 plan 假设前端可能有未使用的 date 字段引用——审计后再决定）

- [ ] **Step 4.8: 跑前端测试确认通过（若前端改动涉及 ConductPoints 相关测试）**

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run --run 2>&1 | tail -10
```
Expected: 全部 PASS（若有 ConductPoints 相关测试需同步更新）。

- [ ] **Step 4.8a: state.json 本 Task 置 completed（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '4':
        task['status'] = 'completed'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 4 -> completed')
"
```

- [ ] **Step 4.9: Commit**

```bash
cd C:/Users/Administrator/edu-cloud && git reset HEAD >/dev/null 2>&1 && \
  git add src/edu_cloud/modules/conduct/schemas.py src/edu_cloud/modules/conduct/admin_router.py tests/test_conduct/test_admin_crud_api.py docs/plans/2026-04-14-conduct-roadmap-batch1-state.json && \
  (ls frontend/src/api/conduct.js frontend/src/pages/conduct/ConductPoints.vue 2>/dev/null | xargs -r git add) && \
  git diff --cached --name-only
# verify-only（不改动）: admin_service.py L254/271 已是目标状态；若该文件出现在 staged 列表说明不慎 staged，需 restore
# staged 包括 state.json（completed 状态）
```

```bash
git commit -m "$(cat <<'EOF'
fix(conduct): T2 AddPointsRequest.date → record_date（修 pydantic v2 字段名遮蔽 type）

根因: schemas.py L2 `from datetime import date` + L38 字段 `date: Optional[date]`
字段名遮蔽 type，pydantic v2 解析为 Optional[None] → 客户端传
`{"date": "2026-04-14"}` 被 422 拒绝。

修复:
- schemas.py L2 改为 `from datetime import date as _date_type`
- AddPointsRequest.date → record_date: Optional[_date_type]
- PointsRecordResponse.date 字段名保留，类型注解 date → _date_type
- admin_router.py L115/L137 `record_date=data.date` → `record_date=data.record_date`
  （R1-F001：service 层 L254/271 已是 record_date 参数，router 入口遗漏修，字段 rename 后会 AttributeError）
- admin_service.py verify-only 不改
- frontend api/Vue 同步（若有）
- 新增 3 红测：入口级 POST 200 + DB readback（R1-F002）

影响: admin_router POST /records 及批量接口；Agent 工具 add_conduct_points
用 server-side date.today() 不受影响。

L017 behavior_change R-T2：用户 2026-04-14 明确批准（"两个都批准"）

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

**审查清单:**
- ✓ POST `/records` with `{"record_date": "2026-04-14"}` → 201，DB Record.date == 2026-04-14
- ✓ POST `/records` without record_date → 201，DB Record.date == today
- ✓ POST `/records` with `{"record_date": null}` → 201，DB Record.date == today
- ✓ POST `/records/batch` 同字段名 rename
- ✓ Agent `add_conduct_points` 工具行为不变（无 request schema 依赖）
- ✗ schemas.py 中 PointsRecordResponse.date 被错误改名 → response 字段丢失（前端/测试 KeyError）
- ✗ admin_service 中 Record.date SQLAlchemy column 被错误改名 → ORM AttributeError
- 关键行为：班主任补录历史日期积分真可用

**边界条件:**
- 空输入（`record_date` 字段未传）→ 接受，默认 today
- 单元素（`record_date="2026-04-10"`）→ 接受，DB 日期等于传入
- 溢出/极值（`record_date="invalid"`）→ pydantic 422 validation error
- 显式 None（`record_date: null`）→ 接受，默认 today（与不传同等）
- 未来日期（`record_date="2099-12-31"`）→ 当前接受（业务校验留未来功能）
- 批量：`/records/batch` body 里 date 字段同 rename

**测试契约（5 字段，behavior_change R-T2）:**

1. **record_date 字段生效**
   - 入口: POST `/api/v1/conduct/classes/{class_id}/records` body `{"record_date": "2026-04-10"}`
   - 反例: 错误实现仍用旧字段名 `date` → pydantic 忽略 record_date，DB 存 today → `assert data[0]["date"] == "2026-04-10"` FAIL
   - 边界: "2026-04-10"（过去）/ null / 未传 / "invalid"（422）
   - 回归: 防止未来再次把字段名改回 `date` 撞 type
   - 命令: `pytest tests/test_conduct/test_admin_api.py::test_add_points_with_record_date_field -v`

2. **不传 record_date 默认 today**
   - 入口: POST `/records` body 无 record_date 字段
   - 反例: 若 default 写死 `None` 并在 service 层不 fallback → DB Record.date 为 NULL → FAIL（DB 列 nullable=False）
   - 边界: 空 body（仍需 student_ids/points/reason 必填）/ 未传 record_date
   - 回归: 防止未来 default 行为变更
   - 命令: `pytest tests/test_conduct/test_admin_api.py::test_add_points_without_record_date_defaults_today -v`

3. **null 等价于不传**
   - 入口: POST `/records` body `{"record_date": null}`
   - 反例: 错误实现 `if request.record_date is None: raise 400` → 422 或 400 FAIL
   - 边界: null / missing 应同语义
   - 回归: N/A
   - 命令: `pytest tests/test_conduct/test_admin_api.py::test_add_points_with_record_date_null_defaults_today -v`

---

## Task 5: T3 sidebar 按 permissions 派生（前端重构，2 commits）

**Files:**
- Modify: `frontend/src/config/sidebarConfig.js`（CONDUCT_* 三档 → 单一 `export const CONDUCT_ITEMS` + filterConductByRole；**R1-F007 要求 export** 以供治理测试 import）
- Test: `frontend/src/__tests__/sidebarConfig.conduct.test.js`（矩阵扩展 9 角色 × 关键入口 + R1-F007 `test_conduct_items_perm_valid` 治理契约）
- Test: `frontend/src/__tests__/AppSidebar.test.js`（R1-F006 入口级追加 `test_academic_director_conduct_seven_items`）

**性质:** behavior_change（已 L017 批准 R-T3 2026-04-14）。T3 级别（前端架构调整）。

**依赖:** T1（lesson_prep_leader 权限已回收）完成后再做（否则 lesson_prep 会从 permission 派生出 2 项）。

### Steps

- [ ] **Step 5.0: state.json 本 Task 置 in_progress（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '5':
        task['status'] = 'in_progress'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 5 -> in_progress')
"
```

- [ ] **Step 5.1: 写失败矩阵测试（sidebarConfig.conduct.test.js 扩展）**

使用 Read 工具先看 `frontend/src/__tests__/sidebarConfig.conduct.test.js` 现有结构。

然后使用 Edit 工具扩展（在现有 describe 块末尾或新 describe 块）：

```javascript
describe('T3 — sidebar 按 permissions 派生（conduct 矩阵）', () => {
  const getConductItems = (role) => {
    const items = getSidebarItems(role) // 或 sidebarConfig[role] 按现有 API
    return items.filter(it => it.moduleCode === 'conduct').map(it => it.route)
  }

  it('platform_admin 看到 9 项 conduct 菜单', () => {
    const routes = getConductItems('platform_admin')
    expect(routes).toHaveLength(9)
  })

  it('academic_director 改后看到 7 项（新增积分操作/记录/班规/小组）', () => {
    const routes = getConductItems('academic_director')
    expect(routes).toEqual(expect.arrayContaining([
      '/conduct',
      '/conduct/points',
      '/conduct/records',
      '/conduct/rankings',
      '/conduct/rules',
      '/conduct/groups',
      '/conduct/export',
    ]))
    expect(routes).not.toContain('/conduct/parents')   // 无 MANAGE_CONDUCT_PARENTS
    expect(routes).not.toContain('/conduct/settings')  // 设置走 rules 权限，但需 manage_conduct_rules
    expect(routes).toHaveLength(7)
  })

  it('grade_leader 改后看到 5 项（新增积分操作/记录）', () => {
    const routes = getConductItems('grade_leader')
    expect(routes).toEqual(expect.arrayContaining([
      '/conduct',
      '/conduct/points',
      '/conduct/records',
      '/conduct/rankings',
      '/conduct/export',
    ]))
    expect(routes).toHaveLength(5)
  })

  it('lesson_prep_leader 无 conduct 入口（T1=C 回收后）', () => {
    const routes = getConductItems('lesson_prep_leader')
    expect(routes).toHaveLength(0)
  })

  it('principal 仍 3 项（view + export）', () => {
    const routes = getConductItems('principal')
    expect(routes).toEqual(expect.arrayContaining([
      '/conduct', '/conduct/rankings', '/conduct/export',
    ]))
    expect(routes).toHaveLength(3)
  })

  it('homeroom_teacher 9 项不变', () => {
    const routes = getConductItems('homeroom_teacher')
    expect(routes).toHaveLength(9)
  })

  it('subject_teacher 按权限派生得 4 项（概览/积分操作/记录/排行）', () => {
    // T3 扩展：subject_teacher 权限 view+manage → 派生 4 项，非原 TEACHER 2 项
    const routes = getConductItems('subject_teacher')
    expect(routes).toEqual(expect.arrayContaining([
      '/conduct', '/conduct/points', '/conduct/records', '/conduct/rankings',
    ]))
    expect(routes).toHaveLength(4)
  })

  it('teaching_research_leader 无 conduct 权限 → 0 项', () => {
    const routes = getConductItems('teaching_research_leader')
    expect(routes).toHaveLength(0)
  })

  it('parent 无 sidebar（走独立 ParentLayout）', () => {
    // parent 不应调用 sidebarConfig；若调用应 fallback 空
    const routes = getConductItems('parent')
    expect(routes).toHaveLength(0)
  })
})
```

✅ **已批准 (R1-F005)**：subject_teacher 从 2 项扩展到 4 项（view+manage 权限派生）为 behavior_change，用户于 **2026-04-14T07:45:00+08:00** 精确回复"批准 F005"（记录于 `gates.json` round1_findings.F005.approval）。保守备选方案（allowed_roles 白名单维持 2 项）**rejected**，不再执行。本 plan 按批准方案落地。

- [ ] **Step 5.2: 跑测试确认 FAIL（至少 academic_director / grade_leader / subject_teacher 三个测试）**

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/sidebarConfig.conduct.test.js 2>&1 | tail -25
```
Expected: 原有 13 个测试 PASS + 新增 9 个中至少 3 个 FAIL（academic_director 数量 3≠7 / grade_leader 3≠5 / subject_teacher 2≠4）。lesson_prep/platform/principal/homeroom/teaching_research/parent 可能已 PASS。

- [ ] **Step 5.2a: 新增 CONDUCT_ITEMS.perm 合法性治理测试（R1-F007 入口级，落到主 Steps）**

使用 Edit 工具在 `frontend/src/__tests__/sidebarConfig.conduct.test.js` 末尾追加一个独立 describe 块：

```javascript
import { ROLE_PERMISSIONS } from '@/config/permissions'
import { CONDUCT_ITEMS } from '@/config/sidebarConfig' // 依赖 Step 5.3 导出

describe('T3 (R1-F007) — CONDUCT_ITEMS perm 合法性治理', () => {
  it('test_conduct_items_perm_valid: CONDUCT_ITEMS 每个 perm 字段都在合法 permission 集，防 typo 静默失败', () => {
    const allPerms = new Set()
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      for (const p of perms) allPerms.add(p)
    }
    for (const item of CONDUCT_ITEMS) {
      expect(allPerms.has(item.perm)).toBe(true)
    }
  })
})
```

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/sidebarConfig.conduct.test.js -t "CONDUCT_ITEMS perm 合法性" 2>&1 | tail -10
```
Expected: test FAIL（当前 sidebarConfig.js 未 export CONDUCT_ITEMS，import 失败 → ReferenceError / undefined）。这个测试会在 Step 5.3 完成 export 后 PASS。

- [ ] **Step 5.2b: 新增 AppSidebar 入口级快照测试（R1-F006）**

使用 Edit 工具在 `frontend/src/__tests__/AppSidebar.test.js` 末尾追加（导入按现有文件既有模式）：

```javascript
describe('T3 (R1-F006) — AppSidebar 入口级渲染', () => {
  it('test_academic_director_conduct_seven_items: academic_director 登录侧边栏 conduct 段渲染 7 项', async () => {
    const pinia = createTestingPinia({
      initialState: { auth: { currentRole: 'academic_director', user: { id: 'u1' } } },
    })
    const wrapper = mount(AppSidebar, { global: { plugins: [pinia] } })
    const conductItems = wrapper.findAll('[data-module="conduct"]')
    expect(conductItems).toHaveLength(7)
  })
})
```

若 AppSidebar.vue 渲染的菜单项未加 `data-module="conduct"` 属性，Step 5.3 同步改渲染层加此属性；否则退回按 label 文字查找（aria-label / text）。

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/AppSidebar.test.js -t "academic_director conduct seven items" 2>&1 | tail -10
```
Expected: test FAIL（当前 academic_director 走 VIEWER 档 3 项，断言 7 项失败）。Step 5.3 完成后 PASS。

- [ ] **Step 5.3: 重构 sidebarConfig.js CONDUCT 部分**

使用 Read 工具先完整读 `frontend/src/config/sidebarConfig.js`（预计 130-150 行）。

再使用 Edit 工具：
- old（L1-21 附近，即 CONDUCT_ITEMS_FULL / VIEWER / TEACHER 三档定义）:
```javascript
const CONDUCT_ITEMS_FULL = [
  { icon: 'conduct', label: '德育概览', route: '/conduct', moduleCode: 'conduct' },
  // ... 9 项
]

const CONDUCT_ITEMS_VIEWER = [
  // ... 3 项
]

const CONDUCT_ITEMS_TEACHER = [
  // ... 2 项
]
```
- new:
```javascript
// T3 (2026-04-14): 按 permissions 派生，废弃 FULL/VIEWER/TEACHER 三档硬编码
// 每个菜单项声明依赖的 permission；渲染时按 hasPermission(role, perm) 过滤
// R1-F007: 必须 export 以供 sidebarConfig.conduct.test.js 治理测试 import
export const CONDUCT_ITEMS = [
  { icon: 'conduct', label: '德育概览', route: '/conduct',          perm: 'view_conduct',           moduleCode: 'conduct' },
  { icon: 'conduct', label: '积分操作', route: '/conduct/points',   perm: 'manage_conduct',         moduleCode: 'conduct' },
  { icon: 'conduct', label: '积分记录', route: '/conduct/records',  perm: 'view_conduct',           moduleCode: 'conduct' },
  { icon: 'conduct', label: '排行榜',   route: '/conduct/rankings', perm: 'view_conduct',           moduleCode: 'conduct' },
  { icon: 'conduct', label: '班规管理', route: '/conduct/rules',    perm: 'manage_conduct_rules',   moduleCode: 'conduct' },
  { icon: 'conduct', label: '小组管理', route: '/conduct/groups',   perm: 'manage_conduct',         moduleCode: 'conduct' },
  { icon: 'conduct', label: '家长管理', route: '/conduct/parents',  perm: 'manage_conduct_parents', moduleCode: 'conduct' },
  { icon: 'conduct', label: '德育设置', route: '/conduct/settings', perm: 'manage_conduct_rules',   moduleCode: 'conduct' },
  { icon: 'conduct', label: '数据导出', route: '/conduct/export',   perm: 'export_conduct',         moduleCode: 'conduct' },
]

function filterConductByRole(role) {
  // 依赖 ROLE_PERMISSIONS 导入，按 perm 字段过滤
  return CONDUCT_ITEMS.filter(it => hasPermission(role, it.perm))
}
```

再 Edit sidebarConfig 导出的 role→items 映射（原 `...CONDUCT_ITEMS_FULL` / `...CONDUCT_ITEMS_VIEWER` / `...CONDUCT_ITEMS_TEACHER` 的所有 spread 点），**统一改为** `...filterConductByRole('<role>')`。

⚠ **导入权限函数**：在文件顶部加 `import { hasPermission } from './permissions'`，若已导入跳过。

⚠ **R1-F006 data-module 属性**：AppSidebar.vue 渲染每个菜单项时必须带 `data-module` 属性（= item.moduleCode 值），以供 `test_academic_director_conduct_seven_items` 入口级测试 `wrapper.findAll('[data-module="conduct"]')` 定位。若 AppSidebar.vue 当前未带此属性，Step 5.3 同时改模板（典型行：`<n-menu-item :data-module="item.moduleCode">`）。若渲染层无法控制 DOM 属性（Naive UI n-menu 结构限制），退而按 label 文本查找。

具体角色行：
- `platform_admin: [...其他, ...filterConductByRole('platform_admin')]`
- `district_admin: [...其他, ...filterConductByRole('district_admin')]`
- `principal: [...其他, ...filterConductByRole('principal')]`
- `academic_director: [...其他, ...filterConductByRole('academic_director')]`
- `grade_leader: [...其他, ...filterConductByRole('grade_leader')]`
- `homeroom_teacher: [...其他, ...filterConductByRole('homeroom_teacher')]`
- `subject_teacher: [...其他, ...filterConductByRole('subject_teacher')]`
- `lesson_prep_leader`: 保持无 conduct（既没有调用 filterConductByRole 也没有 CONDUCT_ITEMS_* spread）；或显式 `...filterConductByRole('lesson_prep_leader')` 返回空数组也可
- `teaching_research_leader`: 同 lesson_prep（权限里本就无 conduct）

- [ ] **Step 5.4: 跑测试确认全 PASS**

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/sidebarConfig.conduct.test.js src/__tests__/AppSidebar.test.js 2>&1 | tail -15
```
Expected: sidebarConfig.conduct.test.js 原 13 + 新 9 矩阵 + 新 1 (F007 perm 合法性) = 23 passed；AppSidebar.test.js 原有 + 新 1 (F006 academic_director 7 项) 全 PASS。合计对 conduct 套件贡献 ≥ 24 pass（原 13 + 10 新增）。

- [ ] **Step 5.5: 跑 AppSidebar.test.js + 全量前端**

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/AppSidebar.test.js 2>&1 | tail -10
```
Expected: 既有测试 PASS（AppSidebar.vue 接收 sidebarConfig 产物，不因 CONDUCT_ITEMS_* 重构而 break）。

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run 2>&1 | tail -5
```
Expected: 全量前端测试 PASS（≥ 77，即 72 原 + 4 T1 + 9 T3 新增测试，数字按实际）。

- [ ] **Step 5.6: 手动浏览器 smoke（可选但推荐）**

若 dev server 运行中：
```bash
cd C:/Users/Administrator/edu-cloud/frontend && python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev
# 访问 http://localhost:5273，用 academic_director 账号登录（如 admin + switch-role）
# 验证侧边栏 conduct 段能看到 7 个菜单项
```
（若不跑 smoke，在 commit message 里明确声明"UI 未 E2E，仅单元测试覆盖"）

- [ ] **Step 5.6a: state.json 本 Task 置 completed（R1-F004）**

```bash
cd C:/Users/Administrator/edu-cloud && python3 -c "
import json, datetime, pathlib
STATE = pathlib.Path('docs/plans/2026-04-14-conduct-roadmap-batch1-state.json')
state = json.loads(STATE.read_text(encoding='utf-8'))
for task in state['tasks']:
    if task['id'] == '5':
        task['status'] = 'completed'
state['updated_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')
print('Task 5 -> completed')
"
```

- [ ] **Step 5.7: Commit**

```bash
cd C:/Users/Administrator/edu-cloud && git reset HEAD >/dev/null 2>&1 && \
  git add frontend/src/config/sidebarConfig.js frontend/src/__tests__/sidebarConfig.conduct.test.js frontend/src/__tests__/AppSidebar.test.js docs/plans/2026-04-14-conduct-roadmap-batch1-state.json && \
  (ls frontend/src/components/shell/AppSidebar.vue 2>/dev/null | xargs -r git add) && \
  git diff --cached --name-only
# staged: sidebarConfig.js + 2 test files + state.json（completed 状态）+ 可选 AppSidebar.vue（若加了 data-module 属性）
```

```bash
git commit -m "$(cat <<'EOF'
refactor(frontend): T3 sidebar 按 permissions 派生 — conduct 三档硬编码→单源 filter

废弃 CONDUCT_ITEMS_FULL / VIEWER / TEACHER 三档，改为单一 CONDUCT_ITEMS 列表
+ filterConductByRole(role) 按 hasPermission(role, item.perm) 过滤。

影响（可见入口数）:
- academic_director 3→7（新增 积分操作/记录/班规/小组）
- grade_leader 3→5（新增 积分操作/记录）
- subject_teacher 2→4（按 view+manage 派生，原 TEACHER 2 项 → 概览/积分/记录/排行）
- lesson_prep_leader 0（T1=C 权限回收后一致）
- platform_admin / district_admin / principal / homeroom / teaching_research / parent 不变

新增 9 个矩阵测试覆盖 9 角色 × 关键入口 + R1-F007 CONDUCT_ITEMS.perm 合法性治理 1 测试 + R1-F006 AppSidebar academic_director 7 项入口级 1 测试。合计 conduct 前端套件 29 passed。

L017 behavior_change R-T3：用户 2026-04-14 明确批准（"两个都批准"）
R-T3-followup（subject_teacher 2→4 扩展）用户 2026-04-14T07:45 精确批准 F005，随 R-T3 一同落地。

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
git log --oneline -3
```

**审查清单:**
- ✓ academic_director 渲染 7 个 conduct 菜单项
- ✓ grade_leader 渲染 5 个 conduct 菜单项
- ✓ subject_teacher 渲染 4 个 conduct 菜单项（R-T3-followup，2026-04-14T07:45 用户已批准 F005）
- ✓ lesson_prep_leader 渲染 0 个 conduct 菜单项
- ✓ 非 conduct 角色（teaching_research_leader / parent）无 conduct 菜单
- ✗ subject_teacher 错误渲染 9 项 → 说明 filter 漏 perm 判断
- ✗ academic_director 仍渲染 3 项 → 说明 hasPermission 未生效 / 未迁移出 VIEWER 档
- 关键行为：教务主任点击 /conduct/points 前端路由守卫放行 + 后端 API 200 OK

**边界条件:**
- 空输入（`filterConductByRole('unknown_role')`）→ 返回 []（`hasPermission` 对未知角色返 false）
- 单元素（某角色仅 view_conduct 权限）→ 过滤得 3 项（概览 / 记录 / 排行榜，均 perm: 'view_conduct'）
- 完整（platform_admin 有全 5 conduct perm）→ 9 项全出
- 非法 perm 字段（CONDUCT_ITEMS 某项写了不存在的 perm 'xxx'）→ 该项对任何角色都不显示（但这是 bug，应加契约测试）
- 角色切换（auth.currentRole 变更）→ sidebar 重算（Pinia reactive）

**测试契约（5 字段，behavior_change R-T3）:**

1. **academic_director 从 3 项扩到 7 项**
   - 入口: `getSidebarItems('academic_director').filter(i => i.moduleCode === 'conduct')`
   - 反例: 错误实现仍 spread `CONDUCT_ITEMS_VIEWER` → 返回 3 项 → `expect(routes).toHaveLength(7)` FAIL
   - 边界: 7 项中必含 `/conduct/rules`（manage_conduct_rules）和 `/conduct/groups`（manage_conduct）；必不含 `/conduct/parents`（无 MANAGE_CONDUCT_PARENTS）
   - 回归: 防止后续改 academic_director 权限（如移除 manage_conduct_rules）而忘记更新 sidebar 逻辑
   - 命令: `npx vitest run src/__tests__/sidebarConfig.conduct.test.js -t "academic_director 改后"`

2. **subject_teacher 从 2 项扩到 4 项（R-T3-followup）**
   - 入口: 同上，role='subject_teacher'
   - 反例: 若保守方案（allowed_roles 白名单）被采纳 → 仍返回 2 项（原 TEACHER 档）→ FAIL
   - 边界: 4 项必含 `/conduct`、`/conduct/points`、`/conduct/records`、`/conduct/rankings`
   - 回归: 若 Plan Review 改为保守方案，此测试预期改为 2 项 + allowed_roles 字段校验
   - 命令: `npx vitest run src/__tests__/sidebarConfig.conduct.test.js -t "subject_teacher 按权限"`

3. **lesson_prep_leader 保持 0 项（T1 依赖验证）**
   - 入口: role='lesson_prep_leader'
   - 反例: 若 T1 权限回收被回退（_TEACHER_BASE 加回 conduct）→ filter 派生出 4 项 → FAIL
   - 边界: 该角色其他非 conduct 菜单（如 /homework）应正常显示
   - 回归: 与 T1 test_lesson_prep_leader_no_view_conduct 联动回归
   - 命令: `npx vitest run src/__tests__/sidebarConfig.conduct.test.js -t "lesson_prep"`

4. **CONDUCT_ITEMS perm 合法性治理（R1-F007 入口级治理契约）**
   - 入口: `CONDUCT_ITEMS.forEach(item => expect(allPerms.has(item.perm)).toBe(true))`（从 ROLE_PERMISSIONS 聚合合法集）
   - 反例: 新增一项 `{ perm: 'manage_condut' }`（typo）→ allPerms 不含该字符串 → assert FAIL；无此治理测试时，9 角色矩阵快照测试因该项对所有角色均 false 而 PASS（静默失败）
   - 边界: 空 CONDUCT_ITEMS 列表应 PASS（vacuous truth）；ROLE_PERMISSIONS 空时所有 perm 字段都 FAIL（预期）
   - 回归: 防止后续新增菜单项 perm 字段拼错被 9 角色矩阵测试漏过
   - 命令: `npx vitest run src/__tests__/sidebarConfig.conduct.test.js -t "CONDUCT_ITEMS perm 合法性"`

5. **AppSidebar 入口级渲染（R1-F006 用户可触达入口）**
   - 入口: `mount(AppSidebar)` with `pinia.auth.currentRole='academic_director'` → `findAll('[data-module="conduct"]').length === 7`
   - 反例: 若 Step 5.3 漏改某 role 的 spread（如仍 `...CONDUCT_ITEMS_VIEWER`）→ 渲染 3 项 → length 断言 FAIL
   - 边界: `role='principal'` 应渲染 3 项；`role='lesson_prep_leader'` 应渲染 0 项；`role='homeroom_teacher'` 应渲染 9 项
   - 回归: 与 sidebarConfig 矩阵测试联动，防 config 层和渲染层分裂
   - 命令: `npx vitest run src/__tests__/AppSidebar.test.js -t "academic_director conduct seven items"`

---

## Task 6: 批次 1 收尾（state.json + design.md [实现完成] + CLAUDE.md 迁移，1 commit）

**Files:**
- Modify: `docs/plans/2026-04-14-conduct-roadmap-batch1-state.json`（**R1-F004**：Planner 在 Gate 1 PASS 后 Step 0 已创建；本 Task 仅把 Task 6 自身 status 置 completed + 最终 updated_at）
- Modify: `docs/plans/2026-04-14-conduct-roadmap-design.md`（§ 10 填 [实现完成]）
- Modify: `C:/Users/Administrator/CLAUDE.md`（进行中 → 已完成设计）

**性质:** 收尾，非 behavior_change。T1 级别。

**依赖:** Task 1-5 全部 completed + Gate 2 Code Review PASS。

### Steps

- [ ] **Step 6.1: 跑全量回归基线（R1-F006/F007 更新后数字）**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_conduct/ -q --tb=no 2>&1 | tail -3
```
Expected: `129 passed`（118 基线 + 3 T4 governance + 4 T1 helper + 1 T1 入口级 API 403 + 3 T2 入口级 = 129）。

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q 2>&1 | tail -3
```
Expected: `15 passed`。

Run:
```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/sidebarConfig.conduct.test.js src/__tests__/AppSidebar.test.js src/pages/parent/__tests__/ParentRules.spec.js src/__tests__/permissions.lesson_prep.test.js 2>&1 | tail -5
```
Expected: `29 passed`（13 基线 3 件套 + 10 T3 sidebarConfig 新增（9 矩阵 + 1 F007 perm 合法性）+ 1 T3 AppSidebar F006 入口级 + 5 T1 permissions.lesson_prep = 29）。

- [ ] **Step 6.2: 最终更新 state.json（Task 6 置 completed + 测试基线数字校准）**

**R1-F004 注：state.json 由 Planner 在 Gate 1 PASS 后的 Step 0 已创建（模板见本 plan § state.json 生命周期）；Task 1-5 已在各自 Steps N.0/N.final 迁移状态。本 Step 仅把 Task 6 自身置 completed + 同步最终 updated_at + 校准 test_baseline 数字。**

使用 Edit 工具打开 `docs/plans/2026-04-14-conduct-roadmap-batch1-state.json`，更新三处字段：

1. `tasks[5]`（id="6"，即"批次 1 收尾"）的 status：`"pending"` → `"completed"`
2. `test_baseline.conduct_backend`：`118` → `129`
3. `test_baseline.frontend_conduct_suite`：`13` → `29`

（`services: 15` 不变；`updated_at` 字段由 Step 6.5 统一更新为精确时间戳）

实际编辑的 state.json 最终样态如下（参考）：

```json
{
  "topic": "2026-04-14-conduct-roadmap-batch1",
  "plan_file": "docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md",
  "design_file": "docs/plans/2026-04-14-conduct-roadmap-design.md",
  "tasks": [
    {"id": "1", "desc": "T5 文档数字修正", "status": "completed"},
    {"id": "2", "desc": "T4 conduct MODULE.md 补全", "status": "completed"},
    {"id": "3", "desc": "T1 lesson_prep_leader conduct 权限回收", "status": "completed"},
    {"id": "4", "desc": "T2 AddPointsRequest.date → record_date", "status": "completed"},
    {"id": "5", "desc": "T3 sidebar 按 permissions 派生", "status": "completed"},
    {"id": "6", "desc": "批次 1 收尾", "status": "completed"}
  ],
  "test_baseline": {
    "conduct_backend": 129,
    "services": 15,
    "frontend_conduct_suite": 29
  },
  "updated_at": "<Step 6.5 精确时间戳>"
}
```

- [ ] **Step 6.3: 在 design.md §10 填 [实现完成]**

Run:
```bash
cd C:/Users/Administrator/edu-cloud && git log --oneline --grep="T[1-5]" -10
```
记录 T5 首个 commit hash 到 T3 最后 commit hash（批次 1 commits 范围）。

使用 Edit 工具：
- 文件：`docs/plans/2026-04-14-conduct-roadmap-design.md`
- old:
```markdown
## § 10. 实现完成标记

> 待批次 1 所有 gate PASS 后填写：
> `[YYYY-MM-DD HH:MM:SS 实现完成] Commits: {first}..{last} | Tests: conduct={N}, frontend={M}`
```
- new:
```markdown
## § 10. 实现完成标记

> [2026-04-14 HH:MM:SS 批次 1 实现完成] Commits: <first>..<last> | Tests: conduct=129, services=15, frontend_conduct_suite=29
>
> 5 Tasks 全部 completed，Gate 1 Plan Review PASS，Gate 2 Code Review PASS。
> 行为变更审批 R-T1/R-T2/R-T3 均 resolved-correct。R-T3-followup（subject_teacher 2→4）
> 在 Code Review 阶段单独确认后 resolved-correct。
```

（HH:MM:SS 由 Step 6.5 commit 前跑 `date '+%Y-%m-%d %H:%M:%S'` 填入）

- [ ] **Step 6.4: 迁移 CLAUDE.md 进行中 → 已完成设计**

使用 Edit 工具，`C:/Users/Administrator/CLAUDE.md`:
- old（进行中设计段的 conduct-roadmap 条目）:
```markdown
- **德育板块统筹规划路线图（conduct-roadmap）[批次 1 draft]**: ...
```
- new（移除，因批次 1 已完成）:
```markdown
（当前无进行中设计）
```

使用 Edit 工具在"已完成设计"段末尾（L35 之后）追加：
```markdown
- **德育板块统筹规划路线图 批次 1 [实现完成]**: R3 PASS 后的全景治理批次 1 — T5 文档数字修正 / T4 conduct MODULE.md 补全 / T1 lesson_prep_leader 权限回收（C 方案，behavior_change R-T1）/ T2 AddPointsRequest.date→record_date（修 pydantic v2 field-type shadowing bug，behavior_change R-T2）/ T3 sidebar 按 permissions 派生（academic_director 入口 3→7，grade_leader 3→5，subject_teacher 2→4 per R-T3-followup，behavior_change R-T3）。5 Tasks / 7 commits / Gate 1 R2 PASS + Gate 2 PASS。129 conduct tests + 15 services + 29 frontend conduct suite = 173 passed。批次 2 (D-005/D-009/D-010 运维就绪) 与批次 3 (D-006/D-007/D-008 真实验证) 占位等待启动。真源: `edu-cloud/docs/plans/2026-04-14-conduct-roadmap-design.md`
```

- [ ] **Step 6.5: 更新 state.json updated_at**

Run:
```bash
date '+%Y-%m-%d %H:%M:%S'
```
记录结果。使用 Edit 工具替换 state.json 的 `updated_at` 占位为该时间戳；同时 Edit design.md §10 的 HH:MM:SS 占位。

同时改 state.json 中最后一个 task 的 status:
- `{"id": "6", "desc": "批次 1 收尾", "status": "in_progress"}` → `"completed"`

- [ ] **Step 6.6: Commit 收尾**

```bash
cd C:/Users/Administrator/edu-cloud && git reset HEAD >/dev/null 2>&1 && \
  git add docs/plans/2026-04-14-conduct-roadmap-batch1-state.json docs/plans/2026-04-14-conduct-roadmap-design.md && \
  git diff --cached --name-only
```

```bash
git commit -m "$(cat <<'EOF'
chore(conduct-roadmap): 批次 1 [实现完成] — state.json + design.md §10 标记

5 Tasks 全部 completed：T5 文档 / T4 MODULE.md / T1 lesson_prep 权限回收 /
T2 record_date rename / T3 sidebar permissions 派生。

测试总计: conduct 129 + services 15 + frontend 29 = 173 passed。
Gate 1 Plan Review PASS + Gate 2 Code Review PASS。
L017 behavior_change 三项均 resolved-correct。

批次 2/3 占位等待。

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

另一个 commit 迁移 CLAUDE.md（全局级 repo）：
```bash
cd C:/Users/Administrator && git reset HEAD >/dev/null 2>&1 && \
  git add CLAUDE.md && \
  git diff --cached --name-only
```
```bash
git commit -m "$(cat <<'EOF'
docs: conduct-roadmap 批次 1 [实现完成] — 进行中 → 已完成设计迁移

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

**审查清单:**
- ✓ state.json 的 tasks 全部 status=completed
- ✓ design.md §10 含 [实现完成] + 具体 commit range + test 数字
- ✓ CLAUDE.md 进行中设计 = "（当前无进行中设计）"
- ✓ CLAUDE.md 已完成设计段 含 "批次 1 [实现完成]" 条目
- ✗ state.json updated_at 是占位字符串未替换 → 污染记录
- 关键行为：后续 planner 读 CLAUDE.md 得到批次 1 已完成 + 批次 2/3 待启动 的准确状态

**边界条件:** N/A（纯文档收尾）

**测试契约:** N/A（非 behavior_change）

---

## Self-Review（按 writing-plans 要求）

### 1. Spec coverage

对照 design.md 批次 1 T1-T5：

| design Task | plan Task 编号 | 覆盖情况 |
|---|---|---|
| T5 文档数字修正 | Task 1 | ✅ |
| T4 MODULE.md | Task 2 | ✅ |
| T1 lesson_prep_leader 回收 | Task 3 | ✅ |
| T2 AddPointsRequest rename | Task 4 | ✅ |
| T3 sidebar 按 permissions 派生 | Task 5 | ✅ |
| 批次 1 退出条件（§ 6.1） | Task 6 | ✅ |

### 2. Placeholder scan

- ❌ 有几个**计划内占位**（Step 6.2 state.json `updated_at`、Step 6.3 design.md §10 时间戳、Step 6.6 commit message 中的 commit range）——这些是**运行时才能填**的时间戳和 hash，在 Step 6.5 有明确替换说明，符合 writing-plans 允许的"execution-time placeholder"模式（而非"设计/需求未定"的 TBD）。保留。
- ✅ 无 TBD / TODO / implement later
- ✅ 无 "Add appropriate error handling"（所有异常处理在测试契约里明确）
- ✅ 无 "Similar to Task N"（每个 Task 完整列 Files + Steps + 审查清单）
- ⚠ Step 4.7 有"若前端目前根本没传 date 字段"的分支——这是真实不确定性（前端可能已经没用这个字段），Step 4.1 的审计命令会给出确定答案。保留。

### 3. Type consistency

- `ROLE_PERMISSIONS` / `hasPermission` / `has_permission` 在 Task 3 + Task 5 一致（前端 js + 后端 py）
- `_TEACHER_BASE` 在 Task 3 用作 frozenset-like 减法（`_TEACHER_BASE - {...}`），前端用 `.filter()` —— 后端是 `set`, 前端是 `Array`，各自符合语言惯例 ✅
- `record_date`（而非 `recordDate` 或 `record-date`）在 Task 4 的 schemas.py + admin_service.py + frontend 一致（Python snake_case）
- `CONDUCT_ITEMS` / `filterConductByRole` 在 Task 5 定义，在同 Task 后续 spread 使用，一致
- `module_code: 'conduct'` 在 Task 5 的 CONDUCT_ITEMS 每项 + Task 2 的 MODULE.md owns_routes、exposes.ai_tools 一致

### 4. Gate 相关

- 本 plan 需在 commit 后立即通过 codex-review (plan) 拿 Gate 1 PASS
- 每 Task 的 commit 分别触发 scope_guard.py（检查 staged 范围）和 logging_guard.py（无裸 print）
- Gate 2 Code Review 在 Task 1-5 全 commit 后触发（单批次 T3，一轮 review）
- R-T3-followup（subject_teacher 2→4）已于 2026-04-14T07:45 用户批准 F005（gates.json），Gate 1 无待定审批

---

## R1 Findings 处置总结（2026-04-14 Gate 1 Plan Review；R2 修订 2026-04-17）

Gate 1 R1 结论: FAIL（9 finding，HIGH×4 / MED×5，raw log SHA256 `9554e5ee...`）。R2 修订针对每项真正回填到主 Task 正文（非附录声明）：

| ID | Sev | Cat | Type | 状态 | 处置位置（R2 修订后的主正文回填） |
|---|---|---|---|---|---|
| F001 | HIGH | code-bug | defect_fix | resolved-inline | Task 4 Files L690 已列 `admin_router.py:115,137` + Step 4.5 两处 `record_date=data.date` → `record_date=data.record_date`；service 层 L254/271 已是目标状态 verify-only；Task 4 commit message 已更正描述 |
| F002 | HIGH | test-gap | defect_fix | resolved-inline | Task 4 Step 4.2 测试代码用入口级 POST 200 + DB readback，fixture `homeroom_headers`，测试文件锁定 `test_admin_crud_api.py`；Step 4.6/4.9 命令与 git add 一致使用 crud_api 文件名 |
| F003 | MED | code-bug | defect_fix | resolved-inline | Task 2 Step 2.7 脚本路径 `scripts/governance/aggregate_modules.py` |
| F004 | MED | code-bug | defect_fix | **resolved-inline R2** | **R2 已真正回填到主 Task 正文**：Task 1-5 每个都插入 Step N.0（pending→in_progress）+ Step N.final（in_progress→completed）Python inline 脚本；每个 Task 的 commit Step git add 清单都已加入 state.json；Task 6 Step 6.2 改为"更新"（非 Create）；Files 段同步为 Modify。详见上方 § state.json 生命周期 |
| F005 | HIGH | design-concern | **behavior_change** | **approved** | 用户 2026-04-14 07:45:00 精确回复"批准 F005"，subject_teacher 2→4 扩展落地；R2 清理 3 处残留"待二次确认"措辞（L1088 扩展说明改为"已批准"；Task 5 commit message 改为"精确批准"；Gate 相关段改为"无待定审批"）；design.md §9 R-T3-followup 表格行同步改 approved |
| F006 | MED | test-gap | defect_fix | **resolved-inline R2** | **R2 已真正回填**：Task 3 Files L442 列 `test_admin_crud_api.py` + 新 Step 3.4a 写 `test_lesson_prep_leader_cannot_call_conduct_api` API 403 入口级 + Step 3.4b 跑 PASS + 测试契约新增第 4 slice；Task 5 Files 列 `AppSidebar.test.js` + 新 Step 5.2b 写 `test_academic_director_conduct_seven_items` 入口级 + 测试契约新增第 5 slice；Step 5.3 说明 `data-module` 属性要求 |
| F007 | MED | test-gap | defect_fix | **resolved-inline R2** | **R2 已真正回填**：Task 5 新 Step 5.2a 写 `CONDUCT_ITEMS.perm` 合法性治理测试到 `sidebarConfig.conduct.test.js`；Step 5.3 CONDUCT_ITEMS 声明改为 `export const`；测试契约新增第 4 slice；Files 段标注 R1-F007 要求 export |
| F008 | HIGH | design-concern | defect_fix | **resolved-inline R2** | **R2 按 schema 重写 Contract Pack**：invariants 用 `statement`（非 `rule`）；verification 值取 `pending_test`（非嵌套 `{type: new_test}`）；`risk_modules[].module`（非 `path`）；`test_debt[].deadline` 为纯 `YYYY-MM-DD`（TD-001/002/003=2026-05-15, TD-004=2026-05-01, TD-005=2026-12-31 远期占位，deferred 在 reason 里说明） |
| F009 | MED | code-bug | defect_fix | resolved-in-design | `docs/plans/2026-04-14-conduct-roadmap-design.md` §8 L393 已承认 workspace CLAUDE.md 为跨 repo audit trail 合法产出；plan Task 6 Step 6.4 与之对齐 |

### § state.json 生命周期（F004 修复）

**旧模型（错）**：state.json 在 Task 6 才创建并一次性回填完成状态——执行期无状态可迁。

**新模型（R1 修复后）**：

```
Gate 1 Plan Review PASS
  ↓
Planner Step 0: 生成 state.json 初始版（所有 Task status=pending）并 commit（与 final plan 一起，作为 Gate 1 PASS 后首批产物）
  ↓
Executor 在每 Task 起始:
  - Step N.0: Edit state.json 把本 Task status 从 pending → in_progress，更新 updated_at
Executor 完成 Task 所有原 Step 后:
  - Step N.final: Edit state.json 把本 Task status 从 in_progress → completed，更新 updated_at
  ↓
Task 1→5 顺序推进（同一时刻只允许一个 in_progress）
  ↓
Task 6 收尾:
  - 最终 updated_at 回填 + [实现完成] 标记（state.json 结构不改，只更新字段）
```

每个 Task 的 Steps 增加 2 个 state.json 管理 step（入口 + 出口）。**R2 已真正回填到各 Task 主 Steps 正文**（不是仅附录说明），实际编号如下：
- Task 1 (T5): 新增 Step 1.0（pending→in_progress）+ Step 1.5a（in_progress→completed）；Step 1.6 commit 的 git add 已包含 state.json
- Task 2 (T4): 新增 Step 2.0 + Step 2.8a；Step 2.9 commit git add 已加 state.json
- Task 3 (T1，双 commit): 新增 Step 3.0（Task 起始 in_progress）+ Step 3.9a（Task 结束 completed）；Step 3.5 后端 commit staged state.json（in_progress 状态）；Step 3.10 前端 commit staged state.json（completed 状态）
- Task 4 (T2): 新增 Step 4.0 + Step 4.8a；Step 4.9 commit git add 已加 state.json
- Task 5 (T3): 新增 Step 5.0 + Step 5.6a（在 R1-F006/F007 新增的 Step 5.2a/5.2b 之外）；Step 5.7 commit git add 已加 state.json
- Task 6 保持，Step 6.2 已改为"最终更新 state.json（Task 6 置 completed + 测试基线数字校准）"而非"创建"

Executor 编辑 state.json 通用模板：

```python
# Step N.0 (Task 起始) - 把 pending → in_progress
import json, datetime, pathlib
STATE = pathlib.Path("docs/plans/2026-04-14-conduct-roadmap-batch1-state.json")
state = json.loads(STATE.read_text(encoding="utf-8"))
for task in state["tasks"]:
    if task["id"] == "{N}":  # 本 Task id
        task["status"] = "in_progress"
state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
# 不单独 commit，此 Edit 与本 Task 首个功能 commit 合并 staged
```

Step N.final 把 `in_progress → completed` 逻辑相同。

**Planner 在 Gate 1 PASS 后的 Step 0 产物:**

```json
{
  "topic": "conduct-roadmap-batch1",
  "plan_file": "docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md",
  "design_file": "docs/plans/2026-04-14-conduct-roadmap-design.md",
  "tasks": [
    {"id": "1", "desc": "T5 文档数字修正", "status": "pending"},
    {"id": "2", "desc": "T4 conduct MODULE.md 补全", "status": "pending"},
    {"id": "3", "desc": "T1 lesson_prep_leader conduct 权限回收", "status": "pending"},
    {"id": "4", "desc": "T2 AddPointsRequest.date → record_date", "status": "pending"},
    {"id": "5", "desc": "T3 sidebar 按 permissions 派生", "status": "pending"},
    {"id": "6", "desc": "批次 1 收尾", "status": "pending"}
  ],
  "test_baseline": {
    "conduct_backend": 118,
    "services": 15,
    "frontend_conduct_suite": 13
  },
  "updated_at": "<Gate 1 PASS 后跑 date '+%Y-%m-%d %H:%M:%S' 填入>"
}
```

### § 入口级测试补充（F006 修复）

**T1 入口级测试**（追加到 `tests/test_conduct/test_admin_crud_api.py`，Task 3 的 Step 3.11 改为同时跑此测试）:

```python
@pytest.mark.anyio
async def test_lesson_prep_leader_cannot_call_conduct_api(
    client, db, school_class_student,
):
    """T1 入口级（R1-F006）: lesson_prep_leader 调 conduct API 返回 403（权限守卫层面）."""
    from edu_cloud.modules.student.models import UserRole, User
    from edu_cloud.shared.auth import create_access_token
    import uuid
    school, cls, _ = school_class_student

    # 构造 lesson_prep_leader user + role (按 conftest fixture 模式)
    user = User(id=str(uuid.uuid4()), username=f"lpl_{uuid.uuid4().hex[:8]}", hashed_password="x", display_name="备课组长")
    db.add(user)
    await db.flush()
    role = UserRole(id=str(uuid.uuid4()), user_id=user.id, role="lesson_prep_leader", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()

    token = create_access_token({"sub": user.id, "active_role_id": role.id})
    resp = await client.get(
        f"/api/v1/conduct/classes/{cls.id}/rankings/students",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

**T3 入口级测试**（追加到 `frontend/src/__tests__/AppSidebar.test.js`）:

```javascript
import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import AppSidebar from '@/components/shell/AppSidebar.vue'

it('academic_director 渲染侧边栏 conduct 段含 7 项（R1-F006 入口级）', async () => {
  const pinia = createTestingPinia({
    initialState: { auth: { currentRole: 'academic_director', user: { id: 'u1' } } },
  })
  const wrapper = mount(AppSidebar, { global: { plugins: [pinia] } })
  const conductItems = wrapper.findAll('[data-module="conduct"]')
  expect(conductItems).toHaveLength(7)
})
```

（若 AppSidebar.vue 未给菜单项加 `data-module` 属性，Task 5 Step 5.3 改 sidebarConfig 的同时需让渲染层带出该属性；否则改为按 label 文字查找）

### § CONDUCT_ITEMS 治理测试（F007 修复）

**Task 5 新增 Step 5.2a（夹在 5.2 测试失败后，5.3 实现改动前）：**

追加到 `frontend/src/__tests__/sidebarConfig.conduct.test.js`:

```javascript
import { ROLE_PERMISSIONS } from '@/config/permissions'
import { CONDUCT_ITEMS } from '@/config/sidebarConfig' // Task 5 Step 5.3 需 export CONDUCT_ITEMS

describe('T3 (R1-F007) — CONDUCT_ITEMS perm 合法性治理', () => {
  it('CONDUCT_ITEMS 每个 perm 字段都在合法 permission 集，防 typo 静默失败', () => {
    const allPerms = new Set()
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      for (const p of perms) allPerms.add(p)
    }
    for (const item of CONDUCT_ITEMS) {
      expect(allPerms.has(item.perm)).toBe(true)
    }
  })
})
```

Task 5 Step 5.3 的 CONDUCT_ITEMS 定义需改为 `export const CONDUCT_ITEMS = [...]`（供测试文件 import）。

### § Contract Pack（F008 修复 R2，按 `~/.claude/config/contract-pack-schema.md`）

schema 对齐：invariants 用 `statement`（非 rule）；verification 取 `existing_test|pending_test|uncovered`；risk_modules 用 `module`（非 path）；test_debt.deadline 为纯 `YYYY-MM-DD` 日期。

```yaml
contract_pack:
  invariants:
    - id: INV-T1-001
      statement: "lesson_prep_leader 永不拥有 VIEW_CONDUCT 或 MANAGE_CONDUCT"
      rationale: "备课组长职责是学科教研，不碰德育（2026-04-14 T1=C 用户批准）"
      verification: pending_test
      test_ref: "tests/test_conduct/test_permissions.py::test_lesson_prep_leader_no_view_conduct,test_lesson_prep_leader_no_manage_conduct"
    - id: INV-T1-002
      statement: "subject_teacher 与 homeroom_teacher 未被 T1 误伤（仍拥有 conduct 基础权限）"
      verification: pending_test
      test_ref: "tests/test_conduct/test_permissions.py::test_subject_teacher_still_has_conduct,test_homeroom_teacher_still_has_conduct"
    - id: INV-T1-003
      statement: "lesson_prep_leader 调 conduct API 入口被拒（403），ToolAccessResolver 过滤 6 conduct AI tools"
      rationale: "权限回收需在入口层面生效（F006 入口级验证）"
      verification: pending_test
      test_ref: "tests/test_conduct/test_admin_crud_api.py::test_lesson_prep_leader_cannot_call_conduct_api"
    - id: INV-T2-001
      statement: "AddPointsRequest 的公开字段名不与 datetime.date 类型名冲突"
      rationale: "pydantic v2 字段名遮蔽 type 导致 Optional[None] 解析，阻断客户端传真实日期"
      verification: pending_test
      test_ref: "tests/test_conduct/test_admin_crud_api.py::test_add_points_with_record_date_field"
    - id: INV-T2-002
      statement: "AddPointsRequest 的 record_date 传入值真实落库到 ConductRecord.date（入口级契约）"
      verification: pending_test
      test_ref: "tests/test_conduct/test_admin_crud_api.py::test_add_points_with_record_date_field"
    - id: INV-T3-001
      statement: "sidebar conduct 菜单项的可见性由 permission 派生，不由角色-档硬编码"
      rationale: "三档 FULL/VIEWER/TEACHER 粒度过粗，教务主任/年级组长有权无路"
      verification: pending_test
      test_ref: "frontend/src/__tests__/sidebarConfig.conduct.test.js"
    - id: INV-T3-002
      statement: "CONDUCT_ITEMS[*].perm 字段必须来自 ROLE_PERMISSIONS 定义的 permission 集"
      rationale: "typo 会让菜单项静默对所有角色不可见（F007 根因 — hasPermission 对未知 perm 返 false）"
      verification: pending_test
      test_ref: "frontend/src/__tests__/sidebarConfig.conduct.test.js::test_conduct_items_perm_valid"
    - id: INV-T3-003
      statement: "academic_director 登录后侧边栏 conduct 段渲染出 7 项（入口级）"
      verification: pending_test
      test_ref: "frontend/src/__tests__/AppSidebar.test.js::test_academic_director_conduct_seven_items"
    - id: INV-T4-001
      statement: "conduct MODULE.md 的 owns_tables 与 models.py __tablename__ 集合严格一致"
      verification: pending_test
      test_ref: "tests/test_conduct/test_module_governance.py::test_owns_tables_matches_orm_definitions"
    - id: INV-T4-002
      statement: "conduct MODULE.md 的 depends_on.ai_tools 与 ai.registry 实际注册的 conduct tools 严格一致"
      verification: pending_test
      test_ref: "tests/test_conduct/test_module_governance.py::test_exposes_ai_tools_matches_registry"

  counter_examples:
    - id: CE-001
      scenario: "开发者未来把 _TEACHER_BASE 从 set 改为 frozenset 或 list"
      break_invariant: INV-T1-001
      tests_that_still_pass: "has_permission 成员断言仍 PASS（frozenset/list 都支持成员判定，但 set 减法 - 对 list 会 TypeError）"
      mitigation: "批次 2 D-005 加 sentinel: isinstance(_TEACHER_BASE, (set, frozenset)) 或显式过滤"
      status: deferred
    - id: CE-002
      scenario: "开发者在 CONDUCT_ITEMS 新增菜单项时 perm 字段拼错（如 manage_condut）"
      break_invariant: INV-T3-002
      tests_that_still_pass: "若无 INV-T3-002 治理测试，9 角色 × 矩阵快照测试仍 PASS（该项对所有角色不可见被误判为设计如此）"
      mitigation: "INV-T3-002 治理测试在 CI 立即失败（F007 修复已加）"
      status: resolved
    - id: CE-003
      scenario: "开发者 rename AddPointsRequest.record_date 但忘记同步 admin_router 两处（复现 F001 根因）"
      break_invariant: INV-T2-001
      tests_that_still_pass: "若只跑 service 层单测或直接调用 service.add_points(record_date=...)，发现不了 router 层 data.record_date AttributeError"
      mitigation: "T2 入口级测试 POST 200 + DB readback（F001+F002 修复）+ admin_router.py 纳入 Task 4 Files 范围"
      status: resolved
    - id: CE-004
      scenario: "subject_teacher 的权限被未来某次重构从 _TEACHER_BASE 拿掉 view_conduct"
      break_invariant: INV-T1-002
      tests_that_still_pass: "若只测 lesson_prep_leader，不测 subject_teacher，无法发现基线角色被误伤"
      mitigation: "test_subject_teacher_still_has_conduct + test_homeroom_teacher_still_has_conduct 防基线角色回退"
      status: resolved

  risk_modules:
    - module: src/edu_cloud/core/permissions.py
      reason: "T1 改动 ROLE_PERMISSIONS（公开 RBAC 契约，8 角色 × 5 permission 矩阵）"
      tier: T2
    - module: src/edu_cloud/modules/conduct/schemas.py
      reason: "T2 rename 改动 pydantic schema（公开 HTTP API 契约）"
      tier: T2
    - module: src/edu_cloud/modules/conduct/admin_router.py
      reason: "T2 rename 连带必改，公开 POST /records 入口"
      tier: T2
    - module: src/edu_cloud/modules/conduct/MODULE.md
      reason: "T4 新增治理基础设施，module_governance_guard 的契约依赖"
      tier: T2
    - module: frontend/src/config/sidebarConfig.js
      reason: "T3 架构级重构 — 影响所有角色 UI 可见性（9 角色 × 9 菜单矩阵）"
      tier: T3
    - module: frontend/src/config/permissions.js
      reason: "T1 前端镜像后端 RBAC"
      tier: T2

  test_debt:
    - id: TD-001
      item: "家长端 Playwright E2E（5 核心流程：注册→邀请码→绑定→概览→记录→排行榜→班规）"
      reason: "归属批次 3 D-006；批次 1 scope 外，批次 3 启动时补齐"
      deadline: "2026-05-15"
    - id: TD-002
      item: "AI Chat 真实调用 conduct Agent 工具（rankings/records/summary 数据返回 assertion）"
      reason: "归属批次 3 D-007；批次 1 仅验 Agent 工具注册 + F003 scope 红测，不验数据正确性"
      deadline: "2026-05-15"
    - id: TD-003
      item: "Excel 导出中文 sheet 名 / UTF-8 / 日期 range 真实下载验证"
      reason: "归属批次 3 D-008；批次 1 scope 外"
      deadline: "2026-05-15"
    - id: TD-004
      item: "_TEACHER_BASE 类型合约 sentinel（防 set→frozenset/list 重构破坏集合减法）"
      reason: "归属批次 2 D-005；本 plan 仅以回归测试兜底"
      deadline: "2026-05-01"
    - id: TD-005
      item: "T2 record_date 业务校验（不应晚于今日或早于班级学期起始）"
      reason: "业务校验留未来增强，当前允许任意合法日期；deferred（无阻塞需求），远期占位日期"
      deadline: "2026-12-31"

contract_pack_version: "1.0"
contract_pack_source: "~/.claude/config/contract-pack-schema.md"
```

---

## Plan complete

Plan saved to `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md`.

**下一步选项:**

1. **新会话 executing-plans**（项目 CLAUDE.md T3 硬约束：T3 plan 必须新会话执行，禁止同会话执行）—— 我会输出 Executor 启动 prompt + handoff 交接卡，你另开一个 Claude 窗口执行。

2. **先做 Gate 1 Plan Review**（codex-review skill 审本 plan）—— 拿到 PASS 再启新会话 Executor；若 FAIL 在本会话修 plan。按项目流程这是**必经步骤**。

推荐：先做 Gate 1 Plan Review（流程必需），然后输出 Executor 启动 prompt。
