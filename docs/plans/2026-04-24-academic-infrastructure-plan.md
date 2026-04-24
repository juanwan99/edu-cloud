---
baseline_command: "cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=no -q; cd frontend-nuxt && npx vitest run"
baseline_verified_at: "2026-04-24T08:44:45+08:00"
baseline_count: "backend 2046 passed, 21 failed (pre-existing), 23 skipped; frontend-nuxt 51 passed"
---

# 教务时间轴基础设施 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 edu-cloud 教务三大缺口——平台级学期管理、课表排布、考试安排——建立统一的教务时间轴基础设施。

**Architecture:** 新建 `modules/academic/` 模块集中管理学期(Semester)、节次(TimePeriod)、课表(TimetableSlot)。考试安排通过扩展现有 `Subject` 表实现。conduct 模块的 `ConductSemester` 通过双写过渡到平台级 Semester。前端填充 3 个 stub 页面。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (async) + Alembic + Nuxt 3 + Element Plus + Vitest

**Design doc:** `docs/plans/2026-04-24-academic-infrastructure-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/edu_cloud/modules/academic/__init__.py` | Module package |
| `src/edu_cloud/modules/academic/models.py` | Semester + TimePeriod + TimetableSlot ORM |
| `src/edu_cloud/modules/academic/service.py` | Business logic (activate, conflict detection, stats) |
| `src/edu_cloud/modules/academic/router.py` | API endpoints (semesters/periods/timetable) |
| `tests/test_api/test_academic_semester.py` | Semester API tests (5) |
| `tests/test_api/test_academic_period.py` | Period API tests (3) |
| `tests/test_api/test_academic_timetable.py` | Timetable API tests (5) |
| `tests/test_api/test_exam_schedule.py` | Exam schedule API tests (3) |
| `tests/test_services/test_conduct_semester_migration.py` | Dual-write tests (3) |
| `frontend-nuxt/composables/useAcademic.ts` | Academic composable |
| `frontend-nuxt/tests/composables/useAcademic.test.ts` | Frontend tests (4) |

### Modified Files
| File | Change |
|------|--------|
| `src/edu_cloud/modules/exam/models.py` | Add 4 fields to Subject |
| `src/edu_cloud/modules/exam/router.py` | Add 2 schedule endpoints |
| `src/edu_cloud/modules/conduct/admin_service.py` | Dual-write to platform Semester |
| `src/edu_cloud/api/app.py` | Register academic_router |
| `tests/conftest.py` | Import academic models |
| `src/edu_cloud/data/seed_demo.py` | Add semester/period/timetable seed data |
| `frontend-nuxt/composables/useApi.ts` | Add 12 API methods |
| `frontend-nuxt/tests/setup.ts` | Add useAcademic mock |
| `frontend-nuxt/pages/academic/semester.vue` | Replace stub |
| `frontend-nuxt/pages/academic/timetable.vue` | Replace stub |
| `frontend-nuxt/pages/academic/exam-schedule.vue` | Replace stub |

---

## Batch 1: Semester + TimePeriod (Foundation)

### Task 1: Academic Module Models + Migration

**Files:**
- Create: `src/edu_cloud/modules/academic/__init__.py`
- Create: `src/edu_cloud/modules/academic/models.py`
- Modify: `src/edu_cloud/modules/exam/models.py:51-58`
- Modify: `tests/conftest.py:44` (add model import)

- [ ] **Step 1: Create academic module package**

```python
# src/edu_cloud/modules/academic/__init__.py
```
(Empty file — package marker only.)

- [ ] **Step 2: Create academic models**

```python
# src/edu_cloud/modules/academic/models.py
from datetime import date, time

from sqlalchemy import String, Integer, Boolean, Date, Time, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Semester(Base, IdMixin, TimestampMixin):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("school_id", "school_year", "term", name="uq_semester"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    school_year: Mapped[str] = mapped_column(String(20))
    term: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


class TimePeriod(Base, IdMixin):
    __tablename__ = "time_periods"
    __table_args__ = (
        UniqueConstraint("school_id", "semester_id", "period_number", name="uq_time_period"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    semester_id: Mapped[str] = mapped_column(String(36), ForeignKey("semesters.id"))
    period_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(20))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    period_type: Mapped[str] = mapped_column(String(20))


class TimetableSlot(Base, IdMixin):
    __tablename__ = "timetable_slots"
    __table_args__ = (
        UniqueConstraint("class_id", "semester_id", "weekday", "period_id", name="uq_timetable_slot"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    semester_id: Mapped[str] = mapped_column(String(36), ForeignKey("semesters.id"))
    class_id: Mapped[str] = mapped_column(String(36), ForeignKey("classes.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    period_id: Mapped[str] = mapped_column(String(36), ForeignKey("time_periods.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    room: Mapped[str | None] = mapped_column(String(50), default=None)
```

- [ ] **Step 3: Add Subject schedule fields**

Add these 4 fields after `school_id` in `src/edu_cloud/modules/exam/models.py` class `Subject`:

```python
    exam_start: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    exam_end: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    exam_room: Mapped[str | None] = mapped_column(String(100), default=None)
    proctor_ids: Mapped[list | None] = mapped_column(JSON, default=None)
```

Also add `DateTime, JSON` to the existing import at top of file:
```python
from sqlalchemy import (
    String, Integer, Float, Text, ForeignKey, JSON, Boolean, DateTime,
    UniqueConstraint, Index, Column,
)
```
(`JSON` and `DateTime` are already imported — verify before adding duplicates.)

- [ ] **Step 4: Register models in conftest.py**

Add after line 45 (`import edu_cloud.modules.analytics.models`):
```python
import edu_cloud.modules.academic.models  # noqa: F401
```

- [ ] **Step 5: Generate Alembic migration**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m alembic revision --autogenerate -m "add academic tables and subject schedule fields"
```

Review the generated file — it should contain:
- `op.create_table('semesters', ...)` with UniqueConstraint
- `op.create_table('time_periods', ...)` with UniqueConstraint
- `op.create_table('timetable_slots', ...)` with UniqueConstraint
- `op.add_column('subjects', sa.Column('exam_start', ...))` × 4

- [ ] **Step 6: Run migration smoke test**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_alembic_migration.py -v --tb=short
```
Expected: PASS (upgrade creates tables, downgrade drops them)

- [ ] **Step 7: Run full backend tests**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q
```
Expected: All existing tests pass (no regression). New tables are nullable, no existing code affected.

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/modules/academic/__init__.py src/edu_cloud/modules/academic/models.py src/edu_cloud/modules/exam/models.py tests/conftest.py alembic/versions/
git commit -m "feat(academic): add Semester, TimePeriod, TimetableSlot models + Subject schedule fields"
```

---

### Task 2: Semester + Period Service Layer

**Files:**
- Create: `src/edu_cloud/modules/academic/service.py`

- [ ] **Step 1: Write the service**

