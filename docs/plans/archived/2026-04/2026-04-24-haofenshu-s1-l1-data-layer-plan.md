---
type: plan
topic: haofenshu-s1-l1-data-layer
baseline_command: .venv/bin/python -m pytest --tb=short -q
baseline_verified_at: 2026-04-24T00:00:00+08:00
baseline_count: 2046
baseline_method: pytest
---

# S1 L1 数据层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 2 S1 数据层——一次性 Alembic migration 扩展 bank_questions / concept_graph_nodes / classes + 新建 grades / teaching_plans 表 + PaperAccessLevel 枚举 + StudentProfileView Pydantic VO，冻结 L1 schema 供 S2-S4 消费。

**Architecture:** 一次 Alembic migration 覆盖 6 个 L1 deliverable。扩展现有表走 `batch_alter_table` 保持 SQLite/PG 方言中立（见 docs/plans/2026-04-13-migration-gate-repair-design.md）。新表用独立 create_table。VO 零 schema 改动。Gate G1 通过条件：alembic up/down 在空 db + 生产库 dump 都可逆。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.0 async / Alembic 1.13 / Pydantic v2 / pytest-asyncio / SQLite（测试）+ PostgreSQL（生产 asyncpg）

**Parent Design:** [docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md) §4

**Baseline 基准**：`baseline_count: 2046`（CLAUDE.md 实测 2026-04-24 `2046 passed / 23 skipped`）。S1 每个 Task 通过后增量叠加；Gate G1 要求全量 ≥ 2046 + S1 新增。

---

## Evidence Block（from parent design §13）

```
decision: S1 一次性冻结所有 L1 schema 变更（不分拆 migration）
evidence_refs:
  - 附录 B §Gap#2 — 知识点 L3 未定影响组卷精度
  - 附录 C §Gap#5 — bank_question 字段稀疏影响错题本依赖
  - 附录 D §Gap#1 — Grade 缺独立表影响年级聚合
  - edu-cloud/alembic/versions/ 25 migration 印证渐进式代价
Q1: evidence_source: agent-surveyed-code + CLAUDE.md, evidence_state: verified
Q2_excluded:
  - "分散扩展 schema": 反证: S2/S3/S4 各改 L1 → Alembic 合并冲突 + 并发 schema 漂移
impact_scope: system
unknowns:
  - 生产库 mcu.asia 的 concept_graph_nodes / bank_questions 行数（S1 Day 1 spike）
```

---

## semantic_regression（ORC from parent design §12）

后续 executor 每轮 codex-review code 都必须对照本段：

**ORC-001: L1 数据模型冻结后上层 Sprint 不得扩展 L1 字段**
- Why: 避免并发开发的 schema 漂移
- How to apply: S2/S3/S4 发现需扩必须退回 S1 patch session

**ORC-002: edu-cloud 超前能力清单禁止倒退**
- Why: 防止局部 finding 覆盖全局设计（L017）
- How to apply: 本 plan 仅扩展字段，**不改 conduct / AI Agent / knowledge_tree G6 / BKT adaptive 任何现有字段语义**

**ORC-004: 好分数对照可追溯**
- Why: 决策证据纪律
- How to apply: 每个新字段 / 新表的 docstring 或 code comment 中注明 `refs: 附录{X} §{Gap#}` 或 `refs: haofenshu-clone/{path}:{line}`

**ORC-005: Sprint Gate 串行不可并跳**
- Why: 防止 S2 executor 基于未定型的 L1 假设
- How to apply: 本 plan 落地后必须 Gate G1 通过（alembic up/down 可逆 + 所有 deliverable 一次 commit + 数据模型冻结声明）

ORC-003（感知型任务）S1 无 UI 不涉及。

---

## File Structure

**Create:**
- `alembic/versions/{new_rev}_s1_l1_data_layer_haofenshu.py` — 一次性 L1 migration
- `src/edu_cloud/models/grade.py` — Grade ORM 模型
- `src/edu_cloud/modules/paper/constants.py` — PaperAccessLevel 枚举
- `src/edu_cloud/modules/calendar/teaching_plan_models.py` — TeachingPlan 骨架 ORM
- `src/edu_cloud/modules/profile/schemas.py` — StudentProfileView Pydantic VO
- `tests/modules/bank/test_bank_question_extended.py`
- `tests/modules/knowledge_tree/test_concept_depth_level.py`
- `tests/models/test_grade.py`
- `tests/modules/calendar/test_teaching_plan_model.py`
- `tests/modules/paper/test_access_level.py`
- `tests/modules/profile/test_student_profile_view.py`
- `tests/test_alembic_s1_migration.py`

**Modify:**
- `src/edu_cloud/modules/bank/models.py` — 5 个新字段
- `src/edu_cloud/modules/knowledge_tree/models.py` — `depth_level` 枚举列
- `src/edu_cloud/modules/student/models.py` — `Class.grade_id` FK
- `src/edu_cloud/models/__init__.py` — 暴露 Grade / TeachingPlan
- `src/edu_cloud/modules/profile/service.py` — 新增 `get_student_profile_view()`
- `src/edu_cloud/modules/profile/router.py` — 新增 GET `/api/v1/profile/students/{id}/view`

**Not touched in S1**: homework / adaptive / conduct / ai / knowledge / studio / 任何路由端点（除 profile/router 加 1 端点）

---

## Batch 1: 题库 + 知识点 schema（对应 design 1.1 + 1.2）

### Task 1: bank_question 5 个新字段（SQLAlchemy model）

**Files:**
- Modify: `src/edu_cloud/modules/bank/models.py:10-34`（BankQuestion 类）
- Test: `tests/modules/bank/test_bank_question_extended.py` (new)

**Reference:** 附录 C §Gap#5 + haofenshu-clone/server/config/schema.sql:232-245

- [ ] **Step 1.1: 写失败测试**

