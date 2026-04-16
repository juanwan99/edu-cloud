"""发布过滤测试。"""
import pytest
from datetime import datetime

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap,
)


@pytest.fixture
async def seed_mixed_status(db, admin_headers):
    """混合审核状态的图谱。"""
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_PF_TEST", name="过滤测试大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    # A: teacher_reviewed, B: ai_draft, C: published
    for sid, status in [("A", "teacher_reviewed"), ("B", "ai_draft"), ("C", "published")]:
        db.add(ConceptGraphNode(
            id=f"PF_{sid}", name=f"过滤{sid}", knowledge_level="L1",
            primary_module="M1", node_type="concept", review_status=status, synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"PF_{sid}", big_concept_id="BC_PF_TEST", is_primary=True,
        ))
    # Edges: A→C (teacher_reviewed), A→B (ai_draft), B→C (rejected)
    db.add(ConceptGraphEdge(
        source_id="PF_A", target_id="PF_C", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.9, review_status="teacher_reviewed", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="PF_A", target_id="PF_B", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.5, review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="PF_B", target_id="PF_C", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.6, review_status="rejected", synced_at=now,
    ))
    await db.commit()
    return {"auth_headers": admin_headers}


@pytest.mark.asyncio
async def test_include_draft_false_filters_nodes(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=false",
                            headers=seed_mixed_status["auth_headers"])
    assert resp.status_code == 200
    node_ids = {n["id"] for n in resp.json()["graph"]["nodes"]}
    assert "PF_A" in node_ids  # teacher_reviewed
    assert "PF_C" in node_ids  # published
    assert "PF_B" not in node_ids  # ai_draft → 被过滤


@pytest.mark.asyncio
async def test_include_draft_false_filters_edges(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=false",
                            headers=seed_mixed_status["auth_headers"])
    edges = resp.json()["graph"]["edges"]
    # A→C (teacher_reviewed) 应保留
    assert any(e["source"] == "PF_A" and e["target"] == "PF_C" for e in edges)
    # A→B (ai_draft edge) 应被过滤
    assert not any(e["target"] == "PF_B" for e in edges)
    # B→C (rejected) 应被过滤
    assert not any(e["source"] == "PF_B" for e in edges)


@pytest.mark.asyncio
async def test_navigation_filtered(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=false",
                            headers=seed_mixed_status["auth_headers"])
    nav = resp.json()["navigation"]
    m1 = next(m for m in nav if m["id"] == "M1")
    bc = next(bc for bc in m1["big_concepts"] if bc["id"] == "BC_PF_TEST")
    assert "PF_B" not in bc["concept_ids"]
    assert "PF_A" in bc["concept_ids"]


@pytest.mark.asyncio
async def test_include_draft_true_shows_all(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=true",
                            headers=seed_mixed_status["auth_headers"])
    node_ids = {n["id"] for n in resp.json()["graph"]["nodes"]}
    assert "PF_B" in node_ids  # ai_draft 可见


@pytest.mark.asyncio
async def test_null_review_status_treated_as_ai_draft(client, db, admin_headers):
    """review_status=NULL（旧数据）在 include_draft=false 时被过滤。"""
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_NULL_TEST", name="NULL测试大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    db.add(ConceptGraphNode(
        id="NULL_NODE", name="旧数据节点", knowledge_level="L1",
        primary_module="M1", node_type="concept", review_status=None, synced_at=now,
    ))
    db.add(ConceptBigConceptMap(
        concept_id="NULL_NODE", big_concept_id="BC_NULL_TEST", is_primary=True,
    ))
    await db.commit()

    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=false",
                            headers=admin_headers)
    node_ids = {n["id"] for n in resp.json()["graph"]["nodes"]}
    assert "NULL_NODE" not in node_ids  # NULL 当作 ai_draft，被过滤


@pytest.mark.asyncio
async def test_all_ai_draft_returns_empty(client, db, admin_headers):
    """所有节点都是 ai_draft + include_draft=false → 返回空 nodes/edges。"""
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_EMPTY_TEST", name="空测试大概念", knowledge_level="L1",
        primary_module="M9", node_type="big_concept", synced_at=now,
    ))
    db.add(ConceptGraphNode(
        id="EMPTY_A", name="全草稿A", knowledge_level="L1",
        primary_module="M9", node_type="concept", review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptBigConceptMap(
        concept_id="EMPTY_A", big_concept_id="BC_EMPTY_TEST", is_primary=True,
    ))
    await db.commit()

    resp = await client.get("/api/v1/knowledge-tree/graph?module=M9&include_draft=false",
                            headers=admin_headers)
    data = resp.json()
    assert len(data["graph"]["nodes"]) == 0
    assert len(data["graph"]["edges"]) == 0
    # navigation 中 concept_ids 应为空
    if data["navigation"]:
        m9 = next((m for m in data["navigation"] if m["id"] == "M9"), None)
        if m9:
            for bc in m9["big_concepts"]:
                assert len(bc["concept_ids"]) == 0


@pytest.mark.asyncio
async def test_parent_role_forced_draft_filter(client, db):
    """parent 角色在 KNOWLEDGE_DRAFT_VISIBLE=False 时强制 include_draft=false。"""
    from edu_cloud.models.school import School
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from edu_cloud.shared.auth import create_access_token
    from edu_cloud.config import settings

    # 创建 school + parent 用户
    school = School(name="测试学校PF", code="PFTEST", district="测试区")
    db.add(school)
    await db.flush()
    user = User(username="parent_pf", display_name="家长PF")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="parent", school_id=school.id, is_primary=True))
    await db.commit()
    await db.refresh(user)
    await db.refresh(school)

    token = create_access_token({"sub": user.id, "role": "parent", "school_id": str(school.id)})
    headers = {"Authorization": f"Bearer {token}"}

    # 创建一个 ai_draft 节点
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_PARENT_TEST", name="家长测试BC", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    db.add(ConceptGraphNode(
        id="PARENT_DRAFT", name="草稿节点", knowledge_level="L1",
        primary_module="M1", node_type="concept", review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptBigConceptMap(
        concept_id="PARENT_DRAFT", big_concept_id="BC_PARENT_TEST", is_primary=True,
    ))
    db.add(ConceptGraphNode(
        id="PARENT_PUB", name="发布节点", knowledge_level="L1",
        primary_module="M1", node_type="concept", review_status="published", synced_at=now,
    ))
    db.add(ConceptBigConceptMap(
        concept_id="PARENT_PUB", big_concept_id="BC_PARENT_TEST", is_primary=True,
    ))
    await db.commit()

    # 临时设置 KNOWLEDGE_DRAFT_VISIBLE=False
    original = settings.KNOWLEDGE_DRAFT_VISIBLE
    try:
        settings.KNOWLEDGE_DRAFT_VISIBLE = False
        resp = await client.get("/api/v1/knowledge-tree/graph?module=all",
                                headers=headers)
        assert resp.status_code == 200
        node_ids = {n["id"] for n in resp.json()["graph"]["nodes"]}
        assert "PARENT_DRAFT" not in node_ids  # 草稿被强制过滤
        assert "PARENT_PUB" in node_ids  # 已发布可见
    finally:
        settings.KNOWLEDGE_DRAFT_VISIBLE = original