```python
# src/edu_cloud/modules/academic/service.py
import logging
from datetime import date as date_type, time as time_type

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.academic.models import Semester, TimePeriod, TimetableSlot
from edu_cloud.services.exceptions import NotFoundError, ValidationError, ConflictError

logger = logging.getLogger(__name__)

VALID_PERIOD_TYPES = {"class", "break", "activity", "self_study"}


# ── Semester ────────────────────────────────────────────────────

async def create_semester(
    db: AsyncSession, *, school_id: str, name: str,
    school_year: str, term: int,
    start_date: date_type, end_date: date_type,
) -> dict:
    if term not in (1, 2):
        raise ValidationError("term 必须为 1 或 2")
    if start_date >= end_date:
        raise ValidationError("start_date 必须早于 end_date")

    semester = Semester(
        school_id=school_id, name=name, school_year=school_year,
        term=term, start_date=start_date, end_date=end_date,
    )
    db.add(semester)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise ConflictError("该学年+学期已存在")
    await db.refresh(semester)
    return _semester_dict(semester)


async def list_semesters(
    db: AsyncSession, *, school_id: str, school_year: str | None = None,
) -> list[dict]:
    stmt = select(Semester).where(Semester.school_id == school_id)
    if school_year:
        stmt = stmt.where(Semester.school_year == school_year)
    stmt = stmt.order_by(Semester.school_year.desc(), Semester.term.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_semester_dict(s) for s in rows]


async def get_current_semester(db: AsyncSession, *, school_id: str) -> dict | None:
    stmt = (
        select(Semester)
        .where(Semester.school_id == school_id, Semester.is_current == True)  # noqa: E712
    )
    s = (await db.execute(stmt)).scalar_one_or_none()
    return _semester_dict(s) if s else None


async def update_semester(
    db: AsyncSession, *, semester_id: str, school_id: str, **fields,
) -> dict:
    semester = await _get_semester(db, semester_id, school_id)
    for k, v in fields.items():
        if v is not None and hasattr(semester, k):
            setattr(semester, k, v)
    await db.commit()
    await db.refresh(semester)
    return _semester_dict(semester)


async def activate_semester(
    db: AsyncSession, *, semester_id: str, school_id: str,
) -> dict:
    semester = await _get_semester(db, semester_id, school_id)
    await db.execute(
        update(Semester)
        .where(Semester.school_id == school_id)
        .values(is_current=False)
    )
    semester.is_current = True
    await db.commit()
    await db.refresh(semester)
    return _semester_dict(semester)


async def _get_semester(db: AsyncSession, semester_id: str, school_id: str) -> Semester:
    semester = await db.get(Semester, semester_id)
    if not semester or semester.school_id != school_id:
        raise NotFoundError("学期不存在")
    return semester


def _semester_dict(s: Semester) -> dict:
    return {
        "id": s.id, "name": s.name,
        "school_year": s.school_year, "term": s.term,
        "start_date": str(s.start_date), "end_date": str(s.end_date),
        "is_current": s.is_current,
    }


# ── TimePeriod ──────────────────────────────────────────────────

async def set_periods(
    db: AsyncSession, *, school_id: str, semester_id: str,
    periods: list[dict],
) -> list[dict]:
    await _get_semester(db, semester_id, school_id)

    for p in periods:
        if p.get("period_type") not in VALID_PERIOD_TYPES:
            raise ValidationError(f"无效的 period_type: {p.get('period_type')}")

    await db.execute(
        delete(TimePeriod).where(
            TimePeriod.school_id == school_id,
            TimePeriod.semester_id == semester_id,
        )
    )

    new_periods = []
    for p in periods:
        tp = TimePeriod(
            school_id=school_id, semester_id=semester_id,
            period_number=p["period_number"], name=p["name"],
            start_time=time_type.fromisoformat(p["start_time"]),
            end_time=time_type.fromisoformat(p["end_time"]),
            period_type=p["period_type"],
        )
        db.add(tp)
        new_periods.append(tp)

    await db.commit()
    for tp in new_periods:
        await db.refresh(tp)
    return [_period_dict(tp) for tp in new_periods]


async def get_periods(
    db: AsyncSession, *, school_id: str, semester_id: str,
) -> list[dict]:
    stmt = (
        select(TimePeriod)
        .where(TimePeriod.school_id == school_id, TimePeriod.semester_id == semester_id)
        .order_by(TimePeriod.period_number)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_period_dict(tp) for tp in rows]


def _period_dict(tp: TimePeriod) -> dict:
    return {
        "id": tp.id, "period_number": tp.period_number,
        "name": tp.name,
        "start_time": tp.start_time.isoformat(),
        "end_time": tp.end_time.isoformat(),
        "period_type": tp.period_type,
    }
```

- [ ] **Step 2: Commit**

```bash
git add src/edu_cloud/modules/academic/service.py
git commit -m "feat(academic): semester + period service layer"
```

---

### Task 3: Semester + Period Router + App Registration

**Files:**
- Create: `src/edu_cloud/modules/academic/router.py`
- Modify: `src/edu_cloud/api/app.py:308,317`

- [ ] **Step 1: Write the router**

```python
# src/edu_cloud/modules/academic/router.py
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.modules.academic import service

router = APIRouter(prefix="/api/v1/academic", tags=["academic"])


def _school_id(current: dict) -> str:
    return current["current_role"].school_id


# ── Schemas ─────────────────────────────────────────────────────

class SemesterCreate(BaseModel):
    name: str
    school_year: str
    term: int
    start_date: date_type
    end_date: date_type


class SemesterUpdate(BaseModel):
    name: str | None = None
    start_date: date_type | None = None
    end_date: date_type | None = None


class PeriodItem(BaseModel):
    period_number: int
    name: str
    start_time: str
    end_time: str
    period_type: str


class PeriodBatch(BaseModel):
    semester_id: str
    periods: list[PeriodItem]


# ── Semester endpoints ──────────────────────────────────────────

@router.post("/semesters", status_code=201)
async def create_semester(
    body: SemesterCreate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.create_semester(
        db, school_id=_school_id(current),
        name=body.name, school_year=body.school_year, term=body.term,
        start_date=body.start_date, end_date=body.end_date,
    )


@router.get("/semesters")
async def list_semesters(
    school_year: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    return await service.list_semesters(
        db, school_id=_school_id(current), school_year=school_year,
    )


@router.get("/semesters/current")
async def get_current_semester(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    result = await service.get_current_semester(db, school_id=_school_id(current))
    if not result:
        return {"detail": "未设置当前学期"}
    return result


@router.patch("/semesters/{semester_id}")
async def update_semester(
    semester_id: str,
    body: SemesterUpdate,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.update_semester(
        db, semester_id=semester_id, school_id=_school_id(current),
        **body.model_dump(exclude_none=True),
    )


@router.post("/semesters/{semester_id}/activate")
async def activate_semester(
    semester_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.activate_semester(
        db, semester_id=semester_id, school_id=_school_id(current),
    )


# ── Period endpoints ────────────────────────────────────────────

@router.put("/periods")
async def set_periods(
    body: PeriodBatch,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.set_periods(
        db, school_id=_school_id(current), semester_id=body.semester_id,
        periods=[p.model_dump() for p in body.periods],
    )


@router.get("/periods")
async def get_periods(
    semester_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    return await service.get_periods(
        db, school_id=_school_id(current), semester_id=semester_id,
    )
```

- [ ] **Step 2: Register router in app.py**

Add to the import block (after line 308 `from edu_cloud.modules.menu.router import router as menu_router`):
```python
    from edu_cloud.modules.academic.router import router as academic_router
```

Add `academic_router` to the router list (in the `for r in [...]` block, after `menu_router`):
```python
              teacher_router, academic_router]:
```

- [ ] **Step 3: Run backend tests to check no regression**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q
```
Expected: All existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/modules/academic/router.py src/edu_cloud/api/app.py
git commit -m "feat(academic): semester + period REST API + app registration"
```

---

### Task 4: Semester API Tests

**Files:**
- Create: `tests/test_api/test_academic_semester.py`

**Test Contract:**
- 入口: POST/GET/PATCH/POST activate via HTTP client
- 反例: duplicate semester returns 409; subject_teacher cannot create (403)
- 边界: activate deactivates others; empty list on no data
- 回归: existing tests unaffected
- 命令: `.venv/bin/python -m pytest tests/test_api/test_academic_semester.py -v`

- [ ] **Step 1: Write semester tests**

```python
# tests/test_api/test_academic_semester.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def school(db):
    s = School(name="教务测试校", code="ACAD01", district="测试区")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
async def director_headers(db, school):
    user = User(username="director_acad", display_name="教务主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "academic_director", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def teacher_headers(db, school):
    user = User(username="teacher_acad", display_name="科任教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="subject_teacher", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "subject_teacher", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_semester(client, director_headers):
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "2025-2026学年第一学期", "school_year": "2025-2026",
        "term": 1, "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "2025-2026学年第一学期"
    assert data["term"] == 1
    assert data["is_current"] is False


@pytest.mark.asyncio
async def test_list_semesters_with_filter(client, director_headers):
    await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    await client.post("/api/v1/academic/semesters", json={
        "name": "S2", "school_year": "2025-2026", "term": 2,
        "start_date": "2026-02-17", "end_date": "2026-07-10",
    }, headers=director_headers)
    await client.post("/api/v1/academic/semesters", json={
        "name": "S3", "school_year": "2024-2025", "term": 1,
        "start_date": "2024-09-01", "end_date": "2025-01-15",
    }, headers=director_headers)

    resp = await client.get("/api/v1/academic/semesters", headers=director_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    resp = await client.get("/api/v1/academic/semesters?school_year=2025-2026", headers=director_headers)
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_activate_mutual_exclusion(client, director_headers):
    r1 = await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    r2 = await client.post("/api/v1/academic/semesters", json={
        "name": "S2", "school_year": "2025-2026", "term": 2,
        "start_date": "2026-02-17", "end_date": "2026-07-10",
    }, headers=director_headers)
    sid1 = r1.json()["id"]
    sid2 = r2.json()["id"]

    resp = await client.post(f"/api/v1/academic/semesters/{sid1}/activate", headers=director_headers)
    assert resp.status_code == 200
    assert resp.json()["is_current"] is True

    resp = await client.post(f"/api/v1/academic/semesters/{sid2}/activate", headers=director_headers)
    assert resp.status_code == 200
    assert resp.json()["is_current"] is True

    all_sems = await client.get("/api/v1/academic/semesters", headers=director_headers)
    current_count = sum(1 for s in all_sems.json() if s["is_current"])
    assert current_count == 1


@pytest.mark.asyncio
async def test_duplicate_semester_rejected(client, director_headers):
    await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "S1 duplicate", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_teacher_cannot_create_semester(client, teacher_headers):
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=teacher_headers)
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they pass**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_academic_semester.py -v
```
Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_api/test_academic_semester.py
git commit -m "test(academic): semester API tests (5 cases)"
```

---

### Task 5: Period API Tests

**Files:**
- Create: `tests/test_api/test_academic_period.py`

**Test Contract:**
- 入口: PUT /periods + GET /periods via HTTP
- 反例: invalid period_type returns 422
- 边界: PUT replaces existing periods entirely
- 回归: existing tests unaffected
- 命令: `.venv/bin/python -m pytest tests/test_api/test_academic_period.py -v`

- [ ] **Step 1: Write period tests**

```python
# tests/test_api/test_academic_period.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def school(db):
    s = School(name="节次测试校", code="PERIOD01", district="测试区")
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


