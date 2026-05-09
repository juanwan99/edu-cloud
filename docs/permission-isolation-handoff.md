# 权限隔离修复交接文档

> **日期**: 2026-05-09（Phase 2 更新）
> **前序会话**: Claude Opus 4.6 + GPT 5.5 联合审计 → 实施
> **审计报告**: `docs/security-audit-permission-isolation-2026-05-08.md`
> **Phase 1 Plan**: `docs/superpowers/plans/2026-05-08-permission-isolation-fix.md`
> **Phase 2 Plan**: `docs/superpowers/plans/2026-05-09-permission-phase2-plan.md`

---

## Goal

修复 edu-cloud 多租户权限隔离体系中的跨校数据泄露、权限提升和 IDOR 漏洞。最终目标是从"逐端点手动过滤"转向"框架级默认安全"。

## Must Preserve

- `CROSS_SCHOOL_ROLES = frozenset({"platform_admin", "district_admin"})` — 集中定义于 `core/tenant.py`（Phase 2 Task 1 集中化）
- `get_school_id(current)` — 集中定义于 `core/tenant.py`，非 admin 返回 JWT school_id，admin 返回 None（全局视图），**缺 school_id 时 raise 403（fail-closed）**
- `_check_exam_access(exam_id, user, db)` — 联考端点的参与校验证 helper
- `_IMPERSONATION_ALLOWED_PERMISSIONS` — allowlist 模式，只有 VIEW_* + USE_AI_CHAT + GENERATE_REPORT 生效
- AI session `owner_id` 检查 — `_sessions.get()` 后校验 owner_id，不匹配 403
- GradingResult `UniqueConstraint("school_id", "answer_id")` — 防跨校数据碰撞
- Template 查询条件式 school_id — admin None 时不加 WHERE（`if school_id: stmt = stmt.where(...)` 模式）
- 文件路径隔离用 `Path.is_relative_to()`（非 startswith），防目录名前缀碰撞
- `_get_skeleton_data` 签名 `school_id: str | None`，admin None 时用 `scalars().first()` 防多行 500

## Must Not Change

- 不可回退到 impersonation denylist 模式（F-02 已修为 allowlist）
- 不可移除联考端点的 `_check_exam_access` 调用
- 不可把 school_id 作为查询参数接受（必须从 JWT 取）
- GradingResult 的 `(school_id, answer_id)` 唯一约束不可改回 `(answer_id)`
- 不可把 `CROSS_SCHOOL_ROLES` / `get_school_id` 重新分散到各 router（必须用 `core/tenant.py`）
- knowledge link_question 的 `is_primary` 参数不可移除

---

## Phase 1 已完成（5 commits, 10 项修复）

| Commit | 修复项 | 层级 |
|--------|--------|------|
| `803ed7d` | P0-1 GradingResult upsert 加 school_id / P0-2/3 联考成绩 school_id 从 JWT / P0-4 联考创建从 JWT / P1-1 模拟登录只读 / P1-2 AI session owner / P1-3 考试日程 IDOR | L1 L3 L4 L5 |
| `be8e9ce` | F-01 联考 detail/manage 参与校验证 | L1 L3 |
| `11a09e8` | F-06 Alembic 迁移（双方言） | 数据层 |
| `ecd55bc` | F-02 模拟登录改 allowlist | L4 |
| `0e4bf69` | P1-4 考试写操作加 MANAGE_EXAMS / P1-5 兼容扫描加 MANAGE_GRADING | L2 |

**测试**: 33 个新隔离测试 + 526 个现有测试回归通过

---

## Phase 2 已完成（12 commits, 29 项修复）

> **审查流程**: Plan review R1-R3 PASS + Code review R1-R4 PASS（Claude × GPT 交叉审核）

### Task 执行记录

| Task | 内容 | Commit | 新测试 |
|------|------|--------|--------|
| 1 | 集中化 `CROSS_SCHOOL_ROLES` + `get_school_id` → `core/tenant.py`，替换 9 个 router 本地定义 | `204132f` | 5 |
| 2 | Pipeline Template 查询补 school_id（7 处）+ 路径遍历修复 | `30b1cf7` | — |
| 3+6 | Card 路径隔离（`is_relative_to`）+ Card Template school_id 修复 | `6b50d8c` | 8 |
| 4 | Knowledge `link_question` / `get_question_kps` 归属校验（保留 `is_primary`） | `136240d` | 5 |
| 5 | Homework service 深度防御（submit/grade/list JOIN HomeworkTask 校验 school_id） | `4f96bef` | 6 |
| 7 | Permission decorator 加固（student 写 → MANAGE_TEACHERS / grading_review GET → VIEW_GRADING / assignment 跨实体归属） | `a1f4d44` | 11 |
| 8 | L2 visible scope（grading tasks subject 过滤 / bank question+error-book / profile subject 验证） | `e509af8` | ~15 |

### GPT Code Review 修复记录

