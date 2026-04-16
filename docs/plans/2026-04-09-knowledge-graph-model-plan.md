# 知识图谱多层教学模型 Phase 1「可信骨架」实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把知识图谱从 AI 草稿升级为教师可审核的可信结构——增强 API 响应、支持关系级审核、添加质量巡检、实现发布过滤。

**Architecture:** 后端在现有 knowledge_tree 模块上增量修改：1 个 migration（edge review_status）+ service 层增强 + 1 个新 quality_service。前端在 KnowledgeTreePage 新增 tab 切换到审查工作台（4 个新组件）。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (async) + Alembic / Vue 3 + Naive UI + Vitest

**设计文档:** `docs/plans/2026-04-09-knowledge-graph-model-design.md`

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `alembic/versions/f1a2b3c4d5e6_add_edge_review_status.py` | Migration: edge 表加 review_status 列 |
| `src/edu_cloud/modules/knowledge_tree/quality_service.py` | 质量巡检 6 条规则 + BFS 连通分量 |
| `tests/test_knowledge_tree/test_graph_v2.py` | Graph API v2 响应增强测试 |
| `tests/test_knowledge_tree/test_edge_review.py` | Edge 审核状态机测试 |
| `tests/test_knowledge_tree/test_publish_filter.py` | 发布过滤测试 |
| `tests/test_knowledge_tree/test_quality_check.py` | 质量巡检测试 |
| `frontend/src/components/knowledge-tree/RelationReviewPanel.vue` | 审查工作台主面板 |
| `frontend/src/components/knowledge-tree/ConceptReviewList.vue` | 概念列表（筛选+排序） |
| `frontend/src/components/knowledge-tree/RelationDetailCard.vue` | 单概念关系详情+操作 |
| `frontend/src/components/knowledge-tree/QualityBadge.vue` | 质量问题徽标 |
| `tests/test_knowledge_tree/conftest.py` | seed fixtures（seed_graph_v2 等） |
| `frontend/src/__tests__/knowledge-tree/RelationReviewPanel.test.js` | 审查工作台 Vitest 测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `src/edu_cloud/modules/knowledge_tree/models.py:47-64` | ConceptGraphEdge 加 review_status 列 |
| `src/edu_cloud/modules/knowledge_tree/schemas.py:6-23` | GraphNodeResponse/GraphEdgeResponse 加新字段 |
| `src/edu_cloud/modules/knowledge_tree/service.py:32-129,233-244,299-308` | get_graph 增强 + edit 扩展 + 发布过滤 |
| `src/edu_cloud/modules/knowledge_tree/router.py:20-27` | include_draft 参数 + quality-check 端点 |
| `src/edu_cloud/modules/knowledge_tree/sync_service.py:95-106` | edge review_status 读取 |
| `src/edu_cloud/config.py:69` | KNOWLEDGE_DRAFT_VISIBLE 配置 |
| `frontend/src/api/knowledgeTree.js` | qualityCheck() + include_draft 参数 |
| `frontend/src/components/knowledge-tree/useKnowledgeTree.js` | 消费新字段 + qualityIssues |
| `frontend/src/pages/KnowledgeTreePage.vue` | tab 切换（图谱/审查） |

---

## Batch 1: 后端（Tasks 1-6）

### Task 1: Migration + Model + Config

**Files:**
- Create: `alembic/versions/f1a2b3c4d5e6_add_edge_review_status.py`
- Modify: `src/edu_cloud/modules/knowledge_tree/models.py:47-64`
- Modify: `src/edu_cloud/config.py:69`

- [ ] **Step 1: 添加 edge review_status 列到 model**

```python
# models.py ConceptGraphEdge 类，在 confidence 列后新增:
    review_status: Mapped[str] = mapped_column(String(20), default="ai_draft")
```

- [ ] **Step 2: 添加 KNOWLEDGE_DRAFT_VISIBLE 配置**

```python
# config.py，在 KNOWLEDGE_DB_PATH 后新增:
    KNOWLEDGE_DRAFT_VISIBLE: bool = True  # 宽限期：True=draft 对所有角色可见
```

- [ ] **Step 3: 生成 migration**

Run: `cd C:/Users/Administrator/edu-cloud && python -m alembic revision --autogenerate -m "add_edge_review_status"`
Expected: 新文件生成，包含 `op.add_column('concept_graph_edges', sa.Column('review_status', sa.String(20), server_default='ai_draft'))`

- [ ] **Step 4: 检查 migration 内容并补充 downgrade**

确认 upgrade 包含 `add_column`，downgrade 包含 `drop_column`。

- [ ] **Step 5: 运行测试确认 migration 不破坏现有功能**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/ -q --tb=short`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/*_add_edge_review_status.py src/edu_cloud/modules/knowledge_tree/models.py src/edu_cloud/config.py
git commit -m "feat(knowledge-tree): add edge review_status column + draft visibility config"
```

**审查清单:**
- ✓ migration 的 upgrade/downgrade 对称
- ✓ model 列定义 default="ai_draft" 与 migration server_default 一致
- ✓ 现有测试不受影响
- ✗ migration 操作了错误的表
- ✗ KNOWLEDGE_DRAFT_VISIBLE 类型不是 bool

---

### Task 2: Graph API v2 响应增强

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/schemas.py:6-23`
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py:32-129`
- Create: `tests/test_knowledge_tree/test_graph_v2.py`

**测试契约:**
1. node 响应包含 description 字段
   - 入口: `GET /api/v1/knowledge-tree/graph?module=M1`
   - 反例: 错误实现遗漏 description 字段——本测试验证响应 node 含 description
   - 边界: description 为 None 的概念 / description 含中文
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_graph_v2.py::test_node_includes_description -v`
2. node 响应包含 hard_in_count 和 hard_out_count
   - 入口: `GET /api/v1/knowledge-tree/graph?module=M1`
   - 反例: 错误实现返回 0 而非实际计数——本测试用已知拓扑验证精确计数
   - 边界: 孤立节点（0,0）/ 仅有入边 / 仅有出边
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_graph_v2.py::test_node_hard_counts -v`
3. edge 响应包含 confidence 和 review_status
   - 入口: `GET /api/v1/knowledge-tree/graph?module=all`
   - 反例: 错误实现遗漏 confidence——本测试验证响应 edge 含 confidence 和 review_status
   - 边界: confidence=0.0 / confidence=1.0 / review_status=None
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_graph_v2.py::test_edge_includes_confidence_and_review -v`
4. module 过滤时返回 external_hard_refs
   - 入口: `GET /api/v1/knowledge-tree/graph?module=M1`
   - 反例: 错误实现在 module 过滤时不返回跨模块引用——本测试验证 external_hard_refs 包含跨模块对端
   - 边界: 无跨模块边（空对象）/ 有入也有出 / module=all 时为空
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_graph_v2.py::test_external_hard_refs -v`

- [ ] **Step 1: 更新 schema**

```python
# schemas.py
class GraphNodeResponse(BaseModel):
    id: str
    name: str
    level: str
    module: str
    big_concept_id: str | None = None
    aliases: list[str] = []
    review_status: str | None = None
    difficulty: int | None = None
    bloom_level: str | None = None
    # v2 新增
    description: str | None = None
    hard_in_count: int = 0
    hard_out_count: int = 0
    external_hard_refs: dict | None = None  # {in: [{id,name,module}], out: [...]}


class GraphEdgeResponse(BaseModel):
    id: int | None = None  # edge PK，审查操作需要
    source: str
    target: str
    type: str
    strength: float
    # v2 新增
    confidence: float = 1.0
    review_status: str | None = None
```

- [ ] **Step 2: 写失败测试**

```python
# tests/test_knowledge_tree/test_graph_v2.py
"""Graph API v2 响应增强测试。"""
import pytest


@pytest.mark.asyncio
async def test_node_includes_description(client, db, seed_graph_v2):
    """node 响应包含 description。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=M1",
                            headers=seed_graph_v2["auth_headers"])
    assert resp.status_code == 200
    nodes = resp.json()["graph"]["nodes"]
    assert len(nodes) > 0
    node = next(n for n in nodes if n["id"] == "TEST_M1_A")
    assert node["description"] == "测试概念A描述"


@pytest.mark.asyncio
async def test_node_hard_counts(client, db, seed_graph_v2):
    """node 的 hard_in_count/hard_out_count 精确。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=M1",
                            headers=seed_graph_v2["auth_headers"])
    nodes = resp.json()["graph"]["nodes"]
    # TEST_M1_A → TEST_M1_B (hard), TEST_M1_A → TEST_M1_C (hard)
    node_a = next(n for n in nodes if n["id"] == "TEST_M1_A")
    assert node_a["hard_out_count"] == 2
    assert node_a["hard_in_count"] == 0
    node_b = next(n for n in nodes if n["id"] == "TEST_M1_B")
    assert node_b["hard_in_count"] == 1
    assert node_b["hard_out_count"] == 0


@pytest.mark.asyncio
async def test_edge_includes_confidence_and_review(client, db, seed_graph_v2):
    """edge 响应包含 confidence 和 review_status。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all",
                            headers=seed_graph_v2["auth_headers"])
    edges = resp.json()["graph"]["edges"]
    assert len(edges) > 0
    edge = edges[0]
    assert "confidence" in edge
    assert "review_status" in edge
    assert isinstance(edge["confidence"], float)


@pytest.mark.asyncio
async def test_external_hard_refs_with_module_filter(client, db, seed_graph_v2):
    """module 过滤时 external_hard_refs 包含跨模块对端。"""
    # seed_graph_v2 含跨模块边: TEST_M1_A → TEST_M2_X (hard)
    resp = await client.get("/api/v1/knowledge-tree/graph?module=M1",
                            headers=seed_graph_v2["auth_headers"])
    nodes = resp.json()["graph"]["nodes"]
    node_a = next(n for n in nodes if n["id"] == "TEST_M1_A")
    refs = node_a["external_hard_refs"]
    assert refs is not None
    assert len(refs["out"]) == 1
    assert refs["out"][0]["module"] == "M2"


@pytest.mark.asyncio
async def test_external_hard_refs_empty_without_module_filter(client, db, seed_graph_v2):
    """module=all 时 external_hard_refs 为 None。"""
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all",
                            headers=seed_graph_v2["auth_headers"])
    nodes = resp.json()["graph"]["nodes"]
    for n in nodes:
        assert n["external_hard_refs"] is None
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_graph_v2.py -v`
Expected: FAIL — description/hard_in_count/hard_out_count/external_hard_refs/confidence 字段缺失