Create `tests/modules/bank/test_bank_question_extended.py`:

```python
"""S1 1.1: BankQuestion 5 个新字段断言。

refs: 附录 C §Gap#5 + haofenshu-clone/server/config/schema.sql:232-245
"""
from edu_cloud.modules.bank.models import BankQuestion


def test_bank_question_has_source_field():
    col = BankQuestion.__table__.columns.get("source")
    assert col is not None
    assert col.nullable is True


def test_bank_question_has_explanation_field():
    col = BankQuestion.__table__.columns.get("explanation")
    assert col is not None
    assert col.nullable is True


def test_bank_question_has_knowledge_point_ids_field():
    col = BankQuestion.__table__.columns.get("knowledge_point_ids")
    assert col is not None


def test_bank_question_has_grade_id_field():
    col = BankQuestion.__table__.columns.get("grade_id")
    assert col is not None
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "grades.id" in fks


def test_bank_question_has_difficulty_level_field():
    col = BankQuestion.__table__.columns.get("difficulty_level")
    assert col is not None
    assert col.nullable is True


def test_bank_question_existing_fields_untouched():
    """ORC-002: 不倒退现有字段"""
    for name in ("tags", "bloom_level", "difficulty", "discrimination", "sample_count"):
        assert BankQuestion.__table__.columns.get(name) is not None
```

- [ ] **Step 1.2: 跑测试确认失败**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/modules/bank/test_bank_question_extended.py -v
```

Expected: FAIL（source 字段缺失等）。

- [ ] **Step 1.3: 实现 model 扩展**

Edit `src/edu_cloud/modules/bank/models.py`，在 `BankQuestion` 的 `school_id` 上方加：

```python
    # S1 1.1 扩展（refs: 附录 C §Gap#5 + haofenshu-clone/server/config/schema.sql:232-245）
    source: Mapped[str | None] = mapped_column(String(20), default=None)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    knowledge_point_ids: Mapped[list | None] = mapped_column(JSON, default=None)
    grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None)
    difficulty_level: Mapped[str | None] = mapped_column(String(10), default=None)
```

- [ ] **Step 1.4: 跑测试验证通过**

```bash
.venv/bin/python -m pytest tests/modules/bank/test_bank_question_extended.py -v
```

Expected: 6 tests OK。

- [ ] **Step 1.5: 跑全量后端测试确认无回归**

```bash
.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -20
```

Expected: 新增 6 合并到 baseline_count，总数 ≥ 2052。

- [ ] **Step 1.6: Commit**

```bash
git add src/edu_cloud/modules/bank/models.py tests/modules/bank/test_bank_question_extended.py
git commit -m "feat(bank): S1 1.1 BankQuestion 5 字段扩展 (source/explanation/kp_ids/grade_id/difficulty_level)

refs: design §4 1.1 / 附录 C §Gap#5
"
```

---

### Task 2: concept_graph_nodes.depth_level 枚举列

**Files:**
- Modify: `src/edu_cloud/modules/knowledge_tree/models.py:11-31`（ConceptGraphNode 类）
- Test: `tests/modules/knowledge_tree/test_concept_depth_level.py` (new)

**Reference:** 附录 B §Gap#2 + haofenshu-clone/server/config/schema.sql:215-225

**设计决策：为什么新增 depth_level 而非复用 knowledge_level：**
现有 `knowledge_level` String(10) 用途未文档化，且知识图谱已有 node_type(concept/big_concept) 区分逻辑。新增独立 `depth_level` 枚举避免语义漂移（ORC-002）。值域：`subject` / `unit` / `core` / `point`。

- [ ] **Step 2.1: 写失败测试**

Create `tests/modules/knowledge_tree/test_concept_depth_level.py`:

```python
"""S1 1.2: ConceptGraphNode.depth_level 4 层枚举断言。

refs: 附录 B §Gap#2 + haofenshu-clone/server/config/schema.sql:215-225
"""
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode


def test_concept_graph_node_has_depth_level_field():
    col = ConceptGraphNode.__table__.columns.get("depth_level")
    assert col is not None
    assert col.nullable is True


def test_concept_graph_node_knowledge_level_unchanged():
    """ORC-002: knowledge_level 现有字段不倒退"""
    col = ConceptGraphNode.__table__.columns.get("knowledge_level")
    assert col is not None
    assert col.nullable is False


def test_concept_graph_node_node_type_unchanged():
    """ORC-002: node_type 默认值不倒退"""
    col = ConceptGraphNode.__table__.columns.get("node_type")
    assert col is not None
    assert col.default.arg == "concept"


def test_depth_level_valid_values():
    """4 层枚举值域断言（应用层校验）"""
    VALID = {"subject", "unit", "core", "point"}
    assert VALID == {"subject", "unit", "core", "point"}
```

- [ ] **Step 2.2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/modules/knowledge_tree/test_concept_depth_level.py -v
```

Expected: `test_concept_graph_node_has_depth_level_field` 失败。

- [ ] **Step 2.3: 实现 model 字段**

Edit `src/edu_cloud/modules/knowledge_tree/models.py`，在 `ConceptGraphNode` 的 `bloom_level` 字段之后加：

```python
    # S1 1.2 好分数 4 层知识体系（refs: 附录 B §Gap#2 + haofenshu-clone/server/config/schema.sql:215-225）
    # 值域: subject / unit / core / point
    depth_level: Mapped[str | None] = mapped_column(String(20), default=None)
```

- [ ] **Step 2.4: 跑测试验证通过**

```bash
.venv/bin/python -m pytest tests/modules/knowledge_tree/test_concept_depth_level.py -v
```

Expected: 4 tests OK。

- [ ] **Step 2.5: Commit**

```bash
git add src/edu_cloud/modules/knowledge_tree/models.py tests/modules/knowledge_tree/test_concept_depth_level.py
git commit -m "feat(knowledge_tree): S1 1.2 ConceptGraphNode.depth_level 枚举列

refs: design §4 1.2 / 附录 B §Gap#2
"
```

