# 权限隔离修复交接文档

> **日期**: 2026-05-09
> **前序会话**: Claude Opus 4.6 + GPT 5.5 联合审计 → 实施
> **审计报告**: `docs/security-audit-permission-isolation-2026-05-08.md`
> **Plan**: `docs/superpowers/plans/2026-05-08-permission-isolation-fix.md`

---

## Goal

修复 edu-cloud 多租户权限隔离体系中的跨校数据泄露、权限提升和 IDOR 漏洞。最终目标是从"逐端点手动过滤"转向"框架级默认安全"。

## Must Preserve

- `_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}` — 跨校角色白名单，所有 school_id 过滤都依赖此集合判断是否放行
- `_get_school_id(current)` 模式 — 非 admin 返回 JWT school_id，admin 返回 None（全局视图），**缺 school_id 时 raise 403（fail-closed）**
- `_check_exam_access(exam_id, user, db)` — 联考端点的参与校验证 helper，非 admin 必须是 JointExamParticipant
- `_IMPERSONATION_ALLOWED_PERMISSIONS` — allowlist 模式，只有 VIEW_* + USE_AI_CHAT + GENERATE_REPORT 生效
- AI session `owner_id` 检查 — `_sessions.get()` 后校验 owner_id，不匹配 403
- GradingResult `UniqueConstraint("school_id", "answer_id")` — 防跨校数据碰撞

## Must Not Change

- 不可回退到 impersonation denylist 模式（F-02 已修为 allowlist）
- 不可移除联考端点的 `_check_exam_access` 调用
- 不可把 school_id 作为查询参数接受（必须从 JWT 取）
- GradingResult 的 `(school_id, answer_id)` 唯一约束不可改回 `(answer_id)`

---

## 已完成（5 commits, 10 项修复）

| Commit | 修复项 | 层级 |
|--------|--------|------|
| `803ed7d` | P0-1 GradingResult upsert 加 school_id / P0-2/3 联考成绩 school_id 从 JWT / P0-4 联考创建从 JWT / P1-1 模拟登录只读 / P1-2 AI session owner / P1-3 考试日程 IDOR | L1 L3 L4 L5 |
| `be8e9ce` | F-01 联考 detail/manage 参与校验证 | L1 L3 |
| `11a09e8` | F-06 Alembic 迁移（双方言） | 数据层 |
| `ecd55bc` | F-02 模拟登录改 allowlist | L4 |
| `0e4bf69` | P1-4 考试写操作加 MANAGE_EXAMS / P1-5 兼容扫描加 MANAGE_GRADING | L2 |

**测试**: 33 个新隔离测试 + 526 个现有测试回归通过

---

## 未完成：逐端点修复（P1 剩余 + P2）

### 优先级 1：L2 校内角色隔离 + IDOR（P1-6 ~ P1-13）

这些端点有 school_id 过滤（L1 安全），但缺 visible_class_ids / visible_subject_codes 过滤（校内教师可越权看其他班数据）。

| # | 模块 | 文件 | 问题 | 修复方向 |
|---|------|------|------|---------|
| P1-6 | 作业 | `homework/router.py:129,143,230,243` | task/submission 只按 school_id，无 class/subject 校验 | 建 `authorize_task_access` helper：创建者 or 任教科目+班级 or 学生本人 |
| P1-7 | 阅卷结果 | `grading/grading_review_router.py:52,91,470` | 结果列表只按学校，批注写只需 VIEW_GRADING | 绑定阅卷分配 + 科目范围；批注写要 MANAGE_GRADING |
| P1-8 | 阅卷分配 | `grading/assignment_router.py:45` | 创建分配未校验对象归属 | 服务层逐项校验 exam/subject/question/teacher 的 school_id |
| P1-9 | 扫描 | `scan/router.py:44,103,134,374` + `pipeline_router.py:323,433,715,850,886` | 上传端点只要登录；文件路径无租户校验 | 上传加 MANAGE_GRADING；路径映射到租户根目录 |
| P1-10 | 答题卡 | `card/router.py:96,159,280` + `card_export_router.py:37,188,283,311` + `card_template_router.py:100,211` | 布局/发布/文件访问缺权限 | 写操作加 MANAGE_EXAMS；文件用对象 ID + school_id |
| P1-11 | 学生/教师 | `student/router.py:55,125,141` + `teacher_router.py:106,149,208,268,416` | 班级列表接受未授权 school_id；教师导出接受任意 school_id | 非 admin 禁止 school_id 覆盖；写操作加管理权限 |
| P1-12 | 画像/错题 | `profile/router.py:52,95` + `bank/router.py:137,152,164,178` | 接受任意 student_id/class_id | 校验学生班级在 visible_class_ids 内 |
| P1-13 | 知识点 | `knowledge/router.py:69` + `knowledge/service.py:51` | 只要登录就能关联/读取知识点 | 校验 question.school_id + 编辑权限 |
| P1-14 | 阅卷导入 | `marking/router.py` import-folder | 只要登录 | 代码已改（在 dirty state 中），需随 marking 预存改动一起提交 |

