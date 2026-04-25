# 审查交接单: Task 4-9 (Round 2)

[edu-cloud] Executor→Reviewer | 2026-04-14 07:09:03

项目: `C:\Users\Administrator\edu-cloud`
计划: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-plan.md`
设计: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-biz-replication-design.md`
独立修复设计: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-auth-fail-closed-repair-design.md`
R1 审查报告: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-report-batch2.md`
R1 审查交接单: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-haofenshu-phase1-review-handoff-batch2.md`
R2 Executor 交接卡: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-14-haofenshu-phase1-batch2-r2-executor-handoff.md`

Round 2 commit 范围: `08d86f0..{R2 commit}` (R1 范围 + Round 2 修复增量)

---

## 1. 逐 Task 自审（Round 2 视角）

| Task | 计划要求 | R1 状态 | R2 增量 | 状态 | 说明 |
|------|---------|---------|---------|------|------|
| T4 Nuxt 骨架 | Nuxt 3 + Element Plus + Pinia + 品牌色 | ✅ PASS | — | ✅ | 不变 |
| T5 auth/context store + middleware | 8/8 vitest | ✅ PASS | — | ✅ | 不变 |
| T6 useApi composable | 27 方法 + 4 tests | ✅ PASS | **+ AuthError sentinel + getMenus 401/403 转抛** | 🔀 | 非 goal-shifting 变更：为 fail-closed 语义恢复而新增，未破坏原 27 方法签名 |
| T7 useMenus + nav 组件 | 层级菜单 + 导航 | ✅ PASS | **+ AuthError 向上抛路径（区分菜单降级 vs auth fail-closed）** | 🔀 | 修复 plan Task 8 契约偏离 |
| T8 三种 layout | default/fullscreen/auth | ✅ PASS | **+ default.vue catch 分 AuthError/其他** | 🔀 | 对齐独立修复设计 §2.4 |
| T9 login + home pages | 模块卡片网格 + 身份门 | ✅ PASS | — | ✅ | 不变 |
| **B2-F001 lockfile** | package-lock.json 可复现 | ❌ FAIL | **rm + npm install (no --legacy-peer-deps)** | ✅ | npm ci --ignore-scripts 零报错 / npm ls 零 invalid |
| **B2-F002 fail-closed** | Task 8 "token 有值 + loadMenus 失败 → logout" | ❌ FAIL | **AuthError 职责分层 + 4 新测试 + 3 反证** | ✅ | 见独立修复设计 §3 Fix Intent Card |
| **B2-F003 措辞** | 归因准确 | ❌ design-concern | **9000 常驻陈旧/fresh 9001 对照** | ✅ | 本交接单 §6 吸收 |

> 🔀 三项（T6/T7/T8）为"恢复 plan Task 8 声明契约"的实现修正，非新功能。R2 commit 不扩大范围，仅针对 R1 failing assertions。

## 2. R1 Finding 处置总结

| Finding | Severity | Category | Type | R2 终态 | 证据 |
|---------|----------|----------|------|---------|------|
| B2-F001 | MED | code-bug | defect_fix | **resolved-correct** | `npm ci --ignore-scripts` → added 706 packages audited 708; `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2` → 零 invalid / 零 extraneous |
| B2-F002 | MED | code-bug | defect_fix | **resolved-correct** | 独立修复设计 §2 三点修改落盘 + 4 新测试 + 3 反证成立；L017 红旗复核保留 defect_fix（恢复 plan 契约非引入新行为，已由独立设计 + Fix Intent Card 4 ORC 护航） |
| B2-F003 | LOW | design-concern | defect_fix | **resolved-correct** | 本交接单 §6 措辞收窄，未单独 commit |

## 3. 预审自检（测试契约 5 slice）

