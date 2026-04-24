---
topic: 2026-04-24-super-admin-cross-school-account
gate: plan_review
round: 1
status: FAIL
reviewer: gpt (codex MCP)
plan_commit: 8f9c03540476e77f5c32282a0d777c86ab6c825f
raw_output_log: docs/plans/.codex-raw-plan-review-super-admin-r1-20260424_234500.log
raw_output_sha256: 2537f0d802a34a1c4255390ed9fcb1050b3e45a526592570d492f354465bcfec
mcp_thread_id: 019dc035-3d62-72f3-8fb5-08eebddb4caf
reviewed_at: 2026-04-24T23:45:00+08:00
summary: 3 HIGH + 4 MED，R2 允许（跨模块 ≥2 文件 ≥2 模块，满足 R2 条件 3）
---

# Plan Review R1 Report — super-admin-cross-school-account

## 原始 GPT 输出

见 `docs/plans/.codex-raw-plan-review-super-admin-r1-20260424_234500.log`（sha256 `2537f0d8...ec`）。

## Finding 三态标注

| ID | Severity | Type | Category | Verdict | 备注 |
|---|---|---|---|---|---|
| F001 | HIGH | test_gap | 完整性/不变量 | **valid** | ORC-004 后端契约（超管跨校 `role=subject_teacher` → 201，保持 `ALL_SCHOOL_ROLES`）无测试回放 |
| F002 | HIGH | test_gap | 完整性/测试质量 | **valid** | Step 1.2 "6 测试全红" 不成立：`test_platform_admin_creates_academic_director` + 其他弱断言测试在现状代码下会直接绿（Pydantic v2 extra='ignore' + UserRole.school_id nullable） |
| F003 | HIGH | defect_fix | 自洽性/行为契约 | **valid** | `openCreate` 不重置 `form.roles`，超管跨校打开表单默认 `['subject_teacher']`，用户不改角色直接保存会造出"景炎 subject_teacher 跨校账号"，偏离"创建学校管理账号"产品意图 |
| F004 | MED | defect_fix | 代码库对齐/范围控制 | **valid** | `roleOptions` 同时服务创建表单（L77）和 Excel 导入（L102 `importRole`），改全局 computed 会连带裁剪导入下拉 → 超出 scope |
| F005 | MED | test_gap | 完整性/测试质量 | **valid** | Task 2 全部 4 测试都用 `wrapper.vm.xxx` 断言，是 `ORC-003` DOM 渲染条件的逻辑镜像；缺 DOM 级入口验证 |
| F006 | MED | process | 自洽性/回滚 | **valid** | Step 3.3 场景 C 用 `localStorage.getItem('edu_cloud_token')`，实际键名是 `'token'`（已 grep 确认 `frontend/src/stores/auth.js:32/67/117`）；场景 A/D 在生产 mcu.asia 创建真实账号无 cleanup |
| F007 | MED | process | 完整性/审查流程 | **valid** | plan 缺每 Task 的"审查清单"和"边界条件 ≥3"段，违反 review-templates.md:206-215 writing-plans 必填要求 |

## R2 升级判定

按 codex-review skill §Gate 条件 R2 允许条件：
- Tier = T4？**否**（T3）
- topic 含 remote/deploy/publish？**否**
- **跨模块重构（plan 声明修改文件数 ≥2 且涉及 ≥2 个模块）？是** —— plan 修改 `src/edu_cloud/modules/student/teacher_router.py`（后端 student 模块）+ `frontend/src/pages/TeachersPage.vue`（前端 pages 模块）+ `frontend/src/api/schools.js`（前端 api 模块），≥3 文件 ≥2 模块

**结论：R2 允许**。

## 处置动作

F001-F007 全部 valid，按 finding 逐条在 plan 中修订：

| Finding | 修订位置 | 动作 |
|---|---|---|
| F001 | Task 1 Step 1.1 测试文件 + Self-Review §5 ORC-004 映射 | 新增测试 `test_platform_admin_creates_subject_teacher_cross_school` 断言 201 + role 落库 + ORC-004 双映射到 Step 1.1 此用例 + Step 2.1 |
| F002 | Task 1 Step 1.1 测试 + Step 1.2 描述 | `test_platform_admin_creates_academic_director` 加 `UserRole.school_id` 落库断言；`test_platform_admin_creates_principal_in_target_school` 已有此断言保留；Step 1.2 描述修正为"现状代码下 orphan_principal 和 subject_teacher 跨校这 3 个测试 FAIL（422/403/body 不匹配），其他 3 个测试 PASS 但在加强断言后也会 FAIL（school_id 落库不对）" |
| F003 | Task 2 新增 Step 2.6a（或放进 Step 2.7 前）+ 测试 Step 2.1 新增用例 | `openCreate()` 在 `isPlatformAdmin && selectedSchool` 时把 `form.roles` 初始化为 `['principal']`（默认管理角色）；新增测试"超管跨校 openCreate 后未手改角色时 form.roles === ['principal']" |
| F004 | Task 2 Step 2.5 重构 | 拆 `createRoleOptions`（computed，跨校裁剪）与 `importRoleOptions`（静态，全集）；模板 L78 用 `createRoleOptions`，L102 用 `importRoleOptions` |
| F005 | Task 2 Step 2.1 测试增强 | 新增 DOM 级断言：`wrapper.find('[data-testid="school-select"]').exists()` 或通过 `wrapper.html()` 搜 `学校` 下拉是否渲染；模板中 `<n-select>` 加 `data-testid` |
| F006 | Task 3 Step 3.3 | token 键改 `'token'`；场景 A/D 末尾追加 cleanup（DELETE /teachers/{id} 或手动登录 mcu.asia admin 删除） |
| F007 | 每 Task 新增"审查清单"+"边界条件（≥3）"段 | Task 1 / Task 2 / Task 3 各补两段 |

## R2 入口预期

修订完成后触发 codex-review plan R2（MCP 路径），预期 GPT 重点核对：
1. ORC-004 双映射（后端 Step 1.1 新 case + 前端 Step 2.1）
2. Step 1.2 红灯描述准确性
3. form.roles 重置逻辑
4. roleOptions 拆分
5. DOM 级测试存在
6. Task 3 token 键与 cleanup
7. 每 Task 审查清单 + 边界条件段
