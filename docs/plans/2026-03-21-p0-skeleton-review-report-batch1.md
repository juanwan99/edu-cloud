[edu-cloud] GPT Reviewer | 2026-03-22 08:50:00
## 审查报告: Task 1-8
结论: PASS（R3, 条件通过）

### Round 1 — FAIL (Phase 1 未通过)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| TG-01 | HIGH | test-gap | ✅ 已修复 (commit 03229e7) — scope 过滤测试补充 out-of-scope 班级 |
| TG-02 | MED | test-gap | ✅ 已修复 (commit 03229e7) — 补充单成绩+全满分边界测试 |
| TG-03 | MED | test-gap | ✅ 已修复 (commit 03229e7) — 同步测试补充 DB 验证 |

### Round 2 — FAIL (Phase 2 发现 2 个 code-bug)

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| R2-01 | HIGH | code-bug | ✅ 已修复 (commit after 03229e7) — workspace 端点添加 require_permission(VIEW_EXAMS) |
| R2-02 | HIGH→design-concern | code-bug→重分类 | 📋 Planner 处置：grade_ids/subject_codes scope 过滤为 P1 范围，计划本身只设计了 class_ids 过滤。记入 design.md §待处置 |

**R2-02 重分类理由**：计划 Task 6 的 WorkspaceService 代码只实现了 class_ids 过滤。grade_ids 和 subject_codes 的过滤逻辑在设计文档中属于 P1 范围（多角色完整 scope 隔离），P0 只支持 homeroom_teacher + class_ids 场景。GPT 审查者按"模型字段存在即应生效"判定为 code-bug，但从产品范围看这是 design-concern。

### Round 3 — PASS（仅审 code-bug 修复）

R2-01 修复验证：
- `src/edu_cloud/api/workspace.py` 两个端点改为 `require_permission(Permission.VIEW_EXAMS)`
- 新增 `test_workspace_denied_for_parent` 验证 parent 角色 403
- 94 tests 全通过

### 统计

- 测试: 58 → 94 (+36)
- Commits: beab26e..HEAD (10 commits)
- R1: FAIL (3 test-gap), R2: FAIL (2 code-bug), R3: PASS (条件通过，R2-02 待 P1 处置)
