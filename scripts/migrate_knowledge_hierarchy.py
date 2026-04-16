"""知识图谱层级重构迁移脚本。

将扁平概念图谱重构为 4 层结构：
  Module → BigConcept → Concept(L1) → Evidence(原 L0)

步骤:
  1. 建表 big_concepts + concept_big_concept_map + concepts 加列
  2. 从 curriculum_requirements.big_concept 聚合生成 BigConcept
  3. 读 skeleton/L1/*.json 构建 concept→BigConcept 映射 + aliases + evidence_ids
  4. UPDATE L0 → evidence
  5. 初始化 concepts 新列默认值

用法:
  python scripts/migrate_knowledge_hierarchy.py [--db-path PATH] [--base-dir DIR] [--dry-run]
"""
import json
import logging
import os
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# module_id -> module 简码映射
_MODULE_MAP = {
    "mod:bio_sr:required_1": "M1",
    "mod:bio_sr:required_2": "M2",
    "mod:bio_sr:selective_1": "M3",
    "mod:bio_sr:selective_2": "M4",
    "mod:bio_sr:selective_3": "M5",
}


def _slugify(text: str) -> str:
    """从大概念文本提取短标识（取编号部分）。"""
    # "概念1 细胞是生物体结构与..." → "1"
    m = re.match(r"概念(\d+)", text)
    return m.group(1) if m else text[:10].replace(" ", "_")


