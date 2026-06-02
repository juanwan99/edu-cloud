"""删除概念节点时 ConceptStats 应被审计记录。"""
import pytest
import sqlalchemy as sa
from datetime import datetime
from unittest.mock import patch

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptStats,
)
from edu_cloud.modules.knowledge_tree.service import apply_edits


@pytest.mark.asyncio
async def test_remove_node_logs_stats_before_cascade(db):
    """remove_node 操作应在删除前记录被删节点的 stats 信息"""
    now = datetime.now()
    node = ConceptGraphNode(
        id="AUDIT_TEST_001", name="审计测试节点", knowledge_level="L1",
        primary_module="M1", synced_at=now,
    )
    db.add(node)
    await db.commit()

    stats = ConceptStats(
        concept_id="AUDIT_TEST_001",
        exam_frequency=42,
        importance_score=0.85,
        exam_coverage=0.6,
        textbook_chapters=[],
        prerequisite_depth=2,
        computed_at=now,
    )
    db.add(stats)
    await db.commit()

    with patch("edu_cloud.modules.knowledge_tree.service.logger") as mock_logger:
        applied = await apply_edits(
            db,
            [{"op": "remove_node", "id": "AUDIT_TEST_001"}],
        )
        assert applied == 1

        info_calls = [
            call for call in mock_logger.info.call_args_list
            if "concept_stats_archived" in str(call)
        ]
        assert len(info_calls) >= 1, "删除节点前应记录 concept_stats 审计日志"

    check = await db.execute(
        sa.select(ConceptGraphNode).where(ConceptGraphNode.id == "AUDIT_TEST_001")
    )
    assert check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_remove_node_without_stats_no_error(db):
    """删除没有 stats 的节点不应报错"""
    now = datetime.now()
    node = ConceptGraphNode(
        id="AUDIT_TEST_002", name="无统计节点", knowledge_level="L1",
        primary_module="M1", synced_at=now,
    )
    db.add(node)
    await db.commit()

    applied = await apply_edits(
        db,
        [{"op": "remove_node", "id": "AUDIT_TEST_002"}],
    )
    assert applied == 1
