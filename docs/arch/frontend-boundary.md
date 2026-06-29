<!-- pre-takeover: archived for history, not active spec -->
<!-- STALE: frontend-nuxt/ 已退役（2026-04-25 takeover-index 裁定），本文档仅供历史参考 -->
# 双前端业务边界规范（已归档）

> **归档声明（2026-05-05）**：frontend-nuxt/ 骨架已退役，edu-cloud 唯一生产前端为 `frontend/`（Vite + Naive UI）。
> 本文档保留供历史追溯，不再作为活规范。新前端开发直接遵循 CLAUDE.md 项目结构段。

> 原生效日期：2026-04-17
> 适用范围：edu-cloud 仓库内 `frontend/`（生产主前端）+ `frontend-nuxt/`（haofenshu 复刻骨架，已退役）
> 决策来源：2026-04-17 技术债清理 · Q3 = B 共存（`retired-archived-plan-history`）
> 相关规范：`docs/arch/module-template.md`、`docs/arch/orm-placement.md`

本文档固化 edu-cloud 仓库内两个前端项目的业务边界，给出新需求的归属决策树，避免未来路由/权限重叠。

## 1. 现状定位

### 1.1 `frontend/` — 生产主前端（edu-cloud 原生阅卷平台）

- **技术栈**（`frontend/package.json` 2026-04-17 verify）：
  - Vite `7.3.1` + Vue `3.5.25`（Composition API）
  - Naive UI `2.44.0`（暗色主题）
  - Vue Router `4.6.4`（AppShell 根布局 + 角色/权限守卫）
  - Pinia `3.0.4`（状态管理）
  - Axios `1.13.6`（HTTP 客户端，baseURL `/api/v1`）
  - ECharts `6.0.0` + vue-echarts + @antv/g6 `5.1.0`（图表 / 知识图谱）
  - KaTeX `0.16.38` + marked `17.0.4`（公式 / Markdown）
  - Vitest `4.1.0` + happy-dom（单元测试）
- **Dev port**：`5273`（Vite dev server）
- **路由规模**：`frontend/src/router/index.js` `grep -c "path:"` → **44 路由**（含家长端 + conduct + 主阅卷链路）
- **测试规模**：`frontend/src/` + `frontend/tests/` 共 **24 spec 文件**（对应 CLAUDE.md "1851 后端 + 73 前端 Vitest"）
- **业务范围**：edu-cloud 原生平台全功能 —— 登录 / 分析 / 考试管理 / 扫描 / AI 阅卷 / 手工阅卷 / 通知 / 家长端 / conduct 德育 / 知识图谱 / Studio 文档 / Homework / Profile / ...（详见 `CLAUDE.md` "项目结构" + `frontend/src/pages/` 23 个页面目录）

### 1.2 `frontend-nuxt/` — haofenshu 业务复刻 Phase 1（骨架阶段）

- **技术栈**（`frontend-nuxt/package.json` 2026-04-17 verify）：
  - Nuxt `~3.17.7`（SSR=false，次版本锁定）
  - Vue `3.5.13` + Vite 6 + Nitro 2.13
  - Element Plus `2.8.7` + @element-plus/nuxt `~1.1.4` + @element-plus/icons-vue
  - Pinia `2.3.1` + @pinia/nuxt
  - vue-router `4.4.5`
  - Vitest `3.2.0` + @vue/test-utils + happy-dom `15.11.6`
- **Node 运行时锁定**：`package.json engines.node ">=22.12.0"` + `frontend-nuxt/.nvmrc` 锁 `22.12.0`（L017 批准 2026-04-14，R3 PASS 定锚）
- **Dev port**：`3000`（`nuxt.config.ts devServer.port`；`haofenshu-clone` 占用 3000 时 fallback 3100）
- **API 配置**（`frontend-nuxt/nuxt.config.ts` verify）：
  - `runtimeConfig.public.apiBase = "http://localhost:9000"`
  - Vite `devProxy` `/api` → `http://localhost:9000`（`changeOrigin: true`）
