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
- Modify: `tests/test_api/test_auth_v2.py` (扩展现有 RBAC 测试)

**Why:** 顶栏需要显示学校名，但登录只返回 school_id。教师/家长无 VIEW_SCHOOLS 权限，无法通过 /schools API 获取。

**测试契约:** 入口=`POST /auth/login` + `POST /auth/switch-role` | 反例=context 字段缺失/type 错误/name 为空 | 边界=①platform_admin 无 school_id ②多角色切换后 context 更新 ③school 不存在返回"未知学校" | 回归=现有 9 个 auth_v2 测试全绿 | 命令=`pytest tests/test_api/test_auth_v2.py -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_auth_v2.py — 在现有测试末尾追加
async def test_login_returns_context(client, seed_teacher):
    """登录响应每个 role 包含 context 对象（type + name）。
    seed_teacher 已创建 school + homeroom_teacher role。"""
    resp = await client.post("/api/v1/auth/login", json={"username": "teacher1", "password": "123456"})
    assert resp.status_code == 200
    data = resp.json()
    role = data["roles"][0]
    assert "context" in role
    assert role["context"]["type"] == "school"
    assert role["context"]["name"] == "测试校"  # seed_teacher fixture 的学校名


async def test_login_platform_admin_context(client, admin_user):
    """platform_admin 的 context.type 应为 platform。"""
    resp = await client.post("/api/v1/auth/login", json={"username": "admin_test", "password": "test123"})
    data = resp.json()
    role = data["roles"][0]
    assert role["context"]["type"] == "platform"
    assert role["context"]["name"] == "全平台"


async def test_switch_role_returns_context(client, db):
    """switch-role 响应也包含 context 对象。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="切换测试校", code="SW01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="sw_user", display_name="切换用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    role1 = UserRole(user_id=user.id, role="platform_admin", is_primary=True)
    role2 = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=False)
    db.add_all([role1, role2])
    await db.commit()
    await db.refresh(role2)

    login = await client.post("/api/v1/auth/login", json={"username": "sw_user", "password": "pass123"})
    token = login.json()["access_token"]
    resp = await client.post("/api/v1/auth/switch-role",
        json={"role_id": role2.id}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["active_role"]["context"]["type"] == "school"
    assert resp.json()["active_role"]["context"]["name"] == "切换测试校"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_auth_v2.py -v -k "context"`
Expected: FAIL — `"context" not in role`

- [ ] **Step 3: 实现 — 修改 auth.py login + switch-role 端点**

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

修改 login 响应的 roles 序列化，每个 role 加 `context` 字段。switch-role 响应的 `active_role` 同样加 `context` 字段。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_auth_v2.py -v -k "context"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/auth.py tests/test_api/test_auth_v2.py
git commit -m "feat(api): login/switch-role 返回 context 对象（type+id+name）"
```

---

### Task 2: 后端 — Dashboard Summary API

**Files:**
- Create: `src/edu_cloud/api/dashboard.py`
- Modify: `src/edu_cloud/api/app.py` (注册路由)
- Create: `tests/test_api/test_dashboard.py`

**Why:** KPI 卡片需要聚合统计（学生数/班级数/考试数/待批改数）。

**测试契约:** 入口=`GET /api/v1/dashboard/summary` | 反例=①不按 school_id 过滤→全库数据 ②不按 class_ids 过滤→全校数据 ③始终返回 0→精确计数断言失败 | 边界=①platform_admin 无 school_id→返回零值 ②班级有学生/无学生 ③deferred 字段返回 null | 回归=现有 770 tests | 命令=`pytest tests/test_api/test_dashboard.py -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_dashboard.py
import pytest

