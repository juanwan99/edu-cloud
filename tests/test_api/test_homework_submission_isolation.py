"""Task 5: Homework submission cross-school isolation tests.

Verifies that school_id depth defense in HomeworkSubmissionService
prevents cross-school access via submit/grade_single/list_submissions/grade_batch.
"""
import pytest

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student
from edu_cloud.modules.homework.models import HomeworkTask, HomeworkSubmission
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def two_schools(db):
    """Create two schools, each with a teacher, class, students, and a published task."""
    # --- School A ---
    school_a = School(name="A校", code="ISOLA", district="测试区", api_key_hash="x")
    db.add(school_a)
    await db.flush()

    teacher_a = User(username="iso_teacher_a", display_name="A校老师")
    teacher_a.set_password("123456")
    db.add(teacher_a)
    await db.flush()
    db.add(UserRole(
        user_id=teacher_a.id, role="homeroom_teacher",
        school_id=school_a.id, class_ids=[], is_primary=True,
    ))

    cls_a = ClassGroup(name="A-七1班", grade="七年级", grade_number=7, school_id=school_a.id)
    db.add(cls_a)
    await db.flush()

    stu_a = Student(
        name="A学生", student_number="A001",
        school_id=school_a.id, grade="七年级", class_id=cls_a.id,
    )
    db.add(stu_a)
    await db.flush()

    task_a = HomeworkTask(
        school_id=school_a.id, title="A校作业", task_type="regular",
        subject_code="SX", class_id=cls_a.id, assigned_by=teacher_a.id,
        status="active",
    )
    db.add(task_a)
    await db.flush()

    sub_a = HomeworkSubmission(task_id=task_a.id, student_id=stu_a.id, status="pending")
    db.add(sub_a)
    await db.flush()

    # --- School B ---
    school_b = School(name="B校", code="ISOLB", district="测试区", api_key_hash="x")
    db.add(school_b)
    await db.flush()

    teacher_b = User(username="iso_teacher_b", display_name="B校老师")
    teacher_b.set_password("123456")
    db.add(teacher_b)
    await db.flush()
    db.add(UserRole(
        user_id=teacher_b.id, role="homeroom_teacher",
        school_id=school_b.id, class_ids=[], is_primary=True,
    ))

    cls_b = ClassGroup(name="B-七1班", grade="七年级", grade_number=7, school_id=school_b.id)
    db.add(cls_b)
    await db.flush()

    stu_b = Student(
        name="B学生", student_number="B001",
        school_id=school_b.id, grade="七年级", class_id=cls_b.id,
    )
    db.add(stu_b)
    await db.flush()

    task_b = HomeworkTask(
        school_id=school_b.id, title="B校作业", task_type="regular",
        subject_code="SX", class_id=cls_b.id, assigned_by=teacher_b.id,
        status="active",
    )
    db.add(task_b)
    await db.flush()

    sub_b = HomeworkSubmission(task_id=task_b.id, student_id=stu_b.id, status="pending")
    db.add(sub_b)
    await db.flush()

    await db.commit()

    token_a = create_access_token({
        "sub": teacher_a.id, "role": "homeroom_teacher",
        "school_id": school_a.id,
    })
    token_b = create_access_token({
        "sub": teacher_b.id, "role": "homeroom_teacher",
        "school_id": school_b.id,
    })

    return {
        "school_a_id": school_a.id,
        "school_b_id": school_b.id,
        "teacher_a_id": teacher_a.id,
        "teacher_b_id": teacher_b.id,
        "task_a_id": task_a.id,
        "task_b_id": task_b.id,
        "sub_a_id": sub_a.id,
        "sub_b_id": sub_b.id,
        "stu_a_id": stu_a.id,
        "stu_b_id": stu_b.id,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
    }


# ── list_submissions isolation ──────────────────────────────


@pytest.mark.asyncio
async def test_list_submissions_own_school(client, two_schools):
    """Teacher A can list submissions for school A's task."""
    resp = await client.get(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/submissions",
        headers=two_schools["headers_a"],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_list_submissions_cross_school_blocked(client, two_schools):
    """Teacher B cannot list submissions for school A's task (404 at task level)."""
    resp = await client.get(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/submissions",
        headers=two_schools["headers_b"],
    )
    assert resp.status_code == 404


# ── submit isolation ────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_own_school(client, two_schools):
    """Teacher A can submit for school A's submission."""
    resp = await client.post(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/submissions/{two_schools['sub_a_id']}/submit",
        json={"content": "answer"},
        headers=two_schools["headers_a"],
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "submitted"


@pytest.mark.asyncio
async def test_submit_cross_school_blocked(client, two_schools):
    """Teacher B cannot submit for school A's submission (404)."""
    resp = await client.post(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/submissions/{two_schools['sub_a_id']}/submit",
        json={"content": "hack"},
        headers=two_schools["headers_b"],
    )
    assert resp.status_code == 404


# ── grade_single isolation ──────────────────────────────────


@pytest.mark.asyncio
async def test_grade_single_cross_school_blocked(client, two_schools):
    """Teacher B cannot grade school A's submission (404).

    First submit so the submission is in 'submitted' state, then try cross-school grade.
    """
    # Submit via school A teacher first
    await client.post(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/submissions/{two_schools['sub_a_id']}/submit",
        json={"content": "answer"},
        headers=two_schools["headers_a"],
    )
    # Cross-school grade attempt
    resp = await client.post(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/submissions/{two_schools['sub_a_id']}/grade",
        json={"score": 100},
        headers=two_schools["headers_b"],
    )
    assert resp.status_code == 404


# ── grade_batch isolation ───────────────────────────────────


@pytest.mark.asyncio
async def test_grade_batch_cross_school_returns_zero(client, two_schools):
    """Teacher B batch-grading school A's task grades 0 submissions (blocked at task level)."""
    # Submit via school A teacher
    await client.post(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/submissions/{two_schools['sub_a_id']}/submit",
        json={"content": "answer"},
        headers=two_schools["headers_a"],
    )
    # Cross-school batch grade -- router get_task check returns 404
    resp = await client.post(
        f"/api/v1/homework/tasks/{two_schools['task_a_id']}/grade-batch",
        json={"grades": [{"student_id": two_schools["stu_a_id"], "score": 100}]},
        headers=two_schools["headers_b"],
    )
    assert resp.status_code == 404
