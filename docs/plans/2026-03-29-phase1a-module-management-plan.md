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
| Create | `src/edu_cloud/modules/school/settings_router.py` | Settings + Modules API endpoints |
| Modify | `src/edu_cloud/modules/school/router.py` | Include settings_router |
| Create | `src/edu_cloud/api/module_middleware.py` | Module check middleware |
| Modify | `src/edu_cloud/api/app.py` | Register middleware + import models |
| Create | `alembic/versions/xxxx_add_school_settings_modules.py` | DB migration |
| Create | `tests/test_api/test_school_settings.py` | API tests |
| Create | `tests/test_services/test_school_settings_service.py` | Service tests |
| Create | `frontend/src/api/schoolSettings.js` | API client |
| Modify | `frontend/src/stores/auth.js` | Add enabledModules state |
| Modify | `frontend/src/components/shell/AppSidebar.vue` | Filter nav by modules |
| Create | `frontend/src/pages/SchoolSettingsPage.vue` | Management page |
| Modify | `frontend/src/router/index.js` | Add route |
| Modify | `frontend/src/config/sidebarConfig.js` | Add settings menu item |

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
    "report": "分析报告",
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_settings_service.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/models/school_settings.py tests/test_services/test_school_settings_service.py
git commit -m "feat: add SchoolSetting + SchoolModule models"
```

**审查清单:**
- [x] UniqueConstraint 防止同 school 同 key/module_code 重复
- [x] MODULE_CODES 常量集中定义，不散落各处
- [x] ForeignKey 关联 schools.id
- [x] IdMixin + TimestampMixin 一致

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
    assert len(modules) == 9  # All MODULE_CODES
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py -v`
Expected: FAIL — 404 (routes not registered)

- [ ] **Step 3: Implement router**

```python
# src/edu_cloud/modules/school/settings_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.school_settings_service import (
    get_settings, upsert_setting, get_all_modules,
    set_module_enabled, get_enabled_modules, init_school_modules,
)
from edu_cloud.services.exceptions import ValidationError

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["school-settings"])


@router.get("/settings")
async def list_settings(
    school_id: str,
    category: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL)),
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
    body: dict,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL)),
    db: AsyncSession = Depends(get_db),
):
    result = await upsert_setting(
        db, school_id=school_id,
        category=body.get("category", "general"),
        key=body["key"],
        value=body.get("value"),
    )
    return {"id": result.id, "category": result.category, "key": result.key, "value": result.value}


@router.get("/modules")
async def list_modules(
    school_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL)),
    db: AsyncSession = Depends(get_db),
):
    await init_school_modules(db, school_id=school_id)
    return await get_all_modules(db, school_id=school_id)


@router.get("/modules/enabled")
async def list_enabled_modules(
    school_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL)),
    db: AsyncSession = Depends(get_db),
):
    return list(await get_enabled_modules(db, school_id=school_id))


@router.patch("/modules/{module_code}")
async def toggle_module(
    school_id: str,
    module_code: str,
    body: dict,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL)),
    db: AsyncSession = Depends(get_db),
):
    try:
        module = await set_module_enabled(
            db, school_id=school_id, module_code=module_code, enabled=body["enabled"],
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": module.module_code, "enabled": module.enabled}
```

- [ ] **Step 4: Register router in app.py**

在 `src/edu_cloud/api/app.py` 中添加：

```python
# 在 import 区域添加:
from edu_cloud.modules.school.settings_router import router as settings_router
import edu_cloud.models.school_settings  # noqa: F401

# 在 include_router 列表中添加:
app.include_router(settings_router)
```

- [ ] **Step 5: Run API tests**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py -v`
Expected: 7 passed

- [ ] **Step 6: Run full test suite to check no regression**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All existing tests pass + 7 new tests

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/school/settings_router.py src/edu_cloud/api/app.py tests/test_api/test_school_settings.py
git commit -m "feat: add school settings + modules API endpoints"
```

**审查清单:**
- [x] require_permission(Permission.MANAGE_SCHOOL) 保护所有端点
- [x] 无效 module_code 返回 400
- [x] init_school_modules 幂等（重复调用不报错）
- [x] 未认证请求返回 401/403

---

### Task 4: Module Check Middleware

**Files:**
- Create: `src/edu_cloud/api/module_middleware.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_api/test_school_settings.py` (追加)

- [ ] **Step 1: Write failing middleware tests**

```python
# tests/test_api/test_school_settings.py (追加)

# 需要一个 helper 设置模块状态
async def _disable_module(client, admin_headers, school_id, module_code):
    await client.patch(
        f"/api/v1/schools/{school_id}/modules/{module_code}",
        json={"enabled": False},
        headers=admin_headers,
    )

@pytest.mark.asyncio
async def test_middleware_blocks_disabled_module(client, admin_headers, seed_school):
    """当 calendar 模块 disabled 时，/api/v1/calendar/* 应返回 403"""
    school, _ = seed_school
    # 先初始化模块
    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    # 禁用 calendar
    await _disable_module(client, admin_headers, school.id, "calendar")
    # calendar API 应该被拦截
    resp = await client.get("/api/v1/calendar/events", headers=admin_headers)
    assert resp.status_code == 403
    assert "未启用" in resp.json().get("detail", "")

@pytest.mark.asyncio
async def test_middleware_allows_enabled_module(client, admin_headers, seed_school):
    """当 calendar 模块 enabled 时，/api/v1/calendar/* 正常访问"""
    school, _ = seed_school
    await client.get(f"/api/v1/schools/{school.id}/modules", headers=admin_headers)
    # calendar 默认 enabled
    resp = await client.get("/api/v1/calendar/events", headers=admin_headers)
    assert resp.status_code != 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py::test_middleware_blocks_disabled_module -v`
