<!-- pre-takeover: archived for history, not active spec -->
# P0 平台骨架实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 edu-cloud 超级智能平台骨架——三栏前端 + RBAC 后端 + 数据同步，让班主任能登录、选考试、看成绩分布图。

**Architecture:** Vue 3 + Naive UI 前端（monorepo frontend/），FastAPI 后端保留现有结构并扩展 RBAC（users + user_roles + scope）。PostgreSQL RLS 数据隔离。exam-ai 通过 sync API 推送学生/班级/成绩到 edu-cloud。

**Tech Stack:** Vue 3, Naive UI, Vite, Pinia, ECharts | FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Alembic | pytest, pytest-asyncio

**Design Doc:** `docs/plans/2026-03-21-super-platform-design.md` §1-§4, §8-§9

---

## 文件结构

### 新增文件（前端）

```
frontend/
├── package.json
├── vite.config.js
├── index.html
├── src/
│   ├── main.js                          # Vue 入口
│   ├── App.vue                          # 根组件（路由）
│   ├── router/index.js                  # 路由定义
│   ├── api/client.js                    # axios 封装 + JWT 拦截器
│   ├── stores/
│   │   ├── auth.js                      # 认证状态（登录/角色/token）
│   │   └── context.js                   # 左栏选中上下文状态
│   ├── layouts/
│   │   └── WorkbenchLayout.vue          # 三栏主布局
│   ├── pages/
│   │   ├── LoginPage.vue                # 登录页
│   │   └── WorkbenchPage.vue            # 工作台（三栏容器）
│   └── components/
│       ├── context/
│       │   └── ContextPanel.vue         # 左栏上下文选择器
│       ├── workspace/
│       │   ├── DataView.vue             # 中栏数据呈现
│       │   └── ExamScoreChart.vue       # 成绩分布图组件
│       └── studio/
│           └── StudioPanel.vue          # 右栏（P0 空壳）
```

### 新增文件（后端）

```
src/edu_cloud/
├── models/
│   ├── user.py                          # 新 User 模型（替代 platform_user.py）
│   ├── user_role.py                     # UserRole 模型（多角色 + scope）
│   ├── student.py                       # Student 模型（从 exam-ai 同步）
│   ├── class_group.py                   # ClassGroup 模型
│   └── exam.py                          # Exam + ExamResult 模型
├── api/
│   ├── workspace.py                     # 工作台数据 API（仪表盘/成绩）
│   └── sync_students.py                 # 学生/班级/成绩同步端点
├── services/
│   └── workspace_service.py             # 工作台数据查询逻辑

tests/
├── test_models/
│   ├── test_user_model.py
│   └── test_teaching_models.py
├── test_api/
│   ├── test_auth_v2.py                  # 新认证测试（多角色）
│   ├── test_workspace.py                # 工作台数据测试
│   └── test_sync_students.py            # 同步端点测试
└── test_services/
    └── test_workspace_service.py
```

### 修改文件

```
src/edu_cloud/
├── core/permissions.py                  # 扩展为 7+ 角色 + scope
├── api/deps.py                          # 支持多角色认证 + scope 注入
├── api/app.py                           # 注册新路由
├── api/auth.py                          # 返回多角色信息
├── shared/auth.py                       # JWT payload 扩展（roles）
├── database.py                          # 添加 RLS 相关配置
├── config.py                            # 前端 CORS 配置
tests/conftest.py                        # 新增多角色 fixture
```

---

## Task 1: 前端脚手架

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`, `frontend/src/main.js`, `frontend/src/App.vue`

- [ ] **Step 1: 初始化 Vite + Vue 3 项目**

```bash
cd C:/Users/Administrator/edu-cloud
npm create vite@latest frontend -- --template vue
cd frontend
npm install
npm install naive-ui @vicons/ionicons5 vue-router@4 pinia axios echarts vue-echarts
```

- [ ] **Step 2: 配置 vite.config.js**

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      }
    }
  }
})
```

- [ ] **Step 3: 配置 main.js 入口**

```javascript
// frontend/src/main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import naive from 'naive-ui'
import router from './router/index.js'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(naive)
app.mount('#app')
```

- [ ] **Step 4: 创建路由**

```javascript
// frontend/src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../pages/LoginPage.vue') },
  { path: '/', name: 'Workbench', component: () => import('../pages/WorkbenchPage.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
```

- [ ] **Step 5: 创建 App.vue**

```vue
<!-- frontend/src/App.vue -->
<template>
  <n-config-provider :theme="darkTheme">
    <n-message-provider>
      <router-view />
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { darkTheme } from 'naive-ui'
</script>
```

- [ ] **Step 6: 验证前端可启动**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npm run dev`
Expected: Vite 启动在 localhost:5173，显示空白页无报错

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat(P0-1): 前端脚手架 — Vite + Vue 3 + Naive UI + Router + Pinia"
```

**审查清单:**
- ✓ Vite dev server 可启动
- ✓ Naive UI 暗色主题加载
- ✓ 路由守卫生效（未登录跳转 /login）
- ✗ 不应有任何 API 调用

---

## Task 2: 三栏布局

**Files:**
- Create: `frontend/src/layouts/WorkbenchLayout.vue`, `frontend/src/pages/WorkbenchPage.vue`, `frontend/src/pages/LoginPage.vue`
- Create: `frontend/src/components/context/ContextPanel.vue`, `frontend/src/components/workspace/DataView.vue`, `frontend/src/components/studio/StudioPanel.vue`

- [ ] **Step 1: 创建三栏主布局**

```vue
<!-- frontend/src/layouts/WorkbenchLayout.vue -->
<template>
  <n-layout has-sider style="height: 100vh">
    <!-- 左栏 -->
    <n-layout-sider
      bordered
      :collapsed="leftCollapsed"
      :collapsed-width="64"
      :width="280"
      show-trigger
      @collapse="leftCollapsed = true"
      @expand="leftCollapsed = false"
    >
      <slot name="left" />
    </n-layout-sider>

    <!-- 中栏 -->
    <n-layout>
      <n-layout-header bordered style="height: 56px; padding: 0 16px; display: flex; align-items: center; justify-content: space-between;">
        <slot name="header" />
      </n-layout-header>
      <n-layout-content content-style="padding: 16px; height: calc(100vh - 56px); overflow-y: auto;">
        <slot name="center" />
      </n-layout-content>
    </n-layout>

    <!-- 右栏 -->
    <n-layout-sider
      bordered
      :collapsed="rightCollapsed"
      :collapsed-width="0"
      :width="320"
      show-trigger="bar"
      collapse-mode="transform"
      @collapse="rightCollapsed = true"
      @expand="rightCollapsed = false"
    >
      <slot name="right" />
    </n-layout-sider>
  </n-layout>
</template>

<script setup>
import { ref } from 'vue'
const leftCollapsed = ref(false)
const rightCollapsed = ref(false)
</script>
```

