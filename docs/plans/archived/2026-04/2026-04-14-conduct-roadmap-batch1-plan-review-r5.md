<!-- pre-takeover: archived for history, not active spec -->
[edu-cloud] GPT Reviewer R5 | 2026-04-18 (UTC+8)

## 审查报告（R5）: R4 3 findings 复核 + 全量 checklist
结论: FAIL

raw log SHA256: `f0582600db8dda95152b6c3d90e2077c150570a523b42cded2c6466c06776cd8`
subject: plan.md @ commit e73481a
override 声明: 用户 2026-04-17 override "禁 R3+"（持续生效至 R5）

## R4 三项复核（R5 verify —— 全部 resolved ✅）

| R4 ID | R5 Status | 证据 |
|---|---|---|
| R4-F001 | **resolved** | Step 3.11 vitest 命令已去除 AppSidebar.conduct.test.js；后端 Expected `126 passed`；前端 Expected `18 passed` |
| R4-F002 | **resolved** | design §4/§6.1 `129/29`；plan L795/1624/1636 统一；Step 5.5 算术 `72+5+10+1=88` |
| R4-F003 | **resolved** | `students_profiles` 全部替换为 `student_profiles` |

R4 三项全部 resolved。

## R5 新增 Findings

### R5-F001
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Before-behavior: Task 3 的 API 403 入口级测试（`test_lesson_prep_leader_cannot_call_conduct_api`）可能因 scope 失败而假绿——lesson_prep_leader fixture 未赋 `class_ids`，conduct scope 守卫会直接 403，而非因 RBAC VIEW_CONDUCT 被回收。
- After-behavior: 测试 fixture 必须给 lesson_prep_leader 赋 `class_ids=[cls.id]` 让 scope 通过，从而仅验 RBAC 层 403；并加对照组 subject_teacher 同 scope 下 200，以根因区分 "403 来自 RBAC 回收" 与 "403 来自 scope 空"。
- Evidence: `plan.md:625/630`；`src/edu_cloud/api/permissions.py:18-22`（`get_visible_class_ids` 对非管理员 `return role.class_ids or []`）；`src/edu_cloud/modules/conduct/permissions.py:47-51`（`check_class_scope` 对空 visible 直接 403）。
- Impact: 即使 VIEW_CONDUCT 没被回收，`test_lesson_prep_leader_cannot_call_conduct_api` 也会因 scope 通过——INV-T1-003 和 Contract Pack 失真。
- Repair hypothesis: fixture 加 `class_ids=[cls.id]`；新增对照组测试 `test_subject_teacher_with_same_scope_passes_rbac` 返回 200。这对 INV-T1-003 提供 root-cause 区分证据。

### R5-F002
- Severity: LOW
- Category: design-concern
- Type: defect_fix
- Before-behavior: Task 2 顶部 Files 摘要写 `test_module_governance.py`（新建，1 测试），但正文 Step 2.5/2.6 明确是 3 测试。
- After-behavior: Files 摘要应与正文一致（3 测试）。
- Evidence: `plan.md:178` vs `plan.md:353/418/424`。
- Impact: 读者/Executor 数字口径不一。
- Repair hypothesis: 将 Files 摘要的 "1 测试" 改为 "3 测试"。

### R5-F003
- Severity: LOW
- Category: design-concern
- Type: defect_fix
- Before-behavior: Step 5.5 "全量前端 = 72 原 + 16 新 = 88" 来源已与当前代码库脱节。
- After-behavior: 应用实际 frontend 全量基线（GPT 实跑 `234 passed`）作为口径。
- Evidence: `plan.md:1482`；GPT 实跑 `cd frontend && npx vitest run`。
- Impact: repo-wide baseline 叙述不可信；但已标注"数字按实际"未致阻断。
- Repair hypothesis: 改为 "234 基线 + 16 新 = 250 passed"。

## Checklist 结果
- A 自洽性: FAIL (R5-F002/F003)
- B 代码库对齐: FAIL (R5-F001 与鉴权链路真实行为不对齐)
- C 架构适配: PASS
- D 完整性: FAIL (核心行为无 root-cause 区分测试)
- D+ 测试契约质量: FAIL (R5-F001 假绿)
- E 风险评估: PASS
- F Contract Pack 完整性: FAIL (INV-T1-003 test_ref 可假绿)

## R5 结论
**FAIL**（HIGH×1 + LOW×2，3 个 defect_fix；R4 核心 100% resolved；R5-F001 是测试设计层面的根因洞察）

GPT 额外实跑：`sidebarConfig.conduct + AppSidebar + ParentRules = 13 passed`（与 plan baseline 一致）；`frontend` 全量 `234 passed`（揭示 L1482 过期）。

## R6 计划（2026-04-18 进行中）

对应 R5-F001/F002/F003 的修复已在 plan (R6 pending commit) 中落地：
- R5-F001: Step 3.4a 加 `class_ids=[cls.id]` + 新增对照组 `test_subject_teacher_with_same_scope_passes_rbac`；Step 3.4b 跑 2 tests；所有相关数字从 129/173 升到 130/174
- R5-F002: Task 2 Files 摘要 "1 测试" → "3 测试"
- R5-F003: Step 5.5 基线从 "72 原" 改为 "234 基线（实跑）+ 16 新 = 250"

R6 重审触发后验证。