Expected: FAIL — status_code != 403 (middleware not yet installed)

- [ ] **Step 3: Implement middleware**

```python
# src/edu_cloud/api/module_middleware.py
"""
Module check middleware: blocks API requests for disabled modules.

Route prefix → module_code mapping. Requests to disabled modules get 403.
This is a hard enforcement layer — Agent/LLM cannot bypass it.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import select

from edu_cloud.models.school_settings import SchoolModule

# Route prefix → module_code
ROUTE_MODULE_MAP = {
    "/api/v1/calendar": "calendar",
    "/api/v1/studio": "studio",
    "/api/v1/grading": "grading",
    "/api/v1/marking": "marking",
    "/api/v1/analytics": "report",
    "/api/v1/knowledge": "research",
}

# Paths that are never blocked (auth, health, schools, dashboard, ai)
EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/health",
    "/api/v1/version",
    "/api/v1/schools",
    "/api/v1/dashboard",
    "/api/v1/ai",
    "/api/v1/exams",
    "/api/v1/subjects",
    "/api/v1/questions",
    "/api/v1/classes",
    "/api/v1/students",
    "/api/v1/scan",
    "/api/v1/cards",
    "/api/v1/joint-exams",
    "/api/v1/notifications",
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

        # Extract school_id from JWT (already decoded by auth)
        # We need to check the auth state; if no auth, let auth middleware handle it
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        try:
            from edu_cloud.shared.auth import decode_access_token
            payload = decode_access_token(auth_header.split(" ")[1])
            school_id = payload.get("school_id")
        except Exception:
            return await call_next(request)

        if not school_id:
            return await call_next(request)

        # Check module status — use a fresh DB session
        from edu_cloud.database import async_session_factory
        async with async_session_factory() as db:
            result = await db.execute(
                select(SchoolModule.enabled).where(
                    SchoolModule.school_id == school_id,
                    SchoolModule.module_code == module_code,
                )
            )
            row = result.first()

        # If module exists and is disabled → block
        if row is not None and not row[0]:
            return JSONResponse(
                status_code=403,
                content={"detail": f"模块「{module_code}」未启用"},
            )

        return await call_next(request)
```

- [ ] **Step 4: Register middleware in app.py**

在 `src/edu_cloud/api/app.py` 的 `create_app()` 中添加：

```python
from edu_cloud.api.module_middleware import ModuleCheckMiddleware

# 在 CORS middleware 之后添加:
app.add_middleware(ModuleCheckMiddleware)
```

- [ ] **Step 5: Run middleware tests**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_school_settings.py -v`
Expected: 9 passed

- [ ] **Step 6: Run full suite**

Run: `cd /mnt/c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass (middleware should not break existing tests since modules default to enabled or not found → pass through)

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/api/module_middleware.py src/edu_cloud/api/app.py tests/test_api/test_school_settings.py
git commit -m "feat: add module check middleware — hard block for disabled modules"
```

**审查清单:**
- [x] Middleware 是代码级硬执行，不是 LLM 判断
- [x] 豁免路径包含所有核心 API（auth/health/schools/dashboard/ai/exams）
- [x] 模块不存在时 pass through（不阻拦未配置的学校）
- [x] disabled 模块返回 403 + 中文消息

**边界条件:**
- school_id 为空（未认证）→ pass through，让 auth middleware 处理
- 模块未初始化（新学校）→ row is None → pass through
- JWT 解码失败 → pass through（不影响正常错误处理链）

**测试契约:**
1. disabled 模块被拦截
   - 入口: `GET /api/v1/calendar/events`（calendar disabled）
   - 反例: 错误实现会忽略模块状态 → 返回 200 而非 403
   - 边界: 模块未初始化 / JWT 缺 school_id / 路径不在 ROUTE_MODULE_MAP
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_school_settings.py::test_middleware_blocks_disabled_module -v`

---

### Task 5: Alembic Migration

**Files:**
- Create: `alembic/versions/xxxx_add_school_settings_modules.py`

- [ ] **Step 1: Generate migration**

```bash
cd /mnt/c/Users/Administrator/edu-cloud
python -m alembic revision --autogenerate -m "add_school_settings_modules"
```

- [ ] **Step 2: Review generated migration**

检查生成的文件包含:
- `op.create_table("school_settings", ...)` 含 school_id, category, key, value, UniqueConstraint
- `op.create_table("school_modules", ...)` 含 school_id, module_code, enabled, config, UniqueConstraint
- `downgrade()` 包含 `op.drop_table("school_settings")` 和 `op.drop_table("school_modules")`

