"""概念→高考真题查询 + 知识图谱统计概览。

链路:
  concept_id → diagnostic_attributes.linked_concept_ids
            → q_matrix(attribute_id → item_id)
            → assessment_items

统计概览聚合自 ConceptGraphNode + ConceptGraphEdge + ConceptStats 投影。
"""
import json
import logging
import sqlite3
from collections import defaultdict

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptGraphEdge, ConceptStats,
)

logger = logging.getLogger(__name__)


def get_exam_items(
    kb_path: str,
    concept_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询某概念关联的高考真题。

    Args:
        kb_path: knowledge.db 绝对路径
        concept_id: 概念节点 ID
        page: 页码（1-based）
        page_size: 每页数量

    Returns:
        {total: int, items: list, page: int, page_size: int}
        未关联或概念不存在时 total=0 / items=[]（降级，不抛）
    """
    conn = sqlite3.connect(kb_path)
    try:
        # 1. 找到关联该概念的 DA
        das: list[str] = []
        for da_id, linked in conn.execute(
            "SELECT id, linked_concept_ids FROM diagnostic_attributes "
            "WHERE linked_concept_ids IS NOT NULL"
        ):
            try:
                if concept_id in json.loads(linked):
                    das.append(da_id)
            except (json.JSONDecodeError, TypeError):
                continue

        if not das:
            return {"total": 0, "items": [], "page": page, "page_size": page_size}

        # 2. 找所有关联 item_id（去重 + INNER JOIN 过滤 + 稳定排序）
        # INNER JOIN assessment_items：q_matrix 引用 assessment_items 不存在 id 时
        # 在分页前过滤掉，保证 total/page_ids/items 三者一致（N001 修复）
        # ORDER BY item_id ASC：保证翻页之间页边界确定，避免 SQLite 默认顺序抖动
        placeholders = ",".join("?" * len(das))
        item_ids_rows = conn.execute(
            f"SELECT DISTINCT q.item_id FROM q_matrix q "
            f"INNER JOIN assessment_items a ON q.item_id = a.id "
            f"WHERE q.attribute_id IN ({placeholders}) "
            f"ORDER BY q.item_id ASC",
            das,
        ).fetchall()
        item_ids = [r[0] for r in item_ids_rows]
        total = len(item_ids)
        if total == 0:
            return {"total": 0, "items": [], "page": page, "page_size": page_size}

        # 3. 分页取 id 切片（按 item_id ASC 顺序）
        offset = (page - 1) * page_size
        page_ids = item_ids[offset:offset + page_size]
        if not page_ids:
            return {"total": total, "items": [], "page": page, "page_size": page_size}

        # 4. 查询题目详情
        # 🔀 plan 原设 difficulty 列，但 knowledge.db.assessment_items 实际 schema
        # 有 score/options/module_tag，无 difficulty。改为返回 score + options（raw JSON）
        # 详情查询用 dict 索引重排，保持 page_ids 顺序（IN(...) 不保证返回顺序与参数序一致）
        placeholders_p = ",".join("?" * len(page_ids))
        rows_by_id = {}
        for row in conn.execute(
            f"""SELECT id, exam_id, question_number, question_type, stem,
                       answer, score, options, explanation, module_tag
                FROM assessment_items WHERE id IN ({placeholders_p})""",
            page_ids,
        ):
            rows_by_id[row[0]] = row

        items = []
        for pid in page_ids:
            row = rows_by_id.get(pid)
            if row is None:
                continue  # 防御性：经 INNER JOIN 过滤后理论上不应触发
            items.append({
                "id": row[0],
                "exam_id": row[1],
                "question_number": row[2],
                "question_type": row[3],
                "stem": row[4],
                "answer": row[5],
                "score": row[6],
                "options": row[7],
                "explanation": row[8],
                "module_tag": row[9],
            })

        return {"total": total, "items": items, "page": page, "page_size": page_size}
    finally:
        conn.close()


async def get_stats_overview(db: AsyncSession, module: str = "all") -> dict:
    """知识图谱全模块统计概览。

    Args:
        db: async session
        module: "all" 或具体模块 ID（M1/M2/...）

    Returns:
        {
          total_concepts: int,
          total_edges: int,
          exam_freq_distribution: {high, mid, low, zero},
          module_stats: {M1: {concepts, edges, avg_freq, exam_coverage}, ...},
        }
    """
    # 1. 概念（按 module filter）
    node_q = sa.select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    if module != "all":
        node_q = node_q.where(ConceptGraphNode.primary_module == module)
    nodes = list((await db.execute(node_q)).scalars())
    node_ids = {n.id for n in nodes}

    # 2. 边（module filter 时只保留端点都在视图内的边）
    all_edges = list((await db.execute(sa.select(ConceptGraphEdge))).scalars())
    edges = (
        [e for e in all_edges if e.source_id in node_ids and e.target_id in node_ids]
        if module != "all" else all_edges
    )

    # 3. ConceptStats 预加载
    stats_q = sa.select(ConceptStats)
    if module != "all":
        stats_q = stats_q.where(ConceptStats.concept_id.in_(node_ids))
    stats = list((await db.execute(stats_q)).scalars())
    stats_by_id = {s.concept_id: s for s in stats}

    # 4. 考频分布：high>=500 / mid[50,499] / low[1,49] / zero=0
    distribution = {"high": 0, "mid": 0, "low": 0, "zero": 0}
    module_stats: dict[str, dict] = defaultdict(
        lambda: {
            "concepts": 0, "edges": 0, "total_freq": 0,
            "nonzero_freq_count": 0, "avg_freq": 0.0, "exam_coverage": 0.0,
        }
    )
    for n in nodes:
        s = stats_by_id.get(n.id)
        freq = s.exam_frequency if s else 0
        if freq >= 500:
            distribution["high"] += 1
        elif freq >= 50:
            distribution["mid"] += 1
        elif freq >= 1:
            distribution["low"] += 1
        else:
            distribution["zero"] += 1
        ms = module_stats[n.primary_module]
        ms["concepts"] += 1
        ms["total_freq"] += freq
        if freq > 0:
            ms["nonzero_freq_count"] += 1

    # 5. 边按 source 所属 module 计数
    nodes_by_id = {n.id: n for n in nodes}
    for e in edges:
        src = nodes_by_id.get(e.source_id)
        if src:
            module_stats[src.primary_module]["edges"] += 1

    # 6. 派生指标：avg_freq + exam_coverage（非零比例）
    for mod, ms in module_stats.items():
        if ms["concepts"]:
            ms["avg_freq"] = round(ms["total_freq"] / ms["concepts"], 1)
            ms["exam_coverage"] = round(ms["nonzero_freq_count"] / ms["concepts"], 3)
        # 中间字段从响应中剥离
        del ms["total_freq"]
        del ms["nonzero_freq_count"]

    return {
        "total_concepts": len(nodes),
        "total_edges": len(edges),
        "exam_freq_distribution": distribution,
        "module_stats": dict(module_stats),
    }
