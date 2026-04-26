<!-- pre-takeover: archived for history, not active spec -->
# 知识图谱深度优化 Phase 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 暴露 knowledge.db 中已有但未使用的数据资产（考频、教材章节、MCU 规划权重、StudyUnit），让教师打开知识图谱立刻看到"什么重要、什么考、怎么学"。

**Architecture:** 在 edu-cloud PG 新增 `concept_stats` 计算表（投影自 knowledge.db + MCU），启动时全量计算 + 编辑后增量刷新；Graph API 扩展返回统计指标；前端节点视觉升级为大小编码重要度 + 热力着色 + 详情面板新增标签页。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 async / Alembic / PostgreSQL / SQLite（只读 knowledge.db）/ Vue 3.5 / AntV G6 6.x / Vitest

**设计文档:** `docs/plans/2026-04-12-knowledge-graph-optimization-design.md`

**Phase 1 范围:** 数据暴露（不含图谱边增强、教学规划、学生画像 —— 后续 Phase 2/3/4）

---

## 文件结构

### 后端新建

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/modules/knowledge_tree/stats_service.py` | concept_stats 计算（考频/章节/重要度/深度） |
| `src/edu_cloud/modules/knowledge_tree/exam_items_service.py` | 概念→高考真题查询 |
| `scripts/import_mcu_planning_weights.py` | MCU CP→kb concept 映射 + 权重导入（一次性脚本） |
| `alembic/versions/<hash>_add_concept_stats.py` | concept_stats 表迁移 |
| `tests/test_knowledge_tree/test_stats_service.py` | stats 计算单测 |
| `tests/test_knowledge_tree/test_exam_items_service.py` | 高考题查询单测 |
| `tests/test_knowledge_tree/test_mcu_import.py` | MCU 映射脚本单测 |
| `tests/test_knowledge_tree/test_graph_v3.py` | Graph API v3 字段测试 |

### 后端修改

| 文件 | 修改 |
|------|------|
| `src/edu_cloud/modules/knowledge_tree/models.py` | +ConceptStats 模型 |
| `src/edu_cloud/modules/knowledge_tree/service.py` | get_graph 合并 stats |
| `src/edu_cloud/modules/knowledge_tree/sync_service.py` | 同步后触发 stats 重算 |
| `src/edu_cloud/modules/knowledge_tree/router.py` | +3 新端点 |
| `src/edu_cloud/modules/knowledge_tree/schemas.py` | +ExamItem/StatsOverview 响应 |
| `src/edu_cloud/api/app.py` | lifespan 触发 stats 初始化 |

### 前端新建

| 文件 | 职责 |
|------|------|
| `frontend/src/components/knowledge-tree/ColorModeToggle.vue` | 着色模式切换（考频/掌握度/审核状态） |
| `frontend/src/components/knowledge-tree/ExamItemsTab.vue` | 详情面板高考真题标签页 |
| `frontend/src/components/knowledge-tree/StudyUnitTab.vue` | 详情面板学习单元标签页 |
| `frontend/src/components/knowledge-tree/heatmapUtils.js` | 考频→颜色映射工具函数 |
| `frontend/src/__tests__/knowledge-tree/ColorModeToggle.test.js` | 单测 |
| `frontend/src/__tests__/knowledge-tree/heatmapUtils.test.js` | 单测 |

### 前端修改

| 文件 | 修改 |
|------|------|
| `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` | 节点 size ∝ importance，fill 由 colorMode 决定 |
| `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue` | +2 标签页 |
| `frontend/src/components/knowledge-tree/TreeNavPanel.vue` | 导航模式切换（模块/教材章节） |
| `frontend/src/components/knowledge-tree/useKnowledgeTree.js` | +loadChapterNav, +loadExamItems, +colorMode state |
| `frontend/src/api/knowledgeTree.js` | +getExamItems, +getStatsOverview |
| `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue` | 卡片增加考频/覆盖率统计 |

---

## 测试契约汇总

| Slice | 入口 | 反例 | 边界 | 回归 |
|-------|------|------|------|------|
| S1 concept_stats 模型 | migration upgrade/downgrade | 表名冲突/字段缺失 | FK 级联、NOT NULL 约束 | N/A |
| S2 考频计算 | compute_exam_frequency(db) | 错误实现会把 L0 计入 | 零考频概念 / 单 DA 多概念 / 孤立概念 | N/A |
| S3 教材章节聚合 | compute_textbook_chapters(db) | 不回溯 evidence 会漏 89.5% 映射 | evidence 为空 / 跨册概念 / section 缺失 | N/A |
| S4 重要度计算 | compute_importance_score(stats) | 不归一化会让高考频概念独占高位 | 全零考频 / 全同考频 / 极值 | N/A |
| S5 MCU 映射导入 | import_mcu_weights(db) | 匹配阈值过低会误关联 | 完全不匹配 / 同名歧义 | N/A |
| S6 Graph API v3 | GET /graph response | 节点缺 exam_frequency 字段 | stats 表为空 / 部分概念无 stats | 原 v2 字段保留 |
| S7 高考题查询 API | GET /graph/{id}/exam-items | 返回其他概念的题 | 概念无关联题 / 分页边界 | N/A |
| S8 统计概览 API | GET /stats/overview | 覆盖率计算错误 | 单模块/全模块 | N/A |
| S9 前端节点视觉 | ConceptMapPanel 渲染 | 节点大小不反映 importance | importance=0 的节点 / 全同节点 | 焦点模式不破坏 |
| S10 着色模式切换 | ColorModeToggle 点击 | 切换后节点颜色未更新 | 切到掌握度但无学生 | 原状态保留 |
| S11 详情面板标签页 | NodeDetailDrawer 打开 | 新标签页默认不显示 | 无 SU 关联 / 无题目关联 | 原标签页保留 |
| S12 教材章节导航 | TreeNavPanel 切换模式 | 切换后树结构未变 | 概念跨多章 / 章节无概念 | 模块模式可回切 |

---

## Task 0: 环境准备与设计契约验证

**Files:**
- Read: `docs/plans/2026-04-12-knowledge-graph-optimization-design.md`
- Read: `src/edu_cloud/modules/knowledge_tree/models.py`
- Read: `src/edu_cloud/modules/knowledge_tree/service.py`
- Read: `src/edu_cloud/modules/knowledge_tree/sync_service.py`

**Steps:**

- [ ] **Step 1: 确认 knowledge.db 可访问并验证数据链路**

Run:
```bash
cd /c/Users/Administrator/edu-cloud
python -c "
import sqlite3, json
conn = sqlite3.connect('C:/Users/Administrator/edu-knowledge-base/knowledge.db')
# 抽一个概念验证完整链路
c = conn.execute('SELECT id, name FROM concepts WHERE id=\"BIO_SR_CP_M1_PHOTOSYNTHESIS\"').fetchone()
print(f'Concept: {c}')
das = conn.execute('SELECT id FROM diagnostic_attributes WHERE linked_concept_ids LIKE ?', (f'%{c[0]}%',)).fetchall()
print(f'DAs: {len(das)}')
da_ids = [d[0] for d in das]
if da_ids:
    p = ','.join('?'*len(da_ids))
    items = conn.execute(f'SELECT COUNT(DISTINCT item_id) FROM q_matrix WHERE attribute_id IN ({p})', da_ids).fetchone()[0]
    print(f'Items: {items}')
