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
