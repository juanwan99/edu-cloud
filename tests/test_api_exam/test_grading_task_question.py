"""Tests for per-question GradingTask support (Task 5).

ORC-002: Subject-level path (question_id=NULL) must not change AT ALL.
ORC-001: confirmed GradingResults cannot be overwritten.
AGP-001: question must belong to the subject and be subjective.
AGP-004: regrade cleans ai_pending/ai_done results, keeps confirmed.
"""
import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult
from edu_cloud.shared.auth import create_access_token


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

async def _seed_school_and_user(db, school_code: str, username: str):
    school = School(name=f"School-{school_code}", code=school_code)
    db.add(school)
    await db.commit()

    user = User(username=username, display_name=username)
    user.set_password("pass")
    db.add(user)
    await db.commit()

    db.add(UserRole(
        user_id=user.id,
        role="academic_director",
        school_id=school.id,
        is_primary=True,
    ))
    await db.flush()

    token = create_access_token({
        "sub": user.id,
        "school_id": school.id,
        "role": "academic_director",
    })
    headers = {"Authorization": f"Bearer {token}"}
    return school, user, headers


async def _seed_exam_and_subject(db, school_id: str):
    exam = Exam(name="期中考试", school_id=school_id)
    db.add(exam)
    await db.commit()

    subject = Subject(
        exam_id=exam.id,
        name="语文",
        code="chinese",
        school_id=school_id,
    )
    db.add(subject)
    await db.commit()
    return exam, subject


async def _seed_question(db, subject_id: str, school_id: str, q_type: str = "essay"):
    q = Question(
        subject_id=subject_id,
        name="作文题",
        question_type=q_type,
        max_score=20.0,
        school_id=school_id,
    )
    db.add(q)
    await db.commit()
    return q


async def _seed_rubric(db, question_id: str, school_id: str):
    rubric = Rubric(
        question_id=question_id,
        school_id=school_id,
        source="manual",
        criteria=[{"blankNo": "1", "score": 20.0, "answer": "示例答案"}],
    )
    db.add(rubric)
    await db.commit()
    return rubric


async def _seed_answers(db, exam_id: str, subject_id: str, question_id: str,
                         school_id: str, count: int = 2):
    answers = []
    for i in range(count):
        a = StudentAnswer(
            exam_id=exam_id,
            subject_id=subject_id,
            student_id=f"student-{i}",
            question_id=question_id,
            image_path=f"/fake/q/{i}.png",
            school_id=school_id,
        )
        db.add(a)
        answers.append(a)
    await db.commit()
    return answers


# ---------------------------------------------------------------------------
# Fixture: full happy-path setup for question-level task
# ---------------------------------------------------------------------------

@pytest.fixture
async def q_task_setup(client, db):
    school, user, headers = await _seed_school_and_user(db, "QTS01", "qts_user")
    exam, subject = await _seed_exam_and_subject(db, school.id)
    question = await _seed_question(db, subject.id, school.id)
    await _seed_rubric(db, question.id, school.id)
    answers = await _seed_answers(db, exam.id, subject.id, question.id, school.id)
    return {
        "headers": headers,
        "school_id": school.id,
        "subject_id": subject.id,
        "question_id": question.id,
        "answer_ids": [a.id for a in answers],
        "exam_id": exam.id,
    }


# ---------------------------------------------------------------------------
# Test 1: POST with question_id creates task, response has question_id
# ---------------------------------------------------------------------------

@patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock)
async def test_create_task_with_question_id(mock_enqueue, client, q_task_setup):
    """AGP-001: question_id 存在时创建题目级 task，响应包含 question_id。"""
    resp = await client.post(
        "/api/v1/grading/tasks",
        json={
            "subject_id": q_task_setup["subject_id"],
            "question_id": q_task_setup["question_id"],
        },
        headers=q_task_setup["headers"],
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "pending"
    assert data["subject_id"] == q_task_setup["subject_id"]
    assert data["question_id"] == q_task_setup["question_id"]
    assert "id" in data
    mock_enqueue.assert_called_once()


# ---------------------------------------------------------------------------
# Test 2: question has no Rubric → 400
# ---------------------------------------------------------------------------

@pytest.fixture
async def q_task_no_rubric_setup(client, db):
    school, user, headers = await _seed_school_and_user(db, "QNR01", "qnr_user")
    exam, subject = await _seed_exam_and_subject(db, school.id)
    question = await _seed_question(db, subject.id, school.id)
    # No rubric seeded
    await _seed_answers(db, exam.id, subject.id, question.id, school.id)
    return {
        "headers": headers,
        "subject_id": subject.id,
        "question_id": question.id,
    }


@patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock)
async def test_create_task_question_no_rubric(mock_enqueue, client, q_task_no_rubric_setup):
    """题目无 Rubric 时返回 400。"""
    resp = await client.post(
        "/api/v1/grading/tasks",
        json={
            "subject_id": q_task_no_rubric_setup["subject_id"],
            "question_id": q_task_no_rubric_setup["question_id"],
        },
        headers=q_task_no_rubric_setup["headers"],
    )
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    assert "Rubric" in resp.json().get("detail", "") or "评分标准" in resp.json().get("detail", "")
    mock_enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: ORC-002 — no question_id → subject-level logic unchanged (4 checks)
# ---------------------------------------------------------------------------

@pytest.fixture
async def subject_level_setup(client, db):
    school, user, headers = await _seed_school_and_user(db, "SLS01", "sls_user")
    exam, subject = await _seed_exam_and_subject(db, school.id)
    question = await _seed_question(db, subject.id, school.id)
    await _seed_rubric(db, question.id, school.id)
    await _seed_answers(db, exam.id, subject.id, question.id, school.id)
    return {
        "headers": headers,
        "subject_id": subject.id,
        "question_id": question.id,
        "school_id": school.id,
    }


@patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock)
async def test_create_task_subject_level_unchanged(mock_enqueue, client, subject_level_setup):
    """ORC-002: no question_id → 走 subject-level path，4 个前置校验保持原样。"""
    # Happy path: subject-level task created successfully (no question_id)
    resp = await client.post(
        "/api/v1/grading/tasks",
        json={"subject_id": subject_level_setup["subject_id"]},
        headers=subject_level_setup["headers"],
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["status"] == "pending"
    assert data["subject_id"] == subject_level_setup["subject_id"]
    # subject-level task has no question_id
    assert data.get("question_id") is None
    mock_enqueue.assert_called_once()


@patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock)
async def test_create_task_subject_level_no_rubric_still_400(mock_enqueue, client, db):
    """ORC-002 回归: subject-level path 缺 Rubric 仍 400（未受题目级变更干扰）。"""
    school, user, headers = await _seed_school_and_user(db, "SLR01", "slr_user")
    exam, subject = await _seed_exam_and_subject(db, school.id)
    question = await _seed_question(db, subject.id, school.id)
    # No rubric, no question_id in request
    await _seed_answers(db, exam.id, subject.id, question.id, school.id)

    resp = await client.post(
        "/api/v1/grading/tasks",
        json={"subject_id": subject.id},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "评分标准" in resp.json().get("detail", "") or "Rubric" in resp.json().get("detail", "")
    mock_enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4: question belongs to another subject → 400 (AGP-001)
# ---------------------------------------------------------------------------

@pytest.fixture
async def q_wrong_subject_setup(client, db):
    school, user, headers = await _seed_school_and_user(db, "QWS01", "qws_user")
    exam, subject = await _seed_exam_and_subject(db, school.id)

    # Another subject in same school
    other_subject = Subject(
        exam_id=exam.id,
        name="数学",
        code="math",
        school_id=school.id,
    )
    db.add(other_subject)
    await db.commit()

    # Question belongs to other_subject, NOT subject
    question = Question(
        subject_id=other_subject.id,
        name="大题",
        question_type="essay",
        max_score=15.0,
        school_id=school.id,
    )
    db.add(question)
    await db.commit()

    await _seed_rubric(db, question.id, school.id)
    await _seed_answers(db, exam.id, other_subject.id, question.id, school.id)

    return {
        "headers": headers,
        "subject_id": subject.id,         # request uses subject
        "question_id": question.id,       # question actually belongs to other_subject
    }


@patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock)
async def test_create_task_question_wrong_subject(mock_enqueue, client, q_wrong_subject_setup):
    """AGP-001: question 不属于该 subject → 400。"""
    resp = await client.post(
        "/api/v1/grading/tasks",
        json={
            "subject_id": q_wrong_subject_setup["subject_id"],
            "question_id": q_wrong_subject_setup["question_id"],
        },
        headers=q_wrong_subject_setup["headers"],
    )
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    mock_enqueue.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5: regrade cleans ai_pending/ai_done results, keeps confirmed (AGP-004 + ORC-001)
# ---------------------------------------------------------------------------

