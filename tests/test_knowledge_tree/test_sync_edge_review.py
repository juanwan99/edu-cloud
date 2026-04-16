"""Sync/backwrite edge review_status 测试。"""
import sqlite3
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import select

from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
from edu_cloud.modules.knowledge_tree.sync_service import _read_knowledge_db


def _create_test_knowledge_db(path: str, with_review_status: bool = True):
    """创建临时 knowledge.db，含 L1 concepts + concept_relations。"""
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE concepts (
            id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT,
            description TEXT, difficulty INTEGER, bloom_level TEXT,
            aliases_json TEXT, evidence_ids_json TEXT, review_status TEXT
        )
    """)
    review_col = ", review_status TEXT" if with_review_status else ""
    conn.execute(f"""
        CREATE TABLE concept_relations (
            source_id TEXT, target_id TEXT, relation_type TEXT,
            strength REAL, confidence REAL{review_col}
        )
    """)
    conn.execute("""
        CREATE TABLE big_concepts (
            id TEXT PRIMARY KEY, name TEXT, module TEXT, display_order INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE concept_big_concept_map (
            concept_id TEXT, big_concept_id TEXT, is_primary INTEGER
        )
    """)
    # 插入数据
    conn.execute("INSERT INTO concepts VALUES ('BIO_M1_A','概念A','L1','描述A',NULL,NULL,NULL,NULL,'ai_draft')")
    conn.execute("INSERT INTO concepts VALUES ('BIO_M1_B','概念B','L1','描述B',NULL,NULL,NULL,NULL,'teacher_reviewed')")
    conn.execute("INSERT INTO big_concepts VALUES ('BC_M1','大概念','M1',0)")
    conn.execute("INSERT INTO concept_big_concept_map VALUES ('BIO_M1_A','BC_M1',1)")
    conn.execute("INSERT INTO concept_big_concept_map VALUES ('BIO_M1_B','BC_M1',1)")
    if with_review_status:
        conn.execute(
            "INSERT INTO concept_relations (source_id,target_id,relation_type,strength,confidence,review_status) "
            "VALUES ('BIO_M1_A','BIO_M1_B','prerequisite_hard',1.0,0.8,'teacher_reviewed')"
        )
    else:
        conn.execute(
            "INSERT INTO concept_relations (source_id,target_id,relation_type,strength,confidence) "
            "VALUES ('BIO_M1_A','BIO_M1_B','prerequisite_hard',1.0,0.8)"
        )
    conn.commit()
    conn.close()


def test_read_knowledge_db_with_edge_review_status(tmp_path):
    """sync 读取 edge review_status（新 schema）。"""
    db_path = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db(db_path, with_review_status=True)
    l1_nodes, bc_nodes, edges, maps = _read_knowledge_db(db_path)
    assert len(edges) == 1
    assert edges[0]["review_status"] == "teacher_reviewed"


def test_read_knowledge_db_without_edge_review_status(tmp_path):
    """sync 读取旧 schema（无 review_status 列）→ 默认 None。"""
    db_path = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db(db_path, with_review_status=False)
    l1_nodes, bc_nodes, edges, maps = _read_knowledge_db(db_path)
    assert len(edges) == 1
    assert edges[0]["review_status"] is None


@pytest.mark.asyncio
async def test_sync_writes_edge_review_status(db, tmp_path):
    """sync 将 edge review_status 写入 PG（通过 _sync_graph）。"""
    from edu_cloud.modules.knowledge_tree.sync_service import _read_knowledge_db, _sync_graph
    db_path = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db(db_path, with_review_status=True)
    l1_nodes, bc_nodes, edges, maps = _read_knowledge_db(db_path)
    await _sync_graph(db, l1_nodes, bc_nodes, edges, maps)
    await db.commit()
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "BIO_M1_A",
            ConceptGraphEdge.target_id == "BIO_M1_B",
        )
    )).scalar_one()
    assert edge.review_status == "teacher_reviewed"


@pytest.mark.asyncio
async def test_backwrite_edge_review_status(db, seed_graph_v2, tmp_path):
    """backwrite 将 edge review_status 回写到 knowledge.db。"""
    from edu_cloud.modules.knowledge_tree.service import backwrite_to_knowledge_db
    db_path = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db(db_path, with_review_status=True)

    # 拿到一条 PG edge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    # 模拟 backwrite（含 _edge_source/_edge_target/_edge_type 元数据）
    # 先在 knowledge.db 插入对应 edge
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO concept_relations VALUES ('TEST_M1_A','TEST_M1_B','prerequisite_hard',1.0,0.9,'ai_draft')"
    )
    conn.commit()
    conn.close()

    ops = [{
        "op": "set_review_status", "edge_id": edge.id, "status": "teacher_reviewed",
        "_edge_source": "TEST_M1_A", "_edge_target": "TEST_M1_B", "_edge_type": "prerequisite_hard",
    }]
    result = await backwrite_to_knowledge_db(db, db_path, ops)
    assert result["success"]

    # 验证 knowledge.db 已更新
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT review_status FROM concept_relations WHERE source_id='TEST_M1_A' AND target_id='TEST_M1_B'"
    ).fetchone()
    assert row["review_status"] == "teacher_reviewed"
    conn.close()


@pytest.mark.asyncio
async def test_backwrite_edge_no_review_column(db, seed_graph_v2, tmp_path):
    """backwrite 到旧 schema（无 review_status 列）→ 静默跳过不报错。"""
    from edu_cloud.modules.knowledge_tree.service import backwrite_to_knowledge_db
    db_path = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db(db_path, with_review_status=False)

    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    ops = [{
        "op": "set_review_status", "edge_id": edge.id, "status": "teacher_reviewed",
        "_edge_source": "TEST_M1_A", "_edge_target": "TEST_M1_B", "_edge_type": "prerequisite_hard",
    }]
    result = await backwrite_to_knowledge_db(db, db_path, ops)
    assert result["success"]  # 不报错