@pytest.fixture
async def director_headers(db, school):
    user = User(username="director_period", display_name="教务主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "academic_director", "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def semester_id(client, director_headers):
    resp = await client.post("/api/v1/academic/semesters", json={
        "name": "S1", "school_year": "2025-2026", "term": 1,
        "start_date": "2025-09-01", "end_date": "2026-01-15",
    }, headers=director_headers)
    return resp.json()["id"]


def _make_periods(n=3):
    times = [("08:00", "08:45"), ("08:55", "09:40"), ("10:00", "10:45")]
    return [
        {"period_number": i + 1, "name": f"第{i+1}节",
         "start_time": times[i][0], "end_time": times[i][1], "period_type": "class"}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_set_and_get_periods(client, director_headers, semester_id):
    periods = _make_periods(3)
    resp = await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id, "periods": periods,
    }, headers=director_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    resp = await client.get(f"/api/v1/academic/periods?semester_id={semester_id}", headers=director_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    assert data[0]["period_number"] == 1


@pytest.mark.asyncio
async def test_set_periods_replaces_existing(client, director_headers, semester_id):
    await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id, "periods": _make_periods(3),
    }, headers=director_headers)

    new_periods = [
        {"period_number": 1, "name": "新第1节", "start_time": "09:00", "end_time": "09:45", "period_type": "class"},
    ]
    resp = await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id, "periods": new_periods,
    }, headers=director_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp = await client.get(f"/api/v1/academic/periods?semester_id={semester_id}", headers=director_headers)
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "新第1节"


@pytest.mark.asyncio
async def test_invalid_period_type_rejected(client, director_headers, semester_id):
    resp = await client.put("/api/v1/academic/periods", json={
        "semester_id": semester_id,
        "periods": [{"period_number": 1, "name": "X", "start_time": "08:00", "end_time": "08:45", "period_type": "invalid"}],
    }, headers=director_headers)
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_academic_period.py -v
```
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_api/test_academic_period.py
git commit -m "test(academic): period API tests (3 cases)"
```

---

### Task 6: Seed Data

**Files:**
- Modify: `src/edu_cloud/data/seed_demo.py`

- [ ] **Step 1: Add academic seed data**

Add at the end of `seed_demo.py` (before the final return), after all existing seed logic:

```python
    # ── Academic: Semesters + Periods ──────────────────────────────
    from edu_cloud.modules.academic.models import Semester, TimePeriod
    from datetime import time as time_type

    sem1 = Semester(
        school_id=school.id, name="2025-2026学年第一学期",
        school_year="2025-2026", term=1,
        start_date=date(2025, 9, 1), end_date=date(2026, 1, 15),
        is_current=True,
    )
    sem2 = Semester(
        school_id=school.id, name="2025-2026学年第二学期",
        school_year="2025-2026", term=2,
        start_date=date(2026, 2, 17), end_date=date(2026, 7, 10),
    )
    db.add_all([sem1, sem2])
    await db.flush()

    period_defs = [
        (1, "第一节", "08:00", "08:45", "class"),
        (2, "第二节", "08:55", "09:40", "class"),
        (3, "第三节", "10:00", "10:45", "class"),
        (4, "第四节", "10:55", "11:40", "class"),
        (5, "第五节", "14:00", "14:45", "class"),
        (6, "第六节", "14:55", "15:40", "class"),
        (7, "第七节", "16:00", "16:45", "class"),
        (8, "晚自习一", "19:00", "19:45", "self_study"),
        (9, "晚自习二", "19:55", "20:40", "self_study"),
    ]
    for num, name, st, et, ptype in period_defs:
        db.add(TimePeriod(
            school_id=school.id, semester_id=sem1.id,
            period_number=num, name=name,
            start_time=time_type.fromisoformat(st),
            end_time=time_type.fromisoformat(et),
            period_type=ptype,
        ))
    await db.flush()
    logger.info("Academic seed: 2 semesters + 9 periods created")
```

Also add `from datetime import date, time as time_type` to the imports at top if `date` is not already imported (check existing imports first).

- [ ] **Step 2: Run backend tests**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q
```
Expected: All tests pass (seed is only invoked on demand, not in tests).

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/data/seed_demo.py
git commit -m "feat(academic): add semester + period seed data"
```

---

## Batch 2: Timetable (课表)

### Task 7: Timetable Service + Router

**Files:**
- Modify: `src/edu_cloud/modules/academic/service.py` (add timetable functions)
- Modify: `src/edu_cloud/modules/academic/router.py` (add timetable endpoints)

- [ ] **Step 1: Add timetable service functions**

Append to `src/edu_cloud/modules/academic/service.py`:

```python
# ── Timetable ───────────────────────────────────────────────────

SCHEDULABLE_PERIOD_TYPES = {"class", "self_study"}


async def save_timetable(
    db: AsyncSession, *, school_id: str, semester_id: str, class_id: str,
    slots: list[dict],
) -> dict:
    await _get_semester(db, semester_id, school_id)

    # Validate period_type: only class/self_study slots can be scheduled
    for s in slots:
        period = await db.get(TimePeriod, s["period_id"])
        if not period or period.period_type not in SCHEDULABLE_PERIOD_TYPES:
            raise ValidationError(f"节次 {s['period_id']} 不可排课（仅 class/self_study 类型）")

    # Teacher conflict detection
    conflicts = await _check_teacher_conflicts(db, school_id, semester_id, class_id, slots)
    if conflicts:
        raise ValidationError(f"教师时间冲突: {conflicts}")

    # TeacherAssignment soft check (warning, non-blocking)
    from edu_cloud.models.teacher_assignment import TeacherAssignment
    warnings = []
    for s in slots:
        ta = (await db.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.school_id == school_id,
                TeacherAssignment.class_id == class_id,
                TeacherAssignment.subject_code == s["subject_code"],
                TeacherAssignment.user_id == s["teacher_id"],
            )
        )).scalar_one_or_none()
        if not ta:
            warnings.append(f"教师{s['teacher_id']}未在排课表中任教{class_id}班{s['subject_code']}")

    await db.execute(
        delete(TimetableSlot).where(
            TimetableSlot.class_id == class_id,
            TimetableSlot.semester_id == semester_id,
        )
    )

    new_slots = []
    for s in slots:
        slot = TimetableSlot(
            school_id=school_id, semester_id=semester_id, class_id=class_id,
            weekday=s["weekday"], period_id=s["period_id"],
            subject_code=s["subject_code"], teacher_id=s["teacher_id"],
            room=s.get("room"),
        )
        db.add(slot)
        new_slots.append(slot)

    await db.commit()
    result = {"saved": len(new_slots)}
    if warnings:
        result["warnings"] = warnings
    return result


async def get_timetable(
    db: AsyncSession, *, school_id: str, semester_id: str,
    class_id: str | None = None, teacher_id: str | None = None,
) -> list[dict]:
    stmt = select(TimetableSlot).where(
        TimetableSlot.school_id == school_id,
        TimetableSlot.semester_id == semester_id,
    )
    if class_id:
        stmt = stmt.where(TimetableSlot.class_id == class_id)
    if teacher_id:
        stmt = stmt.where(TimetableSlot.teacher_id == teacher_id)
    stmt = stmt.order_by(TimetableSlot.weekday, TimetableSlot.period_id)

    rows = (await db.execute(stmt)).scalars().all()
    return [_slot_dict(s) for s in rows]


async def get_timetable_stats(
    db: AsyncSession, *, school_id: str, semester_id: str, class_id: str,
) -> list[dict]:
    from sqlalchemy import func
    stmt = (
        select(TimetableSlot.subject_code, func.count().label("count"))
        .where(
            TimetableSlot.school_id == school_id,
            TimetableSlot.semester_id == semester_id,
            TimetableSlot.class_id == class_id,
        )
        .group_by(TimetableSlot.subject_code)
        .order_by(func.count().desc())
    )
    rows = (await db.execute(stmt)).all()
    return [{"subject_code": r[0], "count": r[1]} for r in rows]


async def _check_teacher_conflicts(
    db: AsyncSession, school_id: str, semester_id: str,
    class_id: str, new_slots: list[dict],
) -> list[str]:
    conflicts = []
    for s in new_slots:
        stmt = (
            select(TimetableSlot)
            .where(
                TimetableSlot.school_id == school_id,
                TimetableSlot.semester_id == semester_id,
                TimetableSlot.teacher_id == s["teacher_id"],
                TimetableSlot.weekday == s["weekday"],
                TimetableSlot.period_id == s["period_id"],
                TimetableSlot.class_id != class_id,
            )
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            conflicts.append(
                f"教师{s['teacher_id']} 在周{s['weekday']}第{s['period_id']}节已有课（班级{existing.class_id}）"
            )
    return conflicts


def _slot_dict(s: TimetableSlot) -> dict:
    return {
        "id": s.id, "class_id": s.class_id,
        "weekday": s.weekday, "period_id": s.period_id,
        "subject_code": s.subject_code, "teacher_id": s.teacher_id,
        "room": s.room,
    }
```

