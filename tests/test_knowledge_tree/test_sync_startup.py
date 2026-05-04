"""启动同步测试（临时 SQLite fixture，不依赖本机 knowledge.db）。"""
import sqlite3
import pytest
from sqlalchemy import select, func
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap
from edu_cloud.modules.adaptive.models import DaCatalogSnapshot, DaKnowledgePointMap


def _create_test_knowledge_db(path: str, *, with_hierarchy: bool = False):
    conn = sqlite3.connect(path)
    if with_hierarchy:
        conn.execute("""CREATE TABLE concepts (
            id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT,
            difficulty INTEGER, bloom_level TEXT, aliases_json TEXT, evidence_ids_json TEXT, review_status TEXT
        )""")
    else:
        conn.execute("CREATE TABLE concepts (id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT)")
    conn.execute("CREATE TABLE concept_relations (source_id TEXT, target_id TEXT, relation_type TEXT, strength REAL, confidence REAL)")
    conn.execute("CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, name TEXT, linked_concept_ids TEXT, observable_behaviors TEXT, common_cause_families TEXT, required_evidence_modes TEXT, common_errors TEXT, description TEXT)")
    conn.execute("CREATE TABLE study_units (id TEXT PRIMARY KEY, linked_da_ids TEXT)")

    if with_hierarchy:
        conn.execute("INSERT INTO concepts VALUES ('BIO_SR_CP_M1_A','TestA','L1','d', 4, 'apply', '[\"别名A\"]', '[\"EV1\"]', 'ai_draft')")
        conn.execute("INSERT INTO concepts VALUES ('BIO_SR_CP_M1_B','TestB','L1','d', 2, 'remember', NULL, NULL, 'teacher_reviewed')")
        conn.execute("INSERT INTO concepts VALUES ('BIO_SR_B1_BK_001','Evidence1','evidence','e', NULL, NULL, NULL, NULL, NULL)")
        # big_concepts
        conn.execute("CREATE TABLE big_concepts (id TEXT PRIMARY KEY, name TEXT, module TEXT, display_order INTEGER)")
        conn.execute("INSERT INTO big_concepts VALUES ('BC_BIO_M1_C1', '细胞学说', 'M1', 0)")
        # map
        conn.execute("CREATE TABLE concept_big_concept_map (concept_id TEXT, big_concept_id TEXT, is_primary INTEGER, PRIMARY KEY(concept_id, big_concept_id))")
        conn.execute("INSERT INTO concept_big_concept_map VALUES ('BIO_SR_CP_M1_A', 'BC_BIO_M1_C1', 1)")
        conn.execute("INSERT INTO concept_big_concept_map VALUES ('BIO_SR_CP_M1_B', 'BC_BIO_M1_C1', 1)")
    else:
        conn.execute("INSERT INTO concepts VALUES ('BIO_SR_CP_M1_A','TestA','L1','d')")
        conn.execute("INSERT INTO concepts VALUES ('BIO_SR_CP_M1_B','TestB','L1','d')")

    conn.execute("INSERT INTO concept_relations VALUES ('BIO_SR_CP_M1_A','BIO_SR_CP_M1_B','prerequisite_hard',1.0,1.0)")
    conn.execute("""INSERT INTO diagnostic_attributes VALUES ('da:bio_sr:m1_001','DA1','["BIO_SR_CP_M1_A"]','["can id"]','["gap"]','["recall"]','[]','d')""")
    conn.execute("""INSERT INTO study_units VALUES ('su:m1_001','["da:bio_sr:m1_001"]')""")
    conn.commit()
    conn.close()


@pytest.fixture
def knowledge_db_path(tmp_path):
    p = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db(p)
    return p


@pytest.fixture
def knowledge_db_with_hierarchy(tmp_path):
    p = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db(p, with_hierarchy=True)
    return p


