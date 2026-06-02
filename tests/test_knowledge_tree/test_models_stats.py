"""ConceptStats 模型测试"""
import pytest
from datetime import datetime
import sqlalchemy as sa
from edu_cloud.modules.knowledge_tree.models import (
    ConceptStats, ConceptGraphNode,
)


@pytest.mark.asyncio
async def test_concept_stats_instantiation(db):
    """ConceptStats 可以实例化且所有设计字段存在"""
    node = ConceptGraphNode(
        id="TEST_CONCEPT_001",
        name="测试概念",
        knowledge_level="L1",
        primary_module="M1",
        synced_at=datetime.now(),
    )
    db.add(node)
    await db.commit()

    stats = ConceptStats(
        concept_id="TEST_CONCEPT_001",
        exam_frequency=100,
        exam_coverage=0.8,
        avg_difficulty=3.5,
        importance_score=7.2,
        planning_weight={"exam_freq": 8, "priority_score": 7.5},
        textbook_chapters=[{"book": "b1", "chapter": "ch01", "section": "s01"}],
        study_unit_id="su:bio_sr:test_001",
        estimated_minutes=70,
        prerequisite_depth=2,
        computed_at=datetime.now(),
    )
    db.add(stats)
    await db.commit()

    result = await db.execute(
        sa.select(ConceptStats).where(ConceptStats.concept_id == "TEST_CONCEPT_001")
    )
    loaded = result.scalar_one()
    assert loaded.exam_frequency == 100
    assert loaded.importance_score == 7.2
    assert loaded.planning_weight["priority_score"] == 7.5
    assert loaded.textbook_chapters[0]["book"] == "b1"


@pytest.mark.asyncio
async def test_concept_stats_restrict_on_node_delete(db):
    """FK ON DELETE RESTRICT: 有 stats 时直接删节点应被拒绝，需先删 stats"""
    node = ConceptGraphNode(
        id="TEST_RESTRICT_001", name="RESTRICT 测试", knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(),
    )
    db.add(node)
    await db.commit()

    stats = ConceptStats(
        concept_id="TEST_RESTRICT_001",
        exam_frequency=50,
        computed_at=datetime.now(),
    )
    db.add(stats)
    await db.commit()

    try:
        await db.execute(sa.text("PRAGMA foreign_keys = ON"))
    except Exception:
        pass

    # 先删 stats，再删节点（RESTRICT 要求显式删除依赖行）
    await db.execute(
        sa.delete(ConceptStats).where(ConceptStats.concept_id == "TEST_RESTRICT_001")
    )
    await db.execute(
        sa.delete(ConceptGraphNode).where(ConceptGraphNode.id == "TEST_RESTRICT_001")
    )
    await db.commit()
    db.expire_all()

    result = await db.execute(
        sa.select(ConceptStats).where(ConceptStats.concept_id == "TEST_RESTRICT_001")
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_concept_stats_restrict_blocks_direct_node_delete(db):
    """FK ON DELETE RESTRICT: 有 stats 时直接删节点应失败（IntegrityError）"""
    node = ConceptGraphNode(
        id="TEST_RESTRICT_002", name="RESTRICT 拒绝测试", knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(),
    )
    db.add(node)
    await db.commit()

    stats = ConceptStats(
        concept_id="TEST_RESTRICT_002",
        exam_frequency=50,
        computed_at=datetime.now(),
    )
    db.add(stats)
    await db.commit()

    try:
        await db.execute(sa.text("PRAGMA foreign_keys = ON"))
    except Exception:
        pass

    with pytest.raises(Exception, match="FOREIGN KEY constraint failed"):
        await db.execute(
            sa.delete(ConceptGraphNode).where(ConceptGraphNode.id == "TEST_RESTRICT_002")
        )
    await db.rollback()


@pytest.mark.asyncio
async def test_concept_stats_defaults(db):
    """未设置字段应有合理默认值"""
    node = ConceptGraphNode(
        id="TEST_DEFAULT_001", name="默认值测试", knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(),
    )
    db.add(node)
    await db.commit()

    stats = ConceptStats(
        concept_id="TEST_DEFAULT_001",
        computed_at=datetime.now(),
    )
    db.add(stats)
    await db.commit()

    result = await db.execute(
        sa.select(ConceptStats).where(ConceptStats.concept_id == "TEST_DEFAULT_001")
    )
    loaded = result.scalar_one()
    assert loaded.exam_frequency == 0
    assert loaded.exam_coverage == 0.0
    assert loaded.importance_score == 0.0
    assert loaded.textbook_chapters == []
    assert loaded.prerequisite_depth == 0


def test_migration_symmetric():
    """迁移 upgrade/downgrade 对称：直接调用新迁移文件的 upgrade/downgrade。

    不走 alembic head（受上游 b08103b3a6f5 SQLite 兼容性影响），
    只验证本次新增迁移 46b200fa9704 自身对称。
    """
    from sqlalchemy import create_engine, inspect, MetaData, Column, String, DateTime
    from sqlalchemy import Table
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    import importlib.util, tempfile, os

    tmpdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmpdb.close()
    try:
        url = f"sqlite:///{tmpdb.name}"
        engine = create_engine(url)

        # 先建 FK 依赖的 concept_graph_nodes 骨架
        meta = MetaData()
        Table(
            "concept_graph_nodes", meta,
            Column("id", String(64), primary_key=True),
            Column("name", String(200), nullable=False),
            Column("knowledge_level", String(10), nullable=False),
            Column("primary_module", String(10), nullable=False),
            Column("synced_at", DateTime, nullable=False),
        )
        meta.create_all(engine)

        spec = importlib.util.spec_from_file_location(
            "mig_concept_stats",
            os.path.join(
                os.path.dirname(__file__), "..", "..",
                "alembic", "versions", "46b200fa9704_add_concept_stats_table.py"
            ),
        )
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            op_proxy = Operations(ctx)
            import alembic.operations.base as _opsbase
            _opsbase.Operations._proxy = op_proxy
            mig.op = op_proxy
            mig.upgrade()
            conn.commit()

        insp = inspect(engine)
        assert "concept_stats" in insp.get_table_names()

        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            op_proxy = Operations(ctx)
            mig.op = op_proxy
            mig.downgrade()
            conn.commit()

        insp = inspect(engine)
        assert "concept_stats" not in insp.get_table_names()
        engine.dispose()
    finally:
        os.unlink(tmpdb.name)