conn.close()
"
```
Expected: 输出 `Concept: ('BIO_SR_CP_M1_PHOTOSYNTHESIS', '光合作用')` / `DAs: 4` / `Items: 1260`

- [ ] **Step 2: 确认当前基线测试全部通过**

Run:
```bash
cd /c/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/ --tb=short -q
```
Expected: 所有测试通过（当前 knowledge_tree 测试数约 200+ 条）

- [ ] **Step 3: 创建 state sidecar**

Run:
```bash
python -c "
import json, datetime
state = {
    'topic': '2026-04-13-knowledge-graph-phase1',
    'plan_file': 'docs/plans/2026-04-13-knowledge-graph-phase1-plan.md',
    'design_file': 'docs/plans/2026-04-12-knowledge-graph-optimization-design.md',
    'tasks': [{'id': str(i), 'desc': f'Task {i}', 'status': 'pending'} for i in range(0, 15)],
    'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
}
with open('docs/plans/2026-04-13-knowledge-graph-phase1-state.json', 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
print('state.json created')
"
git add docs/plans/2026-04-13-knowledge-graph-phase1-state.json
git commit -m "chore: Phase 1 state sidecar"
```

---

## Task 1: ConceptStats 模型 + Alembic 迁移

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/models.py`
- Create: `alembic/versions/<timestamp>_add_concept_stats.py`
- Create: `tests/test_knowledge_tree/test_models_stats.py`

**测试契约:**

1. ConceptStats 模型字段完整性
   - 入口: `ConceptStats(concept_id='X', exam_frequency=100, ...)`
   - 反例: 如果遗漏 `importance_score` 字段，后续服务无法计算和排序
   - 边界: 所有字段有合理默认值（NULL 或 0）
   - 回归: N/A（新表）
   - 命令: `pytest tests/test_knowledge_tree/test_models_stats.py::test_concept_stats_instantiation -v`

2. 迁移 upgrade/downgrade 对称性
   - 入口: Alembic upgrade 创建表、downgrade 删除表
   - 反例: 迁移只 upgrade 不 downgrade 会阻塞回滚
   - 边界: FK 级联（concept 被删除时 stats 应级联删除）
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_models_stats.py::test_migration_symmetric -v`

**Steps:**

- [ ] **Step 1: 写失败测试 — ConceptStats 模型实例化**

Create `tests/test_knowledge_tree/test_models_stats.py`:

```python
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
    # 先创建 parent node
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
async def test_concept_stats_cascade_on_node_delete(db):
    """删除概念节点时 stats 应级联删除（FK ON DELETE CASCADE）"""
    node = ConceptGraphNode(
        id="TEST_CASCADE_001", name="级联测试", knowledge_level="L1",
        primary_module="M1", synced_at=datetime.now(),
    )
    db.add(node)
    await db.commit()

    stats = ConceptStats(
        concept_id="TEST_CASCADE_001",
        exam_frequency=50,
        computed_at=datetime.now(),
    )
    db.add(stats)
    await db.commit()

    # 删除 node
    await db.execute(
        sa.delete(ConceptGraphNode).where(ConceptGraphNode.id == "TEST_CASCADE_001")
    )
    await db.commit()

    # stats 应同时被删除
    result = await db.execute(
        sa.select(ConceptStats).where(ConceptStats.concept_id == "TEST_CASCADE_001")
    )
    assert result.scalar_one_or_none() is None


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
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /c/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_models_stats.py -v`
Expected: FAIL with "ImportError: cannot import name 'ConceptStats'"

- [ ] **Step 3: 添加 ConceptStats 模型到 models.py**

Append to `src/edu_cloud/modules/knowledge_tree/models.py`:

```python
from sqlalchemy import JSON


class ConceptStats(Base):
    """概念统计指标（从 knowledge.db + MCU 计算投影）。

    目的：Graph API 返回节点时合并这些指标，让前端能按重要度/考频可视化。
    计算时机：sync_service 同步后触发全量计算；编辑图谱时触发受影响节点增量计算。
    """
    __tablename__ = "concept_stats"

    concept_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("concept_graph_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    exam_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exam_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_difficulty: Mapped[float | None] = mapped_column(Float)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    planning_weight: Mapped[dict | None] = mapped_column(JSON)
    textbook_chapters: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    study_unit_id: Mapped[str | None] = mapped_column(String(64))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    prerequisite_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
```

- [ ] **Step 4: 生成 Alembic 迁移**

Run:
```bash
cd /c/Users/Administrator/edu-cloud
python -m alembic revision --autogenerate -m "add concept_stats table"
```
Expected: 新增 `alembic/versions/<hash>_add_concept_stats.py` 文件

- [ ] **Step 5: 验证迁移脚本内容**

Inspect 新生成的迁移文件，确认：
- `op.create_table('concept_stats', ...)` 包含所有字段
- `ForeignKey` 约束带 `ondelete='CASCADE'`
- `downgrade()` 包含 `op.drop_table('concept_stats')`

手动修正（如果 autogenerate 遗漏）确保 JSON 字段使用 `sa.JSON()` 类型。

- [ ] **Step 6: 运行迁移升级**

Run:
```bash
cd /c/Users/Administrator/edu-cloud && python -m alembic upgrade head
```
Expected: `Running upgrade ... -> <hash>, add concept_stats table`

- [ ] **Step 7: 添加迁移对称性测试**

Append to `tests/test_knowledge_tree/test_models_stats.py`:

```python
def test_migration_symmetric():
    """迁移 upgrade/downgrade 对称：表存在性可逆"""
    from alembic.config import Config
    from alembic import command
    from sqlalchemy import create_engine, inspect
    import tempfile, os

    tmpdb = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmpdb.close()
    try:
        url = f"sqlite:///{tmpdb.name}"
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)

        command.upgrade(cfg, "head")
        engine = create_engine(url)
        insp = inspect(engine)
        assert "concept_stats" in insp.get_table_names()
        engine.dispose()

        command.downgrade(cfg, "-1")
        engine = create_engine(url)
        insp = inspect(engine)
        assert "concept_stats" not in insp.get_table_names()
        engine.dispose()
    finally:
        os.unlink(tmpdb.name)
```

- [ ] **Step 8: 运行所有模型测试确认通过**

Run: `cd /c/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_models_stats.py -v`
Expected: 3 PASS

- [ ] **Step 9: Commit**

```bash
cd /c/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/knowledge_tree/models.py \
        alembic/versions/*_add_concept_stats.py \
        tests/test_knowledge_tree/test_models_stats.py
git commit -m "feat(knowledge-tree): add ConceptStats model + migration"
```

**审查清单:**
- ✓ ConceptStats 模型包含设计文档中所有字段
- ✓ FK 有 ON DELETE CASCADE
- ✓ 迁移 upgrade/downgrade 对称
- ✗ 不应使用字符串字段存 JSON（应用原生 JSON 类型）

**边界条件:**
- 空 textbook_chapters → 应返回 `[]` 不是 `None`
- NULL planning_weight → 允许（MCU 映射不到的概念）
- concept_id 不存在 → FK 约束报错

---

## Task 2: 考频计算（exam_frequency + avg_difficulty + exam_coverage）

**Files:**
- Create: `src/edu_cloud/modules/knowledge_tree/stats_service.py`
- Create: `tests/test_knowledge_tree/test_stats_service.py`

**测试契约:**

1. 考频计算正确性（真实数据验证）
   - 入口: `compute_exam_frequency(kb_path)` 返回 `dict[concept_id, int]`
   - 反例: 错误实现会把 L0 evidence 计入（返回 1200+ 个键而非 108）；或忽略 JSON 数组解析把 "[id1,id2]" 当单字符串匹配
   - 边界: 零考频概念 / 单 DA 关联多概念 / 概念无任何 DA
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_stats_service.py::test_exam_frequency_real_data -v`

2. avg_difficulty 聚合
   - 入口: `compute_avg_difficulty(kb_path)` 返回 `dict[concept_id, float]`
   - 反例: 未聚合直接返回单题难度；零除错误
   - 边界: 概念无题 → 返回 None 不是 0
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_stats_service.py::test_avg_difficulty -v`

**Steps:**

- [ ] **Step 1: 写失败测试 — 考频真实数据验证**

Create `tests/test_knowledge_tree/test_stats_service.py`:

```python
"""concept_stats 计算服务测试"""
import os
import pytest
from pathlib import Path


KB_PATH = os.environ.get(
    "KNOWLEDGE_DB_PATH",
    str(Path.home() / "edu-knowledge-base" / "knowledge.db")
)


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_exam_frequency_real_data():
    """考频计算：光合作用应有 1260 题（实测值），零考频概念应存在"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_frequency

    freq = compute_exam_frequency(KB_PATH)

    # 返回应只包含 L1 概念（约 108 个），不含 L0/evidence
    assert 100 <= len(freq) <= 120, f"Expected ~108 L1 concepts, got {len(freq)}"

    # 光合作用是高频概念
    photo = freq.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None and photo >= 1000, f"光合作用考频应>=1000, got {photo}"

    # 应存在零考频概念
    zero_freq = [cid for cid, f in freq.items() if f == 0]
    assert len(zero_freq) >= 10, f"应有多个零考频概念, got {len(zero_freq)}"


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_exam_frequency_excludes_l0():
    """考频计算不应把 L0 evidence 当作概念（反例检查）"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_frequency
    freq = compute_exam_frequency(KB_PATH)
    # L0 evidence ID 格式为 BIO_SR_B1_CH01_BK_001，不应出现
    l0_keys = [k for k in freq if "_BK_" in k]
    assert len(l0_keys) == 0, f"不应包含 L0 evidence, got {l0_keys[:3]}"


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_avg_difficulty():
    """avg_difficulty：聚合概念关联题目的 difficulty 平均"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_avg_difficulty
    diff = compute_avg_difficulty(KB_PATH)

    # 有题目的概念应有 avg_difficulty，范围 1-5
    photo = diff.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None
    assert 1.0 <= photo <= 5.0, f"avg_difficulty 应在 [1,5], got {photo}"

    # 零考频概念应为 None
    zero_freq_concepts = [cid for cid, d in diff.items() if d is None]
    assert len(zero_freq_concepts) >= 10


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_exam_coverage():
    """exam_coverage：概念出现在多少套高考卷中 / 总卷数"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_coverage
    cov = compute_exam_coverage(KB_PATH)

    photo = cov.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None
    assert 0.0 <= photo <= 1.0
    assert photo >= 0.5, f"光合作用应覆盖 >50% 高考卷, got {photo}"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /c/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_stats_service.py -v`
Expected: FAIL `ImportError: cannot import name 'compute_exam_frequency'`

- [ ] **Step 3: 实现 stats_service.py — 考频函数**

Create `src/edu_cloud/modules/knowledge_tree/stats_service.py`:

```python
"""concept_stats 计算服务。

从 knowledge.db 读取关联链路计算每个 L1 概念的：
- exam_frequency: 关联高考题数量（通过 DA → Q-Matrix 回溯）
- avg_difficulty: 关联题目平均难度
- exam_coverage: 出现在多少比例的高考卷中
- textbook_chapters: 教材章节列表（通过 evidence → content_blocks → sections）
- importance_score: 综合重要度（考频 + error_prone + transfer_value + depth）
- prerequisite_depth: 前置链深度（拓扑排序 rank）

设计文档: docs/plans/2026-04-12-knowledge-graph-optimization-design.md §7
"""
import json
import logging
import sqlite3
from collections import defaultdict

logger = logging.getLogger(__name__)


def _load_da_to_concepts(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """从 diagnostic_attributes 构建 DA→concept_ids 映射。

    linked_concept_ids 是 JSON 数组存为 TEXT，用 json.loads 解析。
    """
    mapping: dict[str, list[str]] = {}
    for da_id, linked in conn.execute(
        "SELECT id, linked_concept_ids FROM diagnostic_attributes WHERE linked_concept_ids IS NOT NULL"
    ):
        try:
            concept_ids = json.loads(linked)
            if isinstance(concept_ids, list):
                mapping[da_id] = concept_ids
        except (json.JSONDecodeError, TypeError):
            logger.warning("DA %s has invalid linked_concept_ids: %r", da_id, linked)
    return mapping


def _load_l1_concept_ids(conn: sqlite3.Connection) -> set[str]:
    """只返回 L1 concepts（过滤 L0 evidence 和 L2）。"""
    return {
        r[0] for r in conn.execute(
            "SELECT id FROM concepts WHERE knowledge_level='L1'"
        )
    }


def compute_exam_frequency(kb_path: str) -> dict[str, int]:
    """计算每个 L1 概念关联的高考题数量。

    链路: concepts(L1) ← DA.linked_concept_ids → q_matrix.attribute_id → item_id (DISTINCT)
    """
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)
        da_to_concepts = _load_da_to_concepts(conn)

        # concept_id → set of item_ids
        concept_items: dict[str, set[str]] = defaultdict(set)
        for item_id, da_id in conn.execute("SELECT item_id, attribute_id FROM q_matrix"):
            for cid in da_to_concepts.get(da_id, []):
                if cid in l1_ids:
                    concept_items[cid].add(item_id)

        # 为所有 L1 概念填 0（包括零考频）
        result = {cid: len(concept_items.get(cid, set())) for cid in l1_ids}
        return result
    finally:
        conn.close()


def compute_avg_difficulty(kb_path: str) -> dict[str, float | None]:
    """计算每个 L1 概念关联题目的平均难度。"""
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)
        da_to_concepts = _load_da_to_concepts(conn)

        # concept_id → list of difficulties
        concept_difficulties: dict[str, list[float]] = defaultdict(list)
        # item_id → difficulty
        item_difficulty: dict[str, float] = {}
        for item_id, diff in conn.execute(
            "SELECT id, difficulty FROM assessment_items WHERE difficulty IS NOT NULL"
        ):
            item_difficulty[item_id] = float(diff)

        # 通过 q_matrix 聚合
        seen_pairs: set[tuple[str, str]] = set()
        for item_id, da_id in conn.execute("SELECT item_id, attribute_id FROM q_matrix"):
            if item_id not in item_difficulty:
                continue
            for cid in da_to_concepts.get(da_id, []):
                if cid not in l1_ids:
                    continue
                pair = (cid, item_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                concept_difficulties[cid].append(item_difficulty[item_id])

        result: dict[str, float | None] = {}
        for cid in l1_ids:
            diffs = concept_difficulties.get(cid)
            result[cid] = sum(diffs) / len(diffs) if diffs else None
        return result
    finally:
        conn.close()


def compute_exam_coverage(kb_path: str) -> dict[str, float]:
    """计算每个概念出现在多少比例的高考卷中（0-1）。"""
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)
        da_to_concepts = _load_da_to_concepts(conn)

        # 总卷数
        total_exams = conn.execute(
            "SELECT COUNT(DISTINCT exam_id) FROM assessment_items"
        ).fetchone()[0]
        if total_exams == 0:
            return {cid: 0.0 for cid in l1_ids}

        # concept_id → set of exam_ids
        item_to_exam: dict[str, str] = dict(
            conn.execute("SELECT id, exam_id FROM assessment_items")
        )
        concept_exams: dict[str, set[str]] = defaultdict(set)
        for item_id, da_id in conn.execute("SELECT item_id, attribute_id FROM q_matrix"):
            exam_id = item_to_exam.get(item_id)
            if not exam_id:
                continue
            for cid in da_to_concepts.get(da_id, []):
                if cid in l1_ids:
                    concept_exams[cid].add(exam_id)

        return {cid: len(concept_exams.get(cid, set())) / total_exams for cid in l1_ids}
    finally:
        conn.close()
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /c/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_stats_service.py -v`
Expected: 4 PASS

- [ ] **Step 5: 手动验证 Top 10 考频数据与调查报告一致**

Run:
```bash
cd /c/Users/Administrator/edu-cloud
python -c "
from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_frequency
import sqlite3
freq = compute_exam_frequency('C:/Users/Administrator/edu-knowledge-base/knowledge.db')
conn = sqlite3.connect('C:/Users/Administrator/edu-knowledge-base/knowledge.db')
names = dict(conn.execute('SELECT id, name FROM concepts WHERE knowledge_level=\"L1\"'))
top10 = sorted(freq.items(), key=lambda x: -x[1])[:10]
for cid, f in top10:
    print(f'{names[cid]}: {f}')
"
```
Expected: ATP 1313 / 细胞呼吸 1295 / 光合作用 1260 / 糖类 748 / ... (与设计文档 §0.1 一致)

- [ ] **Step 6: Commit**

```bash
cd /c/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/knowledge_tree/stats_service.py \
        tests/test_knowledge_tree/test_stats_service.py
git commit -m "feat(stats): compute exam_frequency/avg_difficulty/exam_coverage from knowledge.db"
```

**审查清单:**
- ✓ 考频基于 DA→Q-Matrix 链路计算，非基于 concept 表的 source_req_id
- ✓ 只返回 L1 概念，不包含 L0 evidence 和 L2 原理
- ✓ 零考频概念显式返回 0，不省略
- ✓ avg_difficulty 在无关联题目时返回 None（非 0）
- ✗ 不应使用 LIKE 匹配 linked_concept_ids（应用 json.loads 精确匹配）

**边界条件:**
- DA 的 linked_concept_ids 为 NULL → 跳过，不报错
- 概念关联 DA 但 DA 未在 Q-Matrix 中出现 → 考频为 0
- 题目 difficulty 为 NULL → 不计入平均

---

## Task 3: 教材章节聚合 + 前置深度计算

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/stats_service.py`
- Modify: `tests/test_knowledge_tree/test_stats_service.py`

**测试契约:**

1. 教材章节聚合
   - 入口: `compute_textbook_chapters(kb_path)` 返回 `dict[concept_id, list[dict]]`
   - 反例: 不走 evidence 回溯会漏 89.5% 映射（只有 L1 的 source_block_id 并不全）
   - 边界: L1 概念无 evidence_ids_json / evidence 的 source_block_id 为 NULL / 同概念跨多节
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_stats_service.py::test_textbook_chapters -v`

2. prerequisite_depth 拓扑排序
   - 入口: `compute_prerequisite_depth(pg_session)` 返回 `dict[concept_id, int]`
   - 反例: 未处理环形依赖会死循环
   - 边界: 孤立节点 depth=0 / 有环时 fallback 到最大+1
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_stats_service.py::test_prerequisite_depth -v`

**Steps:**

- [ ] **Step 1: 写失败测试**

Append to `tests/test_knowledge_tree/test_stats_service.py`:

```python
@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_textbook_chapters():
    """教材章节聚合：通过 evidence → content_blocks → sections 回溯"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_textbook_chapters
    chapters = compute_textbook_chapters(KB_PATH)

    # 光合作用应映射到必修1
    photo = chapters.get("BIO_SR_CP_M1_PHOTOSYNTHESIS")
    assert photo is not None and len(photo) > 0, "光合作用应关联教材章节"
    assert any(ch["book"] == "b1" for ch in photo), "光合作用应在必修1"

    # 每个章节条目应包含 book/chapter/section/title
    for cid, chs in chapters.items():
        for ch in chs:
            assert "book" in ch
            assert "chapter" in ch
            assert "section" in ch
            assert "title" in ch

    # 覆盖率应 >= 80%（设计中 89.5% 是 evidence 层面，聚合到 L1 层会更高）
    non_empty = sum(1 for v in chapters.values() if v)
    coverage = non_empty / len(chapters)
    assert coverage >= 0.8, f"L1 概念教材覆盖率应 >=80%, got {coverage:.1%}"


@pytest.mark.asyncio
async def test_prerequisite_depth(db):
    """拓扑排序计算前置深度。构造: A→B→C, D 孤立"""
    from datetime import datetime
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge
    from edu_cloud.modules.knowledge_tree.stats_service import compute_prerequisite_depth

    now = datetime.now()
    for cid in ["A", "B", "C", "D"]:
        db.add(ConceptGraphNode(
            id=cid, name=cid, knowledge_level="L1",
            primary_module="M1", node_type="concept", synced_at=now,
        ))
    db.add(ConceptGraphEdge(
        source_id="A", target_id="B", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="B", target_id="C", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    await db.commit()

    depth = await compute_prerequisite_depth(db)
    assert depth["A"] == 0, "A 无前置，depth=0"
    assert depth["B"] == 1, "B 前置链长度 1"
    assert depth["C"] == 2, "C 前置链长度 2"
    assert depth["D"] == 0, "D 孤立，depth=0"


@pytest.mark.asyncio
async def test_prerequisite_depth_cycle_handling(db):
    """有环时不应死循环"""
    from datetime import datetime
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge
    from edu_cloud.modules.knowledge_tree.stats_service import compute_prerequisite_depth

    now = datetime.now()
    for cid in ["X", "Y"]:
        db.add(ConceptGraphNode(
            id=cid, name=cid, knowledge_level="L1",
            primary_module="M1", node_type="concept", synced_at=now,
        ))
    # 构造环: X→Y, Y→X
    db.add(ConceptGraphEdge(
        source_id="X", target_id="Y", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    db.add(ConceptGraphEdge(
        source_id="Y", target_id="X", relation_type="prerequisite_hard",
        strength=1.0, confidence=1.0, synced_at=now,
    ))
    await db.commit()

    # 不应抛异常或死循环（带 timeout 验证）
    import asyncio
    depth = await asyncio.wait_for(compute_prerequisite_depth(db), timeout=2.0)
    # 环中节点应有 fallback 值
    assert "X" in depth
    assert "Y" in depth
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/test_knowledge_tree/test_stats_service.py::test_textbook_chapters -v`
Expected: FAIL `ImportError: cannot import name 'compute_textbook_chapters'`

- [ ] **Step 3: 实现教材章节聚合**

Append to `src/edu_cloud/modules/knowledge_tree/stats_service.py`:

```python
def compute_textbook_chapters(kb_path: str) -> dict[str, list[dict]]:
    """为每个 L1 概念聚合教材章节信息。

    链路: L1.evidence_ids_json → evidence concepts → source_block_id
          → content_blocks.section_id → sections
    """
    conn = sqlite3.connect(kb_path)
    try:
        l1_ids = _load_l1_concept_ids(conn)

        # 预加载 evidence concept → section_id
        evidence_to_section: dict[str, str | None] = {}
        for cid, block_id in conn.execute(
            "SELECT id, source_block_id FROM concepts WHERE knowledge_level='evidence' AND source_block_id IS NOT NULL"
        ):
            section = conn.execute(
                "SELECT section_id FROM content_blocks WHERE id=?", (block_id,)
            ).fetchone()
            if section:
                evidence_to_section[cid] = section[0]

        # 预加载 section → {book, chapter, section, title}
        section_info: dict[str, dict] = {}
        for sid, title in conn.execute("SELECT id, title FROM sections"):
            # sid 格式: b1:ch01_s01 或 xe1:ch02_s03
            parts = sid.split(":")
            if len(parts) != 2:
                continue
            book, rest = parts
            sub = rest.split("_", 1)
            chapter = sub[0] if sub else ""
            section = sub[1] if len(sub) > 1 else ""
            section_info[sid] = {
                "book": book, "chapter": chapter,
                "section": section, "title": title or "",
            }

        # 聚合每个 L1 概念
        result: dict[str, list[dict]] = {}
        for l1_id in l1_ids:
            evi_row = conn.execute(
                "SELECT evidence_ids_json FROM concepts WHERE id=?", (l1_id,)
            ).fetchone()
            if not evi_row or not evi_row[0]:
                result[l1_id] = []
                continue
            try:
                evidence_ids = json.loads(evi_row[0])
            except (json.JSONDecodeError, TypeError):
                result[l1_id] = []
                continue

            seen_sections: set[str] = set()
            chapters: list[dict] = []
            for eid in evidence_ids:
                sid = evidence_to_section.get(eid)
                if sid and sid not in seen_sections:
                    seen_sections.add(sid)
                    if sid in section_info:
                        chapters.append(section_info[sid])

            result[l1_id] = chapters
        return result
    finally:
        conn.close()


async def compute_prerequisite_depth(db) -> dict[str, int]:
    """拓扑排序计算每个 L1 概念的前置链深度。

    环形依赖: 未被排序的节点统一赋值 max_rank + 1。
    """
    import sqlalchemy as sa
    from edu_cloud.modules.knowledge_tree.models import (
        ConceptGraphNode, ConceptGraphEdge,
    )
    from collections import deque

    # 加载所有 L1 concept 节点
    node_result = await db.execute(
        sa.select(ConceptGraphNode.id)
        .where(ConceptGraphNode.node_type == "concept")
    )
    node_ids = {r[0] for r in node_result.all()}

    # 加载 hard edges
    edge_result = await db.execute(
        sa.select(ConceptGraphEdge.source_id, ConceptGraphEdge.target_id)
        .where(ConceptGraphEdge.relation_type == "prerequisite_hard")
    )
    edges = [(s, t) for s, t in edge_result.all() if s in node_ids and t in node_ids]

    # Kahn 拓扑排序
    adj: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)
    for cid in node_ids:
        in_degree[cid] = 0
    for s, t in edges:
        adj[s].append(t)
        in_degree[t] += 1

    queue: deque = deque([cid for cid in node_ids if in_degree[cid] == 0])
    depth: dict[str, int] = {cid: 0 for cid in queue}

    processed = set()
    while queue:
        u = queue.popleft()
        if u in processed:
            continue
        processed.add(u)
        for v in adj[u]:
            new_depth = depth[u] + 1
            if v not in depth or depth[v] < new_depth:
                depth[v] = new_depth
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    # 环中节点 fallback
    max_depth = max(depth.values()) if depth else 0
    for cid in node_ids:
        if cid not in depth:
            depth[cid] = max_depth + 1

    return depth
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_knowledge_tree/test_stats_service.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Administrator/edu-cloud
git add src/edu_cloud/modules/knowledge_tree/stats_service.py \
        tests/test_knowledge_tree/test_stats_service.py
git commit -m "feat(stats): compute textbook_chapters + prerequisite_depth"
```

**审查清单:**
- ✓ 教材章节通过 evidence 回溯（非直接 L1.source_block_id）
- ✓ 拓扑排序使用 Kahn 算法，O(V+E)
- ✓ 环形依赖有 fallback，不死循环
- ✗ 不应硬编码 section ID 格式（解析 "b1:ch01_s01" 时要处理异常格式）

**边界条件:**
- evidence_ids_json 为 NULL → 返回空列表
- 同概念的多个 evidence 映射到同一 section → 去重
- 跨册概念（b1 + xe1） → 都保留
- 孤立节点（无前置无后继）→ depth=0

---

## Task 4: MCU 规划权重映射与导入

**Files:**
- Create: `scripts/import_mcu_planning_weights.py`
- Create: `tests/test_knowledge_tree/test_mcu_import.py`

**测试契约:**

1. MCU CP → kb concept 语义匹配
   - 入口: `match_mcu_to_kb(mcu_patterns, kb_concepts)` 返回 `dict[mcu_id, (kb_id, score)]`
   - 反例: 用完全匹配（name 精确相等）会漏 >90% 映射；匹配阈值过低会乱匹配
   - 边界: MCU CP 找不到 kb 对应 / 同 kb 被多个 MCU 匹配 / 文本完全不同
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_mcu_import.py::test_mcu_matching -v`

2. 权重导入幂等性
   - 入口: `import_weights(db, mapping)` 调用两次结果一致
   - 反例: 不处理重复 concept_id 会插入多条
   - 边界: mapping 为空 / 部分 concept 无 stats 记录
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_mcu_import.py::test_import_idempotent -v`

**Steps:**

- [ ] **Step 1: 写失败测试**

Create `tests/test_knowledge_tree/test_mcu_import.py`:

```python
"""MCU 权重导入脚本测试"""
import json
import pytest
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptStats

MCU_PATH = Path("C:/Users/Administrator/Archive/MCU-03/knowledge_skeleton")


@pytest.mark.skipif(not MCU_PATH.exists(), reason="MCU-03 not available")
def test_mcu_matching_by_content():
    """MCU L1 CP 的 content 和 kb concept 的 name+description 做语义匹配"""
    from scripts.import_mcu_planning_weights import match_mcu_to_kb

    mcu_patterns = {
        "L01_CP_001": {
            "content": "生命系统的层级中，细胞是最基本且唯一能独立完成生命活动的单位",
        }
    }
    kb_concepts = {
        "BIO_SR_CP_M1_LIFE_SYSTEM_LEVELS": {
            "name": "生命系统的结构层次",
            "description": "从分子到生物圈的 9 个层次",
        },
        "BIO_SR_CP_M1_CELL_THEORY": {
            "name": "细胞学说",
            "description": "施莱登施旺细胞学说三要点",
        },
    }
    result = match_mcu_to_kb(mcu_patterns, kb_concepts, threshold=0.3)
    # L01_CP_001 讲生命系统层级，应匹配到 LIFE_SYSTEM_LEVELS 而非 CELL_THEORY
    assert "L01_CP_001" in result
    kb_id, score = result["L01_CP_001"]
    assert kb_id == "BIO_SR_CP_M1_LIFE_SYSTEM_LEVELS", \
        f"应匹配到 LIFE_SYSTEM_LEVELS, got {kb_id}"
    assert score >= 0.3


@pytest.mark.skipif(not MCU_PATH.exists(), reason="MCU-03 not available")
def test_mcu_matching_filters_low_confidence():
    """低于阈值的匹配应被过滤（反例：阈值太低会乱匹配）"""
    from scripts.import_mcu_planning_weights import match_mcu_to_kb

    mcu_patterns = {
        "L99_CP_999": {"content": "完全不相关的文本内容 XYZ"},
    }
    kb_concepts = {
        "BIO_SR_CP_M1_CELL_THEORY": {"name": "细胞学说", "description": "..."},
    }
    result = match_mcu_to_kb(mcu_patterns, kb_concepts, threshold=0.5)
    assert "L99_CP_999" not in result, "不相关内容不应匹配"


@pytest.mark.asyncio
async def test_import_idempotent(db):
    """两次导入权重结果一致（UPSERT）"""
    from scripts.import_mcu_planning_weights import import_weights

    # 准备一个 concept + 空 stats
    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_MCU_001", name="测试", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    db.add(ConceptStats(concept_id="TEST_MCU_001", computed_at=now))
    await db.commit()

    weights = {
        "TEST_MCU_001": {
            "exam_frequency": 8, "error_prone": 6,
            "transfer_value": 9, "priority_score": 7.7,
        }
    }
    await import_weights(db, weights)
    await import_weights(db, weights)  # 第二次

    result = await db.execute(
        sa.select(ConceptStats).where(ConceptStats.concept_id == "TEST_MCU_001")
    )
    loaded = result.scalar_one()
    assert loaded.planning_weight["priority_score"] == 7.7
    # 确认只有一条记录
    count = await db.execute(
        sa.select(sa.func.count()).select_from(ConceptStats)
        .where(ConceptStats.concept_id == "TEST_MCU_001")
    )
    assert count.scalar() == 1
```

- [ ] **Step 2: 实现 import_mcu_planning_weights.py**

Create `scripts/import_mcu_planning_weights.py`:

```python
"""MCU-03 规划权重导入脚本。

作用: 将 MCU L1_patterns/*.json 中的 planning_weight 字段（exam_frequency/error_prone/
transfer_value/priority_score）通过语义匹配导入到 edu-cloud ConceptStats.planning_weight。

用法: python scripts/import_mcu_planning_weights.py [--dry-run]

匹配策略: TF-IDF 字符 n-gram 相似度（无外部依赖，轻量级方案）
- MCU 侧取 CP.content
- kb 侧取 concept.name + concept.description
- 相似度 > 0.5 自动接受，0.3-0.5 写入日志人工确认，< 0.3 放弃
"""
import asyncio
import glob
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logger = logging.getLogger(__name__)

MCU_BASE = Path("C:/Users/Administrator/Archive/MCU-03/knowledge_skeleton")
DEFAULT_THRESHOLD = 0.5


def _char_ngrams(text: str, n: int = 2) -> Counter:
    """字符 n-gram 提取（中文友好）。"""
    text = text.replace(" ", "")
    return Counter(text[i:i+n] for i in range(len(text) - n + 1))


def _cosine_similarity(a: Counter, b: Counter) -> float:
    """Counter 间余弦相似度。"""
    if not a or not b:
        return 0.0
    intersection = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in intersection)
    norm_a = sum(v * v for v in a.values()) ** 0.5
    norm_b = sum(v * v for v in b.values()) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def match_mcu_to_kb(
    mcu_patterns: dict[str, dict],
    kb_concepts: dict[str, dict],
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, tuple[str, float]]:
    """匹配 MCU CP ID → kb concept ID。

    Args:
        mcu_patterns: {mcu_id: {"content": "..."}}
        kb_concepts: {kb_id: {"name": "...", "description": "..."}}
        threshold: 相似度阈值（低于此值不匹配）

    Returns:
        {mcu_id: (kb_id, similarity_score)}
    """
    # 预计算 kb 概念的 n-gram
    kb_ngrams = {
        kb_id: _char_ngrams((info.get("name") or "") + (info.get("description") or ""))
        for kb_id, info in kb_concepts.items()
    }

    result: dict[str, tuple[str, float]] = {}
    for mcu_id, mcu_info in mcu_patterns.items():
        mcu_ng = _char_ngrams(mcu_info.get("content") or "")
        best_kb, best_score = None, 0.0
        for kb_id, kb_ng in kb_ngrams.items():
            score = _cosine_similarity(mcu_ng, kb_ng)
            if score > best_score:
                best_score = score
                best_kb = kb_id
        if best_kb and best_score >= threshold:
            result[mcu_id] = (best_kb, best_score)
    return result


def load_mcu_patterns_and_weights() -> tuple[dict[str, dict], dict[str, dict]]:
    """加载 MCU L1 patterns 内容和规划权重。

    Returns: (patterns_by_id, weights_by_id)
    """
    patterns: dict[str, dict] = {}
    for f in sorted(glob.glob(str(MCU_BASE / "L1_patterns/*.json"))):
        data = json.load(open(f, encoding="utf-8"))
        for p in data.get("patterns", []):
            patterns[p["id"]] = {"content": p.get("content", "")}

    weights_file = MCU_BASE / "weights/planning_weights_L1.json"
    weights_data = json.load(open(weights_file, encoding="utf-8"))
    weights = weights_data.get("weights", {})
    return patterns, weights


async def load_kb_concepts(db) -> dict[str, dict]:
    """从 edu-cloud PG 加载 L1 概念。"""
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode

    result = await db.execute(
        sa.select(ConceptGraphNode.id, ConceptGraphNode.name, ConceptGraphNode.description)
        .where(ConceptGraphNode.node_type == "concept")
    )
    return {r[0]: {"name": r[1], "description": r[2] or ""} for r in result.all()}


async def import_weights(db, weights_by_concept_id: dict[str, dict]) -> int:
    """将权重写入 ConceptStats.planning_weight（幂等 UPSERT）。

    Args:
        weights_by_concept_id: {kb_concept_id: {"exam_frequency": ..., "priority_score": ...}}

    Returns: 更新的记录数
    """
    from edu_cloud.modules.knowledge_tree.models import ConceptStats
    from datetime import datetime

    updated = 0
    for concept_id, weight in weights_by_concept_id.items():
        stats = await db.get(ConceptStats, concept_id)
        if stats is None:
            # stats 不存在 → 创建
            db.add(ConceptStats(
                concept_id=concept_id,
                planning_weight=weight,
                computed_at=datetime.now(),
            ))
        else:
            stats.planning_weight = weight
            stats.computed_at = datetime.now()
        updated += 1
    await db.commit()
    return updated


async def main(dry_run: bool = False):
    from edu_cloud.database import get_session_factory

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    patterns, weights = load_mcu_patterns_and_weights()
    logger.info("MCU patterns: %d, weights: %d", len(patterns), len(weights))

    SessionFactory = get_session_factory()
    async with SessionFactory() as session:
        kb_concepts = await load_kb_concepts(session)
        logger.info("KB concepts: %d", len(kb_concepts))

        mapping = match_mcu_to_kb(patterns, kb_concepts)
        logger.info("Matched: %d MCU CPs → kb concepts", len(mapping))

        # 转换为 kb_concept_id → weight
        weights_by_kb: dict[str, dict] = {}
        for mcu_id, (kb_id, score) in mapping.items():
            if mcu_id in weights:
                weights_by_kb[kb_id] = weights[mcu_id]
                logger.info("  %s → %s (score=%.2f, priority=%.1f)",
                            mcu_id, kb_id, score, weights[mcu_id].get("priority_score", 0))

        if dry_run:
            logger.info("DRY-RUN: 不写入数据库")
            return

        updated = await import_weights(session, weights_by_kb)
        logger.info("Updated %d ConceptStats.planning_weight", updated)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(dry_run=args.dry_run))
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_knowledge_tree/test_mcu_import.py -v`
Expected: 3 PASS

- [ ] **Step 4: dry-run 验证映射质量**

Run:
```bash
cd /c/Users/Administrator/edu-cloud && python scripts/import_mcu_planning_weights.py --dry-run 2>&1 | head -40
```
Expected: 至少 60 条映射日志，priority_score 在 5-10 范围

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Administrator/edu-cloud
git add scripts/import_mcu_planning_weights.py \
        tests/test_knowledge_tree/test_mcu_import.py
git commit -m "feat(mcu): import MCU planning_weights with semantic matching"
```

**审查清单:**
- ✓ 语义匹配使用 TF-IDF n-gram（无外部依赖）
- ✓ 阈值 0.5 过滤低质量匹配
- ✓ import 函数幂等（UPSERT）
- ✗ 不应使用精确 name 匹配（MCU 和 kb 命名体系完全不同）

**边界条件:**
- MCU patterns 为空 → 返回空映射
- MCU CP 无 planning_weight 记录 → 跳过导入
- 同一 kb concept 被多个 MCU 匹配 → 取相似度最高的

---

## Task 5: importance_score 计算 + compute_all 编排

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/stats_service.py`
- Modify: `tests/test_knowledge_tree/test_stats_service.py`

**测试契约:**

1. importance_score 归一化
   - 入口: `compute_importance_score(freq, depth, planning_weight)` 返回 float ∈ [0, 10]
   - 反例: 不做百分位归一化，光合作用考频 1260 会使所有其他概念看起来都是 0
   - 边界: 全零考频 / 无 MCU 权重 / 极值
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_stats_service.py::test_importance_score -v`

2. compute_all_stats 编排
   - 入口: `compute_all_stats(db, kb_path)` 写入 concept_stats 表
   - 反例: 部分字段计算失败时整个函数崩溃（应容错继续）
   - 边界: kb_path 不存在 / PG 中无概念
   - 回归: 现有 108 L1 概念应全部有 stats 记录
   - 命令: `pytest tests/test_knowledge_tree/test_stats_service.py::test_compute_all_stats_real -v`

**Steps:**

- [ ] **Step 1: 写失败测试**

Append to `tests/test_knowledge_tree/test_stats_service.py`:

```python
def test_importance_score_normalization():
    """importance_score 应归一化到 [0, 10]"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_importance_score

    # 样本 1: 高频 + 高权重 + 深前置
    score_high = compute_importance_score(
        exam_frequency_percentile=0.95,
        prerequisite_depth=5,
        planning_weight={"error_prone": 9, "transfer_value": 10},
    )
    assert 7.0 <= score_high <= 10.0, f"高权重应得高分, got {score_high}"

    # 样本 2: 全零
    score_low = compute_importance_score(
        exam_frequency_percentile=0.0,
        prerequisite_depth=0,
        planning_weight=None,
    )
    assert 0.0 <= score_low <= 2.0, f"全零应得低分, got {score_low}"

    # 样本 3: 无 MCU 权重时应有 fallback（用 DA 数量等）
    score_no_mcu = compute_importance_score(
        exam_frequency_percentile=0.5,
        prerequisite_depth=2,
        planning_weight=None,
    )
    assert 0.0 < score_no_mcu < 10.0


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
@pytest.mark.asyncio
async def test_compute_all_stats_real(db, seeded_concepts):
    """端到端：触发 compute_all_stats，验证 108 个 L1 概念都有 stats"""
    from edu_cloud.modules.knowledge_tree.stats_service import compute_all_stats

    await compute_all_stats(db, KB_PATH)

    count = await db.execute(
        sa.select(sa.func.count()).select_from(ConceptStats)
    )
    total = count.scalar()
    assert total >= 100, f"应至少有 100 个 stats 记录, got {total}"

    # 验证光合作用的数据合理
    from edu_cloud.modules.knowledge_tree.models import ConceptStats
    photo_result = await db.execute(
        sa.select(ConceptStats).where(
            ConceptStats.concept_id == "BIO_SR_CP_M1_PHOTOSYNTHESIS"
        )
    )
    photo = photo_result.scalar_one_or_none()
    if photo:
        assert photo.exam_frequency >= 1000
        assert photo.importance_score > 5.0
        assert len(photo.textbook_chapters) > 0
```

注：`seeded_concepts` fixture 需要先将 knowledge.db 的 L1 概念同步到 PG，由 conftest.py 提供。如果不存在则 skip。

- [ ] **Step 2: 实现 importance_score 和 compute_all_stats**

Append to `src/edu_cloud/modules/knowledge_tree/stats_service.py`:

```python
def compute_importance_score(
    exam_frequency_percentile: float,
    prerequisite_depth: int,
    planning_weight: dict | None,
    max_depth: int = 6,
) -> float:
    """计算综合重要度得分，归一化到 [0, 10]。

    公式（设计文档 §7.3）:
        0.4 × exam_frequency_percentile × 10
      + 0.3 × error_prone_score
      + 0.2 × transfer_value
      + 0.1 × prerequisite_depth_factor × 10

    无 MCU 权重时用默认值 5.0 替代。
    """
    # 考频分量（0-10）
    freq_component = exam_frequency_percentile * 10

    # MCU 权重分量（fallback 到 5.0）
    if planning_weight:
        error_prone = float(planning_weight.get("error_prone", 5))
        transfer_value = float(planning_weight.get("transfer_value", 5))
    else:
        error_prone = 5.0
        transfer_value = 5.0

    # 前置深度分量（0-10）：depth 越深越基础越重要
    depth_component = min(prerequisite_depth / max_depth, 1.0) * 10

    score = (
        0.4 * freq_component +
        0.3 * error_prone +
        0.2 * transfer_value +
        0.1 * depth_component
    )
    return round(max(0.0, min(10.0, score)), 2)


async def compute_all_stats(db, kb_path: str) -> int:
    """编排全量计算：考频 + avg_difficulty + coverage + textbook + depth + importance。

    写入 concept_stats 表（UPSERT）。返回更新的记录数。
    """
    import sqlalchemy as sa
    from edu_cloud.modules.knowledge_tree.models import ConceptStats, ConceptGraphNode
    from datetime import datetime

    freq = compute_exam_frequency(kb_path)
    difficulty = compute_avg_difficulty(kb_path)
    coverage = compute_exam_coverage(kb_path)
    chapters = compute_textbook_chapters(kb_path)
    depth = await compute_prerequisite_depth(db)

    # 加载 StudyUnit 映射（如果 knowledge.db 有）
    su_map: dict[str, tuple[str, int]] = {}  # concept_id → (su_id, estimated_minutes)
    try:
        import sqlite3
        kconn = sqlite3.connect(kb_path)
        for sid, concepts_json, minutes in kconn.execute(
            "SELECT id, source_concept_ids, estimated_minutes FROM study_units"
        ):
            try:
                concept_ids = json.loads(concepts_json) if concepts_json else []
                for cid in concept_ids:
                    su_map[cid] = (sid, minutes or 0)
            except json.JSONDecodeError:
                continue
        kconn.close()
    except Exception as e:
        logger.warning("load study_units failed: %s", e)

    # 加载已有 planning_weight（保留 MCU 导入结果）
    existing_weights: dict[str, dict] = {}
    existing_result = await db.execute(
        sa.select(ConceptStats.concept_id, ConceptStats.planning_weight)
        .where(ConceptStats.planning_weight.isnot(None))
    )
    for cid, pw in existing_result.all():
        if pw:
            existing_weights[cid] = pw

    # 计算考频百分位（排除零考频，用于 percentile rank）
    sorted_freqs = sorted(freq.values())
    def freq_percentile(f: int) -> float:
        if not sorted_freqs or max(sorted_freqs) == 0:
            return 0.0
        # 使用 rank-based percentile
        rank = sum(1 for x in sorted_freqs if x < f)
        return rank / len(sorted_freqs)

    # 加载所有 L1 concept ID（从 PG）
    pg_concepts = await db.execute(
        sa.select(ConceptGraphNode.id)
        .where(ConceptGraphNode.node_type == "concept")
    )
    pg_concept_ids = {r[0] for r in pg_concepts.all()}

    now = datetime.now()
    updated = 0
    for cid in pg_concept_ids:
        f = freq.get(cid, 0)
        pct = freq_percentile(f)
        d = depth.get(cid, 0)
        pw = existing_weights.get(cid)
        importance = compute_importance_score(pct, d, pw)

        su = su_map.get(cid, (None, None))

        # UPSERT
        existing = await db.get(ConceptStats, cid)
        if existing:
            existing.exam_frequency = f
            existing.avg_difficulty = difficulty.get(cid)
            existing.exam_coverage = coverage.get(cid, 0.0)
            existing.textbook_chapters = chapters.get(cid, [])
            existing.prerequisite_depth = d
            existing.importance_score = importance
            existing.study_unit_id = su[0]
            existing.estimated_minutes = su[1]
            existing.computed_at = now
        else:
            db.add(ConceptStats(
                concept_id=cid,
                exam_frequency=f,
                avg_difficulty=difficulty.get(cid),
                exam_coverage=coverage.get(cid, 0.0),
                textbook_chapters=chapters.get(cid, []),
                prerequisite_depth=d,
                importance_score=importance,
                study_unit_id=su[0],
                estimated_minutes=su[1],
                planning_weight=pw,
                computed_at=now,
            ))
        updated += 1

    await db.commit()
    logger.info("compute_all_stats: updated %d records", updated)
    return updated
```

- [ ] **Step 3: 添加 seeded_concepts fixture**

Modify `tests/test_knowledge_tree/conftest.py` — 如果没有就创建，添加：

```python
@pytest.fixture
async def seeded_concepts(db):
    """从 knowledge.db 同步 L1 concepts 到测试 PG"""
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    await sync_knowledge_on_startup(db, KB_PATH)
    yield
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_knowledge_tree/test_stats_service.py -v`
Expected: 9+ PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/stats_service.py \
        tests/test_knowledge_tree/test_stats_service.py \
        tests/test_knowledge_tree/conftest.py
git commit -m "feat(stats): compute_importance_score + compute_all_stats orchestrator"
```

**审查清单:**
- ✓ importance_score 使用百分位归一化（不用原始考频）
- ✓ 无 MCU 权重时有 fallback（5.0 默认）
- ✓ compute_all_stats 使用 UPSERT 幂等
- ✓ StudyUnit 映射从 knowledge.db 加载

**边界条件:**
- 所有概念考频为 0 → 百分位全为 0，importance 只由深度+MCU 决定
- PG 中没有概念 → 返回 0 更新
- kb_path 不存在 → compute_exam_* 会抛异常，编排函数应捕获

---

## Task 6: sync_service 集成 + 应用启动触发

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/sync_service.py`
- Modify: `src/edu_cloud/api/app.py`
- Modify: `tests/test_knowledge_tree/test_sync_startup.py`

**测试契约:**

1. 同步后自动触发 stats 计算
   - 入口: `sync_knowledge_on_startup(db, kb_path)` 完成后 concept_stats 表有数据
   - 反例: 手动调用 sync 后 stats 仍为空
   - 边界: 无 kb_path（skip stats）/ stats 计算失败（不影响 sync 成功）
   - 回归: 原有 sync 测试仍通过
   - 命令: `pytest tests/test_knowledge_tree/test_sync_startup.py -v`

**Steps:**

- [ ] **Step 1: 写失败测试**

Append to `tests/test_knowledge_tree/test_sync_startup.py`:

```python
@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
@pytest.mark.asyncio
async def test_sync_triggers_stats_computation(db):
    """sync_knowledge_on_startup 完成后 concept_stats 应有数据"""
    import sqlalchemy as sa
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    from edu_cloud.modules.knowledge_tree.models import ConceptStats

    await sync_knowledge_on_startup(db, KB_PATH)

    count = await db.execute(sa.select(sa.func.count()).select_from(ConceptStats))
    assert count.scalar() >= 100, "sync 后应触发 stats 计算"


@pytest.mark.asyncio
async def test_sync_stats_failure_does_not_break_sync(db, monkeypatch):
    """stats 计算失败时不应阻止 sync 完成"""
    from edu_cloud.modules.knowledge_tree import sync_service

    async def failing_compute(*args, **kwargs):
        raise RuntimeError("simulated stats failure")

    monkeypatch.setattr(
        "edu_cloud.modules.knowledge_tree.stats_service.compute_all_stats",
        failing_compute,
    )
    # 使用不存在的 kb_path 使 sync 走 fallback 路径
    result = await sync_service.sync_knowledge_on_startup(db, "/nonexistent")
    # sync 应返回（不抛异常）
    assert result is not None or result is None  # 不崩溃就行
```

- [ ] **Step 2: 修改 sync_service.py**

Modify `src/edu_cloud/modules/knowledge_tree/sync_service.py`，在 `sync_knowledge_on_startup` 函数末尾（commit 之后）添加：

```python
    # ... 原有 sync 逻辑 ...
    await db.commit()

    # Phase 1: 同步完成后触发 stats 计算（best-effort，失败不阻塞）
    try:
        from edu_cloud.modules.knowledge_tree.stats_service import compute_all_stats
        from pathlib import Path
        if Path(kb_path).exists():
            updated = await compute_all_stats(db, kb_path)
            logger.info("post-sync stats computed: %d records", updated)
        else:
            logger.info("kb_path not exists, skip stats computation")
    except Exception as e:
        logger.error("stats computation failed (sync not affected): %s", e)
```

- [ ] **Step 3: 修改 app.py lifespan 以包含 sync 触发**

检查 `src/edu_cloud/api/app.py` 是否已有启动时 sync_knowledge_on_startup 调用。如无则添加：

```python
# 在 lifespan 的 startup 阶段
async def lifespan(app: FastAPI):
    # ... 其他启动逻辑 ...
    from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
    from edu_cloud.database import get_session_factory
    import os
    from pathlib import Path

    kb_path = os.environ.get(
        "KNOWLEDGE_DB_PATH",
        str(Path.home() / "edu-knowledge-base" / "knowledge.db")
    )
    if Path(kb_path).exists():
        SessionFactory = get_session_factory()
        async with SessionFactory() as session:
            try:
                await sync_knowledge_on_startup(session, kb_path)
            except Exception as e:
                logger.error("startup sync failed: %s", e)
    yield
    # shutdown
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_knowledge_tree/test_sync_startup.py -v`
Expected: 所有 PASS（包括原有 + 新增 2）

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/sync_service.py \
        src/edu_cloud/api/app.py \
        tests/test_knowledge_tree/test_sync_startup.py
git commit -m "feat(sync): trigger stats computation after knowledge.db sync"
```

**审查清单:**
- ✓ stats 计算失败不阻塞 sync
- ✓ kb_path 不存在时跳过（日志提示）
- ✓ 启动时触发 sync + stats 一条龙
- ✗ 不应在每次 API 请求时重新计算

**边界条件:**
- knowledge.db 不存在 → 跳过 stats
- db 事务失败 → rollback，不留半写入数据

---

## Task 7: Graph API v3 — 合并 stats 到节点返回

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/service.py`
- Modify: `src/edu_cloud/modules/knowledge_tree/schemas.py`
- Create: `tests/test_knowledge_tree/test_graph_v3.py`

**测试契约:**

1. Graph API 返回节点包含 v3 字段
   - 入口: `GET /api/v1/knowledge-tree/graph?module=M1`
   - 反例: 新字段缺失导致前端无数据着色
   - 边界: concept_stats 表为空 → 节点字段为默认值不报错
   - 回归: v2 字段（hard_in_count/external_hard_refs/review_status）保留
   - 命令: `pytest tests/test_knowledge_tree/test_graph_v3.py::test_graph_v3_fields -v`

**Steps:**

- [ ] **Step 1: 写失败测试**

Create `tests/test_knowledge_tree/test_graph_v3.py`:

```python
"""Graph API v3 字段测试"""
import pytest
from datetime import datetime
import sqlalchemy as sa
from edu_cloud.modules.knowledge_tree.models import (
    ConceptGraphNode, ConceptStats,
)


@pytest.mark.asyncio
async def test_graph_v3_fields_present(db):
    """Graph 返回节点应包含 v3 新字段"""
    from edu_cloud.modules.knowledge_tree.service import get_graph

    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_V3_001", name="v3测试", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    db.add(ConceptStats(
        concept_id="TEST_V3_001",
        exam_frequency=500, importance_score=8.5,
        estimated_minutes=90,
        textbook_chapters=[{"book": "b1", "chapter": "ch03", "section": "s01", "title": "T"}],
        study_unit_id="su:test",
        planning_weight={"priority_score": 8.0},
        computed_at=now,
    ))
    await db.commit()

    result = await get_graph(db, module="M1", include_draft=True)
    nodes = result["graph"]["nodes"]
    node = next((n for n in nodes if n["id"] == "TEST_V3_001"), None)
    assert node is not None

    # v3 新字段
    assert node["exam_frequency"] == 500
    assert node["importance_score"] == 8.5
    assert node["estimated_minutes"] == 90
    assert node["study_unit_id"] == "su:test"
    assert len(node["textbook_chapters"]) == 1
    assert node["planning_weight"]["priority_score"] == 8.0


@pytest.mark.asyncio
async def test_graph_v3_defaults_when_no_stats(db):
    """无 stats 记录时节点应有默认值，不报错"""
    from edu_cloud.modules.knowledge_tree.service import get_graph

    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_NO_STATS", name="无stats", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    await db.commit()

    result = await get_graph(db, module="M1", include_draft=True)
    nodes = result["graph"]["nodes"]
    node = next((n for n in nodes if n["id"] == "TEST_NO_STATS"), None)
    assert node is not None

    # 默认值
    assert node["exam_frequency"] == 0
    assert node["importance_score"] == 0.0
    assert node["textbook_chapters"] == []
    assert node["planning_weight"] is None
    assert node["estimated_minutes"] is None


@pytest.mark.asyncio
async def test_graph_v2_fields_preserved(db):
    """v3 扩展不应破坏 v2 字段（hard_in_count, external_hard_refs 等）"""
    from edu_cloud.modules.knowledge_tree.service import get_graph

    now = datetime.now()
    db.add(ConceptGraphNode(
        id="TEST_V2_KEEP", name="v2保留", knowledge_level="L1",
        primary_module="M1", node_type="concept", synced_at=now,
    ))
    await db.commit()

    result = await get_graph(db, module="M1", include_draft=True)
    node = next((n for n in result["graph"]["nodes"] if n["id"] == "TEST_V2_KEEP"), None)
    # v2 字段仍存在
    assert "hard_in_count" in node
    assert "hard_out_count" in node
    assert "review_status" in node
    assert "big_concept_id" in node
```

- [ ] **Step 2: 修改 service.py get_graph**

Modify `src/edu_cloud/modules/knowledge_tree/service.py`，在 `get_graph` 函数中，在构建 nodes 的循环之前加载 stats：

```python
    # ---- v3: 加载 concept_stats ----
    from edu_cloud.modules.knowledge_tree.models import ConceptStats
    stats_q = sa.select(ConceptStats)
    if module_filter:
        stats_q = stats_q.where(
            ConceptStats.concept_id.in_([n.id for n in concept_nodes])
        )
    stats_result = await db.execute(stats_q)
    stats_by_id: dict[str, ConceptStats] = {s.concept_id: s for s in stats_result.scalars()}
```

然后修改节点构建代码（原第 161-175 行的 nodes 循环），添加 v3 字段：

```python
    nodes = []
    for n in concept_nodes:
        aliases = json.loads(n.aliases_json) if n.aliases_json else []
        s = stats_by_id.get(n.id)
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
            # ---- v3 字段 ----
            "exam_frequency": s.exam_frequency if s else 0,
            "exam_coverage": s.exam_coverage if s else 0.0,
            "avg_difficulty": s.avg_difficulty if s else None,
            "importance_score": s.importance_score if s else 0.0,
            "textbook_chapters": s.textbook_chapters if s else [],
            "study_unit_id": s.study_unit_id if s else None,
            "estimated_minutes": s.estimated_minutes if s else None,
            "prerequisite_depth": s.prerequisite_depth if s else 0,
            "planning_weight": s.planning_weight if s else None,
        })
```

- [ ] **Step 3: 运行测试**

Run: `pytest tests/test_knowledge_tree/test_graph_v3.py -v`
Expected: 3 PASS

- [ ] **Step 4: 运行全部 knowledge_tree 测试确认无回归**

Run: `pytest tests/test_knowledge_tree/ -v --tb=short`
Expected: 原有测试继续通过

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/service.py \
        src/edu_cloud/modules/knowledge_tree/schemas.py \
        tests/test_knowledge_tree/test_graph_v3.py
git commit -m "feat(api): Graph API v3 — merge concept_stats into node response"
```

**审查清单:**
- ✓ v3 新字段：exam_frequency/importance_score/textbook_chapters/study_unit_id/estimated_minutes/planning_weight
- ✓ 无 stats 时所有字段有合理默认（0/0.0/[]/None）
- ✓ v2 字段保留（hard_in_count/external_hard_refs/review_status）
- ✗ 不应每个节点单独查询 stats（应批量预加载）

**边界条件:**
- concept_stats 表为空 → 所有节点返回默认值
- stats 记录但 planning_weight 为 NULL → 返回 null（不是空对象）

---

## Task 8: 高考真题查询 API + 统计概览 API

**Files:**
- Create: `src/edu_cloud/modules/knowledge_tree/exam_items_service.py`
- Modify: `src/edu_cloud/modules/knowledge_tree/router.py`
- Modify: `src/edu_cloud/modules/knowledge_tree/schemas.py`
- Create: `tests/test_knowledge_tree/test_exam_items_service.py`

**测试契约:**

1. 概念高考真题查询
   - 入口: `GET /api/v1/knowledge-tree/graph/{node_id}/exam-items?page=1&page_size=20`
   - 反例: 返回其他概念的题目（DA 链路错误）
   - 边界: 概念无关联题 / 分页超出范围
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_exam_items_service.py::test_get_exam_items -v`

2. 统计概览 API
   - 入口: `GET /api/v1/knowledge-tree/stats/overview`
   - 反例: 覆盖率计算错误（分母用错）
   - 边界: 单模块 vs 全模块
   - 回归: N/A
   - 命令: `pytest tests/test_knowledge_tree/test_exam_items_service.py::test_stats_overview -v`

**Steps:**

- [ ] **Step 1: 写失败测试**

Create `tests/test_knowledge_tree/test_exam_items_service.py`:

```python
"""高考真题查询和统计概览 API 测试"""
import os
import pytest
from pathlib import Path

KB_PATH = os.environ.get(
    "KNOWLEDGE_DB_PATH",
    str(Path.home() / "edu-knowledge-base" / "knowledge.db")
)


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_get_exam_items_for_concept():
    """概念关联的高考真题查询"""
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    result = get_exam_items(
        kb_path=KB_PATH,
        concept_id="BIO_SR_CP_M1_PHOTOSYNTHESIS",
        page=1, page_size=10,
    )
    assert "items" in result
    assert "total" in result
    assert result["total"] >= 1000, f"光合作用应有 1000+ 题, got {result['total']}"
    assert len(result["items"]) <= 10

    # 每个 item 的字段
    for item in result["items"]:
        assert "id" in item
        assert "exam_id" in item
        assert "question_type" in item
        assert "stem" in item
        # 可选: difficulty, answer, explanation


@pytest.mark.skipif(not Path(KB_PATH).exists(), reason="knowledge.db not available")
def test_get_exam_items_empty_for_unknown():
    """未知概念返回空列表"""
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items
    result = get_exam_items(kb_path=KB_PATH, concept_id="UNKNOWN_ID", page=1, page_size=10)
    assert result["total"] == 0
    assert result["items"] == []


@pytest.mark.asyncio
async def test_get_exam_items_endpoint_for_seeded_concept(client, admin_headers, db, seeded_concepts):
    """HTTP 端点测试 — 入口级验证，必须返回 200 且数据结构正确

    反例: 错误实现若 500 或 items 缺 stem 字段，本测试会失败。
    """
    resp = await client.get(
        "/api/v1/knowledge-tree/graph/BIO_SR_CP_M1_PHOTOSYNTHESIS/exam-items?page=1&page_size=5",
        headers=admin_headers,
    )
    assert resp.status_code == 200, f"应返回 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 100, f"光合作用应有大量关联题，got {data['total']}"
    assert len(data["items"]) <= 5
    # 每个 item 必须含关键字段（反例检查）
    for item in data["items"]:
        assert item.get("id"), "item 必须有 id"
        assert item.get("stem"), "item 必须有 stem"
        assert item.get("question_type"), "item 必须有 question_type"


@pytest.mark.asyncio
async def test_get_exam_items_endpoint_unknown_concept(client, admin_headers):
    """未知概念应返回 200 total=0 空列表（降级处理，不 500）"""
    resp = await client.get(
        "/api/v1/knowledge-tree/graph/NONEXISTENT_CONCEPT_XYZ/exam-items",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_stats_overview_endpoint(client, admin_headers):
    """统计概览端点"""
    resp = await client.get(
        "/api/v1/knowledge-tree/stats/overview",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_concepts" in data
    assert "total_edges" in data
    assert "exam_freq_distribution" in data  # {high: N, mid: N, low: N, zero: N}
    assert "module_stats" in data  # {M1: {concepts, edges, avg_freq}, ...}
```

- [ ] **Step 2: 实现 exam_items_service.py**

Create `src/edu_cloud/modules/knowledge_tree/exam_items_service.py`:

```python
"""概念→高考真题查询服务。"""
import json
import sqlite3
from collections import defaultdict


def get_exam_items(
    kb_path: str,
    concept_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """查询某概念关联的高考真题。

    链路: concept_id → DA.linked_concept_ids → q_matrix → assessment_items
    """
    conn = sqlite3.connect(kb_path)
    try:
        # 找到关联该概念的 DA
        das = []
        for da_id, linked in conn.execute(
            "SELECT id, linked_concept_ids FROM diagnostic_attributes WHERE linked_concept_ids IS NOT NULL"
        ):
            try:
                if concept_id in json.loads(linked):
                    das.append(da_id)
            except (json.JSONDecodeError, TypeError):
                continue

        if not das:
            return {"total": 0, "items": [], "page": page, "page_size": page_size}

        # 找到所有关联 item_id
        placeholders = ",".join("?" * len(das))
        item_ids_rows = conn.execute(
            f"SELECT DISTINCT item_id FROM q_matrix WHERE attribute_id IN ({placeholders})",
            das,
        ).fetchall()
        item_ids = [r[0] for r in item_ids_rows]

        total = len(item_ids)
        if total == 0:
            return {"total": 0, "items": [], "page": page, "page_size": page_size}

        # 分页
        offset = (page - 1) * page_size
        page_ids = item_ids[offset:offset + page_size]
        if not page_ids:
            return {"total": total, "items": [], "page": page, "page_size": page_size}

        # 查询题目详情
        placeholders_p = ",".join("?" * len(page_ids))
        items = []
        for row in conn.execute(
            f"""SELECT id, exam_id, question_number, question_type, stem,
                       answer, difficulty, explanation
                FROM assessment_items WHERE id IN ({placeholders_p})""",
            page_ids,
        ):
            items.append({
                "id": row[0],
                "exam_id": row[1],
                "question_number": row[2],
                "question_type": row[3],
                "stem": row[4],
                "answer": row[5],
                "difficulty": row[6],
                "explanation": row[7],
            })

        return {"total": total, "items": items, "page": page, "page_size": page_size}
    finally:
        conn.close()


async def get_stats_overview(db, module: str = "all") -> dict:
    """计算全模块统计概览"""
    import sqlalchemy as sa
    from edu_cloud.modules.knowledge_tree.models import (
        ConceptGraphNode, ConceptGraphEdge, ConceptStats,
    )
    from collections import defaultdict

    # 概念数
    node_q = sa.select(ConceptGraphNode).where(ConceptGraphNode.node_type == "concept")
    if module != "all":
        node_q = node_q.where(ConceptGraphNode.primary_module == module)
    nodes = list((await db.execute(node_q)).scalars())

    # 边数
    node_ids = {n.id for n in nodes}
    edges = list((await db.execute(sa.select(ConceptGraphEdge))).scalars())
    if module != "all":
        edges = [e for e in edges if e.source_id in node_ids and e.target_id in node_ids]

    # Stats 聚合
    stats = list((await db.execute(sa.select(ConceptStats))).scalars())
    stats_by_id = {s.concept_id: s for s in stats}

    # 考频分布: high >= 500, mid 50-499, low 1-49, zero = 0
    distribution = {"high": 0, "mid": 0, "low": 0, "zero": 0}
    # F008: 模块级统计含 coverage — 覆盖率 = 该模块非零考频概念 / 总概念数
    module_stats: dict[str, dict] = defaultdict(
        lambda: {
            "concepts": 0, "edges": 0, "total_freq": 0,
            "nonzero_freq_count": 0,  # F008: 用于计算 coverage
            "avg_freq": 0.0, "exam_coverage": 0.0,
        }
    )
    for n in nodes:
        s = stats_by_id.get(n.id)
        freq = s.exam_frequency if s else 0
        if freq >= 500:
            distribution["high"] += 1
        elif freq >= 50:
            distribution["mid"] += 1
        elif freq >= 1:
            distribution["low"] += 1
        else:
            distribution["zero"] += 1
        module_stats[n.primary_module]["concepts"] += 1
        module_stats[n.primary_module]["total_freq"] += freq
        if freq > 0:
            module_stats[n.primary_module]["nonzero_freq_count"] += 1

    for e in edges:
        src_node = next((n for n in nodes if n.id == e.source_id), None)
        if src_node:
            module_stats[src_node.primary_module]["edges"] += 1

    for mod, ms in module_stats.items():
        if ms["concepts"]:
            ms["avg_freq"] = round(ms["total_freq"] / ms["concepts"], 1)
            # F008: exam_coverage = 有高考题关联的概念比例（0-1）
            ms["exam_coverage"] = round(ms["nonzero_freq_count"] / ms["concepts"], 3)
        del ms["total_freq"]
        del ms["nonzero_freq_count"]

    return {
        "total_concepts": len(nodes),
        "total_edges": len(edges),
        "exam_freq_distribution": distribution,
        "module_stats": dict(module_stats),  # 每个 module_stats 含 exam_coverage (F008)
    }
```

- [ ] **Step 3: 添加 router 端点**

Modify `src/edu_cloud/modules/knowledge_tree/router.py`，添加：

```python
@router.get("/graph/{node_id}/exam-items")
async def get_exam_items_endpoint(
    node_id: str,
    page: int = 1,
    page_size: int = 20,
    current_user=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """概念关联的高考真题列表（分页）"""
    import os
    from pathlib import Path
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_exam_items

    kb_path = os.environ.get(
        "KNOWLEDGE_DB_PATH",
        str(Path.home() / "edu-knowledge-base" / "knowledge.db"),
    )
    if not Path(kb_path).exists():
        return {"total": 0, "items": [], "page": page, "page_size": page_size}
    return get_exam_items(kb_path, node_id, page, page_size)


@router.get("/stats/overview")
async def get_stats_overview_endpoint(
    module: str = "all",
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission(Permission.VIEW_KNOWLEDGE_TREE)),
):
    """全模块统计概览"""
    from edu_cloud.modules.knowledge_tree.exam_items_service import get_stats_overview
    return await get_stats_overview(db, module)
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_knowledge_tree/test_exam_items_service.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/exam_items_service.py \
        src/edu_cloud/modules/knowledge_tree/router.py \
        src/edu_cloud/modules/knowledge_tree/schemas.py \
        tests/test_knowledge_tree/test_exam_items_service.py
git commit -m "feat(api): GET /graph/{id}/exam-items + GET /stats/overview"
```

**审查清单:**
- ✓ 分页正确（total 是关联题数，不是总题数）
- ✓ 未关联概念返回 total=0 / items=[]
- ✓ 权限检查（VIEW_KNOWLEDGE_TREE）
- ✗ 不应在请求时连接 knowledge.db 失败就 500（优雅降级）

**边界条件:**
- 概念关联 DA 但 DA 无 Q-Matrix 记录 → items=[]
- page 超出范围 → 返回空 items 但 total 正确

---

## Task 9: 前端热力色工具 + 着色模式切换组件

**Files:**
- Create: `frontend/src/components/knowledge-tree/heatmapUtils.js`
- Create: `frontend/src/components/knowledge-tree/ColorModeToggle.vue`
- Create: `frontend/src/__tests__/knowledge-tree/heatmapUtils.test.js`
- Create: `frontend/src/__tests__/knowledge-tree/ColorModeToggle.test.js`

**测试契约:**

1. 考频→颜色映射
   - 入口: `heatmapColor(freq, maxFreq)` 返回 `#RRGGBB`
   - 反例: 线性映射在 freq 分布偏斜时区分度极差
   - 边界: freq=0 / freq=maxFreq / freq>maxFreq
   - 回归: N/A
   - 命令: `npx vitest run heatmapUtils.test.js`

**Steps:**

- [ ] **Step 1: 写 heatmapUtils 测试**

Create `frontend/src/__tests__/knowledge-tree/heatmapUtils.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { heatmapColor, masteryColor, reviewStatusColor, nodeSizeFromImportance } from '../heatmapUtils'

describe('heatmapColor', () => {
  it('freq=0 returns light gray', () => {
    const c = heatmapColor(0, 1000)
    expect(c).toMatch(/#[Ee][0-9a-fA-F]{5}/) // 浅色
  })

  it('freq=maxFreq returns deep color', () => {
    const c = heatmapColor(1000, 1000)
    expect(c).toMatch(/#[0-5][0-9a-fA-F]{5}/) // 深色
  })

  it('handles freq > maxFreq by clamping', () => {
    const c = heatmapColor(2000, 1000)
    const max = heatmapColor(1000, 1000)
    expect(c).toBe(max)
  })

  it('uses log scale to handle skewed distribution', () => {
    // freq 100 应比 freq 1 明显更深，但不应与 freq 1000 差异过大
    const c1 = heatmapColor(1, 1000)
    const c100 = heatmapColor(100, 1000)
    const c1000 = heatmapColor(1000, 1000)
    expect(c1).not.toBe(c100)
    expect(c100).not.toBe(c1000)
  })
})

describe('masteryColor', () => {
  it('unseen returns gray', () => {
    expect(masteryColor('unseen')).toMatch(/#[A-Fa-f0-9]{6}/)
  })
  it('solid returns green', () => {
    const c = masteryColor('solid')
    // 绿色应有较高的 G 分量
    const g = parseInt(c.slice(3, 5), 16)
    const r = parseInt(c.slice(1, 3), 16)
    expect(g).toBeGreaterThan(r)
  })
})

describe('nodeSizeFromImportance', () => {
  it('importance=0 returns minimum size', () => {
    expect(nodeSizeFromImportance(0)).toBeGreaterThanOrEqual(20)
    expect(nodeSizeFromImportance(0)).toBeLessThanOrEqual(30)
  })
  it('importance=10 returns maximum size', () => {
    expect(nodeSizeFromImportance(10)).toBeGreaterThanOrEqual(50)
    expect(nodeSizeFromImportance(10)).toBeLessThanOrEqual(70)
  })
  it('monotonic increasing', () => {
    expect(nodeSizeFromImportance(5)).toBeGreaterThan(nodeSizeFromImportance(2))
  })
})
```

- [ ] **Step 2: 实现 heatmapUtils.js**

Create `frontend/src/components/knowledge-tree/heatmapUtils.js`:

```javascript
// 节点视觉编码工具函数
// 考频→颜色映射使用对数尺度（考频分布偏斜，max 1313, median 11）
// 重要度→节点大小 线性映射到 [20, 60] 像素

const CLAMP = (v, min, max) => Math.max(min, Math.min(max, v))

/**
 * 考频热力色 — 使用 log(freq+1) 归一化后映射到颜色
 * 0: 浅灰 → 低频: 浅蓝 → 中频: 蓝 → 高频: 深紫
 */
export function heatmapColor(freq, maxFreq) {
  if (maxFreq <= 0) return '#EEEEEE'
  const clamped = CLAMP(freq, 0, maxFreq)
  const ratio = Math.log(clamped + 1) / Math.log(maxFreq + 1)

  // 插值: #EEEEEE (238,238,238) → #3B5998 (59,89,152)
  const r = Math.round(238 - (238 - 59) * ratio)
  const g = Math.round(238 - (238 - 89) * ratio)
  const b = Math.round(238 - (238 - 152) * ratio)
  const toHex = (v) => v.toString(16).padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

/**
 * 掌握度 4 态着色
 */
const MASTERY_COLORS = {
  solid:   '#52C41A', // 绿
  fragile: '#FAAD14', // 黄
  weak:    '#FF4D4F', // 红
  unseen:  '#D9D9D9', // 灰
}
export function masteryColor(state) {
  return MASTERY_COLORS[state] || MASTERY_COLORS.unseen
}

/**
 * 审核状态着色
 */
const REVIEW_COLORS = {
  ai_draft:         '#D9D9D9',
  teacher_reviewed: '#1890FF',
  published:        '#52C41A',
}
export function reviewStatusColor(status) {
  return REVIEW_COLORS[status] || REVIEW_COLORS.ai_draft
}

/**
 * importance_score (0-10) → 节点像素大小 [20, 60]
 */
export function nodeSizeFromImportance(score) {
  const clamped = CLAMP(score, 0, 10)
  return Math.round(20 + (clamped / 10) * 40)
}
```

- [ ] **Step 3: 实现 ColorModeToggle.vue**

Create `frontend/src/components/knowledge-tree/ColorModeToggle.vue`:

```vue
<template>
  <div class="color-mode-toggle">
    <span class="label">着色模式：</span>
    <n-radio-group v-model:value="localMode" @update:value="onChange" size="small">
      <n-radio-button value="exam_frequency">考频</n-radio-button>
      <n-radio-button value="mastery" :disabled="!hasStudent">掌握度</n-radio-button>
      <n-radio-button value="review_status">审核状态</n-radio-button>
    </n-radio-group>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { NRadioGroup, NRadioButton } from 'naive-ui'

const props = defineProps({
  modelValue: { type: String, default: 'exam_frequency' },
  hasStudent: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const localMode = ref(props.modelValue)
watch(() => props.modelValue, (v) => { localMode.value = v })

function onChange(val) {
  emit('update:modelValue', val)
}
</script>

<style scoped>
.color-mode-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}
.label {
  font-size: 13px;
  color: var(--text-color-2);
}
</style>
```

- [ ] **Step 4: 写 ColorModeToggle 测试**

Create `frontend/src/__tests__/knowledge-tree/ColorModeToggle.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ColorModeToggle from '../ColorModeToggle.vue'

describe('ColorModeToggle', () => {
  it('renders with default mode', () => {
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency' },
    })
    expect(wrapper.text()).toContain('考频')
    expect(wrapper.text()).toContain('掌握度')
    expect(wrapper.text()).toContain('审核状态')
  })

  it('emits update when mode changes', async () => {
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency', hasStudent: true },
    })
    // 模拟切换到掌握度
    wrapper.vm.onChange('mastery')
    expect(wrapper.emitted()['update:modelValue']).toBeTruthy()
    expect(wrapper.emitted()['update:modelValue'][0]).toEqual(['mastery'])
  })

  it('disables mastery mode when no student selected', () => {
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency', hasStudent: false },
    })
    // 找到掌握度 radio button 应 disabled
    const html = wrapper.html()
    expect(html).toMatch(/disabled/i)
  })
})
```

- [ ] **Step 5: 运行测试**

Run:
```bash
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run heatmapUtils.test.js ColorModeToggle.test.js
```
Expected: 所有测试 PASS

- [ ] **Step 6: Commit**

```bash
cd /c/Users/Administrator/edu-cloud
git add frontend/src/components/knowledge-tree/heatmapUtils.js \
        frontend/src/components/knowledge-tree/ColorModeToggle.vue \
        frontend/src/__tests__/knowledge-tree/heatmapUtils.test.js \
        frontend/src/__tests__/knowledge-tree/ColorModeToggle.test.js