- [ ] **Step 4: 创建 seed_graph_v2 fixture**

在 `tests/test_knowledge_tree/conftest.py`（新建或追加）中添加 fixture：

```python
# tests/test_knowledge_tree/conftest.py
import pytest
from datetime import datetime
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap


@pytest.fixture
async def seed_graph_v2(db, admin_headers):
    """创建 v2 测试图谱：M1 3节点 + M2 1节点 + 跨模块边。"""
    now = datetime.now()
    # BigConcept
    db.add(ConceptGraphNode(
        id="BC_M1_TEST", name="测试大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", display_order=0, synced_at=now,
    ))
    # M1 Concepts
    for suffix, desc in [("A", "测试概念A描述"), ("B", "测试概念B描述"), ("C", None)]:
        db.add(ConceptGraphNode(
            id=f"TEST_M1_{suffix}", name=f"概念{suffix}", knowledge_level="L1",
            primary_module="M1", description=desc, node_type="concept",
            review_status="ai_draft", synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"TEST_M1_{suffix}", big_concept_id="BC_M1_TEST", is_primary=True,
        ))
    # M2 Concept
    db.add(ConceptGraphNode(
        id="BC_M2_TEST", name="M2大概念", knowledge_level="L1",
        primary_module="M2", node_type="big_concept", display_order=0, synced_at=now,
    ))
    db.add(ConceptGraphNode(
        id="TEST_M2_X", name="概念X", knowledge_level="L1",
        primary_module="M2", description="M2概念", node_type="concept",
        review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptBigConceptMap(
        concept_id="TEST_M2_X", big_concept_id="BC_M2_TEST", is_primary=True,
    ))
    # Edges: A→B(hard), A→C(hard), A→X(hard,跨模块), B↔C(soft)
    for src, tgt, rtype, conf in [
        ("TEST_M1_A", "TEST_M1_B", "prerequisite_hard", 0.9),
        ("TEST_M1_A", "TEST_M1_C", "prerequisite_hard", 0.5),
        ("TEST_M1_A", "TEST_M2_X", "prerequisite_hard", 0.8),
        ("TEST_M1_B", "TEST_M1_C", "prerequisite_soft", 0.7),
    ]:
        db.add(ConceptGraphEdge(
            source_id=src, target_id=tgt, relation_type=rtype,
            strength=1.0, confidence=conf, review_status="ai_draft", synced_at=now,
        ))
    await db.commit()
    return {"auth_headers": admin_headers}
```

- [ ] **Step 5: 实现 get_graph 增强**

修改 `service.py` 的 `get_graph` 函数：

```python
async def get_graph(db: AsyncSession, module: str = "all") -> dict:
    """查询图谱结构（navigation + graph 格式），v2 增强。"""
    module_filter = None if module == "all" else module

    # ... 现有代码（BigConcept + map + concept 查询，不变）...

    # 4. Edges — 查全部 edge（包含跨模块，后面过滤）
    all_edge_q = sa.select(ConceptGraphEdge)
    all_edges_result = await db.execute(all_edge_q)
    all_edges = list(all_edges_result.scalars())

    # 获取所有 concept 的 id→(name, module) 映射（用于 external_hard_refs）
    all_concept_q = sa.select(
        ConceptGraphNode.id, ConceptGraphNode.name, ConceptGraphNode.primary_module
    ).where(ConceptGraphNode.node_type == "concept")
    all_concepts_lookup = {
        r[0]: {"name": r[1], "module": r[2]}
        for r in (await db.execute(all_concept_q)).all()
    }

    # 计算 hard_in/out 计数（基于全量 edge）
    hard_in_count: dict[str, int] = defaultdict(int)
    hard_out_count: dict[str, int] = defaultdict(int)
    for e in all_edges:
        if e.relation_type == "prerequisite_hard":
            hard_in_count[e.target_id] += 1
            hard_out_count[e.source_id] += 1

    # 计算 external_hard_refs（仅 module 过滤时）
    external_refs: dict[str, dict] = {}
    concept_ids_in_view = {n.id for n in concept_nodes}
    if module_filter:
        for e in all_edges:
            if e.relation_type != "prerequisite_hard":
                continue
            src_in = e.source_id in concept_ids_in_view
            tgt_in = e.target_id in concept_ids_in_view
            if src_in and not tgt_in:
                # 出边（本模块→外模块）
                refs = external_refs.setdefault(e.source_id, {"in": [], "out": []})
                info = all_concepts_lookup.get(e.target_id)
                if info:
                    refs["out"].append({"id": e.target_id, "name": info["name"], "module": info["module"]})
            elif tgt_in and not src_in:
                # 入边（外模块→本模块）
                refs = external_refs.setdefault(e.target_id, {"in": [], "out": []})
                info = all_concepts_lookup.get(e.source_id)
                if info:
                    refs["in"].append({"id": e.source_id, "name": info["name"], "module": info["module"]})

    # 过滤 edge（module 过滤时只保留模块内 edge）
    if module_filter:
        filtered_edges = [e for e in all_edges
                          if e.source_id in concept_ids_in_view and e.target_id in concept_ids_in_view]
    else:
        filtered_edges = all_edges

    # 6. 构建 graph
    nodes = []
    for n in concept_nodes:
        aliases = json.loads(n.aliases_json) if n.aliases_json else []
        nodes.append({
            "id": n.id, "name": n.name, "level": n.knowledge_level,
            "module": n.primary_module,
            "big_concept_id": concept_bc_id.get(n.id),
            "aliases": aliases,
            "review_status": n.review_status,
            "difficulty": n.difficulty,
            "bloom_level": n.bloom_level,
            "description": n.description,
            "hard_in_count": hard_in_count.get(n.id, 0),
            "hard_out_count": hard_out_count.get(n.id, 0),
            "external_hard_refs": external_refs.get(n.id) if module_filter else None,
        })
    edges = [
        {"id": e.id, "source": e.source_id, "target": e.target_id, "type": e.relation_type,
         "strength": e.strength, "confidence": e.confidence,
         "review_status": e.review_status}
        for e in filtered_edges
    ]

    return {
        "navigation": navigation,
        "graph": {"nodes": nodes, "edges": edges},
    }
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_graph_v2.py -v`
Expected: 5 tests PASS

- [ ] **Step 7: 运行全量测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/ -q --tb=short`
Expected: 全部通过

- [ ] **Step 8: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/schemas.py src/edu_cloud/modules/knowledge_tree/service.py tests/test_knowledge_tree/
git commit -m "feat(knowledge-tree): graph API v2 response — description, hard counts, external refs, confidence"
```

**边界条件:**
- 孤立节点（无任何 hard 边）→ hard_in_count=0, hard_out_count=0, external_hard_refs=None
- module=all 时 → external_hard_refs 为 None（不计算）
- description=None 的节点 → 返回 null，不报错
- 跨模块边两端都不在当前模块 → 不出现在 external_hard_refs

**审查清单:**
- ✓ GraphNodeResponse 含 description/hard_in_count/hard_out_count/external_hard_refs
- ✓ GraphEdgeResponse 含 confidence/review_status
- ✓ hard 计数基于全量 edge（不受 module 过滤影响）
- ✓ external_hard_refs 仅 module 过滤时计算
- ✗ hard 计数只统计了当前模块内的 edge
- ✗ external_hard_refs 在 module=all 时仍返回非 None

---

### Task 3: Edge 审核状态机

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py:237-244,299-308`
- Modify: `src/edu_cloud/modules/knowledge_tree/schemas.py:65-81`
- Create: `tests/test_knowledge_tree/test_edge_review.py`

**测试契约:**
1. edge set_review_status 正常转移
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`{operations: [{op: "set_review_status", edge_id: 1, status: "teacher_reviewed"}]}`
   - 反例: 错误实现不区分 node_id/edge_id，总是操作 node——本测试验证 edge 的 review_status 被修改
   - 边界: edge_id 不存在 / 非法转移（ai_draft→published 跳步）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_edge_review.py::test_edge_review_status_transition -v`
2. edge rejected 状态
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`{operations: [{op: "set_review_status", edge_id: 1, status: "rejected"}]}`
   - 反例: 错误实现不允许 rejected 状态——本测试验证 ai_draft→rejected 合法
   - 边界: rejected→ai_draft（撤回）/ teacher_reviewed→rejected
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_edge_review.py::test_edge_rejected -v`
3. 非法转移被拒绝
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`{operations: [{op: "set_review_status", edge_id: 1, status: "published"}]}`（当前 ai_draft）
   - 反例: 错误实现允许跳步——本测试验证 applied=0
   - 边界: ai_draft→published / rejected→teacher_reviewed / rejected→published
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_edge_review.py::test_edge_invalid_transition -v`

- [ ] **Step 1: 定义 edge 状态机常量**