@pytest.fixture
async def seed_two_classes(db):
    """Seed 两个班级+不同数量学生，用于验证 scope 过滤。
    class_a: 10 学生 | class_b: 5 学生 → 全校 15。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.class_group import ClassGroup
    from edu_cloud.models.student import Student
    from edu_cloud.models.exam import Exam
    school = School(name="Dashboard测试校", code="DASH01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    cls_a = ClassGroup(name="七年级1班", grade="七年级", grade_number=7, school_id=school.id)
    cls_b = ClassGroup(name="七年级2班", grade="七年级", grade_number=7, school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.flush()
    for i in range(10):
        db.add(Student(name=f"A生{i}", student_number=f"A{i:03d}", school_id=school.id, class_id=cls_a.id, grade="七年级"))
    for i in range(5):
        db.add(Student(name=f"B生{i}", student_number=f"B{i:03d}", school_id=school.id, class_id=cls_b.id, grade="七年级"))
    exam = Exam(name="月考", subject_code="SX", subject_name="数学", max_score=100, school_id=school.id, semester="2025-2026-2")
    db.add(exam)
    await db.commit()
    return {"school_id": school.id, "class_a_id": cls_a.id, "class_b_id": cls_b.id}


async def test_dashboard_summary_principal(client, db, seed_two_classes):
    """校长看到全校聚合：15 学生、2 班级、1 考试。
    反例：如果实现忽略 school_id 过滤 → 可能返回其他 fixture 的数据。
    反例：如果始终返回 0 → total_students != 15。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_id = seed_two_classes["school_id"]
    user = User(username="dash_principal", display_name="仪表盘校长")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_id, is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "dash_principal", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    # 精确计数（非弱断言）
    assert data["total_students"] == 15  # 10 + 5
    assert data["total_classes"] == 2
    assert data["total_exams"] == 1
    # 暂缓字段返回 null
    assert data["total_staff"] is None
    assert data["pending_subjects"] is None
    assert "pending_grading" in data


async def test_dashboard_summary_grade_leader_scoped(client, db, seed_two_classes):
    """年级组长只看 class_a(10 学生)，不看 class_b(5 学生)。
    反例：如果不按 class_ids 过滤 → 返回 15 而非 10。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_id = seed_two_classes["school_id"]
    class_a_id = seed_two_classes["class_a_id"]
    user = User(username="dash_leader", display_name="仪表盘组长")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="grade_leader", school_id=school_id,
                    class_ids=[class_a_id], is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "dash_leader", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 10  # 只有 class_a
    assert data["total_classes"] == 1    # 只有 class_a


async def test_dashboard_summary_homeroom_teacher_scoped(client, db, seed_two_classes):
    """班主任只看 class_b(5 学生)。
    反例：如果不按 class_ids 过滤 → 返回 15 而非 5。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_id = seed_two_classes["school_id"]
    class_b_id = seed_two_classes["class_b_id"]
    user = User(username="dash_teacher", display_name="仪表盘班主任")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher", school_id=school_id,
                    class_ids=[class_b_id], is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "dash_teacher", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/dashboard/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_students"] == 5   # 只有 class_b
    assert data["total_classes"] == 1    # 只有 class_b
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
        "total_staff": None,        # 暂缓：需 staff 表，前端显示 "--"
        "pending_subjects": None,    # 暂缓：需阅卷状态聚合
        "pending_grading": 0,        # placeholder
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

### Task 2b: 后端 — Notifications List API

**Files:**
- Create: `src/edu_cloud/api/notifications_api.py`
- Modify: `src/edu_cloud/api/app.py` (注册路由)
- Create: `tests/test_api/test_notifications_api.py`

**Why:** 通知铃 badge、ActivityFeed、校长 Dashboard "待审批/本周通知" KPI 均需要通知列表 API。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_api/test_notifications_api.py
import pytest
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=8))

@pytest.fixture
async def seed_notifications(db):
    """Seed 3 条通知：2 条 pending(本校)、1 条 sent(本校)、1 条 pending(他校)。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.notification import Notification
    school_a = School(name="通知校A", code="NOTIA", district="测试区", api_key_hash="x")
    school_b = School(name="通知校B", code="NOTIB", district="测试区", api_key_hash="x")
    db.add_all([school_a, school_b])
    await db.flush()
    now = datetime.now(TZ)
    n1 = Notification(school_id=school_a.id, status="pending", channel="system",
                      created_at=now - timedelta(hours=1))
    n2 = Notification(school_id=school_a.id, status="pending", channel="approval",
                      created_at=now - timedelta(days=10))
    n3 = Notification(school_id=school_a.id, status="sent", channel="system",
                      created_at=now - timedelta(hours=2))
    n4 = Notification(school_id=school_b.id, status="pending", channel="system",
                      created_at=now)
    db.add_all([n1, n2, n3, n4])
    await db.commit()
    return {"school_a_id": school_a.id, "school_b_id": school_b.id,
            "pending_a": [n1.id, n2.id], "sent_a": [n3.id], "pending_b": [n4.id]}


async def test_notifications_list_school_scope(client, db, seed_notifications):
    """教师只看到本校通知（3 条），不看他校（1 条）。
    反例：不按 school_id 过滤 → 返回 4 条。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    school_a_id = seed_notifications["school_a_id"]
    user = User(username="noti_teacher", display_name="通知教师")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher", school_id=school_a_id, is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "noti_teacher", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/notifications", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3  # 只有 school_a 的 3 条
    # 响应包含丰富字段
    assert "title" in data[0]
    assert "kind" in data[0]
    assert "unread" in data[0]