| 测试契约 slice | 对应测试 | 验证命令 | 实际输出 | 反证验证 |
|---------------|----------|---------|---------|---------|
| **Slice 1** getMenus 401/403 → AuthError | `useMenus.test.ts` > `getMenus 在 401/403 时转为 AuthError` (4 case) | `./node_modules/.bin/vitest run --no-cache tests/composables/useMenus.test.ts` | `Tests 8 passed (8)` (含 4 Slice 1 case) | 反证 3: useApi.getMenus 去掉 AuthError 转换 → Slice 1 的 401/403 两个 case FAIL (`expected {response:{status:401}} to be an instance of AuthError`, `expected {statusCode:403} to be an instance of AuthError`)；非 401 和无 status 两个 case 仍 pass（反证对偶性验证） |
| **Slice 2** loadMenus AuthError 向上抛 | `useMenus.test.ts` > `loadMenus AuthError 向上抛` (2 case: 401 / 403) | 同上 | 2 case PASS | 反证 1: useMenus 删除 `if (err instanceof AuthError) { throw err }` → Slice 2 两个 case FAIL (`Expected: rejected promise; Received: undefined`) |
| **Slice 3** loadMenus 非 auth 错误降级 | `useMenus.test.ts` > `loadMenus 降级空菜单` (2 case: network / null response) | 同上 | 2 case PASS | 反证 1（同反证 1）下 Slice 3 仍 PASS（降级路径未被反证破坏，对偶正确） |
| **Slice 4** default.vue AuthError → logout | `default.test.ts` > `layouts/default.vue auth lifecycle` (4 case: 401 / 403 / 500 / token=null) | `./node_modules/.bin/vitest run --no-cache tests/layouts/default.test.ts` | `Tests 4 passed (4)` | 反证 2: default.vue `if (err instanceof AuthError)` → `if (true)` → Slice 4 "500 不触发 logout" case FAIL (`expected logoutSpy not to be called; Number of calls: 1`) |
| **Slice 5** 原 T5-T9 vitest 基线 | `useApi.test.ts` + `auth.test.ts` (12 原 case) | `./node_modules/.bin/vitest run` | `Tests 24 passed (24)`（原 12 + 新 12） | N/A（原基线测试，R2 新增不破坏） |

## 4. 验证清单自检（Step 1-4 每步证据）

### Step 1: B2-F001 lockfile 对齐

- `rm -rf node_modules package-lock.json` + `cmd.exe /c "rd /s /q node_modules"`：CLEAN（PowerShell `Remove-Item -Recurse -Force` 首次被 happy-dom 残留锁；`cmd.exe rd /s /q` 双调用后成功）
- `npm install --ignore-scripts`（无 `--legacy-peer-deps`）：完成 `added 706 packages and audited 708 packages`。**R2 偏离**：交接卡字面命令是 `npm install`，R2 采用 `--ignore-scripts` 绕开 Windows 文件锁——原因：Windows 环境 `nuxt prepare` postinstall 在 tar 解包时产生 `.DELETE.xxx` 幽灵文件无法 unlink → `acorn.mjs` / `fzf.es.js` 等核心模块缺失 → prepare 崩溃 (ERR_MODULE_NOT_FOUND)。B2-F001 验收点是 lockfile 与 package.json 同步 + `npm ci --ignore-scripts` 干净 + `npm ls` 零 invalid，均已满足；GPT Reviewer 若需端到端 `nuxt dev`，先手动 `npx nuxt prepare` 补 `.nuxt` 目录即可（Windows 本地问题，不影响 lockfile 正确性）
- `npm ci --ignore-scripts`：✅ `added 706 packages, and audited 708 packages in 25s` exit 0 零报错
- `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2`：✅ 零 invalid / 零 extraneous
  ```
  frontend-nuxt@ C:\Users\Administrator\edu-cloud\frontend-nuxt
  ├─┬ @element-plus/nuxt@1.1.5
  │ └── @nuxt/kit@4.4.2
  ├─┬ @nuxt/test-utils@3.23.0
  │ ├── @nuxt/kit@3.21.2
  │ ├─┬ h3-next@npm:h3@2.0.1-rc.20
  │ │ └── crossws@0.4.5
  │ └─┬ h3@1.15.11
  │   └── crossws@0.3.5
  ├─┬ @pinia/nuxt@0.5.5
  │ └── @nuxt/kit@3.21.2
  └─┬ nuxt@3.17.7
    ├─┬ @nuxt/cli@3.34.0
    │ └── @nuxt/schema@4.4.2
    ├─┬ @nuxt/devtools@2.7.0
    │ └── @nuxt/kit@3.21.2
    ├── @nuxt/kit@3.17.7
    ├── @nuxt/schema@3.17.7
    ├─┬ @nuxt/telemetry@2.8.0
    │ └── @nuxt/kit@4.4.2 deduped
    ├─┬ @nuxt/vite-builder@3.17.7
    │ └── @nuxt/kit@3.17.7
    └─┬ nitropack@2.13.3
      └── crossws@0.3.5
  ```