@pytest.mark.asyncio
async def test_sync_all_tables(db, knowledge_db_path):
    """F005: 单事务同步后 4 张表都有数据（确定性 fixture，无 skip）。
    3-layer tree: 1 module + 2 concepts = 3 nodes; 2 orphan contains + 1 concept-relation = 3 edges.
    """
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    r = await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_path)
    assert r["status"] == "synced"
    assert r["nodes"] == 3  # 1 module(M1) + 2 L1 concepts
    assert r["edges"] == 3  # 2 contains(module→orphan) + 1 concept-relation
    assert (await db.execute(select(func.count()).select_from(ConceptGraphNode))).scalar() == 3
    assert (await db.execute(select(func.count()).select_from(ConceptGraphEdge))).scalar() == 3
    assert (await db.execute(select(func.count()).select_from(DaCatalogSnapshot))).scalar() == 1
    assert (await db.execute(select(func.count()).select_from(DaKnowledgePointMap))).scalar() == 1


@pytest.mark.asyncio
async def test_sync_idempotent(db, knowledge_db_path):
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_path)
    r2 = await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_path)
    assert r2["status"] == "skipped"


@pytest.mark.asyncio
async def test_sync_missing_db(db):
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    assert (await sync_knowledge_on_startup(db, knowledge_db_path="/nonexistent.db"))["status"] == "not_found"


@pytest.mark.asyncio
async def test_sync_partial_init_resyncs(db, knowledge_db_path):
    """Gate 2 R2: 图谱已存在但 DA 为空时应重新同步（部分初始化场景）。"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    # 先正常同步
    r1 = await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_path)
    assert r1["status"] == "synced"

    # 手动清空 DA 表模拟部分初始化
    from sqlalchemy import delete
    await db.execute(delete(DaCatalogSnapshot))
    await db.execute(delete(DaKnowledgePointMap))
    await db.commit()

    # 再次同步应重新执行（不是 skipped）
    r2 = await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_path)
    assert r2["status"] == "synced", f"Expected re-sync when DA tables empty, got {r2['status']}"
    assert (await db.execute(select(func.count()).select_from(DaCatalogSnapshot))).scalar() > 0


@pytest.mark.asyncio
async def test_sync_commit_persists(db_engine, knowledge_db_path):
    """F002: 验证 commit 真正持久化——用独立 session 读取。"""
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    make_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    # 第一个 session: 执行同步
    async with make_session() as s1:
        from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
        r = await sync_knowledge_on_startup(s1, knowledge_db_path=knowledge_db_path)
        assert r["status"] == "synced"

    # 第二个独立 session: 验证数据真正持久化（不是 flush 幻觉）
    async with make_session() as s2:
        count = (await s2.execute(select(func.count()).select_from(ConceptGraphNode))).scalar()
        assert count == 3, f"Expected 3 nodes (1 module + 2 concepts) persisted across sessions, got {count}"


# --- 层级重构同步测试 ---

@pytest.mark.asyncio
async def test_sync_l1_only(db, knowledge_db_with_hierarchy):
    """同步后有 Module + L1 概念 + BigConcept 节点，无 evidence。"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    r = await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_with_hierarchy)
    assert r["status"] == "synced"

    # 节点：1 module(M1) + 2 L1 + 1 BigConcept = 4（evidence 不同步）
    total = (await db.execute(select(func.count()).select_from(ConceptGraphNode))).scalar()
    assert total == 4

    # 验证 node_type
    modules = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.node_type == "module")
    )).scalars().all()
    assert len(modules) == 1
    assert modules[0].id == "mod:bio_sr:M1"

    concepts = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    )).scalars().all()
    assert len(concepts) == 2

    bcs = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.node_type == "big_concept")
    )).scalars().all()
    assert len(bcs) == 1
    assert bcs[0].id == "BC_BIO_M1_C1"


@pytest.mark.asyncio
async def test_sync_map(db, knowledge_db_with_hierarchy):
    """concept_big_concept_map 同步到 PG。"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_with_hierarchy)

    map_count = (await db.execute(select(func.count()).select_from(ConceptBigConceptMap))).scalar()
    assert map_count == 2

    maps = (await db.execute(select(ConceptBigConceptMap))).scalars().all()
    assert all(m.big_concept_id == "BC_BIO_M1_C1" for m in maps)
    assert all(m.is_primary for m in maps)


@pytest.mark.asyncio
async def test_sync_difficulty_bloom(db, knowledge_db_with_hierarchy):
    """difficulty/bloom_level 同步到 PG。"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_with_hierarchy)

    a = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.id == "BIO_SR_CP_M1_A")
    )).scalar_one()
    assert a.difficulty == 4
    assert a.bloom_level == "apply"
    assert a.aliases_json == '["别名A"]'
    assert a.review_status == "ai_draft"

    b = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.id == "BIO_SR_CP_M1_B")
    )).scalar_one()
    assert b.difficulty == 2
    assert b.bloom_level == "remember"
    assert b.aliases_json is None
    assert b.review_status == "teacher_reviewed"


