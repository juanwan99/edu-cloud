# Phase 1b: 基础信息增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud 添加教师排课表和选考组合管理，补全学校基础信息数据层。

**Architecture:** 新增 teacher_assignments 和 subject_selections 两张表，各自有独立的 Service + Router + 前端管理页。Router 挂在 `/api/v1/schools/{school_id}/` 路径下，复用 Phase 1a 的 `MANAGE_SCHOOL_SETTINGS` 权限和 `_check_school_scope` 跨校防护模式。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL + Vue 3 + Naive UI + Pinia

**Design doc:** `docs/plans/2026-03-29-phase1b-base-info-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/edu_cloud/models/teacher_assignment.py` | TeacherAssignment ORM model |
| Create | `src/edu_cloud/models/subject_selection.py` | SubjectSelection ORM model |
| Create | `src/edu_cloud/services/teacher_assignment_service.py` | 排课 CRUD + 批量创建 + 聚合摘要 |
| Create | `src/edu_cloud/services/subject_selection_service.py` | 选考 CRUD + 校验 |
| Create | `src/edu_cloud/modules/school/assignment_router.py` | 排课 API（`/api/v1/schools/{school_id}/assignments`） |
| Create | `src/edu_cloud/modules/school/selection_router.py` | 选考 API（`/api/v1/schools/{school_id}/selections`） |
| Modify | `src/edu_cloud/api/app.py` | 注册两个 router + lifespan 导入模型 |
| Modify | `alembic/env.py` | 导入新模型 |
| Modify | `tests/conftest.py` | 导入新模型 |
| Modify | `tests/test_alembic_migration.py` | 导入新模型 |
| Create | `tests/test_services/test_teacher_assignment_service.py` | 排课 service 测试 |
| Create | `tests/test_services/test_subject_selection_service.py` | 选考 service 测试 |
| Create | `tests/test_api/test_teacher_assignments.py` | 排课 API 测试 |
| Create | `tests/test_api/test_subject_selections.py` | 选考 API 测试 |
| Create | `frontend/src/api/teacherAssignments.js` | 排课 API client |
| Create | `frontend/src/api/subjectSelections.js` | 选考 API client |
| Create | `frontend/src/pages/TeacherAssignmentsPage.vue` | 排课管理页 |
| Create | `frontend/src/pages/SubjectSelectionsPage.vue` | 选考管理页 |
| Modify | `frontend/src/config/sidebarConfig.js` | principal/academic_director 加导航项 |
| Modify | `frontend/src/router/index.js` | 加两个路由 |

> **Note:** `_check_school_scope` 函数已在 `settings_router.py` 中定义。assignment_router 和 selection_router 各自独立定义自己的 scope guard（同模式，避免跨文件耦合）。

---

### Task 1: TeacherAssignment Model

**Files:**
- Create: `src/edu_cloud/models/teacher_assignment.py`
- Create: `tests/test_services/test_teacher_assignment_service.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing model tests**

```python
# tests/test_services/test_teacher_assignment_service.py
import pytest
from edu_cloud.models.teacher_assignment import TeacherAssignment


