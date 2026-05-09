# 权限隔离修复交接文档

> **最后更新**: 2026-05-09（Phase 3 完成）
> **跨度**: 2026-05-08 ~ 2026-05-09，3 个 Phase，46 commits
> **参与者**: Claude Opus 4.6 + GPT 5.5 联合审计 → 实施 → 交叉审查
> **审计报告**: `docs/security-audit-permission-isolation-2026-05-08.md`
> **Phase 1 Plan**: `docs/superpowers/plans/2026-05-08-permission-isolation-fix.md`
> **Phase 2 Plan**: `docs/superpowers/plans/2026-05-09-permission-phase2-plan.md`
> **Phase 3 Design**: `docs/superpowers/plans/2026-05-09-tenant-middleware-design.md`
> **Phase 3 Plan**: `docs/superpowers/plans/2026-05-09-tenant-middleware-plan.md`

---

## Goal

修复 edu-cloud 多租户权限隔离体系中的跨校数据泄露、权限提升和 IDOR 漏洞，并建立架构级防线（TenantContext + 静态治理）防止未来遗漏。

## Must Preserve

- `CROSS_SCHOOL_ROLES = frozenset({"platform_admin", "district_admin"})` — 集中定义于 `core/tenant.py`
- `get_school_id(current)` — 集中定义于 `core/tenant.py`，fail-closed（缺 school_id 时 raise 403）
- `TenantContext` — frozen dataclass（`core/tenant.py`），纯数据类零 api 层依赖，`None=不限制 / ()=deny-all` 语义
- `get_tenant_context` — FastAPI dependency（`api/deps.py`），api 层负责调用 permissions helpers 构造 TenantContext
- `ScopeFilter.apply()` — 使用 `is not None` 检查（不是 falsy），空列表 `[]` 生成 deny-all
- `_check_exam_access(exam_id, user, db)` — 联考端点的参与校验证
- `_IMPERSONATION_ALLOWED_PERMISSIONS` — allowlist 模式
- AI session `owner_id` 检查 — 不匹配 403
- GradingResult `UniqueConstraint("school_id", "answer_id")` — 防跨校数据碰撞
- Template 条件式 school_id — admin None 时不加 WHERE
- 文件路径隔离用 `Path.is_relative_to()`（非 startswith）
- Pipeline `_pipeline_school_id` — 运行中的 pipeline 不可被其他学校的 enqueue 覆盖 owner

## Must Not Change

- 不可回退到 impersonation denylist 模式
- 不可移除联考 `_check_exam_access` 调用
- 不可把 school_id 作为查询参数接受（必须从 JWT 取）
- GradingResult 唯一约束不可改回 `(answer_id)`
- 不可把 `CROSS_SCHOOL_ROLES` / `get_school_id` 重新分散到各 router
- knowledge `link_question` 的 `is_primary` 参数不可移除
- `ScopeFilter` 不可回退到 `if self.subject_codes`（falsy check）
- `TenantContext` 不可导入 `edu_cloud.api.*`（core→api 反向依赖）
- 新 router 不可直接使用 `role.school_id`（静态治理 `test_tenant_static.py` 拦截）

---

## Phase 1 已完成（5 commits, 10 项修复）

P0 紧急止血 + P1 加固。

| Commit | 修复项 | 层级 |
|--------|--------|------|
| `803ed7d` | P0-1 GradingResult upsert 加 school_id / P0-2/3 联考成绩 school_id 从 JWT / P0-4 联考创建从 JWT / P1-1 模拟登录只读 / P1-2 AI session owner / P1-3 考试日程 IDOR | L1 L3 L4 L5 |
| `be8e9ce` | F-01 联考 detail/manage 参与校验证 | L1 L3 |
| `11a09e8` | F-06 Alembic 迁移（双方言） | 数据层 |
| `ecd55bc` | F-02 模拟登录改 allowlist | L4 |
| `0e4bf69` | P1-4 考试写操作加 MANAGE_EXAMS / P1-5 兼容扫描加 MANAGE_GRADING | L2 |

---

## Phase 2 已完成（12 commits, 29 项修复）

系统性修复 L1~L5 全部 5 层。审查流程: Plan R1-R3 PASS + Code R1-R4 PASS。

