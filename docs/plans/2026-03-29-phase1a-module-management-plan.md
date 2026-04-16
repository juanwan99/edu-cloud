# Phase 1a: 模块管理核心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud 建立学校配置体系和模块管理机制，使管理员能启用/禁用功能模块，前端 sidebar 和后端 API 同步响应。

**Architecture:** 新增 school_settings (KV 配置) 和 school_modules (模块开关) 两张表。后端通过 FastAPI 中间件在请求级别拦截 disabled 模块的 API。前端 sidebar 读取 school_modules 动态渲染导航。管理员通过新增的"学校配置"页面管理。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL + Vue 3 + Naive UI + Pinia

**Design doc:** `docs/plans/2026-03-29-business-logic-backfill-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/edu_cloud/models/school_settings.py` | SchoolSetting + SchoolModule ORM models |
| Create | `src/edu_cloud/services/school_settings_service.py` | Settings + Modules CRUD service |
| Create | `src/edu_cloud/modules/school/settings_router.py` | Settings + Modules API endpoints (self-contained prefix, registered in app.py) |
| Create | `src/edu_cloud/api/module_middleware.py` | Module check middleware |
| Modify | `src/edu_cloud/api/app.py` | Register settings_router + middleware + import school_settings model |
| Modify | `alembic/env.py` | Import `edu_cloud.models.school_settings` for autogenerate |
| Modify | `tests/test_alembic_migration.py` | Import `edu_cloud.models.school_settings` for table comparison |
| Modify | `tests/conftest.py` | Import `edu_cloud.models.school_settings` for create_all |
| Create | `alembic/versions/xxxx_add_school_settings_modules.py` | DB migration |
| Create | `tests/test_api/test_school_settings.py` | API + middleware tests |
| Create | `tests/test_services/test_school_settings_service.py` | Service tests |
| Create | `frontend/src/api/schoolSettings.js` | API client |
| Modify | `frontend/src/stores/auth.js` | Add `enabledModules` + `modulesLoaded` refs and `loadModules` function (setup store pattern) |
| Modify | `frontend/src/components/shell/AppSidebar.vue` | Filter nav by enabled modules |
| Modify | `frontend/src/config/sidebarConfig.js` | Add moduleCode field to items (extend `{ icon, label, route }` to `{ icon, label, route, moduleCode }`) |
| Create | `frontend/src/pages/SchoolSettingsPage.vue` | Management page |
| Modify | `frontend/src/router/index.js` | Add school-settings route for school-scoped admin roles (`principal` / `academic_director`) |
| Create | `frontend/src/__tests__/AppSidebar.test.js` | Vitest real-component sidebar module filtering test |

> **Note (F-08 fix):** settings_router registers directly in app.py with its own full prefix `/api/v1/schools/{school_id}`. It does NOT register through `modules/school/router.py` (which has prefix `/api/v1/schools`). No modification to school/router.py is needed.

---

### Task 1: Database Models

**Files:**
- Create: `src/edu_cloud/models/school_settings.py`
- Test: `tests/test_services/test_school_settings_service.py`

- [ ] **Step 1: Write failing tests for SchoolSetting model**

```python
# tests/test_services/test_school_settings_service.py
import pytest
from edu_cloud.models.school_settings import SchoolSetting, SchoolModule

@pytest.mark.asyncio
async def test_school_setting_model(db, seed_school):
    school, _ = seed_school
    setting = SchoolSetting(
        school_id=school.id,
        category="feature",
        key="ai_enabled",
        value='true',
    )
    db.add(setting)
    await db.commit()
    await db.refresh(setting)
    assert setting.id is not None
    assert setting.school_id == school.id
    assert setting.key == "ai_enabled"
    assert setting.value == "true"
    assert setting.category == "feature"

@pytest.mark.asyncio
async def test_school_module_model(db, seed_school):
    school, _ = seed_school
    module = SchoolModule(
        school_id=school.id,
        module_code="homework",
        enabled=True,
        config='{}',
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)
    assert module.id is not None
    assert module.module_code == "homework"
    assert module.enabled is True

@pytest.mark.asyncio
async def test_school_module_unique_constraint(db, seed_school):
    from sqlalchemy.exc import IntegrityError
    school, _ = seed_school
    m1 = SchoolModule(school_id=school.id, module_code="homework", enabled=True)
    m2 = SchoolModule(school_id=school.id, module_code="homework", enabled=False)
    db.add(m1)
    await db.flush()
    db.add(m2)
    with pytest.raises(IntegrityError):
        await db.flush()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.models.school_settings'`

- [ ] **Step 3: Implement models**

```python
# src/edu_cloud/models/school_settings.py
from sqlalchemy import String, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class SchoolSetting(Base, IdMixin, TimestampMixin):
    """School-level key-value configuration."""
    __tablename__ = "school_settings"
    __table_args__ = (
        UniqueConstraint("school_id", "key", name="uq_school_settings_school_key"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    category: Mapped[str] = mapped_column(String(50))
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[str | None] = mapped_column(Text, default=None)


# Default module codes and their display names
MODULE_CODES = {
    "exam": "考试管理",
    "grading": "阅卷系统",
    "homework": "作业管理",
    "study_analytics": "学情分析",
    "research": "教研题库",
    "teaching": "教学管理",
    "calendar": "校历日程",
    "studio": "文档中心",
}

# Modules enabled by default for new schools
DEFAULT_ENABLED = {"exam", "grading", "calendar", "studio"}


class SchoolModule(Base, IdMixin, TimestampMixin):
    """Module enable/disable per school."""
    __tablename__ = "school_modules"
    __table_args__ = (
        UniqueConstraint("school_id", "module_code", name="uq_school_modules_school_code"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    module_code: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[str | None] = mapped_column(Text, default=None)
```

- [ ] **Step 4: Update conftest.py to import the new model**

In `tests/conftest.py`, add the import alongside existing model imports (after line 26, alongside other `import edu_cloud.modules.*.models` lines):

```python
import edu_cloud.models.school_settings  # noqa: F401
```

This ensures `Base.metadata.create_all` discovers the new tables in test fixtures.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/models/school_settings.py tests/test_services/test_school_settings_service.py tests/conftest.py
git commit -m "feat: add SchoolSetting + SchoolModule models"
```

**审查清单:**
- [x] UniqueConstraint 防止同 school 同 key/module_code 重复
- [x] MODULE_CODES 常量集中定义，不散落各处
- [x] ForeignKey 关联 schools.id
- [x] IdMixin + TimestampMixin 一致
- [x] conftest.py 导入新模型确保 create_all 能发现表

**边界条件:**
- 同一 school_id + key 重复插入 → IntegrityError（已测试）
- value 为 None → 允许（nullable）
- module_code 不在 MODULE_CODES 中 → 模型层不阻拦，service 层校验

---

### Task 2: Settings + Modules Service

**Files:**
- Create: `src/edu_cloud/services/school_settings_service.py`
- Test: `tests/test_services/test_school_settings_service.py` (追加)

- [ ] **Step 1: Write failing service tests**

```python
# tests/test_services/test_school_settings_service.py (追加以下测试)
from edu_cloud.services.school_settings_service import (
    get_settings, upsert_setting, get_enabled_modules,
    set_module_enabled, init_school_modules,
)

