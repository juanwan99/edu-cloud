import pytest
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
    """GradingResult.final_score=None + StudentAnswer.score=None → 跳过该行。"""
    from sqlalchemy import select

    r_result = await db.execute(
        select(GradingResult).where(GradingResult.source == "ai_override")
    )
    overridden = r_result.scalar_one()
    overridden.final_score = None
    await db.commit()

    scores = await get_effective_scores(
        db, analytics_data["subject_id"], analytics_data["school_id"]
    )

    # COALESCE(NULL, NULL) = NULL → 跳过，只剩 2 条
    assert len(scores) == 2


async def test_effective_scores(db, analytics_data):
    scores = await get_effective_scores(
        db, analytics_data["subject_id"], analytics_data["school_id"]
    )
    assert len(scores) == 3
    score_map = {s["student_id"]: s["effective_score"] for s in scores}
    assert score_map["stu_0"] == 8.0   # AI 预评，待审 → final=8
    assert score_map["stu_1"] == 7.0   # 教师改分 → final=7
    assert score_map["stu_2"] == 9.0   # 教师 approve → final=9


async def test_effective_scores_excludes_absent_answers(db, analytics_data):
    absent = StudentAnswer(
        exam_id=analytics_data["exam_id"],
        subject_id=analytics_data["subject_id"],
        student_id="absent-student",
        question_id=analytics_data["question_id"],
        school_id=analytics_data["school_id"],
        score=10.0,
        is_absent=True,
    )
    db.add(absent)
    await db.commit()

    scores = await get_effective_scores(
        db, analytics_data["subject_id"], analytics_data["school_id"]
    )

    assert {s["student_id"] for s in scores} == {"stu_0", "stu_1", "stu_2"}


async def test_exam_distribution_uses_default_segments(db, analytics_data):
    """exam_distribution 使用硬编码默认分数段（学校自定义配置已废弃，见 segment_service）。"""
    from edu_cloud.modules.analytics.segment_service import DEFAULT_LABELS
    from edu_cloud.modules.analytics.service import exam_distribution

    school_id = analytics_data["school_id"]
    exam_id = analytics_data["exam_id"]

    result = await exam_distribution(db, exam_id=exam_id, school_id=school_id)
    labels = [iv["label"] for iv in result["intervals"]]
    assert labels == DEFAULT_LABELS


def test_effective_score_read_model_lives_in_shared_service():
    """D-03F: effective-score read model authority is module-external shared service.

    The analytics package (and the analytics.service module the AI tools import
    from) only re-export the shared implementation, so the cross-module model
    imports no longer live inside the analytics package.
    """
    import edu_cloud.modules.analytics as analytics_pkg
    import edu_cloud.modules.analytics.service as analytics_service
    from edu_cloud.services import effective_scores as shared

    # Shared service is the authority for both public entry points.
    assert analytics_pkg.get_effective_scores is shared.get_effective_scores
    assert analytics_pkg.get_effective_scores_batch is shared.get_effective_scores_batch
    # AI-tool import path (analytics.service.get_effective_scores) stays compatible.
    assert analytics_service.get_effective_scores is shared.get_effective_scores
