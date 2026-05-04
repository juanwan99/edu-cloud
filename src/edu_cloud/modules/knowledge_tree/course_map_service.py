"""课程地图聚合服务 — 从 knowledge.db + PG 构建课程概览/模块地图/学习单元详情。"""
import json
import logging
import sqlite3
from pathlib import Path

import sqlalchemy as sa
import sqlalchemy.orm
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.config import settings
from edu_cloud.modules.knowledge_tree.course_map_schemas import (
    ConceptCluster,
    CrossModuleBridge,
    CurriculumRequirement,
    CurriculumSummary,
    ExamPatternGroup,
    ExamSummary,
    ModuleCardData,
    ModuleCurriculumItem,
    ModuleExamProfile,
    ModuleMapResponse,
    ModuleOverviewResponse,
    RelationItem,
    StudyUnitCard,
    StudyUnitDetailResponse,
    TextbookAnchor,
)
from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge, ConceptGraphNode

logger = logging.getLogger(__name__)

_MODULE_NAMES = {
    "M1": "分子与细胞",
    "M2": "遗传与进化",
    "M3": "稳态与调节",
    "M4": "生态与环境",
    "M5": "生物技术与工程",
}

_MODULE_TAGLINES = {
    "M1": "生命的物质基础与细胞生命活动",
    "M2": "基因传递与生命演化机制",
    "M3": "生命活动的内稳态维持",
    "M4": "生物与环境的协调统一",
    "M5": "现代生物技术及其应用",
}

_BAND_NAMES = {
    "near": "基础调用",
    "mid": "情境应用",
    "far": "综合迁移",
}


def _open_kb(kb_path: str | None) -> sqlite3.Connection | None:
    """打开 knowledge.db，path 不存在时返回 None。"""
    path = Path(kb_path) if kb_path else Path(settings.KNOWLEDGE_DB_PATH)
    if not path.exists():
        logger.warning("knowledge.db not found at %s", path)
        return None
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row[0] > 0


def _json_list(val: str | None) -> list:
    if not val:
        return []
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ──────────────────────────────────────────────────────────────────────────────
# get_module_overview
# ──────────────────────────────────────────────────────────────────────────────