async def test_notifications_filter_status_pending(client, db, seed_notifications):
    """status=pending 只返回 pending 通知。
    反例：忽略 status 过滤 → 返回 3 条而非 2 条。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    user = User(username="noti_filter", display_name="过滤测试")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher",
                    school_id=seed_notifications["school_a_id"], is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "noti_filter", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/notifications?status=pending", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # n1 + n2 (本校 pending)
    assert all(n["unread"] for n in resp.json())


async def test_notifications_filter_since_week(client, db, seed_notifications):
    """since=week 排除 10 天前的通知。
    反例：忽略 since → 返回 3 条而非 2 条。"""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    user = User(username="noti_since", display_name="时间过滤测试")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="homeroom_teacher",
                    school_id=seed_notifications["school_a_id"], is_primary=True))
    await db.commit()
    login = await client.post("/api/v1/auth/login", json={"username": "noti_since", "password": "123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = await client.get("/api/v1/notifications?since=week", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2  # n1 + n3 (7 天内), n2 excluded (10 天前)


async def test_notifications_unauth(client):
    """未认证 → 401。"""
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_notifications_api.py -v`
Expected: FAIL — 404 (路由不存在)

- [ ] **Step 3: 实现**

```python
# src/edu_cloud/api/notifications_api.py
"""Notifications List API — 按角色 scope 过滤通知。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.models.notification import Notification

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

TZ = timezone(timedelta(hours=8))

