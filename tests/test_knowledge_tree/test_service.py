import pytest
import tempfile
import sqlite3
from datetime import datetime

from sqlalchemy import select, func
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap
from edu_cloud.modules.adaptive.models import StudentDaMastery, DaKnowledgePointMap


async def _seed_graph(db):
    """插入测试图谱数据。"""
    now = datetime.now()
    db.add_all([
        ConceptGraphNode(id="CP_M1_A", name="概念A", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now),
        ConceptGraphNode(id="CP_M1_B", name="概念B", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now),
        ConceptGraphNode(id="CP_M2_C", name="概念C", knowledge_level="L1",
                         primary_module="M2", node_type="concept", synced_at=now),
    ])
    await db.flush()
    db.add_all([
        ConceptGraphEdge(source_id="CP_M1_A", target_id="CP_M1_B",
                         relation_type="prerequisite_hard", synced_at=now),
        ConceptGraphEdge(source_id="CP_M1_B", target_id="CP_M2_C",
                         relation_type="bridge_to", synced_at=now),
    ])
    await db.commit()


async def _seed_mastery(db):
    """插入测试掌握度数据。"""
    db.add_all([
        DaKnowledgePointMap(da_id="DA_001", knowledge_point_id="CP_M1_A", weight=1.0),
        DaKnowledgePointMap(da_id="DA_002", knowledge_point_id="CP_M1_A", weight=1.0),
        DaKnowledgePointMap(da_id="DA_003", knowledge_point_id="CP_M1_B", weight=1.0),
    ])
    await db.flush()
    db.add_all([
        StudentDaMastery(id="m1", student_id="S001", da_id="DA_001",
                         mastery_prob=0.9, attempt_count=10, correct_count=9, school_id="SCH1"),
        StudentDaMastery(id="m2", student_id="S001", da_id="DA_002",
                         mastery_prob=0.6, attempt_count=5, correct_count=3, school_id="SCH1"),
        StudentDaMastery(id="m3", student_id="S001", da_id="DA_003",
                         mastery_prob=0.2, attempt_count=3, correct_count=0, school_id="SCH1"),
    ])
    await db.commit()


@pytest.mark.asyncio
async def test_get_graph_all_modules(db):
    await _seed_graph(db)
    from edu_cloud.modules.knowledge_tree.service import get_graph
    result = await get_graph(db, module="all")
    assert len(result["graph"]["nodes"]) == 3
    assert len(result["graph"]["edges"]) == 2


@pytest.mark.asyncio
async def test_get_graph_filter_by_module(db):
    await _seed_graph(db)
    from edu_cloud.modules.knowledge_tree.service import get_graph
    result = await get_graph(db, module="M1")
    assert len(result["graph"]["nodes"]) == 2
    assert all(n["module"] == "M1" for n in result["graph"]["nodes"])
    # 跨模块边 CP_M1_B→CP_M2_C 不应返回（induced subgraph）
    edge_targets = {e["target"] for e in result["graph"]["edges"]}
    assert "CP_M2_C" not in edge_targets


@pytest.mark.asyncio
async def test_get_mastery(db):
    await _seed_graph(db)
    await _seed_mastery(db)
    from edu_cloud.modules.knowledge_tree.service import get_mastery
    result = await get_mastery(db, student_id="S001", module="all")
    assert len(result["concept_mastery"]) >= 1
    # CP_M1_A 关联 DA_001(0.9) + DA_002(0.6)，平均 0.75
    cp_a = next(c for c in result["concept_mastery"] if c["concept_id"] == "CP_M1_A")
    assert abs(cp_a["mastery"] - 0.75) < 0.01
    assert cp_a["state"] == "fragile"  # 0.6 <= 0.75 < 0.85


@pytest.mark.asyncio
async def test_get_mastery_unseen_concept(db):
    await _seed_graph(db)
    # 不插入 mastery 数据
    from edu_cloud.modules.knowledge_tree.service import get_mastery
    result = await get_mastery(db, student_id="S001", module="all")
    for cm in result["concept_mastery"]:
        assert cm["state"] == "unseen"
        assert cm["mastery"] == 0.0


@pytest.mark.asyncio
async def test_get_mastery_module_aggregation(db):
    await _seed_graph(db)
    await _seed_mastery(db)
    from edu_cloud.modules.knowledge_tree.service import get_mastery
    result = await get_mastery(db, student_id="S001", module="all")
    assert len(result["module_mastery"]) >= 1
    m1 = next(m for m in result["module_mastery"] if m["module"] == "M1")
    assert m1["mastery"] > 0


@pytest.mark.asyncio
async def test_backwrite_to_knowledge_db(db):
    """编辑后回写到 knowledge.db。"""
    await _seed_graph(db)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        kb_path = f.name
    conn = sqlite3.connect(kb_path)
    conn.execute("""
        CREATE TABLE concepts (
            id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT,
            description TEXT, source_block_id TEXT
        )
    """)
    conn.execute("INSERT INTO concepts VALUES ('CP_M1_A', '概念A', 'L1', NULL, NULL)")
    conn.execute("INSERT INTO concepts VALUES ('CP_M1_B', '概念B', 'L1', NULL, NULL)")
    conn.execute("""
        CREATE TABLE concept_relations (
            source_id TEXT, target_id TEXT, relation_type TEXT,
            strength REAL DEFAULT 1.0, confidence REAL DEFAULT 1.0,
            PRIMARY KEY (source_id, target_id)
        )
    """)
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.service import backwrite_to_knowledge_db
    result = await backwrite_to_knowledge_db(
        db, kb_path,
        [
            {"op": "update_node", "id": "CP_M1_A", "fields": {"name": "概念A改名"}},
            {"op": "add_edge", "source": "CP_M1_A", "target": "CP_M1_B",
             "type": "prerequisite_hard", "strength": 0.8},
        ]
    )
    assert result["success"] is True

    # 验证 knowledge.db 已更新
    conn = sqlite3.connect(kb_path)
    name = conn.execute("SELECT name FROM concepts WHERE id='CP_M1_A'").fetchone()[0]
    assert name == "概念A改名"
    edge = conn.execute("SELECT * FROM concept_relations WHERE source_id='CP_M1_A'").fetchone()
    assert edge is not None
    conn.close()


