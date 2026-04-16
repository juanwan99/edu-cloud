# Plan Review R4: 好分数业务复刻 Phase 1

> [edu-cloud] GPT Reviewer | 2026-04-13
> Raw output hash: 94c6d8fdaa0d5dac838e5176b574ceb816796b7518d9e3c87bc12936f816fc2a

## 审查报告

结论: **FAIL**

依据：F011 / F013（R3 已解决表层）PASS；但发现 3 个阻塞 finding（F014 HIGH test-gap + F012 MED test-gap 未完全闭环 + F015 MED code-bug）+ F013-R4 MED design-concern（不阻塞）。

## R3 GPT 复核结论

| ID | R4 结论 |
|----|---------|
| F011 | 表层 PASS（Task 2 命令已改），但 F014 在同一测试中发现新缺口 |
| F012 | 未完全闭环 — Task 5 只有命令没有 Vitest 骨架 |
| F013 | 表层已补 superseded 说明，但未覆盖所有漂移点（F013-R4） |

## Findings

### F014 — 测试契约条件断言导致测试无效
- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** `test_get_menus_subject_teacher` 的 seeded_client fixture 只种入 exam/exam_list，测试中 `if report: ...` 分支永不执行 → 删除 MenuService 角色过滤仍能过
- **After-behavior:** fixture 真实种入 report + report_contrast，测试用直接断言（无 if）
- **Evidence:** plan:L570 fixture 缺 report；plan:L595 `if report:` 条件断言
- **Impact:** 权限回归保护失效

### F012 — Task 5 仍缺 Vitest 骨架
- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** R3 称 Task 5/6/10 全补骨架，但 Task 5 只有命令无 `it(...)` 骨架
- **After-behavior:** Task 5 补 3 个最小 it 骨架覆盖 applyLoginResponse/applySwitchRoleResponse/restoreFromStorage
- **Evidence:** plan:L1388 Task 5 vs L1571/L2526 Task 6/10

### F015 — UserRole 接口未声明 is_primary
- **Severity:** MED
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** UserRole 接口没有 `is_primary` 字段，但 applyLoginResponse 直接读 `r.is_primary`
- **After-behavior:** UserRole 加 `is_primary?: boolean`（+ `id: string`）
- **Evidence:** plan:L1197 interface vs L1278 `r.is_primary`；后端确实返回（auth.py:L78）

### F013-R4 — 设计文档 superseded 清单不完整（不阻塞 PASS）
- **Severity:** MED
- **Category:** design-concern
- 新遗漏点: §3 `roles TEXT[]`、§4 `login(phone)` / `switchRole(roleIndex)` / `/knowledge/tree`

## 处置状态（R5 处置完成 2026-04-13）

| ID | 状态 | 处置 |
|----|------|------|
| F014 | resolved-correct | seeded_client 加 report + report_exam + report_contrast；测试改直接断言 `"report" in codes` + `/report/contrast not in child_paths` |
| F012 | resolved-correct | Task 5 补 3 个 Vitest 骨架（is_primary 选中 / 保留 roles / JSON 损坏不崩） |
| F015 | resolved-correct | UserRole 接口加 `id: string` + `is_primary?: boolean`（对齐后端 auth.py 响应） |
| F013-R4 | resolved-correct | design superseded 清单扩充 4 项（§3 roles TEXT[] / §4 login phone / switchRole roleIndex / /knowledge/tree） |