async def get_module_overview(
    db: AsyncSession,
    kb_path: str | None = None,
) -> ModuleOverviewResponse:
    """构建所有模块的概览卡片 + 跨模块桥接 + 课标摘要 + 高考摘要。"""
    conn = _open_kb(kb_path)

    # ── 1. Study units grouped by module ──────────────────────────────────────
    module_su: dict[str, list[sqlite3.Row]] = {m: [] for m in _MODULE_NAMES}
    module_concept_ids: dict[str, set[str]] = {m: set() for m in _MODULE_NAMES}

    if conn and _table_exists(conn, "study_units"):
        for row in conn.execute(
            "SELECT id, name, module, estimated_minutes, source_concept_ids, "
            "exam_tags FROM study_units"
        ):
            mod = row["module"]
            if mod in module_su:
                module_su[mod].append(row)
                for cid in _json_list(row["source_concept_ids"]):
                    module_concept_ids[mod].add(cid)

    # ── 2. exam_tags per module from seed_su_exam_stats ───────────────────────
    module_top_bands: dict[str, list[str]] = {m: [] for m in _MODULE_NAMES}
    if conn and _table_exists(conn, "seed_su_exam_stats"):
        band_accum: dict[str, dict[str, float]] = {m: {} for m in _MODULE_NAMES}
        for row in conn.execute(
            "SELECT su_id, transfer_band_dist FROM seed_su_exam_stats "
            "WHERE transfer_band_dist IS NOT NULL"
        ):
            # find which module owns this su
            su_mod = None
            for mod, rows in module_su.items():
                if any(r["id"] == row["su_id"] for r in rows):
                    su_mod = mod
                    break
            if su_mod is None:
                continue
            try:
                dist = json.loads(row["transfer_band_dist"])
                for band, cnt in dist.items():
                    band_accum[su_mod][band] = band_accum[su_mod].get(band, 0) + float(cnt)
            except (json.JSONDecodeError, TypeError):
                pass
        for mod, dist in band_accum.items():
            if dist:
                top = sorted(dist, key=dist.get, reverse=True)[:2]
                module_top_bands[mod] = [_BAND_NAMES.get(b, b) for b in top]

    # ── 3. ModuleCardData ─────────────────────────────────────────────────────
    module_cards: list[ModuleCardData] = []
    for mod_id, name in _MODULE_NAMES.items():
        rows = module_su[mod_id]
        total_minutes = sum(r["estimated_minutes"] or 0 for r in rows)
        module_cards.append(ModuleCardData(
            id=mod_id,
            name=name,
            tagline=_MODULE_TAGLINES.get(mod_id, ""),
            study_unit_count=len(rows),
            concept_count=len(module_concept_ids[mod_id]),
            total_hours=round(total_minutes / 45, 1),
            exam_tags=module_top_bands[mod_id],
        ))

    # ── 4. Cross-module bridges from PG ──────────────────────────────────────
    bridges: list[CrossModuleBridge] = []
    try:
        SrcNode = sa.orm.aliased(ConceptGraphNode, name="src")
        TgtNode = sa.orm.aliased(ConceptGraphNode, name="tgt")
        bridge_q = (
            sa.select(
                ConceptGraphEdge.evidence,
                SrcNode.name.label("source_name"),
                SrcNode.primary_module.label("source_module"),
                TgtNode.name.label("target_name"),
                TgtNode.primary_module.label("target_module"),
            )
            .join(SrcNode, SrcNode.id == ConceptGraphEdge.source_id)
            .join(TgtNode, TgtNode.id == ConceptGraphEdge.target_id)
            .where(ConceptGraphEdge.relation_type == "bridge_to")
        )
        result = await db.execute(bridge_q)
        for row in result:
            if row.source_module != row.target_module:
                bridges.append(CrossModuleBridge(
                    source_name=row.source_name,
                    target_name=row.target_name,
                    source_module=row.source_module,
                    target_module=row.target_module,
                    evidence=row.evidence,
                ))
    except Exception as exc:
        logger.warning("bridge_to query failed: %s", exc)

    # ── 5. Curriculum summary ─────────────────────────────────────────────────
    content_count = 0
    academic_count = 0
    big_concepts: list[str] = []

    if conn and _table_exists(conn, "curriculum_requirements"):
        for row in conn.execute(
            "SELECT requirement_type FROM curriculum_requirements"
        ):
            rt = row["requirement_type"] or ""
            if rt == "content_requirement":
                content_count += 1
            elif rt == "academic_requirement":
                academic_count += 1

    if conn and _table_exists(conn, "big_concepts"):
        for row in conn.execute("SELECT DISTINCT name FROM big_concepts"):
            big_concepts.append(row["name"])

    curriculum = CurriculumSummary(
        content_count=content_count,
        academic_count=academic_count,
        big_concepts=big_concepts,
    )

    # ── 6. Exam summary ───────────────────────────────────────────────────────
    total_items = 0
    near_count = 0
    mid_count = 0
    far_count = 0

    if conn and _table_exists(conn, "assessment_items"):
        row = conn.execute("SELECT COUNT(*) FROM assessment_items").fetchone()
        total_items = row[0] if row else 0

    if conn and _table_exists(conn, "q_matrix"):
        for row in conn.execute(
            "SELECT transfer_band, COUNT(*) AS cnt FROM q_matrix GROUP BY transfer_band"
        ):
            band = row["transfer_band"]
            cnt = row["cnt"]
            if band == "near":
                near_count = cnt
            elif band == "mid":
                mid_count = cnt
            elif band == "far":
                far_count = cnt

    exam = ExamSummary(
        total_items=total_items,
        near_count=near_count,
        mid_count=mid_count,
        far_count=far_count,
    )

    if conn:
        conn.close()

    return ModuleOverviewResponse(
        modules=module_cards,
        bridges=bridges,
        curriculum=curriculum,
        exam=exam,
    )


