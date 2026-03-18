# edu-cloud P1 联考 MVP 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 edu-cloud 联考 MVP——学校管理 CRUD、联考生命周期（创建→模板上传→下发→成绩收集→排名）、exam-ai 同步客户端，2 所模拟学校端到端验证。

**Architecture:** edu-cloud（FastAPI + SQLAlchemy 2.0 async）新增 3 个 Service（school/joint_exam/results）+ 改造现有 sync 端点 + 新增管理端点。exam-ai 新增 CloudSyncService（httpx 客户端）+ 4 个触发端点。TDD 驱动，先测试后实现。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, asyncpg, Pydantic v2, pytest-asyncio, httpx, bcrypt, aiofiles

**Design doc:** `docs/plans/2026-03-18-joint-exam-mvp-design.md`

---

## File Structure

### edu-cloud 新增/修改文件

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/edu_cloud/services/exceptions.py` | 创建 | 自定义异常（5 类）+ 全局处理器注册函数 |
| `src/edu_cloud/services/school_service.py` | 创建 | 学校 CRUD + API Key 管理 |
| `src/edu_cloud/services/joint_exam_service.py` | 创建 | 联考生命周期 + 模板管理 + 成绩提交 |
| `src/edu_cloud/services/results_service.py` | 创建 | 排名 + 按校对比 + 学生明细 |
| `src/edu_cloud/api/schools.py` | 创建 | 学校管理 REST 端点 |
| `src/edu_cloud/api/joint_exams.py` | 创建 | 联考管理 REST 端点 |
| `src/edu_cloud/api/results.py` | 创建 | 成绩查看 REST 端点 |
| `src/edu_cloud/api/sync.py` | 修改 | 改造 pull_joint_exams/upload_scores + 新增 templates 端点 |
| `src/edu_cloud/api/app.py` | 修改 | 注册新路由 + 全局异常处理器 |
| `src/edu_cloud/api/deps.py` | 修改 | 新增 require_permission 依赖 |
| `src/edu_cloud/models/joint_exam.py` | 修改 | JointExam 新字段 + JointExamStudentResult 新模型 + 状态机改造 |
| `src/edu_cloud/config.py` | 修改 | 新增 UPLOAD_DIR 配置 |
| `tests/conftest.py` | 修改 | 新增 auth_headers/school fixtures |
| `tests/test_services/test_school_service.py` | 创建 | SchoolService 单测 |
| `tests/test_services/test_joint_exam_service.py` | 创建 | JointExamService 单测 |
| `tests/test_services/test_results_service.py` | 创建 | ResultsService 单测 |
| `tests/test_api/test_schools.py` | 创建 | 学校管理 API 集成测试 |
| `tests/test_api/test_joint_exams.py` | 创建 | 联考管理 API 集成测试 |
| `tests/test_api/test_results.py` | 创建 | 成绩查看 API 集成测试 |
| `tests/test_api/test_sync_v2.py` | 创建 | 改造后 sync 端点测试 |
| `scripts/e2e_joint_exam.py` | 创建 | 端到端验证脚本 |

### exam-ai 新增文件（Phase 4）

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/exam_ai/services/cloud_sync.py` | 创建 | 云端同步服务（httpx 客户端） |
| `src/exam_ai/api/cloud_sync.py` | 创建 | 同步触发 API 端点 |
| `src/exam_ai/config.py` | 修改 | 新增 CLOUD_* 配置 |
| `src/exam_ai/api/app.py` | 修改 | 条件注册 cloud_sync 路由 |
| `tests/test_services/test_cloud_sync.py` | 创建 | mock httpx 单测 |
| `tests/test_api/test_cloud_sync.py` | 创建 | API 集成测试 |

---

## Phase 1: 基础设施 + 异常体系 + 权限依赖

### Task 1: 异常体系 + 全局异常处理器

**Files:**
- Create: `src/edu_cloud/services/exceptions.py`
- Modify: `src/edu_cloud/api/app.py`
- Test: `tests/test_services/test_exceptions.py`

**Testable Slices:**
1. 异常类定义 → test: `test_exception_classes_exist`
2. 全局处理器映射正确状态码 → test: `test_not_found_returns_404`, `test_state_error_returns_409`
3. 未知异常不被处理器吞掉 → test: `test_unhandled_exception_propagates`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_exceptions.py
import pytest
from edu_cloud.services.exceptions import (
    NotFoundError, PermissionDeniedError, ValidationError,
    ConflictError, StateError,
)


def test_exception_classes_exist():
    """All 5 custom exceptions are importable and are Exception subclasses."""
    for cls in [NotFoundError, PermissionDeniedError, ValidationError, ConflictError, StateError]:
        assert issubclass(cls, Exception)
        exc = cls("test message")
        assert str(exc) == "test message"


@pytest.mark.asyncio
async def test_not_found_returns_404(client):
    """Global handler maps NotFoundError → 404."""
    # GET a non-existent school triggers NotFoundError from service
    resp = await client.get(
        "/api/v1/schools/nonexistent-id",
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_state_error_returns_409(client):
    """Global handler maps StateError → 409."""
    # Will be tested via distribute on draft exam (no templates)
    pass  # placeholder — full test in Task 5
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_exceptions.py -v`
Expected: ImportError (exceptions.py doesn't exist)

- [ ] **Step 3: Implement exceptions + handler**

```python
# src/edu_cloud/services/exceptions.py
"""Service-layer exceptions. Decoupled from FastAPI — no HTTPException here."""


class NotFoundError(Exception):
    """Resource not found."""


class PermissionDeniedError(Exception):
    """Insufficient permissions."""


class ValidationError(Exception):
    """Input validation failed."""


class ConflictError(Exception):
    """Resource conflict (e.g., duplicate)."""


class StateError(Exception):
    """Illegal state transition."""
```

Modify `src/edu_cloud/api/app.py` — add after `app = FastAPI(...)`:

```python
from fastapi.responses import JSONResponse
from edu_cloud.services.exceptions import (
    NotFoundError, PermissionDeniedError, ValidationError as SvcValidationError,
    ConflictError, StateError,
)

@app.exception_handler(NotFoundError)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(PermissionDeniedError)
async def permission_denied_handler(request, exc):
    return JSONResponse(status_code=403, content={"detail": str(exc)})

@app.exception_handler(SvcValidationError)
async def validation_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})

@app.exception_handler(ConflictError)
async def conflict_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(StateError)
async def state_error_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})
```

- [ ] **Step 4: Run tests, verify pass**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_exceptions.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/exceptions.py src/edu_cloud/api/app.py tests/test_services/test_exceptions.py
git commit -m "feat: 异常体系 + 全局异常处理器（5 类 → HTTP 状态码映射）"
```

**审查清单:**
- ✓ 5 个异常类均可导入且继承 Exception
- ✓ 全局处理器注册在 app 上
- ✗ 异常类不导入 FastAPI 任何内容
- 关键行为: NotFoundError→404, StateError→409, ConflictError→409

**边界条件:**
- 异常消息为空字符串 → 期望: 返回 `{"detail": ""}`, 不抛异常
- 异常消息含中文 → 期望: JSON 正确编码，不乱码
- 非注册异常类 → 期望: 走 FastAPI 默认 500 处理

---

### Task 2: 权限依赖 + 测试 fixtures

**Files:**
- Modify: `src/edu_cloud/api/deps.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_api/test_deps.py`

**Testable Slices:**
1. require_permission 工厂函数 → test: `test_admin_has_all_permissions`, `test_observer_cannot_manage`
2. conftest fixtures（auth_headers, seed_school） → test: 被后续 Task 使用

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api/test_deps.py
import pytest