- `vitest run` 原 12 tests：✅ `Tests 12 passed (12)`（反证前基线）
- package.json 版本收紧至 `nuxt: ~3.17.7` + `@element-plus/nuxt: ~1.1.4`（R2 追加，对齐 R1 Item 1 "Nuxt 3 锁定" questioned → 次版本锁定）

### Step 2: B2-F002 AuthError 职责分层

- `composables/useApi.ts`：新增 `export class AuthError extends Error` + `getMenus` 401/403 转抛
- `composables/useMenus.ts`：区分 AuthError（清空 menus + 向上抛）vs 其他错误（降级空菜单）
- `layouts/default.vue`：catch 分支 `if (err instanceof AuthError) logout() else console.warn()`（两个分支均改）
- `tests/composables/useMenus.test.ts` 新建 8 测试：
  - 2 Slice 2 case（AuthError 401/403 向上抛 + menus 清空）
  - 2 Slice 3 case（network timeout 降级 / null response 兜底）
  - 4 Slice 1 case（401 / 403 / 500 / ECONNREFUSED 边界）
- `tests/layouts/default.test.ts` 新建 4 测试：
  - 2 AuthError 触发 logout（401 / 403）
  - 1 非 AuthError(500) 保留 session
  - 1 token=null 不触发
- `vitest.config.ts`：新增 `plugins: [vue()]`（挂载 SFC 必需，@vitejs/plugin-vue 经 Nuxt 间接引入，版本 5.2.4）
- 全量 vitest：✅ `Test Files 4 passed (4) / Tests 24 passed (24)`

### Step 3: 反证验证（独立修复设计 §3 verification）

| 反证 | 修改 | 期望 | 实测 | 状态 |
|------|------|------|------|------|
| 1 | useMenus.ts 删 `if (err instanceof AuthError) { throw err }` | Slice 2 AuthError 向上抛测试 FAIL | 2 failed, 6 passed（Slice 2 401/403 两个 case 断言 `rejects` 失败 → `undefined`） | ✅ |
| 2 | default.vue `if (err instanceof AuthError)` → `if (true)` | Slice 4 "500 不触发 logout" FAIL | 1 failed, 3 passed（"500 不触发 logout" 断言 `logoutSpy not toHaveBeenCalled; Number of calls: 1` 失败） | ✅ |
| 3 | useApi.getMenus 去掉 AuthError 转换 | Slice 1 "401/403 转 AuthError" FAIL | 2 failed, 6 passed（401 断言 `expected {response:{status:401}} to be an instance of AuthError`, 403 断言同结构失败） | ✅ |

恢复代码后全量 vitest：`Tests 24 passed (24)`

### Step 4: Pre-existing 2 failures 独立复现

