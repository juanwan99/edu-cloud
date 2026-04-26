<!-- pre-takeover: archived for history, not active spec -->
# 知识图谱层级重构实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将扁平 1233 节点图谱重构为 4 层导航结构（Module→BigConcept→Concept→Evidence），只展示 108 个 L1 概念作为图谱节点。

**Architecture:** knowledge.db 新增 big_concepts + concept_big_concept_map 表，L0 降级为 evidence。sync_service 只同步 L1 + BigConcept 到 PG。Graph API 返回显式 navigation + graph 结构。前端 TreeNavPanel 改为三级树。

**Tech Stack:** Python/FastAPI, SQLAlchemy, SQLite, PostgreSQL, Alembic, Vue 3, Naive UI, AntV G6

**Design:** `docs/plans/2026-04-09-knowledge-graph-restructure-design.md`

**Gate 1 修订记录（R2 → R3）：**

| Finding | 处置 |
|---------|------|
| F001 (HIGH code-bug) | Task 4 新增 mastery 过滤步骤 + 测试契约 + INV-005 |
| F002 (HIGH code-bug) | Task 2 PG 模型 + Task 3 sync 补 difficulty/bloom_level |
| F003 (HIGH code-bug) | 新增 Task 6 编辑 API 扩展 |
| F004 (HIGH behavior_change) | 合并为单 Batch 2，后端+前端原子切换 |
| F005 (HIGH test-gap) | 所有 Task 补齐 5 字段测试契约 + 边界条件 |
| F006 (MED test-gap) | INV-002 verification 改为专门测试 |

**R3 修订记录：**

| Finding | 处置 |
|---------|------|
| R3-F001 (HIGH design-concern) | accepted-risk: BigConcept 存 concept_graph_nodes，type discrimination 标准做法 → design.md §待处置 |
| R3-F002 (HIGH code-bug) | Task 1 补 aliases/evidence 迁移独立测试契约（契约 4-5） |
| R3-F003 (HIGH code-bug) | Task 2 补 reviewed_by/reviewed_at；Task 6 状态机转移 + 自动回退 |
| R3-F004 (MED code-bug) | Task 6 reorder 加 big_concept_id 作用域验证 |
| R3-F005 (MED code-bug) | Task 5 search 移到 service 层 + 补 description 字段 |
| R3-F006 (HIGH design-concern) | deferred: Contract Pack YAML 格式化 → design.md §待处置 |
| R3-F007 (MED test-gap) | contested: 已在 test_debt（deadline 2026-04-20） |

---

## Batch 1: 后端（Task 1-6）

### Task 1: knowledge.db Schema 变更 + 迁移脚本

**Files:**
- Create: `scripts/migrate_knowledge_hierarchy.py`
- Create: `tests/test_knowledge_tree/test_migration.py`
- Modify: `C:/Users/Administrator/edu-knowledge-base/knowledge.db`（运行迁移）

**测试契约:**
1. 迁移后 big_concepts 行数 = 11
   - 入口: `python scripts/migrate_knowledge_hierarchy.py --dry-run`
   - 反例: 错误实现会把 curriculum_requirements 每行都当 BigConcept（产出 175 个而非 11 个）
   - 边界: big_concept 为 NULL 的行 / 重复 big_concept 值 / 跨模块 big_concept
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_migration.py::test_big_concept_count -v`
2. concept_big_concept_map 覆盖 108 个 L1，is_primary 唯一约束生效
   - 入口: `python scripts/migrate_knowledge_hierarchy.py`
   - 反例: 错误实现会给多归属概念自动设 is_primary=TRUE（违反唯一索引）
   - 边界: 单归属 / 多归属（2 个） / 无 req_ids 的 ORPHAN
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_migration.py::test_map_coverage -v`
3. L0 重分类为 evidence
   - 入口: 迁移脚本 Step 4
   - 反例: 错误实现会删除 L0 行而非修改标签
   - 边界: L0 / L1 / L2 三种 level
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_migration.py::test_l0_reclassification -v`
4. aliases_json 从 L1 JSON 骨架迁移到 concepts 表（R3-F002）
   - 入口: `python scripts/migrate_knowledge_hierarchy.py`
   - 反例: 不读 JSON 骨架的 aliases 字段会导致 concepts.aliases_json 全部为 NULL，搜索别名功能失效
   - 边界: JSON 骨架无 aliases 字段 → NULL / aliases 为空数组 [] / aliases 含特殊字符
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_migration.py::test_aliases_migration -v`
5. evidence_ids_json 从 L1 JSON 骨架迁移到 concepts 表（R3-F002）
   - 入口: `python scripts/migrate_knowledge_hierarchy.py`
   - 反例: 不读 JSON 骨架的 l0_ids 字段会导致 concepts.evidence_ids_json 全部为 NULL，详情页 Evidence tab 永远空
   - 边界: JSON 骨架无 l0_ids 字段 → NULL / l0_ids 为空数组 / l0_ids 含不存在的 ID
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_migration.py::test_evidence_ids_migration -v`

**边界条件:**
- L1 概念的 req_ids 为空数组 → 无法推导 BigConcept，标记为 ORPHAN
- 同一 big_concept 文本出现在不同 module → 按 module 分别生成 BigConcept
- 迁移脚本重复运行 → INSERT OR IGNORE 保证幂等

- [ ] **Step 1:** 编写测试 — big_concepts 生成、map 覆盖率、L0 重分类、幂等性
- [ ] **Step 2:** 运行测试确认失败
- [ ] **Step 3:** 实现迁移脚本（5 步骤：建表→生成 BigConcept→构建 map→L0 重分类→初始化默认值）

迁移脚本核心逻辑：
```python
# Step 1: 建表（big_concepts + concept_big_concept_map + concepts 加列）
# Step 2: 从 curriculum_requirements.big_concept 聚合，生成 BC_{SUBJECT}_{MODULE}_{SLUG} ID
#   - 读 knowledge.db 的 curriculum_requirements 表
#   - GROUP BY big_concept, 取所属 module（从关联的 concepts 推导）
#   - 生成短名（截取 big_concept 文本的核心术语作为显示名）
# Step 3: 读 skeleton/L1/*.json 的 req_ids（多值）
#   - req_ids → curriculum_requirements.big_concept → big_concept_id
#   - 单归属: is_primary=TRUE
#   - 多归属: is_primary=FALSE（待人工）
# Step 4: UPDATE concepts SET knowledge_level='evidence' WHERE knowledge_level='L0'
# Step 5: 初始化 concepts 新列默认值（difficulty=3, bloom_level='understand', review_status='ai_draft'）
# 注意：Step 3 必须包含 aliases → aliases_json 和 l0_ids → evidence_ids_json 的迁移（R3-F002）
```

- [ ] **Step 4:** 运行测试确认通过
- [ ] **Step 5:** 在实际 knowledge.db 上运行迁移，验证清单：

| 检查项 | 预期 |
|--------|------|
| big_concepts 行数 | 11 |
| concept_big_concept_map 行数 | ~110 |
| is_primary=TRUE 行数 | ~106 |
| evidence 行数 | 1103 |

- [ ] **Step 6:** Commit

**审查清单:**
- ✓ BigConcept ID 使用稳定编码（BC_BIO_M{n}_{SLUG}），不用长文本当主键
- ✓ is_primary 默认 FALSE
- ✓ concept_big_concept_map 有部分唯一索引 ux_cbc_primary
- ✓ 迁移幂等（INSERT OR IGNORE）
- ✓ aliases_json 从 JSON 骨架迁移且有独立测试（R3-F002）
- ✓ evidence_ids_json 从 JSON 骨架迁移且有独立测试（R3-F002）
- ✗ 迁移后 big_concept 数量不等于 curriculum_requirements 的 DISTINCT big_concept 数量 → 说明聚合逻辑有误
- ✗ 有 L1 概念没有任何 map 条目 → 覆盖率不足

---

### Task 2: PG Models + Alembic Migration

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/models.py`
- Create: `alembic/versions/xxxx_add_knowledge_hierarchy.py`
- Modify: `tests/test_knowledge_tree/test_models.py`