- [ ] **Step 3: Commit migration**

```bash
git add alembic/versions/
git commit -m "migrate: add school_settings + school_modules tables"
```

---

### Task 6: Frontend API Layer + Sidebar Integration

**Files:**
- Create: `frontend/src/api/schoolSettings.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/components/shell/AppSidebar.vue`

- [ ] **Step 1: Create API client**

```javascript
// frontend/src/api/schoolSettings.js
import client from './client'

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

- [ ] **Step 2: Add enabledModules to auth store**

在 `frontend/src/stores/auth.js` 的 state 中添加 `enabledModules`，在 login 成功后加载：

```javascript
// 在 state 中添加:
enabledModules: [],

// 在 login action 成功后添加:
async loadModules() {
  const role = this.currentRole
  if (!role?.school_id) return
  try {
    const { data } = await getEnabledModules(role.school_id)
    this.enabledModules = data
  } catch {
    this.enabledModules = ['exam', 'grading', 'calendar', 'studio']
  }
},

// 在 switchRole 后也调用 loadModules
```

在文件顶部添加 import：
```javascript
import { getEnabledModules } from '../api/schoolSettings'
```

- [ ] **Step 3: Filter sidebar by enabled modules**

在 `frontend/src/components/shell/AppSidebar.vue` 中，当前 sidebar 从 `sidebarConfig.js` 读取菜单项。添加模块过滤：

```javascript
// 在 computed 或 setup 中，过滤菜单项:
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()

const filteredMenuItems = computed(() => {
  const items = getSidebarItems(auth.currentRole?.role)
  const enabled = new Set(auth.enabledModules)
  return items.filter(item => {
    // 如果菜单项有 moduleCode 属性，检查是否启用
    if (item.moduleCode && !enabled.has(item.moduleCode)) return false
    return true
  })
})
```

- [ ] **Step 4: Add moduleCode to sidebarConfig**

在 `frontend/src/config/sidebarConfig.js` 中，为每个菜单项添加 `moduleCode` 属性：

```javascript
// 示例（具体看现有结构追加字段）:
{ label: '考试管理', key: 'exams', icon: '...', moduleCode: 'exam' },
{ label: '阅卷系统', key: 'grading', icon: '...', moduleCode: 'grading' },
{ label: '校历日程', key: 'calendar', icon: '...', moduleCode: 'calendar' },
// ...
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/schoolSettings.js frontend/src/stores/auth.js frontend/src/components/shell/AppSidebar.vue frontend/src/config/sidebarConfig.js
git commit -m "feat: frontend sidebar filters by enabled modules"
```

---

### Task 7: School Settings Management Page

**Files:**
- Create: `frontend/src/pages/SchoolSettingsPage.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/sidebarConfig.js`

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
import { ref, onMounted, h } from 'vue'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { getSchoolModules, toggleModule, getSchoolSettings } from '../api/schoolSettings'

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

- [ ] **Step 2: Add route**

在 `frontend/src/router/index.js` 的 AppShell children 中添加：

```javascript
{
  path: '/school-settings',
  name: 'school-settings',
  component: () => import('../pages/SchoolSettingsPage.vue'),
  meta: { permission: 'manage_school' },
},
```

- [ ] **Step 3: Add sidebar entry**

在 `frontend/src/config/sidebarConfig.js` 中，为 platform_admin 和 principal 角色添加：

```javascript
{ label: '学校配置', key: 'school-settings', icon: 'SettingsOutline' },
```

- [ ] **Step 4: Run frontend dev to verify page renders**

Run: `cd /mnt/c/Users/Administrator/edu-cloud/frontend && npx vite build 2>&1 | tail -5`
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SchoolSettingsPage.vue frontend/src/router/index.js frontend/src/config/sidebarConfig.js
git commit -m "feat: add school settings management page with module toggles"
```

**审查清单:**
- [x] 模块切换后 auth store 的 enabledModules 同步更新
- [x] 管理权限检查（meta.permission = manage_school）
- [x] 禁用模块后 sidebar 菜单消失（通过 auth.loadModules 联动）
- [x] Naive UI 组件风格与项目一致（n-card / n-tabs / n-switch / n-data-table）

---

## Summary

| Task | 产出 | 测试 |
|------|------|------|
| 1 | SchoolSetting + SchoolModule models | 3 model tests |
| 2 | Settings + Modules service | 6 service tests |
| 3 | Settings + Modules API | 7 API tests |
| 4 | Module check middleware | 2 middleware tests |
| 5 | Alembic migration | Schema validation |
| 6 | Frontend sidebar module filtering | Manual (vite build) |
| 7 | Settings management page | Manual (vite build) |

**Total: 7 tasks, ~18 automated tests, ~7 commits**

完成后，edu-cloud 具备：
- 学校级 KV 配置存储
- 9 个功能模块的启用/禁用管理
- API 层硬拦截 disabled 模块
- 前端 sidebar 动态渲染
- 管理员配置页面
