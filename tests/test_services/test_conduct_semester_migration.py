"""Test conduct ↔ academic Semester side-write migration (方案 E).

ConductSemester is class-owned and remains the authoritative entity for conduct
semester APIs. Platform Semester is written once per (school_id, school_year,
term=1) as an idempotent side-effect, so the academic module can reference the
school-level timeline. is_current is NOT synced across the two models; they
carry independent meaning (class-scoped conduct period vs school-scoped term).
"""
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
    cls_a = Class(name="初一1班", grade="初一", school_id=school.id)
    cls_b = Class(name="初一2班", grade="初一", school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.commit()
    await db.refresh(school)
    await db.refresh(cls_a)
    await db.refresh(cls_b)
    return school, cls_a, cls_b


@pytest.mark.asyncio
async def test_create_side_writes_platform_semester(db, setup):
    """Creating a ConductSemester also writes a corresponding platform Semester."""
    school, cls_a, _ = setup
    result = await admin_service.create_semester(
        db, cls_a.id, "2025-2026第一学期", date(2025, 9, 1), date(2026, 1, 15),
    )
    # Returned id is ConductSemester.id (authoritative entity for conduct API)
    conduct = (await db.execute(select(ConductSemester).where(ConductSemester.class_id == cls_a.id))).scalars().all()
    assert len(conduct) == 1
    assert result["id"] == conduct[0].id

    # Platform Semester was side-written (school-level)
    platform = (await db.execute(select(Semester).where(Semester.school_id == school.id))).scalars().all()
    assert len(platform) == 1
    assert platform[0].school_year == "2025-2026"
    assert platform[0].term == 1


@pytest.mark.asyncio
async def test_create_is_idempotent_across_classes(db, setup):
    """Two classes creating the same-named semester share ONE platform Semester."""
    school, cls_a, cls_b = setup
    await admin_service.create_semester(
        db, cls_a.id, "2025-2026第一学期", date(2025, 9, 1), date(2026, 1, 15),
    )
    await admin_service.create_semester(
        db, cls_b.id, "2025-2026第一学期", date(2025, 9, 1), date(2026, 1, 15),
    )

    # Each class has its own ConductSemester (class-owned)
    conduct = (await db.execute(select(ConductSemester).where(ConductSemester.school_id == school.id))).scalars().all()
    assert len(conduct) == 2

    # Platform Semester deduplicated by (school_id, school_year, term=1)
    platform = (await db.execute(select(Semester).where(Semester.school_id == school.id))).scalars().all()
    assert len(platform) == 1


@pytest.mark.asyncio
async def test_conduct_semantics_preserved(db, setup):
    """get_semesters is class-scoped; activate_semester is class-scoped."""
    school, cls_a, cls_b = setup
    r1 = await admin_service.create_semester(db, cls_a.id, "S1 class A", date(2025, 9, 1), date(2026, 1, 15))
    await admin_service.create_semester(db, cls_a.id, "S2 class A", date(2026, 2, 17), date(2026, 7, 10))
    await admin_service.create_semester(db, cls_b.id, "S1 class B", date(2025, 9, 1), date(2026, 1, 15))

    # get_semesters returns only cls_a's semesters (class-scoped)
    result_a = await admin_service.get_semesters(db, cls_a.id)
    assert len(result_a) == 2
    assert all("class A" in s["name"] for s in result_a)

    result_b = await admin_service.get_semesters(db, cls_b.id)
    assert len(result_b) == 1
    assert result_b[0]["name"] == "S1 class B"

    # activate_semester only flips cls_a's rows, leaves cls_b untouched
    await admin_service.activate_semester(db, r1["id"])
    cls_a_current = sum(
        1 for s in (await db.execute(
            select(ConductSemester).where(ConductSemester.class_id == cls_a.id)
        )).scalars().all()
        if s.is_current
    )
    cls_b_current = sum(
        1 for s in (await db.execute(
            select(ConductSemester).where(ConductSemester.class_id == cls_b.id)
        )).scalars().all()
        if s.is_current
    )
    assert cls_a_current == 1
    assert cls_b_current == 0  # cls_b unaffected by cls_a activation