```python
# service.py，在 _VALID_TRANSITIONS 后新增:
_EDGE_VALID_TRANSITIONS = {
    "ai_draft": {"teacher_reviewed", "rejected"},
    "teacher_reviewed": {"published", "rejected"},
    "published": {"ai_draft"},
    "rejected": {"ai_draft"},
}
```

- [ ] **Step 2: 更新 EditOperation schema 支持 edge_id**

```python
# schemas.py EditOperation，新增字段:
    edge_id: int | None = None  # for set_review_status on edge
```

- [ ] **Step 3: 写失败测试**

```python
# tests/test_knowledge_tree/test_edge_review.py
"""Edge 审核状态机测试。"""
import pytest


@pytest.mark.asyncio
async def test_edge_review_status_transition(client, db, seed_graph_v2):
    """edge ai_draft → teacher_reviewed。"""
    # 先拿到 edge id
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "teacher_reviewed"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["applied"] == 1

    await db.refresh(edge)
    assert edge.review_status == "teacher_reviewed"


@pytest.mark.asyncio
async def test_edge_rejected(client, db, seed_graph_v2):
    """edge ai_draft → rejected 合法。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "rejected"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp.json()["applied"] == 1

    await db.refresh(edge)
    assert edge.review_status == "rejected"

    # 撤回: rejected → ai_draft
    resp2 = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "ai_draft"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp2.json()["applied"] == 1


@pytest.mark.asyncio
async def test_edge_invalid_transition(client, db, seed_graph_v2):
    """非法转移: ai_draft → published（跳步）。"""
    from sqlalchemy import select
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge
    edge = (await db.execute(
        select(ConceptGraphEdge).where(
            ConceptGraphEdge.source_id == "TEST_M1_A",
            ConceptGraphEdge.target_id == "TEST_M1_B",
        )
    )).scalar_one()

    resp = await client.post("/api/v1/knowledge-tree/edit",
        json={"operations": [{"op": "set_review_status", "edge_id": edge.id, "status": "published"}]},
        headers=seed_graph_v2["auth_headers"],
    )
    assert resp.json()["applied"] == 0
```

- [ ] **Step 4: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_edge_review.py -v`
Expected: FAIL

- [ ] **Step 5: 实现 edge set_review_status**

修改 `service.py` 的 `apply_edits`，在 `set_review_status` 分支中区分 node/edge:

```python
        elif op == "set_review_status":
            new_status = op_data.get("status")
            edge_id = op_data.get("edge_id")
            if edge_id is not None:
                # Edge 审核
                edge = await db.get(ConceptGraphEdge, edge_id)
                current_status = (edge.review_status or "ai_draft") if edge else None
                if edge and new_status in _EDGE_VALID_TRANSITIONS.get(current_status, set()):
                    edge.review_status = new_status
                    applied += 1
            else:
                # Node 审核（现有逻辑不变）
                node = await db.get(ConceptGraphNode, op_data.get("id"))
                current_status = (node.review_status or "ai_draft") if node else None
                if node and new_status in _VALID_TRANSITIONS.get(current_status, set()):
                    node.review_status = new_status
                    node.reviewed_by = op_data.get("user_id")
                    node.reviewed_at = datetime.now().isoformat()
                    applied += 1
```

- [ ] **Step 6: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_edge_review.py -v`
Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/service.py src/edu_cloud/modules/knowledge_tree/schemas.py tests/test_knowledge_tree/test_edge_review.py
git commit -m "feat(knowledge-tree): edge review status state machine — ai_draft/teacher_reviewed/published/rejected"
```

**边界条件:**
- edge_id 不存在 → applied=0（不报错）
- edge review_status 为 NULL（旧数据）→ 当作 ai_draft 处理
- 同时有 edge_id 和 node_id → edge_id 优先（if edge_id is not None）

**审查清单:**
- ✓ edge 状态机含 rejected 状态（node 不含）
- ✓ edge_id/node_id 分支正确区分
- ✓ 非法转移返回 applied=0 不报错
- ✗ 操作 node 时误走了 edge 分支
- ✗ rejected 状态在 backwrite 时被遗漏

---

### Task 4: 发布过滤

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/router.py:20-27`
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py:32-129`
- Create: `tests/test_knowledge_tree/test_publish_filter.py`

**测试契约:**
1. include_draft=false 过滤 ai_draft 节点
   - 入口: `GET /api/v1/knowledge-tree/graph?module=all&include_draft=false`
   - 反例: 错误实现不过滤 ai_draft 节点——本测试验证 ai_draft 节点被排除
   - 边界: 所有节点都是 ai_draft（返回空）/ 混合状态 / include_draft=true 不过滤
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_publish_filter.py::test_include_draft_false_filters_nodes -v`
2. include_draft=false 过滤 rejected 和 ai_draft 边
   - 入口: `GET /api/v1/knowledge-tree/graph?module=all&include_draft=false`
   - 反例: 错误实现只过滤节点不过滤边——本测试验证 rejected/ai_draft 边被排除
   - 边界: 两端节点 teacher_reviewed 但边是 ai_draft / 边端节点被过滤后级联
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_publish_filter.py::test_include_draft_false_filters_edges -v`
3. navigation 的 concept_ids 同步过滤
   - 入口: `GET /api/v1/knowledge-tree/graph?module=all&include_draft=false`
   - 反例: 错误实现只过滤 graph.nodes 不过滤 navigation——本测试验证 concept_ids 不含被过滤的节点
   - 边界: 某 BigConcept 下所有概念都被过滤（concept_ids 为空）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_publish_filter.py::test_navigation_filtered -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_knowledge_tree/test_publish_filter.py
"""发布过滤测试。"""
import pytest
from datetime import datetime
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap


@pytest.fixture
async def seed_mixed_status(db, admin_headers):
    """混合审核状态的图谱。"""
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_PF_TEST", name="过滤测试大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    # A: teacher_reviewed, B: ai_draft, C: published
    for sid, status in [("A", "teacher_reviewed"), ("B", "ai_draft"), ("C", "published")]:
        db.add(ConceptGraphNode(
            id=f"PF_{sid}", name=f"过滤{sid}", knowledge_level="L1",
            primary_module="M1", node_type="concept", review_status=status, synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"PF_{sid}", big_concept_id="BC_PF_TEST", is_primary=True,
        ))
    # Edges: A→C (teacher_reviewed), A→B (ai_draft), B→C (rejected)
    db.add(ConceptGraphEdge(
        source_id="PF_A", target_id="PF_C", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.9, review_status="teacher_reviewed", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="PF_A", target_id="PF_B", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.5, review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="PF_B", target_id="PF_C", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.6, review_status="rejected", synced_at=now,
    ))
    await db.commit()
    return {"auth_headers": admin_headers}


@pytest.mark.asyncio
async def test_include_draft_false_filters_nodes(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=false",
                            headers=seed_mixed_status["auth_headers"])
    assert resp.status_code == 200
    node_ids = {n["id"] for n in resp.json()["graph"]["nodes"]}
    assert "PF_A" in node_ids  # teacher_reviewed
    assert "PF_C" in node_ids  # published
    assert "PF_B" not in node_ids  # ai_draft → 被过滤


@pytest.mark.asyncio
async def test_include_draft_false_filters_edges(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=false",
                            headers=seed_mixed_status["auth_headers"])
    edges = resp.json()["graph"]["edges"]
    # A→C (teacher_reviewed) 应保留
    assert any(e["source"] == "PF_A" and e["target"] == "PF_C" for e in edges)
    # A→B (ai_draft edge) 应被过滤
    assert not any(e["target"] == "PF_B" for e in edges)
    # B→C (rejected) 应被过滤
    assert not any(e["source"] == "PF_B" for e in edges)


@pytest.mark.asyncio
async def test_navigation_filtered(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=false",
                            headers=seed_mixed_status["auth_headers"])
    nav = resp.json()["navigation"]
    m1 = next(m for m in nav if m["id"] == "M1")
    bc = next(bc for bc in m1["big_concepts"] if bc["id"] == "BC_PF_TEST")
    assert "PF_B" not in bc["concept_ids"]
    assert "PF_A" in bc["concept_ids"]


@pytest.mark.asyncio
async def test_include_draft_true_shows_all(client, db, seed_mixed_status):
    resp = await client.get("/api/v1/knowledge-tree/graph?module=all&include_draft=true",
                            headers=seed_mixed_status["auth_headers"])
    node_ids = {n["id"] for n in resp.json()["graph"]["nodes"]}
    assert "PF_B" in node_ids  # ai_draft 可见
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_publish_filter.py -v`
Expected: FAIL

- [ ] **Step 3: 更新 router 添加 include_draft 参数**

```python
# router.py get_graph 端点
@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    module: str = Query("all", description="模块过滤: M1/M2/M3/M4/M5/all"),
    include_draft: bool = Query(True, description="是否包含未审核内容"),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """获取知识图谱结构（节点+边）。"""
    # 角色强制覆盖：学生/家长强制 include_draft=false
    role = current["current_role"].role
    if role in ("parent", "student"):
        from edu_cloud.config import settings
        if not settings.KNOWLEDGE_DRAFT_VISIBLE:
            include_draft = False
    return await service.get_graph(db, module=module, include_draft=include_draft)
```

- [ ] **Step 4: 实现 service 发布过滤**

修改 `service.py` 的 `get_graph` 函数签名和逻辑:

```python
async def get_graph(db: AsyncSession, module: str = "all", include_draft: bool = True) -> dict:
```

在构建 nodes 列表后，edges 列表前，添加过滤逻辑:

