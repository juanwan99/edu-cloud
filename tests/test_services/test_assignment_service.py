import pytest
from edu_cloud.modules.grading.models import GradingAssignment, GradingQualityCheck
from edu_cloud.modules.exam.models import Exam, Subject


@pytest.mark.asyncio
async def test_create_grading_assignment(db):
    exam = Exam(name="期中考试", status="grading", school_id="s1")
    db.add(exam)
    await db.flush()

    assignment = GradingAssignment(
        exam_id=exam.id, subject_id="sub-1",
        question_ids=["q1", "q2", "q3"],
        assigned_to="teacher-1",
        total_count=120,
        school_id="s1",
    )
    db.add(assignment)
    await db.flush()
    assert assignment.id is not None
    assert assignment.status == "pending"
    assert assignment.graded_count == 0
    assert assignment.is_second_grading is False


@pytest.mark.asyncio
async def test_create_quality_check(db):
    check = GradingQualityCheck(
        exam_id="exam-1", subject_id="sub-1", question_id="q-1",
        check_type="sampling",
        original_score=8.0,
        school_id="s1",
    )
    db.add(check)
    await db.flush()
    assert check.id is not None
    assert check.status == "pending"
    assert check.checker_id is None
    assert check.check_score is None


@pytest.mark.asyncio
async def test_quality_check_types():
    """check_type 必须是有效值"""
    for ct in ["sampling", "consistency", "deviation"]:
        check = GradingQualityCheck(
            exam_id="e", subject_id="s", question_id="q",
            check_type=ct, original_score=5.0, school_id="s1",
        )
        assert check.check_type == ct


@pytest.mark.asyncio
async def test_assignment_status_default(db):
    a = GradingAssignment(
        exam_id="e", subject_id="s", question_ids=["q1"],
        assigned_to="t1", total_count=10, school_id="s1",
    )
    db.add(a)
    await db.flush()
    assert a.status == "pending"
    assert a.started_at is None
    assert a.completed_at is None