@pytest.mark.asyncio
async def test_backwrite_failure_recorded(db):
    """回写失败时记录到 edit_sync_failures 表。"""
    await _seed_graph(db)
    from edu_cloud.modules.knowledge_tree.service import backwrite_to_knowledge_db
    result = await backwrite_to_knowledge_db(
        db, "/nonexistent/knowledge.db",
        [{"op": "update_node", "id": "CP_M1_A", "fields": {"name": "X"}}]
    )
    assert result["success"] is False

    from edu_cloud.modules.knowledge_tree.models import EditSyncFailure
    count = await db.scalar(select(func.count()).select_from(EditSyncFailure))
    assert count >= 1


@pytest.mark.asyncio
async def test_apply_edits_records_failure_when_kb_missing(db, monkeypatch):
    """F002/F003: apply_edits 主入口在 knowledge.db 不存在时应记录 EditSyncFailure。"""
    await _seed_graph(db)
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", "/nonexistent/knowledge.db")
    from edu_cloud.modules.knowledge_tree.service import apply_edits
    applied = await apply_edits(db, [{"op": "update_node", "id": "CP_M1_A", "fields": {"name": "X"}}])
    assert applied == 1

    from edu_cloud.modules.knowledge_tree.models import EditSyncFailure
    count = await db.scalar(select(func.count()).select_from(EditSyncFailure))
    assert count >= 1, "apply_edits should record EditSyncFailure when knowledge.db is missing"


@pytest.mark.asyncio
async def test_update_node_whitelist_blocks_disallowed_fields(db):
    """F004: update_node 只允许修改 name/description，不允许 knowledge_level 等。"""
    await _seed_graph(db)
    from edu_cloud.modules.knowledge_tree.service import apply_edits
    await apply_edits(db, [{"op": "update_node", "id": "CP_M1_A", "fields": {"name": "NewName", "knowledge_level": "L0"}}])
    node = await db.get(ConceptGraphNode, "CP_M1_A")
    assert node.name == "NewName"
    assert node.knowledge_level == "L1", "knowledge_level should not be updatable via whitelist"


@pytest.mark.asyncio
async def test_backwrite_whitelist_blocks_disallowed_fields_sqlite(db):
    """R2-02: SQLite 回写路径也应遵守白名单，禁止字段不写入 knowledge.db。"""
    await _seed_graph(db)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        kb_path = f.name
    conn = sqlite3.connect(kb_path)
    conn.execute("""
        CREATE TABLE concepts (
            id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT,
            description TEXT, source_block_id TEXT
        )
    """)
    conn.execute("INSERT INTO concepts VALUES ('CP_M1_A', '概念A', 'L1', NULL, NULL)")
    conn.execute("""
        CREATE TABLE concept_relations (
            source_id TEXT, target_id TEXT, relation_type TEXT,
            strength REAL DEFAULT 1.0, confidence REAL DEFAULT 1.0,
            PRIMARY KEY (source_id, target_id)
        )
    """)
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.service import backwrite_to_knowledge_db
    await backwrite_to_knowledge_db(
        db, kb_path,
        [{"op": "update_node", "id": "CP_M1_A", "fields": {"name": "NewName", "knowledge_level": "L0"}}]
    )
    conn = sqlite3.connect(kb_path)
    row = conn.execute("SELECT name, knowledge_level FROM concepts WHERE id='CP_M1_A'").fetchone()
    conn.close()
    assert row[0] == "NewName", "allowed field 'name' should be updated"
    assert row[1] == "L1", "disallowed field 'knowledge_level' should NOT be updated in SQLite"


@pytest.mark.asyncio
async def test_get_mastery_filters_by_school_id(db):
    """F003: mastery 按 school_id 过滤，跨校数据不可见。"""
    await _seed_graph(db)
    await _seed_mastery(db)  # school_id="SCH1"
    from edu_cloud.modules.knowledge_tree.service import get_mastery
    result = await get_mastery(db, student_id="S001", module="all", school_id="OTHER_SCHOOL")
    # 应返回所有概念但 mastery 都是 0（找不到该校的掌握度数据）
    for cm in result["concept_mastery"]:
        assert cm["mastery"] == 0.0, f"concept {cm['concept_id']} should have 0 mastery for wrong school"


@pytest.mark.asyncio
async def test_get_mastery_excludes_big_concepts(db):
    """INV-005 / F001: mastery 不含 BigConcept 节点。"""
    await _seed_graph(db)
    now = datetime.now()
    # 插入 BigConcept 节点
    db.add(ConceptGraphNode(
        id="BC_M1_C1", name="大概念1", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    await db.commit()
    await _seed_mastery(db)

    from edu_cloud.modules.knowledge_tree.service import get_mastery
    result = await get_mastery(db, student_id="S001", module="all")
    concept_ids = {cm["concept_id"] for cm in result["concept_mastery"]}
    assert "BC_M1_C1" not in concept_ids, "BigConcept should not appear in mastery"
    # 仍然包含 3 个 concept 节点
    assert len(result["concept_mastery"]) == 3
