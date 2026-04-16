"""MCU-03 规划权重导入脚本。

将 MCU L1_patterns/*.json 中的 planning_weight 字段（exam_frequency/error_prone/
transfer_value/priority_score）通过语义匹配导入到 edu-cloud ConceptStats.planning_weight。

用法: python scripts/import_mcu_planning_weights.py [--dry-run]

匹配策略: TF-IDF 字符 n-gram 相似度（无外部依赖，轻量级方案）
- MCU 侧取 CP.content
- kb 侧取 concept.name + concept.description
- 相似度 >= threshold(0.5) 自动接受，< threshold 放弃
"""
import asyncio
import glob
import json
import logging
import sys
from collections import Counter
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logger = logging.getLogger(__name__)

MCU_BASE = Path("C:/Users/Administrator/Archive/MCU-03/knowledge_skeleton")
DEFAULT_THRESHOLD = 0.5


def _char_ngrams(text: str, n: int = 2) -> Counter:
    """字符 n-gram 提取（中文友好）。"""
    text = text.replace(" ", "")
    return Counter(text[i:i+n] for i in range(len(text) - n + 1))


def _cosine_similarity(a: Counter, b: Counter) -> float:
    """Counter 间余弦相似度。"""
    if not a or not b:
        return 0.0
    intersection = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in intersection)
    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def match_mcu_to_kb(
    mcu_patterns: dict[str, dict],
    kb_concepts: dict[str, dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, tuple[str, float]]:
    """匹配 MCU CP ID → kb concept ID。

    Args:
        mcu_patterns: {mcu_id: {"content": "..."}}
        kb_concepts: {kb_id: {"name": "...", "description": "..."}}
        threshold: 相似度阈值（低于此值不匹配）

    Returns:
        {mcu_id: (kb_id, similarity_score)}
    """
    kb_ngrams = {
        kb_id: _char_ngrams((info.get("name") or "") + (info.get("description") or ""))
        for kb_id, info in kb_concepts.items()
    }

    result: dict[str, tuple[str, float]] = {}
    for mcu_id, mcu_info in mcu_patterns.items():
        mcu_ng = _char_ngrams(mcu_info.get("content") or "")
        best_kb, best_score = None, 0.0
        for kb_id, kb_ng in kb_ngrams.items():
            score = _cosine_similarity(mcu_ng, kb_ng)
            if score > best_score:
                best_score = score
                best_kb = kb_id
        if best_kb and best_score >= threshold:
            result[mcu_id] = (best_kb, best_score)
    return result


def load_mcu_patterns_and_weights() -> tuple[dict[str, dict], dict[str, dict]]:
    """加载 MCU L1 patterns 内容和规划权重。

    Returns: (patterns_by_id, weights_by_id)
    """
    patterns: dict[str, dict] = {}
    for f in sorted(glob.glob(str(MCU_BASE / "L1_patterns/*.json"))):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        for p in data.get("patterns", []):
            patterns[p["id"]] = {"content": p.get("content", "")}

    weights_file = MCU_BASE / "weights/planning_weights_L1.json"
    with open(weights_file, encoding="utf-8") as fh:
        weights_data = json.load(fh)
    weights = weights_data.get("weights", {})
    return patterns, weights


async def load_kb_concepts(db) -> dict[str, dict]:
    """从 edu-cloud PG 加载 L1 概念。"""
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode

    result = await db.execute(
        sa.select(ConceptGraphNode.id, ConceptGraphNode.name, ConceptGraphNode.description)
        .where(ConceptGraphNode.node_type == "concept")
    )
    return {r[0]: {"name": r[1], "description": r[2] or ""} for r in result.all()}


async def import_weights(db, weights_by_concept_id: dict[str, dict]) -> int:
    """将权重写入 ConceptStats.planning_weight（幂等 UPSERT）。

    Args:
        weights_by_concept_id: {kb_concept_id: {"exam_frequency": ..., "priority_score": ...}}

    Returns: 更新的记录数
    """
    from datetime import datetime

    from edu_cloud.modules.knowledge_tree.models import ConceptStats

    updated = 0
    for concept_id, weight in weights_by_concept_id.items():
        stats = await db.get(ConceptStats, concept_id)
        if stats is None:
            db.add(ConceptStats(
                concept_id=concept_id,
                planning_weight=weight,
                computed_at=datetime.now(),
            ))
        else:
            stats.planning_weight = weight
            stats.computed_at = datetime.now()
        updated += 1
    await db.commit()
    return updated


async def main(dry_run: bool = False):
    from edu_cloud.database import async_session

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    patterns, weights = load_mcu_patterns_and_weights()
    logger.info("MCU patterns: %d, weights: %d", len(patterns), len(weights))

    async with async_session() as session:
        kb_concepts = await load_kb_concepts(session)
        logger.info("KB concepts: %d", len(kb_concepts))

        mapping = match_mcu_to_kb(patterns, kb_concepts)
        logger.info("Matched: %d MCU CPs → kb concepts", len(mapping))

        weights_by_kb: dict[str, dict] = {}
        for mcu_id, (kb_id, score) in mapping.items():
            if mcu_id in weights:
                weights_by_kb[kb_id] = weights[mcu_id]
                logger.info("  %s → %s (score=%.2f, priority=%.1f)",
                            mcu_id, kb_id, score, weights[mcu_id].get("priority_score", 0))

        if dry_run:
            logger.info("DRY-RUN: 不写入数据库")
            return

        updated = await import_weights(session, weights_by_kb)
        logger.info("Updated %d ConceptStats.planning_weight", updated)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