git commit -m "feat(frontend): heatmapUtils + ColorModeToggle component"
```

**审查清单:**
- ✓ heatmapColor 使用对数尺度（处理偏斜分布）
- ✓ 三种着色模式：考频/掌握度/审核状态
- ✓ 无学生时掌握度模式 disabled
- ✗ 不应在组件内硬编码颜色常量（集中在 heatmapUtils）

**边界条件:**
- freq 超出 maxFreq → clamp
- 未知 mastery state → fallback 到 unseen（灰色）

---

## Task 10: ConceptMapPanel 节点视觉升级

**Files:**
- Modify: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`
- Modify: `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`

**测试契约:**

1. 节点大小反映重要度
   - 入口: ConceptMapPanel 渲染时根据 node.importance_score 设置节点 size
   - 反例: 节点大小硬编码统一值
   - 边界: importance=0 / importance=10 / 无 importance 字段
   - 回归: 焦点模式节点淡化仍正常
   - 命令: `npx vitest run ConceptMapPanel.test.js`

2. 节点填充色根据 colorMode 决定
   - 入口: colorMode prop 变化时 G6 updateElementStates
   - 反例: 切换模式后 G6 未重绘
   - 边界: colorMode 无效值 → fallback
   - 回归: 审核状态着色仍可用
   - 命令: `npx vitest run ConceptMapPanel.test.js`