def _ensure_schema(conn: sqlite3.Connection):
    """Step 1: 建表 + concepts 加列（幂等）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS big_concepts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            module TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            source_text TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS concept_big_concept_map (
            concept_id TEXT NOT NULL REFERENCES concepts(id),
            big_concept_id TEXT NOT NULL REFERENCES big_concepts(id),
            is_primary INTEGER DEFAULT 0,
            PRIMARY KEY (concept_id, big_concept_id)
        )
    """)
    # 部分唯一索引: 每个概念只能有一个 is_primary=1
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_cbc_primary
        ON concept_big_concept_map(concept_id)
        WHERE is_primary = 1
    """)

    # concepts 加列（幂等：检查列是否存在）
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(concepts)")}
    new_cols = {
        "aliases_json": "TEXT",
        "evidence_ids_json": "TEXT",
        "difficulty": "INTEGER",
        "bloom_level": "TEXT",
        "review_status": "TEXT",
    }
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE concepts ADD COLUMN {col} {col_type}")


def _generate_big_concepts(conn: sqlite3.Connection) -> dict[str, str]:
    """Step 2: 从 curriculum_requirements 聚合生成 BigConcept。

    Returns: {big_concept_text -> big_concept_id} 按 (module_id, big_concept) 分组。
    """
    rows = conn.execute("""
        SELECT big_concept, module_id, COUNT(*) as cnt
        FROM curriculum_requirements
        WHERE big_concept IS NOT NULL AND big_concept != ''
        GROUP BY big_concept, module_id
        ORDER BY module_id, big_concept
    """).fetchall()

    text_to_id = {}
    for big_concept_text, module_id, _cnt in rows:
        module = _MODULE_MAP.get(module_id, "MX")
        slug = _slugify(big_concept_text)
        bc_id = f"BC_BIO_{module}_C{slug}"

        # 短名: 取核心术语（去掉"概念N "前缀）
        display_name = re.sub(r"^概念\d+\s*", "", big_concept_text).strip()
        if not display_name:
            display_name = big_concept_text

        conn.execute(
            "INSERT OR IGNORE INTO big_concepts (id, name, module, display_order, source_text) VALUES (?, ?, ?, ?, ?)",
            (bc_id, display_name, module, 0, big_concept_text),
        )
        text_to_id[big_concept_text] = bc_id

    conn.commit()
    return text_to_id


def _build_concept_map(conn: sqlite3.Connection, text_to_id: dict[str, str], base_dir: str):
    """Step 3: 读 skeleton 构建 concept→BigConcept 映射 + aliases + evidence_ids。"""
    skel_dir = os.path.join(base_dir, "subjects", "biology_senior", "skeleton", "L1")

    # req_id → big_concept_text 索引
    req_to_bc_text: dict[str, str] = {}
    for row in conn.execute(
        "SELECT id, big_concept FROM curriculum_requirements WHERE big_concept IS NOT NULL AND big_concept != ''"
    ):
        req_to_bc_text[row[0]] = row[1]

    # 遍历 L1 骨架 JSON
    if not os.path.exists(skel_dir):
        logger.warning("Skeleton dir not found: %s, skipping map + aliases", skel_dir)
        return

    for fname in sorted(os.listdir(skel_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(skel_dir, fname), encoding="utf-8") as f:
            concepts = json.load(f)

        for concept in concepts:
            cid = concept["id"]
            req_ids = concept.get("req_ids", [])
            aliases = concept.get("aliases", [])
            l0_ids = concept.get("l0_ids", [])

            # aliases_json
            aliases_json = json.dumps(aliases, ensure_ascii=False) if aliases else None
            conn.execute(
                "UPDATE concepts SET aliases_json = ? WHERE id = ?",
                (aliases_json, cid),
            )

            # evidence_ids_json
            evidence_json = json.dumps(l0_ids, ensure_ascii=False) if l0_ids else None
            conn.execute(
                "UPDATE concepts SET evidence_ids_json = ? WHERE id = ?",
                (evidence_json, cid),
            )

            # 推导 BigConcept 映射
            bc_ids = set()
            for rid in req_ids:
                bc_text = req_to_bc_text.get(rid)
                if bc_text and bc_text in text_to_id:
                    bc_ids.add(text_to_id[bc_text])

            is_single = len(bc_ids) == 1
            for bc_id in bc_ids:
                conn.execute(
                    "INSERT OR IGNORE INTO concept_big_concept_map (concept_id, big_concept_id, is_primary) VALUES (?, ?, ?)",
                    (cid, bc_id, 1 if is_single else 0),
                )

    conn.commit()


def _reclassify_l0(conn: sqlite3.Connection):
    """Step 4: L0 → evidence。"""
    conn.execute("UPDATE concepts SET knowledge_level = 'evidence' WHERE knowledge_level = 'L0'")
    conn.commit()


def _init_defaults(conn: sqlite3.Connection):
    """Step 5: 初始化 concepts 新列默认值（仅 L1）。"""
    conn.execute("""
        UPDATE concepts SET
            difficulty = COALESCE(difficulty, 3),
            bloom_level = COALESCE(bloom_level, 'understand'),
            review_status = COALESCE(review_status, 'ai_draft')
        WHERE knowledge_level = 'L1'
    """)
    conn.commit()


def run_migration(db_path: str, base_dir: str | None = None, dry_run: bool = False):
    """执行完整迁移。"""
    if base_dir is None:
        base_dir = str(Path(db_path).parent.parent)  # knowledge.db 上两级

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        # Step 1: Schema
        _ensure_schema(conn)

        # Step 2: BigConcepts
        text_to_id = _generate_big_concepts(conn)
        logger.info("Generated %d BigConcepts", len(text_to_id))

        # Step 3: Map + aliases + evidence_ids
        _build_concept_map(conn, text_to_id, base_dir)

        # Step 4: L0 → evidence
        _reclassify_l0(conn)

        # Step 5: Defaults
        _init_defaults(conn)

        if dry_run:
            conn.rollback()
            logger.info("Dry run — rolled back")
        else:
            logger.info("Migration complete")
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="知识图谱层级重构迁移")
    parser.add_argument("--db-path", default=str(Path.home() / "edu-knowledge-base" / "knowledge.db"))
    parser.add_argument("--base-dir", default=str(Path.home() / "edu-knowledge-base"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_migration(args.db_path, args.base_dir, args.dry_run)
