<!-- pre-takeover: archived for history, not active spec -->
---
type: design
topic: conduct-roadmap
created: 2026-04-14 06:39:01
status: draft
T-level: T3
batches: 3
supersedes_handoff: docs/plans/2026-04-13-conduct-next-phase-handoff.md
---

# 德育板块统筹规划路线图（批次 1 详细 + 批次 2/3 占位）

## § 0. 上下文

### 0.1 前置状态（2026-04-14，事实基线）

- 德育 R1+R2+R3 已 PASS，commits `e584e6a..93f0b60`（2026-04-13）
- 默认上线落地：`a117222` DEFAULT_ENABLED 加 conduct + `d1bfd10` sidebar 挂载补齐
- **测试基线实跑（2026-04-14 本会话 verified）**：
  - conduct 后端: **118 passed, 237.52s, exit 0**
  - services（school_settings + homework_permissions）: **15 passed, 10s, exit 0**
  - frontend conduct 3 件套 (sidebarConfig.conduct / AppSidebar / ParentRules): 13 passed（未在本会话跑）
- 实际代码规模（2026-04-14 wc 统计）:
  - 后端 `modules/conduct/`: 11 文件 / 2356 行
  - 前端管理端 `pages/conduct/`: 9 Vue / 1703 行
  - 前端家长端 `pages/parent/`: 8 Vue / 748 行
  - 测试 `tests/test_conduct/`: 8 文件 / 1867 行
  - **总 6734 行**
- 39 API 端点（admin 28 + parent 11）
- 8 ORM 表（student_profiles + 7 conduct_*）
- 6 Agent 工具（L2_conduct ×5 + L6_profile ×1）

### 0.2 统筹路线图决策（2026-04-14）

- 分 **3 批次**：批次 1 治理最小集 → 批次 2 运维就绪 → 批次 3 真实验证
- 每批独立 `design-bN.md + plan-bN.md + gates-bN.json`
- 批次间 **可中止**：批次 1 PASS 后可决定不做批次 2/3
- 本 design 覆盖：批次 1 详细设计 + 批次 2/3 目标占位

### 0.3 批次 1 用户决策（2026-04-14，L017 批准记录）

| Task | 决策 | 性质 |
|---|---|---|
| T1 lesson_prep_leader conduct | **C**（回收后端权限） | behavior_change 批准 |
| T2 AddPointsRequest rename | **批准** | behavior_change 批准 |
| T3 sidebar 按 permissions 派生 | **批准** | behavior_change 批准 |
| T4 conduct MODULE.md | 默认 | governance 添加，非 behavior_change |
| T5 文档数字修正 | 默认 | 纯文档，非 behavior_change |

## § 1. 真实现状盘点（相对 handoff 的事实核对）

### 1.1 权限矩阵（前后端已一致）

**关键发现**：handoff D-003 声称 principal / academic_director 前后端不一致——**事实上完全一致**，handoff 描述过时（可能是 sidebar 挂载前的状态）。

真正的治理债是 **sidebar 粒度 vs permissions 粒度不匹配**：

| 角色 | permissions（5 权限组合） | sidebar 挂入口 | 差距 |
|---|---|---|---|
| platform_admin / district_admin | 全 5 权限 | FULL 9 项 | ✅ |
| principal | VIEW+EXPORT (2) | VIEWER 3 项 | ✅ |
| academic_director | VIEW+MANAGE+RULES+EXPORT (4) | VIEWER 3 项 | ❌ 少 4 项（积分操作/班规/记录/小组） |
| teaching_research_leader | 无 | 无 | ✅ |
| grade_leader | VIEW+MANAGE+EXPORT (3) | VIEWER 3 项 | ❌ 少 2 项（积分操作/记录） |
| lesson_prep_leader | VIEW+MANAGE (2) | **无** | ❌ 有权无路（T1 决策 C 回收权限） |
| homeroom_teacher | _TEACHER_BASE + RULES+PARENTS+EXPORT | FULL 9 项 | ✅ |
| subject_teacher | VIEW+MANAGE (2) | TEACHER 2 项 | ✅ |
| parent | VIEW（家长端独立路由） | 不走 sidebar | ✅ |

