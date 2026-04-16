"""节点详情聚合 — 从 knowledge.db 查询课标/教材/DA/真题。"""
import json
import logging
import re
import sqlite3
from pathlib import Path

from edu_cloud.config import settings

logger = logging.getLogger(__name__)


def get_node_detail(node_id: str, *, pg_node: dict | None = None, knowledge_db_path: str | None = None) -> dict:
    """查询概念节点详情（F004: PG 兜底 + json_each 精确匹配）。

    Args:
        pg_node: PG 中已查到的节点基础信息（路由层传入，兜底用）
    """
    base_concept = pg_node or {"id": node_id}
    result = {"concept": base_concept, "curriculum": [], "textbook": [], "das": [], "questions": {}, "evidence": []}

    path = Path(knowledge_db_path) if knowledge_db_path else Path(settings.KNOWLEDGE_DB_PATH)
    if not path.exists():
        return result  # F004: 返回 PG 兜底信息，不丢失 name/description

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row

    # 1. 概念基本信息（knowledge.db 有则覆盖 PG 兜底）
    row = conn.execute("SELECT id, name, knowledge_level, description FROM concepts WHERE id = ?", (node_id,)).fetchone()
    if row:
        # R5: 统一 schema — 用 PG 字段名 level/module（前端期望）
        from edu_cloud.modules.knowledge_tree.sync_service import _MODULE_RE
        m = _MODULE_RE.search(row["id"])
        result["concept"] = {
            "id": row["id"], "name": row["name"],
            "level": row["knowledge_level"],
            "module": f"M{m.group(1)}" if m else "unknown",
            "description": row["description"],
        }

    # 2. 关联 DA（json_each 精确匹配，F004 修复）
    das = conn.execute("""
        SELECT da.id, da.name, da.observable_behaviors, da.common_cause_families
        FROM diagnostic_attributes da, json_each(da.linked_concept_ids) je
        WHERE je.value = ?
    """, (node_id,)).fetchall()
    result["das"] = []
    for da in das:
        linked = json.loads(da["observable_behaviors"]) if da["observable_behaviors"] else []
        result["das"].append({
            "da_id": da["id"], "name": da["name"],
            "observable_behaviors": linked,
        })

    # 3. 课标要求（通过 DA → seed_req_da_map → curriculum_requirements）
    da_ids = [d["da_id"] for d in result["das"]]
    if da_ids:
        placeholders = ",".join("?" * len(da_ids))
        reqs = conn.execute(f"""
            SELECT DISTINCT cr.id, cr.text
            FROM curriculum_requirements cr
            JOIN seed_req_da_map srdm ON srdm.req_id = cr.id
            WHERE srdm.da_id IN ({placeholders})
        """, da_ids).fetchall()
        result["curriculum"] = [{"requirement_id": r["id"], "content": r["text"]} for r in reqs]

    # 4. 教材定位（通过概念名关键词在 content_blocks 中搜索）
    if row:
        concept_name = row["name"]
        # 概念名是完整句子，需提取关键词段进行匹配
        segments = re.split(r'[，。；：、！？（）\s]+', concept_name)
        search_terms = [s[:15] for s in segments if len(s) >= 2][:3]
        textbook_rows = []
        for term in search_terms:
            textbook_rows = conn.execute("""
                SELECT DISTINCT s.title AS section_title, d.title AS book
                FROM content_blocks cb
                JOIN sections s ON cb.section_id = s.id
                JOIN documents d ON s.document_id = d.id
                WHERE cb.content LIKE ? AND d.type = 'textbook'
                LIMIT 5
            """, (f'%{term}%',)).fetchall()
            if textbook_rows:
                break
        # 兜底：用概念名搜索章节标题
        if not textbook_rows and search_terms:
            textbook_rows = conn.execute("""
                SELECT DISTINCT s.title AS section_title, d.title AS book
                FROM sections s
                JOIN documents d ON s.document_id = d.id
                WHERE s.title LIKE ? AND d.type = 'textbook'
                LIMIT 5
            """, (f'%{search_terms[0]}%',)).fetchall()
        result["textbook"] = [{"section_title": r["section_title"], "book": r["book"]} for r in textbook_rows]

    # 5. 教材证据（evidence_ids_json → 查 concepts 表中的 evidence 行）
    if row:
        evidence_ids_json_col = None
        # 检查 concepts 表是否有 evidence_ids_json 列
        col_names = {r[1] for r in conn.execute("PRAGMA table_info(concepts)")}
        if "evidence_ids_json" in col_names:
            ev_row = conn.execute(
                "SELECT evidence_ids_json FROM concepts WHERE id = ?", (node_id,)
            ).fetchone()
            if ev_row and ev_row["evidence_ids_json"]:
                try:
                    ev_ids = json.loads(ev_row["evidence_ids_json"])
                    if ev_ids:
                        ev_placeholders = ",".join("?" * len(ev_ids))
                        ev_rows = conn.execute(
                            f"SELECT id, name FROM concepts WHERE id IN ({ev_placeholders})",
                            ev_ids,
                        ).fetchall()
                        result["evidence"] = [{"id": e["id"], "text": e["name"]} for e in ev_rows]
                except (json.JSONDecodeError, TypeError):
                    pass

    # 6. 典型真题（通过 Q-Matrix DA 映射，按 transfer_band 分组，每组 3 题）
    if da_ids:
        for band in ("near", "mid", "far"):
            items = conn.execute(f"""
                SELECT DISTINCT ai.id, ai.stem, ai.answer, ai.question_type
                FROM q_matrix qm
                JOIN assessment_items ai ON qm.item_id = ai.id
                WHERE qm.attribute_id IN ({placeholders})
                  AND qm.transfer_band = ?
                LIMIT 3
            """, [*da_ids, band]).fetchall()
            result["questions"][band] = [
                {"id": i["id"], "stem": i["stem"][:200], "answer": i["answer"], "type": i["question_type"]}
                for i in items
            ]

    conn.close()
    return result