**测试契约:**
1. ConceptGraphNode 新增列可正常读写（含 difficulty/bloom_level）
   - 入口: SQLAlchemy ORM add + query
   - 反例: 列名拼错会导致 AttributeError；遗漏 difficulty/bloom_level 会导致 Graph API 返回永远为空
   - 边界: NULL aliases_json / NULL review_status / NULL difficulty / NULL bloom_level
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_models.py -v`
2. ConceptBigConceptMap 外键和复合主键正确
   - 入口: SQLAlchemy ORM add + query + 违反约束
   - 反例: 缺 FK 约束会导致孤儿记录；单列主键会允许重复映射
   - 边界: 同一 concept_id+big_concept_id 重复插入 → IntegrityError
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_models.py::test_big_concept_map -v`

**边界条件:**
- difficulty 为 NULL → ORM 层正常读写，API 层返回 null
- bloom_level 为非法枚举值 → PG 无 CHECK 约束（应用层校验），存储不报错
- Alembic downgrade → 所有新增列和表被清理

- [ ] **Step 1:** ConceptGraphNode 模型加列

```python
# models.py — ConceptGraphNode 新增列
subject: Mapped[str | None] = mapped_column(String(30))
node_type: Mapped[str] = mapped_column(String(20), default="concept")  # concept | big_concept
display_order: Mapped[int] = mapped_column(Integer, default=0)
review_status: Mapped[str | None] = mapped_column(String(20))
reviewed_by: Mapped[str | None] = mapped_column(String(100))           # R3-F003: 审核人
reviewed_at: Mapped[str | None] = mapped_column(String(30))            # R3-F003: 审核时间 ISO
aliases_json: Mapped[str | None] = mapped_column(Text)
difficulty: Mapped[int | None] = mapped_column(Integer)                # F002: 1-5 教师标签
bloom_level: Mapped[str | None] = mapped_column(String(20))            # F002: 记忆/理解/应用/分析/评价/创造
```

- [ ] **Step 2:** 新增 BigConceptMap PG 模型（存储从 knowledge.db 同步的映射）

```python
class ConceptBigConceptMap(Base):
    __tablename__ = "concept_big_concept_map"
    concept_id: Mapped[str] = mapped_column(String(64), ForeignKey("concept_graph_nodes.id"), primary_key=True)
    big_concept_id: Mapped[str] = mapped_column(String(64), ForeignKey("concept_graph_nodes.id"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(default=False)
```

- [ ] **Step 3:** 生成 Alembic migration

```bash
cd C:/Users/Administrator/edu-cloud
python -m alembic revision --autogenerate -m "add knowledge hierarchy columns"
```

- [ ] **Step 4:** 编写测试（模型读写含 difficulty/bloom_level、约束验证）
- [ ] **Step 5:** 运行 migration + 测试
- [ ] **Step 6:** Commit

**审查清单:**
- ✓ subject 列存在
- ✓ node_type 列存在
- ✓ difficulty 列存在（Integer, nullable）
- ✓ bloom_level 列存在（String(20), nullable）
- ✓ Alembic migration 可 upgrade + downgrade
- ✗ ConceptGraphNode.id 长度不够存 BigConcept ID → 检查 String(64) 是否足够

---

