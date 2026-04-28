# UI 基线改造设计 (P0+P1)

> 状态：approved
> 日期：2026-04-28
> 范围：前端 CSS/排版/动效基线，不涉及业务逻辑

## 背景

baseline-ui skill 审查发现 23 项 UI 改进点。本次执行 P0（4 项）+ P1（5 项），共 9 项，涉及 8 个文件。

## 现有资产盘点

本次改造是**增强已有代码**，不新建任何文件/组件/页面。所有改动在现有文件上原地修改。

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| 全局样式 | CSS Variables 45 行 | `frontend/src/assets/styles/variables.css:1-45` | Read 确认：颜色/圆角/阴影/字体/动效 5 组变量 |
| 全局样式 | global.css 108 行 | `frontend/src/assets/styles/global.css:1-108` | Read 确认：reset + 工具类 + stat-card + tag + floatSlow 动画 |
| 主题覆盖 | Naive UI theme 48 行 | `frontend/src/theme.js:1-48` | Read 确认：common/Button/Card/DataTable/Tag/Input/Select/Dialog/Message/Menu 覆盖 |
| 组件 | KpiCard.vue 89 行 | `frontend/src/components/dashboard/KpiCard.vue:1-89` | Read 确认：props color/value/label/trend，scoped style |
| 页面 | DashboardPage.vue 596 行 | `frontend/src/pages/DashboardPage.vue:1-596` | Read 确认：KPI + charts + exam cards + activity feed |
| 页面 | LoginPage.vue 303 行 | `frontend/src/pages/LoginPage.vue:1-303` | Read 确认：装饰圆 + 品牌区 + 表单 + 成功遮罩 |
| 布局 | AppShell.vue 57 行 | `frontend/src/layouts/AppShell.vue:1-57` | Read 确认：header + sidebar + main + AI panel |
| 组件 | AppHeader.vue 126 行 | `frontend/src/components/shell/AppHeader.vue:1-126` | Read 确认：固定顶栏 + 毛玻璃 + 搜索 + 通知 + 角色切换 |
| 组件 | AppSidebar.vue 285 行 | `frontend/src/components/shell/AppSidebar.vue:1-285` | Read 确认：折叠侧栏 + 分组导航 + SVG 图标 |

**增量论证**：全部 9 项改动均为在已有文件上修改 CSS 属性值或追加 CSS 属性，不新建文件、不新建组件、不新建页面。

## 交付路径

```
用户浏览器 → https://mcu.asia (nginx 443)
  → try_files $uri /index.html
  → frontend/dist/ 静态文件
```

- 目标目录：`frontend/`（源码），产物 `frontend/dist/`
- 生产 serving：nginx HTTPS 443 → `frontend/dist/`（已有，无需新建）
- 用户访问 URL：`https://mcu.asia`
- **交付动作**：改完代码 → `cd frontend && npx vite build` → nginx 自动 serve 新 dist

## 改动策略

全局优先：先改 `variables.css` + `global.css` 让全局生效的改动自动覆盖所有页面，再逐文件修个别组件。

## Batch 1 — 全局样式 (P0)

### T1: variables.css 全局变量修正

**文件**: `frontend/src/assets/styles/variables.css`

改动：
1. `--transition: all 0.25s ...` → `--transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1)`
2. 新增 z-index scale：`--z-sidebar: 90; --z-header: 100; --z-overlay: 200; --z-modal: 300`
3. `--font-sans` 补中文字体：追加 `"PingFang SC", "Microsoft YaHei"` 到 sans-serif 前

### T2: global.css 排版与工具类

**文件**: `frontend/src/assets/styles/global.css`

改动：
1. `.page-title` 加 `line-height: 1.2; text-wrap: balance;`
2. `.page-subtitle` 加 `text-wrap: pretty;`
3. `.stat-card .stat-value` 加 `font-variant-numeric: tabular-nums;`
4. `.stat-card` 的 `transition: var(--transition)` 无需改（跟随变量自动生效）
5. 新增工具类 `.tabular-nums { font-variant-numeric: tabular-nums; }`

## Batch 2 — 组件级修正 (P0)

### T3: KpiCard.vue

**文件**: `frontend/src/components/dashboard/KpiCard.vue`

改动：
1. `.kpi-card__value` 加 `font-variant-numeric: tabular-nums;`
2. `.kpi-card` 的 transition 跟随全局变量自动生效（T1 已改 `--transition`）