- [ ] **Step 2: 创建左栏占位组件**

```vue
<!-- frontend/src/components/context/ContextPanel.vue -->
<template>
  <div style="padding: 16px">
    <n-h3>上下文</n-h3>
    <n-text depth="3">P0: 数据源选择器将在 Step 5 实现</n-text>
  </div>
</template>
```

- [ ] **Step 3: 创建中栏占位组件**

```vue
<!-- frontend/src/components/workspace/DataView.vue -->
<template>
  <div>
    <n-h3>工作台</n-h3>
    <n-text depth="3">P0: 数据呈现将在 Task 6 实现</n-text>
  </div>
</template>
```

- [ ] **Step 4: 创建右栏占位组件**

```vue
<!-- frontend/src/components/studio/StudioPanel.vue -->
<template>
  <div style="padding: 16px">
    <n-h3>Studio</n-h3>
    <n-text depth="3">P2 实现：AI 产出物 + 行动队列</n-text>
  </div>
</template>
```

- [ ] **Step 5: 创建登录页占位**

```vue
<!-- frontend/src/pages/LoginPage.vue -->
<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #1a1a2e;">
    <n-card style="width: 400px" title="edu-cloud 智能平台">
      <n-text depth="3">P0-4: 登录表单将在 Task 4 实现</n-text>
    </n-card>
  </div>
</template>
```

- [ ] **Step 6: 组装 WorkbenchPage**

```vue
<!-- frontend/src/pages/WorkbenchPage.vue -->
<template>
  <WorkbenchLayout>
    <template #header>
      <n-h3 style="margin: 0">edu-cloud 智能平台</n-h3>
      <n-space>
        <n-text>{{ authStore.displayName }}</n-text>
        <n-tag type="info">{{ authStore.currentRole }}</n-tag>
      </n-space>
    </template>
    <template #left>
      <ContextPanel />
    </template>
    <template #center>
      <DataView />
    </template>
    <template #right>
      <StudioPanel />
    </template>
  </WorkbenchLayout>
</template>

<script setup>
import WorkbenchLayout from '../layouts/WorkbenchLayout.vue'
import ContextPanel from '../components/context/ContextPanel.vue'
import DataView from '../components/workspace/DataView.vue'
import StudioPanel from '../components/studio/StudioPanel.vue'
import { useAuthStore } from '../stores/auth.js'

const authStore = useAuthStore()
</script>
```

- [ ] **Step 7: 创建 auth store 占位**

```javascript
// frontend/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const displayName = ref('开发模式')
  const currentRole = ref('platform_admin')
  const roles = ref([])
  const scope = ref({})

  return { token, displayName, currentRole, roles, scope }
})
```

- [ ] **Step 8: 验证三栏布局**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npm run dev`
Expected: 三栏并排显示，左右栏可折叠，顶栏显示用户信息

- [ ] **Step 9: Commit**

```bash
git add frontend/src/
git commit -m "feat(P0-2): 三栏工作台布局 — WorkbenchLayout + 左中右占位组件"
```

**审查清单:**
- ✓ 三栏并排，左栏 280px，右栏 320px，中栏自适应
- ✓ 左右栏折叠/展开功能正常
- ✓ 顶栏显示用户名和角色标签
- ✗ 不应有 API 调用，纯前端骨架

---

## Task 3: RBAC 后端重构

**Files:**
- Create: `src/edu_cloud/models/user.py`, `src/edu_cloud/models/user_role.py`
- Modify: `src/edu_cloud/core/permissions.py`, `src/edu_cloud/api/deps.py`, `src/edu_cloud/shared/auth.py`
- Test: `tests/test_models/test_user_model.py`, `tests/test_api/test_auth_v2.py`

- [ ] **Step 1: 写 User 模型测试**

```python
# tests/test_models/test_user_model.py
import pytest
from edu_cloud.models.user import User

def test_user_has_required_fields():
    """User 模型包含必要字段"""
    columns = {c.name for c in User.__table__.columns}
    assert "username" in columns
    assert "display_name" in columns
    assert "hashed_password" in columns
    assert "is_active" in columns
    assert "phone" in columns

def test_user_table_name():
    assert User.__tablename__ == "users"

def test_username_unique_constraint():
    """PR-05: username 必须有唯一约束"""
    username_col = User.__table__.c.username
    assert username_col.unique is True

def test_username_not_nullable():
    username_col = User.__table__.c.username
    assert username_col.nullable is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_models/test_user_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.models.user'`

- [ ] **Step 3: 实现 User 模型**

```python
# src/edu_cloud/models/user.py
from sqlalchemy import Column, String, Boolean, DateTime
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class User(Base, IdMixin, TimestampMixin):
    __tablename__ = "users"

    username = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_models/test_user_model.py -v`
Expected: PASS

- [ ] **Step 5: 写 UserRole 模型测试**

```python
# tests/test_models/test_user_model.py (追加)
from edu_cloud.models.user_role import UserRole

def test_user_role_has_scope_fields():
    """UserRole 包含 scope 字段"""
    columns = {c.name for c in UserRole.__table__.columns}
    assert "user_id" in columns
    assert "role" in columns
    assert "school_id" in columns
    assert "grade_ids" in columns
    assert "class_ids" in columns
    assert "subject_codes" in columns
    assert "is_primary" in columns
```

- [ ] **Step 6: 实现 UserRole 模型**

```python
# src/edu_cloud/models/user_role.py
from sqlalchemy import Column, String, ForeignKey, Boolean, JSON
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class UserRole(Base, IdMixin, TimestampMixin):
    __tablename__ = "user_roles"

    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)  # principal / academic_director / grade_leader / homeroom_teacher / subject_teacher / district_admin / parent / platform_admin
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=True)
    grade_ids = Column(JSON, nullable=True)       # ["grade-7", "grade-8"]
    class_ids = Column(JSON, nullable=True)        # ["class-7-2"]
    subject_codes = Column(JSON, nullable=True)    # ["SX", "YW"]
    is_primary = Column(Boolean, default=False, nullable=False)
```

- [ ] **Step 7: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_models/test_user_model.py -v`
Expected: PASS

- [ ] **Step 8: 扩展 permissions.py（保留旧枚举值兼容）**

> **重要:** 现有 API 路由（schools.py, joint_exams.py, results.py, sync.py）和 58 个测试
> 都引用旧 Permission 枚举值。必须保留旧值作为别名，不能删除或重命名。

```python
# src/edu_cloud/core/permissions.py — 扩展（非重写，保留所有旧值）
from enum import Enum