### 1.2 Handoff deferred 项重分级（12 项）

| ID | 原 P | 事实核对 | 新 P | 归属批次 |
|---|---|---|---|---|
| D-001 Alembic SQLite | P0 | 外部依赖（Migration Gate Repair 自动接线） | — | 不主动做 |
| D-002 AddPointsRequest.date | P0 | ✅ verified（L2+L38 同名遮蔽），Agent 不影响 | P1 | **批次 1 T2** |
| D-003 权限镜像 | P1 | ❌ 已一致（作废） | — | 不做 |
| **D-003' sidebar × permissions**（新） | — | ✅ 3 角色有权无路 | P1 | **批次 1 T3** |
| D-004 lesson_prep sidebar | P1 | 需决策 | 决策完成 | **批次 1 T1=C** |
| D-005 防退化 sentinel | P1 | ✅ 存在 | P1 | 批次 2 |
| D-006 家长端 E2E | P2 | ✅ 缺 | P2 | 批次 3 |
| D-007 Agent happy-path | P2 | ✅ 缺 | P2 | 批次 3 |
| D-008 Excel UTF-8 实测 | P2 | ✅ 缺 | P2 | 批次 3 |
| D-009 F007 同模式横扫 | P3 | ✅ 存在 | P3 | 批次 2 |
| D-010 seed_menus 加 conduct | P3 | ✅ 已识别 | P3 | 批次 2 |
| **D-011 conduct MODULE.md**（新） | — | ✅ 缺失（grading + pipeline 已有） | P1 | **批次 1 T4** |
| **D-012 文档数字漂移**（新） | — | ✅ CLAUDE.md 120 / handoff 120 / 实跑 118 | P3 | **批次 1 T5** |

## § 2. 路线图（3 批次）

### 2.1 批次间依赖关系

```
批次 1 (治理最小集) ──┬──→ 批次 2 (运维就绪)
                     │        ├─ D-005 sentinel（批次 1 契约定型后做）
                     │        ├─ D-009 F007 横扫（独立）
                     │        └─ D-010 seed_menus（依赖 T3 sidebar 定型）
                     │
                     └──→ 批次 3 (真实验证)
                              ├─ D-006 家长端 E2E（依赖 T2 API 契约稳定）
                              ├─ D-007 Agent happy-path（独立）
                              └─ D-008 Excel UTF-8（独立）
```

### 2.2 批次 1 目标（本 design § 3 详细）

消除 API 契约漂移（T2）+ 菜单入口治理债（T1+T3）+ 模块治理债（T4）+ 文档事实漂移（T5）

### 2.3 批次 2 目标（占位，批次 1 PASS 后 refine）

- **D-005** 为 `check_class_scope` / `check_resource_class` / AES-256-GCM 加密路径补 sentinel 规则（高风险契约防退化）
- **D-009** analytics / statistics / profile 等 service 抽检 F007 同模式 test-gap（单学生零积分型断言不足）
- **D-010** `scripts/seed_menus.py` MODULES 加 conduct 9 子菜单（协同 haofenshu-phase1 动态菜单切换）

### 2.4 批次 3 目标（占位，批次 1+2 PASS 后 refine）

- **D-006** 家长端 5 核心流程 Playwright E2E（注册→邀请码→绑定→概览→记录→排行榜→班规）
- **D-007** AI Chat 真实调用 Agent conduct 工具（rankings/records/summary 数据返回对齐验证）
- **D-008** Excel 导出中文 sheet 名 / UTF-8 / 日期 range 真实下载并开查

## § 3. 批次 1 详细设计

### 3.1 Task 清单（5 Tasks）