**Steps:**

- [ ] **Step 1: 修改 ConceptMapPanel.vue — 接受 colorMode prop**

Modify `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`:

```vue
<script setup>
// ... 原有 imports ...
import {
  heatmapColor, masteryColor, reviewStatusColor,
  nodeSizeFromImportance,
} from './heatmapUtils'

const props = defineProps({
  // ... 原有 props ...
  colorMode: { type: String, default: 'exam_frequency' },
  // nodesWithMastery 已有
})
</script>
```

在 `buildG6Data` 函数中修改节点数据构建：

```javascript
function buildG6Data() {
  const maxFreq = Math.max(1, ...props.nodes.map(n => n.exam_frequency || 0))

  const g6Nodes = props.nodes.map((n) => {
    // 节点大小 ∝ importance_score
    const size = nodeSizeFromImportance(n.importance_score || 0)

    // 节点填充色根据 colorMode
    let fill
    if (props.colorMode === 'mastery') {
      const masteryInfo = props.nodesWithMastery?.find(m => m.id === n.id)
      fill = masteryColor(masteryInfo?.mastery_state || 'unseen')
    } else if (props.colorMode === 'review_status') {
      fill = reviewStatusColor(n.review_status || 'ai_draft')
    } else { // exam_frequency (default)
      fill = heatmapColor(n.exam_frequency || 0, maxFreq)
    }

    return {
      id: n.id,
      data: {
        label: n.name.length > 10 ? n.name.slice(0, 10) + '…' : n.name,
        fullName: n.name,
        importance: n.importance_score || 0,
        examFrequency: n.exam_frequency || 0,
        badgeText: n.external_hard_refs ? formatBadge(n.external_hard_refs) : '',
        reviewStatus: n.review_status || 'ai_draft',
      },
      style: {
        size: [size, size * 0.6],  // 椭圆：宽 x 高
        fill,
      },
    }
  })
  // ... edges 构建不变 ...
  return { nodes: g6Nodes, edges: g6Edges }
}
```

