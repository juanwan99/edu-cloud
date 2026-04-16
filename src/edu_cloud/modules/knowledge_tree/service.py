"""知识树业务逻辑：图谱查询、掌握度聚合、编辑操作。"""

import json
import logging
from collections import defaultdict
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap, ConceptStats,
)
from edu_cloud.modules.adaptive.models import StudentDaMastery, DaKnowledgePointMap

logger = logging.getLogger(__name__)

# BKT 4 态分类阈值（与 bkt_engine.py 一致）
_SOLID = 0.85
_FRAGILE = 0.6
_WEAK = 0.3


def _classify_state(mastery: float) -> str:
    if mastery >= _SOLID:
        return "solid"
    if mastery >= _FRAGILE:
        return "fragile"
    if mastery >= _WEAK:
        return "weak"
    return "unseen"


async def get_graph(db: AsyncSession, module: str = "all", include_draft: bool = True) -> dict:
    """查询图谱结构（navigation + graph 格式），v2 增强。"""
    module_filter = None if module == "all" else module

    # 1. BigConcept 节点
    bc_q = sa.select(ConceptGraphNode).where(ConceptGraphNode.node_type == "big_concept")
    if module_filter:
        bc_q = bc_q.where(ConceptGraphNode.primary_module == module_filter)
    bc_result = await db.execute(bc_q)
    bc_nodes = list(bc_result.scalars())

    # 2. concept_big_concept_map(is_primary=True)
    map_q = sa.select(ConceptBigConceptMap).where(ConceptBigConceptMap.is_primary == True)
    map_result = await db.execute(map_q)
    all_maps = list(map_result.scalars())

    # BigConcept → [concept_ids]
    bc_concept_ids: dict[str, list[str]] = defaultdict(list)
    concept_bc_id: dict[str, str] = {}
    for m in all_maps:
        bc_concept_ids[m.big_concept_id].append(m.concept_id)
        concept_bc_id[m.concept_id] = m.big_concept_id

    # 如果概念没有 is_primary map，fallback 到第一个 map 条目
    all_map_q = sa.select(ConceptBigConceptMap)
    all_map_result = await db.execute(all_map_q)
    for m in all_map_result.scalars():
        if m.concept_id not in concept_bc_id:
            concept_bc_id[m.concept_id] = m.big_concept_id
            bc_concept_ids[m.big_concept_id].append(m.concept_id)

    # 3. Concept 节点（只返回 node_type='concept'）
    concept_q = sa.select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    if module_filter:
        concept_q = concept_q.where(ConceptGraphNode.primary_module == module_filter)
    concept_result = await db.execute(concept_q)
    concept_nodes = list(concept_result.scalars())

    # 4. Edges — 查全部 edge（包含跨模块，用于 hard 计数和 external refs）
    all_edge_result = await db.execute(sa.select(ConceptGraphEdge))
    all_edges = list(all_edge_result.scalars())

    # 获取所有 concept 的 id→(name, module) 映射（用于 external_hard_refs）
    all_concept_q = sa.select(
        ConceptGraphNode.id, ConceptGraphNode.name, ConceptGraphNode.primary_module
    ).where(ConceptGraphNode.node_type == "concept")
    all_concepts_lookup = {
        r[0]: {"name": r[1], "module": r[2]}
        for r in (await db.execute(all_concept_q)).all()
    }

    # 计算 hard_in/out 计数（基于全量 edge）
    hard_in_count: dict[str, int] = defaultdict(int)
    hard_out_count: dict[str, int] = defaultdict(int)
    for e in all_edges:
        if e.relation_type == "prerequisite_hard":
            hard_in_count[e.target_id] += 1
            hard_out_count[e.source_id] += 1

    # 计算 external_hard_refs（仅 module 过滤时）
    concept_ids_in_view = {n.id for n in concept_nodes}
    external_refs: dict[str, dict] = {}
    if module_filter:
        for e in all_edges:
            if e.relation_type != "prerequisite_hard":
                continue
            src_in = e.source_id in concept_ids_in_view
            tgt_in = e.target_id in concept_ids_in_view
            if src_in and not tgt_in:
                # 出边（本模块→外模块）
                refs = external_refs.setdefault(e.source_id, {"in": [], "out": []})
                info = all_concepts_lookup.get(e.target_id)
                if info:
                    refs["out"].append({"id": e.target_id, "name": info["name"], "module": info["module"]})
            elif tgt_in and not src_in:
                # 入边（外模块→本模块）
                refs = external_refs.setdefault(e.target_id, {"in": [], "out": []})
                info = all_concepts_lookup.get(e.source_id)
                if info:
                    refs["in"].append({"id": e.source_id, "name": info["name"], "module": info["module"]})

    # 过滤 edge（module 过滤时只保留模块内 edge）
    if module_filter:
        filtered_edges = [e for e in all_edges
                          if e.source_id in concept_ids_in_view and e.target_id in concept_ids_in_view]
    else:
        filtered_edges = all_edges

    # 发布过滤（在 hard 计数之后，navigation 构建之前）
    if not include_draft:
        visible_statuses = {"teacher_reviewed", "published"}
        concept_nodes = [n for n in concept_nodes if (n.review_status or "ai_draft") in visible_statuses]
        concept_ids_in_view = {n.id for n in concept_nodes}
        # 重建 bc_concept_ids（只保留可见概念）
        for bc_id in bc_concept_ids:
            bc_concept_ids[bc_id] = [c for c in bc_concept_ids[bc_id] if c in concept_ids_in_view]
        # 过滤 edge：边自身状态 + 端点可见性
        edge_visible = {"teacher_reviewed", "published"}
        filtered_edges = [e for e in filtered_edges
                          if (e.review_status or "ai_draft") in edge_visible
                          and e.source_id in concept_ids_in_view
                          and e.target_id in concept_ids_in_view]

    # 5. 构建 navigation
    module_bcs: dict[str, list[dict]] = defaultdict(list)
    for bc in bc_nodes:
        cids = bc_concept_ids.get(bc.id, [])
        # 过滤：module filter + publish filter 后只保留可见概念
        if module_filter or not include_draft:
            cids = [c for c in cids if c in concept_ids_in_view]
        module_bcs[bc.primary_module].append({
            "id": bc.id, "name": bc.name, "concept_ids": cids,
        })

    # 模块名映射
    module_names = {
        "M1": "分子与细胞", "M2": "遗传与进化",
        "M3": "稳态与调节", "M4": "生态与环境", "M5": "生物技术",
    }
    navigation = []
    for mod in sorted(module_bcs.keys()):
        navigation.append({
            "id": mod,
            "name": module_names.get(mod, mod),
            "big_concepts": module_bcs[mod],
        })

    # 6. 加载 concept_stats（v3）— 在 publish 过滤后 concept_nodes 已定版
    #    module=all 全表加载；带模块过滤时按 IN(concept_nodes.id) 收窄
    stats_q = sa.select(ConceptStats)
    if module_filter:
        stats_q = stats_q.where(
            ConceptStats.concept_id.in_([n.id for n in concept_nodes])
        )
    stats_result = await db.execute(stats_q)
    stats_by_id: dict[str, ConceptStats] = {
        s.concept_id: s for s in stats_result.scalars()
    }

    # 7. 构建 graph
    nodes = []
    for n in concept_nodes:
        aliases = json.loads(n.aliases_json) if n.aliases_json else []
        s = stats_by_id.get(n.id)
        nodes.append({
            "id": n.id, "name": n.name, "level": n.knowledge_level,
            "module": n.primary_module,
            "big_concept_id": concept_bc_id.get(n.id),
            "aliases": aliases,
            "review_status": n.review_status,
            "difficulty": n.difficulty,
            "bloom_level": n.bloom_level,
            "description": n.description,
            "hard_in_count": hard_in_count.get(n.id, 0),
            "hard_out_count": hard_out_count.get(n.id, 0),
            "external_hard_refs": external_refs.get(n.id) if module_filter else None,
            # v3 stats 合并（无记录时回退默认，avg_difficulty 保留 None 语义）
            "exam_frequency": s.exam_frequency if s else 0,
            "exam_coverage": s.exam_coverage if s else 0.0,
            "avg_difficulty": s.avg_difficulty if s else None,
            "importance_score": s.importance_score if s else 0.0,
            "textbook_chapters": s.textbook_chapters if s else [],
            "study_unit_id": s.study_unit_id if s else None,
            "estimated_minutes": s.estimated_minutes if s else None,
            "prerequisite_depth": s.prerequisite_depth if s else 0,
            "planning_weight": s.planning_weight if s else None,
        })
    edges = [
        {"id": e.id, "source": e.source_id, "target": e.target_id, "type": e.relation_type,
         "strength": e.strength, "confidence": e.confidence,
         "review_status": e.review_status}
        for e in filtered_edges
    ]

    return {
        "navigation": navigation,
        "graph": {"nodes": nodes, "edges": edges},
    }