| Task | 性质 | T | behavior_change | 文件范围 | 依赖 |
|---|---|---|---|---|---|
| T1 lesson_prep_leader 权限回收 | 后端+前端 | T2 | ✅ | core/permissions.py + frontend/config/permissions.js + test | — |
| T2 AddPointsRequest.date rename（R2-F004 收窄仅后端） | 后端 | T2 | ✅ | conduct/schemas.py + admin_router.py:115,137（R1-F001）；admin_service.py verify-only；不改前端 | — |
| T3 sidebar 按 permissions 派生（R2-F003 扩容视图层） | 前端重构 | T3 | ✅ | sidebarConfig.js + AppSidebar.vue（data-module 视图层）+ 矩阵测试 + AppSidebar.conduct.test.js 新文件 | T1 |
| T4 conduct MODULE.md 补全 | 治理 | T2 | ❌ | modules/conduct/MODULE.md（新建） + governance 巡检 | — |
| T5 文档数字修正 | 纯文档 | T1 | ❌ | CLAUDE.md + next-phase handoff | — |

### 3.2 T1 — lesson_prep_leader conduct 权限回收

**Before**：`lesson_prep_leader: _TEACHER_BASE.copy()`（含 VIEW_CONDUCT + MANAGE_CONDUCT，源自 _TEACHER_BASE 共享）

**After**：`lesson_prep_leader` 从 _TEACHER_BASE 派生但移除 conduct 相关权限

**代码改动**：
- `src/edu_cloud/core/permissions.py` L240: `_TEACHER_BASE.copy()` → `_TEACHER_BASE - {Permission.VIEW_CONDUCT, Permission.MANAGE_CONDUCT}`
- `frontend/src/config/permissions.js` L59: `[..._TEACHER_BASE]` → 过滤掉 view_conduct / manage_conduct
- sidebar 保持无挂载（T3 范围内一并处理）

**审查清单**：
- ✓ `has_permission('lesson_prep_leader', Permission.VIEW_CONDUCT) is False`
- ✓ `has_permission('lesson_prep_leader', Permission.MANAGE_CONDUCT) is False`
- ✓ `has_permission('subject_teacher', Permission.VIEW_CONDUCT) is True`（未误伤其他 _TEACHER_BASE 角色）
- ✓ `has_permission('homeroom_teacher', Permission.VIEW_CONDUCT) is True`（班主任不变）
- ✗ lesson_prep_leader 调 conduct API → 403（require_view_conduct 依赖失败）

**关键行为（批次 1 范围）**：备课组长调 conduct HTTP API 入口被拒（403）。**AI Chat ToolAccessResolver 过滤 conduct 工具集 deferred 到 TD-006 批次 3 D-007 独立验证**，不在批次 1 退出条件内。

**边界条件**：
- `_TEACHER_BASE` 成员集运算结果必须不影响其他教师角色（subject_teacher / homeroom_teacher / lesson_prep_leader 各自独立 copy 后再删除）
- 若 `_TEACHER_BASE` 未来新增权限，lesson_prep_leader 自动继承（但仍排除 conduct）

### 3.3 T2 — AddPointsRequest 字段 rename

**Before**：
```python
# schemas.py L2
from datetime import date
# L33-38
class AddPointsRequest(BaseModel):
    ...
    date: Optional[date] = None  # pydantic v2 字段名遮蔽类型名 → Optional[None]，422 "Input should be None"
```
客户端传 `{"date": "2026-04-14"}` 被 422 拒绝；前端 `ConductPoints.vue` 无法补录历史日期积分。

**After**：
```python
# schemas.py L2
from datetime import date as _date_type
# L33-38
class AddPointsRequest(BaseModel):
    ...
    record_date: Optional[_date_type] = None
```

**代码改动（R2-F004 范围收窄，后端 API 契约修复）**：
- `src/edu_cloud/modules/conduct/schemas.py`: type import 别名 + 字段 rename
- `src/edu_cloud/modules/conduct/admin_router.py:115,137`: `record_date=data.date` → `record_date=data.record_date`（R1-F001 关键补充）
- `src/edu_cloud/modules/conduct/admin_service.py`: L254/271 已是 `record_date` 参数，verify-only 不改
- **不改前端**：`frontend/src/api/conduct.js` 和 `frontend/src/pages/conduct/ConductPoints.vue` 不在本批次范围。当前 UI 无日期控件，API 也不传 record_date；UI 补录日期是独立 behavior_change，需单独 L017 批准，留未来批次