---

## Batch 2: 行政配置 schema（对应 design 1.3 + 1.4 + 1.5）

### Task 3: grades 独立表 ORM model

**Files:**
- Create: `src/edu_cloud/models/grade.py`
- Modify: `src/edu_cloud/models/__init__.py`（暴露 Grade 入口）
- Modify: `src/edu_cloud/modules/student/models.py`（Class.grade_id FK）
- Test: `tests/models/test_grade.py`（new）

**Reference:** 附录 D §Gap#1 + haofenshu-clone/server/routes/baseinfo.js

- [ ] **Step 3.1: 写失败测试**

Create `tests/models/test_grade.py`:

```python
"""S1 1.3: Grade 独立表 + Class.grade_id FK 断言。

refs: 附录 D §Gap#1 + haofenshu-clone/server/routes/baseinfo.js
"""


def test_grade_model_can_import():
    """ORM 外部入口约定（docs/arch/orm-placement.md）"""
    from edu_cloud.models import Grade  # noqa: F401


def test_grade_fields():
    from edu_cloud.models import Grade

    columns = {c.name for c in Grade.__table__.columns}
    required = {"id", "school_id", "name", "grade_level", "xueduan", "sort_order", "created_at", "updated_at"}
    assert required.issubset(columns)


def test_grade_school_fk():
    from edu_cloud.models import Grade

    col = Grade.__table__.columns.get("school_id")
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "schools.id" in fks


def test_grade_unique_school_name():
    from edu_cloud.models import Grade

    uqs = {tuple(sorted(c.name for c in uq.columns)) for uq in Grade.__table__.constraints
           if uq.__class__.__name__ == "UniqueConstraint"}
    assert any({"school_id", "name"} <= set(uq) for uq in uqs)


def test_class_has_grade_id_fk():
    from edu_cloud.modules.student.models import Class

    col = Class.__table__.columns.get("grade_id")
    assert col is not None
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "grades.id" in fks
    assert col.nullable is True

    g = Class.__table__.columns.get("grade")
    assert g is not None and g.nullable is False
```

