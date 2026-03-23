import pytest
from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.knowledge.models import KnowledgePoint
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def kp_setup(client, db):
    """Create school, user, and seed some knowledge points."""
    school = School(name="测试学校", code="KP_TEST")
    db.add(school)
    await db.flush()
    user = User(username="kpadmin", display_name="管理员")
    user.set_password("123456")
    db.add(user)
    await db.commit()
    db.add(UserRole(user_id=user.id, role="admin", school_id=school.id, is_primary=True))
    await db.flush()

    token = create_access_token({"sub": user.id, "school_id": school.id, "role": "admin"})
    headers = {"Authorization": f"Bearer {token}"}

    # Seed knowledge points manually (edu-cloud has no /seed endpoint)
    root = KnowledgePoint(code="MATH_FUNC", name="函数", course_code="SX", level=1)
    child1 = KnowledgePoint(code="MATH_FUNC_CONCEPT", name="函数概念", course_code="SX", level=2)
    child2 = KnowledgePoint(code="MATH_FUNC_ELEM", name="初等函数", course_code="SX", level=2)
    child3 = KnowledgePoint(code="MATH_FUNC_DERIV", name="导数", course_code="SX", level=2)
    db.add_all([root, child1, child2, child3])
    await db.commit()
    # Set parent after commit so IDs are available
    child1.parent_id = root.id
    child2.parent_id = root.id
    child3.parent_id = root.id
    await db.commit()

    return {"headers": headers, "school": school, "root_kp": root}


@pytest.mark.asyncio
async def test_seed_and_list(client, db, kp_setup):
    h = kp_setup["headers"]

    # List root level
    resp = await client.get("/api/v1/knowledge/points?course_code=SX", headers=h)
    assert resp.status_code == 200
    roots = resp.json()
    assert len(roots) >= 1
    assert all(kp["level"] == 1 for kp in roots)

    # Get children
    func_kp = next(kp for kp in roots if kp["code"] == "MATH_FUNC")
    resp = await client.get(f"/api/v1/knowledge/points/{func_kp['id']}/children", headers=h)
    assert resp.status_code == 200
    children = resp.json()
    assert len(children) >= 3  # 函数概念、初等函数、导数


@pytest.mark.asyncio
async def test_get_point_not_found(client, db, kp_setup):
    """GET /points/{id} 不存在返回 404。"""
    h = kp_setup["headers"]
    resp = await client.get("/api/v1/knowledge/points/nonexistent-id", headers=h)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_link_and_query_question_kps(client, db, kp_setup):
    """POST /link + GET /question/{id} 正常流程。"""
    h = kp_setup["headers"]
    school = kp_setup["school"]

    exam = Exam(name="考试", card_title="考试", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    kp = KnowledgePoint(code="API_TEST_KP", name="API测试", course_code="SX", level=1)
    db.add_all([q, kp])
    await db.commit()

    # Link
    resp = await client.post("/api/v1/knowledge/link", headers=h, json={
        "question_id": q.id, "knowledge_point_id": kp.id,
    })
    assert resp.status_code == 200
    assert resp.json()["question_id"] == q.id

    # Query
    resp = await client.get(f"/api/v1/knowledge/question/{q.id}", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["code"] == "API_TEST_KP"


@pytest.mark.asyncio
async def test_question_kps_empty(client, db, kp_setup):
    """GET /question/{id} 无关联返回空列表。"""
    h = kp_setup["headers"]
    school = kp_setup["school"]

    exam = Exam(name="考试2", card_title="考试2", school_id=school.id)
    db.add(exam)
    await db.flush()
    subj = Subject(exam_id=exam.id, name="数学", code="SX2", school_id=school.id)
    db.add(subj)
    await db.flush()
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="subjective", max_score=10)
    db.add(q)
    await db.commit()

    resp = await client.get(f"/api/v1/knowledge/question/{q.id}", headers=h)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(client, db):
    """未认证请求返回 401。"""
    resp = await client.get("/api/v1/knowledge/points?course_code=SX")
    assert resp.status_code in (401, 403)