@pytest.mark.asyncio
async def test_da_map_unchanged_after_sync(db, knowledge_db_with_hierarchy):
    """INV-002: da_knowledge_point_map 在层级重构同步前后行数和内容完全一致。

    R3-F002/Batch2-F002: 原 INV-002 verification 只测 mastery 排除 BigConcept，
    不够精确。本测试直接断言 da_knowledge_point_map 的 count + 全量内容不变。
    """
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup

    # 第一次同步（建立基线）
    await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_with_hierarchy)

    # 快照 da_knowledge_point_map
    rows_before = (await db.execute(select(DaKnowledgePointMap))).scalars().all()
    snapshot = {(r.da_id, r.knowledge_point_id): r.weight for r in rows_before}
    count_before = len(rows_before)
    assert count_before > 0, "da_knowledge_point_map should have data after sync"

    # 强制重新同步（模拟层级重构后的再次同步）
    from sqlalchemy import delete
    await db.execute(delete(ConceptGraphNode))
    await db.commit()
    await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_with_hierarchy)

    # 验证 da_knowledge_point_map 行数不变
    count_after = (await db.execute(select(func.count()).select_from(DaKnowledgePointMap))).scalar()
    assert count_after == count_before, f"da_knowledge_point_map count changed: {count_before} → {count_after}"

    # 验证内容不变
    rows_after = (await db.execute(select(DaKnowledgePointMap))).scalars().all()
    snapshot_after = {(r.da_id, r.knowledge_point_id): r.weight for r in rows_after}
    assert snapshot_after == snapshot, "da_knowledge_point_map content changed after re-sync"


