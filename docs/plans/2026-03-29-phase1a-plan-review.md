# Phase 1a Plan Review — GPT 5.4 独立审查

> **审查者**: GPT 5.4 (Codex MCP)
> **时间**: 2026-03-29 18:08:42
> **结论**: **FAIL** (7 HIGH + 1 MED)

## Findings

### F-01 [HIGH] code-bug: Permission 枚举名错误 + 前端路由守卫字段名错误

**Evidence**: 计划使用 `Permission.MANAGE_SCHOOL`，实际代码库是 `Permission.MANAGE_SCHOOLS`。前端路由用 `meta.permission` (单数)，实际代码用 `meta.permissions` (复数数组)。

**Impact**: 后端鉴权和前端页面守卫均不可运行。

**Action**: 统一改为 `Permission.MANAGE_SCHOOLS` 和 `meta: { permissions: ['manage_schools'] }`。

### F-02 [HIGH] code-bug: 函数名/工厂名引用错误

**Evidence**: 计划引用 `decode_access_token` 和 `async_session_factory`，实际是 `decode_token` (shared/auth.py:13) 和 `async_session` (database.py:6)。

**Impact**: 中间件导入时直接失败。

**Action**: 改为 `decode_token` / `async_session`。

### F-03 [HIGH] design-concern: JWT 不含 school_id，中间件无法获取学校范围

**Evidence**: 现有 token 只写入 `sub`/`role`/`active_role_id`，不含 school_id。平台管理员上下文也没有 school_id。

**Impact**: 模块检查中间件的核心前提不成立。

**Action**: 中间件从 JWT 获取 active_role_id → 查 DB 获取 UserRole.school_id。或在 login/switch-role 时将 school_id 写入 token。

### F-04 [HIGH] code-bug: 模块映射不一致

**Evidence**: 中间件有 `marking` 但 MODULE_CODES 里没有。exam/students/scan 等核心路由被豁免，模块开关对它们无效。

**Impact**: "禁用模块后 API 硬拦截"目标不完整。

**Action**: 建立集中式模块元数据（module_code → route_prefixes → sidebar_items → agent_tools），消除多处手写映射。

### F-05 [HIGH] code-bug: 前端 store 类型错误 + sidebar 配置结构不匹配

**Evidence**: auth store 是 setup-store (ref/computed)，计划用 options-store 写法 (this.xxx)。sidebar 用 `{ icon, label, route }`，计划用 `{ key, icon }`。

**Impact**: 前端实现直接报错。

**Action**: 用 `const enabledModules = ref([])`；sidebar 扩展为 `{ icon, label, route, moduleCode }`。

### F-06 [HIGH] code-bug: Alembic 模型导入遗漏

**Evidence**: alembic/env.py 要求显式导入每个模型才能 autogenerate。计划未提及这一步。test_alembic_migration.py 也需要更新。

**Impact**: `alembic revision --autogenerate` 看不到新表。

**Action**: Task 5 补充 alembic/env.py 和 test_alembic_migration.py 的导入。

### F-07 [HIGH] test-gap: 前端任务无自动化测试 + 多个 Task 缺测试契约

**Evidence**: Task 6/7 只做 vite build。Task 3 无测试契约段。中间件测试只覆盖单路径。

**Impact**: 无法证明"sidebar 和 API 同步响应"的主目标。

**Action**: 补三类自动化契约：(1) API 多学校隔离；(2) store/sidebar 模块过滤；(3) 中间件多路径覆盖。

### F-08 [MED] design-concern: 路由注册策略矛盾

**Evidence**: File Map 写"修改 school/router.py"，Task 3 却在 app.py 注册。

**Impact**: 实现者困惑，可能重复注册或嵌套前缀。

**Action**: 选一种，推荐 app.py 直接注册 + settings_router 自带完整前缀。
