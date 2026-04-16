import pytest
from sqlalchemy import inspect
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap


def test_concept_graph_node_fields():
    cols = {c.name for c in inspect(ConceptGraphNode).columns}
    assert "id" in cols
    assert "name" in cols
    assert "knowledge_level" in cols
    assert "primary_module" in cols
    assert "description" in cols
    assert "synced_at" in cols
    # 层级重构新增列
    assert "subject" in cols
    assert "node_type" in cols
    assert "display_order" in cols
    assert "review_status" in cols
    assert "reviewed_by" in cols
    assert "reviewed_at" in cols
    assert "aliases_json" in cols
    assert "evidence_ids_json" in cols
    assert "difficulty" in cols
    assert "bloom_level" in cols


def test_concept_graph_node_tablename():
    assert ConceptGraphNode.__tablename__ == "concept_graph_nodes"


def test_big_concept_map_fields():
    cols = {c.name for c in inspect(ConceptBigConceptMap).columns}
    assert "concept_id" in cols
    assert "big_concept_id" in cols
    assert "is_primary" in cols


def test_big_concept_map_tablename():
    assert ConceptBigConceptMap.__tablename__ == "concept_big_concept_map"


def test_big_concept_map_composite_pk():
    pk_cols = {c.name for c in inspect(ConceptBigConceptMap).mapper.primary_key}
    assert pk_cols == {"concept_id", "big_concept_id"}


def test_concept_graph_edge_fields():
    cols = {c.name for c in inspect(ConceptGraphEdge).columns}
    assert "id" in cols
    assert "source_id" in cols
    assert "target_id" in cols
    assert "relation_type" in cols
    assert "strength" in cols
    assert "confidence" in cols
    assert "synced_at" in cols


def test_concept_graph_edge_tablename():
    assert ConceptGraphEdge.__tablename__ == "concept_graph_edges"


def test_concept_graph_edge_unique_constraint():
    constraints = ConceptGraphEdge.__table_args__
    unique_cols = None
    for c in constraints:
        if hasattr(c, "columns"):
            unique_cols = {col.name for col in c.columns}
    assert unique_cols == {"source_id", "target_id", "relation_type"}


@pytest.mark.asyncio
async def test_node_new_columns_read_write(db):
    """ConceptGraphNode 新增列可正常读写（含 difficulty/bloom_level）。"""
    from datetime import datetime
    node = ConceptGraphNode(
        id="TEST_NODE_1", name="测试节点", knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(),
        subject="biology_senior", node_type="concept", display_order=5,
        review_status="ai_draft", reviewed_by="user1", reviewed_at="2026-04-09T12:00:00",
        aliases_json='["别名1"]', evidence_ids_json='["EV_001"]',
        difficulty=4, bloom_level="apply",
    )
    db.add(node)
    await db.flush()

    from sqlalchemy import select
    result = await db.execute(select(ConceptGraphNode).where(ConceptGraphNode.id == "TEST_NODE_1"))
    n = result.scalar_one()
    assert n.subject == "biology_senior"
    assert n.node_type == "concept"
    assert n.display_order == 5
    assert n.review_status == "ai_draft"
    assert n.reviewed_by == "user1"
    assert n.aliases_json == '["别名1"]'
    assert n.evidence_ids_json == '["EV_001"]'
    assert n.difficulty == 4
    assert n.bloom_level == "apply"


@pytest.mark.asyncio
async def test_node_nullable_new_columns(db):
    """新增列为 NULL 时正常工作。"""
    from datetime import datetime
    node = ConceptGraphNode(
        id="TEST_NODE_NULL", name="空列测试", knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(),
    )
    db.add(node)
    await db.flush()

    from sqlalchemy import select
    result = await db.execute(select(ConceptGraphNode).where(ConceptGraphNode.id == "TEST_NODE_NULL"))
    n = result.scalar_one()
    assert n.difficulty is None
    assert n.bloom_level is None
    assert n.aliases_json is None
    assert n.review_status is None


@pytest.mark.asyncio
async def test_big_concept_map_crud(db):
    """ConceptBigConceptMap 外键和复合主键正确。"""
    from datetime import datetime
    # Create parent nodes first
    for nid, ntype in [("BC_1", "big_concept"), ("C_1", "concept")]:
        db.add(ConceptGraphNode(
            id=nid, name=nid, knowledge_level="L1",
            primary_module="M1", synced_at=datetime.now(), node_type=ntype,
        ))
    await db.flush()

    m = ConceptBigConceptMap(concept_id="C_1", big_concept_id="BC_1", is_primary=True)
    db.add(m)
    await db.flush()

    from sqlalchemy import select, func
    count = await db.scalar(select(func.count()).select_from(ConceptBigConceptMap))
    assert count == 1

    result = await db.execute(select(ConceptBigConceptMap))
    row = result.scalar_one()
    assert row.concept_id == "C_1"
    assert row.big_concept_id == "BC_1"
    assert row.is_primary is True
