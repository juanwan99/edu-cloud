import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.analytics.models import StudentKnpMastery
from tests.conftest import *  # noqa


@pytest.fixture
async def principal_headers(db, seed_school):
    school, _ = seed_school
    user = User(username="layer_principal", display_name="校长")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="principal", school_id=school.id, is_primary=True))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "principal"})
    return {"Authorization": f"Bearer {token}"}


async def _seed_layer_data(db, seed_school):
    school, _ = seed_school
    cls = Class(name="高一(1)班", grade="高一", grade_number=10, school_id=school.id)
    db.add(cls)
    await db.flush()

    students = []
    for i, (name, num) in enumerate([
        ("张优", "L001"), ("李优", "L002"),
        ("赵良", "L003"), ("钱良", "L004"), ("孙良", "L005"),
        ("周差", "L006"),
    ]):
        s = Student(name=name, student_number=num, class_id=cls.id, school_id=school.id, grade="高一")
        db.add(s)
        students.append(s)
    await db.flush()

    from datetime import date
    exam = Exam(name="期中", status="completed", exam_date=date(2026, 3, 1), school_id=school.id)
    db.add(exam)
    await db.flush()

    subj = Subject(name="数学", code="math", exam_id=exam.id, school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(name="1", question_type="choice", max_score=100, subject_id=subj.id, school_id=school.id)
    db.add(q)
    await db.flush()

    scores = [92, 88, 75, 70, 65, 40]
    for stu, score in zip(students, scores):
        sa = StudentAnswer(exam_id=exam.id, subject_id=subj.id, student_id=stu.id, question_id=q.id, school_id=school.id)
        db.add(sa)
        await db.flush()
        gr = GradingResult(answer_id=sa.id, question_id=q.id, school_id=school.id,
                           final_score=float(score), max_score=100, status="confirmed", source="manual")
        db.add(gr)

    knp_data = [
        ("张优", 0.95), ("李优", 0.90),
        ("赵良", 0.70), ("钱良", 0.65), ("孙良", 0.60),
        ("周差", 0.30),
    ]
    for stu, rate in zip(students, [d[1] for d in knp_data]):
        db.add(StudentKnpMastery(
            student_id=stu.id, exam_id=exam.id, concept_id="kp_001",
            school_id=school.id, stu_rate=rate, class_rate=0.7, grade_rate=0.7,
        ))

    await db.commit()
    return exam, subj, cls, students


@pytest.mark.asyncio
async def test_layer_analysis_returns_three_layers(client, principal_headers, seed_school, db):
    exam, subj, cls, students = await _seed_layer_data(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/layer-analysis",
        headers=principal_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["layers"]) == 3
    counts = [layer["count"] for layer in data["layers"]]
    assert sum(counts) == 6


@pytest.mark.asyncio
async def test_layer_analysis_score_rates_reasonable(client, principal_headers, seed_school, db):
    exam, subj, cls, students = await _seed_layer_data(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/layer-analysis",
        headers=principal_headers,
    )
    data = resp.json()

    for layer in data["layers"]:
        rate = layer["avgScoreRate"]
        assert rate is None or 0 <= rate <= 1


@pytest.mark.asyncio
async def test_layer_analysis_has_max_diff_knowledges(client, principal_headers, seed_school, db):
    exam, subj, cls, students = await _seed_layer_data(db, seed_school)

    resp = await client.get(
        f"/api/v1/analytics/exam/{exam.id}/layer-analysis",
        headers=principal_headers,
    )
    data = resp.json()

    assert "maxDiffKnowledges" in data
    assert isinstance(data["maxDiffKnowledges"], list)
