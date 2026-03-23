# 前端角色感知重设计 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 edu-cloud 前端从扁平单校 UI 改造为多校多角色分层 UI，让每个角色登录后看到专属的导航和 Dashboard。

**Architecture:** AppShell 壳层（Header + Sidebar + AI 浮窗）包裹所有页面，JSON 配置驱动角色差异化。后端补 3 个轻量 API（login context / dashboard summary / notifications）。

**Tech Stack:** Vue 3.5, Naive UI 2.44, Pinia 3, Vite 7, Vitest 4, FastAPI

**Design doc:** `docs/plans/2026-03-23-frontend-role-aware-redesign-design.md`

---

## Batch 1: 后端 API + 样式基础（可独立测试）

### Task 1: 后端 — login/switch-role 返回 context 对象

**Files:**
- Modify: `src/edu_cloud/api/auth.py`
- Modify: `tests/test_api/test_auth.py` (或新增测试)
- Modify: `tests/conftest.py` (seed_school fixture 补 name)

**Why:** 顶栏需要显示学校名，但登录只返回 school_id。教师/家长无 VIEW_SCHOOLS 权限，无法通过 /schools API 获取。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_auth.py
async def test_login_returns_context(client, db):
    """登录响应应包含 context 对象（type + name）。"""
    # seed user + school
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school = School(name="测试一校", code="CTX01", district="测试区")
    db.add(school)
    await db.flush()
    user = User(username="ctx_user", display_name="上下文测试")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()

    resp = await client.post("/api/v1/auth/login", json={"username": "ctx_user", "password": "123456"})
    assert resp.status_code == 200
    data = resp.json()
    # 每个 role 应该有 context
    assert "roles" in data
    role = data["roles"][0]
    assert "context" in role
    assert role["context"]["type"] == "school"
    assert role["context"]["name"] == "测试一校"


async def test_login_platform_admin_context(client, admin_user):
    """platform_admin 的 context.type 应为 platform。"""
    resp = await client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "test123"})
    data = resp.json()
    role = data["roles"][0]
    assert role["context"]["type"] == "platform"
    assert role["context"]["name"] == "全平台"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_auth.py -v -k "context"`
Expected: FAIL — `"context" not in role`

- [ ] **Step 3: 实现 — 修改 auth.py login 端点**

在 `auth.py` 的 login 响应中，为每个 role 补 context 字段：

```python
# 在 login 端点，roles 序列化部分添加：
async def _build_role_context(role, db):
    """构建角色的上下文对象。"""
    if role.school_id is None:
        if role.role in ("platform_admin", "admin"):
            return {"type": "platform", "id": None, "name": "全平台"}
        elif role.role == "district_admin":
            return {"type": "district", "id": None, "name": "管辖区域"}
        return {"type": "platform", "id": None, "name": "全平台"}

    from edu_cloud.models.school import School
    school = await db.get(School, role.school_id)
    return {
        "type": "school",
        "id": role.school_id,
        "name": school.name if school else "未知学校",
    }
```

修改 login 响应的 roles 序列化，每个 role 加 `context` 字段。switch-role 响应同理。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_auth.py -v -k "context"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/auth.py tests/test_api/test_auth.py
git commit -m "feat(api): login/switch-role 返回 context 对象（type+id+name）"
```

---

### Task 2: 后端 — Dashboard Summary API

**Files:**
- Create: `src/edu_cloud/api/dashboard.py`
- Modify: `src/edu_cloud/api/app.py` (注册路由)
- Create: `tests/test_api/test_dashboard.py`

