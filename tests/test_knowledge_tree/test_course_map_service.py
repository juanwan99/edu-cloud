"""课程地图服务测试 — 自包含 SQLite fixture + PG session。"""
import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge, ConceptGraphNode


# ──────────────────────────────────────────────────────────────────────────────
# SQLite knowledge.db fixture builder
# ──────────────────────────────────────────────────────────────────────────────

def _create_course_map_db(path: Path) -> str:
    """Create a minimal knowledge.db with all tables needed by the service."""
    conn = sqlite3.connect(str(path))
    cur = conn.cursor()

    # concepts
    cur.execute("""
        CREATE TABLE concepts (
            id TEXT PRIMARY KEY,
            name TEXT,
            knowledge_level TEXT,
            description TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO concepts VALUES (?, ?, ?, ?)",
        [
            ("BIO_M1_C1", "细胞膜结构", "L1", "描述细胞膜结构"),
            ("BIO_M1_C2", "光合作用", "L1", "光能转化"),
            ("BIO_M3_C1", "神经调节", "L1", "神经系统功能"),
        ],
    )

    # big_concepts
    cur.execute("""
        CREATE TABLE big_concepts (
            id TEXT PRIMARY KEY,
            name TEXT,
            module TEXT,
            display_order INTEGER DEFAULT 0
        )
    """)
    cur.executemany(
        "INSERT INTO big_concepts VALUES (?, ?, ?, ?)",
        [
            ("BC_M1_01", "细胞结构与功能", "M1", 1),
            ("BC_M3_01", "稳态调节", "M3", 1),
        ],
    )

    # concept_big_concept_map
    cur.execute("""
        CREATE TABLE concept_big_concept_map (
            concept_id TEXT,
            big_concept_id TEXT,
            is_primary INTEGER DEFAULT 0
        )
    """)
    cur.executemany(
        "INSERT INTO concept_big_concept_map VALUES (?, ?, ?)",
        [
            ("BIO_M1_C1", "BC_M1_01", 1),
            ("BIO_M1_C2", "BC_M1_01", 0),
            ("BIO_M3_C1", "BC_M3_01", 1),
        ],
    )

    # concept_relations (contrast)
    cur.execute("""
        CREATE TABLE concept_relations (
            source_id TEXT,
            target_id TEXT,
            relation_type TEXT,
            strength REAL DEFAULT 1.0,
            confidence REAL DEFAULT 1.0,
            evidence TEXT
        )
    """)
    cur.execute(
        "INSERT INTO concept_relations VALUES (?, ?, ?, ?, ?, ?)",
        ("BIO_M1_C1", "BIO_M1_C2", "contrast", 0.8, 0.9, "两者均为膜结构"),
    )

    # diagnostic_attributes
    cur.execute("""
        CREATE TABLE diagnostic_attributes (
            id TEXT PRIMARY KEY,
            name TEXT,
            linked_concept_ids TEXT,
            observable_behaviors TEXT,
            common_cause_families TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO diagnostic_attributes VALUES (?, ?, ?, ?, ?)",
        [
            ("DA_M1_01", "细胞膜功能", '["BIO_M1_C1"]', '["描述"]', None),
            ("DA_M1_02", "光合能量转换", '["BIO_M1_C2"]', '["分析"]', None),
            ("DA_M3_01", "神经传导", '["BIO_M3_C1"]', '["解释"]', None),
        ],
    )

    # study_units
    cur.execute("""
        CREATE TABLE study_units (
            id TEXT PRIMARY KEY,
            name TEXT,
            description TEXT,
            module TEXT,
            estimated_minutes INTEGER,
            source_concept_ids TEXT,
            prerequisite_unit_ids TEXT,
            textbook_anchor_ids TEXT,
            linked_da_ids TEXT,
            exam_tags TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO study_units VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "SU_M1_01", "细胞膜与细胞壁", "细胞膜功能概述", "M1", 90,
                '["BIO_M1_C1"]', '[]', '["SEC_01"]', '["DA_M1_01"]', '["基础"]',
            ),
            (
                "SU_M1_02", "光合作用与化能合成", "光能转化机制", "M1", 135,
                '["BIO_M1_C2"]', '["SU_M1_01"]', '["SEC_02"]', '["DA_M1_02"]', '["综合"]',
            ),
            (
                "SU_M3_01", "神经调节基础", "神经系统概述", "M3", 90,
                '["BIO_M3_C1"]', '[]', '[]', '["DA_M3_01"]', '["迁移"]',
            ),
        ],
    )

    # documents
    cur.execute("""
        CREATE TABLE documents (
            id TEXT PRIMARY KEY,
            title TEXT,
            type TEXT
        )
    """)
    cur.execute("INSERT INTO documents VALUES (?, ?, ?)", ("DOC_01", "人教版必修一", "textbook"))

    # sections
    cur.execute("""
        CREATE TABLE sections (
            id TEXT PRIMARY KEY,
            document_id TEXT,
            title TEXT,
            page_start INTEGER,
            page_end INTEGER
        )
    """)
    cur.executemany(
        "INSERT INTO sections VALUES (?, ?, ?, ?, ?)",
        [
            ("SEC_01", "DOC_01", "第一章第一节", 12, 15),
            ("SEC_02", "DOC_01", "第一章第四节", 28, 35),
        ],
    )

    # curriculum_requirements
    cur.execute("""
        CREATE TABLE curriculum_requirements (
            id TEXT PRIMARY KEY,
            text TEXT,
            requirement_type TEXT,
            big_concept TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO curriculum_requirements VALUES (?, ?, ?, ?)",
        [
            ("REQ_01", "描述细胞膜的结构", "content_requirement", "BC_M1_01"),
            ("REQ_02", "分析光合作用过程", "content_requirement", "BC_M1_01"),
            ("REQ_03", "解释神经调节机制", "academic_requirement", "BC_M3_01"),
        ],
    )

    # seed_req_da_map
    cur.execute("""
        CREATE TABLE seed_req_da_map (
            req_id TEXT,
            da_id TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO seed_req_da_map VALUES (?, ?)",
        [
            ("REQ_01", "DA_M1_01"),
            ("REQ_02", "DA_M1_02"),
            ("REQ_03", "DA_M3_01"),
        ],
    )

    # assessment_items
    cur.execute("""
        CREATE TABLE assessment_items (
            id TEXT PRIMARY KEY,
            stem TEXT,
            answer TEXT,
            question_type TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO assessment_items VALUES (?, ?, ?, ?)",
        [
            ("ITEM_01", "关于细胞膜的叙述正确的是", "A", "single"),
            ("ITEM_02", "下列关于光合作用的说法", "B", "single"),
            ("ITEM_03", "神经冲动传导方式是", "A", "single"),
            ("ITEM_04", "细胞膜功能综合题", "答案略", "essay"),
        ],
    )

    # q_matrix
    cur.execute("""
        CREATE TABLE q_matrix (
            item_id TEXT,
            attribute_id TEXT,
            transfer_band TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO q_matrix VALUES (?, ?, ?)",
        [
            ("ITEM_01", "DA_M1_01", "near"),
            ("ITEM_02", "DA_M1_02", "mid"),
            ("ITEM_03", "DA_M3_01", "near"),
            ("ITEM_04", "DA_M1_01", "far"),
        ],
    )

    # seed_su_exam_stats
    cur.execute("""
        CREATE TABLE seed_su_exam_stats (
            su_id TEXT PRIMARY KEY,
            transfer_band_dist TEXT
        )
    """)
    cur.executemany(
        "INSERT INTO seed_su_exam_stats VALUES (?, ?)",
        [
            ("SU_M1_01", '{"near": 5, "mid": 2, "far": 1}'),
            ("SU_M1_02", '{"near": 1, "mid": 6, "far": 3}'),
            ("SU_M3_01", '{"near": 4, "mid": 1, "far": 1}'),
        ],
    )

    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def course_map_db(tmp_path) -> str:
    """Create and return path to a temporary knowledge.db."""
    db_path = tmp_path / "knowledge.db"
    return _create_course_map_db(db_path)


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_module_overview(db, course_map_db):
    """ModuleOverviewResponse: 5 modules, curriculum summary, exam summary."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_module_overview

    result = await get_module_overview(db, kb_path=course_map_db)

    # 5 modules returned
    assert len(result.modules) == 5

    # Find M1 card
    m1 = next(c for c in result.modules if c.id == "M1")
    assert m1.name == "分子与细胞"
    assert m1.study_unit_count == 2
    assert m1.concept_count == 2  # BIO_M1_C1 + BIO_M1_C2
    assert m1.total_hours > 0

    # M3 card
    m3 = next(c for c in result.modules if c.id == "M3")
    assert m3.study_unit_count == 1
    assert m3.concept_count == 1

    # Curriculum summary: 2 content + 1 academic
    assert result.curriculum.content_count == 2
    assert result.curriculum.academic_count == 1
    assert len(result.curriculum.big_concepts) >= 1

    # Exam summary: 4 items total
    assert result.exam.total_items == 4
    # near=2 (ITEM_01, ITEM_03), mid=1, far=1
    assert result.exam.near_count == 2

    # Bridges: empty in this test (no PG bridge_to edges created)
    assert isinstance(result.bridges, list)


@pytest.mark.asyncio
async def test_get_module_overview_with_pg_bridge(db, course_map_db):
    """bridge_to edges in PG are returned as CrossModuleBridge items."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_module_overview

    now = datetime.now()
    # Insert PG nodes + bridge_to edge
    db.add(ConceptGraphNode(
        id="BIO_M1_C1", name="细胞膜结构", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    db.add(ConceptGraphNode(
        id="BIO_M3_C1", name="神经调节", knowledge_level="L1",
        primary_module="M3", node_type="concept", synced_at=now,
    ))
    await db.flush()
    db.add(ConceptGraphEdge(
        source_id="BIO_M1_C1", target_id="BIO_M3_C1",
        relation_type="bridge_to", strength=1.0, confidence=0.8, synced_at=now,
    ))
    await db.commit()

    result = await get_module_overview(db, kb_path=course_map_db)
    assert len(result.bridges) == 1
    bridge = result.bridges[0]
    assert bridge.source_module == "M1"
    assert bridge.target_module == "M3"


@pytest.mark.asyncio
async def test_get_module_map(db, course_map_db):
    """ModuleMapResponse for M1: study_units, concept_clusters, exam_profile."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_module_map

    result = await get_module_map(db, module="M1", kb_path=course_map_db)

    assert result.module_id == "M1"
    assert result.module_name == "分子与细胞"
    assert result.total_hours > 0

    # 2 study units
    assert len(result.study_units) == 2
    su_names = {su.name for su in result.study_units}
    assert "细胞膜与细胞壁" in su_names
    assert "光合作用与化能合成" in su_names

    # SU_M1_02 has SU_M1_01 as prerequisite
    su2 = next(su for su in result.study_units if su.id == "SU_M1_02")
    assert "细胞膜与细胞壁" in su2.prerequisites

    # Concept clusters: BC_M1_01 maps to 2 concepts
    assert len(result.concept_clusters) >= 1
    all_concepts_in_clusters = [c for cl in result.concept_clusters for c in cl.concepts]
    assert len(all_concepts_in_clusters) >= 1

    # Exam profile: has data
    assert result.exam_profile.total_items > 0
    pct_sum = result.exam_profile.near_pct + result.exam_profile.mid_pct + result.exam_profile.far_pct
    assert abs(pct_sum - 100.0) < 1.0

    # No PG bridges in this test
    assert isinstance(result.outgoing_bridges, list)


@pytest.mark.asyncio
async def test_get_module_map_empty_module(db, course_map_db):
    """M2 has no study units → empty lists, zero hours."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_module_map

    result = await get_module_map(db, module="M2", kb_path=course_map_db)
    assert result.module_id == "M2"
    assert result.study_units == []
    assert result.total_hours == 0.0


@pytest.mark.asyncio
async def test_get_study_unit_detail(db, course_map_db):
    """StudyUnitDetailResponse for SU_M1_02: prerequisites, textbook, exam_patterns."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_study_unit_detail

    result = await get_study_unit_detail(db, su_id="SU_M1_02", kb_path=course_map_db)

    assert result.id == "SU_M1_02"
    assert result.name == "光合作用与化能合成"
    assert result.estimated_minutes == 135

    # Prerequisites
    prereq_names = [p.target_name for p in result.prerequisites]
    assert "细胞膜与细胞壁" in prereq_names
    assert all(p.category == "必经前置" for p in result.prerequisites)

    # Textbook anchors
    assert len(result.textbook) >= 1
    anchor = result.textbook[0]
    assert anchor.book == "人教版必修一"
    assert "第一章" in anchor.section

    # Concepts
    assert len(result.concepts) >= 1
    assert any(c["name"] == "光合作用" for c in result.concepts)

    # Curriculum
    assert len(result.curriculum) >= 1

    # Exam patterns: DA_M1_02 → ITEM_02 (mid)
    assert len(result.exam_patterns) >= 1
    bands = {ep.band for ep in result.exam_patterns}
    assert "情境应用" in bands  # mid


@pytest.mark.asyncio
async def test_get_study_unit_detail_successors(db, course_map_db):
    """SU_M1_01 should have SU_M1_02 as a successor."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_study_unit_detail

    result = await get_study_unit_detail(db, su_id="SU_M1_01", kb_path=course_map_db)

    assert result.id == "SU_M1_01"
    successor_names = [s.target_name for s in result.successors]
    assert "光合作用与化能合成" in successor_names


@pytest.mark.asyncio
async def test_get_study_unit_detail_contrasts(db, course_map_db):
    """SU_M1_01 (contains BIO_M1_C1) should have contrast with BIO_M1_C2."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_study_unit_detail

    result = await get_study_unit_detail(db, su_id="SU_M1_01", kb_path=course_map_db)

    contrast_names = [c.target_name for c in result.contrasts]
    assert "光合作用" in contrast_names
    assert result.contrasts[0].evidence == "两者均为膜结构"


@pytest.mark.asyncio
async def test_get_study_unit_detail_missing(db, course_map_db):
    """Non-existent SU returns fallback response without crashing."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_study_unit_detail

    result = await get_study_unit_detail(db, su_id="NONEXISTENT", kb_path=course_map_db)
    assert result.id == "NONEXISTENT"
    assert result.prerequisites == []
    assert result.exam_patterns == []


@pytest.mark.asyncio
async def test_get_module_overview_no_db(db, tmp_path):
    """When knowledge.db doesn't exist, service returns zeros gracefully."""
    from edu_cloud.modules.knowledge_tree.course_map_service import get_module_overview

    missing = str(tmp_path / "nonexistent.db")
    result = await get_module_overview(db, kb_path=missing)

    assert len(result.modules) == 5
    for card in result.modules:
        assert card.study_unit_count == 0
    assert result.exam.total_items == 0
    assert result.curriculum.content_count == 0
