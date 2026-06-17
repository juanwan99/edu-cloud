# edu-cloud — 教育云平台

> 多校协同云端平台，学校端（exam-ai）的上游调度中心。
> 架构边界：ECS 单一权威开发环境，与原 Windows/WSL 环境完全切断。

## 交付合同

| 字段 | 值 |
|------|-----|
| 权威代码 | `frontend/src/` → `vite build` → `frontend/dist/` |
| 用户消费 URL | `https://mcu.asia`（nginx 443 → `frontend/dist/`） |
| 验证目标 | `https://mcu.asia`（唯一完成证据 URL） |
| dev server | `localhost:8080/5173`（仅调试，不可验收） |
| 后端验证 | `.venv/bin/python -m pytest --tb=short -q` |

## 启动命令

```bash
# 后端
cd /home/ops/projects/edu-cloud
.venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload

# 前端（Vite dev server）
cd frontend && npm run dev

# 测试
.venv/bin/python -m pytest --tb=short -q       # 后端
cd frontend && npx vitest run                    # 前端
```

## 硬禁令

- 前端改代码必须 `vite build` 才能让用户看到
- Migration 唯一路径：`python scripts/db_migrate [target]`（直接 alembic 命令被 guard 阻断）
- `/var/www/website/` SPA 产物禁止服务器编辑（查 `.SPA_MANAGED`）
- 禁止 `print()`/`console.log()` 用于业务日志
- 不得用 `cp`/`rsync` 复制活跃 SQLite（用 `.dump` 或 `.backup`）

## 模块治理设施（2026-06-05 Phase -1 收口 · commit 时 staged index 强制校验）

| 维度 | 真源 | 守卫脚本 |
|------|------|---------|
| 模块定义/结构 | `docs/governance/modules.yaml` + 各模块 `MODULE.md`（模板 `docs/governance/MODULE-template.md`） | `scripts/governance/module_governance_guard.py`（聚合器 `aggregate_modules.py`） |
| 运行时路由门控（Phase 0.6） | `frontend/src/config/routeAccess.js`（静态 route↔moduleCode）∪ `to.meta.moduleCode`（动态路由 `/exams/:id`、`/profile/student/:studentId` 等） | `frontend/src/router/index.js` `authGuard`：roles/permissions 通过后按学校 `enabledModules` 对直达 URL（含动态详情页）二次门控；有 `school_id` 用户 fail-closed（模块态须已加载且 moduleCode 在启用列表，否则 `next('/')`），admin 无校豁免；`loadModules` API 失败给空列表（非默认模块）使门控真 fail-closed |

> Phase 0.5（模块语义统一，设计 v4 + plan-review R1/R2 处置 + v4 必修6项处置，待实施）：将新增 `docs/governance/module-semantics.yaml`（逐入口期望表：架构模块/后端 prefix/前端 route/portal service ↔ 9 学校开关码；backend_routes 36 条 == `app.routes` 实测顶层 segment，方向 A）+ `scripts/governance/check_module_semantics.py`（6 个 check：守卫用 FastAPI `app.routes` 展开逐路由比对，前端 routeAccess/sidebar/dashboard 均做 route 级 fail-closed+一致性，行为不变、known_drift 按四元组精确豁免、frontend drift 实际探测禁过期）。已登记 10 处 known_drift = 8 backend（3 fail-open: academic/conduct/exam-imports + 5 hygiene: menus/portal/grades/teachers/client-logs）+ 2 frontend（studio/teaching），profile 后端门控已实装（0.6C 收口，从 fail-open 清单移除），其余初期只登记不修复（**0.7B 已收口 conduct/exam-imports 补门控 + menus/portal/grades/teachers/client-logs 入 exempt，详见下方 Phase 0.7B；0.7B 后 3 条；0.7D 已收口 academic 双面 fail-open → 现存 known_drift = studio 前端，共 1 条**）；`schoolSettings.js` 设置写入消费点纳入零 diff gate。CI 接入 backend job（重依赖）。设计见 `docs/superpowers/specs/2026-06-05-module-semantics-design.md`、计划见 `docs/superpowers/plans/2026-06-05-module-semantics-implementation.md`。