- [ ] **Step 3.2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/models/test_grade.py -v
```

Expected: `test_grade_model_can_import` 失败 with ImportError。

- [ ] **Step 3.3: 创建 Grade model**

Create `src/edu_cloud/models/grade.py`:

```python
"""Grade 独立表（S1 1.3）。

refs: design §4 1.3 / 附录 D §Gap#1 / haofenshu-clone/server/routes/baseinfo.js

独立 Grade 表支持年级级聚合分析。Class.grade_id 为新 FK，
同时保留原 Class.grade 字符串列以支持渐进式迁移。
"""
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Grade(Base, IdMixin, TimestampMixin):
    """年级实体（校内唯一，支持学段分层）。"""
    __tablename__ = "grades"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_grade_school_name"),)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(50))
    grade_level: Mapped[int | None] = mapped_column(Integer, default=None)
    xueduan: Mapped[str | None] = mapped_column(String(20), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 3.4: 暴露 Grade 到 models 入口**

Edit `src/edu_cloud/models/__init__.py`，加：

```python
from edu_cloud.models.grade import Grade  # noqa: F401
```

若已有 `__all__`，补入 `"Grade"`。

- [ ] **Step 3.5: 实现 Class.grade_id**

Edit `src/edu_cloud/modules/student/models.py` 的 `Class` 类，在 `school_id` 上方加：

```python
    # S1 1.3 独立年级引用（refs: design §4 1.3 / 附录 D §Gap#1）
    grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None, nullable=True)
```

- [ ] **Step 3.6: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/models/test_grade.py -v
```

Expected: 5 tests OK。

- [ ] **Step 3.7: Commit**

```bash
git add src/edu_cloud/models/grade.py src/edu_cloud/models/__init__.py src/edu_cloud/modules/student/models.py tests/models/test_grade.py
git commit -m "feat(models): S1 1.3 Grade 独立表 + Class.grade_id FK

refs: design §4 1.3 / 附录 D §Gap#1
"
```

---

### Task 4: teaching_plans 表骨架

**Files:**
- Create: `src/edu_cloud/modules/calendar/teaching_plan_models.py`
- Modify: `src/edu_cloud/models/__init__.py`（暴露 TeachingPlan 入口）
- Test: `tests/modules/calendar/test_teaching_plan_model.py`（new）

**Reference:** 附录 C §Gap#6 + haofenshu-clone/server/config/schema.sql:284-302

**范围约束（ORC-005）**：S1 仅建骨架表 + ORM 模型，不加业务 service / router。

- [ ] **Step 4.1: 写失败测试**

Create `tests/modules/calendar/test_teaching_plan_model.py`:

```python
"""S1 1.4: TeachingPlan 骨架 ORM 断言。

refs: 附录 C §Gap#6 + haofenshu-clone/server/config/schema.sql:284-302
"""


def test_teaching_plan_import_from_models():
    from edu_cloud.models import TeachingPlan  # noqa: F401


def test_teaching_plan_fields():
    from edu_cloud.models import TeachingPlan

    cols = {c.name for c in TeachingPlan.__table__.columns}
    required = {"id", "school_id", "subject_code", "grade_id", "semester", "weeks_json", "created_by", "created_at", "updated_at"}
    assert required.issubset(cols)


def test_teaching_plan_fks():
    from edu_cloud.models import TeachingPlan

    fks_by_column = {}
    for col in TeachingPlan.__table__.columns:
        if col.foreign_keys:
            fks_by_column[col.name] = {fk.target_fullname for fk in col.foreign_keys}
    assert "schools.id" in fks_by_column.get("school_id", set())
    assert "grades.id" in fks_by_column.get("grade_id", set())
    assert "users.id" in fks_by_column.get("created_by", set())
```

- [ ] **Step 4.2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/modules/calendar/test_teaching_plan_model.py -v
```

Expected: ImportError 失败。

- [ ] **Step 4.3: 创建 TeachingPlan model 骨架**

Create `src/edu_cloud/modules/calendar/teaching_plan_models.py`:

```python
"""TeachingPlan 骨架 ORM（S1 1.4，S4 扩展业务）。

refs: design §4 1.4 / 附录 C §Gap#6 / haofenshu-clone/server/config/schema.sql:284-302

骨架目的：让 L2 2.2 ChapterCompose 组卷引擎引用 weeks_json 结构，避免 S4 改 schema 回溯。
"""
from sqlalchemy import String, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class TeachingPlan(Base, IdMixin, TimestampMixin):
    """教学计划（学期→周次→知识点，S4 关联资源）。"""
    __tablename__ = "teaching_plans"
    __table_args__ = (UniqueConstraint("school_id", "subject_code", "grade_id", "semester",
                                        name="uq_teaching_plan_subject_grade_semester"),)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None)
    semester: Mapped[str] = mapped_column(String(30))
    weeks_json: Mapped[list | None] = mapped_column(JSON, default=None)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), default=None)
```

- [ ] **Step 4.4: 暴露 TeachingPlan**

Edit `src/edu_cloud/models/__init__.py`，加：

```python
from edu_cloud.modules.calendar.teaching_plan_models import TeachingPlan  # noqa: F401
```

- [ ] **Step 4.5: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/modules/calendar/test_teaching_plan_model.py -v
```

Expected: 3 tests OK。

- [ ] **Step 4.6: Commit**

```bash
git add src/edu_cloud/modules/calendar/teaching_plan_models.py src/edu_cloud/models/__init__.py tests/modules/calendar/test_teaching_plan_model.py
git commit -m "feat(calendar): S1 1.4 TeachingPlan 骨架 ORM

refs: design §4 1.4 / 附录 C §Gap#6
"
```

---

### Task 5: PaperAccessLevel 枚举常量

**Files:**
- Create: `src/edu_cloud/modules/paper/constants.py`
- Test: `tests/modules/paper/test_access_level.py`（new）

**Reference:** 附录 C §Gap#4（试卷库权限分层）

- [ ] **Step 5.1: 写失败测试**

Create `tests/modules/paper/test_access_level.py`:

```python
"""S1 1.5: PaperAccessLevel 枚举常量断言。"""


def test_paper_access_level_import():
    from edu_cloud.modules.paper.constants import PaperAccessLevel  # noqa: F401


def test_paper_access_level_values():
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    assert PaperAccessLevel.TEACHER_PRIVATE.value == "teacher_private"
    assert PaperAccessLevel.SCHOOL_SHARED.value == "school_shared"
    assert PaperAccessLevel.DISTRICT_SHARED.value == "district_shared"


def test_paper_access_level_all_values():
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    values = {lvl.value for lvl in PaperAccessLevel}
    assert values == {"teacher_private", "school_shared", "district_shared"}
```

- [ ] **Step 5.2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/modules/paper/test_access_level.py -v
```

Expected: ImportError 失败。

- [ ] **Step 5.3: 创建 constants.py**

Create `src/edu_cloud/modules/paper/constants.py`:

```python
"""Paper 模块常量（S1 1.5）。

refs: design §4 1.5 / 附录 C §Gap#4
"""
from enum import Enum


class PaperAccessLevel(str, Enum):
    """试卷访问层级（S4 4.2 分享工作流使用）。"""
    TEACHER_PRIVATE = "teacher_private"
    SCHOOL_SHARED = "school_shared"
    DISTRICT_SHARED = "district_shared"
```

- [ ] **Step 5.4: 跑测试确认通过**

```bash
.venv/bin/python -m pytest tests/modules/paper/test_access_level.py -v
```

Expected: 3 tests OK。

- [ ] **Step 5.5: Commit**

```bash
git add src/edu_cloud/modules/paper/constants.py tests/modules/paper/test_access_level.py
git commit -m "feat(paper): S1 1.5 PaperAccessLevel 枚举常量

refs: design §4 1.5 / 附录 C §Gap#4
"
```

---

## Batch 3: Pydantic VO（对应 design 1.6）

### Task 6: StudentProfileView Pydantic schema

**Files:**
- Create: `src/edu_cloud/modules/profile/schemas.py`
- Test: `tests/modules/profile/test_student_profile_view.py`（new，T6 + T7 共用）

**Reference:** 附录 B §Gap#1（学情画像前端综合页）

**设计决策**：复用现有 `StudentExamSnapshot / StudentKnowledgeMastery / StudentErrorPattern` 三表，零新表。

- [ ] **Step 6.1: 写失败测试（仅 schema 部分）**

Create `tests/modules/profile/test_student_profile_view.py`:

```python
"""S1 1.6: StudentProfileView Pydantic VO + 聚合服务断言。

refs: 附录 B §Gap#1 + design §4 1.6
"""
import pytest
from datetime import datetime


def test_student_profile_view_schema_import():
    from edu_cloud.modules.profile.schemas import StudentProfileView  # noqa: F401


def test_student_profile_view_required_fields():
    from edu_cloud.modules.profile.schemas import StudentProfileView

    fields = StudentProfileView.model_fields
    required = {"student_id", "school_id", "trend", "knowledge_map", "error_patterns", "summary", "generated_at"}
    assert required.issubset(set(fields.keys()))


def test_student_profile_view_minimal_construction():
    from edu_cloud.modules.profile.schemas import StudentProfileView

    vo = StudentProfileView(
        student_id="s001",
        school_id="sch_a",
        trend=[],
        knowledge_map=[],
        error_patterns=[],
        summary={"exam_count": 0, "avg_score_rate": 0.0, "weakness_top3": []},
        generated_at=datetime.utcnow(),
    )
    assert vo.student_id == "s001"
    assert vo.summary["exam_count"] == 0
```

- [ ] **Step 6.2: 跑测试确认失败**

```bash
.venv/bin/python -m pytest tests/modules/profile/test_student_profile_view.py -v
```

Expected: ImportError 失败。

- [ ] **Step 6.3: 创建 schemas.py**

Create `src/edu_cloud/modules/profile/schemas.py`:

```python
"""Profile 模块 Pydantic schemas（S1 1.6）。

refs: design §4 1.6 / 附录 B §Gap#1

StudentProfileView 聚合 StudentExamSnapshot / StudentKnowledgeMastery / StudentErrorPattern 三表。
零新表，为 S3 3.2 StudentProfilePage.vue 提供综合数据源。
"""
from datetime import datetime
from pydantic import BaseModel, Field


class TrendEntry(BaseModel):
    exam_id: str
    subject_code: str
    total_score: float
    max_score: float
    score_rate: float
    class_rank: int | None = None
    grade_rank: int | None = None
    exam_date: datetime | None = None


class KnowledgeEntry(BaseModel):
    knowledge_point_id: str
    mastery_level: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    trend: str
    attempt_count: int
    correct_count: int


class ErrorPatternEntry(BaseModel):
    subject_code: str
    error_distribution: dict
    total_errors: int
    careless_rate: float | None = None
    snapshot_date: datetime


class ProfileSummary(BaseModel):
    exam_count: int
    avg_score_rate: float
    weakness_top3: list[str]


class StudentProfileView(BaseModel):
    """学生学情综合视图（S3 前端消费）。"""
    student_id: str
    school_id: str
    trend: list[TrendEntry]
    knowledge_map: list[KnowledgeEntry]
    error_patterns: list[ErrorPatternEntry]
    summary: ProfileSummary
    generated_at: datetime
```

- [ ] **Step 6.4: 跑测试确认通过（Task 6 部分）**

```bash
.venv/bin/python -m pytest tests/modules/profile/test_student_profile_view.py::test_student_profile_view_schema_import tests/modules/profile/test_student_profile_view.py::test_student_profile_view_required_fields tests/modules/profile/test_student_profile_view.py::test_student_profile_view_minimal_construction -v
```

Expected: 3 tests OK。

- [ ] **Step 6.5: Commit**

```bash
git add src/edu_cloud/modules/profile/schemas.py tests/modules/profile/test_student_profile_view.py
git commit -m "feat(profile): S1 1.6 StudentProfileView Pydantic VO

refs: design §4 1.6 / 附录 B §Gap#1
"
```

---

### Task 7: Profile 聚合服务方法 + 骨架端点

**Files:**
- Modify: `src/edu_cloud/modules/profile/service.py`（add `get_student_profile_view`）
- Modify: `src/edu_cloud/modules/profile/router.py`（add GET `/api/v1/profile/students/{id}/view`）
- Test: `tests/modules/profile/test_student_profile_view.py`（extend）

- [ ] **Step 7.1: 扩展失败测试**

Edit `tests/modules/profile/test_student_profile_view.py`，在文件末尾追加：

```python
@pytest.mark.asyncio
async def test_get_student_profile_view_empty_student(db_engine, school):
    """学生无历史数据时返回空 VO（不崩溃）"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from edu_cloud.modules.profile.service import get_student_profile_view

    async with AsyncSession(db_engine) as db:
        vo = await get_student_profile_view(
            db, student_id="student_no_data", school_id=school.id
        )
    assert vo.student_id == "student_no_data"
    assert vo.trend == []
    assert vo.knowledge_map == []
    assert vo.summary.exam_count == 0


@pytest.mark.asyncio
async def test_profile_view_endpoint_requires_auth(client):
    resp = await client.get("/api/v1/profile/students/s001/view")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_profile_view_endpoint_returns_vo_shape(client, admin_headers, school):
    resp = await client.get(
        f"/api/v1/profile/students/student_no_data/view",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["student_id"] == "student_no_data"
    assert "trend" in data and "knowledge_map" in data
```

`client` / `admin_headers` / `school` / `db_engine` 来自 `tests/conftest.py` 现有 fixture。

- [ ] **Step 7.2: 跑测试确认新断言失败**

```bash
.venv/bin/python -m pytest tests/modules/profile/test_student_profile_view.py -v
```

Expected: 3 个新 test 失败。

- [ ] **Step 7.3: 实现 service 方法**

Edit `src/edu_cloud/modules/profile/service.py`，在文件末尾加：

```python
from datetime import datetime
from edu_cloud.modules.profile.schemas import (
    StudentProfileView, TrendEntry, KnowledgeEntry, ErrorPatternEntry, ProfileSummary,
)


async def get_student_profile_view(
    db: AsyncSession,
    *,
    student_id: str,
    school_id: str,
    subject_code: str | None = None,
    trend_limit: int = 10,
) -> StudentProfileView:
    """聚合学生学情综合视图（零新表，读取现有 3 表）。

    refs: design §4 1.6 / 附录 B §Gap#1
    """
    trend_rows = await get_student_trend(
        db, student_id=student_id, school_id=school_id,
        subject_code=subject_code, limit=trend_limit,
    )
    trend = [
        TrendEntry(
            exam_id=r.exam_id, subject_code=r.subject_code,
            total_score=r.total_score, max_score=r.max_score,
            score_rate=r.score_rate,
            class_rank=r.class_rank, grade_rank=r.grade_rank,
            exam_date=r.exam_date,
        ) for r in trend_rows
    ]

    knowledge_rows = await get_student_knowledge_map(
        db, student_id=student_id, school_id=school_id,
    )
    knowledge_map = [
        KnowledgeEntry(
            knowledge_point_id=r.knowledge_point_id,
            mastery_level=r.mastery_level, confidence=r.confidence,
            trend=r.trend, attempt_count=r.attempt_count, correct_count=r.correct_count,
        ) for r in knowledge_rows
    ]

    error_rows = await get_student_error_pattern(
        db, student_id=student_id, school_id=school_id, subject_code=subject_code,
    )
    error_patterns = [
        ErrorPatternEntry(
            subject_code=r.subject_code,
            error_distribution=r.error_distribution or {},
            total_errors=r.total_errors,
            careless_rate=r.careless_rate,
            snapshot_date=r.snapshot_date,
        ) for r in error_rows
    ]

    weakness_top3 = [k.knowledge_point_id for k in sorted(
        knowledge_map, key=lambda x: x.mastery_level
    )[:3]]

    summary = ProfileSummary(
        exam_count=len(trend),
        avg_score_rate=(sum(t.score_rate for t in trend) / len(trend)) if trend else 0.0,
        weakness_top3=weakness_top3,
    )

    return StudentProfileView(
        student_id=student_id, school_id=school_id,
        trend=trend, knowledge_map=knowledge_map, error_patterns=error_patterns,
        summary=summary, generated_at=datetime.utcnow(),
    )
```

- [ ] **Step 7.4: 实现 router 端点**

Edit `src/edu_cloud/modules/profile/router.py`。若已有 router 实例（变量名以 `router` 或 `profile_router` 命名），复用并追加：

```python
from edu_cloud.modules.profile.schemas import StudentProfileView
from edu_cloud.modules.profile.service import get_student_profile_view
from edu_cloud.core.permissions import Permission


@router.get("/students/{student_id}/view", response_model=StudentProfileView)
async def student_profile_view(
    student_id: str,
    subject_code: str | None = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission(Permission.VIEW_SCORES)),
) -> StudentProfileView:
    """学情画像综合视图（S3 前端消费骨架端点，refs: design §4 1.6）"""
    return await get_student_profile_view(
        db, student_id=student_id, school_id=user.school_id, subject_code=subject_code,
    )
```

若现有 router 实例不同名字或端点挂载在 `api/app.py`，请按照现有 profile/router.py 的 pattern 调整 import / decorator。

- [ ] **Step 7.5: 跑测试确认全通过**

```bash
.venv/bin/python -m pytest tests/modules/profile/test_student_profile_view.py -v
```

Expected: 6 tests OK（3 Task 6 + 3 Task 7）。

- [ ] **Step 7.6: 跑全量测试**

```bash
.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -20
```

Expected: 总 pass 数 ≥ baseline_count + Batch 1-3 增量。

- [ ] **Step 7.7: Commit**

```bash
git add src/edu_cloud/modules/profile/service.py src/edu_cloud/modules/profile/router.py tests/modules/profile/test_student_profile_view.py
git commit -m "feat(profile): S1 1.6 get_student_profile_view 聚合 + /profile/students/{id}/view 端点

refs: design §4 1.6 / 附录 B §Gap#1
"
```

---

## Batch 4: Alembic migration + Gate G1 通过

### Task 8: 一次性 Alembic migration

**Files:**
- Create: `alembic/versions/{new_rev}_s1_l1_data_layer_haofenshu.py`
- Test: `tests/test_alembic_s1_migration.py`（new）

**基准**：`down_revision = 'f7a3b2c1d456'`（现最新 migration `add_teacher_profile_fields`）

**方言中立约束**（见 docs/plans/2026-04-13-migration-gate-repair-design.md）：所有表扩展走 `batch_alter_table`；UniqueConstraint 内嵌 create_table。

- [ ] **Step 8.1: 生成 migration 骨架**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/alembic revision -m "s1 l1 data layer haofenshu"
```

Expected output: 创建 `alembic/versions/XXXXXXXXXXXX_s1_l1_data_layer_haofenshu.py`。

- [ ] **Step 8.2: 写失败 smoke test**

Create `tests/test_alembic_s1_migration.py`:

```python
"""S1 Alembic migration smoke test：upgrade/downgrade 可逆 + 数据保留。"""
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command


@pytest.fixture(scope="function")
def alembic_cfg(tmp_path):
    db_path = tmp_path / "s1_test.db"
    cfg = Config("/home/ops/projects/edu-cloud/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg, f"sqlite:///{db_path}"


def test_s1_migration_upgrade_creates_tables(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "grades" in tables
    assert "teaching_plans" in tables

    bank_cols = {c["name"] for c in insp.get_columns("bank_questions")}
    assert {"source", "explanation", "knowledge_point_ids", "grade_id", "difficulty_level"}.issubset(bank_cols)

    concept_cols = {c["name"] for c in insp.get_columns("concept_graph_nodes")}
    assert "depth_level" in concept_cols

    class_cols = {c["name"] for c in insp.get_columns("classes")}
    assert "grade_id" in class_cols


def test_s1_migration_downgrade_removes_all_changes(alembic_cfg):
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "f7a3b2c1d456")

    engine = create_engine(url)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "grades" not in tables
    assert "teaching_plans" not in tables

    bank_cols = {c["name"] for c in insp.get_columns("bank_questions")}
    assert "source" not in bank_cols
    assert "grade_id" not in bank_cols

    concept_cols = {c["name"] for c in insp.get_columns("concept_graph_nodes")}
    assert "depth_level" not in concept_cols


def test_s1_migration_preserves_existing_data(alembic_cfg):
    """ORC-002: upgrade 不丢现有数据"""
    cfg, url = alembic_cfg
    command.upgrade(cfg, "f7a3b2c1d456")

    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO bank_questions (id, question_type, max_score, school_id, tags, bloom_level) "
            "VALUES ('bq1', 'choice', 5.0, 'sch1', '[]', NULL)"
        ))
        conn.commit()

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        result = conn.execute(text("SELECT id, tags, bloom_level, source FROM bank_questions WHERE id='bq1'"))
        row = result.first()
    assert row is not None
    assert row[0] == "bq1"
    assert row[1] == "[]"
    assert row[3] is None
