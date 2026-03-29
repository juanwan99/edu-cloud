[edu-cloud] GPT Reviewer | 2026-03-29 20:35:04
## 审查报告: Task 1-7
结论: FAIL

Raw output hash: `db65a7a2925b3629115846083d1e0d6053988c4d15a94791c079072f84ae80bb`
Raw output: `docs/plans/.codex-code-review-phase1a-raw.log`

### 第一段：测试充分性（Test Adequacy）

**整体评价：** 测试覆盖面较全（9 个 service tests + 12 个 API tests + 6 个 middleware tests + 3 个 Vitest），但存在两个结构性缺陷：
- 中间件"允许通过"断言使用 `!= 403` 而非明确状态码，无法区分"正常放行"和"异常放行"（404/500 也会通过）
- SchoolSetting 的唯一约束测试缺失（只测了 SchoolModule 的唯一约束）
- Contract Pack 段落在 plan 中未独立成段

### 第二段：行为正确性（Behavioral Correctness）

**变更理解：** 新增学校配置体系（KV settings + 模块开关），包含 ORM 模型、Service 层 CRUD、API 端点（5 个）、中间件硬拦截、前端 sidebar 模块过滤、管理页面。9 commits 覆盖 7 个 Task。

**Executor 自审抽检：** 抽检 handoff 中的 "marking 路由映射到 grading 模块" 自审声明。验证 `module_middleware.py:30` 确认 `"/api/v1/marking": "grading"` 映射存在，自审准确。抽检 "JWT 不含 school_id，中间件从 active_role_id→UserRole 查询 school_id"，验证 `module_middleware.py:82-101` 确认流程正确，自审准确。

**对抗性审查：** GPT 枚举了全部 16 个 APIRouter prefix 与 ROUTE_MODULE_MAP 逐一比对，发现 `/api/v1/card`（实际）vs `/api/v1/cards`（映射）不匹配（F-02）。GPT 追踪了 `require_permission` 实现，确认只做权限检查不做 school_id scope 校验，构造了"principal 改 URL 访问他校配置"的攻击路径（F-01）。GPT 追踪了 auth.js hydration 路径，确认 enabledModules 在 localStorage 恢复链路中缺失（F-03）。

**关键问题：**
1. **跨校越权（F-01）**：settings router 只校验权限，不验证 URL 中 school_id 与当前角色 school_id 一致性
2. **路由映射错误（F-02）**：中间件映射 `/api/v1/cards` 但实际路由前缀是 `/api/v1/card`，禁用 exam 后 card API 仍可访问
3. **页面刷新状态丢失（F-03）**：enabledModules 不持久化也不在刷新时重载，导致 sidebar 显示全部模块

### 第三段：未测试风险（Non-tested Risks）

- 中间件对 DB 查询异常的处理：async_session 连接失败时 middleware 会直接放行（catch-all）
- 并发场景：init_school_modules 在两个端点中调用，理论上存在并发初始化竞争
- `loadModules` catch 分支硬编码默认模块，如果 API 返回非网络错误（如 401），也会降级到默认模块

### 发现清单

#### F-01 | HIGH | code-bug | verified
**跨校越权：settings router 缺少 school_id scope guard**

Evidence: `src/edu_cloud/modules/school/settings_router.py:31-95`、`src/edu_cloud/api/deps.py:71-76`

`require_permission(Permission.MANAGE_SCHOOL_SETTINGS)` 只检查用户是否拥有该权限，不校验 URL 中 `school_id` 参数是否属于当前角色的 school scope。principal/academic_director 修改 URL 即可读写其他学校配置。

Impact: 任意 school-scoped admin 可跨校越权读写 settings/modules。安全问题。

Suggested action: 在 router 中增加 scope guard，对 school-scoped 角色强制 `school_id == current["current_role"].school_id`，平台/区域角色放行。补跨校访问返回 403 的负向测试。

#### F-02 | HIGH | code-bug | verified
**中间件路由映射错误：`/api/v1/cards` ≠ `/api/v1/card`**

Evidence: `src/edu_cloud/api/module_middleware.py:27`、`src/edu_cloud/modules/card/router.py:30`

中间件 ROUTE_MODULE_MAP 写的是 `"/api/v1/cards": "exam"`，但实际 card router prefix 是 `/api/v1/card`。`"/api/v1/card/xxx".startswith("/api/v1/cards")` 为 False，所以禁用 exam 模块后 card API 不受影响。

Impact: 核心功能——禁用模块后 API 硬拦截——对 card 路由失效。

Suggested action: 改为 `"/api/v1/card": "exam"`。补回归测试：禁用 exam 后请求 `/api/v1/card/*` 应返回 403。

#### F-03 | MED | code-bug | verified
**页面刷新后 enabledModules 未恢复**

Evidence: `frontend/src/stores/auth.js:35-41`、`frontend/src/stores/auth.js:69,90`

`enabledModules` 和 `modulesLoaded` 在 hydration 时不从 localStorage 恢复，且 `loadModules()` 仅在 `login()`/`switchRole()` 中调用。页面刷新后 `modulesLoaded=false`，sidebar computed 逻辑为"未加载时显示全部"→ 用户看到所有模块。

Impact: 刷新页面后 sidebar 前后端不同步，用户看到已禁用模块的导航项。

Suggested action: 在 AppShell.vue `onMounted` 中（或 store hydration 后），若有 token 且 currentRole 有 school_id，调用 `auth.loadModules()`。

#### F-04 | MED | test-gap | verified
**中间件"允许通过"测试使用弱断言 `!= 403`**

Evidence: `tests/test_api/test_school_settings.py:255,292,353`

`test_middleware_allows_enabled_module`、`test_middleware_no_school_id_skips_check`、`test_middleware_multi_school_isolation` 的正向断言只是 `status_code != 403`。如果实现返回 500/404/422，测试仍然通过。

Impact: 测试无法区分"正常放行"和"异常错误"，contract 验证不完整。

Suggested action: 改为断言具体状态码（如 200）或至少 `assert resp.status_code < 400`。

#### F-05 | MED | test-gap | verified
**SchoolSetting 唯一约束测试缺失 + Contract Pack 段未独立**

Evidence: `tests/test_services/test_school_settings_service.py`（只有 SchoolModule 唯一约束测试）、plan 边界条件声称"同 school_id+key 重复 → IntegrityError"但无对应测试

Impact: plan 声明的 invariant verification mapping 不准确，SchoolSetting 重复 key 约束未被测试覆盖。

Suggested action: 补 `test_school_setting_unique_constraint` 测试。

---

### PASS/FAIL 判定

| Finding | Severity | Category | Status | 阻塞? |
|---------|----------|----------|--------|--------|
| F-01 | HIGH | code-bug | verified | **阻塞** |
| F-02 | HIGH | code-bug | verified | **阻塞** |
| F-03 | MED | code-bug | verified | **阻塞** |
| F-04 | MED | test-gap | verified | **阻塞** |
| F-05 | MED | test-gap | verified | **阻塞** |

**结论：FAIL** — 2 个 HIGH code-bug + 1 个 MED code-bug + 2 个 MED test-gap 未修复。