@router.get("")
async def list_notifications(
    status: str | None = Query(None),
    since: str | None = Query(None),
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = current["current_role"]
    school_id = role.school_id

    q = select(Notification).order_by(Notification.created_at.desc())
    if school_id:
        q = q.where(Notification.school_id == school_id)
    if status:
        q = q.where(Notification.status == status)
    if since == "week":
        cutoff = datetime.now(TZ) - timedelta(days=7)
        q = q.where(Notification.created_at >= cutoff)

    result = await db.execute(q.limit(50))
    rows = result.scalars().all()
    return [
        {
            "id": n.id,
            "status": n.status,
            "channel": n.channel,
            "created_at": str(n.created_at),
            # 丰富字段（R2-02 修复）：前端 NotificationBell/ActivityFeed 需要
            "title": getattr(n, 'title', None) or f"通知 {n.id[:8]}",
            "summary": getattr(n, 'summary', None),
            "kind": n.channel or "system",   # system/approval/message
            "unread": n.status == "pending",
        }
        for n in rows
    ]
```

在 `app.py` 注册路由：`from edu_cloud.api.notifications_api import router as notifications_router`

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_notifications_api.py -v`
Expected: PASS

- [ ] **Step 5: 前端 API 封装**

在 `frontend/src/api/` 添加 `notifications.js`：

```javascript
import client from './client.js'
export const getNotifications = (params = {}) => client.get('/notifications', { params })
```

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/api/notifications_api.py src/edu_cloud/api/app.py tests/test_api/test_notifications_api.py frontend/src/api/notifications.js
git commit -m "feat(api): GET /notifications — 通知列表（status/since 过滤）"
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
- Create: `frontend/src/config/permissions.js`
- Create: `frontend/src/config/sidebarConfig.js`
- Create: `frontend/src/config/dashboardConfig.js`
- Create: `frontend/src/__tests__/config.test.js`

**Why:** 角色常量、侧栏导航、Dashboard widget 配置是整个角色感知系统的核心数据。

- [ ] **Step 1: 写测试**

```javascript
// frontend/src/__tests__/config.test.js
import { describe, it, expect } from 'vitest'
import { CANONICAL_ROLES, ROLE_LABELS, normalizeRole, SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { hasPermission, ROLE_PERMISSIONS } from '../config/permissions.js'
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

describe('permissions config', () => {
  it('hasPermission checks role→permission mapping', () => {
    expect(hasPermission('platform_admin', 'manage_schools')).toBe(true)
    expect(hasPermission('parent', 'manage_schools')).toBe(false)
    expect(hasPermission('subject_teacher', 'use_ai_chat')).toBe(true)
    expect(hasPermission('parent', 'use_ai_chat')).toBe(false)
  })
  it('uses lowercase values matching backend enum', () => {
    for (const perms of Object.values(ROLE_PERMISSIONS)) {
      for (const p of perms) {
        expect(p).toBe(p.toLowerCase())
      }
    }
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

- [ ] **Step 4: 实现 permissions.js**

```javascript
// frontend/src/config/permissions.js
// 镜像后端 core/permissions.py ROLE_PERMISSIONS，值使用小写（与后端 enum value 一致）
export const ROLE_PERMISSIONS = {
  platform_admin: ['manage_schools', 'view_schools', 'create_joint_exam', 'manage_joint_exam',
    'view_joint_exam', 'view_cross_school_analytics', 'manage_question_bank', 'view_question_bank',
    'manage_users', 'manage_platform', 'view_students', 'view_exams', 'view_scores',
    'generate_report', 'generate_notification', 'approve_notification', 'send_notification',
    'use_ai_chat', 'write_paper'],
  district_admin: ['manage_schools', 'view_schools', 'create_joint_exam', 'manage_joint_exam',
    'view_joint_exam', 'view_cross_school_analytics', 'view_question_bank', 'manage_users',
    'view_students', 'view_exams', 'view_scores', 'generate_report', 'approve_notification',
    'send_notification', 'generate_notification', 'use_ai_chat'],
  principal: ['view_schools', 'view_joint_exam', 'view_cross_school_analytics', 'view_question_bank',
    'view_students', 'view_exams', 'view_scores', 'generate_report', 'approve_notification',
    'send_notification', 'generate_notification', 'use_ai_chat'],
  academic_director: ['view_schools', 'create_joint_exam', 'manage_joint_exam', 'view_joint_exam',
    'view_question_bank', 'view_students', 'view_exams', 'view_scores', 'generate_report',
    'generate_notification', 'send_notification', 'use_ai_chat'],
  grade_leader: ['view_students', 'view_exams', 'view_scores', 'view_joint_exam',
    'generate_report', 'generate_notification', 'use_ai_chat'],
  homeroom_teacher: ['view_students', 'view_exams', 'view_scores', 'generate_report',
    'generate_notification', 'send_notification', 'use_ai_chat'],
  subject_teacher: ['view_students', 'view_exams', 'view_scores', 'view_question_bank',
    'use_ai_chat', 'write_paper', 'generate_report'],
  parent: ['view_scores'],
}

export function hasPermission(role, permission) {
  const perms = ROLE_PERMISSIONS[role]
  return perms ? perms.includes(permission) : false
}
```

- [ ] **Step 5: 实现 sidebarConfig.js**

按 spec §3.2 定义每个角色的侧栏导航项。每项包含 `{ icon, label, route, badge? }`。

- [ ] **Step 6: 实现 dashboardConfig.js**

按 spec §4 定义每个角色的 KPI 列表和 widget 列表。每个 widget 包含 `{ type, id, title, icon, route?, planned? }`。

- [ ] **Step 7: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/config.test.js`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/config/ frontend/src/__tests__/config.test.js
git commit -m "feat: 角色配置文件 — roles/permissions/sidebar/dashboard JSON 驱动"
```

---

## Batch 2: 壳层组件（AppShell + 导航）

### Task 5: Auth Store 增强 — role normalization + context

**Files:**
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/__tests__/router.test.js` (验证 normalization)
- Create: `frontend/src/__tests__/auth-store.test.js` (持久化 + hydrate 测试)

**Why:** auth store 需要 normalize legacy 角色名，存储 context 对象，提供 permissions 计算属性。F-03 要求页面刷新后恢复 auth 状态。

- [ ] **Step 1: 修改 auth store**

- login 时 normalize 每个 role 的 role name（使用 `normalizeRole`）
- 存储 context 对象（来自 login 响应）
- 添加 `currentContext` computed（当前角色的 context）
- 修改 `isAdmin` 使用 `normalizeRole`
- 添加 `hasPermission(perm)` 方法（使用 `config/permissions.js`，本地检查不调 API）
- **F-03 修复: Auth Bootstrap** — 持久化 `user`/`roles`/`currentRoleIndex` 到 localStorage：
  - login 成功后：`localStorage.setItem('auth_state', JSON.stringify({ user, roles, currentRoleIndex }))`
  - store 初始化时：从 localStorage 恢复（如果 token 存在）
  - logout 时：清除 `auth_state`
  - switchRole 后：更新 `auth_state`

- [ ] **Step 2: 写 auth store 持久化测试（R2-05 修复）**

```javascript
// frontend/src/__tests__/auth-store.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth.js'

describe('auth store persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('hydrates state from localStorage on init', () => {
    const saved = { user: { id: '1', display_name: 'Test' }, roles: [{ id: 'r1', role: 'principal' }], currentRoleIndex: 0 }
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    expect(store.user).toEqual(saved.user)
    expect(store.roles).toHaveLength(1)
  })

  it('ignores corrupt auth_state gracefully', () => {
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', '{bad json')
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.roles).toEqual([])
  })

  it('clears auth_state on logout', () => {
    localStorage.setItem('auth_state', '{}')
    const store = useAuthStore()
    store.logout()
    expect(localStorage.getItem('auth_state')).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })
})
```

- [ ] **Step 3: 验证前端测试通过**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/auth.js frontend/src/__tests__/auth-store.test.js
git commit -m "feat(auth): role normalization + context 存储 + hasPermission + localStorage 持久化"
```

---

### Task 6: AppShell + AppHeader

**Files:**
- Create: `frontend/src/layouts/AppShell.vue`
- Create: `frontend/src/components/shell/AppHeader.vue`
- Create: `frontend/src/components/shell/SchoolContext.vue`
- Create: `frontend/src/components/shell/AppSidebar.vue` (占位)
- Create: `frontend/src/components/ai/AiFloatingButton.vue` (占位)

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

- [ ] **Step 3b: 创建占位组件（F-05 修复）**

AppShell 模板引用了 AppSidebar 和 AiFloatingButton，但这些组件在后续 Task 才实现。此步创建空占位避免构建报错：

```vue
<!-- frontend/src/components/shell/AppSidebar.vue -->
<template><aside class="app-sidebar"><!-- Task 7 实现 --></aside></template>
```

```vue
<!-- frontend/src/components/ai/AiFloatingButton.vue -->
<template><div><!-- Task 12 实现 --></div></template>
```

- [ ] **Step 4: 验证构建**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vite build`
Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/layouts/AppShell.vue frontend/src/components/shell/ frontend/src/components/ai/AiFloatingButton.vue
git commit -m "feat: AppShell 壳层 + AppHeader 顶栏 + SchoolContext + 占位组件"
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

NPopover 触发。badge 红点显示 `unread` 计数（调用 `GET /api/v1/notifications?status=pending` 取 `length`）。下拉面板按 `kind` 分 tab（system/approval/message），渲染 `title` + `summary` + `created_at`。无通知时显示"暂无通知"。

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
- 每个路由补 `meta.roles` 或 `meta.permissions`（permission 值使用小写，与后端 enum value 一致，如 `'use_ai_chat'` 而非 `'USE_AI_CHAT'`）
- authGuard 增强：检查 roles/permissions（使用 `config/permissions.js` 的 `hasPermission`）
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
仅 `hasPermission('use_ai_chat')` 时渲染。
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

**回滚策略:** `git revert <commit>` 即可恢复所有删除的文件（git 历史完整保留）。

- [ ] **Step 1: 删除 AppNavbar.vue**

确认没有其他文件 import 它。

- [ ] **Step 2: 删除 DashboardLayout.vue**

确认没有其他文件引用。

- [ ] **Step 3: 重命名 WorkbenchPage → AnalysisPage**

更新 router import。

- [ ] **Step 3b: 移除 AnalysisPage 中的身份控件（F-08 修复）**

WorkbenchPage 原有 header slot 中包含用户身份控件（角色标签/学校名等），这些已迁移到 AppShell 的 AppHeader。重命名后须移除 AnalysisPage 中的重复身份控件，避免双层头部。具体：
- 检查 WorkbenchLayout.vue 的 header slot 是否有身份/角色显示
- 如有，移除 AnalysisPage 传给 header slot 的身份控件
- 保留功能性控件（搜索、上下文选择器等）

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
| 1 | T1, T2, T2b, T3, T4 | 后端 API（login context + dashboard + notifications）+ CSS + config（含 permissions.js）全部有测试 | codex-review (code) |
| 2 | T5-T9 | 壳层完整（含 auth 持久化 + 占位组件），可视觉检查 | codex-review (code) |
| 3 | T10-T11 | Dashboard 功能完整 | codex-review (code) |
| 4 | T12-T14 | AI 浮窗 + 清理（含 AnalysisPage 去重复头部）+ 最终验证 | codex-review (code) + integration |
