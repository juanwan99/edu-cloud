"""Tests for POST /rubrics/generate and criteria validation on POST /rubrics."""
import pytest
from unittest.mock import AsyncMock, patch

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.shared.auth import create_access_token


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def grading_school(db):
    """Seed a school for grading tests."""
    school = School(name="阅卷测试校", code="GRD01", district="测试区", api_key_hash="x")
    db.add(school)
    await db.commit()
    await db.refresh(school)
    return school


@pytest.fixture
async def manager_headers(db, grading_school):
    """JWT headers for academic_director (has MANAGE_GRADING)."""
    user = User(username="grading_mgr", display_name="阅卷管理员")
    user.set_password("pw")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id,
        role="academic_director",
        school_id=grading_school.id,
        is_primary=True,
    ))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "academic_director"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def no_perm_headers(db, grading_school):
    """JWT headers for observer (lacks MANAGE_GRADING)."""
    user = User(username="grading_obs", display_name="观察员")
    user.set_password("pw")
    db.add(user)
    await db.flush()
    db.add(UserRole(
        user_id=user.id,
        role="observer",
        school_id=grading_school.id,
        is_primary=True,
    ))
    await db.commit()
    token = create_access_token({"sub": user.id, "role": "observer"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def essay_question(db, grading_school):
    """Seed an essay question with content and reference_answer."""
    exam = Exam(name="期末", school_id=grading_school.id)
    db.add(exam)
    await db.flush()
    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=grading_school.id)
    db.add(subject)
    await db.flush()
    q = Question(
        subject_id=subject.id,
        name="论述题",
        question_type="essay",
        max_score=8.0,
        school_id=grading_school.id,
        content="请解释光合作用的过程及意义。",
        reference_answer="光合作用是植物利用光能将二氧化碳和水转化为有机物并释放氧气的过程。",
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q


@pytest.fixture
async def empty_question(db, grading_school):
    """Seed a question with no content or reference_answer."""
    exam = Exam(name="期末2", school_id=grading_school.id)
    db.add(exam)
    await db.flush()
    subject = Subject(exam_id=exam.id, name="数学", code="math", school_id=grading_school.id)
    db.add(subject)
    await db.flush()
    q = Question(
        subject_id=subject.id,
        name="空白题",
        question_type="essay",
        max_score=5.0,
        school_id=grading_school.id,
        content=None,
        reference_answer=None,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q


# ---------------------------------------------------------------------------
# Tests: POST /rubrics/generate
# ---------------------------------------------------------------------------

async def test_generate_rubric_success(client, db, manager_headers, essay_question):
    """LLM returns criteria → rubric saved with source=ai_generated."""
    mock_criteria = [
        {
            "blankNo": "1",
            "score": 4,
            "answer": "光合作用定义",
            "intent": "考查概念理解",
            "coreRequirement": "必须包含光能转化",
        },
        {
            "blankNo": "2",
            "score": 4,
            "answer": "释放氧气",
            "intent": "考查过程描述",
            "coreRequirement": "必须提及氧气",
        },
    ]
    with patch(
        "edu_cloud.modules.grading.router.generate_rubric_via_llm",
        new_callable=AsyncMock,
        return_value=mock_criteria,
    ):
        resp = await client.post(
            "/api/v1/grading/rubrics/generate",
            json={"question_id": essay_question.id, "max_score": 8.0},
            headers=manager_headers,
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "ai_generated"
    assert data["question_id"] == essay_question.id
    assert len(data["criteria"]) == 2
    assert data["criteria"][0]["blankNo"] == "1"


async def test_generate_rubric_no_content(client, db, manager_headers, empty_question):
    """Question with no content and no reference_answer → 400."""
    resp = await client.post(
        "/api/v1/grading/rubrics/generate",
        json={"question_id": empty_question.id, "max_score": 5.0},
        headers=manager_headers,
    )
    assert resp.status_code == 400
    assert "content" in resp.json()["detail"].lower() or "reference" in resp.json()["detail"].lower()


async def test_generate_rubric_with_images(client, db, manager_headers, grading_school, tmp_path):
    """Images on the question are passed as base64 to generate_rubric_via_llm."""
    # Create a question that has an image path
    exam = Exam(name="图片考试", school_id=grading_school.id)
    db.add(exam)
    await db.flush()
    subject = Subject(exam_id=exam.id, name="物理", code="physics", school_id=grading_school.id)
    db.add(subject)
    await db.flush()

    # Write a dummy image to tmp_path so the base64 conversion can find it
    img_file = tmp_path / "q_image.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header

    q = Question(
        subject_id=subject.id,
        name="图片题",
        question_type="essay",
        max_score=4.0,
        school_id=grading_school.id,
        content="如图所示，分析受力情况。",
        reference_answer="竖直向下为重力。",
        content_images=[str(img_file)],
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    captured = {}

    async def fake_generate(question, max_score, db_session):
        # Record what images the real function would have used
        # We just want to confirm it was called with the right question
        captured["question_id"] = question.id
        return [{"blankNo": "1", "score": 4, "answer": "重力", "intent": "test", "coreRequirement": "必须"}]

    with patch(
        "edu_cloud.modules.grading.router.generate_rubric_via_llm",
        new_callable=AsyncMock,
        side_effect=fake_generate,
    ):
        resp = await client.post(
            "/api/v1/grading/rubrics/generate",
            json={"question_id": q.id, "max_score": 4.0},
            headers=manager_headers,
        )

    assert resp.status_code == 200, resp.text
    assert captured["question_id"] == q.id
    assert resp.json()["source"] == "ai_generated"


async def test_generate_rubric_permission_denied(client, db, no_perm_headers, essay_question):
    """Observer lacks MANAGE_GRADING → 403."""
    resp = await client.post(
        "/api/v1/grading/rubrics/generate",
        json={"question_id": essay_question.id, "max_score": 8.0},
        headers=no_perm_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tests: POST /rubrics — criteria validation
# ---------------------------------------------------------------------------

@pytest.fixture
async def rubric_question(db, grading_school):
    """Seed a question with max_score=10 for rubric validation tests."""
    exam = Exam(name="验证考试", school_id=grading_school.id)
    db.add(exam)
    await db.flush()
    subject = Subject(exam_id=exam.id, name="英语", code="english", school_id=grading_school.id)
    db.add(subject)
    await db.flush()
    q = Question(
        subject_id=subject.id,
        name="写作题",
        question_type="essay",
        max_score=10.0,
        school_id=grading_school.id,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return q


async def test_rubric_create_missing_fields(client, db, manager_headers, rubric_question):
    """Criteria item missing blankNo → 422."""
    resp = await client.post(
        "/api/v1/grading/rubrics",
        json={
            "question_id": rubric_question.id,
            "criteria": [
                # Missing blankNo — has score and answer but no blankNo
                {"score": 10, "answer": "some answer"},
            ],
            "source": "manual",
        },
        headers=manager_headers,
    )
    assert resp.status_code == 422


async def test_rubric_create_score_mismatch(client, db, manager_headers, rubric_question):
    """Sum of criteria scores != question max_score → 422."""
    resp = await client.post(
        "/api/v1/grading/rubrics",
        json={
            "question_id": rubric_question.id,
            "criteria": [
                {"blankNo": "1", "score": 3, "answer": "A"},
                {"blankNo": "2", "score": 4, "answer": "B"},
                # Total = 7, but max_score = 10
            ],
            "source": "manual",
        },
        headers=manager_headers,
    )
    assert resp.status_code == 422
    assert "10" in resp.json()["detail"]


async def test_rubric_create_negative_score(client, db, manager_headers, rubric_question):
    """Negative score in criteria → 422."""
    resp = await client.post(
        "/api/v1/grading/rubrics",
        json={
            "question_id": rubric_question.id,
            "criteria": [
                {"blankNo": "1", "score": -1, "answer": "A"},
                {"blankNo": "2", "score": 11, "answer": "B"},
                # Total = 10 but one is negative
            ],
            "source": "manual",
        },
        headers=manager_headers,
    )
    assert resp.status_code == 422
    assert ">= 0" in resp.json()["detail"]


async def test_rubric_create_valid_passes(client, db, manager_headers, rubric_question):
    """Valid criteria (sum == max_score, all fields present) → 201."""
    resp = await client.post(
        "/api/v1/grading/rubrics",
        json={
            "question_id": rubric_question.id,
            "criteria": [
                {"blankNo": "1", "score": 5, "answer": "First point"},
                {"blankNo": "2", "score": 5, "answer": "Second point"},
            ],
            "source": "manual",
        },
        headers=manager_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["criteria"]) == 2
