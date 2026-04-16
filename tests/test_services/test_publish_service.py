import pytest
from edu_cloud.modules.exam.publish_service import ExamPublishService
from edu_cloud.modules.exam.models import Exam
from edu_cloud.modules.grading.models import GradingAssignment, GradingQualityCheck
from edu_cloud.services.exceptions import StateError


@pytest.mark.asyncio
async def test_publish_success(db):
    exam = Exam(name="Test", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()

    result = await ExamPublishService.publish(db, exam_id=exam.id, school_id="s1")
    assert result["status"] == "published"

    await db.refresh(exam)
    assert exam.status == "published"


@pytest.mark.asyncio
async def test_publish_wrong_status(db):
    exam = Exam(name="Test", status="grading", school_id="s1")
    db.add(exam)
    await db.flush()

    with pytest.raises(StateError, match="Cannot publish"):
        await ExamPublishService.publish(db, exam_id=exam.id, school_id="s1")


@pytest.mark.asyncio
async def test_publish_blocks_on_incomplete_assignments(db):
    exam = Exam(name="Test", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()

    db.add(GradingAssignment(
        exam_id=exam.id, subject_id="s1", question_ids=["q1"],
        assigned_to="t1", total_count=10, graded_count=5,
        status="in_progress", school_id="s1",
    ))
    await db.flush()

    with pytest.raises(StateError, match="grading assignments not completed"):
        await ExamPublishService.publish(db, exam_id=exam.id, school_id="s1")


@pytest.mark.asyncio
async def test_publish_blocks_on_high_severity(db):
    exam = Exam(name="Test", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()

    db.add(GradingQualityCheck(
        exam_id=exam.id, subject_id="s1", question_id="q1",
        check_type="sampling", original_score=8.0, check_score=2.0,
        deviation=6.0, severity="high", status="reviewed", school_id="s1",
    ))
    await db.flush()

    with pytest.raises(StateError, match="high-severity quality issues"):
        await ExamPublishService.publish(db, exam_id=exam.id, school_id="s1")


@pytest.mark.asyncio
async def test_publish_wrong_school(db):
    """F-02: 跨校访问必须被拒绝"""
    from edu_cloud.services.exceptions import NotFoundError
    exam = Exam(name="Test", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()
    with pytest.raises(NotFoundError):
        await ExamPublishService.publish(db, exam_id=exam.id, school_id="wrong-school")


@pytest.mark.asyncio
async def test_archive_success(db):
    exam = Exam(name="Test", status="published", school_id="s1")
    db.add(exam)
    await db.flush()

    await ExamPublishService.archive(db, exam_id=exam.id, school_id="s1")
    await db.refresh(exam)
    assert exam.status == "archived"


@pytest.mark.asyncio
async def test_archive_wrong_status(db):
    exam = Exam(name="Test", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()

    with pytest.raises(StateError, match="Cannot archive"):
        await ExamPublishService.archive(db, exam_id=exam.id, school_id="s1")


@pytest.mark.asyncio
async def test_archive_wrong_school(db):
    """F-02: 归档也必须校验 school_id"""
    from edu_cloud.services.exceptions import NotFoundError
    exam = Exam(name="Test", status="published", school_id="s1")
    db.add(exam)
    await db.flush()
    with pytest.raises(NotFoundError):
        await ExamPublishService.archive(db, exam_id=exam.id, school_id="wrong-school")
