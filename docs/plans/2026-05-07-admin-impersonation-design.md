# 超级管理员角色模拟（Impersonation）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 超管可通过专属页面切换到任意学校的任意角色视角（含细粒度 scope），查看/操作该视角下的数据。

## GPT Review Findings — 执行修订（2026-05-07）

以下修订在执行各 Task 时强制适用：

1. **scope_override DB 校验**（HIGH）：`/impersonate` 端点必须校验 class_ids/grade_ids 属于目标 school_id，subject_codes 属于合法枚举。不信任 JWT 中的 scope_override 裸值。
2. **审计落库**（HIGH）：新增 `impersonation_sessions` 表（id, impersonator_id, school_id, effective_role, scope, started_at, ended_at, reason）。start/exit 各写一条。
3. **前端 token 存储**（HIGH）：原始 admin token 存 `sessionStorage`（非 localStorage），关标签页即清。impersonation state 同理。
4. **fail-closed**（MED）：impersonation token 缺少 `effective_role`/`effective_school_id`/`scope_override` 任一 claim → 直接 401。不 fallback。
5. **scope 必填校验**（MED）：后端按角色定义必填 scope。subject_teacher 必须有 class_ids+subject_codes；grade_leader 必须有 grade_ids。空 scope → 422。
6. **前端 currentRole**（MED）：不用 `currentRoleIndex=-1`。impersonate 成功后构造一个完整的 virtualRole 对象存入 roles 数组并设为 current，保证路由守卫和菜单正常工作。
7. **exit 容许过期**（MED）：`/impersonate/exit` 解析 token 时捕获 ExpiredSignatureError，仍允许退出（从 JWT payload 提取 impersonator_id 恢复）。
8. **_ImpersonatedRole 正式化**（MED）：用 `@dataclass` 替代内部 class，字段与 UserRole 一致 + `is_impersonation: bool = True`。

**Architecture:** 新增 `POST /api/v1/auth/impersonate` 端点生成短过期 JWT（含 `is_impersonation` + `impersonator_id` + `scope_override`）。`get_current_user()` 检测 impersonation token 后从 JWT claims 直接构造权限和 scope，不查 UserRole 表。前端新增 `/admin/impersonate` 页面 + 顶栏模拟状态条。

**Tech Stack:** FastAPI / python-jose JWT / Pinia / Vue 3 / Naive UI

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| Create | `src/edu_cloud/api/impersonate.py` | impersonate + exit 两个端点 |
| Modify | `src/edu_cloud/api/deps.py` | get_current_user 识别 impersonation token |
| Modify | `src/edu_cloud/shared/auth.py` | 新增 `create_impersonation_token` 短过期 |
| Modify | `src/edu_cloud/api/app.py` | 注册 impersonate router + 请求日志记录 impersonator |
| Modify | `src/edu_cloud/ai/data_scope.py` | 新增 `build_from_override` 支持 scope_override |
| Modify | `src/edu_cloud/logging_config.py` | 新增 `impersonator_var` ContextVar |
| Create | `tests/test_api/test_impersonate.py` | 后端 impersonation 测试 |
| Create | `frontend/src/pages/ImpersonatePage.vue` | 超管角色模拟页面 |
| Create | `frontend/src/components/shell/ImpersonationBar.vue` | 顶栏模拟状态条 |
| Modify | `frontend/src/stores/auth.js` | 新增 impersonate/exitImpersonation 方法 |
| Modify | `frontend/src/router/index.js` | 新增 /admin/impersonate 路由 |
| Modify | `frontend/src/layouts/AppShell.vue` | 挂载 ImpersonationBar |
| Modify | `frontend/src/config/sidebarConfig.js` | 超管菜单加"角色模拟"入口 |
| Create | `frontend/src/api/impersonate.js` | API 调用层 |
| Create | `frontend/src/__tests__/impersonate.spec.js` | 前端测试 |

---

## Batch 1: 后端 Impersonation API（Task 1-4）

### Task 1: JWT 工具函数扩展

**Files:**
- Modify: `src/edu_cloud/shared/auth.py`
- Test: `tests/test_api/test_impersonate.py`

- [ ] **Step 1: Write failing test — impersonation token 创建与解析**

```python
# tests/test_api/test_impersonate.py
import pytest
from edu_cloud.shared.auth import create_impersonation_token, decode_token


def test_impersonation_token_has_required_claims():
    token = create_impersonation_token(
        impersonator_id="admin-uuid",
        effective_role="subject_teacher",
        effective_school_id="school-uuid",
        scope_override={
            "class_ids": ["c1", "c2"],
            "subject_codes": ["math"],
            "grade_ids": None,
        },
    )
    payload = decode_token(token)
    assert payload["sub"] == "admin-uuid"
    assert payload["is_impersonation"] is True
    assert payload["impersonator_id"] == "admin-uuid"
    assert payload["effective_role"] == "subject_teacher"
    assert payload["effective_school_id"] == "school-uuid"
    assert payload["scope_override"] == {
        "class_ids": ["c1", "c2"],
        "subject_codes": ["math"],
        "grade_ids": None,
    }


def test_impersonation_token_short_expiry():
    """Impersonation token expires in 30 minutes, not 24 hours."""
    import time
    from jose import jwt
    from edu_cloud.config import settings

    token = create_impersonation_token(
        impersonator_id="admin-uuid",
        effective_role="principal",
        effective_school_id="school-uuid",
        scope_override={},
    )
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    # exp should be ~30min from now, not 24h
    remaining = payload["exp"] - time.time()
    assert remaining < 35 * 60  # less than 35 min
    assert remaining > 25 * 60  # more than 25 min
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py::test_impersonation_token_has_required_claims -v`
Expected: ImportError — `create_impersonation_token` does not exist

