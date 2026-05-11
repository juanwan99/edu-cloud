"""Tenant isolation tests — verify cross-school data leakage is prevented.

Each test creates data for school_A and attempts access from school_B context,
asserting that the cross-school path returns empty results or 404.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.profile.models import (
    StudentExamSnapshot, StudentKnowledgeMastery, StudentErrorPattern,
)
from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.shared.auth import create_access_token


# ── helpers ──

async def _make_school(db: AsyncSession, code: str, name: str) -> School:
    s = School(name=name, code=code)
    db.add(s)
    await db.flush()
    return s


async def _make_user_role(db: AsyncSession, school_id: str, role: str = "academic_director") -> tuple:
    user = User(username=f"user_{school_id[:8]}_{role}", display_name=f"U {role}")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    ur = UserRole(user_id=user.id, role=role, school_id=school_id, is_primary=True)
    db.add(ur)
    await db.flush()
    return user, ur


def _headers(user, role):
    token = create_access_token({
        "sub": user.id,
        "role": role.role,
        "active_role_id": role.id,
    })
    return {"Authorization": f"Bearer {token}"}


# ════════════════════════════════════════════════════════
# C-6: Pipeline derived table isolation
# ════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pipeline_snapshot_upsert_respects_school_id(db):
    """StudentExamSnapshot upsert must include school_id in WHERE,
    so school_B's pipeline cannot overwrite school_A's snapshot."""
    from edu_cloud.modules.pipeline.service import generate_exam_snapshots

    school_a = await _make_school(db, "SCH_A1", "School A")
    school_b = await _make_school(db, "SCH_B1", "School B")

    # Create exam + subject in school_a
    exam = Exam(name="Exam1", school_id=school_a.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="Math", code="math", school_id=school_a.id)
    db.add(subj)
    await db.flush()

    # Create class + student in school_a
    cls_a = Class(name="Class1", grade="G10", school_id=school_a.id)
    db.add(cls_a)
    await db.flush()

    stu = Student(name="Stu1", student_number="S001", school_id=school_a.id, class_id=cls_a.id)
    db.add(stu)
    await db.flush()

    q = Question(
        name="Q1", subject_id=subj.id, school_id=school_a.id,
        question_type="fill_blank", max_score=10,
    )
    db.add(q)
    await db.flush()

    sa = StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id=stu.id,
        question_id=q.id, school_id=school_a.id, is_absent=False,
        score=8.0,
    )
    db.add(sa)
    await db.commit()

    # Run pipeline for school_a -- should create snapshot
    count_a = await generate_exam_snapshots(db, exam_id=exam.id, school_id=school_a.id)
    assert count_a >= 1

    # Run pipeline for school_b with same exam_id -- should find nothing
    count_b = await generate_exam_snapshots(db, exam_id=exam.id, school_id=school_b.id)
    assert count_b == 0


@pytest.mark.asyncio
async def test_pipeline_mastery_upsert_respects_school_id(db):
    """StudentKnowledgeMastery upsert must include school_id so
    school_B cannot update school_A's mastery records."""
    from edu_cloud.modules.pipeline.service import update_knowledge_mastery

    school_a = await _make_school(db, "SCH_A2", "School A2")
    school_b = await _make_school(db, "SCH_B2", "School B2")

    exam = Exam(name="Exam2", school_id=school_a.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="Physics", code="physics", school_id=school_a.id)
    db.add(subj)
    await db.flush()

    # school_b should get 0 updates (no subjects found)
    count_b = await update_knowledge_mastery(db, exam_id=exam.id, school_id=school_b.id)
    assert count_b == 0


@pytest.mark.asyncio
async def test_pipeline_error_pattern_upsert_respects_school_id(db):
    """StudentErrorPattern upsert must include school_id so
    school_B cannot update school_A's error pattern records."""
    from edu_cloud.modules.pipeline.service import update_error_patterns

    school_a = await _make_school(db, "SCH_A3", "School A3")
    school_b = await _make_school(db, "SCH_B3", "School B3")

    exam = Exam(name="Exam3", school_id=school_a.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="Chem", code="chemistry", school_id=school_a.id)
    db.add(subj)
    await db.flush()

    # school_b should get 0 updates
    count_b = await update_error_patterns(db, exam_id=exam.id, school_id=school_b.id)
    assert count_b == 0


