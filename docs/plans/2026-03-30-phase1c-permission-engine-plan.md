# Phase 1c: 权限引擎 + 审计日志 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud 添加 Capability 可配置权限层、ScopeFilter 查询工具、审计日志系统，实现权限检查链的前 4 步和变更可追溯性。

**Architecture:** Capability 表存储学校级角色能力配置（域×操作×角色），ScopeFilter 工具类基于 UserRole 自动注入 WHERE 条件，AuditLog 表 + @audited 装饰器在 Service 层自动记录 before/after 快照。三者独立叠加在现有 Permission RBAC 之上，不修改现有代码。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL + pytest

**Design doc:** `docs/plans/2026-03-30-phase1c-permission-engine-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/edu_cloud/models/capability.py` | Capability ORM + CAPABILITY_DOMAINS + CAPABILITY_ACTIONS |
| Create | `src/edu_cloud/services/capability_service.py` | init_school_capabilities + get/set/check capability |
| Create | `src/edu_cloud/modules/school/capability_router.py` | Capability API（GET/PATCH/POST init） |
| Create | `src/edu_cloud/core/scope_filter.py` | ScopeFilter 工具类 |
| Create | `src/edu_cloud/models/audit_log.py` | AuditLog ORM |
| Create | `src/edu_cloud/services/audit_service.py` | @audited 装饰器 + write_audit_log + list_audit_logs |
| Create | `src/edu_cloud/modules/school/audit_router.py` | AuditLog 查询 API |
| Modify | `src/edu_cloud/logging_config.py` | 新增 current_user_var ContextVar |
| Modify | `src/edu_cloud/api/app.py` | 注册 capability_router + audit_router + lifespan 导入 + current_user_var 中间件 |
| Modify | `src/edu_cloud/services/school_settings_service.py` | 给 upsert_setting / set_module_enabled 加 @audited |
| Modify | `src/edu_cloud/services/teacher_assignment_service.py` | 给 create/delete 加 @audited + list_assignments 示范 ScopeFilter |
| Modify | `src/edu_cloud/services/subject_selection_service.py` | 给 create/update/delete 加 @audited |
| Modify | `alembic/env.py` | 导入新模型 |
| Modify | `tests/conftest.py` | 导入新模型 |
| Modify | `tests/test_alembic_migration.py` | 导入新模型 |
| Modify | `CLAUDE.md` | 同步 API 端点 + 数据模型 |
| Create | `tests/test_services/test_capability_service.py` | Capability model + service 测试 |
| Create | `tests/test_api/test_capabilities.py` | Capability API 测试 |
| Create | `tests/test_services/test_scope_filter.py` | ScopeFilter 单元测试 |
| Create | `tests/test_services/test_audit_service.py` | @audited 装饰器 + 查询测试 |
| Create | `tests/test_api/test_audit_logs.py` | AuditLog API 测试 |

> **Note:** 每个 router 独立定义自己的 `_CROSS_SCHOOL_ROLES` set 和 `_check_school_scope` 函数（同模式，避免跨文件耦合）。

---

### Task 1: Capability Model

**Files:**
- Create: `src/edu_cloud/models/capability.py`
- Create: `tests/test_services/test_capability_service.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing model tests**

```python
# tests/test_services/test_capability_service.py
import pytest
from edu_cloud.models.capability import Capability, CAPABILITY_DOMAINS, CAPABILITY_ACTIONS


@pytest.mark.asyncio
async def test_capability_domains_contains_nine():
    assert len(CAPABILITY_DOMAINS) == 9
    assert "exam" in CAPABILITY_DOMAINS
    assert "system" in CAPABILITY_DOMAINS


@pytest.mark.asyncio
async def test_capability_actions():
    assert CAPABILITY_ACTIONS == {"read", "write"}


@pytest.mark.asyncio
async def test_capability_model(db, seed_school):
    school, _ = seed_school
    cap = Capability(
        school_id=school.id,
        role="principal",
        domain="exam",
        action="read",
        enabled=True,
    )
    db.add(cap)
    await db.commit()
    await db.refresh(cap)
    assert cap.id is not None
    assert cap.role == "principal"
    assert cap.domain == "exam"
    assert cap.action == "read"
    assert cap.enabled is True


@pytest.mark.asyncio
async def test_capability_unique_constraint(db, seed_school):
    from sqlalchemy.exc import IntegrityError

    school, _ = seed_school
    c1 = Capability(school_id=school.id, role="principal", domain="exam", action="read", enabled=True)
    c2 = Capability(school_id=school.id, role="principal", domain="exam", action="read", enabled=False)
    db.add(c1)
    await db.flush()
    db.add(c2)
    with pytest.raises(IntegrityError):
        await db.flush()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_capability_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.models.capability'`

- [ ] **Step 3: Implement model**

```python
# src/edu_cloud/models/capability.py
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


# 9 个域对齐 MODULE_CODES + system 管理域
CAPABILITY_DOMAINS = {
    "exam": "考试管理",
    "grading": "阅卷系统",
    "homework": "作业管理",
    "study_analytics": "学情分析",
    "research": "教研题库",
    "teaching": "教学管理",
    "calendar": "校历日程",
    "studio": "文档中心",
    "system": "系统管理",
}

CAPABILITY_ACTIONS = {"read", "write"}


class Capability(Base, IdMixin, TimestampMixin):
    """学校级角色能力配置：域×操作×角色。"""
    __tablename__ = "capabilities"
    __table_args__ = (
        UniqueConstraint("school_id", "role", "domain", "action",
                         name="uq_capability"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    role: Mapped[str] = mapped_column(String(50))
    domain: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: Update conftest.py to import the new model**

In `tests/conftest.py`, add after the `import edu_cloud.models.subject_selection` line:

```python
import edu_cloud.models.capability  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_capability_service.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/models/capability.py tests/test_services/test_capability_service.py tests/conftest.py
git commit -m "feat: add Capability model with domain/action/role"
```

**审查清单:**
- ✓ UniqueConstraint 防止同学校同角色同域同操作重复
- ✓ ForeignKey 关联 schools
- ✓ CAPABILITY_DOMAINS 包含 9 个域（8 MODULE_CODES + system）
- ✓ CAPABILITY_ACTIONS 只含 read/write
- ✓ enabled 默认 True
- ✗ 插入 domain 不在 CAPABILITY_DOMAINS 中 → DB 层允许（service 层校验）

**边界条件:**
- 同 school_id + role + domain + action 重复插入 → IntegrityError（已测试）
- 不同 school_id 相同其他字段 → 允许（不同学校独立配置）
- enabled 默认 True

---

### Task 2: Capability Service

**Files:**
- Create: `src/edu_cloud/services/capability_service.py`
- Modify: `tests/test_services/test_capability_service.py` (追加)

- [ ] **Step 1: Write failing service tests**

追加到 `tests/test_services/test_capability_service.py`:

```python
from edu_cloud.services.capability_service import (
    init_school_capabilities, get_capabilities, set_capability, check_capability,
    DEFAULT_CAPABILITIES,
)


@pytest.mark.asyncio
async def test_default_capabilities_template():
    """DEFAULT_CAPABILITIES 包含 6 个角色模板。"""
    assert "principal" in DEFAULT_CAPABILITIES
    assert "academic_director" in DEFAULT_CAPABILITIES
    assert "grade_leader" in DEFAULT_CAPABILITIES
    assert "homeroom_teacher" in DEFAULT_CAPABILITIES
    assert "subject_teacher" in DEFAULT_CAPABILITIES
    assert "parent" in DEFAULT_CAPABILITIES
    # platform_admin/district_admin 不在模板中
    assert "platform_admin" not in DEFAULT_CAPABILITIES
    assert "district_admin" not in DEFAULT_CAPABILITIES