- [ ] **Step 3: Implement create_impersonation_token**

```python
# src/edu_cloud/shared/auth.py — append after existing functions

IMPERSONATION_EXPIRE_MINUTES = 30


def create_impersonation_token(
    *,
    impersonator_id: str,
    effective_role: str,
    effective_school_id: str,
    scope_override: dict,
) -> str:
    """Create a short-lived JWT for role impersonation.

    NOTE: grants full permissions of effective_role — may be restricted
    to read-only in a future iteration.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=IMPERSONATION_EXPIRE_MINUTES)
    payload = {
        "sub": impersonator_id,
        "is_impersonation": True,
        "impersonator_id": impersonator_id,
        "effective_role": effective_role,
        "effective_school_id": effective_school_id,
        "scope_override": scope_override,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py -v`
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ops/projects/edu-cloud && git add src/edu_cloud/shared/auth.py tests/test_api/test_impersonate.py && git commit -m "feat(auth): add create_impersonation_token with 30min expiry"
```

---

### Task 2: get_current_user 识别 impersonation token

**Files:**
- Modify: `src/edu_cloud/api/deps.py`
- Modify: `src/edu_cloud/logging_config.py`
- Test: `tests/test_api/test_impersonate.py`

- [ ] **Step 1: Write failing test — impersonation token 被 get_current_user 正确解析**

```python
# tests/test_api/test_impersonate.py — append

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_impersonation_token_parsed_by_endpoint(client: AsyncClient, admin_token: str):
    """Impersonation token should yield effective_role permissions."""
    from edu_cloud.shared.auth import create_impersonation_token

    imp_token = create_impersonation_token(
        impersonator_id="test-admin-id",
        effective_role="subject_teacher",
        effective_school_id="test-school-id",
        scope_override={"class_ids": ["c1"], "subject_codes": ["math"], "grade_ids": None},
    )
    # Hit a protected endpoint — should get teacher-level permissions
    resp = await client.get(
        "/api/v1/health",
        headers={"Authorization": f"Bearer {imp_token}"},
    )
    # health endpoint has no permission requirement, should pass
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_impersonation_lacks_admin_permission(client: AsyncClient):
    """Impersonating subject_teacher should NOT have manage_schools."""
    from edu_cloud.shared.auth import create_impersonation_token

    imp_token = create_impersonation_token(
        impersonator_id="test-admin-id",
        effective_role="subject_teacher",
        effective_school_id="test-school-id",
        scope_override={"class_ids": ["c1"], "subject_codes": ["math"], "grade_ids": None},
    )
    resp = await client.get(
        "/api/v1/schools",
        headers={"Authorization": f"Bearer {imp_token}"},
    )
    # subject_teacher lacks VIEW_SCHOOLS → 403
    assert resp.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py::test_impersonation_token_parsed_by_endpoint -v`
Expected: 401 — get_current_user 查不到 user（sub 是 admin UUID 但 is_impersonation 未处理）

- [ ] **Step 3: Modify get_current_user to handle impersonation**

```python
# src/edu_cloud/api/deps.py — replace get_current_user entirely

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """平台用户认证（JWT）。返回 dict 含 user/roles/current_role/permissions。
    
    支持 impersonation token：检测 is_impersonation claim 后从 JWT 直接构造
    权限和 scope，不查 UserRole 表。
    """
    try:
        payload = decode_token(credentials.credentials)
    except ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token")

    # ── Impersonation 分支 ──
    if payload.get("is_impersonation"):
        from edu_cloud.logging_config import impersonator_var
        impersonator_id = payload.get("impersonator_id", user_id)
        impersonator_var.set(impersonator_id)

        from edu_cloud.models.user import User
        user = await db.get(User, impersonator_id)
        if not user or not user.is_active:
            raise HTTPException(401, "Impersonator user not found or inactive")

        # 验证 impersonator 是 platform_admin
        from edu_cloud.models.user_role import UserRole
        admin_roles = (
            await db.execute(
                select(UserRole).where(
                    UserRole.user_id == impersonator_id,
                    UserRole.role.in_(["platform_admin", "admin"]),
                )
            )
        ).scalars().all()
        if not admin_roles:
            raise HTTPException(403, "Only platform_admin can impersonate")

        effective_role = payload.get("effective_role", "subject_teacher")
        scope_override = payload.get("scope_override", {})

        # 构造虚拟 current_role 对象（duck-type 兼容 UserRole 接口）
        class _ImpersonatedRole:
            def __init__(self, role, school_id, scope):
                self.id = f"impersonated-{impersonator_id}"
                self.user_id = impersonator_id
                self.role = role
                self.school_id = school_id
                self.class_ids = scope.get("class_ids")
                self.subject_codes = scope.get("subject_codes")
                self.grade_ids = scope.get("grade_ids")
                self.is_primary = False
                self.is_impersonation = True

        virtual_role = _ImpersonatedRole(
            effective_role,
            payload.get("effective_school_id"),
            scope_override,
        )

        return {
            "user": user,
            "roles": [],
            "current_role": virtual_role,
            "permissions": ROLE_PERMISSIONS.get(effective_role, set()),
            "is_impersonation": True,
            "impersonator_id": impersonator_id,
        }

    # ── 正常分支（保持不变）──
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole

    user = await db.get(User, user_id)
    if user:
        if not user.is_active:
            raise HTTPException(401, "User not found or inactive")

        roles = (
            await db.execute(select(UserRole).where(UserRole.user_id == user.id))
        ).scalars().all()
        if not roles:
            raise HTTPException(403, "No role assigned")

        active_role_id = payload.get("active_role_id")
        if active_role_id:
            active = next((r for r in roles if r.id == active_role_id), None)
        else:
            active = next((r for r in roles if r.is_primary), roles[0])

        if active is None:
            active = roles[0]

        return {
            "user": user,
            "roles": roles,
            "current_role": active,
            "permissions": ROLE_PERMISSIONS.get(active.role, set()),
        }

    logger.warning("token user_id=%s not found", user_id)
    raise HTTPException(401, "User not found")