@pytest.fixture
async def q_regrade_setup(client, db):
    school, user, headers = await _seed_school_and_user(db, "RGR01", "rgr_user")
    exam, subject = await _seed_exam_and_subject(db, school.id)
    question = await _seed_question(db, subject.id, school.id)
    await _seed_rubric(db, question.id, school.id)
    answers = await _seed_answers(db, exam.id, subject.id, question.id, school.id, count=3)

    # Create a previous GradingTask to hang results off
    old_task = GradingTask(
        subject_id=subject.id,
        question_id=question.id,
        school_id=school.id,
        status="completed",
        total=3,
        completed=3,
        failed=0,
        created_by=user.id,
    )
    db.add(old_task)
    await db.commit()

    # Seed 3 GradingResults:
    #   answers[0] → ai_pending  (should be cleaned)
    #   answers[1] → ai_done     (should be cleaned)
    #   answers[2] → confirmed   (ORC-001: must NOT be cleaned)
    r_pending = GradingResult(
        ai_task_id=old_task.id,
        answer_id=answers[0].id,
        question_id=question.id,
        school_id=school.id,
        ai_score=10.0,
        final_score=10.0,
        max_score=20.0,
        status="ai_pending",
    )
    r_done = GradingResult(
        ai_task_id=old_task.id,
        answer_id=answers[1].id,
        question_id=question.id,
        school_id=school.id,
        ai_score=15.0,
        final_score=15.0,
        max_score=20.0,
        status="ai_done",
    )
    r_confirmed = GradingResult(
        ai_task_id=old_task.id,
        answer_id=answers[2].id,
        question_id=question.id,
        school_id=school.id,
        ai_score=18.0,
        final_score=18.0,
        max_score=20.0,
        status="confirmed",
        source="ai",
    )
    db.add(r_pending)
    db.add(r_done)
    db.add(r_confirmed)
    await db.commit()

    return {
        "headers": headers,
        "school_id": school.id,
        "subject_id": subject.id,
        "question_id": question.id,
        "answer_ids": [a.id for a in answers],
        "confirmed_answer_id": answers[2].id,
    }


@patch("edu_cloud.modules.grading.router.enqueue_grading_task", new_callable=AsyncMock)
async def test_create_task_regrade_cleans_old_results(mock_enqueue, client, db, q_regrade_setup):
    """AGP-004 + ORC-001: regrade 清理 ai_pending/ai_done，保留 confirmed。"""
    resp = await client.post(
        "/api/v1/grading/tasks",
        json={
            "subject_id": q_regrade_setup["subject_id"],
            "question_id": q_regrade_setup["question_id"],
        },
        headers=q_regrade_setup["headers"],
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    mock_enqueue.assert_called_once()

    # Verify: ai_pending and ai_done for answers[0] and answers[1] are gone
    cleaned_answer_ids = q_regrade_setup["answer_ids"][:2]
    remaining = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id.in_(cleaned_answer_ids),
            GradingResult.status.in_(["ai_pending", "ai_done"]),
        )
    )).scalars().all()
    assert len(remaining) == 0, (
        f"Expected stale ai_pending/ai_done to be cleaned, found {len(remaining)}"
    )

    # ORC-001: confirmed result for answers[2] must survive
    confirmed = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id == q_regrade_setup["confirmed_answer_id"],
            GradingResult.status == "confirmed",
        )
    )).scalar_one_or_none()
    assert confirmed is not None, "ORC-001 violated: confirmed GradingResult was deleted"