```python
    # 发布过滤
    if not include_draft:
        visible_statuses = {"teacher_reviewed", "published"}
        concept_nodes = [n for n in concept_nodes if (n.review_status or "ai_draft") in visible_statuses]
        concept_ids_in_view = {n.id for n in concept_nodes}
        # 重建 bc_concept_ids（只保留可见概念）
        for bc_id in bc_concept_ids:
            bc_concept_ids[bc_id] = [c for c in bc_concept_ids[bc_id] if c in concept_ids_in_view]

    # ... 然后正常构建 nodes/edges，edge 过滤中增加:
    if not include_draft:
        edge_visible = {"teacher_reviewed", "published"}
        filtered_edges = [e for e in filtered_edges
                          if (e.review_status or "ai_draft") in edge_visible
                          and e.source_id in concept_ids_in_view
                          and e.target_id in concept_ids_in_view]
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_publish_filter.py -v`
Expected: 4 tests PASS

- [ ] **Step 6: 运行全量知识树测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/ -q --tb=short`
Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/router.py src/edu_cloud/modules/knowledge_tree/service.py tests/test_knowledge_tree/test_publish_filter.py
git commit -m "feat(knowledge-tree): publish filtering — include_draft param + role enforcement"
```

**边界条件:**
- 所有节点都是 ai_draft + include_draft=false → 返回空 nodes/edges、navigation concept_ids 全空
- review_status=NULL（旧数据）→ 当作 ai_draft，include_draft=false 时被过滤
- KNOWLEDGE_DRAFT_VISIBLE=True 时 parent 角色也能看到 ai_draft（宽限期）

**审查清单:**
- ✓ include_draft=false 同时过滤 node 和 edge
- ✓ 被过滤 node 的关联边也被级联过滤
- ✓ navigation concept_ids 与 graph nodes 一致
- ✓ 教师/管理员默认 include_draft=true
- ✗ 过滤逻辑在 hard_in_count 计算之后执行（计数应基于全量，不受过滤影响）
- ✗ KNOWLEDGE_DRAFT_VISIBLE 逻辑反了（True 应该是不过滤）

---

### Task 5: 质量巡检 API

**Files:**
- Create: `src/edu_cloud/modules/knowledge_tree/quality_service.py`
- Modify: `src/edu_cloud/modules/knowledge_tree/router.py`
- Create: `tests/test_knowledge_tree/test_quality_check.py`

**测试契约:**
1. Q1 检测孤立概念
   - 入口: `GET /api/v1/knowledge-tree/quality-check?module=M1`
   - 反例: 错误实现不检查 soft 边（孤立只看 hard）——本测试验证有 soft 边但无 hard 边的节点被标为孤立
   - 边界: 有 soft 但无 hard（仍孤立）/ 只有 hard_in（非孤立）/ 只有 hard_out（非孤立）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_quality_check.py::test_q1_orphan -v`
2. Q2 弱连通分量
   - 入口: `GET /api/v1/knowledge-tree/quality-check?module=M1`
   - 反例: 错误实现将有向图当无向图——BFS 应按无向处理 prerequisite_hard
   - 边界: 单个连通分量（不报告）/ 2 个分量 / 所有节点都孤立（每个节点一个分量）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_quality_check.py::test_q2_weak_components -v`
3. Q3 低置信度关系
   - 入口: `GET /api/v1/knowledge-tree/quality-check?module=M1`
   - 反例: 错误实现不考虑 review_status——已审核的低置信度不报告
   - 边界: confidence=0.7（不报告，阈值是 <0.7）/ confidence=0.69（报告）/ 已审核的低置信度（不报告）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_quality_check.py::test_q3_low_confidence -v`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_knowledge_tree/test_quality_check.py
"""质量巡检测试。"""
import pytest
from datetime import datetime
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge, ConceptBigConceptMap


@pytest.fixture
async def seed_quality(db, admin_headers):
    """质量巡检测试数据。"""
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="BC_QC", name="巡检大概念", knowledge_level="L1",
        primary_module="M1", node_type="big_concept", synced_at=now,
    ))
    # A: 正常（有 hard in/out）, B: 正常, C: 孤立（只有 soft）, D: 无描述, E: 独立分量
    for sid, desc, rs in [
        ("A", "概念A", "ai_draft"), ("B", "概念B", "ai_draft"),
        ("C", "概念C", "ai_draft"), ("D", None, "ai_draft"),
        ("E", "概念E", "ai_draft"),
    ]:
        db.add(ConceptGraphNode(
            id=f"QC_{sid}", name=f"巡检{sid}", knowledge_level="L1",
            primary_module="M1", description=desc, node_type="concept",
            review_status=rs, synced_at=now,
        ))
        db.add(ConceptBigConceptMap(
            concept_id=f"QC_{sid}", big_concept_id="BC_QC", is_primary=True,
        ))
    # A→B (hard, low confidence), C only has soft edge, E is isolated component
    db.add(ConceptGraphEdge(
        source_id="QC_A", target_id="QC_B", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.5, review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="QC_A", target_id="QC_D", relation_type="prerequisite_hard",
        strength=1.0, confidence=0.9, review_status="ai_draft", synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="QC_C", target_id="QC_A", relation_type="prerequisite_soft",
        strength=1.0, confidence=0.8, review_status="ai_draft", synced_at=now,
    ))
    await db.commit()
    return {"auth_headers": admin_headers}


@pytest.mark.asyncio
async def test_q1_orphan(client, db, seed_quality):
    """Q1: 有 soft 但无 hard 的节点被标为孤立。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    assert resp.status_code == 200
    issues = resp.json()["issues"]
    q1 = [i for i in issues if i["rule_id"] == "Q1"]
    orphan_ids = set()
    for issue in q1:
        orphan_ids.update(issue["node_ids"])
    assert "QC_C" in orphan_ids  # 只有 soft 边
    assert "QC_E" in orphan_ids  # 完全无边
    assert "QC_A" not in orphan_ids  # 有 hard out


@pytest.mark.asyncio
async def test_q2_weak_components(client, db, seed_quality):
    """Q2: 检测到多个弱连通分量。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    issues = resp.json()["issues"]
    q2 = [i for i in issues if i["rule_id"] == "Q2"]
    assert len(q2) == 1  # 有多个分量
    # A→B, A→D 是一个分量; C 孤立; E 孤立
    # 但 Q2 只在分量>1时报告，报告所有分量


@pytest.mark.asyncio
async def test_q3_low_confidence(client, db, seed_quality):
    """Q3: confidence<0.7 且 ai_draft 的边。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    issues = resp.json()["issues"]
    q3 = [i for i in issues if i["rule_id"] == "Q3"]
    assert len(q3) >= 1
    # A→B (confidence=0.5, ai_draft) 应被检出
    edge_ids = set()
    for issue in q3:
        edge_ids.update(issue["edge_ids"])
    assert len(edge_ids) >= 1


@pytest.mark.asyncio
async def test_q5_no_description(client, db, seed_quality):
    """Q5: 无描述的概念。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    issues = resp.json()["issues"]
    q5 = [i for i in issues if i["rule_id"] == "Q5"]
    assert len(q5) >= 1
    node_ids = set()
    for issue in q5:
        node_ids.update(issue["node_ids"])
    assert "QC_D" in node_ids


@pytest.mark.asyncio
async def test_quality_summary(client, db, seed_quality):
    """summary 统计正确。"""
    resp = await client.get("/api/v1/knowledge-tree/quality-check?module=M1",
                            headers=seed_quality["auth_headers"])
    data = resp.json()
    assert data["module"] == "M1"
    assert data["summary"]["total_nodes"] == 5
    assert data["summary"]["total_edges"] == 3
    assert sum(data["summary"]["issues_by_severity"].values()) > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_quality_check.py -v`
Expected: FAIL（endpoint 不存在）

- [ ] **Step 3: 实现 quality_service.py**