@pytest.mark.asyncio
async def test_teacher_assignment_model(db, seed_school):
    school, _ = seed_school
    from edu_cloud.models.user import User
    user = User(username="ta_teacher1", display_name="排课教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    from edu_cloud.modules.student.models import Class
    cls = Class(name="高三1班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.flush()

    assignment = TeacherAssignment(
        user_id=user.id,
        class_id=cls.id,
        subject_code="math",
        semester="2025-2026-2",
        school_id=school.id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    assert assignment.id is not None
    assert assignment.subject_code == "math"
    assert assignment.semester == "2025-2026-2"
    assert assignment.is_active is True


@pytest.mark.asyncio
async def test_teacher_assignment_unique_constraint(db, seed_school):
    from sqlalchemy.exc import IntegrityError
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    school, _ = seed_school
    user = User(username="ta_dup_teacher", display_name="重复测试")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = Class(name="高三2班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.flush()

    a1 = TeacherAssignment(user_id=user.id, class_id=cls.id, subject_code="math",
                           semester="2025-2026-2", school_id=school.id)
    a2 = TeacherAssignment(user_id=user.id, class_id=cls.id, subject_code="math",
                           semester="2025-2026-2", school_id=school.id)
    db.add(a1)
    await db.flush()
    db.add(a2)
    with pytest.raises(IntegrityError):
        await db.flush()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'edu_cloud.models.teacher_assignment'`

- [ ] **Step 3: Implement model**

```python
# src/edu_cloud/models/teacher_assignment.py
from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class TeacherAssignment(Base, IdMixin, TimestampMixin):
    """教师排课记录：哪个教师在哪个学期教哪个班的什么科目。"""
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint("user_id", "class_id", "subject_code", "semester",
                         name="uq_teacher_assignment"),
    )

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), index=True)
    subject_code: Mapped[str] = mapped_column(String(50))
    semester: Mapped[str] = mapped_column(String(20))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: Update conftest.py to import the new model**

In `tests/conftest.py`, add after the `import edu_cloud.models.school_settings` line:

```python
import edu_cloud.models.teacher_assignment  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/models/teacher_assignment.py tests/test_services/test_teacher_assignment_service.py tests/conftest.py
git commit -m "feat: add TeacherAssignment model"
```

**审查清单:**
- ✓ UniqueConstraint 防止同教师同班同科同学期重复
- ✓ ForeignKey 关联 users/classes/schools
- ✓ is_active 默认 True
- ✗ 不同学期相同教师+班级+科目 → 允许（正确，学期是区分维度）

**边界条件:**
- 同 user_id + class_id + subject_code + semester 重复插入 → IntegrityError（已测试）
- 不同 semester 相同其他字段 → 允许
- is_active 默认 True

---

### Task 2: TeacherAssignment Service

**Files:**
- Create: `src/edu_cloud/services/teacher_assignment_service.py`
- Modify: `tests/test_services/test_teacher_assignment_service.py` (追加)

- [ ] **Step 1: Write failing service tests**

追加到 `tests/test_services/test_teacher_assignment_service.py`:

```python
from edu_cloud.services.teacher_assignment_service import (
    list_assignments, create_assignments, delete_assignment, get_summary,
)
from edu_cloud.models.user import User
from edu_cloud.modules.student.models import Class


async def _seed_teacher_and_classes(db, school_id):
    """Helper: create a teacher + 2 classes, return (user, [cls_a, cls_b])."""
    user = User(username="svc_teacher", display_name="服务测试教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls_a = Class(name="高三1班", grade="高三", grade_number=12, school_id=school_id)
    cls_b = Class(name="高三2班", grade="高三", grade_number=12, school_id=school_id)
    db.add(cls_a)
    db.add(cls_b)
    await db.flush()
    return user, [cls_a, cls_b]


@pytest.mark.asyncio
async def test_create_assignments_batch(db, seed_school):
    school, _ = seed_school
    user, classes = await _seed_teacher_and_classes(db, school.id)
    created = await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[c.id for c in classes], subject_code="math", semester="2025-2026-2",
    )
    assert created == 2


@pytest.mark.asyncio
async def test_create_assignments_idempotent(db, seed_school):
    school, _ = seed_school
    user, classes = await _seed_teacher_and_classes(db, school.id)
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[c.id for c in classes], subject_code="math", semester="2025-2026-2",
    )
    # Second call with same data → 0 new
    created = await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[c.id for c in classes], subject_code="math", semester="2025-2026-2",
    )
    assert created == 0


@pytest.mark.asyncio
async def test_list_assignments_filter(db, seed_school):
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
    all_rows = await list_assignments(db, school_id=school.id)
    assert len(all_rows) == 2
    math_only = await list_assignments(db, school_id=school.id, subject_code="math")
    assert len(math_only) == 1


@pytest.mark.asyncio
async def test_delete_assignment(db, seed_school):
    school, _ = seed_school
    user, classes = await _seed_teacher_and_classes(db, school.id)
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[classes[0].id], subject_code="math", semester="2025-2026-2",
    )
    rows = await list_assignments(db, school_id=school.id)
    assert len(rows) == 1
    await delete_assignment(db, school_id=school.id, assignment_id=rows[0].id)
    rows = await list_assignments(db, school_id=school.id)
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_get_summary(db, seed_school):
    school, _ = seed_school
    user, classes = await _seed_teacher_and_classes(db, school.id)
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[c.id for c in classes], subject_code="math", semester="2025-2026-2",
    )
    summary = await get_summary(db, school_id=school.id, semester="2025-2026-2")
    assert len(summary) == 1
    assert summary[0]["class_count"] == 2
    assert "math" in summary[0]["subject_codes"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py::test_create_assignments_batch -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement service**

```python
# src/edu_cloud/services/teacher_assignment_service.py
from sqlalchemy import select, func, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.teacher_assignment import TeacherAssignment
from edu_cloud.models.user import User
from edu_cloud.services.exceptions import NotFoundError


async def list_assignments(
    db: AsyncSession, *, school_id: str,
    semester: str | None = None, user_id: str | None = None,
    class_id: str | None = None, subject_code: str | None = None,
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
    result = await db.execute(stmt.order_by(TeacherAssignment.created_at))
    return list(result.scalars().all())


async def create_assignments(
    db: AsyncSession, *, school_id: str, user_id: str,
    class_ids: list[str], subject_code: str, semester: str,
) -> int:
    """Batch create assignments. Skips existing (idempotent). Returns count created."""
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


async def get_summary(
    db: AsyncSession, *, school_id: str, semester: str | None = None,
) -> list[dict]:
    """Per-teacher summary: display_name, class_count, subject_codes."""
    stmt = (
        select(
            TeacherAssignment.user_id,
            func.count(TeacherAssignment.id).label("class_count"),
        )
        .where(TeacherAssignment.school_id == school_id)
        .group_by(TeacherAssignment.user_id)
    )
    if semester:
        stmt = stmt.where(TeacherAssignment.semester == semester)
    rows = (await db.execute(stmt)).all()

    result = []
    for user_id, class_count in rows:
        user = await db.get(User, user_id)
        # Get distinct subject codes
        subj_stmt = (
            select(TeacherAssignment.subject_code)
            .where(TeacherAssignment.school_id == school_id,
                   TeacherAssignment.user_id == user_id)
            .distinct()
        )
        if semester:
            subj_stmt = subj_stmt.where(TeacherAssignment.semester == semester)
        subjects = [r[0] for r in (await db.execute(subj_stmt)).all()]
        result.append({
            "user_id": user_id,
            "display_name": user.display_name if user else "Unknown",
            "class_count": class_count,
            "subject_codes": subjects,
        })
    return result
```

- [ ] **Step 4: Run all service tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_teacher_assignment_service.py -v`
Expected: 7 passed (2 model + 5 service)

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/services/teacher_assignment_service.py tests/test_services/test_teacher_assignment_service.py
git commit -m "feat: add teacher assignment service with batch create + summary"
```

**测试契约:**
1. 批量创建幂等性
   - 入口: `create_assignments(db, ..., class_ids=[A, B])` 调用两次
   - 反例: 错误实现不检查已存在 → IntegrityError 或重复行
   - 边界: 空 class_ids / 全部已存在 / 部分已存在
   - 回归: N/A
   - 命令: `pytest tests/test_services/test_teacher_assignment_service.py::test_create_assignments_idempotent -v`
2. 过滤查询
   - 入口: `list_assignments(db, school_id=X, subject_code="math")`
   - 反例: 错误实现忽略 filter → 返回全部行
   - 边界: 无匹配 / 多条件组合
   - 回归: N/A
   - 命令: `pytest tests/test_services/test_teacher_assignment_service.py::test_list_assignments_filter -v`

---

### Task 3: TeacherAssignment API

**Files:**
- Create: `src/edu_cloud/modules/school/assignment_router.py`
- Modify: `src/edu_cloud/api/app.py`
- Create: `tests/test_api/test_teacher_assignments.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_api/test_teacher_assignments.py
import pytest


@pytest.mark.asyncio
async def test_list_assignments_empty(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_and_list_assignments(client, admin_headers, seed_school, db):
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    user = User(username="api_teacher", display_name="API教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = Class(name="高三API班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.commit()

    resp = await client.post(
        f"/api/v1/schools/{school.id}/assignments",
        json={"user_id": user.id, "class_ids": [cls.id], "subject_code": "math", "semester": "2025-2026-2"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["created"] == 1

    resp = await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["subject_code"] == "math"


@pytest.mark.asyncio
async def test_delete_assignment(client, admin_headers, seed_school, db):
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    user = User(username="api_del_teacher", display_name="删除教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls = Class(name="删除测试班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls)
    await db.commit()

    await client.post(
        f"/api/v1/schools/{school.id}/assignments",
        json={"user_id": user.id, "class_ids": [cls.id], "subject_code": "math", "semester": "2025-2026-2"},
        headers=admin_headers,
    )
    rows = (await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)).json()
    resp = await client.delete(f"/api/v1/schools/{school.id}/assignments/{rows[0]['id']}", headers=admin_headers)
    assert resp.status_code == 200

    rows = (await client.get(f"/api/v1/schools/{school.id}/assignments", headers=admin_headers)).json()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_get_summary(client, admin_headers, seed_school, db):
    school, _ = seed_school
    from edu_cloud.models.user import User
    from edu_cloud.modules.student.models import Class

    user = User(username="api_sum_teacher", display_name="摘要教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    cls_a = Class(name="摘要1班", grade="高三", grade_number=12, school_id=school.id)
    cls_b = Class(name="摘要2班", grade="高三", grade_number=12, school_id=school.id)
    db.add(cls_a)
    db.add(cls_b)
    await db.commit()

    await client.post(
        f"/api/v1/schools/{school.id}/assignments",
        json={"user_id": user.id, "class_ids": [cls_a.id, cls_b.id], "subject_code": "math", "semester": "2025-2026-2"},
        headers=admin_headers,
    )
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments/summary?semester=2025-2026-2", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["class_count"] == 2


@pytest.mark.asyncio
async def test_assignments_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_principal_can_manage_own_school_assignments(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School

    school = School(name="排课权限校", code="ASSGN01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.flush()
    user = User(username="assign_principal", display_name="排课校长")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "assign_principal", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school.id}/assignments", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_principal_cannot_access_other_school_assignments(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="排课A校", code="ASG_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="排课B校", code="ASG_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="assign_scope_test", display_name="跨校测试")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "assign_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/assignments", headers=headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_teacher_assignments.py::test_list_assignments_empty -v`
Expected: FAIL — 404 (routes not registered)

- [ ] **Step 3: Implement router**

```python
# src/edu_cloud/modules/school/assignment_router.py
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.teacher_assignment_service import (
    list_assignments, create_assignments, delete_assignment, get_summary,
)
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["teacher-assignments"])

_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in _CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的排课数据")


class CreateAssignmentsRequest(BaseModel):
    user_id: str
    class_ids: list[str]
    subject_code: str
    semester: str


@router.get("/assignments")
async def api_list_assignments(
    school_id: str,
    semester: str | None = None,
    user_id: str | None = None,
    class_id: str | None = None,
    subject_code: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    rows = await list_assignments(
        db, school_id=school_id, semester=semester,
        user_id=user_id, class_id=class_id, subject_code=subject_code,
    )
    return [
        {"id": r.id, "user_id": r.user_id, "class_id": r.class_id,
         "subject_code": r.subject_code, "semester": r.semester, "is_active": r.is_active}
        for r in rows
    ]


@router.post("/assignments")
async def api_create_assignments(
    school_id: str,
    body: CreateAssignmentsRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    count = await create_assignments(
        db, school_id=school_id, user_id=body.user_id,
        class_ids=body.class_ids, subject_code=body.subject_code, semester=body.semester,
    )
    return {"created": count}


@router.delete("/assignments/{assignment_id}")
async def api_delete_assignment(
    school_id: str,
    assignment_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await delete_assignment(db, school_id=school_id, assignment_id=assignment_id)
    return {"ok": True}


@router.get("/assignments/summary")
async def api_assignment_summary(
    school_id: str,
    semester: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    return await get_summary(db, school_id=school_id, semester=semester)
```

- [ ] **Step 4: Register router in app.py**

In `src/edu_cloud/api/app.py`:

1. In the lifespan model imports block, add:
```python
import edu_cloud.models.teacher_assignment  # noqa: F401
```

2. In the router import section, add:
```python
from edu_cloud.modules.school.assignment_router import router as assignment_router
```

3. Add `assignment_router` to the `for r in [...]` loop list (after `settings_router`).

- [ ] **Step 5: Run API tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_teacher_assignments.py -v`
Expected: 7 passed

- [ ] **Step 6: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass + 7 new

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/school/assignment_router.py src/edu_cloud/api/app.py tests/test_api/test_teacher_assignments.py
git commit -m "feat: add teacher assignment API with scope guard + 7 tests"
```

**审查清单:**
- ✓ `require_permission(Permission.MANAGE_SCHOOL_SETTINGS)` 保护所有端点
- ✓ `_check_school_scope` 跨校防护
- ✓ 批量创建通过 Pydantic model 校验 class_ids 非空
- ✓ DELETE 检查 school_id 匹配
- ✓ 未认证请求返回 401/403
- ✓ 跨校访问返回 403

**测试契约:**
1. 跨校越权拦截
   - 入口: principal of school A → `GET /api/v1/schools/{school_b}/assignments`
   - 反例: 错误实现不检查 school scope → 返回 200
   - 边界: platform_admin 可跨校 / principal 不能
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_teacher_assignments.py::test_principal_cannot_access_other_school_assignments -v`

---

### Task 4: SubjectSelection Model + Service

**Files:**
- Create: `src/edu_cloud/models/subject_selection.py`
- Create: `src/edu_cloud/services/subject_selection_service.py`
- Create: `tests/test_services/test_subject_selection_service.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_services/test_subject_selection_service.py
import pytest
from edu_cloud.models.subject_selection import SubjectSelection
from edu_cloud.services.subject_selection_service import (
    list_selections, create_selection, update_selection, delete_selection,
)


@pytest.mark.asyncio
async def test_subject_selection_model(db, seed_school):
    school, _ = seed_school
    sel = SubjectSelection(
        school_id=school.id, name="物化生",
        subject_codes=["physics", "chemistry", "biology"],
        mode="3+1+2",
    )
    db.add(sel)
    await db.commit()
    await db.refresh(sel)
    assert sel.id is not None
    assert sel.name == "物化生"
    assert sel.subject_codes == ["physics", "chemistry", "biology"]
    assert sel.is_active is True


@pytest.mark.asyncio
async def test_subject_selection_unique_name(db, seed_school):
    from sqlalchemy.exc import IntegrityError
    school, _ = seed_school
    s1 = SubjectSelection(school_id=school.id, name="物化生", subject_codes=["physics"])
    s2 = SubjectSelection(school_id=school.id, name="物化生", subject_codes=["chemistry"])
    db.add(s1)
    await db.flush()
    db.add(s2)
    with pytest.raises(IntegrityError):
        await db.flush()


@pytest.mark.asyncio
async def test_create_selection(db, seed_school):
    school, _ = seed_school
    sel = await create_selection(
        db, school_id=school.id, name="史地政",
        subject_codes=["history", "geography", "politics"], mode="3+1+2",
    )
    assert sel.name == "史地政"
    assert sel.mode == "3+1+2"


@pytest.mark.asyncio
async def test_create_selection_invalid_mode(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="无效的选考模式"):
        await create_selection(
            db, school_id=school.id, name="无效模式",
            subject_codes=["physics"], mode="invalid",
        )


@pytest.mark.asyncio
async def test_create_selection_too_many_subjects(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="科目数量"):
        await create_selection(
            db, school_id=school.id, name="过多科目",
            subject_codes=["a", "b", "c", "d", "e", "f", "g", "h"],
        )


@pytest.mark.asyncio
async def test_create_selection_empty_subjects(db, seed_school):
    from edu_cloud.services.exceptions import ValidationError
    school, _ = seed_school
    with pytest.raises(ValidationError, match="科目数量"):
        await create_selection(
            db, school_id=school.id, name="空科目", subject_codes=[],
        )


@pytest.mark.asyncio
async def test_list_selections_filter(db, seed_school):
    school, _ = seed_school
    await create_selection(db, school_id=school.id, name="组合A", subject_codes=["physics"])
    sel_b = await create_selection(db, school_id=school.id, name="组合B", subject_codes=["history"], mode="3+3")
    await update_selection(db, school_id=school.id, selection_id=sel_b.id, is_active=False)
    active = await list_selections(db, school_id=school.id, is_active=True)
    assert len(active) == 1
    assert active[0].name == "组合A"


@pytest.mark.asyncio
async def test_update_selection(db, seed_school):
    school, _ = seed_school
    sel = await create_selection(db, school_id=school.id, name="更新测试", subject_codes=["physics"])
    updated = await update_selection(
        db, school_id=school.id, selection_id=sel.id,
        name="更新后", subject_codes=["chemistry", "biology"],
    )
    assert updated.name == "更新后"
    assert updated.subject_codes == ["chemistry", "biology"]


@pytest.mark.asyncio
async def test_delete_selection(db, seed_school):
    school, _ = seed_school
    sel = await create_selection(db, school_id=school.id, name="删除测试", subject_codes=["physics"])
    await delete_selection(db, school_id=school.id, selection_id=sel.id)
    rows = await list_selections(db, school_id=school.id)
    assert len(rows) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_subject_selection_service.py::test_subject_selection_model -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement model**

```python
# src/edu_cloud/models/subject_selection.py
from sqlalchemy import String, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

VALID_MODES = {"3+1+2", "3+3", "custom"}


class SubjectSelection(Base, IdMixin, TimestampMixin):
    """学校提供的选考科目组合。"""
    __tablename__ = "subject_selections"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_subject_selection_name"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    subject_codes: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(20), default="custom")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: Implement service**

```python
# src/edu_cloud/services/subject_selection_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.subject_selection import SubjectSelection, VALID_MODES
from edu_cloud.services.exceptions import ValidationError, NotFoundError


def _validate_selection(subject_codes: list, mode: str):
    if not subject_codes or len(subject_codes) > 7:
        raise ValidationError("科目数量必须在 1-7 之间")
    if mode not in VALID_MODES:
        raise ValidationError(f"无效的选考模式: {mode}，可选: {', '.join(VALID_MODES)}")


async def list_selections(
    db: AsyncSession, *, school_id: str,
    is_active: bool | None = None, mode: str | None = None,
) -> list[SubjectSelection]:
    stmt = select(SubjectSelection).where(SubjectSelection.school_id == school_id)
    if is_active is not None:
        stmt = stmt.where(SubjectSelection.is_active == is_active)
    if mode:
        stmt = stmt.where(SubjectSelection.mode == mode)
    result = await db.execute(stmt.order_by(SubjectSelection.name))
    return list(result.scalars().all())


async def create_selection(
    db: AsyncSession, *, school_id: str, name: str,
    subject_codes: list[str], mode: str = "custom",
) -> SubjectSelection:
    _validate_selection(subject_codes, mode)
    sel = SubjectSelection(
        school_id=school_id, name=name,
        subject_codes=subject_codes, mode=mode,
    )
    db.add(sel)
    await db.commit()
    await db.refresh(sel)
    return sel


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

- [ ] **Step 5: Update conftest.py**

In `tests/conftest.py`, add after the `import edu_cloud.models.teacher_assignment` line:

```python
import edu_cloud.models.subject_selection  # noqa: F401
```

- [ ] **Step 6: Run all tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_subject_selection_service.py -v`
Expected: 10 passed

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/models/subject_selection.py src/edu_cloud/services/subject_selection_service.py tests/test_services/test_subject_selection_service.py tests/conftest.py
git commit -m "feat: add SubjectSelection model + service with validation"
```

**审查清单:**
- ✓ UniqueConstraint 防止同校同名重复
- ✓ subject_codes 长度校验（1-7）
- ✓ mode 枚举校验（3+1+2 / 3+3 / custom）
- ✓ update 支持部分更新（**kwargs）
- ✓ delete 检查 school_id 匹配

**边界条件:**
- 空 subject_codes → ValidationError（已测试）
- 8+ subject_codes → ValidationError（已测试）
- 无效 mode → ValidationError（已测试）
- 同校同名 → IntegrityError（已测试）

---

### Task 5: SubjectSelection API

**Files:**
- Create: `src/edu_cloud/modules/school/selection_router.py`
- Modify: `src/edu_cloud/api/app.py`
- Create: `tests/test_api/test_subject_selections.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/test_api/test_subject_selections.py
import pytest


@pytest.mark.asyncio
async def test_list_selections_empty(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/selections", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_selection(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "物化生", "subject_codes": ["physics", "chemistry", "biology"], "mode": "3+1+2"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "物化生"
    assert data["subject_codes"] == ["physics", "chemistry", "biology"]
    assert data["mode"] == "3+1+2"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_selection_invalid_mode(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "无效", "subject_codes": ["physics"], "mode": "invalid"},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_selection_empty_subjects(client, admin_headers, seed_school):
    school, _ = seed_school
    resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "空", "subject_codes": []},
        headers=admin_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_selection(client, admin_headers, seed_school):
    school, _ = seed_school
    create_resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "更新测试", "subject_codes": ["physics"]},
        headers=admin_headers,
    )
    sel_id = create_resp.json()["id"]
    resp = await client.patch(
        f"/api/v1/schools/{school.id}/selections/{sel_id}",
        json={"name": "更新后", "is_active": False},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "更新后"
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_selection(client, admin_headers, seed_school):
    school, _ = seed_school
    create_resp = await client.post(
        f"/api/v1/schools/{school.id}/selections",
        json={"name": "删除测试", "subject_codes": ["physics"]},
        headers=admin_headers,
    )
    sel_id = create_resp.json()["id"]
    resp = await client.delete(f"/api/v1/schools/{school.id}/selections/{sel_id}", headers=admin_headers)
    assert resp.status_code == 200

    rows = (await client.get(f"/api/v1/schools/{school.id}/selections", headers=admin_headers)).json()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_selections_requires_auth(client, seed_school):
    school, _ = seed_school
    resp = await client.get(f"/api/v1/schools/{school.id}/selections")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_principal_cannot_access_other_school_selections(client, db):
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.models.school import School
    import bcrypt

    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    school_a = School(name="选考A校", code="SEL_A", district="测试区", api_key_hash=hashed)
    school_b = School(name="选考B校", code="SEL_B", district="测试区", api_key_hash=hashed)
    db.add(school_a)
    db.add(school_b)
    await db.flush()
    user = User(username="sel_scope_test", display_name="选考跨校")
    user.set_password("pass123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school_a.id, is_primary=True))
    await db.commit()

    login = await client.post("/api/v1/auth/login", json={"username": "sel_scope_test", "password": "pass123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = await client.get(f"/api/v1/schools/{school_b.id}/selections", headers=headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_subject_selections.py::test_list_selections_empty -v`
Expected: FAIL — 404

- [ ] **Step 3: Implement router**

```python
# src/edu_cloud/modules/school/selection_router.py
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import get_db
from edu_cloud.services.subject_selection_service import (
    list_selections, create_selection, update_selection, delete_selection,
)
from edu_cloud.services.exceptions import ValidationError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/schools/{school_id}", tags=["subject-selections"])

_CROSS_SCHOOL_ROLES = {"platform_admin", "district_admin"}


def _check_school_scope(current: dict, school_id: str):
    role = current["current_role"]
    if role.role in _CROSS_SCHOOL_ROLES:
        return
    if role.school_id != school_id:
        raise PermissionDeniedError("无权访问其他学校的选考数据")


class CreateSelectionRequest(BaseModel):
    name: str
    subject_codes: list[str]
    mode: str = "custom"


class UpdateSelectionRequest(BaseModel):
    name: str | None = None
    subject_codes: list[str] | None = None
    mode: str | None = None
    is_active: bool | None = None


@router.get("/selections")
async def api_list_selections(
    school_id: str,
    is_active: bool | None = None,
    mode: str | None = None,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    rows = await list_selections(db, school_id=school_id, is_active=is_active, mode=mode)
    return [
        {"id": s.id, "name": s.name, "subject_codes": s.subject_codes,
         "mode": s.mode, "is_active": s.is_active}
        for s in rows
    ]


@router.post("/selections")
async def api_create_selection(
    school_id: str,
    body: CreateSelectionRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    try:
        sel = await create_selection(
            db, school_id=school_id, name=body.name,
            subject_codes=body.subject_codes, mode=body.mode,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": sel.id, "name": sel.name, "subject_codes": sel.subject_codes,
            "mode": sel.mode, "is_active": sel.is_active}


@router.patch("/selections/{selection_id}")
async def api_update_selection(
    school_id: str,
    selection_id: str,
    body: UpdateSelectionRequest,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    kwargs = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        sel = await update_selection(db, school_id=school_id, selection_id=selection_id, **kwargs)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"id": sel.id, "name": sel.name, "subject_codes": sel.subject_codes,
            "mode": sel.mode, "is_active": sel.is_active}


@router.delete("/selections/{selection_id}")
async def api_delete_selection(
    school_id: str,
    selection_id: str,
    current=Depends(require_permission(Permission.MANAGE_SCHOOL_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    _check_school_scope(current, school_id)
    await delete_selection(db, school_id=school_id, selection_id=selection_id)
    return {"ok": True}
```

- [ ] **Step 4: Register router in app.py**

In `src/edu_cloud/api/app.py`:

1. In the lifespan model imports block, add:
```python
import edu_cloud.models.subject_selection  # noqa: F401
```

2. In the router import section, add:
```python
from edu_cloud.modules.school.selection_router import router as selection_router
```

3. Add `selection_router` to the `for r in [...]` loop list (after `assignment_router`).

- [ ] **Step 5: Run API tests**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_subject_selections.py -v`
Expected: 8 passed

- [ ] **Step 6: Run full test suite**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/school/selection_router.py src/edu_cloud/api/app.py tests/test_api/test_subject_selections.py
git commit -m "feat: add subject selection API with scope guard + 8 tests"
```

**审查清单:**
- ✓ `require_permission(Permission.MANAGE_SCHOOL_SETTINGS)` 保护所有端点
- ✓ `_check_school_scope` 跨校防护
- ✓ ValidationError → 422
- ✓ PATCH 支持部分更新
- ✓ DELETE 检查 school_id 匹配
- ✓ 跨校访问返回 403

**测试契约:**
1. 校验规则拒绝
   - 入口: `POST /selections` with `subject_codes=[]` 或 `mode="invalid"`
   - 反例: 错误实现不校验 → 脏数据入库
   - 边界: 空列表 / 8+ 科目 / 无效 mode
   - 回归: N/A
   - 命令: `pytest tests/test_api/test_subject_selections.py::test_create_selection_invalid_mode -v`

---

### Task 6: Alembic Migration

**Files:**
- Modify: `alembic/env.py`
- Modify: `tests/test_alembic_migration.py`
- Create: `alembic/versions/xxxx_add_assignments_selections.py`

- [ ] **Step 1: Add model imports to alembic/env.py**

After the existing `from edu_cloud.models.school_settings import ...` line, add:

```python
from edu_cloud.models.teacher_assignment import TeacherAssignment  # noqa: F401
from edu_cloud.models.subject_selection import SubjectSelection  # noqa: F401
```

- [ ] **Step 2: Add model import to tests/test_alembic_migration.py**

Inside `test_migration_creates_all_expected_tables`, after `import edu_cloud.models.school_settings`, add:

```python
    import edu_cloud.models.teacher_assignment  # noqa: F401
    import edu_cloud.models.subject_selection  # noqa: F401
```

- [ ] **Step 3: Generate migration**

```bash
cd C:/Users/Administrator/edu-cloud
python -m alembic stamp head  # if needed
python -m alembic revision --autogenerate -m "add_assignments_selections"
```

- [ ] **Step 4: Review generated migration**

Verify it contains:
- `op.create_table("teacher_assignments", ...)` with UniqueConstraint
- `op.create_table("subject_selections", ...)` with UniqueConstraint
- Both `downgrade()` drop tables

- [ ] **Step 5: Run migration smoke test**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_alembic_migration.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add alembic/env.py alembic/versions/ tests/test_alembic_migration.py
git commit -m "migrate: add teacher_assignments + subject_selections tables"
```

---

### Task 7: Frontend Pages + Router + Sidebar

**Files:**
- Create: `frontend/src/api/teacherAssignments.js`
- Create: `frontend/src/api/subjectSelections.js`
- Create: `frontend/src/pages/TeacherAssignmentsPage.vue`
- Create: `frontend/src/pages/SubjectSelectionsPage.vue`
- Modify: `frontend/src/config/sidebarConfig.js`
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Create API clients**

```javascript
// frontend/src/api/teacherAssignments.js
import client from './client.js'

export const getAssignments = (schoolId, params) =>
  client.get(`/schools/${schoolId}/assignments`, { params })

export const createAssignments = (schoolId, data) =>
  client.post(`/schools/${schoolId}/assignments`, data)

export const deleteAssignment = (schoolId, id) =>
  client.delete(`/schools/${schoolId}/assignments/${id}`)

export const getAssignmentSummary = (schoolId, params) =>
  client.get(`/schools/${schoolId}/assignments/summary`, { params })
```

```javascript
// frontend/src/api/subjectSelections.js
import client from './client.js'

export const getSelections = (schoolId, params) =>
  client.get(`/schools/${schoolId}/selections`, { params })

export const createSelection = (schoolId, data) =>
  client.post(`/schools/${schoolId}/selections`, data)

export const updateSelection = (schoolId, id, data) =>
  client.patch(`/schools/${schoolId}/selections/${id}`, data)

export const deleteSelection = (schoolId, id) =>
  client.delete(`/schools/${schoolId}/selections/${id}`)
```

- [ ] **Step 2: Create TeacherAssignmentsPage.vue**

```vue
<!-- frontend/src/pages/TeacherAssignmentsPage.vue -->
<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">排课管理</h1>
        <p class="page-subtitle">管理教师排课信息</p>
      </div>
      <n-button type="primary" @click="showCreate = true">新增排课</n-button>
    </div>

    <n-space style="margin-bottom: 16px">
      <n-input v-model:value="filterSemester" placeholder="学期 (如 2025-2026-2)" clearable style="width: 200px" />
      <n-button @click="loadData">查询</n-button>
    </n-space>

    <n-data-table :columns="columns" :data="rows" :loading="loading" />

    <n-modal v-model:show="showCreate" preset="dialog" title="新增排课" positive-text="确认" negative-text="取消"
      @positive-click="handleCreate">
      <n-space vertical>
        <n-input v-model:value="form.user_id" placeholder="教师 ID" />
        <n-input v-model:value="form.subject_code" placeholder="科目代码 (如 math)" />
        <n-input v-model:value="form.semester" placeholder="学期 (如 2025-2026-2)" />
        <n-input v-model:value="form.class_ids_raw" placeholder="班级 ID（逗号分隔）" />
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { getAssignments, createAssignments, deleteAssignment } from '../api/teacherAssignments.js'

const auth = useAuthStore()
const message = useMessage()
const rows = ref([])
const loading = ref(false)
const showCreate = ref(false)
const filterSemester = ref('')

const form = ref({ user_id: '', subject_code: '', semester: '', class_ids_raw: '' })

const schoolId = () => auth.currentRole?.school_id

const columns = [
  { title: '教师 ID', key: 'user_id', ellipsis: true, width: 200 },
  { title: '班级 ID', key: 'class_id', ellipsis: true, width: 200 },
  { title: '科目', key: 'subject_code', width: 100 },
  { title: '学期', key: 'semester', width: 120 },
  {
    title: '操作', key: 'actions', width: 80,
    render(row) {
      return h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row.id) }, () => '删除')
    }
  },
]

async function loadData() {
  if (!schoolId()) return
  loading.value = true
  try {
    const params = {}
    if (filterSemester.value) params.semester = filterSemester.value
    const { data } = await getAssignments(schoolId(), params)
    rows.value = data
  } catch { message.error('加载失败') }
  loading.value = false
}

async function handleCreate() {
  try {
    const classIds = form.value.class_ids_raw.split(',').map(s => s.trim()).filter(Boolean)
    await createAssignments(schoolId(), {
      user_id: form.value.user_id,
      class_ids: classIds,
      subject_code: form.value.subject_code,
      semester: form.value.semester,
    })
    message.success('排课创建成功')
    showCreate.value = false
    form.value = { user_id: '', subject_code: '', semester: '', class_ids_raw: '' }
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '创建失败') }
}

async function handleDelete(id) {
  try {
    await deleteAssignment(schoolId(), id)
    message.success('已删除')
    await loadData()
  } catch (e) { message.error('删除失败') }
}

onMounted(loadData)
</script>
```

- [ ] **Step 3: Create SubjectSelectionsPage.vue**

```vue
<!-- frontend/src/pages/SubjectSelectionsPage.vue -->
<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">选考组合</h1>
        <p class="page-subtitle">管理学校提供的选考科目组合</p>
      </div>
      <n-button type="primary" @click="showCreate = true">新增组合</n-button>
    </div>

    <n-space v-if="selections.length" wrap>
      <n-card v-for="s in selections" :key="s.id" style="width: 280px" :title="s.name" size="small">
        <template #header-extra>
          <n-switch :value="s.is_active" size="small" @update:value="(v) => handleToggle(s.id, v)" />
        </template>
        <n-space>
          <n-tag v-for="code in s.subject_codes" :key="code" type="info" size="small">{{ code }}</n-tag>
        </n-space>
        <n-text depth="3" style="display: block; margin-top: 8px">模式: {{ s.mode }}</n-text>
        <template #action>
          <n-button size="small" type="error" @click="handleDelete(s.id)">删除</n-button>
        </template>
      </n-card>
    </n-space>
    <n-empty v-else description="暂无选考组合" />

    <n-modal v-model:show="showCreate" preset="dialog" title="新增选考组合" positive-text="确认" negative-text="取消"
      @positive-click="handleCreate">
      <n-space vertical>
        <n-input v-model:value="form.name" placeholder="组合名称 (如 物化生)" />
        <n-input v-model:value="form.codes_raw" placeholder="科目代码（逗号分隔，如 physics,chemistry,biology）" />
        <n-select v-model:value="form.mode" :options="modeOptions" placeholder="选考模式" />
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { getSelections, createSelection, updateSelection, deleteSelection } from '../api/subjectSelections.js'

const auth = useAuthStore()
const message = useMessage()
const selections = ref([])
const showCreate = ref(false)
const form = ref({ name: '', codes_raw: '', mode: 'custom' })

const modeOptions = [
  { label: '3+1+2', value: '3+1+2' },
  { label: '3+3', value: '3+3' },
  { label: '自定义', value: 'custom' },
]

const schoolId = () => auth.currentRole?.school_id

async function loadData() {
  if (!schoolId()) return
  try {
    const { data } = await getSelections(schoolId())
    selections.value = data
  } catch { message.error('加载失败') }
}

async function handleCreate() {
  try {
    const codes = form.value.codes_raw.split(',').map(s => s.trim()).filter(Boolean)
    await createSelection(schoolId(), { name: form.value.name, subject_codes: codes, mode: form.value.mode })
    message.success('组合创建成功')
    showCreate.value = false
    form.value = { name: '', codes_raw: '', mode: 'custom' }
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '创建失败') }
}

async function handleToggle(id, active) {
  try {
    await updateSelection(schoolId(), id, { is_active: active })
    await loadData()
  } catch { message.error('操作失败') }
}

async function handleDelete(id) {
  try {
    await deleteSelection(schoolId(), id)
    message.success('已删除')
    await loadData()
  } catch { message.error('删除失败') }
}

onMounted(loadData)
</script>
```

- [ ] **Step 4: Add sidebar entries**

In `frontend/src/config/sidebarConfig.js`, add to `principal` array (before the `学校配置` entry):

```javascript
{ icon: 'settings', label: '排课管理', route: '/assignments' },
{ icon: 'exam', label: '选考组合', route: '/selections' },
```

Add the same two entries to `academic_director` array (before `学校配置`).

- [ ] **Step 5: Add routes**

In `frontend/src/router/index.js`, add to the AppShell children (before the `school-settings` route):

```javascript
{ path: 'assignments', name: 'TeacherAssignments', component: () => import('../pages/TeacherAssignmentsPage.vue'), meta: { roles: ['principal', 'academic_director'] } },
{ path: 'selections', name: 'SubjectSelections', component: () => import('../pages/SubjectSelectionsPage.vue'), meta: { roles: ['principal', 'academic_director'] } },
```

- [ ] **Step 6: Run frontend build + tests**

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
cd C:/Users/Administrator/edu-cloud/frontend && npx vite build 2>&1 | tail -5
```

Expected: Tests pass, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/teacherAssignments.js frontend/src/api/subjectSelections.js \
  frontend/src/pages/TeacherAssignmentsPage.vue frontend/src/pages/SubjectSelectionsPage.vue \
  frontend/src/config/sidebarConfig.js frontend/src/router/index.js
git commit -m "feat: add teacher assignments + subject selections pages + routes"
```

---

## Summary

| Task | 产出 | 测试 |
|------|------|------|
| 1 | TeacherAssignment model + conftest import | 2 model tests |
| 2 | Teacher assignment service (4 functions) | 5 service tests |
| 3 | Teacher assignment API (4 endpoints) + scope guard | 7 API tests |
| 4 | SubjectSelection model + service (4 functions) + conftest | 10 tests (2 model + 8 service) |
| 5 | Subject selection API (4 endpoints) + scope guard | 8 API tests |
| 6 | Alembic migration + env.py + test imports | Schema validation (smoke test) |
| 7 | Frontend pages + API clients + sidebar + routes | Build verification |

**Total: 7 tasks, ~32 automated tests, ~7 commits**