@pytest.mark.asyncio
async def test_sync_old_db_no_hierarchy(db, knowledge_db_path):
    """旧版 knowledge.db（无 big_concepts 表）不崩溃，正常同步 L1 + module。"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    r = await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_path)
    assert r["status"] == "synced"

    # 1 module(M1) + 2 L1 nodes, 0 BigConcepts, 0 maps
    total = (await db.execute(select(func.count()).select_from(ConceptGraphNode))).scalar()
    assert total == 3

    map_count = (await db.execute(select(func.count()).select_from(ConceptBigConceptMap))).scalar()
    assert map_count == 0


# --- Phase 1: sync 后触发 stats 计算 ---

import os
from pathlib import Path

_REAL_KB_PATH = os.environ.get(
    "KNOWLEDGE_DB_PATH",
    str(Path.home() / "edu-knowledge-base" / "knowledge.db"),
)


@pytest.mark.skipif(not Path(_REAL_KB_PATH).exists(), reason="knowledge.db not available")
@pytest.mark.asyncio
async def test_sync_triggers_stats_computation(db):
    """sync_knowledge_on_startup 完成后 concept_stats 应有数据"""
    from edu_cloud.modules.knowledge_tree.models import ConceptStats
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup

    await sync_knowledge_on_startup(db, _REAL_KB_PATH)

    count = await db.execute(select(func.count()).select_from(ConceptStats))
    assert count.scalar() >= 100, "sync 后应触发 stats 计算"


@pytest.mark.asyncio
async def test_sync_stats_failure_does_not_break_sync(db, knowledge_db_path, monkeypatch):
    """stats 计算失败时不应阻止 sync 完成（INV-003）"""
    from edu_cloud.modules.knowledge_tree import stats_service
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup

    async def failing_compute(*args, **kwargs):
        raise RuntimeError("simulated stats failure")

    monkeypatch.setattr(stats_service, "compute_all_stats", failing_compute)

    # sync 完整跑完（status=synced），stats 失败被 best-effort 吞掉
    result = await sync_knowledge_on_startup(db, knowledge_db_path)
    assert result["status"] == "synced"
    # sync 本身持久化的数据应保留（1 module + 2 concepts = 3）
    assert (await db.execute(select(func.count()).select_from(ConceptGraphNode))).scalar() == 3


@pytest.mark.asyncio
async def test_sync_skipped_branch_computes_stats_when_empty(db, knowledge_db_path, monkeypatch):
    """F001 Round 2: skipped 分支必须在 concept_stats 空时触发补算（生产升级路径 + 失败自愈）。

    反例：如果 skipped 分支不检测 stats 表，mutant 实现（return 后什么也不做）此测试应失败。
    """
    from edu_cloud.modules.knowledge_tree import stats_service
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup

    # 1) 第一次 sync 触发真实流程，但 compute_all_stats 不跑（避免真 kb 依赖）
    call_log: list[str] = []

    async def fake_compute(db_arg, kb_arg):
        call_log.append(f"call#{len(call_log)+1}:{kb_arg}")
        return 0  # 模拟 kb 表不全 / 真实计算被替换

    monkeypatch.setattr(stats_service, "compute_all_stats", fake_compute)

    r1 = await sync_knowledge_on_startup(db, knowledge_db_path)
    assert r1["status"] == "synced", f"first run should sync, got {r1['status']}"
    assert len(call_log) == 1, f"synced 分支应调用 compute_all_stats 1 次，got {len(call_log)}"

    # 2) 再次 sync：projections 已满 → skipped 分支
    r2 = await sync_knowledge_on_startup(db, knowledge_db_path)
    assert r2["status"] == "skipped", f"second run should skip, got {r2['status']}"
    # 关键断言：skipped 分支检测到 ConceptStats 为空（fake_compute 没真写入）→ 必须再次调用
    assert len(call_log) == 2, (
        f"F001: skipped 分支在 stats 为空时未触发补算，call_log={call_log}"
    )


# --- P0-R1: 三层树 + edge evidence 测试 ---

def _create_test_knowledge_db_v2(path: str):
    """新 schema fixture：含 study_units 完整列 + edge evidence。"""
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE concepts (
        id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT, description TEXT,
        difficulty INTEGER, bloom_level TEXT, aliases_json TEXT, evidence_ids_json TEXT, review_status TEXT
    )""")
    # M1: 2 concepts, M2: 1 concept
    conn.execute("INSERT INTO concepts VALUES ('BIO_SR_CP_M1_A','光合作用','L1','光合描述',4,'apply',NULL,NULL,'ai_draft')")
    conn.execute("INSERT INTO concepts VALUES ('BIO_SR_CP_M1_B','细胞分裂','L1','分裂描述',3,'understand',NULL,NULL,'ai_draft')")
    conn.execute("INSERT INTO concepts VALUES ('BIO_SR_CP_M2_C','基因突变','L1','突变描述',5,'analyze',NULL,NULL,'ai_draft')")

    conn.execute("""CREATE TABLE concept_relations (
        source_id TEXT, target_id TEXT, relation_type TEXT, strength REAL, confidence REAL,
        evidence TEXT, pedagogical_use TEXT
    )""")
    conn.execute("INSERT INTO concept_relations VALUES ('BIO_SR_CP_M1_A','BIO_SR_CP_M1_B','prerequisite_hard',1.0,0.9,'教材第三章实验证据','diagnosis')")
    conn.execute("INSERT INTO concept_relations VALUES ('BIO_SR_CP_M1_B','BIO_SR_CP_M2_C','related',0.8,0.7,NULL,NULL)")

    conn.execute("""CREATE TABLE study_units (
        id TEXT PRIMARY KEY, name TEXT, description TEXT, source_concept_ids TEXT,
        module TEXT, estimated_minutes INTEGER, linked_da_ids TEXT
    )""")
    conn.execute("""INSERT INTO study_units VALUES ('su:bio_sr:m1_001','光合作用单元','单元描述','["BIO_SR_CP_M1_A"]','M1',45,'["da:bio_sr:m1_001"]')""")
    conn.execute("""INSERT INTO study_units VALUES ('su:bio_sr:m1_002','细胞分裂单元','单元描述','["BIO_SR_CP_M1_B"]','M1',30,NULL)""")
    conn.execute("""INSERT INTO study_units VALUES ('su:bio_sr:m2_001','基因突变单元','单元描述','["BIO_SR_CP_M2_C"]','M2',60,NULL)""")

    conn.execute("CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, name TEXT, linked_concept_ids TEXT, observable_behaviors TEXT, common_cause_families TEXT, required_evidence_modes TEXT, common_errors TEXT, description TEXT)")
    conn.execute("""INSERT INTO diagnostic_attributes VALUES ('da:bio_sr:m1_001','DA1','["BIO_SR_CP_M1_A"]','["obs"]','["gap"]','["recall"]','[]','d')""")

    # 不创建 big_concepts / map 表（测试三层树不需要 BC）
    conn.commit()
    conn.close()