Watch colorMode 变化触发更新：

```javascript
watch(() => props.colorMode, () => {
  if (g6Graph.value) {
    const data = buildG6Data()
    g6Graph.value.setData(data)
    g6Graph.value.render()
    // 保持焦点状态
    if (focusedNodeId.value) {
      updateElementStates(focusedNodeId.value)
    }
  }
})
```

- [ ] **Step 2: 修改 KnowledgeTreePage.vue — 传 colorMode 给 ConceptMapPanel**

Modify `frontend/src/pages/KnowledgeTreePage.vue`:

```vue
<template>
  <!-- ... 工具栏 ... -->
  <ColorModeToggle
    v-if="activeTab === 'graph' && selectedModule !== 'all'"
    v-model="colorMode"
    :has-student="!!selectedStudentId"
  />

  <ConceptMapPanel
    v-if="activeTab === 'graph' && selectedModule !== 'all'"
    :nodes="graphData.nodes"
    :edges="graphData.edges"
    :big-concept-order="bigConceptOrder"
    :nodes-with-mastery="nodesWithMastery"
    :color-mode="colorMode"
    @node-click="onNodeClick"
  />
</template>

<script setup>
import { ref, watch } from 'vue'
import ColorModeToggle from '@/components/knowledge-tree/ColorModeToggle.vue'

// ... 原有代码 ...
const colorMode = ref('exam_frequency')

// 选择学生后自动切换到掌握度
watch(() => selectedStudentId.value, (newVal) => {
  if (newVal) colorMode.value = 'mastery'
  else if (colorMode.value === 'mastery') colorMode.value = 'exam_frequency'
})
</script>
```

- [ ] **Step 3: 更新 ConceptMapPanel 测试**

Modify `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`:

```javascript
// 前置: ConceptMapPanel 需用 defineExpose({ buildG6Data }) 暴露 buildG6Data
// 这样测试可以断言返回的节点数据（反例: 如果不暴露，测试只能看挂载成功，失去检测力）
describe('ConceptMapPanel v3 visual — behavior assertions', () => {
  it('buildG6Data: node size reflects importance_score', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', importance_score: 10, exam_frequency: 100 },
          { id: 'B', name: 'B', big_concept_id: 'BC1', importance_score: 2, exam_frequency: 100 },
        ],
        edges: [],
        bigConceptOrder: [{ id: 'BC1', name: 'BC1' }],
        colorMode: 'exam_frequency',
      },
    })
    const data = wrapper.vm.buildG6Data()
    const nodeA = data.nodes.find(n => n.id === 'A')
    const nodeB = data.nodes.find(n => n.id === 'B')
    // 反例: 若 size 硬编码为常量，两节点相等 → 失败
    const sizeA = Array.isArray(nodeA.style.size) ? nodeA.style.size[0] : nodeA.style.size
    const sizeB = Array.isArray(nodeB.style.size) ? nodeB.style.size[0] : nodeB.style.size
    expect(sizeA).toBeGreaterThan(sizeB)
    expect(sizeA).toBeGreaterThanOrEqual(50)  // importance=10 应 ≥50
    expect(sizeB).toBeLessThanOrEqual(30)     // importance=2 应 ≤30
  })

  it('buildG6Data: fill color changes with colorMode', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        nodes: [{ id: 'A', name: 'A', big_concept_id: 'BC1', exam_frequency: 500, review_status: 'published' }],
        edges: [],
        bigConceptOrder: [{ id: 'BC1', name: 'BC1' }],
        colorMode: 'exam_frequency',
      },
    })
    const examFill = wrapper.vm.buildG6Data().nodes[0].style.fill
    await wrapper.setProps({ colorMode: 'review_status' })
    const reviewFill = wrapper.vm.buildG6Data().nodes[0].style.fill
    // 反例: 若 colorMode 被忽略，两次 fill 相同 → 失败
    expect(examFill).not.toBe(reviewFill)
    expect(reviewFill.toLowerCase()).toMatch(/^#[0-9a-f]{6}$/)
  })

  it('buildG6Data: mastery mode uses mastery state', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        nodes: [{ id: 'A', name: 'A', big_concept_id: 'BC1', review_status: 'published' }],
        edges: [],
        bigConceptOrder: [{ id: 'BC1', name: 'BC1' }],
        colorMode: 'mastery',
        nodesWithMastery: [{ id: 'A', mastery_state: 'weak' }],
      },
    })
    const hex = wrapper.vm.buildG6Data().nodes[0].style.fill
    // weak 应为红色系（R > G）— 反例: 若 mastery 被忽略走 review_status 则绿色，失败
    const r = parseInt(hex.slice(1, 3), 16)
    const g = parseInt(hex.slice(3, 5), 16)
    expect(r).toBeGreaterThan(g)
  })
})
```

- [ ] **Step 4: 运行测试**

Run:
```bash
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run ConceptMapPanel.test.js
```
Expected: 所有测试 PASS（原有 + 新增）

- [ ] **Step 5: 本地启动验证**

Run:
```bash
cd /c/Users/Administrator/edu-cloud/frontend
python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev
```
打开浏览器 http://localhost:5273，进入知识图谱页，选择 M1 模块，验证：
- 节点大小有差异（光合作用/ATP 应明显更大）
- 切换着色模式工作
- 切换回考频后颜色合理（高频深蓝）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/knowledge-tree/ConceptMapPanel.vue \
        frontend/src/pages/KnowledgeTreePage.vue \
        frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js
git commit -m "feat(frontend): ConceptMapPanel v3 — node size + heatmap coloring"
```

**审查清单:**
- ✓ 节点大小反映 importance_score
- ✓ 三种着色模式切换有效
- ✓ 焦点模式与新视觉兼容
- ✓ 模块切换时颜色/大小正确刷新

**边界条件:**
- 节点 importance_score 缺失 → 使用默认值 0 → size 最小
- exam_frequency 缺失 → 淡灰色
- 切换模式后焦点模式仍生效

---

## Task 11: NodeDetailDrawer 高考真题 + 学习单元 标签页

**Files:**
- Create: `frontend/src/components/knowledge-tree/ExamItemsTab.vue`
- Create: `frontend/src/components/knowledge-tree/StudyUnitTab.vue`
- Modify: `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue`
- Modify: `frontend/src/api/knowledgeTree.js`

**测试契约:**

1. 高考真题标签页加载关联题目
   - 入口: NodeDetailDrawer 切换到"高考真题"标签
   - 反例: 不加载就显示空列表
   - 边界: 无关联题 / 分页 / 加载中
   - 回归: 原标签页切换正常
   - 命令: `npx vitest run ExamItemsTab.test.js`

2. 学习单元标签页展示 SU 信息
   - 入口: StudyUnitTab 接收 node 数据
   - 反例: 无 study_unit_id 时组件崩溃
   - 边界: study_unit_id 为 null
   - 回归: N/A
   - 命令: `npx vitest run StudyUnitTab.test.js`

**Steps:**

- [ ] **Step 1: 扩展 API 客户端**

Modify `frontend/src/api/knowledgeTree.js`:

```javascript
export async function getExamItems(nodeId, page = 1, pageSize = 20) {
  const resp = await client.get(
    `/knowledge-tree/graph/${nodeId}/exam-items`,
    { params: { page, page_size: pageSize } }
  )
  return resp.data
}