### Task 3: sync_service 适配

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/sync_service.py`
- Modify: `tests/test_knowledge_tree/test_sync.py`
- Modify: `tests/test_knowledge_tree/test_sync_startup.py`

**测试契约:**
1. 同步后只有 L1 概念 + BigConcept 节点，无 L0/evidence
   - 入口: `sync_knowledge_on_startup(db)`
   - 反例: 不加 knowledge_level 过滤会同步全部 1233 个
   - 边界: knowledge.db 中无 big_concepts 表（未迁移） / big_concepts 为空
   - 回归: 原有同步行为（1233 节点）被替代
   - 命令: `pytest tests/test_knowledge_tree/test_sync.py -v`
2. concept_big_concept_map 同步到 PG
   - 入口: `sync_knowledge_on_startup(db)`
   - 反例: 只同步 nodes/edges 不同步 map 会导致 navigation 构建失败
   - 边界: map 为空 / 概念无 primary 归属
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_sync_startup.py -v`
3. difficulty/bloom_level 同步到 PG（F002）
   - 入口: `sync_knowledge_on_startup(db)`
   - 反例: 不携带 difficulty/bloom_level 会导致 PG 中字段永远为 NULL，API 返回空
   - 边界: difficulty 为 NULL（未设置）/ bloom_level 为 NULL
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_sync.py::test_sync_difficulty_bloom -v`

**边界条件:**
- knowledge.db 没有 big_concepts 表（旧版未迁移）→ 跳过 BigConcept 同步，只同步 L1 concepts
- big_concepts 表存在但为空 → 正常同步，navigation 无 BigConcept 层
- concept_big_concept_map 中有 concept_id 指向不存在的 L1 → 跳过该条
- concepts 表无 difficulty 列（旧版未迁移）→ 跳过该字段，PG 保持 NULL

- [ ] **Step 1:** 编写测试 — L1-only 过滤、BigConcept 同步、map 同步、difficulty/bloom 同步
- [ ] **Step 2:** 运行测试确认失败
- [ ] **Step 3:** 修改 `_read_knowledge_db()` 过滤逻辑

```python
# 核心变更：
# 1. concepts 查询加 WHERE knowledge_level = 'L1'
# 2. 新增读取 big_concepts 表（带容错：表不存在则返回空）
# 3. 新增读取 concept_big_concept_map 表
# 4. 携带新字段：subject, node_type, display_order, review_status, aliases_json
# 5. 携带 difficulty, bloom_level（带容错：列不存在则默认 NULL）  ← F002
```

- [ ] **Step 4:** 修改 `_sync_graph()` 写入逻辑

```python
# 核心变更：
# 1. 删除现有 ConceptBigConceptMap 数据
# 2. 先写 BigConcept 节点（node_type='big_concept'）
# 3. 再写 L1 Concept 节点（node_type='concept'，含 difficulty/bloom_level）
# 4. 写 edges（不变）
# 5. 写 concept_big_concept_map
```

- [ ] **Step 5:** 运行测试确认通过
- [ ] **Step 6:** Commit

**审查清单:**
- ✓ `_read_knowledge_db` 只读 L1 concepts
- ✓ BigConcept 节点的 node_type = 'big_concept'
- ✓ 旧版 knowledge.db（无 big_concepts 表）不崩溃
- ✓ difficulty/bloom_level 从 knowledge.db 读取并写入 PG（F002）
- ✓ 旧版 knowledge.db 无 difficulty 列时不崩溃（容错）
- ✗ sync 后 PG 节点数与 knowledge.db 的 L1+BigConcept 数不一致

---

### Task 4: Graph API — navigation + graph 响应 + mastery 过滤

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/schemas.py`
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py`（get_graph + get_mastery）
- Modify: `src/edu_cloud/modules/knowledge_tree/router.py`
- Modify: `tests/test_knowledge_tree/test_router.py`
- Modify: `tests/test_knowledge_tree/test_service.py`

**测试契约:**
1. GET /graph 返回 navigation + graph 结构
   - 入口: `GET /api/v1/knowledge-tree/graph?module=all`
   - 反例: 返回旧的扁平 {nodes, edges} 会导致前端 navigation 字段为 undefined
   - 边界: module=all / module=M1 / module=INVALID
   - 回归: 旧响应格式被替代
   - 命令: `pytest tests/test_knowledge_tree/test_router.py::test_get_graph -v`
2. navigation 从 big_concepts + map 动态构建
   - 入口: `GET /api/v1/knowledge-tree/graph`
   - 反例: 从平铺节点拼装会在 map 不完整时丢失概念
   - 边界: BigConcept 下无概念 / 概念无 primary 归属（fallback 到第一个 map 条目）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_router.py::test_navigation_structure -v`
3. graph.nodes 包含 difficulty/bloom_level 字段（F002）
   - 入口: `GET /api/v1/knowledge-tree/graph`
   - 反例: schemas.py 遗漏 difficulty/bloom_level 会导致字段被 Pydantic 过滤掉
   - 边界: difficulty=NULL / bloom_level=NULL → JSON 返回 null
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_router.py::test_graph_node_fields -v`
4. get_mastery() 只聚合 node_type='concept' 的节点（F001）
   - 入口: `GET /api/v1/knowledge-tree/mastery?student_id=S001`
   - 反例: 不加 node_type 过滤会混入 BigConcept 节点，掌握度、模块均值、Top 5 薄弱概念全部失真
   - 边界: 无 BigConcept 节点（空 sync）/ 全部是 BigConcept（极端）
   - 回归: 现有 mastery 测试仍然通过（node_type='concept' 的节点集合 = 原有全部节点集合，在 BigConcept 引入前）
   - 命令: `pytest tests/test_knowledge_tree/test_service.py::test_get_mastery_excludes_big_concepts -v`

**边界条件:**
- module=INVALID → 返回空 navigation + 空 graph.nodes
- BigConcept 下 concept_ids 为空 → navigation 中该 BigConcept 仍显示（children=[]）
- 概念有多个 map 条目但无 is_primary=TRUE → big_concept_id 取第一个 map 条目的 big_concept_id

- [ ] **Step 1:** 编写测试 — navigation 结构、graph.nodes 只含 L1、module 过滤、mastery 排除 BigConcept、graph node 含 difficulty/bloom_level
- [ ] **Step 2:** 运行测试确认失败
- [ ] **Step 3:** 更新 schemas.py

```python
# 新增 response models
class BigConceptNav(BaseModel):
    id: str
    name: str
    concept_ids: list[str]

