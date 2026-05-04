import pytest
from datetime import datetime, timezone

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.models.exam import Exam, Subject, Question
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge
from edu_cloud.shared.auth import create_access_token


def _node(id_, name, course_code="SX"):
    return ConceptGraphNode(
        id=id_, name=name, course_code=course_code,
        node_type="concept", knowledge_level="L1", primary_module="M1",
        synced_at=datetime.now(timezone.utc),
    )


@pytest.fixture
async def kp_setup(client, db):
    """Create school, user, and seed some knowledge points (ConceptGraphNode)."""
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

    # Seed knowledge points (ConceptGraphNode, edge-based hierarchy)
    root = _node("MATH_FUNC_KA", "函数")
    child1 = _node("MATH_FUNC_CONCEPT_KA", "函数概念")
    child2 = _node("MATH_FUNC_ELEM_KA", "初等函数")
    child3 = _node("MATH_FUNC_DERIV_KA", "导数")
    db.add_all([root, child1, child2, child3])
    await db.commit()
    # Build parent-child edges via ConceptGraphEdge
    for child in [child1, child2, child3]:
        db.add(ConceptGraphEdge(
            source_id=root.id, target_id=child.id,
            relation_type="contains",
            synced_at=datetime.now(timezone.utc),
        ))
    await db.commit()

    return {"headers": headers, "school": school, "root_kp": root}


@pytest.mark.asyncio
async def test_seed_and_list(client, db, kp_setup):
    h = kp_setup["headers"]

    # List nodes by course_code
    resp = await client.get("/api/v1/knowledge/points?course_code=SX", headers=h)
    assert resp.status_code == 200
    nodes = resp.json()
    assert len(nodes) >= 1
    # All nodes should have id and name fields
    assert all("id" in kp and "name" in kp for kp in nodes)

    # Get children of root via edge
    root_id = kp_setup["root_kp"].id
    resp = await client.get(f"/api/v1/knowledge/points/{root_id}/children", headers=h)
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
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
    kp = _node("API_TEST_KP_KA", "API测试")
    db.add_all([q, kp])
    await db.commit()

    # Link using new concept_id field
    resp = await client.post("/api/v1/knowledge/link", headers=h, json={
        "question_id": q.id, "concept_id": kp.id,
    })
    assert resp.status_code == 200
    assert resp.json()["question_id"] == q.id

    # Query
    resp = await client.get(f"/api/v1/knowledge/question/{q.id}", headers=h)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == "API_TEST_KP_KA"


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
    q = Question(subject_id=subj.id, school_id=school.id, name="1", question_type="essay", max_score=10)
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
