"""高考真题查询 + 统计概览 API 测试 — Round 2 加固版

契约（来自 plan Task 8）：
- 概念→DA→q_matrix→assessment_items 链路查询高考真题，支持分页 + 稳定排序
- 未关联概念返回 total=0/items=[]（降级，不 500）
- /stats/overview 返回 total_concepts/total_edges/exam_freq_distribution/module_stats

Round 2 加固（F001/F002/F003）：
- F001：受控临时 SQLite KB 构造已知 DA→item 映射，精确断言 item_id 集合相等
- F002：先 DELETE 现存数据隔离 fixture，精确数值断言（== 而非 >=）
- F003：分页稳定性 — 跨页 item_id 不重叠 + 按 ASC 顺序

反例（错误实现会失败）：
- 占位实现"已知概念返回任意非空" → test_get_exam_items_returns_exact_da_chain 集合不等
- 硬编码 M1/M2 + high/mid/zero 三态 → test_stats_overview_exact_aggregation 数值偏差
- 分页未排序 → test_get_exam_items_pagination_stable 跨页重复或顺序抖动
"""
import os
import sqlite3
import pytest
from pathlib import Path
from datetime import datetime

import sqlalchemy as sa

from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptGraphEdge, ConceptStats,
)

KB_PATH = os.environ.get(
    "KNOWLEDGE_DB_PATH",
    str(Path.home() / "edu-knowledge-base" / "knowledge.db"),
)


# ════════════════════════════════════════════════════════════════
# F001 加固：受控临时 SQLite KB 锁定 DA→item 链路
# ════════════════════════════════════════════════════════════════