```python
# src/edu_cloud/modules/knowledge_tree/quality_service.py
"""知识图谱质量巡检服务。"""
from collections import defaultdict
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge


async def run_quality_check(db: AsyncSession, module: str = "all") -> dict:
    """执行 6 条质量巡检规则，返回 issues 列表。"""
    module_filter = None if module == "all" else module

    # 查 concept 节点
    node_q = sa.select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    if module_filter:
        node_q = node_q.where(ConceptGraphNode.primary_module == module_filter)
    nodes = list((await db.execute(node_q)).scalars())
    node_ids = {n.id for n in nodes}
    node_map = {n.id: n for n in nodes}

    # 查 edge（两端都在当前范围内）
    edge_q = sa.select(ConceptGraphEdge)
    if module_filter:
        subq = sa.select(ConceptGraphNode.id).where(
            ConceptGraphNode.primary_module == module_filter,
            ConceptGraphNode.node_type == "concept",
        )
        edge_q = edge_q.where(
            ConceptGraphEdge.source_id.in_(subq),
            ConceptGraphEdge.target_id.in_(subq),
        )
    edges = list((await db.execute(edge_q)).scalars())

    # 所有 edge（含跨模块，用于 Q4）
    all_edges = list((await db.execute(sa.select(ConceptGraphEdge))).scalars())

    issues: list[dict[str, Any]] = []

    # --- Q1: 孤立概念（无 hard 边）---
    hard_connected = set()
    for e in all_edges:
        if e.relation_type == "prerequisite_hard":
            hard_connected.add(e.source_id)
            hard_connected.add(e.target_id)
    orphans = [n.id for n in nodes if n.id not in hard_connected]
    if orphans:
        issues.append({
            "rule_id": "Q1", "severity": "HIGH",
            "message": f"孤立概念（无硬前置关系）：{len(orphans)} 个",
            "node_ids": orphans, "edge_ids": [],
        })

    # --- Q2: 弱连通分量（prerequisite_hard 无向图）---
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        if e.relation_type == "prerequisite_hard":
            adj[e.source_id].add(e.target_id)
            adj[e.target_id].add(e.source_id)
    # 只看有 hard 边的节点
    hard_node_ids = node_ids & set(adj.keys())
    visited: set[str] = set()
    components: list[list[str]] = []
    for nid in hard_node_ids:
        if nid in visited:
            continue
        # BFS
        component = []
        queue = [nid]
        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)
            component.append(curr)
            for neighbor in adj.get(curr, set()):
                if neighbor not in visited and neighbor in hard_node_ids:
                    queue.append(neighbor)
        components.append(component)
    if len(components) > 1:
        comp_desc = "; ".join(f"[{', '.join(c[:3])}{'...' if len(c)>3 else ''}]({len(c)})" for c in components)
        issues.append({
            "rule_id": "Q2", "severity": "MED",
            "message": f"硬前置子图有 {len(components)} 个弱连通分量：{comp_desc}",
            "node_ids": [nid for comp in components for nid in comp],
            "edge_ids": [],
        })

    # --- Q3: 低置信度关系（<0.7 且 ai_draft）---
    low_conf_edges = [
        e for e in edges
        if e.confidence < 0.7 and (e.review_status or "ai_draft") == "ai_draft"
    ]
    if low_conf_edges:
        issues.append({
            "rule_id": "Q3", "severity": "MED",
            "message": f"低置信度未审核关系：{len(low_conf_edges)} 条（confidence < 0.7）",
            "node_ids": [], "edge_ids": [e.id for e in low_conf_edges],
        })

    # --- Q4: 跨模块硬前置（列出供确认）---
    if module_filter:
        cross_module = [
            e for e in all_edges
            if e.relation_type == "prerequisite_hard"
            and ((e.source_id in node_ids) != (e.target_id in node_ids))
        ]
        if cross_module:
            issues.append({
                "rule_id": "Q4", "severity": "LOW",
                "message": f"跨模块硬前置关系：{len(cross_module)} 条",
                "node_ids": [], "edge_ids": [e.id for e in cross_module],
            })

    # --- Q5: 无描述概念 ---
    no_desc = [n.id for n in nodes if not n.description]
    if no_desc:
        issues.append({
            "rule_id": "Q5", "severity": "MED",
            "message": f"无描述概念：{len(no_desc)} 个",
            "node_ids": no_desc, "edge_ids": [],
        })

    # --- Q6: rejected 堆积（>20%）---
    rejected_count = sum(1 for e in edges if (e.review_status or "ai_draft") == "rejected")
    if edges and rejected_count / len(edges) > 0.2:
        issues.append({
            "rule_id": "Q6", "severity": "LOW",
            "message": f"被驳回关系占比 {rejected_count}/{len(edges)}（>{20}%），建议清理",
            "node_ids": [], "edge_ids": [e.id for e in edges if (e.review_status or "ai_draft") == "rejected"],
        })

    # Summary
    severity_count: dict[str, int] = defaultdict(int)
    for issue in issues:
        severity_count[issue["severity"]] += 1

    return {
        "module": module,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "issues_by_severity": dict(severity_count),
        },
        "issues": issues,
    }
```

- [ ] **Step 4: 添加 router 端点**

```python
# router.py 新增端点（在 edit 之前）
@router.get("/quality-check")
async def quality_check(
    module: str = Query("all", description="模块过滤"),
    db: AsyncSession = Depends(get_db),
    current=Depends(require_permission(Permission.EDIT_KNOWLEDGE_TREE)),
):
    """知识图谱质量巡检（6 条规则）。"""
    from edu_cloud.modules.knowledge_tree.quality_service import run_quality_check
    return await run_quality_check(db, module=module)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_quality_check.py -v`
Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/quality_service.py src/edu_cloud/modules/knowledge_tree/router.py tests/test_knowledge_tree/test_quality_check.py
git commit -m "feat(knowledge-tree): quality check API — 6 rules (orphan/SCC/low-confidence/cross-module/no-desc/rejected)"
```

**边界条件:**
- 无节点（空模块）→ 返回 summary 全 0，issues 空
- 所有节点孤立 → Q1 报全部，Q2 不报（无 hard 边则无分量）
- confidence=0.7 → 不触发 Q3（阈值 <0.7）
- module=all 时 Q4 不触发（只在模块过滤时检查跨模块）

**审查清单:**
- ✓ Q1 孤立判定只看 hard 边（soft 不算）
- ✓ Q2 BFS 按无向图处理 hard 边
- ✓ Q3 排除已审核的低置信度关系
- ✓ Q4 仅 module 过滤时生效
- ✗ BFS 遗漏反向边（adj 应双向添加）
- ✗ Q6 除法分母为 0（edges 为空时 ZeroDivisionError）

---

### Task 6: Sync 适配 + Backwrite

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/sync_service.py:95-106`
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py:376-448`

- [ ] **Step 1: sync_service 读取 edge review_status**

修改 `_read_knowledge_db` 中 edge 读取部分:

```python
    # 3. Edges（只读 L1 节点之间的边）
    l1_ids = {n["id"] for n in l1_nodes}
    has_edge_review = _column_exists(conn, "concept_relations", "review_status")
    edge_cols = "source_id, target_id, relation_type, strength, confidence"
    if has_edge_review:
        edge_cols += ", review_status"
    edges = []
    for row in conn.execute(f"SELECT {edge_cols} FROM concept_relations"):
        if row["source_id"] in l1_ids and row["target_id"] in l1_ids:
            edges.append({
                "source_id": row["source_id"], "target_id": row["target_id"],
                "relation_type": row["relation_type"],
                "strength": row["strength"] or 1.0, "confidence": row["confidence"] or 1.0,
                "review_status": row["review_status"] if has_edge_review else None,
            })
```

- [ ] **Step 2: _sync_graph 写入 edge review_status**

修改 `_sync_graph` 中 edge 写入:

```python
    # 写 edges
    for e in edges:
        db.add(ConceptGraphEdge(
            source_id=e["source_id"], target_id=e["target_id"],
            relation_type=e["relation_type"], strength=e["strength"],
            confidence=e["confidence"],
            review_status=e.get("review_status"),
            synced_at=now,
        ))
```

- [ ] **Step 3: backwrite 支持 edge set_review_status**

修改 `service.py` 的 `backwrite_to_knowledge_db`，在 `set_review_status` 分支中处理 edge:

```python
            elif op == "set_review_status":
                edge_id = op_data.get("edge_id")
                if edge_id is not None:
                    # Edge review status backwrite
                    edge_review_cols = {r[1] for r in conn.execute("PRAGMA table_info(concept_relations)")}
                    if "review_status" in edge_review_cols:
                        # 需要通过 PG edge_id 找到 source/target/type 来定位 sqlite 行
                        # 查 PG 获取 edge 信息
                        from edu_cloud.modules.knowledge_tree.models import ConceptGraphEdge as CGE
                        import sqlalchemy as _sa
                        # backwrite 在 commit 后调用，用新 session 查
                        pass  # edge backwrite 需要 source/target/type，在 operations 中补全
                else:
                    if "review_status" in existing_cols:
                        conn.execute(
                            "UPDATE concepts SET review_status=? WHERE id=?",
                            (op_data.get("status"), op_data.get("id")),
                        )
```

注意：edge backwrite 需要 source_id/target_id/relation_type 来定位 sqlite 行。在 `apply_edits` 中，对 edge set_review_status 成功后，将 edge 的 source/target/type 附加到 op_data 中再传给 backwrite:

```python
            # 在 apply_edits 的 edge set_review_status 分支末尾:
                if edge and new_status in _EDGE_VALID_TRANSITIONS.get(current_status, set()):
                    edge.review_status = new_status
                    # 附加 edge 坐标供 backwrite
                    op_data["_edge_source"] = edge.source_id
                    op_data["_edge_target"] = edge.target_id
                    op_data["_edge_type"] = edge.relation_type
                    applied += 1
```

然后 backwrite 中:

```python
                if edge_id is not None:
                    edge_review_cols = {r[1] for r in conn.execute("PRAGMA table_info(concept_relations)")}
                    if "review_status" in edge_review_cols:
                        conn.execute(
                            "UPDATE concept_relations SET review_status=? WHERE source_id=? AND target_id=? AND relation_type=?",
                            (op_data.get("status"), op_data.get("_edge_source"),
                             op_data.get("_edge_target"), op_data.get("_edge_type")),
                        )
```

- [ ] **Step 4: 运行全量测试**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/ -q --tb=short`
Expected: 全部通过

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/sync_service.py src/edu_cloud/modules/knowledge_tree/service.py
git commit -m "feat(knowledge-tree): sync edge review_status between knowledge.db and PG"
```

**测试契约:**
1. sync 读取 edge review_status
   - 入口: app startup → `sync_knowledge_on_startup()` → PG edge 表
   - 反例: 错误实现不读取 review_status 列——sync 后 PG edge 全为 NULL 而非 knowledge.db 的值
   - 边界: knowledge.db 无 review_status 列（旧 schema）→ 默认 None / 有列但值为 NULL
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_sync_edge_review.py::test_sync_reads_edge_review_status -v`
2. backwrite edge review_status
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`{operations: [{op: "set_review_status", edge_id: N, status: "teacher_reviewed"}]}`
   - 反例: 错误实现不回写 edge review_status——knowledge.db 中边仍为旧状态
   - 边界: knowledge.db 无 review_status 列（静默跳过不报错）/ edge_id 不存在（不回写）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_sync_edge_review.py::test_backwrite_edge_review_status -v`

**边界条件:**
- knowledge.db concept_relations 表无 review_status 列（旧 schema）→ 默认 None，不报错
- edge_id 在 backwrite 时无 _edge_source 元数据（非 edge 操作）→ 跳过回写
- knowledge.db 不存在 → sync 返回 not_found，backwrite 报错记录到 edit_sync_failures

**审查清单:**
- ✓ sync 读取时检查 concept_relations 表的 review_status 列存在性
- ✓ sync 写入时传递 review_status 到 ConceptGraphEdge
- ✓ backwrite edge review_status 使用 source/target/type 定位
- ✗ backwrite 中访问了未 import 的模块
- ✗ _edge_source/_edge_target 在非 edge 操作时被错误读取

---

## Batch 2: 前端（Tasks 7-9）

### Task 7: 前端 API + Composable 更新

**Files:**
- Modify: `frontend/src/api/knowledgeTree.js`
- Modify: `frontend/src/components/knowledge-tree/useKnowledgeTree.js`

- [ ] **Step 1: 更新 API client**

```javascript
// frontend/src/api/knowledgeTree.js
import client from './client'

