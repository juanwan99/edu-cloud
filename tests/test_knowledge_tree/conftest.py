"""知识图谱 v2 测试 fixtures。"""
import pytest
from datetime import datetime

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap,
)


@pytest.fixture
async def seed_graph_v2(db, admin_headers):
    """创建 v2 测试图谱：M1 3节点 + M2 1节点 + 跨模块边。"""
    now = datetime.now()
    # BigConcept
    db.add(ConceptGraphNode(
        id="BC_M1_TEST", name="测试大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", display_order=0, synced_at=now,
    ))
    # M1 Concepts
    for suffix, desc in [("A", "测试概念A描述"), ("B", "测试概念B描述"), ("C", None)]:
        db.add(ConceptGraphNode(
            id=f"TEST_M1_{suffix}", name=f"概念{suffix}", knowledge_level="L1",
            primary_module="M1", description=desc, node_type="concept",
            review_status="ai_draft", synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"TEST_M1_{suffix}", big_concept_id="BC_M1_TEST", is_primary=True,
        ))
    # M2 Concept
    db.add(ConceptGraphNode(
        id="BC_M2_TEST", name="M2大概念", knowledge_level="L1",
        primary_module="M2", node_type="big_concept", display_order=0, synced_at=now,
    ))
    db.add(ConceptGraphNode(
        id="TEST_M2_X", name="概念X", knowledge_level="L1",
        primary_module="M2", description="M2概念", node_type="concept",
        review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptBigConceptMap(
        concept_id="TEST_M2_X", big_concept_id="BC_M2_TEST", is_primary=True,
    ))
    # Edges: A→B(hard), A→C(hard), A→X(hard,跨模块), B↔C(soft)
    for src, tgt, rtype, conf in [
        ("TEST_M1_A", "TEST_M1_B", "prerequisite_hard", 0.9),
        ("TEST_M1_A", "TEST_M1_C", "prerequisite_hard", 0.5),
        ("TEST_M1_A", "TEST_M2_X", "prerequisite_hard", 0.8),
        ("TEST_M1_B", "TEST_M1_C", "prerequisite_soft", 0.7),
    ]:
        db.add(ConceptGraphEdge(
            source_id=src, target_id=tgt, relation_type=rtype,
            strength=1.0, confidence=conf, review_status="ai_draft", synced_at=now,
        ))
    await db.commit()
    return {"auth_headers": admin_headers}


@pytest.fixture
async def seeded_concepts(db):
    """从 knowledge.db 同步 L1 concepts 到测试 DB（T5 compute_all_stats 端到端测试用）。"""
    import os
    from pathlib import Path

    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup

    kb_path = os.environ.get(
        "KNOWLEDGE_DB_PATH",
        str(Path.home() / "edu-knowledge-base" / "knowledge.db"),
    )
    if not Path(kb_path).exists():
        pytest.skip("knowledge.db not available")
    await sync_knowledge_on_startup(db, kb_path)
    yield