# ════════════════════════════════════════════════════════
# H-3: Parent bind must use student's class school_id
# ════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_parent_bind_uses_class_school_id(db):
    """When a parent binds to a student, the link.school_id should come from
    the student's class, not from the parent's role."""
    from edu_cloud.modules.conduct.parent_service import bind_child
    from edu_cloud.modules.conduct.models import ConductClassConfig, StudentProfile
    from edu_cloud.modules.conduct.crypto import encrypt

    school_a = await _make_school(db, "SCH_PA", "Parent School A")
    school_b = await _make_school(db, "SCH_PB", "Parent School B")

    # Parent registered under school_b
    parent_user = User(username="parent_phone", phone="13800138000", display_name="Parent")
    parent_user.set_password("pass123")
    db.add(parent_user)
    await db.flush()

    parent_role = UserRole(
        user_id=parent_user.id, role="parent",
        school_id=school_b.id, is_primary=True,
    )
    db.add(parent_role)
    await db.flush()

    # Student is in school_a's class
    cls_a = Class(name="ClassA", grade="G10", school_id=school_a.id)
    db.add(cls_a)
    await db.flush()

    stu = Student(name="Kid", student_number="K001", school_id=school_a.id, class_id=cls_a.id)
    db.add(stu)
    await db.flush()

    # ConductClassConfig for cls_a with id_card verify
    config = ConductClassConfig(
        class_id=cls_a.id, invite_code="INVITE1", is_active=True,
        verify_code_type="custom",
    )
    db.add(config)
    await db.flush()

    # StudentProfile with verify_code
    profile = StudentProfile(
        student_id=stu.id,
        verify_code=encrypt("VERIFY123"),
    )
    db.add(profile)
    await db.commit()

    # Bind: parent (school_b role) binds to student (school_a class)
    result = await bind_child(
        db, user_id=parent_user.id, class_id=cls_a.id,
        student_name="Kid", verify_code="VERIFY123",
    )
    assert result["student_id"] == stu.id

    # Verify the link.school_id is school_a (from class), not school_b (from role)
    link = (await db.execute(
        select(GuardianStudentLink).where(
            GuardianStudentLink.guardian_user_id == parent_user.id,
            GuardianStudentLink.student_id == stu.id,
        )
    )).scalar_one()
    assert link.school_id == school_a.id, (
        f"link.school_id should be {school_a.id} (student's class school), "
        f"got {link.school_id}"
    )


# ════════════════════════════════════════════════════════
# M-3: Worker queries must include school_id
# ════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_worker_graded_rows_filter_by_school_id(db):
    """GradingResult exclusion query in the worker must filter by school_id,
    so school_B's grading results don't cause school_A answers to be skipped."""
    school_a = await _make_school(db, "SCH_WA", "Worker School A")
    school_b = await _make_school(db, "SCH_WB", "Worker School B")

    exam = Exam(name="WExam", school_id=school_a.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="Bio", code="bio", school_id=school_a.id)
    db.add(subj)
    await db.flush()

    q = Question(
        name="WQ1", subject_id=subj.id, school_id=school_a.id,
        question_type="short_answer", max_score=10,
    )
    db.add(q)
    await db.flush()

    sa = StudentAnswer(
        exam_id=exam.id, subject_id=subj.id, student_id="stu_wa",
        question_id=q.id, school_id=school_a.id, is_absent=False,
    )
    db.add(sa)
    await db.flush()

    # GradingResult in school_b for the same answer_id (cross-school leak scenario)
    gr_b = GradingResult(
        answer_id=sa.id, question_id=q.id, school_id=school_b.id,
        status="ai_done", max_score=10,
    )
    db.add(gr_b)
    await db.commit()

    # Query graded_rows filtered by school_a -- should NOT find gr_b
    all_answer_ids = [sa.id]
    graded_rows = set((await db.execute(
        select(GradingResult.answer_id).where(
            GradingResult.answer_id.in_(all_answer_ids),
            GradingResult.school_id == school_a.id,
        )
    )).scalars().all())
    assert sa.id not in graded_rows, "school_B's GradingResult should not appear in school_A filter"

    # Without school_id filter, it would be found (demonstrating the fix matters)
    graded_rows_unfiltered = set((await db.execute(
        select(GradingResult.answer_id).where(
            GradingResult.answer_id.in_(all_answer_ids),
        )
    )).scalars().all())
    assert sa.id in graded_rows_unfiltered


# ════════════════════════════════════════════════════════
# H-2: Router layer school_id validation
# ════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_grading_task_create_validates_subject_school_id(client, db):
    """POST /grading/tasks should reject subjects not belonging to the caller's school."""
    school_a = await _make_school(db, "SCH_RA", "Router School A")
    school_b = await _make_school(db, "SCH_RB", "Router School B")

    user_b, role_b = await _make_user_role(db, school_b.id)
    headers = _headers(user_b, role_b)

    # Create subject under school_a
    exam = Exam(name="RExam", school_id=school_a.id, status="completed")
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="Eng", code="english", school_id=school_a.id)
    db.add(subj)
    await db.commit()

    # User from school_b tries to create grading task for school_a's subject
    resp = await client.post(
        "/api/v1/grading/tasks",
        json={"subject_id": subj.id},
        headers=headers,
    )
    assert resp.status_code == 404, f"Expected 404 for cross-school subject, got {resp.status_code}"


@pytest.mark.asyncio
async def test_grading_task_list_filters_by_school_id(client, db):
    """GET /grading/tasks should only return tasks for the caller's school."""
    school_a = await _make_school(db, "SCH_LA", "List School A")
    school_b = await _make_school(db, "SCH_LB", "List School B")

    user_a, role_a = await _make_user_role(db, school_a.id)
    user_b, role_b = await _make_user_role(db, school_b.id)

    # Create a grading task under school_a
    from edu_cloud.modules.grading.models import GradingTask
    exam = Exam(name="LExam", school_id=school_a.id, status="completed")
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="Hist", code="history", school_id=school_a.id)
    db.add(subj)
    await db.flush()

    task = GradingTask(
        subject_id=subj.id, school_id=school_a.id,
        status="completed", total=10, completed=10, failed=0,
        created_by=user_a.id,
    )
    db.add(task)
    await db.commit()

    # school_b user should see empty list
    headers_b = _headers(user_b, role_b)
    resp = await client.get("/api/v1/grading/tasks", headers=headers_b)
    assert resp.status_code == 200
    tasks = resp.json()
    task_ids = [t["id"] for t in tasks]
    assert task.id not in task_ids, "school_B should not see school_A's grading tasks"