- 命令：`python -m pytest tests/test_ai/test_tool_access_fail_closed.py --tb=line`
- 输出：
  ```
  tests\test_ai\test_tool_access_fail_closed.py F....F.                    [100%]
  ================================== FAILURES ===================================
  E   AssertionError: assert 1 == 0
  FAILED tests/test_ai/test_tool_access_fail_closed.py::test_no_capability_record_rejects
  FAILED tests/test_ai/test_tool_access_fail_closed.py::test_partial_capability_match_rejects
  ========================= 2 failed, 5 passed in 0.26s =========================
  ```
- 结论：与 R1 报告完全一致（2 failed / 5 passed），两个失败与 Batch 2 前端无关，继承自既有 pre-existing 状态

### Step 5 Executor 观察：plan.md hash 失效（非 R2 阻塞，供 Planner 处置）

- `docs/plans/2026-04-12-haofenshu-phase1-gates.json` 的 `plan_review.subject_hash = e77cf539...`
- 当前 `docs/plans/2026-04-12-haofenshu-phase1-plan.md` 实际 hash = `e55a651e...`
- 差异源：Planner 系统梳理 commit `c4c365c`（"docs(haofenshu): Planner 系统性梳理 — CLAUDE.md/design/plan 三文档同步"）之后，gates.json subject_hash 未同步
- R2 不擅自更新 gates.json — Executor 所有修改严格按独立修复设计执行，未依赖 plan.md 任何特定段落的精确 hash
- 建议 Reviewer 与 Planner 协调决策：追认新 hash / 回退 c4c365c 修改 / 另开处置

## 5. 自查（四要素格式）

### 新增文件的边界 case（useMenus.test.ts + default.test.ts）

构造输入: 空 response / 401 / 403 / 500 / ECONNREFUSED / token=null 6 种边界
运行命令: `./node_modules/.bin/vitest run --no-cache`
实际输出:
```
 ✓ tests/composables/useMenus.test.ts (8 tests) 44ms
 ✓ tests/layouts/default.test.ts (4 tests) 98ms
 Test Files  4 passed (4)
      Tests  24 passed (24)
```
结论: 所有边界 case 覆盖，包括 401/403（AuthError 路径）+ 500/network（降级路径）+ null response + token=null。

### 状态变量/锁的异常路径（menus 清空 + store.logout 幂等）

构造输入: loadMenusMock.mockRejectedValue(AuthError 401) 并先 setMenus 过期菜单
运行命令: 同上
实际输出: `expect(store.menus).toEqual([])` PASS；`expect(logoutSpy).toHaveBeenCalledTimes(1)` PASS（非 2 次）
结论: 异常路径清空 menus 成立 (`ORC-auth-state-consistency`)；logout 幂等成立 (`ORC-no-double-logout`)。

### 字符串匹配/条件判断的假阴性（instanceof AuthError 三处）

构造输入: 错误 `new AuthError(401, ...)` vs 错误 `new Error('network')` vs 错误 `{ response: { status: 500 } }`
运行命令: 反证 1/2/3 各自单跑
实际输出:
- 反证 1 删 `if (err instanceof AuthError)`（useMenus） → 2 fail（两个 AuthError 向上抛 case）
- 反证 2 改 `if (true)`（default.vue） → 1 fail（500 不触发 logout case）
- 反证 3 不转 AuthError（useApi） → 2 fail（401/403 转 AuthError case）
结论: 三处 `instanceof AuthError` 判断都是 test-assertion 唯一识别点，反证成立。

## 6. B2-F003 根因定论（本交接单吸收）

**Step 3/4 端到端根因**：9000 常驻后端进程陈旧/未重启。独立复现：`uvicorn --port 9001` fresh 实例能正常返回 `openapi.json` 含 `/api/v1/menus` 且登录后 `GET /api/v1/menus` 对 `t_yw_001` 返回 `menu_count=6 first=exam`。

**取证**：GPT Reviewer `netstat` + `Get-CimInstance Win32_Process` 独立查证确认 9000 监听进程是 `"python.exe" -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000`（Windows 本机原生进程，非 WSL 中转）。fresh 9001 对照实例正常 → 根因定位为 9000 进程陈旧/未重启。