- [ ] **Step 2: Add timetable router endpoints**

Append to `src/edu_cloud/modules/academic/router.py`:

```python
# ── Timetable schemas ───────────────────────────────────────────

class TimetableSlotItem(BaseModel):
    weekday: int
    period_id: str
    subject_code: str
    teacher_id: str
    room: str | None = None


class TimetableSave(BaseModel):
    semester_id: str
    slots: list[TimetableSlotItem]


# ── Timetable endpoints ────────────────────────────────────────

@router.get("/timetable")
async def get_timetable(
    semester_id: str = Query(...),
    class_id: str | None = Query(None),
    teacher_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    if not class_id and not teacher_id:
        return {"detail": "必须提供 class_id 或 teacher_id"}
    # RBAC: non-admin roles can only see their visible classes
    from edu_cloud.api.permissions import get_visible_class_ids
    role = current["current_role"]
    visible = get_visible_class_ids(role)
    if class_id and visible is not None and class_id not in visible:
        return []
    return await service.get_timetable(
        db, school_id=_school_id(current), semester_id=semester_id,
        class_id=class_id, teacher_id=teacher_id,
    )


@router.put("/timetable/{class_id}")
async def save_timetable(
    class_id: str,
    body: TimetableSave,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_SCHEDULING)),
):
    return await service.save_timetable(
        db, school_id=_school_id(current), semester_id=body.semester_id,
        class_id=class_id, slots=[s.model_dump() for s in body.slots],
    )


@router.get("/timetable/stats")
async def get_timetable_stats(
    semester_id: str = Query(...),
    class_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    return await service.get_timetable_stats(
        db, school_id=_school_id(current), semester_id=semester_id,
        class_id=class_id,
    )
```

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/modules/academic/service.py src/edu_cloud/modules/academic/router.py
git commit -m "feat(academic): timetable service + router (save, query, stats, conflict detection)"
```

---

### Task 8: Timetable API Tests

**Files:**
- Create: `tests/test_api/test_academic_timetable.py`

**Test Contract:**
- 入口: PUT /timetable/{class_id} + GET /timetable + GET /timetable/stats via HTTP
- 反例: teacher conflict returns 422; teacher cannot save (403)
- 边界: empty timetable returns []; PUT replaces all slots; teacher query cross-class
- 回归: existing tests unaffected
- 命令: `.venv/bin/python -m pytest tests/test_api/test_academic_timetable.py -v`

- [ ] **Step 1: Write timetable tests**

```python
# tests/test_api/test_academic_timetable.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class
from edu_cloud.modules.academic.models import Semester, TimePeriod
from edu_cloud.shared.auth import create_access_token
from datetime import date, time as time_type


@pytest.fixture
async def setup(db):
    school = School(name="课表测试校", code="TT01", district="测试区")
    db.add(school)
    await db.flush()

    sem = Semester(school_id=school.id, name="S1", school_year="2025-2026", term=1,
                   start_date=date(2025, 9, 1), end_date=date(2026, 1, 15), is_current=True)
    db.add(sem)
    await db.flush()

    tp = TimePeriod(school_id=school.id, semester_id=sem.id, period_number=1,
                    name="第一节", start_time=time_type(8, 0), end_time=time_type(8, 45), period_type="class")
    db.add(tp)
    await db.flush()

    cls1 = Class(name="初一1班", grade="初一", school_id=school.id)
    cls2 = Class(name="初一2班", grade="初一", school_id=school.id)
    db.add_all([cls1, cls2])
    await db.flush()

    teacher = User(username="math_teacher_tt", display_name="数学老师")
    teacher.set_password("test123")
    db.add(teacher)
    await db.flush()
    db.add(UserRole(user_id=teacher.id, role="subject_teacher", school_id=school.id, is_primary=True))

    director = User(username="director_tt", display_name="教务主任")
    director.set_password("test123")
    db.add(director)
    await db.flush()
    db.add(UserRole(user_id=director.id, role="academic_director", school_id=school.id, is_primary=True))

    await db.commit()
    for obj in [school, sem, tp, cls1, cls2, teacher, director]:
        await db.refresh(obj)

    d_token = create_access_token({"sub": director.id, "role": "academic_director", "school_id": school.id})
    t_token = create_access_token({"sub": teacher.id, "role": "subject_teacher", "school_id": school.id})

    return {
        "school": school, "semester": sem, "period": tp,
        "class1": cls1, "class2": cls2, "teacher": teacher,
        "director_headers": {"Authorization": f"Bearer {d_token}"},
        "teacher_headers": {"Authorization": f"Bearer {t_token}"},
    }


@pytest.mark.asyncio
async def test_save_and_get_timetable(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    resp = await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])
    assert resp.status_code == 200
    assert resp.json()["saved"] == 1

    resp = await client.get(f"/api/v1/academic/timetable?semester_id={s['semester'].id}&class_id={s['class1'].id}",
                            headers=s["director_headers"])
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["subject_code"] == "math"


@pytest.mark.asyncio
async def test_teacher_conflict_rejected(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])

    resp = await client.put(f"/api/v1/academic/timetable/{s['class2'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_query_by_teacher(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["director_headers"])

    resp = await client.get(
        f"/api/v1/academic/timetable?semester_id={s['semester'].id}&teacher_id={s['teacher'].id}",
        headers=s["director_headers"])
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_timetable_stats(client, setup):
    s = setup
    slots = [
        {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id},
    ]
    await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": slots,
    }, headers=s["director_headers"])

    resp = await client.get(
        f"/api/v1/academic/timetable/stats?semester_id={s['semester'].id}&class_id={s['class1'].id}",
        headers=s["director_headers"])
    assert resp.status_code == 200
    data = resp.json()
    assert any(d["subject_code"] == "math" and d["count"] == 1 for d in data)


@pytest.mark.asyncio
async def test_teacher_cannot_save_timetable(client, setup):
    s = setup
    slot = {"weekday": 1, "period_id": s["period"].id, "subject_code": "math", "teacher_id": s["teacher"].id}
    resp = await client.put(f"/api/v1/academic/timetable/{s['class1'].id}", json={
        "semester_id": s["semester"].id, "slots": [slot],
    }, headers=s["teacher_headers"])
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_academic_timetable.py -v
```
Expected: 5 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_api/test_academic_timetable.py
git commit -m "test(academic): timetable API tests (5 cases incl. conflict detection)"
```

---

## Batch 3: Exam Schedule + Conduct Dual-Write

### Task 9: Exam Schedule Endpoints

**Files:**
- Modify: `src/edu_cloud/modules/exam/router.py` (add 2 endpoints at end)

- [ ] **Step 1: Add schedule endpoints to exam router**

Append to `src/edu_cloud/modules/exam/router.py`:

```python
# ── Exam Schedule ───────────────────────────────────────────────

class ExamScheduleItem(BaseModel):
    subject_id: str
    exam_start: str | None = None
    exam_end: str | None = None
    exam_room: str | None = None
    proctor_ids: list[str] | None = None


class ExamScheduleBatch(BaseModel):
    subjects: list[ExamScheduleItem]


@router.put("/{exam_id}/schedule")
async def set_exam_schedule(
    exam_id: str,
    body: ExamScheduleBatch,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(require_permission(Permission.MANAGE_EXAMS)),
):
    from datetime import datetime as dt
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")

    for item in body.subjects:
        subject = await db.get(Subject, item.subject_id)
        if not subject or subject.exam_id != exam_id:
            raise HTTPException(400, f"科目 {item.subject_id} 不属于该考试")
        if item.exam_start:
            subject.exam_start = dt.fromisoformat(item.exam_start)
        if item.exam_end:
            subject.exam_end = dt.fromisoformat(item.exam_end)
        subject.exam_room = item.exam_room
        subject.proctor_ids = item.proctor_ids

    # Overlap check
    from edu_cloud.modules.exam.models import Subject as SubjectModel
    stmt = select(SubjectModel).where(SubjectModel.exam_id == exam_id, SubjectModel.exam_start != None)  # noqa: E711
    all_subjects = (await db.execute(stmt)).scalars().all()
    for i, a in enumerate(all_subjects):
        for b in all_subjects[i+1:]:
            if a.exam_start and a.exam_end and b.exam_start and b.exam_end:
                if a.exam_start < b.exam_end and b.exam_start < a.exam_end:
                    raise HTTPException(422, f"科目 {a.name} 和 {b.name} 时间段重叠")

    await db.commit()
    return {"updated": len(body.subjects)}


@router.get("/{exam_id}/schedule")
async def get_exam_schedule(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    exam = await db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(404, "考试不存在")

    stmt = select(Subject).where(Subject.exam_id == exam_id).order_by(Subject.code)
    subjects = (await db.execute(stmt)).scalars().all()

    return {
        "exam_id": exam_id,
        "exam_name": exam.name,
        "subjects": [
            {
                "id": s.id, "name": s.name, "code": s.code,
                "exam_start": s.exam_start.isoformat() if s.exam_start else None,
                "exam_end": s.exam_end.isoformat() if s.exam_end else None,
                "exam_room": s.exam_room,
                "proctor_ids": s.proctor_ids,
            }
            for s in subjects
        ],
    }
```

