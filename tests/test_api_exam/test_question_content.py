"""Tests for question content update and image upload endpoints (Task 3)."""
import io
import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Subject, Question
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def seed_question(db):
    """Create school + user + exam + subject + question. Returns (headers, question_id)."""
    school = School(name="Content Test School", code="CTS01")
    db.add(school)
    await db.flush()

    user = User(username="content_admin", display_name="Content Admin")
    user.set_password("pass123")
    db.add(user)
    await db.flush()

    db.add(UserRole(
        user_id=user.id,
        role="academic_director",  # has MANAGE_EXAMS
        school_id=school.id,
        is_primary=True,
    ))
    await db.flush()

    token = create_access_token({"sub": user.id, "role": "academic_director"})
    headers = {"Authorization": f"Bearer {token}"}

    # Create exam via API to get proper school_id wiring
    from edu_cloud.modules.exam.models import Exam
    exam = Exam(name="期中考试", card_title="期中答题卡", school_id=school.id)
    db.add(exam)
    await db.flush()

    subject = Subject(exam_id=exam.id, name="语文", code="yuwen", school_id=school.id)
    db.add(subject)
    await db.flush()

    question = Question(
        subject_id=subject.id,
        name="第1题",
        question_type="essay",
        max_score=10.0,
        school_id=school.id,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    return headers, question.id


@pytest.fixture
async def observer_headers_for_content(db):
    """JWT headers for observer role (lacks MANAGE_EXAMS)."""
    school = School(name="Observer School", code="OBS01")
    db.add(school)
    await db.flush()

    user = User(username="obs_content_user", display_name="Observer")
    user.set_password("pass123")
    db.add(user)
    await db.flush()

    db.add(UserRole(
        user_id=user.id,
        role="observer",
        school_id=school.id,
        is_primary=True,
    ))
    await db.commit()

    token = create_access_token({"sub": user.id, "role": "observer"})
    return {"Authorization": f"Bearer {token}"}


async def test_update_question_content(client, seed_question):
    """PUT /questions/{id}/content — updates content + reference_answer successfully."""
    headers, question_id = seed_question

    payload = {
        "content": "请阅读下文并回答问题",
        "reference_answer": "参考答案：这是示例回答",
    }
    resp = await client.put(f"/api/v1/questions/{question_id}/content", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert data["content"] == "请阅读下文并回答问题"
    assert data["reference_answer"] == "参考答案：这是示例回答"
    # Other fields still present
    assert data["id"] == question_id
    assert data["name"] == "第1题"
    assert data["question_type"] == "essay"


async def test_update_content_not_found(client, seed_question):
    """PUT /questions/{id}/content — nonexistent question returns 404."""
    headers, _ = seed_question

    payload = {"content": "Some content"}
    resp = await client.put("/api/v1/questions/nonexistent-id/content", json=payload, headers=headers)
    assert resp.status_code == 404, resp.text


async def test_upload_question_image(client, seed_question, tmp_path, monkeypatch):
    """POST /questions/{id}/content/upload-image — multipart upload returns path."""
    import edu_cloud.config as cfg_module
    monkeypatch.setattr(cfg_module.settings, "UPLOAD_DIR", str(tmp_path))

    headers, question_id = seed_question

    image_bytes = b"fake-image-data-png"
    resp = await client.post(
        f"/api/v1/questions/{question_id}/content/upload-image",
        files={"file": ("test.png", io.BytesIO(image_bytes), "image/png")},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text

    data = resp.json()
    assert "path" in data
    assert data["path"].startswith("/uploads/questions/")
    assert data["path"].endswith(".png")


async def test_update_content_permission_denied(client, seed_question, observer_headers_for_content):
    """PUT /questions/{id}/content — observer role returns 403 (AGP-002 反例)."""
    _, question_id = seed_question

    payload = {"content": "Observer tries to update"}
    resp = await client.put(
        f"/api/v1/questions/{question_id}/content",
        json=payload,
        headers=observer_headers_for_content,
    )
    assert resp.status_code == 403, resp.text