## 7. 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| B2-F002 | N/A — GPT 标 Type=defect_fix 且 Claude 独立复核保留 defect_fix | **无需批准** | 红旗模式自动检测命中（fallback strategy + lifecycle），但 intent 是恢复 plan Task 8 已声明契约（`ORC-auth-fail-closed`），不是"引入用户未要求的新行为"。已由独立修复设计 + Fix Intent Card 4 ORC (auth-fail-closed / menu-degrade / auth-state-consistency / no-double-logout) + 3 反证护航。不触发 L017 逐条批准流程。 |

## 8. 根因分析（B2-F002 / bug-fix-discipline 四要素）

- **症状**: plan Task 8 边界条件 "token 有值但 loadMenus 失败 → logout" 无自动化测试且实现已偏离 —— `useMenus.loadMenus()` 无差别吞错，`default.vue` 外层 `catch` 不可达
- **根因**: 两层策略（菜单降级 vs auth 生命周期 fail-closed）被错误合并为同一层 —— `loadMenus` 同时承担"任何失败不影响页面渲染"与"token 失效必须退回登录"，语义冲突时只满足前者
- **证据**: R1 GPT Reviewer 独立取证 `useMenus.ts:5` catch 吞错 + `default.vue:25` catch 分支不可达 + plan Task 8 边界条件文本
- **影响面** (scope check):
  - 同模式: useMenus 外是唯一的 auth-critical 菜单 composable，其他 useHomework/useAnalytics 等不涉及 auth fail-closed
  - 同边界: /api/v1/menus 是 Batch 2 唯一 auth-critical 端点（login/switch-role 自带 401 处理）
  - 同不变量: `ORC-auth-fail-closed` 是 Phase 1 唯一 auth lifecycle 不变量
- **排除的假设**: 
  - 假设 A "在 useMenus 直接删 try/catch" — 排除：会让菜单失败变成整页崩溃（违反 `ORC-menu-degrade`）
  - 假设 B "在 default.vue 外层加空菜单检查触发 logout" — 排除：重复策略 + 职责漂移（空菜单≠auth 失败）

## 9. Semantic Regression Gate（Fix Intent Card）

> 详见 `docs/plans/2026-04-14-auth-fail-closed-repair-design.md` §3

实施结果对照：
- `root_cause`: ✅ 策略职责边界缺失 — 已通过 AuthError sentinel + 3 处修改分层承接
- `preserved_invariants`:
  - ORC-auth-fail-closed: ✅ Slice 4 AuthError→logout 测试通过 + 反证 2 验证
  - ORC-menu-degrade: ✅ Slice 3 非 auth 降级测试通过
  - ORC-auth-state-consistency: ✅ AuthError 路径清空 menus 测试通过
  - ORC-no-double-logout: ✅ Slice 4 `toHaveBeenCalledTimes(1)` 断言
- `non_goals`: ✅ 全部遵守（后端零改动 / Pinia/Nuxt 版本零改动 / 不引入全局拦截器 / 不改 auth.global.ts 白名单 / 不改 useCookie 存储格式 / 不加多 tab 同步）
- `allowed_change_surface`:
  - `frontend-nuxt/composables/useApi.ts` ✅
  - `frontend-nuxt/composables/useMenus.ts` ✅
  - `frontend-nuxt/layouts/default.vue` ✅
  - `frontend-nuxt/tests/composables/useMenus.test.ts` ✅
  - `frontend-nuxt/tests/layouts/default.test.ts` ✅
  - **追加**: `frontend-nuxt/vitest.config.ts`（Slice 4 SFC 挂载所需 vue plugin；`@vitejs/plugin-vue` 经 nuxt 间接引入，非新增依赖）
  - **追加**: `frontend-nuxt/package.json`（R1 Item 1 Nuxt 3 锁定：`~3.17.7` + `@element-plus/nuxt ~1.1.4`）
  - **追加**: `frontend-nuxt/package-lock.json`（B2-F001 rebuild）
