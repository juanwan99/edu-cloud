import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from tests.conftest import *  # noqa


@pytest.fixture
async def school_admin_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="insight_principal", display_name="校长")
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


async def _seed_graded_exam(db, seed_school):
    """Seed a completed exam with AI grading results."""
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()

    stu1 = Student(name="张三", student_number="S001", class_id=cls.id, school_id=school.id, grade="高一")
    stu2 = Student(name="李四", student_number="S002", class_id=cls.id, school_id=school.id, grade="高一")
    db.add_all([stu1, stu2])
    await db.flush()

    exam = Exam(name="期中考试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()

    subj = Subject(name="生物", code="biology", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()

    q1 = Question(name="1", question_type="choice", max_score=3.0, subject_id=subj.id, school_id=school.id)
    q2 = Question(name="15", question_type="essay", max_score=10.0, subject_id=subj.id, school_id=school.id)
    db.add_all([q1, q2])
    await db.flush()

    # 学生 1 答题
    sa1_q1 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu1.id, question_id=q1.id, score=3.0, school_id=school.id)
    sa1_q2 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu1.id, question_id=q2.id, school_id=school.id)
    # 学生 2 答题
    sa2_q1 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu2.id, question_id=q1.id, score=3.0, school_id=school.id)
    sa2_q2 = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu2.id, question_id=q2.id, school_id=school.id)
    db.add_all([sa1_q1, sa1_q2, sa2_q1, sa2_q2])
    await db.flush()

    # GradingResult for essay questions — with AI raw response
    gr1 = GradingResult(
        answer_id=sa1_q2.id, question_id=q2.id, school_id=school.id,
        ai_score=8.0, ai_confidence=0.9, final_score=8.0, max_score=10.0,
        status="confirmed", source="ai",
        ai_raw_response={"details": [{"subQuestion": "(1)", "blanks": [
            {"index": 1, "answer": "光合作用", "score": 4, "fullScore": 5, "correct": False,
             "reason": "概念混淆：将叶绿素误写为叶绿体"},
            {"index": 2, "answer": "正确答案", "score": 4, "fullScore": 5, "correct": True,
             "reason": "满足满分条件"},
        ]}]},
    )
    gr2 = GradingResult(
        answer_id=sa2_q2.id, question_id=q2.id, school_id=school.id,
        ai_score=3.0, ai_confidence=0.85, final_score=3.0, max_score=10.0,
        status="confirmed", source="ai",
        ai_raw_response={"details": [{"subQuestion": "(1)", "blanks": [
            {"index": 1, "answer": "错误答案", "score": 0, "fullScore": 5, "correct": False,
             "reason": "概念混淆：完全混淆光合作用与呼吸作用"},
            {"index": 2, "answer": "步骤不全", "score": 3, "fullScore": 5, "correct": False,
             "reason": "步骤不完整：缺少因果推导链"},
        ]}]},
    )
    # Choice questions — no AI raw response
    gr3 = GradingResult(
        answer_id=sa1_q1.id, question_id=q1.id, school_id=school.id,
        final_score=3.0, max_score=3.0, status="confirmed", source="manual",
    )
    gr4 = GradingResult(
        answer_id=sa2_q1.id, question_id=q1.id, school_id=school.id,
        final_score=3.0, max_score=3.0, status="confirmed", source="manual",
    )
    db.add_all([gr1, gr2, gr3, gr4])
    await db.commit()
    return exam, subj, [q1, q2], cls, [stu1, stu2]


@pytest.mark.asyncio
async def test_question_insights_empty(client, school_admin_headers, seed_school, db):
    school, _ = seed_school
    exam = Exam(name="空考试", status="completed", school_id=school.id)
    db.add(exam)
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/question-insights",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["questions"] == []


@pytest.mark.asyncio
async def test_question_insights_with_grading(client, school_admin_headers, seed_school, db):
    exam, subj, questions, _, _ = await _seed_graded_exam(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/question-insights",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["questions"]) == 2

    # 找 essay 题（题号 15）
    q15 = next(q for q in data["questions"] if q["name"] == "15")
    assert q15["graded_count"] == 2
    assert 0 < q15["score_rate"] < 1
    # 错因聚合应该有数据
    assert len(q15["error_causes"]) > 0
    # 概念混淆应该是最多的（2 个学生都有）
    top_cause = q15["error_causes"][0]
    assert top_cause["cause"] == "概念混淆"
    assert top_cause["count"] >= 2


@pytest.mark.asyncio
async def test_question_insights_subject_filter(client, school_admin_headers, seed_school, db):
    exam, subj, _, _, _ = await _seed_graded_exam(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/question-insights",
        params={"subject_id": subj.id},
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["questions"]) == 2


@pytest.mark.asyncio
async def test_diagnosis_text(client, school_admin_headers, seed_school, db):
    """ORC-007: 诊断文本必须是模板拼接，包含具体数据。"""
    exam, subj, _, _, _ = await _seed_graded_exam(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/diagnosis",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["summary_text"], str)
    assert len(data["summary_text"]) > 0
    assert isinstance(data["weak_questions"], list)
    assert isinstance(data["error_distribution"], dict)
    assert isinstance(data["suggestions"], list)


@pytest.mark.asyncio
async def test_diagnosis_empty_exam(client, school_admin_headers, seed_school, db):
    school, _ = seed_school
    exam = Exam(name="空诊断", status="completed", school_id=school.id)
    db.add(exam)
    await db.commit()

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/diagnosis",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    assert "暂无" in resp.json()["summary_text"]
