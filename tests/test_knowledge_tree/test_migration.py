"""知识图谱层级重构 — 迁移脚本测试。"""
import json
import os
import sqlite3

import pytest


def _create_knowledge_db_with_hierarchy(path: str) -> str:
    """创建含 curriculum_requirements 和 L1 骨架的测试 knowledge.db。"""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE concepts (
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL DEFAULT 'biology_senior',
            level TEXT NOT NULL DEFAULT 'L1',
            knowledge_level TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            source_block_id TEXT,
            source_req_id TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE concept_relations (
            id INTEGER PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            strength REAL DEFAULT 1.0,
            confidence REAL DEFAULT 1.0
        )
    """)
    conn.execute("""
        CREATE TABLE curriculum_requirements (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL DEFAULT 'doc1',
            module_id TEXT NOT NULL,
            big_concept TEXT,
            text TEXT NOT NULL,
            source_page INTEGER NOT NULL DEFAULT 1,
            requirement_type TEXT DEFAULT 'content'
        )
    """)

    # 3 modules, 3 big_concepts (2 in M1, 1 in M2)
    conn.executemany("INSERT INTO curriculum_requirements VALUES (?,?,?,?,?,?,?)", [
        ("req:001", "doc1", "mod:bio_sr:required_1", "概念1 细胞是基本单位", "内容A", 1, "content"),
        ("req:002", "doc1", "mod:bio_sr:required_1", "概念1 细胞是基本单位", "内容B", 2, "content"),
        ("req:003", "doc1", "mod:bio_sr:required_1", "概念2 细胞需要能量", "内容C", 3, "content"),
        ("req:004", "doc1", "mod:bio_sr:required_2", "概念3 遗传信息", "内容D", 4, "content"),
        ("req:005", "doc1", "mod:bio_sr:required_2", None, "无大概念行", 5, "content"),
    ])

    # 5 L1 concepts
    for i, (cid, name, module) in enumerate([
        ("BIO_SR_CP_M1_C1", "细胞学说", "M1"),
        ("BIO_SR_CP_M1_C2", "ATP合成", "M1"),
        ("BIO_SR_CP_M1_C3", "细胞呼吸", "M1"),
        ("BIO_SR_CP_M2_C4", "DNA复制", "M2"),
        ("BIO_SR_CP_M2_C5", "基因表达", "M2"),
    ]):
        conn.execute(
            "INSERT INTO concepts VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, "biology_senior", "L1", "L1", name, f"描述{i}", None, None, None),
        )

    # 3 L0 concepts
    for i, cid in enumerate(["BIO_SR_B1_BK_001", "BIO_SR_B1_BK_002", "BIO_SR_B1_BK_003"]):
        conn.execute(
            "INSERT INTO concepts VALUES (?,?,?,?,?,?,?,?,?)",
            (cid, "biology_senior", "L0", "L0", f"原子事实{i}", f"L0描述{i}", None, None, None),
        )

    # edges
    conn.execute(
        "INSERT INTO concept_relations VALUES (1, 'BIO_SR_CP_M1_C1', 'BIO_SR_CP_M1_C2', 'prerequisite_hard', 1.0, 1.0)"
    )
    conn.execute(
        "INSERT INTO concept_relations VALUES (2, 'BIO_SR_CP_M2_C4', 'BIO_SR_CP_M2_C5', 'prerequisite_hard', 1.0, 1.0)"
    )

    conn.commit()
    conn.close()
    return path


def _create_skeleton(base_dir: str):
    """创建 L1 骨架 JSON 文件。"""
    skel_dir = os.path.join(base_dir, "subjects", "biology_senior", "skeleton", "L1")
    os.makedirs(skel_dir, exist_ok=True)

    m1_concepts = [
        {
            "id": "BIO_SR_CP_M1_C1", "canonical_name": "细胞学说",
            "description": "desc", "module": "M1",
            "req_ids": ["req:001", "req:002"],  # -> 概念1
            "l0_ids": ["BIO_SR_B1_BK_001", "BIO_SR_B1_BK_002"],
            "aliases": ["细胞学说三要点"],
        },
        {
            "id": "BIO_SR_CP_M1_C2", "canonical_name": "ATP合成",
            "description": "desc", "module": "M1",
            "req_ids": ["req:003"],  # -> 概念2
            "l0_ids": ["BIO_SR_B1_BK_003"],
            "aliases": [],
        },
        {
            "id": "BIO_SR_CP_M1_C3", "canonical_name": "细胞呼吸",
            "description": "desc", "module": "M1",
            "req_ids": ["req:001"],  # -> 概念1
            "l0_ids": [],
            "aliases": ["有氧呼吸", "无氧呼吸"],
        },
    ]
    m2_concepts = [
        {
            "id": "BIO_SR_CP_M2_C4", "canonical_name": "DNA复制",
            "description": "desc", "module": "M2",
            "req_ids": ["req:004"],  # -> 概念3
            "l0_ids": [],
            "aliases": [],
        },
        {
            "id": "BIO_SR_CP_M2_C5", "canonical_name": "基因表达",
            "description": "desc", "module": "M2",
            "req_ids": ["req:004"],  # -> 概念3
            "l0_ids": [],
            "aliases": ["基因的表达"],
        },
    ]

    with open(os.path.join(skel_dir, "M1_concepts.json"), "w", encoding="utf-8") as f:
        json.dump(m1_concepts, f, ensure_ascii=False)
    with open(os.path.join(skel_dir, "M2_concepts.json"), "w", encoding="utf-8") as f:
        json.dump(m2_concepts, f, ensure_ascii=False)

    return skel_dir


@pytest.fixture
def migration_env(tmp_path):
    """创建完整的迁移测试环境。"""
    db_path = str(tmp_path / "knowledge.db")
    _create_knowledge_db_with_hierarchy(db_path)
    _create_skeleton(str(tmp_path))
    return db_path, str(tmp_path)


class TestBigConceptCount:
    """契约 1: 迁移后 big_concepts 行数正确。"""

    def test_big_concept_count(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM big_concepts").fetchone()[0]
        # 3 distinct big_concepts: 概念1(M1), 概念2(M1), 概念3(M2)
        assert count == 3
        conn.close()

    def test_big_concept_ids_are_stable(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        ids = [r[0] for r in conn.execute("SELECT id FROM big_concepts ORDER BY id")]
        # IDs follow BC_{SUBJECT}_{MODULE}_{SLUG} pattern
        for bc_id in ids:
            assert bc_id.startswith("BC_BIO_")
        conn.close()

    def test_big_concept_has_module(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        for row in conn.execute("SELECT id, module FROM big_concepts"):
            assert row[1] in ("M1", "M2", "M3", "M4", "M5"), f"Bad module for {row[0]}"
        conn.close()


class TestMapCoverage:
    """契约 2: concept_big_concept_map 覆盖所有 L1，is_primary 约束生效。"""

    def test_map_coverage(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        # All 5 L1 concepts should have at least one map entry
        mapped_concepts = {r[0] for r in conn.execute(
            "SELECT DISTINCT concept_id FROM concept_big_concept_map"
        )}
        l1_concepts = {r[0] for r in conn.execute(
            "SELECT id FROM concepts WHERE knowledge_level='L1'"
        )}
        assert mapped_concepts == l1_concepts

        # is_primary: each concept has at most one primary
        for cid in mapped_concepts:
            primary_count = conn.execute(
                "SELECT COUNT(*) FROM concept_big_concept_map WHERE concept_id=? AND is_primary=1",
                (cid,)
            ).fetchone()[0]
            assert primary_count <= 1, f"{cid} has {primary_count} primary entries"
        conn.close()

    def test_single_membership_is_primary(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        # Concepts with single BigConcept should be is_primary=TRUE
        for cid in ["BIO_SR_CP_M1_C2", "BIO_SR_CP_M2_C4", "BIO_SR_CP_M2_C5"]:
            row = conn.execute(
                "SELECT is_primary FROM concept_big_concept_map WHERE concept_id=?", (cid,)
            ).fetchone()
            assert row is not None, f"{cid} not in map"
            assert row[0] == 1, f"{cid} should be primary"
        conn.close()


class TestL0Reclassification:
    """契约 3: L0 重分类为 evidence。"""

    def test_l0_reclassification(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        l0_count = conn.execute(
            "SELECT COUNT(*) FROM concepts WHERE knowledge_level='L0'"
        ).fetchone()[0]
        assert l0_count == 0, "L0 should be reclassified"

        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM concepts WHERE knowledge_level='evidence'"
        ).fetchone()[0]
        assert evidence_count == 3  # was 3 L0

        # L1 untouched
        l1_count = conn.execute(
            "SELECT COUNT(*) FROM concepts WHERE knowledge_level='L1'"
        ).fetchone()[0]
        assert l1_count == 5
        conn.close()

    def test_l0_only_level_changed(self, migration_env):
        """CE-001: L0 只改 knowledge_level，不改 name/id/description。"""
        db_path, base_dir = migration_env

        conn = sqlite3.connect(db_path)
        before = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT id, name, description FROM concepts WHERE knowledge_level='L0'"
        )}
        conn.close()

        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        for cid, (name, desc) in before.items():
            row = conn.execute(
                "SELECT name, description, knowledge_level FROM concepts WHERE id=?", (cid,)
            ).fetchone()
            assert row[0] == name, f"{cid} name changed"
            assert row[1] == desc, f"{cid} description changed"
            assert row[2] == "evidence"
        conn.close()


class TestAliasesMigration:
    """契约 4 (R3-F002): aliases_json 从 JSON 骨架迁移。"""

    def test_aliases_migration(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        # BIO_SR_CP_M1_C1 has aliases ["细胞学说三要点"]
        row = conn.execute(
            "SELECT aliases_json FROM concepts WHERE id='BIO_SR_CP_M1_C1'"
        ).fetchone()
        assert row[0] is not None
        aliases = json.loads(row[0])
        assert "细胞学说三要点" in aliases

        # BIO_SR_CP_M1_C2 has aliases [] -> NULL
        row = conn.execute(
            "SELECT aliases_json FROM concepts WHERE id='BIO_SR_CP_M1_C2'"
        ).fetchone()
        assert row[0] is None or json.loads(row[0]) == []
        conn.close()

    def test_aliases_no_skeleton_is_null(self, migration_env):
        """骨架中找不到概念 → aliases_json 为 NULL。"""
        db_path, base_dir = migration_env

        # Add concept without skeleton entry
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO concepts VALUES (?,?,?,?,?,?,?,?,?)",
            ("BIO_SR_CP_M1_ORPHAN", "biology_senior", "L1", "L1", "孤儿概念", None, None, None, None),
        )
        conn.commit()
        conn.close()

        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT aliases_json FROM concepts WHERE id='BIO_SR_CP_M1_ORPHAN'"
        ).fetchone()
        assert row[0] is None
        conn.close()


class TestEvidenceIdsMigration:
    """契约 5 (R3-F002): evidence_ids_json 从 JSON 骨架迁移。"""

    def test_evidence_ids_migration(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT evidence_ids_json FROM concepts WHERE id='BIO_SR_CP_M1_C1'"
        ).fetchone()
        assert row[0] is not None
        evidence_ids = json.loads(row[0])
        assert "BIO_SR_B1_BK_001" in evidence_ids
        assert "BIO_SR_B1_BK_002" in evidence_ids

        # C2 has one l0_id
        row = conn.execute(
            "SELECT evidence_ids_json FROM concepts WHERE id='BIO_SR_CP_M1_C2'"
        ).fetchone()
        assert row[0] is not None
        assert "BIO_SR_B1_BK_003" in json.loads(row[0])
        conn.close()

    def test_empty_l0_ids(self, migration_env):
        """l0_ids 为空数组 → evidence_ids_json 为 NULL。"""
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT evidence_ids_json FROM concepts WHERE id='BIO_SR_CP_M2_C4'"
        ).fetchone()
        assert row[0] is None or json.loads(row[0]) == []
        conn.close()


class TestRelationsUnchanged:
    """INV-003: concept_relations 在迁移前后不变。"""

    def test_relations_unchanged(self, migration_env):
        db_path, base_dir = migration_env

        conn = sqlite3.connect(db_path)
        before_count = conn.execute("SELECT COUNT(*) FROM concept_relations").fetchone()[0]
        before_data = set(conn.execute(
            "SELECT source_id, target_id, relation_type FROM concept_relations"
        ).fetchall())
        conn.close()

        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        after_count = conn.execute("SELECT COUNT(*) FROM concept_relations").fetchone()[0]
        after_data = set(conn.execute(
            "SELECT source_id, target_id, relation_type FROM concept_relations"
        ).fetchall())
        conn.close()

        assert before_count == after_count
        assert before_data == after_data


class TestL1IdsUnchanged:
    """INV-001: L1 ID 不变。"""

    def test_l1_ids_unchanged(self, migration_env):
        db_path, base_dir = migration_env

        conn = sqlite3.connect(db_path)
        before_ids = {r[0] for r in conn.execute(
            "SELECT id FROM concepts WHERE knowledge_level='L1'"
        )}
        conn.close()

        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        after_ids = {r[0] for r in conn.execute(
            "SELECT id FROM concepts WHERE knowledge_level='L1'"
        )}
        conn.close()

        assert before_ids == after_ids


class TestIdempotency:
    """迁移幂等性。"""

    def test_idempotent(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration

        run_migration(db_path, base_dir)
        conn = sqlite3.connect(db_path)
        count1 = conn.execute("SELECT COUNT(*) FROM big_concepts").fetchone()[0]
        map1 = conn.execute("SELECT COUNT(*) FROM concept_big_concept_map").fetchone()[0]
        conn.close()

        run_migration(db_path, base_dir)
        conn = sqlite3.connect(db_path)
        count2 = conn.execute("SELECT COUNT(*) FROM big_concepts").fetchone()[0]
        map2 = conn.execute("SELECT COUNT(*) FROM concept_big_concept_map").fetchone()[0]
        conn.close()

        assert count1 == count2
        assert map1 == map2


class TestDefaultValues:
    """Step 5: concepts 新列默认值。"""

    def test_default_values(self, migration_env):
        db_path, base_dir = migration_env
        from scripts.migrate_knowledge_hierarchy import run_migration
        run_migration(db_path, base_dir)

        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT difficulty, bloom_level, review_status FROM concepts WHERE id='BIO_SR_CP_M1_C1'"
        ).fetchone()
        assert row[0] == 3  # default difficulty
        assert row[1] == "understand"  # default bloom_level
        assert row[2] == "ai_draft"  # default review_status
        conn.close()