class Permission(str, Enum):
    # 数据查看
    VIEW_STUDENTS = "VIEW_STUDENTS"
    VIEW_EXAMS = "VIEW_EXAMS"
    VIEW_SCORES = "VIEW_SCORES"
    VIEW_CROSS_SCHOOL = "VIEW_CROSS_SCHOOL"
    # 管理
    MANAGE_SCHOOLS = "MANAGE_SCHOOLS"
    VIEW_SCHOOLS = "VIEW_SCHOOLS"
    MANAGE_USERS = "MANAGE_USERS"
    MANAGE_JOINT_EXAM = "MANAGE_JOINT_EXAM"
    CREATE_JOINT_EXAM = "CREATE_JOINT_EXAM"
    VIEW_JOINT_EXAM = "VIEW_JOINT_EXAM"
    # Studio（P2 预留）
    GENERATE_REPORT = "GENERATE_REPORT"
    GENERATE_NOTIFICATION = "GENERATE_NOTIFICATION"
    APPROVE_NOTIFICATION = "APPROVE_NOTIFICATION"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    # AI（P1 预留）
    USE_AI_CHAT = "USE_AI_CHAT"
    # 论文（P4 预留）
    WRITE_PAPER = "WRITE_PAPER"
    # 旧值保留（向后兼容现有路由和测试）
    VIEW_CROSS_SCHOOL_ANALYTICS = "VIEW_CROSS_SCHOOL"
    MANAGE_QUESTION_BANK = "MANAGE_QUESTION_BANK"
    VIEW_QUESTION_BANK = "VIEW_QUESTION_BANK"
    MANAGE_PLATFORM = "MANAGE_PLATFORM"

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "platform_admin": set(Permission),
    "district_admin": {
        Permission.VIEW_SCHOOLS, Permission.MANAGE_SCHOOLS,
        Permission.VIEW_CROSS_SCHOOL, Permission.VIEW_JOINT_EXAM,
        Permission.CREATE_JOINT_EXAM, Permission.MANAGE_JOINT_EXAM,
        Permission.GENERATE_REPORT, Permission.USE_AI_CHAT,
    },
    "principal": {
        Permission.VIEW_STUDENTS, Permission.VIEW_EXAMS, Permission.VIEW_SCORES,
        Permission.VIEW_CROSS_SCHOOL, Permission.VIEW_JOINT_EXAM,
        Permission.CREATE_JOINT_EXAM, Permission.MANAGE_JOINT_EXAM,
        Permission.MANAGE_USERS,
        Permission.GENERATE_REPORT, Permission.GENERATE_NOTIFICATION,
        Permission.APPROVE_NOTIFICATION, Permission.SEND_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },
    "academic_director": {
        Permission.VIEW_STUDENTS, Permission.VIEW_EXAMS, Permission.VIEW_SCORES,
        Permission.VIEW_CROSS_SCHOOL, Permission.VIEW_JOINT_EXAM,
        Permission.CREATE_JOINT_EXAM, Permission.MANAGE_JOINT_EXAM,
        Permission.MANAGE_USERS,
        Permission.GENERATE_REPORT, Permission.GENERATE_NOTIFICATION,
        Permission.APPROVE_NOTIFICATION, Permission.SEND_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },
    "grade_leader": {
        Permission.VIEW_STUDENTS, Permission.VIEW_EXAMS, Permission.VIEW_SCORES,
        Permission.VIEW_JOINT_EXAM,
        Permission.GENERATE_REPORT, Permission.USE_AI_CHAT,
    },
    "homeroom_teacher": {
        Permission.VIEW_STUDENTS, Permission.VIEW_EXAMS, Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT, Permission.GENERATE_NOTIFICATION,
        Permission.USE_AI_CHAT,
    },
    "subject_teacher": {
        Permission.VIEW_STUDENTS, Permission.VIEW_EXAMS, Permission.VIEW_SCORES,
        Permission.GENERATE_REPORT, Permission.USE_AI_CHAT, Permission.WRITE_PAPER,
    },
    "parent": {
        Permission.VIEW_SCORES,
    },
}
```

- [ ] **Step 9: 更新 deps.py 支持多角色（渐进兼容）**

> **关键迁移点:** `get_current_user` 返回值从 `PlatformUser` 对象变为 `dict`。
> 以下文件直接使用 `user.role` / `user.id` 等属性访问，必须同步更新：
> - `src/edu_cloud/api/auth.py` — `user.role` → `current["user"]`
> - `src/edu_cloud/api/schools.py` — `Depends(require_permission(...))` 返回值
> - `src/edu_cloud/api/joint_exams.py` — `user.id` 用于 `created_by`
> - `src/edu_cloud/api/results.py` — 仅用 require_permission，影响小
> - `src/edu_cloud/api/sync.py` — 使用 `get_school_by_api_key`（不受影响）
>
> 策略：返回的 dict 中 `user` 键是 User 对象，所以 `current["user"].id` 仍然是属性访问。
> 路由代码改动最小化：`user = current["user"]` 后沿用 `.id` / `.username`。

```python
# src/edu_cloud/api/deps.py
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import decode_token
from edu_cloud.core.permissions import Permission, ROLE_PERMISSIONS

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(401, "Invalid token")

    user = await db.get(User, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(401, "User not found or inactive")

    # 查询用户所有角色
    result = await db.execute(
        select(UserRole).where(UserRole.user_id == user.id)
    )
    roles = result.scalars().all()
    if not roles:
        raise HTTPException(403, "No role assigned")

    # PR-01 修复：支持角色切换
    # JWT payload 含 active_role_id（可选），前端切换角色时重新请求 token
    active_role_id = payload.get("active_role_id")
    if active_role_id:
        active = next((r for r in roles if r.id == active_role_id), None)
    else:
        active = next((r for r in roles if r.is_primary), roles[0])

    return {
        "user": user,
        "roles": roles,
        "current_role": active,
        "permissions": ROLE_PERMISSIONS.get(active.role, set()),
    }

def require_permission(permission: Permission):
    async def checker(current=Depends(get_current_user)):
        if permission not in current["permissions"]:
            raise HTTPException(403, f"Permission denied: {permission}")
        return current
    return checker
```

- [ ] **Step 10: 写认证测试**

```python
# tests/test_api/test_auth_v2.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_login_returns_roles(client, seed_teacher):
    """登录返回用户角色列表"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "teacher1", "password": "123456"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "roles" in data
    assert len(data["roles"]) >= 1
    assert data["roles"][0]["role"] in ["homeroom_teacher", "subject_teacher"]

@pytest.mark.asyncio
async def test_permission_denied_for_wrong_role(client, teacher_headers):
    """教师无权管理学校"""
    resp = await client.post("/api/v1/schools", json={
        "name": "测试校", "code": "TEST01", "district": "测试区"
    }, headers=teacher_headers)
    assert resp.status_code == 403
```

- [ ] **Step 11: 更新 auth.py 登录接口 + seed 新管理员**

修改 login 端点查询新 User + UserRole 表，返回角色列表。
同时更新 `app.py` 的 lifespan seed 逻辑，改为创建新 `User` + `UserRole(platform_admin)` 而非旧 `PlatformUser`。
新增 `POST /api/v1/auth/switch-role` 端点：接收 `role_id`，签发含 `active_role_id` 的新 JWT。

```python
# app.py lifespan seed 改造（PR-02）
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole

existing = await db.execute(select(User).where(User.username == "admin"))
if not existing.scalar_one_or_none():
    admin = User(username="admin", display_name="平台管理员",
                 hashed_password=bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode())
    db.add(admin)
    await db.flush()
    db.add(UserRole(user_id=admin.id, role="platform_admin", is_primary=True))
    await db.commit()
```

- [ ] **Step 12: 更新 conftest.py 添加新 fixture**

```python
# tests/conftest.py 追加
@pytest.fixture
async def seed_teacher(db):
    """创建一个班主任教师"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    import bcrypt
    user = User(
        username="teacher1", display_name="张老师",
        hashed_password=bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode(),
    )
    db.add(user)
    await db.flush()
    # 需要一个学校关联（workspace API 依赖 school_id 查询数据）
    from edu_cloud.models.school import RegisteredSchool
    school = RegisteredSchool(name="测试校", code="TEST01", district="测试区", api_key_hash="placeholder")
    db.add(school)
    await db.flush()
    role = UserRole(
        user_id=user.id, role="homeroom_teacher",
        school_id=school.id,
        class_ids=["class-7-2"], is_primary=True,
    )
    db.add(role)
    await db.commit()
    return user

@pytest.fixture
async def teacher_headers(client, seed_teacher):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "teacher1", "password": "123456"
    })
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 13: 运行全量测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 所有现有 58 tests + 新增 tests 全部 PASS

