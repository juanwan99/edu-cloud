"""Phase 2.3: subject_id 统一查询入参的 API 测试。"""
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def subj_setup(client, db):
    school = School(name="SJ", code="SJ01")
    db.add(school)
    await db.commit()
    user = User(username="sj_t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="期中", school_id=school.id)
    db.add(exam)
    await db.commit()

    subject = Subject(exam_id=exam.id, name="数学", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()

    q = Question(subject_id=subject.id, name="Q1", question_type="essay", max_score=10.0, school_id=school.id)
    db.add(q)
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="completed", total=2, completed=2, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.commit()

    for sid, score in [("s1", 8.0), ("s2", 6.0)]:
        a = StudentAnswer(
            exam_id=exam.id, subject_id=subject.id, student_id=sid,
            question_id=q.id, image_path=f"/fake/{sid}.png", school_id=school.id,
        )
        db.add(a)
        await db.commit()
        r = GradingResult(
            ai_task_id=task.id, answer_id=a.id, question_id=q.id,
            school_id=school.id, ai_score=score, final_score=score, max_score=10.0,
            ai_feedback="f", ai_confidence=0.9, status="ai_done",
        )
        db.add(r)
        await db.commit()

    return {
        "headers": headers, "exam_id": exam.id, "subject_id": subject.id,
        "school_id": school.id,
    }


async def test_subject_summary(client, subj_setup):
    resp = await client.get(
        f"/api/v1/analytics/subject/{subj_setup['subject_id']}/summary",
        headers=subj_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exam_id"] == subj_setup["exam_id"]
    assert data["total_students"] == 2
    assert len(data["subjects"]) == 1
    assert data["subjects"][0]["subject_name"] == "数学"


async def test_subject_distribution(client, subj_setup):
    resp = await client.get(
        f"/api/v1/analytics/subject/{subj_setup['subject_id']}/distribution",
        headers=subj_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exam_id"] == subj_setup["exam_id"]
    assert data["subject_id"] == subj_setup["subject_id"]
    assert data["total_students"] == 2


async def test_subject_grade_aggregates(client, subj_setup):
    resp = await client.get(
        f"/api/v1/analytics/subject/{subj_setup['subject_id']}/grade-aggregates",
        headers=subj_setup["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exam_id"] == subj_setup["exam_id"]
    assert data["subject_id"] == subj_setup["subject_id"]


async def test_subject_summary_not_found(client, subj_setup):
    resp = await client.get(
        "/api/v1/analytics/subject/nonexistent-id/summary",
        headers=subj_setup["headers"],
    )
    assert resp.status_code == 404


async def test_resolve_subject_to_exam_service(db, subj_setup):
    from edu_cloud.modules.analytics.service import resolve_subject_to_exam
    exam_id, subject = await resolve_subject_to_exam(
        db, subj_setup["subject_id"], subj_setup["school_id"],
    )
    assert exam_id == subj_setup["exam_id"]
    assert subject.name == "数学"


async def test_resolve_subject_wrong_school(db, subj_setup):
    from edu_cloud.modules.analytics.service import resolve_subject_to_exam
    from edu_cloud.services.exceptions import NotFoundError
    with pytest.raises(NotFoundError):
        await resolve_subject_to_exam(db, subj_setup["subject_id"], "wrong-school-id")
