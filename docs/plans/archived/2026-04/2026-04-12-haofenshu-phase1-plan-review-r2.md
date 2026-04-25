# Plan Review R2: 好分数业务复刻 Phase 1

> [edu-cloud] GPT Reviewer | 2026-04-12 23:00:46
> Raw output hash: 8eede8cd00b50af969d5a36dda3bab3c545c52239c1196691a103ed5af442455

## 审查报告

结论: **FAIL**

依据：R1 的 F002/F003/F007/F008 未实质关闭（HIGH 2 + MED 2）；新发现 F009 HIGH + F010 MED。R1 的 F001/F004/F005/F006 本轮验证通过。

## R1 已验证通过

- **F001** 已补齐 Contract Pack（invariants/counter_examples/risk_modules/test_debt）
- **F004** 已对齐 `get_current_user` 返回结构 + `get_enabled_modules` 函数式调用
- **F005** `ARRAY(String)` → `JSON` + `server_default="[]"`
- **F006** 文件路径统一为 `analysis_models.py` + 显式 import

## Findings

### F002 — 测试契约仍不完整
- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** plan 声称 Task 1-11 已补齐测试契约，但实际只有 Task 1/2/3/5/7/9 有 `测试契约` 段
- **After-behavior:** 所有行为变更 Task 须有 5 字段测试契约 + ≥3 边界条件；非行为变更 Task 明确标注为非行为变更
- **Evidence:** Task 4/6/8/10/11/12 缺失测试契约段
- **Impact:** 执行者在这些 Task 上没有可落地的入口级验证规范

### F007 — useApi 仍有错误路径 + Task 10 调用不存在端点
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** analytics 方法路径仍不精确；`getPowerOptions` 被注释为 Phase 2/3 但 Task 10 仍调用它
- **After-behavior:** useApi 只暴露真实存在的端点；Task 10 不调用不存在的 API
- **Evidence:** `getAnalyticsSummary` 等路径与 `analytics/router.py` 实际路由不匹配；Task 10 `api.getPowerOptions(...)` 调用已注释掉的方法
- **Impact:** 按计划实现会产出 404；Task 10 无法正常运行

### F009 — 前端 auth store 与后端响应结构不匹配（新发现）
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** auth store 约定 `user` 含 `roles` 和 `active_role`，但后端 login 返回 `user + roles` 分离结构，switch-role 只返回 `active_role`；plan 无归一化逻辑
- **After-behavior:** 前端必须归一化登录/切角色响应为统一 UserInfo 结构，并提供刷新后用户态恢复
- **Evidence:** store 定义 `UserInfo { roles, active_role }` vs auth.py login 返回 `{user, roles, access_token}` / switch-role 返回 `{active_role}`；刷新后只 loadMenus 不恢复 user
- **Impact:** UserDropdown/home 的 roleName/schoolName 登录后可能为空；切角色不更新；刷新后用户信息丢失

### F003 — API 测试仍有空壳和前提错误
- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** `test_get_menus_role_filtering` 仍是 `pass` 空壳；`test_get_menus_authenticated` 用 `admin_token`（platform_admin）但种子菜单只给 subject_teacher/academic_director/principal
- **After-behavior:** 用 `subject_teacher_headers` fixture 写精确断言，验证角色过滤在 API 层生效
- **Evidence:** conftest.py 已有 `subject_teacher_headers` fixture（L323）可直接使用
- **Impact:** 当前测试既可能因前提错误失败，也无法捕获 router 错误

### F008 — Batch 2 验证仍依赖 Batch 3
- **Severity:** MED
- **Category:** design-concern
- **Type:** defect_fix
- **Before-behavior:** Batch 2 的登录/home 测试契约命令写 "手动端到端验证（Task 12）"，但 Task 12 在 Batch 3
- **After-behavior:** 每批有本批内可完成的独立验证点
- **Evidence:** Task 9 测试契约命令引用 Task 12
- **Impact:** Batch 2 无法独立验收

### F010 — 设计文档 schema 与 plan/代码库不一致（新发现）
- **Severity:** MED
- **Category:** design-concern
- **Type:** defect_fix
- **Before-behavior:** 设计文档写 `ALTER TABLE exam_scores` 和 `ALTER TABLE exams ADD COLUMN exam_type`，但代码中已有 `Exam.exam_type`，结果表是 `ExamResult`
- **After-behavior:** 设计文档应与 plan 和代码库统一
- **Evidence:** design:L355 `exam_scores` vs plan:L243 `ExamResult` vs exam/models.py:L28 已有 `exam_type`
- **Impact:** 设计文档作为执行依据时可能拉回错误基线

## 处置状态（R3 处置完成 2026-04-13）

| ID | 状态 | 处置 |
|----|------|------|
| F002 | resolved-correct | Task 4/6/8/10/11/12 全部补测试契约（5 字段）或明确标注"变更类型: 非行为变更" |
| F007 | resolved-correct | analytics 路径对齐 `/analytics/exam/{id}/summary` 等真实路由；getPowerOptions 改为本地 stub（返回空结构），Task 10 可正常运行 |
| F009 | resolved-correct | 新增 `applyLoginResponse` / `applySwitchRoleResponse` / `restoreFromStorage` actions；login.vue 和 default layout 调用归一化；localStorage 持久化 user |
| F003 | resolved-correct | 用 `subject_teacher_headers` 和 `admin_headers` 替换 placeholder；新增两个入口级测试（subject_teacher 可见 exam/不可见 principal-only；platform_admin 不在 seed roles → 空菜单） |
| F008 | resolved-correct | 批次表加 Batch 2 独立 Gate 4 项 + 独立验证命令段（不依赖 Task 12）；Task 9 测试契约命令改为引用独立验证段 |
| F010 | resolved-correct | 设计文档标注 `exam_scores` 为 superseded，改正为 `ExamResult`；`exams.exam_type` 标注已存在 |
