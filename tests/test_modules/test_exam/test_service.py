"""ExamService 服务测试 — TG-02 修复。"""
import pytest
from sqlalchemy.exc import IntegrityError as SAIntegrityError

from edu_cloud.modules.exam.service import (
    create_exam, list_exams, get_exam, update_exam,
    create_subject, list_subjects, list_questions,
)
from edu_cloud.modules.exam.models import Exam, Question
from edu_cloud.models.school import School
from edu_cloud.services.exceptions import NotFoundError, ValidationError, ConflictError


@pytest.mark.asyncio
async def test_create_exam_basic(db):
    school = School(name="Svc校", code="SVC01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="期中", card_title="CT", school_id=school.id)
    assert exam.name == "期中"
    assert exam.school_id == school.id
    assert exam.status == "draft"


@pytest.mark.asyncio
async def test_list_exams_school_filter(db):
    """跨校隔离：list_exams 只返回本校。"""
    s1 = School(name="A", code="LS_A", district="X")
    s2 = School(name="B", code="LS_B", district="X")
    db.add_all([s1, s2])
    await db.flush()
    await create_exam(db, name="A考", card_title="A", school_id=s1.id)
    await create_exam(db, name="B考", card_title="B", school_id=s2.id)
    exams = await list_exams(db, school_id=s1.id)
    assert len(exams) == 1
    assert exams[0].name == "A考"


@pytest.mark.asyncio
async def test_get_exam_wrong_school(db):
    """错误 school_id → NotFoundError。"""
    s1 = School(name="C", code="GE_C", district="X")
    s2 = School(name="D", code="GE_D", district="X")
    db.add_all([s1, s2])
    await db.flush()
    exam = await create_exam(db, name="C考", card_title="C", school_id=s1.id)
    with pytest.raises(NotFoundError):
        await get_exam(db, exam_id=exam.id, school_id=s2.id)


@pytest.mark.asyncio
async def test_update_exam_invalid_transition(db):
    """非法状态转换 → ValidationError。"""
    school = School(name="ST", code="ST01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="状态测试", card_title="ST", school_id=school.id)
    # draft → completed 不合法
    with pytest.raises(ValidationError, match="无效的状态变更"):
        await update_exam(db, exam_id=exam.id, school_id=school.id, status="completed")


@pytest.mark.asyncio
async def test_update_exam_valid_transition(db):
    """合法状态转换 draft → scanning。"""
    school = School(name="VT", code="VT01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="合法转换", card_title="VT", school_id=school.id)
    updated = await update_exam(db, exam_id=exam.id, school_id=school.id, status="scanning")
    assert updated.status == "scanning"


@pytest.mark.asyncio
async def test_update_exam_full_lifecycle(db):
    """完整状态链 draft→scanning→grading→reviewing→completed。"""
    school = School(name="LC", code="LC01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="生命周期", card_title="LC", school_id=school.id)
    for status in ["scanning", "grading", "reviewing", "completed"]:
        exam = await update_exam(db, exam_id=exam.id, school_id=school.id, status=status)
        assert exam.status == status


@pytest.mark.asyncio
async def test_update_exam_completed_pipeline_error_rollback(db):
    """C-3: pipeline 失败时回滚到 reviewing，允许用户重试。"""
    from unittest.mock import patch, AsyncMock
    school = School(name="PF", code="PF01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="Pipeline测试", card_title="PF", school_id=school.id)
    for status in ["scanning", "grading", "reviewing"]:
        exam = await update_exam(db, exam_id=exam.id, school_id=school.id, status=status)
    with patch("edu_cloud.modules.pipeline.service.run_full_pipeline", new_callable=AsyncMock, side_effect=RuntimeError("pipeline boom")):
        exam = await update_exam(db, exam_id=exam.id, school_id=school.id, status="completed")
        assert exam.status == "reviewing"


@pytest.mark.asyncio
async def test_create_subject_duplicate(db):
    """重复 subject code → ConflictError。"""
    school = School(name="DU", code="DU01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="重复测试", card_title="DU", school_id=school.id)
    await create_subject(db, exam_id=exam.id, name="语文", code="YW", school_id=school.id)
    with pytest.raises(ConflictError):
        await create_subject(db, exam_id=exam.id, name="语文2", code="YW", school_id=school.id)


@pytest.mark.asyncio
async def test_list_subjects_empty(db):
    """无科目时返回空列表。"""
    school = School(name="EM", code="EM01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="空科目", card_title="EM", school_id=school.id)
    subjects = await list_subjects(db, exam_id=exam.id, school_id=school.id)
    assert subjects == []


@pytest.mark.asyncio
async def test_list_questions_empty(db):
    """无题目时返回空列表。"""
    school = School(name="EQ", code="EQ01", district="X")
    db.add(school)
    await db.flush()
    exam = await create_exam(db, name="空题目", card_title="EQ", school_id=school.id)
    subj = await create_subject(db, exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    questions = await list_questions(db, subject_id=subj.id, school_id=school.id)
    assert questions == []
