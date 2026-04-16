# Auth Fail-Closed 恢复 — 独立修复设计（B2-F002 R1 处置）

> 创建: 2026-04-14 06:16:17
> 归属: `2026-04-12-haofenshu-phase1` Batch 2 Code Review R1 B2-F002 的独立修复
> 状态: 设计完成，待用户批准
> 触发规则: review-templates.md — risk_modules finding 要求 "independent fix design + Semantic Regression Gate"（红旗模式：fallback/retry strategy + lifecycle）
> 禁止的修复模式（来自 B2-F002 repair_hypothesis）：
> - ❌ 在 `useMenus.ts` 直接删 try/catch（会让菜单加载失败从"空壳"变"整页崩溃"，破坏降级）
> - ❌ 在 `default.vue` 外层再加一层菜单空值检查来触发 logout（重复策略、职责漂移）
> - ❌ 把 "菜单降级" 和 "auth fail-closed" 合并为同一个策略（设计耦合）

---

## §0 本次修复不做什么（non-goals，锚定边界）

- **不**改 `useApi.ts` 的统一错误处理（只需让 auth 链路能识别 401/token 失效）
- **不**改 Element Plus / Pinia / Nuxt 任何第三方库版本
- **不**改变 `auth.global.ts` middleware 的公共路径白名单
- **不**引入新的状态机（auth store 现有 user/roles/menus 结构不变）
- **不**修改后端 `/api/v1/menus` 或 `/api/v1/auth/*` 路由
- **不**在 Phase 1 引入多 tab 间 token 同步（Phase 2+ 工作）

## §1 背景与根因

### 1.1 B2-F002 审查结论（从 codex-code-review-batch2-raw.log 摘取）

> Before-behavior: default layout 在 token 存在但菜单加载失败时应 fail-closed logout，避免过期 token 把用户困在空壳页面。
> After-behavior (当前实现): `useMenus.ts:5` 在内部吞掉所有 `getMenus()` 异常并返回空菜单，导致 `default.vue:25` 外层 `catch { authStore.logout() }` 分支不可达；token 会保留，页面只会降级成空菜单壳。
> Impact: token 过期、`/menus` 401/404、后端菜单 API 异常时，用户不会被踢回 `/login`。
> Repair hypothesis: 需要把"可容忍的菜单降级"与"认证链路 fail-closed"分开设计，禁止在需要 fail-closed 的调用链里无条件吞错。涉及 auth lifecycle / fallback strategy，requires independent fix design + Semantic Regression Gate。

### 1.2 实测复现（2026-04-14）

Plan Task 8 边界条件明确写：`token 有值但 loadMenus 失败 → logout（防 token 过期卡死）`。

当前 `frontend-nuxt/composables/useMenus.ts:5` 实现：

```typescript
async function loadMenus() {
  try {
    const res = await api.getMenus()
    authStore.menus = res?.menus || []
  } catch (err) {
    authStore.menus = []   // ← 吞错，返回空菜单
  }
}
```

而 `frontend-nuxt/layouts/default.vue:25`：

```typescript
watch(token, async (val) => {
  if (val && !authStore.user) {
    authStore.restoreFromStorage()
  }
  if (val) {
    try {
      await loadMenus()  // ← 永不抛
    } catch {
      authStore.logout()  // ← 永不可达
    }
  }
}, { immediate: true })
```

实测：token 过期 → /menus 返回 401 → `useMenus` 吞错置空 → `default.vue` 无感知 → 用户留在 `/home`，菜单为空。

### 1.3 根因（single root cause）

**两层策略被错误合并为同一层**：`useMenus.loadMenus()` 同时承担了"菜单降级"（任何失败不影响页面渲染）与"auth 生命周期 fail-closed"（token 失效必须退回登录）两个职责。当两个策略语义冲突（降级 → 不抛；fail-closed → 必须抛特定错），合并后的行为只能满足其一。

这不是业务语义问题，而是**策略职责边界缺失**——前端 auth lifecycle 的设计契约（plan Task 8）没有被代码层的错误分类承接。

## §2 修复方案

### 2.1 核心设计：引入 AuthError sentinel + 职责分层

将菜单加载的错误分为两类：
- **AuthError（sentinel）**：401 / 403 / token 失效 → auth 链路必须 fail-closed
- **其他错误**（网络、500、解析失败等）：可降级为空菜单，不中断页面

