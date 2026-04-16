"""concept_stats 计算服务。

从 knowledge.db 读取关联链路计算每个 L1 概念的：
- exam_frequency: 关联高考题数量（通过 DA → Q-Matrix 回溯）
- avg_difficulty: 关联题目平均难度
- exam_coverage: 出现在多少比例的高考卷中
- textbook_chapters: 教材章节列表（通过 evidence → content_blocks → sections）
- importance_score: 综合重要度（考频 + error_prone + transfer_value + depth）
- prerequisite_depth: 前置链深度（拓扑排序 rank）

设计文档: docs/plans/2026-04-12-knowledge-graph-optimization-design.md §7
"""
import json
import logging
import sqlite3
from collections import defaultdict

logger = logging.getLogger(__name__)


def _load_da_to_concepts(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """从 diagnostic_attributes 构建 DA→concept_ids 映射。

    linked_concept_ids 是 JSON 数组存为 TEXT，用 json.loads 解析。
    """
    mapping: dict[str, list[str]] = {}
    for da_id, linked in conn.execute(
        "SELECT id, linked_concept_ids FROM diagnostic_attributes WHERE linked_concept_ids IS NOT NULL"
    ):
        try:
            concept_ids = json.loads(linked)
            if isinstance(concept_ids, list):
                mapping[da_id] = concept_ids
        except (json.JSONDecodeError, TypeError):
            logger.warning("DA %s has invalid linked_concept_ids: %r", da_id, linked)
    return mapping


def _load_l1_concept_ids(conn: sqlite3.Connection) -> set[str]:
    """只返回 L1 concepts（过滤 L0 evidence 和 L2）。"""
    return {
        r[0] for r in conn.execute(
            "SELECT id FROM concepts WHERE knowledge_level='L1'"
        )
    }


def compute_exam_frequency(kb_path: str) -> dict[str, int]:
    """计算每个 L1 概念关联的高考题数量。

    链路: concepts(L1) ← DA.linked_concept_ids → q_matrix.attribute_id → item_id (DISTINCT)
    """
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)
        da_to_concepts = _load_da_to_concepts(conn)

        # concept_id → set of item_ids
        concept_items: dict[str, set[str]] = defaultdict(set)
        for item_id, da_id in conn.execute("SELECT item_id, attribute_id FROM q_matrix"):
            for cid in da_to_concepts.get(da_id, []):
                if cid in l1_ids:
                    concept_items[cid].add(item_id)

        # 为所有 L1 概念填 0（包括零考频）
        result = {cid: len(concept_items.get(cid, set())) for cid in l1_ids}
        return result
    finally:
        conn.close()


# q_matrix.transfer_band → 难度数值映射
# plan 假设 assessment_items.difficulty 存在，实际 schema 无此列，
# 改用 q_matrix.transfer_band（题目对概念的迁移距离）作为难度代理：
# near = 基础识记（低难度）/ mid = 一般应用（中难度）/ far = 远迁移（高难度）
_TRANSFER_BAND_SCORE = {"near": 2.0, "mid": 3.0, "far": 4.0}


def compute_avg_difficulty(kb_path: str) -> dict[str, float | None]:
    """计算每个 L1 概念关联题目的平均难度。

    数据源: q_matrix.transfer_band（assessment_items 无 difficulty 列，
    用 transfer_band 的 near/mid/far → 2/3/4 映射作为代理）。
    """
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)
        da_to_concepts = _load_da_to_concepts(conn)

        concept_difficulties: dict[str, list[float]] = defaultdict(list)
        seen_pairs: set[tuple[str, str]] = set()
        for item_id, da_id, band in conn.execute(
            "SELECT item_id, attribute_id, transfer_band FROM q_matrix"
        ):
            score = _TRANSFER_BAND_SCORE.get(band)
            if score is None:
                continue
            for cid in da_to_concepts.get(da_id, []):
                if cid not in l1_ids:
                    continue
                pair = (cid, item_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                concept_difficulties[cid].append(score)

        result: dict[str, float | None] = {}
        for cid in l1_ids:
            diffs = concept_difficulties.get(cid)
            result[cid] = sum(diffs) / len(diffs) if diffs else None
        return result
    finally:
        conn.close()


def compute_exam_coverage(kb_path: str) -> dict[str, float]:
    """计算每个概念出现在多少比例的高考卷中（0-1）。"""
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)
        da_to_concepts = _load_da_to_concepts(conn)

        total_exams = conn.execute(
            "SELECT COUNT(DISTINCT exam_id) FROM assessment_items"
        ).fetchone()[0]
        if total_exams == 0:
            return {cid: 0.0 for cid in l1_ids}

        item_to_exam: dict[str, str] = dict(
            conn.execute("SELECT id, exam_id FROM assessment_items")
        )
        concept_exams: dict[str, set[str]] = defaultdict(set)
        for item_id, da_id in conn.execute("SELECT item_id, attribute_id FROM q_matrix"):
            exam_id = item_to_exam.get(item_id)
            if not exam_id:
                continue
            for cid in da_to_concepts.get(da_id, []):
                if cid in l1_ids:
                    concept_exams[cid].add(exam_id)

        return {cid: len(concept_exams.get(cid, set())) / total_exams for cid in l1_ids}
    finally:
        conn.close()