- **路由/页面规模**：`frontend-nuxt/pages/` 仅 3 个（`home.vue` + `index.vue` + `login.vue`，Batch 2 骨架阶段）
- **测试规模**：`frontend-nuxt/tests/` 共 **4 spec 文件 / 24 tests**（Batch 2 R3 PASS 基线 `6ddb19c`）
- **业务范围**：严格限定于好分数业务复刻（`docs/archive/plans/2026-04-12-haofenshu-biz-replication-design.md`）。Phase 1 Batch 2 已完成登录 + 首页模块卡片网格；Batch 3 待启动（PowerFilter + 45 页面 stub）。**目标复刻范围**：8 模块 × 45 页面（学情看板、班级 Dashboard、作业、教学、教研、教务、基础信息、报告）。

### 1.3 两前端与后端的构建/部署关系

- **后端零引用 `frontend-nuxt/`**：`grep -r "frontend-nuxt" src/ Dockerfile docker-compose.yml` **零命中**（2026-04-17 verify）
- **`Dockerfile` 不构建任何前端**：仅 `COPY src/ + alembic/`（后端容器纯 Python），前端走独立部署（Vite 产物 `dist/` / Nuxt 产物 `.output/`）
- **`docker-compose.yml` 服务**：`edu-cloud` + `postgres` + `redis` 三服务，均为后端生态

## 2. 业务范围划分（不重叠原则）

| 业务域 | 归属 | 说明 |
|--------|------|------|
| 阅卷链路（扫描 / AI 阅卷 / 手工阅卷 / 分配 / 进度 / 校对） | `frontend/` | edu-cloud 原生核心，不复制到 Nuxt |
| conduct 德育 + 家长端（邀请码 / 积分 / 班规 / 小组 / 导出） | `frontend/` | 已完成 118 conduct tests，Nuxt 不动 |
| 知识图谱可视化（G6 力导向图 + 教师工作台 Phase 2 / 2.5） | `frontend/` | G6 5.1.0 绑定 Naive UI，不迁 |
| 答题卡编辑器（5 模块原生 JS + CardEditor.vue） | `frontend/` | 不迁 |
| Studio 文档 / 校历 / 通知 / 学校管理 / 排课 | `frontend/` | 管理端集中 |
| 好分数 8 模块 × 45 页面骨架复刻 | `frontend-nuxt/` | Phase 1 范围，设计文档 `docs/archive/plans/2026-04-12-haofenshu-biz-replication-design.md` |
| 动态菜单（后端 `/api/v1/menus` 驱动） | `frontend-nuxt/` 优先 | `frontend/` 仍用 `sidebarConfig.js`（静态 JSON）；后端 `menu_configs` 主要服务 Nuxt 版 |

**铁律**：同一业务功能不允许两前端各实现一次。新需求触发 §7 归属决策树。

## 3. API 调用规约

### 3.1 共同契约

两前端均调用同一后端（port 9000），统一走 `/api/v1/*` 路由。JWT 共享 —— 同一 `access_token` 两边都认，401/403 行为由各自前端处理。

### 3.2 `frontend/`（Axios）

- **入口**：`frontend/src/api/client.js`
  - `axios.create({ baseURL: '/api/v1' })`（相对路径，依赖 Vite dev proxy 或生产反向代理）
  - 请求拦截器自动注入 `Authorization: Bearer ${localStorage.token}`
  - 响应拦截器：401 → 清 token + `router.push('/login')`
- **分域 api 模块**：`frontend/src/api/` 14 模块 + `client.js`（详见 CLAUDE.md "项目结构"）
- **conduct 家长端例外**：独立 `parentClient` 使用 `cp_token`（家长独立认证体系）

### 3.3 `frontend-nuxt/`（`$fetch`）

- **入口**：`frontend-nuxt/composables/useApi.ts`
  - `baseURL = config.public.apiBase + '/api/v1'`（其中 `apiBase = "http://localhost:9000"`）
  - Token 从 `useCookie('edu_token')` 读取
  - 导出 `AuthError` sentinel（`401/403` 转抛，供 `useMenus` / `layouts/default.vue` 分层处理）
- **方法清单**（verify：~**30 业务方法**，含 5 个 Phase 2/3 stub）：
  - Auth × 2 / Menu × 1 / Exam × 3 / Analytics × 10 / PowerOptions × 1（stub）
  - Homework × 4 / Knowledge × 3 / BaseInfo × 2 / Profile × 2 / AI × 1 / Dashboard × 1
  - 另导出 `raw` + `token` 作为逃生口