> **注意:** 现有测试依赖旧 PlatformUser 模型。需要保留旧模型兼容现有测试，或迁移 conftest fixtures。选择迁移 fixtures——将 `admin_user` / `observer_user` 改为使用新 User + UserRole 模型。

- [ ] **Step 14: Commit**

```bash
git add src/edu_cloud/models/user.py src/edu_cloud/models/user_role.py \
        src/edu_cloud/core/permissions.py src/edu_cloud/api/deps.py \
        src/edu_cloud/api/auth.py src/edu_cloud/shared/auth.py \
        tests/
git commit -m "feat(P0-3): RBAC 重构 — User + UserRole + 7 角色 + scope + 权限矩阵"
```

**审查清单:**
- ✓ User 模型包含 username/display_name/hashed_password/is_active
- ✓ UserRole 包含 role/school_id/grade_ids/class_ids/subject_codes/is_primary
- ✓ 7+ 角色权限矩阵与设计文档 §3 一致
- ✓ require_permission 从新模型查询权限
- ✓ 现有 58 tests 无回归
- ✗ 不应删除旧 PlatformUser（渐进迁移）

**边界条件:**
- 用户无角色时 → 403 "No role assigned"
- 用户 is_active=False → 401 "User not found or inactive"
- Token 过期 → 401 "Invalid token"

**测试契约:**
1. 多角色用户登录返回完整角色列表
   - 入口: `POST /api/v1/auth/login`
   - 反例: 错误实现可能只返回第一个角色
   - 边界: 无角色用户 / 单角色 / 多角色
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_auth_v2.py::test_login_returns_roles -v`
2. 权限隔离——教师不能管理学校
   - 入口: `POST /api/v1/schools` with teacher token
   - 反例: 错误实现可能漏掉权限检查
   - 边界: 每种角色 × 每种受限操作
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_auth_v2.py::test_permission_denied_for_wrong_role -v`

---

## Task 4: 登录页前端

**Files:**
- Modify: `frontend/src/pages/LoginPage.vue`, `frontend/src/stores/auth.js`
- Create: `frontend/src/api/client.js`

- [ ] **Step 1: 创建 API 客户端**

```javascript
// frontend/src/api/client.js
import axios from 'axios'
import router from '../router/index.js'

const client = axios.create({ baseURL: '/api/v1' })

client.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

client.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

export default client
```

- [ ] **Step 2: 实现 auth store**

```javascript
// frontend/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import client from '../api/client.js'
import router from '../router/index.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)
  const roles = ref([])
  const currentRoleIndex = ref(0)

  const currentRole = computed(() => roles.value[currentRoleIndex.value] || null)
  const displayName = computed(() => user.value?.display_name || '')
  const roleName = computed(() => currentRole.value?.role || '')

  async function login(username, password) {
    const { data } = await client.post('/auth/login', { username, password })
    token.value = data.access_token
    user.value = data.user
    roles.value = data.roles
    currentRoleIndex.value = roles.value.findIndex(r => r.is_primary) || 0
    localStorage.setItem('token', data.access_token)
    router.push('/')
  }

  async function switchRole(index) {
    // PR-01: 切换角色时请求新 token（后端按 active_role_id 签发）
    currentRoleIndex.value = index
    const roleId = roles.value[index]?.id
    if (roleId) {
      const { data } = await client.post('/auth/switch-role', { role_id: roleId })
      token.value = data.access_token
      localStorage.setItem('token', data.access_token)
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    roles.value = []
    localStorage.removeItem('token')
    router.push('/login')
  }

  return { token, user, roles, currentRole, currentRoleIndex, displayName, roleName, login, switchRole, logout }
})
```

- [ ] **Step 3: 实现登录页**

