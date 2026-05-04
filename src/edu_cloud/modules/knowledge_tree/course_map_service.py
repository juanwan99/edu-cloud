"""课程地图聚合服务 — 从 knowledge.db + PG 构建课程概览/模块地图/学习单元详情。"""
import json
import logging
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import sqlalchemy as sa
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

_MODULE_RE = re.compile(r"_M(\d+)_")


def _open_kb(kb_path: str | None) -> sqlite3.Connection | None:
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


def _concept_module(concept_id: str) -> str:
    m = _MODULE_RE.search(concept_id)
    return f"M{m.group(1)}" if m else "unknown"


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

    if conn and _table_exists(conn, "study_units"):
        for row in conn.execute(
            "SELECT id, name, module, estimated_minutes, source_concept_ids "
            "FROM study_units"
        ):
            mod = row["module"]
            if mod in module_su:
                module_su[mod].append(row)

    # [M3 fix] L1 concept count per module from concepts table (not source_concept_ids)
    module_l1_count: dict[str, int] = {m: 0 for m in _MODULE_NAMES}
    if conn and _table_exists(conn, "concepts"):
        for row in conn.execute("SELECT id FROM concepts WHERE knowledge_level='L1'"):
            mod = _concept_module(row["id"])
            if mod in module_l1_count:
                module_l1_count[mod] += 1

    # ── 2. exam_tags per module from seed_su_exam_stats ───────────────────────
    module_top_bands: dict[str, list[str]] = {m: [] for m in _MODULE_NAMES}
    if conn and _table_exists(conn, "seed_su_exam_stats"):
        band_accum: dict[str, dict[str, float]] = {m: {} for m in _MODULE_NAMES}
        for row in conn.execute(
            "SELECT study_unit_id, transfer_band_dist FROM seed_su_exam_stats "
            "WHERE transfer_band_dist IS NOT NULL"
        ):
            su_mod = None
            for mod, rows in module_su.items():
                if any(r["id"] == row["study_unit_id"] for r in rows):
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
                top = sorted(dist, key=lambda b: dist.get(b, 0), reverse=True)[:2]
                module_top_bands[mod] = [_BAND_NAMES.get(b, b) for b in top if b is not None]

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
            concept_count=module_l1_count[mod_id],
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
    # [H1 fix] requirement_type actual values are 'content'/'academic'
    content_count = 0
    academic_count = 0
    big_concepts: list[str] = []

    if conn and _table_exists(conn, "curriculum_requirements"):
        for row in conn.execute(
            "SELECT requirement_type FROM curriculum_requirements"
        ):
            rt = row["requirement_type"] or ""
            if rt == "content":
                content_count += 1
            elif rt == "academic":
                academic_count += 1

        # [H1 fix] Read big_concepts from curriculum_requirements.big_concept
        for row in conn.execute(
            "SELECT DISTINCT big_concept FROM curriculum_requirements "
            "WHERE big_concept IS NOT NULL AND big_concept != ''"
        ):
            big_concepts.append(row["big_concept"])

    curriculum = CurriculumSummary(
        content_count=content_count,
        academic_count=academic_count,
        big_concepts=big_concepts,
    )

    # ── 6. Exam summary ───────────────────────────────────────────────────────
    # [H3 fix] Use COUNT(DISTINCT item_id) for actual question counts
    total_items = 0
    near_count = 0
    mid_count = 0
    far_count = 0

    if conn and _table_exists(conn, "assessment_items"):
        row = conn.execute("SELECT COUNT(*) FROM assessment_items").fetchone()
        total_items = row[0] if row else 0

    if conn and _table_exists(conn, "q_matrix"):
        for row in conn.execute(
            "SELECT transfer_band, COUNT(DISTINCT item_id) AS cnt "
            "FROM q_matrix GROUP BY transfer_band"
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
    if conn and _table_exists(conn, "study_units"):
        for row in conn.execute(
            "SELECT id, name, description, estimated_minutes, "
            "source_concept_ids, prerequisite_unit_ids, linked_da_ids "
            "FROM study_units WHERE module=?",
            (module,),
        ):
            su_rows.append(row)

    su_name_map: dict[str, str] = {}
    if conn and _table_exists(conn, "study_units"):
        for row in conn.execute("SELECT id, name FROM study_units"):
            su_name_map[row["id"]] = row["name"]

    study_unit_cards: list[StudyUnitCard] = []
    total_minutes = 0
    all_concept_ids: set[str] = set()
    all_da_ids: set[str] = set()

    for row in su_rows:
        prereq_ids = _json_list(row["prerequisite_unit_ids"])
        prereq_names = [su_name_map.get(pid, pid) for pid in prereq_ids]
        concept_ids = _json_list(row["source_concept_ids"])
        all_concept_ids.update(concept_ids)
        for da_id in _json_list(row["linked_da_ids"]):
            all_da_ids.add(da_id)

        concept_names: list[str] = []
        if conn and concept_ids:
            ph = ",".join("?" * len(concept_ids))
            for crow in conn.execute(
                f"SELECT name FROM concepts WHERE id IN ({ph})", concept_ids
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

    # ── 2. Concept clusters via curriculum_requirements.big_concept ───────────
    # [M1 fix] big_concepts/concept_big_concept_map are empty;
    # use DA chain: SU.linked_da_ids → seed_req_da_map → curriculum_requirements.big_concept
    concept_clusters: list[ConceptCluster] = []
    if conn and all_da_ids and _table_exists(conn, "curriculum_requirements") and _table_exists(conn, "seed_req_da_map"):
        ph = ",".join("?" * len(all_da_ids))
        bc_concepts: dict[str, set[str]] = defaultdict(set)
        da_to_su_concepts: dict[str, set[str]] = {}
        for row in su_rows:
            for da_id in _json_list(row["linked_da_ids"]):
                da_to_su_concepts.setdefault(da_id, set()).update(
                    _json_list(row["source_concept_ids"])
                )

        for row in conn.execute(
            f"SELECT DISTINCT cr.big_concept, srdm.da_id "
            f"FROM curriculum_requirements cr "
            f"JOIN seed_req_da_map srdm ON srdm.req_id = cr.id "
            f"WHERE srdm.da_id IN ({ph}) AND cr.big_concept IS NOT NULL AND cr.big_concept != ''",
            list(all_da_ids),
        ):
            bc = row["big_concept"]
            for cid in da_to_su_concepts.get(row["da_id"], set()):
                bc_concepts[bc].add(cid)

        concept_name_map: dict[str, str] = {}
        if bc_concepts and conn:
            all_cids = set()
            for cids in bc_concepts.values():
                all_cids.update(cids)
            if all_cids:
                ph2 = ",".join("?" * len(all_cids))
                for crow in conn.execute(
                    f"SELECT id, name FROM concepts WHERE id IN ({ph2})", list(all_cids)
                ):
                    concept_name_map[crow["id"]] = crow["name"]

        for bc, cids in bc_concepts.items():
            names = [concept_name_map.get(c, c) for c in sorted(cids)]
            if names:
                concept_clusters.append(ConceptCluster(big_concept=bc, concepts=names))

    # ── 3. Curriculum per big_concept ─────────────────────────────────────────
    # [M2 fix] Group by curriculum_requirements.big_concept instead of lumping all into one
    curriculum: list[ModuleCurriculumItem] = []
    if conn and all_da_ids and _table_exists(conn, "curriculum_requirements") and _table_exists(conn, "seed_req_da_map"):
        ph = ",".join("?" * len(all_da_ids))
        bc_reqs: dict[str, list[str]] = defaultdict(list)
        for row in conn.execute(
            f"SELECT DISTINCT cr.id, cr.text, cr.big_concept "
            f"FROM curriculum_requirements cr "
            f"JOIN seed_req_da_map srdm ON srdm.req_id = cr.id "
            f"WHERE srdm.da_id IN ({ph})",
            list(all_da_ids),
        ):
            bc = row["big_concept"] or _MODULE_NAMES.get(module, module)
            bc_reqs[bc].append(row["text"])

        for bc, texts in bc_reqs.items():
            curriculum.append(ModuleCurriculumItem(big_concept=bc, requirements=texts))

    # ── 4. Exam profile from seed_su_exam_stats ───────────────────────────────
    exam_profile = ModuleExamProfile(total_items=0, near_pct=0.0, mid_pct=0.0, far_pct=0.0)
    if conn and su_rows and _table_exists(conn, "seed_su_exam_stats"):
        su_ids = [r["id"] for r in su_rows]
        ph = ",".join("?" * len(su_ids))
        band_totals: dict[str, float] = {}
        for row in conn.execute(
            f"SELECT transfer_band_dist FROM seed_su_exam_stats WHERE study_unit_id IN ({ph})",
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
    study_unit_id: str,
    kb_path: str | None = None,
) -> StudyUnitDetailResponse:
    """构建学习单元详情（前置/后续/对比/教材定位/课标/高考题型）。"""
    conn = _open_kb(kb_path)

    _empty = StudyUnitDetailResponse(
        id=study_unit_id, name=study_unit_id, estimated_minutes=0,
        textbook=[], prerequisites=[], successors=[],
        contrasts=[], concepts=[], curriculum=[], exam_patterns=[],
    )

    if conn is None or not _table_exists(conn, "study_units"):
        return _empty

    su_row = conn.execute(
        "SELECT id, name, description, estimated_minutes, "
        "prerequisite_unit_ids, source_concept_ids, textbook_anchor_ids, "
        "linked_da_ids, module "
        "FROM study_units WHERE id=?",
        (study_unit_id,),
    ).fetchone()

    if su_row is None:
        conn.close()
        return _empty

    su_name_map: dict[str, tuple[str, str]] = {}
    for row in conn.execute("SELECT id, name, module FROM study_units"):
        su_name_map[row["id"]] = (row["name"], row["module"] or "unknown")

    # ── 2. Prerequisites ──────────────────────────────────────────────────────
    prerequisites: list[RelationItem] = []
    for pid in _json_list(su_row["prerequisite_unit_ids"]):
        name, mod = su_name_map.get(pid, (pid, None))
        prerequisites.append(RelationItem(
            category="必经前置", target_name=name, target_module=mod
        ))

    # ── 3. Successors ─────────────────────────────────────────────────────────
    successors: list[RelationItem] = []
    for row in conn.execute(
        "SELECT id, name, module, prerequisite_unit_ids FROM study_units "
        "WHERE prerequisite_unit_ids IS NOT NULL"
    ):
        prereqs = _json_list(row["prerequisite_unit_ids"])
        if study_unit_id in prereqs:
            successors.append(RelationItem(
                category="后续单元",
                target_name=row["name"],
                target_module=row["module"] or "unknown",
            ))

    # ── 4. Contrasts ──────────────────────────────────────────────────────────
    contrasts: list[RelationItem] = []
    concept_ids = _json_list(su_row["source_concept_ids"])

    if concept_ids and _table_exists(conn, "concept_relations"):
        ph = ",".join("?" * len(concept_ids))
        for row in conn.execute(
            f"SELECT cr.evidence, c.name AS target_name "
            f"FROM concept_relations cr "
            f"JOIN concepts c ON c.id = cr.target_id "
            f"WHERE cr.relation_type='contrast' AND cr.source_id IN ({ph})",
            concept_ids,
        ):
            contrasts.append(RelationItem(
                category="易混对照",
                target_name=row["target_name"],
                evidence=row["evidence"],
            ))

    # ── 5. Concepts ───────────────────────────────────────────────────────────
    concepts: list[dict] = []
    if concept_ids and _table_exists(conn, "concepts"):
        ph = ",".join("?" * len(concept_ids))
        for row in conn.execute(
            f"SELECT id, name, knowledge_level, description FROM concepts WHERE id IN ({ph})",
            concept_ids,
        ):
            concepts.append({
                "id": row["id"],
                "name": row["name"],
                "level": row["knowledge_level"],
                "description": row["description"],
            })

    # ── 6. Textbook anchors ───────────────────────────────────────────────────
    # [H2 fix] textbook_anchor_ids point to content_blocks, not sections
    textbook: list[TextbookAnchor] = []
    anchor_ids = _json_list(su_row["textbook_anchor_ids"])
    if anchor_ids and _table_exists(conn, "content_blocks"):
        ph = ",".join("?" * len(anchor_ids))
        has_sections = _table_exists(conn, "sections")
        has_docs = _table_exists(conn, "documents")

        if has_sections and has_docs:
            seen: set[str] = set()
            for row in conn.execute(
                f"SELECT DISTINCT s.id AS sec_id, s.chapter_title, s.title AS section_title, "
                f"s.page_start, s.page_end, d.title AS book "
                f"FROM content_blocks cb "
                f"JOIN sections s ON cb.section_id = s.id "
                f"JOIN documents d ON s.document_id = d.id "
                f"WHERE cb.id IN ({ph})",
                anchor_ids,
            ):
                key = row["sec_id"]
                if key in seen:
                    continue
                seen.add(key)
                page_range = ""
                if row["page_start"] is not None:
                    page_range = f"P{row['page_start']}"
                    if row["page_end"] and row["page_end"] != row["page_start"]:
                        page_range += f"-{row['page_end']}"
                section = row["section_title"] or ""
                if row["chapter_title"] and row["chapter_title"] not in section:
                    section = f"{row['chapter_title']} · {section}"
                textbook.append(TextbookAnchor(
                    book=row["book"] or "",
                    section=section,
                    page_range=page_range,
                ))
        else:
            for row in conn.execute(
                f"SELECT DISTINCT title, page FROM content_blocks WHERE id IN ({ph})",
                anchor_ids,
            ):
                page_range = f"P{row['page']}" if row["page"] else ""
                textbook.append(TextbookAnchor(
                    book="教材", section=row["title"] or "", page_range=page_range,
                ))

    # ── 7. Curriculum requirements via DA ─────────────────────────────────────
    curriculum: list[CurriculumRequirement] = []
    da_ids = _json_list(su_row["linked_da_ids"])
    if da_ids and _table_exists(conn, "curriculum_requirements") and _table_exists(conn, "seed_req_da_map"):
        ph = ",".join("?" * len(da_ids))
        for row in conn.execute(
            f"SELECT DISTINCT cr.id, cr.text, cr.requirement_type "
            f"FROM curriculum_requirements cr "
            f"JOIN seed_req_da_map srdm ON srdm.req_id = cr.id "
            f"WHERE srdm.da_id IN ({ph})",
            da_ids,
        ):
            text = row["text"] or ""
            mastery_verb = text.split("、")[0].split("，")[0][:8] if text else ""
            curriculum.append(CurriculumRequirement(
                mastery_verb=mastery_verb,
                text=text,
                requirement_type=row["requirement_type"] or "",
            ))

    # ── 8. Exam patterns via DA → q_matrix → assessment_items ────────────────
    # [M4 fix] Separate COUNT from LIMIT-3 sample
    exam_patterns: list[ExamPatternGroup] = []
    if da_ids and _table_exists(conn, "q_matrix") and _table_exists(conn, "assessment_items"):
        ph = ",".join("?" * len(da_ids))
        for band in ("near", "mid", "far"):
            count_row = conn.execute(
                f"SELECT COUNT(DISTINCT ai.id) AS cnt "
                f"FROM q_matrix qm JOIN assessment_items ai ON qm.item_id = ai.id "
                f"WHERE qm.attribute_id IN ({ph}) AND qm.transfer_band=?",
                [*da_ids, band],
            ).fetchone()
            cnt = count_row["cnt"] if count_row else 0
            if cnt == 0:
                continue
            samples = conn.execute(
                f"SELECT DISTINCT ai.id, ai.stem, ai.question_type "
                f"FROM q_matrix qm JOIN assessment_items ai ON qm.item_id = ai.id "
                f"WHERE qm.attribute_id IN ({ph}) AND qm.transfer_band=? LIMIT 3",
                [*da_ids, band],
            ).fetchall()
            exam_patterns.append(ExamPatternGroup(
                band=_BAND_NAMES.get(band, band),
                count=cnt,
                sample_items=[
                    {"id": i["id"], "stem": (i["stem"] or "")[:200], "type": i["question_type"]}
                    for i in samples
                ],
            ))

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