export const getGraph = (module = 'all', includeDraft = true) =>
  client.get('/knowledge-tree/graph', { params: { module, include_draft: includeDraft } })

export const getMastery = (studentId, module = 'all') =>
  client.get('/knowledge-tree/mastery', { params: { student_id: studentId, module } })

export const getNodeDetail = (nodeId, signal) =>
  client.get(`/knowledge-tree/graph/${nodeId}/detail`, { signal })

export const searchConcepts = (q) =>
  client.get('/knowledge-tree/search', { params: { q } })

export const editGraph = (operations) =>
  client.post('/knowledge-tree/edit', { operations })

export const qualityCheck = (module = 'all') =>
  client.get('/knowledge-tree/quality-check', { params: { module } })
```

- [ ] **Step 2: 更新 composable**

```javascript
// frontend/src/components/knowledge-tree/useKnowledgeTree.js
import { ref, computed } from 'vue'
import { getGraph, getMastery, editGraph, qualityCheck } from '../../api/knowledgeTree'

export function useKnowledgeTree() {
  const navigationData = ref([])
  const graphData = ref({ nodes: [], edges: [] })
  const masteryData = ref({ student_id: '', concept_mastery: [], module_mastery: [] })
  const qualityIssues = ref([])
  const qualitySummary = ref(null)
  const loading = ref(false)
  const selectedModule = ref('all')
  const selectedStudentId = ref(null)

  const moduleMastery = computed(() => masteryData.value.module_mastery)

  const nodesWithMastery = computed(() => {
    const masteryMap = {}
    for (const cm of masteryData.value.concept_mastery) {
      masteryMap[cm.concept_id] = cm
    }
    return graphData.value.nodes.map(node => ({
      ...node,
      mastery: masteryMap[node.id]?.mastery ?? 0,
      mastery_state: masteryMap[node.id]?.state ?? 'unseen',
      da_count: masteryMap[node.id]?.da_count ?? 0,
    }))
  })

  async function loadGraph(module = 'all', includeDraft = true) {
    selectedModule.value = module
    const resp = await getGraph(module, includeDraft)
    navigationData.value = resp.data.navigation ?? []
    graphData.value = resp.data.graph ?? { nodes: [], edges: [] }
  }

  async function loadMastery(studentId, module = 'all') {
    selectedStudentId.value = studentId
    const resp = await getMastery(studentId, module)
    masteryData.value = resp.data
  }

  async function loadQuality(module = 'all') {
    const resp = await qualityCheck(module)
    qualityIssues.value = resp.data.issues ?? []
    qualitySummary.value = resp.data.summary ?? null
  }

  async function applyEdit(operations) {
    loading.value = true
    try {
      const resp = await editGraph(operations)
      await loadGraph(selectedModule.value)
      return resp.data
    } finally {
      loading.value = false
    }
  }

  return {
    navigationData, graphData, masteryData, qualityIssues, qualitySummary,
    loading, selectedModule, selectedStudentId, moduleMastery, nodesWithMastery,
    loadGraph, loadMastery, loadQuality, applyEdit,
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/knowledgeTree.js frontend/src/components/knowledge-tree/useKnowledgeTree.js
git commit -m "feat(knowledge-tree): frontend API client + composable — quality check + include_draft"
```

**测试契约:**
1. getGraph 透传 includeDraft 参数
   - 入口: `useKnowledgeTree().loadGraph('M1', false)` → Axios GET `/knowledge-tree/graph?module=M1&include_draft=false`
   - 反例: 错误实现丢失 includeDraft 参数——API 请求 URL 不含 include_draft
   - 边界: includeDraft=true（默认）/ includeDraft=false / 不传参
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js`
2. qualityCheck 调用和 loadQuality 异常传播
   - 入口: `useKnowledgeTree().loadQuality('M1')` → Axios GET `/knowledge-tree/quality-check?module=M1`
   - 反例: 错误实现静默吞错——调用方无法感知失败
   - 边界: API 返回 200 正常数据 / API 返回 500（异常传播）/ 空 issues 数组
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js`

**边界条件:**
- API 返回 500 → loadQuality 异常传播到调用方（不静默吞错）
- qualityIssues 为空数组 → 工作台仍可用，只是没有标记
- includeDraft=true 是默认值 → 现有调用无需改动（向后兼容）

**审查清单:**
- ✓ getGraph 新增 includeDraft 参数，默认 true（向后兼容）
- ✓ qualityCheck 新增
- ✓ composable 导出 qualityIssues/qualitySummary/loadQuality
- ✗ loadGraph 调用时丢失了 includeDraft 参数

---

### Task 8: 审查工作台前端组件

**Files:**
- Create: `frontend/src/components/knowledge-tree/QualityBadge.vue`
- Create: `frontend/src/components/knowledge-tree/ConceptReviewList.vue`
- Create: `frontend/src/components/knowledge-tree/RelationDetailCard.vue`
- Create: `frontend/src/components/knowledge-tree/RelationReviewPanel.vue`

- [ ] **Step 1: QualityBadge 组件**

```vue
<!-- frontend/src/components/knowledge-tree/QualityBadge.vue -->
<template>
  <n-tag v-if="severity" :type="tagType" size="small" round>
    {{ label }}
  </n-tag>
</template>

<script setup>
import { computed } from 'vue'
import { NTag } from 'naive-ui'

const props = defineProps({
  severity: { type: String, default: null },  // HIGH / MED / LOW
  label: { type: String, default: '' },
})

const tagType = computed(() => {
  if (props.severity === 'HIGH') return 'error'
  if (props.severity === 'MED') return 'warning'
  return 'default'
})
</script>
```

- [ ] **Step 2: ConceptReviewList 组件**

```vue
<!-- frontend/src/components/knowledge-tree/ConceptReviewList.vue -->
<template>
  <div class="concept-review-list">
    <div class="filters">
      <n-select v-model:value="filterModule" :options="moduleOptions" size="small" placeholder="模块" clearable style="width: 100%" />
      <n-select v-model:value="filterStatus" :options="statusOptions" size="small" placeholder="审核状态" clearable style="width: 100%; margin-top: 6px" />
      <n-select v-model:value="sortBy" :options="sortOptions" size="small" style="width: 100%; margin-top: 6px" />
    </div>
    <div class="progress-bar" v-if="totalEdges > 0">
      <n-progress :percentage="Math.round(reviewedEdges / totalEdges * 100)" :height="8" />
      <span class="progress-label">{{ reviewedEdges }}/{{ totalEdges }} 关系已审核</span>
    </div>
    <n-list hoverable clickable class="concept-list">
      <n-list-item v-for="concept in sortedConcepts" :key="concept.id"
        :class="{ active: concept.id === selectedId }"
        @click="$emit('select', concept)">
        <div class="concept-item">
          <span class="status-dot" :class="statusClass(concept)" />
          <span class="concept-name">{{ concept.name }}</span>
          <QualityBadge v-if="conceptIssue(concept.id)" :severity="conceptIssue(concept.id)" label="!" />
        </div>
      </n-list-item>
    </n-list>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NSelect, NList, NListItem, NProgress } from 'naive-ui'
import QualityBadge from './QualityBadge.vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  qualityIssues: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
})
defineEmits(['select'])

const filterModule = ref(null)
const filterStatus = ref(null)
const sortBy = ref('priority')

const moduleOptions = [
  { label: 'M1 分子与细胞', value: 'M1' }, { label: 'M2 遗传与进化', value: 'M2' },
  { label: 'M3 稳态与调节', value: 'M3' }, { label: 'M4 生态与环境', value: 'M4' },
  { label: 'M5 生物技术', value: 'M5' },
]
const statusOptions = [
  { label: 'AI 草稿', value: 'ai_draft' },
  { label: '教师已审', value: 'teacher_reviewed' },
  { label: '已发布', value: 'published' },
]
const sortOptions = [
  { label: '按优先级', value: 'priority' },
  { label: '按名称', value: 'name' },
  { label: '按排序', value: 'order' },
]

// 质量问题映射: node_id → 最高严重度
const issueMap = computed(() => {
  const m = {}
  for (const issue of props.qualityIssues) {
    for (const nid of issue.node_ids || []) {
      if (!m[nid] || severityRank(issue.severity) > severityRank(m[nid])) {
        m[nid] = issue.severity
      }
    }
  }
  return m
})

function severityRank(s) {
  return s === 'HIGH' ? 3 : s === 'MED' ? 2 : 1
}

function conceptIssue(id) {
  return issueMap.value[id] || null
}

// 审查进度
const totalEdges = computed(() => props.edges.length)
const reviewedEdges = computed(() =>
  props.edges.filter(e => e.review_status && e.review_status !== 'ai_draft').length
)