**审查清单**：
- ✓ POST `/records` with `{"record_date": "2026-04-10"}` → 200, response `created_ids` 非空, DB `ConductRecord.date == 2026-04-10`
- ✓ POST `/records` without record_date → 200, DB `ConductRecord.date == today`
- ✓ POST `/records` with `{"record_date": null}` → 200, DB `ConductRecord.date == today`
- ✗ POST `/records` with old `{"date": "2026-04-14"}` → 被 pydantic 忽略（extra 字段），实际日期走 default today
- **关键行为（R2-F004 收窄）**：POST `/records` API 接受 `record_date` 字段并落库 `ConductRecord.date`；前端 UX 日期补录控件不在本批次，班主任"补录昨天积分"UX 留未来批次

**边界条件**：
- 日期格式非法（`"invalid"`）→ 422
- 日期早于班级学期开始 → 当前**不校验**，记作未来功能（design-concern）
- 批量 `/records/batch` 同字段名变更

**Agent 工具不受影响**：`ai/tools/conduct.py::add_conduct_points` L353 用 `date=date.today()` server-side，不走 schema，无需改动。

### 3.4 T3 — sidebar 按 permissions 派生

**Before**：`sidebarConfig.js` 三档硬编码：
- `CONDUCT_ITEMS_FULL`(9 项) / `CONDUCT_ITEMS_VIEWER`(3 项) / `CONDUCT_ITEMS_TEACHER`(2 项)
- 角色一次性绑定一个档（principal→VIEWER, subject_teacher→TEACHER, ...）

**After**：每个菜单项声明依赖的 permission；渲染时按 `hasPermission(currentRole, item.perm)` 过滤。

**设计结构**：
```js
// 单一 CONDUCT_ITEMS 列表，每项自带 perm 声明
const CONDUCT_ITEMS = [
  { label: '德育概览',   route: '/conduct',          perm: 'view_conduct',         moduleCode: 'conduct' },
  { label: '积分操作',   route: '/conduct/points',   perm: 'manage_conduct',       moduleCode: 'conduct' },
  { label: '积分记录',   route: '/conduct/records',  perm: 'view_conduct',         moduleCode: 'conduct' },
  { label: '排行榜',     route: '/conduct/rankings', perm: 'view_conduct',         moduleCode: 'conduct' },
  { label: '班规管理',   route: '/conduct/rules',    perm: 'manage_conduct_rules', moduleCode: 'conduct' },
  { label: '小组管理',   route: '/conduct/groups',   perm: 'manage_conduct',       moduleCode: 'conduct' },
  { label: '家长管理',   route: '/conduct/parents',  perm: 'manage_conduct_parents', moduleCode: 'conduct' },
  { label: '德育设置',   route: '/conduct/settings', perm: 'manage_conduct_rules', moduleCode: 'conduct' },
  { label: '数据导出',   route: '/conduct/export',   perm: 'export_conduct',       moduleCode: 'conduct' },
]
// 渲染层：items.filter(i => hasPermission(currentRole, i.perm))
```

废弃 `CONDUCT_ITEMS_FULL / VIEWER / TEACHER`。

**角色 × 菜单项矩阵**（改后预期可见入口数）：

| 角色 | 权限集 | 改前入口 | 改后入口 | 新增 |
|---|---|---|---|---|
| platform_admin | 全 5 | 9 | 9 | — |
| district_admin | 全 5 | 9 | 9 | — |
| principal | view+export | 3 | 3 | — |
| academic_director | view+manage+rules+export | 3 | **7** | 积分操作 / 记录 / 班规管理 / 小组管理 |
| teaching_research_leader | 无 | 0 | 0 | — |
| grade_leader | view+manage+export | 3 | **5** | 积分操作 / 记录 |
| lesson_prep_leader | 无（T1=C 回收后） | 0 | 0 | — |
| homeroom_teacher | 全 5 | 9 | 9 | — |
| subject_teacher | view+manage | 2 | **4**（概览 + 积分操作 + 记录 + 排行） | R-T3-followup F005 approved 2026-04-14T07:45 |