class ModuleNav(BaseModel):
    id: str
    name: str
    big_concepts: list[BigConceptNav]

class GraphNodeResponse(BaseModel):  # 扩展
    id: str
    name: str
    level: str
    module: str
    big_concept_id: str | None = None
    aliases: list[str] = []
    review_status: str | None = None
    difficulty: int | None = None        # F002
    bloom_level: str | None = None       # F002

class NewGraphResponse(BaseModel):
    navigation: list[ModuleNav]
    graph: GraphResponse  # 复用现有 {nodes, edges}
```

- [ ] **Step 4:** 修改 service.py `get_graph()` — 构建 navigation + 过滤 L1 节点

```python
# 核心逻辑：
# 1. 查询 node_type='big_concept' 的节点 → 构建 module→BigConcept 映射
# 2. 查询 ConceptBigConceptMap(is_primary=True) → 构建 BigConcept→[concept_ids]
# 3. 查询 node_type='concept' 的节点 → graph.nodes（携带新字段含 difficulty/bloom_level）
# 4. 查询 edges（不变）
# 5. 组装 navigation 和 graph
```

- [ ] **Step 5:** 修改 service.py `get_mastery()` — 加 node_type 过滤（F001）

```python
# 在 get_mastery() 的节点查询中加过滤：
node_q = sa.select(ConceptGraphNode).where(
    ConceptGraphNode.node_type == "concept"  # F001: 排除 big_concept
)
```

- [ ] **Step 6:** 修改 router.py response_model
- [ ] **Step 7:** 运行测试确认通过
- [ ] **Step 8:** Commit

**审查清单:**
- ✓ navigation 是显式字段，不从 nodes 临时拼
- ✓ graph.nodes 只含 node_type='concept'（L1）
- ✓ big_concept_id 取 is_primary=TRUE 的归属
- ✓ module 过滤同时作用于 navigation 和 graph
- ✓ get_mastery() 查询加 node_type='concept' 过滤（F001）
- ✓ graph.nodes 每个节点携带 difficulty/bloom_level（F002）
- ✗ 响应中出现 node_type='big_concept' 的节点在 graph.nodes 里 → BigConcept 不应是图节点
- ✗ mastery 返回中包含 big_concept ID → 掌握度失真

---

### Task 5: Detail API + Search API + Evidence

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/detail_service.py`
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py`（新增 search_concepts，R3-F005）
- Modify: `src/edu_cloud/modules/knowledge_tree/router.py`（新增 search 端点，薄路由委托 service）
- Modify: `tests/test_knowledge_tree/test_node_detail_api.py`
- Create: `tests/test_knowledge_tree/test_search.py`

**测试契约:**
1. 节点详情包含 evidence 段
   - 入口: `GET /api/v1/knowledge-tree/graph/{node_id}/detail`
   - 反例: 不读 evidence_ids_json 会返回空 evidence 列表
   - 边界: evidence_ids_json 为 NULL / 引用不存在的 L0 ID / evidence_ids_json 为空数组 "[]"
   - 回归: 现有 DA/课标/教材/真题功能不受影响
   - 命令: `pytest tests/test_knowledge_tree/test_node_detail_api.py -v`
2. 搜索 API 匹配 name + aliases + description（R3-F005 补 description）
   - 入口: `GET /api/v1/knowledge-tree/search?q=质膜`
   - 反例: 只搜 name 不搜 aliases_json/description 会漏掉别名和描述中的匹配
   - 边界: 空查询（min_length=1 拦截）/ 单字符 "细" / 仅 description 中匹配的关键词
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_search.py -v`
3. 搜索 API 只返回 concept 节点
   - 入口: `GET /api/v1/knowledge-tree/search?q=细胞`
   - 反例: 不加 node_type 过滤会返回 BigConcept 节点
   - 边界: 查询词同时匹配 concept 和 big_concept 名称
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_search.py::test_search_excludes_big_concepts -v`

**边界条件:**
- evidence_ids_json 为 NULL → evidence 段返回空列表 []
- evidence_ids_json 含不存在的 ID → 跳过该 ID，不报错
- 搜索 q 参数长度 = 1 → 正常搜索，返回匹配结果（可能较多）
- 搜索无匹配 → 返回空列表 []

- [ ] **Step 1:** 编写测试 — evidence 返回、search 别名匹配、search 空查询、search 排除 big_concept
- [ ] **Step 2:** 运行测试确认失败
- [ ] **Step 3:** detail_service.py 追加 evidence 段

```python
# 在 get_node_detail() 中，读取 concepts.evidence_ids_json
# 解析 JSON 数组，查询 concepts 表中 id IN (evidence_ids) 的行
# 返回 [{"id": "...", "text": row["name"]}]
```

- [ ] **Step 4:** service.py 新增 search_concepts() 函数（R3-F005: 搜索逻辑在 service 层，不在 router）

```python
# service.py
async def search_concepts(db: AsyncSession, q: str, limit: int = 20) -> list[dict]:
    """搜索知识点（name + aliases + description）。R3-F005: 补 description 字段。"""
    from sqlalchemy import or_
    pattern = f"%{q}%"
    results = await db.execute(
        sa.select(ConceptGraphNode)
        .where(ConceptGraphNode.node_type == "concept")
        .where(or_(
            ConceptGraphNode.name.ilike(pattern),
            ConceptGraphNode.aliases_json.ilike(pattern),
            ConceptGraphNode.description.ilike(pattern),  # R3-F005: 设计要求搜 description
        ))
        .limit(limit)
    )
    return [{"id": n.id, "name": n.name, "module": n.primary_module,
             "aliases": json.loads(n.aliases_json) if n.aliases_json else []}
            for n in results.scalars()]