@pytest.mark.asyncio
async def test_upsert_setting_create(db, seed_school):
    school, _ = seed_school
    result = await upsert_setting(db, school_id=school.id, category="feature", key="ai", value="true")
    assert result.key == "ai"
    assert result.value == "true"

@pytest.mark.asyncio
async def test_upsert_setting_update(db, seed_school):
    school, _ = seed_school
    await upsert_setting(db, school_id=school.id, category="feature", key="ai", value="true")
    result = await upsert_setting(db, school_id=school.id, category="feature", key="ai", value="false")
    assert result.value == "false"

@pytest.mark.asyncio
async def test_get_settings(db, seed_school):
    school, _ = seed_school
    await upsert_setting(db, school_id=school.id, category="feature", key="a", value="1")
    await upsert_setting(db, school_id=school.id, category="exam", key="b", value="2")
    all_settings = await get_settings(db, school_id=school.id)
    assert len(all_settings) == 2
    feature_only = await get_settings(db, school_id=school.id, category="feature")
    assert len(feature_only) == 1

@pytest.mark.asyncio
async def test_init_school_modules(db, seed_school):
    school, _ = seed_school
    await init_school_modules(db, school_id=school.id)
    enabled = await get_enabled_modules(db, school_id=school.id)
    from edu_cloud.models.school_settings import DEFAULT_ENABLED
    assert enabled == DEFAULT_ENABLED

@pytest.mark.asyncio
async def test_set_module_enabled(db, seed_school):
    school, _ = seed_school
    await init_school_modules(db, school_id=school.id)
    await set_module_enabled(db, school_id=school.id, module_code="homework", enabled=True)
    enabled = await get_enabled_modules(db, school_id=school.id)
    assert "homework" in enabled