> Phase 0.6 + 0.6C（已实施，HEAD 见 `docs/context/NOW.md`）：`authGuard` 对直达 URL 二次模块门控（`8606ac6`/`bd8be46`）；0.6C 覆盖完整性子任务处置 codex-review R4 F-001/F-002——`check_module_semantics.py` 将 `router_meta` 升为完整门控面：每个受控 route（`fr` 非 null）必须在 router-meta 标 `moduleCode`、动态路由 fail-closed，守卫绿 == 运行时无 fail-open；`/profile/student/:studentId` 补 `study_analytics` 门控堵直达。

> Phase 0.7A（已实施，处置 R5 F-001 MED security_design）：前端**可见性 surface** 统一 fail-closed。`routeAccess.js` 新增显式门控上下文 `createModuleGate`/`moduleGateFromAuth`（`{exempt,modulesLoaded,enabledModules}`），取代「空数组同时表达 未加载/失败/无模块/admin豁免」的 fail-open；`moduleMatches` 改 fail-closed（exempt 显式豁免）。`AppSidebar`/`AppHeader`/`RoleSwitcher`/`DashboardPage` 4 个 surface 经 `moduleGateFromAuth(auth)` 取门控，与 `authGuard` 数学等价（allow IFF 无 school_id 豁免 OR (已加载 && 启用)）；删 `AppHeader.moduleFallbacks` + `DashboardPage` 死代码 fallback。authGuard 不动。R6/R7 codex F-001：`RoleSwitcher` 切换身份后对**当前已匹配路由**改用 `canAccessMatchedRoute(role, path, route.meta, gate)`（routeAccess.js）——覆盖静态精确表 ∪ 动态 `route.meta`（**权限 + 模块**两维，与 authGuard 同源），堵动态子路由（`/exams/:id`、`/exams/:examId/ai-grading/:subjectId`）「停留动态模块/高权页 → 切到未启用该模块或无该权限的身份」绕过 fail-closed。

> Phase 0.7B（drift burn-down，进行中）：后端中间件门控硬化。①（item3/R5-DC2 + R2 段边界加固）`module_middleware.py` 抽 `resolve_module_code`/`_longest_prefix_match`/`_prefix_matches`，匹配规则由 dict 插入序首匹配改为**最长前缀优先**且**段边界安全**（`==` 或 `prefix+'/'`，防 `/api/v1/conductors` 误命中 `/api/v1/conduct`），与守卫 `check_module_semantics._actual_gating` 严格同算法（exempt-first → ROUTE_MODULE_MAP 最长前缀；exempt 与 gated 前缀集互斥，重排 inert）——收口规则漂移（守卫绿但运行时重叠前缀/邻接同段名可命中错误模块）。②（item4）`ROUTE_MODULE_MAP` 补 `/api/v1/conduct→conduct`、`/api/v1/exam-imports→exam`，收口后端 fail-open drift（参照 0.6C profile；前端已标 moduleCode、authGuard 已 fail-close，后端补同源门控=模块关即不可用）。**academic 不补门控**：前端 `/academic/*` 仅 permission 无 moduleCode（teaching-frontend-unwired），单独后端 gating 会让有 manage_scheduling 但 teaching 关闭的校 403 破坏页面，需前端 wiring 配套（超出 0.7B「不改业务 UI」），保留为 known_drift。③（item5）`EXEMPT_PREFIXES` 补 menus/portal/grades/teachers/client-logs（本就 pass-through，显式豁免，行为零变更）。守卫 stale-drift 检测强制：收口入口须同步删 `backend_routes` drift 字段 + `known_drift` 登记（11→3：academic + studio + teaching）。