```

- [ ] **Step 5:** router.py 新增 search 端点（薄路由，委托 service）

```python
@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current=Depends(get_current_user),
):
    return await service.search_concepts(db, q)
```

- [ ] **Step 5:** 运行测试确认通过
- [ ] **Step 6:** Commit

**审查清单:**
- ✓ evidence 段从 evidence_ids_json 读取，不硬编码
- ✓ search 逻辑在 service.py 中，router.py 是薄路由（R3-F005）
- ✓ search 同时匹配 name、aliases_json 和 description（R3-F005）
- ✓ search 需认证（get_current_user）
- ✓ search 只返回 node_type='concept'
- ✗ search 查询逻辑写在 router.py 中 → 违反薄路由架构
- ✗ search 返回 big_concept 节点 → 只搜 node_type='concept'

---

### Task 6: 编辑 API 扩展（F003）

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py`（apply_edits + _NODE_UPDATABLE + backwrite）
- Create: `tests/test_knowledge_tree/test_edit_extended.py`

> **F003 处置**：设计声明了 update_concept/set_review_status/reorder 三个新编辑操作。
> 现有 apply_edits() 已支持 update_node op，只需扩展 _NODE_UPDATABLE 白名单 + 新增 set_review_status/reorder op。

**测试契约:**
1. update_node 支持 difficulty/bloom_level/aliases_json/review_status 字段
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`[{"op": "update_node", "id": "...", "fields": {"difficulty": 4, "bloom_level": "apply"}}]`
   - 反例: _NODE_UPDATABLE 不含新字段会导致 fields 被静默过滤，返回 applied=0，UI 保存无效果
   - 边界: difficulty 超出 1-5 范围 / bloom_level 非法值 / aliases_json 非法 JSON
   - 回归: 已有 update_node(name/description) 行为不变
   - 命令: `pytest tests/test_knowledge_tree/test_edit_extended.py::test_update_concept_fields -v`
2. set_review_status 操作走状态机 + 审计字段（R3-F003）
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`[{"op": "set_review_status", "id": "...", "status": "teacher_reviewed", "user_id": "U001"}]`
   - 反例: 直接 UPDATE review_status 会绕过状态机校验，允许 ai_draft→published 跳跃；不写 reviewed_by/reviewed_at 无法追溯
   - 边界: 非法状态转移（ai_draft→published 应拒绝）/ 已是目标状态 / 节点不存在 / user_id 缺失
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_edit_extended.py::test_set_review_status -v`
3a. published 概念被内容修改后自动回退 ai_draft（R3-F003）
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`[{"op": "update_node", "id": "...", "fields": {"name": "新名称"}}]`（节点 review_status=published）
   - 反例: 不回退会导致修改后的内容仍标记为 published，教师审核形同虚设
   - 边界: 修改 display_order（非内容字段）不应触发回退 / 修改 name/description/aliases 应触发回退
   - 回归: ai_draft/teacher_reviewed 状态的节点修改不受影响
   - 命令: `pytest tests/test_knowledge_tree/test_edit_extended.py::test_published_auto_rollback -v`
4. reorder 操作调整 display_order（作用域绑定 BigConcept，R3-F004）
   - 入口: `POST /api/v1/knowledge-tree/edit` body=`[{"op": "reorder", "big_concept_id": "BC_...", "concept_ids": ["C1","C2","C3"]}]`
   - 反例: 不验证 big_concept_id 作用域会导致跨 BigConcept 串写排序，一个错误请求污染其他组的排列
   - 边界: concept_ids 包含不属于该 BigConcept 的概念 → 该 ID 被忽略 / concept_ids 为空列表 / big_concept_id 不存在
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_edit_extended.py::test_reorder -v`

**边界条件:**
- update_node 传入不在白名单的字段（如 id/node_type）→ 被静默过滤
- set_review_status 传入不存在的 node_id → applied 不增加
- reorder 传入空 concept_ids → 无操作

- [ ] **Step 1:** 编写测试 — update_node 扩展字段、set_review_status、reorder、回写验证
- [ ] **Step 2:** 运行测试确认失败
- [ ] **Step 3:** 扩展 `_NODE_UPDATABLE` 白名单

```python
_NODE_UPDATABLE = {"name", "description", "difficulty", "bloom_level", "aliases_json", "display_order"}
# 注意：review_status 不在白名单中（R3-F003），必须通过 set_review_status op 走状态机
```

- [ ] **Step 4:** 在 apply_edits() 新增 set_review_status 和 reorder 操作

