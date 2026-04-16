"""Graph API v3 字段测试

契约（来自 plan Task 7）：
- 节点返回合并 concept_stats 9 字段（exam_frequency/exam_coverage/avg_difficulty/
  importance_score/textbook_chapters/study_unit_id/estimated_minutes/
  prerequisite_depth/planning_weight）。
- 无 stats 记录时使用默认值（0/0.0/[]/None），不报错。
- v2 字段（hard_in_count/hard_out_count/review_status/big_concept_id/
  external_hard_refs）保留。

反例：
- 错误实现若未加载 ConceptStats → v3 字段缺失或全 None（test_graph_v3_fields_present fail）
- 错误实现若把 None 的 avg_difficulty 默认为 0.0 → 前端无法识别"无数据" → 本测试断言 avg_difficulty is None
- 错误实现若 stats IN 子查询用了其它 key → 对应节点仍取不到 stats（test_graph_v3_fields_present fail）
"""
import pytest
from datetime import datetime

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptStats,
)


@pytest.mark.asyncio
async def test_graph_v3_fields_present(db):
    """Graph 返回节点应包含 v3 新字段（exam_frequency/importance_score/...）"""
    from edu_cloud.modules.knowledge_tree.service import get_graph

    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_V3_001", name="v3测试", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    db.add(ConceptStats(
        concept_id="TEST_V3_001",
        exam_frequency=500,
        exam_coverage=0.42,
        avg_difficulty=3.5,
        importance_score=8.5,
        estimated_minutes=90,
        prerequisite_depth=2,
        textbook_chapters=[{"book": "b1", "chapter": "ch03", "section": "s01", "title": "T"}],
        study_unit_id="su:test",
        planning_weight={"priority_score": 8.0},
        computed_at=now,
    ))
    await db.commit()

    result = await get_graph(db, module="M1", include_draft=True)
    nodes = result["graph"]["nodes"]
    node = next((n for n in nodes if n["id"] == "TEST_V3_001"), None)
    assert node is not None

    # v3 精确值断言（stats_count == expected）
    assert node["exam_frequency"] == 500
    assert node["exam_coverage"] == 0.42
    assert node["avg_difficulty"] == 3.5
    assert node["importance_score"] == 8.5
    assert node["estimated_minutes"] == 90
    assert node["prerequisite_depth"] == 2
    assert node["study_unit_id"] == "su:test"
    assert len(node["textbook_chapters"]) == 1
    assert node["textbook_chapters"][0]["book"] == "b1"
    assert node["planning_weight"] == {"priority_score": 8.0}


@pytest.mark.asyncio
async def test_graph_v3_defaults_when_no_stats(db):
    """无 stats 记录时节点应用合理默认值（不报错，None 语义保留）"""
    from edu_cloud.modules.knowledge_tree.service import get_graph

    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_NO_STATS", name="无stats", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    await db.commit()

    result = await get_graph(db, module="M1", include_draft=True)
    nodes = result["graph"]["nodes"]
    node = next((n for n in nodes if n["id"] == "TEST_NO_STATS"), None)
    assert node is not None

    # 默认值精确匹配
    assert node["exam_frequency"] == 0
    assert node["exam_coverage"] == 0.0
    assert node["avg_difficulty"] is None  # 零考频时无难度代理值
    assert node["importance_score"] == 0.0
    assert node["textbook_chapters"] == []
    assert node["study_unit_id"] is None
    assert node["estimated_minutes"] is None
    assert node["prerequisite_depth"] == 0
    assert node["planning_weight"] is None


@pytest.mark.asyncio
async def test_graph_v2_fields_preserved(db):
    """v3 扩展不应破坏 v2 字段（hard_in_count/hard_out_count/review_status/big_concept_id）"""
    from edu_cloud.modules.knowledge_tree.service import get_graph

    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_V2_KEEP", name="v2保留", knowledge_level="L1",
        primary_module="M1", node_type="concept",
        review_status="published", synced_at=now,
    ))
    await db.commit()

    result = await get_graph(db, module="M1", include_draft=True)
    node = next((n for n in result["graph"]["nodes"] if n["id"] == "TEST_V2_KEEP"), None)
    assert node is not None
    # v2 字段必须存在且语义正确
    assert "hard_in_count" in node and node["hard_in_count"] == 0
    assert "hard_out_count" in node and node["hard_out_count"] == 0
    assert "review_status" in node and node["review_status"] == "published"
    assert "big_concept_id" in node  # 值可为 None（无 map 记录）
    # module 过滤时 external_hard_refs 存在（可为 None）
    assert "external_hard_refs" in node