async def get_mastery(db: AsyncSession, student_id: str, module: str = "all", school_id: str | None = None) -> dict:
    """查询学生掌握度，聚合到概念和模块级别。"""
    # 1. 获取概念节点（F001: 排除 big_concept）
    node_q = sa.select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    if module != "all":
        node_q = node_q.where(ConceptGraphNode.primary_module == module)
    nodes_result = await db.execute(node_q)
    nodes = list(nodes_result.scalars())

    if not nodes:
        return {"student_id": student_id, "concept_mastery": [], "module_mastery": []}

    node_ids = [n.id for n in nodes]

    # 2. 获取概念→DA 映射
    map_q = sa.select(DaKnowledgePointMap).where(
        DaKnowledgePointMap.knowledge_point_id.in_(node_ids)
    )
    maps_result = await db.execute(map_q)
    maps = list(maps_result.scalars())

    # concept_id → [da_id, ...]
    concept_das = defaultdict(list)
    for m in maps:
        concept_das[m.knowledge_point_id].append(m.da_id)

    # 3. 获取学生的 DA 掌握度
    all_da_ids = [da for das in concept_das.values() for da in das]
    mastery_map = {}
    if all_da_ids:
        mastery_q = sa.select(StudentDaMastery).where(
            StudentDaMastery.student_id == student_id,
            StudentDaMastery.da_id.in_(all_da_ids),
        )
        if school_id:
            mastery_q = mastery_q.where(StudentDaMastery.school_id == school_id)
        mastery_result = await db.execute(mastery_q)
        for m in mastery_result.scalars():
            mastery_map[m.da_id] = m.mastery_prob

    # 4. 聚合到概念级别
    concept_mastery = []
    module_scores = defaultdict(list)

    for node in nodes:
        das = concept_das.get(node.id, [])
        if not das:
            concept_mastery.append({
                "concept_id": node.id,
                "mastery": 0.0,
                "state": "unseen",
                "da_count": 0,
            })
            module_scores[node.primary_module].append(0.0)
            continue

        da_masteries = [mastery_map.get(da_id, 0.0) for da_id in das]
        avg_mastery = sum(da_masteries) / len(da_masteries)
        concept_mastery.append({
            "concept_id": node.id,
            "mastery": round(avg_mastery, 4),
            "state": _classify_state(avg_mastery),
            "da_count": len(das),
        })
        module_scores[node.primary_module].append(avg_mastery)

    # 5. 聚合到模块级别
    module_mastery = []
    for mod, scores in sorted(module_scores.items()):
        avg = sum(scores) / len(scores) if scores else 0.0
        module_mastery.append({"module": mod, "mastery": round(avg, 4)})

    return {
        "student_id": student_id,
        "concept_mastery": concept_mastery,
        "module_mastery": module_mastery,
    }