```vue
<!-- frontend/src/pages/LoginPage.vue -->
<template>
  <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #1a1a2e;">
    <n-card style="width: 400px" title="edu-cloud 智能平台">
      <n-form @submit.prevent="handleLogin">
        <n-form-item label="用户名">
          <n-input v-model:value="username" placeholder="请输入用户名" />
        </n-form-item>
        <n-form-item label="密码">
          <n-input v-model:value="password" type="password" placeholder="请输入密码" @keyup.enter="handleLogin" />
        </n-form-item>
        <n-button type="primary" block :loading="loading" @click="handleLogin">
          登录
        </n-button>
      </n-form>
      <n-text v-if="error" type="error" style="margin-top: 8px">{{ error }}</n-text>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth.js'

const authStore = useAuthStore()
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  loading.value = true
  error.value = ''
  try {
    await authStore.login(username.value, password.value)
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 4: 在顶栏添加角色切换器和登出**

更新 WorkbenchPage.vue 顶栏，添加角色切换下拉和登出按钮。

- [ ] **Step 5: 验证端到端登录流程**

Run: 后端 `python -m uvicorn edu_cloud.api.app:create_app --factory --port 9000`，前端 `npm run dev`
Expected: 打开 localhost:5173 → 跳转登录页 → 输入 admin/123456 → 进入三栏工作台 → 顶栏显示角色

- [ ] **Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat(P0-4): 登录页 + auth store + 角色切换器 + API 客户端"
```

**审查清单:**
- ✓ 登录成功后跳转到工作台
- ✓ 登录失败显示错误信息
- ✓ Token 存储到 localStorage
- ✓ 401 自动跳转登录页
- ✓ 角色切换器显示所有角色
- ✓ 切换角色后请求新 token（后端 active_role_id 生效）
- ✗ 不应明文存储密码

**边界条件（PR-06 补充）:**
- 用户名密码为空 → 期望: 前端阻止提交或后端 422
- 用户不存在 → 期望: 401 "用户名或密码错误"（不泄露是用户名还是密码错误）
- 用户 is_active=False → 期望: 401 "账号已停用"

**测试契约（PR-06 补充）:**
1. 登录失败返回 401
   - 入口: `POST /api/v1/auth/login` body=`{username: "wrong", password: "wrong"}`
   - 反例: 错误实现可能返回 200 + 空 token
   - 边界: 空用户名 / 空密码 / 已停用用户 / 正确用户名错误密码
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_auth_v2.py::test_login_failure -v`
2. 角色切换后权限变化
   - 入口: `POST /api/v1/auth/switch-role` + 后续 API 调用
   - 反例: 错误实现可能只更新前端显示而不更新后端权限
   - 边界: 切换到不存在的 role_id / 切换到非自有角色
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_auth_v2.py::test_switch_role -v`

---

## Task 5: 教学数据模型 + 同步端点

**Files:**
- Create: `src/edu_cloud/models/student.py`, `src/edu_cloud/models/class_group.py`, `src/edu_cloud/models/exam.py`
- Create: `src/edu_cloud/api/sync_students.py`, `tests/test_api/test_sync_students.py`
- Modify: `src/edu_cloud/api/app.py`

- [ ] **Step 1: 写教学数据模型测试**

```python
# tests/test_models/test_teaching_models.py
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.exam import Exam, ExamResult

def test_student_fields():
    cols = {c.name for c in Student.__table__.columns}
    assert "name" in cols
    assert "student_number" in cols
    assert "school_id" in cols
    assert "class_id" in cols

def test_class_group_fields():
    cols = {c.name for c in ClassGroup.__table__.columns}
    assert "name" in cols
    assert "grade" in cols
    assert "school_id" in cols

def test_exam_fields():
    cols = {c.name for c in Exam.__table__.columns}
    assert "name" in cols
    assert "school_id" in cols
    assert "subject_code" in cols

def test_exam_result_fields():
    cols = {c.name for c in ExamResult.__table__.columns}
    assert "exam_id" in cols
    assert "student_id" in cols
    assert "total_score" in cols
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_models/test_teaching_models.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 Student / ClassGroup / Exam / ExamResult 模型**

```python
# src/edu_cloud/models/student.py
from sqlalchemy import Column, String, ForeignKey
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class Student(Base, IdMixin, TimestampMixin):
    __tablename__ = "students"
    name = Column(String, nullable=False)
    student_number = Column(String, nullable=False)
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)
    class_id = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    gender = Column(String, nullable=True)

    # PR-09: upsert 幂等保证
    __table_args__ = (
        UniqueConstraint("school_id", "student_number", name="uq_student_school_number"),
    )
```

```python
# src/edu_cloud/models/class_group.py
from sqlalchemy import Column, String, Integer, ForeignKey
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class ClassGroup(Base, IdMixin, TimestampMixin):
    __tablename__ = "class_groups"
    name = Column(String, nullable=False)         # "七年级2班"
    grade = Column(String, nullable=False)         # "七年级"
    grade_number = Column(Integer, nullable=True)  # 7
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)
```

```python
# src/edu_cloud/models/exam.py
from sqlalchemy import Column, String, Float, ForeignKey, JSON, DateTime
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

class Exam(Base, IdMixin, TimestampMixin):
    __tablename__ = "exams"
    name = Column(String, nullable=False)
    subject_code = Column(String, nullable=False)
    subject_name = Column(String, nullable=True)
    max_score = Column(Float, nullable=True)
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)
    exam_date = Column(DateTime, nullable=True)
    semester = Column(String, nullable=True)       # "2025-2026-2"
    source = Column(String, default="sync")        # "sync" / "manual"

class ExamResult(Base, IdMixin, TimestampMixin):
    __tablename__ = "exam_results"
    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)
    total_score = Column(Float, nullable=False)
    detail_scores = Column(JSON, nullable=True)

    # PR-09: upsert 幂等保证
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_result_exam_student"),
    )
```

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/test_models/test_teaching_models.py -v`
Expected: PASS

- [ ] **Step 5: 写同步端点测试**

```python
# tests/test_api/test_sync_students.py
import pytest

@pytest.mark.asyncio
async def test_sync_students(client, school_api_headers):
    """学校端推送学生档案"""
    resp = await client.post("/api/v1/sync/students", json={
        "students": [
            {"name": "张三", "student_number": "S001", "class_name": "七年级2班", "grade": "七年级", "gender": "男"},
            {"name": "李四", "student_number": "S002", "class_name": "七年级2班", "grade": "七年级", "gender": "女"},
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 2

@pytest.mark.asyncio
async def test_sync_exam_results(client, school_api_headers):
    """学校端推送考试成绩"""
    # 先同步学生
    await client.post("/api/v1/sync/students", json={
        "students": [{"name": "张三", "student_number": "S001", "class_name": "七年级2班", "grade": "七年级"}]
    }, headers=school_api_headers)

    resp = await client.post("/api/v1/sync/exam-results", json={
        "exam": {"name": "期中考试", "subject_code": "SX", "subject_name": "数学", "max_score": 150, "semester": "2025-2026-2"},
        "results": [
            {"student_number": "S001", "total_score": 135.0}
        ]
    }, headers=school_api_headers)
    assert resp.status_code == 200
    assert resp.json()["synced_count"] == 1
```

- [ ] **Step 6: 实现同步端点**