@pytest.fixture
def controlled_kb(tmp_path):
    """构造受控 knowledge.db：3 DA + 5 items + 已知 q_matrix 关联。

    数据布局（已知预期）：
    - DA1 关联 concept C1, item_001/002
    - DA2 关联 concept C1+OTHER, item_002/003 (item_002 跨 DA → DISTINCT 应去重)
    - DA3 关联 concept C2, item_004/005
    - C1 链路应返回 {item_001, item_002, item_003} （按 ASC）
    - C2 链路应返回 {item_004, item_005}
    """
    db_path = tmp_path / "controlled.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE diagnostic_attributes (
            id TEXT PRIMARY KEY,
            linked_concept_ids TEXT
        );
        CREATE TABLE q_matrix (
            attribute_id TEXT,
            item_id TEXT
        );
        CREATE TABLE assessment_items (
            id TEXT PRIMARY KEY,
            exam_id TEXT,
            question_number TEXT,
            question_type TEXT,
            stem TEXT,
            answer TEXT,
            score REAL,
            options TEXT,
            explanation TEXT,
            module_tag TEXT
        );
    """)
    conn.executemany("INSERT INTO diagnostic_attributes VALUES (?, ?)", [
        ("DA1", '["C1"]'),
        ("DA2", '["C1", "OTHER"]'),
        ("DA3", '["C2"]'),
    ])
    # 故意倒序插入：让 SQLite 默认 rowid 顺序不等于 item_id ASC
    # 反证强化：若 service 缺 ORDER BY → 默认顺序按 rowid（003→001→002）→ 分页测试 fail
    conn.executemany("INSERT INTO q_matrix VALUES (?, ?)", [
        ("DA2", "item_003"), ("DA2", "item_002"),  # rowid 1, 2
        ("DA1", "item_002"), ("DA1", "item_001"),  # rowid 3, 4 (item_002 重复，DISTINCT 取首现 → rowid=2)
        ("DA3", "item_005"), ("DA3", "item_004"),  # rowid 5, 6
    ])
    conn.executemany(
        "INSERT INTO assessment_items VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("item_001", "EXAM_A", 1, "选择题", "题干 1", "A", 5.0, '["A","B"]', "", "M1"),
            ("item_002", "EXAM_A", 2, "选择题", "题干 2", "B", 5.0, '["A","B"]', "", "M1"),
            ("item_003", "EXAM_A", 3, "填空题", "题干 3", "答案", 5.0, None, "解析", "M1"),
            ("item_004", "EXAM_B", 1, "选择题", "题干 4", "C", 5.0, '["A","B","C"]', "", "M2"),
            ("item_005", "EXAM_B", 2, "解答题", "题干 5", "答案 5", 10.0, None, "解析 5", "M2"),
        ],
    )
    conn.commit()
    conn.close()
    return str(db_path)


def test_get_exam_items_returns_exact_da_chain(controlled_kb):
    """F001 反证：concept C1 通过 DA1+DA2 链路精确返回 {item_001, item_002, item_003}。

    错误实现"已知概念返回任意非空" → 集合不等 → fail
    DISTINCT 失效 → item_002 出现两次 → total != 3 → fail
    """
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    result = get_exam_items(kb_path=controlled_kb, concept_id="C1", page=1, page_size=10)
    item_ids = [it["id"] for it in result["items"]]

    assert set(item_ids) == {"item_001", "item_002", "item_003"}, (
        f"C1 应返回 DA1+DA2 关联的 3 题（去重后），实际 {item_ids}"
    )
    assert result["total"] == 3, "DISTINCT 必须去重 item_002"
    item_001 = next(it for it in result["items"] if it["id"] == "item_001")
    assert item_001["exam_id"] == "EXAM_A"
    assert item_001["question_type"] == "选择题"
    assert item_001["score"] == 5.0


def test_get_exam_items_isolation_between_concepts(controlled_kb):
    """F001 反证：concept C2 必须返回 {item_004, item_005}，与 C1 不重叠。"""
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    result = get_exam_items(kb_path=controlled_kb, concept_id="C2", page=1, page_size=10)
    assert {it["id"] for it in result["items"]} == {"item_004", "item_005"}
    assert result["total"] == 2


def test_get_exam_items_unknown_returns_empty(controlled_kb):
    """F001 反证：未知 concept 精确 total=0 + items=[]。"""
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    result = get_exam_items(kb_path=controlled_kb, concept_id="UNKNOWN_XYZ", page=1, page_size=10)
    assert result == {"total": 0, "items": [], "page": 1, "page_size": 10}


def test_get_exam_items_total_consistent_with_actual_items(tmp_path):
    """N001 反证：q_matrix 引用 assessment_items 不存在 id 时，
    total 必须等于 page 实际可返回的题目总数（不包含 phantom id）。

    构造场景：
    - DA1 关联 concept C1，q_matrix 关联 3 个 item_id (item_001/002/MISSING)
    - assessment_items 仅含 item_001 / item_002（item_MISSING 不存在，模拟数据漂移）
    - 错误实现：total=3，page=2,page_size=2 返回空 → 前端看到 phantom total
    - 正确实现：total=2，page=2,page_size=2 返回空（合理：第 2 页无内容）

    错误实现会 fail：
    - INNER JOIN 缺失 → total 包含 MISSING → total != len(实际可返回 items)
    """
    db_path = tmp_path / "drift.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, linked_concept_ids TEXT);
        CREATE TABLE q_matrix (attribute_id TEXT, item_id TEXT);
        CREATE TABLE assessment_items (
            id TEXT PRIMARY KEY, exam_id TEXT, question_number INTEGER,
            question_type TEXT, stem TEXT, answer TEXT, score REAL,
            options TEXT, explanation TEXT, module_tag TEXT
        );
    """)
    conn.execute("INSERT INTO diagnostic_attributes VALUES ('DA1', '[\"C1\"]')")
    conn.executemany("INSERT INTO q_matrix VALUES (?, ?)", [
        ("DA1", "item_001"), ("DA1", "item_002"), ("DA1", "item_MISSING"),
    ])
    # assessment_items 只有 001/002，故意缺 item_MISSING
    conn.executemany("INSERT INTO assessment_items VALUES (?,?,?,?,?,?,?,?,?,?)", [
        ("item_001", "EXAM_X", 1, "选择题", "题 1", "A", 5.0, None, "", "M1"),
        ("item_002", "EXAM_X", 2, "选择题", "题 2", "B", 5.0, None, "", "M1"),
    ])
    conn.commit()
    conn.close()

    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    # 第 1 页：必须 total == 真实可返回 item 总数 (2)，不是 q_matrix distinct (3)
    p1 = get_exam_items(kb_path=str(db_path), concept_id="C1", page=1, page_size=10)
    assert p1["total"] == 2, f"total 必须排除 q_matrix 引用但 assessment_items 缺失的 id, 实际 total={p1['total']}"
    assert len(p1["items"]) == 2
    assert {it["id"] for it in p1["items"]} == {"item_001", "item_002"}

    # 分页一致性：page=2,page_size=2 应是空但 total 仍为 2（不是 phantom 3）
    p2 = get_exam_items(kb_path=str(db_path), concept_id="C1", page=2, page_size=2)
    assert p2["total"] == 2
    assert p2["items"] == []

    # 第 1 页 page_size=2 应满 2 题
    p1_2 = get_exam_items(kb_path=str(db_path), concept_id="C1", page=1, page_size=2)
    assert p1_2["total"] == 2
    assert len(p1_2["items"]) == 2