@pytest.mark.asyncio
async def test_set_module_invalid_code(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的模块代码"):
        await set_module_enabled(db, school_id=school.id, module_code="nonexistent", enabled=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py::test_upsert_setting_create -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement service**

```python
# src/edu_cloud/services/school_settings_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school_settings import (
    SchoolSetting, SchoolModule, MODULE_CODES, DEFAULT_ENABLED,
)
from edu_cloud.services.exceptions import ValidationError


async def get_settings(
    db: AsyncSession, *, school_id: str, category: str | None = None,
) -> list[SchoolSetting]:
    stmt = select(SchoolSetting).where(SchoolSetting.school_id == school_id)
    if category:
        stmt = stmt.where(SchoolSetting.category == category)
    result = await db.execute(stmt.order_by(SchoolSetting.category, SchoolSetting.key))
    return list(result.scalars().all())


async def upsert_setting(
    db: AsyncSession, *, school_id: str, category: str, key: str, value: str | None,
) -> SchoolSetting:
    stmt = select(SchoolSetting).where(
        SchoolSetting.school_id == school_id, SchoolSetting.key == key,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        existing.value = value
        existing.category = category
    else:
        existing = SchoolSetting(school_id=school_id, category=category, key=key, value=value)
        db.add(existing)
    await db.commit()
    await db.refresh(existing)
    return existing


async def get_enabled_modules(db: AsyncSession, *, school_id: str) -> set[str]:
    stmt = select(SchoolModule.module_code).where(
        SchoolModule.school_id == school_id, SchoolModule.enabled.is_(True),
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


async def init_school_modules(db: AsyncSession, *, school_id: str) -> None:
    for code in MODULE_CODES:
        existing = (await db.execute(
            select(SchoolModule).where(
                SchoolModule.school_id == school_id, SchoolModule.module_code == code,
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(SchoolModule(
                school_id=school_id,
                module_code=code,
                enabled=(code in DEFAULT_ENABLED),
            ))
    await db.commit()


async def set_module_enabled(
    db: AsyncSession, *, school_id: str, module_code: str, enabled: bool,
) -> SchoolModule:
    if module_code not in MODULE_CODES:
        raise ValidationError(f"无效的模块代码: {module_code}")
    stmt = select(SchoolModule).where(
        SchoolModule.school_id == school_id, SchoolModule.module_code == module_code,
    )
    module = (await db.execute(stmt)).scalar_one_or_none()
    if not module:
        module = SchoolModule(school_id=school_id, module_code=module_code, enabled=enabled)
        db.add(module)
    else:
        module.enabled = enabled
    await db.commit()
    await db.refresh(module)
    return module


async def get_all_modules(db: AsyncSession, *, school_id: str) -> list[dict]:
    stmt = select(SchoolModule).where(SchoolModule.school_id == school_id)
    result = await db.execute(stmt)
    existing = {m.module_code: m for m in result.scalars().all()}
    return [
        {
            "code": code,
            "name": name,
            "enabled": existing[code].enabled if code in existing else (code in DEFAULT_ENABLED),
            "config": existing[code].config if code in existing else None,
        }
        for code, name in MODULE_CODES.items()
    ]
```

- [ ] **Step 4: Run all service tests**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/school_settings_service.py tests/test_services/test_school_settings_service.py
git commit -m "feat: add school settings + modules service with tests"
```

**测试契约:**
1. upsert 幂等性
   - 入口: `upsert_setting(db, school_id=X, key="ai", value="true")` 调用两次
   - 反例: 错误实现会创建两行而非更新 → 第二次 get_settings 返回 2 条
   - 边界: value=None / key 含特殊字符 / 超长 value
   - 回归: N/A
   - 命令: `pytest tests/test_services/test_school_settings_service.py::test_upsert_setting_update -v`
2. 无效 module_code 拒绝
   - 入口: `set_module_enabled(db, module_code="nonexistent", ...)`
   - 反例: 错误实现会静默创建非法模块 → get_enabled_modules 返回脏数据
   - 边界: 空字符串 / None / 已存在的 code
   - 回归: N/A
   - 命令: `pytest tests/test_services/test_school_settings_service.py::test_set_module_invalid_code -v`

---

### Task 3: Settings + Modules API

**Files:**
- Create: `src/edu_cloud/modules/school/settings_router.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_api/test_school_settings.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_api/test_school_settings.py
import pytest

@pytest.mark.asyncio
async def test_get_settings(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/settings", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

@pytest.mark.asyncio
async def test_upsert_setting(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"category": "feature", "key": "ai_enabled", "value": "true"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["key"] == "ai_enabled"

@pytest.mark.asyncio
async def test_get_modules(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    assert resp.status_code == 200
    modules = resp.json()
    assert len(modules) == 8  # All MODULE_CODES
    codes = {m["code"] for m in modules}
    assert "exam" in codes
    assert "homework" in codes

@pytest.mark.asyncio
async def test_toggle_module(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/modules/homework",
        json={"enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is True

@pytest.mark.asyncio
async def test_toggle_invalid_module(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/modules/nonexistent",
        json={"enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_settings_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/settings")
    assert resp.status_code in (401, 403)

@pytest.mark.asyncio
async def test_get_enabled_modules_endpoint(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/modules/enabled", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert "exam" in data  # Default enabled

@pytest.mark.asyncio
async def test_principal_can_access_school_settings(client, db):
    """principal has MANAGE_SCHOOL_SETTINGS and can read school settings."""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="校长配置测试校", code="PRNSET01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="principal_settings", display_name="校长配置用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "principal_settings", "password": "pass123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school.id}/settings", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_academic_director_can_access_school_modules(client, db):
    """academic_director has MANAGE_SCHOOL_SETTINGS and can read school modules."""
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="教务配置测试校", code="ACDSET01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="director_settings", display_name="教务配置用户")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "director_settings", "password": "pass123"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school.id}/modules", headers=headers)
    assert resp.status_code == 200

# ── Multi-school isolation (F-07 fix) ──

@pytest.mark.asyncio
async def test_modules_multi_school_isolation(client, admin_headers, db):
    """Two schools have independent module states."""
    from edu_cloud.models.school import School
    import bcrypt

    # Create two schools
    for code in ("ISOLATE_A", "ISOLATE_B"):
        hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
        school = School(name=f"School {code}", code=code, api_key_hash=hashed, district="test")
        db.add(school)
    await db.commit()

    from sqlalchemy import select
    schools = (await db.execute(
        select(School).where(School.code.in_(["ISOLATE_A", "ISOLATE_B"]))
    )).scalars().all()
    school_a, school_b = schools[0], schools[1]

    # Init modules for both
    await client.get(f"/api/v1/schools/{school_a.id}/modules", headers=admin_headers)
    await client.get(f"/api/v1/schools/{school_b.id}/modules", headers=admin_headers)

    # Enable homework for school A, disable for school B
    await client.patch(
        f"/api/v1/schools/{school_a.id}/modules/homework",
        json={"enabled": True}, headers=admin_headers,
    )
    await client.patch(
        f"/api/v1/schools/{school_b.id}/modules/homework",
        json={"enabled": False}, headers=admin_headers,
    )

    # Verify isolation
    resp_a = await client.get(f"/api/v1/schools/{school_a.id}/modules/enabled", headers=admin_headers)
    resp_b = await client.get(f"/api/v1/schools/{school_b.id}/modules/enabled", headers=admin_headers)
    assert "homework" in resp_a.json()
    assert "homework" not in resp_b.json()

# ── Error cases (F-07 fix) ──

@pytest.mark.asyncio
async def test_upsert_setting_missing_key(client, admin_headers, seed_school):
    """PATCH /settings with missing 'key' field should fail."""
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"category": "feature", "value": "true"},
        headers=admin_headers,
    )
    assert resp.status_code in (400, 422)

@pytest.mark.asyncio
async def test_toggle_module_missing_enabled(client, admin_headers, seed_school):
    """PATCH /modules/{code} with missing 'enabled' field should fail."""
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/modules/exam",
        json={},
        headers=admin_headers,
    )
    assert resp.status_code in (400, 422)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py -v`
Expected: FAIL — 404 (routes not registered)

- [ ] **Step 3: Implement router**

> **N-01 prerequisite:** Before implementing the router, add a dedicated permission for school settings/modules endpoints and mirror it on the frontend.

```python
# src/edu_cloud/core/permissions.py — add ONE line to Permission enum (after VIEW_SCHOOLS):
    MANAGE_SCHOOL_SETTINGS = "manage_school_settings"

# Then add Permission.MANAGE_SCHOOL_SETTINGS to these 3 sets in ROLE_PERMISSIONS:
#   "district_admin": add Permission.MANAGE_SCHOOL_SETTINGS,
#   "principal":      add Permission.MANAGE_SCHOOL_SETTINGS,
#   "academic_director": add Permission.MANAGE_SCHOOL_SETTINGS,
# (platform_admin already gets it via set(Permission))
```

Exact edit commands:

```
Edit src/edu_cloud/core/permissions.py:
  after line `VIEW_SCHOOLS = "view_schools"` insert:
    MANAGE_SCHOOL_SETTINGS = "manage_school_settings"

  in "district_admin" set, add:
    Permission.MANAGE_SCHOOL_SETTINGS,

  in "principal" set, add:
    Permission.MANAGE_SCHOOL_SETTINGS,

  in "academic_director" set, add:
    Permission.MANAGE_SCHOOL_SETTINGS,
```

```javascript
// frontend/src/config/permissions.js — exact edits:
// In district_admin array, add: 'manage_school_settings'
// In principal array, add: 'manage_school_settings'
// In academic_director array, add: 'manage_school_settings'
```

> **F-01 fix:** Uses `Permission.MANAGE_SCHOOL_SETTINGS` (dedicated permission for school settings/modules endpoints).
> **F-08 fix:** Router has its own prefix and registers directly in app.py. No modification to `modules/school/router.py`.

```python
# src/edu_cloud/modules/school/settings_router.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.school_settings_service import (
    get_settings, upsert_setting, get_all_modules,
    set_module_enabled, get_enabled_modules, init_school_modules,
)
from edu_cloud.services.exceptions import ValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["school-settings"])


class UpsertSettingRequest(BaseModel):
    category: str = "general"
    key: str
    value: str | None = None


class ToggleModuleRequest(BaseModel):
    enabled: bool


@router.get("/settings")
async def list_settings(
    school_id: str,
    category: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    settings = await get_settings(db, school_id=school_id, category=category)
    return [
        {"id": s.id, "category": s.category, "key": s.key, "value": s.value}
        for s in settings
    ]


@router.patch("/settings")
async def update_setting(
    school_id: str,
    body: UpsertSettingRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    result = await upsert_setting(
        db, school_id=school_id,
        category=body.category,
        key=body.key,
        value=body.value,
    )
    return {"id": result.id, "category": result.category, "key": result.key, "value": result.value}


@router.get("/modules")
async def list_modules(
    school_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    await init_school_modules(db, school_id=school_id)
    return await get_all_modules(db, school_id=school_id)


@router.get("/modules/enabled")
async def list_enabled_modules(
    school_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    return list(await get_enabled_modules(db, school_id=school_id))


@router.patch("/modules/{module_code}")
async def toggle_module(
    school_id: str,
    module_code: str,
    body: ToggleModuleRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    try:
        module = await set_module_enabled(
            db, school_id=school_id, module_code=module_code, enabled=body.enabled,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": module.module_code, "enabled": module.enabled}
```

- [ ] **Step 4: Register router in app.py**

In `src/edu_cloud/api/app.py`, add:

```python
# In the lifespan model imports block, add:
import edu_cloud.models.school_settings  # noqa: F401

# In the router import block at the bottom of create_app(), add:
from edu_cloud.modules.school.settings_router import router as settings_router

# In the include_router loop list, add settings_router:
# (add to the existing for-loop list alongside schools_router, etc.)
```

- [ ] **Step 5: Run API tests**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py -v`
Expected: 10 passed

- [ ] **Step 6: Run full test suite to check no regression**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All existing tests pass + 10 new tests

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/school/settings_router.py src/edu_cloud/api/app.py tests/test_api/test_school_settings.py
git commit -m "feat: add school settings + modules API endpoints"
```

**审查清单:**
- [x] `require_permission(Permission.MANAGE_SCHOOL_SETTINGS)` 保护所有端点
- [x] `principal` / `academic_director` 角色测试验证新权限已真正打通
- [x] Pydantic models validate request body (UpsertSettingRequest requires `key`, ToggleModuleRequest requires `enabled`)
- [x] 无效 module_code 返回 400
- [x] init_school_modules 幂等（重复调用不报错）
- [x] 未认证请求返回 401/403
- [x] Multi-school isolation tested — different schools have independent module states

**测试契约:**
1. Multi-school isolation
   - 入口: `PATCH /api/v1/schools/{school_a}/modules/homework` + `GET /api/v1/schools/{school_b}/modules/enabled`
   - 反例: 错误实现使用全局缓存而非 school_id 隔离 → school_b 看到 school_a 的状态
   - 边界: 两个学校相同 module_code 不同 enabled 状态
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_school_settings.py::test_modules_multi_school_isolation -v`
2. Missing required field rejected
   - 入口: `PATCH /api/v1/schools/{id}/settings` with `{"category": "x", "value": "y"}` (no `key`)
   - 反例: 错误实现用 `dict.get()` → key=None silently inserted
   - 边界: missing `key` / missing `enabled`
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_school_settings.py::test_upsert_setting_missing_key -v`

---

### Task 4: Module Check Middleware

**Files:**
- Create: `src/edu_cloud/api/module_middleware.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_api/test_school_settings.py` (追加)

- [ ] **Step 1: Write failing middleware tests**

> **F-03 fix:** Tests must create a school-scoped UserRole and generate a JWT with `active_role_id`, because the middleware resolves school_id from UserRole, NOT from JWT directly. Platform admin tokens (no school_id) skip the module check.

```python
# tests/test_api/test_school_settings.py (追加)

# Helper to disable a module
async def _disable_module(client, admin_headers, school_id, module_code):
    await client.patch(
        f"/api/v1/schools/{school_id}/modules/{module_code}",
        json={"enabled": False},
        headers=admin_headers,
    )

@pytest.mark.asyncio
async def test_middleware_blocks_disabled_module(client, admin_headers, seed_school, db):
    """When calendar module is disabled, /api/v1/calendar/* should return 403."""
    school, _ = seed_school
    # Create a school-scoped user so middleware can resolve school_id from UserRole
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    user = User(username="mw_test_user", display_name="MW Test")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    await db.refresh(role)

    # JWT contains active_role_id (NOT school_id directly)
    token = create_access_token({"sub": user.id, "role": "principal", "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    # Init modules then disable calendar
    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    await _disable_module(client, admin_headers, school.id, "calendar")

    # calendar API should be blocked
    resp = await client.get("/api/v1/calendar/events", headers=headers)
    assert resp.status_code == 403
    assert "未启用" in resp.json().get("detail", "")

@pytest.mark.asyncio
async def test_middleware_allows_enabled_module(client, admin_headers, seed_school, db):
    """When calendar module is enabled (default), /api/v1/calendar/* works normally."""
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    user = User(username="mw_test_user2", display_name="MW Test 2")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    await db.refresh(role)

    token = create_access_token({"sub": user.id, "role": "principal", "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    # Init modules — calendar is enabled by default
    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    resp = await client.get("/api/v1/calendar/events", headers=headers)
    assert resp.status_code != 403

# ── Additional middleware coverage (F-07 fix) ──

@pytest.mark.asyncio
async def test_middleware_multiple_modules_disabled(client, admin_headers, seed_school, db):
    """Multiple disabled modules are all blocked independently."""
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token

    user = User(username="mw_multi_test", display_name="MW Multi")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    role = UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True)
    db.add(role)
    await db.commit()
    await db.refresh(role)

    token = create_access_token({"sub": user.id, "role": "principal", "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    await _disable_module(client, admin_headers, school.id, "calendar")
    await _disable_module(client, admin_headers, school.id, "studio")

    resp_cal = await client.get("/api/v1/calendar/events", headers=headers)
    resp_studio = await client.get("/api/v1/studio/documents", headers=headers)
    assert resp_cal.status_code == 403
    assert resp_studio.status_code == 403

@pytest.mark.asyncio
async def test_middleware_no_school_id_skips_check(client, admin_headers):
    """Platform admin with no school_id in role -> middleware skips module check."""
    # admin_headers is platform_admin with no school_id -> should not be blocked
    resp = await client.get("/api/v1/calendar/events", headers=admin_headers)
    assert resp.status_code != 403

@pytest.mark.asyncio
async def test_middleware_exempt_paths_always_pass(client):
    """Exempt paths (/api/v1/health, /api/v1/version) are never blocked."""
    resp_health = await client.get("/api/v1/health")
    assert resp_health.status_code == 200
    resp_version = await client.get("/api/v1/version")
    assert resp_version.status_code == 200

@pytest.mark.asyncio
async def test_middleware_multi_school_isolation(client, admin_headers, db):
    """School A disables calendar, School B calendar still works."""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="MW School A", code="MW_A", api_key_hash=hashed, district="test")
    school_b = School(name="MW School B", code="MW_B", api_key_hash=hashed, district="test")
    db.add(school_a)
    db.add(school_b)
    await db.flush()

    user_a = User(username="mw_user_a", display_name="User A")
    user_a.set_password("test123")
    user_b = User(username="mw_user_b", display_name="User B")
    user_b.set_password("test123")
    db.add(user_a)
    db.add(user_b)
    await db.flush()

    role_a = UserRole(user_id=user_a.id, role="principal", school_id=school_a.id, is_primary=True)
    role_b = UserRole(user_id=user_b.id, role="principal", school_id=school_b.id, is_primary=True)
    db.add(role_a)
    db.add(role_b)
    await db.commit()
    await db.refresh(role_a)
    await db.refresh(role_b)

    token_a = create_access_token({"sub": user_a.id, "role": "principal", "active_role_id": role_a.id})
    token_b = create_access_token({"sub": user_b.id, "role": "principal", "active_role_id": role_b.id})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    await client.get(f"/api/v1/schools/{school_a.id}/modules", headers=admin_headers)
    await client.get(f"/api/v1/schools/{school_b.id}/modules", headers=admin_headers)

    # Disable calendar for school A only
    await _disable_module(client, admin_headers, school_a.id, "calendar")

    # School A: blocked
    resp_a = await client.get("/api/v1/calendar/events", headers=headers_a)
    assert resp_a.status_code == 403

    # School B: not blocked
    resp_b = await client.get("/api/v1/calendar/events", headers=headers_b)
    assert resp_b.status_code != 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py::test_middleware_blocks_disabled_module -v`
Expected: FAIL — status_code != 403 (middleware not yet installed)

- [ ] **Step 3: Implement middleware**

> **F-02 fix:** Uses `decode_token` (from `edu_cloud.shared.auth`) not `decode_access_token`. Uses `async_session` (from `edu_cloud.database`) not `async_session_factory`.
> **F-03 fix:** JWT does NOT contain `school_id`. Instead, extract `active_role_id` from JWT payload, then query `UserRole.school_id` from DB. Platform admins without `active_role_id` or with `school_id=None` skip the module check.
> **F-04 fix:** Removed standalone `marking` (maps to `grading`). Added exam-related routes to `exam` module. Moved `/classes` and `/students` to exempt (base info). Core infrastructure stays exempt.

```python
# src/edu_cloud/api/module_middleware.py
"""
Module check middleware: blocks API requests for disabled modules.

Route prefix -> module_code mapping. Requests to disabled modules get 403.
This is a hard enforcement layer -- Agent/LLM cannot bypass it.

Key design decisions:
- JWT does NOT contain school_id. We extract active_role_id from JWT,
  then query UserRole to get school_id.
- Platform admins without a school-scoped role skip module checks.
- Uses decode_token (shared/auth.py) and async_session (database.py).
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import select

from edu_cloud.models.school_settings import SchoolModule

logger = logging.getLogger(__name__)

# Route prefix -> module_code mapping
# marking routes are part of the grading module (not a separate module)
ROUTE_MODULE_MAP = {
    "/api/v1/exams": "exam",
    "/api/v1/subjects": "exam",
    "/api/v1/questions": "exam",
    "/api/v1/scan": "exam",
    "/api/v1/cards": "exam",
    "/api/v1/templates": "exam",
    "/api/v1/grading": "grading",
    "/api/v1/marking": "grading",
    "/api/v1/analytics": "study_analytics",
    "/api/v1/knowledge": "research",
    "/api/v1/calendar": "calendar",
    "/api/v1/studio": "studio",
    "/api/v1/pipeline": "exam",
}

# Paths that are never blocked (core infrastructure + base info)
EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/health",
    "/api/v1/version",
    "/api/v1/schools",
    "/api/v1/dashboard",
    "/api/v1/ai",
    "/api/v1/classes",
    "/api/v1/students",
    "/api/v1/joint-exams",
    "/api/v1/notifications",
    "/api/v1/llm-config",
    "/api/v1/workspace",
    "/docs",
    "/openapi.json",
)


class ModuleCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        # Skip exempt paths
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        # Find matching module
        module_code = None
        for prefix, code in ROUTE_MODULE_MAP.items():
            if path.startswith(prefix):
                module_code = code
                break

        if module_code is None:
            return await call_next(request)

        # Extract active_role_id from JWT to resolve school_id
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        try:
            from edu_cloud.shared.auth import decode_token
            payload = decode_token(auth_header.split(" ")[1])
            active_role_id = payload.get("active_role_id")
        except Exception:
            # JWT decode failure -> let auth middleware handle it
            return await call_next(request)

        if not active_role_id:
            # No active_role_id in token (e.g., old token format) -> skip check
            return await call_next(request)

        # Query UserRole to get school_id
        from edu_cloud.database import async_session
        from edu_cloud.models.user_role import UserRole

        school_id = None
        async with async_session() as db:
            result = await db.execute(
                select(UserRole.school_id).where(UserRole.id == active_role_id)
            )
            row = result.first()
            if row:
                school_id = row[0]

        if not school_id:
            # Platform admin or role without school scope -> skip module check
            return await call_next(request)

        # Check module status
        async with async_session() as db:
            result = await db.execute(
                select(SchoolModule.enabled).where(
                    SchoolModule.school_id == school_id,
                    SchoolModule.module_code == module_code,
                )
            )
            row = result.first()

        # If module exists and is disabled -> block
        if row is not None and not row[0]:
            return JSONResponse(
                status_code=403,
                content={"detail": f"模块「{module_code}」未启用"},
            )

        return await call_next(request)
```

- [ ] **Step 4: Register middleware in app.py**

In `src/edu_cloud/api/app.py` `create_app()`, add after CORS middleware:

```python
from edu_cloud.api.module_middleware import ModuleCheckMiddleware

# After CORS middleware, before request_logging:
app.add_middleware(ModuleCheckMiddleware)
```

- [ ] **Step 5: Run middleware tests**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py -v`
Expected: 16 passed (10 API + 6 middleware)

- [ ] **Step 6: Run full suite**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass (middleware should not break existing tests since modules default to enabled or not found -> pass through)

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/api/module_middleware.py src/edu_cloud/api/app.py tests/test_api/test_school_settings.py
git commit -m "feat: add module check middleware — hard block for disabled modules"
```

**审查清单:**
- [x] Middleware 是代码级硬执行，不是 LLM 判断
- [x] Uses `decode_token` (not `decode_access_token`) matching `shared/auth.py`
- [x] Uses `async_session` (not `async_session_factory`) matching `database.py`
- [x] Resolves school_id via `active_role_id` -> UserRole DB query (NOT from JWT payload)
- [x] No active_role_id (old tokens) -> skip check (graceful degradation)
- [x] No school_id (platform_admin) -> skip check
- [x] Exempt paths include core infrastructure + base info (`/classes`, `/students`)
- [x] `marking` routes map to `grading` module (not a separate module)
- [x] Exam-related routes (`/exams`, `/subjects`, `/questions`, `/scan`, `/cards`) map to `exam` module
- [x] Disabled module returns 403 + Chinese message
- [x] Module not found in DB (new school) -> pass through

**边界条件:**
- No Authorization header -> pass through, let auth middleware handle
- No active_role_id in JWT (old token format or platform_admin) -> skip module check
- UserRole not found for active_role_id -> skip check (defensive)
- school_id is None (platform_admin role) -> skip check
- Module row not in DB (new school, not initialized) -> pass through
- JWT decode failure -> pass through (not our responsibility)

**测试契约:**
1. Disabled module is blocked
   - 入口: `GET /api/v1/calendar/events` (calendar disabled for this school)
   - 反例: 错误实现会忽略模块状态 -> 返回 200 而非 403
   - 边界: 模块未初始化 / JWT 无 active_role_id / role 无 school_id / 路径不在 ROUTE_MODULE_MAP
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_school_settings.py::test_middleware_blocks_disabled_module -v`
2. Platform admin skips module check
   - 入口: `GET /api/v1/calendar/events` with platform_admin token (no school_id)
   - 反例: 错误实现尝试从 JWT 取 school_id -> None -> crash or false block
   - 边界: platform_admin / district_admin without school scope
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_school_settings.py::test_middleware_no_school_id_skips_check -v`
3. Multi-school isolation
   - 入口: School A disables calendar, School B calendar still accessible
   - 反例: 错误实现使用全局缓存 -> School B 也被阻塞
   - 边界: 同 module_code 不同学校不同状态
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_school_settings.py::test_middleware_multi_school_isolation -v`

---

### Task 5: Alembic Migration

**Files:**
- Modify: `alembic/env.py` (add model import)
- Modify: `tests/test_alembic_migration.py` (add model import)
- Create: `alembic/versions/xxxx_add_school_settings_modules.py`

- [ ] **Step 1: Add model import to alembic/env.py (F-06 fix)**

In `alembic/env.py`, add the following import alongside the existing model imports (after the "core models" section, around line 25):

```python
# Add after existing core model imports:
from edu_cloud.models.school_settings import SchoolSetting, SchoolModule  # noqa: F401
```

This ensures `alembic revision --autogenerate` can discover the new tables.

- [ ] **Step 2: Add model import to tests/test_alembic_migration.py (F-06 fix)**

In `tests/test_alembic_migration.py`, add the following import inside `test_migration_creates_all_expected_tables` function, alongside existing model imports (after line 69):

```python
    import edu_cloud.models.school_settings  # noqa: F401
```

This ensures the table comparison includes the new tables.

- [ ] **Step 3: Generate migration**

```bash
cd /mnt/c/Users/Administrator/edu-cloud
python -m alembic revision --autogenerate -m "add_school_settings_modules"
```

- [ ] **Step 4: Review generated migration**

Check the generated file contains:
- `op.create_table("school_settings", ...)` with school_id, category, key, value, UniqueConstraint
- `op.create_table("school_modules", ...)` with school_id, module_code, enabled, config, UniqueConstraint
- `downgrade()` contains `op.drop_table("school_settings")` and `op.drop_table("school_modules")`

- [ ] **Step 5: Run migration smoke test**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_alembic_migration.py -v`
Expected: All migration tests pass (new tables included in comparison)

- [ ] **Step 6: Commit migration**

```bash
git add alembic/env.py alembic/versions/ tests/test_alembic_migration.py
git commit -m "migrate: add school_settings + school_modules tables"
```

**审查清单:**
- [x] `alembic/env.py` imports `SchoolSetting` and `SchoolModule` for autogenerate discovery
- [x] `tests/test_alembic_migration.py` imports `edu_cloud.models.school_settings` for table comparison
- [x] Migration includes both tables with correct columns and constraints
- [x] Downgrade drops both tables cleanly
- [x] Migration smoke test passes

---

### Task 6: Frontend API Layer + Sidebar Integration

**Files:**
- Create: `frontend/src/api/schoolSettings.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/components/shell/AppSidebar.vue`
- Modify: `frontend/src/config/sidebarConfig.js`
- Create: `frontend/src/__tests__/AppSidebar.test.js` (F-07 fix: Vitest real-component test)

- [ ] **Step 1: Create API client**

```javascript
// frontend/src/api/schoolSettings.js
import client from './client.js'

export const getSchoolSettings = (schoolId, category) =>
  client.get(`/schools/${schoolId}/settings`, { params: { category } })

export const updateSchoolSetting = (schoolId, data) =>
  client.patch(`/schools/${schoolId}/settings`, data)

export const getSchoolModules = (schoolId) =>
  client.get(`/schools/${schoolId}/modules`)

export const getEnabledModules = (schoolId) =>
  client.get(`/schools/${schoolId}/modules/enabled`)

export const toggleModule = (schoolId, moduleCode, enabled) =>
  client.patch(`/schools/${schoolId}/modules/${moduleCode}`, { enabled })
```

- [ ] **Step 2: Add enabledModules + modulesLoaded to auth store (F-05 fix: setup store pattern)**

> The auth store uses the setup store pattern (`defineStore('auth', () => { ... })`), using `ref()` / `computed()`. Do NOT use options-store syntax (`this.xxx`).

In `frontend/src/stores/auth.js`, make the following changes:

```javascript
// 1. Add import at top (after existing imports):
import { getEnabledModules } from '../api/schoolSettings.js'

// 2. Inside the defineStore('auth', () => { ... }) function body,
//    after the existing ref declarations (after currentRoleIndex ref), add:
const enabledModules = ref([])
const modulesLoaded = ref(false)

// 3. Add the loadModules function (after the switchRole function):
async function loadModules() {
  const role = currentRole.value
  if (!role?.school_id) {
    enabledModules.value = []
    modulesLoaded.value = false
    return
  }
  try {
    const { data } = await getEnabledModules(role.school_id)
    enabledModules.value = data
    modulesLoaded.value = true
  } catch {
    // Fallback to defaults if API fails
    enabledModules.value = ['exam', 'grading', 'calendar', 'studio']
    modulesLoaded.value = true
  }
}

// 4. In the login function, after saveAuthState() call (line 64), add:
//    await loadModules()

// 5. In the switchRole function, after saveAuthState() call (line 84), add:
//    await loadModules()

// 6. In the logout function, after resetting other state, add:
//    enabledModules.value = []
//    modulesLoaded.value = false

// 7. In the return statement, add enabledModules, modulesLoaded and loadModules:
return {
  token, user, roles, currentRole, currentRoleIndex,
  displayName, roleName, currentContext, isAdmin,
  enabledModules, modulesLoaded,
  checkPermission, login, switchRole, logout, loadModules,
}
```

- [ ] **Step 3: Add moduleCode to sidebarConfig (F-05 fix: matching existing `{ icon, label, route }` pattern)**

> Existing sidebar config uses `{ icon, label, route }`. Extend to `{ icon, label, route, moduleCode }`. Items without `moduleCode` are always shown.

Replace `frontend/src/config/sidebarConfig.js` content with moduleCode fields added:

```javascript
// frontend/src/config/sidebarConfig.js
const SIDEBAR_ITEMS = {
  platform_admin: [
    { icon: 'dashboard', label: '平台概览', route: '/' },
    { icon: 'school', label: '学校管理', route: '/schools' },
    { icon: 'exam', label: '联考管理', route: '/exams' },
  ],
  district_admin: [
    { icon: 'dashboard', label: '区域概览', route: '/' },
    { icon: 'school', label: '学校管理', route: '/schools' },
    { icon: 'exam', label: '联考管理', route: '/exams' },
    { icon: 'chart', label: '跨校分析', route: '/analysis' },
  ],
  principal: [
    { icon: 'dashboard', label: '校务概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'document', label: '文档中心', route: '/analysis', moduleCode: 'studio' },
    { icon: 'calendar', label: '校历通知', route: '/analysis', moduleCode: 'calendar' },
    { icon: 'settings', label: '学校配置', route: '/school-settings' },
  ],
  academic_director: [
    { icon: 'dashboard', label: '教务概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'exam', label: '联考管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷调度', route: '/grading/tasks', moduleCode: 'grading' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'document', label: '文档中心', route: '/analysis', moduleCode: 'studio' },
    { icon: 'settings', label: '学校配置', route: '/school-settings' },
  ],
  grade_leader: [
    { icon: 'dashboard', label: '年级概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'document', label: '文档', route: '/analysis', moduleCode: 'studio' },
  ],
  homeroom_teacher: [
    { icon: 'dashboard', label: '我的工作台', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷', route: '/marking', moduleCode: 'grading' },
    { icon: 'chart', label: '成绩分析', route: '/analysis' },
    { icon: 'notification', label: '通知管理', route: '/analysis' },
    { icon: 'document', label: '文档', route: '/analysis', moduleCode: 'studio' },
  ],
  subject_teacher: [
    { icon: 'dashboard', label: '我的工作台', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷', route: '/marking', moduleCode: 'grading' },
    { icon: 'chart', label: '成绩分析', route: '/analysis' },
    { icon: 'paper', label: '论文写作', route: '/analysis' },
    { icon: 'document', label: '文档', route: '/analysis', moduleCode: 'studio' },
  ],
  parent: [
    { icon: 'score', label: '孩子成绩', route: '/' },
    { icon: 'notification', label: '学校通知', route: '/' },
  ],
}

export function getSidebarItems(role) {
  return SIDEBAR_ITEMS[role] || SIDEBAR_ITEMS.subject_teacher
}
```

- [ ] **Step 4: Filter sidebar by enabled modules in AppSidebar.vue**

In `frontend/src/components/shell/AppSidebar.vue`, replace the `navItems` computed (line 40):

Current:
```javascript
const navItems = computed(() => getSidebarItems(currentNormalizedRole.value))
```

Replace with:
```javascript
const navItems = computed(() => {
  const items = getSidebarItems(currentNormalizedRole.value)
  if (!auth.currentRole?.school_id) return items
  if (!auth.modulesLoaded) return items
  const enabled = new Set(auth.enabledModules)
  return items.filter(item => {
    if (!item.moduleCode) return true
    return enabled.has(item.moduleCode)
  })
})
```

- [ ] **Step 5: Create Vitest real-component test for sidebar module filtering (F-07 fix)**

```javascript
// frontend/src/__tests__/AppSidebar.test.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref, reactive, nextTick } from 'vue'

// Mock sidebarConfig to return predictable items
vi.mock('../config/sidebarConfig.js', () => ({
  getSidebarItems: () => [
    { icon: 'dashboard', label: 'Dashboard', route: '/' },
    { icon: 'exam', label: 'Exams', route: '/exams', moduleCode: 'exam' },
    { icon: 'calendar', label: 'Calendar', route: '/analysis', moduleCode: 'calendar' },
    { icon: 'document', label: 'Studio', route: '/analysis', moduleCode: 'studio' },
  ],
}))

vi.mock('../config/roles.js', () => ({
  normalizeRole: (r) => r || 'subject_teacher',
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/' }),
  RouterLink: {
    template: '<a><slot /></a>',
    props: ['to'],
  },
}))

// Reactive mock auth state so tests can mutate it
const mockAuth = reactive({
  currentRole: { role: 'principal', school_id: 'school-1' },
  enabledModules: [],
  modulesLoaded: false,
  checkPermission: () => true,
})

vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => mockAuth,
}))

import AppSidebar from '../components/shell/AppSidebar.vue'

describe('AppSidebar module filtering', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Reset mock state
    mockAuth.currentRole = { role: 'principal', school_id: 'school-1' }
    mockAuth.enabledModules = []
    mockAuth.modulesLoaded = false
  })

  it('shows all items when modulesLoaded=false (not yet loaded)', async () => {
    mockAuth.modulesLoaded = false
    const wrapper = mount(AppSidebar)
    await nextTick()
    // All 4 items should render since modules not loaded yet
    const labels = wrapper.findAll('[class*="nav"]').map(el => el.text())
    // Fallback: all items visible
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Exams')
    expect(wrapper.text()).toContain('Calendar')
    expect(wrapper.text()).toContain('Studio')
  })

  it('hides calendar when modulesLoaded=true and enabledModules=[exam,studio]', async () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = ['exam', 'studio']
    const wrapper = mount(AppSidebar)
    await nextTick()
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Exams')
    expect(wrapper.text()).toContain('Studio')
    expect(wrapper.text()).not.toContain('Calendar')
  })

  it('hides ALL module-bound items when enabledModules=[], keeps non-module items', async () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = []
    const wrapper = mount(AppSidebar)
    await nextTick()
    // Dashboard has no moduleCode -> always shown
    expect(wrapper.text()).toContain('Dashboard')
    // All module-bound items hidden
    expect(wrapper.text()).not.toContain('Exams')
    expect(wrapper.text()).not.toContain('Calendar')
    expect(wrapper.text()).not.toContain('Studio')
  })
})
```

- [ ] **Step 6: Run frontend tests**

Run: `cd /mnt/c/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: All existing tests pass + 3 new sidebar tests

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/schoolSettings.js frontend/src/stores/auth.js frontend/src/components/shell/AppSidebar.vue frontend/src/config/sidebarConfig.js frontend/src/__tests__/AppSidebar.test.js
git commit -m "feat: frontend sidebar filters by enabled modules + Vitest tests"
```

**审查清单:**
- [x] Auth store uses setup store pattern: `const enabledModules = ref([])` + `const modulesLoaded = ref(false)` and `async function loadModules()` (NOT `this.enabledModules`)
- [x] `modulesLoaded` distinguishes "not loaded yet" from "loaded but empty" — `modulesLoaded=false` shows all items, `modulesLoaded=true` + empty enabledModules hides module-bound items
- [x] Sidebar config extends to `{ icon, label, route, moduleCode }` matching existing pattern; platform_admin/district_admin have no moduleCode (no school scope)
- [x] Items without `moduleCode` are always shown (dashboard, settings, analysis)
- [x] Sidebar computed checks `auth.currentRole?.school_id` and `auth.modulesLoaded` before filtering
- [x] `loadModules()` called after login and switchRole; sets `modulesLoaded=true` on success and fallback
- [x] `enabledModules` and `modulesLoaded` cleared on logout
- [x] Vitest real-component tests (mount AppSidebar) verify 3 scenarios: not loaded / partial / empty

**测试契约:**
1. Sidebar filters by enabled modules (real component test)
   - 入口: `mount(AppSidebar)` with mocked auth store reactive state
   - 反例: 错误实现不检查 `modulesLoaded` -> 空 enabledModules 隐藏所有模块项（加载中误杀）
   - 边界: modulesLoaded=false / modulesLoaded=true+enabledModules=['exam','studio'] / modulesLoaded=true+enabledModules=[]
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/AppSidebar.test.js`

---

### Task 7: School Settings Management Page

**Files:**
- Create: `frontend/src/pages/SchoolSettingsPage.vue`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Create management page**

```vue
<!-- frontend/src/pages/SchoolSettingsPage.vue -->
<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">学校配置</h1>
        <p class="page-subtitle">管理功能模块和学校设置</p>
      </div>
    </div>

    <n-tabs type="line" animated>
      <n-tab-pane name="modules" tab="功能模块">
        <n-card title="功能模块管理" style="margin-top: 16px">
          <p style="color: #999; margin-bottom: 16px">启用或禁用学校可用的功能模块。禁用后，对应的导航菜单、API 和 AI 助手工具将不可用。</p>
          <n-space vertical>
            <div v-for="m in modules" :key="m.code" class="module-row">
              <div class="module-info">
                <n-text strong>{{ m.name }}</n-text>
                <n-text depth="3" style="margin-left: 8px">{{ m.code }}</n-text>
              </div>
              <n-switch
                :value="m.enabled"
                :loading="toggling === m.code"
                @update:value="(v) => handleToggle(m.code, v)"
              />
            </div>
          </n-space>
        </n-card>
      </n-tab-pane>

      <n-tab-pane name="settings" tab="学校设置">
        <n-card title="配置项" style="margin-top: 16px">
          <n-data-table :columns="settingsColumns" :data="settings" :loading="loadingSettings" />
        </n-card>
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { getSchoolModules, toggleModule, getSchoolSettings } from '../api/schoolSettings.js'

const auth = useAuthStore()
const message = useMessage()
const modules = ref([])
const settings = ref([])
const toggling = ref(null)
const loadingSettings = ref(false)

const schoolId = () => auth.currentRole?.school_id

const settingsColumns = [
  { title: '分类', key: 'category', width: 120 },
  { title: '键', key: 'key', width: 200 },
  { title: '值', key: 'value' },
]

async function loadModules() {
  if (!schoolId()) return
  try {
    const { data } = await getSchoolModules(schoolId())
    modules.value = data
  } catch (e) {
    message.error('加载模块失败')
  }
}

async function loadSettings() {
  if (!schoolId()) return
  loadingSettings.value = true
  try {
    const { data } = await getSchoolSettings(schoolId())
    settings.value = data
  } catch { /* */ }
  loadingSettings.value = false
}

async function handleToggle(code, enabled) {
  toggling.value = code
  try {
    await toggleModule(schoolId(), code, enabled)
    await loadModules()
    await auth.loadModules()
    message.success(`模块「${code}」已${enabled ? '启用' : '禁用'}`)
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  }
  toggling.value = null
}

onMounted(() => {
  loadModules()
  loadSettings()
})
</script>

<style scoped>
.module-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
}
.module-info {
  display: flex;
  align-items: center;
}
</style>
```

- [ ] **Step 2: Add route (school-scoped admin roles)**

In `frontend/src/router/index.js`, add to the AppShell children array (after the Schools route):

> School settings is for school-scoped admin roles (principal, academic_director), not permission-gated. Platform admin manages schools via SchoolsPage, not SchoolSettingsPage.

```javascript
// School settings management (school-scoped admin roles)
{
  path: 'school-settings',
  name: 'SchoolSettings',
  component: () => import('../pages/SchoolSettingsPage.vue'),
  meta: { roles: ['principal', 'academic_director'] },
},
```

> Note: The sidebar entry for `principal` and `academic_director` is already added in Task 6 Step 3 (sidebarConfig.js update).

- [ ] **Step 3: Run frontend build to verify page renders**

Run: `cd /mnt/c/Users/Administrator/edu-cloud/frontend && npx vite build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/SchoolSettingsPage.vue frontend/src/router/index.js
git commit -m "feat: add school settings management page with module toggles"
```

**审查清单:**
- [x] Route uses `meta: { roles: ['principal', 'academic_director'] }` (school-scoped admin roles, not permission-gated)
- [x] Module toggle calls `auth.loadModules()` to sync sidebar (updates both enabledModules and modulesLoaded)
- [x] Page uses schoolId from `auth.currentRole?.school_id`
- [x] Naive UI components match project style (n-card / n-tabs / n-switch / n-data-table)
- [x] No hardcoded school_id

---

## Summary

| Task | 产出 | 测试 |
|------|------|------|
| 1 | SchoolSetting + SchoolModule models + conftest import | 3 model tests |
| 2 | Settings + Modules service | 6 service tests |
| 3 | Settings + Modules API | 12 API tests (incl. multi-school isolation + error cases) |
| 4 | Module check middleware | 6 middleware tests (incl. multi-school, no school_id, exempt paths) |
| 5 | Alembic migration + env.py + test imports | Schema validation (migration smoke test) |
| 6 | Frontend sidebar module filtering | 3 Vitest tests + manual (vite build) |
| 7 | Settings management page | Manual (vite build) |

**Total: 7 tasks, ~30 automated tests, ~7 commits**

完成后，edu-cloud 具备：
- 学校级 KV 配置存储
- 8 个功能模块的启用/禁用管理
- API 层硬拦截 disabled 模块（通过 JWT active_role_id -> UserRole.school_id 查询）
- 前端 sidebar 动态渲染（setup store pattern）
- 管理员配置页面

---

## Finding 处置记录

| ID | Severity | Category | 处置 |
|----|----------|----------|------|
| F-01 | HIGH | code-bug | Fixed: `Permission.MANAGE_SCHOOLS` (plural) + `meta: { permissions: ['manage_schools'] }` (array) |
| F-02 | HIGH | code-bug | Fixed: `decode_token` (not decode_access_token) + `async_session` (not async_session_factory) |
| F-03 | HIGH | design-concern | Fixed: Middleware extracts `active_role_id` from JWT -> queries UserRole.school_id from DB. Platform admin (no school_id) skips check. |
| F-04 | HIGH | code-bug | Fixed R2: Removed `report` from MODULE_CODES (8 entries). `/api/v1/analytics` maps to `study_analytics`. |
| F-05 | HIGH | code-bug | Fixed R2: Setup store adds `modulesLoaded` ref. Sidebar computed checks `modulesLoaded` before filtering (distinguishes "not loaded" from "loaded empty"). |
| F-06 | HIGH | code-bug | Fixed: Explicit import steps for `alembic/env.py`, `tests/test_alembic_migration.py`, and `tests/conftest.py`. |
| F-07 | HIGH | test-gap | Fixed R2: Real component test (`mount(AppSidebar)`) with 3 scenarios: modulesLoaded=false / partial modules / empty modules. Multi-school isolation + middleware coverage unchanged. |
| F-08 | MED | design-concern | Fixed: Removed "Modify school/router.py" from File Map. Settings router registers directly in app.py with full prefix. |