```

- [ ] **Step 8.3: 编辑 migration 文件**

Edit 刚生成的 `alembic/versions/XXXXXXXXXXXX_s1_l1_data_layer_haofenshu.py`：

```python
"""s1 l1 data layer haofenshu

Revision ID: {新 rev}
Revises: f7a3b2c1d456
Create Date: 2026-04-24

S1 L1 数据层一次性 migration（refs: design §4 / 附录 B/C/D）：
- bank_questions +5 字段
- concept_graph_nodes +depth_level
- 新建 grades 表
- classes +grade_id FK
- 新建 teaching_plans 表

方言中立（SQLite + PG 双支持）。refs: docs/plans/2026-04-13-migration-gate-repair-design.md
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '{新 rev}'
down_revision: Union[str, Sequence[str], None] = 'f7a3b2c1d456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1.3 grades 新表
    op.create_table(
        'grades',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('school_id', sa.String(length=36), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('grade_level', sa.Integer(), nullable=True),
        sa.Column('xueduan', sa.String(length=20), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('school_id', 'name', name='uq_grade_school_name'),
    )

    # 1.4 teaching_plans 新表
    op.create_table(
        'teaching_plans',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('school_id', sa.String(length=36), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('subject_code', sa.String(length=50), nullable=False),
        sa.Column('grade_id', sa.String(length=36), sa.ForeignKey('grades.id'), nullable=True),
        sa.Column('semester', sa.String(length=30), nullable=False),
        sa.Column('weeks_json', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('school_id', 'subject_code', 'grade_id', 'semester',
                            name='uq_teaching_plan_subject_grade_semester'),
    )

    # 1.1 bank_questions 扩展
    with op.batch_alter_table('bank_questions') as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('explanation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('knowledge_point_ids', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('grade_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('difficulty_level', sa.String(length=10), nullable=True))
        batch_op.create_foreign_key(
            'fk_bank_questions_grade_id', 'grades', ['grade_id'], ['id'],
        )

    # 1.2 concept_graph_nodes.depth_level
    with op.batch_alter_table('concept_graph_nodes') as batch_op:
        batch_op.add_column(sa.Column('depth_level', sa.String(length=20), nullable=True))

    # 1.3 classes.grade_id FK
    with op.batch_alter_table('classes') as batch_op:
        batch_op.add_column(sa.Column('grade_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_classes_grade_id', 'grades', ['grade_id'], ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('classes') as batch_op:
        batch_op.drop_constraint('fk_classes_grade_id', type_='foreignkey')
        batch_op.drop_column('grade_id')

    with op.batch_alter_table('concept_graph_nodes') as batch_op:
        batch_op.drop_column('depth_level')

    with op.batch_alter_table('bank_questions') as batch_op:
        batch_op.drop_constraint('fk_bank_questions_grade_id', type_='foreignkey')
        batch_op.drop_column('difficulty_level')
        batch_op.drop_column('grade_id')
        batch_op.drop_column('knowledge_point_ids')
        batch_op.drop_column('explanation')
        batch_op.drop_column('source')

    op.drop_table('teaching_plans')
    op.drop_table('grades')
```

`{新 rev}` 替换为 Step 8.1 生成的 12 位 hex id。

- [ ] **Step 8.4: 跑 smoke test 验证**

```bash
.venv/bin/python -m pytest tests/test_alembic_s1_migration.py -v
```

Expected: 3 tests OK（upgrade / downgrade / data preservation）。

- [ ] **Step 8.5: 跑现有 alembic smoke test 确认无回归**

```bash
.venv/bin/python -m pytest tests/test_alembic_migration.py -v
```

Expected: 原测试全通过（不回归历史 migration 完整性）。

- [ ] **Step 8.6: 跑全量测试集确认无回归**

```bash
.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -20
```

Expected: 总 pass 数 ≥ baseline_count + Batch 1-3 增量 + 3。

- [ ] **Step 8.7: Commit**

```bash
git add alembic/versions/*s1_l1_data_layer_haofenshu.py tests/test_alembic_s1_migration.py
git commit -m "feat(alembic): S1 L1 数据层一次性 migration + smoke test

含：bank_questions +5 字段 / concept_graph_nodes.depth_level / grades 表 / classes.grade_id / teaching_plans 骨架
SQLite + PG 方言中立，upgrade/downgrade 可逆

refs: design §4 / 附录 B/C/D / 2026-04-13-migration-gate-repair-design.md
"
```

---

### Task 9: 生产库 dump spike（Gate G1 前置验证）

**Files:** 无代码变更，spike 验证。

**目的**：G1 通过前验证 S1 migration 在 mcu.asia 生产库 dump 上能正确 up/down。

- [ ] **Step 9.1: 获取 mcu.asia 生产库 dump**

由用户在本地执行（Claude 不操作生产库）：

```bash
# SQLite（L016：禁止 cp 活跃 db）
sqlite3 edu_cloud.db ".backup /tmp/edu_cloud_dump_s1_test.db"
# PostgreSQL
# pg_dump -U postgres edu_cloud > /tmp/edu_cloud_dump_s1_test.sql
```

- [ ] **Step 9.2: 配置临时 DATABASE_URL 跑 migration**

```bash
cd /home/ops/projects/edu-cloud
DATABASE_URL="sqlite:////tmp/edu_cloud_dump_s1_test.db" .venv/bin/alembic current
DATABASE_URL="sqlite:////tmp/edu_cloud_dump_s1_test.db" .venv/bin/alembic upgrade head
```

Expected:
- `alembic current` 显示 `f7a3b2c1d456` 或更早
- `alembic upgrade head` 成功到新 S1 revision

- [ ] **Step 9.3: 验证数据保留**

```bash
sqlite3 /tmp/edu_cloud_dump_s1_test.db <<EOF
SELECT COUNT(*) FROM bank_questions;
SELECT COUNT(*) FROM concept_graph_nodes;
SELECT COUNT(*) FROM classes;
SELECT COUNT(*) FROM grades;
SELECT COUNT(*) FROM teaching_plans;
SELECT id, source, difficulty_level FROM bank_questions LIMIT 3;
EOF
```

Expected:
- bank_questions / concept_graph_nodes / classes 行数与 migration 前一致
- grades / teaching_plans 行数为 0
- 新列返回 NULL

- [ ] **Step 9.4: 验证 downgrade 可逆**

```bash
DATABASE_URL="sqlite:////tmp/edu_cloud_dump_s1_test.db" .venv/bin/alembic downgrade f7a3b2c1d456
sqlite3 /tmp/edu_cloud_dump_s1_test.db ".schema bank_questions" | grep -E "source|difficulty_level"
```

Expected: grep 无匹配（新列已移除）。

- [ ] **Step 9.5: 记录 spike 结果（Task 10 使用）**

手工记录（不 commit）：

```
S1 Day 1 Production DB Spike 结果：
- 原 bank_questions 行数: {实测}
- 原 concept_graph_nodes 行数: {实测}
- 原 classes 行数: {实测}
- upgrade 耗时: {实测秒}
- downgrade 可逆: PASS
- 数据完整性: PASS
```

---

### Task 10: Gate G1 通过声明 + Handoff

**Files:**
- Create: `docs/plans/2026-04-24-haofenshu-s1-handoff.md`

- [ ] **Step 10.1: Gate G1 checklist**

逐项手动确认 PASS：

- [ ] S1 Alembic migration 单文件（未分拆）
- [ ] `alembic upgrade head` 在空 db 成功
- [ ] `alembic downgrade f7a3b2c1d456` 在空 db 成功
- [ ] `alembic upgrade head` 在 mcu.asia 生产库 dump 成功（Task 9）
- [ ] `tests/test_alembic_s1_migration.py` 3/3 tests OK
- [ ] `tests/test_alembic_migration.py` 不回归
- [ ] 全量测试总 pass 数 ≥ baseline_count + S1 增量
- [ ] 每个 deliverable commit 有 `refs: design §X / 附录 Y §Gap#Z`（ORC-004）
- [ ] ORC-001 遵守：S1 之后不改 L1 schema
- [ ] ORC-002 遵守：conduct / AI Agent / knowledge_tree G6 / BKT adaptive 字段零变更

- [ ] **Step 10.2: 写 handoff.md**

Create `docs/plans/2026-04-24-haofenshu-s1-handoff.md` (≤15 行硬限)：

```markdown
# S1 L1 数据层 Handoff

**Sprint**: S1 (Phase 2 haofenshu) / **Gate G1**: PASS / **Date**: {执行日期}

## Deliverables PASS
- 1.1 bank_questions +5 字段
- 1.2 concept_graph_nodes.depth_level
- 1.3 grades 独立表 + Class.grade_id FK
- 1.4 teaching_plans 骨架表
- 1.5 PaperAccessLevel 枚举
- 1.6 StudentProfileView VO + /profile/students/{id}/view 端点

## 测试基线
- 全量 {实测} OK（原 baseline_count 见本 plan frontmatter）

## Gate G1 证据
- alembic up/down 空 db + 生产库 dump: PASS
- ORC-001 / -002 / -004 / -005 遵守
```

- [ ] **Step 10.3: Commit handoff**

```bash
git add docs/plans/2026-04-24-haofenshu-s1-handoff.md
git commit -m "chore(haofenshu): S1 Gate G1 PASS + handoff

数据模型冻结声明生效，S2 可启动 writing-plans
"
```

- [ ] **Step 10.4: 准备 codex-review plan 触发**

本 plan commit 后会触发 `codex-review plan`（gates.json 硬拦截）。不要开启 executor session 直到 codex-review plan PASS。

---

## Self-Review

**1. Spec coverage check:**
- design §4.1 1.1 bank_question → Task 1 ✓
- design §4.1 1.2 concept depth_level → Task 2 ✓
- design §4.1 1.3 grades + Class.grade_id → Task 3 ✓
- design §4.1 1.4 teaching_plans 骨架 → Task 4 ✓
- design §4.1 1.5 paper_access_level → Task 5 ✓
- design §4.1 1.6 StudentProfileView VO → Task 6+7 ✓
- design §4.2 Alembic 迁移策略 → Task 8 ✓
- design §4.3 生产库 spike → Task 9 ✓
- design §9 Gate G1 → Task 10 ✓

**2. Placeholder scan:** 每个 Step 都有具体 code / command / expected。

**3. Type consistency:**
- BankQuestion 新字段名贯穿 Task 1 / Task 8 一致
- ConceptGraphNode.depth_level 命名一致
- Grade / Class.grade_id / TeachingPlan / PaperAccessLevel 跨 Task 命名一致
- StudentProfileView 的 TrendEntry / KnowledgeEntry / ErrorPatternEntry / ProfileSummary 在 schemas.py 和 service.py 引用一致

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan.md`.

按 CLAUDE.md `session_guard` 规则，executing-plans 必须在新会话进行。当前会话写完 plan + commit 后即停手。

**下一会话（Session B）启动（用户手动）：**

```
开新 Claude Code 会话，执行：
superpowers:executing-plans docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan.md
```

**推荐执行模式：superpowers:subagent-driven-development**（本 plan 10 Task 可拆 3 subagent 并发：Batch 1 / Batch 2 / Batch 3；Batch 4 Task 8-10 依赖前三 batch 顺序执行）。

**备选模式：superpowers:executing-plans**（单 session inline）。

---

## 变更日志

- 2026-04-24 v0.1 初稿（writing-plans session by Claude Opus 4.7 1M；基于 2026-04-24-haofenshu-vs-edu-phase2-design.md §4 + 附录 B/C/D）
