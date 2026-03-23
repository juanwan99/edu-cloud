"""Knowledge 服务测试 — TG-01 修复。"""
import pytest
from edu_cloud.modules.knowledge.service import (
    create_knowledge_point, list_knowledge_points, get_knowledge_point,
    get_children, link_question, get_question_knowledge_points,
)
from edu_cloud.modules.knowledge.models import KnowledgePoint
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.models.school import School
from edu_cloud.services.exceptions import NotFoundError, ConflictError


@pytest.mark.asyncio
async def test_create_and_list(db):
    """创建知识点 + 列表查询。"""
    kp = await create_knowledge_point(db, code="BIO-1", name="细胞", course_code="BIO")
    assert kp.id is not None
    kps = await list_knowledge_points(db, course_code="BIO")
    assert len(kps) == 1
    assert kps[0].code == "BIO-1"


@pytest.mark.asyncio
async def test_list_empty_course(db):
    """无知识点时返回空。"""
    kps = await list_knowledge_points(db, course_code="NONEXIST")
    assert kps == []


@pytest.mark.asyncio
async def test_get_not_found(db):
    """不存在的知识点 → NotFoundError。"""
    with pytest.raises(NotFoundError):
        await get_knowledge_point(db, kp_id="nonexistent-id")


@pytest.mark.asyncio
async def test_children(db):
    """parent-child 关系。"""
    parent = await create_knowledge_point(db, code="P1", name="生物", course_code="BIO")
    child = await create_knowledge_point(
        db, code="P1-1", name="细胞", course_code="BIO", parent_id=parent.id
    )
    children = await get_children(db, parent_id=parent.id)
    assert len(children) == 1
    assert children[0].code == "P1-1"


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
    q = Question(subject_id=subj.id, name="题1", question_type="objective", max_score=5, school_id=school.id)
    db.add(q)
    await db.flush()
    kp = await create_knowledge_point(db, code="M1", name="代数", course_code="MATH")
    link = await link_question(db, question_id=q.id, knowledge_point_id=kp.id)
    assert link.is_primary is True
    kps = await get_question_knowledge_points(db, question_id=q.id)
    assert len(kps) == 1
    assert kps[0].code == "M1"


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
    q = Question(subject_id=subj.id, name="题1", question_type="objective", max_score=5, school_id=school.id)
    db.add(q)
    await db.flush()
    kp = await create_knowledge_point(db, code="M2", name="几何", course_code="MATH")
    await link_question(db, question_id=q.id, knowledge_point_id=kp.id)
    with pytest.raises(ConflictError):
        await link_question(db, question_id=q.id, knowledge_point_id=kp.id)