```python
# src/edu_cloud/api/sync_students.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.sync import get_school_by_api_key  # PR-04: 函数定义在 sync.py，非 deps.py；后续应提取到 deps.py

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

@router.post("/students")
async def sync_students(
    body: dict,
    school=Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    count = 0
    for s in body.get("students", []):
        # 1. 查找或创建 ClassGroup
        class_name = s.get("class_name")
        grade = s.get("grade", "")
        if class_name:
            existing_class = (await db.execute(
                select(ClassGroup).where(ClassGroup.name == class_name, ClassGroup.school_id == school.id)
            )).scalar_one_or_none()
            if not existing_class:
                existing_class = ClassGroup(name=class_name, grade=grade, school_id=school.id)
                db.add(existing_class)
                await db.flush()

        # 2. Upsert 学生（student_number + school_id 唯一）
        existing = (await db.execute(
            select(Student).where(Student.student_number == s["student_number"], Student.school_id == school.id)
        )).scalar_one_or_none()
        if existing:
            existing.name = s["name"]
            existing.class_id = existing_class.id if existing_class else None
            existing.grade = grade
            existing.gender = s.get("gender")
        else:
            db.add(Student(
                name=s["name"], student_number=s["student_number"], school_id=school.id,
                class_id=existing_class.id if existing_class else None, grade=grade, gender=s.get("gender"),
            ))
        count += 1
    await db.commit()
    return {"synced_count": count}

@router.post("/exam-results")
async def sync_exam_results(
    body: dict,
    school=Depends(get_school_by_api_key),
    db: AsyncSession = Depends(get_db),
):
    exam_data = body["exam"]
    # 1. 查找或创建 Exam（name + subject_code + school_id 唯一）
    exam = (await db.execute(
        select(Exam).where(
            Exam.name == exam_data["name"],
            Exam.subject_code == exam_data["subject_code"],
            Exam.school_id == school.id,
        )
    )).scalar_one_or_none()
    if not exam:
        exam = Exam(
            name=exam_data["name"], subject_code=exam_data["subject_code"],
            subject_name=exam_data.get("subject_name"), max_score=exam_data.get("max_score"),
            school_id=school.id, semester=exam_data.get("semester"), source="sync",
        )
        db.add(exam)
        await db.flush()

    # 2. Upsert 成绩
    count = 0
    for r in body.get("results", []):
        student = (await db.execute(
            select(Student).where(Student.student_number == r["student_number"], Student.school_id == school.id)
        )).scalar_one_or_none()
        if not student:
            continue  # 学生不存在则跳过

        existing = (await db.execute(
            select(ExamResult).where(ExamResult.exam_id == exam.id, ExamResult.student_id == student.id)
        )).scalar_one_or_none()
        if existing:
            existing.total_score = r["total_score"]
            existing.detail_scores = r.get("detail_scores")
        else:
            db.add(ExamResult(
                exam_id=exam.id, student_id=student.id, school_id=school.id,
                total_score=r["total_score"], detail_scores=r.get("detail_scores"),
            ))
        count += 1
    await db.commit()
    return {"synced_count": count}
```

- [ ] **Step 7: 注册路由到 app.py**

- [ ] **Step 8: 运行测试确认通过**

Run: `python -m pytest tests/test_api/test_sync_students.py -v`
Expected: PASS

- [ ] **Step 9: 运行全量测试**

Run: `python -m pytest --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 10: Commit**

```bash
git add src/edu_cloud/models/student.py src/edu_cloud/models/class_group.py \
        src/edu_cloud/models/exam.py src/edu_cloud/api/sync_students.py \
        src/edu_cloud/api/app.py tests/
git commit -m "feat(P0-5): 教学数据模型 + 学生/成绩同步端点"
```

**审查清单:**
- ✓ Student/ClassGroup/Exam/ExamResult 模型字段与设计文档 §4 一致
- ✓ 同步端点使用 API Key 认证
- ✓ 学生同步使用 upsert（student_number + school_id 唯一）
- ✓ ClassGroup 自动创建（同步学生时按 class_name 查找或创建）
- ✗ 不应同步原始切图数据

**测试契约:**
1. 学生同步 upsert 语义
   - 入口: `POST /api/v1/sync/students`
   - 反例: 错误实现会重复创建学生记录
   - 边界: 空列表 / 重复 student_number / 新班级
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_sync_students.py::test_sync_students -v`
2. 成绩同步关联正确
   - 入口: `POST /api/v1/sync/exam-results`
   - 反例: 错误实现可能关联到错误学生
   - 边界: 学生不存在 / 重复提交 / 空成绩列表
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_sync_students.py::test_sync_exam_results -v`

---

## Task 6: 工作台数据 API + 左栏选择器

**Files:**
- Create: `src/edu_cloud/api/workspace.py`, `src/edu_cloud/services/workspace_service.py`
- Create: `tests/test_api/test_workspace.py`, `tests/test_services/test_workspace_service.py`
- Modify: `frontend/src/components/context/ContextPanel.vue`, `frontend/src/stores/context.js`
- Modify: `frontend/src/components/workspace/DataView.vue`

- [ ] **Step 1: 写工作台 API 测试**

```python
# tests/test_api/test_workspace.py
import pytest

