import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError

from edu_cloud.modules.conduct.models import (
    StudentProfile,
    ConductClassConfig,
    ConductRecord,
    ConductGroup,
    ConductSemester,
)
from tests.test_conduct.conftest import _make_school_class_student


@pytest.mark.asyncio
async def test_student_profile_create(db):
    """StudentProfile: create and verify avatar/ethnicity fields."""
    school, cls, student = await _make_school_class_student(db)
    profile = StudentProfile(
        student_id=student.id,
        avatar="boy01",
        ethnicity="汉族",
        birth_date=date(2010, 5, 15),
        blood_type="A",
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    assert profile.avatar == "boy01"
    assert profile.ethnicity == "汉族"
    assert profile.birth_date == date(2010, 5, 15)
    assert profile.blood_type == "A"
    assert profile.id is not None
    assert profile.created_at is not None


@pytest.mark.asyncio
async def test_conduct_class_config_unique_invite(db):
    """ConductClassConfig: verify default verify_code_type is 'id_card'."""
    school, cls, _ = await _make_school_class_student(db)
    config = ConductClassConfig(class_id=cls.id, invite_code="ABC123")
    db.add(config)
    await db.commit()
    await db.refresh(config)

    assert config.verify_code_type == "id_card"
    assert config.is_active is True
    assert config.invite_code == "ABC123"


@pytest.mark.asyncio
async def test_conduct_record_create(db):
    """ConductRecord: create and verify default source is 'manual'."""
    from edu_cloud.models.user import User

    school, cls, student = await _make_school_class_student(db)
    operator = User(username="operator1", display_name="操作员")
    operator.set_password("test123")
    db.add(operator)
    await db.flush()

    # Need a semester for nullable FK
    semester = ConductSemester(
        name="2025-2026-2",
        school_id=school.id,
        start_date=date(2026, 2, 1),
        end_date=date(2026, 7, 1),
    )
    db.add(semester)
    await db.flush()

    record = ConductRecord(
        student_id=student.id,
        class_id=cls.id,
        points=5,
        reason="上课积极回答问题",
        date=date(2026, 4, 12),
        operator_id=operator.id,
        semester_id=semester.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    assert record.source == "manual"
    assert record.points == 5
    assert record.reason == "上课积极回答问题"
    assert record.created_at is not None


@pytest.mark.asyncio
async def test_conduct_group_unique_constraint(db):
    """ConductGroup: duplicate group name in same class raises IntegrityError."""
    school, cls, _ = await _make_school_class_student(db)

    g1 = ConductGroup(name="第一组", class_id=cls.id)
    db.add(g1)
    await db.commit()

    g2 = ConductGroup(name="第一组", class_id=cls.id)
    db.add(g2)
    with pytest.raises(IntegrityError):
        await db.flush()