**Why:** KPI 卡片需要聚合统计（学生数/班级数/考试数/待批改数）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_dashboard.py
async def test_dashboard_summary_principal(client, teacher_headers, seed_exam_with_results):
    """校长级角色应看到全校聚合统计。"""
    resp = await client.get("/api/v1/dashboard/summary", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_students" in data
    assert "total_classes" in data
    assert "total_exams" in data
    assert isinstance(data["total_students"], int)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_dashboard.py -v`
Expected: FAIL — 404 (路由不存在)

- [ ] **Step 3: 实现**

```python
# src/edu_cloud/api/dashboard.py
"""Dashboard Summary API — 角色 scope 内的聚合统计。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.api.permissions import get_visible_class_ids
from edu_cloud.modules.student.models import Student, Class
from edu_cloud.modules.exam.models import Exam

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

@router.get("/summary")
async def get_summary(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = role.school_id
    if not school_id:
        return {"total_students": 0, "total_classes": 0, "total_exams": 0, "pending_grading": 0}

    visible_classes = get_visible_class_ids(role)

    # Students count
    q = select(func.count(Student.id)).where(Student.school_id == school_id)
    if visible_classes is not None:
        q = q.where(Student.class_id.in_(visible_classes))
    total_students = (await db.execute(q)).scalar() or 0

    # Classes count
    q = select(func.count(Class.id)).where(Class.school_id == school_id)
    if visible_classes is not None:
        q = q.where(Class.id.in_(visible_classes))
    total_classes = (await db.execute(q)).scalar() or 0

    # Exams count
    total_exams = (await db.execute(
        select(func.count(Exam.id)).where(Exam.school_id == school_id)
    )).scalar() or 0

    return {
        "total_students": total_students,
        "total_classes": total_classes,
        "total_exams": total_exams,
        "pending_grading": 0,  # placeholder
    }
```

在 `app.py` 注册路由：`from edu_cloud.api.dashboard import router as dashboard_router`

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_dashboard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/dashboard.py src/edu_cloud/api/app.py tests/test_api/test_dashboard.py
git commit -m "feat(api): GET /dashboard/summary — 角色 scope 聚合统计"
```

---

### Task 3: 前端 — CSS Token 系统 + Naive UI 主题切换

**Files:**
- Modify: `frontend/src/assets/styles/variables.css`
- Modify: `frontend/src/theme.js`
- Modify: `frontend/src/App.vue` (移除 darkTheme)

**Why:** 当前使用 Naive UI darkTheme，与 momowan 白底风格冲突。需要统一 CSS token。

- [ ] **Step 1: 更新 variables.css**

写入 §8 定义的完整 token 表（颜色、圆角、阴影、动效）。

- [ ] **Step 2: 更新 theme.js**

Naive UI themeOverrides 对齐 momowan token：primaryColor → #1a2e1f，borderRadius → 10px 等。

- [ ] **Step 3: App.vue 移除 darkTheme**

将 `<n-config-provider :theme="darkTheme">` 改为 `<n-config-provider :theme-overrides="themeOverrides">`。

- [ ] **Step 4: 验证构建 + 视觉检查**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vite build`
Expected: 构建成功，无报错

Run: `npm run dev` → 浏览器检查登录页是否为白底 momowan 风格

- [ ] **Step 5: Commit**

```bash
git add frontend/src/assets/styles/variables.css frontend/src/theme.js frontend/src/App.vue
git commit -m "style: CSS token 系统 + Naive UI 切换为 momowan light 主题"
```

---

### Task 4: 前端 — 角色配置文件

**Files:**
- Create: `frontend/src/config/roles.js`
- Create: `frontend/src/config/sidebarConfig.js`
- Create: `frontend/src/config/dashboardConfig.js`
- Create: `frontend/src/__tests__/config.test.js`

**Why:** 角色常量、侧栏导航、Dashboard widget 配置是整个角色感知系统的核心数据。

- [ ] **Step 1: 写测试**

```javascript
// frontend/src/__tests__/config.test.js
import { describe, it, expect } from 'vitest'
import { CANONICAL_ROLES, ROLE_LABELS, normalizeRole, SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { getSidebarItems } from '../config/sidebarConfig.js'
import { getDashboardConfig } from '../config/dashboardConfig.js'

describe('roles config', () => {
  it('has 8 canonical roles', () => {
    expect(CANONICAL_ROLES).toHaveLength(8)
  })
  it('normalizes legacy aliases', () => {
    expect(normalizeRole('admin')).toBe('platform_admin')
    expect(normalizeRole('teacher')).toBe('subject_teacher')
    expect(normalizeRole('head_teacher')).toBe('homeroom_teacher')
    expect(normalizeRole('principal')).toBe('principal')  // no change
  })
  it('SCHOOL_ADMIN_ROLES includes platform_admin and principal', () => {
    expect(SCHOOL_ADMIN_ROLES).toContain('platform_admin')
    expect(SCHOOL_ADMIN_ROLES).toContain('principal')
    expect(SCHOOL_ADMIN_ROLES).not.toContain('parent')
  })
})

describe('sidebar config', () => {
  it('returns items for every canonical role', () => {
    for (const role of CANONICAL_ROLES) {
      const items = getSidebarItems(role)
      expect(items.length, `${role} should have sidebar items`).toBeGreaterThan(0)
    }
  })
  it('parent has minimal items', () => {
    const items = getSidebarItems('parent')
    expect(items.length).toBeLessThanOrEqual(3)
  })
})

describe('dashboard config', () => {
  it('returns config for every canonical role', () => {
    for (const role of CANONICAL_ROLES) {
      const config = getDashboardConfig(role)
      expect(config, `${role} should have dashboard config`).toBeTruthy()
      expect(config.kpis?.length).toBeGreaterThan(0)
    }
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/config.test.js`
Expected: FAIL — modules not found

- [ ] **Step 3: 实现 roles.js**

```javascript
// frontend/src/config/roles.js
export const CANONICAL_ROLES = [
  'platform_admin', 'district_admin', 'principal', 'academic_director',
  'grade_leader', 'homeroom_teacher', 'subject_teacher', 'parent',
]

export const LEGACY_ALIAS_MAP = {
  admin: 'platform_admin',
  teacher: 'subject_teacher',
  head_teacher: 'homeroom_teacher',
}

export function normalizeRole(role) {
  return LEGACY_ALIAS_MAP[role] || role
}

export const SCHOOL_ADMIN_ROLES = ['platform_admin', 'district_admin', 'principal', 'academic_director']
export const EXAM_ROLES = [...SCHOOL_ADMIN_ROLES, 'grade_leader', 'homeroom_teacher', 'subject_teacher']
export const MARKING_ROLES = [...SCHOOL_ADMIN_ROLES, 'homeroom_teacher', 'subject_teacher']

export const ROLE_LABELS = {
  platform_admin: '平台管理员', district_admin: '区管理员', principal: '校长',
  academic_director: '教务主任', grade_leader: '年级组长',
  homeroom_teacher: '班主任', subject_teacher: '科任教师', parent: '家长',
}
```

- [ ] **Step 4: 实现 sidebarConfig.js**

按 spec §3.2 定义每个角色的侧栏导航项。每项包含 `{ icon, label, route, badge? }`。

- [ ] **Step 5: 实现 dashboardConfig.js**

按 spec §4 定义每个角色的 KPI 列表和 widget 列表。每个 widget 包含 `{ type, id, title, icon, route?, planned? }`。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/config.test.js`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/config/ frontend/src/__tests__/config.test.js
git commit -m "feat: 角色配置文件 — roles/sidebar/dashboard JSON 驱动"
```

---

## Batch 2: 壳层组件（AppShell + 导航）

### Task 5: Auth Store 增强 — role normalization + context

**Files:**
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/__tests__/router.test.js` (验证 normalization)

**Why:** auth store 需要 normalize legacy 角色名，存储 context 对象，提供 permissions 计算属性。

- [ ] **Step 1: 修改 auth store**

- login 时 normalize 每个 role 的 role name
- 存储 context 对象（来自 login 响应）
- 添加 `currentContext` computed
- 修改 `isAdmin` 使用 `normalizeRole`
- 添加 `hasPermission(perm)` 方法（本地检查，不调 API）

- [ ] **Step 2: 验证前端测试通过**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add frontend/src/stores/auth.js
git commit -m "feat(auth): role normalization + context 存储 + hasPermission"
```

---

### Task 6: AppShell + AppHeader

**Files:**
- Create: `frontend/src/layouts/AppShell.vue`
- Create: `frontend/src/components/shell/AppHeader.vue`
- Create: `frontend/src/components/shell/SchoolContext.vue`

**Why:** 新的壳层布局：固定顶栏 + 可折叠侧栏 + 主内容区。

- [ ] **Step 1: 创建 AppHeader**

68px 固定顶栏：Logo（edu-cloud 智能平台）+ SchoolContext + 搜索占位 + 通知铃占位 + 头像菜单占位。
毛玻璃效果，momowan 风格。

- [ ] **Step 2: 创建 SchoolContext**

显示 `auth.currentContext.name`。纯展示组件。

- [ ] **Step 3: 创建 AppShell**

```vue
<template>
  <div class="app-shell">
    <AppHeader />
    <div class="app-body">
      <AppSidebar />  <!-- Task 7 -->
      <main class="app-main">
        <router-view />
      </main>
    </div>
    <AiFloatingButton />  <!-- Task 11 -->
  </div>
</template>
```

暂时 AppSidebar 和 AiFloatingButton 用空占位。

- [ ] **Step 4: 验证构建**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vite build`
Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layouts/AppShell.vue frontend/src/components/shell/
git commit -m "feat: AppShell 壳层 + AppHeader 顶栏 + SchoolContext"
```

---

### Task 7: AppSidebar — 角色过滤导航

**Files:**
- Create: `frontend/src/components/shell/AppSidebar.vue`

**Why:** 左侧栏是角色感知的核心——不同角色看到不同导航。

- [ ] **Step 1: 实现 AppSidebar**

- 从 `sidebarConfig.js` 获取当前角色的导航项
- 渲染导航列表（图标 + 标签 + 可选 badge）
- 支持折叠（220px ↔ 64px）
- Active 态：左边框 + 背景变色
- 底部：AI 助手入口（仅 USE_AI_CHAT 角色）
- 监听 `auth.currentRole` 变化自动刷新

- [ ] **Step 2: 验证构建 + 视觉检查**

Run: `npm run dev` → 登录后检查侧栏是否按角色渲染

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/shell/AppSidebar.vue
git commit -m "feat: AppSidebar 角色过滤侧栏导航"
```

---

### Task 8: RoleSwitcher + NotificationBell

**Files:**
- Create: `frontend/src/components/shell/RoleSwitcher.vue`
- Create: `frontend/src/components/shell/NotificationBell.vue`
- Modify: `frontend/src/components/shell/AppHeader.vue` (集成)

**Why:** 头像菜单中的角色切换 + 通知铃。

- [ ] **Step 1: 实现 RoleSwitcher**

NDropdown 嵌入头像菜单。显示所有角色 + context.name。当前角色高亮。
点击切换调用 `auth.switchRole()`，触发 sidebar + dashboard 刷新。

- [ ] **Step 2: 实现 NotificationBell**

NPopover 触发。badge 红点。内容暂时显示"暂无通知"占位（notifications API 待后续接入）。

- [ ] **Step 3: 集成到 AppHeader**

替换之前的占位。

- [ ] **Step 4: 验证**

Run: `npm run dev` → 测试角色切换、通知铃展开

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/shell/RoleSwitcher.vue frontend/src/components/shell/NotificationBell.vue
git add frontend/src/components/shell/AppHeader.vue
git commit -m "feat: RoleSwitcher 角色切换 + NotificationBell 通知铃"
```

---

### Task 9: Router 重构 — AppShell + 权限守卫

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/__tests__/router.test.js`

**Why:** 路由树需要以 AppShell 为根，所有页面作为 children。守卫需要检查角色/权限。

- [ ] **Step 1: 更新测试**

```javascript
// 新增测试
it('all routes except login are children of AppShell', () => { ... })
it('marking/assign requires SCHOOL_ADMIN_ROLES', () => { ... })
it('parent cannot access exams route', () => { ... })
```

- [ ] **Step 2: 重构路由**

- 以 AppShell 为根路由组件
- 所有页面为 children（按 spec §6.2 路由表）
- 每个路由补 `meta.roles` 或 `meta.permissions`
- authGuard 增强：检查 roles/permissions
- WorkbenchPage 重命名路由为 `/analysis`（文件暂不改名）
- LoginPage 保持在 AppShell 外

- [ ] **Step 3: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.js frontend/src/__tests__/router.test.js
git commit -m "refactor: 路由重构 — AppShell 根 + 角色/权限守卫"
```

---

## Batch 3: Dashboard 组件 + 页面

### Task 10: Dashboard 组件 — KpiCard + DashboardCard + WidgetGrid

**Files:**
- Create: `frontend/src/components/dashboard/KpiCard.vue`
- Create: `frontend/src/components/dashboard/DashboardCard.vue`
- Create: `frontend/src/components/dashboard/WidgetGrid.vue`

**Why:** Dashboard 页面由这些可复用组件组合。

- [ ] **Step 1: KpiCard**

Props: `{ value, label, sublabel, color, trend }`
色彩: macaron 柔彩 (mint/yellow/coral/purple)
数值: 36px weight 800 primary色

- [ ] **Step 2: DashboardCard**

Props: `{ title, icon, route, planned, children(slot) }`
白底卡片, 24px 圆角, hover 上浮。`planned=true` 时灰度显示。

- [ ] **Step 3: WidgetGrid**

Props: `{ columns }`（默认 2）
CSS Grid 容器，gap 24px。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/
git commit -m "feat: Dashboard 组件 — KpiCard + DashboardCard + WidgetGrid"
```

---

### Task 11: ActivityFeed + DashboardPage

**Files:**
- Create: `frontend/src/components/dashboard/ActivityFeed.vue`
- Rewrite: `frontend/src/pages/DashboardPage.vue`

**Why:** 这是用户登录后看到的第一个页面，角色感知的核心体验。

- [ ] **Step 1: ActivityFeed**

时间线列表，按日期分组。Props: `{ items: [{ time, text, type }] }`。
占位数据，后续从 notifications API 获取。

- [ ] **Step 2: 重写 DashboardPage**

```vue
<script setup>
import { computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getDashboardConfig } from '../config/dashboardConfig'
import { normalizeRole } from '../config/roles'
import KpiCard from '../components/dashboard/KpiCard.vue'
import DashboardCard from '../components/dashboard/DashboardCard.vue'
import WidgetGrid from '../components/dashboard/WidgetGrid.vue'
import ActivityFeed from '../components/dashboard/ActivityFeed.vue'

const auth = useAuthStore()
const role = computed(() => normalizeRole(auth.currentRole?.role || ''))
const config = computed(() => getDashboardConfig(role.value))

// 每个 KPI 独立请求数据
// ...
</script>
```

读取 `dashboardConfig` → 渲染 KPI 行 + 模块卡片网格 + 动态流。

- [ ] **Step 3: 验证**

Run: `npm run dev` → 以不同角色登录检查 Dashboard 差异
Run: `npx vitest run` → 确认无回归

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/ActivityFeed.vue frontend/src/pages/DashboardPage.vue
git commit -m "feat: 角色定制 Dashboard — KPI + 模块卡片 + 动态流"
```

---

## Batch 4: AI 浮窗 + 清理

### Task 12: AI 浮窗 — AiFloatingButton + AiSlidePanel

**Files:**
- Create: `frontend/src/components/ai/AiFloatingButton.vue`
- Create: `frontend/src/components/ai/AiSlidePanel.vue`
- Modify: `frontend/src/components/workspace/ChatPanel.vue` (提取为独立组件)
- Modify: `frontend/src/layouts/AppShell.vue` (集成浮窗)

**Why:** AI 助手从任何页面可调出，不再锁死在三栏布局。

- [ ] **Step 1: AiFloatingButton**

48px 圆形按钮，墨绿色，右下角固定。hover 上浮 + shadow。
仅 `hasPermission('USE_AI_CHAT')` 时渲染。
点击 emit `toggle`。

- [ ] **Step 2: AiSlidePanel**

右侧滑出 400px 面板。包含标题栏（关闭 + 展开按钮）+ ChatPanel + 输入框。
复用 `aiChat.js` store。

- [ ] **Step 3: 重构 ChatPanel**

从 workspace/ChatPanel.vue 提取核心对话逻辑到 ai/ChatPanel.vue。
保持 workspace 版本作为三栏页的 wrapper。

- [ ] **Step 4: 集成到 AppShell**

AppShell 底部添加 AiFloatingButton + AiSlidePanel。

- [ ] **Step 5: 验证**

Run: `npm run dev` → 测试浮窗打开/关闭/对话
Run: `npx vitest run` → 无回归

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ai/ frontend/src/layouts/AppShell.vue
git commit -m "feat: AI 浮窗 — 任意页面右下角调出 AI 助手"
```

---

### Task 13: 清理 — 删除旧组件 + 重命名

**Files:**
- Delete: `frontend/src/components/AppNavbar.vue`
- Delete: `frontend/src/layouts/DashboardLayout.vue`
- Rename: `frontend/src/pages/WorkbenchPage.vue` → `frontend/src/pages/AnalysisPage.vue`
- Modify: `frontend/src/layouts/AppShell.vue` (确认不引用旧组件)
- Modify: `frontend/src/router/index.js` (更新 import)

**Why:** 旧组件被新壳层替代，需要清理避免混淆。

- [ ] **Step 1: 删除 AppNavbar.vue**

确认没有其他文件 import 它。

- [ ] **Step 2: 删除 DashboardLayout.vue**

确认没有其他文件引用。

- [ ] **Step 3: 重命名 WorkbenchPage → AnalysisPage**

更新 router import。

- [ ] **Step 4: 运行全量验证**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vite build`
Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add -A frontend/
git commit -m "chore: 删除 AppNavbar + DashboardLayout，重命名 WorkbenchPage → AnalysisPage"
```

---

### Task 14: CLAUDE.md 更新 + 最终验证

**Files:**
- Modify: `CLAUDE.md` (更新项目结构、路由数、测试数)
- Modify: `docs/plans/2026-03-23-frontend-role-aware-redesign-design.md` (标记 `[实现完成]`)

- [ ] **Step 1: 更新 CLAUDE.md**

项目结构段落更新：新增 layouts/AppShell、components/shell/*、components/dashboard/*、components/ai/*、config/*。
路由数更新。测试数更新。

- [ ] **Step 2: 标记设计文档实现完成**

在 design.md 顶部添加 `[实现完成] 2026-03-24`。

- [ ] **Step 3: 最终全量验证**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vite build`

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/plans/2026-03-23-frontend-role-aware-redesign-design.md
git commit -m "docs: 更新项目文档 + 设计文档标记实现完成"
```

---

## 批次边界与审查计划

| Batch | Tasks | 可独立验证 | 审查 |
|-------|-------|-----------|------|
| 1 | T1-T4 | 后端 API + CSS + config 全部有测试 | codex-review (code) |
| 2 | T5-T9 | 壳层完整，可视觉检查 | codex-review (code) |
| 3 | T10-T11 | Dashboard 功能完整 | codex-review (code) |
| 4 | T12-T14 | AI 浮窗 + 清理 + 最终验证 | codex-review (code) + integration |
