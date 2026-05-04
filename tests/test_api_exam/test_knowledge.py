import pytest
from datetime import datetime, timezone
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint, GLOBAL_SCHOOL_ID
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.models.exam import Question, Subject, Exam
from edu_cloud.models.school import School


def _make_node(id_, name, course_code="SX"):
    return ConceptGraphNode(
        id=id_, name=name, course_code=course_code,
        node_type="concept", knowledge_level="L1", primary_module="M1",
        synced_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_create_knowledge_point(db):
    kp = _make_node("MATH_FUNC", "函数")
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    assert kp.id == "MATH_FUNC"


@pytest.mark.asyncio
async def test_knowledge_tree_parent_child(db):
    """ConceptGraphNode hierarchy is via ConceptGraphEdge, not parent_id.
    This test verifies two nodes can be created independently."""
    parent = _make_node("MATH_FUNC_P", "函数(父)")
    db.add(parent)
    await db.flush()

    child = _make_node("MATH_FUNC_DERIV_P", "导数(子)")
    db.add(child)
    await db.commit()

    from sqlalchemy import select
    result = await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.id == "MATH_FUNC_DERIV_P")
    )
    node = result.scalar_one()
    assert node.name == "导数(子)"


@pytest.mark.asyncio
async def test_link_question_to_knowledge_point(db):
    school = School(name="测试学校", code="T01")
    db.add(school)
    await db.flush()

    exam = Exam(name="测试考试", card_title="测试", school_id=school.id)
    db.add(exam)
    await db.flush()

    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()

    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    db.add(q)
    kp = _make_node("MATH_FUNC_DERIV_L", "导数")
    db.add(kp)
    await db.flush()

    link = QuestionKnowledgePoint(question_id=q.id, concept_id=kp.id, is_primary=True)
    db.add(link)
    await db.commit()
    assert link.id is not None


@pytest.mark.asyncio
async def test_question_kp_unique_constraint(db):
    school = School(name="测试学校", code="T02")
    db.add(school)
    await db.flush()
    exam = Exam(name="测试考试", card_title="测试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    kp = _make_node("MATH_DERIV_APP_U", "导数应用")
    db.add_all([q, kp])
    await db.flush()

    db.add(QuestionKnowledgePoint(question_id=q.id, concept_id=kp.id))
    await db.commit()

    from sqlalchemy.exc import IntegrityError
    db.add(QuestionKnowledgePoint(question_id=q.id, concept_id=kp.id))
    with pytest.raises(IntegrityError):
        await db.commit()


@pytest.mark.asyncio
async def test_kp_different_id_coexist(db):
    """Different ConceptGraphNode IDs can coexist in the same course."""
    kp1 = _make_node("MATH_FUNC_G1", "函数(全局)")
    db.add(kp1)
    await db.commit()

    kp2 = _make_node("MATH_FUNC_S1", "函数(学校)")
    db.add(kp2)
    await db.commit()
    assert kp2.id is not None


@pytest.mark.asyncio
async def test_global_kp_can_be_created(db):
    """ConceptGraphNode with a global-style ID can be created."""
    db.add(_make_node("DUP_GLOBAL_C", "全局1"))
    await db.commit()

    from sqlalchemy import select
    result = await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.id == "DUP_GLOBAL_C")
    )
    assert result.scalar_one() is not None
