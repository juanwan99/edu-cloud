import pytest
from edu_cloud.modules.knowledge.models import KnowledgePoint
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.models.school import School
from edu_cloud.modules.knowledge import service as knowledge_service
from edu_cloud.services.exceptions import NotFoundError, ConflictError
from edu_cloud.modules.knowledge.models import GLOBAL_SCHOOL_ID


@pytest.mark.asyncio
async def test_list_root_knowledge_points(db):
    db.add(KnowledgePoint(code="MATH_FUNC", name="函数", course_code="SX", level=1))
    db.add(KnowledgePoint(code="MATH_GEOM", name="几何", course_code="SX", level=1))
    db.add(KnowledgePoint(code="ENG_READ", name="阅读", course_code="YY", level=1))
    await db.commit()

    result = await knowledge_service.list_knowledge_points(db, course_code="SX")
    assert len(result) == 2
    assert result[0].code == "MATH_FUNC"


@pytest.mark.asyncio
async def test_get_children(db):
    parent = KnowledgePoint(code="MATH_FUNC", name="函数", course_code="SX", level=1)
    db.add(parent)
    await db.flush()
    db.add(KnowledgePoint(code="MATH_FUNC_DERIV", name="导数", course_code="SX", level=2, parent_id=parent.id))
    db.add(KnowledgePoint(code="MATH_FUNC_ELEM", name="初等函数", course_code="SX", level=2, parent_id=parent.id))
    await db.commit()

    children = await knowledge_service.get_children(db, parent_id=parent.id)
    assert len(children) == 2


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
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    kp = KnowledgePoint(code="MATH_DERIV", name="导数", course_code="SX", level=2)
    db.add_all([q, kp])
    await db.flush()

    await knowledge_service.link_question(db, question_id=q.id, knowledge_point_id=kp.id)

    kps = await knowledge_service.get_question_knowledge_points(db, question_id=q.id)
    assert len(kps) == 1
    assert kps[0].name == "导数"


@pytest.mark.asyncio
async def test_list_with_school_id_filter(db):
    """DF-003: 查询返回全局(NULL) + 本校知识点。"""
    db.add(KnowledgePoint(code="MATH_FUNC", name="函数(全局)", course_code="SX", level=1, school_id=GLOBAL_SCHOOL_ID))
    db.add(KnowledgePoint(code="MATH_FUNC", name="函数(学校A)", course_code="SX", level=1, school_id="school-a"))
    db.add(KnowledgePoint(code="MATH_FUNC", name="函数(学校B)", course_code="SX", level=1, school_id="school-b"))
    await db.commit()

    result = await knowledge_service.list_knowledge_points(db, course_code="SX", school_id="school-a")
    assert len(result) == 2  # 全局 + school-a
    names = {kp.name for kp in result}
    assert "函数(全局)" in names
    assert "函数(学校A)" in names


@pytest.mark.asyncio
async def test_create_knowledge_point(db):
    """TG-001: 验证 create_knowledge_point 正常创建。"""
    kp = await knowledge_service.create_knowledge_point(
        db, code="TEST_CREATE", name="测试创建", course_code="SX", level=1,
    )
    assert kp.id is not None
    assert kp.code == "TEST_CREATE"
    assert kp.school_id == GLOBAL_SCHOOL_ID


@pytest.mark.asyncio
async def test_create_knowledge_point_with_school(db):
    kp = await knowledge_service.create_knowledge_point(
        db, code="TEST_SCHOOL", name="学校知识点", course_code="SX",
        level=1, school_id="school-x",
    )
    assert kp.school_id == "school-x"


@pytest.mark.asyncio
async def test_get_knowledge_point_found(db):
    """TG-001: get 正常命中。"""
    kp = KnowledgePoint(code="GET_TEST", name="获取测试", course_code="SX", level=1)
    db.add(kp)
    await db.commit()

    result = await knowledge_service.get_knowledge_point(db, kp_id=kp.id)
    assert result.code == "GET_TEST"


@pytest.mark.asyncio
async def test_get_knowledge_point_not_found(db):
    """TG-001: get 不存在抛 NotFoundError。"""
    with pytest.raises(NotFoundError):
        await knowledge_service.get_knowledge_point(db, kp_id="nonexistent-id")


@pytest.mark.asyncio
async def test_get_question_kps_empty(db):
    """TG-001: 题目无关联知识点返回空列表。"""
    school = School(name="测试", code="T_EMPTY")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    db.add(q)
    await db.commit()

    kps = await knowledge_service.get_question_knowledge_points(db, question_id=q.id)
    assert kps == []


@pytest.mark.asyncio
async def test_duplicate_link_raises_conflict(db):
    """R2-002: 重复 link 抛 ConflictError。"""
    school = School(name="测试", code="T_DUP")
    db.add(school)
    await db.flush()
    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    kp = KnowledgePoint(code="DUP_TEST", name="重复测试", course_code="SX", level=1)
    db.add_all([q, kp])
    await db.flush()

    await knowledge_service.link_question(db, question_id=q.id, knowledge_point_id=kp.id)

    with pytest.raises(ConflictError):
        await knowledge_service.link_question(db, question_id=q.id, knowledge_point_id=kp.id)


@pytest.mark.asyncio
async def test_get_knowledge_point_cross_tenant_blocked(db):
    """R2-001: 跨租户读取学校级知识点返回 NotFoundError。"""
    kp = KnowledgePoint(code="SCHOOL_A_KP", name="学校A", course_code="SX", level=1, school_id="school-a")
    db.add(kp)
    await db.commit()

    # school-b 用户尝试读取 school-a 的知识点
    with pytest.raises(NotFoundError):
        await knowledge_service.get_knowledge_point(db, kp_id=kp.id, school_id="school-b")

    # 全局知识点可被任何学校读取
    global_kp = KnowledgePoint(code="GLOBAL_KP", name="全局", course_code="SX", level=1, school_id=GLOBAL_SCHOOL_ID)
    db.add(global_kp)
    await db.commit()
    result = await knowledge_service.get_knowledge_point(db, kp_id=global_kp.id, school_id="school-b")
    assert result.code == "GLOBAL_KP"