@pytest.fixture
def knowledge_db_v2(tmp_path):
    p = str(tmp_path / "knowledge.db")
    _create_test_knowledge_db_v2(p)
    return p


@pytest.mark.asyncio
async def test_sync_three_layer_tree(db, knowledge_db_v2):
    """R1: 验证 module → study_unit → concept 三层投影精确。"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    r = await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_v2)
    assert r["status"] == "synced"

    # 节点：2 modules (M1,M2) + 3 study_units + 3 concepts = 8
    assert r["nodes"] == 8

    modules = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.node_type == "module")
    )).scalars().all()
    assert len(modules) == 2
    mod_ids = {m.id for m in modules}
    assert mod_ids == {"mod:bio_sr:M1", "mod:bio_sr:M2"}

    sus = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.node_type == "study_unit")
    )).scalars().all()
    assert len(sus) == 3
    su_ids = {s.id for s in sus}
    assert su_ids == {"su:bio_sr:m1_001", "su:bio_sr:m1_002", "su:bio_sr:m2_001"}

    concepts = (await db.execute(
        select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    )).scalars().all()
    assert len(concepts) == 3

    # contains edges: 2 mod→su(M1) + 1 mod→su(M2) + 3 su→concept = 6
    contains_edges = (await db.execute(
        select(ConceptGraphEdge).where(ConceptGraphEdge.relation_type == "contains")
    )).scalars().all()
    assert len(contains_edges) == 6

    # 验证 mod→su 边
    mod_su_edges = [(e.source_id, e.target_id) for e in contains_edges if e.target_id.startswith("su:")]
    assert set(mod_su_edges) == {
        ("mod:bio_sr:M1", "su:bio_sr:m1_001"),
        ("mod:bio_sr:M1", "su:bio_sr:m1_002"),
        ("mod:bio_sr:M2", "su:bio_sr:m2_001"),
    }

    # 验证 su→concept 边
    su_concept_edges = [(e.source_id, e.target_id) for e in contains_edges if e.target_id.startswith("BIO_")]
    assert set(su_concept_edges) == {
        ("su:bio_sr:m1_001", "BIO_SR_CP_M1_A"),
        ("su:bio_sr:m1_002", "BIO_SR_CP_M1_B"),
        ("su:bio_sr:m2_001", "BIO_SR_CP_M2_C"),
    }

    # concept-relation 边: 2 条
    rel_edges = (await db.execute(
        select(ConceptGraphEdge).where(ConceptGraphEdge.relation_type != "contains")
    )).scalars().all()
    assert len(rel_edges) == 2


@pytest.mark.asyncio
async def test_sync_edge_evidence_projection(db, knowledge_db_v2):
    """R1 补充: 验证 knowledge.db concept_relations 的 evidence 和 pedagogical_use 投影到 ConceptGraphEdge。"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    await sync_knowledge_on_startup(db, knowledge_db_path=knowledge_db_v2)

    # 有 evidence 的边
    edge_with_ev = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "BIO_SR_CP_M1_A",
            ConceptGraphEdge.target_id == "BIO_SR_CP_M1_B",
            ConceptGraphEdge.relation_type == "prerequisite_hard",
        )
    )).scalar_one()
    assert edge_with_ev.evidence == "教材第三章实验证据"
    assert edge_with_ev.pedagogical_use == "diagnosis"

    # 无 evidence 的边
    edge_no_ev = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "BIO_SR_CP_M1_B",
            ConceptGraphEdge.target_id == "BIO_SR_CP_M2_C",
            ConceptGraphEdge.relation_type == "related",
        )
    )).scalar_one()
    assert edge_no_ev.evidence is None
    assert edge_no_ev.pedagogical_use is None
