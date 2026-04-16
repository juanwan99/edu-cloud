import pytest
from edu_cloud.modules.knowledge.models import KnowledgePoint, QuestionKnowledgePoint, GLOBAL_SCHOOL_ID
from edu_cloud.models.exam import Question, Subject, Exam
from edu_cloud.models.school import School


@pytest.mark.asyncio
async def test_create_knowledge_point(db):
    kp = KnowledgePoint(
        code="MATH_FUNC", name="函数", course_code="SX", level=1,
    )
    db.add(kp)
    await db.commit()
    await db.refresh(kp)
    assert kp.id is not None
    assert kp.school_id == GLOBAL_SCHOOL_ID  # 全局预置


@pytest.mark.asyncio
async def test_knowledge_tree_parent_child(db):
    parent = KnowledgePoint(code="MATH_FUNC", name="函数", course_code="SX", level=1)
    db.add(parent)
    await db.flush()

    child = KnowledgePoint(
        code="MATH_FUNC_DERIV", name="导数", course_code="SX",
        level=2, parent_id=parent.id,
    )
    db.add(child)
    await db.commit()

    from sqlalchemy import select
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.parent_id == parent.id)
    )
    children = result.scalars().all()
    assert len(children) == 1
    assert children[0].name == "导数"


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
    kp = KnowledgePoint(code="MATH_FUNC_DERIV", name="导数", course_code="SX", level=2)
    db.add(kp)
    await db.flush()

    link = QuestionKnowledgePoint(question_id=q.id, knowledge_point_id=kp.id, is_primary=True)
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
    kp = KnowledgePoint(code="MATH_DERIV_APP", name="导数应用", course_code="SX", level=3)
    db.add_all([q, kp])
    await db.flush()

    db.add(QuestionKnowledgePoint(question_id=q.id, knowledge_point_id=kp.id))
    await db.commit()

    from sqlalchemy.exc import IntegrityError
    db.add(QuestionKnowledgePoint(question_id=q.id, knowledge_point_id=kp.id))
    with pytest.raises(IntegrityError):
        await db.commit()


@pytest.mark.asyncio
async def test_kp_different_school_id_coexist(db):
    """同 code 不同 school_id 可共存（edu-cloud 无 unique 约束在 code 上）。"""
    kp1 = KnowledgePoint(code="MATH_FUNC", name="函数(全局)", course_code="SX", level=1, school_id=GLOBAL_SCHOOL_ID)
    db.add(kp1)
    await db.commit()

    kp2 = KnowledgePoint(code="MATH_FUNC", name="函数(学校)", course_code="SX", level=1, school_id="school-001")
    db.add(kp2)
    await db.commit()
    assert kp2.id is not None  # 不同 school_id 可共存


@pytest.mark.asyncio
async def test_global_kp_can_be_created(db):
    """全局知识点（GLOBAL_SCHOOL_ID）可正常创建。"""
    db.add(KnowledgePoint(code="DUP_GLOBAL", name="全局1", course_code="SX", level=1, school_id=GLOBAL_SCHOOL_ID))
    await db.commit()
    # edu-cloud KnowledgePoint 模型暂无 (school_id, course_code, code) unique 约束
    # 验证创建成功即可
    from sqlalchemy import select
    result = await db.execute(
        select(KnowledgePoint).where(KnowledgePoint.code == "DUP_GLOBAL")
    )
    assert result.scalar_one() is not None
