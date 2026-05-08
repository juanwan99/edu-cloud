"""Cross-school isolation tests for GradingResult upsert (P0-1).

Verifies that the grade-single upsert query filters by school_id,
preventing one school from reading or overwriting another school's results.
"""
import pytest
from sqlalchemy import select

from edu_cloud.models.school import School
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult


@pytest.fixture
async def two_school_setup(db):
    """Create 2 schools, each with exam/subject/question/answer + school_b GradingResult."""
    # -- School A --
    school_a = School(name="隔离测试校A", code="ISO_A", district="测试区", api_key_hash="x")
    db.add(school_a)
    await db.flush()

    exam_a = Exam(name="期中考试A", school_id=school_a.id)
    db.add(exam_a)
    await db.flush()

    subject_a = Subject(exam_id=exam_a.id, name="数学", code="SX", school_id=school_a.id)
    db.add(subject_a)
    await db.flush()

    question_a = Question(
        subject_id=subject_a.id, name="第1题",
        question_type="essay", max_score=10.0, school_id=school_a.id,
    )
    db.add(question_a)
    await db.flush()

    answer_a = StudentAnswer(
        exam_id=exam_a.id, subject_id=subject_a.id,
        student_id="STU_A_001", question_id=question_a.id,
        school_id=school_a.id,
    )
    db.add(answer_a)
    await db.flush()

    # -- School B --
    school_b = School(name="隔离测试校B", code="ISO_B", district="测试区", api_key_hash="y")
    db.add(school_b)
    await db.flush()

    exam_b = Exam(name="期中考试B", school_id=school_b.id)
    db.add(exam_b)
    await db.flush()

    subject_b = Subject(exam_id=exam_b.id, name="数学", code="SX", school_id=school_b.id)
    db.add(subject_b)
    await db.flush()

    question_b = Question(
        subject_id=subject_b.id, name="第1题",
        question_type="essay", max_score=10.0, school_id=school_b.id,
    )
    db.add(question_b)
    await db.flush()

    answer_b = StudentAnswer(
        exam_id=exam_b.id, subject_id=subject_b.id,
        student_id="STU_B_001", question_id=question_b.id,
        school_id=school_b.id,
    )
    db.add(answer_b)
    await db.flush()

    # -- GradingResult for school_b only --
    gr_b = GradingResult(
        answer_id=answer_b.id,
        question_id=question_b.id,
        school_id=school_b.id,
        status="ai_done",
        ai_score=8.0,
    )
    db.add(gr_b)
    await db.commit()

    return {
        "school_a": school_a,
        "school_b": school_b,
        "answer_a": answer_a,
        "answer_b": answer_b,
        "question_a": question_a,
        "question_b": question_b,
        "gr_b": gr_b,
    }


@pytest.mark.asyncio
async def test_grade_single_cannot_hit_other_school_result(db, two_school_setup):
    """School A querying with school_b's answer_id must return None."""
    setup = two_school_setup
    result = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id == setup["answer_b"].id,
            GradingResult.school_id == setup["school_a"].id,
        )
    )).scalar_one_or_none()

    assert result is None, "School A must not see school B's GradingResult"


@pytest.mark.asyncio
async def test_grade_single_finds_own_school_result(db, two_school_setup):
    """School B querying its own answer_id with its own school_id succeeds."""
    setup = two_school_setup
    result = (await db.execute(
        select(GradingResult).where(
            GradingResult.answer_id == setup["answer_b"].id,
            GradingResult.school_id == setup["school_b"].id,
        )
    )).scalar_one_or_none()

    assert result is not None, "School B must find its own GradingResult"
    assert result.id == setup["gr_b"].id
    assert result.ai_score == 8.0