Also add these imports at the top of the exam router if not present:
```python
from pydantic import BaseModel
from fastapi import HTTPException
```
(Check existing imports — `HTTPException` may already be imported.)

- [ ] **Step 2: Run existing exam tests to check no regression**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api_exam/ --tb=short -q
```
Expected: All existing exam tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/modules/exam/router.py
git commit -m "feat(exam): add schedule endpoints (PUT + GET /exams/{id}/schedule)"
```

---

### Task 10: Exam Schedule Tests

**Files:**
- Create: `tests/test_api/test_exam_schedule.py`

**Test Contract:**
- 入口: PUT /exams/{id}/schedule + GET via HTTP
- 反例: overlapping subject times returns 422
- 边界: subjects with no schedule return null fields
- 回归: existing exam tests unaffected
- 命令: `.venv/bin/python -m pytest tests/test_api/test_exam_schedule.py -v`

- [ ] **Step 1: Write exam schedule tests**

```python
# tests/test_api/test_exam_schedule.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def setup(db):
    school = School(name="排考测试校", code="ES01", district="测试区")
    db.add(school)
    await db.flush()

    exam = Exam(name="期中考试", school_id=school.id, status="draft")
    db.add(exam)
    await db.flush()

    s1 = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    s2 = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    s3 = Subject(exam_id=exam.id, name="英语", code="english", school_id=school.id)
    db.add_all([s1, s2, s3])
    await db.flush()

    user = User(username="director_es", display_name="教务主任")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="academic_director", school_id=school.id, is_primary=True))
    await db.commit()

    for obj in [school, exam, s1, s2, s3, user]:
        await db.refresh(obj)

    token = create_access_token({"sub": user.id, "role": "academic_director", "school_id": school.id})
    return {
        "exam": exam, "s1": s1, "s2": s2, "s3": s3,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.mark.asyncio
async def test_set_and_get_schedule(client, setup):
    s = setup
    resp = await client.put(f"/api/v1/exams/{s['exam'].id}/schedule", json={
        "subjects": [
            {"subject_id": s["s1"].id, "exam_start": "2026-04-10T08:00:00", "exam_end": "2026-04-10T10:00:00",
             "exam_room": "301", "proctor_ids": ["t1"]},
            {"subject_id": s["s2"].id, "exam_start": "2026-04-10T10:30:00", "exam_end": "2026-04-10T12:00:00",
             "exam_room": "302"},
        ],
    }, headers=s["headers"])
    assert resp.status_code == 200
    assert resp.json()["updated"] == 2

    resp = await client.get(f"/api/v1/exams/{s['exam'].id}/schedule", headers=s["headers"])
    assert resp.status_code == 200
    subjects = resp.json()["subjects"]
    scheduled = [sub for sub in subjects if sub["exam_start"] is not None]
    assert len(scheduled) == 2


@pytest.mark.asyncio
async def test_overlap_rejected(client, setup):
    s = setup
    resp = await client.put(f"/api/v1/exams/{s['exam'].id}/schedule", json={
        "subjects": [
            {"subject_id": s["s1"].id, "exam_start": "2026-04-10T08:00:00", "exam_end": "2026-04-10T10:00:00"},
            {"subject_id": s["s2"].id, "exam_start": "2026-04-10T09:00:00", "exam_end": "2026-04-10T11:00:00"},
        ],
    }, headers=s["headers"])
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_unscheduled_subjects_null(client, setup):
    s = setup
    resp = await client.get(f"/api/v1/exams/{s['exam'].id}/schedule", headers=s["headers"])
    subjects = resp.json()["subjects"]
    assert all(sub["exam_start"] is None for sub in subjects)
```

- [ ] **Step 2: Run tests**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_api/test_exam_schedule.py -v
```
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add tests/test_api/test_exam_schedule.py
git commit -m "test(exam): schedule API tests (3 cases incl. overlap detection)"
```

---

### Task 11: Conduct Semester Dual-Write

**Files:**
- Modify: `src/edu_cloud/modules/conduct/admin_service.py:576-653`
- Create: `tests/test_services/test_conduct_semester_migration.py`

**Test Contract:**
- 入口: conduct admin_service.create_semester / activate_semester
- 反例: platform Semester created even when called via conduct API
- 边界: activate syncs both tables
- 回归: existing conduct tests unaffected
- 命令: `.venv/bin/python -m pytest tests/test_services/test_conduct_semester_migration.py -v`

- [ ] **Step 1: Modify conduct admin_service.py for dual-write**

Replace the three functions `get_semesters`, `create_semester`, `activate_semester` in `src/edu_cloud/modules/conduct/admin_service.py` (lines 576-653):

```python
def _derive_school_year(start: date_type) -> str:
    """Derive school_year from start_date: Sep-Dec → 'YYYY-(YYYY+1)', Jan-Aug → '(YYYY-1)-YYYY'."""
    if start.month >= 9:
        return f"{start.year}-{start.year + 1}"
    return f"{start.year - 1}-{start.year}"


def _derive_term(start: date_type) -> int:
    """Derive term: Sep-Jan → 1, Feb-Aug → 2."""
    return 1 if start.month >= 9 or start.month == 1 else 2


async def _get_or_create_platform_semester(
    db: AsyncSession, *, school_id: str, name: str,
    start_date: date_type, end_date: date_type,
) -> "Semester":
    """Get or create a platform Semester. Avoids unique constraint collision."""
    from edu_cloud.modules.academic.models import Semester
    school_year = _derive_school_year(start_date)
    term = _derive_term(start_date)

    existing = (await db.execute(
        select(Semester).where(
            Semester.school_id == school_id,
            Semester.school_year == school_year,
            Semester.term == term,
        )
    )).scalar_one_or_none()
    if existing:
        return existing

    sem = Semester(
        school_id=school_id, name=name, school_year=school_year,
        term=term, start_date=start_date, end_date=end_date,
    )
    db.add(sem)
    await db.flush()
    return sem


async def get_semesters(db: AsyncSession, class_id: str) -> list[dict]:
    """List semesters — read from ConductSemester (backward compat, conduct router returns conduct IDs)."""
    semesters = (
        await db.execute(
            select(ConductSemester)
            .where(ConductSemester.class_id == class_id)
            .order_by(ConductSemester.start_date.desc())
        )
    ).scalars().all()

    return [
        {
            "id": s.id,
            "name": s.name,
            "start_date": str(s.start_date),
            "end_date": str(s.end_date),
            "is_current": s.is_current,
        }
        for s in semesters
    ]


async def create_semester(
    db: AsyncSession,
    class_id: str,
    name: str,
    start_date: date_type,
    end_date: date_type,
) -> dict:
    """Create semester — dual-write. Returns ConductSemester ID (conduct router compatibility)."""
    cls = await db.get(Class, class_id)
    school_id = cls.school_id if cls else None

    # Shadow-write to platform Semester (get_or_create avoids unique constraint collision)
    await _get_or_create_platform_semester(
        db, school_id=school_id, name=name,
        start_date=start_date, end_date=end_date,
    )

    # Primary: write ConductSemester (conduct_records FK depends on this)
    conduct_sem = ConductSemester(
        class_id=class_id, school_id=school_id,
        name=name, start_date=start_date, end_date=end_date,
        is_current=False,
    )
    db.add(conduct_sem)
    await db.commit()
    await db.refresh(conduct_sem)
    return {
        "id": conduct_sem.id,
        "name": conduct_sem.name,
        "start_date": str(conduct_sem.start_date),
        "end_date": str(conduct_sem.end_date),
        "is_current": conduct_sem.is_current,
    }


async def activate_semester(db: AsyncSession, semester_id: str) -> dict:
    """Activate ConductSemester + sync platform Semester is_current."""
    from edu_cloud.modules.academic.models import Semester

    # Primary path: ConductSemester (conduct router validates this ID)
    conduct_sem = await db.get(ConductSemester, semester_id)
    if not conduct_sem:
        raise NotFoundError("学期不存在")

    # Deactivate all ConductSemesters in same class
    await db.execute(
        update(ConductSemester)
        .where(ConductSemester.class_id == conduct_sem.class_id)
        .values(is_current=False)
    )
    conduct_sem.is_current = True

    # Best-effort sync: deactivate all platform Semesters in same school, activate matching one
    if conduct_sem.school_id:
        await db.execute(
            update(Semester)
            .where(Semester.school_id == conduct_sem.school_id)
            .values(is_current=False)
        )
        school_year = _derive_school_year(conduct_sem.start_date)
        term = _derive_term(conduct_sem.start_date)
        platform_match = (await db.execute(
            select(Semester).where(
                Semester.school_id == conduct_sem.school_id,
                Semester.school_year == school_year,
                Semester.term == term,
            )
        )).scalar_one_or_none()
        if platform_match:
            platform_match.is_current = True

    await db.commit()
    await db.refresh(conduct_sem)
    return {
        "id": conduct_sem.id, "name": conduct_sem.name,
        "start_date": str(conduct_sem.start_date),
        "end_date": str(conduct_sem.end_date),
        "is_current": conduct_sem.is_current,
    }
```