**✅ subject_teacher 细节（已批准 F005）**：改前 TEACHER 档是"积分操作 + 排行榜"（2 项），改后按 view_conduct+manage_conduct 过滤应得到 4 项（概览+积分操作+记录+排行）。这是 **R-T3-followup behavior_change 扩展**，用户 2026-04-14T07:45:00+08:00 精确回复"批准 F005"（记录于 `2026-04-14-conduct-roadmap-batch1-gates.json` F005.approval）。保守备选方案（`@allowed_roles` 白名单维持 2 项）**rejected**，不执行。

**审查清单**：
- ✓ `sidebarConfig.conduct.test.js` 9 角色 × 9 菜单项矩阵断言全通过
- ✓ academic_director 侧边栏渲染出 7 个 conduct 项
- ✓ grade_leader 侧边栏渲染出 5 个 conduct 项
- ✗ subject_teacher 看不到"班规管理"（无 MANAGE_CONDUCT_RULES）
- ✗ lesson_prep_leader 看不到任何 conduct 项（T1=C 已回收权限）
- 关键行为：教务主任点 /conduct/points 路由守卫放行（permissions.js 已给 manage_conduct）

**边界条件**：
- parent 不走 sidebar（独立 ParentLayout），本次设计不影响
- 角色切换后 sidebar 立即重渲染（Pinia auth.currentRole 变更触发）

### 3.5 T4 — conduct MODULE.md 补全

按 `src/edu_cloud/modules/grading/MODULE.md`（117 行模板）格式新建 `src/edu_cloud/modules/conduct/MODULE.md`。

**核心字段**：
```yaml
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
    - AdminService  # admin_service.py
    - ParentService  # parent_service.py
    - RulesService  # rules_service.py
    - ExportService  # export_service.py
  events: []

depends_on:
  modules:
    - student
    - school
  services:
    - ai.registry (6 Agent tools)
    - ai.tool_context (ToolContext / ToolResult)
  ai_tools:
    - get_conduct_rankings
    - get_student_conduct_summary
    - get_conduct_records
    - add_conduct_points
    - get_conduct_rules
    - get_class_conduct_overview

design_docs:
  - docs/plans/2026-04-12-conduct-module-design.md
  - docs/plans/2026-04-14-conduct-roadmap-design.md
```

**审查清单**：
- ✓ `aggregate_modules.py` 产出的 modules.yaml 含 conduct 条目
- ✓ module_governance_guard 对 conduct commit 不再触发 ask（ask→静默通过）
- ✗ owns_tables 若遗漏 conduct_group_members 等 → governance 巡检报错
- ✗ 跨模块 conduct_records.student_id 指向 students → deps 必须含 student

**边界条件**：
- `exposes.ai_tools` 列表必须与 `ai/tools/conduct.py` 的 `@tools.register` 实际注册名一致
- `owns_routes` 前缀 `/api/v1/conduct` 覆盖 admin_router + parent_router 两处挂载

### 3.6 T5 — 文档数字修正

- `C:\Users\Administrator\edu-cloud\CLAUDE.md` 德育条目：
  - "120 conduct tests（R2 基线 108 + 12 新增）" → "118 conduct tests（R2 基线 108 + 10 新增）"
- `docs/plans/2026-04-13-conduct-next-phase-handoff.md` L151:
  - "期望: 120 passed (R3 收尾基线)" → "期望: 118 passed (R3 收尾基线)"
- **T5 不修改 `C:\Users\Administrator\CLAUDE.md`**（全局级无 conduct 测试数字，仅进行中设计/已完成设计的 audit trail 条目，归 Task 6 收尾处理）

**审查清单**：
- ✓ 两文件数字改正后一致
- ✓ R3 handoff L171 原本就是 118（无需改）

