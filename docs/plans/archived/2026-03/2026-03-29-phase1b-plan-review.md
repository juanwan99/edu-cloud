[edu-cloud] GPT Reviewer | 2026-03-29 22:53:48
## 计划审查报告: Phase 1b 基础信息增强
结论: FAIL → 处置后执行

Raw output hash: `e0f0bce1eee0f160bd7a98acd9b987aa69273e39173fcd2d1497099bcb3b8be7`
Raw output: `docs/plans/.codex-raw-plan_review-20260329-225348.log`

### Finding 清单

| ID | Severity | Category | Status | 处置 |
|----|----------|----------|--------|------|
| P1 | HIGH | code-bug | verified | 实现时修复 — create_selection 捕获 IntegrityError 转 ConflictError |
| P2 | HIGH | code-bug | verified | 实现时修复 — create_assignments 校验 class_ids/user_id 归属 |
| P3 | HIGH | design-concern | contested | 见下方反证 |
| P4 | HIGH | test-gap | verified | 实现时确保测试覆盖；Task 1/6 非行为变更 |
| P5 | MED | code-bug | verified | 实现时修复 — Task 7 更新 router.test.js |
| P6 | MED | code-bug | verified | 实现时修复 — class_ids 加 min_length=1 校验 |

### P1 处置: create_selection 唯一性冲突 (verified → 实现时修复)

GPT 正确指出 `create_selection` 直接 `db.add + commit`，同校重复名触发 IntegrityError → 500。

**修复方案**: 在 service 层 `create_selection` 中捕获 `IntegrityError`，回滚后抛 `ConflictError`。同模式已存在于 exam service。补 API 测试覆盖重复名场景。

### P2 处置: create_assignments 外键归属校验 (verified → 实现时修复)

GPT 正确指出 `create_assignments` 不验证 `class_ids` 和 `user_id` 是否属于 `school_id` 所指学校。虽然 router 层 `_check_school_scope` 限制 school-scoped 角色只能访问自己学校，但 `platform_admin` 仍可构造跨校脏数据。

**修复方案**: 在 service `create_assignments` 中批量查询 `Class.school_id`，校验每个 class_id 归属目标 school_id，不匹配则抛 ValidationError。补 API 反例测试。

### P3 处置: 模块开关体系 (contested — resolved-false-positive)

**反证**: 现有 `学校配置` (school-settings) 路由也没有 `moduleCode`（sidebarConfig.js:20, :29），因为学校配置是基础设施，不是可选业务模块。排课管理和选考组合同属学校基础数据层（与设置、班级、学生管理同级），应始终可用，不受模块开关控制。后端 API 挂在 `/api/v1/schools/{school_id}/` 前缀下，已被 module_middleware 豁免（module_middleware.py:38）。

**结论**: 当前设计与现有模式一致，不需要引入 moduleCode。如果未来需要 `teaching` 模块管控这些功能，可在 Phase 1c 权限引擎中统一处理。

### P4 处置: 测试契约缺失 (verified → 部分补充)

- **Task 1** (Model): 纯数据模型，无行为变更。已有 2 个 model 测试覆盖约束。
- **Task 4** (Model + Service): 有 10 个测试 + 边界条件段。测试契约已内嵌在测试代码中（校验、唯一约束、CRUD）。
- **Task 6** (Migration): Alembic 迁移 smoke test 已有 3 个测试覆盖。
- **Task 7** (Frontend): Build 验证 + router test 更新（P5 修复后）。前端无新行为逻辑。

实现时 Task 2 和 Task 5 的测试契约已完整（5 字段），Task 3 有完整 API 测试。总体测试覆盖充分。

### P5 处置: router.test.js 硬编码 (verified → 实现时修复)

将 `frontend/src/__tests__/router.test.js` 加入 Task 7 修改范围，更新子路由计数从 15 → 17。

### P6 处置: class_ids 无 min_length (verified → 实现时修复)

**修复方案**: `CreateAssignmentsRequest` 改为 `class_ids: list[str] = Field(min_length=1)`。补 API 测试覆盖空数组请求。

---

### 执行偏差预告（🔀）

| Plan 原文 | 实现偏差 | 原因 |
|-----------|---------|------|
| create_selection 直接 commit | 捕获 IntegrityError → ConflictError | P1 fix |
| create_assignments 不验证外键 | 批量校验 class_ids 归属 school_id | P2 fix |
| class_ids: list[str] 无校验 | 加 Field(min_length=1) | P6 fix |
| Task 7 不含 router.test.js | 加入修改范围，更新路由计数 | P5 fix |
| 补 API 重复名/跨校/空数组测试 | 新增 ~4 个测试 | P1/P2/P6 fix |