**修复模式统一**：所有 P1 端点遵循同一模式——
1. school_id 从 JWT 取（`current["current_role"].school_id`）
2. 非 admin 缺 school_id → 403
3. 写操作加对应 `require_permission`
4. 涉及子对象（student/question/class）时校验归属链

### 优先级 2：L2 聚合数据裁剪（P2-1 ~ P2-8）

校内角色看到的聚合数据范围过大（如科任教师看到全校统计）。不涉及跨校泄露，但违反最小权限原则。

| # | 模块 | 问题 |
|---|------|------|
| P2-1 | dashboard | 考试/阅卷统计未按 class/subject 裁剪 |
| P2-2 | compat 登录 | 忽略 school_code |
| P2-3 | 考试工作台 | 按学校列考试，未按科目/班级过滤 |
| P2-4 | 分析报告 | 年级概览未传 visible 范围 |
| P2-5 | 课表 | 接受任意 class_id/teacher_id |
| P2-6 | 知识掌握 | 接受任意 student_id |
| P2-7 | 阅卷任务列表 | 只按学校过滤，未按分配/科目裁剪 |
| P2-8 | 试卷生成 | 只按 paper_id，未绑定学校/创建人 |

**修复模式统一**：查询加 `visible_class_ids` / `visible_subject_codes`（从 `api/permissions.py` 的 `get_visible_class_ids` / `get_visible_subject_codes` 获取）。

---

## 未完成：架构级根因治理

### 根因诊断

当前租户隔离是**开放环**——每个端点手动加 `WHERE school_id = ?`，新端点默认不安全，开发者忘了加就泄露。320 个端点 26 个遗漏（8%），不是偶然是架构缺陷。

### Phase 3 方案：租户中间件（独立立项）

两条路线，建议先 A 后 B：

**方案 A：Request-level school_id injection（过渡方案）**
- FastAPI middleware 解析 JWT → `request.state.tenant_school_id`
- 各 service 可选用做二次防护
- 优点：渐进式，不破坏现有代码
- 缺点：仍依赖各端点主动使用
- 工期：~2 天

**方案 B：SQLAlchemy session-level filter（终极方案）**
- 自定义 Session 类，从 context 读 school_id
- 所有含 `school_id` 列的表自动加 WHERE
- `platform_admin` 通过 context flag 豁免
- 优点：新端点自动安全，根本性解决
- 缺点：改动大，需处理联考等跨校场景的豁免
- 工期：~1 周，需独立 design + plan + review

### 配套治理措施

| 措施 | 说明 | 状态 |
|------|------|------|
| **school_id 覆盖率 CI 检查** | 静态分析：所有返回数据的 GET 端点必须有 school_id 过滤 | 待建 |
| **endpoint 级集成测试** | 每个端点一个跨校攻击测试（F-07 deferred） | 待建 |
| **Rubric UniqueConstraint** | 当前是 `(question_id)`，应改为 `(school_id, question_id)` | 待评估 |
| **DB 外键审计** | 确认所有含 school_id 的表都有 FK 到 schools | 待跑 |

---

## 全局架构图：5 层隔离模型

```
┌─────────────────────────────────────────────────────┐
│ L1: 学校间隔离（school_id WHERE）                      │  ← 已修 P0 ×4
│   ┌─────────────────────────────────────────────────┤
│   │ L2: 校内角色隔离（visible_class/subject）          │  ← P1-6~13 待修
│   │   ┌─────────────────────────────────────────────┤
│   │   │ L3: 联考隔离（参与校验证）                     │  ← 已修 F-01
│   │   └─────────────────────────────────────────────┤
│   └─────────────────────────────────────────────────┤
│ L4: 模拟登录（allowlist 权限降级）                      │  ← 已修 F-02
│ L5: IDOR（对象级归属验证）                              │  ← 部分已修
└─────────────────────────────────────────────────────┘
     ↑ 当前状态：L1/L3/L4 已系统性修复
       L2/L5 逐端点修复中，P1 8 项待完成
       架构根因（tenant middleware）待独立立项
```

---

## 执行建议

1. **本周**：完成 P1-6 ~ P1-13（逐端点修复，每个 ~30 分钟，模式统一）
2. **下周**：Phase 3 方案 A（tenant middleware injection，2 天）
3. **月内**：P2 全部 + CI school_id 覆盖率检查 + endpoint 集成测试
4. **季度**：Phase 3 方案 B（session-level filter）评估和实施
