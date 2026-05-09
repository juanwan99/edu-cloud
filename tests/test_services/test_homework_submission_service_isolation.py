"""T2: Homework service-level cross-school isolation tests.

Existing tests in test_api/test_homework_submission_isolation.py are blocked
at the router level (get_task 404).  These tests call the service methods
directly to verify the JOIN-based depth defense in HomeworkSubmissionService.
"""
import pytest

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student
from edu_cloud.modules.homework.models import HomeworkTask, HomeworkSubmission
from edu_cloud.modules.homework.service import (
    HomeworkSubmissionService,
    HomeworkTaskService,
)
from edu_cloud.services.exceptions import NotFoundError


@pytest.fixture
async def two_school_hw(db):
    """Two schools each with a teacher, class, student, and published task."""
    # --- School A ---
    school_a = School(name="服务隔离A校", code="SVCIA", district="测试区", api_key_hash="x")
    db.add(school_a)
    await db.flush()

    teacher_a = User(username="svc_iso_a", display_name="A校老师")
    teacher_a.set_password("123456")
    db.add(teacher_a)
    await db.flush()

    cls_a = ClassGroup(name="A-七1班", grade="七年级", grade_number=7, school_id=school_a.id)
    db.add(cls_a)
    await db.flush()

    stu_a = Student(
        name="A学生", student_number="SVCA001",
        school_id=school_a.id, grade="七年级", class_id=cls_a.id,
    )
    db.add(stu_a)
    await db.flush()

    task_a = await HomeworkTaskService.create_task(
        db, school_id=school_a.id, title="A校服务测试作业",
        task_type="regular", subject_code="SX",
        class_id=cls_a.id, assigned_by=teacher_a.id,
    )
    await HomeworkTaskService.transition_status(
        db, task_id=task_a.id, school_id=school_a.id, action="publish",
    )

    subs_a = await HomeworkSubmissionService.list_submissions(
        db, task_id=task_a.id, school_id=school_a.id,
    )
    sub_a = subs_a[0]

    # --- School B ---
    school_b = School(name="服务隔离B校", code="SVCIB", district="测试区", api_key_hash="x")
    db.add(school_b)
    await db.flush()

    teacher_b = User(username="svc_iso_b", display_name="B校老师")
    teacher_b.set_password("123456")
    db.add(teacher_b)
    await db.flush()

    cls_b = ClassGroup(name="B-七1班", grade="七年级", grade_number=7, school_id=school_b.id)
    db.add(cls_b)
    await db.flush()

    stu_b = Student(
        name="B学生", student_number="SVCB001",
        school_id=school_b.id, grade="七年级", class_id=cls_b.id,
    )
    db.add(stu_b)
    await db.flush()

    await db.commit()

    return {
        "school_a_id": school_a.id,
        "school_b_id": school_b.id,
        "teacher_a_id": teacher_a.id,
        "teacher_b_id": teacher_b.id,
        "task_a_id": task_a.id,
        "sub_a_id": sub_a.id,
        "stu_a_id": stu_a.id,
    }


@pytest.mark.asyncio
async def test_submit_service_rejects_wrong_school(db, two_school_hw):
    """Direct service call: submit with wrong school_id raises NotFoundError."""
    with pytest.raises(NotFoundError):
        await HomeworkSubmissionService.submit(
            db,
            task_id=two_school_hw["task_a_id"],
            submission_id=two_school_hw["sub_a_id"],
            school_id=two_school_hw["school_b_id"],  # wrong school
            content="cross-school hack",
        )


@pytest.mark.asyncio
async def test_list_submissions_service_returns_empty_for_wrong_school(db, two_school_hw):
    """Direct service call: list_submissions with wrong school_id returns empty.

    list_submissions uses JOIN (HomeworkTask.school_id == school_id), so the
    wrong school_id naturally returns zero rows without raising.
    """
    subs = await HomeworkSubmissionService.list_submissions(
        db,
        task_id=two_school_hw["task_a_id"],
        school_id=two_school_hw["school_b_id"],  # wrong school
    )
    assert len(subs) == 0


@pytest.mark.asyncio
async def test_get_task_service_rejects_wrong_school(db, two_school_hw):
    """Direct service call: get_task with wrong school_id raises NotFoundError."""
    with pytest.raises(NotFoundError):
        await HomeworkTaskService.get_task(
            db,
            task_id=two_school_hw["task_a_id"],
            school_id=two_school_hw["school_b_id"],  # wrong school
        )


@pytest.mark.asyncio
async def test_grade_batch_service_rejects_wrong_school(db, two_school_hw):
    """Direct service call: grade_batch with wrong school_id returns 0 (JOIN blocks)."""
    # First submit via correct school so there's a graded-eligible row
    await HomeworkSubmissionService.submit(
        db,
        task_id=two_school_hw["task_a_id"],
        submission_id=two_school_hw["sub_a_id"],
        school_id=two_school_hw["school_a_id"],
        content="legitimate answer",
    )

    # Cross-school grade_batch: wrong school_id → JOIN yields empty → count=0
    count = await HomeworkSubmissionService.grade_batch(
        db,
        task_id=two_school_hw["task_a_id"],
        school_id=two_school_hw["school_b_id"],  # wrong school
        grades=[{"student_id": two_school_hw["stu_a_id"], "score": 100.0}],
        graded_by=two_school_hw["teacher_b_id"],
    )
    assert count == 0


@pytest.mark.asyncio
async def test_grade_single_service_rejects_wrong_school(db, two_school_hw):
    """Direct service call: grade_single with wrong school_id raises NotFoundError."""
    # First submit via correct school
    await HomeworkSubmissionService.submit(
        db,
        task_id=two_school_hw["task_a_id"],
        submission_id=two_school_hw["sub_a_id"],
        school_id=two_school_hw["school_a_id"],
        content="legitimate answer",
    )

    # Cross-school grade attempt at service level
    with pytest.raises(NotFoundError):
        await HomeworkSubmissionService.grade_single(
            db,
            task_id=two_school_hw["task_a_id"],
            submission_id=two_school_hw["sub_a_id"],
            school_id=two_school_hw["school_b_id"],  # wrong school
            score=100.0,
            feedback="hack",
            graded_by=two_school_hw["teacher_b_id"],
        )