`useApi` 层已经能识别 HTTP 状态码（responseType + baseURL 统一），只需在 auth 相关调用上抛出 `AuthError` 代替吞错。

### 2.2 修改点 1：`composables/useApi.ts`

新增 AuthError 类型 + 让 `getMenus()` 对 401/403 抛 AuthError：

**Before（当前）:**
```typescript
// useApi.ts 没有 AuthError 概念，错误直接用 $fetch 默认抛
async function getMenus() {
  return await request('/menus')
}
```

**After（方言中立）:**
```typescript
// useApi.ts 文件头增加
export class AuthError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'AuthError'
  }
}

async function getMenus() {
  try {
    return await request('/menus')
  } catch (err: any) {
    const status = err?.response?.status ?? err?.statusCode ?? err?.status
    if (status === 401 || status === 403) {
      throw new AuthError(status, 'auth failed on getMenus')
    }
    throw err
  }
}
```

### 2.3 修改点 2：`composables/useMenus.ts`

`loadMenus` 区分 AuthError 与其他错误：AuthError 向上抛，其他错误降级空菜单：

**Before:**
```typescript
async function loadMenus() {
  try {
    const res = await api.getMenus()
    authStore.menus = res?.menus || []
  } catch (err) {
    authStore.menus = []
  }
}
```

**After:**
```typescript
import { AuthError } from '~/composables/useApi'

async function loadMenus() {
  try {
    const res = await api.getMenus()
    authStore.menus = res?.menus || []
  } catch (err) {
    if (err instanceof AuthError) {
      authStore.menus = []  // 清空，防止中间状态
      throw err             // ← 向上抛，让 default.vue 的 catch 捕获并 logout
    }
    // 其他错误：降级为空菜单，保留 auth 状态
    authStore.menus = []
  }
}
```

### 2.4 修改点 3：`layouts/default.vue`

`default.vue` 已有 `catch { logout() }`，但需要确保只对 AuthError 触发 logout，其他错误可以静默（否则一个 500 就把用户踢走）：

**Before:**
```typescript
try {
  await loadMenus()
} catch {
  authStore.logout()  // ← 吞错 + 无差别 logout
}
```

**After:**
```typescript
import { AuthError } from '~/composables/useApi'

try {
  await loadMenus()
} catch (err) {
  if (err instanceof AuthError) {
    authStore.logout()
  } else {
    console.warn('[default.vue] loadMenus non-auth failure; keeping session', err)
  }
}
```

### 2.5 修改点 4：Vitest 测试覆盖

新增 3 个 Vitest 测试在 `tests/composables/useMenus.test.ts`（新文件）：

1. `loadMenus 遇 AuthError 向上抛` — mock `getMenus` 抛 `new AuthError(401, ...)`，断言 `loadMenus()` 也抛 AuthError 且 `menus` 被清空
2. `loadMenus 遇网络错误降级空菜单` — mock `getMenus` 抛 `new Error('network')`，断言 `loadMenus()` 不抛，`menus=[]`
3. `getMenus 在 401 时转为 AuthError` — mock `$fetch` 返回 401，断言 `getMenus()` 抛 AuthError

新增 1 个 Vitest 测试在 `tests/layouts/default.test.ts`（新文件，或 `tests/integration/auth-lifecycle.test.ts`）：

4. `default.vue watch token + loadMenus AuthError 路径触发 logout` — 构造 token=present + mock loadMenus 抛 AuthError，断言 `authStore.logout()` 被调用

## §3 Fix Intent Card（Semantic Regression Gate 输入）

