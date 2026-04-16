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


# ── Service tests ──

from edu_cloud.modules.grading.assignment_service import GradingAssignmentService


@pytest.mark.asyncio
async def test_assign_block(db):
    result = await GradingAssignmentService.assign_block(
        db, exam_id="e1", subject_id="s1",
        question_ids=["q1", "q2"], teacher_id="t1", school_id="s1",
        total_count=10,
    )
    assert result.assigned_to == "t1"
    assert result.question_ids == ["q1", "q2"]
    assert result.total_count == 10
    assert result.status == "pending"


@pytest.mark.asyncio
async def test_update_progress_start(db):
    a = GradingAssignment(
        exam_id="e1", subject_id="s1", question_ids=["q1"],
        assigned_to="t1", total_count=10, school_id="s1",
    )
    db.add(a)
    await db.flush()

    result = await GradingAssignmentService.update_progress(db, a.id, graded_count=1)
    assert result.status == "in_progress"
    assert result.started_at is not None


@pytest.mark.asyncio
async def test_update_progress_complete(db):
    a = GradingAssignment(
        exam_id="e1", subject_id="s1", question_ids=["q1"],
        assigned_to="t1", total_count=5, school_id="s1",
    )
    db.add(a)
    await db.flush()

    result = await GradingAssignmentService.update_progress(db, a.id, graded_count=5)
    assert result.status == "completed"
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_update_progress_zero_total_empty_assignment(db):
    """F-06: total_count=0 且 question_ids=[] 表示无答卷需批改，直接 completed"""
    a = GradingAssignment(
        exam_id="e1", subject_id="s1", question_ids=[],
        assigned_to="t1", total_count=0, school_id="s1",
    )
    db.add(a)
    await db.flush()

    result = await GradingAssignmentService.update_progress(db, a.id, graded_count=0)
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_get_progress(db):
    for i in range(3):
        a = GradingAssignment(
            exam_id="e1", subject_id="s1", question_ids=[f"q{i}"],
            assigned_to=f"t{i}", total_count=10, graded_count=10 if i < 2 else 3,
            status="completed" if i < 2 else "in_progress",
            school_id="s1",
        )
        db.add(a)
    await db.flush()

    progress = await GradingAssignmentService.get_progress(db, "e1", school_id="s1")
    assert progress["total_assignments"] == 3
    assert progress["completed"] == 2
    assert progress["in_progress"] == 1
    assert progress["graded_papers"] == 23
    assert progress["total_papers"] == 30


@pytest.mark.asyncio
async def test_list_assignments(db):
    for i in range(2):
        db.add(GradingAssignment(
            exam_id="e1", subject_id="s1", question_ids=[f"q{i}"],
            assigned_to=f"t{i}", total_count=10, school_id="s1",
        ))
    db.add(GradingAssignment(
        exam_id="e2", subject_id="s1", question_ids=["q0"],
        assigned_to="t0", total_count=5, school_id="s1",
    ))
    await db.flush()

    result = await GradingAssignmentService.list_assignments(db, exam_id="e1", school_id="s1")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_assign_block_duplicate_rejected(db):
    """N-01: 同科目未完成任务的题目重叠时应抛 ConflictError"""
    from edu_cloud.services.exceptions import ConflictError
    await GradingAssignmentService.assign_block(
        db, exam_id="e1", subject_id="s1",
        question_ids=["q1", "q2"], teacher_id="t1", school_id="s1", total_count=10,
    )
    with pytest.raises(ConflictError):
        await GradingAssignmentService.assign_block(
            db, exam_id="e1", subject_id="s1",
            question_ids=["q2", "q3"], teacher_id="t2", school_id="s1", total_count=10,
        )