## § 4. 测试基线预期

| 套件 | 改前基线 | 批次 1 实现后预期 | 增量来源 |
|---|---|---|---|
| conduct 后端 | 118 | **≥ 130**（R1-F006 入口级 + R5-F001 对照组补齐后） | T1 helper 4 + T1 入口级 API 403（R1-F006）+ T1 对照组 subject_teacher 200（R5-F001 隔离 scope 假绿）+ T2 红测 3（R1-F002 DB readback）+ T4 governance 测试 3 = 12 新增 |
| services | 15 | 15 | 不改 |
| frontend conduct 3 件套 + 扩展 | 13 | **≥ 29**（R1-F006/F007 + T1 permissions 镜像） | T3 sidebarConfig.conduct 矩阵 9 + R1-F007 perm 合法性 1 + R1-F006 AppSidebar.conduct.test.js 入口级 1 + T1 permissions.lesson_prep 5 = 16 新增 |

## § 5. 风险评估

### 5.1 批次 1 内部风险

| 风险 | 严重度 | 缓解 |
|---|---|---|
| T1 若有学校已依赖备课组长管德育 | 低 | MVP 初版给权限不当；L017 已充分讨论 |
| T2 未知外部客户端传老 `date` 字段 | 低 | 现状就已 422；rename 不破坏已工作调用 |
| T3 教务主任看到新菜单乱点 | 中 | 后端 F002 class-scope 守卫 R3 已覆盖，越权 403；subject_teacher 子问题（从 2 项→4 项）已由用户于 2026-04-14T07:45 精确批准 F005，不再悬空 |
| T4 MODULE.md 字段与实际不一致 | 低 | aggregate_modules.py 会校验；CI 可加 pre-commit 检查 |
| T5 文档修改触发 doc_sync_guard | 低 | 纯数字修正，应通过；若被拦，明确 accept risk |

### 5.2 防退化 sentinel（批次 1 不加）

批次 1 **仅加 red 回归测试**，不新增 sentinel 规则。Sentinel（design.md §3 防退化条款）留给批次 2 的 D-005。

## § 6. 成功度量与退出条件

### 6.1 批次 1 退出条件（全部满足才视为完成）

- 5 Tasks 全部 completed（`state.json` 标记）
- conduct 后端测试 ≥ 130 通过（R1-F006 入口级 + R5-F001 对照组补齐后，含 T1 helper/入口级/对照组 + T4 governance + T2 入口级）
- frontend conduct 测试 ≥ 29 通过（R1-F006/F007 新增 + T1 permissions.lesson_prep 镜像后）
- Gate 1 Plan Review PASS（codex-review plan）
- Gate 2 Code Review PASS（codex-review code）
- 所有 behavior_change finding 已 resolved-correct 或 approved
- design.md §10 添加 `[实现完成] Commits: {first}..{last}` 标记
- `CLAUDE.md` 进行中设计段迁移到已完成设计段

### 6.2 路线图整体成功度量

- 批次 1 完成：API 契约修复 + 菜单入口对齐 + 治理债清零
- 批次 2 完成：高风险契约有 sentinel + 同模式横扫完成 + 菜单源切换前置就绪
- 批次 3 完成：家长端真实可用 + Agent 真实数据返回对齐 + 导出真实可用

## § 7. 依赖

### 7.1 外部依赖

| 外部项 | 关系 | 阻塞批次 1？ |
|---|---|---|
| Migration Gate Repair（haofenshu-phase1） | 自动解锁 D-001 conduct F001 | 否 |
| haofenshu-phase1 Batch 2 菜单系统切换 | 批次 2 D-010 协同 | 否（批次 1 独立） |

### 7.2 内部依赖（跨模块）

- `students`, `schools`, `users`, `classes` 表 schema 不变
- `ai.registry.ToolContext` 接口不变
- `core/permissions.Permission` 枚举不变（仅改 `ROLE_PERMISSIONS` 映射）
- `api/deps.require_permission` / `api/permissions.get_visible_class_ids` 接口不变