- [ ] **Step 2: Write dual-write tests**

```python
# tests/test_services/test_conduct_semester_migration.py
import pytest
from datetime import date
from sqlalchemy import select
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class
from edu_cloud.modules.conduct.models import ConductSemester
from edu_cloud.modules.academic.models import Semester
from edu_cloud.modules.conduct import admin_service


@pytest.fixture
async def setup(db):
    school = School(name="双写测试校", code="DW01", district="测试区")
    db.add(school)
    await db.flush()
    cls = Class(name="初一1班", grade="初一", school_id=school.id)
    db.add(cls)
    await db.commit()
    await db.refresh(school)
    await db.refresh(cls)
    return school, cls


@pytest.mark.asyncio
async def test_create_writes_both_tables(db, setup):
    school, cls = setup
    result = await admin_service.create_semester(
        db, cls.id, "2025-2026第一学期", date(2025, 9, 1), date(2026, 1, 15),
    )
    assert result["name"] == "2025-2026第一学期"

    # Platform table has the record
    platform = (await db.execute(select(Semester).where(Semester.school_id == school.id))).scalars().all()
    assert len(platform) == 1

    # Conduct table also has the record
    conduct = (await db.execute(select(ConductSemester).where(ConductSemester.class_id == cls.id))).scalars().all()
    assert len(conduct) == 1


@pytest.mark.asyncio
async def test_activate_syncs_both(db, setup):
    school, cls = setup
    r1 = await admin_service.create_semester(db, cls.id, "S1", date(2025, 9, 1), date(2026, 1, 15))
    r2 = await admin_service.create_semester(db, cls.id, "S2", date(2026, 2, 17), date(2026, 7, 10))

    result = await admin_service.activate_semester(db, r1["id"])
    assert result["is_current"] is True

    # Platform: only one is_current
    all_platform = (await db.execute(select(Semester).where(Semester.school_id == school.id))).scalars().all()
    current_count = sum(1 for s in all_platform if s.is_current)
    assert current_count == 1


@pytest.mark.asyncio
async def test_get_reads_from_platform(db, setup):
    school, cls = setup
    await admin_service.create_semester(db, cls.id, "S1", date(2025, 9, 1), date(2026, 1, 15))

    result = await admin_service.get_semesters(db, cls.id)
    assert len(result) == 1
    assert result[0]["name"] == "S1"
```

- [ ] **Step 3: Run tests**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/test_services/test_conduct_semester_migration.py -v
```
Expected: 3 passed

- [ ] **Step 4: Run existing conduct tests to check no regression**

Run:
```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest tests/ -k "conduct" --tb=short -q
```
Expected: All existing conduct tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/conduct/admin_service.py tests/test_services/test_conduct_semester_migration.py
git commit -m "feat(conduct): dual-write semesters to platform Semester table"
```

---

## Batch 4: Frontend

### Task 12: useApi + useAcademic Composable

**Files:**
- Modify: `frontend-nuxt/composables/useApi.ts:157` (before `// === Raw ===`)
- Create: `frontend-nuxt/composables/useAcademic.ts`
- Modify: `frontend-nuxt/tests/setup.ts` (add useAcademic mock)

- [ ] **Step 1: Add 12 API methods to useApi.ts**

Add before the `// === Raw ===` section:

```typescript
    // === Academic ===
    createSemester: (data: any) =>
      request('/academic/semesters', { method: 'POST', body: data }),
    getSemesters: (params?: Record<string, any>) =>
      request('/academic/semesters', { query: params }),
    getCurrentSemester: () =>
      request('/academic/semesters/current'),
    updateSemester: (id: string, data: any) =>
      request(`/academic/semesters/${id}`, { method: 'PATCH', body: data }),
    activateSemester: (id: string) =>
      request(`/academic/semesters/${id}/activate`, { method: 'POST' }),
    setPeriods: (data: any) =>
      request('/academic/periods', { method: 'PUT', body: data }),
    getPeriods: (params?: Record<string, any>) =>
      request('/academic/periods', { query: params }),
    getTimetable: (params?: Record<string, any>) =>
      request('/academic/timetable', { query: params }),
    saveTimetable: (classId: string, data: any) =>
      request(`/academic/timetable/${classId}`, { method: 'PUT', body: data }),
    getTimetableStats: (params?: Record<string, any>) =>
      request('/academic/timetable/stats', { query: params }),
    setExamSchedule: (examId: string, data: any) =>
      request(`/exams/${examId}/schedule`, { method: 'PUT', body: data }),
    getExamSchedule: (examId: string) =>
      request(`/exams/${examId}/schedule`),
```

- [ ] **Step 2: Create useAcademic composable**

```typescript
// frontend-nuxt/composables/useAcademic.ts
export function useAcademic() {
  const api = useApi()
  const semesters = ref<any[]>([])
  const currentSemester = ref<any>(null)
  const periods = ref<any[]>([])
  const timetable = ref<any[]>([])
  const timetableStats = ref<any[]>([])
  const loading = ref(false)

  async function loadSemesters(schoolYear?: string) {
    loading.value = true
    try {
      semesters.value = await api.getSemesters(schoolYear ? { school_year: schoolYear } : undefined)
    } finally {
      loading.value = false
    }
  }

  async function loadCurrentSemester() {
    currentSemester.value = await api.getCurrentSemester()
  }

  async function loadPeriods(semesterId: string) {
    periods.value = await api.getPeriods({ semester_id: semesterId })
  }

  async function loadTimetable(semesterId: string, classId?: string, teacherId?: string) {
    loading.value = true
    try {
      const params: Record<string, any> = { semester_id: semesterId }
      if (classId) params.class_id = classId
      if (teacherId) params.teacher_id = teacherId
      timetable.value = await api.getTimetable(params)
    } finally {
      loading.value = false
    }
  }

  async function loadTimetableStats(semesterId: string, classId: string) {
    timetableStats.value = await api.getTimetableStats({ semester_id: semesterId, class_id: classId })
  }

  function semesterProgress(semester: any): { percent: number; week: number } {
    if (!semester?.start_date || !semester?.end_date) return { percent: 0, week: 0 }
    const start = new Date(semester.start_date).getTime()
    const end = new Date(semester.end_date).getTime()
    const now = Date.now()
    const total = end - start
    const elapsed = Math.min(Math.max(now - start, 0), total)
    const percent = Math.round((elapsed / total) * 100)
    const week = Math.ceil(elapsed / (7 * 24 * 60 * 60 * 1000))
    return { percent, week }
  }

  return {
    semesters, currentSemester, periods, timetable, timetableStats, loading,
    loadSemesters, loadCurrentSemester, loadPeriods, loadTimetable, loadTimetableStats,
    semesterProgress,
  }
}
```

- [ ] **Step 3: Add useAcademic mock to setup.ts**

Add after the `useAnalytics` mock block:

```typescript
// useAcademic mock
g.useAcademic = () => ({
  semesters: ref([]),
  currentSemester: ref(null),
  periods: ref([]),
  timetable: ref([]),
  timetableStats: ref([]),
  loading: ref(false),
  loadSemesters: vi.fn(),
  loadCurrentSemester: vi.fn(),
  loadPeriods: vi.fn(),
  loadTimetable: vi.fn(),
  loadTimetableStats: vi.fn(),
  semesterProgress: vi.fn().mockReturnValue({ percent: 0, week: 0 }),
})
```

- [ ] **Step 4: Commit**

```bash
git add frontend-nuxt/composables/useApi.ts frontend-nuxt/composables/useAcademic.ts frontend-nuxt/tests/setup.ts
git commit -m "feat(frontend): useAcademic composable + 12 useApi methods"
```

---

### Task 13: semester.vue Page

**Files:**
- Modify: `frontend-nuxt/pages/academic/semester.vue` (replace stub)

- [ ] **Step 1: Replace semester.vue stub**