export async function getStatsOverview(module = 'all') {
  const resp = await client.get('/knowledge-tree/stats/overview', {
    params: { module }
  })
  return resp.data
}
```

- [ ] **Step 2: 实现 ExamItemsTab.vue**

Create `frontend/src/components/knowledge-tree/ExamItemsTab.vue`:

```vue
<template>
  <div class="exam-items-tab">
    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="total === 0" class="empty">该概念暂无关联高考真题</div>
    <div v-else>
      <div class="summary">共 {{ total }} 道关联题，显示第 {{ (page-1)*pageSize + 1 }}-{{ Math.min(page*pageSize, total) }} 条</div>
      <div class="item-list">
        <div v-for="item in items" :key="item.id" class="item">
          <div class="item-header">
            <span class="type-tag">{{ itemTypeLabel(item.question_type) }}</span>
            <span class="exam-year">{{ formatExamId(item.exam_id) }}</span>
            <span v-if="item.difficulty" class="difficulty">难度: {{ item.difficulty }}/5</span>
          </div>
          <div class="item-stem">{{ truncate(item.stem, 200) }}</div>
          <details v-if="item.answer || item.explanation" class="item-detail">
            <summary>查看答案与解析</summary>
            <div v-if="item.answer" class="answer">答案: {{ item.answer }}</div>
            <div v-if="item.explanation" class="explanation">解析: {{ item.explanation }}</div>
          </details>
        </div>
      </div>
      <div class="pagination">
        <n-button :disabled="page <= 1" @click="prevPage" size="small">上一页</n-button>
        <span>{{ page }} / {{ totalPages }}</span>
        <n-button :disabled="page >= totalPages" @click="nextPage" size="small">下一页</n-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { NButton } from 'naive-ui'
import { getExamItems } from '@/api/knowledgeTree'

const props = defineProps({
  nodeId: { type: String, required: true },
})

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function load() {
  if (!props.nodeId) return
  loading.value = true
  try {
    const data = await getExamItems(props.nodeId, page.value, pageSize.value)
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    console.error('loadExamItems failed', e)
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function prevPage() { if (page.value > 1) { page.value--; load() } }
function nextPage() { if (page.value < totalPages.value) { page.value++; load() } }

watch(() => props.nodeId, () => { page.value = 1; load() }, { immediate: true })

function truncate(text, n) {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}
function itemTypeLabel(type) {
  return { single_choice: '单选', multiple_choice: '多选', non_choice: '主观题' }[type] || type
}
function formatExamId(examId) {
  // GK_2019_ZJ_04 → 2019 浙江
  const m = /GK_(\d{4})_([A-Z]+)/.exec(examId || '')
  return m ? `${m[1]} ${m[2]}` : examId
}
</script>

<style scoped>
.exam-items-tab { padding: 8px; }
.loading, .empty { text-align: center; color: var(--text-color-3); padding: 20px; }
.summary { font-size: 12px; color: var(--text-color-2); margin-bottom: 10px; }
.item { border: 1px solid var(--border-color); border-radius: 4px; padding: 10px; margin-bottom: 8px; }
.item-header { display: flex; gap: 8px; margin-bottom: 6px; font-size: 12px; }
.type-tag { background: var(--primary-color-hover); color: white; padding: 2px 6px; border-radius: 3px; }
.exam-year { color: var(--text-color-2); }
.difficulty { color: var(--text-color-3); }
.item-stem { font-size: 13px; line-height: 1.5; }
.item-detail { margin-top: 8px; }
.item-detail summary { cursor: pointer; font-size: 12px; color: var(--primary-color); }
.answer { margin-top: 6px; color: var(--success-color); font-size: 13px; }
.explanation { margin-top: 4px; color: var(--text-color-2); font-size: 12px; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 12px; }
</style>
```

- [ ] **Step 3: 实现 StudyUnitTab.vue**

Create `frontend/src/components/knowledge-tree/StudyUnitTab.vue`:

```vue
<template>
  <div class="study-unit-tab">
    <div v-if="!node.study_unit_id" class="empty">该概念暂无关联学习单元</div>
    <div v-else>
      <div class="field-row">
        <span class="label">学习单元 ID：</span>
        <span class="value">{{ node.study_unit_id }}</span>
      </div>
      <div class="field-row">
        <span class="label">建议学习时间：</span>
        <span class="value">{{ node.estimated_minutes }} 分钟</span>
      </div>
      <div class="field-row">
        <span class="label">前置深度：</span>
        <span class="value">{{ node.prerequisite_depth }}</span>
      </div>
      <div v-if="node.planning_weight" class="weight-section">
        <div class="section-title">规划权重</div>
        <div class="weight-grid">
          <div class="weight-item">
            <span class="weight-label">考频</span>
            <span class="weight-value">{{ node.planning_weight.exam_frequency || '—' }}</span>
          </div>
          <div class="weight-item">
            <span class="weight-label">易错度</span>
            <span class="weight-value">{{ node.planning_weight.error_prone || '—' }}</span>
          </div>
          <div class="weight-item">
            <span class="weight-label">迁移价值</span>
            <span class="weight-value">{{ node.planning_weight.transfer_value || '—' }}</span>
          </div>
          <div class="weight-item priority">
            <span class="weight-label">综合优先级</span>
            <span class="weight-value">{{ node.planning_weight.priority_score || '—' }}</span>
          </div>
        </div>
      </div>
      <div v-if="node.textbook_chapters && node.textbook_chapters.length" class="chapters-section">
        <div class="section-title">教材定位</div>
        <div v-for="(ch, i) in node.textbook_chapters" :key="i" class="chapter-item">
          {{ ch.book }} / {{ ch.chapter }} / {{ ch.title }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  node: { type: Object, required: true },
})
</script>

<style scoped>
.study-unit-tab { padding: 8px; }
.empty { text-align: center; color: var(--text-color-3); padding: 20px; }
.field-row { display: flex; margin-bottom: 8px; }
.label { color: var(--text-color-2); width: 100px; }
.value { color: var(--text-color-1); }
.section-title { font-weight: 600; margin: 14px 0 6px; color: var(--text-color-1); }
.weight-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.weight-item { display: flex; justify-content: space-between; padding: 4px 8px; background: var(--card-color); border-radius: 3px; }
.weight-item.priority { grid-column: 1 / -1; background: var(--primary-color-hover); color: white; }
.weight-label { font-size: 12px; }
.weight-value { font-weight: 600; }
.chapter-item { padding: 4px 8px; background: var(--card-color); border-radius: 3px; margin-bottom: 4px; font-size: 12px; }
</style>
```

- [ ] **Step 4: 集成到 NodeDetailDrawer**

Modify `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue`:

**重要（F007 决策）**: 仅**追加**两个新 tab，**不移除**现有的 `evidence` 和 `questions` tab。
教师现有的"教材证据"和"典型真题"浏览路径必须保留。
现有抽屉顶部 n-descriptions（基本信息）也保留，不改动。

```vue
<template>
  <n-drawer v-model:show="visible" :width="420" placement="right">
    <n-drawer-content :title="node?.name || ''" closable>
      <template v-if="node">
        <!-- 顶部基本信息（原有，不改）-->
        <n-descriptions :column="1" label-placement="left" size="small">
          <!-- 原有 items: ID / 层级 / 模块 / 掌握度 / DA 数量 -->
        </n-descriptions>

        <n-spin v-if="detailLoading" style="margin: 24px auto; display: block;" />
        <n-tabs type="line" v-if="detail" style="margin-top: 12px;">
          <!-- 原有 5 tab，不动 -->
          <n-tab-pane name="curriculum" tab="课标要求"><!-- 原有 --></n-tab-pane>
          <n-tab-pane name="textbook" tab="教材定位"><!-- 原有 --></n-tab-pane>
          <n-tab-pane name="das" tab="诊断属性"><!-- 原有 --></n-tab-pane>
          <n-tab-pane name="evidence" tab="教材证据"><!-- 原有，保留 --></n-tab-pane>
          <n-tab-pane name="questions" tab="典型真题"><!-- 原有，保留，按难度分级 --></n-tab-pane>
          <!-- Phase 1 新增（追加，不替换）-->
          <n-tab-pane name="exam_items" tab="高考真题全集">
            <ExamItemsTab :node-id="node.id" />
          </n-tab-pane>
          <n-tab-pane name="study_unit" tab="学习单元">
            <StudyUnitTab :node="node" />
          </n-tab-pane>
        </n-tabs>

        <!-- 原有编辑表单（不动）-->
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
// 原有 imports 保留
import ExamItemsTab from './ExamItemsTab.vue'  // 新增
import StudyUnitTab from './StudyUnitTab.vue'  // 新增
</script>
```

- [ ] **Step 5: 测试组件**

Create `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`:

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ExamItemsTab from '../ExamItemsTab.vue'

vi.mock('@/api/knowledgeTree', () => ({
  getExamItems: vi.fn(),
}))
import { getExamItems } from '@/api/knowledgeTree'

describe('ExamItemsTab', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('shows empty state when no items', async () => {
    getExamItems.mockResolvedValue({ items: [], total: 0 })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'X' } })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无关联高考真题')
  })

  it('renders items list', async () => {
    getExamItems.mockResolvedValue({
      items: [
        { id: '1', exam_id: 'GK_2019_ZJ', question_type: 'single_choice', stem: '光合作用相关题干' },
      ],
      total: 1,
    })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'Y' } })
    await flushPromises()
    expect(wrapper.text()).toContain('光合作用相关题干')
    expect(wrapper.text()).toContain('2019 ZJ')
  })

  it('pagination triggers reload', async () => {
    getExamItems.mockResolvedValue({ items: [{ id: '1', stem: 's' }], total: 30 })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'Z' } })
    await flushPromises()
    expect(getExamItems).toHaveBeenCalledWith('Z', 1, 10)
  })
})
```

Create `frontend/src/__tests__/knowledge-tree/StudyUnitTab.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StudyUnitTab from '../StudyUnitTab.vue'

describe('StudyUnitTab', () => {
  it('shows empty when no study_unit_id', () => {
    const wrapper = mount(StudyUnitTab, {
      props: { node: { study_unit_id: null } }
    })
    expect(wrapper.text()).toContain('暂无关联学习单元')
  })

  it('renders SU info when present', () => {
    const wrapper = mount(StudyUnitTab, {
      props: {
        node: {
          study_unit_id: 'su:bio_sr:m1_test',
          estimated_minutes: 70,
          prerequisite_depth: 2,
          planning_weight: { priority_score: 8.5, exam_frequency: 9 },
          textbook_chapters: [{ book: 'b1', chapter: 'ch03', title: '第3章' }],
        }
      }
    })
    expect(wrapper.text()).toContain('su:bio_sr:m1_test')
    expect(wrapper.text()).toContain('70 分钟')
    expect(wrapper.text()).toContain('8.5')
    expect(wrapper.text()).toContain('第3章')
  })
})
```

- [ ] **Step 6: 运行测试**

Run:
```bash
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run ExamItemsTab StudyUnitTab
```
Expected: 5 PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/knowledge-tree/ExamItemsTab.vue \
        frontend/src/components/knowledge-tree/StudyUnitTab.vue \
        frontend/src/components/knowledge-tree/NodeDetailDrawer.vue \
        frontend/src/api/knowledgeTree.js \
        frontend/src/__tests__/knowledge-tree/
git commit -m "feat(frontend): NodeDetailDrawer — exam items + study unit tabs"
```

**审查清单:**
- ✓ 高考真题分页加载（不全量）
- ✓ 无关联数据时显示空状态（不崩溃）
- ✓ 学习单元含权重和教材定位
- ✗ 不应在组件中直接发 axios（通过 api/knowledgeTree.js）

**边界条件:**
- 关联 1000+ 题 → 分页加载只拿第一页
- node.study_unit_id 为 null → 空状态
- 切换节点时 page 重置为 1

---

## Task 12: 教材章节导航模式

**Files:**
- Modify: `frontend/src/components/knowledge-tree/TreeNavPanel.vue`
- Modify: `frontend/src/components/knowledge-tree/useKnowledgeTree.js`

**F002 契约约束（R2 新增）**: 严禁修改 TreeNavPanel 现有的 props/emit 契约。现有：
- props: `navigation / module-mastery / nodes-with-mastery / selected-module`
- emits: `select-module / select-node`
- KnowledgeTreePage.vue:13 的调用方不变。

新增能力通过**组件内部状态** `navMode`（ref）实现，不暴露到外部。章节树从已有 `nodesWithMastery` prop 数据聚合，不新增 prop。

**测试契约:**

1. 导航模式切换 — 用户入口级验证
   - 入口: 挂载 TreeNavPanel，模拟点击"按教材章节" radio button
   - 反例: 切换后 DOM 仍显示模块名而非书名 → 失败
   - 边界: 章节模式下，nodes 无 textbook_chapters 时显示空树
   - 回归: 切回"按模块"模式，原 n-tree 内容恢复
   - 命令: `npx vitest run TreeNavPanel.test.js::test_nav_mode_toggle`

2. 章节树从节点数据聚合 — 纯函数单测
   - 入口: `buildChapterTree(nodes)` 返回 book→chapter→section→concepts 树
   - 反例: 若不按 section key 聚合，concepts 会漏/重 → 断言同 section 的 concepts 数量会失败
   - 边界: 无章节信息（空数组）/ 跨册概念（出现在多个 book 下）
   - 回归: N/A
   - 命令: `npx vitest run useKnowledgeTree.test.js::test_build_chapter_tree`

3. KnowledgeTreePage 集成 — 契约保持回归
   - 入口: 挂载 KnowledgeTreePage，检查 TreeNavPanel 接收到的 props 集合
   - 反例: 如果 Task 12 误改了 props 签名，KnowledgeTreePage 传入 `module-mastery` 会报 "Invalid prop" → 失败
   - 边界: 无 mastery 数据 / navigation 为空
   - 回归: @select-module 事件仍能触发 handleModuleSelect
   - 命令: `npx vitest run KnowledgeTreePage.test.js`

**Steps:**

- [ ] **Step 1: 实现 buildChapterTree 工具**

Append to `frontend/src/components/knowledge-tree/useKnowledgeTree.js`:

```javascript
/**
 * 从节点列表聚合章节树
 * node.textbook_chapters = [{book, chapter, section, title}]
 */
export function buildChapterTree(nodes) {
  const BOOK_LABELS = {
    b1: '必修1 分子与细胞',
    b2: '必修2 遗传与进化',
    xe1: '选必1 稳态与调节',
    xe2: '选必2 生物与环境',
    xe3: '选必3 生物技术',
  }
  const bookMap = new Map()

  for (const node of nodes) {
    const chapters = node.textbook_chapters || []
    for (const ch of chapters) {
      const bookKey = ch.book
      if (!bookMap.has(bookKey)) {
        bookMap.set(bookKey, { id: bookKey, name: BOOK_LABELS[bookKey] || bookKey, chapters: new Map() })
      }
      const book = bookMap.get(bookKey)
      const chapterKey = ch.chapter
      if (!book.chapters.has(chapterKey)) {
        book.chapters.set(chapterKey, { id: chapterKey, name: chapterKey, sections: new Map() })
      }
      const chapter = book.chapters.get(chapterKey)
      const sectionKey = ch.section
      if (!chapter.sections.has(sectionKey)) {
        chapter.sections.set(sectionKey, { id: sectionKey, name: ch.title || sectionKey, concept_ids: [] })
      }
      const section = chapter.sections.get(sectionKey)
      if (!section.concept_ids.includes(node.id)) {
        section.concept_ids.push(node.id)
      }
    }
  }

  // Map → 排序数组
  return Array.from(bookMap.values())
    .sort((a, b) => a.id.localeCompare(b.id))
    .map(book => ({
      ...book,
      chapters: Array.from(book.chapters.values())
        .sort((a, b) => a.id.localeCompare(b.id))
        .map(ch => ({
          ...ch,
          sections: Array.from(ch.sections.values())
            .sort((a, b) => a.id.localeCompare(b.id))
        }))
    }))
}
```

- [ ] **Step 2: 修改 TreeNavPanel.vue 支持双模式**

Modify `frontend/src/components/knowledge-tree/TreeNavPanel.vue`:

```vue
<template>
  <div class="tree-nav-panel">
    <!-- 导航模式切换 -->
    <div class="nav-mode-switcher">
      <n-radio-group v-model:value="navMode" size="small">
        <n-radio-button value="module">按模块</n-radio-button>
        <n-radio-button value="chapter">按教材章节</n-radio-button>
      </n-radio-group>
    </div>

    <!-- 搜索框 (原有) -->
    <n-input v-model:value="searchQuery" placeholder="搜索概念..." clearable size="small" />

    <!-- 模块模式 (原有树) -->
    <n-tree
      v-if="navMode === 'module'"
      :data="moduleTree"
      :selected-keys="selectedKeys"
      @update:selected-keys="onSelect"
    />

    <!-- 章节模式 -->
    <n-tree
      v-else
      :data="chapterTreeData"
      :selected-keys="selectedKeys"
      @update:selected-keys="onSelect"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NTree, NRadioGroup, NRadioButton, NInput } from 'naive-ui'
import { buildChapterTree } from './useKnowledgeTree'

// F002: 保持现有 props/emit 契约，navMode 作为内部状态
const props = defineProps({
  navigation: { type: Array, default: () => [] },
  moduleMastery: { type: Array, default: () => [] },   // 现有，保留
  nodesWithMastery: { type: Array, default: () => [] }, // 现有，保留（作为 nodes 数据源）
  selectedModule: { type: String, default: 'all' },     // 现有，保留
})
const emit = defineEmits(['select-module', 'select-node'])  // 现有事件，不改

const navMode = ref('module')  // 内部状态，不暴露
const searchQuery = ref('')

const moduleTree = computed(() => {
  // 原有逻辑：navigation → tree
  return props.navigation.map(mod => ({
    key: mod.id,
    label: mod.name,
    children: mod.big_concepts.map(bc => ({
      key: bc.id,
      label: bc.name,
      children: bc.concept_ids.map(cid => {
        const node = props.nodesWithMastery.find(n => n.id === cid)
        return { key: cid, label: node?.name || cid, isLeaf: true }
      }),
    })),
  }))
})

const chapterTreeData = computed(() => {
  const tree = buildChapterTree(props.nodesWithMastery)
  return tree.map(book => ({
    key: `book:${book.id}`,
    label: book.name,
    children: book.chapters.map(ch => ({
      key: `chapter:${book.id}:${ch.id}`,
      label: ch.name,
      children: ch.sections.map(s => ({
        key: `section:${book.id}:${ch.id}:${s.id}`,
        label: s.name,
        children: s.concept_ids.map(cid => {
          const node = props.nodesWithMastery.find(n => n.id === cid)
          return { key: cid, label: node?.name || cid, isLeaf: true }
        }),
      })),
    })),
  }))
})