def test_get_exam_items_pagination_stable(controlled_kb):
    """F003 反证：跨页 item_id 不重叠 + 按 ASC 稳定 + 重复请求一致。

    DISTINCT 未排序 → 重复同一页可能返回不同 item_id → fail
    IN 查询未保持顺序 → page 内顺序不稳定 → fail
    """
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    page1 = get_exam_items(kb_path=controlled_kb, concept_id="C1", page=1, page_size=2)
    page2 = get_exam_items(kb_path=controlled_kb, concept_id="C1", page=2, page_size=2)

    p1_ids = [it["id"] for it in page1["items"]]
    p2_ids = [it["id"] for it in page2["items"]]
    assert set(p1_ids) & set(p2_ids) == set(), "翻页禁止重复 item"

    # 顺序按 item_id ASC（item_001 < item_002 < item_003）
    assert p1_ids == ["item_001", "item_002"], f"page1 应 [001, 002] ASC, 实际 {p1_ids}"
    assert p2_ids == ["item_003"], f"page2 应只剩 [003], 实际 {p2_ids}"

    page1_again = get_exam_items(kb_path=controlled_kb, concept_id="C1", page=1, page_size=2)
    assert [it["id"] for it in page1_again["items"]] == p1_ids, "重复请求必须确定性"


# ════════════════════════════════════════════════════════════════
# 兼容真实 KB 烟雾测试（保留 batch1 happy-path）
# ════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_get_exam_items_smoke_with_real_kb():
    """烟雾测试：真实 knowledge.db 存在时光合作用至少有真题。"""
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    result = get_exam_items(
        kb_path=KB_PATH, concept_id="BIO_SR_CP_M1_PHOTOSYNTHESIS",
        page=1, page_size=10,
    )
    assert result["total"] > 0
    for item in result["items"]:
        assert item.get("id")
        assert item.get("question_type")