async def search_concepts(db: AsyncSession, q: str, limit: int = 20) -> list[dict]:
    """搜索知识点（name + aliases_json + description）。R3-F005: service 层实现。"""
    pattern = f"%{q}%"
    results = await db.execute(
        sa.select(ConceptGraphNode)
        .where(ConceptGraphNode.node_type == "concept")
        .where(sa.or_(
            ConceptGraphNode.name.ilike(pattern),
            ConceptGraphNode.aliases_json.ilike(pattern),
            ConceptGraphNode.description.ilike(pattern),
        ))
        .limit(limit)
    )
    return [
        {
            "id": n.id, "name": n.name, "module": n.primary_module,
            "aliases": json.loads(n.aliases_json) if n.aliases_json else [],
        }
        for n in results.scalars()
    ]


# 字段白名单：只允许修改设计文档规定的字段
# review_status 不在白名单中（R3-F003），必须通过 set_review_status op 走状态机
_NODE_UPDATABLE = {"name", "description", "difficulty", "bloom_level", "aliases_json", "display_order"}
_CONTENT_FIELDS = {"name", "description", "aliases_json", "difficulty", "bloom_level"}
_EDGE_UPDATABLE = {"strength"}

# R3-F003: 审核状态机合法转移
_VALID_TRANSITIONS = {
    "ai_draft": {"teacher_reviewed"},
    "teacher_reviewed": {"published", "ai_draft"},
    "published": {"ai_draft"},
}

_EDGE_VALID_TRANSITIONS = {
    "ai_draft": {"teacher_reviewed", "rejected"},
    "teacher_reviewed": {"published", "rejected"},
    "published": {"ai_draft"},
    "rejected": {"ai_draft"},
}