# ──────────────────────────────────────────────────────────────────────────────
# get_module_map
# ──────────────────────────────────────────────────────────────────────────────

async def get_module_map(
    db: AsyncSession,
    module: str,
    kb_path: str | None = None,
) -> ModuleMapResponse:
    """构建单模块完整地图（学习单元 + 概念聚类 + 课标 + 高考概况 + 外出桥接）。"""
    conn = _open_kb(kb_path)

    # ── 1. Study units for module ─────────────────────────────────────────────
    su_rows: list[sqlite3.Row] = []
    su_id_to_row: dict[str, sqlite3.Row] = {}
    if conn and _table_exists(conn, "study_units"):
        for row in conn.execute(
            "SELECT id, name, description, estimated_minutes, "
            "source_concept_ids, prerequisite_unit_ids, linked_da_ids "
            "FROM study_units WHERE module=?",
            (module,),
        ):
            su_rows.append(row)
            su_id_to_row[row["id"]] = row

    # Build id→name map for prerequisite resolution
    su_name_map: dict[str, str] = {}
    if conn and _table_exists(conn, "study_units"):
        for row in conn.execute("SELECT id, name FROM study_units"):
            su_name_map[row["id"]] = row["name"]

    study_unit_cards: list[StudyUnitCard] = []
    total_minutes = 0
    all_concept_ids: set[str] = set()

    for row in su_rows:
        prereq_ids = _json_list(row["prerequisite_unit_ids"])
        prereq_names = [su_name_map.get(pid, pid) for pid in prereq_ids]
        concept_ids = _json_list(row["source_concept_ids"])
        all_concept_ids.update(concept_ids)

        # concept names
        concept_names: list[str] = []
        if conn and concept_ids:
            placeholders = ",".join("?" * len(concept_ids))
            for crow in conn.execute(
                f"SELECT name FROM concepts WHERE id IN ({placeholders})", concept_ids
            ):
                concept_names.append(crow["name"])

        minutes = row["estimated_minutes"] or 0
        total_minutes += minutes
        study_unit_cards.append(StudyUnitCard(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            estimated_minutes=minutes,
            prerequisites=prereq_names,
            concept_names=concept_names,
        ))

    # ── 2. Concept clusters via big_concept ───────────────────────────────────
    concept_clusters: list[ConceptCluster] = []
    if conn and all_concept_ids and _table_exists(conn, "concept_big_concept_map"):
        bc_to_concepts: dict[str, list[str]] = {}
        bc_id_to_name: dict[str, str] = {}
        if _table_exists(conn, "big_concepts"):
            for row in conn.execute("SELECT id, name FROM big_concepts WHERE module=?", (module,)):
                bc_id_to_name[row["id"]] = row["name"]

        placeholders = ",".join("?" * len(all_concept_ids))
        for row in conn.execute(
            f"SELECT cbcm.concept_id, cbcm.big_concept_id, c.name AS concept_name "
            f"FROM concept_big_concept_map cbcm "
            f"JOIN concepts c ON c.id = cbcm.concept_id "
            f"WHERE cbcm.concept_id IN ({placeholders})",
            list(all_concept_ids),
        ):
            bc_id = row["big_concept_id"]
            if bc_id not in bc_to_concepts:
                bc_to_concepts[bc_id] = []
            bc_to_concepts[bc_id].append(row["concept_name"])

        for bc_id, names in bc_to_concepts.items():
            bc_name = bc_id_to_name.get(bc_id, bc_id)
            concept_clusters.append(ConceptCluster(big_concept=bc_name, concepts=names))

    # ── 3. Curriculum per big_concept ─────────────────────────────────────────
    curriculum: list[ModuleCurriculumItem] = []
    if conn and su_rows and _table_exists(conn, "curriculum_requirements") and _table_exists(conn, "seed_req_da_map"):
        # Collect all DA ids linked to this module's SUs
        da_ids: set[str] = set()
        for row in su_rows:
            for da_id in _json_list(row["linked_da_ids"]):
                da_ids.add(da_id)

        if da_ids:
            placeholders = ",".join("?" * len(da_ids))
            req_rows = conn.execute(
                f"SELECT DISTINCT cr.id, cr.text, cr.requirement_type "
                f"FROM curriculum_requirements cr "
                f"JOIN seed_req_da_map srdm ON srdm.req_id = cr.id "
                f"WHERE srdm.da_id IN ({placeholders})",
                list(da_ids),
            ).fetchall()

            # Group by big_concept (use requirement_type as grouping key here)
            if req_rows:
                curriculum.append(ModuleCurriculumItem(
                    big_concept=_MODULE_NAMES.get(module, module),
                    requirements=[r["text"] for r in req_rows],
                ))

    # ── 4. Exam profile from seed_su_exam_stats ───────────────────────────────
    exam_profile = ModuleExamProfile(total_items=0, near_pct=0.0, mid_pct=0.0, far_pct=0.0)
    if conn and su_rows and _table_exists(conn, "seed_su_exam_stats"):
        su_ids = [r["id"] for r in su_rows]
        placeholders = ",".join("?" * len(su_ids))
        band_totals: dict[str, float] = {}
        for row in conn.execute(
            f"SELECT transfer_band_dist FROM seed_su_exam_stats WHERE su_id IN ({placeholders})",
            su_ids,
        ):
            try:
                dist = json.loads(row["transfer_band_dist"])
                for band, cnt in dist.items():
                    band_totals[band] = band_totals.get(band, 0) + float(cnt)
            except (json.JSONDecodeError, TypeError):
                pass

        total = sum(band_totals.values())
        if total > 0:
            exam_profile = ModuleExamProfile(
                total_items=int(total),
                near_pct=round(band_totals.get("near", 0) / total * 100, 1),
                mid_pct=round(band_totals.get("mid", 0) / total * 100, 1),
                far_pct=round(band_totals.get("far", 0) / total * 100, 1),
            )

    # ── 5. Outgoing bridges from PG ───────────────────────────────────────────
    outgoing_bridges: list[CrossModuleBridge] = []
    try:
        SrcNode = sa.orm.aliased(ConceptGraphNode, name="src")
        TgtNode = sa.orm.aliased(ConceptGraphNode, name="tgt")
        out_q = (
            sa.select(
                ConceptGraphEdge.evidence,
                SrcNode.name.label("source_name"),
                SrcNode.primary_module.label("source_module"),
                TgtNode.name.label("target_name"),
                TgtNode.primary_module.label("target_module"),
            )
            .join(SrcNode, SrcNode.id == ConceptGraphEdge.source_id)
            .join(TgtNode, TgtNode.id == ConceptGraphEdge.target_id)
            .where(
                sa.and_(
                    ConceptGraphEdge.relation_type == "bridge_to",
                    SrcNode.primary_module == module,
                    TgtNode.primary_module != module,
                )
            )
        )
        result = await db.execute(out_q)
        for row in result:
            outgoing_bridges.append(CrossModuleBridge(
                source_name=row.source_name,
                target_name=row.target_name,
                source_module=row.source_module,
                target_module=row.target_module,
                evidence=row.evidence,
            ))
    except Exception as exc:
        logger.warning("outgoing bridge query failed: %s", exc)

    if conn:
        conn.close()

    return ModuleMapResponse(
        module_id=module,
        module_name=_MODULE_NAMES.get(module, module),
        tagline=_MODULE_TAGLINES.get(module, ""),
        total_hours=round(total_minutes / 45, 1),
        study_units=study_unit_cards,
        concept_clusters=concept_clusters,
        curriculum=curriculum,
        exam_profile=exam_profile,
        outgoing_bridges=outgoing_bridges,
    )


