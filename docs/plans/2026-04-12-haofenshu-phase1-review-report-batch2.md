# Code Review R1 报告 — haofenshu Phase 1 Batch 2

[edu-cloud] GPT Reviewer | 2026-04-13 23:53:23
Commits: 08d86f0..674cd99
结论: FAIL

## 第一段：测试充分性 (Test Adequacy)

独立执行 `cd frontend-nuxt && .\node_modules\.bin\vitest.cmd run`，结果为 `2 files / 12 tests passed`，交接单声称的 12 个 Vitest 用例当前能稳定通过。anti-tautology 我随机抽了 2 条并做了红测复现：

- 将 [auth.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/stores/auth.ts#L82) 的 `res.roles.find((r) => r.is_primary) || res.roles[0]` 临时改成 `res.roles[0]` 后，执行 `vitest run tests/stores/auth.test.ts -t applyLoginResponse`，结果变为 `1 failed, 2 passed, 5 skipped`，失败点是 [auth.test.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/tests/stores/auth.test.ts#L16) 对 `active_role.id === 'r2'` 的断言。
- 将 [useApi.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/composables/useApi.ts#L65) 的 `getPowerOptions` stub 临时改成 `Promise.resolve(undefined)` 后，执行 `vitest run tests/composables/useApi.test.ts -t getPowerOptions`，结果变为 `3 failed, 1 skipped`，分别命中 [useApi.test.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/tests/composables/useApi.test.ts#L14)、[useApi.test.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/tests/composables/useApi.test.ts#L20)、[useApi.test.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/tests/composables/useApi.test.ts#L27)。

但 Task 8 计划里“token 有值但 `loadMenus` 失败时应 logout”的 fail-closed 契约没有任何自动化测试覆盖，而当前实现确实已经偏离该契约，见 B2-F002。也就是说，现有 Vitest 只能证明 store/composable 局部 slice 正确，不能守住 layout 级 auth 生命周期语义。

另一个测试可复现性问题是 clean install 不成立。独立执行 `cd frontend-nuxt && npm ci --ignore-scripts` 直接报 `package.json and package-lock.json are not in sync`，随后 `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2` 也给出 `invalid: @nuxt/schema@3.17.7`、`invalid: crossws@0.3.5`。这意味着本轮前端验证依赖现成 `node_modules`，而不是可重放的锁文件环境，见 B2-F001。

## 第二段：行为正确性 (Behavioral Correctness)

Phase 0 Contract Pack 先看范围与不变量。`git diff 08d86f0~1..674cd99 -- frontend` 为空，INV-01 成立；`git diff --stat 08d86f0~1..674cd99 -- frontend-nuxt CLAUDE.md` 只覆盖 `frontend-nuxt/` 与 `CLAUDE.md`，不存在后端改动，INV-02/04/05/06 未被 Batch 2 直接触碰。Plan 现有 `risk_modules` 只列了 [useApi.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/composables/useApi.ts#L1)，但从本轮实际风险看，`frontend-nuxt/package.json` / `package-lock.json` 也应补入 risk_modules。

`useApi` 的真实路径我抽检了 8 条：`/api/v1/auth/login`、`/api/v1/auth/switch-role`、`/api/v1/menus`、`/api/v1/analytics/exam/{id}/summary`、`/api/v1/homework/tasks/{task_id}/submissions`、`/api/v1/knowledge-tree/graph`、`/api/v1/profile/students/{id}/trend`、`/api/v1/dashboard/summary`，分别与 [auth.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/api/auth.py#L13)、[menu/router.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/menu/router.py#L9)、[analytics/router.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/analytics/router.py#L15)、[homework/router.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/homework/router.py#L16)、[knowledge_tree/router.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/knowledge_tree/router.py#L18)、[profile/router.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/modules/profile/router.py#L14)、[dashboard.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/api/dashboard.py#L10) 对齐。`chatStream` 也与 [ai.py](C:/Users/Administrator/edu-cloud/src/edu_cloud/api/ai.py#L39) 的 `message + session_id` 契约一致。

Focus 1 的 8 项改进里，我的结论如下：

- Item 1 Nuxt 3 锁定：主线方向 accepted。plan 标题就是 Nuxt 3，且 Nuxt 官方 roadmap 仍把 Nuxt 3 与 Nuxt 4 并列维护（https://nuxt.com/docs/community/roadmap），没有即时 EOL blocker；但“锁定”实现 questioned，因为 [package.json](C:/Users/Administrator/edu-cloud/frontend-nuxt/package.json#L18) 仍是 `^3.13.0`，而锁文件当前又无法 clean install。
- Item 2 `tsconfig.json extends`：accepted。Nuxt 3 的 `extends ./.nuxt/tsconfig.json` 与当前目录结构匹配，等价于 Nuxt 3 常规用法。
- Item 3 SSR guard 改写：accepted。对于 [auth.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/stores/auth.ts#L72) 这两个纯 `localStorage` callsite，`typeof window !== 'undefined'` 与 `import.meta.client` 的运行语义等价，未改变 Nuxt 特定行为。
- Item 4 测试扩展 3 slice → 12 tests：accepted。红测已证明确有 anti-tautology，而非为了通过当前实现硬凑断言。
- Item 5 `setup.ts` 全局 mock 注入：accepted with limit。它对 unit slice 足够，但确实不代表真实 Nuxt router/middleware 生命周期，因此不能拿来替代集成验证。
- Item 6 `vitest.config.ts` 首次创建：accepted。`happy-dom + ~ alias + setupFiles` 合理；`define import.meta.*` 在当前代码里偏冗余，但无害。
- Item 7 Vitest 2→3 peer 升级：方向 accepted，但结果 questioned。没有发现 2→3 API 误用；真正的问题是升级后产出的依赖图与锁文件不同步，见 B2-F001。
- Item 8 `CLAUDE.md` 进度行：accepted。位置与格式一致，未破坏原有文档结构。

Focus 2 的反证栏当前成立，如第一段所述。Focus 3 的 Gate Step 3-4，我独立验证到：当前常驻 `9000` 进程的 `openapi.json` 不含 `/api/v1/menus`，登录后访问 `GET /api/v1/menus` 返回 404；但我没有去杀现有 9000 进程，而是临时在 `9001` 起了独立 `uvicorn edu_cloud.api.app:create_app --factory --host 127.0.0.1 --port 9001` 对照实例，结果 `openapi=200 menus_in_openapi=True`，`/api/v1/menus` 对 `t_yw_001` 返回 `menu_count=6 first=exam`。这说明 Step 3/4 的阻塞来自“当前 9000 常驻后端进程陈旧/未重启”，不是 Batch 2 前端 diff 本身；但因为浏览器级 `/home` 渲染与模块点击跳转并未在真实 9000 环境重放成功，所以 Step 3/4 不应记 PASS，建议记 `deferred`。

Focus 4 的 `startsWith` 理论误匹配目前不触发。我用 `scripts/seed_menus.py` 统计到 `modules=8, children=42, total=50`，并验证所有 child path 都满足 `/{module}/...` 前缀，额外做前缀冲突检查得到 `collision_count 0`。因此这不是 Batch 2 blocker；deadline 也不必强绑到 Batch 3 启动前，但必须在“新增任何与现有 child path 共享前缀的 sibling 路由”之前关闭，当前 plan/design 写的 “Phase 2 填充前处理” 是合理的。

Focus 5 的 R2-F001 继承表述当前是自洽的。独立执行 `python -m pytest tests/test_ai/test_tool_access_fail_closed.py --tb=line`，结果仍是 `2 failed, 5 passed`，稳定失败项就是 `test_no_capability_record_rejects` 和 `test_partial_capability_match_rejects`。同时 grep 交接单全文，只出现“2 个稳定 pre-existing 已确认”，没有重新引入“5 failures pre-existing”旧口径。

## 第三段：未测试风险 (Non-tested Risks)

- [default.vue](C:/Users/Administrator/edu-cloud/frontend-nuxt/layouts/default.vue#L25) 的 auth lifecycle 目前依赖 `loadMenus()` 抛异常才会 logout，但 [useMenus.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/composables/useMenus.ts#L5) 已经吞错；这条 fail-closed 语义既无自动化测试，也没有手工 gate 真正跑通。
- `SSR=false + useCookie + localStorage` 目前是纯 client-side 会话模型，`edu_token` 不是 `httpOnly`，这在 Phase 1 骨架可接受，但安全语义与 SSR 应用不同，后续不能误当成服务端会话。
- `vite.server.proxy` 只覆盖 dev；生产环境如何把 `/api` 反代到后端，plan 仍停留在说明层，没有部署回归验证。
- `home.vue` 在 `menus=[]` 时只是空网格，不崩溃但没有用户提示；这不构成 Gate blocker，不过 UX 上仍是剩余风险。
- 多 tab 间 token/localStorage 不同步没有任何处理；一个 tab 登录/登出后，另一个 tab 需要刷新才能收敛状态。

## 🔀 改进条目复核
| Item | Executor 声明 | GPT 复核 | 理由 |
|------|--------------|---------|------|
| 1. Nuxt 3 锁定 | 合理 | questioned | 选 Nuxt 3 主线本身合理，Nuxt 官方 roadmap（https://nuxt.com/docs/community/roadmap）也未显示 Nuxt 3 已 EOL；但 [package.json](C:/Users/Administrator/edu-cloud/frontend-nuxt/package.json#L18) 仍是 `^3.13.0`，且 lockfile 当前不可 clean install，不能叫“锁定到 3.17.7”。 |
| 2. tsconfig.json extends | 功能等价 | accepted | [tsconfig.json](C:/Users/Administrator/edu-cloud/frontend-nuxt/tsconfig.json#L1) 的 Nuxt 3 写法与当前目录结构匹配。 |
| 3. SSR guard 改写 | 语义等价 | accepted | 在 [auth.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/stores/auth.ts#L74) / [auth.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/stores/auth.ts#L101) 这些只包 `localStorage` 的位置，`window` guard 不改变行为。 |
| 4. 测试契约扩展 3 slice → 12 测试 | 更稳 | accepted | 两条反证红测都成立，没有 over-fit 迹象。 |
| 5. setup.ts 全局 mock 注入 | 测试便捷 | accepted | 对 unit slice 足够，但只能作为 unit harness，不能替代 Nuxt 集成验证。 |
| 6. vitest.config.ts 首次创建 | 合理 | accepted | `happy-dom`、`~` alias、`setupFiles` 都合理。 |
| 7. vitest 2→3 peer 升级 | 必要 | questioned | 升级方向没问题，也未发现 2→3 API 不兼容；但当前依赖树与 lockfile 不一致，`npm ci` 直接失败。 |
| 8. CLAUDE.md 每 Task commit 追加进度行 | 符合 doc-sync | accepted | [CLAUDE.md](C:/Users/Administrator/edu-cloud/CLAUDE.md#L296) 追加位置正确，格式一致。 |

## Batch 2 独立 Gate 4 步复核
| Step | Executor 判定 | GPT 独立验证 | 最终建议处置 |
|------|--------------|-------------|------------|
| ① Nuxt dev | ✅ | verified | 并行保活 `npm run dev -- --port 3100` 时，独立请求 `http://127.0.0.1:3100/` 返回 `status=200` 且 `x-powered-by=Nuxt`。建议 PASS。 |
| ② login | ✅ | verified | `admin/123456` 与 `t_yw_001/123456` 都能从 `/api/v1/auth/login` 拿到 `access_token`。建议 PASS。 |
| ③ 模块卡片 | ⚠ 代码路径 PASS | partially verified | 当前 9000 常驻进程缺 `/api/v1/menus`，真实 `/home` E2E 未跑通；但 fresh 9001 对照实例能返回 6 模块，说明仓库代码路径可达。建议 deferred。 |
| ④ 模块跳转 | ⚠ 代码路径 PASS | partially verified | `scripts/seed_menus.py` 的 42 个 child path 全部存在且无前缀冲突，但浏览器级点击跳转未在真实 9000 环境完成。建议 deferred。 |

## 发现清单

### B2-F001
- Severity: MED
- Category: code-bug
- Type: defect_fix
- Before-behavior: Batch 2 前端依赖应可由 `package-lock.json` 在干净环境下稳定重建，Gate 证据可重复。
- After-behavior: `npm ci --ignore-scripts` 直接失败，当前验证依赖已有 `node_modules` 和一次不可重放的安装状态。
- Evidence: [package.json](C:/Users/Administrator/edu-cloud/frontend-nuxt/package.json#L13)；[package-lock.json](C:/Users/Administrator/edu-cloud/frontend-nuxt/package-lock.json#L405)；[package-lock.json](C:/Users/Administrator/edu-cloud/frontend-nuxt/package-lock.json#L1343)；[package-lock.json](C:/Users/Administrator/edu-cloud/frontend-nuxt/package-lock.json#L6982)；独立命令 `cd frontend-nuxt && npm ci --ignore-scripts` 报 `package.json and package-lock.json are not in sync`；`npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2` 报 `invalid: @nuxt/schema@3.17.7`、`invalid: crossws@0.3.5`。
- Impact: clean checkout / CI 无法复现本轮前端环境，“Nuxt 3 锁定”与 Gate 可追溯性失真；任何后续 Batch 若在新环境执行都可能先卡死在安装阶段。
- Repair hypothesis: 对齐 `frontend-nuxt/package.json` 与 `frontend-nuxt/package-lock.json` 的实际 dependency graph，确保 `npm ci` 与 `npm ls` 都 clean；禁止继续把已有 `node_modules` 或 `--legacy-peer-deps` 的历史产物当作交付基线。

### B2-F002
- Severity: MED
- Category: code-bug
- Type: defect_fix
- Before-behavior: default layout 在 token 存在但菜单加载失败时应 fail-closed logout，避免过期 token 把用户困在空壳页面。
- After-behavior: [useMenus.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/composables/useMenus.ts#L5) 在内部吞掉所有 `getMenus()` 异常并返回空菜单，导致 [default.vue](C:/Users/Administrator/edu-cloud/frontend-nuxt/layouts/default.vue#L25) 外层 `catch { authStore.logout() }` 分支不可达；token 会保留，页面只会降级成空菜单壳。
- Evidence: [useMenus.ts](C:/Users/Administrator/edu-cloud/frontend-nuxt/composables/useMenus.ts#L5)；[default.vue](C:/Users/Administrator/edu-cloud/frontend-nuxt/layouts/default.vue#L25)；plan Task 8 边界条件写明 “token 有值但 loadMenus 失败 → logout（防 token 过期卡死）”。
- Impact: token 过期、`/menus` 401/404、后端菜单 API 异常时，用户不会被踢回 `/login`；这既偏离 plan 的 fail-closed 语义，也会让 auth 生命周期卡在“有 token 但无可用菜单”的错误状态。
- Repair hypothesis: 需要把“可容忍的菜单降级”与“认证链路 fail-closed”分开设计，禁止在需要 fail-closed 的调用链里无条件吞错；涉及 auth lifecycle / fallback strategy，requires independent fix design + Semantic Regression Gate。

### B2-F003
- Severity: LOW
- Category: design-concern
- Type: defect_fix
- Before-behavior: 交接单把 Step 3/4 的环境阻塞具体归因于 “WSL 后端 hot-reload 失效”。
- After-behavior: 我能独立确认的是“当前 9000 常驻后端进程陈旧，不含 `/api/v1/menus`”；但当前监听者实际上是 Windows `python -m uvicorn ... --port 9000`，并没有独立复现出交接单声称的 WSL `--reload` 根因。
- Evidence: `netstat -ano | findstr :9000` 得到 `LISTENING 41476`；`Get-CimInstance Win32_Process` 显示命令行为 `"python.exe" -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000`；当前 `openapi.json` 不含 `/api/v1/menus`，而临时 fresh 9001 对照实例则 `menus_in_openapi=True` 且返回 6 模块。
- Impact: 不影响“不是 Batch 2 前端回归”的主结论，但会降低 Gate 证据链的根因可信度。
- Repair hypothesis: 后续报告把措辞收窄为“现有 9000 常驻后端进程陈旧/未重启”，除非能附上真实 WSL + reload 复现证据，再去声称具体根因。

## 行为变更审批记录（如有 behavior_change finding）

无新增 behavior_change finding。

## PASS/FAIL 判定依据

按 `review-templates.md` 的 PASS/FAIL 规则，未修复的 HIGH/MED `code-bug` 或 `test-gap` 会直接阻塞。B2-F001 与 B2-F002 都是本轮独立确认的 MED `code-bug`，且当前未修复，所以本轮结论为 FAIL。

## Inv-conflict 标注

无 direct inv-conflict。INV-01 已独立验证成立；其余 INV-02~06 未被 Batch 2 代码直接触碰。B2-F001/B2-F002 主要是前端依赖复现性与 auth lifecycle 语义问题，不直接违反既有不变量文本，但会削弱 Gate 2 的可重复验证性。
