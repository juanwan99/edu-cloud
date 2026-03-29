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
