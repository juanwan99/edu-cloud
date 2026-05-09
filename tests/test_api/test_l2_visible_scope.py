"""L2 visible_subject_codes / visible_class_ids scope isolation tests.

Verifies that subject_teacher with restricted scope cannot see data
outside their assigned subjects/classes, while admin (unrestricted) can.
"""
import pytest
from sqlalchemy import select

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.student.models import Student, Class
from edu_cloud.modules.grading.models import GradingTask
from edu_cloud.modules.bank.models import BankQuestion
from edu_cloud.modules.profile.models import StudentExamSnapshot, StudentErrorPattern
from edu_cloud.shared.auth import create_access_token


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def l2_school(db):
    school = School(name="L2测试校", code="L2TEST", district="测试区", api_key_hash="x")
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@pytest.fixture
async def l2_classes(db, l2_school):
    c1 = Class(name="高一1班", grade="高一", school_id=l2_school.id)
    c2 = Class(name="高一2班", grade="高一", school_id=l2_school.id)
    db.add_all([c1, c2])
    await db.commit()
    await db.refresh(c1)
    await db.refresh(c2)
    return c1, c2


@pytest.fixture
async def l2_students(db, l2_school, l2_classes):
    c1, c2 = l2_classes
    s1 = Student(name="张三", student_number="S001", class_id=c1.id, school_id=l2_school.id)
    s2 = Student(name="李四", student_number="S002", class_id=c2.id, school_id=l2_school.id)
    db.add_all([s1, s2])
    await db.commit()
    await db.refresh(s1)
    await db.refresh(s2)
    return s1, s2


@pytest.fixture
async def l2_exam_subjects(db, l2_school):
    exam = Exam(name="期中考试", school_id=l2_school.id)
    db.add(exam)
    await db.commit()
    await db.refresh(exam)
    subj_math = Subject(exam_id=exam.id, name="数学", code="SX", school_id=l2_school.id)
    subj_eng = Subject(exam_id=exam.id, name="英语", code="YY", school_id=l2_school.id)
    db.add_all([subj_math, subj_eng])
    await db.commit()
    await db.refresh(subj_math)
    await db.refresh(subj_eng)
    return exam, subj_math, subj_eng


@pytest.fixture
async def l2_questions(db, l2_school, l2_exam_subjects):
    _, subj_math, subj_eng = l2_exam_subjects
    q_math = Question(
        subject_id=subj_math.id, name="Q1", question_type="essay",
        max_score=10, school_id=l2_school.id,
    )
    q_eng = Question(
        subject_id=subj_eng.id, name="Q2", question_type="essay",
        max_score=10, school_id=l2_school.id,
    )
    db.add_all([q_math, q_eng])
    await db.commit()
    await db.refresh(q_math)
    await db.refresh(q_eng)
    return q_math, q_eng


@pytest.fixture
async def l2_grading_tasks(db, l2_school, l2_exam_subjects, l2_admin_user):
    _, subj_math, subj_eng = l2_exam_subjects
    t_math = GradingTask(
        subject_id=subj_math.id, school_id=l2_school.id,
        status="completed", total=10, completed=10, failed=0,
        created_by=l2_admin_user.id,
    )
    t_eng = GradingTask(
        subject_id=subj_eng.id, school_id=l2_school.id,
        status="completed", total=5, completed=5, failed=0,
        created_by=l2_admin_user.id,
    )
    db.add_all([t_math, t_eng])
    await db.commit()
    await db.refresh(t_math)
    await db.refresh(t_eng)
    return t_math, t_eng


@pytest.fixture
async def l2_bank_questions(db, l2_school, l2_questions):
    q_math, q_eng = l2_questions
    bq_math = BankQuestion(
        question_type="essay", max_score=10,
        source_question_id=q_math.id, school_id=l2_school.id,
    )
    bq_eng = BankQuestion(
        question_type="essay", max_score=10,
        source_question_id=q_eng.id, school_id=l2_school.id,
    )
    db.add_all([bq_math, bq_eng])
    await db.commit()
    await db.refresh(bq_math)
    await db.refresh(bq_eng)
    return bq_math, bq_eng