```yaml
root_cause: |
  useMenus.loadMenus 无差别吞掉所有错误，破坏了 plan Task 8 边界条件
  "token 有值但 loadMenus 失败 → logout" 的 fail-closed 契约。
  策略职责边界缺失 — 菜单降级 vs auth fail-closed 被错误合并为同一层。

preserved_invariants:
  - ORC-auth-fail-closed: "plan Task 8 边界：token 有值但 loadMenus 失败 → logout（对 401/403/token 过期场景）"
  - ORC-menu-degrade: "getMenus 非 auth 错误（网络/500/解析失败）应降级为空菜单，不中断 session"
  - ORC-auth-state-consistency: "logout 后 token/user/menus 同时清空，不残留中间状态"
  - ORC-no-double-logout: "单次 401 响应最多触发一次 logout（不产生重复 navigate）"

non_goals:
  - 不修改后端 /api/v1/menus 或 /api/v1/auth/* 路由
  - 不改 useCookie / localStorage 存储格式
  - 不在 useApi 层做全局错误拦截器（那是 Phase 2 工作）
  - 不引入全局事件总线（不加 $bus / provide/inject 新入口）
  - 不触发 Nuxt plugin 新增（中间件已有 auth.global.ts）

allowed_change_surface:
  - frontend-nuxt/composables/useApi.ts（新增 AuthError class + getMenus 抛 AuthError）
  - frontend-nuxt/composables/useMenus.ts（区分 AuthError 与其他错误）
  - frontend-nuxt/layouts/default.vue（catch 分支区分 AuthError）
  - frontend-nuxt/tests/composables/useMenus.test.ts（新建）
  - frontend-nuxt/tests/layouts/default.test.ts（新建，或合并进 integration/）
  - docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md（R2 交接单）

verification:
  - "cd frontend-nuxt && ./node_modules/.bin/vitest run"
    期望: 16 passed（原 12 + 新增 4），0 failed
  - "cd frontend-nuxt && ./node_modules/.bin/vitest run tests/composables/useMenus.test.ts"
    期望: 3 passed（AuthError 抛 / 网络错误降级 / getMenus 401 转 AuthError）
  - "cd frontend-nuxt && ./node_modules/.bin/vitest run tests/layouts/default.test.ts"
    期望: 1 passed（AuthError 路径触发 logout）
  - 反证 1: 临时删除 useMenus 的 `if (err instanceof AuthError) { throw err }`
    期望: `loadMenus 遇 AuthError 向上抛` 测试 fail
  - 反证 2: 临时把 default.vue 的 `if (err instanceof AuthError)` 改成 `if (true)`
    期望: `loadMenus 遇网络错误降级空菜单` 路径的集成测试 fail（无差别 logout）
  - 反证 3: 临时把 useApi.getMenus 的 401 处理改成 `throw err`（不转 AuthError）
    期望: `getMenus 在 401 时转为 AuthError` 测试 fail
```

## §4 测试契约

### Slice 1: getMenus 对 401/403 抛 AuthError
- 入口: `const api = useApi(); api.getMenus()` with mocked `$fetch` returning 401
- 反例: 错误实现（不识别 status，直接 throw err）→ `getMenus()` 抛 FetchError 而非 AuthError
- 边界: 401 / 403 / 其他 status / 网络超时（无 status）
- 回归: 防止 B2-F002 复发（auth 链路能识别 auth 失败）
- 命令: `./node_modules/.bin/vitest run tests/composables/useApi.test.ts -t "getMenus 在 401"`

### Slice 2: loadMenus AuthError 向上抛
- 入口: `useMenus().loadMenus()` with `api.getMenus` mocked 抛 `new AuthError(401, ...)`
- 反例: 错误实现（吞掉所有错误）→ `loadMenus()` 不抛，测试断言失败
- 边界: AuthError / 普通 Error / Promise.reject(undefined)
- 回归: plan Task 8 边界条件
- 命令: `./node_modules/.bin/vitest run tests/composables/useMenus.test.ts -t "AuthError 向上抛"`

### Slice 3: loadMenus 非 auth 错误降级空菜单
- 入口: `useMenus().loadMenus()` with `api.getMenus` mocked 抛 `new Error('network')`
- 反例: 错误实现（对所有错误都抛）→ `loadMenus()` 抛，但本测试期望不抛
- 边界: 网络错误 / 500 / 解析错误 / 空 response
- 回归: ORC-menu-degrade（不破坏降级语义）
- 命令: `./node_modules/.bin/vitest run tests/composables/useMenus.test.ts -t "降级空菜单"`

### Slice 4: default.vue AuthError 路径触发 logout
- 入口: 挂载 `<default>` layout + token=present + mock loadMenus 抛 AuthError
- 反例: 错误实现（catch 无差别 logout / 或不 logout）→ `authStore.logout` spy 断言失败
- 边界: AuthError 触发 / 非 AuthError 不触发 / token=null 不触发
- 回归: ORC-auth-fail-closed
- 命令: `./node_modules/.bin/vitest run tests/layouts/default.test.ts -t "AuthError 路径"`

