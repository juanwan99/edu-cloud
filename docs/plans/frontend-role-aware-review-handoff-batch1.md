# Code Review Handoff — Batch 1

**Plan:** `docs/plans/2026-03-24-frontend-role-aware-plan.md`
**Commits:** `5ad0d09..7aeb21e` (5 commits)
**Branch:** `feat/frontend-role-aware`

## Tasks Completed

| Task | Files | Tests |
|------|-------|-------|
| T1: login/switch-role context | auth.py, test_auth_v2.py | 12/12 pass (3 new) |
| T2: Dashboard Summary API | dashboard.py, test_dashboard.py, app.py | 3/3 pass (new) |
| T2b: Notifications List API | notifications_api.py, test_notifications_api.py, app.py, notifications.js | 4/4 pass (new) |
| T3: CSS Token + theme switch | variables.css, App.vue | build pass |
| T4: Config files | roles.js, permissions.js, sidebarConfig.js, dashboardConfig.js, config.test.js | 8/8 pass (new) |

## Verification

- Backend: 780 tests passed (was 770, +10 new)
- Frontend: 35 tests passed (was 17, +18 new)
- Vite build: success

## 逐 Task 自审

| Task | 计划匹配 | 测试覆盖 | 边界处理 | 备注 |
|------|---------|---------|---------|------|
| T1 | ✓ login/switch-role 均返回 context | ✓ 3 个入口级测试 | ✓ platform_admin(无 school) / school role / switch-role | — |
| T2 | ✓ 精确 scope 过滤 | ✓ 3 个角色分组+精确计数 | ✓ 无 school_id→零值 / class_ids scope / null deferred 字段 | — |
| T2b | ✓ school scope + status + since 过滤 | ✓ 4 个测试含 seed 数据 | ✓ 跨校隔离 / 时间窗口 / 未认证 401 | R3-02 deferred: target_scope |
| T3 | ✓ darkTheme→themeOverrides | ✓ vite build 通过 | — | 视觉变更，待用户确认 |
| T4 | ✓ 8 角色全覆盖 | ✓ 8 个配置测试 | ✓ legacy alias / parent 最少项 / 全角色覆盖 | — |

## 验证清单自检

- [x] 后端全量测试：780 passed
- [x] 前端全量测试：35 passed
- [x] Vite 构建：成功
- [x] 无计划外文件变更（`git diff --stat` 确认）
- [x] CLAUDE.md 已同步更新

## 自查

- 权限常量全链路小写（permissions.js + 计划 meta.permissions 说明）
- notifications API 响应包含 title/kind/unread 丰富字段
- dashboard 测试使用精确计数断言（15/10/5），非弱断言
- auth context 在 login 和 switch-role 两个端点均实现

## Known Limitations (from plan review)

- R3-02 deferred: notifications API filters by school_id only, not target_scope
- R3-03 deferred: grade_leader uses class_ids, not grade_ids