> Phase 0.7D（academic 双面 fail-open 收口，已实施）：**撤销 0.7B「academic 不补门控」决定**。前端 `/academic/*`（teaching-plans/timetable/semesters）三 surface（`routeAccess`/`router-meta`/`sidebar`）加 `moduleCode:teaching`，后端 `ROUTE_MODULE_MAP` 补 `/api/v1/academic→teaching`——authGuard 直达拦截 + 中间件 403 + 前端可见性三处同源 fail-closed。`module-semantics.yaml` 删 `academic-backend-fail-open` + `teaching-frontend-unwired` 两条 drift（`check_module_semantics._FRONTEND_DRIFT_PROBES` 保留 teaching 探测器作回退守护：academic 若被改回未接线且无登记则 fail-closed 报红），known_drift 3→1（仅余 `studio-frontend-entry-missing`）。teaching 默认未开启（不改 `DEFAULT_ENABLED`）；缺 `SchoolModule(teaching)` 行的语义见下方 Phase 0.7E（F-001 absent-row 收口）。

> Phase 0.7E（F-001 absent-row fail-open 收口，已实施）：撤销 0.7D 对 codex-review F-001 的 WONTFIX——设计者改判 **Option B「全系统原则性修复」**。`module_middleware.py` 缺行判定抽纯函数 `module_enabled_default(code,row)` 对齐前端 `get_all_modules`（`services/school_settings_service.py:109` `else (code in DEFAULT_ENABLED)`）：**present row** 显式 `enabled` 优先（行为不变）；**absent row** 仅 `code in DEFAULT_ENABLED` 才放行——非默认模块（teaching/research/study_analytics）缺行 **fail-closed 403**，默认模块（exam/grading/homework/calendar/studio/conduct）缺行仍 pass-through。后端 403 面与前端可见性面自此单一真源，闭合全系统 absent-row fail-open（不止 academic）。`init_school_modules` 为新校建全 9 行 → 正常学校 present row、行为不变，仅未 backfill 的存量缺行学校受 fail-closed（安全修复非破坏）。补 6 纯函数单测（脱离 DB/JWT 直测三态）+ 受影响测试经 `tests/_module_seed.py` seed `SchoolModule(enabled=True)`。teaching 仍不在 `DEFAULT_ENABLED`；known_drift 仍 1（studio）。**R1（codex-review F-001 HIGH test_gap 收口）**：原 6 纯函数单测未经 HTTP dispatch 入口验证——突变缺行判定为 fail-open（`enabled=True if row is None ...`）后原 87 目标测试仍全过；补最小 FastAPI app + `ModuleCheckMiddleware` + ASGITransport 的 dispatch 回归 4 测试（`tests/test_api/test_module_middleware.py`：缺 `SchoolModule(teaching)` 行→HTTP 403 / 显式 enabled 放行 200 / 显式 disabled 403 / DEFAULT_ENABLED 缺行放行），突变下核心测试失败 catch 回归，关闭 test_gap（未改生产 middleware 语义/`DEFAULT_ENABLED`）。

## 按需上下文（需要时 Read）

| 信息 | 路径 |
|------|------|
| 项目结构 + 模块列表 | `docs/reference/REPO_MAP.md` |
| API 端点完整表（320 路由） | `docs/reference/API_ENDPOINTS.md` |
| 角色体系 + 权限映射 | `docs/reference/ROLES.md` |
| 数据模型（88 表） | `docs/reference/DATA_MODELS.md` |
| 技术栈 + 部署 + 端口 | `docs/reference/TECH_STACK.md` |
| 活跃设计/计划索引 | `docs/context/ACTIVE_INDEX.md` |
| 日志查询工具 | `scripts/edu-log <command> --help` |

## 测试基线（单一真源，CI-aligned）

- 后端完成口径 = `.github/workflows/test.yml` backend job 的「Backend pytest (main suite)」过滤集（== `scripts/codex-verify` 的 `CI_BACKEND_PROFILE`）；由 `scripts/pytest_delta.py` 对 `.quality/known-pytest-failures.txt` 跑 no-new-failures 门控。**已知失败清单以该文件为唯一真源，不在文档硬编码失败数**（历史数字如 12/22/26 已废弃，见 `docs/governance/debt-ledger.md` D-07）。本地核验：`scripts/codex-verify backend`。
- 前端：`cd frontend && npx vitest run`（已知失败见运行输出，不在文档硬编码计数）。
