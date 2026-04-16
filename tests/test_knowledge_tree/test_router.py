import pytest
from datetime import datetime

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap
from edu_cloud.modules.adaptive.models import StudentDaMastery, DaKnowledgePointMap


async def _seed_data(db):
    now = datetime.now()
    # BigConcept 节点
    db.add(ConceptGraphNode(id="BC_M1_C1", name="细胞学说大概念", knowledge_level="L1",
                            primary_module="M1", node_type="big_concept", synced_at=now))
    # L1 Concept 节点
    db.add_all([
        ConceptGraphNode(id="CP_M1_A", name="概念A", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now,
                         difficulty=3, bloom_level="understand",
                         aliases_json='["别名A"]', review_status="ai_draft"),
        ConceptGraphNode(id="CP_M1_B", name="概念B", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now),
    ])
    await db.flush()
    # Map
    db.add_all([
        ConceptBigConceptMap(concept_id="CP_M1_A", big_concept_id="BC_M1_C1", is_primary=True),
        ConceptBigConceptMap(concept_id="CP_M1_B", big_concept_id="BC_M1_C1", is_primary=True),
    ])
    db.add(ConceptGraphEdge(source_id="CP_M1_A", target_id="CP_M1_B",
                            relation_type="prerequisite_hard", synced_at=now))
    db.add(DaKnowledgePointMap(da_id="DA_001",
                               knowledge_point_id="CP_M1_A", weight=1.0))
    await db.flush()
    db.add(StudentDaMastery(id="m1", student_id="S001", da_id="DA_001",
                            mastery_prob=0.8, attempt_count=5, correct_count=4, school_id="SCH1"))
    await db.commit()


@pytest.mark.asyncio
async def test_get_graph(client, db, admin_headers):
    await _seed_data(db)
    resp = await client.get("/api/v1/knowledge-tree/graph", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    # 新格式: navigation + graph
    assert "navigation" in data
    assert "graph" in data
    # graph.nodes 只含 concept（不含 big_concept）
    assert len(data["graph"]["nodes"]) == 2
    assert len(data["graph"]["edges"]) == 1
    # navigation 含一个模块
    assert len(data["navigation"]) >= 1


@pytest.mark.asyncio
async def test_get_graph_filter_module(client, db, admin_headers):
    await _seed_data(db)
    resp = await client.get("/api/v1/knowledge-tree/graph?module=M1", headers=admin_headers)
    assert resp.status_code == 200
    assert len(resp.json()["graph"]["nodes"]) == 2


@pytest.mark.asyncio
async def test_navigation_structure(client, db, admin_headers):
    """navigation 从 big_concepts + map 动态构建。"""
    await _seed_data(db)
    resp = await client.get("/api/v1/knowledge-tree/graph", headers=admin_headers)
    nav = resp.json()["navigation"]
    assert len(nav) >= 1
    m1 = next((m for m in nav if m["id"] == "M1"), None)
    assert m1 is not None
    assert len(m1["big_concepts"]) == 1
    bc = m1["big_concepts"][0]
    assert bc["id"] == "BC_M1_C1"
    assert set(bc["concept_ids"]) == {"CP_M1_A", "CP_M1_B"}


@pytest.mark.asyncio
async def test_graph_node_fields(client, db, admin_headers):
    """graph.nodes 包含 difficulty/bloom_level 字段。"""
    await _seed_data(db)
    resp = await client.get("/api/v1/knowledge-tree/graph", headers=admin_headers)
    nodes = resp.json()["graph"]["nodes"]
    a = next(n for n in nodes if n["id"] == "CP_M1_A")
    assert a["difficulty"] == 3
    assert a["bloom_level"] == "understand"
    assert a["aliases"] == ["别名A"]
    assert a["review_status"] == "ai_draft"
    assert a["big_concept_id"] == "BC_M1_C1"


@pytest.mark.asyncio
async def test_graph_nodes_l1_only(client, db, admin_headers):
    """INV-004: graph.nodes 中无 BigConcept 节点。"""
    await _seed_data(db)
    resp = await client.get("/api/v1/knowledge-tree/graph", headers=admin_headers)
    nodes = resp.json()["graph"]["nodes"]
    for n in nodes:
        assert n["id"] != "BC_M1_C1", "BigConcept should not appear in graph.nodes"


@pytest.mark.asyncio
async def test_navigation_graph_consistency(client, db, admin_headers):
    """CE-002: navigation 和 graph 中 big_concept_id 一致。"""
    await _seed_data(db)
    resp = await client.get("/api/v1/knowledge-tree/graph", headers=admin_headers)
    data = resp.json()
    node_map = {n["id"]: n for n in data["graph"]["nodes"]}
    for mod in data["navigation"]:
        for bc in mod["big_concepts"]:
            for cid in bc["concept_ids"]:
                if cid in node_map:
                    assert node_map[cid]["big_concept_id"] == bc["id"]


@pytest.mark.asyncio
async def test_get_mastery(client, db, admin_headers):
    await _seed_data(db)
    resp = await client.get("/api/v1/knowledge-tree/mastery?student_id=S001", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == "S001"
    assert len(data["concept_mastery"]) >= 1


@pytest.mark.asyncio
async def test_get_mastery_missing_student_id(client, admin_headers):
    """student_id 不传时返回空掌握度（F001 修复后的预期行为）。"""
    resp = await client.get("/api/v1/knowledge-tree/mastery", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["concept_mastery"] == []


@pytest.mark.asyncio
async def test_edit_graph(client, db, admin_headers):
    await _seed_data(db)
    resp = await client.post("/api/v1/knowledge-tree/edit", json={
        "operations": [
            {"op": "update_node", "id": "CP_M1_A", "fields": {"name": "概念A改名"}}
        ]
    }, headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["applied"] == 1


@pytest.mark.asyncio
async def test_graph_requires_auth(client):
    resp = await client.get("/api/v1/knowledge-tree/graph")
    assert resp.status_code in (401, 403)  # module middleware may return 403 before auth


@pytest.mark.asyncio
async def test_edit_requires_edit_permission(client, db, observer_headers):
    """F003: observer 角色无 EDIT_KNOWLEDGE_TREE 权限，应被拒绝。"""
    resp = await client.post("/api/v1/knowledge-tree/edit", json={
        "operations": [{"op": "update_node", "id": "X", "fields": {"name": "Y"}}]
    }, headers=observer_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mastery_school_scope_at_router_level(client, db, subject_teacher_headers):
    """R2-01: 路由级 school_id 过滤 — teacher 角色只能看到本校掌握度。"""
    await _seed_data(db)  # mastery 数据 school_id="SCH1"
    # subject_teacher 绑定的 school_id != "SCH1"，所以应该看不到掌握度
    resp = await client.get(
        "/api/v1/knowledge-tree/mastery?student_id=S001",
        headers=subject_teacher_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # 教师所属学校非 SCH1，所有概念掌握度应为 0
    for cm in data["concept_mastery"]:
        assert cm["mastery"] == 0.0, f"跨校数据泄露: {cm['concept_id']} mastery={cm['mastery']}"


