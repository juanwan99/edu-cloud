# Code Review Handoff — Batch 2（壳层组件）

## 审查范围

- **Commit range**: `72651ee..6cc0959`（5 commits）
- **Plan**: `docs/plans/2026-03-24-frontend-role-aware-plan.md`（Task T5-T9）
- **Branch**: `feat/frontend-role-aware`

## Commits

| Commit | Task | 描述 |
|--------|------|------|
| 72651ee | T5 | Auth Store — role normalization + context + localStorage + hasPermission |
| 3592563 | T6 | AppShell + AppHeader + SchoolContext + AiFloatingButton 占位 |
| 5a6904b | T7 | AppSidebar 角色过滤侧栏导航 |
| e05cab6 | T8 | RoleSwitcher 角色切换 + NotificationBell 通知铃 |
| 6cc0959 | T9 | Router 重构 — AppShell 根 + 角色/权限守卫 |

## 变更文件（12 files, +1010/-55）

### 核心变更
- `frontend/src/stores/auth.js` — 多角色 store（normalization + context + switchRole + hasPermission）
- `frontend/src/layouts/AppShell.vue` — 角色感知壳层（AppHeader + AppSidebar + router-view + AiFloatingButton）
- `frontend/src/components/shell/AppHeader.vue` — 68px 毛玻璃顶栏
- `frontend/src/components/shell/AppSidebar.vue` — 角色过滤侧栏导航（sidebarConfig 驱动）
- `frontend/src/components/shell/RoleSwitcher.vue` — 角色切换下拉菜单
- `frontend/src/components/shell/NotificationBell.vue` — 通知铃铛（占位）
- `frontend/src/components/shell/SchoolContext.vue` — 当前角色上下文名称展示
- `frontend/src/components/ai/AiFloatingButton.vue` — AI 助手浮动按钮（占位）
- `frontend/src/router/index.js` — AppShell 根 + 角色/权限守卫

### 测试
- `frontend/src/__tests__/auth-store.test.js` — auth store 单测（109 行新增）
- `frontend/src/__tests__/router.test.js` — router 守卫测试（141 行，含扩展）

## 审查重点

1. Auth store 的 normalization 逻辑是否与后端 `core/permissions.py` 一致
2. Router 守卫是否正确拦截未授权路由
3. 壳层组件是否正确消费 auth store 的响应式状态
4. hasPermission 检查是否与后端 RBAC 映射一致

## 逐 Task 自审

### T5: Auth Store（72651ee）
- **plan 契约**: role normalization + context 对象 + localStorage 持久化 + hasPermission
- **实现检查**: `stores/auth.js` 实现了 normalizeRole 调用、context computed、saveAuthState/loadAuthState、checkPermission
- **测试覆盖**: `auth-store.test.js` 覆盖 hydration、corrupt JSON、logout 清理、legacy alias normalization、context 有/无、permission 检查正反例（8 tests）
- **已知边界**: localStorage quota exceeded 静默失败（非关键，浏览器标准处理）

### T6: AppShell + AppHeader + SchoolContext（3592563）
- **plan 契约**: 角色感知壳层，顶栏含 Logo/SchoolContext/搜索/通知铃/角色切换
- **实现检查**: `AppShell.vue` 组合 AppHeader + AppSidebar + router-view + AiFloatingButton + AiSlidePanel；`AppHeader.vue` 68px 毛玻璃顶栏；`SchoolContext.vue` 展示 currentContext.name
- **测试覆盖**: 组件为纯展示层，由 router 测试间接覆盖（AppShell 作为根布局）
- **已知边界**: 搜索框为占位（设计文档声明 P2 实现）

### T7: AppSidebar（5a6904b）
- **plan 契约**: 角色过滤侧栏导航，sidebarConfig 驱动，折叠/展开
- **实现检查**: `AppSidebar.vue` 消费 getSidebarItems(normalizedRole)，watch currentRole 自动刷新导航项，支持 220px/64px 折叠
- **测试覆盖**: sidebarConfig 单测覆盖各角色导航项过滤；组件为配置驱动纯展示
- **已知边界**: 折叠态 active 指示从 border-left 改为 border-bottom（视觉微调，不影响功能）

### T8: RoleSwitcher + NotificationBell（e05cab6）
- **plan 契约**: NDropdown 角色切换 + NBadge 通知铃
- **实现检查**: `RoleSwitcher.vue` 使用 NDropdown，渲染角色列表含当前标记，handleSwitch 区分 header/divider/logout/index；`NotificationBell.vue` 使用 NBadge + NPopover，占位
- **测试覆盖**: 依赖 auth store 测试（switchRole 逻辑）；组件为 Naive UI 组件组合
- **已知边界**: NotificationBell 为占位（设计声明），无实际 API 调用

### T9: Router 重构（6cc0959）
- **plan 契约**: AppShell 根 + 角色/权限守卫，2 顶级 + 14 子路由
- **实现检查**: `router/index.js` — Login 外置，AppShell 包裹全部认证路由，meta.roles 和 meta.permissions 双模守卫，normalizeRole 处理 legacy alias
- **测试覆盖**: `router.test.js` 22 tests — 路由结构验证（2 顶级 + 14 子路由）、认证重定向、角色拦截（parent 不能访问 exams）、权限拦截（parent 不能访问 schools）、legacy alias normalization、已认证跳转
- **已知边界**: parse error 时 let through（设计决策：宁可放行不阻断用户）

## 验证清单自检

- [x] 前端测试全绿（54 tests，含 Batch 2 新增的 auth-store 8 + router 22）
- [x] 后端测试无回归（781 tests）
- [x] `git diff --stat` 确认无计划外文件变更
- [x] import 路径检查：所有新组件 import 路径与文件位置一致
- [x] roles.js / permissions.js 与后端 core/permissions.py 的映射一致（8 角色 + 3 别名）
- [x] 无硬编码密钥或敏感信息
- [x] CSS 变量全部使用 design token（`--color-*`, `--radius-*`, `--shadow-*`），无硬编码色值

## 自查

| 维度 | 结果 |
|------|------|
| 测试充分性 | auth store 8 tests + router 22 tests，覆盖正反例、边界、legacy alias |
| 行为正确性 | normalization 逻辑前后端镜像、守卫拦截 + 放行双向验证 |
| 安全 | 无明文密钥、token 仅存 localStorage（SPA 标准模式）、权限检查前端+后端双重 |
| 架构 | config → stores → components 单向依赖，无反向引用 |
| 已知限制 | 搜索框/通知铃为占位、localStorage quota 静默处理 |
