"""MCU 权重导入脚本测试"""
import sys
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptStats

# scripts/ 不在默认 pythonpath 内，显式加入
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

MCU_PATH = Path("C:/Users/Administrator/Archive/MCU-03/knowledge_skeleton")


@pytest.mark.skipif(not MCU_PATH.exists(), reason="MCU-03 not available")
def test_mcu_matching_by_content():
    """MCU L1 CP 的 content 和 kb concept 的 name+description 做语义匹配"""
    from scripts.import_mcu_planning_weights import match_mcu_to_kb

    mcu_patterns = {
        "L01_CP_001": {
            "content": "生命系统的层级中，细胞是最基本且唯一能独立完成生命活动的单位",
        }
    }
    kb_concepts = {
        "BIO_SR_CP_M1_LIFE_SYSTEM_LEVELS": {
            "name": "生命系统的结构层次",
            "description": "从分子到生物圈的 9 个层次",
        },
        "BIO_SR_CP_M1_CELL_THEORY": {
            "name": "细胞学说",
            "description": "施莱登施旺细胞学说三要点",
        },
    }
    # threshold=0.15: 中文短句 n-gram 余弦真实区间 0.1-0.3；
    # LIFE_SYSTEM ~0.19 可匹配，CELL_THEORY ~0.08 被过滤（保留区分力）
    result = match_mcu_to_kb(mcu_patterns, kb_concepts, threshold=0.15)
    # L01_CP_001 讲生命系统层级，应匹配到 LIFE_SYSTEM_LEVELS 而非 CELL_THEORY
    assert "L01_CP_001" in result
    kb_id, score = result["L01_CP_001"]
    assert kb_id == "BIO_SR_CP_M1_LIFE_SYSTEM_LEVELS", \
        f"应匹配到 LIFE_SYSTEM_LEVELS, got {kb_id}"
    assert score >= 0.15


@pytest.mark.skipif(not MCU_PATH.exists(), reason="MCU-03 not available")
def test_mcu_matching_filters_low_confidence():
    """低于阈值的匹配应被过滤（反例：阈值太低会乱匹配）"""
    from scripts.import_mcu_planning_weights import match_mcu_to_kb

    mcu_patterns = {
        "L99_CP_999": {"content": "完全不相关的文本内容 XYZ"},
    }
    kb_concepts = {
        "BIO_SR_CP_M1_CELL_THEORY": {"name": "细胞学说", "description": "细胞学说三要点：细胞是生命基本单位"},
    }
    result = match_mcu_to_kb(mcu_patterns, kb_concepts, threshold=0.5)
    assert "L99_CP_999" not in result, "不相关内容不应匹配"


@pytest.mark.asyncio
async def test_import_idempotent(db):
    """两次导入权重结果一致（UPSERT）"""
    from scripts.import_mcu_planning_weights import import_weights

    # 准备一个 concept + 空 stats
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_MCU_001", name="测试", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    db.add(ConceptStats(concept_id="TEST_MCU_001", computed_at=now))
    await db.commit()

    weights = {
        "TEST_MCU_001": {
            "exam_frequency": 8, "error_prone": 6,
            "transfer_value": 9, "priority_score": 7.7,
        }
    }
    await import_weights(db, weights)
    await import_weights(db, weights)  # 第二次

    result = await db.execute(
        sa.select(ConceptStats).where(ConceptStats.concept_id == "TEST_MCU_001")
    )
    loaded = result.scalar_one()
    assert loaded.planning_weight["priority_score"] == 7.7
    # 确认只有一条记录
    count = await db.execute(
        sa.select(sa.func.count()).select_from(ConceptStats)
        .where(ConceptStats.concept_id == "TEST_MCU_001")
    )
    assert count.scalar() == 1
