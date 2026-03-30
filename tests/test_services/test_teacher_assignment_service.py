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


@pytest.mark.asyncio
async def test_create_assignments_rejects_cross_school_class(db, seed_school):
    """P2 fix: class_ids belonging to another school should be rejected."""
    from edu_cloud.services.exceptions import ValidationError as SvcValidationError
    from edu_cloud.models.school import School

    school_a, _ = seed_school
    school_b = School(name="另一校", code="OTHER01", district="测试区", api_key_hash="x")
    db.add(school_b)
    await db.flush()

    user = User(username="cross_school_teacher", display_name="跨校教师")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    cls_b = Class(name="B校班级", grade="高三", grade_number=12, school_id=school_b.id)
    db.add(cls_b)
    await db.flush()

    with pytest.raises(SvcValidationError, match="不属于目标学校"):
        await create_assignments(
            db, school_id=school_a.id, user_id=user.id,
            class_ids=[cls_b.id], subject_code="math", semester="2025-2026-2",
        )


# ── ScopeFilter integration ──

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


@pytest.mark.asyncio
async def test_list_assignments_with_scope_class_ids(db, seed_school):
    """CR-01 fix: ScopeFilter class_ids 也应过滤。"""
    school, _ = seed_school
    user, classes = await _seed_teacher_and_classes(db, school.id)
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[classes[0].id], subject_code="math", semester="2025-2026-2",
    )
    await create_assignments(
        db, school_id=school.id, user_id=user.id,
        class_ids=[classes[1].id], subject_code="math", semester="2025-2026-2",
    )

    role = UserRole(
        user_id=user.id, role="homeroom_teacher",
        school_id=school.id, class_ids=[classes[0].id],
    )
    scope = ScopeFilter(role)
    rows = await list_assignments(db, school_id=school.id, scope=scope)
    assert len(rows) == 1
    assert rows[0].class_id == classes[0].id
