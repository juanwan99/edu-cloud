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
    user = User(username="advanced_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_knowledge_exam(db, seed_school):
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()
    stu = Student(name="测试生", student_number="K001", class_id=cls.id, school_id=school.id, grade="高一")
    db.add(stu)
    await db.flush()
    exam = Exam(name="知识点测试", status="completed", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(name="生物", code="biology", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(name="1", question_type="essay", max_score=10, subject_id=subj.id, school_id=school.id,
                 knowledge_points={"knowledge_ids": ["光合作用", "细胞分裂"]})
    db.add(q)
    await db.flush()
    sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
    db.add(sa)
    await db.flush()
    gr = GradingResult(
        answer_id=sa.id, question_id=q.id, school_id=school.id,
        final_score=6.0, max_score=10.0, status="confirmed", source="ai",
        ai_raw_response={"details": [{"subQuestion": "(1)", "blanks": [
            {"index": 1, "answer": "错误", "score": 0, "fullScore": 5, "correct": False,
             "reason": "概念混淆：细胞分裂与减数分裂混淆"},
        ]}]},
    )
    db.add(gr)
    await db.commit()
    return exam, subj, stu, cls


@pytest.mark.asyncio
async def test_class_knowledge_returns_structure(client, school_admin_headers, seed_school, db):
    exam, subj, _, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-knowledge",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "knowledge_points" in data
    assert "classes" in data


@pytest.mark.asyncio
async def test_class_error_patterns_returns_structure(client, school_admin_headers, seed_school, db):
    exam, _, _, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/class-error-patterns",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "error_types" in data
    assert "classes" in data


@pytest.mark.asyncio
async def test_student_ai_diagnosis(client, school_admin_headers, seed_school, db):
    exam, _, stu, _ = await _seed_knowledge_exam(db, seed_school)
    resp = await client.get(
        f"/api/v1/profile/students/{stu.id}/ai-diagnosis",
        headers=school_admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["summary"], str)
    assert isinstance(data["improving"], list)
    assert isinstance(data["declining"], list)
    assert isinstance(data["weak_points"], list)
