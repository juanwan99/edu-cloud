import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def scan_setup(client, db, tmp_path):
    school = School(name="Test", code="SC01")
    db.add(school)
    await db.commit()
    user = User(username="t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()
    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    exam = Exam(name="E", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="Math", code="math", school_id=school.id)
    db.add(subject)
    await db.commit()
    question = Question(subject_id=subject.id, name="Q1", question_type="essay", max_score=10, school_id=school.id)
    db.add(question)
    await db.commit()

    return {
        "headers": headers,
        "school_id": school.id,
        "exam_id": exam.id,
        "subject_id": subject.id,
        "question_id": question.id,
        "tmp_path": str(tmp_path),
    }


async def test_upload_single(client, scan_setup):
    s = scan_setup
    resp = await client.post(
        "/api/v1/scan/upload",
        data={
            "exam_id": s["exam_id"],
            "subject_id": s["subject_id"],
            "student_id": "STU001",
            "question_id": s["question_id"],
        },
        files={"image": ("q1.png", b"\x89PNG\r\n\x1a\nfake-png-data", "image/png")},
        headers=s["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["student_id"] == "STU001"
    assert data["question_id"] == s["question_id"]
    assert "image_path" in data


async def test_upload_duplicate_returns_409(client, scan_setup):
    s = scan_setup
    upload_data = {
        "exam_id": s["exam_id"],
        "subject_id": s["subject_id"],
        "student_id": "STU002",
        "question_id": s["question_id"],
    }
    files = {"image": ("q1.png", b"\x89PNG\r\n\x1a\ndata1", "image/png")}
    await client.post("/api/v1/scan/upload", data=upload_data, files=files, headers=s["headers"])
    resp = await client.post(
        "/api/v1/scan/upload",
        data=upload_data,
        files={"image": ("q1.png", b"\x89PNG\r\n\x1a\ndata2", "image/png")},
        headers=s["headers"],
    )
    assert resp.status_code == 409


async def test_upload_batch(client, scan_setup):
    s = scan_setup
    resp = await client.post(
        "/api/v1/scan/upload/batch",
        data={
            "exam_id": s["exam_id"],
            "subject_id": s["subject_id"],
            "student_id": "STU003",
            "question_ids": s["question_id"],
        },
        files=[("images", ("q1.png", b"\x89PNG\r\n\x1a\ndata-q1", "image/png"))],
        headers=s["headers"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["uploaded"] == 1
