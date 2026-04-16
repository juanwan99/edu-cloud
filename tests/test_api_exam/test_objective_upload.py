import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def obj_setup(client, db):
    """Create school + user + exam + subject + 2 objective questions."""
    school = School(name="ObjTest", code="OBJ1")
    db.add(school)
    await db.commit()

    user = User(username="obj_teacher", display_name="T")
    user.set_password("pass")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="ObjExam", school_id=school.id)
    db.add(exam)
    await db.commit()

    subject = Subject(exam_id=exam.id, name="Math", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()

    q1 = Question(
        subject_id=subject.id, name="Q1", question_type="choice",
        max_score=5.0, correct_answer="A", school_id=school.id,
    )
    q2 = Question(
        subject_id=subject.id, name="Q2", question_type="choice",
        max_score=3.0, correct_answer="BD", school_id=school.id,
    )
    db.add_all([q1, q2])
    await db.commit()

    return {
        "headers": headers,
        "exam_id": exam.id,
        "subject_id": subject.id,
        "q1_id": q1.id,
        "q2_id": q2.id,
    }


async def test_normal_grading(client, obj_setup):
    """One correct, one wrong -> partial score."""
    s = obj_setup
    resp = await client.post(
        "/api/v1/scan/upload-objective",
        json={
            "exam_id": s["exam_id"],
            "subject_id": s["subject_id"],
            "student_id": "STU100",
            "answers": [
                {"question_id": s["q1_id"], "detected_answer": "A"},
                {"question_id": s["q2_id"], "detected_answer": "C"},
            ],
        },
        headers=s["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_absent"] is False
    assert len(data["results"]) == 2
    # Q1 correct -> 5.0
    assert data["results"][0]["is_correct"] is True
    assert data["results"][0]["score"] == 5.0
    # Q2 wrong -> 0
    assert data["results"][1]["is_correct"] is False
    assert data["results"][1]["score"] == 0.0
    assert data["total_score"] == 5.0
    assert data["total_max"] == 8.0


async def test_absent_student(client, obj_setup):
    """Absent student -> all zeros."""
    s = obj_setup
    resp = await client.post(
        "/api/v1/scan/upload-objective",
        json={
            "exam_id": s["exam_id"],
            "subject_id": s["subject_id"],
            "student_id": "STU_ABSENT",
            "is_absent": True,
        },
        headers=s["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_absent"] is True
    assert data["results"] == []
    assert data["total_score"] == 0.0
    assert data["total_max"] == 8.0


async def test_anomaly_flag_stored(client, obj_setup, db):
    """Anomaly flag is persisted in StudentAnswer."""
    s = obj_setup
    resp = await client.post(
        "/api/v1/scan/upload-objective",
        json={
            "exam_id": s["exam_id"],
            "subject_id": s["subject_id"],
            "student_id": "STU_ANOMALY",
            "answers": [
                {
                    "question_id": s["q1_id"],
                    "detected_answer": "A",
                    "anomaly": True,
                    "fill_ratios": {"A": 0.85, "B": 0.12},
                },
            ],
        },
        headers=s["headers"],
    )
    assert resp.status_code == 200

    # Verify via DB
    from sqlalchemy import select
    from edu_cloud.modules.scan.models import StudentAnswer

    result = await db.execute(
        select(StudentAnswer).where(
            StudentAnswer.student_id == "STU_ANOMALY",
            StudentAnswer.question_id == s["q1_id"],
        )
    )
    answer = result.scalar_one()
    assert answer.is_anomaly is True
    assert answer.fill_ratios == {"A": 0.85, "B": 0.12}
    assert answer.score == 5.0
