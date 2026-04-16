"""Edge 审核状态机测试。"""
import pytest


@pytest.mark.asyncio
async def test_edge_review_status_transition(client, db, seed_graph_v2):
    """edge ai_draft → teacher_reviewed。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "teacher_reviewed"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] == 1

    await db.refresh(edge)
    assert edge.review_status == "teacher_reviewed"


@pytest.mark.asyncio
async def test_edge_rejected(client, db, seed_graph_v2):
    """edge ai_draft → rejected 合法。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "rejected"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp.json()["applied"] == 1

    await db.refresh(edge)
    assert edge.review_status == "rejected"

    # 撤回: rejected → ai_draft（验证最终状态落库）
    resp2 = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "ai_draft"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp2.json()["applied"] == 1
    await db.refresh(edge)
    assert edge.review_status == "ai_draft"


@pytest.mark.asyncio
async def test_edge_teacher_reviewed_to_published(client, db, seed_graph_v2):
    """teacher_reviewed → published 合法。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()
    # 先推到 teacher_reviewed
    await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "teacher_reviewed"}]},
        headers=seed_graph_v2["auth_headers"])
    # teacher_reviewed → published
    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "published"}]},
        headers=seed_graph_v2["auth_headers"])
    assert resp.json()["applied"] == 1
    await db.refresh(edge)
    assert edge.review_status == "published"


@pytest.mark.asyncio
async def test_edge_teacher_reviewed_to_rejected(client, db, seed_graph_v2):
    """teacher_reviewed → rejected 合法。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()
    await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "teacher_reviewed"}]},
        headers=seed_graph_v2["auth_headers"])
    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "rejected"}]},
        headers=seed_graph_v2["auth_headers"])
    assert resp.json()["applied"] == 1
    await db.refresh(edge)
    assert edge.review_status == "rejected"


@pytest.mark.asyncio
async def test_edge_published_to_ai_draft(client, db, seed_graph_v2):
    """published → ai_draft 合法（回收）。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()
    # 推到 published
    await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "teacher_reviewed"}]},
        headers=seed_graph_v2["auth_headers"])
    await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "published"}]},
        headers=seed_graph_v2["auth_headers"])
    # published → ai_draft
    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "ai_draft"}]},
        headers=seed_graph_v2["auth_headers"])
    assert resp.json()["applied"] == 1
    await db.refresh(edge)
    assert edge.review_status == "ai_draft"


@pytest.mark.asyncio
async def test_edge_nonexistent_id(client, db, seed_graph_v2):
    """edge_id 不存在 → applied=0。"""
    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": 99999, "status": "teacher_reviewed"}]},
        headers=seed_graph_v2["auth_headers"])
    assert resp.json()["applied"] == 0


@pytest.mark.asyncio
async def test_edge_invalid_transition(client, db, seed_graph_v2):
    """非法转移: ai_draft → published（跳步）。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "published"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp.json()["applied"] == 0