| Task | 内容 | Commit | 新测试 |
|------|------|--------|--------|
| 1 | 集中化 `CROSS_SCHOOL_ROLES` + `get_school_id` → `core/tenant.py`，替换 9 个 router | `204132f` | 5 |
| 2 | Pipeline Template 查询补 school_id（7 处）+ 路径遍历修复 | `30b1cf7` | — |
| 3+6 | Card 路径隔离（`is_relative_to`）+ Card Template school_id 修复 | `6b50d8c` | 8 |
| 4 | Knowledge `link_question` / `get_question_kps` 归属校验 | `136240d` | 5 |
| 5 | Homework service 深度防御（submit/grade/list JOIN HomeworkTask） | `4f96bef` | 6 |
| 7 | Permission decorator 加固（student 写 / grading_review GET / assignment 归属） | `a1f4d44` | 11 |
| 8 | L2 visible scope（grading tasks / bank / profile subject 验证） | `e509af8` | ~15 |
| GPT R1-R3 | admin None bypass / tenant path / homework fail-closed / skeleton multi-school | `4788313`..`f7fedc5` | — |

---

## Phase 3 已完成（9 commits, 12 项修复 + 架构基础设施）

从"逐端点手动修复"转向"框架级默认安全"。审查流程: Plan R1-R2 + 拆 topic 重审 + Code R1-R2。

### Task 执行记录

| Task | 内容 | Commit | 新测试 |
|------|------|--------|--------|
| 1 | P1-14 marking importer 3 处查询加 school_id（Exam/Subject/StudentAnswer） | `15dc865` | 2 |
| 2 | H4 pipeline progress/stop school_id 隔离 + 并发 owner 保护 | `80a46b5` | 4 |
| 3 | TenantContext frozen dataclass + get_tenant_context dependency + ScopeFilter fail-open 修复 | `df38360` | 7 |
| 4 | P2-1 dashboard pending_grading/pending_subjects 加 subject_codes JOIN | `b0b4dc0` | 1 |
| 5 | P2-3 workspace context/dashboard 传 subject_codes 到 service | `f6e55c7` | 1 |
| 6 | P2-4 analytics grade overview 传 visible_subject_codes | `60b07c7` | 1 |
| 7 | pytest 静态治理（2 规则 + allowlist） | `39de414`+`da624f8` | 2 |
| GPT R1 | pipeline owner 并发覆盖修复 + 测试断言强化 | `ba72069` | 1 |

### Phase 3 架构交付物

| 组件 | 位置 | 说明 |
|------|------|------|
| **TenantContext** | `core/tenant.py:24-60` | frozen dataclass，`None=不限制 / ()=deny-all`，require_school/apply_school/apply_subject_scope/apply_class_scope |
| **get_tenant_context** | `api/deps.py:193+` | FastAPI Depends，调用 get_school_id + get_visible_* 构造 TenantContext |
| **ScopeFilter 修复** | `core/scope_filter.py:21,23,25` | `if self.X` → `if self.X is not None`（空列表 fail-open → deny-all） |
| **Pipeline school owner** | `pipeline_service.py:34` | `_pipeline_school_id` 全局变量 + 并发 enqueue 保护 |
| **静态治理** | `tests/governance/test_tenant_static.py` | 2 规则：no-new-raw-school_id + scope-filter-no-falsy |

---

## 全局覆盖矩阵

| 层级 | 总修复数 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|---------|
| L1 跨校隔离 | 19 | 4 | 11 | 4（marking import + pipeline state + dashboard + workspace） |
| L2 校内角色 | 19 | 2 | 14 | 3（dashboard subject + workspace subject + analytics subject） |
| L3 联考隔离 | 2 | 2 | — | — |
| L4 模拟登录 | 1 | 1 | — | — |
| L5 IDOR | 5 | 3 | 2 | — |
| 架构基础设施 | 4 | — | — | 4（TenantContext + ScopeFilter + governance + pipeline owner） |
| **合计** | **50** | **10** | **29** | **11** |

**隔离测试总量**: 85 个测试函数（跨 16 个测试文件 + 1 个治理测试文件）
**全量回归**: 2590 passed / 45 failed（预存债）/ 0 新增失败

---

## 全局架构图：当前状态