const filteredConcepts = computed(() => {
  let list = [...props.nodes]
  if (filterModule.value) list = list.filter(n => n.module === filterModule.value)
  if (filterStatus.value) list = list.filter(n => (n.review_status || 'ai_draft') === filterStatus.value)
  return list
})

const sortedConcepts = computed(() => {
  const list = [...filteredConcepts.value]
  if (sortBy.value === 'priority') {
    list.sort((a, b) => severityRank(issueMap.value[b.id] || '') - severityRank(issueMap.value[a.id] || ''))
  } else if (sortBy.value === 'name') {
    list.sort((a, b) => a.name.localeCompare(b.name, 'zh'))
  }
  return list
})

function statusClass(concept) {
  const s = concept.review_status || 'ai_draft'
  const hasUnreviewedEdge = props.edges.some(e =>
    (e.source === concept.id || e.target === concept.id) && (e.review_status || 'ai_draft') === 'ai_draft'
  )
  if (s === 'published' && !hasUnreviewedEdge) return 'published'
  if (hasUnreviewedEdge) return 'warning'
  return 'draft'
}
</script>

<style scoped>
.concept-review-list { display: flex; flex-direction: column; height: 100%; }
.filters { padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.progress-bar { padding: 8px 12px; }
.progress-label { font-size: 12px; color: rgba(255,255,255,0.5); }
.concept-list { flex: 1; overflow-y: auto; }
.concept-item { display: flex; align-items: center; gap: 8px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.published { background: #63e2b7; }
.status-dot.warning { background: #f2c97d; }
.status-dot.draft { background: rgba(255,255,255,0.3); }
.concept-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.active { background: rgba(99, 226, 183, 0.1) !important; }
</style>
```

- [ ] **Step 3: RelationDetailCard 组件**

```vue
<!-- frontend/src/components/knowledge-tree/RelationDetailCard.vue -->
<template>
  <div class="relation-detail-card" v-if="concept">
    <div class="concept-header">
      <h3>{{ concept.name }}</h3>
      <n-tag :type="reviewTagType" size="small">{{ concept.review_status || 'ai_draft' }}</n-tag>
      <p v-if="concept.description" class="desc">{{ concept.description }}</p>
    </div>

    <div v-for="group in relationGroups" :key="group.type" class="relation-group">
      <div class="group-header">
        <span class="group-label">{{ group.label }}</span>
        <n-button size="tiny" quaternary @click="batchConfirm(group.edges)" :disabled="!canEdit">
          全部确认
        </n-button>
      </div>
      <div v-for="edge in group.edges" :key="edgeKey(edge)" class="relation-row">
        <span class="direction">{{ edge._direction === 'in' ? '←' : '→' }}</span>
        <span class="peer-name">{{ edge._peerName }}</span>
        <n-tag v-if="edge.confidence < 0.7" type="warning" size="tiny">{{ edge.confidence.toFixed(2) }}</n-tag>
        <span class="edge-status" :class="edge.review_status || 'ai_draft'">
          {{ statusLabel(edge.review_status) }}
        </span>
        <n-button-group size="tiny">
          <n-button type="success" :disabled="!canEdit" @click="confirmEdge(edge)">确认</n-button>
          <n-button type="error" :disabled="!canEdit" @click="rejectEdge(edge)">驳回</n-button>
          <n-button :disabled="!canEdit" @click="editEdge(edge)">编辑</n-button>
        </n-button-group>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NTag, NButton, NButtonGroup } from 'naive-ui'

const props = defineProps({
  concept: { type: Object, default: null },
  edges: { type: Array, default: () => [] },
  allNodes: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['review-edge', 'edit-edge'])

const nodeMap = computed(() => {
  const m = {}
  for (const n of props.allNodes) m[n.id] = n
  return m
})

const reviewTagType = computed(() => {
  const s = props.concept?.review_status || 'ai_draft'
  if (s === 'published') return 'success'
  if (s === 'teacher_reviewed') return 'info'
  return 'default'
})

// 找到与当前概念相关的所有边，标注方向和对端名称
const relatedEdges = computed(() => {
  if (!props.concept) return []
  const cid = props.concept.id
  return props.edges
    .filter(e => e.source === cid || e.target === cid)
    .map(e => ({
      ...e,
      _direction: e.target === cid ? 'in' : 'out',
      _peerId: e.target === cid ? e.source : e.target,
      _peerName: nodeMap.value[e.target === cid ? e.source : e.target]?.name || '未知',
    }))
})

// 按关系类型分组
const typeConfig = [
  { type: 'prerequisite_hard', label: '硬前置依赖' },
  { type: 'prerequisite_soft', label: '软前置依赖' },
  { type: 'bridge_to', label: '跨域桥接' },
  { type: 'contrast', label: '边界对比' },
]

const relationGroups = computed(() =>
  typeConfig
    .map(tc => ({
      ...tc,
      edges: relatedEdges.value.filter(e => e.type === tc.type),
    }))
    .filter(g => g.edges.length > 0)
)

function edgeKey(e) {
  return `${e.source}-${e.target}-${e.type}`
}

function statusLabel(s) {
  const labels = { ai_draft: '待审', teacher_reviewed: '已审', published: '已发布', rejected: '已驳回' }
  return labels[s || 'ai_draft'] || s
}

function confirmEdge(edge) {
  // 从当前状态推进到 teacher_reviewed
  emit('review-edge', { edgeId: edge.id, status: 'teacher_reviewed' })
}

function rejectEdge(edge) {
  emit('review-edge', { edgeId: edge.id, status: 'rejected' })
}

function editEdge(edge) {
  emit('edit-edge', {
    edgeId: edge.id, source: edge.source, target: edge.target,
    type: edge.type, strength: edge.strength,
  })
}

function batchConfirm(edges) {
  for (const e of edges) {
    if ((e.review_status || 'ai_draft') !== 'teacher_reviewed' && (e.review_status || 'ai_draft') !== 'published') {
      emit('review-edge', { edgeId: e.id, status: 'teacher_reviewed' })
    }
  }
}
</script>

<style scoped>
.concept-header { margin-bottom: 16px; }
.concept-header h3 { margin: 0 0 4px; }
.desc { color: rgba(255,255,255,0.5); font-size: 13px; margin: 4px 0 0; }
.relation-group { margin-bottom: 16px; }
.group-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.group-label { font-weight: 600; font-size: 13px; color: rgba(255,255,255,0.7); }
.relation-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
.direction { font-family: monospace; color: rgba(255,255,255,0.4); width: 20px; text-align: center; }
.peer-name { flex: 1; }
.edge-status { font-size: 12px; color: rgba(255,255,255,0.4); min-width: 40px; }
.edge-status.rejected { color: #e88080; text-decoration: line-through; }
.edge-status.teacher_reviewed { color: #63e2b7; }
</style>
```

- [ ] **Step 4: RelationReviewPanel 组件**

```vue
<!-- frontend/src/components/knowledge-tree/RelationReviewPanel.vue -->
<template>
  <div class="relation-review-panel">
    <div class="review-left">
      <ConceptReviewList
        :nodes="nodes"
        :edges="edges"
        :quality-issues="qualityIssues"
        :selected-id="selectedConcept?.id"
        @select="selectedConcept = $event"
      />
    </div>
    <div class="review-right">
      <RelationDetailCard
        v-if="selectedConcept"
        :concept="selectedConcept"
        :edges="edges"
        :all-nodes="nodes"
        :can-edit="canEdit"
        @review-edge="handleReviewEdge"
        @edit-edge="handleEditEdge"
      />
      <div v-else class="empty-hint">
        ← 选择一个概念查看关系
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ConceptReviewList from './ConceptReviewList.vue'
import RelationDetailCard from './RelationDetailCard.vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  qualityIssues: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['edit'])

const selectedConcept = ref(null)

function handleReviewEdge({ edgeId, status }) {
  emit('edit', [{ op: 'set_review_status', edge_id: edgeId, status }])
}

function handleEditEdge({ edgeId, source, target, type, strength }) {
  // 弹窗编辑 relation_type / strength，复用 edit API 的 update_edge
  // 简化 v1: 直接 emit update_edge 操作，由 KnowledgeTreePage 的 handleEdit 处理
  emit('edit', [{ op: 'update_edge', source, target, type, fields: { strength } }])
}
</script>

<style scoped>
.relation-review-panel { display: flex; height: 100%; }
.review-left { width: 260px; border-right: 1px solid rgba(255,255,255,0.08); flex-shrink: 0; overflow: hidden; }
.review-right { flex: 1; padding: 16px; overflow-y: auto; }
.empty-hint { display: flex; align-items: center; justify-content: center; height: 100%; color: rgba(255,255,255,0.3); }
</style>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/knowledge-tree/QualityBadge.vue frontend/src/components/knowledge-tree/ConceptReviewList.vue frontend/src/components/knowledge-tree/RelationDetailCard.vue frontend/src/components/knowledge-tree/RelationReviewPanel.vue
git commit -m "feat(knowledge-tree): relation review panel — concept list + detail card + quality badge"
```

**测试契约:**
1. 概念列表筛选与质量排序
   - 入口: `mount(ConceptReviewList, { props: { nodes, edges, qualityIssues } })` → 渲染概念列表
   - 反例: 错误实现不按质量优先级排序——有 HIGH 问题的概念不在最前
   - 边界: qualityIssues 为空（按名称排序）/ 多概念有不同严重度 / filterModule 过滤后为空
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptReviewList.test.js`
2. 关系操作发射（确认/驳回/编辑）
   - 入口: `mount(RelationDetailCard, { props: { concept, edges, allNodes, canEdit: true } })` → 点击确认/驳回/编辑按钮
   - 反例: 错误实现发射错误的 op 类型——确认发射 rejected 而非 teacher_reviewed
   - 边界: canEdit=false（按钮禁用）/ 选中概念无关系（空分组）/ 已审核的边点确认（幂等）
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/RelationDetailCard.test.js`

**审查清单:**
- ✓ 4 个组件职责单一（QualityBadge/ConceptReviewList/RelationDetailCard/RelationReviewPanel）
- ✓ 批量确认跳过已审核的边
- ✓ 低置信度（<0.7）高亮
- ✓ rejected 边显示删除线
- ✗ edge.id 在 Graph API 响应中缺失（Task 2 已补充 id 字段）

**边界条件:**
- 选中概念无关系（edges 全不关联）→ RelationDetailCard 显示空分组，不报错
- 概念列表为空（所有节点被过滤）→ 概念列表显示空状态
- qualityIssues 含某概念的 HIGH 问题 → 该概念排在列表最前，显示红色徽标

---

### Task 9: KnowledgeTreePage 集成 + 前端测试

**Files:**
- Modify: `frontend/src/pages/KnowledgeTreePage.vue`
- Create: `frontend/src/__tests__/knowledge-tree/RelationReviewPanel.test.js`

- [ ] **Step 1: KnowledgeTreePage 添加 tab 切换**

```vue
<!-- 修改 KnowledgeTreePage.vue 的 graph-side 区域 -->
    <div class="graph-side">
      <div class="view-tabs" v-if="canEdit">
        <n-tabs v-model:value="activeTab" type="segment" size="small">
          <n-tab-pane name="graph" tab="图谱视图" />
          <n-tab-pane name="review" tab="审查工作台" />
        </n-tabs>
      </div>
      <GraphPanel
        v-if="activeTab === 'graph'"
        :nodes="nodesWithMastery"
        :edges="graphData.edges"
        :selected-module="selectedModule"
        @node-click="handleNodeClick"
      />
      <RelationReviewPanel
        v-if="activeTab === 'review'"
        :nodes="nodesWithMastery"
        :edges="graphData.edges"
        :quality-issues="qualityIssues"
        :can-edit="canEdit"
        @edit="handleEdit"
      />
    </div>
```

script 部分补充:

```javascript
import { NTabs, NTabPane } from 'naive-ui'
import RelationReviewPanel from '../components/knowledge-tree/RelationReviewPanel.vue'

const activeTab = ref('graph')

// 在 init 或 handleModuleSelect 时加载质量巡检
async function init() {
  await loadGraph()
  if (canEdit.value) {
    await loadQuality(selectedModule.value)
  }
  // ... 其余不变
}

async function handleModuleSelect(mod) {
  showCards.value = false
  selectedModule.value = mod
  await loadGraph(mod)
  if (canEdit.value) {
    await loadQuality(mod)
  }
}
```

从 composable 解构新增 `qualityIssues, loadQuality`:

```javascript
const {
  navigationData, graphData, loading, selectedModule, moduleMastery,
  nodesWithMastery, qualityIssues, loadGraph, loadMastery, loadQuality, applyEdit,
} = useKnowledgeTree()
```

- [ ] **Step 2: 添加 view-tabs 样式**

```css
.view-tabs {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
```

- [ ] **Step 3: 写前端测试**

```javascript
// frontend/src/__tests__/knowledge-tree/RelationReviewPanel.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RelationReviewPanel from '../../components/knowledge-tree/RelationReviewPanel.vue'

const mockNodes = [
  { id: 'A', name: '概念A', module: 'M1', review_status: 'ai_draft', description: '描述A' },
  { id: 'B', name: '概念B', module: 'M1', review_status: 'teacher_reviewed', description: '描述B' },
]

const mockEdges = [
  { id: 1, source: 'A', target: 'B', type: 'prerequisite_hard', strength: 1.0, confidence: 0.5, review_status: 'ai_draft' },
]

describe('RelationReviewPanel', () => {
  it('renders concept list with nodes', () => {
    const wrapper = mount(RelationReviewPanel, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: [], canEdit: true },
    })
    expect(wrapper.text()).toContain('概念A')
    expect(wrapper.text()).toContain('概念B')
  })

  it('emits edit event after selecting concept and clicking confirm', async () => {
    const wrapper = mount(RelationReviewPanel, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: [], canEdit: true },
    })
    // 点击第一个概念触发选中
    const listItems = wrapper.findAll('.concept-item')
    expect(listItems.length).toBeGreaterThan(0)
    await listItems[0].trigger('click')
    await wrapper.vm.$nextTick()
    // 确认 RelationDetailCard 已渲染（不用 if guard，直接断言）
    const detail = wrapper.findComponent({ name: 'RelationDetailCard' })
    expect(detail.exists()).toBe(true)
    // 模拟确认操作
    detail.vm.$emit('review-edge', { edgeId: 1, status: 'teacher_reviewed' })
    expect(wrapper.emitted('edit')).toBeTruthy()
    expect(wrapper.emitted('edit')[0][0]).toEqual([
      { op: 'set_review_status', edge_id: 1, status: 'teacher_reviewed' },
    ])
  })
})
```

- [ ] **Step 4: 运行前端测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/`
Expected: PASS

- [ ] **Step 5: 运行全部前端测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部通过

- [ ] **Step 6: 运行全部后端测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q`
Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/KnowledgeTreePage.vue frontend/src/__tests__/knowledge-tree/
git commit -m "feat(knowledge-tree): integrate review panel into KnowledgeTreePage with tab switching"
```

**审查清单:**
- ✓ tab 切换在教师/管理员角色下可见
- ✓ 审查工作台的 edit 事件复用 handleEdit（同 GraphPanel）
- ✓ quality-check 在模块切换时刷新
- ✓ edge 响应包含 id 字段（审查操作依赖）
- ✓ 前端测试覆盖组件渲染和事件传递
- ✗ activeTab 在非教师角色下显示了审查 tab（v-if="canEdit" 已修复）

**测试契约:**
1. canEdit=false 时 tab 不可见
   - 入口: `mount(KnowledgeTreePage)` 配合 auth store mock（role=parent）→ DOM 不含 `.view-tabs`
   - 反例: 错误实现无条件渲染 tab——parent 角色也能看到审查工作台
   - 边界: canEdit=true（显示 tab）/ canEdit=false（隐藏 tab + 审查工作台）/ 角色切换后
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/RelationReviewPanel.test.js`
2. 模块切换触发 quality-check 刷新
   - 入口: `handleModuleSelect('M2')` → loadGraph('M2') + loadQuality('M2') 均被调用
   - 反例: 错误实现只刷新图谱不刷新质量检查——切换模块后工作台显示旧模块的问题
   - 边界: canEdit=false 时不调用 loadQuality / 模块从 M1 切到 all
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/RelationReviewPanel.test.js`

**边界条件:**
- 非教师角色（canEdit=false）→ 不显示 tab 切换，只显示 GraphPanel
- 切换模块时 quality-check 自动刷新 → 新模块的质量问题正确加载
- activeTab='review' 时切回 graph → GraphPanel 正常渲染（不丢状态）

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "edge review_status 状态机只允许 {ai_draft→teacher_reviewed, ai_draft→rejected, teacher_reviewed→published, teacher_reviewed→rejected, published→ai_draft, rejected→ai_draft} 6 种转移，其余组合返回 applied=0"
      verification: pending_test
    - id: INV-002
      statement: "include_draft=false 时，Graph API 响应的 nodes 不含 review_status=ai_draft 的节点，edges 不含 review_status 为 ai_draft 或 rejected 的边，且被过滤节点的关联边也被级联过滤"
      verification: pending_test
    - id: INV-003
      statement: "quality check Q1 孤立判定只看 prerequisite_hard 边（soft/bridge/contrast 不算），Q3 低置信度阈值为 confidence < 0.7 且 review_status=ai_draft"
      verification: pending_test
    - id: INV-004
      statement: "hard_in_count/hard_out_count 基于全量 edge 计算（不受 module 过滤和 include_draft 影响），external_hard_refs 仅 module 过滤时非 None"
      verification: pending_test

  counter_examples:
    - id: CE-001
      scenario: "get_graph 空实现——返回空 nodes/edges 但不计算 hard counts 和 external refs"
      tests_that_still_pass: "test_node_includes_description（如果只检查字段存在性不检查值）"
      mitigation: "test_node_hard_counts 用已知拓扑精确断言 hard_out_count=2/hard_in_count=1"
    - id: CE-002
      scenario: "edge set_review_status 忽略状态机——任意状态间可直接跳转"
      tests_that_still_pass: "test_edge_review_status_transition（ai_draft→teacher_reviewed 合法转移在错误实现下也通过）"
      mitigation: "test_edge_invalid_transition 断言 ai_draft→published 跳步时 applied=0"
    - id: CE-003
      scenario: "include_draft=false 只过滤 node 不过滤 edge——ai_draft 边仍返回"
      tests_that_still_pass: "test_include_draft_false_filters_nodes（只检查 node）"
      mitigation: "test_include_draft_false_filters_edges 独立检查边过滤 + 级联过滤"

  risk_modules:
    - module: src/edu_cloud/modules/knowledge_tree/service.py
      reason: "核心变更：get_graph v2 增强 + edge 状态机 + 发布过滤，3 个高风险语义集中在同一文件"
    - module: src/edu_cloud/modules/knowledge_tree/quality_service.py
      reason: "新增文件：BFS 连通分量 + 阈值判定（0.7/20%），算法正确性关键"
    - module: src/edu_cloud/modules/knowledge_tree/sync_service.py
      reason: "sync 链路变更：edge review_status 同步 + backwrite，数据一致性关键"
    - module: src/edu_cloud/modules/knowledge_tree/router.py
      reason: "API 契约变更：新增 include_draft 参数 + quality-check 端点"

  test_debt: []
```