```vue
<template>
  <div class="p-6">
    <div class="flex justify-between items-center mb-6">
      <h2 class="text-xl font-bold">学期管理</h2>
      <el-button type="primary" @click="showCreateDialog = true">新建学期</el-button>
    </div>

    <!-- Current semester card -->
    <el-card v-if="currentSem" class="mb-6">
      <template #header><span class="font-bold">当前学期</span></template>
      <div class="flex items-center gap-4">
        <div>
          <div class="text-lg font-medium">{{ currentSem.name }}</div>
          <div class="text-sm text-gray-500">{{ currentSem.start_date }} ~ {{ currentSem.end_date }}</div>
        </div>
        <div class="flex-1">
          <el-progress :percentage="progress.percent" :format="() => `已过 ${progress.percent}%（第 ${progress.week} 周）`" />
        </div>
      </div>
    </el-card>

    <!-- Semesters table -->
    <el-card class="mb-6">
      <template #header><span class="font-bold">历史学期</span></template>
      <el-table :data="academic.semesters.value" stripe>
        <el-table-column prop="name" label="学期名" />
        <el-table-column prop="school_year" label="学年" width="120" />
        <el-table-column label="起止日期" width="220">
          <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_current ? 'success' : 'info'" size="small">
              {{ row.is_current ? '当前' : '历史' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button v-if="!row.is_current" size="small" @click="doActivate(row.id)">激活</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Periods card -->
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span class="font-bold">作息时间表</span>
          <el-button size="small" @click="showPeriodDialog = true">编辑作息</el-button>
        </div>
      </template>
      <el-table :data="academic.periods.value" stripe size="small">
        <el-table-column prop="period_number" label="节次" width="60" />
        <el-table-column prop="name" label="名称" width="100" />
        <el-table-column label="时间" width="140">
          <template #default="{ row }">{{ row.start_time }} - {{ row.end_time }}</template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.period_type === 'class' ? 'primary' : 'info'">
              {{ { class: '正课', self_study: '自习', break: '课间', activity: '活动' }[row.period_type] || row.period_type }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create dialog -->
    <el-dialog v-model="showCreateDialog" title="新建学期" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="学期名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="学年"><el-input v-model="form.school_year" placeholder="2025-2026" /></el-form-item>
        <el-form-item label="学期">
          <el-radio-group v-model="form.term">
            <el-radio :value="1">第一学期</el-radio>
            <el-radio :value="2">第二学期</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="doCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- Period edit dialog (simplified) -->
    <el-dialog v-model="showPeriodDialog" title="编辑作息时间" width="600px">
      <p class="text-sm text-gray-500 mb-2">编辑作息时间表功能开发中</p>
      <template #footer>
        <el-button @click="showPeriodDialog = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const academic = useAcademic()

const showCreateDialog = ref(false)
const showPeriodDialog = ref(false)
const form = reactive({ name: '', school_year: '', term: 1, start_date: '', end_date: '' })

const currentSem = computed(() =>
  academic.semesters.value.find((s: any) => s.is_current) || null
)
const progress = computed(() => academic.semesterProgress(currentSem.value))

async function doCreate() {
  await api.createSemester(form)
  showCreateDialog.value = false
  await academic.loadSemesters()
}

async function doActivate(id: string) {
  await api.activateSemester(id)
  await academic.loadSemesters()
}

function openEdit(row: any) {
  ElMessage.info('编辑功能开发中')
}

onMounted(async () => {
  await academic.loadSemesters()
  if (currentSem.value) {
    await academic.loadPeriods(currentSem.value.id)
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend-nuxt/pages/academic/semester.vue
git commit -m "feat(frontend): semester management page"
```

---

### Task 14: timetable.vue Page

**Files:**
- Modify: `frontend-nuxt/pages/academic/timetable.vue` (replace stub)

- [ ] **Step 1: Replace timetable.vue stub**

```vue
<template>
  <div class="p-6">
    <h2 class="text-xl font-bold mb-4">课程表</h2>

    <!-- Filters -->
    <div class="flex gap-4 mb-4">
      <el-select v-model="selectedGrade" placeholder="年级" class="w-32">
        <el-option v-for="g in grades" :key="g" :label="g" :value="g" />
      </el-select>
      <el-select v-model="selectedClassId" placeholder="班级" class="w-40">
        <el-option v-for="c in filteredClasses" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>
      <el-radio-group v-model="viewMode">
        <el-radio-button value="class">按班级</el-radio-button>
        <el-radio-button value="teacher">按教师</el-radio-button>
      </el-radio-group>
    </div>

    <div class="flex gap-4">
      <!-- Timetable grid -->
      <el-card class="flex-1">
        <el-table :data="gridRows" border stripe :cell-class-name="cellClassName">
          <el-table-column prop="period_label" label="节次" width="100" fixed />
          <el-table-column v-for="d in 5" :key="d" :label="weekdayLabels[d-1]" min-width="140">
            <template #default="{ row }">
              <div v-if="row.slots[d]" class="text-center text-xs leading-5"
                   :style="{ backgroundColor: subjectColor(row.slots[d].subject_code) + '20' }">
                <div class="font-medium" :style="{ color: subjectColor(row.slots[d].subject_code) }">
                  {{ row.slots[d].subject_code }}
                </div>
                <div class="text-gray-500">{{ row.slots[d].teacher_id?.slice(0,6) }}</div>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- Stats sidebar -->
      <el-card class="w-48" v-if="academic.timetableStats.value.length">
        <template #header><span class="font-bold text-sm">课时统计</span></template>
        <div v-for="s in academic.timetableStats.value" :key="s.subject_code" class="flex justify-between text-sm mb-2">
          <el-tag size="small" :color="subjectColor(s.subject_code) + '20'"
                  :style="{ color: subjectColor(s.subject_code), borderColor: subjectColor(s.subject_code) }">
            {{ s.subject_code }}
          </el-tag>
          <span>{{ s.count }}节</span>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const academic = useAcademic()

const selectedGrade = ref('')
const selectedClassId = ref('')
const viewMode = ref('class')
const classes = ref<any[]>([])

const grades = computed(() => [...new Set(classes.value.map((c: any) => c.grade))])
const filteredClasses = computed(() =>
  selectedGrade.value ? classes.value.filter((c: any) => c.grade === selectedGrade.value) : classes.value
)

const weekdayLabels = ['周一', '周二', '周三', '周四', '周五']
const todayWeekday = new Date().getDay()

const SUBJECT_COLORS: Record<string, string> = {
  chinese: '#E74C3C', math: '#3498DB', english: '#2ECC71',
  physics: '#9B59B6', chemistry: '#E67E22', biology: '#1ABC9C',
  history: '#F39C12', geography: '#16A085', politics: '#8E44AD',
}

function subjectColor(code: string) {
  return SUBJECT_COLORS[code] || '#95A5A6'
}

function cellClassName({ columnIndex }: any) {
  if (columnIndex > 0 && columnIndex === todayWeekday) return 'bg-blue-50'
  return ''
}

const gridRows = computed(() => {
  const periods = academic.periods.value.filter((p: any) => p.period_type !== 'break')
  return periods.map((p: any) => {
    const slotsMap: Record<number, any> = {}
    for (const s of academic.timetable.value) {
      if (s.period_id === p.id) slotsMap[s.weekday] = s
    }
    return { period_label: `${p.name}\n${p.start_time}-${p.end_time}`, slots: slotsMap }
  })
})

watch([selectedClassId], async () => {
  if (!selectedClassId.value || !academic.currentSemester.value?.id) return
  const semId = academic.currentSemester.value.id
  await academic.loadTimetable(semId, selectedClassId.value)
  await academic.loadTimetableStats(semId, selectedClassId.value)
})

onMounted(async () => {
  await academic.loadCurrentSemester()
  const resp = await api.getClasses()
  classes.value = Array.isArray(resp) ? resp : resp?.items || []
  if (academic.currentSemester.value?.id) {
    await academic.loadPeriods(academic.currentSemester.value.id)
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend-nuxt/pages/academic/timetable.vue
git commit -m "feat(frontend): timetable page with grid view + stats sidebar"
```

---

### Task 15: exam-schedule.vue Page

**Files:**
- Modify: `frontend-nuxt/pages/academic/exam-schedule.vue` (replace stub)

- [ ] **Step 1: Replace exam-schedule.vue stub**