```
┌─────────────────────────────────────────────────────┐
│ L1: 学校间隔离（school_id WHERE）                      │  ← Phase 1+2+3 系统性修复 ✅
│   ┌─────────────────────────────────────────────────┤
│   │ L2: 校内角色隔离（visible_class/subject）          │  ← Phase 2+3 修复 ✅
│   │   ┌─────────────────────────────────────────────┤
│   │   │ L3: 联考隔离（参与校验证）                     │  ← Phase 1 修复 ✅
│   │   └─────────────────────────────────────────────┤
│   └─────────────────────────────────────────────────┤
│ L4: 模拟登录（allowlist 权限降级）                      │  ← Phase 1 修复 ✅
│ L5: IDOR（对象级归属验证）                              │  ← Phase 1+2 修复 ✅
├─────────────────────────────────────────────────────┤
│ 架构防线:                                              │
│   TenantContext (core/tenant.py)     ← Phase 3 新增 │
│   ScopeFilter deny-all 语义          ← Phase 3 修复 │
│   静态治理 test_tenant_static.py     ← Phase 3 新增 │
│   Pipeline school owner             ← Phase 3 新增 │
└─────────────────────────────────────────────────────┘
```

---

## 未完成：剩余治理项

### 低优先级端点修复

| # | 模块 | 问题 | 优先级 |
|---|------|------|--------|
| P2-2 | Compat 登录 | 忽略 school_code（2026-07-31 sunset） | P3（sunset 后自然消除） |
| P2-5 | 课表 | 校历是全校事件，无 class_id 维度，模型设计合理 | 无需修 |

### 测试债（GPT R2 残留）

| 项 | 说明 | Deadline |
|---|------|---------|
| workspace 测试 fixture | Exam 无 subject_code 字段，导致 scope 过滤测试无法触达完整路径 | 2026-06-30 |
| grade overview 测试 fixture | 缺 Grade 记录，返回 404 跳过断言 | 2026-06-30 |
| pipeline 入口级测试 | 经真实 /start 触发的端到端测试需要完整扫描图+模板数据 | 2026-06-15 |

### 架构路线图（Phase 3.4+）

| 阶段 | 内容 | 状态 |
|------|------|------|
| **3.0** | 热修 P1-14 + H4 | ✅ 完成 |
| **3.1** | TenantContext + ScopeFilter 修复 | ✅ 完成 |
| **3.2** | P2-1/3/4 subject scope 迁移 | ✅ 完成 |
| **3.3** | pytest 静态治理 | ✅ 完成 |
| **3.4** | SQLAlchemy `do_orm_execute` audit mode（只记录未 scoped 查询，不拦截） | 待启动 |
| **3.5** | 选择性启用强制过滤（需 model registry 确定 tenant-scoped 表清单） | 待 3.4 验证 |

### 旧 router 迁移进度

38 个 router 文件中：
- **10 个**已用 `get_school_id`（Phase 2 集中化）
- **28 个**仍用裸 `role.school_id`（在 governance allowlist 中，触碰即迁移）
- **0 个**已用 `TenantContext`（Phase 3 建立基础，新 router 优先使用）

静态治理 `test_tenant_static.py` 确保新增 router 不可使用裸 `role.school_id`。

### 配套治理措施

| 措施 | 状态 |
|------|------|
| TenantContext typed dependency | ✅ 完成 |
| ScopeFilter 空列表 deny-all | ✅ 完成 |
| 静态治理（no-new-raw-school_id + scope-filter-no-falsy） | ✅ 完成 |
| SQLAlchemy audit mode | 待启动（Phase 3.4） |
| school_id 覆盖率 CI 检查 | 待建 |
| Rubric UniqueConstraint `(school_id, question_id)` | 待评估 |

---

## GPT 审查历程

| Gate | 轮次 | 结果 | 关键 finding |
|------|------|------|-------------|
| Phase 1 Code | R1 | PASS | — |
| Phase 2 Plan | R1→R3 | PASS | MANAGE_STUDENTS 不存在 / admin None 条件处理 / 并行依赖 |
| Phase 2 Code | R1→R4 | PASS | admin bypass / tenant path / homework fail-closed / skeleton multi-row |
| Phase 3 Plan | R1→R2→拆 topic | 收敛 | Contract Pack schema / Evidence Block / 反向依赖 / 测试契约 |
| Phase 3 Code | R1→R2 | R2 MED test-gap ×2 | pipeline owner 并发覆盖 / 测试 fixture 不足（记 test_debt） |
