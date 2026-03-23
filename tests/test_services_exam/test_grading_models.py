import pytest
from edu_cloud.modules.grading.models import Rubric, GradingTask, AIGradingResult, TeacherReview


async def test_rubric_fields(db):
    r = Rubric(
        question_id="q1", school_id="s1",
        criteria=[{"point": "概念", "score": 3.0, "description": "正确表述"}],
        reference_answer="答案文本",
        source="manual",
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    assert r.id is not None
    assert r.criteria[0]["point"] == "概念"
    assert r.source == "manual"


async def test_grading_task_new_fields(db):
    t = GradingTask(
        subject_id="sub1", school_id="s1",
        status="pending", total=10, completed=0,
        failed=0, created_by="user1",
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)
    assert t.failed == 0
    assert t.created_by == "user1"
    assert t.error_log is None


async def test_ai_grading_result_new_fields(db):
    r = AIGradingResult(
        task_id="t1", answer_id="a1", question_id="q1", school_id="s1",
        score=8.0, max_score=10.0, feedback="不错",
        confidence=0.9, review_status="pending",
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    assert r.task_id == "t1"
    assert r.question_id == "q1"
    assert r.review_status == "pending"


async def test_teacher_review_new_fields(db):
    r = TeacherReview(
        result_id="r1", reviewer_id="u1", school_id="s1",
        action="override", adjusted_score=7.5, comment="扣分",
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    assert r.result_id == "r1"
    assert r.adjusted_score == 7.5