```python
elif op == "set_review_status":
    # R3-F003: 状态机校验 + 审计字段
    valid_transitions = {
        "ai_draft": {"teacher_reviewed"},
        "teacher_reviewed": {"published", "ai_draft"},
        "published": {"ai_draft"},  # 显式回退
    }
    new_status = op_data.get("status")
    node = await db.get(ConceptGraphNode, op_data["id"])
    if node and new_status in valid_transitions.get(node.review_status or "ai_draft", set()):
        node.review_status = new_status
        node.reviewed_by = op_data.get("user_id")  # 由 router 从 current_user 注入
        node.reviewed_at = datetime.now().isoformat()
        applied += 1

elif op == "update_node":
    # ... 原有逻辑 ...
    # R3-F003: published 概念被内容修改后自动回退到 ai_draft
    content_fields = fields.keys() & {"name", "description", "aliases_json", "difficulty", "bloom_level"}
    if content_fields:
        node = await db.get(ConceptGraphNode, op_data["id"])
        if node and node.review_status == "published":
            node.review_status = "ai_draft"
            node.reviewed_by = None
            node.reviewed_at = None

elif op == "reorder":
    # R3-F004: 作用域验证 — 只更新属于指定 BigConcept 的概念
    bc_id = op_data.get("big_concept_id")
    valid_cids = set()
    if bc_id:
        maps = await db.execute(
            sa.select(ConceptBigConceptMap.concept_id)
            .where(ConceptBigConceptMap.big_concept_id == bc_id)
        )
        valid_cids = {r[0] for r in maps}
    for idx, cid in enumerate(op_data.get("concept_ids", [])):
        if not bc_id or cid in valid_cids:  # 无 bc_id 时全量更新（向后兼容）
            await db.execute(
                sa.update(ConceptGraphNode)
                .where(ConceptGraphNode.id == cid)
                .values(display_order=idx)
            )
    applied += 1
```

- [ ] **Step 5:** 扩展 backwrite_to_knowledge_db() 处理新操作
- [ ] **Step 6:** 运行测试确认通过
- [ ] **Step 7:** Commit

**审查清单:**
- ✓ _NODE_UPDATABLE 包含 difficulty/bloom_level/aliases_json/display_order（不含 review_status）
- ✓ review_status 不在 _NODE_UPDATABLE 中，必须通过 set_review_status 走状态机（R3-F003）
- ✓ set_review_status 校验状态转移合法性 + 写 reviewed_by/reviewed_at（R3-F003）
- ✓ update_node 修改 published 概念的内容字段时自动回退 review_status 到 ai_draft（R3-F003）
- ✓ reorder 使用 big_concept_id 做作用域验证（R3-F004）
- ✓ 新操作有 knowledge.db 回写
- ✗ update_node 允许修改 node_type → node_type 不应在 _NODE_UPDATABLE 中
- ✗ reorder 的 concept_ids 包含不属于指定 BigConcept 的 ID → 应被忽略

---

## Batch 2: 前端原子切换（Task 7-10）

> **F004 处置**：Graph API 格式变更是 breaking change。后端 API 切换（Batch 1 Task 4-6）和前端适配（Task 7-9）
> 在连续批次完成，部署时一次性上线。不存在"后端已切新格式但前端未适配"的中间态。

### Task 7: API 客户端适配 + TreeNavPanel 三级树改造

**Files:**
- Modify: `frontend/src/api/knowledgeTree.js`
- Modify: `frontend/src/components/knowledge-tree/useKnowledgeTree.js`
- Modify: `frontend/src/components/knowledge-tree/TreeNavPanel.vue`

**测试契约:**
1. useKnowledgeTree.loadGraph() 正确解析 { navigation, graph } 结构
   - 入口: `loadGraph('all')` → `navigationData.value` 和 `graphData.value` 分别赋值
   - 反例: 仍读 resp.data 作为 graph 会导致 nodes/edges 为 undefined
   - 边界: navigation 为空数组 / graph.nodes 为空数组
   - 回归: graphData 的消费方（GraphPanel/NodeDetailDrawer）不受影响
   - 命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
2. TreeNavPanel 从 navigation 字段渲染三级树
   - 入口: 组件 props 接收 navigation 数组
   - 反例: 仍从 nodes 平铺拼装会在新数据格式下渲染空树
   - 边界: navigation 为 null/undefined → 渲染空树 / BigConcept 下无概念 → 空 children
   - 回归: 搜索/选中/展开交互保持
   - 命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
3. 搜索框实时过滤 + 高亮
   - 入口: 用户在搜索框输入关键词
   - 反例: 只过滤顶层不展开子树会导致匹配的叶子节点不可见
   - 边界: 搜索词匹配 BigConcept 名称 → 展开该组 / 清空搜索 → 恢复原始折叠状态
   - 回归: N/A
   - 命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`

**边界条件:**
- API 返回 navigation=[] → TreeNavPanel 显示空状态提示
- BigConcept 下 concept_ids 全部不在 graph.nodes 中 → 显示 "(无匹配节点)"
- 搜索输入快速变化（防抖 300ms）→ 不发送密集请求

- [ ] **Step 1:** knowledgeTree.js 新增 search API

```javascript
export const searchConcepts = (q) =>
  client.get('/knowledge-tree/search', { params: { q } })
```

- [ ] **Step 2:** useKnowledgeTree.js 适配新响应格式

```javascript
// loadGraph() 改为解析 { navigation, graph } 结构
async function loadGraph(module = 'all') {
  selectedModule.value = module
  const resp = await getGraph(module)
  navigationData.value = resp.data.navigation  // 新增
  graphData.value = resp.data.graph            // 改：从 resp.data 改为 resp.data.graph
}
```

- [ ] **Step 3:** 重写 TreeNavPanel treeData computed — 从 navigation 字段构建三级树

```javascript
const treeData = computed(() => {
  // 直接从 props.navigation 渲染，不再从 nodes 平铺拼装
  return (props.navigation || []).map(mod => ({
    key: mod.id,
    label: mod.name,
    children: mod.big_concepts.map(bc => ({
      key: bc.id,
      label: bc.name,
      children: bc.concept_ids.map(cid => {
        const node = nodeMap.value[cid]
        return {
          key: cid,
          label: node?.name || cid,
          isLeaf: true,
          reviewStatus: node?.review_status,
        }
      }),
    })),
  }))
})
```

- [ ] **Step 2:** 添加搜索框 — 实时过滤 + 高亮
- [ ] **Step 3:** 添加审核状态图标 renderSuffix
- [ ] **Step 6:** 运行前端测试

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
```

