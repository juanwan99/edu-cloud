# Plan Review R1: 好分数业务复刻 Phase 1

> [edu-cloud] GPT Reviewer | 2026-04-12 22:16:44
> Raw output hash: 5fd4eff940bb0d72d5c126d2ae190288f976cbd7f1a0cdc23e3dbced94387e57

## 审查报告

结论: **FAIL**

依据：code-bug HIGH 3 条、test-gap HIGH 2 条、test-gap MED 2 条；Contract Pack 缺失。

## Findings

### F001 — Contract Pack 缺失
- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** plan 不包含 Contract Pack（invariants / counter_examples / risk_modules / test_debt 全部缺失）
- **After-behavior:** 补齐 schema 合规的 contract_pack 段，覆盖 public API 变更、migration、前端壳层替换
- **Evidence:** phase1-plan.md 全文未出现 contract_pack / invariants / counter_examples / risk_modules / test_debt
- **Impact:** F 项直接不通过，后续 Gate 无法判断不变量和风险模块

### F002 — 多数 Task 缺测试契约和边界条件
- **Severity:** HIGH
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** 仅 Task 2 有测试契约（2 个），仅 Task 2 和 Task 10 有边界条件
- **After-behavior:** 每个行为变更 Task 须有 5 字段测试契约 + 至少 3 条边界条件
- **Evidence:** Task 1/3/4/5/6/7/8/9/11 均缺失
- **Impact:** 执行者无法按 Gate 要求逐行为验证

### F003 — Task 2 API 测试弱断言
- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** 测试契约入口声称 GET /api/v1/menus，但命令跑的是 MenuService 内部单测；API 测试仅断言 200 + list
- **After-behavior:** 入口级验证覆盖角色过滤/模块过滤，反例字段填实
- **Evidence:** plan L604-608 入口/命令不一致，L509-516 弱断言

### F004 — menu router 与现有认证契约不匹配
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** plan 用 `user.get("active_role")` 取角色，实例化 `SchoolSettingsService(db)`
- **After-behavior:** 对齐 `get_current_user` 实际返回结构，复用现有 `get_enabled_modules(db, school_id)` 函数式 API
- **Evidence:** deps.py L23/L63 返回结构 vs plan L520-537；school_settings_service.py L53 是函数不是 class

### F005 — ARRAY(String) 与 SQLite 方言不兼容
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** menu_configs.roles 用 PostgreSQL ARRAY(String)，Alembic smoke test 在 SQLite 上跑
- **After-behavior:** 选择跨方言存储（如 JSON），或调整 migration 测试策略
- **Evidence:** plan L124 ARRAY(String)；test_alembic_migration.py 用 SQLite

### F006 — 模型文件路径不一致 + import 链断裂
- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** 文件结构写 `analytics/models.py`，Task 1 实际创建 `analysis_models.py`；无显式 import 注册
- **After-behavior:** 统一模型落点，显式 import 确保 Alembic autogenerate 可见
- **Evidence:** plan L27-28 vs L90；app.py 和 test_alembic_migration.py 无新模型 import

### F007 — useApi 引用不存在的后端端点
- **Severity:** HIGH
- **Category:** code-bug
- **Type:** defect_fix
- **Before-behavior:** useApi 固化了 `/analytics/power-options`、`/study/*`、`/knowledge/tree`、`/bank/paper/generate`、`/grades` 等当前不存在的端点；`switchRole` 用 `role_index` 但后端用 `role_id`
- **After-behavior:** 前端 API 层从现有后端路由反推，不存在的端点标注为 Phase 2/3 待实现
- **Evidence:** plan L1189-1245；后端 auth.py L40 用 role_id；grep 不到 power-options / study/dashboard 等路由

### F008 — 缺少批次拆分和回滚边界
- **Severity:** MED
- **Category:** design-concern
- **Type:** defect_fix
- **Before-behavior:** 12 个 Task 在同一 Phase 主线上，无批次边界和独立 Gate
- **After-behavior:** 按风险拆批（schema → API → frontend-shell），每批独立验证
- **Evidence:** Phase 1 规模 ~60 前端 + ~8 后端 + 2 migration

## 处置状态（R2 处置完成 2026-04-12 22:37）

| ID | 状态 | 处置 |
|----|------|------|
| F001 | resolved-correct | plan 新增 Contract Pack 段（invariants 6 条 / counter_examples 4 / risk_modules 4 / test_debt 3） |
| F002 | resolved-correct | 逐 Task 补齐测试契约（5 字段）+ 边界条件（≥3 条），覆盖 Task 1-11 |
| F003 | resolved-correct | Task 2 API 测试加强断言（结构完整性 + 角色过滤入口级验证）+ 测试契约新增第 3 条 |
| F004 | resolved-correct | router 改用 `user["current_role"]`（UserRole ORM）+ `get_enabled_modules(db, school_id=...)` 函数式调用 |
| F005 | resolved-correct | `ARRAY(String)` → `JSON` + `server_default="[]"`，兼容 SQLite smoke test |
| F006 | resolved-correct | 文件结构段统一为 `analysis_models.py` + Task 1 新增 Step 6 显式 import 到 app.py |
| F007 | resolved-correct | useApi 全部方法对齐后端实际路由；switchRole 改 role_id；不存在端点注释为 Phase 2/3 待实现 |
| F008 | resolved-correct | 拆为 3 个批次（Batch 1 Schema+API / Batch 2 Frontend 骨架 / Batch 3 Frontend 完善），每批独立验证 |
