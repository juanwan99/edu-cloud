"""Knowledge service tests — updated to use ConceptGraphNode (KNU-011)."""
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.models.school import School
from edu_cloud.modules.knowledge import service as knowledge_service
from edu_cloud.services.exceptions import NotFoundError, ConflictError


def _make_node(code: str, name: str, course_code: str = "SX") -> ConceptGraphNode:
    return ConceptGraphNode(
        id=code, name=name, knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(timezone.utc),
        course_code=course_code,
    )


@pytest.mark.asyncio
async def test_list_root_knowledge_points(db):
    db.add(_make_node("MATH_FUNC", "函数"))
    db.add(_make_node("MATH_GEOM", "几何"))
    db.add(_make_node("ENG_READ", "阅读", course_code="YY"))
    await db.commit()

    result = await knowledge_service.list_knowledge_points(db, course_code="SX")
    assert len(result) == 2
    codes = {r.id for r in result}
    assert "MATH_FUNC" in codes


@pytest.mark.asyncio
async def test_link_question_and_query(db):
    school = School(name="测试", code="T03")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    kp = _make_node("MATH_DERIV", "导数")
    db.add_all([q, kp])
    await db.flush()

    await knowledge_service.link_question(db, question_id=q.id, concept_id=kp.id)

    kps = await knowledge_service.get_question_knowledge_points(db, question_id=q.id)
    assert len(kps) == 1
    assert kps[0].name == "导数"


@pytest.mark.asyncio
async def test_get_knowledge_point_found(db):
    kp = _make_node("GET_TEST", "获取测试")
    db.add(kp)
    await db.commit()

    result = await knowledge_service.get_knowledge_point(db, kp_id=kp.id)
    assert result.id == "GET_TEST"


@pytest.mark.asyncio
async def test_get_knowledge_point_not_found(db):
    result = await knowledge_service.get_knowledge_point(db, kp_id="nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_get_question_kps_empty(db):
    school = School(name="测试", code="T_EMPTY")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    db.add(q)
    await db.commit()

    kps = await knowledge_service.get_question_knowledge_points(db, question_id=q.id)
    assert kps == []


@pytest.mark.asyncio
async def test_duplicate_link_raises_conflict(db):
    school = School(name="测试", code="T_DUP")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    kp = _make_node("DUP_TEST", "重复测试")
    db.add_all([q, kp])
    await db.flush()

    await knowledge_service.link_question(db, question_id=q.id, concept_id=kp.id)

    with pytest.raises(ConflictError):
        await knowledge_service.link_question(db, question_id=q.id, concept_id=kp.id)