- [ ] **Step 7:** Commit

**审查清单:**
- ✓ loadGraph 解析 { navigation, graph } 而非旧的 { nodes, edges }
- ✓ 从 navigation 字段渲染，不从 nodes 拼装
- ✓ 搜索匹配时展开到匹配节点的路径
- ✗ 仍然引用旧的 moduleMastery/nodesWithMastery 作为 tree 数据源
- ✗ loadGraph 仍读 resp.data 作为 graph（旧格式）

---

### Task 8: GraphPanel 模块级渲染

**Files:**
- Modify: `frontend/src/components/knowledge-tree/GraphPanel.vue`

**测试契约:**
1. 节点渲染只使用 graph.nodes（无 BigConcept/L0 节点）
   - 入口: GraphPanel props 接收 graphData（新格式 {nodes, edges}）
   - 反例: 仍用 LEVEL_SIZES 按 level 分大小会在只有 L1 节点时渲染单调
   - 边界: graph.nodes 为空 → 显示空图提示 / 单个节点 → 不崩溃
   - 回归: 节点点击/高亮/tooltip 交互保持
   - 命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
2. 力导向参数适配 ~35 节点/模块
   - 入口: G6 图实例化
   - 反例: 保持旧参数（优化 1200 节点）会导致 35 个节点过度分散
   - 边界: module=all 时节点数 ~108 / module=M1 时 ~35 / 全空
   - 回归: N/A
   - 命令: 手动验证（视觉布局无自动化测试）

**边界条件:**
- graph.nodes 为空 → 显示 "当前模块暂无知识点" 空状态
- 节点数 = 1 → 居中显示，不启动力仿真
- 节点 difficulty/bloom_level 为 null → 使用默认颜色/尺寸

- [ ] **Step 1:** 移除 LEVEL_SIZES（不再有 L0 节点），统一节点尺寸逻辑

```javascript
// 节点大小 = DA 数量（从 mastery 数据获取）
// 颜色 = review_status（教师模式）或 mastery_state（学生模式）
```

- [ ] **Step 2:** 调优力导向参数 — 节点数从 ~1200 降到 ~35/模块

```javascript
// 降低 nodeStrength、linkDistance 等参数
// 35 个节点不需要激进的排斥力
```

- [ ] **Step 3:** 运行前端测试
- [ ] **Step 4:** Commit

**审查清单:**
- ✓ 移除 LEVEL_SIZES，使用统一尺寸逻辑
- ✓ 力导向参数适配小规模节点
- ✗ 仍引用 LEVEL_SIZES 或 knowledge_level 分大小

---

### Task 9: NodeDetailDrawer 扩展

**Files:**
- Modify: `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue`

**测试契约:**
1. Evidence tab 展示教材证据列表
   - 入口: 用户点击概念节点 → 抽屉打开 → 切换到 "教材证据" tab
   - 反例: 不读 detail.evidence 会导致 tab 永远显示 "暂无教材证据"
   - 边界: evidence 为空列表 → 显示空状态 / evidence 数量 > 20 → 正常滚动
   - 回归: 现有 DA/课标/教材/真题 tab 不受影响
   - 命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
2. 编辑表单支持 difficulty/bloom_level/review_status
   - 入口: 教师点击编辑 → 修改难度/布鲁姆 → 保存
   - 反例: 编辑表单未绑定 difficulty/bloom_level 字段会导致保存时这两个字段被清空
   - 边界: difficulty 未设置（null）→ 显示空 rate / bloom_level 未设置 → select 无选中项
   - 回归: 已有 name/description 编辑不受影响
   - 命令: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`

**边界条件:**
- evidence 列表项文本过长（L0 原子事实可能是整句）→ CSS 自动换行
- 审核按钮在无 EDIT_KNOWLEDGE_TREE 权限时隐藏（canEdit=false）
- 快速切换节点时（点击 A→立即点击 B）→ 不显示 A 的 detail

- [ ] **Step 1:** 新增 Evidence tab（教材证据列表）

```vue
<n-tab-pane name="evidence" tab="教材证据">
  <div v-for="ev in detail.evidence" :key="ev.id" class="detail-item">
    {{ ev.text }}
  </div>
  <n-empty v-if="!detail.evidence?.length" description="暂无教材证据" />
</n-tab-pane>
```

- [ ] **Step 2:** 编辑表单扩展 — 难度/布鲁姆/审核状态

```vue
<n-form-item label="难度">
  <n-rate :value="editForm.difficulty" @update:value="v => editForm.difficulty = v" :count="5" />
</n-form-item>
<n-form-item label="认知层级">
  <n-select v-model:value="editForm.bloom_level"
    :options="bloomOptions" />
</n-form-item>
<n-button v-if="canEdit" size="small" @click="handleReview">
  {{ detail.concept.review_status === 'ai_draft' ? '标记已审核' : '审核状态' }}
