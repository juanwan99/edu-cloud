"""生物知识点标准树 — 从 knowledge.db study_units + concepts(L1) 提取，分 3 层。

层次结构：
  L1 模块（M1-M5）→ L2 学习单元（study_units）→ L3 概念（L1 concepts）

数据源：edu-knowledge-base/knowledge.db
  - study_units: 99 条（5 模块，每模块 11-33 学习单元）
  - concepts(L1): 108 条（对应知识图谱的 L1 概念）
  - concept → study_unit 映射来自 study_units.concept_ids JSON 字段
"""

import json
import sqlite3
from pathlib import Path

MODULE_NAMES = {
    "M1": "分子与细胞",
    "M2": "遗传与进化",
    "M3": "稳态与调节",
    "M4": "生态与环境",
    "M5": "生物技术与工程",
}


def _build_tree_from_db(db_path: str) -> list[tuple]:
    """从 knowledge.db 读取 study_units + concepts，构建 (code, name, level, parent_code, grade_hint) 列表。"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    tree = []

    for mod_code, mod_name in MODULE_NAMES.items():
        tree.append((f"BIO_{mod_code}", mod_name, 1, None, None))

    rows = conn.execute(
        "SELECT id, name, module, estimated_minutes FROM study_units ORDER BY module, id"
    ).fetchall()
    su_code_by_id: dict[str, str] = {}
    for row in rows:
        su_id = row["id"]
        su_name = row["name"]
        module = row["module"]
        parent_code = f"BIO_{module}"
        code = f"BIO_{su_id.upper().replace(':', '_').replace('bio_sr_', '')}"
        tree.append((code, su_name, 2, parent_code, None))
        su_code_by_id[su_id] = code

    concepts = conn.execute(
        "SELECT id, name FROM concepts WHERE knowledge_level = 'L1' ORDER BY id"
    ).fetchall()
    concept_name_map = {c["id"]: c["name"] for c in concepts}

    su_rows = conn.execute(
        "SELECT id, module, source_concept_ids FROM study_units WHERE source_concept_ids IS NOT NULL"
    ).fetchall()
    concept_to_su: dict[str, str] = {}
    for row in su_rows:
        su_id = row["id"]
        su_code = su_code_by_id.get(su_id, f"BIO_{su_id.upper().replace(':', '_').replace('bio_sr_', '')}")
        try:
            cids = json.loads(row["source_concept_ids"])
        except (json.JSONDecodeError, TypeError):
            continue
        for cid in cids:
            if cid in concept_name_map:
                concept_to_su[cid] = su_code

    for cid, cname in concept_name_map.items():
        code = f"BIO_{cid.upper().replace(':', '_')}"
        parent_code = concept_to_su.get(cid)
        if not parent_code:
            module_part = cid.split("_")[3] if len(cid.split("_")) > 3 else "M1"
            parent_code = f"BIO_{module_part.upper()}"
        tree.append((code, cname, 3, parent_code, None))

    conn.close()
    return tree


def get_biology_tree(db_path: str | None = None) -> list[tuple]:
    """返回生物知识点树。如果提供 db_path 则从数据库读取，否则返回静态 fallback。"""
    if db_path:
        p = Path(db_path)
        if p.exists():
            return _build_tree_from_db(str(p))
    return _FALLBACK_TREE


_FALLBACK_TREE = [
    ("BIO_M1", "分子与细胞", 1, None, None),
    ("BIO_M2", "遗传与进化", 1, None, None),
    ("BIO_M3", "稳态与调节", 1, None, None),
    ("BIO_M4", "生态与环境", 1, None, None),
    ("BIO_M5", "生物技术与工程", 1, None, None),
]


async def seed_biology_knowledge(db, db_path: str | None = None) -> int:
    """Seed 生物知识点树到 KnowledgePoint 表。幂等：已存在则跳过。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge.models import KnowledgePoint, GLOBAL_SCHOOL_ID

    tree = get_biology_tree(db_path)

    existing = await db.execute(
        select(KnowledgePoint.code).where(
            KnowledgePoint.course_code == "SW",
            KnowledgePoint.school_id == GLOBAL_SCHOOL_ID,
        )
    )
    existing_codes = set(row[0] for row in existing.all())

    code_to_id = {}
    created = 0
    for code, name, level, parent_code, grade_hint in tree:
        if code in existing_codes:
            r = await db.execute(
                select(KnowledgePoint.id).where(
                    KnowledgePoint.code == code,
                    KnowledgePoint.school_id == GLOBAL_SCHOOL_ID,
                )
            )
            code_to_id[code] = r.scalar_one()
            continue

        kp = KnowledgePoint(
            code=code, name=name, course_code="SW", level=level,
            grade_hint=grade_hint, school_id=GLOBAL_SCHOOL_ID,
        )
        db.add(kp)
        await db.flush()
        code_to_id[code] = kp.id
        created += 1

    for code, name, level, parent_code, grade_hint in tree:
        if parent_code and parent_code in code_to_id:
            kp_id = code_to_id[code]
            parent_id = code_to_id[parent_code]
            await db.execute(
                KnowledgePoint.__table__.update()
                .where(KnowledgePoint.__table__.c.id == kp_id)
                .values(parent_id=parent_id)
            )

    await db.commit()
    return created