@pytest.fixture
async def l2_admin_user(db, l2_school):
    user = User(username="l2_admin", display_name="L2 Admin")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    role = UserRole(
        user_id=user.id, role="academic_director",
        school_id=l2_school.id, is_primary=True,
    )
    db.add(role)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def l2_admin_headers(client, l2_admin_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "l2_admin", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def l2_teacher_user(db, l2_school, l2_classes):
    """subject_teacher restricted to SX (math) and class 1 only."""
    c1, _ = l2_classes
    user = User(username="l2_teacher", display_name="L2 Teacher")
    user.set_password("123456")
    db.add(user)
    await db.flush()
    role = UserRole(
        user_id=user.id, role="subject_teacher",
        school_id=l2_school.id, is_primary=True,
        subject_codes=["SX"],
        class_ids=[c1.id],
    )
    db.add(role)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def l2_teacher_headers(client, l2_teacher_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "l2_teacher", "password": "123456"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Grading: GET /tasks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grading_tasks_admin_sees_all(
    client, l2_admin_headers, l2_grading_tasks,
):
    """Admin (academic_director) sees tasks for all subjects."""
    resp = await client.get("/api/v1/grading/tasks", headers=l2_admin_headers)
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    t_math, t_eng = l2_grading_tasks
    assert t_math.id in ids
    assert t_eng.id in ids


@pytest.mark.asyncio
async def test_grading_tasks_teacher_filtered(
    client, l2_teacher_headers, l2_grading_tasks,
):
    """subject_teacher with subject_codes=['SX'] only sees math tasks."""
    resp = await client.get("/api/v1/grading/tasks", headers=l2_teacher_headers)
    assert resp.status_code == 200
    ids = {t["id"] for t in resp.json()}
    t_math, t_eng = l2_grading_tasks
    assert t_math.id in ids
    assert t_eng.id not in ids


# ---------------------------------------------------------------------------
# Grading: GET /tasks/{task_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grading_task_detail_allowed(
    client, l2_teacher_headers, l2_grading_tasks,
):
    """Teacher can access task for their subject."""
    t_math, _ = l2_grading_tasks
    resp = await client.get(f"/api/v1/grading/tasks/{t_math.id}", headers=l2_teacher_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_grading_task_detail_blocked(
    client, l2_teacher_headers, l2_grading_tasks,
):
    """Teacher cannot access task for another subject."""
    _, t_eng = l2_grading_tasks
    resp = await client.get(f"/api/v1/grading/tasks/{t_eng.id}", headers=l2_teacher_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Bank: question endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bank_questions_admin_sees_all(
    client, l2_admin_headers, l2_bank_questions,
):
    """Admin sees all bank questions."""
    resp = await client.get("/api/v1/bank/questions", headers=l2_admin_headers)
    assert resp.status_code == 200
    ids = {q["id"] for q in resp.json()}
    bq_math, bq_eng = l2_bank_questions
    assert bq_math.id in ids
    assert bq_eng.id in ids


@pytest.mark.asyncio
async def test_bank_questions_teacher_filtered(
    client, l2_teacher_headers, l2_bank_questions,
):
    """Teacher with subject_codes=['SX'] only sees math bank questions."""
    resp = await client.get("/api/v1/bank/questions", headers=l2_teacher_headers)
    assert resp.status_code == 200
    ids = {q["id"] for q in resp.json()}
    bq_math, bq_eng = l2_bank_questions
    assert bq_math.id in ids
    assert bq_eng.id not in ids


@pytest.mark.asyncio
async def test_bank_question_detail_blocked(
    client, l2_teacher_headers, l2_bank_questions,
):
    """Teacher cannot get detail for bank question outside their subjects."""
    _, bq_eng = l2_bank_questions
    resp = await client.get(f"/api/v1/bank/questions/{bq_eng.id}", headers=l2_teacher_headers)
    assert resp.status_code == 404  # NotFoundError from service


# ---------------------------------------------------------------------------
# Bank: error-book endpoints (class_id check)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_book_own_class_allowed(
    client, l2_teacher_headers, l2_students,
):
    """Teacher can access error-book for student in their class."""
    s1, _ = l2_students  # s1 is in class 1 (teacher's class)
    resp = await client.get(
        f"/api/v1/bank/error-book/{s1.id}", headers=l2_teacher_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_error_book_other_class_blocked(
    client, l2_teacher_headers, l2_students,
):
    """Teacher cannot access error-book for student in another class."""
    _, s2 = l2_students  # s2 is in class 2 (not teacher's class)
    resp = await client.get(
        f"/api/v1/bank/error-book/{s2.id}", headers=l2_teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_error_book_stats_other_class_blocked(
    client, l2_teacher_headers, l2_students,
):
    """Teacher cannot access error-book/stats for student in another class."""
    _, s2 = l2_students
    resp = await client.get(
        f"/api/v1/bank/error-book/{s2.id}/stats", headers=l2_teacher_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Profile: subject_code parameter validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_profile_trend_allowed_subject(
    client, l2_teacher_headers, l2_students,
):
    """Teacher can query trend for their own subject."""
    s1, _ = l2_students
    resp = await client.get(
        f"/api/v1/profile/students/{s1.id}/trend?subject_code=SX",
        headers=l2_teacher_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_profile_trend_blocked_subject(
    client, l2_teacher_headers, l2_students,
):
    """Teacher cannot query trend for a subject outside their scope."""
    s1, _ = l2_students
    resp = await client.get(
        f"/api/v1/profile/students/{s1.id}/trend?subject_code=YY",
        headers=l2_teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_profile_error_patterns_blocked_subject(
    client, l2_teacher_headers, l2_students,
):
    """Teacher cannot query error-patterns for another subject."""
    s1, _ = l2_students
    resp = await client.get(
        f"/api/v1/profile/students/{s1.id}/error-patterns?subject_code=YY",
        headers=l2_teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_profile_knowledge_blocked_course(
    client, l2_teacher_headers, l2_students,
):
    """Teacher cannot query knowledge map for another course_code."""
    s1, _ = l2_students
    resp = await client.get(
        f"/api/v1/profile/students/{s1.id}/knowledge?course_code=YY",
        headers=l2_teacher_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Profile: class/weakness class_id validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_class_weakness_own_class_allowed(
    client, l2_teacher_headers, l2_classes,
):
    """Teacher can query weakness for their class."""
    c1, _ = l2_classes
    resp = await client.get(
        f"/api/v1/profile/class/weakness?class_id={c1.id}",
        headers=l2_teacher_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_class_weakness_other_class_blocked(
    client, l2_teacher_headers, l2_classes,
):
    """Teacher cannot query weakness for another class."""
    _, c2 = l2_classes
    resp = await client.get(
        f"/api/v1/profile/class/weakness?class_id={c2.id}",
        headers=l2_teacher_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin bypasses all L2 checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_bypasses_all_l2(
    client, l2_admin_headers, l2_students, l2_classes,
):
    """Admin can access any student/class without L2 restriction."""
    _, s2 = l2_students
    _, c2 = l2_classes

    # error-book for any student
    resp = await client.get(
        f"/api/v1/bank/error-book/{s2.id}", headers=l2_admin_headers,
    )
    assert resp.status_code == 200

    # class weakness for any class
    resp = await client.get(
        f"/api/v1/profile/class/weakness?class_id={c2.id}",
        headers=l2_admin_headers,
    )
    assert resp.status_code == 200

    # profile trend with any subject_code
    resp = await client.get(
        f"/api/v1/profile/students/{s2.id}/trend?subject_code=YY",
        headers=l2_admin_headers,
    )
    assert resp.status_code == 200
