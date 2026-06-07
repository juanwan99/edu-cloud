"""Knowledge link_question / get_question_kps 跨校隔离测试。

验证：school-scoped 用户只能操作本校 Question，不能跨校 link 或查询知识点。
"""
import pytest
from datetime import datetime, timezone

from edu_cloud.models.school import School
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode
from edu_cloud.shared.auth import create_access_token

from tests._module_seed import enable_school_modules


@pytest.fixture
async def two_schools(db):
    """Create two schools with an academic_director user in each."""
    school_a = School(name="隔离校A", code="ISO_A", district="测试区", api_key_hash="x")
    school_b = School(name="隔离校B", code="ISO_B", district="测试区", api_key_hash="x")
    db.add_all([school_a, school_b])
    await db.flush()

    user_a = User(username="director_a", display_name="主任A")
    user_a.set_password("test123")
    user_b = User(username="director_b", display_name="主任B")
    user_b.set_password("test123")
    db.add_all([user_a, user_b])
    await db.flush()

    role_a = UserRole(
        user_id=user_a.id, role="academic_director",
        school_id=school_a.id, is_primary=True,
    )
    role_b = UserRole(
        user_id=user_b.id, role="academic_director",
        school_id=school_b.id, is_primary=True,
    )
    db.add_all([role_a, role_b])
    await db.flush()

    # Create exam + subject + question in school A
    exam_a = Exam(name="隔离考试", school_id=school_a.id)
    db.add(exam_a)
    await db.flush()

    subj_a = Subject(
        exam_id=exam_a.id, name="数学", code="SX", school_id=school_a.id,
    )
    db.add(subj_a)
    await db.flush()

    q_a = Question(
        subject_id=subj_a.id, name="Q1", question_type="essay",
        max_score=10, school_id=school_a.id,
    )
    db.add(q_a)
    await db.flush()

    # Create a ConceptGraphNode (global, no school_id)
    node = ConceptGraphNode(
        id="test-concept-iso", name="测试概念",
        knowledge_level="L1", primary_module="SX",
        synced_at=datetime.now(timezone.utc),
    )
    db.add(node)
    await db.commit()

    # Phase 0.7E: 两校均为校级 token；启用模块使中间件对 /api/v1/knowledge（research）放行，
    # 测试专注于 link_question / get_question_kps 的跨校隔离逻辑本身。
    await enable_school_modules(db, school_a.id, school_b.id)

    token_a = create_access_token({"sub": user_a.id, "active_role_id": role_a.id})
    token_b = create_access_token({"sub": user_b.id, "active_role_id": role_b.id})

    return {
        "school_a_id": school_a.id,
        "school_b_id": school_b.id,
        "question_id": q_a.id,
        "concept_id": node.id,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
    }


@pytest.mark.asyncio
async def test_link_question_own_school(client, two_schools):
    """Same-school user can link a question to a knowledge point."""
    data = two_schools
    resp = await client.post(
        "/api/v1/knowledge/link",
        json={
            "question_id": data["question_id"],
            "concept_id": data["concept_id"],
        },
        headers=data["headers_a"],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["question_id"] == data["question_id"]
    assert body["concept_id"] == data["concept_id"]


@pytest.mark.asyncio
async def test_link_question_cross_school_blocked(client, two_schools):
    """Cross-school user gets 404 when linking another school's question."""
    data = two_schools
    resp = await client.post(
        "/api/v1/knowledge/link",
        json={
            "question_id": data["question_id"],
            "concept_id": data["concept_id"],
        },
        headers=data["headers_b"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_question_kps_own_school(client, two_schools):
    """Same-school user can query knowledge points for own question."""
    data = two_schools
    # First link (as school A user)
    await client.post(
        "/api/v1/knowledge/link",
        json={
            "question_id": data["question_id"],
            "concept_id": data["concept_id"],
        },
        headers=data["headers_a"],
    )
    # Then query
    resp = await client.get(
        f"/api/v1/knowledge/question/{data['question_id']}",
        headers=data["headers_a"],
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == data["concept_id"]


@pytest.mark.asyncio
async def test_get_question_kps_cross_school_blocked(client, two_schools):
    """Cross-school user gets 404 when querying another school's question."""
    data = two_schools
    resp = await client.get(
        f"/api/v1/knowledge/question/{data['question_id']}",
        headers=data["headers_b"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_link_requires_edit_permission(client, two_schools, db):
    """A role without EDIT_KNOWLEDGE_TREE cannot use /link (parent role)."""
    user = User(username="parent_iso", display_name="家长ISO")
    user.set_password("test123")
    db.add(user)
    await db.flush()

    data = two_schools
    role = UserRole(
        user_id=user.id, role="parent",
        school_id=data["school_a_id"], is_primary=True,
    )
    db.add(role)
    await db.commit()

    token = create_access_token({"sub": user.id, "active_role_id": role.id})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/knowledge/link",
        json={
            "question_id": data["question_id"],
            "concept_id": data["concept_id"],
        },
        headers=headers,
    )
    assert resp.status_code == 403