def compute_textbook_chapters(kb_path: str) -> dict[str, list[dict]]:
    """为每个 L1 概念聚合教材章节信息。

    链路: L1.evidence_ids_json → evidence concepts.source_block_id
          → content_blocks.section_id → sections
    """
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)

        # 预加载 evidence concept → section_id
        evidence_to_section: dict[str, str | None] = {}
        for cid, block_id in conn.execute(
            "SELECT id, source_block_id FROM concepts "
            "WHERE knowledge_level='evidence' AND source_block_id IS NOT NULL"
        ):
            section = conn.execute(
                "SELECT section_id FROM content_blocks WHERE id=?", (block_id,)
            ).fetchone()
            if section:
                evidence_to_section[cid] = section[0]

        # 预加载 section → {book, chapter, section, title}
        section_info: dict[str, dict] = {}
        for sid, title in conn.execute("SELECT id, title FROM sections"):
            # sid 格式: b1:ch01_s01 或 xe1:ch02_s03
            parts = sid.split(":")
            if len(parts) != 2:
                continue
            book, rest = parts
            sub = rest.split("_", 1)
            chapter = sub[0] if sub else ""
            section = sub[1] if len(sub) > 1 else ""
            section_info[sid] = {
                "book": book, "chapter": chapter,
                "section": section, "title": title or "",
            }

        # 聚合每个 L1 概念
        result: dict[str, list[dict]] = {}
        for l1_id in l1_ids:
            evi_row = conn.execute(
                "SELECT evidence_ids_json FROM concepts WHERE id=?", (l1_id,)
            ).fetchone()
            if not evi_row or not evi_row[0]:
                result[l1_id] = []
                continue
            try:
                evidence_ids = json.loads(evi_row[0])
            except (json.JSONDecodeError, TypeError):
                result[l1_id] = []
                continue

            seen_sections: set[str] = set()
            chapters: list[dict] = []
            for eid in evidence_ids:
                sid = evidence_to_section.get(eid)
                if sid and sid not in seen_sections:
                    seen_sections.add(sid)
                    if sid in section_info:
                        chapters.append(section_info[sid])

            result[l1_id] = chapters
        return result
    finally:
        conn.close()


async def compute_prerequisite_depth(db) -> dict[str, int]:
    """拓扑排序计算每个 L1 概念的前置链深度。

    环形依赖: 未被排序的节点统一赋值 max_rank + 1。
    """
    from collections import deque

    import sqlalchemy as sa

    from edu_cloud.modules.knowledge_tree.models import (
        ConceptGraphEdge,
        ConceptGraphNode,
    )

    # 加载所有 concept 节点
    node_result = await db.execute(
        sa.select(ConceptGraphNode.id)
        .where(ConceptGraphNode.node_type == "concept")
    )
    node_ids = {r[0] for r in node_result.all()}

    # 加载 hard edges
    edge_result = await db.execute(
        sa.select(ConceptGraphEdge.source_id, ConceptGraphEdge.target_id)
        .where(ConceptGraphEdge.relation_type == "prerequisite_hard")
    )
    edges = [(s, t) for s, t in edge_result.all() if s in node_ids and t in node_ids]

    adj: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)
    for cid in node_ids:
        in_degree[cid] = 0
    for s, t in edges:
        adj[s].append(t)
        in_degree[t] += 1

    queue: deque = deque([cid for cid in node_ids if in_degree[cid] == 0])
    depth: dict[str, int] = {cid: 0 for cid in queue}

    processed: set[str] = set()
    while queue:
        u = queue.popleft()
        if u in processed:
            continue
        processed.add(u)
        for v in adj[u]:
            new_depth = depth[u] + 1
            if v not in depth or depth[v] < new_depth:
                depth[v] = new_depth
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    # 环中节点 fallback
    max_depth = max(depth.values()) if depth else 0
    for cid in node_ids:
        if cid not in depth:
            depth[cid] = max_depth + 1

    return depth


