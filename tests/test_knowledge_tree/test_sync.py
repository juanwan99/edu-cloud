import pytest
import sqlite3

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge


def _create_knowledge_db(path):
    """创建测试用的 knowledge.db"""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE concepts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            knowledge_level TEXT NOT NULL,
            description TEXT,
            source_block_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE concept_relations (
            id INTEGER PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            strength REAL DEFAULT 1.0
        )
    """)
    conn.execute("""
        INSERT INTO concepts VALUES
        ('BIO_SR_CP_M1_ATP', 'ATP与细胞能量货币', 'L1', '描述', NULL)
    """)
    conn.execute("""
        INSERT INTO concepts VALUES
        ('BIO_SR_CP_M1_CELL_RESP', '细胞呼吸', 'L1', NULL, NULL)
    """)
    conn.execute("""
        INSERT INTO concept_relations VALUES
        (1, 'BIO_SR_CP_M1_ATP', 'BIO_SR_CP_M1_CELL_RESP', 'prerequisite_hard', 1.0, 1.0)
    """)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def knowledge_db_path(tmp_path):
    return _create_knowledge_db(str(tmp_path / "knowledge.db"))


def test_read_concepts_from_knowledge_db(knowledge_db_path):
    from scripts.sync_concept_graph import read_knowledge_db
    nodes, edges = read_knowledge_db(knowledge_db_path)
    assert len(nodes) == 2
    assert nodes[0]["id"] == "BIO_SR_CP_M1_ATP"
    assert nodes[0]["name"] == "ATP与细胞能量货币"
    assert nodes[0]["knowledge_level"] == "L1"


def test_read_edges_from_knowledge_db(knowledge_db_path):
    from scripts.sync_concept_graph import read_knowledge_db
    nodes, edges = read_knowledge_db(knowledge_db_path)
    assert len(edges) == 1
    assert edges[0]["source_id"] == "BIO_SR_CP_M1_ATP"
    assert edges[0]["target_id"] == "BIO_SR_CP_M1_CELL_RESP"
    assert edges[0]["relation_type"] == "prerequisite_hard"


def test_extract_module_from_id():
    from scripts.sync_concept_graph import extract_module
    assert extract_module("BIO_SR_CP_M1_ATP") == "M1"
    assert extract_module("BIO_SR_CP_M2_DNA") == "M2"
    assert extract_module("UNKNOWN_FORMAT") == "unknown"


@pytest.mark.asyncio
async def test_sync_writes_to_db(db, knowledge_db_path):
    from scripts.sync_concept_graph import read_knowledge_db, sync_to_postgres
    nodes, edges = read_knowledge_db(knowledge_db_path)
    await sync_to_postgres(db, nodes, edges)

    from sqlalchemy import select, func
    node_count = await db.scalar(select(func.count()).select_from(ConceptGraphNode))
    edge_count = await db.scalar(select(func.count()).select_from(ConceptGraphEdge))
    assert node_count == 2
    assert edge_count == 1


@pytest.mark.asyncio
async def test_sync_is_idempotent(db, knowledge_db_path):
    from scripts.sync_concept_graph import read_knowledge_db, sync_to_postgres
    nodes, edges = read_knowledge_db(knowledge_db_path)
    await sync_to_postgres(db, nodes, edges)
    await sync_to_postgres(db, nodes, edges)  # 再次同步

    from sqlalchemy import select, func
    node_count = await db.scalar(select(func.count()).select_from(ConceptGraphNode))
    assert node_count == 2  # 不会翻倍