@pytest.mark.asyncio
async def test_init_school_capabilities(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    caps = await get_capabilities(db, school_id=school.id)
    assert len(caps) > 0
    # principal 应该有全域 read+write
    principal_caps = [c for c in caps if c.role == "principal"]
    assert len(principal_caps) == 18  # 9 domains × 2 actions
    assert all(c.enabled for c in principal_caps)


@pytest.mark.asyncio
async def test_init_school_capabilities_idempotent(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    count1 = len(await get_capabilities(db, school_id=school.id))
    await init_school_capabilities(db, school_id=school.id)
    count2 = len(await get_capabilities(db, school_id=school.id))
    assert count1 == count2


@pytest.mark.asyncio
async def test_get_capabilities_filter_by_role(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    parent_caps = await get_capabilities(db, school_id=school.id, role="parent")
    # parent: study_analytics read only = 1
    assert len(parent_caps) == 1
    assert parent_caps[0].domain == "study_analytics"
    assert parent_caps[0].action == "read"


@pytest.mark.asyncio
async def test_set_capability(db, seed_school):
    school, _ = seed_school
    await init_school_capabilities(db, school_id=school.id)
    # Disable principal exam.write
    cap = await set_capability(
        db, school_id=school.id, role="principal",
        domain="exam", action="write", enabled=False,
    )
    assert cap.enabled is False
    # Verify it persisted
    result = await check_capability(
        db, school_id=school.id, role="principal", domain="exam", action="write",
    )
    assert result is False


@pytest.mark.asyncio
async def test_check_capability_no_record_default_allow(db, seed_school):
    """无记录 = 默认允许（宽松策略）。"""
    school, _ = seed_school
    # Don't init → no rows → should default allow
    result = await check_capability(
        db, school_id=school.id, role="principal", domain="exam", action="read",
    )
    assert result is True


@pytest.mark.asyncio
async def test_check_capability_explicit_false(db, seed_school):
    """显式 enabled=False → 拒绝。"""
    school, _ = seed_school
    await set_capability(
        db, school_id=school.id, role="subject_teacher",
        domain="system", action="write", enabled=False,
    )
    result = await check_capability(
        db, school_id=school.id, role="subject_teacher", domain="system", action="write",
    )
    assert result is False


@pytest.mark.asyncio
async def test_set_capability_invalid_domain(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError

    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的域"):
        await set_capability(
            db, school_id=school.id, role="principal",
            domain="nonexistent", action="read", enabled=True,
        )


@pytest.mark.asyncio
async def test_set_capability_invalid_action(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError

    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的操作"):
        await set_capability(
            db, school_id=school.id, role="principal",
            domain="exam", action="execute", enabled=True,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_capability_service.py::test_init_school_capabilities -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement service**

```python
# src/edu_cloud/services/capability_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.capability import Capability, CAPABILITY_DOMAINS, CAPABILITY_ACTIONS
from edu_cloud.services.exceptions import ValidationError


# 默认模板: role → {domain: {action: enabled}}
# platform_admin / district_admin 不生成 capability 行（跳过检查）
DEFAULT_CAPABILITIES: dict[str, dict[str, dict[str, bool]]] = {
    "principal": {
        domain: {"read": True, "write": True}
        for domain in CAPABILITY_DOMAINS
    },
    "academic_director": {
        domain: {
            "read": True,
            "write": True if domain != "system" else False,
        }
        for domain in CAPABILITY_DOMAINS
    },
    "grade_leader": {
        domain: actions
        for domain, actions in [
            ("exam", {"read": True}),
            ("grading", {"read": True}),
            ("study_analytics", {"read": True}),
            ("studio", {"read": True}),
            ("calendar", {"read": True}),
        ]
    },
    "homeroom_teacher": {
        domain: actions
        for domain, actions in [
            ("exam", {"read": True, "write": True}),
            ("grading", {"read": True, "write": True}),
            ("study_analytics", {"read": True}),
            ("calendar", {"read": True}),
            ("studio", {"read": True}),
        ]
    },
    "subject_teacher": {
        domain: actions
        for domain, actions in [
            ("exam", {"read": True, "write": True}),
            ("grading", {"read": True, "write": True}),
            ("study_analytics", {"read": True}),
            ("research", {"read": True}),
        ]
    },
    "parent": {
        "study_analytics": {"read": True},
    },
}


async def init_school_capabilities(
    db: AsyncSession, *, school_id: str,
) -> None:
    """按默认模板批量创建 capability 行（幂等）。"""
    for role, domains in DEFAULT_CAPABILITIES.items():
        for domain, actions in domains.items():
            for action, enabled in actions.items():
                existing = (await db.execute(
                    select(Capability).where(
                        Capability.school_id == school_id,
                        Capability.role == role,
                        Capability.domain == domain,
                        Capability.action == action,
                    )
                )).scalar_one_or_none()
                if not existing:
                    db.add(Capability(
                        school_id=school_id,
                        role=role,
                        domain=domain,
                        action=action,
                        enabled=enabled,
                    ))
    await db.commit()


async def get_capabilities(
    db: AsyncSession, *, school_id: str, role: str | None = None,
) -> list[Capability]:
    stmt = select(Capability).where(Capability.school_id == school_id)
    if role:
        stmt = stmt.where(Capability.role == role)
    result = await db.execute(stmt.order_by(Capability.role, Capability.domain, Capability.action))
    return list(result.scalars().all())


async def set_capability(
    db: AsyncSession, *, school_id: str, role: str,
    domain: str, action: str, enabled: bool,
) -> Capability:
    if domain not in CAPABILITY_DOMAINS:
        raise ValidationError(f"无效的域: {domain}")
    if action not in CAPABILITY_ACTIONS:
        raise ValidationError(f"无效的操作: {action}")
    stmt = select(Capability).where(
        Capability.school_id == school_id,
        Capability.role == role,
        Capability.domain == domain,
        Capability.action == action,
    )
    cap = (await db.execute(stmt)).scalar_one_or_none()
    if cap:
        cap.enabled = enabled
    else:
        cap = Capability(
            school_id=school_id, role=role,
            domain=domain, action=action, enabled=enabled,
        )
        db.add(cap)
    await db.commit()
    await db.refresh(cap)
    return cap


async def check_capability(
    db: AsyncSession, *, school_id: str, role: str,
    domain: str, action: str,
) -> bool:
    """检查角色在指定域的操作权限。无记录 = 默认允许（宽松策略）。"""
    stmt = select(Capability).where(
        Capability.school_id == school_id,
        Capability.role == role,
        Capability.domain == domain,
        Capability.action == action,
    )
    cap = (await db.execute(stmt)).scalar_one_or_none()
    if cap is None:
        return True  # 宽松策略：无记录默认允许
    return cap.enabled
```

- [ ] **Step 4: Run all service tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_capability_service.py -v`
Expected: 14 passed (4 model + 10 service)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/capability_service.py tests/test_services/test_capability_service.py
git commit -m "feat: add capability service with init/get/set/check + lenient policy"
```

**审查清单:**
- ✓ init_school_capabilities 幂等（已存在不重复创建）
- ✓ check_capability 无记录默认允许（宽松策略）
- ✓ check_capability 显式 enabled=False 返回 False
- ✓ set_capability 校验 domain 和 action
- ✓ DEFAULT_CAPABILITIES 包含 6 个角色，不含 platform_admin/district_admin
- ✗ 无效 domain/action → ValidationError

**边界条件:**
- 空数据库（无 capability 行）→ check_capability 返回 True（宽松策略）
- init 后再 init → 行数不变
- set_capability 对不存在的行 → 创建新行

**测试契约:**
1. 宽松策略验证
   - 入口: `check_capability(db, school_id=X, role="principal", domain="exam", action="read")` 无任何行
   - 反例: 错误实现无记录时返回 False → 未初始化学校被全面封锁
   - 边界: 无行 / 有行且 enabled=True / 有行且 enabled=False
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_capability_service.py::test_check_capability_no_record_default_allow -v`
2. 初始化幂等性
   - 入口: `init_school_capabilities(db, school_id=X)` 调用两次
   - 反例: 错误实现不检查已存在 → IntegrityError 或重复行
   - 边界: 空 / 已初始化 / 部分初始化
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_capability_service.py::test_init_school_capabilities_idempotent -v`
3. 无效输入拒绝
   - 入口: `set_capability(db, ..., domain="nonexistent", action="read", enabled=True)`
   - 反例: 错误实现不校验 → 垃圾数据入库
   - 边界: 无效 domain / 无效 action / 有效 domain+action
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_capability_service.py::test_set_capability_invalid_domain -v`

---

### Task 3: Capability API

**Files:**
- Create: `src/edu_cloud/modules/school/capability_router.py`
- Modify: `src/edu_cloud/api/app.py`
- Create: `tests/test_api/test_capabilities.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_api/test_capabilities.py
import pytest


@pytest.mark.asyncio
async def test_init_capabilities(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/capabilities/init",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_init_capabilities_idempotent(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_capabilities(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.get(f"/api/v1/schools/{school.id}/capabilities", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    assert "role" in data[0]
    assert "domain" in data[0]
    assert "action" in data[0]
    assert "enabled" in data[0]


@pytest.mark.asyncio
async def test_get_capabilities_filter_role(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.get(
        f"/api/v1/schools/{school.id}/capabilities?role=parent",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["role"] == "parent"
    assert data[0]["domain"] == "study_analytics"


@pytest.mark.asyncio
async def test_patch_capability(client, admin_headers, seed_school):
    school, _ = seed_school
    await client.post(f"/api/v1/schools/{school.id}/capabilities/init", headers=admin_headers)
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/capabilities",
        json={"role": "principal", "domain": "exam", "action": "write", "enabled": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    # Verify persisted
    resp = await client.get(
        f"/api/v1/schools/{school.id}/capabilities?role=principal",
        headers=admin_headers,
    )
    data = resp.json()
    exam_write = [c for c in data if c["domain"] == "exam" and c["action"] == "write"]
    assert len(exam_write) == 1
    assert exam_write[0]["enabled"] is False


@pytest.mark.asyncio
async def test_patch_capability_invalid_domain(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/capabilities",
        json={"role": "principal", "domain": "nonexistent", "action": "read", "enabled": True},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_capabilities_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/capabilities")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_capabilities_scope_guard(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="能力A校", code="CAP_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="能力B校", code="CAP_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="cap_scope_test", display_name="跨校测试")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "cap_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/capabilities", headers=headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_capabilities.py::test_init_capabilities -v`
Expected: FAIL — 404 (routes not registered)

- [ ] **Step 3: Implement router**

```python
# src/edu_cloud/modules/school/capability_router.py
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.capability_service import (
    init_school_capabilities, get_capabilities, set_capability,
)
from edu_cloud.services.exceptions import ValidationError, PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["capabilities"])

_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in _CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的能力配置")


class PatchCapabilityRequest(BaseModel):
    role: str
    domain: str
    action: str
    enabled: bool


@router.get("/capabilities")
async def api_get_capabilities(
    school_id: str,
    role: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    caps = await get_capabilities(db, school_id=school_id, role=role)
    return [
        {
            "id": c.id, "role": c.role, "domain": c.domain,
            "action": c.action, "enabled": c.enabled,
        }
        for c in caps
    ]


@router.patch("/capabilities")
async def api_patch_capability(
    school_id: str,
    body: PatchCapabilityRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    cap = await set_capability(
        db, school_id=school_id, role=body.role,
        domain=body.domain, action=body.action, enabled=body.enabled,
    )
    return {
        "id": cap.id, "role": cap.role, "domain": cap.domain,
        "action": cap.action, "enabled": cap.enabled,
    }


@router.post("/capabilities/init")
async def api_init_capabilities(
    school_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await init_school_capabilities(db, school_id=school_id)
    return {"ok": True}
```

- [ ] **Step 4: Register router in app.py**

In `src/edu_cloud/api/app.py`:

1. In the lifespan model imports block, add after `import edu_cloud.models.subject_selection`:
```python
    import edu_cloud.models.capability  # noqa: F401
```

2. In the router import section, add after the selection_router import:
```python
    from edu_cloud.modules.school.capability_router import router as capability_router
```

3. Add `capability_router` to the `for r in [...]` loop list (after `selection_router`).

- [ ] **Step 5: Run API tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_capabilities.py -v`
Expected: 8 passed

- [ ] **Step 6: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass + 8 new

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/school/capability_router.py src/edu_cloud/api/app.py tests/test_api/test_capabilities.py
git commit -m "feat: add capability API with scope guard + 8 tests"
```

**审查清单:**
- ✓ `require_permission(Permission.MANAGE_SCHOOL_SETTINGS)` 保护所有端点
- ✓ `_check_school_scope` 跨校防护
- ✓ PATCH 校验 domain/action 有效性（service 层 ValidationError → 422）
- ✓ POST /init 幂等
- ✓ GET 支持 role 过滤
- ✗ 未认证请求 → 401/403
- ✗ 跨校访问 → 403

**边界条件:**
- 未初始化时 GET → 空列表
- PATCH 不存在的 role+domain+action → 创建新行
- 无效 domain → 422

**测试契约:**
1. 跨校越权拦截
   - 入口: principal of school A → `GET /api/v1/schools/{school_b}/capabilities`
   - 反例: 错误实现不检查 school scope → 返回 200
   - 边界: platform_admin 可跨校 / principal 不能
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_capabilities.py::test_capabilities_scope_guard -v`
2. 无效域名拒绝
   - 入口: `PATCH /api/v1/schools/{id}/capabilities` body `{"domain": "nonexistent", ...}`
   - 反例: 错误实现不校验 → 垃圾数据入库
   - 边界: 无效 domain / 无效 action / 有效组合
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_capabilities.py::test_patch_capability_invalid_domain -v`

---

### Task 4: ScopeFilter

**Files:**
- Create: `src/edu_cloud/core/scope_filter.py`
- Create: `tests/test_services/test_scope_filter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_scope_filter.py
import pytest
from sqlalchemy import select

from edu_cloud.core.scope_filter import ScopeFilter
from edu_cloud.models.teacher_assignment import TeacherAssignment
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.user import User
from edu_cloud.modules.student.models import Class


async def _seed_scope_data(db, school_id):
    """Helper: create teacher + 2 classes + 2 assignments with different subjects."""
    user = User(username="scope_teacher", display_name="Scope教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls_a = Class(name="Scope1班", grade="高三", grade_number=12, school_id=school_id)
    cls_b = Class(name="Scope2班", grade="高三", grade_number=12, school_id=school_id)
    db.add(cls_a)
    db.add(cls_b)
    await db.flush()
    a1 = TeacherAssignment(
        user_id=user.id, class_id=cls_a.id,
        subject_code="math", semester="2025-2026-2", school_id=school_id,
    )
    a2 = TeacherAssignment(
        user_id=user.id, class_id=cls_b.id,
        subject_code="english", semester="2025-2026-2", school_id=school_id,
    )
    db.add(a1)
    db.add(a2)
    await db.commit()
    return user, [cls_a, cls_b], [a1, a2]


@pytest.mark.asyncio
async def test_scope_filter_school_id(db, seed_school):
    from edu_cloud.models.school import School
    import bcrypt

    school, _ = seed_school
    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    other_school = School(name="其他校", code="OTHER_SF", district="测试区", api_key_hash=hashed)
    db.add(other_school)
    await db.flush()

    user, classes, assignments = await _seed_scope_data(db, school.id)
    # Create assignment in other school
    other_cls = Class(name="OtherClass", grade="高一", grade_number=10, school_id=other_school.id)
    db.add(other_cls)
    await db.flush()
    db.add(TeacherAssignment(
        user_id=user.id, class_id=other_cls.id,
        subject_code="math", semester="2025-2026-2", school_id=other_school.id,
    ))
    await db.commit()

    # ScopeFilter for school should only return school's assignments
    role = UserRole(user_id=user.id, role="subject_teacher", school_id=school.id)
    sf = ScopeFilter(role)
    stmt = select(TeacherAssignment)
    stmt = sf.apply(stmt, TeacherAssignment)
    result = (await db.execute(stmt)).scalars().all()
    assert len(result) == 2
    assert all(r.school_id == school.id for r in result)


@pytest.mark.asyncio
async def test_scope_filter_class_ids(db, seed_school):
    school, _ = seed_school
    user, classes, assignments = await _seed_scope_data(db, school.id)

    role = UserRole(
        user_id=user.id, role="homeroom_teacher",
        school_id=school.id, class_ids=[classes[0].id],
    )
    sf = ScopeFilter(role)
    stmt = select(TeacherAssignment)
    stmt = sf.apply(stmt, TeacherAssignment, class_col="class_id")
    result = (await db.execute(stmt)).scalars().all()
    assert len(result) == 1
    assert result[0].class_id == classes[0].id


@pytest.mark.asyncio
async def test_scope_filter_subject_codes(db, seed_school):
    school, _ = seed_school
    user, classes, assignments = await _seed_scope_data(db, school.id)

    role = UserRole(
        user_id=user.id, role="subject_teacher",
        school_id=school.id, subject_codes=["math"],
    )
    sf = ScopeFilter(role)
    stmt = select(TeacherAssignment)
    stmt = sf.apply(stmt, TeacherAssignment, subject_col="subject_code")
    result = (await db.execute(stmt)).scalars().all()
    assert len(result) == 1
    assert result[0].subject_code == "math"


@pytest.mark.asyncio
async def test_scope_filter_none_scope_skips(db, seed_school):
    school, _ = seed_school
    user, classes, assignments = await _seed_scope_data(db, school.id)

    # Role with no class_ids / subject_codes → don't filter those
    role = UserRole(
        user_id=user.id, role="principal",
        school_id=school.id,
    )
    sf = ScopeFilter(role)
    stmt = select(TeacherAssignment)
    stmt = sf.apply(stmt, TeacherAssignment, class_col="class_id", subject_col="subject_code")
    result = (await db.execute(stmt)).scalars().all()
    # school_id filter only, should get both
    assert len(result) == 2


@pytest.mark.asyncio
async def test_scope_filter_from_role_admin():
    """platform_admin 没有 school_id → from_role 返回 None。"""
    role = UserRole(user_id="fake", role="platform_admin")
    sf = ScopeFilter.from_role(role)
    assert sf is None


@pytest.mark.asyncio
async def test_scope_filter_from_role_teacher():
    """school-scoped 角色 → from_role 返回 ScopeFilter。"""
    role = UserRole(
        user_id="fake", role="subject_teacher",
        school_id="school-123", subject_codes=["math"],
    )
    sf = ScopeFilter.from_role(role)
    assert sf is not None
    assert sf.school_id == "school-123"
    assert sf.subject_codes == ["math"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_scope_filter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.core.scope_filter'`

- [ ] **Step 3: Implement ScopeFilter**

```python
# src/edu_cloud/core/scope_filter.py
from __future__ import annotations

from edu_cloud.models.user_role import UserRole


class ScopeFilter:
    """基于 UserRole 的 scope 自动注入 WHERE 条件。"""

    def __init__(self, role: UserRole):
        self.school_id = role.school_id
        self.grade_ids = role.grade_ids
        self.class_ids = role.class_ids
        self.subject_codes = role.subject_codes

    def apply(self, stmt, model, *, school_col="school_id",
              class_col=None, grade_col=None, subject_col=None):
        """追加过滤条件。school_id 始终追加（非 None 时）；
        grade/class/subject 有 scope 值且 model 有对应列时才追加。"""
        if self.school_id:
            stmt = stmt.where(getattr(model, school_col) == self.school_id)
        if self.class_ids and class_col:
            stmt = stmt.where(getattr(model, class_col).in_(self.class_ids))
        if self.grade_ids and grade_col:
            stmt = stmt.where(getattr(model, grade_col).in_(self.grade_ids))
        if self.subject_codes and subject_col:
            stmt = stmt.where(getattr(model, subject_col).in_(self.subject_codes))
        return stmt

    @classmethod
    def from_role(cls, role) -> ScopeFilter | None:
        """platform_admin/district_admin 等无 school_id 的角色返回 None（不过滤）。"""
        if not role or not role.school_id:
            return None
        return cls(role)
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_scope_filter.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/core/scope_filter.py tests/test_services/test_scope_filter.py
git commit -m "feat: add ScopeFilter utility for role-based query filtering"
```

**审查清单:**
- ✓ school_id 始终过滤（非 None 时）
- ✓ class_ids/grade_ids/subject_codes 有值且指定了 col 参数时才过滤
- ✓ None scope 值跳过对应过滤
- ✓ from_role 对 platform_admin/district_admin 返回 None
- ✗ model 无指定列 → AttributeError（调用方责任）

**边界条件:**
- school_id=None → 不追加 school 过滤
- class_ids=[] → falsy，不追加 class 过滤
- class_ids=[X] 且 class_col=None → 不追加（col 未指定）
- from_role(None) → None

**测试契约:**
1. school 隔离
   - 入口: `ScopeFilter(role_with_school_A).apply(stmt, TeacherAssignment)`
   - 反例: 错误实现不追加 school_id WHERE → 返回全部学校数据
   - 边界: 单校 / 多校 / school_id=None
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_scope_filter.py::test_scope_filter_school_id -v`
2. None scope 跳过
   - 入口: `ScopeFilter(role_with_no_class_ids).apply(stmt, model, class_col="class_id")`
   - 反例: 错误实现把 None 传给 .in_() → SQL 错误或空结果
   - 边界: class_ids=None / [] / [X]
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_scope_filter.py::test_scope_filter_none_scope_skips -v`

---

### Task 5: ScopeFilter Demonstration

**Files:**
- Modify: `src/edu_cloud/services/teacher_assignment_service.py`
- Modify: `tests/test_services/test_teacher_assignment_service.py` (追加)

- [ ] **Step 1: Write failing test**

追加到 `tests/test_services/test_teacher_assignment_service.py`:

```python
from edu_cloud.core.scope_filter import ScopeFilter
from edu_cloud.models.user_role import UserRole


@pytest.mark.asyncio
async def test_list_assignments_with_scope(db, seed_school):
    school, _ = seed_school
    user, classes = await _seed_teacher_and_classes(db, school.id)
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[classes[0].id], subject_code="math", semester="2025-2026-2",
    )
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[classes[1].id], subject_code="english", semester="2025-2026-2",
    )

    # Create a scope that only sees math
    role = UserRole(
        user_id=user.id, role="subject_teacher",
        school_id=school.id, subject_codes=["math"],
    )
    scope = ScopeFilter(role)
    rows = await list_assignments(db, school_id=school.id, scope=scope)
    assert len(rows) == 1
    assert rows[0].subject_code == "math"


@pytest.mark.asyncio
async def test_list_assignments_without_scope(db, seed_school):
    """scope=None 不过滤（向后兼容）。"""
    school, _ = seed_school
    user, classes = await _seed_teacher_and_classes(db, school.id)
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[classes[0].id], subject_code="math", semester="2025-2026-2",
    )
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[classes[1].id], subject_code="english", semester="2025-2026-2",
    )
    rows = await list_assignments(db, school_id=school.id, scope=None)
    assert len(rows) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py::test_list_assignments_with_scope -v`
Expected: FAIL — `TypeError: list_assignments() got an unexpected keyword argument 'scope'`

- [ ] **Step 3: Modify list_assignments**

In `src/edu_cloud/services/teacher_assignment_service.py`, change `list_assignments` signature and body:

```python
from edu_cloud.core.scope_filter import ScopeFilter


async def list_assignments(
    db: AsyncSession, *, school_id: str,
    semester: str | None = None, user_id: str | None = None,
    class_id: str | None = None, subject_code: str | None = None,
    scope: ScopeFilter | None = None,
) -> list[TeacherAssignment]:
    stmt = select(TeacherAssignment).where(TeacherAssignment.school_id == school_id)
    if semester:
        stmt = stmt.where(TeacherAssignment.semester == semester)
    if user_id:
        stmt = stmt.where(TeacherAssignment.user_id == user_id)
    if class_id:
        stmt = stmt.where(TeacherAssignment.class_id == class_id)
    if subject_code:
        stmt = stmt.where(TeacherAssignment.subject_code == subject_code)
    if scope:
        stmt = scope.apply(stmt, TeacherAssignment, subject_col="subject_code")
    result = await db.execute(stmt.order_by(TeacherAssignment.created_at))
    return list(result.scalars().all())
```

- [ ] **Step 4: Run all teacher assignment tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py -v`
Expected: All pass (existing + 2 new)

- [ ] **Step 5: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass (ScopeFilter is additive, default scope=None doesn't change existing behavior)

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/services/teacher_assignment_service.py tests/test_services/test_teacher_assignment_service.py
git commit -m "feat: demonstrate ScopeFilter integration in list_assignments"
```

**审查清单:**
- ✓ scope 参数是 Optional，默认 None（向后兼容）
- ✓ scope=None 不追加任何过滤
- ✓ scope 存在时追加 subject_code 过滤
- ✓ 既有测试不受影响（scope 参数有默认值）
- ✗ scope 与显式 subject_code 参数同时存在 → 两个条件叠加（AND），符合预期

**边界条件:**
- scope=None → 行为与之前完全一致
- scope 有 subject_codes=["math"] → 只返回 math
- scope 有 subject_codes=["math"] 且 subject_code="english" → 空结果（AND 叠加）

**测试契约:**
1. ScopeFilter 集成
   - 入口: `list_assignments(db, school_id=X, scope=ScopeFilter(role_with_subject_codes=["math"]))`
   - 反例: 错误实现忽略 scope → 返回全部
   - 边界: scope=None / scope 有值 / scope+显式参数叠加
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py::test_list_assignments_with_scope -v`
2. 向后兼容
   - 入口: `list_assignments(db, school_id=X)` 不传 scope
   - 反例: 错误实现改变了无 scope 时的行为 → 既有调用方出错
   - 边界: 不传 scope / scope=None
   - 回归: Phase 1b 排课列表功能
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py::test_list_assignments_filter -v`

---

### Task 6: AuditLog Model + @audited Decorator

**Files:**
- Create: `src/edu_cloud/models/audit_log.py`
- Create: `src/edu_cloud/services/audit_service.py`
- Modify: `src/edu_cloud/logging_config.py`
- Modify: `src/edu_cloud/api/app.py`
- Create: `tests/test_services/test_audit_service.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_audit_service.py
import pytest
from edu_cloud.models.audit_log import AuditLog
from edu_cloud.logging_config import current_user_var, request_id_var


@pytest.mark.asyncio
async def test_audit_log_model(db, seed_school):
    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="audit_user", display_name="审计测试")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    log = AuditLog(
        school_id=school.id,
        user_id=user.id,
        entity_type="school_setting",
        entity_id="fake-entity-id",
        action="create",
        before_data=None,
        after_data={"key": "test", "value": "hello"},
        request_id="req-12345",
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    assert log.id is not None
    assert log.entity_type == "school_setting"
    assert log.after_data == {"key": "test", "value": "hello"}
    assert log.request_id == "req-12345"


@pytest.mark.asyncio
async def test_write_audit_log(db, seed_school):
    from edu_cloud.services.audit_service import write_audit_log

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="wal_user", display_name="写审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    await write_audit_log(
        db,
        school_id=school.id,
        user_id=user.id,
        entity_type="teacher_assignment",
        entity_id="ent-123",
        action="create",
        before_data=None,
        after_data={"user_id": "u1", "class_id": "c1"},
    )

    from sqlalchemy import select
    logs = (await db.execute(select(AuditLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].action == "create"
    assert logs[0].after_data == {"user_id": "u1", "class_id": "c1"}


@pytest.mark.asyncio
async def test_list_audit_logs(db, seed_school):
    from edu_cloud.services.audit_service import write_audit_log, list_audit_logs

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="list_audit_user", display_name="列审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    await write_audit_log(
        db, school_id=school.id, user_id=user.id,
        entity_type="school_setting", entity_id="e1", action="create",
    )
    await write_audit_log(
        db, school_id=school.id, user_id=user.id,
        entity_type="teacher_assignment", entity_id="e2", action="delete",
    )

    # All logs
    logs = await list_audit_logs(db, school_id=school.id)
    assert len(logs) == 2

    # Filter by entity_type
    logs = await list_audit_logs(db, school_id=school.id, entity_type="school_setting")
    assert len(logs) == 1
    assert logs[0].entity_type == "school_setting"

    # Filter by action
    logs = await list_audit_logs(db, school_id=school.id, action="delete")
    assert len(logs) == 1
    assert logs[0].action == "delete"

    # Filter by user_id
    logs = await list_audit_logs(db, school_id=school.id, user_id=user.id)
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_list_audit_logs_pagination(db, seed_school):
    from edu_cloud.services.audit_service import write_audit_log, list_audit_logs

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="page_audit_user", display_name="分页审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    for i in range(5):
        await write_audit_log(
            db, school_id=school.id, user_id=user.id,
            entity_type="school_setting", entity_id=f"e{i}", action="create",
        )

    logs = await list_audit_logs(db, school_id=school.id, limit=2, offset=0)
    assert len(logs) == 2

    logs = await list_audit_logs(db, school_id=school.id, limit=2, offset=3)
    assert len(logs) == 2


@pytest.mark.asyncio
async def test_audited_decorator_create(db, seed_school):
    """@audited 装饰器: create 操作 → before=None, after=快照。"""
    from edu_cloud.services.audit_service import audited
    from sqlalchemy import select

    school, _ = seed_school

    from edu_cloud.models.user import User
    user = User(username="dec_create_user", display_name="装饰器创建")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    # Set up ContextVars
    token_user = current_user_var.set(user.id)
    token_req = request_id_var.set("req-create-test")

    try:
        @audited("test_entity", action="create")
        async def fake_create(db, *, school_id, name):
            from edu_cloud.models.school_settings import SchoolSetting
            s = SchoolSetting(school_id=school_id, category="test", key=name, value="v1")
            db.add(s)
            await db.commit()
            await db.refresh(s)
            return s

        result = await fake_create(db, school_id=school.id, name="dec_test")
        assert result is not None

        logs = (await db.execute(select(AuditLog))).scalars().all()
        assert len(logs) == 1
        assert logs[0].action == "create"
        assert logs[0].before_data is None
        assert logs[0].after_data is not None
        assert logs[0].user_id == user.id
        assert logs[0].request_id == "req-create-test"
    finally:
        current_user_var.reset(token_user)
        request_id_var.reset(token_req)


@pytest.mark.asyncio
async def test_audited_decorator_delete(db, seed_school):
    """@audited 装饰器: delete 操作 → before=快照, after=None。"""
    from edu_cloud.services.audit_service import audited
    from edu_cloud.models.school_settings import SchoolSetting
    from sqlalchemy import select

    school, _ = seed_school

    from edu_cloud.models.user import User
    user = User(username="dec_delete_user", display_name="装饰器删除")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    setting = SchoolSetting(school_id=school.id, category="test", key="del_key", value="v1")
    db.add(setting)
    await db.commit()
    await db.refresh(setting)

    token_user = current_user_var.set(user.id)
    token_req = request_id_var.set("req-delete-test")

    try:
        @audited("school_setting", action="delete", id_param="setting_id")
        async def fake_delete(db, *, school_id, setting_id):
            s = (await db.execute(
                select(SchoolSetting).where(SchoolSetting.id == setting_id)
            )).scalar_one()
            await db.delete(s)
            await db.commit()
            return None

        await fake_delete(db, school_id=school.id, setting_id=setting.id)

        logs = (await db.execute(select(AuditLog))).scalars().all()
        assert len(logs) == 1
        assert logs[0].action == "delete"
        assert logs[0].before_data is not None
        assert logs[0].after_data is None
        assert logs[0].entity_id == setting.id
    finally:
        current_user_var.reset(token_user)
        request_id_var.reset(token_req)


@pytest.mark.asyncio
async def test_audited_decorator_no_user_context(db, seed_school):
    """ContextVar 未设置时 user_id 为 '-' 但不崩溃。"""
    from edu_cloud.services.audit_service import audited
    from sqlalchemy import select

    school, _ = seed_school

    @audited("test_entity", action="create")
    async def fake_create_no_user(db, *, school_id):
        from edu_cloud.models.school_settings import SchoolSetting
        s = SchoolSetting(school_id=school_id, category="test", key="nouser", value="v1")
        db.add(s)
        await db.commit()
        await db.refresh(s)
        return s

    result = await fake_create_no_user(db, school_id=school.id)
    assert result is not None

    logs = (await db.execute(select(AuditLog))).scalars().all()
    assert len(logs) == 1
    assert logs[0].user_id == "-"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py::test_audit_log_model -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement AuditLog model**

```python
# src/edu_cloud/models/audit_log.py
from sqlalchemy import String, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AuditLog(Base, IdMixin, TimestampMixin):
    """实体变更审计日志。"""
    __tablename__ = "audit_logs"

    school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("schools.id"), index=True, default=None, nullable=True,
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(20))
    before_data: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    after_data: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(50), default=None, nullable=True)
```

- [ ] **Step 4: Add current_user_var to logging_config.py**

In `src/edu_cloud/logging_config.py`, add after the `request_id_var` line:

```python
current_user_var: ContextVar[str] = ContextVar("current_user_id", default="-")
```

- [ ] **Step 5: Implement audit_service.py**

```python
# src/edu_cloud/services/audit_service.py
import functools
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.audit_log import AuditLog
from edu_cloud.logging_config import current_user_var, request_id_var

logger = logging.getLogger(__name__)


def _snapshot(obj) -> dict | None:
    """Extract a JSON-serializable snapshot from an ORM object."""
    if obj is None:
        return None
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        data[col.name] = val
    return data


async def write_audit_log(
    db: AsyncSession, *,
    school_id: str | None = None,
    user_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    before_data: dict | None = None,
    after_data: dict | None = None,
    request_id: str | None = None,
) -> AuditLog:
    log = AuditLog(
        school_id=school_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_data=before_data,
        after_data=after_data,
        request_id=request_id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def list_audit_logs(
    db: AsyncSession, *,
    school_id: str,
    entity_type: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.school_id == school_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if start_date:
        stmt = stmt.where(AuditLog.created_at >= start_date)
    if end_date:
        stmt = stmt.where(AuditLog.created_at <= end_date)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def audited(entity_type: str, *, action: str = "create", id_param: str = "entity_id"):
    """Service 层装饰器：自动记录 before/after 快照。

    被装饰函数需要:
    - 第一个位置参数是 db (AsyncSession)
    - keyword 参数中有 school_id
    - create: 返回 ORM 对象 → before=None, after=snapshot
    - delete: 可选 id_param kwarg → before=snapshot (先查), after=None
    - update: 可选 id_param kwarg → before=snapshot (先查), after=snapshot

    user_id 从 current_user_var ContextVar 获取。
    request_id 从 request_id_var ContextVar 获取。
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract db session (first positional arg)
            db = args[0] if args else kwargs.get("db")
            school_id = kwargs.get("school_id")
            user_id = current_user_var.get()
            req_id = request_id_var.get()

            before_snapshot = None
            entity_id_val = kwargs.get(id_param)

            # For update/delete: try to snapshot before
            if action in ("update", "delete") and entity_id_val and db:
                # We need to know the model type — infer from entity_type
                model_cls = _entity_type_to_model(entity_type)
                if model_cls:
                    old = await db.get(model_cls, entity_id_val)
                    before_snapshot = _snapshot(old)

            # Call the original function
            result = await func(*args, **kwargs)

            # Build after snapshot
            after_snapshot = _snapshot(result) if result is not None else None

            # Determine entity_id
            if result is not None and hasattr(result, "id"):
                eid = result.id
            elif entity_id_val:
                eid = entity_id_val
            else:
                eid = "-"

            # Write audit log (best-effort, don't crash the main operation)
            try:
                await write_audit_log(
                    db,
                    school_id=school_id,
                    user_id=user_id,
                    entity_type=entity_type,
                    entity_id=eid,
                    action=action,
                    before_data=before_snapshot,
                    after_data=after_snapshot,
                    request_id=req_id,
                )
            except Exception:
                logger.warning("Failed to write audit log", exc_info=True)

            return result
        return wrapper
    return decorator


def _entity_type_to_model(entity_type: str):
    """Map entity_type string to ORM model class (lazy import to avoid circular)."""
    mapping = {
        "school_setting": "edu_cloud.models.school_settings:SchoolSetting",
        "school_module": "edu_cloud.models.school_settings:SchoolModule",
        "teacher_assignment": "edu_cloud.models.teacher_assignment:TeacherAssignment",
        "subject_selection": "edu_cloud.models.subject_selection:SubjectSelection",
    }
    path = mapping.get(entity_type)
    if not path:
        return None
    module_path, class_name = path.split(":")
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name, None)
```

- [ ] **Step 6: Set current_user_var in app.py middleware**

In `src/edu_cloud/api/app.py`, modify the import line:

```python
from edu_cloud.logging_config import request_id_var, current_user_var, setup_logging
```

In the `request_logging` middleware, after setting `request_id_var`, add user extraction:

```python
    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        token = request_id_var.set(req_id)

        # Best-effort: extract user_id from JWT for audit logging
        user_token = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from edu_cloud.shared.auth import decode_token
                payload = decode_token(auth_header[7:])
                uid = payload.get("sub", "-")
                user_token = current_user_var.set(uid)
            except Exception:
                pass

        start = time.perf_counter()
        try:
            response = await call_next(request)
            ms = (time.perf_counter() - start) * 1000
            path = request.url.path
            if not path.startswith(("/docs", "/openapi", "/favicon")):
                log = logger.info if response.status_code < 400 else logger.warning
                log("%s %s → %d (%.0fms)", request.method, path, response.status_code, ms)
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            # Let registered Service exceptions propagate to FastAPI exception_handlers
            if isinstance(exc, (NotFoundError, PermissionDeniedError,
                                SvcValidationError, ConflictError, StateError)):
                raise
            # Truly unknown exceptions → 500
            ms = (time.perf_counter() - start) * 1000
            path = request.url.path
            logger.error("%s %s → 500 (%.0fms) unhandled exception", request.method, path, ms, exc_info=True)
            from starlette.responses import PlainTextResponse
            error_response = PlainTextResponse("Internal Server Error", status_code=500)
            error_response.headers["X-Request-ID"] = req_id
            return error_response
        finally:
            request_id_var.reset(token)
            if user_token:
                current_user_var.reset(user_token)
```

- [ ] **Step 7: Update conftest.py**

In `tests/conftest.py`, add after `import edu_cloud.models.capability`:

```python
import edu_cloud.models.audit_log  # noqa: F401
```

- [ ] **Step 8: In app.py lifespan, add model import**

After `import edu_cloud.models.capability`:

```python
    import edu_cloud.models.audit_log  # noqa: F401
```

- [ ] **Step 9: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py -v`
Expected: 8 passed

- [ ] **Step 10: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass + 8 new

- [ ] **Step 11: Commit**

```bash
git add src/edu_cloud/models/audit_log.py src/edu_cloud/services/audit_service.py src/edu_cloud/logging_config.py src/edu_cloud/api/app.py tests/test_services/test_audit_service.py tests/conftest.py
git commit -m "feat: add AuditLog model + @audited decorator + current_user_var"
```

**审查清单:**
- ✓ AuditLog 表含 school_id/user_id/entity_type/entity_id/action/before_data/after_data/request_id
- ✓ current_user_var ContextVar 在中间件中 best-effort 设置
- ✓ @audited create: before=None, after=snapshot
- ✓ @audited delete: before=snapshot, after=None
- ✓ @audited 无 user context 时 user_id="-" 不崩溃
- ✓ write_audit_log 直接写入
- ✓ list_audit_logs 支持 entity_type/user_id/action 过滤 + limit/offset 分页
- ✗ JWT 解析失败 → 静默跳过（best-effort）

**边界条件:**
- current_user_var 未设置 → user_id="-"
- 被装饰函数抛异常 → 异常正常冒泡，审计日志不写（函数未完成）
- before_data/after_data 为 None → 允许（create/delete 场景）
- list_audit_logs limit=0 → 返回空（SQL LIMIT 0）

**测试契约:**
1. create 审计记录
   - 入口: `@audited("test_entity", action="create")` 包装的函数
   - 反例: 错误实现不记录 after_data → 审计信息不完整
   - 边界: 返回 None / 返回 ORM 对象 / 有 user / 无 user
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py::test_audited_decorator_create -v`
2. delete 审计记录
   - 入口: `@audited("school_setting", action="delete", id_param="setting_id")` 包装的函数
   - 反例: 错误实现不查 before snapshot → before_data=None 丢失删前状态
   - 边界: entity 存在 / entity 不存在 / id_param 未传
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py::test_audited_decorator_delete -v`
3. 无 user context 安全
   - 入口: 不设 current_user_var → 调用 @audited 函数
   - 反例: 错误实现在 get() 时抛异常 → 整个请求崩溃
   - 边界: ContextVar 未设置 / 设为 "-" / 设为有效 user_id
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py::test_audited_decorator_no_user_context -v`

---

### Task 7: @audited Integration

**Files:**
- Modify: `src/edu_cloud/services/school_settings_service.py`
- Modify: `src/edu_cloud/services/teacher_assignment_service.py`
- Modify: `src/edu_cloud/services/subject_selection_service.py`
- Modify: `tests/test_services/test_audit_service.py` (追加集成测试)

- [ ] **Step 1: Write failing integration tests**

追加到 `tests/test_services/test_audit_service.py`:

```python
from edu_cloud.services import school_settings_service
from edu_cloud.services import teacher_assignment_service
from edu_cloud.services import subject_selection_service


@pytest.mark.asyncio
async def test_audited_upsert_setting(db, seed_school):
    """upsert_setting 加 @audited 后产生审计日志。"""
    from sqlalchemy import select

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="audit_settings_user", display_name="Settings审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    token_user = current_user_var.set(user.id)
    try:
        result = await school_settings_service.upsert_setting(
            db, school_id=school.id, category="test", key="audit_key", value="val1",
        )
        assert result.key == "audit_key"

        logs = (await db.execute(select(AuditLog))).scalars().all()
        setting_logs = [l for l in logs if l.entity_type == "school_setting"]
        assert len(setting_logs) >= 1
        assert setting_logs[0].action == "create"
    finally:
        current_user_var.reset(token_user)


@pytest.mark.asyncio
async def test_audited_create_assignments(db, seed_school):
    """create_assignments 加 @audited 后产生审计日志。"""
    from sqlalchemy import select
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    school, _ = seed_school
    user = User(username="audit_assign_user", display_name="Assignment审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = Class(name="审计测试班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.commit()

    token_user = current_user_var.set(user.id)
    try:
        count = await teacher_assignment_service.create_assignments(
            db, school_id=school.id, user_id=user.id,
            class_ids=[cls.id], subject_code="math", semester="2025-2026-2",
        )
        assert count == 1

        logs = (await db.execute(select(AuditLog))).scalars().all()
        assign_logs = [l for l in logs if l.entity_type == "teacher_assignment"]
        assert len(assign_logs) >= 1
        assert assign_logs[0].action == "create"
    finally:
        current_user_var.reset(token_user)


@pytest.mark.asyncio
async def test_audited_create_selection(db, seed_school):
    """create_selection 加 @audited 后产生审计日志。"""
    from sqlalchemy import select

    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="audit_sel_user", display_name="Selection审计")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    await db.commit()

    token_user = current_user_var.set(user.id)
    try:
        sel = await subject_selection_service.create_selection(
            db, school_id=school.id, name="审计理化生",
            subject_codes=["physics", "chemistry", "biology"], mode="custom",
        )
        assert sel.name == "审计理化生"

        logs = (await db.execute(select(AuditLog))).scalars().all()
        sel_logs = [l for l in logs if l.entity_type == "subject_selection"]
        assert len(sel_logs) >= 1
        assert sel_logs[0].action == "create"
    finally:
        current_user_var.reset(token_user)


@pytest.mark.asyncio
async def test_existing_settings_tests_still_pass(db, seed_school):
    """确认 @audited 不影响原有 service 返回值。"""
    school, _ = seed_school
    result = await school_settings_service.upsert_setting(
        db, school_id=school.id, category="test", key="compat_key", value="compat_val",
    )
    assert result.key == "compat_key"
    assert result.value == "compat_val"
```

- [ ] **Step 2: Run to verify they fail (upsert_setting not yet decorated)**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py::test_audited_upsert_setting -v`
Expected: FAIL — no audit_logs rows (function not decorated yet)

- [ ] **Step 3: Add @audited to school_settings_service.py**

In `src/edu_cloud/services/school_settings_service.py`:

Add import at top:
```python
from edu_cloud.services.audit_service import audited
```

Decorate `upsert_setting`:
```python
@audited("school_setting", action="create")
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
```

Decorate `set_module_enabled`:
```python
@audited("school_module", action="update", id_param="module_code")
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
```

- [ ] **Step 4: Add @audited to teacher_assignment_service.py**

In `src/edu_cloud/services/teacher_assignment_service.py`:

Add import at top:
```python
from edu_cloud.services.audit_service import audited
```

Decorate `create_assignments`:
```python
@audited("teacher_assignment", action="create")
async def create_assignments(
    db: AsyncSession, *, school_id: str, user_id: str,
    class_ids: list[str], subject_code: str, semester: str,
) -> int:
    """Batch create assignments. Skips existing (idempotent). Returns count created."""
    # P2 fix: validate class_ids belong to target school
    if class_ids:
        rows = (await db.execute(
            select(Class.id, Class.school_id).where(Class.id.in_(class_ids))
        )).all()
        found_ids = {r[0] for r in rows}
        missing = set(class_ids) - found_ids
        if missing:
            raise ValidationError(f"班级 ID 不存在: {missing}")
        wrong_school = {r[0] for r in rows if r[1] != school_id}
        if wrong_school:
            raise ValidationError(f"班级不属于目标学校: {wrong_school}")

    created = 0
    for cid in class_ids:
        existing = (await db.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.user_id == user_id,
                TeacherAssignment.class_id == cid,
                TeacherAssignment.subject_code == subject_code,
                TeacherAssignment.semester == semester,
            )
        )).scalar_one_or_none()
        if not existing:
            db.add(TeacherAssignment(
                user_id=user_id, class_id=cid, subject_code=subject_code,
                semester=semester, school_id=school_id,
            ))
            created += 1
    await db.commit()
    return created
```

Note: `create_assignments` returns `int` (not ORM object), so the decorator will record `after_data=None` and `entity_id="-"` for the count. This is acceptable for batch create — the individual assignment IDs are not easily returned from a batch operation. The audit log records the action with school_id/user_id context which is sufficient for traceability.

Decorate `delete_assignment`:
```python
@audited("teacher_assignment", action="delete", id_param="assignment_id")
async def delete_assignment(
    db: AsyncSession, *, school_id: str, assignment_id: str,
) -> None:
    row = (await db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not row:
        raise NotFoundError("排课记录不存在")
    await db.delete(row)
    await db.commit()
```

- [ ] **Step 5: Add @audited to subject_selection_service.py**

In `src/edu_cloud/services/subject_selection_service.py`:

Add import at top:
```python
from edu_cloud.services.audit_service import audited
```

Decorate `create_selection`:
```python
@audited("subject_selection", action="create")
async def create_selection(
    db: AsyncSession, *, school_id: str, name: str,
    subject_codes: list[str], mode: str = "custom",
) -> SubjectSelection:
    _validate_selection(subject_codes, mode)
    await _check_name_conflict(db, school_id, name)
    sel = SubjectSelection(
        school_id=school_id, name=name,
        subject_codes=subject_codes, mode=mode,
    )
    db.add(sel)
    await db.commit()
    await db.refresh(sel)
    return sel
```

Decorate `update_selection`:
```python
@audited("subject_selection", action="update", id_param="selection_id")
async def update_selection(
    db: AsyncSession, *, school_id: str, selection_id: str, **kwargs,
) -> SubjectSelection:
    sel = (await db.execute(
        select(SubjectSelection).where(
            SubjectSelection.id == selection_id,
            SubjectSelection.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not sel:
        raise NotFoundError("选考组合不存在")
    # F01 fix: pre-check name conflict on rename
    if "name" in kwargs and kwargs["name"] is not None and kwargs["name"] != sel.name:
        await _check_name_conflict(db, school_id, kwargs["name"], exclude_id=selection_id)
    for key, value in kwargs.items():
        if key == "subject_codes" and value is not None:
            _validate_selection(value, kwargs.get("mode", sel.mode))
        if key == "mode" and value is not None:
            _validate_selection(kwargs.get("subject_codes", sel.subject_codes), value)
        if hasattr(sel, key) and value is not None:
            setattr(sel, key, value)
    await db.commit()
    await db.refresh(sel)
    return sel
```

Decorate `delete_selection`:
```python
@audited("subject_selection", action="delete", id_param="selection_id")
async def delete_selection(
    db: AsyncSession, *, school_id: str, selection_id: str,
) -> None:
    sel = (await db.execute(
        select(SubjectSelection).where(
            SubjectSelection.id == selection_id,
            SubjectSelection.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not sel:
        raise NotFoundError("选考组合不存在")
    await db.delete(sel)
    await db.commit()
```

- [ ] **Step 6: Run integration tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py -v`
Expected: 12 passed (8 prior + 4 integration)

- [ ] **Step 7: Run full test suite to verify no regressions**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass (existing service tests pass — @audited is transparent)

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/services/school_settings_service.py src/edu_cloud/services/teacher_assignment_service.py src/edu_cloud/services/subject_selection_service.py tests/test_services/test_audit_service.py
git commit -m "feat: integrate @audited decorator into settings/assignments/selections services"
```

**审查清单:**
- ✓ upsert_setting 加 @audited("school_setting", action="create")
- ✓ set_module_enabled 加 @audited("school_module", action="update")
- ✓ create_assignments 加 @audited("teacher_assignment", action="create")
- ✓ delete_assignment 加 @audited("teacher_assignment", action="delete")
- ✓ create_selection 加 @audited("subject_selection", action="create")
- ✓ update_selection 加 @audited("subject_selection", action="update")
- ✓ delete_selection 加 @audited("subject_selection", action="delete")
- ✓ 既有 service 测试不受影响
- ✗ create_assignments 返回 int → after_data=None（批量操作已知限制）

**边界条件:**
- @audited 对 ValidationError/NotFoundError 不拦截 → 异常正常冒泡
- 无 current_user_var → user_id="-"
- create_assignments 返回 int 非 ORM → snapshot 为 None（可接受）

**测试契约:**
1. 既有 service 向后兼容
   - 入口: `upsert_setting(db, school_id=X, ...)` — 返回值和行为不变
   - 反例: @audited 装饰器改变了返回值或抛出意外异常
   - 边界: create / update / delete 三种操作
   - 回归: Phase 1a 设置管理功能
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py::test_existing_settings_tests_still_pass -v`
2. 审计日志写入
   - 入口: 调用 upsert_setting → 检查 audit_logs 表
   - 反例: 装饰器未正确调用 write_audit_log → 无审计记录
   - 边界: create/update/delete + 有 user context/无 user context
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_audit_service.py::test_audited_upsert_setting -v`

---

### Task 8: AuditLog API + Migration + Docs

**Files:**
- Create: `src/edu_cloud/modules/school/audit_router.py`
- Modify: `src/edu_cloud/api/app.py`
- Create: `tests/test_api/test_audit_logs.py`
- Modify: `alembic/env.py`
- Modify: `tests/test_alembic_migration.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_api/test_audit_logs.py
import pytest


@pytest.mark.asyncio
async def test_list_audit_logs_empty(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_audit_logs_after_setting_change(client, admin_headers, seed_school):
    school, _ = seed_school
    # Create a setting (which triggers @audited)
    await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"key": "api_audit_test", "value": "hello"},
        headers=admin_headers,
    )
    resp = await client.get(f"/api/v1/schools/{school.id}/audit-logs", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["entity_type"] == "school_setting"


@pytest.mark.asyncio
async def test_list_audit_logs_filter_entity_type(client, admin_headers, seed_school, db):
    school, _ = seed_school
    # Create setting + selection to get different entity_types
    await client.patch(
        f"/api/v1/schools/{school.id}/settings",
        json={"key": "filter_test_key", "value": "v1"},
        headers=admin_headers,
    )
    await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "审计过滤理化生", "subject_codes": ["physics", "chemistry", "biology"], "mode": "custom"},
        headers=admin_headers,
    )

    resp = await client.get(
        f"/api/v1/schools/{school.id}/audit-logs?entity_type=school_setting",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all(d["entity_type"] == "school_setting" for d in data)


@pytest.mark.asyncio
async def test_list_audit_logs_pagination(client, admin_headers, seed_school):
    school, _ = seed_school
    # Create multiple settings
    for i in range(5):
        await client.patch(
            f"/api/v1/schools/{school.id}/settings",
            json={"key": f"page_test_{i}", "value": f"v{i}"},
            headers=admin_headers,
        )

    resp = await client.get(
        f"/api/v1/schools/{school.id}/audit-logs?limit=2&offset=0",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    resp = await client.get(
        f"/api/v1/schools/{school.id}/audit-logs?limit=2&offset=3",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_audit_logs_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/audit-logs")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_audit_logs_scope_guard(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="审计A校", code="AUD_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="审计B校", code="AUD_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="audit_scope_test", display_name="跨校审计测试")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "audit_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/audit-logs", headers=headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_audit_logs.py::test_list_audit_logs_empty -v`
Expected: FAIL — 404 (routes not registered)

- [ ] **Step 3: Implement audit router**

```python
# src/edu_cloud/modules/school/audit_router.py
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.audit_service import list_audit_logs
from edu_cloud.services.exceptions import PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["audit-logs"])

_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in _CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的审计日志")


@router.get("/audit-logs")
async def api_list_audit_logs(
    school_id: str,
    entity_type: str | None = None,
    user_id: str | None = None,
    action: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    logs = await list_audit_logs(
        db, school_id=school_id,
        entity_type=entity_type, user_id=user_id, action=action,
        start_date=start_date, end_date=end_date,
        limit=limit, offset=offset,
    )
    return [
        {
            "id": l.id,
            "school_id": l.school_id,
            "user_id": l.user_id,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "action": l.action,
            "before_data": l.before_data,
            "after_data": l.after_data,
            "request_id": l.request_id,
            "created_at": l.created_at.isoformat() if l.created_at else None,
        }
        for l in logs
    ]
```

- [ ] **Step 4: Register router in app.py**

In `src/edu_cloud/api/app.py`, in the router import section, add after the capability_router import:

```python
    from edu_cloud.modules.school.audit_router import router as audit_router
```

Add `audit_router` to the `for r in [...]` loop list (after `capability_router`).

- [ ] **Step 5: Update alembic/env.py**

Add after `from edu_cloud.models.subject_selection import SubjectSelection`:

```python
from edu_cloud.models.capability import Capability  # noqa: F401
from edu_cloud.models.audit_log import AuditLog  # noqa: F401
```

- [ ] **Step 6: Update tests/test_alembic_migration.py**

Add the same imports as alembic/env.py. The test file uses `from ... import ...` style for model discovery. The two new tables (`capabilities` and `audit_logs`) will be included in the ORM metadata table set comparison.

At the top of the file, no changes needed — the test collects tables from `Base.metadata` which already has them from conftest.py imports. Just verify the test passes.

- [ ] **Step 7: Generate alembic migration**

Run: `cd C:/Users/Administrator/edu-cloud && python -m alembic revision --autogenerate -m "add capabilities and audit_logs tables"`

Verify the generated migration creates `capabilities` and `audit_logs` tables.

- [ ] **Step 8: Update CLAUDE.md**

Add to the API 端点 tables:

Under "学校配置端点" section, add:

```markdown
### 能力配置端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/schools/{id}/capabilities` | MANAGE_SCHOOL_SETTINGS | 获取角色能力矩阵（支持 role 过滤） |
| PATCH | `/api/v1/schools/{id}/capabilities` | MANAGE_SCHOOL_SETTINGS | 修改单个 capability（role + domain + action + enabled） |
| POST | `/api/v1/schools/{id}/capabilities/init` | MANAGE_SCHOOL_SETTINGS | 按默认模板初始化（幂等） |

### 审计日志端点（JWT 认证）

| 方法 | 路径 | 权限 | 用途 |
|------|------|------|------|
| GET | `/api/v1/schools/{id}/audit-logs` | MANAGE_SCHOOL_SETTINGS | 查询审计日志（支持 entity_type/user_id/action/date 过滤，分页） |
```

Add to 数据模型概要 table:

```markdown
| capabilities | school_id(FK), role, domain, action, enabled(default True) | 学校级角色能力配置（唯一约束：school+role+domain+action） |
| audit_logs | school_id(FK,nullable), user_id(FK), entity_type, entity_id, action, before_data(JSON), after_data(JSON), request_id | 变更审计日志 |
```

Update project structure `core/` section to include `scope_filter.py`.
Update `services/` section to include `capability_service.py` and `audit_service.py`.
Update `models/` section to include `capability.py` and `audit_log.py`.
Update `modules/school/` section to include `capability_router.py` and `audit_router.py`.

- [ ] **Step 9: Run API tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_audit_logs.py -v`
Expected: 6 passed

- [ ] **Step 10: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass + ~35 new tests total

- [ ] **Step 11: Commit**

```bash
git add src/edu_cloud/modules/school/audit_router.py src/edu_cloud/api/app.py alembic/env.py tests/test_api/test_audit_logs.py CLAUDE.md
git add alembic/versions/  # the generated migration file
git commit -m "feat: add audit-logs API + capability/audit_log migration + docs update"
```

**审查清单:**
- ✓ `require_permission(Permission.MANAGE_SCHOOL_SETTINGS)` 保护审计日志端点
- ✓ `_check_school_scope` 跨校防护
- ✓ GET 支持 entity_type/user_id/action/start_date/end_date 过滤
- ✓ GET 支持 limit/offset 分页（limit 上限 200）
- ✓ alembic/env.py 导入新模型
- ✓ CLAUDE.md 更新 API 端点 + 数据模型
- ✗ 未认证请求 → 401/403
- ✗ 跨校访问 → 403

**边界条件:**
- 空审计日志 → 返回空列表
- limit=200 + offset=0 → 最多返回 200 条
- start_date/end_date 过滤 → ISO datetime 字符串
- 审计日志只读，无 POST/PATCH/DELETE 端点

**测试契约:**
1. 审计日志联动
   - 入口: `PATCH /settings` → `GET /audit-logs` 检查是否有记录
   - 反例: @audited 未正确集成 → GET 返回空
   - 边界: 无操作 / 单操作 / 多操作
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_audit_logs.py::test_list_audit_logs_after_setting_change -v`
2. 跨校越权拦截
   - 入口: principal of school A → `GET /api/v1/schools/{school_b}/audit-logs`
   - 反例: 错误实现不检查 school scope → 暴露其他学校审计数据
   - 边界: platform_admin 可跨校 / principal 不能
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_audit_logs.py::test_audit_logs_scope_guard -v`