# ──────────────────────────────────────────────────────────────────────────────
# get_study_unit_detail
# ──────────────────────────────────────────────────────────────────────────────

async def get_study_unit_detail(
    db: AsyncSession,
    su_id: str,
    kb_path: str | None = None,
) -> StudyUnitDetailResponse:
    """构建学习单元详情（前置/后续/对比/教材定位/课标/高考题型）。"""
    conn = _open_kb(kb_path)

    if conn is None or not _table_exists(conn, "study_units"):
        # Return a minimal empty response
        return StudyUnitDetailResponse(
            id=su_id, name=su_id, estimated_minutes=0,
            textbook=[], prerequisites=[], successors=[],
            contrasts=[], concepts=[], curriculum=[], exam_patterns=[],
        )

    # ── 1. Load main SU row ───────────────────────────────────────────────────
    su_row = conn.execute(
        "SELECT id, name, description, estimated_minutes, "
        "prerequisite_unit_ids, source_concept_ids, textbook_anchor_ids, "
        "linked_da_ids, module "
        "FROM study_units WHERE id=?",
        (su_id,),
    ).fetchone()

    if su_row is None:
        if conn:
            conn.close()
        return StudyUnitDetailResponse(
            id=su_id, name=su_id, estimated_minutes=0,
            textbook=[], prerequisites=[], successors=[],
            contrasts=[], concepts=[], curriculum=[], exam_patterns=[],
        )

    # Module of this SU (for module labels)
    su_module = su_row["module"] or "unknown"

    # SU name map for prereq/successor resolution
    su_name_map: dict[str, tuple[str, str]] = {}  # id → (name, module)
    for row in conn.execute("SELECT id, name, module FROM study_units"):
        su_name_map[row["id"]] = (row["name"], row["module"] or "unknown")

    # ── 2. Prerequisites ──────────────────────────────────────────────────────
    prerequisites: list[RelationItem] = []
    for pid in _json_list(su_row["prerequisite_unit_ids"]):
        name, mod = su_name_map.get(pid, (pid, None))
        prerequisites.append(RelationItem(
            category="必经前置", target_name=name, target_module=mod
        ))

    # ── 3. Successors (SUs that list this SU as prerequisite) ─────────────────
    successors: list[RelationItem] = []
    for row in conn.execute(
        "SELECT id, name, module, prerequisite_unit_ids FROM study_units "
        "WHERE prerequisite_unit_ids IS NOT NULL"
    ):
        prereqs = _json_list(row["prerequisite_unit_ids"])
        if su_id in prereqs:
            mod = row["module"] or "unknown"
            successors.append(RelationItem(
                category="后续单元", target_name=row["name"], target_module=mod
            ))

    # ── 4. Contrasts from concept_relations ───────────────────────────────────
    contrasts: list[RelationItem] = []
    concept_ids = _json_list(su_row["source_concept_ids"])

    if concept_ids and _table_exists(conn, "concept_relations"):
        placeholders = ",".join("?" * len(concept_ids))
        for row in conn.execute(
            f"SELECT cr.source_id, cr.target_id, cr.evidence, c.name AS target_name "
            f"FROM concept_relations cr "
            f"JOIN concepts c ON c.id = cr.target_id "
            f"WHERE cr.relation_type='contrast' AND cr.source_id IN ({placeholders})",
            concept_ids,
        ):
            contrasts.append(RelationItem(
                category="对比关系",
                target_name=row["target_name"],
                evidence=row["evidence"],
            ))

    # ── 5. Concepts ───────────────────────────────────────────────────────────
    concepts: list[dict] = []
    if concept_ids and _table_exists(conn, "concepts"):
        placeholders = ",".join("?" * len(concept_ids))
        for row in conn.execute(
            f"SELECT id, name, knowledge_level, description FROM concepts "
            f"WHERE id IN ({placeholders})",
            concept_ids,
        ):
            concepts.append({
                "id": row["id"],
                "name": row["name"],
                "level": row["knowledge_level"],
                "description": row["description"],
            })

    # ── 6. Textbook anchors ───────────────────────────────────────────────────
    textbook: list[TextbookAnchor] = []
    anchor_ids = _json_list(su_row["textbook_anchor_ids"])
    if anchor_ids and _table_exists(conn, "sections"):
        placeholders = ",".join("?" * len(anchor_ids))
        has_docs = _table_exists(conn, "documents")
        if has_docs:
            for row in conn.execute(
                f"SELECT s.title AS section_title, d.title AS book, "
                f"s.page_start, s.page_end "
                f"FROM sections s JOIN documents d ON s.document_id = d.id "
                f"WHERE s.id IN ({placeholders})",
                anchor_ids,
            ):
                page_range = ""
                if row["page_start"] is not None:
                    page_range = f"P{row['page_start']}"
                    if row["page_end"]:
                        page_range += f"-{row['page_end']}"
                textbook.append(TextbookAnchor(
                    book=row["book"] or "",
                    section=row["section_title"] or "",
                    page_range=page_range,
                ))
        else:
            for row in conn.execute(
                f"SELECT title, page_start, page_end FROM sections WHERE id IN ({placeholders})",
                anchor_ids,
            ):
                page_range = ""
                if row["page_start"] is not None:
                    page_range = f"P{row['page_start']}"
                textbook.append(TextbookAnchor(
                    book="教材", section=row["title"] or "", page_range=page_range,
                ))

    # ── 7. Curriculum requirements via DA ─────────────────────────────────────
    curriculum: list[CurriculumRequirement] = []
    da_ids = _json_list(su_row["linked_da_ids"])
    if da_ids and _table_exists(conn, "curriculum_requirements") and _table_exists(conn, "seed_req_da_map"):
        placeholders = ",".join("?" * len(da_ids))
        for row in conn.execute(
            f"SELECT DISTINCT cr.id, cr.text, cr.requirement_type "
            f"FROM curriculum_requirements cr "
            f"JOIN seed_req_da_map srdm ON srdm.req_id = cr.id "
            f"WHERE srdm.da_id IN ({placeholders})",
            da_ids,
        ):
            # Extract mastery verb: first word of text typically
            text = row["text"] or ""
            mastery_verb = text.split("、")[0].split("，")[0][:8] if text else ""
            curriculum.append(CurriculumRequirement(
                mastery_verb=mastery_verb,
                text=text,
                requirement_type=row["requirement_type"] or "",
            ))

    # ── 8. Exam patterns via DA → q_matrix → assessment_items ────────────────
    exam_patterns: list[ExamPatternGroup] = []
    if da_ids and _table_exists(conn, "q_matrix") and _table_exists(conn, "assessment_items"):
        placeholders = ",".join("?" * len(da_ids))
        for band in ("near", "mid", "far"):
            items = conn.execute(
                f"SELECT DISTINCT ai.id, ai.stem, ai.question_type "
                f"FROM q_matrix qm "
                f"JOIN assessment_items ai ON qm.item_id = ai.id "
                f"WHERE qm.attribute_id IN ({placeholders}) AND qm.transfer_band=? "
                f"LIMIT 3",
                [*da_ids, band],
            ).fetchall()
            if items:
                exam_patterns.append(ExamPatternGroup(
                    band=_BAND_NAMES.get(band, band),
                    count=len(items),
                    sample_items=[
                        {"id": i["id"], "stem": (i["stem"] or "")[:200], "type": i["question_type"]}
                        for i in items
                    ],
                ))

    if conn:
        conn.close()

    return StudyUnitDetailResponse(
        id=su_row["id"],
        name=su_row["name"],
        description=su_row["description"],
        estimated_minutes=su_row["estimated_minutes"] or 0,
        textbook=textbook,
        prerequisites=prerequisites,
        successors=successors,
        contrasts=contrasts,
        concepts=concepts,
        curriculum=curriculum,
        exam_patterns=exam_patterns,
    )