@pytest.mark.asyncio
async def test_get_context_tree(client, teacher_headers):
    """获取左栏上下文树"""
    resp = await client.get("/api/v1/workspace/context", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "exams" in data
    assert "classes" in data

@pytest.mark.asyncio
async def test_get_exam_dashboard(client, teacher_headers, seed_exam_data):
    """获取考试数据仪表盘"""
    exam_id = seed_exam_data["exam_id"]
    resp = await client.get(f"/api/v1/workspace/exams/{exam_id}/dashboard", headers=teacher_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "score_distribution" in data
    assert "stats" in data  # avg, max, min, median
```

- [ ] **Step 2: 实现 workspace_service**

```python
# src/edu_cloud/services/workspace_service.py
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.exam import Exam, ExamResult
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student

class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_context_tree(self, school_id: str, scope: dict) -> dict:
        """获取左栏上下文数据（按 scope 过滤）"""
        # 查询可见的班级
        q = select(ClassGroup).where(ClassGroup.school_id == school_id)
        if scope.get("class_ids"):
            q = q.where(ClassGroup.id.in_(scope["class_ids"]))
        classes = (await self.db.execute(q)).scalars().all()

        # 查询可见的考试
        q = select(Exam).where(Exam.school_id == school_id).order_by(Exam.created_at.desc()).limit(20)
        exams = (await self.db.execute(q)).scalars().all()

        return {
            "classes": [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes],
            "exams": [{"id": e.id, "name": e.name, "subject_code": e.subject_code, "semester": e.semester} for e in exams],
        }

    async def get_exam_dashboard(self, exam_id: str, school_id: str, scope: dict) -> dict:
        """获取考试仪表盘数据（成绩分布 + 统计），按 scope 过滤"""
        # PR-03: 必须按 school_id + class_ids 过滤，班主任只看本班
        q = select(ExamResult).where(ExamResult.exam_id == exam_id, ExamResult.school_id == school_id)
        if scope.get("class_ids"):
            q = q.join(Student, ExamResult.student_id == Student.id).where(
                Student.class_id.in_(scope["class_ids"])
            )
        results = (await self.db.execute(q)).scalars().all()

        scores = [r.total_score for r in results]
        if not scores:
            return {"stats": {}, "score_distribution": []}

        # 按得分率分段（适配不同满分的考试）
        # 先查询 max_score
        exam = await self.db.get(Exam, exam_id)
        max_s = exam.max_score or 100
        bins = [0, max_s*0.4, max_s*0.6, max_s*0.7, max_s*0.8, max_s*0.9, max_s+0.1]
        labels = ["<40%", "40-59%", "60-69%", "70-79%", "80-89%", "90%+"]
        distribution = []
        for i in range(len(bins) - 1):
            count = len([s for s in scores if bins[i] <= s < bins[i+1]])
            distribution.append({"range": labels[i], "count": count})

        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        median = sorted_scores[n // 2] if n % 2 == 1 else (sorted_scores[n//2 - 1] + sorted_scores[n//2]) / 2

        return {
            "stats": {
                "count": n,
                "avg": round(sum(scores) / n, 1),
                "max": max(scores),
                "min": min(scores),
                "median": median,
            },
            "score_distribution": distribution,
        }
```

- [ ] **Step 3: 实现 workspace API 路由**

```python
# src/edu_cloud/api/workspace.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])

@router.get("/context")
async def get_context(
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WorkspaceService(db)
    role = current["current_role"]
    scope = {
        "class_ids": role.class_ids,
        "grade_ids": role.grade_ids,
    }
    school_id = role.school_id
    return await svc.get_context_tree(school_id, scope)

@router.get("/exams/{exam_id}/dashboard")
async def get_exam_dashboard(
    exam_id: str,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = WorkspaceService(db)
    role = current["current_role"]
    # PR-03: 传入 scope 过滤
    return await svc.get_exam_dashboard(exam_id, role.school_id, {
        "class_ids": role.class_ids,
        "grade_ids": role.grade_ids,
    })
```

- [ ] **Step 4: 运行后端测试**

Run: `python -m pytest tests/test_api/test_workspace.py -v`
Expected: PASS

- [ ] **Step 5: 实现前端 context store**

```javascript
// frontend/src/stores/context.js
import { defineStore } from 'pinia'
import { ref } from 'vue'
import client from '../api/client.js'

export const useContextStore = defineStore('context', () => {
  const classes = ref([])
  const exams = ref([])
  const selectedExamId = ref(null)
  const dashboard = ref(null)
  const loading = ref(false)

  async function loadContext() {
    const { data } = await client.get('/workspace/context')
    classes.value = data.classes
    exams.value = data.exams
  }

  async function selectExam(examId) {
    selectedExamId.value = examId
    loading.value = true
    try {
      const { data } = await client.get(`/workspace/exams/${examId}/dashboard`)
      dashboard.value = data
    } finally {
      loading.value = false
    }
  }

  return { classes, exams, selectedExamId, dashboard, loading, loadContext, selectExam }
})
```

- [ ] **Step 6: 实现左栏 ContextPanel**

```vue
<!-- frontend/src/components/context/ContextPanel.vue -->
<template>
  <div style="padding: 16px">
    <n-h4>考试</n-h4>
    <n-menu
      :options="examOptions"
      :value="contextStore.selectedExamId"
      @update:value="contextStore.selectExam"
    />
    <n-divider />
    <n-h4>班级</n-h4>
    <n-list>
      <n-list-item v-for="cls in contextStore.classes" :key="cls.id">
        {{ cls.name }}
      </n-list-item>
    </n-list>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useContextStore } from '../../stores/context.js'

const contextStore = useContextStore()

const examOptions = computed(() =>
  contextStore.exams.map(e => ({ label: `${e.name} (${e.subject_code})`, key: e.id }))
)

onMounted(() => contextStore.loadContext())
</script>
```

- [ ] **Step 7: 实现中栏成绩分布图**

```vue
<!-- frontend/src/components/workspace/ExamScoreChart.vue -->
<template>
  <v-chart :option="chartOption" autoresize style="height: 300px" />
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({ distribution: { type: Array, default: () => [] } })

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: props.distribution.map(d => d.range) },
  yAxis: { type: 'value', name: '人数' },
  series: [{ type: 'bar', data: props.distribution.map(d => d.count), itemStyle: { color: '#63e2b7' } }]
}))
</script>
```

- [ ] **Step 8: 更新 DataView 组装仪表盘**

```vue
<!-- frontend/src/components/workspace/DataView.vue -->
<template>
  <div>
    <template v-if="contextStore.dashboard">
      <n-grid :cols="4" :x-gap="12" style="margin-bottom: 16px">
        <n-gi><n-statistic label="参加人数" :value="stats.count" /></n-gi>
        <n-gi><n-statistic label="平均分" :value="stats.avg" /></n-gi>
        <n-gi><n-statistic label="最高分" :value="stats.max" /></n-gi>
        <n-gi><n-statistic label="中位数" :value="stats.median" /></n-gi>
      </n-grid>
      <n-card title="成绩分布">
        <ExamScoreChart :distribution="contextStore.dashboard.score_distribution" />
      </n-card>
    </template>
    <n-empty v-else description="请在左栏选择一次考试" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useContextStore } from '../../stores/context.js'
import ExamScoreChart from './ExamScoreChart.vue'

const contextStore = useContextStore()
const stats = computed(() => contextStore.dashboard?.stats || {})
</script>
```

- [ ] **Step 9: 端到端验证**

Run: 后端 + 前端同时启动。先通过 sync API 注入测试数据，再登录工作台查看。
Expected: 左栏显示考试列表 → 点击一次考试 → 中栏显示统计卡片 + 成绩分布柱状图

- [ ] **Step 10: Commit**

```bash
git add src/edu_cloud/api/workspace.py src/edu_cloud/services/workspace_service.py \
        frontend/src/ tests/