```

- [ ] **Step 4: Add impersonator_var to logging_config.py**

```python
# src/edu_cloud/logging_config.py — add after line 32 (current_school_var)
impersonator_var: ContextVar[str | None] = ContextVar("impersonator_id", default=None)
```

And update `get_trace_context()`:
```python
def get_trace_context() -> dict:
    return {
        "trace_id": trace_id_var.get(),
        "req_id": request_id_var.get(),
        "user_id": current_user_var.get(),
        "school_id": current_school_var.get(),
        "impersonator_id": impersonator_var.get(),
    }
```

- [ ] **Step 5: Run tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py -v`
Expected: 4 PASS

- [ ] **Step 6: Run existing auth tests to verify no regression**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_auth_v2.py -v`
Expected: all existing tests PASS

- [ ] **Step 7: Commit**

```bash
cd /home/ops/projects/edu-cloud && git add src/edu_cloud/api/deps.py src/edu_cloud/logging_config.py tests/test_api/test_impersonate.py && git commit -m "feat(auth): get_current_user supports impersonation token with scope_override"
```

---

### Task 3: Impersonation API 端点

**Files:**
- Create: `src/edu_cloud/api/impersonate.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_api/test_impersonate.py`

- [ ] **Step 1: Write failing tests — impersonate + exit endpoints**

```python
# tests/test_api/test_impersonate.py — append

@pytest.mark.asyncio
async def test_impersonate_success(client: AsyncClient, admin_token: str, test_school_id: str):
    """platform_admin can impersonate any role at any school."""
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": test_school_id,
            "role": "subject_teacher",
            "scope": {"class_ids": ["c1"], "subject_codes": ["math"], "grade_ids": None},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["effective_role"] == "subject_teacher"
    assert data["effective_school_id"] == test_school_id
    assert data["is_impersonation"] is True