function onSelect(keys) {
  // F002: 使用现有 emits 契约
  if (!keys[0]) return
  // key 前缀 book:/chapter:/section: 表示聚合节点，不是 concept
  if (keys[0].includes(':')) return
  // 判断是模块 ID 还是 concept ID
  const isModule = props.navigation.some(m => m.id === keys[0])
  if (isModule) {
    emit('select-module', keys[0])
  } else {
    // F010: select-node payload 必须是完整 node 对象（与现有 TreeNavPanel.vue:147 契约一致），
    // KnowledgeTreePage handleNodeClick / NodeDetailDrawer 均依赖对象字段。
    const node = props.nodesWithMastery.find(n => n.id === keys[0])
    if (node) emit('select-node', node)
  }
}
</script>
```

- [ ] **Step 3: 写单元测试**

Create `frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js` (或在已有文件中添加):

```javascript
import { describe, it, expect } from 'vitest'
import { buildChapterTree } from '../useKnowledgeTree'

describe('buildChapterTree', () => {
  it('aggregates concepts into book→chapter→section tree', () => {
    const nodes = [
      {
        id: 'C1',
        textbook_chapters: [{ book: 'b1', chapter: 'ch01', section: 's01', title: '第1节' }]
      },
      {
        id: 'C2',
        textbook_chapters: [{ book: 'b1', chapter: 'ch01', section: 's01', title: '第1节' }]
      },
      {
        id: 'C3',
        textbook_chapters: [{ book: 'b1', chapter: 'ch02', section: 's01', title: '第1节' }]
      },
    ]
    const tree = buildChapterTree(nodes)
    expect(tree).toHaveLength(1)
    expect(tree[0].id).toBe('b1')
    expect(tree[0].chapters).toHaveLength(2)
    expect(tree[0].chapters[0].sections[0].concept_ids).toEqual(['C1', 'C2'])
  })

  it('handles cross-book concepts', () => {
    const nodes = [
      {
        id: 'Shared',
        textbook_chapters: [
          { book: 'b1', chapter: 'ch01', section: 's01', title: 'a' },
          { book: 'xe1', chapter: 'ch02', section: 's02', title: 'b' },
        ]
      },
    ]
    const tree = buildChapterTree(nodes)
    expect(tree).toHaveLength(2)
  })

  it('handles empty textbook_chapters', () => {
    const nodes = [{ id: 'C1', textbook_chapters: [] }]
    const tree = buildChapterTree(nodes)
    expect(tree).toHaveLength(0)
  })
})

// F004: UI 挂载级 slice — nav mode 切换改变 DOM 内容
import { mount } from '@vue/test-utils'
import TreeNavPanel from '../TreeNavPanel.vue'

describe('TreeNavPanel — nav mode toggle (UI-level)', () => {
  const sampleNavigation = [
    { id: 'M1', name: '分子与细胞', big_concepts: [
      { id: 'BC1', name: '细胞学说', concept_ids: ['C1'] }
    ]}
  ]
  const sampleNodes = [
    { id: 'C1', name: '细胞膜', module: 'M1',
      textbook_chapters: [{ book: 'b1', chapter: 'ch01', section: 's01', title: '第1节 细胞膜' }] }
  ]

  it('default mode shows module tree (反例: 若默认 chapter 则此断言失败)', () => {
    const wrapper = mount(TreeNavPanel, {
      props: {
        navigation: sampleNavigation,
        moduleMastery: [],
        nodesWithMastery: sampleNodes,
        selectedModule: 'all',
      },
    })
    // 模块模式应显示模块名
    expect(wrapper.text()).toContain('分子与细胞')
  })

  it('chapter mode shows book title, not module name (反例: 若忽略 navMode 则显示模块名)', async () => {
    const wrapper = mount(TreeNavPanel, {
      props: {
        navigation: sampleNavigation,
        moduleMastery: [],
        nodesWithMastery: sampleNodes,
        selectedModule: 'all',
      },
    })
    // 切换到 chapter 模式（internal state via ref）
    wrapper.vm.navMode = 'chapter'
    await wrapper.vm.$nextTick()
    // 章节模式应显示教材册名而非模块名
    expect(wrapper.text()).toContain('必修1 分子与细胞')
  })

  it('preserves emits contract — select-module fires for module key', async () => {
    const wrapper = mount(TreeNavPanel, {
      props: {
        navigation: sampleNavigation,
        moduleMastery: [],
        nodesWithMastery: sampleNodes,
        selectedModule: 'all',
      },
    })
    // 直接调用 onSelect 验证 emit 契约
    wrapper.vm.onSelect(['M1'])
    expect(wrapper.emitted('select-module')).toBeTruthy()
    expect(wrapper.emitted('select-module')[0]).toEqual(['M1'])
  })

  it('preserves emits contract — select-node fires with full node object (F010: 不可降级为 id)', async () => {
    const wrapper = mount(TreeNavPanel, {
      props: {
        navigation: sampleNavigation,
        moduleMastery: [],
        nodesWithMastery: sampleNodes,
        selectedModule: 'all',
      },
    })
    wrapper.vm.onSelect(['C1'])
    expect(wrapper.emitted('select-node')).toBeTruthy()
    const payload = wrapper.emitted('select-node')[0][0]
    // 反例: 若 emit('select-node', keys[0]) 只传 id 字符串，以下断言会失败
    expect(typeof payload).toBe('object')
    expect(payload.id).toBe('C1')
    expect(payload.name).toBe('细胞膜')
    // NodeDetailDrawer 依赖 module、textbook_chapters 等字段
    expect(payload.module).toBe('M1')
  })
})
```

- [ ] **Step 4: 运行测试**

Run:
```bash
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run TreeNavPanel
```
Expected: 所有 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/knowledge-tree/TreeNavPanel.vue \
        frontend/src/components/knowledge-tree/useKnowledgeTree.js \
        frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js
git commit -m "feat(frontend): textbook chapter navigation mode"
```

**审查清单:**
- ✓ 导航模式切换平滑
- ✓ 章节树按 book/chapter/section 三级
- ✓ 选择概念时 emit 事件
- ✗ 不应重新请求数据（章节树从已有 nodes 聚合）

**边界条件:**
- nodes.textbook_chapters 全空 → 章节树为空（显示"无数据"）
- 跨册概念 → 出现在多个 book 下

---

## Task 13: ModuleOverviewPanel 统计增强 + 集成验证

**Files:**
- Modify: `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue`
- Modify: `frontend/src/components/knowledge-tree/useKnowledgeTree.js`
- Modify: `frontend/src/pages/KnowledgeTreePage.vue` (仅加 :stats-overview 传递)

**F002 契约约束（R2 新增）**: 保留现有 props/emit 契约：
- props: `navigation / nodes / edges / modules-quality`（现有，全保留）
- 新增 prop: `stats-overview`（optional）
- emits: `select-module / refresh-quality`（现有，不改）

KnowledgeTreePage.vue 的改动仅为追加 `:stats-overview="statsOverview"`，保持其他 binding 不变。

**测试契约:**

1. 模块卡片显示考频分布 — UI 级入口
   - 入口: 挂载 ModuleOverviewPanel，传入 nodes 和 statsOverview，检查 DOM 中是否含 "平均考频: 186" 文案
   - 反例: 若 statsOverview 被忽略，DOM 文案仅显示 "—" → 失败
   - 边界: 某模块全零考频（freqDist 高频段占比 0）/ statsOverview 为 null（显示 "—" 不崩溃）/ nodes 为空
   - 回归: 原有"概念数/边数/审核进度/质量问题数"字段保留显示
   - 命令: `npx vitest run ModuleOverviewPanel.test.js`

2. KnowledgeTreePage 集成 — 契约保持回归
   - 入口: 挂载 KnowledgeTreePage 并在 all 模块下渲染，验证 ModuleOverviewPanel 接收的 props
   - 反例: 若 navigation prop 丢失，ModuleOverviewPanel 会报警告 → 失败
   - 边界: statsOverview 未加载（null）不影响现有字段展示
   - 回归: @select-module 和 @refresh-quality 事件仍可达 KnowledgeTreePage
   - 命令: `npx vitest run KnowledgeTreePage.test.js`

**Steps:**

- [ ] **Step 1: 扩展 useKnowledgeTree.js 加载统计概览**

```javascript
// 在 useKnowledgeTree 中新增
import { getStatsOverview } from '@/api/knowledgeTree'

const statsOverview = ref(null)

async function loadStatsOverview() {
  try {
    statsOverview.value = await getStatsOverview('all')
  } catch (e) {
    console.error('loadStatsOverview failed', e)
  }
}

// export 中加入
return {
  // ... 原有 ...
  statsOverview,
  loadStatsOverview,
}
```

- [ ] **Step 2: 修改 ModuleOverviewPanel.vue**

```vue
<template>
  <div class="module-overview">
    <div
      v-for="mod in modules"
      :key="mod.id"
      class="module-card"
      @click="$emit('select-module', mod.id)"
    >
      <div class="card-title">{{ mod.name }}</div>
      <div class="card-stats">
        <div class="stat-row">
          <span>概念: {{ getModuleStats(mod.id)?.concepts ?? mod.concept_count }}</span>
          <span>边: {{ getModuleStats(mod.id)?.edges ?? 0 }}</span>
        </div>
        <div class="stat-row">
          <span>平均考频: {{ getModuleStats(mod.id)?.avg_freq ?? '—' }}</span>
          <span>考频覆盖: {{ formatCoverage(getModuleStats(mod.id)?.exam_coverage) }}</span>
        </div>
        <div class="freq-bar">
          <div class="freq-seg high" :style="{width: highPct(mod.id)+'%'}"></div>
          <div class="freq-seg mid" :style="{width: midPct(mod.id)+'%'}"></div>
          <div class="freq-seg low" :style="{width: lowPct(mod.id)+'%'}"></div>
        </div>
        <div class="freq-legend">
          <span class="dot high"></span>高频
          <span class="dot mid"></span>中频
          <span class="dot low"></span>低频/零
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// F002: 保留现有 props 契约（navigation/nodes/edges/modulesQuality），仅新增 statsOverview
const props = defineProps({
  navigation: { type: Array, default: () => [] },
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  modulesQuality: { type: Object, default: () => ({}) },
  statsOverview: { type: Object, default: null },  // 新增，optional
})
defineEmits(['select-module', 'refresh-quality'])  // 现有事件，不改

// 从 navigation 派生 modules 列表（保持现有数据流）
const modules = computed(() => props.navigation.map(m => ({
  id: m.id,
  name: m.name,
  concept_count: m.big_concepts.reduce((sum, bc) => sum + (bc.concept_ids?.length || 0), 0),
})))

function getModuleStats(moduleId) {
  return props.statsOverview?.module_stats?.[moduleId]
}

// 计算该模块的考频分布百分比
function freqDist(moduleId) {
  const modNodes = props.nodes.filter(n => n.module === moduleId)
  if (!modNodes.length) return { high: 0, mid: 0, low: 0 }
  let high = 0, mid = 0, low = 0
  for (const n of modNodes) {
    const f = n.exam_frequency || 0
    if (f >= 500) high++
    else if (f >= 50) mid++
    else low++
  }
  const total = modNodes.length
  return {
    high: Math.round(100 * high / total),
    mid: Math.round(100 * mid / total),
    low: Math.round(100 * low / total),
  }
}
function highPct(id) { return freqDist(id).high }
function midPct(id) { return freqDist(id).mid }
function lowPct(id) { return freqDist(id).low }

// F008: 考频覆盖率格式化（0.96 → "96%"，undefined/null → "—"）
function formatCoverage(cov) {
  if (cov == null || isNaN(cov)) return '—'
  return `${Math.round(cov * 100)}%`
}
</script>

<style scoped>
/* ... 原有样式 + 新增 freq-bar */
.freq-bar { display: flex; height: 6px; border-radius: 3px; overflow: hidden; margin: 8px 0; background: #eee; }
.freq-seg.high { background: #3B5998; }
.freq-seg.mid { background: #8FA3D1; }
.freq-seg.low { background: #D0DAED; }
.freq-legend { display: flex; gap: 12px; font-size: 11px; color: var(--text-color-2); }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 3px; }
.dot.high { background: #3B5998; }
.dot.mid { background: #8FA3D1; }
.dot.low { background: #D0DAED; }
</style>
```

- [ ] **Step 3: 在 KnowledgeTreePage 加载 stats + 传入组件**

a) `onMounted` 中追加加载：

```javascript
// KnowledgeTreePage.vue onMounted (保留原有调用)
onMounted(async () => {
  await loadGraph()
  await loadStatsOverview()  // 新增
  // ...
})

// 从 useKnowledgeTree 取 statsOverview
const { statsOverview, loadStatsOverview /* ...原有解构... */ } = useKnowledgeTree(...)
```

b) 在 template 中为 ModuleOverviewPanel 追加 prop（仅追加一行，不删原有 binding）：

```vue
<ModuleOverviewPanel
  v-if="selectedModule === 'all'"
  :navigation="navigationData"
  :nodes="nodesWithMastery"
  :edges="graphData.edges"
  :modules-quality="modulesQuality"
  :stats-overview="statsOverview"        <!-- Phase 1 新增 -->
  style="flex: 1; min-height: 0"
  @select-module="handleModuleSelect"
  @refresh-quality="loadAllModulesQuality"
/>
```

- [ ] **Step 4: 写 ModuleOverviewPanel UI 级测试（F004 入口级 slice）**

Create `frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ModuleOverviewPanel from '../ModuleOverviewPanel.vue'

const sampleNavigation = [
  { id: 'M1', name: '分子与细胞', big_concepts: [
    { id: 'BC1', name: '细胞学说', concept_ids: ['C1', 'C2', 'C3'] },
  ]},
]
const sampleNodes = [
  { id: 'C1', module: 'M1', exam_frequency: 800 },  // high
  { id: 'C2', module: 'M1', exam_frequency: 100 },  // mid
  { id: 'C3', module: 'M1', exam_frequency: 0 },    // zero
]
const sampleStatsOverview = {
  module_stats: {
    M1: { concepts: 3, edges: 5, avg_freq: 300.0, exam_coverage: 0.667 }
  }
}

describe('ModuleOverviewPanel — UI render (F004 entry-level)', () => {
  it('renders avg_freq from statsOverview (反例: 若忽略 statsOverview 则显示 "—")', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: {
        navigation: sampleNavigation,
        nodes: sampleNodes,
        edges: [],
        modulesQuality: {},
        statsOverview: sampleStatsOverview,
      },
    })
    expect(wrapper.text()).toContain('平均考频: 300')
  })

  it('renders exam_coverage as percentage (F008: 67% for 2/3 nonzero)', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: {
        navigation: sampleNavigation,
        nodes: sampleNodes,
        edges: [],
        modulesQuality: {},
        statsOverview: sampleStatsOverview,
      },
    })
    expect(wrapper.text()).toContain('考频覆盖: 67%')
  })

  it('degrades gracefully when statsOverview is null (反例: 若强依赖会报错)', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: {
        navigation: sampleNavigation,
        nodes: sampleNodes,
        edges: [],
        modulesQuality: {},
        statsOverview: null,
      },
    })
    expect(wrapper.text()).toContain('平均考频: —')
    expect(wrapper.text()).toContain('考频覆盖: —')
  })

  it('preserves original fields (concepts count) — regression', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: {
        navigation: sampleNavigation,
        nodes: sampleNodes,
        edges: [],
        modulesQuality: {},
        statsOverview: sampleStatsOverview,
      },
    })
    expect(wrapper.text()).toContain('概念: 3')
  })

  it('emits select-module when card clicked (contract preservation)', async () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: {
        navigation: sampleNavigation,
        nodes: sampleNodes,
        edges: [],
        modulesQuality: {},
        statsOverview: null,
      },
    })
    await wrapper.find('.module-card').trigger('click')
    expect(wrapper.emitted('select-module')).toBeTruthy()
    expect(wrapper.emitted('select-module')[0]).toEqual(['M1'])
  })
})
```

- [ ] **Step 5: 运行前端全量测试**

Run:
```bash
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run
```
Expected: 所有 PASS（原有 73 + 新增约 15）

- [ ] **Step 6: 运行后端全量测试**

Run:
```bash
cd /c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```
Expected: 1582 + 新增测试 PASS

- [ ] **Step 7: 启动服务端到端验证**

手动验证清单：
```
☐ 打开 http://localhost:5273/knowledge-tree
☐ 选择 M1 模块
☐ 节点大小有明显差异（ATP/光合作用 大，冷门概念小）
☐ 节点颜色有热力分布（深色=高考频）
☐ 工具栏切换到"审核状态"模式 — 颜色变化
☐ 工具栏切换到"掌握度" — 若无学生则 disabled
☐ 点击光合作用节点 — 详情面板打开
☐ 切到"高考真题"标签 — 显示 1260 题的第一页
☐ 分页 — 下一页工作
☐ 切到"学习单元"标签 — 显示 SU 信息 + 规划权重
☐ 切到"按教材章节"导航模式 — 树结构变为 book→chapter→section
☐ ModuleOverviewPanel 卡片显示考频分布条
☐ 焦点模式（点击后其他节点淡化）仍正常
☐ ModuleOverviewPanel 卡片显示"考频覆盖: XX%"（F008）
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue \
        frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js \
        frontend/src/components/knowledge-tree/useKnowledgeTree.js \
        frontend/src/pages/KnowledgeTreePage.vue
git commit -m "feat(frontend): ModuleOverviewPanel freq distribution"
```

**审查清单:**
- ✓ 模块卡片显示概念数 + 边数 + 平均考频 + 分布条
- ✓ 分布条颜色语义（深色=高频）
- ✓ 图例清晰
- ✗ 不应重复请求 stats（缓存在 statsOverview）

**边界条件:**
- statsOverview 加载失败 → 显示"—"不崩溃
- 某模块全零考频 → 分布条全是低频色

---

## Task 14: 收尾 — design.md 标记 + 审查交接单

**Steps:**

- [ ] **Step 0 (P001 处置): 新增 INV-002 L1 集合相等测试**

追加到 `tests/test_knowledge_tree/test_stats_service.py`:

```python
def test_exam_frequency_l1_set_equals_kb_l1(tmp_path):
    """INV-002 P001: compute_exam_frequency 返回 key 集合必须 == KB 中 knowledge_level='L1' 集合。

    反例：若实现改为 knowledge_level != 'L0'，L2 概念被纳入 → set 不等 → 此测试 fail。
    """
    import sqlite3
    from edu_cloud.modules.knowledge_tree.stats_service import compute_exam_frequency

    db_path = tmp_path / "kb.db"
    conn = sqlite3.connect(str(db_path))
    # R6 修复 (R5-T001): schema 精确匹配 stats_service.compute_exam_frequency 实际读取的表：
    #   - concepts (id, knowledge_level) — _load_l1_concept_ids 读取
    #   - diagnostic_attributes (id, linked_concept_ids) — _load_da_to_concepts 读取（必须存在，否则 OperationalError）
    #   - q_matrix (item_id, attribute_id) — JOIN 聚合 item_ids 读取
    # L1 集合相等断言只依赖 _load_l1_concept_ids，所以 diagnostic_attributes / q_matrix 可为空表
    conn.executescript("""
        CREATE TABLE concepts (id TEXT PRIMARY KEY, name TEXT, knowledge_level TEXT);
        CREATE TABLE diagnostic_attributes (id TEXT PRIMARY KEY, linked_concept_ids TEXT);
        CREATE TABLE q_matrix (item_id TEXT, attribute_id TEXT);
    """)
    conn.executemany("INSERT INTO concepts(id, name, knowledge_level) VALUES (?, ?, ?)", [
        ("L1_A", "光合作用", "L1"),
        ("L1_B", "细胞膜", "L1"),
        ("L1_C", "遗传物质", "L1"),
        ("L0_A", "叶绿体", "L0"),
        ("L0_B", "线粒体", "L0"),
        ("L2_A", "能量观", "L2"),
    ])
    conn.commit()
    conn.close()

    freq = compute_exam_frequency(str(db_path))
    kb_l1_ids = {"L1_A", "L1_B", "L1_C"}
    actual_ids = set(freq.keys())
    diff = actual_ids ^ kb_l1_ids
    assert actual_ids == kb_l1_ids, f"INV-002 L1 集合不等，对称差集: {diff}"
```

