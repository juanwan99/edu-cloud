import pytest
from edu_cloud.modules.exam.service import update_exam
from edu_cloud.modules.exam.models import Exam


@pytest.mark.asyncio
async def test_update_exam_rejects_published(db):
    """update_exam 不能设置 published 状态——必须走 ExamPublishService.publish()"""
    from edu_cloud.services.exceptions import ValidationError
    exam = Exam(name="Test", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()
    with pytest.raises(ValidationError, match="无效的状态变更"):
        await update_exam(db, exam_id=exam.id, school_id="s1", status="published")


@pytest.mark.asyncio
async def test_update_exam_rejects_archived(db):
    """update_exam 不能设置 archived 状态——必须走 ExamPublishService.archive()"""
    from edu_cloud.services.exceptions import ValidationError
    exam = Exam(name="Test", status="published", school_id="s1")
    db.add(exam)
    await db.flush()
    with pytest.raises(ValidationError, match="无效的状态变更"):
        await update_exam(db, exam_id=exam.id, school_id="s1", status="archived")


@pytest.mark.asyncio
async def test_completed_to_archived_invalid(db):
    """不能跳过 published 直接归档"""
    from edu_cloud.services.exceptions import ValidationError
    exam = Exam(name="Test", status="completed", school_id="s1")
    db.add(exam)
    await db.flush()
    with pytest.raises(ValidationError, match="无效的状态变更"):
        await update_exam(db, exam_id=exam.id, school_id="s1", status="archived")


@pytest.mark.asyncio
async def test_published_to_draft_invalid(db):
    """published 不能回退到 draft"""
    from edu_cloud.services.exceptions import ValidationError
    exam = Exam(name="Test", status="published", school_id="s1")
    db.add(exam)
    await db.flush()
    with pytest.raises(ValidationError, match="无效的状态变更"):
        await update_exam(db, exam_id=exam.id, school_id="s1", status="draft")


@pytest.mark.asyncio
async def test_archived_is_terminal(db):
    """archived 是终态，不能转到任何状态"""
    from edu_cloud.services.exceptions import ValidationError
    exam = Exam(name="Test", status="archived", school_id="s1")
    db.add(exam)
    await db.flush()
    with pytest.raises(ValidationError, match="无效的状态变更"):
        await update_exam(db, exam_id=exam.id, school_id="s1", status="published")


@pytest.mark.asyncio
async def test_existing_transitions_unchanged(db):
    """确保原有转换不受影响"""
    exam = Exam(name="Test", status="draft", school_id="s1")
    db.add(exam)
    await db.flush()
    result = await update_exam(db, exam_id=exam.id, school_id="s1", status="scanning")
    assert result.status == "scanning"