@pytest.mark.asyncio
async def test_impersonate_requires_platform_admin(client: AsyncClient, teacher_token: str, test_school_id: str):
    """Non-admin users cannot impersonate."""
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": test_school_id,
            "role": "principal",
            "scope": {},
        },
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_impersonate_invalid_role_rejected(client: AsyncClient, admin_token: str, test_school_id: str):
    """Unknown role names are rejected."""
    resp = await client.post(
        "/api/v1/auth/impersonate",
        json={
            "school_id": test_school_id,
            "role": "nonexistent_role",
            "scope": {},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_impersonate_exit(client: AsyncClient, admin_token: str, test_school_id: str):
    """Exit impersonation returns a normal platform_admin token."""
    # First impersonate
    imp_resp = await client.post(
        "/api/v1/auth/impersonate",
        json={"school_id": test_school_id, "role": "principal", "scope": {}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    imp_token = imp_resp.json()["access_token"]

    # Then exit
    exit_resp = await client.post(
        "/api/v1/auth/impersonate/exit",
        headers={"Authorization": f"Bearer {imp_token}"},
    )
    assert exit_resp.status_code == 200
    data = exit_resp.json()
    assert "access_token" in data
    # The returned token should be a normal token (not impersonation)
    from edu_cloud.shared.auth import decode_token
    payload = decode_token(data["access_token"])
    assert payload.get("is_impersonation") is None or payload["is_impersonation"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py::test_impersonate_success -v`
Expected: 404 — route doesn't exist

- [ ] **Step 3: Implement impersonate.py**

```python
# src/edu_cloud/api/impersonate.py
"""角色模拟 API — 仅 platform_admin 可用。

NOTE: 当前实现授予模拟角色的完整权限（含写操作）。
后续版本可能收回为只读模式（修改 create_impersonation_token 添加 mode 字段
+ get_current_user 中检查 mode 拦截写操作）。
"""
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import get_current_user
from edu_cloud.config import settings
from edu_cloud.core.permissions import ROLE_PERMISSIONS
from edu_cloud.database import get_db
from edu_cloud.logging_config import business_event
from edu_cloud.shared.auth import create_access_token, create_impersonation_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

IMPERSONATABLE_ROLES = [
    "principal",
    "academic_director",
    "teaching_research_leader",
    "grade_leader",
    "lesson_prep_leader",
    "homeroom_teacher",
    "subject_teacher",
]


class ImpersonateRequest(BaseModel):
    school_id: str
    role: str
    scope: dict = {}

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in IMPERSONATABLE_ROLES:
            raise ValueError(
                f"Invalid role '{v}'. Must be one of: {IMPERSONATABLE_ROLES}"
            )
        return v


@router.post("/impersonate")
async def impersonate(
    req: ImpersonateRequest,
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """进入角色模拟。仅 platform_admin 可调用。"""
    user = current["user"]

    # 权限校验：必须是 platform_admin
    role_name = current["current_role"].role
    if role_name not in ("platform_admin", "admin"):
        raise HTTPException(403, "Only platform_admin can impersonate")

    # 验证目标学校存在且活跃
    from edu_cloud.models.school import School
    school = await db.get(School, req.school_id)
    if not school or not school.is_active:
        raise HTTPException(404, "School not found or inactive")

    # 构造 scope_override
    scope_override = {
        "class_ids": req.scope.get("class_ids"),
        "subject_codes": req.scope.get("subject_codes"),
        "grade_ids": req.scope.get("grade_ids"),
    }

    token = create_impersonation_token(
        impersonator_id=user.id,
        effective_role=req.role,
        effective_school_id=req.school_id,
        scope_override=scope_override,
    )

    logger.info(
        "impersonate: admin=%s → role=%s school=%s",
        user.username, req.role, school.name,
    )
    business_event(
        "impersonate_start", "user", user.id,
        effective_role=req.role, school_id=req.school_id,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "is_impersonation": True,
        "effective_role": req.role,
        "effective_school_id": req.school_id,
        "effective_school_name": school.name,
        "scope": scope_override,
    }


@router.post("/impersonate/exit")
async def exit_impersonation(
    current: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """退出角色模拟，恢复 platform_admin 身份。"""
    impersonator_id = current.get("impersonator_id") or current["user"].id
    user = current["user"]

    # 查找用户的 platform_admin 主角色
    from edu_cloud.models.user_role import UserRole
    result = await db.execute(
        select(UserRole).where(
            UserRole.user_id == impersonator_id,
            UserRole.role.in_(["platform_admin", "admin"]),
        )
    )
    admin_role = result.scalars().first()
    if not admin_role:
        raise HTTPException(403, "Cannot exit: no admin role found")

    token = create_access_token({
        "sub": impersonator_id,
        "role": admin_role.role,
        "active_role_id": admin_role.id,
        **({"school_id": admin_role.school_id} if admin_role.school_id else {}),
    })

    logger.info("impersonate_exit: admin=%s", user.username)
    business_event("impersonate_exit", "user", impersonator_id)

    return {
        "access_token": token,
        "token_type": "bearer",
    }
```

- [ ] **Step 4: Register router in app.py**

In `src/edu_cloud/api/app.py`, add after other router includes:
```python
from edu_cloud.api.impersonate import router as impersonate_router
app.include_router(impersonate_router)
```

- [ ] **Step 5: Run tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
cd /home/ops/projects/edu-cloud && git add src/edu_cloud/api/impersonate.py src/edu_cloud/api/app.py tests/test_api/test_impersonate.py && git commit -m "feat(auth): add POST /impersonate and /impersonate/exit endpoints"
```

---

### Task 4: DataScope 支持 impersonation override

**Files:**
- Modify: `src/edu_cloud/ai/data_scope.py`
- Test: `tests/test_api/test_impersonate.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_api/test_impersonate.py — append

@pytest.mark.asyncio
async def test_data_scope_from_impersonation(db_session):
    """DataScopeBuilder.build_from_override constructs scope without DB lookup."""
    from edu_cloud.ai.data_scope import DataScopeBuilder

    builder = DataScopeBuilder(db_session)
    scope = builder.build_from_override(
        impersonator_id="admin-uuid",
        effective_role="subject_teacher",
        school_id="school-uuid",
        scope_override={
            "class_ids": ["c1", "c2"],
            "subject_codes": ["math"],
            "grade_ids": None,
        },
    )
    assert scope.role == "subject_teacher"
    assert scope.school_id == "school-uuid"
    assert scope.visible_class_ids == ["c1", "c2"]
    assert scope.visible_subject_codes == ["math"]
    assert scope.visible_grade_ids is None
    assert scope.can_write is True  # full permissions for now
    assert scope.persona == "teacher_assistant"
    assert scope.user_id == "admin-uuid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py::test_data_scope_from_impersonation -v`
Expected: AttributeError — `build_from_override` doesn't exist

- [ ] **Step 3: Implement build_from_override**

```python
# src/edu_cloud/ai/data_scope.py — add method to DataScopeBuilder class after build()

    def build_from_override(
        self,
        *,
        impersonator_id: str,
        effective_role: str,
        school_id: str,
        scope_override: dict,
    ) -> DataScope:
        """Build DataScope directly from impersonation claims (no DB lookup).

        Used when JWT contains is_impersonation=True. The scope is fully
        specified in the token, so we skip UserRole/TeacherAssignment queries.
        """
        persona = PERSONA_MAP.get(effective_role)
        if persona is None:
            raise DataScopeBuildError(
                f"Cannot impersonate unknown role '{effective_role}'"
            )

        return self._make(
            user_id=impersonator_id,
            school_id=school_id,
            role=effective_role,
            persona=persona,
            visible_class_ids=scope_override.get("class_ids"),
            visible_subject_codes=scope_override.get("subject_codes"),
            visible_grade_ids=scope_override.get("grade_ids"),
            # NOTE: full write access during impersonation.
            # Future: add mode param to restrict to read-only.
            can_write=True,
            can_see_rankings=True,
            can_cross_school=(effective_role in ("platform_admin", "district_admin")),
        )
```

- [ ] **Step 4: Run test**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py::test_data_scope_from_impersonation -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/ops/projects/edu-cloud && git add src/edu_cloud/ai/data_scope.py tests/test_api/test_impersonate.py && git commit -m "feat(ai): DataScopeBuilder.build_from_override for impersonation"
```

---

## Batch 2: 前端 Impersonation 页面（Task 5-8）

### Task 5: API 调用层 + Auth Store 扩展

**Files:**
- Create: `frontend/src/api/impersonate.js`
- Modify: `frontend/src/stores/auth.js`

- [ ] **Step 1: Create API module**

```javascript
// frontend/src/api/impersonate.js
import client from './client.js'

export function startImpersonation(schoolId, role, scope = {}) {
  return client.post('/auth/impersonate', {
    school_id: schoolId,
    role,
    scope,
  })
}

export function exitImpersonation() {
  return client.post('/auth/impersonate/exit')
}
```

- [ ] **Step 2: Extend auth store with impersonation state**

Add to `frontend/src/stores/auth.js`:

```javascript
// After line 45 (modulesLoaded ref):
const impersonation = ref(JSON.parse(localStorage.getItem('impersonation') || 'null'))

// New computed:
const isImpersonating = computed(() => !!impersonation.value)

// New methods:
async function impersonate(schoolId, role, scope = {}) {
  const { startImpersonation } = await import('../api/impersonate.js')
  const { data } = await startImpersonation(schoolId, role, scope)

  // Save original token for exit fallback
  const originalToken = token.value
  const originalState = { user: user.value, roles: roles.value, currentRoleIndex: currentRoleIndex.value }

  // Set impersonation state
  impersonation.value = {
    effectiveRole: data.effective_role,
    schoolId: data.effective_school_id,
    schoolName: data.effective_school_name,
    scope: data.scope,
    originalToken,
    originalState,
  }
  localStorage.setItem('impersonation', JSON.stringify(impersonation.value))

  // Switch to impersonation token
  token.value = data.access_token
  localStorage.setItem('token', data.access_token)

  // Update current role display info
  currentRoleIndex.value = -1  // sentinel: not from roles array
  await loadModules()
}

async function stopImpersonation() {
  const { exitImpersonation } = await import('../api/impersonate.js')
  try {
    const { data } = await exitImpersonation()
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
  } catch {
    // Fallback: restore original token
    if (impersonation.value?.originalToken) {
      token.value = impersonation.value.originalToken
      localStorage.setItem('token', impersonation.value.originalToken)
    }
  }

  // Restore original state
  if (impersonation.value?.originalState) {
    const s = impersonation.value.originalState
    user.value = s.user
    roles.value = s.roles
    currentRoleIndex.value = s.currentRoleIndex
    saveAuthState(user.value, roles.value, currentRoleIndex.value)
  }

  impersonation.value = null
  localStorage.removeItem('impersonation')
  await loadModules()
}
```

Update the return statement to export new refs/methods:
```javascript
return {
  token, user, roles, currentRole, currentRoleIndex,
  displayName, roleName, currentContext, isAdmin,
  enabledModules, modulesLoaded,
  impersonation, isImpersonating,
  checkPermission, login, switchRole, logout, loadModules,
  impersonate, stopImpersonation,
}
```

- [ ] **Step 3: Run frontend tests to verify no regression**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/stores/__tests__/`
Expected: existing auth store tests PASS

- [ ] **Step 4: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend && git add src/api/impersonate.js src/stores/auth.js && git commit -m "feat(frontend): auth store impersonate/stopImpersonation methods"
```

---

### Task 6: ImpersonationBar 组件

**Files:**
- Create: `frontend/src/components/shell/ImpersonationBar.vue`
- Modify: `frontend/src/layouts/AppShell.vue`

- [ ] **Step 1: Create ImpersonationBar component**

```vue
<!-- frontend/src/components/shell/ImpersonationBar.vue -->
<template>
  <div v-if="auth.isImpersonating" class="impersonation-bar">
    <span class="impersonation-bar__icon">⚡</span>
    <span class="impersonation-bar__text">
      模拟中: {{ auth.impersonation?.schoolName }} · {{ roleLabel }}
      <template v-if="scopeText"> · {{ scopeText }}</template>
    </span>
    <button class="impersonation-bar__exit" @click="handleExit">
      退出模拟
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth.js'
import { ROLE_LABELS, normalizeRole } from '../../config/roles.js'
import router from '../../router/index.js'

const auth = useAuthStore()

const roleLabel = computed(() => {
  const role = auth.impersonation?.effectiveRole
  return role ? (ROLE_LABELS[normalizeRole(role)] || role) : ''
})

const scopeText = computed(() => {
  const scope = auth.impersonation?.scope
  if (!scope) return ''
  const parts = []
  if (scope.class_ids?.length) parts.push(`${scope.class_ids.length}个班级`)
  if (scope.subject_codes?.length) parts.push(`${scope.subject_codes.length}个学科`)
  if (scope.grade_ids?.length) parts.push(`${scope.grade_ids.length}个年级`)
  return parts.join(' · ')
})

async function handleExit() {
  await auth.stopImpersonation()
  router.push('/admin/impersonate')
}
</script>

<style scoped>
.impersonation-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 36px;
  background: linear-gradient(90deg, #ED9A51, #F4DA4C);
  color: #09061B;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  z-index: 9999;
}

.impersonation-bar__exit {
  margin-left: 16px;
  padding: 2px 12px;
  border: 1.5px solid #09061B;
  border-radius: 4px;
  background: transparent;
  color: #09061B;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.impersonation-bar__exit:hover {
  background: rgba(9, 6, 27, 0.1);
}
</style>
```

- [ ] **Step 2: Mount in AppShell.vue**

In `frontend/src/layouts/AppShell.vue`, add import and component:
```vue
<template>
  <ImpersonationBar />
  <!-- existing content with :style offset when impersonating -->
  <div class="app-shell" :style="auth.isImpersonating ? { marginTop: '36px' } : {}">
    ...existing...
  </div>
</template>

<script setup>
import ImpersonationBar from '../components/shell/ImpersonationBar.vue'
// ... existing imports
</script>
```

- [ ] **Step 3: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend && git add src/components/shell/ImpersonationBar.vue src/layouts/AppShell.vue && git commit -m "feat(frontend): ImpersonationBar status strip with exit button"
```

---

### Task 7: ImpersonatePage 页面

**Files:**
- Create: `frontend/src/pages/ImpersonatePage.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/config/sidebarConfig.js`

- [ ] **Step 1: Create page**

```vue
<!-- frontend/src/pages/ImpersonatePage.vue -->
<template>
  <div class="impersonate-page">
    <h1 class="page-title">角色模拟</h1>
    <p class="page-desc">以任意学校的任意角色视角查看系统</p>

    <div class="impersonate-page__grid">
      <!-- 左列：学校选择 -->
      <div class="impersonate-page__schools">
        <n-input
          v-model:value="schoolSearch"
          placeholder="搜索学校..."
          clearable
          size="large"
        />
        <div class="school-list">
          <div
            v-for="school in filteredSchools"
            :key="school.id"
            class="school-card"
            :class="{ 'school-card--active': selectedSchool?.id === school.id }"
            @click="selectedSchool = school"
          >
            <span class="school-card__name">{{ school.name }}</span>
            <span class="school-card__code">{{ school.code }}</span>
          </div>
          <div v-if="filteredSchools.length === 0" class="school-list__empty">
            无匹配学校
          </div>
        </div>
      </div>

      <!-- 右列：角色 + scope 选择 -->
      <div class="impersonate-page__config">
        <template v-if="selectedSchool">
          <h3>选择角色</h3>
          <div class="role-grid">
            <div
              v-for="role in availableRoles"
              :key="role.value"
              class="role-chip"
              :class="{ 'role-chip--active': selectedRole === role.value }"
              @click="selectedRole = role.value"
            >
              {{ role.label }}
            </div>
          </div>

          <!-- Scope 选择器 -->
          <template v-if="needsScope">
            <h3>选择范围</h3>
            <div class="scope-selectors">
              <n-select
                v-if="needsGrade"
                v-model:value="selectedGradeIds"
                :options="gradeOptions"
                multiple
                placeholder="选择年级"
              />
              <n-select
                v-if="needsClass"
                v-model:value="selectedClassIds"
                :options="classOptions"
                multiple
                placeholder="选择班级"
              />
              <n-select
                v-if="needsSubject"
                v-model:value="selectedSubjectCodes"
                :options="subjectOptions"
                multiple
                placeholder="选择学科"
              />
            </div>
          </template>

          <!-- 确认按钮 -->
          <n-button
            type="primary"
            size="large"
            :disabled="!canImpersonate"
            :loading="loading"
            @click="doImpersonate"
            style="margin-top: 24px; width: 100%;"
          >
            进入模拟
          </n-button>
        </template>
        <template v-else>
          <div class="config-placeholder">
            ← 请先选择学校
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { NInput, NSelect, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import client from '../api/client.js'
import router from '../router/index.js'
import { ROLE_LABELS } from '../config/roles.js'

const auth = useAuthStore()
const message = useMessage()

const schoolSearch = ref('')
const schools = ref([])
const selectedSchool = ref(null)
const selectedRole = ref(null)
const selectedGradeIds = ref([])
const selectedClassIds = ref([])
const selectedSubjectCodes = ref([])
const loading = ref(false)

// Classes/grades for scope selection
const classes = ref([])
const grades = ref([])

const IMPERSONATABLE_ROLES = [
  { value: 'principal', label: ROLE_LABELS.principal || '校长' },
  { value: 'academic_director', label: ROLE_LABELS.academic_director || '教务主任' },
  { value: 'teaching_research_leader', label: ROLE_LABELS.teaching_research_leader || '教研组长' },
  { value: 'grade_leader', label: ROLE_LABELS.grade_leader || '年级组长' },
  { value: 'lesson_prep_leader', label: ROLE_LABELS.lesson_prep_leader || '备课组长' },
  { value: 'homeroom_teacher', label: ROLE_LABELS.homeroom_teacher || '班主任' },
  { value: 'subject_teacher', label: ROLE_LABELS.subject_teacher || '科任教师' },
]

const SUBJECT_OPTIONS = [
  { value: 'chinese', label: '语文' },
  { value: 'math', label: '数学' },
  { value: 'english', label: '英语' },
  { value: 'physics', label: '物理' },
  { value: 'chemistry', label: '化学' },
  { value: 'biology', label: '生物' },
  { value: 'politics', label: '政治' },
  { value: 'history', label: '历史' },
  { value: 'geography', label: '地理' },
]

const filteredSchools = computed(() => {
  if (!schoolSearch.value) return schools.value
  const q = schoolSearch.value.toLowerCase()
  return schools.value.filter(s =>
    s.name.toLowerCase().includes(q) || s.code.toLowerCase().includes(q)
  )
})

const availableRoles = computed(() => IMPERSONATABLE_ROLES)

const needsScope = computed(() => {
  return ['grade_leader', 'lesson_prep_leader', 'homeroom_teacher', 'subject_teacher', 'teaching_research_leader'].includes(selectedRole.value)
})
const needsGrade = computed(() => ['grade_leader', 'lesson_prep_leader'].includes(selectedRole.value))
const needsClass = computed(() => ['homeroom_teacher', 'subject_teacher'].includes(selectedRole.value))
const needsSubject = computed(() => ['subject_teacher', 'teaching_research_leader', 'lesson_prep_leader'].includes(selectedRole.value))

const gradeOptions = computed(() => grades.value.map(g => ({ value: g.id, label: g.name })))
const classOptions = computed(() => classes.value.map(c => ({ value: c.id, label: c.name })))
const subjectOptions = computed(() => SUBJECT_OPTIONS)

const canImpersonate = computed(() => {
  if (!selectedSchool.value || !selectedRole.value) return false
  if (needsClass.value && selectedClassIds.value.length === 0) return false
  if (needsSubject.value && selectedSubjectCodes.value.length === 0) return false
  if (needsGrade.value && selectedGradeIds.value.length === 0) return false
  return true
})

watch(selectedSchool, async (school) => {
  if (!school) return
  selectedRole.value = null
  selectedClassIds.value = []
  selectedGradeIds.value = []
  selectedSubjectCodes.value = []
  // Load school's classes and grades
  try {
    const [classResp, gradeResp] = await Promise.all([
      client.get('/classes', { params: { school_id: school.id } }),
      client.get('/grades', { params: { school_id: school.id } }),
    ])
    classes.value = classResp.data?.items || classResp.data || []
    grades.value = gradeResp.data?.items || gradeResp.data || []
  } catch { /* non-fatal */ }
})

onMounted(async () => {
  try {
    const { data } = await client.get('/schools')
    schools.value = data?.items || data || []
  } catch { /* non-fatal */ }
})

async function doImpersonate() {
  loading.value = true
  try {
    const scope = {}
    if (needsClass.value) scope.class_ids = selectedClassIds.value
    if (needsSubject.value) scope.subject_codes = selectedSubjectCodes.value
    if (needsGrade.value) scope.grade_ids = selectedGradeIds.value

    await auth.impersonate(selectedSchool.value.id, selectedRole.value, scope)
    message.success(`已进入模拟: ${selectedSchool.value.name} · ${selectedRole.value}`)
    router.push('/')
  } catch (e) {
    message.error(e.response?.data?.detail || '模拟失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.impersonate-page {
  padding: 32px;
  max-width: 1100px;
  margin: 0 auto;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  margin-bottom: 4px;
}

.page-desc {
  color: var(--color-text-muted);
  margin-bottom: 24px;
}

.impersonate-page__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.school-list {
  margin-top: 12px;
  max-height: 60vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.school-card {
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.school-card:hover {
  border-color: var(--color-primary);
}

.school-card--active {
  border-color: var(--color-primary);
  background: rgba(100, 76, 240, 0.08);
}

.school-card__name {
  font-weight: 500;
}

.school-card__code {
  font-size: 12px;
  color: var(--color-text-muted);
}

.role-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.role-chip {
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid var(--color-border-light);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.15s;
}

.role-chip:hover {
  border-color: var(--color-primary);
}

.role-chip--active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #fff;
}

.scope-selectors {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}

.config-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: var(--color-text-muted);
  font-size: 16px;
}

.school-list__empty {
  text-align: center;
  padding: 24px;
  color: var(--color-text-muted);
}
</style>
```

- [ ] **Step 2: Add route**

In `frontend/src/router/index.js`, add in AppShell children (after conduct routes, before closing `]`):

```javascript
// 超管工具
{ path: 'admin/impersonate', name: 'Impersonate', component: () => import('../pages/ImpersonatePage.vue'), meta: { roles: ['platform_admin'] } },
```

- [ ] **Step 3: Add sidebar entry**

In `frontend/src/config/sidebarConfig.js`, add a group (or item in existing group) for platform_admin:

```javascript
// In SIDEBAR_GROUPS array, add as last group:
{
  key: 'admin',
  label: '平台管理',
  icon: 'settings',
  children: [
    { label: '学校管理', route: '/schools', perm: 'manage_schools' },
    { label: '角色模拟', route: '/admin/impersonate', perm: 'manage_schools' },
  ],
}
```

- [ ] **Step 4: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend && git add src/pages/ImpersonatePage.vue src/router/index.js src/config/sidebarConfig.js && git commit -m "feat(frontend): ImpersonatePage with school search + role + scope selection"
```

---

### Task 8: 前端测试

**Files:**
- Create: `frontend/src/__tests__/impersonate.spec.js`

- [ ] **Step 1: Write tests**

```javascript
// frontend/src/__tests__/impersonate.spec.js
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth.js'

vi.mock('../api/client.js', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('../router/index.js', () => ({
  default: { push: vi.fn() },
}))

vi.mock('../api/schoolSettings.js', () => ({
  getEnabledModules: vi.fn().mockResolvedValue({ data: ['exam', 'grading'] }),
}))

describe('auth store impersonation', () => {
  let auth

  beforeEach(() => {
    setActivePinia(createPinia())
    auth = useAuthStore()
    localStorage.clear()
    // Seed initial state
    auth.token = 'original-token'
    auth.user = { id: 'admin-id', display_name: 'Admin' }
    auth.roles = [{ id: 'r1', role: 'platform_admin', school_id: null, context: { type: 'platform', name: '全平台' } }]
  })

  it('impersonate sets impersonation state and token', async () => {
    const { default: client } = await import('../api/client.js')
    client.post.mockResolvedValueOnce({
      data: {
        access_token: 'imp-token',
        effective_role: 'subject_teacher',
        effective_school_id: 'school-1',
        effective_school_name: '景炎中学',
        scope: { class_ids: ['c1'], subject_codes: ['math'], grade_ids: null },
        is_impersonation: true,
      },
    })

    await auth.impersonate('school-1', 'subject_teacher', { class_ids: ['c1'], subject_codes: ['math'] })

    expect(auth.isImpersonating).toBe(true)
    expect(auth.impersonation.effectiveRole).toBe('subject_teacher')
    expect(auth.impersonation.schoolName).toBe('景炎中学')
    expect(auth.token).toBe('imp-token')
    expect(localStorage.getItem('token')).toBe('imp-token')
    expect(localStorage.getItem('impersonation')).toBeTruthy()
  })

  it('stopImpersonation restores original state', async () => {
    // Setup impersonation state
    auth.impersonation = {
      effectiveRole: 'subject_teacher',
      schoolId: 'school-1',
      schoolName: '景炎中学',
      scope: {},
      originalToken: 'original-token',
      originalState: { user: auth.user, roles: auth.roles, currentRoleIndex: 0 },
    }
    auth.token = 'imp-token'
    localStorage.setItem('impersonation', JSON.stringify(auth.impersonation))

    const { default: client } = await import('../api/client.js')
    client.post.mockResolvedValueOnce({
      data: { access_token: 'restored-token' },
    })

    await auth.stopImpersonation()

    expect(auth.isImpersonating).toBe(false)
    expect(auth.token).toBe('restored-token')
    expect(localStorage.getItem('impersonation')).toBeNull()
  })

  it('impersonation state persists across page reload', () => {
    const impState = {
      effectiveRole: 'principal',
      schoolId: 'school-1',
      schoolName: '景炎中学',
      scope: {},
      originalToken: 'orig',
      originalState: {},
    }
    localStorage.setItem('impersonation', JSON.stringify(impState))

    // Re-create store (simulates reload)
    const pinia = createPinia()
    setActivePinia(pinia)
    const freshAuth = useAuthStore()

    expect(freshAuth.isImpersonating).toBe(true)
    expect(freshAuth.impersonation.effectiveRole).toBe('principal')
  })
})
```

- [ ] **Step 2: Run tests**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run src/__tests__/impersonate.spec.js`
Expected: 3 PASS

- [ ] **Step 3: Run full frontend test suite for regression**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
cd /home/ops/projects/edu-cloud/frontend && git add src/__tests__/impersonate.spec.js && git commit -m "test(frontend): impersonation store tests"
```

---

## Batch 3: 集成与收尾（Task 9-10）

### Task 9: 请求日志中 impersonator 记录

**Files:**
- Modify: `src/edu_cloud/api/app.py`

- [ ] **Step 1: Update request logging middleware**

In the request logging middleware section of `app.py`, after setting `current_user_var` and `current_school_var`, add impersonation detection:

```python
# After current_school_var.set(school_id) block:
if payload.get("is_impersonation"):
    from edu_cloud.logging_config import impersonator_var
    impersonator_var.set(payload.get("impersonator_id"))
```

- [ ] **Step 2: Run backend tests**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_impersonate.py tests/test_api/test_auth_v2.py -v`
Expected: all PASS

- [ ] **Step 3: Commit**

```bash
cd /home/ops/projects/edu-cloud && git add src/edu_cloud/api/app.py && git commit -m "feat(logging): record impersonator_id in request logs"
```

---

### Task 10: 端到端验证

**覆盖范围：**
- 覆盖: 后端 impersonation API 正确性、get_current_user 两分支无回归、前端 store 状态管理、组件渲染、vite build 成功
- 未覆盖: AI Agent 在 impersonation 下的 DataScope 端到端（需 AI chat 真实调用）、模拟中并发请求竞态、模拟 token 到期后前端自动退出（需手动验证或后续补充）、浏览器 E2E（Playwright）

- [ ] **Step 1: Run full backend test suite**

Run: `cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5`
Expected: no new failures beyond known baseline (33 failed)

- [ ] **Step 2: Run full frontend test suite**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vitest run 2>&1 | tail -5`
Expected: all PASS (0 failed)

- [ ] **Step 3: Build frontend**

Run: `cd /home/ops/projects/edu-cloud/frontend && npx vite build`
Expected: build success, dist/ updated

- [ ] **Step 4: Manual smoke test list (user verification)**

1. 登录 admin/123456 → 侧边栏应有"角色模拟"入口
2. 进入 /admin/impersonate → 学校列表加载
3. 搜索学校 → 过滤正常
4. 选择学校 → 右列显示角色 chips
5. 选择"科任教师" → 出现班级/学科选择器
6. 选择班级+学科 → "进入模拟"按钮可点
7. 点击进入 → 顶栏出现橙色模拟状态条
8. 菜单变为教师可见的菜单项
9. 访问数据页面 → 只显示 scope 内数据
10. 点"退出模拟" → 恢复超管身份
11. 刷新页面 → 模拟状态保持（在退出前）

---

## 隐患防护清单

| 隐患 | 防护措施 | 实现位置 |
|------|---------|---------|
| 审计断链 | JWT `sub` = impersonator_id + `impersonator_var` ContextVar | Task 2, 9 |
| DataScope 无数据 | `build_from_override` 从 JWT claims 构造，不查表 | Task 4 |
| UserRole 污染 | 不创建 UserRole 记录，虚拟 `_ImpersonatedRole` 类 | Task 2 |
| Token 泄漏 | 30 分钟短过期 | Task 1 |
| 前端状态不刷新 | `impersonate()` 后调 `loadModules()` + 跳转首页 | Task 5 |
| 非超管调用 | 端点内 + `get_current_user` 双重校验 platform_admin | Task 2, 3 |
| 页面刷新丢状态 | `localStorage['impersonation']` 持久化 | Task 5 |
| 未知角色 | `ImpersonateRequest.role` Pydantic validator 白名单 | Task 3 |

---

## semantic_regression（ORC 不变量）

| 编号 | 不变量 | 验证方式 |
|------|--------|---------|
| INV-01 | 正常用户（非 impersonation token）认证流程不变 | `test_auth_v2.py` 全绿 |
| INV-02 | switch-role 仍仅允许切换自己的 UserRole | `test_auth_v2.py` 现有切换测试 |
| INV-03 | 非 platform_admin 无法调用 impersonate | `test_impersonate_requires_platform_admin` |
| INV-04 | 模拟 token 过期后无法使用 | JWT 标准过期机制 |
| INV-05 | 审计日志始终包含真实操作者 ID | `impersonator_var` + 日志格式 |