</n-button>
```

- [ ] **Step 3:** 运行前端测试
- [ ] **Step 4:** Commit

**审查清单:**
- ✓ evidence tab 展示 L0 教材证据
- ✓ 编辑表单含难度/布鲁姆/审核
- ✓ 审核按钮根据 canEdit 权限显示
- ✗ evidence tab 允许编辑 L0 内容（L0 由数据管线管理，不可手动改）

---

### Task 10: 端到端验证 + CLAUDE.md 更新

**Files:**
- Modify: `CLAUDE.md`（知识树端点和模型描述更新）

- [ ] **Step 1:** 端到端验证

```
登录（t_yw_001/123456）→ 侧栏"知识图谱" → 看到三级树导航
→ 展开 M1 → 看到大概念分组 → 点击"细胞学说" → 图谱高亮 + 详情抽屉
→ 详情含 DA(1) + 课标 + 教材定位 + 教材证据(10条) + 审核状态
→ 编辑：修改难度→保存→刷新→值保持
→ 搜索"质膜" → 树过滤到匹配节点
```

- [ ] **Step 2:** 运行全量后端测试

```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```

- [ ] **Step 3:** 运行前端测试

```bash
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run
```

- [ ] **Step 4:** 更新 CLAUDE.md
  - Graph API 响应格式变更说明（navigation + graph）
  - 新增 Search API 端点
  - 编辑 API 新增 set_review_status/reorder 操作
  - knowledge_tree 模块描述更新（三级导航、evidence 层）
  - concept_graph_nodes 模型新增列（difficulty/bloom_level/...）

- [ ] **Step 5:** Commit

**审查清单:**
- ✓ 端到端流程可走通
- ✓ 全量测试通过
- ✓ CLAUDE.md 已同步更新

---

## Contract Pack

### invariants

1. **INV-001: L1 ID 不变** — 108 个 L1 概念的 id（如 `BIO_SR_CP_M1_CELL_THEORY`）在迁移前后完全一致，不重命名、不拆分、不合并。
   - verification: `test_migration.py::test_l1_ids_unchanged` — 迁移前后 SELECT id FROM concepts WHERE knowledge_level='L1' 集合相等。
2. **INV-002: DA→concept 映射不变** — `da_knowledge_point_map` 表不被修改，BKT 掌握度历史可连续。
   - verification: `test_service.py::test_get_mastery_excludes_big_concepts` — sync 后 mastery 查询只聚合 node_type='concept' 节点，da_knowledge_point_map 行数和内容不变。（F006 更正：原引用不存在的 test_sync.py mastery 测试）
3. **INV-003: concept_relations 335 条不变** — 边集在迁移前后行数和内容完全一致。
   - verification: `test_migration.py::test_relations_unchanged` — 迁移前后 SELECT COUNT(*) 和 checksum 一致。
4. **INV-004: Graph API 只返回 L1 节点** — `graph.nodes` 中所有条目的 `node_type='concept'`，不包含 BigConcept/evidence。
   - verification: `test_router.py::test_graph_nodes_l1_only`。
5. **INV-005: Mastery 不含 BigConcept** — `get_mastery()` 返回的 concept_mastery 列表中不出现 BigConcept ID。（F001 新增）
   - verification: `test_service.py::test_get_mastery_excludes_big_concepts`。

### counter_examples

1. **CE-001: 迁移脚本意外修改 L0 的 name/id** — 错误实现可能在 UPDATE 时波及 L0 行（如无 WHERE 条件）。
   - tests_that_still_pass: 只检查 L1 行数的测试会通过，因为 L1 没变。
   - mitigation: `test_migration.py::test_l0_only_level_changed` — 验证 L0 行只有 knowledge_level 被改为 'evidence'，name/id/description 不变。
2. **CE-002: navigation 和 graph 不一致** — navigation 显示概念属于 BC_A，但 graph.nodes 中该概念的 big_concept_id 是 BC_B（primary 和 map 不同步）。
   - tests_that_still_pass: 分别测 navigation 和 graph 的测试各自通过，但交叉校验会失败。
   - mitigation: `test_router.py::test_navigation_graph_consistency` — 对每个 navigation.concept_ids 中的 id，验证对应 node 的 big_concept_id 一致。
3. **CE-003: mastery 混入 BigConcept 导致失真** — BigConcept 节点无 DA 映射，混入后均值被拉低。（F001 新增）
   - tests_that_still_pass: 只看 mastery 返回非空的测试会通过（多了几个零值条目但不为空）。
   - mitigation: `test_service.py::test_get_mastery_excludes_big_concepts` — 插入 BigConcept 节点后验证 mastery 结果不包含其 ID。

### risk_modules

| 模块 | 风险级别 | 说明 |
|------|----------|------|
| `knowledge_tree/sync_service.py` | HIGH | 同步逻辑重写，影响启动流程 |
| `knowledge_tree/service.py` | HIGH | get_graph 返回格式变更 + get_mastery 过滤变更 + 编辑 API 扩展 |
| `knowledge_tree/schemas.py` | HIGH | GraphResponse 结构变更，前端强依赖 |
| `knowledge_tree/router.py` | MED | 新增 search 端点，response_model 变更 |
| `knowledge_tree/detail_service.py` | LOW | 追加 evidence 段，不改已有逻辑 |
| `frontend/useKnowledgeTree.js` | HIGH | graphData 解析逻辑变更，影响所有消费组件 |
| `frontend/TreeNavPanel.vue` | HIGH | 重写，旧拼装逻辑完全替换 |
| `frontend/GraphPanel.vue` | MED | 节点数变化影响布局参数 |
| `frontend/NodeDetailDrawer.vue` | LOW | 追加 tab，不改已有 tab |

**兼容策略（F004 处置）**：Graph API 响应格式是 breaking change，无向后兼容。后端 API 变更（Batch 1 Task 4-6）和前端适配（Batch 2 Task 7-9）在连续批次完成，部署时一次性上线。不存在"后端已切新格式但前端未适配"的中间态。

### test_debt

| 项 | 理由 | deadline |
|----|------|----------|
| 双库一致性（PG↔knowledge.db 回写） | 已有技术债（best-effort 语义），不在本次范围。需要独立设计补偿/回滚机制。 | 2026-04-30 |
| 前端 Vitest 对 navigation 的集成测试 | 当前前端测试无 API mock 基础设施，需要先建 mock 层 | 2026-04-20 |

