# tests/test_api/test_analytics_level_score.py
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from tests.conftest import *  # noqa

from edu_cloud.modules.exam.models import Exam, Subject, ExamResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.exam.models import Question
from datetime import datetime


@pytest.fixture
async def school_admin_headers(db, seed_school):
    """principal role bound to test school for school-scoped endpoint tests."""
    school, _ = seed_school
    user = User(username="school_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id, role="principal",
        school_id=school.id, is_primary=True,
    ))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_level_score_data(db, seed_school):
    """10 students, scores from 100 to 91."""
    school, _ = seed_school
    school_id = school.id
    cls = Class(name="高一(1)班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()

    exam = Exam(name="期末考试", status="completed", school_id=school_id,
                exam_date=datetime(2026, 6, 20))
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="物理", code="physics", school_id=school_id)
    db.add(subj)
    await db.flush()

    students = []
    for i in range(10):
        stu = Student(name=f"学生{i}", student_number=f"L{i:03d}",
                      class_id=cls.id, grade="高一", school_id=school_id)
        db.add(stu)
        students.append(stu)
    await db.flush()

    for i, stu in enumerate(students):
        db.add(ExamResult(
            exam_id=exam.id, student_id=stu.id,
            school_id=school_id, total_score=100 - i,
        ))
    await db.flush()

    # LevelScoreService reads from StudentAnswer (per-subject scores), not ExamResult.total_score
    question = Question(
        subject_id=subj.id, school_id=school_id,
        name="T1", question_type="objective", max_score=100,
    )
    db.add(question)
    await db.flush()

    for i, stu in enumerate(students):
        db.add(StudentAnswer(
            exam_id=exam.id, student_id=stu.id, subject_id=subj.id,
            question_id=question.id, school_id=school_id,
            score=100 - i,
        ))
    await db.commit()
    return {"exam": exam, "subj": subj, "cls": cls, "students": students}


DEFAULT_LEVELS = [
    {"level": "A", "start_pct": 0, "end_pct": 20, "score_min": 86, "score_max": 100},
    {"level": "B", "start_pct": 20, "end_pct": 50, "score_min": 71, "score_max": 85},
    {"level": "C", "start_pct": 50, "end_pct": 80, "score_min": 56, "score_max": 70},
    {"level": "D", "start_pct": 80, "end_pct": 100, "score_min": 41, "score_max": 55},
]


@pytest.mark.asyncio
async def test_level_score_basic(client, school_admin_headers, seed_school, db):
    """10 students, 4 levels: verify division and assigned scores."""
    data = await _seed_level_score_data(db, seed_school)

    resp = await client.post(
        "/api/v1/analytics/level-score/convert",
        json={
            "exam_id": data["exam"].id,
            "subject_id": data["subj"].id,
            "class_id": None,
            "levels": DEFAULT_LEVELS,
        },
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["total_students"] == 10
    assert len(result["level_stats"]) == 4
    assert len(result["students"]) == 10

    # ORC-005: sorted by raw_score descending
    scores = [s["raw_score"] for s in result["students"]]
    assert scores == sorted(scores, reverse=True)

    # A level should contain top 20% = 2 students
    a_stat = next(s for s in result["level_stats"] if s["level"] == "A")
    assert a_stat["count"] == 2


@pytest.mark.asyncio
async def test_level_score_empty(client, school_admin_headers, seed_school):
    """Non-existent exam returns 404."""
    resp = await client.post(
        "/api/v1/analytics/level-score/convert",
        json={
            "exam_id": "nonexistent",
            "subject_id": "nonexistent",
            "levels": DEFAULT_LEVELS,
        },
        headers=school_admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_level_score_tied_scores(client, school_admin_headers, seed_school, db):
    """ORC-005: students with same score must be in the same level."""
    school, _ = seed_school
    school_id = school.id
    cls = Class(name="高一(1)班", grade="高一", school_id=school_id)
    db.add(cls)
    await db.flush()

    exam = Exam(name="并列分测试", status="completed", school_id=school_id,
                exam_date=datetime(2026, 6, 20))
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="math", school_id=school_id)
    db.add(subj)
    await db.flush()

    question = Question(
        subject_id=subj.id, school_id=school_id,
        name="T1", question_type="objective", max_score=100,
    )
    db.add(question)
    await db.flush()

    # 5 students, scores 100, 95, 95, 80, 70
    raw_scores = [100, 95, 95, 80, 70]
    students = []
    for i, sc in enumerate(raw_scores):
        stu = Student(name=f"并列{i}", student_number=f"T{i:03d}",
                      class_id=cls.id, grade="高一", school_id=school_id)
        db.add(stu)
        students.append((stu, sc))
    await db.flush()

    for stu, sc in students:
        db.add(ExamResult(exam_id=exam.id, student_id=stu.id,
                          school_id=school_id, total_score=sc))
        db.add(StudentAnswer(exam_id=exam.id, student_id=stu.id,
                             subject_id=subj.id, question_id=question.id,
                             school_id=school_id, score=sc))
    await db.commit()

    # Top 40% = A (2 students), 2nd/3rd same score 95 should be same level
    levels = [
        {"level": "A", "start_pct": 0, "end_pct": 40, "score_min": 86, "score_max": 100},
        {"level": "B", "start_pct": 40, "end_pct": 100, "score_min": 41, "score_max": 85},
    ]
    resp = await client.post(
        "/api/v1/analytics/level-score/convert",
        json={"exam_id": exam.id, "subject_id": subj.id, "levels": levels},
        headers=school_admin_headers,
    )
    result = resp.json()
    tied = [s for s in result["students"] if s["raw_score"] == 95]
    assert len(tied) == 2
    assert tied[0]["level"] == tied[1]["level"], "ORC-005: tied students must be in same level"