- **SSE 例外**：`chatStream` 直调 `/api/v1/ai/chat`，`responseType: 'stream'`，不走 `$fetch` 的 JSON 解析路径

### 3.4 路由挂载互斥

后端不为某个前端定制路由。如需差异化，走 query 参数 / Accept header / 角色判断，禁止新建 `/api/v1/nuxt/*` 或 `/api/v1/frontend/*` 这类前端专属前缀。

## 4. 安全与认证边界差异

两前端均走 JWT Bearer Token，但 token 存储介质和认证错误责任链不同，构成**架构边界的一部分**，不是可替换的实现细节。

### 4.1 Token 存储与注入

| 维度 | `frontend/` | `frontend-nuxt/` |
|------|-------------|------------------|
| 存储 API | `localStorage.getItem('token')` / `setItem` / `removeItem` | `useCookie('edu_token')`（Nuxt 3 响应式 Cookie） |
| 注入方式 | Axios 请求拦截器统一拼 `Authorization: Bearer ${token}` | `useApi.ts` `$fetch` headers 手动注入 |
| XSS 面 | 同源 JS 可读（常规 SPA 暴露面） | 同源 JS 可读（非 `httpOnly` Cookie，前端读取需要） |
| CSRF 面 | 无 Cookie 自动附带，跨站冒用面窄 | Cookie 同源附带 —— 未来开启 SSR 鉴权路径需显式 `SameSite=Strict` |

取向差异：`frontend/` 走 "localStorage + 手动注入"，CSRF 面窄、XSS 面常规；`frontend-nuxt/` 走 "Cookie + 手动注入"，为未来 SSR 模式留接入口，但需防范 CSRF。

### 4.2 认证错误处理责任链

- **`frontend/`**：Axios 响应拦截器 `401 → 清 token + router.push('/login')` **一处集中**，业务代码不关心鉴权失败
- **`frontend-nuxt/`**：`useApi.ts` 导出 `AuthError` sentinel，401/403 在 `getMenus` 等关键方法就地转抛；`useMenus`（区分 auth vs 非 auth 降级空菜单）+ `layouts/default.vue`（AuthError → `logout`，非 AuthError 保留 session）**分层处理**
  - 该分层在 Batch 2 Gate 2 R1-R3 三轮审查固化（B2-F002），**不可退回全局拦截式**

### 4.3 不容忍共识

- 两前端实现差异化容忍（存储介质 / 责任链形态各自原生），但**行为必须等价**：401 → 强制登出 + 清状态 + 跳登录页
- Token 刷新 / 角色切换 / 家长端 `cp_token` 独立认证的语义由后端单一真源定义（`src/edu_cloud/api/auth.py` + `modules/conduct/*_parent.py`），两前端同步实现

## 5. 技术栈差异容忍度

### 5.1 为什么不强制统一（Q3 = B 务实理由）

1. `frontend-nuxt/` 处于 Phase 1 骨架阶段，强推 Vue 生态会破坏 Nuxt 3 SSR/file-based routing 路径
2. Element Plus 与 Naive UI 组件 API 互不兼容，双向迁移成本远超收益
3. `frontend/` 已稳定承载 44 路由 + 73 测试用例 + 生产阅卷链路，retro-fit 风险高
4. Nuxt 3 file-based routing 在 Phase 1 目标的 45 页面规模上显著优于手写 `router/index.js`

### 5.2 容忍清单

| 维度 | `frontend/` | `frontend-nuxt/` | 是否容忍 |
|------|------------|------------------|---------|
| 框架 | Vite 7 + Vue 3.5 | Nuxt 3.17 + Vue 3.5 | 容忍 |
| UI 库 | Naive UI 2.44（暗色） | Element Plus 2.8（好分数品牌色） | 容忍 |
| 路由 | vue-router 4.6（AppShell + 手写守卫） | Nuxt file-based + `middleware/auth.global.ts` | 容忍 |
| 状态 | Pinia 3.0 | Pinia 2.3 + `@pinia/nuxt` | 容忍（Nuxt 侧 Pinia 2.x 由 `@pinia/nuxt` 锁定） |
| HTTP | Axios 1.13（baseURL `/api/v1` 相对） | `$fetch`（`apiBase + /api/v1` 绝对） | 容忍 |
| Node | 18+ | ≥22.12.0（lockfile 锁定） | 容忍（CI/CD 需双 Node 矩阵） |
| 测试 | Vitest 4.1 | Vitest 3.2（`@nuxt/test-utils` 约束） | 容忍 |

