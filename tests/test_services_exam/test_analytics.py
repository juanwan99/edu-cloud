import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, AIGradingResult, TeacherReview
from edu_cloud.modules.analytics import get_effective_scores


@pytest.fixture
async def analytics_data(db):
    school = School(name="AS", code="AS01")
    db.add(school)
    await db.commit()
    user = User(username="t", display_name="T")
    user.set_password("p")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="teacher", school_id=school.id, is_primary=True))
    await db.flush()

    exam = Exam(name="期中", school_id=school.id)
    db.add(exam)
    await db.commit()
    subject = Subject(exam_id=exam.id, name="语文", code="chinese", school_id=school.id)
    db.add(subject)
    await db.commit()
    q = Question(subject_id=subject.id, name="Q1", question_type="subjective", max_score=10.0, school_id=school.id)
    db.add(q)
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="completed", total=3, completed=3, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.commit()

    # 3 students, different scores
    results = []
    for i, (score, review) in enumerate([
        (8.0, None),           # AI score accepted
        (6.0, ("override", 7.0)),  # teacher overridden to 7.0
        (9.0, ("approve", None)),  # teacher approved AI score
    ]):
        a = StudentAnswer(
            exam_id=exam.id, subject_id=subject.id, student_id=f"stu_{i}",
            question_id=q.id, image_path=f"/fake/{i}.png", school_id=school.id,
        )
        db.add(a)
        await db.commit()

        r = AIGradingResult(
            task_id=task.id, answer_id=a.id, question_id=q.id,
            school_id=school.id, score=score, max_score=10.0,
            feedback="f", confidence=0.9,
            review_status="overridden" if review and review[0] == "override" else (
                "approved" if review and review[0] == "approve" else "pending"
            ),
        )
        db.add(r)
        await db.commit()

        if review:
            tr = TeacherReview(
                result_id=r.id, reviewer_id=user.id, school_id=school.id,
                action=review[0], adjusted_score=review[1],
            )
            db.add(tr)
            await db.commit()

        results.append(r)

    return {
        "school_id": school.id, "exam_id": exam.id,
        "subject_id": subject.id, "question_id": q.id,
        "result_ids": [r.id for r in results],
    }


import logging


async def test_effective_scores_overridden_null_adjusted(db, analytics_data):
    """overridden 但 adjusted_score=None 的脏数据应记录 warning 并回退 AI 分"""
    from edu_cloud.modules.grading.models import AIGradingResult, TeacherReview
    from sqlalchemy import select

    # 找到 overridden 的 result（stu_1），把其 TeacherReview.adjusted_score 设为 None
    r_result = await db.execute(
        select(AIGradingResult).where(AIGradingResult.review_status == "overridden")
    )
    overridden_result = r_result.scalar_one()
    tr_result = await db.execute(
        select(TeacherReview).where(TeacherReview.result_id == overridden_result.id)
    )
    tr = tr_result.scalar_one()
    tr.adjusted_score = None
    await db.commit()

    # Use a custom handler to capture warnings (caplog may not work when
    # edu-cloud's logging_config.py has already configured handlers)
    captured_warnings = []
    analytics_logger = logging.getLogger("edu_cloud.modules.analytics")

    class _CapHandler(logging.Handler):
        def emit(self, record):
            captured_warnings.append(record.getMessage())

    cap = _CapHandler()
    cap.setLevel(logging.WARNING)
    analytics_logger.addHandler(cap)
    try:
        scores = await get_effective_scores(
            db, analytics_data["subject_id"], analytics_data["school_id"]
        )
    finally:
        analytics_logger.removeHandler(cap)

    score_map = {s["student_id"]: s["effective_score"] for s in scores}
    # 回退到 AI 分 6.0
    assert score_map["stu_1"] == 6.0
    # 必须有 warning 日志
    assert any("overridden" in msg.lower() and "adjusted_score" in msg.lower() for msg in captured_warnings)


async def test_effective_scores(db, analytics_data):
    scores = await get_effective_scores(
        db, analytics_data["subject_id"], analytics_data["school_id"]
    )
    # scores: list of {student_id, question_id, effective_score}
    assert len(scores) == 3
    score_map = {s["student_id"]: s["effective_score"] for s in scores}
    assert score_map["stu_0"] == 8.0   # AI score (pending review)
    assert score_map["stu_1"] == 7.0   # teacher override
    assert score_map["stu_2"] == 9.0   # teacher approved → AI score