### T4: DashboardPage.vue

**文件**: `frontend/src/pages/DashboardPage.vue`

改动：
1. `.welcome-banner` 的 `background: linear-gradient(...)` → `background: var(--macaron-mint-light)`（去渐变）
2. `.chart-empty` 区域加一个 CTA 按钮（template 中 chart-empty__text 后加 `<n-button>`）
3. `.chart-title` 加 `line-height: 1.2;`
4. `.exam-card` 的 transition 改为 `transition: transform 0.2s ease-out, box-shadow 0.2s ease-out;`（不跟全局变量，因为全局还带 opacity）

## Batch 3 — 壳层与登录 (P1)

### T5: LoginPage.vue 去硬编码

**文件**: `frontend/src/pages/LoginPage.vue`

改动（9 处硬编码颜色）：
1. `.login-container` `background: #ffffff` → `background: var(--color-bg)`
2. `.decor--mint` `background: #e8f8ee` → `background: var(--macaron-mint-light)`
3. `.decor--cream` `background: #fef3c7` → `background: var(--macaron-yellow)`
4. `.decor--pink-ring` `border: 3px solid #fde8e8` → `border: 3px solid var(--macaron-coral)`
5. `.decor--lavender` `border: 3px solid #ede9fe` → `border: 3px solid var(--macaron-purple)`
6. `.brand-name` `color: #1a2e1f` → `color: var(--color-primary)`
7. `.brand-subtitle` / `.login-hint` `color: #8a9a8e` → `color: var(--color-text-muted)`
8. `.login-footer` `color: #b0b8b2` → `color: var(--color-text-muted)`
9. `.success-check` `background: #1a2e1f` → `background: var(--color-primary)`；`.success-text` `color: #1a2e1f` → `color: var(--color-primary)`

布局修正：
- `.login-container` `min-height: 100vh` → `min-height: 100dvh`
- `.login-content` `min-height: 100vh` → `min-height: 100dvh`

### T6: AppShell.vue 100dvh

**文件**: `frontend/src/layouts/AppShell.vue`

改动：
1. `.app-shell` `min-height: 100vh` → `min-height: 100dvh`
2. `.app-body` `min-height: calc(100vh - 68px)` → `min-height: calc(100dvh - 68px)`

### T7: AppHeader.vue 性能与安全

**文件**: `frontend/src/components/shell/AppHeader.vue`

改动：
1. `backdrop-filter: blur(12px)` → 删除 backdrop-filter，改为 `background: rgba(255, 255, 255, 0.96)`
2. `z-index: 1000` → `z-index: var(--z-header)`
3. 加 `padding-top: env(safe-area-inset-top)`

### T8: AppSidebar.vue 动画优化

**文件**: `frontend/src/components/shell/AppSidebar.vue`

改动（降级方案——保持 width 动画但精确化 transition）：
1. `.sidebar` 的 `transition: width 0.25s ...` → `transition: width 0.2s ease-out`（保持布局方案不变，只精确属性和时长）
2. 折叠/展开子菜单的 `.slide-*` transition 不改（Vue Transition 组件管理）

> 不采用 transform 方案：sidebar 折叠时 `.app-main` 需要跟着调整 flex 占比，transform 不改变布局流，会导致内容区域不重排。保持 width 动画是合理妥协。

## 不改的东西

- theme.js（Naive UI 覆盖，已和 variables.css 同步）
- 业务逻辑、路由、API 调用
- 不新增依赖
- P2 项全部留后：prefers-reduced-motion、SVG 组件化、chart 响应式、空状态全站统一

## 验证

- 每批改完：`cd frontend && npx vitest run`（2359 tests 基线）
- 全部完成后：`npx vite build` 构建通过
- 浏览器目视确认：登录页 / 仪表盘 / 考试列表

## 风险

| 风险 | 缓解 |
|------|------|
| `--transition` 全局改影响意外组件 | transition 只含 transform/box-shadow/opacity，这三个是最安全的 compositor 属性 |
| `100dvh` 旧浏览器不支持 | dvh 主流浏览器 2023+ 均支持；B 端用户浏览器版本可控 |
| backdrop-filter 去掉后顶栏视觉差异 | 用 0.96 不透明度补偿，视觉几乎无差 |
