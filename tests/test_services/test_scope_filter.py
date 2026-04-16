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
    other_cls = Class(name="OtherClass", grade="高一", grade_number=10, school_id=other_school.id)
    db.add(other_cls)
    await db.flush()
    db.add(TeacherAssignment(
        user_id=user.id, class_id=other_cls.id,
        subject_code="math", semester="2025-2026-2", school_id=other_school.id,
    ))
    await db.commit()

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

    role = UserRole(
        user_id=user.id, role="principal",
        school_id=school.id,
    )
    sf = ScopeFilter(role)
    stmt = select(TeacherAssignment)
    stmt = sf.apply(stmt, TeacherAssignment, class_col="class_id", subject_col="subject_code")
    result = (await db.execute(stmt)).scalars().all()
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