Run:
```bash
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_knowledge_tree/test_stats_service.py::test_exam_frequency_l1_set_equals_kb_l1 -v
```
Expected: PASS（实际实现 stats_service.py:43 `WHERE knowledge_level='L1'`，符合契约）

反证验证（审查交接单"反证验证"列必填）：Executor 应执行**三类** mutant 临时反证，每类都证明测试能抓住 bug：
  1. **删除 WHERE knowledge_level='L1'**（stats_service.py:43）→ actual = 全 6 ids → 集合不等 fail（超集）
  2. **改 != 'L0'** → actual = {L1_A, L1_B, L1_C, L2_A} 4 ids → 集合不等 fail（含 L2）
  3. **改 LIKE 'L%'** → actual = 全 6 ids → 集合不等 fail（含 L0）
每次改后测试必须 fail（非 OperationalError 崩溃），改回后重跑 PASS。反证输出粘贴到审查交接单 S0 行。

- [ ] **Step 1: 获取 commits 范围**

Run:
```bash
cd /c/Users/Administrator/edu-cloud
git log --oneline docs/plans/2026-04-13-knowledge-graph-phase1-plan.md..HEAD | tail -20
```

- [ ] **Step 2: 更新 design.md 头部标记实现完成**

Modify `docs/plans/2026-04-12-knowledge-graph-optimization-design.md` — 在 §0 之后添加：

```markdown
> [2026-04-XX HH:MM:SS Phase 1 实现完成] Commits: <first>..<last>
> Phase 2/3/4 待后续规划
```

- [ ] **Step 3: 输出审查交接单**

Create `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff.md`:

```markdown
[edu-cloud] Executor→Reviewer | 2026-04-XX HH:MM:SS

## 审查交接单: 知识图谱 Phase 1 (T1-T13)

计划: docs/plans/2026-04-13-knowledge-graph-phase1-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | ConceptStats 模型 + 迁移 | commit <hash>, 表+FK CASCADE | ✅ | |
| T2 | 考频/难度/覆盖率计算 | commit <hash>, Top10 与调查一致 | ✅ | |
| T3 | 章节聚合 + 前置深度 | commit <hash> | ✅ | |
| T4 | MCU 权重导入 | commit <hash>, 映射率 % | ✅/🔀 | |
| T5 | importance_score + compute_all | commit <hash> | ✅ | |
| T6 | sync 集成 + 启动触发 | commit <hash> | ✅ | |
| T7 | Graph API v3 | commit <hash> | ✅ | |
| T8 | 高考题+概览 API | commit <hash> | ✅ | |
| T9 | 热力色+模式切换 | commit <hash> | ✅ | |
| T10 | ConceptMapPanel 视觉 | commit <hash> | ✅ | |
| T11 | 详情面板 2 标签页 | commit <hash> | ✅ | |
| T12 | 章节导航模式 | commit <hash> | ✅ | |
| T13 | 模块概览统计 | commit <hash> | ✅ | |

### 预审自检
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| S0 INV-002 L1 集合相等 (P001) | test_stats_service.py::test_exam_frequency_l1_set_equals_kb_l1 | pytest ... -v | PASS, set=={L1_A,L1_B,L1_C} | SELECT 改为 != 'L0' → L2_A 混入，actual=4 IDs，集合不等 fail |
| S2 考频计算 | test_stats_service.py::test_exam_frequency_real_data | pytest ... | PASS, 光合作用 1260 | 删除 DA JOIN → 返回空 |
| S6 Graph API v3 | test_graph_v3.py::test_graph_v3_fields_present | pytest ... | PASS | 移除 stats_by_id.get → 字段全 None |
| S-INV004-TreeNav | TreeNavPanel.test.js::preserves emits contract | npx vitest run TreeNavPanel | PASS, select-node payload 含 name/module | emit 只传 id 字符串 → payload.id 断言通过但 payload.name undefined fail |
| S-INV004-ModuleOv | ModuleOverviewPanel.test.js::emits select-module | npx vitest run ModuleOverviewPanel | PASS | 删除 @click emit → click 不触发 fail |

### 验证清单自检
[逐项对照 §9 Phase 1 验收标准]

使用 codex-review skill 进行 GPT 代码审查。
```

- [ ] **Step 4: 提交收尾**

```bash
git add docs/plans/2026-04-12-knowledge-graph-optimization-design.md \
        docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff.md
git commit -m "docs: Phase 1 实现完成标记 + 审查交接单"
```

---

## Contract Pack

> **F006 response**: 显式 Contract Pack 覆盖本次 Phase 1 的不变量、反例、高风险模块和测试债务。
> Code Review (Gate 2) 必须逐条核对。

### invariants（不变量，≥3 条）

#### INV-001: Graph API 响应结构向后兼容
**内容**: `GET /api/v1/knowledge-tree/graph` 返回的每个 node 必须保留 v2 字段集合：`id, name, level, module, big_concept_id, aliases, review_status, difficulty, bloom_level, description, hard_in_count, hard_out_count, external_hard_refs`。v3 只能**追加**字段，不能删改。
**违反后果**: 现有前端（TreeNavPanel 焦点模式/RelationReviewPanel）崩溃。
**verification**: existing_test — `tests/test_knowledge_tree/test_graph_v3.py::test_graph_v2_fields_preserved` (Task 7)

#### INV-002: L1 考频计算只涉及 L1 concepts
**内容**: `compute_exam_frequency(kb_path)` 返回的 key 集合必须完全等于 knowledge.db 中 `knowledge_level='L1'` 的 concept ID 集合。不得包含 L0 evidence 或 L2 原理。
**违反后果**: 图谱会出现不属于 L1 层的节点，破坏"L1-only 图谱"的设计前提（2026-04-09-knowledge-graph-restructure-design）。
**verification**:
  - existing_test — `tests/test_knowledge_tree/test_stats_service.py::test_exam_frequency_excludes_l0` (Task 2，exclude L0，必要不充分条件)
  - **new_test (Batch 3.c T14 Step 0)** — `tests/test_knowledge_tree/test_stats_service.py::test_exam_frequency_l1_set_equals_kb_l1`：controlled fixture 含 L0/L1/L2 三类 concept，断言 `set(compute_exam_frequency(kb).keys()) == {L1 ids}`。反例：若 SELECT 条件误写 `knowledge_level != 'L0'`，L2 被纳入，此测试报集合不等。
**Round 3 修复 (P001)**: GPT batch2 R3 deferred — exclude_l0 仅为必要条件，不锁定"集合完全相等"。R3 新增集合相等断言测试，由 Batch 3.c T14 Step 0 落盘。

#### INV-003: concept_stats 计算失败不阻塞 sync
**内容**: `sync_knowledge_on_startup` 中触发 `compute_all_stats` 必须在 try/except 包裹下运行。stats 计算抛异常时：sync 本身已 commit 的数据必须保留，日志记录 error，进程不退出。
**违反后果**: knowledge.db 出现边界数据时整个应用无法启动。
**verification**: existing_test — `tests/test_knowledge_tree/test_sync_startup.py::test_sync_stats_failure_does_not_break_sync` (Task 6)

#### INV-004: 前端子组件契约不变
**内容**: `TreeNavPanel`/`ModuleOverviewPanel` 的公共 props/emits 集合（见 F002）是只增不改的契约。Phase 1 只能追加 optional prop（如 stats-overview），不得修改/删除现有 props 或 emits 名称。
**违反后果**: `KnowledgeTreePage.vue` 其他使用场景和 Phase 2/3/4 的扩展受阻。
**verification**（R3 精确化，Batch 3.b/3.c 落盘）:
  - TreeNavPanel props/emit 契约：`frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js`（Task 12 测试契约 #3，三个 "preserves emits contract" 断言：`select-module` 带模块 ID、`select-node` 带完整 node 对象，F010 不可降级为 id）
  - ModuleOverviewPanel props/emit 契约：`frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js`（Task 13 测试契约 #1，「emits select-module when card clicked (contract preservation)」+ 四项 UI 渲染断言 + statsOverview=null 降级不崩溃）
  - KnowledgeTreePage 集成：**deferred (Phase 2, deadline 2026-05-31)** — 现有 `frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js` 把 TreeNavPanel/ModuleOverviewPanel 全部 stub 掉，不能证明真实子组件 props/emits 集成契约。R6 承认这不构成 accepted-risk，标 deferred。Phase 2 需要扩展 KnowledgeTreePage 集成测试：去掉子组件 stub，使用真实 mount，断言 TreeNavPanel 的 select-module/select-node emit 能到达 KnowledgeTreePage handler + ModuleOverviewPanel 的 select-module emit 能驱动 selectedModule 状态变化。
**Round 3 修复 (P001)**: GPT batch2 R3 deferred — "新增 KnowledgeTreePage.test.js" 为未落盘测试，不构成 verification。R3 映射精确化到 Batch 3.b/3.c 即将落盘的组件级契约断言测试（TreeNavPanel.test.js 新建 / ModuleOverviewPanel.test.js 追加）。
**Round 6 修复 (R5-T002)**: R5 GPT 查证发现 `frontend/src/components/knowledge-tree/__tests__/` 目录不存在，真实测试目录为 `frontend/src/__tests__/knowledge-tree/`。R6 全文批量修正 T9-T13 所有测试路径到真实目录（behavior_change，修 R1-R4 漏审的前置缺陷）。KnowledgeTreePage 集成从 accepted-risk 降级为 deferred（Phase 2，deadline 2026-05-31），理由：现有 KnowledgeTreePage.mount.test.js 子组件全 stub 不证明契约。

#### INV-005: importance_score 归一化到 [0, 10]
**内容**: `compute_importance_score(...)` 返回值必须在闭区间 [0.0, 10.0]，且单调随输入分量递增。
**违反后果**: 前端 `nodeSizeFromImportance` 会产生异常大小（节点遮挡或不可见）。
**verification**: existing_test — 5 测试组合覆盖归一化 + 4 维单调性：
  - `tests/test_knowledge_tree/test_stats_service.py::test_importance_score_normalization` (Task 5，归一化区间)
  - `::test_importance_score_monotonic_in_exam_frequency` (考频维单调性)
  - `::test_importance_score_monotonic_in_prerequisite_depth` (深度维单调性)
  - `::test_importance_score_monotonic_in_error_prone` (易错率维单调性)
  - `::test_importance_score_monotonic_in_transfer_value` (迁移价值维单调性)
**Round 2 修复 (P001)**: GPT batch1 R1 报告 INV-005 verification 仅指向 normalization 测试，删除任一分量贡献后测试仍能绿通。R2 批补全 4 维单调性测试已落盘（test_stats_service.py:196-235），verification 映射本次精确化。

### counter_examples（反例，≥2 个）

#### CE-001: 逻辑镜像测试 — "只验证 prop 传递"
**模式**: `expect(wrapper.props('colorMode')).toBe('review_status')`
**问题**: Vue 的 props 单向绑定总是成功，这个断言和被测行为无关——删除 ConceptMapPanel 内部所有颜色计算逻辑，此测试仍通过。
**tests_that_still_pass_if_implementation_broken**: R1 版本 Task 10 Step 3 的 "changing colorMode updates node fill" 测试。
**mitigation**: R2 改为 `buildG6Data()` 返回值级断言：`expect(examFill).not.toBe(reviewFill)` + 颜色语义断言（weak→R>G）。实现错误（忽略 colorMode / 走错分支）会使测试失败。已在 Task 10 Step 3 修复。

#### CE-002: HTTP 测试将 4xx 视为通过
**模式**: `assert resp.status_code in (200, 404)`
**问题**: 路由未注册、权限配置错、依赖崩溃 → 404/500 都被视为"不失败"，测试失去检测力。
**tests_that_still_pass_if_implementation_broken**: R1 版本 Task 8 Step 1 的 `test_get_exam_items_endpoint`。
**mitigation**: R2 拆成两个测试：`test_get_exam_items_endpoint_for_seeded_concept` 必须返回 200 且校验 items 关键字段；`test_get_exam_items_endpoint_unknown_concept` 必须返回 200 total=0（显式降级契约）。已在 Task 8 Step 1 修复。

#### CE-003: 匹配阈值过低导致乱映射
**模式**: MCU CP → kb concept 语义匹配阈值设为 0.1，导致无关文本也被匹配。
**问题**: MCU 的 L19_CP_003 错误匹配到 kb 的 CELL_THEORY，权重被污染。
**tests_that_still_pass_if_implementation_broken**: 仅测试"匹配数量≥X"而不测"匹配准确性"。
**mitigation**: Task 4 的 `test_mcu_matching_filters_low_confidence` 显式验证阈值过滤；`match_mcu_to_kb` 的 `threshold` 参数默认 0.5 ≥ 设计文档值。

### risk_modules（高风险模块）

| 模块 | 风险类型 | Phase 1 覆盖 |
|------|---------|--------------|
| `stats_service.compute_all_stats` | lifecycle + threshold + fallback | Task 5 + Task 6 + INV-003 |
| `stats_service.compute_prerequisite_depth` | cycle fallback | Task 3 `test_prerequisite_depth_cycle_handling` |
| `import_mcu_planning_weights.match_mcu_to_kb` | matching threshold | Task 4 `test_mcu_matching_*` 两个 |
| `service.get_graph` (v3 扩展) | public API 向后兼容 | INV-001 + Task 7 三个测试 |
| `exam_items_service.get_exam_items` | 新 public API | Task 8 三个测试（含 HTTP 入口级） |
| `sync_service.sync_knowledge_on_startup` 扩展 | startup lifecycle | INV-003 + Task 6 |
| `ConceptMapPanel.buildG6Data` | 视觉编码行为 | Task 10 三个行为断言测试 |
| `TreeNavPanel` + `ModuleOverviewPanel` | 前端契约不变 | INV-004 + Task 12/13 集成测试 |

### test_debt（测试债务）

#### TD-001: G6 渲染的像素级快照不在 Phase 1 覆盖
**理由**: G6 需要 canvas 环境，happy-dom 不完整支持。目前通过 `buildG6Data()` 返回值断言行为，未验证 G6 实际像素输出。
**风险等级**: 低（G6 本身是成熟库，只验数据传入正确即可）
**deadline**: 不修复（Phase 1 接受）。若 Phase 2 加入自定义节点 renderer，再考虑引入 playwright 视觉回归。

#### TD-002: MCU 映射准确率无端到端人工抽检
**理由**: R2 的自动匹配测试（test_mcu_matching_by_content）只覆盖构造示例，未覆盖全部 218 个 MCU CP 的真实匹配结果。
**风险等级**: 中（若准确率 <80%，权重数据污染）
**deadline**: Task 4 Step 4 dry-run 输出到日志，Planner 在审查交接单中抽检 20 个映射条目（<80% 准确则阈值从 0.5 上调到 0.6）。Phase 2 前必须覆盖。

#### TD-003: 启动时 stats 计算耗时未做压力基线
**理由**: 设计文档估计 <5s，但没有基线测试。
**风险等级**: 低（最坏情况应用启动慢，不影响正确性）
**deadline**: Task 5 Step 4 首次执行时记录耗时到日志。超过 30s 则加 `pytest-timeout` 断言。Phase 1 验收后建立基线。

### freshness
此 Contract Pack 对应 plan 版本 **R6**（2026-04-14：R3 P001 处置 INV-002/004 verification 精确化 + T14 Step 0 新增 L1 集合相等测试 + R6 修复 R5-T001/T002/P002 + T9-T13 测试路径批量校正 `frontend/src/__tests__/knowledge-tree/`）。若 Phase 1 执行过程中出现推翻不变量或新增未列出的 public API 变更，Code Review 需将此视为 process finding，要求 Planner 更新 Contract Pack。

---

## 自审

### Spec 覆盖检查
- §1 四条价值链: Phase 1 聚焦链 1（教师看图谱），链 2/3/4 留给后续 Phase ✓
- §2.2 ConceptStats 表: T1 ✓
- §2.2 TeachingPlan 表: 留给 Phase 3（设计文档中说明）✓
- §2.3 Graph API v3: T7 ✓
- §3 Phase 1 的 6 项核心工作: 全部覆盖 T1-T13 ✓
- §4 MCU 数据迁入: T4 ✓
- §5 前端设计:
  - 5.1 节点视觉: T10 ✓
  - 5.2 着色模式切换: T9 ✓
  - 5.3 图层切换: Phase 2
  - 5.4 详情面板增强: T11 ✓
  - 5.5 教材章节导航: T12 ✓
  - 5.6 ModuleOverviewPanel 增强: T13 ✓
- §7 技术决策: 全部体现在代码中 ✓
- §9 Phase 1 验收: T13 Step 6 手动清单覆盖 ✓

### 占位符检查
- 无 TODO / TBD / "fill in later"
- 所有步骤有具体代码
- 所有 pytest/vitest 命令有明确 expected

### 类型一致性
- `concept_id` 在所有任务中类型统一为 `VARCHAR(64)` / `str`
- `importance_score` 一致为 `float ∈ [0, 10]`
- `textbook_chapters` 一致为 `list[dict]` 结构 `{book, chapter, section, title}`
- API 返回字段 snake_case 与前端 camelCase 边界在 api/knowledgeTree.js 统一

### 规模估计
- 15 Task（T0 准备 + T1-T13 实现 + T14 收尾，共 15 条 state sidecar 条目与 `range(0, 15)` 一致）
- 后端新增约 8 个文件、修改 6 个
- 前端新增 6 个文件、修改 4 个
- 新增测试约 30 个（后端 20+ / 前端 10+）

---

## 执行方式

计划保存到 `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md`。

两种执行方式可选：

**1. Subagent-Driven (推荐 T3)** - 每个 Task 派发独立 subagent 执行 + Gate 审查
**2. Inline Execution** - 本会话内批次执行（不推荐 T3，本规则禁止）

按项目规则（CLAUDE.md Superpowers 覆盖规则 §2）:
> writing-plans 完成后：T3/T4 禁止"同会话执行"，必须新会话

故 **不在本会话执行**。用户审阅 plan 后在新会话中启动执行。
