# Code Review Handoff — Batch 3（Dashboard + AI 浮窗）

## 审查范围

- **Commit range**: `b5bc468..1a047df`（3 commits）
- **Plan**: `docs/plans/2026-03-24-frontend-role-aware-plan.md`（Task T10, T11, T12）
- **Branch**: `feat/frontend-role-aware`

## Commits

| Commit | Task | 描述 |
|--------|------|------|
| b5bc468 | T10 | Dashboard 组件 — KpiCard + DashboardCard + WidgetGrid |
| 9d0e0f0 | T12 | AI 浮窗 — AiFloatingButton 权限检查 + AiSlidePanel 右侧滑出 |
| 1a047df | T11 | DashboardPage 角色定制 + ActivityFeed |

## 变更文件（9 files, +649/-127）

### 核心变更
- `frontend/src/components/dashboard/KpiCard.vue` — KPI 卡片（4 色彩变体，趋势指示器）
- `frontend/src/components/dashboard/DashboardCard.vue` — 模块卡片（SVG icon mask，规划中灰度态）
- `frontend/src/components/dashboard/WidgetGrid.vue` — 网格布局容器
- `frontend/src/components/dashboard/ActivityFeed.vue` — 动态列表（按日期分组）
- `frontend/src/pages/DashboardPage.vue` — 重构为角色定制（config 驱动 KPI + 模块 + 动态）
- `frontend/src/components/ai/AiFloatingButton.vue` — 权限检查 `use_ai_chat`
- `frontend/src/components/ai/AiSlidePanel.vue` — 右侧滑出面板（占位，含"打开工作台"链接）
- `frontend/src/layouts/AppShell.vue` — 集成 AiSlidePanel
- `frontend/src/config/dashboardConfig.js` — 新增 KPI source 类型

## 审查重点

1. DashboardPage 是否正确根据角色切换 KPI/Widget 配置
2. KPI 数据从 `/dashboard/summary` API 获取，fallback 为 `--`
3. AiFloatingButton 的 `use_ai_chat` 权限检查是否与后端一致
4. AiSlidePanel 的 overlay 点击关闭和 Transition 动画

## 逐 Task 自审

### T10: Dashboard 组件（b5bc468）
- **plan 契约**: KpiCard（4 色 + 趋势）、DashboardCard（icon + 路由 + 规划态）、WidgetGrid（响应式网格）
- **实现检查**: KpiCard 支持 mint/yellow/coral/purple 4 色 + up/down 趋势 + null/空值 fallback `--`；DashboardCard 使用 CSS mask 渲染 SVG icon，planned 态 grayscale+opacity；WidgetGrid 用 CSS grid 实现 2 列布局
- **测试覆盖**: 组件为纯展示层、props 驱动，DashboardPage 集成测试覆盖数据流
- **已知边界**: DashboardCard ICON_SVGS 为内联 data URI（避免额外网络请求，权衡文件大小）

### T12: AI 浮窗（9d0e0f0）
- **plan 契约**: 右下角浮动按钮 + 滑出面板 + 权限控制
- **实现检查**: AiFloatingButton 用 `authStore.checkPermission('use_ai_chat')` 控制可见性；AiSlidePanel 右侧 400px 滑出，overlay 点击关闭，Transition 动画；AppShell 集成 toggle 状态
- **测试覆盖**: 权限检查复用 auth store 已测逻辑；面板为占位 UI
- **已知边界**: 面板为占位状态，输入框 disabled，显示"AI 助手功能即将上线"

### T11: DashboardPage 角色定制（1a047df）
- **plan 契约**: config 驱动的角色定制仪表盘 + ActivityFeed
- **实现检查**: DashboardPage 用 `getDashboardConfig(role)` 获取角色对应的 KPI/Widget 配置，onMounted 调用 `/dashboard/summary` API 填充 KPI 数据，getKpiValue 按 source 类型路由数据
- **测试覆盖**: dashboardConfig.test.js 覆盖 8 角色的配置完整性；DashboardPage 集成在前端测试中
- **已知边界**: activityItems 为硬编码占位（后续接 notification API）；部分 KPI source 返回 `--`（如 ai_health, local）

## 验证清单自检

- [x] 前端测试全绿（54 tests）
- [x] 后端测试无回归（781 tests）
- [x] DashboardPage 正确消费 dashboardConfig（8 角色全覆盖）
- [x] AiFloatingButton 仅在有 `use_ai_chat` 权限时显示
- [x] AiSlidePanel z-index (1200) > AiFloatingButton z-index (1100) > sidebar
- [x] CSS 全部使用 design token，无硬编码色值（KpiCard trend 色 #16a34a/#dc2626 除外 — 语义色，非品牌色）
- [x] 无硬编码密钥或敏感信息
- [x] 新文件全部 <300 行，职责单一

## 自查

| 维度 | 结果 |
|------|------|
| 测试充分性 | dashboardConfig 8 角色覆盖；展示组件 props 驱动无副作用 |
| 行为正确性 | KPI 数据 API fallback `--`；权限检查复用 auth store |
| 安全 | AI 面板受权限保护；无外部数据注入风险 |
| 架构 | config → page → components 单向数据流；AI 面板与 Dashboard 解耦 |
| 已知限制 | ActivityFeed 占位数据；AI 面板占位 UI；KpiCard trend 色硬编码 |