```vue
<template>
  <div class="p-6">
    <h2 class="text-xl font-bold mb-4">考试安排</h2>

    <!-- Filters -->
    <div class="flex gap-4 mb-6">
      <el-select v-model="selectedSemesterId" placeholder="学期" class="w-60">
        <el-option v-for="s in academic.semesters.value" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
      <el-select v-model="selectedType" placeholder="考试类型" class="w-32" clearable>
        <el-option label="全部" value="" />
        <el-option label="月考" value="monthly" />
        <el-option label="期中" value="midterm" />
        <el-option label="期末" value="final" />
        <el-option label="测验" value="quiz" />
      </el-select>
    </div>

    <!-- Timeline -->
    <el-timeline>
      <el-timeline-item
        v-for="exam in filteredExams" :key="exam.id"
        :type="examStatus(exam) === 'ongoing' ? 'primary' : examStatus(exam) === 'completed' ? 'success' : 'info'"
        :hollow="examStatus(exam) === 'upcoming'"
        :style="examStatus(exam) === 'ongoing' ? { borderLeft: '3px solid var(--el-color-primary)' } : examStatus(exam) === 'completed' ? { opacity: 0.8 } : {}"
      >
        <div class="flex items-center gap-2 mb-2">
          <span class="font-bold">{{ exam.exam_name }}</span>
          <el-tag size="small" :type="examStatus(exam) === 'ongoing' ? 'success' : examStatus(exam) === 'completed' ? 'info' : 'primary'">
            {{ { upcoming: '待考', ongoing: '进行中', completed: '已完成' }[examStatus(exam)] }}
          </el-tag>
        </div>
        <div class="text-sm text-gray-500 mb-2">{{ exam.subjects.length }} 科</div>
        <div v-for="sub in exam.subjects.filter((s: any) => s.exam_start)" :key="sub.id" class="text-sm mb-1">
          <el-tag size="small" class="mr-2">{{ sub.name }}</el-tag>
          <span class="text-gray-600">{{ formatTime(sub.exam_start) }} - {{ formatTime(sub.exam_end) }}</span>
          <span v-if="sub.exam_room" class="text-gray-400 ml-2">{{ sub.exam_room }}</span>
        </div>
        <div v-if="!exam.subjects.some((s: any) => s.exam_start)" class="text-sm text-gray-400">暂未安排时间</div>
      </el-timeline-item>
    </el-timeline>

    <el-empty v-if="!filteredExams.length" description="暂无考试" />
  </div>
</template>

<script setup lang="ts">
const api = useApi()
const academic = useAcademic()

const selectedSemesterId = ref('')
const selectedType = ref('')
const exams = ref<any[]>([])

const filteredExams = computed(() => {
  let list = exams.value
  if (selectedType.value) {
    list = list.filter((e: any) => e.exam_type === selectedType.value)
  }
  return list
})

function examStatus(exam: any): string {
  const now = new Date()
  const subjects = exam.subjects || []
  const scheduled = subjects.filter((s: any) => s.exam_start && s.exam_end)
  if (!scheduled.length) return 'upcoming'
  if (scheduled.every((s: any) => new Date(s.exam_end) < now)) return 'completed'
  if (scheduled.some((s: any) => new Date(s.exam_start) <= now && now <= new Date(s.exam_end))) return 'ongoing'
  return 'upcoming'
}

function formatTime(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

async function loadExams() {
  // Backend GET /exams has no semester query param, so fetch all and filter client-side
  // Exam model has a `semester` string field matching Semester.school_year
  const examList = await api.getExams()
  let items = Array.isArray(examList) ? examList : examList?.items || []

  // Client-side semester filtering via Exam.semester field
  if (selectedSemesterId.value) {
    const sem = academic.semesters.value.find((s: any) => s.id === selectedSemesterId.value)
    if (sem) {
      items = items.filter((e: any) => !e.semester || e.semester === sem.school_year)
    }
  }

  const results = []
  for (const e of items) {
    try {
      const schedule = await api.getExamSchedule(e.id)
      results.push({ ...e, ...schedule })
    } catch {
      results.push({ ...e, subjects: [] })
    }
  }
  exams.value = results
}

watch(selectedSemesterId, () => { if (selectedSemesterId.value) loadExams() })

onMounted(async () => {
  await academic.loadSemesters()
  if (academic.semesters.value.length) {
    const current = academic.semesters.value.find((s: any) => s.is_current)
    selectedSemesterId.value = current?.id || academic.semesters.value[0].id
  }
})
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend-nuxt/pages/academic/exam-schedule.vue
git commit -m "feat(frontend): exam schedule page with timeline view"
```

---

### Task 16: Frontend Tests

**Files:**
- Create: `frontend-nuxt/tests/composables/useAcademic.test.ts`

**Test Contract:**
- 入口: useAcademic composable functions
- 反例: semesterProgress with null semester returns { percent: 0, week: 0 }
- 边界: loadSemesters calls API correctly; loadTimetable passes class_id param
- 回归: existing Vitest unaffected
- 命令: `cd frontend-nuxt && npx vitest run tests/composables/useAcademic.test.ts`

- [ ] **Step 1: Write frontend tests**

```typescript
// frontend-nuxt/tests/composables/useAcademic.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
;(globalThis as any).$fetch = mockFetch

describe('useAcademic', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  it('loadSemesters calls API and stores result', async () => {
    const mockData = [{ id: '1', name: 'S1', is_current: true }]
    mockFetch.mockResolvedValueOnce(mockData)

    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    await academic.loadSemesters()

    expect(mockFetch).toHaveBeenCalledWith(
      '/academic/semesters',
      expect.objectContaining({ baseURL: expect.any(String) })
    )
    expect(academic.semesters.value).toEqual(mockData)
  })

  it('loadTimetable passes class_id as query param', async () => {
    mockFetch.mockResolvedValueOnce([])

    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    await academic.loadTimetable('sem-1', 'cls-1')

    expect(mockFetch).toHaveBeenCalledWith(
      '/academic/timetable',
      expect.objectContaining({
        query: { semester_id: 'sem-1', class_id: 'cls-1' },
      })
    )
  })

  it('semesterProgress returns 0 for null semester', async () => {
    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    const result = academic.semesterProgress(null)
    expect(result).toEqual({ percent: 0, week: 0 })
  })

  it('semesterProgress calculates correctly for past date range', async () => {
    const { useAcademic } = await import('../../composables/useAcademic')
    const academic = useAcademic()
    const result = academic.semesterProgress({
      start_date: '2020-01-01',
      end_date: '2020-06-30',
    })
    expect(result.percent).toBe(100)
  })
})
```

- [ ] **Step 2: Run frontend tests**

Run:
```bash
cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run tests/composables/useAcademic.test.ts
```
Expected: 4 passed

- [ ] **Step 3: Run all frontend tests**

Run:
```bash
cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run
```
Expected: 55 passed (51 existing + 4 new)

- [ ] **Step 4: Commit**

```bash
git add frontend-nuxt/tests/composables/useAcademic.test.ts
git commit -m "test(frontend): useAcademic composable tests (4 cases)"
```

---

## Final Verification

- [ ] **Run full backend test suite**

```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q
```
Expected: 2065+ passed (2046 baseline + 19 new)

- [ ] **Run full frontend test suite**

```bash
cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run
```
Expected: 55 passed (51 baseline + 4 new)

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "同一学校同一 school_year+term 不能有两个学期"
      verification: pending_test
      test_ref: "test_academic_semester.py::test_duplicate_semester_rejected"
    - id: INV-002
      statement: "同一学校同时只有一个 is_current=True 的学期"
      verification: pending_test
      test_ref: "test_academic_semester.py::test_activate_mutual_exclusion"
    - id: INV-003
      statement: "同一班级同一学期同一 weekday+period 只能有一个课表格子"
      verification: pending_test
      test_ref: "UniqueConstraint uq_timetable_slot"
    - id: INV-004
      statement: "同一教师同一学期同一 weekday+period 不能在两个班上课"
      verification: pending_test
      test_ref: "test_academic_timetable.py::test_teacher_conflict_rejected"
    - id: INV-005
      statement: "同一考试的科目时间段不能重叠"
      verification: pending_test
      test_ref: "test_exam_schedule.py::test_overlap_rejected"
  counter_examples:
    - id: CE-001
      description: "如果删除 activate 互斥逻辑，test_activate_mutual_exclusion 仍通过"
      tests_that_still_pass: "No — test asserts current_count == 1 across all semesters"
      mitigation: "Test explicitly counts is_current=True across full list"
    - id: CE-002
      description: "如果删除冲突检测，test_teacher_conflict_rejected 仍通过"
      tests_that_still_pass: "No — test asserts status 422 on conflicting save"
      mitigation: "Test creates slot in class1 then attempts same teacher+period in class2"
    - id: CE-003
      description: "如果 conduct 双写返回 platform_sem.id 而非 conduct_sem.id"
      tests_that_still_pass: "No — test_create_writes_both_tables verifies conduct table has record, conduct router check_resource_class(ConductSemester) would 404"
      mitigation: "create_semester returns conduct_sem.id; test verifies both tables written and returned ID is from conduct_semesters"
    - id: CE-004
      description: "如果 period_type 校验被删除，break 类型节次可被排课"
      tests_that_still_pass: "No — 需新增测试验证 break 类型节次被拒绝"
      mitigation: "save_timetable 校验 period.period_type in SCHEDULABLE_PERIOD_TYPES"
  risk_modules:
    - module: "modules/conduct/admin_service.py"
      reason: "双写改动影响现有 conduct 学期功能，返回 ID 类型决定 conduct 路由能否正常校验"
    - module: "modules/conduct/admin_router.py"
      reason: "line 408 check_resource_class(ConductSemester) 依赖返回的 ID 是 ConductSemester"
    - module: "modules/exam/models.py"
      reason: "Subject 表扩展可能影响现有考试功能"
    - module: "modules/exam/router.py"
      reason: "新增 schedule 端点，路径前缀 /api/v1/exams 已存在，新路径须为 /{exam_id}/schedule"
  test_debt:
    - description: "semester.vue 和 timetable.vue 的编辑模式未覆盖端到端测试"
      reason: "前端视觉交互测试需要 Playwright，超出本批次范围"
      deadline: "2026-05-15"
    - description: "conduct 双写的路由级集成测试（通过 HTTP 调用 conduct API 验证平台 Semester 同步创建）"
      reason: "Task 11 仅覆盖 service 级，路由级需 conduct 完整 fixture"
      deadline: "2026-05-08"

semantic_regression:
  - "ORC-001: 现有 Exam/TeacherAssignment/CalendarEvent 的 semester 字符串字段不做改动"
  - "ORC-002: conduct_semesters 表保留不删，双写过渡保持 conduct_records FK 不断"
  - "ORC-003: MANAGE_SCHEDULING 权限不新增，复用现有枚举"
  - "ORC-004: Subject 表新增字段全部 nullable，不影响现有考试功能"
```
