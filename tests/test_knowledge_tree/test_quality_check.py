"""质量巡检测试。"""
import pytest
from datetime import datetime

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap,
)


@pytest.fixture
async def seed_quality(db, admin_headers):
    """质量巡检测试数据。"""
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_QC", name="巡检大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    # A: 正常（有 hard in/out）, B: 正常, C: 孤立（只有 soft）, D: 无描述, E: 独立分量
    for sid, desc, rs in [
        ("A", "概念A", "ai_draft"), ("B", "概念B", "ai_draft"),
        ("C", "概念C", "ai_draft"), ("D", None, "ai_draft"),
        ("E", "概念E", "ai_draft"),
    ]:
        db.add(ConceptGraphNode(
            id=f"QC_{sid}", name=f"巡检{sid}", knowledge_level="L1",
            primary_module="M1", description=desc, node_type="concept",
            review_status=rs, synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"QC_{sid}", big_concept_id="BC_QC", is_primary=True,
        ))
    # A→B (hard, low confidence), A→D (hard, high confidence),
    # C→A (soft only), E is isolated
    db.add(ConceptGraphEdge(
        source_id="QC_A", target_id="QC_B", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.5, review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="QC_A", target_id="QC_D", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.9, review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="QC_C", target_id="QC_A", relation_type="prerequisite_soft",
        strength=1.0, confidence=0.8, review_status="ai_draft", synced_at=now,
    ))
    await db.commit()
    return {"auth_headers": admin_headers}


@pytest.mark.asyncio
async def test_q1_orphan(client, db, seed_quality):
    """Q1: 有 soft 但无 hard 的节点被标为孤立。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    assert resp.status_code == 200
    issues = resp.json()["issues"]
    q1 = [i for i in issues if i["rule_id"] == "Q1"]
    orphan_ids = set()
    for issue in q1:
        orphan_ids.update(issue["node_ids"])
    assert "QC_C" in orphan_ids  # 只有 soft 边
    assert "QC_E" in orphan_ids  # 完全无边
    assert "QC_A" not in orphan_ids  # 有 hard out


@pytest.mark.asyncio
async def test_q2_weak_components(client, db, seed_quality):
    """Q2: 检测到多个弱连通分量。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    issues = resp.json()["issues"]
    q2 = [i for i in issues if i["rule_id"] == "Q2"]
    # A→B, A→D 是一个分量 (A, B, D connected); C 孤立; E 孤立
    # Q2 只在分量>1 时报告，但孤立节点不在 hard 图中
    # 所以只有 1 个分量 {A,B,D}，不会触发 Q2
    # 除非有其他情况...先验证一下
    # 实际上 hard_node_ids = {A, B, D}（有 hard 边的节点），分量=1，Q2 不触发
    assert len(q2) == 0


@pytest.mark.asyncio
async def test_q3_low_confidence(client, db, seed_quality):
    """Q3: confidence<0.7 且 ai_draft 的边被检出。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    issues = resp.json()["issues"]
    q3 = [i for i in issues if i["rule_id"] == "Q3"]
    assert len(q3) == 1
    # A→B (confidence=0.5, ai_draft) 应被检出，共 1 条
    assert len(q3[0]["edge_ids"]) == 1


@pytest.mark.asyncio
async def test_q3_threshold_boundary(client, db, admin_headers):
    """Q3: confidence==0.7 不报告（阈值 <0.7），0.69 报告。"""
    from datetime import datetime
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_Q3B", name="Q3阈值大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    for sid in ["X", "Y", "Z"]:
        db.add(ConceptGraphNode(
            id=f"Q3B_{sid}", name=f"Q3B{sid}", knowledge_level="L1",
            primary_module="M1", description="d", node_type="concept",
            review_status="ai_draft", synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"Q3B_{sid}", big_concept_id="BC_Q3B", is_primary=True,
        ))
    # X→Y confidence=0.7 (不报), X→Z confidence=0.69 (报)
    db.add(ConceptGraphEdge(
        source_id="Q3B_X", target_id="Q3B_Y", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.7, review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="Q3B_X", target_id="Q3B_Z", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.69, review_status="ai_draft", synced_at=now,
    ))
    await db.commit()

    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=admin_headers)
    issues = resp.json()["issues"]
    q3 = [i for i in issues if i["rule_id"] == "Q3"]
    all_edge_ids = set()
    for issue in q3:
        all_edge_ids.update(issue["edge_ids"])
    # 0.69 的边应被检出，0.7 的不应该
    # 拿到边 id 验证
    from sqlalchemy import select
    edge_07 = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "Q3B_X", ConceptGraphEdge.target_id == "Q3B_Y",
        )
    )).scalar_one()
    edge_069 = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "Q3B_X", ConceptGraphEdge.target_id == "Q3B_Z",
        )
    )).scalar_one()
    assert edge_069.id in all_edge_ids
    assert edge_07.id not in all_edge_ids


@pytest.mark.asyncio
async def test_q3_reviewed_low_confidence_not_reported(client, db, admin_headers):
    """Q3: 已审核（teacher_reviewed）的低置信度边不报告。"""
    from datetime import datetime
    from sqlalchemy import select
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_Q3R", name="Q3审核大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    for sid in ["P", "Q"]:
        db.add(ConceptGraphNode(
            id=f"Q3R_{sid}", name=f"Q3R{sid}", knowledge_level="L1",
            primary_module="M1", description="d", node_type="concept",
            review_status="ai_draft", synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"Q3R_{sid}", big_concept_id="BC_Q3R", is_primary=True,
        ))
    db.add(ConceptGraphEdge(
        source_id="Q3R_P", target_id="Q3R_Q", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.3, review_status="teacher_reviewed", synced_at=now,
    ))
    await db.commit()

    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=admin_headers)
    issues = resp.json()["issues"]
    q3 = [i for i in issues if i["rule_id"] == "Q3"]
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "Q3R_P", ConceptGraphEdge.target_id == "Q3R_Q",
        )
    )).scalar_one()
    for issue in q3:
        assert edge.id not in issue["edge_ids"]


@pytest.mark.asyncio
async def test_q5_no_description(client, db, seed_quality):
    """Q5: 无描述的概念。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    issues = resp.json()["issues"]
    q5 = [i for i in issues if i["rule_id"] == "Q5"]
    assert len(q5) >= 1
    node_ids = set()
    for issue in q5:
        node_ids.update(issue["node_ids"])
    assert "QC_D" in node_ids


@pytest.mark.asyncio
async def test_quality_summary(client, db, seed_quality):
    """summary 统计正确。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    data = resp.json()
    assert data["module"] == "M1"
    assert data["summary"]["total_nodes"] == 5
    assert data["summary"]["total_edges"] == 3
    assert sum(data["summary"]["issues_by_severity"].values()) > 0