git commit -m "feat(P0-6): 工作台数据 API + 左栏选择器 + 中栏成绩分布图"
```

**审查清单:**
- ✓ workspace API 使用 JWT 认证，按 scope 过滤数据
- ✓ 成绩分布分 6 段统计
- ✓ 统计值包含 count/avg/max/min/median
- ✓ 前端左栏选考试 → 中栏自动刷新
- ✓ 无数据时显示空状态
- ✗ 不应暴露其他学校的数据

**测试契约:**
1. 上下文树按 scope 过滤
   - 入口: `GET /api/v1/workspace/context`
   - 反例: 错误实现返回全校数据而非 scope 内数据
   - 边界: 无班级 / 无考试 / scope 为空
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_workspace.py::test_get_context_tree -v`
2. 成绩仪表盘统计正确
   - 入口: `GET /api/v1/workspace/exams/{id}/dashboard`
   - 反例: 错误实现可能计算 median 时对空数组除零
   - 边界: 0 条成绩 / 1 条成绩 / 全部满分
   - 回归: N/A
   - 命令: `python -m pytest tests/test_api/test_workspace.py::test_get_exam_dashboard -v`

---

## Task 7: 后端 CORS + 种子数据

**Files:**
- Modify: `src/edu_cloud/api/app.py` (CORS)
- Modify: `src/edu_cloud/config.py` (CORS origin)
- Create: `scripts/seed_data.py`

- [ ] **Step 1: 添加 CORS 中间件**

```python
# src/edu_cloud/api/app.py 添加
from fastapi.middleware.cors import CORSMiddleware

# 在 create_app() 中添加:
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

```python
# src/edu_cloud/config.py 添加字段
CORS_ORIGINS: list[str] = ["http://localhost:5173"]
```

- [ ] **Step 2: 创建种子数据脚本**

```python
# scripts/seed_data.py
"""
P0 种子数据：创建管理员 + 教师 + 学校 + 班级 + 学生 + 考试 + 成绩
用于演示：班主任登录 → 选考试 → 看成绩分布
"""
import asyncio
import bcrypt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from edu_cloud.config import get_settings
from edu_cloud.models.base import Base
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import RegisteredSchool
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student
from edu_cloud.models.exam import Exam, ExamResult
import random

async def seed():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        # 1. 学校
        school = RegisteredSchool(name="实验中学", code="SYZX", district="城区", api_key_hash="placeholder")
        db.add(school)
        await db.flush()

        # 2. 管理员
        admin = User(username="admin", display_name="平台管理员",
                     hashed_password=bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode())
        db.add(admin)
        await db.flush()
        db.add(UserRole(user_id=admin.id, role="platform_admin", is_primary=True))

        # 3. 班主任
        teacher = User(username="zhanglaoshi", display_name="张老师",
                       hashed_password=bcrypt.hashpw(b"123456", bcrypt.gensalt()).decode())
        db.add(teacher)
        await db.flush()
        db.add(UserRole(user_id=teacher.id, role="homeroom_teacher", school_id=school.id,
                        class_ids=["cls-7-2"], is_primary=True))

        # 4. 班级
        cls = ClassGroup(id="cls-7-2", name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
        db.add(cls)

        # 5. 学生（45 人）
        students = []
        for i in range(1, 46):
            s = Student(name=f"学生{i:02d}", student_number=f"S{i:03d}", school_id=school.id,
                        class_id="cls-7-2", grade="七年级")
            db.add(s)
            students.append(s)
        await db.flush()

        # 6. 考试 + 成绩
        exam = Exam(name="2025-2026 第二学期期中考试", subject_code="SX", subject_name="数学",
                    max_score=150, school_id=school.id, semester="2025-2026-2")
        db.add(exam)
        await db.flush()

        for s in students:
            score = round(random.gauss(105, 20), 1)
            score = max(0, min(150, score))
            db.add(ExamResult(exam_id=exam.id, student_id=s.id, school_id=school.id, total_score=score))

        await db.commit()
        print(f"✅ 种子数据已创建: 1 学校, 2 用户, 1 班级, 45 学生, 1 考试, 45 成绩")

if __name__ == "__main__":
    asyncio.run(seed())
```

- [ ] **Step 3: 运行种子数据**

Run: `cd C:/Users/Administrator/edu-cloud && python scripts/seed_data.py`
Expected: 输出 "✅ 种子数据已创建..."

- [ ] **Step 4: 端到端完整验证（P0 完成标志）**

Run: 启动后端 + 前端
1. 打开 localhost:5173 → 跳转登录页
2. 输入 zhanglaoshi / 123456 → 进入三栏工作台
3. 左栏看到"期中考试 (SX)"
4. 点击 → 中栏显示统计卡片（参加人数 45, 平均分 ~105, 最高分, 中位数）+ 成绩分布柱状图

Expected: P0 完成标志达成

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/app.py src/edu_cloud/config.py scripts/seed_data.py
git commit -m "feat(P0-7): CORS + 种子数据脚本（管理员+教师+45学生+考试成绩）"
```

**审查清单:**
- ✓ CORS 允许 localhost:5173
- ✓ 种子数据包含完整链路（学校→用户→角色→班级→学生→考试→成绩）
- ✓ 成绩按正态分布生成（均值 105，标准差 20）
- ✓ 端到端可跑通 P0 完成标志
- ✗ 种子脚本不应在生产环境运行（仅开发用）

---

## Task 8: Alembic 首个 Migration

**Files:**
- Modify: `alembic/env.py`
- Create: `alembic/versions/001_initial.py`（通过 alembic 生成）

- [ ] **Step 1: 更新 alembic env.py 导入所有模型**

```python
# alembic/env.py — target_metadata 设置
from edu_cloud.models.base import Base
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import RegisteredSchool
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.exam import Exam, ExamResult
from edu_cloud.models.joint_exam import JointExam, JointExamParticipant, JointExamStudentResult
from edu_cloud.models.platform_user import PlatformUser  # 保留兼容

target_metadata = Base.metadata
```

- [ ] **Step 2: 生成 migration**

Run: `cd C:/Users/Administrator/edu-cloud && alembic revision --autogenerate -m "initial: all tables"`
Expected: 在 alembic/versions/ 生成迁移文件

- [ ] **Step 3: 检查生成的迁移文件**

确认包含所有新增表（users, user_roles, students, class_groups, exams, exam_results）和现有表。

- [ ] **Step 4: Commit**

```bash
git add alembic/
git commit -m "feat(P0-8): Alembic 首个 migration — 全部表结构"
```

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 全部 PASS

- [ ] **Step 6: 最终 Commit**

```bash
git commit -m "chore(P0): 全量测试通过，P0 骨架完成"
```

**审查清单:**
- ✓ Migration 覆盖所有表
- ✓ 全量测试 PASS
- ✓ 旧 PlatformUser 表保留（渐进迁移）