# ════════════════════════════════════════════════════════════════
# HTTP 端点级测试（入口级验证）
# ════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_get_exam_items_endpoint_unknown_concept(client, admin_headers):
    """HTTP 端点：未知 concept → 200 total=0 空列表（降级契约，不 500）。"""
    resp = await client.get(
        "/api/v1/knowledge-tree/graph/NONEXISTENT_CONCEPT_XYZ/exam-items",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1
    assert data["page_size"] == 20


@pytest.mark.asyncio
async def test_get_exam_items_endpoint_with_controlled_kb(
    client, admin_headers, controlled_kb, monkeypatch
):
    """HTTP 端点：注入受控 KB → 精确返回链路 item_id，验证 ExamItemsResponse 契约。"""
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", controlled_kb)
    resp = await client.get(
        "/api/v1/knowledge-tree/graph/C1/exam-items?page=1&page_size=10",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert {it["id"] for it in data["items"]} == {"item_001", "item_002", "item_003"}
    assert data["total"] == 3
    assert "page" in data and "page_size" in data
    for it in data["items"]:
        assert "id" in it and "question_type" in it and "stem" in it


# ════════════════════════════════════════════════════════════════
# F002 加固：受控隔离 + 精确数值断言
# ════════════════════════════════════════════════════════════════

async def _purge_concept_data(db):
    """清除现有 ConceptGraphNode/Edge/Stats，让本测试断言精确数值。"""
    await db.execute(sa.delete(ConceptStats))
    await db.execute(sa.delete(ConceptGraphEdge))
    await db.execute(sa.delete(ConceptGraphNode))
    await db.commit()


@pytest.mark.asyncio
async def test_stats_overview_exact_aggregation(client, admin_headers, db):
    """F002 反证：精确数值断言所有聚合指标。

    构造数据：
    - M1: 3 概念 freq=[600, 100, 0] → high=1, mid=1, zero=1 / avg=233.3 / coverage=0.667
    - M2: 1 概念 freq=10 → low=1 / avg=10.0 / coverage=1.0
    - M1 内 1 条边

    错误实现：
    - 分桶阈值改错（high>=400）→ distribution 偏差 → fail
    - avg_freq 算成总和 → 233.3 不等 → fail
    - exam_coverage 分母错 → 0.667 不等 → fail
    """
    await _purge_concept_data(db)
    now = datetime.now()

    db.add_all([
        ConceptGraphNode(id="ST_M1_HIGH", name="高频", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now),
        ConceptGraphNode(id="ST_M1_MID", name="中频", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now),
        ConceptGraphNode(id="ST_M1_ZERO", name="零频", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now),
        ConceptGraphNode(id="ST_M2_LOW", name="低频", knowledge_level="L1",
                         primary_module="M2", node_type="concept", synced_at=now),
        ConceptStats(concept_id="ST_M1_HIGH", exam_frequency=600, exam_coverage=0.5,
                     importance_score=9.0, textbook_chapters=[], computed_at=now),
        ConceptStats(concept_id="ST_M1_MID", exam_frequency=100, exam_coverage=0.2,
                     importance_score=5.0, textbook_chapters=[], computed_at=now),
        # ST_M1_ZERO 无 stats → service 按 freq=0 处理
        ConceptStats(concept_id="ST_M2_LOW", exam_frequency=10, exam_coverage=0.05,
                     importance_score=2.0, textbook_chapters=[], computed_at=now),
        ConceptGraphEdge(source_id="ST_M1_HIGH", target_id="ST_M1_MID",
                        relation_type="prereq", strength=1.0, confidence=1.0,
                        synced_at=now),
    ])
    await db.commit()

    resp = await client.get("/api/v1/knowledge-tree/stats/overview", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # 精确断言（错误实现无法绿通）
    assert data["total_concepts"] == 4
    assert data["total_edges"] == 1
    assert data["exam_freq_distribution"] == {"high": 1, "mid": 1, "low": 1, "zero": 1}

    ms = data["module_stats"]
    assert set(ms.keys()) == {"M1", "M2"}

    m1 = ms["M1"]
    assert m1["concepts"] == 3
    assert m1["edges"] == 1
    assert m1["avg_freq"] == round((600 + 100 + 0) / 3, 1)  # 233.3
    assert m1["exam_coverage"] == round(2 / 3, 3)  # 0.667

    m2 = ms["M2"]
    assert m2["concepts"] == 1
    assert m2["edges"] == 0
    assert m2["avg_freq"] == 10.0
    assert m2["exam_coverage"] == 1.0


@pytest.mark.asyncio
async def test_stats_overview_module_filter_isolation(client, admin_headers, db):
    """F002 反证：module=M1 时 M2 数据被严格排除（不污染 M1 avg_freq）。

    错误实现 filter 错把 M2 计入 M1 → avg_freq 被稀释 → fail
    """
    await _purge_concept_data(db)
    now = datetime.now()

    db.add_all([
        ConceptGraphNode(id="MF_M1_A", name="M1 A", knowledge_level="L1",
                         primary_module="M1", node_type="concept", synced_at=now),
        ConceptGraphNode(id="MF_M2_B", name="M2 B", knowledge_level="L1",
                         primary_module="M2", node_type="concept", synced_at=now),
        ConceptStats(concept_id="MF_M1_A", exam_frequency=200, exam_coverage=0.3,
                     importance_score=6.0, textbook_chapters=[], computed_at=now),
        ConceptStats(concept_id="MF_M2_B", exam_frequency=10, exam_coverage=0.05,
                     importance_score=1.0, textbook_chapters=[], computed_at=now),
    ])
    await db.commit()

    resp = await client.get(
        "/api/v1/knowledge-tree/stats/overview?module=M1",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert "M1" in data["module_stats"]
    assert "M2" not in data["module_stats"]
    assert data["module_stats"]["M1"]["avg_freq"] == 200.0
    assert data["module_stats"]["M1"]["exam_coverage"] == 1.0
    assert data["total_concepts"] == 1