## § 8. 交付文档清单

### 本 design 阶段（2026-04-14）

- `docs/plans/2026-04-14-conduct-roadmap-design.md`（本文档，edu-cloud repo）
- `C:\Users\Administrator\edu-cloud\CLAUDE.md` 参考文档段新增 conduct-roadmap 条目（edu-cloud repo，doc-sync-guard 合规）
- `C:\Users\Administrator\CLAUDE.md` 进行中设计段新增 conduct-roadmap 条目（workspace repo，audit trail 跨项目总索引）

**跨两个 repo 的依据**: edu-cloud CLAUDE.md 是项目级真源（模块/路由/端口），workspace CLAUDE.md 是跨项目 audit trail（已完成/进行中/归档索引）。两处都要同步是项目既有约定（见 `C:\Users\Administrator\CLAUDE.md` 已完成设计段所有历史条目）。

### 批次 1 writing-plans 阶段（本会话后续）

- `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md`
- `docs/plans/2026-04-14-conduct-roadmap-batch1-gates.json`
- `docs/plans/2026-04-14-conduct-roadmap-batch1-state.json`

### 批次 1 Executor 阶段（新会话）

- `docs/plans/2026-04-14-conduct-roadmap-batch1-handoff.md`（Planner → Executor 启动 prompt）
- 实现完成后 Executor 输出 `docs/plans/2026-04-14-conduct-roadmap-batch1-review-handoff.md`

### 批次 1 Reviewer 阶段

- `docs/plans/2026-04-14-conduct-roadmap-batch1-review-report.md`（Gate 2 Code Review）

### 批次 1 收尾

- 本 design §10 追加 `[实现完成]` 标记 + 测试基线 + commit range
- edu-cloud `CLAUDE.md` 参考文档段条目状态更新为 `[批次 1 实现完成]`
- workspace `C:\Users\Administrator\CLAUDE.md` 进行中设计 → 已完成设计 迁移（删除进行中条目 + 在已完成段追加批次 1 条目）

## § 9. 行为变更审批记录（L017）

| Finding ID | Task | 行为变更摘要 | 批准人 | 时间 | 用户原话/理由 |
|---|---|---|---|---|---|
| R-T1 | T1 | 回收 lesson_prep_leader 的 VIEW_CONDUCT + MANAGE_CONDUCT 权限 | 用户 | 2026-04-14 | "备课组长和打分没关系" |
| R-T2 | T2 | AddPointsRequest.date 字段重命名为 record_date（API 契约变更） | 用户 | 2026-04-14 | 精确批准 T2（"两个都批准"） |
| R-T3 | T3 | sidebar 三档硬编码改为按 permissions 派生（academic_director 可见入口 +4 / grade_leader +2） | 用户 | 2026-04-14 | 精确批准 T3（"两个都批准"） |
| R-T3-followup | T3 | ⚠ 隐含：subject_teacher 可见入口从 2 → 4（继承 view_conduct+manage_conduct 派生） | **approved** | 2026-04-14T07:45:00+08:00 | 用户精确回复"批准 F005"（记录于 `2026-04-14-conduct-roadmap-batch1-gates.json` F005.approval）|

## § 10. 实现完成标记

> 待批次 1 所有 gate PASS 后填写：
> `[YYYY-MM-DD HH:MM:SS 实现完成] Commits: {first}..{last} | Tests: conduct={N}, frontend={M}`

## § 11. 防退化条款（sentinel）

批次 1 仅以 red 回归测试兜底，不新增 sentinel。以下契约留给批次 2 加 sentinel：
- `_TEACHER_BASE - {VIEW_CONDUCT, MANAGE_CONDUCT}` 的集合运算（T1）
- `record_date` 字段名（T2）
- `CONDUCT_ITEMS` 单源列表（T3）
- `owns_tables` 八张表枚举（T4）

批次 2 D-005 启动时，对这些契约加 sentinel 规则（design.md §防退化段 + 红测 locking）。
