import pytest
from edu_cloud.modules.grading.models import Rubric, GradingTask, GradingResult


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


async def test_grading_result_ai_path(db):
    """AI 阅卷路径 — worker 写入 status=ai_done。"""
    r = GradingResult(
        ai_task_id="t1", answer_id="a1", question_id="q1", school_id="s1",
        ai_score=8.0, ai_confidence=0.9, ai_feedback="不错",
        final_score=8.0, max_score=10.0,
        status="ai_done",
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    assert r.ai_task_id == "t1"
    assert r.question_id == "q1"
    assert r.status == "ai_done"
    assert r.source is None  # 待教师审核
    assert r.version == 1


async def test_grading_result_teacher_override(db):
    """教师改分后 — source='ai_override', status='confirmed', final_score 已改。"""
    r = GradingResult(
        ai_task_id="t1", answer_id="a2", question_id="q1", school_id="s1",
        ai_score=8.0, max_score=10.0,
        final_score=7.5, status="confirmed", source="ai_override",
        reviewer_id="u1", review_comment="扣分",
        version=2,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    assert r.source == "ai_override"
    assert r.final_score == 7.5
    assert r.reviewer_id == "u1"
    assert r.version == 2


async def test_grading_result_manual_path(db):
    """纯人工评分 — ai_score=None, source='manual'。"""
    r = GradingResult(
        answer_id="a3", question_id="q1", school_id="s1",
        final_score=9.0, max_score=10.0,
        status="confirmed", source="manual",
        reviewer_id="u1",
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    assert r.ai_score is None
    assert r.source == "manual"
    assert r.final_score == 9.0