@pytest.mark.asyncio
async def test_admin_has_manage_schools(client, admin_headers):
    """platform_admin can access school management endpoints."""
    resp = await client.get("/api/v1/schools", headers=admin_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_unauthorized_without_token(client):
    """No token → 403 (HTTPBearer returns 403)."""
    resp = await client.get("/api/v1/schools")
    assert resp.status_code == 403
```

- [ ] **Step 2: Run, verify fail (no admin_headers fixture, no /schools endpoint)**

- [ ] **Step 3: Implement**

Add to `src/edu_cloud/api/deps.py`:

```python
from edu_cloud.core.permissions import Permission, has_permission
from edu_cloud.services.exceptions import PermissionDeniedError


def require_permission(permission: Permission):
    """Factory: returns a FastAPI dependency that checks the user has a permission."""
    async def checker(user: PlatformUser = Depends(get_current_user)):
        if not has_permission(user.role, permission):
            raise PermissionDeniedError(
                f"Role '{user.role}' lacks permission '{permission.value}'"
            )
        return user
    return checker
```

Update `tests/conftest.py` — add:

```python
from edu_cloud.models.platform_user import PlatformUser
from edu_cloud.models.school import RegisteredSchool
from edu_cloud.shared.auth import create_access_token
import bcrypt


@pytest.fixture
async def admin_user(db):
    """Seed a platform_admin user and return it."""
    user = PlatformUser(
        username="admin_test",
        display_name="Test Admin",
        role="platform_admin",
    )
    user.set_password("test123")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def admin_headers(admin_user):
    """JWT Authorization headers for platform_admin."""
    token = create_access_token({"sub": admin_user.id, "role": admin_user.role})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_school(db):
    """Seed a test school with known API key."""
    secret = "test_secret_123"
    hashed = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
    school = RegisteredSchool(
        name="测试一校",
        code="SCHOOL01",
        api_key_hash=hashed,
        district="测试区",
    )
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school, secret  # return (school_model, plaintext_secret)


@pytest.fixture
def school_api_headers(seed_school):
    """X-API-Key headers for sync endpoints."""
    school, secret = seed_school
    return {"X-API-Key": f"{school.code}:{secret}"}
```

- [ ] **Step 4: Run tests (deps test will still fail — /schools doesn't exist yet; that's ok)**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/deps.py tests/conftest.py tests/test_api/test_deps.py
git commit -m "feat: require_permission 依赖 + 测试 fixtures（admin/school）"
```

**审查清单:**
- ✓ require_permission 使用 has_permission() 检查
- ✓ 权限不足抛 PermissionDeniedError（非 HTTPException）
- ✗ deps.py 不直接导入具体 Service
- 关键行为: platform_admin 有全部权限, observer 只读

---

## Phase 2: 学校管理 CRUD

### Task 3: SchoolService

**Files:**
- Create: `src/edu_cloud/services/school_service.py`
- Test: `tests/test_services/test_school_service.py`

**Testable Slices:**
1. create_school 生成 API Key 并 bcrypt 存储 → test: `test_create_school_returns_plaintext_key`
2. list_schools 支持 district/is_active 过滤 → test: `test_list_schools_filter_district`
3. rotate_api_key 旧 key 失效新 key 可用 → test: `test_rotate_key_invalidates_old`
4. get/update 基础 CRUD → test: `test_update_school_deactivate`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_school_service.py
import pytest
import bcrypt
from edu_cloud.services.school_service import SchoolService
from edu_cloud.services.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_create_school_returns_plaintext_key(db):
    svc = SchoolService(db)
    school, plaintext_key = await svc.create_school(
        name="测试学校", code="TEST01", district="海淀区"
    )
    assert school.code == "TEST01"
    assert school.name == "测试学校"
    assert ":" in plaintext_key  # format: CODE:secret
    # Verify bcrypt hash matches
    _, secret = plaintext_key.split(":", 1)
    assert bcrypt.checkpw(secret.encode(), school.api_key_hash.encode())


@pytest.mark.asyncio
async def test_create_school_duplicate_code_raises(db):
    svc = SchoolService(db)
    await svc.create_school(name="A校", code="DUP01", district="X区")
    with pytest.raises(Exception):  # IntegrityError or ConflictError
        await svc.create_school(name="B校", code="DUP01", district="Y区")


@pytest.mark.asyncio
async def test_list_schools_filter_district(db):
    svc = SchoolService(db)
    await svc.create_school(name="A校", code="A01", district="海淀区")
    await svc.create_school(name="B校", code="B01", district="朝阳区")
    schools = await svc.list_schools(district="海淀区")
    assert len(schools) == 1
    assert schools[0].code == "A01"


@pytest.mark.asyncio
async def test_list_schools_filter_active(db):
    svc = SchoolService(db)
    s1, _ = await svc.create_school(name="A校", code="A01", district="X区")
    await svc.create_school(name="B校", code="B01", district="X区")
    await svc.update_school(s1.id, is_active=False)
    active = await svc.list_schools(is_active=True)
    assert all(s.is_active for s in active)


@pytest.mark.asyncio
async def test_get_school_not_found(db):
    svc = SchoolService(db)
    with pytest.raises(NotFoundError):
        await svc.get_school("nonexistent-id")


@pytest.mark.asyncio
async def test_update_school_deactivate(db):
    svc = SchoolService(db)
    school, _ = await svc.create_school(name="X校", code="X01", district="X区")
    updated = await svc.update_school(school.id, is_active=False)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_rotate_key_invalidates_old(db):
    svc = SchoolService(db)
    school, old_key = await svc.create_school(name="R校", code="R01", district="X区")
    _, old_secret = old_key.split(":", 1)

    new_key = await svc.rotate_api_key(school.id)
    _, new_secret = new_key.split(":", 1)

    # Old key no longer works
    assert not bcrypt.checkpw(old_secret.encode(), school.api_key_hash.encode())
    # New key works
    assert bcrypt.checkpw(new_secret.encode(), school.api_key_hash.encode())
```

- [ ] **Step 2: Run, verify fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_school_service.py -v`

- [ ] **Step 3: Implement**

```python
# src/edu_cloud/services/school_service.py
"""学校管理服务。"""
import secrets
import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.school import RegisteredSchool
from edu_cloud.services.exceptions import NotFoundError, ConflictError


class SchoolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_school(
        self, name: str, code: str, district: str
    ) -> tuple[RegisteredSchool, str]:
        # Check uniqueness
        existing = (
            await self.db.execute(
                select(RegisteredSchool).where(RegisteredSchool.code == code)
            )
        ).scalar_one_or_none()
        if existing:
            raise ConflictError(f"School code '{code}' already exists")

        secret = secrets.token_urlsafe(32)
        api_key_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
        plaintext_key = f"{code}:{secret}"

        school = RegisteredSchool(
            name=name, code=code, district=district, api_key_hash=api_key_hash,
        )
        self.db.add(school)
        await self.db.commit()
        await self.db.refresh(school)
        return school, plaintext_key

    async def list_schools(
        self, district: str | None = None, is_active: bool | None = None,
    ) -> list[RegisteredSchool]:
        q = select(RegisteredSchool)
        if district is not None:
            q = q.where(RegisteredSchool.district == district)
        if is_active is not None:
            q = q.where(RegisteredSchool.is_active == is_active)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_school(self, school_id: str) -> RegisteredSchool:
        result = await self.db.execute(
            select(RegisteredSchool).where(RegisteredSchool.id == school_id)
        )
        school = result.scalar_one_or_none()
        if not school:
            raise NotFoundError(f"School '{school_id}' not found")
        return school

    async def update_school(self, school_id: str, **fields) -> RegisteredSchool:
        school = await self.get_school(school_id)
        for key, value in fields.items():
            if hasattr(school, key):
                setattr(school, key, value)
        await self.db.commit()
        await self.db.refresh(school)
        return school

    async def rotate_api_key(self, school_id: str) -> str:
        school = await self.get_school(school_id)
        secret = secrets.token_urlsafe(32)
        school.api_key_hash = bcrypt.hashpw(secret.encode(), bcrypt.gensalt()).decode()
        await self.db.commit()
        return f"{school.code}:{secret}"
```

- [ ] **Step 4: Run tests, verify pass**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/school_service.py tests/test_services/test_school_service.py
git commit -m "feat: SchoolService — CRUD + API Key 生成/轮换（7 tests）"
```

**审查清单:**
- ✓ create_school 返回明文 key 且仅此一次
- ✓ bcrypt hash 存储，明文不持久化
- ✓ rotate_api_key 旧 key 立即失效
- ✗ Service 不导入 FastAPI

**边界条件:**
- 重复 code 创建 → 期望: ConflictError
- 不存在的 school_id → 期望: NotFoundError
- update 传入不存在的字段 → 期望: 静默忽略（hasattr 检查）

---

### Task 4: 学校管理 API 端点

**Files:**
- Create: `src/edu_cloud/api/schools.py`
- Modify: `src/edu_cloud/api/app.py` (register router)
- Test: `tests/test_api/test_schools.py`

**Testable Slices:**
1. POST /schools 创建学校返回 key → test: `test_create_school_api`
2. GET /schools 列表+过滤 → test: `test_list_schools_api`
3. PATCH /schools/{id} 更新 → test: `test_update_school_api`
4. 权限控制 observer 不能创建 → test: `test_observer_cannot_create_school`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api/test_schools.py
import pytest


@pytest.mark.asyncio
async def test_create_school_api(client, admin_headers):
    resp = await client.post("/api/v1/schools", json={
        "name": "API测试校", "code": "API01", "district": "测试区",
    }, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["code"] == "API01"
    assert "api_key" in data  # plaintext key returned once


@pytest.mark.asyncio
async def test_list_schools_api(client, admin_headers):
    # Create 2 schools
    await client.post("/api/v1/schools", json={
        "name": "A校", "code": "LSA", "district": "X区",
    }, headers=admin_headers)
    await client.post("/api/v1/schools", json={
        "name": "B校", "code": "LSB", "district": "Y区",
    }, headers=admin_headers)
    # List all
    resp = await client.get("/api/v1/schools", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) >= 2
    # Filter by district
    resp = await client.get("/api/v1/schools?district=X区", headers=admin_headers)
    assert all(s["district"] == "X区" for s in resp.json())


@pytest.mark.asyncio
async def test_get_school_api(client, admin_headers):
    create_resp = await client.post("/api/v1/schools", json={
        "name": "详情校", "code": "DET01", "district": "Z区",
    }, headers=admin_headers)
    school_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/schools/{school_id}", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["code"] == "DET01"


@pytest.mark.asyncio
async def test_update_school_api(client, admin_headers):
    create_resp = await client.post("/api/v1/schools", json={
        "name": "更新校", "code": "UPD01", "district": "W区",
    }, headers=admin_headers)
    school_id = create_resp.json()["id"]
    resp = await client.patch(f"/api/v1/schools/{school_id}", json={
        "is_active": False,
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_rotate_key_api(client, admin_headers):
    create_resp = await client.post("/api/v1/schools", json={
        "name": "轮换校", "code": "ROT01", "district": "V区",
    }, headers=admin_headers)
    school_id = create_resp.json()["id"]
    resp = await client.post(f"/api/v1/schools/{school_id}/rotate-key", headers=admin_headers)
    assert resp.status_code == 200
    assert "api_key" in resp.json()


@pytest.mark.asyncio
async def test_get_nonexistent_school_404(client, admin_headers):
    resp = await client.get("/api/v1/schools/nonexistent", headers=admin_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
# src/edu_cloud/api/schools.py
"""学校管理 REST 端点。"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.services.school_service import SchoolService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/schools", tags=["schools"])


class CreateSchoolRequest(BaseModel):
    name: str
    code: str
    district: str


class UpdateSchoolRequest(BaseModel):
    name: str | None = None
    district: str | None = None
    is_active: bool | None = None


@router.post("", status_code=201)
async def create_school(
    req: CreateSchoolRequest,
    user=Depends(require_permission(Permission.MANAGE_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    school, plaintext_key = await svc.create_school(
        name=req.name, code=req.code, district=req.district,
    )
    logger.info("school created: code=%s by user=%s", req.code, user.username)
    return {
        "id": school.id, "name": school.name, "code": school.code,
        "district": school.district, "is_active": school.is_active,
        "api_key": plaintext_key,
    }


@router.get("")
async def list_schools(
    district: str | None = None,
    is_active: bool | None = None,
    user=Depends(require_permission(Permission.VIEW_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    schools = await svc.list_schools(district=district, is_active=is_active)
    return [
        {"id": s.id, "name": s.name, "code": s.code, "district": s.district,
         "is_active": s.is_active, "last_heartbeat": str(s.last_heartbeat) if s.last_heartbeat else None}
        for s in schools
    ]


@router.get("/{school_id}")
async def get_school(
    school_id: str,
    user=Depends(require_permission(Permission.VIEW_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    s = await svc.get_school(school_id)
    return {
        "id": s.id, "name": s.name, "code": s.code, "district": s.district,
        "is_active": s.is_active, "last_heartbeat": str(s.last_heartbeat) if s.last_heartbeat else None,
        "client_version": s.client_version,
    }


@router.patch("/{school_id}")
async def update_school(
    school_id: str,
    req: UpdateSchoolRequest,
    user=Depends(require_permission(Permission.MANAGE_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    s = await svc.update_school(school_id, **fields)
    return {
        "id": s.id, "name": s.name, "code": s.code, "district": s.district,
        "is_active": s.is_active,
    }


@router.post("/{school_id}/rotate-key")
async def rotate_key(
    school_id: str,
    user=Depends(require_permission(Permission.MANAGE_SCHOOLS)),
    db: AsyncSession = Depends(get_db),
):
    svc = SchoolService(db)
    new_key = await svc.rotate_api_key(school_id)
    logger.info("api key rotated: school=%s by user=%s", school_id, user.username)
    return {"api_key": new_key}
```

Register in `app.py` — add after existing router registrations:

```python
from edu_cloud.api.schools import router as schools_router
app.include_router(schools_router)
```

- [ ] **Step 4: Run all tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/schools.py src/edu_cloud/api/app.py tests/test_api/test_schools.py
git commit -m "feat: 学校管理 API — CRUD + API Key 轮换（6 tests）"
```

**审查清单:**
- ✓ POST /schools 返回 201 + 明文 key
- ✓ MANAGE_SCHOOLS 权限控制 create/update/rotate
- ✓ VIEW_SCHOOLS 权限控制 list/get
- ✗ 响应不含 api_key_hash
- 关键行为: 404 for nonexistent school, 过滤参数正确传递

**边界条件:**
- 空 district 过滤 → 期望: 返回全部
- PATCH 空 body → 期望: 不修改，返回原数据
- 不存在的 school_id → 期望: 404

---

## Phase 3: 联考核心（模型改造 + Service + API）

### Task 5: 数据模型改造

**Files:**
- Modify: `src/edu_cloud/models/joint_exam.py`
- Modify: `src/edu_cloud/config.py`
- Test: `tests/test_models/test_joint_exam_models.py`

**Testable Slices:**
1. JointExam 新字段可读写 → test: `test_joint_exam_new_fields`
2. JointExamStudentResult 可创建+唯一约束 → test: `test_student_result_upsert`
3. JointExamParticipant 新字段 → test: `test_participant_is_creator`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models/test_joint_exam_models.py
import pytest
from edu_cloud.models.joint_exam import (
    JointExam, JointExamParticipant, JointExamStudentResult,
)


@pytest.mark.asyncio
async def test_joint_exam_new_fields(db):
    exam = JointExam(
        name="测试联考",
        created_by="user-id",
        status="draft",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id="school-id",
        answer_detail_schema={"YW": [{"id": "q1", "max_score": 10}]},
    )
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    assert exam.creator_school_id == "school-id"
    assert exam.answer_detail_schema["YW"][0]["id"] == "q1"


@pytest.mark.asyncio
async def test_participant_is_creator(db):
    exam = JointExam(name="E", created_by="u", status="draft", subjects=[])
    db.add(exam)
    await db.commit()

    p = JointExamParticipant(
        joint_exam_id=exam.id, school_id="s1", is_creator=True,
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    assert p.is_creator is True
    assert p.status == "pending"


@pytest.mark.asyncio
async def test_student_result_create(db):
    exam = JointExam(name="E", created_by="u", status="draft", subjects=[])
    db.add(exam)
    await db.commit()

    result = JointExamStudentResult(
        joint_exam_id=exam.id,
        school_id="s1",
        subject_code="YW",
        student_name="张三",
        student_number="2026001",
        total_score=85.5,
        detail_scores=[{"question_id": "q1", "score": 8, "max_score": 10}],
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    assert result.total_score == 85.5
    assert result.detail_scores[0]["question_id"] == "q1"
```

- [ ] **Step 2: Run, verify fail (JointExamStudentResult doesn't exist)**

- [ ] **Step 3: Implement model changes**

Rewrite `src/edu_cloud/models/joint_exam.py`（现有 49 行 < 200 行，全量重写合规）:

```python
"""联考模型：跨校考试的编排与追踪。"""

from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, ForeignKey, JSON, Boolean, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class JointExam(Base, IdMixin, TimestampMixin):
    """联考主表。"""
    __tablename__ = "joint_exams"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("platform_users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # status: draft → templates_ready → distributed → collecting → completed → archived

    subjects: Mapped[list] = mapped_column(JSON, default=list)
    # [{"code": "YW", "name": "语文", "max_score": 150}, ...]

    # 新增字段
    creator_school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("registered_schools.id"), default=None
    )
    template_file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    answer_detail_schema: Mapped[dict | None] = mapped_column(JSON, default=None)
    # {"YW": [{"id": "q1", "max_score": 10, "type": "主观题"}, ...]}


class JointExamParticipant(Base, IdMixin, TimestampMixin):
    """联考参与学校。"""
    __tablename__ = "joint_exam_participants"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_schools.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # status: pending → scores_uploaded
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)

    student_count: Mapped[int | None] = mapped_column(Integer, default=None)
    score_upload_count: Mapped[int | None] = mapped_column(Integer, default=None)


class JointExamStudentResult(Base, IdMixin, TimestampMixin):
    """联考学生成绩明细（替代旧 JointExamScore）。"""
    __tablename__ = "joint_exam_student_results"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_schools.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    student_name: Mapped[str] = mapped_column(String(100))
    student_number: Mapped[str] = mapped_column(String(100))
    total_score: Mapped[float] = mapped_column(Float)
    detail_scores: Mapped[list] = mapped_column(JSON, default=list)
    # [{"question_id": "q1", "score": 5.0, "max_score": 10.0}, ...]
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "joint_exam_id", "school_id", "subject_code", "student_number",
            name="uq_result_student",
        ),
        Index("ix_result_ranking", "joint_exam_id", "subject_code", "total_score"),
        Index("ix_result_school", "joint_exam_id", "school_id"),
    )
```

Add to `src/edu_cloud/config.py`:

```python
    # File storage
    UPLOAD_DIR: str = "./uploads"
```

- [ ] **Step 4: Run tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/models/joint_exam.py src/edu_cloud/config.py tests/test_models/
git commit -m "feat: 数据模型改造 — JointExam 新字段 + JointExamStudentResult + 状态机重构"
```

**审查清单:**
- ✓ JointExamScore 类已删除
- ✓ JointExamStudentResult 有唯一约束和排名索引
- ✓ 新模型继承 Base + IdMixin + TimestampMixin
- ✗ 旧 sync.py 的 JointExamScore import 将会报错（Task 8 修复）

**边界条件:**
- answer_detail_schema 为 None → 期望: 正常，draft 状态允许
- detail_scores 为空列表 → 期望: 正常，total_score 为 0
- 重复 (exam_id, school_id, subject_code, student_number) 插入 → 期望: 唯一约束冲突

---

### Task 6: JointExamService — 创建 + 参与校管理

**Files:**
- Create: `src/edu_cloud/services/joint_exam_service.py`
- Test: `tests/test_services/test_joint_exam_service.py`

**Testable Slices:**
1. create_exam 创建联考+出题校 Participant → test: `test_create_exam_with_creator`
2. add/remove participant → test: `test_add_remove_participant`
3. distribute 状态推进校验 → test: `test_distribute_requires_templates_ready`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_joint_exam_service.py
import pytest
from edu_cloud.services.joint_exam_service import JointExamService
from edu_cloud.services.school_service import SchoolService
from edu_cloud.services.exceptions import NotFoundError, StateError
from edu_cloud.models.platform_user import PlatformUser


@pytest.fixture
async def setup(db):
    """Create user + 2 schools for testing."""
    user = PlatformUser(username="coord", display_name="C", role="exam_coordinator")
    user.set_password("test")
    db.add(user)
    await db.commit()

    svc = SchoolService(db)
    s1, _ = await svc.create_school("出题校", "CREATOR01", "区1")
    s2, _ = await svc.create_school("参与校", "PART01", "区1")
    return {"user": user, "s1": s1, "s2": s2, "db": db}


@pytest.mark.asyncio
async def test_create_exam_with_creator(setup):
    d = await setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="春季联考",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id,
        created_by=d["user"].id,
    )
    assert exam.status == "draft"
    assert exam.creator_school_id == d["s1"].id
    # Creator auto-added as participant
    detail = await svc.get_exam_detail(exam.id)
    creators = [p for p in detail["participants"] if p["is_creator"]]
    assert len(creators) == 1


@pytest.mark.asyncio
async def test_add_remove_participant(setup):
    d = await setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="E", subjects=[], creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    # Add participant
    p = await svc.add_participant(exam.id, d["s2"].id)
    assert p.school_id == d["s2"].id
    assert p.is_creator is False

    # Remove
    await svc.remove_participant(exam.id, d["s2"].id)
    detail = await svc.get_exam_detail(exam.id)
    assert len(detail["participants"]) == 1  # only creator left


@pytest.mark.asyncio
async def test_distribute_requires_templates_ready(setup):
    d = await setup
    svc = JointExamService(d["db"])
    exam = await svc.create_exam(
        name="E", subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    with pytest.raises(StateError, match="templates_ready"):
        await svc.distribute(exam.id)
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

Create `src/edu_cloud/services/joint_exam_service.py` with `create_exam`, `add_participant`, `remove_participant`, `distribute`, `get_exam_detail`. Full implementation references design §4.2. Key logic:
- `create_exam`: status=draft, auto-create Participant(is_creator=True)
- `distribute`: assert status==templates_ready, set to distributed
- `get_exam_detail`: join participants, return dict with progress

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/joint_exam_service.py tests/test_services/test_joint_exam_service.py
git commit -m "feat: JointExamService — 创建+参与校管理+下发（3 tests）"
```

**审查清单:**
- ✓ create_exam 自动添加出题校为 participant
- ✓ distribute 校验 status=templates_ready
- ✗ remove_participant 不能移除出题校

**边界条件:**
- 重复添加同一参与校 → 期望: ConflictError
- distribute 时 status=draft → 期望: StateError
- 移除出题校 → 期望: ValidationError

---

### Task 7: JointExamService — 模板上传 + 成绩提交 + 状态推进

**Files:**
- Modify: `src/edu_cloud/services/joint_exam_service.py`
- Test: `tests/test_services/test_joint_exam_service.py` (append)

**Testable Slices:**
1. upload_template 存储文件+写 schema+自动推进 → test: `test_upload_template_auto_promotes`
2. submit_scores upsert+状态推进 → test: `test_submit_scores_full_cycle`
3. force_complete 手动截止 → test: `test_force_complete`

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_services/test_joint_exam_service.py

@pytest.mark.asyncio
async def test_upload_template_auto_promotes(setup, tmp_path):
    d = await setup
    svc = JointExamService(d["db"], upload_dir=str(tmp_path))
    exam = await svc.create_exam(
        name="E",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id,
        created_by=d["user"].id,
    )
    assert exam.status == "draft"

    await svc.upload_template(
        exam_id=exam.id,
        subject_code="YW",
        skeleton_data={"regions": []},
        pdf_bytes=b"%PDF-fake",
        answer_schema=[{"id": "q1", "max_score": 10, "type": "主观题"}],
    )
    await d["db"].refresh(exam)
    assert exam.status == "templates_ready"  # auto-promoted (only 1 subject)
    assert exam.answer_detail_schema["YW"][0]["id"] == "q1"


@pytest.mark.asyncio
async def test_submit_scores_full_cycle(setup, tmp_path):
    d = await setup
    svc = JointExamService(d["db"], upload_dir=str(tmp_path))
    exam = await svc.create_exam(
        name="E",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id,
        created_by=d["user"].id,
    )
    # Upload template → promote → distribute
    await svc.upload_template(exam.id, "YW", {}, b"pdf", [{"id": "q1", "max_score": 10}])
    await svc.distribute(exam.id)
    assert exam.status == "distributed"

    # Submit scores from creator school
    await svc.submit_scores(exam.id, d["s1"].id, "YW", [
        {"student_name": "张三", "student_number": "001", "total_score": 85,
         "detail_scores": [{"question_id": "q1", "score": 8, "max_score": 10}]},
    ])
    await d["db"].refresh(exam)
    assert exam.status == "completed"  # only 1 participant (creator), 1 subject → auto-complete


@pytest.mark.asyncio
async def test_submit_scores_upsert(setup, tmp_path):
    d = await setup
    svc = JointExamService(d["db"], upload_dir=str(tmp_path))
    exam = await svc.create_exam(
        name="E", subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
        creator_school_id=d["s1"].id, created_by=d["user"].id,
    )
    await svc.upload_template(exam.id, "YW", {}, b"pdf", [])
    await svc.distribute(exam.id)

    # First submission
    await svc.submit_scores(exam.id, d["s1"].id, "YW", [
        {"student_name": "张三", "student_number": "001", "total_score": 80,
         "detail_scores": []},
    ])
    # Second submission (upsert — same student, updated score)
    await svc.submit_scores(exam.id, d["s1"].id, "YW", [
        {"student_name": "张三", "student_number": "001", "total_score": 90,
         "detail_scores": []},
    ])
    # Should have 1 record, not 2
    from sqlalchemy import select, func
    from edu_cloud.models.joint_exam import JointExamStudentResult
    count = (await d["db"].execute(
        select(func.count()).select_from(JointExamStudentResult)
    )).scalar()
    assert count == 1
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement upload_template + submit_scores + force_complete**

Key implementation notes:
- `upload_template`: write skeleton.json + template.pdf to upload_dir, update answer_detail_schema, check all subjects done → auto-promote
- `submit_scores`: upsert 使用 select→update/insert 两步法（兼容 SQLite 和 PostgreSQL）：
```python
for item in student_results:
    existing = (await self.db.execute(
        select(JointExamStudentResult).where(
            JointExamStudentResult.joint_exam_id == exam_id,
            JointExamStudentResult.school_id == school_id,
            JointExamStudentResult.subject_code == subject_code,
            JointExamStudentResult.student_number == item["student_number"],
        )
    )).scalar_one_or_none()
    if existing:
        existing.total_score = item["total_score"]
        existing.detail_scores = item["detail_scores"]
        existing.student_name = item["student_name"]
    else:
        self.db.add(JointExamStudentResult(...))
```
Update Participant.status; check completion
- `force_complete`: assert status in (distributed, collecting), set completed

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/joint_exam_service.py tests/test_services/test_joint_exam_service.py
git commit -m "feat: JointExamService — 模板上传+成绩提交+状态推进（3 tests）"
```

**审查清单:**
- ✓ upload_template 写文件+更新 schema
- ✓ 所有科目模板上传完自动 draft→templates_ready
- ✓ submit_scores upsert 不重复
- ✓ 所有参与校所有科目上报完自动 collecting→completed
- ✗ 非参与校提交 → NotFoundError

**边界条件:**
- 空 student_results 列表 → 期望: ValidationError
- 对已 completed 的联考提交成绩 → 期望: StateError
- 上传非联考科目的模板 → 期望: ValidationError

---

### Task 8: 联考管理 API + sync 端点改造

**Files:**
- Create: `src/edu_cloud/api/joint_exams.py`
- Modify: `src/edu_cloud/api/sync.py`
- Modify: `src/edu_cloud/api/app.py` (register router)
- Test: `tests/test_api/test_joint_exams.py`
- Test: `tests/test_api/test_sync_v2.py`

**Testable Slices:**
1. POST /joint-exams 创建联考 → test: `test_create_joint_exam_api`
2. POST /sync/templates 上传模板 → test: `test_upload_template_sync`
3. GET /sync/joint-exams 返回模板 URL → test: `test_pull_exams_with_template_url`
4. POST /sync/scores 提交逐题明细 → test: `test_upload_scores_detail`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_api/test_joint_exams.py
import pytest


@pytest.fixture
async def exam_setup(client, admin_headers):
    """Create 2 schools + return their IDs for exam tests."""
    r1 = await client.post("/api/v1/schools", json={
        "name": "出题校", "code": "JE_CR", "district": "区1",
    }, headers=admin_headers)
    r2 = await client.post("/api/v1/schools", json={
        "name": "参与校", "code": "JE_PT", "district": "区1",
    }, headers=admin_headers)
    return {
        "creator_id": r1.json()["id"],
        "participant_id": r2.json()["id"],
        "creator_key": r1.json()["api_key"],
        "participant_key": r2.json()["api_key"],
    }


@pytest.mark.asyncio
async def test_create_joint_exam_api(client, admin_headers, exam_setup):
    setup = await exam_setup
    resp = await client.post("/api/v1/joint-exams", json={
        "name": "春季联考",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
        "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "draft"
    assert data["creator_school_id"] == setup["creator_id"]


@pytest.mark.asyncio
async def test_add_participant_api(client, admin_headers, exam_setup):
    setup = await exam_setup
    # Create exam
    er = await client.post("/api/v1/joint-exams", json={
        "name": "E", "subjects": [], "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]
    # Add participant
    resp = await client.post(
        f"/api/v1/joint-exams/{exam_id}/participants",
        json={"school_id": setup["participant_id"]},
        headers=admin_headers,
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_distribute_api(client, admin_headers, exam_setup):
    setup = await exam_setup
    er = await client.post("/api/v1/joint-exams", json={
        "name": "E",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
        "creator_school_id": setup["creator_id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]
    # Upload template via sync endpoint (as creator school)
    import io
    resp = await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{"regions": []}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf"),
    }, data={
        "joint_exam_id": exam_id,
        "subject_code": "YW",
        "answer_schema": '[{"id": "q1", "max_score": 10}]',
    }, headers={"X-API-Key": setup["creator_key"]})
    assert resp.status_code == 200
    # Distribute
    resp = await client.post(
        f"/api/v1/joint-exams/{exam_id}/distribute", headers=admin_headers,
    )
    assert resp.status_code == 200
```

```python
# tests/test_api/test_sync_v2.py
import pytest
import io


@pytest.fixture
async def sync_setup(client, admin_headers):
    """Full setup: 2 schools + exam + template uploaded + distributed."""
    r1 = await client.post("/api/v1/schools", json={
        "name": "出题校", "code": "SY_CR", "district": "X",
    }, headers=admin_headers)
    r2 = await client.post("/api/v1/schools", json={
        "name": "参与校", "code": "SY_PT", "district": "X",
    }, headers=admin_headers)
    creator_key = r1.json()["api_key"]
    participant_key = r2.json()["api_key"]

    er = await client.post("/api/v1/joint-exams", json={
        "name": "同步测试联考",
        "subjects": [{"code": "YW", "name": "语文", "max_score": 150}],
        "creator_school_id": r1.json()["id"],
    }, headers=admin_headers)
    exam_id = er.json()["id"]

    # Add participant
    await client.post(f"/api/v1/joint-exams/{exam_id}/participants",
        json={"school_id": r2.json()["id"]}, headers=admin_headers)

    return {
        "exam_id": exam_id, "creator_key": creator_key,
        "participant_key": participant_key,
        "creator_id": r1.json()["id"], "participant_id": r2.json()["id"],
    }


@pytest.mark.asyncio
async def test_upload_template_sync(client, sync_setup):
    s = await sync_setup
    resp = await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{"regions": []}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"],
        "subject_code": "YW",
        "answer_schema": '[{"id": "q1", "max_score": 10}]',
    }, headers={"X-API-Key": s["creator_key"]})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pull_exams_with_template_url(client, admin_headers, sync_setup):
    s = await sync_setup
    # Upload + distribute first
    await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"], "subject_code": "YW",
        "answer_schema": '[{"id": "q1", "max_score": 10}]',
    }, headers={"X-API-Key": s["creator_key"]})
    await client.post(f"/api/v1/joint-exams/{s['exam_id']}/distribute", headers=admin_headers)

    # Pull as participant
    resp = await client.get("/api/v1/sync/joint-exams",
        headers={"X-API-Key": s["participant_key"]})
    assert resp.status_code == 200
    exams = resp.json()["joint_exams"]
    assert len(exams) >= 1
    subj = exams[0]["subjects"][0]
    assert "template_url" in subj
    assert "/sync/templates/" in subj["template_url"]


@pytest.mark.asyncio
async def test_upload_scores_detail(client, admin_headers, sync_setup):
    s = await sync_setup
    # Setup: upload template + distribute
    await client.post("/api/v1/sync/templates", files={
        "skeleton": ("skeleton.json", io.BytesIO(b'{}'), "application/json"),
        "pdf": ("template.pdf", io.BytesIO(b"%PDF"), "application/pdf"),
    }, data={
        "joint_exam_id": s["exam_id"], "subject_code": "YW",
        "answer_schema": '[]',
    }, headers={"X-API-Key": s["creator_key"]})
    await client.post(f"/api/v1/joint-exams/{s['exam_id']}/distribute", headers=admin_headers)

    # Upload scores with detail
    resp = await client.post("/api/v1/sync/scores", json={
        "joint_exam_id": s["exam_id"],
        "subject_code": "YW",
        "student_results": [
            {"student_name": "张三", "student_number": "001", "total_score": 85,
             "detail_scores": [{"question_id": "q1", "score": 8, "max_score": 10}]},
        ],
    }, headers={"X-API-Key": s["creator_key"]})
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_inactive_school_rejected(client, admin_headers, sync_setup):
    """已停用学校的 API Key 应返回 401。"""
    s = await sync_setup
    # Deactivate creator school
    await client.patch(f"/api/v1/schools/{s['creator_id']}",
        json={"is_active": False}, headers=admin_headers)
    # Try sync
    resp = await client.post("/api/v1/sync/heartbeat",
        json={"client_version": "1.0", "exam_ai_port": 8000},
        headers={"X-API-Key": s["creator_key"]})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

**`joint_exams.py`**: 创建/列表/详情/下发/截止/参与校管理（参照 schools.py 模式）。所有端点通过 `JointExamService` 调用。

**`sync.py` 改造** — 关键变更（旧 JointExamScore 引用全部替换）：

1. 删除 `ScoreItem`/`ScoreUploadRequest` 旧模型，替换为新模型：
```python
class StudentResultItem(BaseModel):
    student_name: str
    student_number: str
    total_score: float
    detail_scores: list[dict]  # [{"question_id": "q1", "score": 5.0, "max_score": 10.0}]

class ScoreUploadRequest(BaseModel):
    joint_exam_id: str
    subject_code: str
    student_results: list[StudentResultItem]
```

2. `upload_scores` 端点改为调用 `JointExamService.submit_scores()`（不再直接操作模型）

3. `pull_joint_exams` 过滤条件从 `["distributed", "scanning", "grading"]` 改为 `["distributed", "collecting"]`，响应增加 `template_url` 和 `answer_detail_schema`：
```python
resp["joint_exams"] = [{
    "id": e.id, "name": e.name, "status": e.status,
    "subjects": [
        {**subj, "template_url": f"{base_url}/api/v1/sync/templates/{e.id}/{subj['code']}",
         "answer_detail_schema": (e.answer_detail_schema or {}).get(subj["code"], [])}
        for subj in e.subjects
    ],
} for e in exams]
```

4. 新增 `POST /sync/templates`（multipart: skeleton + pdf + answer_schema JSON string）
5. 新增 `GET /sync/templates/{exam_id}/{subject_code}`（FileResponse 下载）
6. 删除所有 `JointExamScore` 导入（Grep 确认零残留）

- [ ] **Step 4: Run all tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/ -v`

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/api/joint_exams.py src/edu_cloud/api/sync.py src/edu_cloud/api/app.py \
    tests/test_api/test_joint_exams.py tests/test_api/test_sync_v2.py
git commit -m "feat: 联考管理 API + sync 端点改造（模板上传/下载 + 成绩新粒度）"
```

**审查清单:**
- ✓ POST /joint-exams 需要 CREATE_JOINT_EXAM 权限
- ✓ /sync/templates POST 接收 multipart（skeleton + pdf）
- ✓ /sync/joint-exams GET 返回 template_url 绝对路径
- ✓ /sync/scores POST 接收 detail_scores JSON
- ✗ 旧 JointExamScore 引用已全部替换

**边界条件:**
- 上传超大 PDF → 期望: 不限制（MVP）
- pull_joint_exams 无联考时 → 期望: 空列表
- 非参与校调用 /sync/scores → 期望: 403

---

## Phase 4: 成绩查看

### Task 9: ResultsService + API

**Files:**
- Create: `src/edu_cloud/services/results_service.py`
- Create: `src/edu_cloud/api/results.py`
- Modify: `src/edu_cloud/api/app.py` (register router)
- Test: `tests/test_services/test_results_service.py`
- Test: `tests/test_api/test_results.py`

**Testable Slices:**
1. get_rankings 按科目排名 → test: `test_rankings_by_subject`
2. get_rankings 全科总分排名 → test: `test_rankings_all_subjects`
3. get_school_comparison 按校对比 → test: `test_school_comparison`
4. get_student_detail → test: `test_student_detail`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_results_service.py
import pytest
from edu_cloud.services.results_service import ResultsService
from edu_cloud.models.joint_exam import JointExam, JointExamStudentResult


@pytest.fixture
async def results_data(db):
    """Seed exam + 2 schools × 3 students × 1 subject."""
    exam = JointExam(
        name="排名测试联考", created_by="user-id", status="completed",
        subjects=[{"code": "YW", "name": "语文", "max_score": 150}],
    )
    db.add(exam)
    await db.commit()

    students = [
        # school_id, name, number, score
        ("s1", "张三", "001", 90.0),
        ("s1", "李四", "002", 85.0),
        ("s1", "王五", "003", 70.0),
        ("s2", "赵六", "004", 95.0),
        ("s2", "孙七", "005", 60.0),
        ("s2", "周八", "006", 80.0),
    ]
    for sid, name, num, score in students:
        db.add(JointExamStudentResult(
            joint_exam_id=exam.id, school_id=sid, subject_code="YW",
            student_name=name, student_number=num, total_score=score,
            detail_scores=[{"question_id": "q1", "score": score, "max_score": 150}],
        ))
    await db.commit()
    return exam


@pytest.mark.asyncio
async def test_rankings_by_subject(db, results_data):
    exam = await results_data
    svc = ResultsService(db)
    rankings = await svc.get_rankings(exam.id, subject_code="YW")
    assert len(rankings) == 6
    # First place: 赵六 (95)
    assert rankings[0]["student_name"] == "赵六"
    assert rankings[0]["total_score"] == 95.0
    # Rank order is descending
    scores = [r["total_score"] for r in rankings]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_rankings_all_subjects(db, results_data):
    exam = await results_data
    svc = ResultsService(db)
    # With only 1 subject, all-subjects ranking = single-subject ranking
    rankings = await svc.get_rankings(exam.id, subject_code=None)
    assert len(rankings) == 6
    assert rankings[0]["total_score"] == 95.0


@pytest.mark.asyncio
async def test_school_comparison(db, results_data):
    exam = await results_data
    svc = ResultsService(db)
    comparison = await svc.get_school_comparison(exam.id)
    # 2 schools, each with 1 subject
    assert len(comparison) == 2
    for entry in comparison:
        assert "avg_score" in entry
        assert "max_score" in entry
        assert "median_score" in entry
        assert "student_count" in entry
    # s1: avg=(90+85+70)/3=81.67, s2: avg=(95+60+80)/3=78.33
    s1_entry = next(e for e in comparison if e["school_id"] == "s1")
    assert abs(s1_entry["avg_score"] - 81.67) < 0.1
    assert s1_entry["max_score"] == 90.0
    assert s1_entry["median_score"] == 85.0  # median of [70, 85, 90]


@pytest.mark.asyncio
async def test_student_detail(db, results_data):
    exam = await results_data
    svc = ResultsService(db)
    detail = await svc.get_student_detail(exam.id, "001")  # 张三
    assert detail["student_name"] == "张三"
    assert len(detail["subjects"]) == 1
    assert detail["subjects"][0]["total_score"] == 90.0
    assert detail["subjects"][0]["detail_scores"][0]["question_id"] == "q1"


@pytest.mark.asyncio
async def test_rankings_empty_exam(db):
    """无成绩数据的联考返回空列表。"""
    exam = JointExam(
        name="空联考", created_by="u", status="completed", subjects=[],
    )
    db.add(exam)
    await db.commit()
    svc = ResultsService(db)
    rankings = await svc.get_rankings(exam.id)
    assert rankings == []
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

```python
# src/edu_cloud/services/results_service.py
"""成绩查看服务。"""
import statistics
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.joint_exam import JointExamStudentResult
from edu_cloud.services.exceptions import NotFoundError


class ResultsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_rankings(
        self, exam_id: str, subject_code: str | None = None,
    ) -> list[dict]:
        if subject_code:
            # Single subject ranking
            q = (
                select(JointExamStudentResult)
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .where(JointExamStudentResult.subject_code == subject_code)
                .order_by(JointExamStudentResult.total_score.desc())
            )
            results = (await self.db.execute(q)).scalars().all()
            return [
                {"rank": i + 1, "student_name": r.student_name,
                 "student_number": r.student_number, "school_id": r.school_id,
                 "total_score": r.total_score}
                for i, r in enumerate(results)
            ]
        else:
            # All-subjects: SUM(total_score) GROUP BY student
            q = (
                select(
                    JointExamStudentResult.student_number,
                    JointExamStudentResult.student_name,
                    JointExamStudentResult.school_id,
                    func.sum(JointExamStudentResult.total_score).label("total"),
                )
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .group_by(
                    JointExamStudentResult.student_number,
                    JointExamStudentResult.student_name,
                    JointExamStudentResult.school_id,
                )
                .order_by(func.sum(JointExamStudentResult.total_score).desc())
            )
            rows = (await self.db.execute(q)).all()
            return [
                {"rank": i + 1, "student_name": r.student_name,
                 "student_number": r.student_number, "school_id": r.school_id,
                 "total_score": float(r.total)}
                for i, r in enumerate(rows)
            ]

    async def get_school_comparison(self, exam_id: str) -> list[dict]:
        """按学校+科目聚合。median 用 Python statistics.median（兼容 SQLite）。"""
        q = (
            select(
                JointExamStudentResult.school_id,
                JointExamStudentResult.subject_code,
                func.avg(JointExamStudentResult.total_score).label("avg"),
                func.max(JointExamStudentResult.total_score).label("max"),
                func.count().label("count"),
            )
            .where(JointExamStudentResult.joint_exam_id == exam_id)
            .group_by(
                JointExamStudentResult.school_id,
                JointExamStudentResult.subject_code,
            )
        )
        rows = (await self.db.execute(q)).all()

        result = []
        for row in rows:
            # Fetch individual scores for median (Python-side, compatible with SQLite)
            scores_q = (
                select(JointExamStudentResult.total_score)
                .where(JointExamStudentResult.joint_exam_id == exam_id)
                .where(JointExamStudentResult.school_id == row.school_id)
                .where(JointExamStudentResult.subject_code == row.subject_code)
            )
            scores = [s for (s,) in (await self.db.execute(scores_q)).all()]
            median = statistics.median(scores) if scores else 0.0

            result.append({
                "school_id": row.school_id,
                "subject_code": row.subject_code,
                "avg_score": round(float(row.avg), 2),
                "max_score": float(row.max),
                "median_score": median,
                "student_count": row.count,
            })
        return result

    async def get_student_detail(self, exam_id: str, student_number: str) -> dict:
        q = (
            select(JointExamStudentResult)
            .where(JointExamStudentResult.joint_exam_id == exam_id)
            .where(JointExamStudentResult.student_number == student_number)
        )
        results = (await self.db.execute(q)).scalars().all()
        if not results:
            raise NotFoundError(f"Student '{student_number}' not found in exam")
        return {
            "student_name": results[0].student_name,
            "student_number": student_number,
            "school_id": results[0].school_id,
            "subjects": [
                {"subject_code": r.subject_code, "total_score": r.total_score,
                 "detail_scores": r.detail_scores}
                for r in results
            ],
        }
```

API（`src/edu_cloud/api/results.py`）: 3 个 GET 端点，权限用 `require_permission(Permission.VIEW_JOINT_EXAM)`。注册到 `app.py`。

> **median 实现决策**: 使用 Python `statistics.median()`（从 DB 取全量分数后计算），兼容 SQLite 和 PostgreSQL。数据量小（MVP 2 校），性能不是问题。

- [ ] **Step 4: Run all tests**

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/results_service.py src/edu_cloud/api/results.py \
    src/edu_cloud/api/app.py tests/test_services/test_results_service.py tests/test_api/test_results.py
git commit -m "feat: 成绩查看 — 排名+按校对比+学生明细（4 tests）"
```

**审查清单:**
- ✓ 排名使用 total_score 列（不解析 JSON）
- ✓ 全科排名用 SUM(total_score)
- ✓ 按校对比含平均分/最高/参考人数
- ✗ 权限控制: observer 可查看, exam_coordinator 可查看

**边界条件:**
- 无成绩数据的联考 → 期望: 空列表
- 只有 1 所学校上报 → 期望: 正常排名，对比只有 1 校
- subject_code 不存在 → 期望: 空列表

---

## Phase 5: exam-ai sync client

### Task 10: exam-ai CloudSyncService + API

**Files:**
- Create: `C:/Users/Administrator/exam-ai/src/exam_ai/services/cloud_sync.py`
- Create: `C:/Users/Administrator/exam-ai/src/exam_ai/api/cloud_sync.py`
- Modify: `C:/Users/Administrator/exam-ai/src/exam_ai/config.py`
- Modify: `C:/Users/Administrator/exam-ai/src/exam_ai/api/app.py`
- Test: `C:/Users/Administrator/exam-ai/tests/test_services/test_cloud_sync.py`
- Test: `C:/Users/Administrator/exam-ai/tests/test_api/test_cloud_sync.py`

**Testable Slices:**
1. push_template 构造正确请求 → test: `test_push_template_request_format`
2. pull_joint_exams 解析响应 → test: `test_pull_exams_parses_response`
3. push_scores 组装逐题明细 → test: `test_push_scores_detail_format`
4. CLOUD_ENABLED=false 路由不注册 → test: `test_cloud_disabled_returns_404`

- [ ] **Step 0: 调研 exam-ai GradingResult 数据结构**

在 exam-ai 中 Grep `GradingResult` 模型，确认字段结构与 `detail_scores` 格式的映射关系：
```bash
cd C:/Users/Administrator/exam-ai && grep -n "class GradingResult" src/ -r
# 确认字段: question_id, score, max_score 等字段名和类型
```
将调研结果记录在 push_scores 实现注释中。

- [ ] **Step 1: Write failing tests (mock httpx)**

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement**

CloudSyncService: httpx.AsyncClient wrapper，4 个方法（push_template/pull_joint_exams/pull_template/push_scores）
API: 4 个端点（POST push-template/pull-exams/push-scores, GET status）
Config: CLOUD_ENABLED/CLOUD_URL/CLOUD_API_KEY（Optional when disabled）
app.py: `if settings.CLOUD_ENABLED: app.include_router(cloud_sync_router)`

- [ ] **Step 4: Run all exam-ai tests**

Run: `cd C:/Users/Administrator/exam-ai && python -m pytest --tb=short -q`
Expected: 440+ tests pass (existing + new)

- [ ] **Step 5: Commit**

```bash
cd C:/Users/Administrator/exam-ai
git add src/exam_ai/services/cloud_sync.py src/exam_ai/api/cloud_sync.py \
    src/exam_ai/config.py src/exam_ai/api/app.py \
    tests/test_services/test_cloud_sync.py tests/test_api/test_cloud_sync.py
git commit -m "feat: CloudSyncService — edu-cloud 同步客户端（手动触发 + CLOUD_ENABLED 开关）"
```

**审查清单:**
- ✓ httpx.AsyncClient 用 base_url + X-API-Key header
- ✓ CLOUD_ENABLED=false 时路由不注册、Service 不实例化
- ✓ push_scores 从 GradingResult 组装 detail_scores
- ✗ 不修改现有 exam-ai 模型或路由

**边界条件:**
- CLOUD_URL 未设置 + CLOUD_ENABLED=false → 期望: 无报错
- 云端返回 401 → 期望: 抛明确错误（API Key 无效）
- 云端不可达 → 期望: httpx.ConnectError, 不 hang

---

## Phase 6: 端到端验证

### Task 11: E2E 验证脚本 + CLAUDE.md 更新

**Files:**
- Create: `C:/Users/Administrator/edu-cloud/scripts/e2e_joint_exam.py`
- Modify: `C:/Users/Administrator/edu-cloud/CLAUDE.md`

- [ ] **Step 1: Write E2E script**

```python
# scripts/e2e_joint_exam.py
"""端到端联考验证脚本。模拟 2 所学校完整联考流程。"""
import asyncio
import httpx

CLOUD_URL = "http://localhost:9000"


async def main():
    async with httpx.AsyncClient(base_url=CLOUD_URL) as c:
        # Step 1: Login as admin
        r = await c.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        print("✓ Step 1: Admin login")

        # Step 2: Create 2 schools
        r1 = await c.post("/api/v1/schools", json={"name": "出题校", "code": "E2E_S1", "district": "测试区"}, headers=auth)
        assert r1.status_code == 201
        r2 = await c.post("/api/v1/schools", json={"name": "参与校", "code": "E2E_S2", "district": "测试区"}, headers=auth)
        assert r2.status_code == 201
        s1_id, s1_key = r1.json()["id"], r1.json()["api_key"]
        s2_id, s2_key = r2.json()["id"], r2.json()["api_key"]
        print("✓ Step 2: 2 schools created")

        # Step 3: Create joint exam (creator = s1)
        er = await c.post("/api/v1/joint-exams", json={
            "name": "E2E 联考", "creator_school_id": s1_id,
            "subjects": [{"code": "YW", "name": "语文", "max_score": 150},
                         {"code": "SX", "name": "数学", "max_score": 150}],
        }, headers=auth)
        assert er.status_code == 201
        exam_id = er.json()["id"]
        print(f"✓ Step 3: Exam created ({exam_id[:8]}...)")

        # Step 4: Add participant school
        await c.post(f"/api/v1/joint-exams/{exam_id}/participants",
            json={"school_id": s2_id}, headers=auth)
        print("✓ Step 4: Participant added")

        # Step 5: Upload templates (as creator school via sync)
        for subj in ["YW", "SX"]:
            r = await c.post("/api/v1/sync/templates", files={
                "skeleton": ("skeleton.json", b'{"regions": []}', "application/json"),
                "pdf": ("template.pdf", b"%PDF-fake-content", "application/pdf"),
            }, data={"joint_exam_id": exam_id, "subject_code": subj,
                     "answer_schema": f'[{{"id": "q1", "max_score": 75}}, {{"id": "q2", "max_score": 75}}]'},
               headers={"X-API-Key": s1_key})
            assert r.status_code == 200, f"Template upload {subj} failed: {r.text}"
        print("✓ Step 5: Templates uploaded (auto → templates_ready)")

        # Step 6: Distribute
        r = await c.post(f"/api/v1/joint-exams/{exam_id}/distribute", headers=auth)
        assert r.status_code == 200
        print("✓ Step 6: Distributed")

        # Step 7: Pull exams (as participant school)
        r = await c.get("/api/v1/sync/joint-exams", headers={"X-API-Key": s2_key})
        assert r.status_code == 200
        exams = r.json()["joint_exams"]
        assert len(exams) >= 1
        assert "template_url" in exams[0]["subjects"][0]
        print("✓ Step 7: Participant pulled exams (with template URLs)")

        # Step 8: Submit scores from both schools
        for key, sid, prefix in [(s1_key, s1_id, "S1"), (s2_key, s2_id, "S2")]:
            for subj in ["YW", "SX"]:
                students = [
                    {"student_name": f"{prefix}_学生{i}", "student_number": f"{prefix}_{i:03d}",
                     "total_score": 60 + i * 10,
                     "detail_scores": [{"question_id": "q1", "score": 30+i*5, "max_score": 75},
                                       {"question_id": "q2", "score": 30+i*5, "max_score": 75}]}
                    for i in range(1, 6)
                ]
                r = await c.post("/api/v1/sync/scores", json={
                    "joint_exam_id": exam_id, "subject_code": subj,
                    "student_results": students,
                }, headers={"X-API-Key": key})
                assert r.status_code == 200, f"Score upload failed: {r.text}"
        print("✓ Step 8: Scores submitted (both schools, both subjects)")

        # Step 9: Check exam status → completed
        r = await c.get(f"/api/v1/joint-exams/{exam_id}", headers=auth)
        assert r.json()["status"] == "completed"
        print("✓ Step 9: Exam status → completed")

        # Step 10: View rankings
        r = await c.get(f"/api/v1/joint-exams/{exam_id}/results?subject_code=YW", headers=auth)
        assert r.status_code == 200
        rankings = r.json()
        assert len(rankings) == 10  # 5 students × 2 schools
        print(f"✓ Step 10: Rankings (top: {rankings[0]['student_name']} = {rankings[0]['total_score']})")

        # Step 11: View school comparison
        r = await c.get(f"/api/v1/joint-exams/{exam_id}/results/by-school", headers=auth)
        assert r.status_code == 200
        comparison = r.json()
        assert len(comparison) >= 2
        print(f"✓ Step 11: School comparison ({len(comparison)} entries)")

        print("\n=== E2E 联考验证完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run against local dev server**

Run: Start edu-cloud on port 9000, then `python scripts/e2e_joint_exam.py`

- [ ] **Step 3: Update CLAUDE.md**

Update 实现状态表、API 端点列表、关联项目状态。

- [ ] **Step 4: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/ -v --tb=short`

- [ ] **Step 5: Commit**

```bash
git add scripts/e2e_joint_exam.py CLAUDE.md
git commit -m "feat: E2E 联考验证脚本 + CLAUDE.md 更新"
```

**审查清单:**
- ✓ E2E 覆盖完整数据流（§1 的 11 个步骤）
- ✓ 断言每一步的 HTTP 状态码和关键字段
- ✓ CLAUDE.md 实现状态与实际一致
- 关键行为: 2 所学校完整跑通创建→模板→下发→成绩→排名

---

## 审查清单汇总

每个 Task 的审查清单在 Task 末尾。全局检查：

- [ ] 所有 Service 不导入 FastAPI
- [ ] 所有异常通过全局处理器映射（无 HTTPException 直抛）
- [ ] API Key 明文仅在 create/rotate 响应中返回一次
- [ ] JointExamScore 旧模型不再被引用
- [ ] CLOUD_ENABLED=false 时 exam-ai 无任何副作用
- [ ] 端口号统一: edu-cloud=9000, exam-ai=8000
- [ ] CLAUDE.md 与实际 API/模型一致