async def apply_edits(db: AsyncSession, operations: list[dict]) -> int:
    """执行编辑操作，返回成功数量。"""
    now = datetime.now()
    applied = 0

    for op_data in operations:
        op = op_data["op"]

        if op == "add_node":
            db.add(ConceptGraphNode(
                id=op_data["id"],
                name=op_data["name"],
                knowledge_level=op_data.get("level", "L1"),
                primary_module=op_data.get("module", "unknown"),
                description=op_data.get("description"),
                synced_at=now,
            ))
            applied += 1

        elif op == "remove_node":
            # 先删关联边
            await db.execute(
                sa.delete(ConceptGraphEdge).where(
                    sa.or_(
                        ConceptGraphEdge.source_id == op_data["id"],
                        ConceptGraphEdge.target_id == op_data["id"],
                    )
                )
            )
            await db.execute(
                sa.delete(ConceptGraphNode).where(ConceptGraphNode.id == op_data["id"])
            )
            applied += 1

        elif op == "update_node":
            fields = {k: v for k, v in op_data.get("fields", {}).items() if k in _NODE_UPDATABLE}
            if fields:
                await db.execute(
                    sa.update(ConceptGraphNode)
                    .where(ConceptGraphNode.id == op_data["id"])
                    .values(**fields)
                )
                # R3-F003: published 概念被内容修改后自动回退到 ai_draft
                content_changed = bool(fields.keys() & _CONTENT_FIELDS)
                if content_changed:
                    node = await db.get(ConceptGraphNode, op_data["id"])
                    if node and node.review_status == "published":
                        node.review_status = "ai_draft"
                        node.reviewed_by = None
                        node.reviewed_at = None
                applied += 1

        elif op == "set_review_status":
            new_status = op_data.get("status")
            edge_id = op_data.get("edge_id")
            if edge_id is not None:
                # Edge 审核
                edge = await db.get(ConceptGraphEdge, edge_id)
                current_status = (edge.review_status or "ai_draft") if edge else None
                if edge and new_status in _EDGE_VALID_TRANSITIONS.get(current_status, set()):
                    edge.review_status = new_status
                    # 附加 edge 坐标供 backwrite
                    op_data["_edge_source"] = edge.source_id
                    op_data["_edge_target"] = edge.target_id
                    op_data["_edge_type"] = edge.relation_type
                    applied += 1
            else:
                # Node 审核（R3-F003: 状态机校验 + 审计字段）
                node = await db.get(ConceptGraphNode, op_data.get("id"))
                current_status = (node.review_status or "ai_draft") if node else None
                if node and new_status in _VALID_TRANSITIONS.get(current_status, set()):
                    node.review_status = new_status
                    node.reviewed_by = op_data.get("user_id")
                    node.reviewed_at = datetime.now().isoformat()
                    applied += 1

        elif op == "reorder":
            # R3-F004: 作用域验证 — 只更新属于指定 BigConcept 的概念
            bc_id = op_data.get("big_concept_id")
            valid_cids = set()
            if bc_id:
                maps = await db.execute(
                    sa.select(ConceptBigConceptMap.concept_id)
                    .where(ConceptBigConceptMap.big_concept_id == bc_id)
                )
                valid_cids = {r[0] for r in maps}
            for idx, cid in enumerate(op_data.get("concept_ids", [])):
                if not bc_id or cid in valid_cids:
                    await db.execute(
                        sa.update(ConceptGraphNode)
                        .where(ConceptGraphNode.id == cid)
                        .values(display_order=idx)
                    )
            applied += 1

        elif op == "add_edge":
            db.add(ConceptGraphEdge(
                source_id=op_data["source"],
                target_id=op_data["target"],
                relation_type=op_data["type"],
                strength=op_data.get("strength", 1.0),
                confidence=1.0,
                synced_at=now,
            ))
            applied += 1

        elif op == "remove_edge":
            await db.execute(
                sa.delete(ConceptGraphEdge).where(
                    ConceptGraphEdge.source_id == op_data["source"],
                    ConceptGraphEdge.target_id == op_data["target"],
                    ConceptGraphEdge.relation_type == op_data["type"],
                )
            )
            applied += 1

        elif op == "update_edge":
            fields = {k: v for k, v in op_data.get("fields", {}).items() if k in _EDGE_UPDATABLE}
            if fields:
                await db.execute(
                    sa.update(ConceptGraphEdge)
                    .where(
                        ConceptGraphEdge.source_id == op_data["source"],
                        ConceptGraphEdge.target_id == op_data["target"],
                        ConceptGraphEdge.relation_type == op_data["type"],
                    )
                    .values(**fields)
                )
                applied += 1

    await db.commit()

    # 回写到 knowledge.db（best-effort，失败记录到 edit_sync_failures）
    import os
    from pathlib import Path
    kb_path = os.environ.get("KNOWLEDGE_DB_PATH", str(Path.home() / "edu-knowledge-base" / "knowledge.db"))
    if operations:
        await backwrite_to_knowledge_db(db, kb_path, operations)

    return applied


