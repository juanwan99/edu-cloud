"""knowledge.db → PostgreSQL 同步服务（app 启动时调用）。"""
import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap

logger = logging.getLogger(__name__)

# F003: 路径从 settings 读取，不硬编码
_MODULE_RE = re.compile(r"_M(\d+)_")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """检查表是否存在。"""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    return row[0] > 0


def _column_exists(conn: sqlite3.Connection, table_name: str, col_name: str) -> bool:
    """检查列是否存在。"""
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table_name})")}
    return col_name in cols


_MODULE_NAMES = {
    "M1": "分子与细胞",
    "M2": "遗传与进化",
    "M3": "稳态与调节",
    "M4": "生态与环境",
    "M5": "生物技术与工程",
}


def _read_knowledge_db(db_path: str) -> dict:
    """读取 knowledge.db：L1 concepts + big_concepts + edges + map + study_units + edge_evidence。

    Returns: dict with keys: concepts, big_concepts, edges, maps, study_units, edge_evidence
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 检查可选列/表
    has_difficulty = _column_exists(conn, "concepts", "difficulty")
    has_bloom = _column_exists(conn, "concepts", "bloom_level")
    has_aliases = _column_exists(conn, "concepts", "aliases_json")
    has_evidence = _column_exists(conn, "concepts", "evidence_ids_json")
    has_review = _column_exists(conn, "concepts", "review_status")
    has_big_concepts = _table_exists(conn, "big_concepts")
    has_map = _table_exists(conn, "concept_big_concept_map")
    has_study_units = _table_exists(conn, "study_units")

    # 1. 只读 L1 concepts
    cols = "id, name, knowledge_level, description"
    if has_difficulty:
        cols += ", difficulty"
    if has_bloom:
        cols += ", bloom_level"
    if has_aliases:
        cols += ", aliases_json"
    if has_evidence:
        cols += ", evidence_ids_json"
    if has_review:
        cols += ", review_status"

    l1_nodes = []
    for row in conn.execute(f"SELECT {cols} FROM concepts WHERE knowledge_level = 'L1'"):
        m = _MODULE_RE.search(row["id"])
        node = {
            "id": row["id"], "name": row["name"],
            "knowledge_level": "L1",
            "primary_module": f"M{m.group(1)}" if m else "unknown",
            "description": row["description"],
            "node_type": "concept",
            "difficulty": row["difficulty"] if has_difficulty else None,
            "bloom_level": row["bloom_level"] if has_bloom else None,
            "aliases_json": row["aliases_json"] if has_aliases else None,
            "evidence_ids_json": row["evidence_ids_json"] if has_evidence else None,
            "review_status": row["review_status"] if has_review else None,
        }
        l1_nodes.append(node)

    # 2. BigConcepts（容错：表不存在则返回空）
    bc_nodes = []
    if has_big_concepts:
        for row in conn.execute("SELECT id, name, module, display_order FROM big_concepts"):
            bc_nodes.append({
                "id": row["id"], "name": row["name"],
                "knowledge_level": "L1",
                "primary_module": row["module"],
                "description": None,
                "node_type": "big_concept",
                "display_order": row["display_order"] or 0,
            })

    # 3. Edges（只读 L1 节点之间的边）
    l1_ids = {n["id"] for n in l1_nodes}
    has_edge_review = _column_exists(conn, "concept_relations", "review_status")
    edge_cols = "source_id, target_id, relation_type, strength, confidence"
    if has_edge_review:
        edge_cols += ", review_status"
    edges = []
    for row in conn.execute(f"SELECT {edge_cols} FROM concept_relations"):
        if row["source_id"] in l1_ids and row["target_id"] in l1_ids:
            edges.append({
                "source_id": row["source_id"], "target_id": row["target_id"],
                "relation_type": row["relation_type"],
                "strength": row["strength"] or 1.0, "confidence": row["confidence"] or 1.0,
                "review_status": row["review_status"] if has_edge_review else None,
            })

    # 4. Map（容错）
    maps = []
    if has_map:
        for row in conn.execute("SELECT concept_id, big_concept_id, is_primary FROM concept_big_concept_map"):
            if row["concept_id"] in l1_ids:  # 跳过不存在的 L1
                maps.append({
                    "concept_id": row["concept_id"],
                    "big_concept_id": row["big_concept_id"],
                    "is_primary": bool(row["is_primary"]),
                })

    # 5. Study units（容错：表不存在 / 旧 schema 缺列 → 返回空）
    study_units = []
    if has_study_units and _column_exists(conn, "study_units", "name"):
        su_rows = conn.execute(
            "SELECT id, name, description, source_concept_ids, module, estimated_minutes FROM study_units"
        ).fetchall()
        for su in su_rows:
            source_ids = json.loads(su["source_concept_ids"]) if su["source_concept_ids"] else []
            study_units.append({
                "id": su["id"], "name": su["name"], "description": su["description"],
                "source_concept_ids": source_ids, "module": su["module"],
                "estimated_minutes": su["estimated_minutes"],
            })

    # 6. Edge evidence + pedagogical_use（enrichment for concept-relation edges）
    #    容错：旧 schema 可能没有 evidence/pedagogical_use 列
    edge_evidence: dict[tuple[str, str, str], dict] = {}
    has_edge_evidence = _column_exists(conn, "concept_relations", "evidence")
    has_edge_ped = _column_exists(conn, "concept_relations", "pedagogical_use")
    if has_edge_evidence or has_edge_ped:
        ev_cols = "source_id, target_id, relation_type"
        if has_edge_evidence:
            ev_cols += ", evidence"
        if has_edge_ped:
            ev_cols += ", pedagogical_use"
        enriched_edges = conn.execute(f"SELECT {ev_cols} FROM concept_relations").fetchall()
        for e in enriched_edges:
            key = (e["source_id"], e["target_id"], e["relation_type"])
            edge_evidence[key] = {
                "evidence": e["evidence"] if has_edge_evidence else None,
                "pedagogical_use": e["pedagogical_use"] if has_edge_ped else None,
            }

    conn.close()
    return {
        "concepts": l1_nodes,
        "big_concepts": bc_nodes,
        "edges": edges,
        "maps": maps,
        "study_units": study_units,
        "edge_evidence": edge_evidence,
    }


async def _sync_graph(
    db: AsyncSession,
    data: dict,
) -> dict:
    """写入 3 层图谱数据（仅 flush，不 commit — F002 单事务）。

    Layers: module → study_unit → concept (+ big_concept)
    Edges: contains (hierarchy) + concept-relation (enriched with evidence/pedagogical_use)

    Returns: counts dict for logging.
    """
    now = datetime.now()
    l1_nodes = data["concepts"]
    bc_nodes = data["big_concepts"]
    edges = data["edges"]
    maps = data["maps"]
    study_units = data["study_units"]
    edge_evidence = data["edge_evidence"]

    # KNU-007: 仅删边和 map（无 FK 指向它们）；节点改为 upsert 防止 FK 违约。
    # question_knowledge_points.concept_id 和 student_knp_mastery.concept_id
    # 都有 FK → concept_graph_nodes.id，直接 DELETE ALL nodes 会触发 FK violation。
    await db.execute(sa.delete(ConceptBigConceptMap))
    await db.execute(sa.delete(ConceptGraphEdge))
    await db.flush()

    async def _upsert_node(node_id: str, **kwargs) -> None:
        existing = await db.get(ConceptGraphNode, node_id)
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
        else:
            db.add(ConceptGraphNode(id=node_id, **kwargs))

    # 1. 写 Module 节点（5 个）
    modules_seen: set[str] = set()
    for n in l1_nodes:
        modules_seen.add(n["primary_module"])
    for su in study_units:
        modules_seen.add(su["module"])

    for mod in sorted(modules_seen):
        mod_id = f"mod:bio_sr:{mod}"
        mod_name = _MODULE_NAMES.get(mod, mod)
        await _upsert_node(
            mod_id, name=mod_name, knowledge_level="L1",
            primary_module=mod, description=None,
            node_type="module", subject="biology", course_code="SW",
            synced_at=now,
        )
    await db.flush()

    # 2. 写 Study Unit 节点（99 个）
    for su in study_units:
        await _upsert_node(
            su["id"], name=su["name"], knowledge_level="L1",
            primary_module=su["module"], description=su.get("description"),
            node_type="study_unit", subject="biology", course_code="SW",
            synced_at=now,
        )
    await db.flush()

    # 3. 写 BigConcept 节点
    for n in bc_nodes:
        await _upsert_node(
            n["id"], name=n["name"], knowledge_level=n["knowledge_level"],
            primary_module=n["primary_module"], description=n.get("description"),
            node_type="big_concept", display_order=n.get("display_order", 0),
            synced_at=now,
        )
    await db.flush()

    # 4. 写 L1 Concept 节点（108 个，enriched with subject/course_code）
    for n in l1_nodes:
        await _upsert_node(
            n["id"], name=n["name"], knowledge_level=n["knowledge_level"],
            primary_module=n["primary_module"], description=n.get("description"),
            node_type="concept", subject="biology", course_code="SW",
            difficulty=n.get("difficulty"),
            bloom_level=n.get("bloom_level"),
            aliases_json=n.get("aliases_json"),
            evidence_ids_json=n.get("evidence_ids_json"),
            review_status=n.get("review_status"),
            synced_at=now,
        )
    await db.flush()

    # 5. 写 BigConcept map
    for m in maps:
        db.add(ConceptBigConceptMap(
            concept_id=m["concept_id"],
            big_concept_id=m["big_concept_id"],
            is_primary=m["is_primary"],
        ))
    await db.flush()

    # 6. 写 hierarchy contains edges
    #    a) module → study_unit (one per SU)
    #    b) study_unit → concept (each SU maps to exactly 1 concept via source_concept_ids)
    #    c) module → orphan concept (concepts with no SU, linked directly to module)
    contains_count = 0
    concept_to_su: dict[str, str] = {}  # concept_id → study_unit_id (for orphan detection)

    for su in study_units:
        mod_id = f"mod:bio_sr:{su['module']}"
        # module → study_unit
        db.add(ConceptGraphEdge(
            source_id=mod_id, target_id=su["id"],
            relation_type="contains", strength=1.0, confidence=1.0,
            synced_at=now,
        ))
        contains_count += 1

        # study_unit → concept(s)
        for cid in su["source_concept_ids"]:
            db.add(ConceptGraphEdge(
                source_id=su["id"], target_id=cid,
                relation_type="contains", strength=1.0, confidence=1.0,
                synced_at=now,
            ))
            contains_count += 1
            concept_to_su[cid] = su["id"]

    # orphan concepts → direct module link
    for n in l1_nodes:
        if n["id"] not in concept_to_su:
            mod_id = f"mod:bio_sr:{n['primary_module']}"
            db.add(ConceptGraphEdge(
                source_id=mod_id, target_id=n["id"],
                relation_type="contains", strength=1.0, confidence=1.0,
                synced_at=now,
            ))
            contains_count += 1

    await db.flush()

    # 7. 写 concept-relation edges（enriched with evidence + pedagogical_use）
    for e in edges:
        key = (e["source_id"], e["target_id"], e["relation_type"])
        ev = edge_evidence.get(key, {})
        db.add(ConceptGraphEdge(
            source_id=e["source_id"], target_id=e["target_id"],
            relation_type=e["relation_type"], strength=e["strength"],
            confidence=e["confidence"],
            evidence=ev.get("evidence"),
            pedagogical_use=ev.get("pedagogical_use"),
            review_status=e.get("review_status"),
            synced_at=now,
        ))
    await db.flush()  # F002: 不 commit，由 sync_knowledge_on_startup 统一提交

    return {
        "modules": len(modules_seen),
        "study_units": len(study_units),
        "concepts": len(l1_nodes),
        "big_concepts": len(bc_nodes),
        "edges": len(edges),
        "contains": contains_count,
        "maps": len(maps),
    }


async def sync_knowledge_on_startup(db: AsyncSession, knowledge_db_path: str | None = None) -> dict:
    """启动时同步 knowledge.db → PostgreSQL（幂等：已有数据则跳过）。

    同步内容:
    1. concept_graph_nodes + edges（知识图谱结构）
    2. da_catalog_snapshot（DA 目录）
    3. da_knowledge_point_map（DA → 概念映射）

    Returns: {"status": "synced"|"skipped"|"not_found", "nodes": int, "edges": int, "das": int, "kp_map": int}
    """
    from edu_cloud.config import settings
    path = Path(knowledge_db_path) if knowledge_db_path else Path(settings.KNOWLEDGE_DB_PATH)  # F003
    if not path.exists():
        logger.warning("sync: knowledge.db not found at %s", path)
        return {"status": "not_found"}

    # 检查 4 类投影是否都已填充（部分初始化 → 重新同步）
    from edu_cloud.services.knowledge_tree_workflow import DaCatalogSnapshot, DaKnowledgePointMap
    node_count = (await db.execute(select(func.count()).select_from(ConceptGraphNode))).scalar() or 0
    edge_count = (await db.execute(select(func.count()).select_from(ConceptGraphEdge))).scalar() or 0
    da_count = (await db.execute(select(func.count()).select_from(DaCatalogSnapshot))).scalar() or 0
    kp_count = (await db.execute(select(func.count()).select_from(DaKnowledgePointMap))).scalar() or 0
    # 3-layer tree: check module nodes exist (upgrade path from old schema → force re-sync)
    has_modules = (await db.execute(
        select(func.count()).select_from(ConceptGraphNode).where(
            ConceptGraphNode.node_type == "module"
        )
    )).scalar() or 0
    if node_count > 0 and edge_count > 0 and da_count > 0 and kp_count > 0 and has_modules > 0:
        logger.debug("sync: all projections populated (%d nodes, %d edges, %d DAs, %d KP maps, %d modules), skipping",
                     node_count, edge_count, da_count, kp_count, has_modules)
        # F001 修复: skipped 分支也要保障 concept_stats 存在（生产升级路径 + 失败自愈）
        await _ensure_concept_stats(db, str(path))
        return {"status": "skipped", "nodes": node_count}

    # 1. 图谱同步（3 层树：module → study_unit → concept + enriched edges）
    data = _read_knowledge_db(str(path))
    counts = await _sync_graph(db, data)
    total_nodes = counts["modules"] + counts["study_units"] + counts["concepts"] + counts["big_concepts"]
    logger.info("sync: knowledge graph → PG (%d modules, %d SUs, %d concepts, %d BC, %d edges, %d contains, %d maps)",
                counts["modules"], counts["study_units"], counts["concepts"], counts["big_concepts"],
                counts["edges"], counts["contains"], counts["maps"])

    # 2. DA 目录 + DA-KP 映射
    from edu_cloud.services.knowledge_tree_workflow import sync_da_catalog, sync_da_kp_map
    da_count = await sync_da_catalog(str(path), db)
    kp_count = await sync_da_kp_map(str(path), db)
    logger.info("sync: DA catalog → PG (%d DAs, %d KP mappings)", da_count, kp_count)

    # F002: 三类投影统一单次 commit
    await db.commit()

    # Phase 1 (INV-003): 同步完成后触发 stats 计算（best-effort，失败不阻塞）
    await _ensure_concept_stats(db, str(path))

    return {"status": "synced", "nodes": total_nodes, "edges": counts["edges"] + counts["contains"], "das": da_count, "kp_map": kp_count}


async def _ensure_concept_stats(db: AsyncSession, kb_path: str) -> None:
    """启动时保障 concept_stats 非空（best-effort，异常吞掉不阻塞 sync）。

    F001 修复（Round 2）：
    - 之前实现只在 sync 走 synced 分支后触发，skipped 分支被跳过，导致：
      1. 生产库首次升级到本版本时 stats 永远是空（因为 sync 进入 skipped）
      2. 首次 stats 计算失败后，下次启动也不恢复
    - 新逻辑：无论 skipped 还是 synced 都进入本函数；检测 ConceptStats 表为空时补算
    """
    from pathlib import Path as _Path

    from edu_cloud.modules.knowledge_tree import stats_service
    from edu_cloud.modules.knowledge_tree.models import ConceptStats

    if not _Path(kb_path).exists():
        logger.info("kb_path not exists, skip stats computation: %s", kb_path)
        return

    try:
        stats_count = (
            await db.execute(select(func.count()).select_from(ConceptStats))
        ).scalar() or 0
        if stats_count > 0:
            logger.debug("concept_stats already populated (%d records), skipping", stats_count)
            return

        updated = await stats_service.compute_all_stats(db, kb_path)
        logger.info("post-sync stats computed: %d records", updated)
    except Exception as e:
        logger.error("stats computation failed (sync not affected): %s", e)