## §5 风险评估

| 维度 | 评估 | 依据 |
|------|------|------|
| 现有 12 Vitest 测试回归 | 零 | AuthError 只新增代码路径，原 happy-path / JSON 容错 / user=null 静默等不变 |
| useApi 其他 26 方法 | 零 | 只修改 getMenus，其他方法签名与错误处理保持原样 |
| `home.vue` 空菜单渲染 | 零 | 非 auth 错误仍降级为空菜单，home 的空状态兜底未变 |
| 多 tab token 同步 | 维持现状（未改） | 不在本次 scope |
| SSR 行为 | 零 | `typeof window` guard 不变，`AuthError` 定义在 composable 层不涉及 SSR |
| 生产环境 proxy | 零 | 纯前端类型/策略修改，后端零改动 |

> **关键断言：** `AuthError instanceof Error` 为 true，所以任何 `catch (err) { ... }` 不写 `instanceof AuthError` 判断的地方仍会捕获到 — 向后兼容。

## §6 实施顺序

1. `composables/useApi.ts` 加 `export class AuthError extends Error` + `getMenus` 401/403 转抛
2. `composables/useMenus.ts` 导入 AuthError + 分支处理
3. `layouts/default.vue` catch 分支区分 AuthError
4. 新建 `tests/composables/useMenus.test.ts` (3 测试)
5. 新建 `tests/layouts/default.test.ts` (1 测试) — 或合并到 integration 目录
6. 跑 Vitest 16/16 PASS + 3 条反证验证
7. 一个 commit 合并 B2-F001（lockfile 修复）+ B2-F002（本设计）+ B2-F003（交接单措辞收窄）
8. 输出 R2 审查交接单

## §7 变更类型

**变更类型：非行为变更**（恢复 plan Task 8 声明的 fail-closed 语义，修正实现偏离）。

GPT 在 B2-F002 标注 Type=defect_fix 保留；Claude Planner 按「行为变更守卫红旗模式自动检测」复核：
- 虽然触及 fallback strategy + lifecycle
- 但 intent 是恢复 plan 声明的契约（`ORC-auth-fail-closed`），不是"引入用户未要求的新行为"
- 保留 Type=defect_fix，不升级为 behavior_change

本设计作为独立修复设计 + Semantic Regression Gate 护航（§3 Fix Intent Card + §5 风险评估 + §4 测试契约反证栏）。

---

## §8 B2-F001 lockfile 依赖对齐（关联修复，不独立设计）

B2-F001 属于依赖管理问题，相对直接，Round 2 交接卡直接给指令：

**诊断**:
- `npm ci --ignore-scripts` 报 `package.json and package-lock.json are not in sync`
- `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2` 报 `invalid: @nuxt/schema@3.17.7` / `invalid: crossws@0.3.5`
- 根因：Executor 在 Batch 2 执行期间用 `rm -rf node_modules package-lock.json && npm install --legacy-peer-deps` 产生的 lockfile 与真实依赖树不一致

**修复步骤（Executor 执行）**:
1. `cd frontend-nuxt && rm -rf node_modules package-lock.json`
2. `npm install`（**不要用 `--legacy-peer-deps`**）
3. `npm ci --ignore-scripts`（必须零报错）
4. `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2`（必须零 invalid）
5. 若 `npm install` 因 peer 冲突失败 → 调整 `package.json` 相应依赖版本（如 `vitest ^3.2.0` → 实际能兼容的版本），不回退 `--legacy-peer-deps`

**验收**: `npm ci --ignore-scripts` 干净 exit 0，`npm ls` 无 invalid；若不满足，Round 2 FAIL。

## §9 B2-F003 交接单措辞收窄（文档修复，随 R2 交接单一并）

原表述："Step 3/4 端到端受 WSL 后端 hot-reload 失效阻塞"
新表述："Step 3/4 端到端受当前 9000 常驻后端进程陈旧/未重启阻塞（独立复现：fresh 9001 对照实例能正常返回 6 模块）"

随 R2 交接单一次修复，不单独 commit。