def compute_importance_score(
    exam_frequency_percentile: float,
    prerequisite_depth: int,
    planning_weight: dict | None,
    max_depth: int = 6,
) -> float:
    """计算综合重要度得分，归一化到 [0, 10]。

    公式（设计文档 §7.3）:
        0.4 × exam_frequency_percentile × 10
      + 0.3 × error_prone_score
      + 0.2 × transfer_value
      + 0.1 × prerequisite_depth_factor × 10

    无 MCU 权重时用默认值 5.0 替代。
    """
    freq_component = exam_frequency_percentile * 10

    if planning_weight:
        error_prone = float(planning_weight.get("error_prone", 5))
        transfer_value = float(planning_weight.get("transfer_value", 5))
    else:
        error_prone = 5.0
        transfer_value = 5.0

    depth_component = min(prerequisite_depth / max_depth, 1.0) * 10

    score = (
        0.4 * freq_component +
        0.3 * error_prone +
        0.2 * transfer_value +
        0.1 * depth_component
    )
    return round(max(0.0, min(10.0, score)), 2)


async def compute_all_stats(db, kb_path: str) -> int:
    """编排全量计算：考频 + avg_difficulty + coverage + textbook + depth + importance。

    写入 concept_stats 表（UPSERT）。返回更新的记录数。
    """
    from datetime import datetime

    import sqlalchemy as sa

    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptStats

    freq = compute_exam_frequency(kb_path)
    difficulty = compute_avg_difficulty(kb_path)
    coverage = compute_exam_coverage(kb_path)
    chapters = compute_textbook_chapters(kb_path)
    depth = await compute_prerequisite_depth(db)

    # 加载 StudyUnit 映射（如果 knowledge.db 有）
    su_map: dict[str, tuple[str, int]] = {}  # concept_id → (su_id, estimated_minutes)
    try:
        kconn = sqlite3.connect(kb_path)
        for sid, concepts_json, minutes in kconn.execute(
            "SELECT id, source_concept_ids, estimated_minutes FROM study_units"
        ):
            try:
                concept_ids = json.loads(concepts_json) if concepts_json else []
                for cid in concept_ids:
                    su_map[cid] = (sid, minutes or 0)
            except json.JSONDecodeError:
                continue
        kconn.close()
    except Exception as e:
        logger.warning("load study_units failed: %s", e)

    # 加载已有 planning_weight（保留 MCU 导入结果）
    existing_weights: dict[str, dict] = {}
    existing_result = await db.execute(
        sa.select(ConceptStats.concept_id, ConceptStats.planning_weight)
        .where(ConceptStats.planning_weight.isnot(None))
    )
    for cid, pw in existing_result.all():
        if pw:
            existing_weights[cid] = pw

    # 计算考频百分位（rank-based）
    sorted_freqs = sorted(freq.values())

    def freq_percentile(f: int) -> float:
        if not sorted_freqs or max(sorted_freqs) == 0:
            return 0.0
        rank = sum(1 for x in sorted_freqs if x < f)
        return rank / len(sorted_freqs)

    # 加载所有 concept ID（从 PG）
    pg_concepts = await db.execute(
        sa.select(ConceptGraphNode.id)
        .where(ConceptGraphNode.node_type == "concept")
    )
    pg_concept_ids = {r[0] for r in pg_concepts.all()}

    now = datetime.now()
    updated = 0
    for cid in pg_concept_ids:
        f = freq.get(cid, 0)
        pct = freq_percentile(f)
        d = depth.get(cid, 0)
        pw = existing_weights.get(cid)
        importance = compute_importance_score(pct, d, pw)

        su = su_map.get(cid, (None, None))

        # UPSERT
        existing = await db.get(ConceptStats, cid)
        if existing:
            existing.exam_frequency = f
            existing.avg_difficulty = difficulty.get(cid)
            existing.exam_coverage = coverage.get(cid, 0.0)
            existing.textbook_chapters = chapters.get(cid, [])
            existing.prerequisite_depth = d
            existing.importance_score = importance
            existing.study_unit_id = su[0]
            existing.estimated_minutes = su[1]
            existing.computed_at = now
        else:
            db.add(ConceptStats(
                concept_id=cid,
                exam_frequency=f,
                avg_difficulty=difficulty.get(cid),
                exam_coverage=coverage.get(cid, 0.0),
                textbook_chapters=chapters.get(cid, []),
                prerequisite_depth=d,
                importance_score=importance,
                study_unit_id=su[0],
                estimated_minutes=su[1],
                planning_weight=pw,
                computed_at=now,
            ))
        updated += 1

    await db.commit()
    logger.info("compute_all_stats: updated %d records", updated)
    return updated