async def backwrite_to_knowledge_db(
    db: AsyncSession, knowledge_db_path: str, operations: list[dict]
) -> dict:
    """将编辑操作回写到 knowledge.db（单向同步补偿）。"""
    import json
    import sqlite3 as stdlib_sqlite3

    # 回写时允许的额外字段（PG 专用字段不回写）
    _BACKWRITE_UPDATABLE = _NODE_UPDATABLE | {"review_status"}

    try:
        conn = stdlib_sqlite3.connect(knowledge_db_path)
        # 检查 knowledge.db 有哪些列
        existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(concepts)")}

        for op_data in operations:
            op = op_data["op"]
            if op == "update_node":
                fields = {k: v for k, v in op_data.get("fields", {}).items()
                          if k in _BACKWRITE_UPDATABLE and k in existing_cols}
                for col, val in fields.items():
                    conn.execute(
                        f"UPDATE concepts SET {col}=? WHERE id=?",
                        (val, op_data["id"]),
                    )
            elif op == "set_review_status":
                edge_id = op_data.get("edge_id")
                if edge_id is not None:
                    # Edge review status backwrite
                    edge_review_cols = {r[1] for r in conn.execute("PRAGMA table_info(concept_relations)")}
                    if "review_status" in edge_review_cols:
                        conn.execute(
                            "UPDATE concept_relations SET review_status=? WHERE source_id=? AND target_id=? AND relation_type=?",
                            (op_data.get("status"), op_data.get("_edge_source"),
                             op_data.get("_edge_target"), op_data.get("_edge_type")),
                        )
                else:
                    if "review_status" in existing_cols:
                        conn.execute(
                            "UPDATE concepts SET review_status=? WHERE id=?",
                            (op_data.get("status"), op_data.get("id")),
                        )
            elif op == "add_node":
                conn.execute(
                    "INSERT OR REPLACE INTO concepts (id, name, knowledge_level, description) VALUES (?, ?, ?, ?)",
                    (op_data["id"], op_data.get("name", ""), op_data.get("level", "L1"), op_data.get("description")),
                )
            elif op == "remove_node":
                conn.execute("DELETE FROM concepts WHERE id=?", (op_data["id"],))
                conn.execute("DELETE FROM concept_relations WHERE source_id=? OR target_id=?",
                             (op_data["id"], op_data["id"]))
            elif op == "add_edge":
                conn.execute(
                    "INSERT OR REPLACE INTO concept_relations (source_id, target_id, relation_type, strength, confidence) VALUES (?, ?, ?, ?, ?)",
                    (op_data["source"], op_data["target"], op_data.get("type", "prerequisite_hard"),
                     op_data.get("strength", 1.0), op_data.get("confidence", 1.0)),
                )
            elif op == "remove_edge":
                conn.execute(
                    "DELETE FROM concept_relations WHERE source_id=? AND target_id=? AND relation_type=?",
                    (op_data["source"], op_data["target"], op_data["type"]),
                )
            elif op == "update_edge":
                fields = {k: v for k, v in op_data.get("fields", {}).items() if k in _EDGE_UPDATABLE}
                for col, val in fields.items():
                    conn.execute(
                        f"UPDATE concept_relations SET {col}=? WHERE source_id=? AND target_id=? AND relation_type=?",
                        (val, op_data["source"], op_data["target"], op_data["type"]),
                    )
        conn.commit()
        conn.close()
        logger.info("backwrite to knowledge.db succeeded: %d operations", len(operations))
        return {"success": True, "synced": len(operations)}
    except Exception as e:
        logger.error("backwrite to knowledge.db failed: %s", e)
        # 记录失败
        from edu_cloud.modules.knowledge_tree.models import EditSyncFailure
        db.add(EditSyncFailure(
            operation_json=json.dumps(operations, ensure_ascii=False),
            error_message=str(e),
            created_at=datetime.now(),
        ))
        await db.commit()
        return {"success": False, "error": str(e)}
