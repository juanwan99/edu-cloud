"""年级聚合分析 + 考情趋势 API 测试（WP-D TDD-lite）。"""
import pytest
from datetime import datetime

from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.grade import Grade
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from tests.conftest import *  # noqa


@pytest.fixture
async def grade_analytics_data(db, seed_school):
    """Seed school with 1 grade, 2 classes, 4 students, 2 exams, scores for grade analytics."""
    school, _ = seed_school

    # Grade
    grade = Grade(school_id=school.id, name="高一", grade_level=10, xueduan="高中", sort_order=1)
    db.add(grade)
    await db.flush()

    # Classes linked to grade
    cls_a = Class(name="高一(1)班", grade="高一", grade_number=10, grade_id=grade.id, school_id=school.id)
    cls_b = Class(name="高一(2)班", grade="高一", grade_number=10, grade_id=grade.id, school_id=school.id)
    db.add_all([cls_a, cls_b])
    await db.flush()

    # Students: 2 per class
    stu_a1 = Student(name="甲一", student_number="GA01", class_id=cls_a.id, school_id=school.id, grade="高一")
    stu_a2 = Student(name="甲二", student_number="GA02", class_id=cls_a.id, school_id=school.id, grade="高一")
    stu_b1 = Student(name="乙一", student_number="GB01", class_id=cls_b.id, school_id=school.id, grade="高一")
    stu_b2 = Student(name="乙二", student_number="GB02", class_id=cls_b.id, school_id=school.id, grade="高一")
    db.add_all([stu_a1, stu_a2, stu_b1, stu_b2])
    await db.flush()

    # Exam 1 (older)
    exam1 = Exam(
        name="高一期中考试", status="completed", school_id=school.id,
        exam_date=datetime(2026, 3, 15),
    )
    db.add(exam1)
    await db.flush()
    subj1_math = Subject(name="数学", code="math", exam_id=exam1.id, school_id=school.id)
    subj1_eng = Subject(name="英语", code="english", exam_id=exam1.id, school_id=school.id)
    db.add_all([subj1_math, subj1_eng])
    await db.flush()

    # Questions for exam1
    q1_math = Question(name="1", question_type="essay", max_score=100, subject_id=subj1_math.id, school_id=school.id)
    q1_eng = Question(name="1", question_type="essay", max_score=100, subject_id=subj1_eng.id, school_id=school.id)
    db.add_all([q1_math, q1_eng])
    await db.flush()

    # Scores for exam1 — math: A1=90, A2=80, B1=70, B2=60 ; eng: A1=85, A2=75, B1=65, B2=55
    scores_exam1 = [
        (stu_a1, subj1_math, q1_math, 90), (stu_a2, subj1_math, q1_math, 80),
        (stu_b1, subj1_math, q1_math, 70), (stu_b2, subj1_math, q1_math, 60),
        (stu_a1, subj1_eng, q1_eng, 85), (stu_a2, subj1_eng, q1_eng, 75),
        (stu_b1, subj1_eng, q1_eng, 65), (stu_b2, subj1_eng, q1_eng, 55),
    ]
    for stu, subj, q, score in scores_exam1:
        sa = StudentAnswer(exam_id=exam1.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
        db.add(sa)
        await db.flush()
        gr = GradingResult(
            answer_id=sa.id, question_id=q.id, school_id=school.id,
            final_score=float(score), max_score=q.max_score, status="confirmed", source="teacher",
        )
        db.add(gr)

    # Exam 2 (newer)
    exam2 = Exam(
        name="高一月考", status="completed", school_id=school.id,
        exam_date=datetime(2026, 4, 15),
    )
    db.add(exam2)
    await db.flush()
    subj2_math = Subject(name="数学", code="math", exam_id=exam2.id, school_id=school.id)
    subj2_eng = Subject(name="英语", code="english", exam_id=exam2.id, school_id=school.id)
    db.add_all([subj2_math, subj2_eng])
    await db.flush()

    q2_math = Question(name="1", question_type="essay", max_score=100, subject_id=subj2_math.id, school_id=school.id)
    q2_eng = Question(name="1", question_type="essay", max_score=100, subject_id=subj2_eng.id, school_id=school.id)
    db.add_all([q2_math, q2_eng])
    await db.flush()

    # Scores for exam2 — math: A1=95, A2=85, B1=75, B2=65 ; eng: A1=90, A2=80, B1=70, B2=60
    scores_exam2 = [
        (stu_a1, subj2_math, q2_math, 95), (stu_a2, subj2_math, q2_math, 85),
        (stu_b1, subj2_math, q2_math, 75), (stu_b2, subj2_math, q2_math, 65),
        (stu_a1, subj2_eng, q2_eng, 90), (stu_a2, subj2_eng, q2_eng, 80),
        (stu_b1, subj2_eng, q2_eng, 70), (stu_b2, subj2_eng, q2_eng, 60),
    ]
    for stu, subj, q, score in scores_exam2:
        sa = StudentAnswer(exam_id=exam2.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
        db.add(sa)
        await db.flush()
        gr = GradingResult(
            answer_id=sa.id, question_id=q.id, school_id=school.id,
            final_score=float(score), max_score=q.max_score, status="confirmed", source="teacher",
        )
        db.add(gr)

    await db.commit()

    return {
        "school": school,
        "grade": grade,
        "classes": [cls_a, cls_b],
        "students": [stu_a1, stu_a2, stu_b1, stu_b2],
        "exams": [exam1, exam2],
        "subjects_exam1": [subj1_math, subj1_eng],
        "subjects_exam2": [subj2_math, subj2_eng],
    }


@pytest.fixture
async def principal_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="grade_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


# ── Test: Grade Overview ────────────────────────────────────────

@pytest.mark.asyncio
async def test_grade_overview_returns_class_breakdown(client, principal_headers, grade_analytics_data):
    """overview 返回该年级各班级的均分/及格率/优秀率/最高分/最低分/中位数。"""
    data = grade_analytics_data
    grade = data["grade"]
    exam = data["exams"][1]  # 月考 (newer)

    resp = await client.get(
        f"/api/v1/analytics/grade/{grade.id}/overview",
        params={"exam_id": exam.id},
        headers=principal_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["grade_name"] == "高一"
    assert body["exam_name"] == "高一月考"
    assert "classes" in body
    assert len(body["classes"]) == 2

    # Class A: math 95+85=180, eng 90+80=170 → totals 185, 165 → avg=175, max=185, min=165
    # Class B: math 75+65=140, eng 70+60=130 → totals 145, 125 → avg=135, max=145, min=125
    classes_by_name = {c["class_name"]: c for c in body["classes"]}
    cls_a = classes_by_name["高一(1)班"]
    assert cls_a["avg_score"] == 175.0
    assert cls_a["max_score"] == 185.0
    assert cls_a["min_score"] == 165.0

    cls_b = classes_by_name["高一(2)班"]
    assert cls_b["avg_score"] == 135.0
    assert cls_b["max_score"] == 145.0
    assert cls_b["min_score"] == 125.0


@pytest.mark.asyncio
async def test_grade_overview_requires_exam_id(client, principal_headers, grade_analytics_data):
    """overview without exam_id returns 422."""
    grade = grade_analytics_data["grade"]
    resp = await client.get(
        f"/api/v1/analytics/grade/{grade.id}/overview",
        headers=principal_headers,
    )
    assert resp.status_code == 422


# ── Test: Grade Exam Trend ──────────────────────────────────────

@pytest.mark.asyncio
async def test_grade_trend_returns_time_series(client, principal_headers, grade_analytics_data):
    """trend 返回该年级最近 N 次考试的时间序列数据。"""
    data = grade_analytics_data
    grade = data["grade"]

    resp = await client.get(
        f"/api/v1/analytics/grade/{grade.id}/trend",
        params={"limit": 10},
        headers=principal_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "points" in body
    assert len(body["points"]) == 2  # 2 exams

    # Points should be chronological (期中 first, then 月考)
    assert body["points"][0]["exam_name"] == "高一期中考试"
    assert body["points"][1]["exam_name"] == "高一月考"

    # Exam 1 overall: totals = 175, 155, 135, 115 → avg = 145
    # Exam 2 overall: totals = 185, 165, 145, 125 → avg = 155
    p1 = body["points"][0]
    assert p1["avg_score"] == 145.0
    assert p1["student_count"] == 4

    p2 = body["points"][1]
    assert p2["avg_score"] == 155.0
    assert p2["student_count"] == 4


# ── Test: Grade Subject Comparison ──────────────────────────────

@pytest.mark.asyncio
async def test_grade_subjects_returns_comparison(client, principal_headers, grade_analytics_data):
    """subjects 返回该年级某次考试各科的对比数据。"""
    data = grade_analytics_data
    grade = data["grade"]
    exam = data["exams"][1]  # 月考

    resp = await client.get(
        f"/api/v1/analytics/grade/{grade.id}/subjects",
        params={"exam_id": exam.id},
        headers=principal_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "subjects" in body
    assert len(body["subjects"]) == 2

    subj_by_code = {s["subject_code"]: s for s in body["subjects"]}
    # Math: 95+85+75+65=320 / 4 = 80, max_possible=100, score_rate=0.8
    math = subj_by_code["math"]
    assert math["avg_score"] == 80.0
    assert math["max_possible"] == 100.0
    assert math["score_rate"] == 0.8

    # English: 90+80+70+60=300 / 4 = 75, score_rate=0.75
    eng = subj_by_code["english"]
    assert eng["avg_score"] == 75.0
    assert eng["score_rate"] == 0.75


@pytest.mark.asyncio
async def test_grade_subjects_requires_exam_id(client, principal_headers, grade_analytics_data):
    """subjects without exam_id returns 422."""
    grade = grade_analytics_data["grade"]
    resp = await client.get(
        f"/api/v1/analytics/grade/{grade.id}/subjects",
        headers=principal_headers,
    )
    assert resp.status_code == 422