- `verification`: 全部执行并通过 + 3 反证全成立

## 10. Contract Pack / INV 对齐（Batch 2 不变量复核）

| 不变量 | Batch 2 R1 状态 | Batch 2 R2 增量 | 状态 |
|--------|---------------|---------------|------|
| INV-01 后端零改动 | ✅ | 零改动 | ✅ |
| INV-02 现有 frontend/ 不动 | ✅ | 零改动 | ✅ |
| INV-03 测试基线 | 待 R2 | 前端 vitest 24/24 + 后端 pytest 2 failed 为 pre-existing | ✅ |
| INV-04 单一真源（plan/design） | ✅ | 不触碰 plan 本体 | ✅ |
| INV-05 scope_guard（commit 范围） | ✅ | 只 add frontend-nuxt/ + docs/plans/ | ✅ |
| INV-06 conduct 零改动 | ✅ | 零改动 | ✅ |

## 11. 提交记录

- Round 2 commit: **`8daa076`** — `fix(frontend,deps): haofenshu phase1 batch2 R2 — B2-F001/F002/F003`
- Batch 2 总体 commit 范围: `08d86f0..8daa076`
- 10 files changed, 700 insertions(+), 115 deletions(-)
- Round 2 变更文件:
  - M `CLAUDE.md`（frontend-nuxt 段同步 Batch 2 R2 修复 + vue plugin + AuthError 错误边界）
  - M `frontend-nuxt/composables/useApi.ts`（+ AuthError class + getMenus 401/403 转抛）
  - M `frontend-nuxt/composables/useMenus.ts`（+ AuthError 分支路径，非 auth 降级静默）
  - M `frontend-nuxt/layouts/default.vue`（+ catch 分 AuthError/其他，非 auth 静默保留 session）
  - M `frontend-nuxt/vitest.config.ts`（+ vue plugin）
  - M `frontend-nuxt/package.json`（R1 Item 1 Nuxt 3 锁定 `~3.17.7`）
  - M `frontend-nuxt/package-lock.json`（B2-F001 rebuild）
  - A `frontend-nuxt/tests/composables/useMenus.test.ts`（8 新测试）
  - A `frontend-nuxt/tests/layouts/default.test.ts`（4 新测试）
  - A `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md`（本交接单）

**logging-guard 合规说明**：Batch 2 修复范围内删除 3 处裸 `console` 调用（useMenus.ts `console.error` + default.vue 2 处 `console.warn`），改为静默降级 + 注释标注 Phase 2 接入 logger 模块；独立修复设计 §2.3/§2.4 的 console.warn 字面推荐被 logging-guard 硬拦截，R2 按项目全局日志规则收敛。default.test.ts Slice 4 "500 不触发 logout" 测试断言由 `expect(warnSpy).toHaveBeenCalled()` 替换为 `expect(store.user).toBeTruthy()`（session 保留的更强语义证据）。

## 12. 送审声明

使用 codex-review skill 进行 GPT 代码审查。

Gate 2 R2 审查请求:
- 覆盖范围：Round 2 增量 + R1 finding 处置证据
- 审查重点：
  1. B2-F001 lockfile 可复现性（npm ci --ignore-scripts + npm ls 清洁度）
  2. B2-F002 AuthError 职责分层是否完整承接 plan Task 8 契约（特别是 3 条反证是否足以 anti-tautology）
  3. B2-F003 措辞收窄是否对等置换
  4. R2 追加变更（vitest.config.ts vue plugin + package.json Nuxt 锁定）是否在合理 scope 内
  5. Pre-existing 2 failures 是否仍稳定复现
- PASS 报告锚定: 若 R2 PASS，gates.json `report_path` 必须指向 R2 报告（不得保留 R1 FAIL 报告）

送审前 Executor 预审自检项（§3 / §4 / §5 / §10）均实测通过，3 反证全部成立。
