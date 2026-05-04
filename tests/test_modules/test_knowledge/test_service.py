"""Knowledge 服务测试 — 更新为使用 ConceptGraphNode (KNU-011)。"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge
from edu_cloud.modules.knowledge.service import (
    list_knowledge_points, get_knowledge_point,
    get_children, link_question, get_question_knowledge_points,
)
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.models.school import School
from edu_cloud.services.exceptions import ConflictError


def _node(id_: str, name: str, course_code: str = "BIO") -> ConceptGraphNode:
    return ConceptGraphNode(
        id=id_, name=name, knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(timezone.utc),
        course_code=course_code,
    )


@pytest.mark.asyncio
async def test_create_and_list(db):
    """创建节点 + 列表查询。"""
    db.add(_node("BIO-1", "细胞", course_code="BIO"))
    await db.commit()
    kps = await list_knowledge_points(db, course_code="BIO")
    assert len(kps) == 1
    assert kps[0].id == "BIO-1"


@pytest.mark.asyncio
async def test_list_empty_course(db):
    """无知识点时返回空。"""
    kps = await list_knowledge_points(db, course_code="NONEXIST")
    assert kps == []


@pytest.mark.asyncio
async def test_get_not_found(db):
    """不存在的知识点 → 返回 None。"""
    result = await get_knowledge_point(db, kp_id="nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_children(db):
    """parent-child 关系（通过 contains 边）。"""
    parent = _node("P1", "生物")
    child = _node("P1-1", "细胞")
    db.add_all([parent, child])
    await db.flush()
    db.add(ConceptGraphEdge(
        source_id="P1", target_id="P1-1", relation_type="contains",
        synced_at=datetime.now(timezone.utc),
    ))
    await db.commit()
    children = await get_children(db, parent_id="P1")
    assert len(children) == 1
    assert children[0].id == "P1-1"


@pytest.mark.asyncio
async def test_link_question_and_get(db):
    """题目-知识点关联 + 查询。"""
    school = School(name="KP校", code="KP01", district="X")
    db.add(school)
    await db.flush()
    exam = Exam(name="KP考", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, name="题1", question_type="choice", max_score=5, school_id=school.id)
    kp = _node("M1", "代数", course_code="MATH")
    db.add_all([q, kp])
    await db.flush()
    link = await link_question(db, question_id=q.id, concept_id=kp.id)
    assert link.is_primary is True
    kps = await get_question_knowledge_points(db, question_id=q.id)
    assert len(kps) == 1
    assert kps[0].id == "M1"


@pytest.mark.asyncio
async def test_link_question_duplicate(db):
    """重复关联 → ConflictError。"""
    school = School(name="DL校", code="DL01", district="X")
    db.add(school)
    await db.flush()
    exam = Exam(name="DL考", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, name="题1", question_type="choice", max_score=5, school_id=school.id)
    kp = _node("M2", "几何", course_code="MATH")
    db.add_all([q, kp])
    await db.flush()
    await link_question(db, question_id=q.id, concept_id=kp.id)
    with pytest.raises(ConflictError):
        await link_question(db, question_id=q.id, concept_id=kp.id)
