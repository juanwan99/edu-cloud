import pytest
import logging
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingTask, GradingResult
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
    q = Question(subject_id=subject.id, name="Q1", question_type="essay", max_score=10.0, school_id=school.id)
    db.add(q)
    await db.commit()

    task = GradingTask(
        subject_id=subject.id, school_id=school.id,
        status="completed", total=3, completed=3, failed=0, created_by=user.id,
    )
    db.add(task)
    await db.commit()

    # 3 students — 覆盖三种 source 分支：ai_done(待审) / ai_override / ai(approve)
    # 统一模型下：final_score 是单一权威源
    cases = [
        ("stu_0", 8.0, 8.0, "ai_done", None),        # AI 已评，未审 → final=ai
        ("stu_1", 6.0, 7.0, "confirmed", "ai_override"),  # 教师改分 → final=7
        ("stu_2", 9.0, 9.0, "confirmed", "ai"),      # 教师确认 → final=ai
    ]
    results = []
    for sid, ai_s, final_s, status, source in cases:
        a = StudentAnswer(
            exam_id=exam.id, subject_id=subject.id, student_id=sid,
            question_id=q.id, image_path=f"/fake/{sid}.png", school_id=school.id,
        )
        db.add(a)
        await db.commit()

        r = GradingResult(
            ai_task_id=task.id, answer_id=a.id, question_id=q.id,
            school_id=school.id, ai_score=ai_s, ai_confidence=0.9, ai_feedback="f",
            final_score=final_s, max_score=10.0,
            status=status, source=source,
            reviewer_id=user.id if status == "confirmed" else None,
        )
        db.add(r)
        await db.commit()
        results.append(r)

    return {
        "school_id": school.id, "exam_id": exam.id,
        "subject_id": subject.id, "question_id": q.id,
        "result_ids": [r.id for r in results],
    }


async def test_effective_scores_missing_final_score(db, analytics_data):
    """final_score=None 的脏数据应被跳过并记录 warning。"""
    from sqlalchemy import select

    # 把 stu_1 的 final_score 清空，模拟脏数据
    r_result = await db.execute(
        select(GradingResult).where(GradingResult.source == "ai_override")
    )
    overridden = r_result.scalar_one()
    overridden.final_score = None
    await db.commit()

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

    # 脏数据被跳过，只剩 2 条
    assert len(scores) == 2
    assert any("final_score" in msg.lower() for msg in captured_warnings)


async def test_effective_scores(db, analytics_data):
    scores = await get_effective_scores(
        db, analytics_data["subject_id"], analytics_data["school_id"]
    )
    assert len(scores) == 3
    score_map = {s["student_id"]: s["effective_score"] for s in scores}
    assert score_map["stu_0"] == 8.0   # AI 预评，待审 → final=8
    assert score_map["stu_1"] == 7.0   # 教师改分 → final=7
    assert score_map["stu_2"] == 9.0   # 教师 approve → final=9


async def test_exam_distribution_uses_school_config(db, analytics_data):
    """exam_distribution 应使用学校配置的分数段而非硬编码。"""
    from edu_cloud.modules.analytics.segment_service import upsert_segment_config
    from edu_cloud.modules.analytics.service import exam_distribution

    school_id = analytics_data["school_id"]
    exam_id = analytics_data["exam_id"]
    await upsert_segment_config(
        db, school_id, boundaries=[50], labels=["通过", "不通过"],
    )
    await db.commit()

    result = await exam_distribution(db, exam_id=exam_id, school_id=school_id)
    labels = [iv["label"] for iv in result["intervals"]]
    assert "通过" in labels
    assert "不通过" in labels