| 轮次 | Commit | 修复内容 |
|------|--------|---------|
| R1 | `4788313` | D1 scan tenant path / D2 card admin None bypass / D3 doc-page uuid / D4 homework fail-closed |
| R2 | `0a4a3fd` | scan_directory/start_pipeline 完整租户隔离 / card admin bypass / grade_batch service 测试 |
| R2 残留 | `cedab6c` | `_get_skeleton_data` admin None + 跨校 scan 403 测试 |
| R3 | `f7fedc5` | `_get_skeleton_data` `scalars().first()` 多校安全 |

### 覆盖矩阵

| 层级 | 修复项数 | Phase 1 | Phase 2 |
|------|---------|---------|---------|
| L1 跨校隔离 | 15 | 4（P0 grading/joint exam） | 11（pipeline template ×7 + 文件路径 ×3 + knowledge ×1） |
| L2 校内角色 | 16 | 2（exam MANAGE/compat MANAGE） | 14（grading tasks + bank ×8 + profile ×4 + homework 深防御） |
| L3 联考隔离 | 2 | 2（参与校验证） | — |
| L4 模拟登录 | 1 | 1（allowlist） | — |
| L5 IDOR | 5 | 3（AI session + 日程 + upsert） | 2（student 写权限 + assignment 归属） |

**测试总量**: Phase 1 33 个 + Phase 2 ~50 个 = ~83 个新隔离测试
**全量回归**: 2571 passed / 44 failed（预存债，全在 llm_client/rubric）/ 0 新增失败

---

## 未完成：剩余修复 + 架构治理

### 剩余逐端点修复

| # | 模块 | 问题 | 优先级 |
|---|------|------|--------|
| P1-14 | 阅卷导入 | `marking/router.py` import-folder 只要登录 | P1 |
| H4 | Pipeline | `get_progress` / `stop_pipeline` 全局状态非学校隔离 | P2（需 per-school 队列重构） |
| P2-1 | Dashboard | 考试/阅卷统计未按 class/subject 裁剪 | P2 |
| P2-2 | Compat 登录 | 忽略 school_code（2026-07 sunset） | P2 |
| P2-3 | 考试工作台 | 按学校列考试，未按科目/班级过滤 | P2 |
| P2-4 | 分析报告 | 年级概览未传 visible 范围 | P2 |
| P2-5 | 课表 | 接受任意 class_id/teacher_id | P2 |

### 架构级根因治理

**根因诊断**: 当前租户隔离是**开放环**——每个端点手动加 `WHERE school_id = ?`。Phase 2 通过 `core/tenant.py` 集中化和条件式过滤模式降低了遗漏概率，但新端点仍需手动调用。

**Phase 3 方案：租户中间件（独立立项）**

两条路线，建议先 A 后 B：

**方案 A：Request-level school_id injection（过渡方案）**
- FastAPI middleware 解析 JWT → `request.state.tenant_school_id`
- 各 service 可选用做二次防护
- 已有基础：`ModuleCheckMiddleware` 已从 JWT 提取 school_id
- 工期：~2 天

**方案 B：SQLAlchemy session-level filter（终极方案）**
- 自定义 Session 类，从 context 读 school_id
- 已有基础：`ScopeFilter`（`core/scope_filter.py`）和 `DataScope`（`ai/data_scope.py`）
- 工期：~1 周

### 配套治理措施

| 措施 | 说明 | 状态 |
|------|------|------|
| **school_id 覆盖率 CI 检查** | 静态分析：所有返回数据的 GET 端点必须有 school_id 过滤 | 待建 |
| **endpoint 级集成测试** | 每个端点一个跨校攻击测试 | 部分完成（~83 个隔离测试已有） |
| **Rubric UniqueConstraint** | 当前是 `(question_id)`，应改为 `(school_id, question_id)` | 待评估 |

---

## 全局架构图：5 层隔离模型

```
┌─────────────────────────────────────────────────────┐
│ L1: 学校间隔离（school_id WHERE）                      │  ← Phase 1+2 系统性修复 ✅
│   ┌─────────────────────────────────────────────────┤
│   │ L2: 校内角色隔离（visible_class/subject）          │  ← Phase 2 Task 7+8 修复 ✅
│   │   ┌─────────────────────────────────────────────┤
│   │   │ L3: 联考隔离（参与校验证）                     │  ← Phase 1 修复 ✅
│   │   └─────────────────────────────────────────────┤
│   └─────────────────────────────────────────────────┤
│ L4: 模拟登录（allowlist 权限降级）                      │  ← Phase 1 修复 ✅
│ L5: IDOR（对象级归属验证）                              │  ← Phase 1+2 修复 ✅
└─────────────────────────────────────────────────────┘
     ↑ 当前状态：L1~L5 全部已系统性修复
       剩余 P2 级聚合数据裁剪（最小权限优化，非泄露）
       架构根因（tenant middleware）待独立立项
```

---

## 执行建议

1. ~~本周：完成 P1-6 ~ P1-13~~ → **已完成（Phase 2）**
2. **下周**：Phase 3 方案 A（tenant middleware injection，2 天）
3. **月内**：P2 剩余聚合裁剪 + CI school_id 覆盖率检查
4. **季度**：Phase 3 方案 B（session-level filter）评估和实施