### 5.3 不容忍清单

- JWT / 角色 / 权限 `Permission` 枚举：必须镜像后端 `core/permissions.py`，两前端 `config/permissions.js|ts` 行为必须一致
- `/api/v1` 路由契约：后端单一真源，两前端同步更新
- 错误边界：401 强制登出（行为等价即可，实现各自原生）

## 6. 未来合并/取代决策条件

### 6.1 触发"启动 Phase N+1 合并评审"的硬条件（任一满足）

- `frontend-nuxt/` 业务覆盖度 ≥ `frontend/` 50%（按功能等价度评估，不按页面数）
- 同一业务在两边各实现一次 → 进入维护双轨成本（违反 §2 铁律）
- Nuxt 3 SSR / 首屏性能生产实测优于 `frontend/` Vite SPA **≥ 2×**
- 用户决策："停 `frontend/`，全量迁 Nuxt" 或反之

### 6.2 合并方案选项（待触发时再深化）

| 方案 | 描述 | 代价 |
|------|------|------|
| A | 废 `frontend/`，业务全量迁 Nuxt | 阅卷链路 / 知识图谱 / 答题卡编辑器重写；73 Vitest 重建 |
| B | 废 `frontend-nuxt/`，haofenshu 业务回迁 `frontend/` | 45 页面用 vue-router 手写；Element Plus → Naive UI 迁移 |
| C | 拆分为 `frontend-admin/`（管理端） + `frontend-edu/`（教学端），两仓按业务域分 | 需重新设计 AppShell + 菜单联动，代价最大 |

## 7. 新功能归属决策树

```
新需求来了：
├─ 复刻好分数已有功能？
│    └─ 是 → frontend-nuxt/（归属 8 模块 45 页面蓝图）
│
├─ edu-cloud 原生功能（阅卷 / conduct / 分析 / 知识图谱 / 答题卡 / Studio）？
│    └─ 是 → frontend/（不进 Nuxt）
│
├─ 跨域功能（既属好分数复刻又属 edu-cloud 原生）？
│    ├─ 主用户角色 = 教师 / 管理员？ → frontend/
│    └─ 主用户角色 = 学生 / 家长？   → frontend-nuxt/
│
├─ 纯管理端（学校 / 排课 / 选考 / 能力矩阵 / 审计 / LLM 配置）？
│    └─ 是 → frontend/（管理端集中，Nuxt 不动）
│
└─ 不确定？
     └─ 默认 frontend/（多数用户场景在主前端）
```

**守门规则**：Phase 1/2 期间，好分数 Phase 1 计划（`docs/archive/plans/2026-04-12-haofenshu-phase1-plan.md`）以外的新需求一律进 `frontend/`。Phase 2/3 启动时再评估是否扩展 Nuxt 范围。

## 8. 端口 / 部署约束

| 资源 | `frontend/` | `frontend-nuxt/` |
|------|-------------|------------------|
| Dev port | `5273`（Vite） | `3000`（Nuxt，fallback `3100`） |
| Build 产物 | `frontend/dist/` | `frontend-nuxt/.output/` |
| Dockerfile 包含 | ❌（镜像仅后端） | ❌（镜像仅后端） |
| docker-compose 服务 | ❌ | ❌ |
| Node 运行时 | 18+ | `>=22.12.0`（engines + `.nvmrc`） |
| 后端代码引用 | 零（`grep "frontend" src/` 仅路径字面量，无 import） | 零（`grep "frontend-nuxt" src/` zero hit） |
| API baseURL | `/api/v1`（相对，靠 proxy） | `http://localhost:9000/api/v1`（绝对，dev proxy `/api → 9000` 兜底） |

**部署约束（Q3 = B 共存）**：两前端各自独立部署产物，不进同一后端容器。未来纳入生产镜像需在本规范 §6 触发评审。

---

**变更记录**：

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-04-17 | 初版（Task 3，Phase 2 技术债清理） | 技术债清理执行窗口 |
