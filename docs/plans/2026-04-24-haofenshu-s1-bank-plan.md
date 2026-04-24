---
baseline_command: .venv/bin/python -m pytest --tb=no -q
baseline_verified_at: 2026-04-24T11:04:27+08:00
baseline_count: 2064 passed / 22 failed / 1 error / 23 skipped (0:13:51)
task_tier: T3
topic: haofenshu-s1-bank
---

> **⚠️ Baseline 诚实披露**（L015 反虚假完成）：当前 HEAD 上 baseline 实测含 **22 failed + 1 error**，是 pre-S1-A 既有状态（S1-A 未动任何代码）。S1-A Gate 只要求"不新增 failure + 新测试全绿"，不承担既有技术债处置。既有 failed 清单由独立 T3 任务评估是否构成 L019 打地鼠模式。详见 §Deferred 第 7 条。

# haofenshu-s1-bank Implementation Plan (S1-A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `bank_questions` 表扩展 5 个学情闭环缺失字段（`source` / `explanation` / `knowledge_point_ids` / `difficulty_level` / `grade_id`），并用 linear chain 首环 migration (down_revision=`36e25241e55d`) 落地，为 S1-B/C/D 后续子 topic 打通首环。

**Architecture:** 遵守 edu-cloud 既有 ORM 注册约定（`alembic/env.py:51` + `api/app.py:41` 已 import `modules.bank.models`，S1-A 只扩字段无需新增 import）。Migration 用 `batch_alter_table` 包装 add_column，兼容 SQLite 测试 + PostgreSQL 生产双方言（echoes `2026-04-13-migration-gate-repair-design.md` 经验）。与 parent design §4.2 v0.2 "linear chain 分拆" 约束对齐。

**Tech Stack:** SQLAlchemy 2.0 async / Alembic / PostgreSQL (prod) + SQLite (test) / pytest / asyncpg

---

## Evidence Block (from parent design §13 + S1-A 独立调研)

### Evidence: E-001 — bank_questions 现有字段清单（ORC-S1A-003 "只加不改" 依据）

**decision**: S1-A 只扩展 5 个**全新**字段；design §4.1 列的 7 字段中 `tags` / `bloom_level` 已存在，无操作（见 §Deferred/Design Concerns）。

**evidence_refs**:
- `src/edu_cloud/modules/bank/models.py:10-35` — BankQuestion 当前字段（13 列 + 4 mixin）
- `alembic/versions/8b3f659c1a2a_initial_merged_schema.py:500-514` — bank_questions initial schema 所有列
- Grep 命令：`grep -n "Mapped" src/edu_cloud/modules/bank/models.py`
  - 输出：包含 `tags: Mapped[list | None] = mapped_column(JSON, default=None)` 和 `bloom_level: Mapped[str | None] = mapped_column(String(20), default=None)`

**Q1**: evidence_source: code-read, evidence_state: verified
**Q2_excluded**:
- "强行加 tags 字段": 反证路径: alembic autogenerate 检测到 duplicate column `tags` 会 raise `DuplicateColumnError`；本地验证 → 预期 upgrade 失败。
- "将 bloom_level String(20) 就地改为 Enum": 反证路径: 属"改字段类型"而非"加"，违反 ORC-S1A-003；需独立 behavior change Task 评估现有数据兼容性。
**impact_scope**: module (bank)
**unknowns**: mcu.asia 生产库当前 bank_questions 行数（影响 migration 耗时，非阻断）
**followup_spike**: Gate G1-S1A 前 `ssh server 'sqlite3 /srv/apps/edu-cloud/shared/data/edu_cloud.db "SELECT COUNT(*) FROM bank_questions;"'` 或 PG 等价查询

---

### Evidence: E-002 — Alembic linear chain 首环锚点（F001 修正核心）

**decision**: S1-A migration 的 `down_revision = '36e25241e55d'`（真实 head），**不是** original plan 误写的 `'f7a3b2c1d456'`（该节点 down_revision=None 是早期分支根）。

**evidence_refs**:
- `.venv/bin/alembic heads` 实测输出（2026-04-24）：
  ```
  36e25241e55d (head)
  ```
- `.venv/bin/alembic current` 实测输出（2026-04-24，本地测试库）：
  ```
  e241e1568792
  ```
- `alembic/versions/36e25241e55d_add_academic_tables_and_subject_.py:17-18`：
  ```python
  revision: str = '36e25241e55d'
  down_revision: Union[str, Sequence[str], None] = 'e241e1568792'
  ```
- 完整链路（向 base 追溯）：`36e25241e55d ← e241e1568792 ← 874f6f9c14cc (merge) ← (45c9d83d780e, f7a3b2c1d456)`
- 负面断言：`grep -n "down_revision = None" alembic/versions/f7a3b2c1d456*.py` → 验证 f7a3b2c1d456 是分支根（down_revision=None）而不是 head

**Q1**: evidence_source: code-read + command-output, evidence_state: verified
**Q2_excluded**:
- "绑到 f7a3b2c1d456（original plan 的选择）": 反证路径: f7a3b2c1d456 down_revision=None，若绑定会形成新分支并让 `alembic heads` 返回 2 个 heads，破坏链性。
**impact_scope**: module (alembic-migrations)
**unknowns**: none

---

### Evidence: E-003 — ORM 注册链路完整（F002 验证）

**decision**: bank 模块的 ORM 注册在 S1-A 开始前**已完整**；S1-A 只扩字段无需改 `alembic/env.py` 或 `api/app.py`。

**evidence_refs**:
- `alembic/env.py:51` — `from edu_cloud.modules.bank.models import BankQuestion, StudentErrorBook  # noqa: F401`
- `src/edu_cloud/api/app.py:41` — `import edu_cloud.modules.bank.models  # noqa: F401 — BankQuestion/StudentErrorBook`
- `docs/arch/orm-placement.md:201-215` — 模块 ORM 约定（只放 `modules/<name>/models.py`）

**Q1**: evidence_source: code-read, evidence_state: verified
**Q2_excluded**:
- "按 original plan 新增 models/__init__.py 导出": 反证路径: `src/edu_cloud/models/__init__.py` 当前是空文件（`wc -l` 实测 0 行），不参与注册；bank 注册已走 env.py+app.py，无须触碰 __init__.py。
**impact_scope**: module (bank, alembic, api)
**unknowns**: none

---

### Evidence: E-004 — bank_questions initial schema 必填列（F003 smoke test 修正依据）

**decision**: Migration smoke test 的 INSERT 语句必须带齐 `school_id` / `id` / `question_type` / `max_score` / `sample_count` / `created_at` / `updated_at` 7 个必填列（NOT NULL），否则 upgrade 后 INSERT 会触发 NOT NULL violation 在数据构造阶段直接失败。

**evidence_refs**:
- `alembic/versions/8b3f659c1a2a_initial_merged_schema.py:502-513` 实测：
  ```python
  sa.Column('question_type', sa.String(length=20), nullable=False),
  sa.Column('max_score', sa.Float(), nullable=False),
  sa.Column('sample_count', sa.Integer(), nullable=False),
  sa.Column('school_id', sa.String(length=36), nullable=False),
  sa.Column('id', sa.String(length=36), nullable=False),
  sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
  sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
  ```

**Q1**: evidence_source: code-read, evidence_state: verified
**Q2_excluded**:
- "只传 `id + question_type + max_score`（original plan Task 8 Step 8.2 做法）": 反证路径: SQLite / PG 都会在执行 INSERT 时报 `NOT NULL constraint failed: bank_questions.sample_count`，smoke test 根本进不到 upgrade 后的断言环节。
**impact_scope**: module (test-infra)
**unknowns**: none

---

### Evidence: E-005 — bank 模块现有测试位置（测试放置惯例）

**decision**: S1-A 新测试分三处：
1. Migration smoke test → 新文件 `tests/test_alembic_s1a_bank.py`（与既有 `tests/test_alembic_migration.py` 并列，便于按子 topic 拆分）
2. ORM round-trip test → 扩展 `tests/test_services_exam/test_bank_service.py`（已有 BankQuestion+School fixture 模式）
3. Migration head 约束 → 扩展 `tests/test_alembic_migration.py::test_migration_head_is_single`（已有 test 天然覆盖"S1-A 后 heads 仍为 1"）

**evidence_refs**:
- `ls tests/ | grep bank` 输出：
  ```
  tests/test_api/test_bank_api.py
  tests/test_services_exam/test_bank_service.py
  tests/test_api_exam/test_bank.py
  ```
- `tests/test_services_exam/test_bank_service.py:10-17` 现有测试模式（School + BankQuestion 直接构造）
- `tests/test_alembic_migration.py:103-117` 现有 3 个 smoke test（creates_all_expected_tables / head_is_single / downgrade_is_clean）

**Q1**: evidence_source: code-read + command-output, evidence_state: verified
**Q2_excluded**:
- "把 migration smoke 塞到 test_alembic_migration.py 里": 反证路径: 该文件是全量 migration smoke，加入 S1-A 专用逻辑后拆 topic 时难以 cherry-pick；独立文件更符合 linear chain 子 topic 自包含原则。
**impact_scope**: module (test-infra)
**unknowns**: none

---

## semantic_regression（ORC from parent design §12）

以下 4 条 ORC 在 S1-A 实施期间**不可违反**。Executor 每完成 Task 必须自审对应 ORC 是否满足。codex-review code 阶段会独立复核。

### ORC-S1A-001: linear chain 首环约束

- **Rule**: S1-A migration 的 `down_revision` 字段必须等于字符串 `'36e25241e55d'`，严禁任何其他值（尤其禁止 original plan 误写的 `'f7a3b2c1d456'`）。
- **Why**: F001 根因。`36e25241e55d` 是 alembic 真实单 head（E-002 实测），`f7a3b2c1d456` down_revision=None 是早期分支根，绑错会产生多 head 破坏链性。
- **How to apply**: 审查 `alembic/versions/*_s1a_bank_question_extension.py` 文件 head 处 `down_revision` 值；Task 2 测试契约必须包含 `test_migration_chain_down_revision_is_academic_head`。
- **Violation reporter**: Task 3 的 migration smoke test 加 `test_chain_head_after_upgrade_is_s1a_slug`；若 down_revision 绑错，`alembic heads` 会返回 2 行触发 assert 失败。

### ORC-S1A-002: ORM 注册链路完整

- **Rule**: S1-A 不得新增或删除 `alembic/env.py` 和 `src/edu_cloud/api/app.py` 中 bank 相关的 import 语句（E-003 证明已完整）。
- **Why**: F002 根因。original plan 要求新增 `models/__init__.py` 导出纯属误解，bank 注册走的是 env.py+app.py 显式 import，现有实现已完整。盲目新增会导致 double-import 或 re-export 污染。
- **How to apply**: Task 1 只改 `modules/bank/models.py`，禁止动 `alembic/env.py` 和 `api/app.py`；`git diff --name-only` 预期只含这三个位置之一。
- **Violation reporter**: Task 5 Gate 前跑 `git diff --stat alembic/env.py src/edu_cloud/api/app.py` → 期望为空。

### ORC-S1A-003: bank_question 现有字段不动（只加不改）

- **Rule**: 只新增字段，不修改现有字段的类型、nullability、默认值。尤其 `tags`（已是 JSON）和 `bloom_level`（已是 String(20)）保持原样。
- **Why**: "只加不改" 保证 migration 可逆性 + 前向数据零动。改类型/nullability 涉及数据迁移与回滚策略，超 S1-A scope。
- **How to apply**:
  1. Task 1 在 `bank/models.py` 末尾（现有字段之后）追加新字段，禁改现有字段行
  2. Task 2 migration 只用 `op.add_column` 不用 `op.alter_column`
- **Violation reporter**: Task 3 smoke test `test_existing_columns_unchanged_after_upgrade` —— 断言 upgrade 后 `tags.type == JSON` / `bloom_level.type == String(20)`。

### ORC-S1A-004: JSON 字段双方言兼容

- **Rule**: `knowledge_point_ids` 用 `sa.JSON()`（SQLAlchemy generic JSON），而不是 `postgresql.JSONB` 或 `sqlite.JSON`，保证 SQLite 测试 + PostgreSQL 生产双方言都能 upgrade/downgrade。
- **Why**: `migration-gate-repair-design.md` 6 个历史 migration 的教训：单方言 DDL 会导致 SQLite smoke 断裂或 PG 重放异常。
- **How to apply**: Task 2 migration import 只使用 `import sqlalchemy as sa` + `sa.JSON()`；禁止 `from sqlalchemy.dialects import postgresql`。
- **Violation reporter**: Task 3 smoke test 在 SQLite in-memory 上跑 upgrade/downgrade；若用 PG-only DDL 会直接 SQL 语法错误。

---

## Contract Pack

```yaml
contract_pack:
  # 字段命名符合 ~/.claude/config/contract-pack-schema.md 真源
  # verification 枚举: existing_test / pending_test / uncovered
  # R2 F-S1A-04 修正：schema 真源 contract-pack-schema.md:20 规定 test_ref 仅限
  # existing_test；pending_test 不带 test_ref，待验证测试名称写入 statement 尾部
  invariants:
    - id: INV-S1A-001
      statement: "upgrade 后 bank_questions 新增 5 列（source/explanation/knowledge_point_ids/difficulty_level/grade_id），SQLAlchemy inspect 下全部 is_nullable=True（待 Task 3 落地 tests/test_alembic_s1a_bank.py::test_new_columns_added_and_nullable）"
      verification: pending_test
    - id: INV-S1A-002
      statement: "S1-A migration 文件 head 处 down_revision 字符串字面值为 '36e25241e55d'（待 Task 3 落地 tests/test_alembic_s1a_bank.py::test_migration_file_exists_and_down_revision_is_academic_head）"
      verification: pending_test
    - id: INV-S1A-003
      statement: "S1-A upgrade head 后 `alembic heads` subprocess 输出过滤空行后恰好 1 行（待 Task 3 落地 tests/test_alembic_s1a_bank.py::test_migration_chain_head_is_single）"
      verification: pending_test
    - id: INV-S1A-004
      statement: "upgrade 后 bank_questions.tags 仍是 JSON 类型；bank_questions.bloom_level 仍是 VARCHAR(20)（SQLAlchemy type.length == 20）（待 Task 3 落地 tests/test_alembic_s1a_bank.py::test_existing_columns_unchanged_after_upgrade）"
      verification: pending_test
    - id: INV-S1A-005
      statement: "S1-A 出口处 alembic/env.py 和 src/edu_cloud/api/app.py 相对 S1-A plan commit 零改动（ORC-S1A-002 机械化）；验证命令走 Gate G1-S1A-4（Task 4 Step 4.2 `git diff --stat $S1A_BASE..HEAD -- alembic/env.py src/edu_cloud/api/app.py` 返回空）"
      verification: pending_test

  counter_examples:
    - id: CE-S1A-001
      scenario: "Task 2 误绑 down_revision='f7a3b2c1d456'（该节点 down_revision=None 是早期分支根），alembic upgrade head 后 heads 返回 2 行（academic head + 本分支新 head）"
      tests_that_still_pass: "Task 1 的 2 个 ORM 属性 round-trip test（test_bank_question_new_fields_roundtrip / _all_nullable）不读 alembic chain，依然通过"
      mitigation: "Task 3 的 test_migration_file_exists_and_down_revision_is_academic_head 直接字符串匹配 '36e25241e55d'，+ test_migration_chain_head_is_single 跑 alembic heads 断言 1 行，任一都会捕获"
    - id: CE-S1A-002
      scenario: "Task 2 误用 `from sqlalchemy.dialects import postgresql; postgresql.JSONB` 而非 `sa.JSON()`"
      tests_that_still_pass: "纯 ORM 层测试（Task 1 新 2 个 + 现有 bank_service.py 3 个）不跑 migration，依然通过"
      mitigation: "Task 3 smoke 在 SQLite in-memory 跑 upgrade，JSONB 抛 `sqlite3.OperationalError: near \"JSONB\"`；test_new_columns_added_and_nullable 直接失败在 upgrade 阶段"
    - id: CE-S1A-003
      scenario: "Task 1 扩展 model 时'顺手'把 bloom_level 从 String(20) 改成 Enum(...)或 String(10)/String(255)，混入同一 commit"
      tests_that_still_pass: "Task 1 的 ORM 属性 round-trip（只读 Python 实例属性不读 DB 列类型）+ test_bank_service.py 现有 6 个依然通过"
      mitigation: "Task 3 的 test_existing_columns_unchanged_after_upgrade 用 SQLAlchemy inspect 精确断言 `bloom_level.type.length == 20`（不是宽松的 substring 匹配），能立刻捕获类型偏离"

  risk_modules:
    - module: src/edu_cloud/modules/bank/models.py
      reason: "BankQuestion ORM 定义。新增字段可能让现有 bank_service.list_bank_questions 的回包 schema 意外扩宽；Task 1 入口级测试 + 现有 6 个测试回归守卫"
    - module: alembic/versions/{slug}_s1a_bank_question_extension.py
      reason: "Linear chain 首环 migration。down_revision / upgrade / downgrade 任何一处写错会阻塞 S1-B/C/D 后续链；Task 3 强制三阶段 upgrade→downgrade→upgrade 验证"
    - module: alembic/env.py
      reason: "模型注册显式 import 列表（L51 已含 bank）。ORC-S1A-002 禁改；Task 4 Step 4.2 用 git diff 零改动断言守卫"
    - module: src/edu_cloud/api/app.py
      reason: "应用启动模型注册 import 列表（L41 已含 bank）。同 alembic/env.py，ORC-S1A-002 禁改"
    - module: tests/test_alembic_migration.py
      reason: "现有 3 个 migration smoke test（creates_all_expected_tables / head_is_single / downgrade_is_clean）。S1-A 不改此文件但 Gate G1-S1A-5 依赖其回归通过，属于回归风险模块"

  test_debt:
    - item: "bloom_level 字段类型从 String(20) 升级到 SQLAlchemy Enum（design §4.1 原目标）"
      reason: "S1-A ORC-S1A-003 禁改现有字段类型；String→Enum 属行为变更，需独立设计现有数据迁移策略（现有 String 值是否全部命中 Enum 值域），无法塞进 S1-A scope"
      deadline: "2026-05-15"
    - item: "bank_questions.grade_id 字段未加 ForeignKey('grades.id') constraint"
      reason: "grades 表归 S1-C scope，当前仓库不存在该表；S1-A 先加 grade_id Integer nullable 占位，S1-C migration 用 batch_alter_table + create_foreign_key 补齐"
      deadline: "2026-05-08"
    - item: "source / difficulty_level 字段值域应用层或 DB CHECK 约束（design §4.1 期望 Enum 值集）"
      reason: "S1-A 保持 String(20)/String(10) 简单定义；值域校验同 bloom_level 升级一起处理，避免 String→Enum 多次迁移"
      deadline: "2026-05-15"
```

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/edu_cloud/modules/bank/models.py` | 修改 | BankQuestion 尾部追加 5 Mapped 字段（source/explanation/knowledge_point_ids/difficulty_level/grade_id） |
| `alembic/versions/{YYYYMMDD}_s1a_bank_question_extension.py` | 新建 | Linear chain 首环 migration，down_revision=`36e25241e55d`；upgrade add_column ×5，downgrade drop_column ×5 |
| `tests/test_alembic_s1a_bank.py` | 新建 | Migration smoke test（upgrade/downgrade/chain head/existing columns/必填列 INSERT） |
| `tests/test_services_exam/test_bank_service.py` | 修改 | 追加 1-2 个 roundtrip test（新字段写入读取） |
| `tests/test_alembic_migration.py` | 修改（可选） | 现有 test_migration_head_is_single 天然覆盖 INV-S1A-003；无需改动，Task 3 自备独立复查 |
| `alembic/env.py` | **不动** | ORC-S1A-002 禁改 |
| `src/edu_cloud/api/app.py` | **不动** | ORC-S1A-002 禁改 |

---

## Task 1: 扩展 BankQuestion ORM model (5 新字段)

**Files:**
- Modify: `src/edu_cloud/modules/bank/models.py:35` (在 `bloom_level` 之后、`school_id` 之前追加)
- Test: `tests/test_services_exam/test_bank_service.py` (扩展)

**测试契约** (F004):
- **入口**: `BankQuestion(...).source / explanation / knowledge_point_ids / difficulty_level / grade_id` 属性读写（通过 SQLAlchemy ORM 存取）
- **反例**: 若 Task 1 漏加某字段（如 `knowledge_point_ids`），`test_bank_question_new_fields_roundtrip` 会在 `getattr(instance, "knowledge_point_ids")` 抛 `AttributeError`
- **边界**:
  1. 5 字段全部 nullable，`BankQuestion()` 不传新字段也能实例化
  2. `knowledge_point_ids` 接受 `list[int]` 空列表 `[]` 和 None 都合法
  3. `source` 接受字符串值（`"textbook"` / `"exam"` / `"custom"` / `"imported"`，取 design §4 deliverable 1.1 枚举集合），Python 层不做值域校验，由 migration CHECK 约束或应用层校验实施（S1-A 只定义字段）
- **回归**: 影响 `bank_service.list_bank_questions()` 等现有查询（SELECT * 语义）—— 回归验证方法：扩展前后各跑 `pytest tests/test_services_exam/test_bank_service.py -v` 确认现有 6 个 test 全通过
- **命令**:
  ```bash
  .venv/bin/python -m pytest tests/test_services_exam/test_bank_service.py -v --tb=short
  ```
  Expected: 原有 6 test + 新增 3 test = 9 个全 PASS（R2 F-S1A-R2-02 修正：test_bank_service.py 实测已有 6 个 def test_ 函数，非 R1 误写的 3）

**边界条件**（至少 3 条，CLAUDE.md `bug-fix-discipline` 惯例扩展到 plan 层）:
1. 新字段全 nullable → `BankQuestion(school_id=..., question_type="choice", max_score=5)` 不传新字段也能创建
2. `knowledge_point_ids` JSON 字段接受 `[]` 和 `None`（不是只接受非空列表）
3. `grade_id` Integer nullable，**不加 FK constraint**（grades 表属 S1-C）

- [ ] **Step 1.1: 先写失败 round-trip test**

Edit `tests/test_services_exam/test_bank_service.py`，在文件末尾追加：

```python
import pytest
from edu_cloud.modules.bank.models import BankQuestion
from edu_cloud.models.school import School


@pytest.mark.asyncio
async def test_bank_question_new_fields_roundtrip(db):
    """S1-A: 5 新字段写入 + 读回完整性验证"""
    school = School(name="测试", code="BS_S1A_01")
    db.add(school)
    await db.flush()

    q = BankQuestion(
        school_id=school.id,
        question_type="essay",
        max_score=10.0,
        sample_count=0,
        source="exam",
        explanation="勾股定理应用题",
        knowledge_point_ids=[101, 102, 103],
        difficulty_level="hard",
        grade_id=9,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    assert q.source == "exam"
    assert q.explanation == "勾股定理应用题"
    assert q.knowledge_point_ids == [101, 102, 103]
    assert q.difficulty_level == "hard"
    assert q.grade_id == 9


@pytest.mark.asyncio
async def test_bank_question_new_fields_all_nullable(db):
    """S1-A: 5 新字段全部可以为 None（不传参数）"""
    school = School(name="测试", code="BS_S1A_02")
    db.add(school)
    await db.flush()

    q = BankQuestion(
        school_id=school.id,
        question_type="choice",
        max_score=5.0,
        sample_count=0,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)

    assert q.source is None
    assert q.explanation is None
    assert q.knowledge_point_ids is None
    assert q.difficulty_level is None
    assert q.grade_id is None


@pytest.mark.asyncio
async def test_bank_question_new_fields_visible_via_service(db):
    """S1-A 入口级验证（R1 F-S1A-02 修正）：经 bank_service.get_bank_question 读回，
    验证新字段在 service 层序列化完整，不只是 ORM 属性可达。

    走 service 的理由：防止 Task 1 改完 ORM 但 bank_service 的 SELECT 列投影
    /Pydantic response model 漏了新字段这种"ORM 层绿但 service 层断"的隐患。
    """
    from edu_cloud.modules.bank import service as bank_service

    school = School(name="测试", code="BS_S1A_03")
    db.add(school)
    await db.flush()

    q = BankQuestion(
        school_id=school.id,
        question_type="essay",
        max_score=10.0,
        sample_count=0,
        source="textbook",
        explanation="教材例题 2-3",
        knowledge_point_ids=[201, 202],
        difficulty_level="medium",
        grade_id=7,
    )
    db.add(q)
    await db.commit()
    qid = q.id

    # 经 service 层读回（不是直接 SQLAlchemy query）
    # R2 F-S1A-R2-01 修正：keyword 参数是 bank_question_id（见 src/edu_cloud/modules/bank/service.py:13），
    # 不是 question_id
    retrieved = await bank_service.get_bank_question(db, bank_question_id=qid, school_id=school.id)
    assert retrieved is not None, "service 层找不到刚写入的 BankQuestion"
    assert retrieved.id == qid
    # 新字段都能从 service 层读出（若 service 的 select_from 缺列或 response model 漏字段 → 任一 AttributeError/None 捕获）
    assert retrieved.source == "textbook"
    assert retrieved.explanation == "教材例题 2-3"
    assert retrieved.knowledge_point_ids == [201, 202]
    assert retrieved.difficulty_level == "medium"
    assert retrieved.grade_id == 7
```

- [ ] **Step 1.2: 跑新测试确认 FAIL**

```bash
.venv/bin/python -m pytest tests/test_services_exam/test_bank_service.py::test_bank_question_new_fields_roundtrip tests/test_services_exam/test_bank_service.py::test_bank_question_new_fields_all_nullable tests/test_services_exam/test_bank_service.py::test_bank_question_new_fields_visible_via_service -v --tb=short
```
Expected: 3 个 test FAIL（R1 F-S1A-02 修正：增加入口级 service 测试），错误信息类似 `AttributeError: 'BankQuestion' object has no attribute 'source'` 或 SQLAlchemy `CompileError` 列不存在。

- [ ] **Step 1.3: 最小实现 — 扩展 BankQuestion ORM**

Edit `src/edu_cloud/modules/bank/models.py`，在 `bloom_level` 字段之后、`school_id` 字段之前（约 L34-35 位置）追加：

```python
    # ── S1-A 扩展 (2026-04-24): design §4.1 deliverable 1.1 ──
    # refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1
    # ORC-S1A-003: 只加不改，新字段全 nullable
    source: Mapped[str | None] = mapped_column(String(20), default=None)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    knowledge_point_ids: Mapped[list | None] = mapped_column(JSON, default=None)
    difficulty_level: Mapped[str | None] = mapped_column(String(10), default=None)
    grade_id: Mapped[int | None] = mapped_column(Integer, default=None)
```

**注意**：`grade_id` 用 `Integer` 且**不加** `ForeignKey("grades.id")` —— grades 表归 S1-C scope，FK constraint 由 S1-C migration 补（见 TD-S1A-002）。

- [ ] **Step 1.4: 跑测试确认 PASS（内存测试）**

```bash
.venv/bin/python -m pytest tests/test_services_exam/test_bank_service.py -v --tb=short
```
Expected: 原有 6 test + 新增 3 test 共 9 个全 PASS（R2 F-S1A-R2-02 修正；这一步不跑 migration，依赖 conftest.py SQLite in-memory + Base.metadata.create_all）。

- [ ] **Step 1.5: ORC-S1A-002 断言 — 未动 env.py / app.py**

```bash
git diff --stat alembic/env.py src/edu_cloud/api/app.py
```
Expected: 无输出（两个文件未修改）。若有输出 → Task 1 违反 ORC-S1A-002，必须回退。

- [ ] **Step 1.6: Commit Task 1**

```bash
git add src/edu_cloud/modules/bank/models.py tests/test_services_exam/test_bank_service.py
git commit -m "$(cat <<'EOF'
feat(bank): S1-A T1 扩展 BankQuestion 5 个学情闭环字段

为 S1-A 子 topic 首 Task。Parent design §4.1 deliverable 1.1。
新增字段: source / explanation / knowledge_point_ids / difficulty_level / grade_id，
全 nullable（ORC-S1A-003 只加不改）；grade_id 无 FK constraint，
grades 表 + FK 归 S1-C（TD-S1A-002）。
新增 3 个测试: 2 个 ORM roundtrip（属性层）+ 1 个入口级 service 测试
（经 bank_service.get_bank_question，R1 F-S1A-02 修正）。

refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 1
EOF
)"
```

---

## Task 2: Linear chain migration (首环，down_revision=36e25241e55d)

**Files:**
- Create: `alembic/versions/{YYYYMMDD_HHMM}_s1a_bank_question_extension.py`（用 `alembic revision -m` 生成，文件名 slug 由 alembic 自动拼接）

**测试契约** (F004):
- **入口**: `alembic upgrade head` 和 `alembic downgrade -1`（CLI）；migration 本身是 `upgrade()` / `downgrade()` 函数
- **反例**: 若 down_revision 绑错（如 `'f7a3b2c1d456'`），`alembic heads` 会返回 2 行（ORC-S1A-001 被 Task 3 `test_migration_chain_head_is_single` 抓获）；若 JSON 字段用 `postgresql.JSONB`，SQLite 会报 `near "JSONB"` 语法错误
- **边界**:
  1. `sample_count` 等原有 NOT NULL 字段不受影响，upgrade 后 INSERT 带齐必填列仍成功（F003 修正）
  2. downgrade 后 5 新列消失，剩余列完全回到 upgrade 前状态
  3. 重复运行 `alembic upgrade head` 幂等（alembic 天然幂等）
- **回归**: migration chain 不可破坏——加入本条后 `alembic heads` 必须返回 1 行（回归由 Task 3 `test_migration_chain_head_is_single` 覆盖）
- **命令**:
  ```bash
  .venv/bin/alembic upgrade head && .venv/bin/alembic heads
  .venv/bin/alembic downgrade -1 && .venv/bin/alembic heads
  ```
  Expected: upgrade 后 head 是本 migration slug；downgrade 后 head 回到 `36e25241e55d`。

**边界条件**（至少 3 条）:
1. SQLite in-memory 上 upgrade/downgrade 能闭环（ORC-S1A-004 双方言依据）
2. PostgreSQL 上 DDL 语法合法（通过 `sa.JSON()` 保证）
3. downgrade 不涉及数据重建（5 列全 nullable，drop_column 不需 default backfill）

- [ ] **Step 2.1: 生成 migration 骨架**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/alembic revision -m "s1a_bank_question_extension"
```
Expected: 输出类似 `Generating /home/ops/projects/edu-cloud/alembic/versions/{NEW_SLUG}_s1a_bank_question_extension.py ... done`。
**立刻记录** `{NEW_SLUG}` 值（12 位十六进制），后续 Task 3 要引用。

- [ ] **Step 2.2: 验证并修正 down_revision（ORC-S1A-001 核心）**

打开刚生成的文件，查找 `down_revision` 行。Alembic 默认会自动填前一个 head：应该是 `'36e25241e55d'`。

**手动断言**：
```bash
grep -n "down_revision" alembic/versions/*s1a_bank_question_extension.py
```
Expected: 必须显示 `down_revision: Union[str, Sequence[str], None] = '36e25241e55d'`

**若不是 '36e25241e55d'** → 手动修正为此值（不允许任何其他值，ORC-S1A-001 硬约束）。

- [ ] **Step 2.3: 实现 upgrade() / downgrade() body**

覆盖 migration 文件的 `upgrade()` 和 `downgrade()` 函数：

```python
def upgrade() -> None:
    """S1-A: bank_questions 扩展 5 字段（source / explanation / knowledge_point_ids / difficulty_level / grade_id）。

    refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 2
    refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.1
    ORC-S1A-003: 只加不改；ORC-S1A-004: sa.JSON() 双方言兼容
    """
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('explanation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('knowledge_point_ids', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('difficulty_level', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('grade_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """S1-A downgrade: 移除 5 新字段。无数据保留（5 列全 nullable 无默认值）。"""
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.drop_column('grade_id')
        batch_op.drop_column('difficulty_level')
        batch_op.drop_column('knowledge_point_ids')
        batch_op.drop_column('explanation')
        batch_op.drop_column('source')
```

**关键要点**：
- `batch_alter_table` 包装是 SQLite 兼容的强制要求（ORC-S1A-004 + `2026-04-13-migration-gate-repair-design.md` 教训）
- `sa.JSON()` 不是 `postgresql.JSONB`（ORC-S1A-004）
- downgrade 顺序与 upgrade 相反（LIFO，减少 FK 依赖假如未来加 FK）
- **禁止** `import from sqlalchemy.dialects`

- [ ] **Step 2.4: 本地 smoke — upgrade → downgrade → upgrade 三阶段**

```bash
# stamp 到 head 的前一个（确保从新 migration 前开始）
.venv/bin/alembic stamp 36e25241e55d

# 1) upgrade：跑到新 head
.venv/bin/alembic upgrade head
.venv/bin/alembic heads  # 期望输出新 slug

# 2) downgrade：回到 36e25241e55d
.venv/bin/alembic downgrade -1
.venv/bin/alembic heads  # 期望输出 36e25241e55d

# 3) upgrade：再跑到新 head 验证幂等
.venv/bin/alembic upgrade head
.venv/bin/alembic heads  # 期望再次输出新 slug
```
Expected: 三阶段全部成功，`alembic heads` 在 (1)(3) 返回新 slug，在 (2) 返回 `36e25241e55d`，且全程无 error。

- [ ] **Step 2.5: Commit Task 2**

```bash
git add alembic/versions/*s1a_bank_question_extension.py
git commit -m "$(cat <<'EOF'
feat(alembic): S1-A T2 linear chain 首环 migration (bank_question +5 字段)

down_revision=36e25241e55d（alembic heads 实测单 head，ORC-S1A-001）。
upgrade() 在 bank_questions 上 batch_alter_table add_column ×5：
source / explanation / knowledge_point_ids / difficulty_level / grade_id。
downgrade() 反向 drop_column ×5（5 列全 nullable，无数据迁移需求）。
使用 sa.JSON() 而非 postgresql.JSONB（ORC-S1A-004 双方言兼容）。

refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 2
EOF
)"
```

---

## Task 3: Migration smoke test（新文件 tests/test_alembic_s1a_bank.py）

**Files:**
- Create: `tests/test_alembic_s1a_bank.py`

**测试契约** (F004):
- **入口**: pytest 收集并运行 `tests/test_alembic_s1a_bank.py` 中全部 test
- **反例**:
  - 若 Task 2 误绑 down_revision='f7a3b2c1d456' → `test_migration_chain_head_is_single` FAIL（heads 返回 2 行）
  - 若 Task 2 用 `postgresql.JSONB` → `test_upgrade_succeeds_on_sqlite` FAIL（SQLite 解析错误）
  - 若 Task 3 INSERT 忘传 `sample_count` → `test_existing_data_preserved_through_migration` FAIL（NOT NULL violation，F003 修正锚点）
- **边界**:
  1. 空 DB 上 upgrade head 从头跑通（覆盖所有前序 migration + S1-A）
  2. 预置测试数据 → upgrade → 数据保留 + 新列为 NULL（INV-S1A-001）
  3. upgrade → downgrade → upgrade 三阶段闭环（migration 可逆性）
- **回归**: 本测试文件独立存在，不触碰 `tests/test_alembic_migration.py` 既有 3 test；回归方式 → S1-A commit 后跑 `pytest tests/test_alembic_migration.py tests/test_alembic_s1a_bank.py -v` 两个文件都全绿
- **命令**:
  ```bash
  .venv/bin/python -m pytest tests/test_alembic_s1a_bank.py -v --tb=short
  ```
  Expected: 全部 5 个 test PASS

**边界条件**（至少 3 条）:
1. 覆盖 SQLite in-memory（ORC-S1A-004 的 CI 侧证据）
2. INSERT 必填列完整（`school_id/id/question_type/max_score/sample_count/created_at/updated_at` —— F003 修正）
3. 现有 `tags` / `bloom_level` 列类型不受影响（ORC-S1A-003 机械化）

- [ ] **Step 3.1: 新建 tests/test_alembic_s1a_bank.py**

Create `tests/test_alembic_s1a_bank.py`:

```python
"""S1-A bank_question extension migration smoke tests.

覆盖 ORC-S1A-001（linear chain 首环）/ ORC-S1A-003（只加不改）/ ORC-S1A-004（双方言）。
refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 3
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _alembic_env(db_url: str) -> dict:
    env = os.environ.copy()
    env['DATABASE_URL'] = db_url
    return env


@pytest.fixture()
def sqlite_db(tmp_path):
    """Per-test SQLite file DB（需要文件路径以便 alembic subprocess 访问）."""
    db_file = tmp_path / 's1a_bank.db'
    yield f'sqlite:///{db_file}'


def _run_alembic(cmd_args: list[str], db_url: str) -> subprocess.CompletedProcess:
    """运行 alembic CLI（用 sync URL 简化）."""
    return subprocess.run(
        [sys.executable, '-m', 'alembic', *cmd_args],
        cwd=PROJECT_ROOT,
        env={**os.environ, 'DATABASE_URL': db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')},
        capture_output=True,
        text=True,
    )


def test_migration_file_exists_and_down_revision_is_academic_head():
    """INV-S1A-002 机械化：打开 S1-A migration 文件，直接读 down_revision 字符串."""
    versions_dir = os.path.join(PROJECT_ROOT, 'alembic', 'versions')
    matches = [f for f in os.listdir(versions_dir) if 's1a_bank_question_extension' in f]
    assert len(matches) == 1, f"Expected exactly 1 S1-A migration file, got {matches}"

    with open(os.path.join(versions_dir, matches[0])) as fp:
        content = fp.read()
    assert "down_revision: Union[str, Sequence[str], None] = '36e25241e55d'" in content, \
        "ORC-S1A-001 违反：down_revision 必须是 '36e25241e55d'"


def test_migration_chain_head_is_single(sqlite_db):
    """INV-S1A-003 机械化：upgrade 到 head 后 alembic heads 仍返回 1 行."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade failed: {r.stderr}"

    r = _run_alembic(['heads'], sqlite_db)
    assert r.returncode == 0
    # heads 输出形如 "{slug} (head)\n"；过滤空行后应只有 1 行
    non_empty_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(non_empty_lines) == 1, f"Expected 1 head, got {len(non_empty_lines)}: {r.stdout}"


def test_new_columns_added_and_nullable(sqlite_db):
    """INV-S1A-001 机械化：upgrade 后 5 新列存在且 is_nullable=True."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('bank_questions')}

    for name in ('source', 'explanation', 'knowledge_point_ids', 'difficulty_level', 'grade_id'):
        assert name in cols, f"Missing new column: {name}"
        assert cols[name]['nullable'] is True, f"Column {name} must be nullable"


def test_existing_columns_unchanged_after_upgrade(sqlite_db):
    """ORC-S1A-003 机械化：tags 仍是 JSON 类型，bloom_level 仍是精确 VARCHAR(20)。

    R1 F-S1A-03 修正：bloom_level 断言从宽松 substring 匹配改为精确 length==20，
    错误的 VARCHAR(10)/VARCHAR(255) 不再漏过。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('bank_questions')}

    assert 'tags' in cols, "tags 列被移除"
    assert 'bloom_level' in cols, "bloom_level 列被移除"

    # tags: SQLAlchemy inspect 对 SQLite 下 JSON 列返回 JSON type 或 TEXT 基类；
    # 取 .__class__.__name__ 做稳定断言
    tags_type_name = cols['tags']['type'].__class__.__name__.upper()
    assert 'JSON' in tags_type_name, \
        f"tags type changed from JSON to {cols['tags']['type']!r}"

    # bloom_level: 精确锁定 VARCHAR(20) —— 读 SQLAlchemy Type 的 .length 属性
    # initial_merged_schema.py:514 是 Column('bloom_level', String(length=20)...)
    bloom_type = cols['bloom_level']['type']
    bloom_length = getattr(bloom_type, 'length', None)
    assert bloom_length == 20, \
        f"bloom_level type.length changed: expected 20, got {bloom_length!r} (full type={bloom_type!r})"
    # 类型类名也要是 String/VARCHAR 家族（不是 Enum/Integer/其他）
    bloom_class = bloom_type.__class__.__name__.upper()
    assert 'STRING' in bloom_class or 'VARCHAR' in bloom_class, \
        f"bloom_level type class changed: expected String/VARCHAR, got {bloom_class!r}"


def test_existing_data_preserved_through_migration(sqlite_db):
    """F003 修正核心：INSERT 带齐必填列 → upgrade → 数据保留 + 新列默认 NULL."""
    # 1) upgrade 到 head 之前一个 revision（academic 表引入点 36e25241e55d）
    #    注：S1-A 前 head 是 36e25241e55d，所以先 upgrade 到 head 之前的一环
    r = _run_alembic(['upgrade', '36e25241e55d'], sqlite_db)
    assert r.returncode == 0, f"upgrade to 36e25241e55d failed: {r.stderr}"

    # 2) 预置数据（F003：INSERT 必填列全齐）
    engine = create_engine(sqlite_db)
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO bank_questions (
                id, school_id, question_type, max_score, sample_count,
                tags, bloom_level, created_at, updated_at
            ) VALUES (
                :id, :school_id, :qtype, :mscore, :scount,
                :tags, :bloom, :created, :updated
            )
        """), {
            'id': str(uuid.uuid4()),
            'school_id': 'test-school-uuid',
            'qtype': 'essay',
            'mscore': 10.0,
            'scount': 0,
            'tags': '[]',
            'bloom': 'apply',
            'created': datetime.now(timezone.utc).isoformat(),
            'updated': datetime.now(timezone.utc).isoformat(),
        })

    # 3) upgrade 到 S1-A new head
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade to S1-A head failed: {r.stderr}"

    # 4) 验证数据保留 + 5 新列 NULL
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT question_type, max_score, sample_count, tags, bloom_level,
                   source, explanation, knowledge_point_ids, difficulty_level, grade_id
            FROM bank_questions LIMIT 1
        """)).fetchone()

    assert row is not None, "预置数据丢失"
    assert row.question_type == 'essay'
    assert row.max_score == 10.0
    assert row.sample_count == 0
    assert row.source is None
    assert row.explanation is None
    assert row.knowledge_point_ids is None
    assert row.difficulty_level is None
    assert row.grade_id is None


def test_upgrade_then_downgrade_is_clean(sqlite_db):
    """INV-S1A-003 配对：downgrade 后 5 新列消失且不破坏现有列."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    r = _run_alembic(['downgrade', '-1'], sqlite_db)
    assert r.returncode == 0, f"downgrade failed: {r.stderr}"

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name'] for c in insp.get_columns('bank_questions')}

    for removed in ('source', 'explanation', 'knowledge_point_ids', 'difficulty_level', 'grade_id'):
        assert removed not in cols, f"Column {removed} still present after downgrade"
    # 原字段仍在
    for kept in ('tags', 'bloom_level', 'sample_count', 'school_id'):
        assert kept in cols, f"Existing column {kept} missing after downgrade"
```

- [ ] **Step 3.2: 跑新测试并全绿**

```bash
.venv/bin/python -m pytest tests/test_alembic_s1a_bank.py -v --tb=short
```
Expected: 6 个 test 全 PASS。

- [ ] **Step 3.3: 回归 — 既有 alembic smoke 不受影响**

```bash
.venv/bin/python -m pytest tests/test_alembic_migration.py -v --tb=short
```
Expected: 原有 3 个 test 全 PASS，S1-A 不破坏既有 smoke 套件。

- [ ] **Step 3.4: Commit Task 3**

```bash
git add tests/test_alembic_s1a_bank.py
git commit -m "$(cat <<'EOF'
test(alembic): S1-A T3 migration smoke (6 tests)

覆盖 ORC-S1A-001 (linear chain 首环 down_revision=36e25241e55d) /
INV-S1A-001 (5 新列 nullable) / ORC-S1A-003 (tags/bloom_level 不动) /
F003 修正 (INSERT 必填列含 sample_count/created_at/updated_at)。
tests/test_alembic_s1a_bank.py 独立于既有 test_alembic_migration.py，
便于子 topic 拆分与 cherry-pick。

refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 3
EOF
)"
```

---

## Task 4: Gate G1-S1A 通过声明 + 跨子 topic handoff 占位

**Files:**
- Create: `docs/plans/2026-04-24-haofenshu-s1-bank-gates.json`（codex-review plan 会自动生成，此 Task 只占位 handoff）
- Create (on completion): `docs/plans/2026-04-24-haofenshu-s1-bank-handoff.md`（S1-A 完成后写，交棒 S1-C 会话）

**测试契约** (F004):
- **入口**: 跑全量 pytest + 验证 S1-A commit 范围
- **反例**: 若 Task 1/2/3 任一步引入回归（既有 test FAIL），Gate G1-S1A 不通过
- **边界**: 全量 pytest baseline = 基线 baseline_count + 9 新 test（Task 1 的 2 个 ORM round-trip + 1 个入口级 service（R1 F-S1A-02 修正）+ Task 3 的 6 个 migration smoke）；若 new count < baseline_count + 9 → 缺测，Gate 不通过
- **回归**: 对比 baseline —— 跑 pytest 验证 passed 数 = baseline_count + 9
- **命令**:
  ```bash
  .venv/bin/python -m pytest --tb=no -q 2>&1 | tail -3
  ```
  Expected (相对 baseline 2064 passed / 22 failed / 1 error / 23 skipped @ 2026-04-24T11:04:27):
  - `passed` 数 >= 2064 + 9 = **2073**（9 = Task 1 新增 2 ORM roundtrip + 1 入口级 service 测试（R1 F-S1A-02 修正） + Task 3 新增 6 migration smoke）
  - `failed` 数 <= 22（S1-A 禁止引入新 failure；原有失败可减少但不得增加）
  - `error` 数 <= 1（同上）
  - `skipped` 数 == 23（S1-A 未 skip 任何测试）

**边界条件**（至少 3 条）:
1. Gate G1-S1A 不要求 mcu.asia 生产库 migration（生产 deploy 归独立 release Task，不在 S1-A scope）
2. Gate 不要求 PostgreSQL 本地跑（SQLite smoke 已覆盖 ORC-S1A-004 双方言中的 SQLite 侧，PG 侧靠 `sa.JSON()` 保证语法合法性；PG 实跑归 staging release）
3. S1-C 开始前需读 handoff.md（Step 4.3 提供内容）

- [ ] **Step 4.1: 跑全量 pytest 确认无回归**

```bash
.venv/bin/python -m pytest --tb=no -q 2>&1 | tail -5
```
Expected（相对 baseline 2064/22/1/23）:
- passed >= 2073（2064 baseline + 9 新增：Task 1 的 2 ORM round-trip + 1 入口级 service + Task 3 的 6 migration smoke）
- failed <= 22（既有技术债不增，详见 §Deferred 第 7 条）
- error <= 1
- skipped == 23

若 passed < 2073 或 failed > 22 或 error > 1 → Gate 不通过，回退调查是否 Task 1/2/3 引入回归。
若 failed < 22（原失败变通过）→ 为有益副作用，不阻塞 Gate，但须在 handoff.md 自由备注段标注"S1-A 期间观察到原失败 N → N' 减少"以便追溯。

- [ ] **Step 4.2: 断言 git diff 范围（ORC-S1A-002 最终验证）**

ORC-S1A-002 的机械守卫用真实 Git 边界，**不用 Alembic revision 充当 Git commit**（R1 F-S1A-01 修正）。S1-A 实施起点 = 最近一次修改本 plan 的 commit（即 R2 修复后的 plan commit）。

```bash
# 取 S1-A plan 的最新 commit SHA（R1/R2 修复合入后 HEAD 指向此点即 S1-A 起点）
S1A_BASE=$(git log -1 --format=%H -- docs/plans/2026-04-24-haofenshu-s1-bank-plan.md)
echo "S1-A base commit: $S1A_BASE"

# 列出 S1-A 期间的 commit（诊断用）
git log --oneline "$S1A_BASE..HEAD" | head -10

# 机械验证：env.py + app.py 零改动
git diff --stat "$S1A_BASE..HEAD" -- alembic/env.py src/edu_cloud/api/app.py
```
Expected: 第三条命令无输出（env.py / app.py 在 S1-A 期间未改）。若有输出 → ORC-S1A-002 违反，Task 1/2/3 任一步骤动了这两个文件，必须回退定位。

- [ ] **Step 4.3: 写 S1-A 交接 handoff 占位（≤15 行硬限）**

Create `docs/plans/2026-04-24-haofenshu-s1-bank-handoff.md`（R1 F-S1A-06 修正：压缩到 ≤15 行硬限，保留 handoff_format_guard 两段式 marker）：

```markdown
# haofenshu-s1-bank Handoff (S1-A → S1-C)
=== 生成块开始 ===
**task_id**: haofenshu-phase2-s1-a-bank; **topic**: haofenshu-s1-bank; **tier**: T3
**gate_status**: plan_review=pass / code_review=pass / G1_S1A=pass
**last_verified_evidence**: `pytest --tb=no -q` @{ts} → {N} passed / 基线 +9
**subject_hash**: {plan_hash}; **raw_output_hashes**: {r2_hash}
**timestamp**: {iso8601}+08:00; **last_commit**: {s1a_last_sha}
=== 生成块结束 ===
=== 自由备注开始 ===
- S1-A merge @ feat/analytics-report；migration slug={NEW_SLUG}，链首 down_revision=36e25241e55d
- S1-C scope：grades + Class.grade_id FK + teaching_plans + PaperAccessLevel + 补 bank_questions.grade_id FK (TD-S1A-002)；S1-C migration down_revision={S1A_NEW_SLUG}（linear chain 第 2 环）
- 禁重犯：F001 down_revision 实测 / F002 ORM 注册现完整 / F003 smoke INSERT 必填列 / F004-5 测试契约+Contract Pack 必备
=== 自由备注结束 ===
```

**行数校验**：上述模板连同生成块/自由备注 marker 共 **14 行**（空行/代码围栏不计），满足 G1-S1A-6 ≤15 行约束。执行者填参数时不要插入新行。

- [ ] **Step 4.4: Commit Task 4 + Gate G1-S1A 标记**

```bash
git add docs/plans/2026-04-24-haofenshu-s1-bank-handoff.md
git commit -m "$(cat <<'EOF'
docs(handoff): S1-A T4 Gate G1-S1A 通过 + 交棒 S1-C

全量 pytest baseline+9 全绿；alembic/env.py + api/app.py 未动（ORC-S1A-002，用 Git commit SHA 机械验证）。
S1-A migration 文件 slug={NEW_SLUG}，链首 down_revision=36e25241e55d。
S1-C 下一步：grades + Class.grade_id + teaching_plans + PaperAccessLevel + bank.grade_id FK 补齐（TD-S1A-002）。

refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 4
EOF
)"
```

---

## Gate G1-S1A 验收条件（S1-A 子 topic 出口）

**必备条件全通过才视为 Gate G1-S1A 通过**：

| ID | 条件 | 验证命令 | 通过判据 |
|----|------|---------|----------|
| G1-S1A-1 | Task 1 ORM + 入口级测试 PASS | `pytest tests/test_services_exam/test_bank_service.py -v` | 原 6 + 新 3 = 9 PASS（R2 F-S1A-R2-02 修正） |
| G1-S1A-2 | Task 3 Migration smoke PASS | `pytest tests/test_alembic_s1a_bank.py -v` | 6 test PASS |
| G1-S1A-3 | Migration chain 可逆 | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` | 三阶段全 exit 0 |
| G1-S1A-4 | ORC-S1A-002 零改动 | `S1A_BASE=$(git log -1 --format=%H -- docs/plans/2026-04-24-haofenshu-s1-bank-plan.md) && git diff --stat "$S1A_BASE..HEAD" -- alembic/env.py src/edu_cloud/api/app.py` | 无输出（R1 F-S1A-01 修正：用 Git commit SHA 而非 Alembic revision） |
| G1-S1A-5 | 全量 pytest 无回归 | `pytest --tb=no -q` | passed >= 2073 且 failed <= 22 且 error <= 1 且 skipped == 23（详见 Step 4.1） |
| G1-S1A-6 | handoff.md ≤15 行 | `wc -l docs/plans/2026-04-24-haofenshu-s1-bank-handoff.md` | ≤ 15 |
| G1-S1A-7 | codex-review plan R1 PASS | 外部工具 | R1/R2 PASS（不允许 R3+） |
| G1-S1A-8 | codex-review code R1 PASS | 外部工具 | R1/R2 PASS（不允许 R3+） |

G1-S1A-1~6 由 Executor 自检；G1-S1A-7/8 由 codex-review 独立审查。

---

## Deferred / Design Concerns

以下事项在 S1-A 范围外，但与 design §4 deliverable 1.1 原初 7 字段清单相关，必须落到其他子 topic 或独立 patch：

1. **bloom_level 升级 String(20) → Enum（TD-S1A-001）**
   - 现状：bank_question.bloom_level 已是 `String(20)`（E-001 证据），存储枚举值靠应用层约束
   - design 原意：SQLAlchemy Enum 类型 + DB CHECK constraint
   - 冲突：从 String 改为 Enum 属"改字段类型"，违反 ORC-S1A-003 "只加不改"
   - 处置建议：S1-D 阶段评估是否有现有数据需迁移；若无 → 独立 T2 migration patch；若有 → 需 design 侧补"现有数据迁移策略"章节
   - 责任归属：S1-D 会话或独立 patch session

2. **grade_id FK constraint 补齐（TD-S1A-002）**
   - 现状：S1-A T1/T2 加 `grade_id Integer nullable`，无 FK
   - S1-C 任务：`grades` 表新建后补 `ForeignKey("grades.id")` constraint，走 `batch_alter_table` + `create_foreign_key`
   - S1-C plan 必须包含此步骤（在其 Contract Pack risk_modules 中锚定 `src/edu_cloud/modules/bank/models.py`）

3. **tags 字段已存在**
   - 现状：bank_question.tags 已是 `JSON` nullable（E-001 证据）
   - design §4 deliverable 1.1 列 `tags: JSON`
   - 实际情况：字段完全符合 design，S1-A 无操作
   - 结论：S1-A 不动 tags，design §4 1.1 字段清单 post-S1-A 减为 5 字段有效新增

4. **source Enum 值域校验**
   - 现状：S1-A T1 将 source 定义为 `String(20)`，应用层期待值域 `{textbook, exam, custom, imported}`（design §4 1.1）
   - deferred：DB 层 CHECK constraint 或 SQLAlchemy Enum 升级 → 归并到 TD-S1A-001 一起评估（避免 String→Enum 多次迁移）

5. **difficulty_level 同上**
   - 现状：`String(10)`，应用层期待 `{easy, medium, hard}`
   - deferred：同 source 一起评估（TD-S1A-001 扩展）

6. **mcu.asia 生产库 deploy**
   - S1-A Gate 不含生产库 upgrade；生产 deploy 归独立 release Task（按 edu-cloud 部署拓扑 `docs/plans/2026-03-30-version-mgmt-consensus.md`）
   - 备份要求（CLAUDE.md L016）：部署前 `sqlite3 ".backup"`（若 mcu.asia 用 SQLite）或 PG dump

7. **既有 22 failed + 1 error 测试债**（L015 反虚假完成）
   - 实测：`.venv/bin/python -m pytest --tb=no -q` @ 2026-04-24T11:04:27 → `2064 passed, 22 failed, 1 error, 23 skipped in 831.70s`
   - 已知失败样例（来自 baseline tail）：
     - `tests/test_workers/test_grading_worker.py::test_run_post_exam_pipeline_stub` FAILED
     - `tests/test_alembic_migration.py::test_migration_creates_all_expected_tables` ERROR
   - 完整 22 failed + 1 error 清单未在本 plan 枚举（非 S1-A scope，避免 scope creep）
   - **归属**：这是 pre-S1-A 既有技术债，S1-A 未动任何代码即能复现。若 22 failed 构成 L019 打地鼠模式（同模块 ≥3 次连续 fix 失败），应独立 T3 设计；若是独立零散问题，可分批清理
   - **S1-A 立场**：诚实披露，不掩盖，Gate G1-S1A-5 只要求"不增加 failure 数"而非"baseline 全绿"
   - **建议后续行动**：S1-A 合入后独立启动 `t3-test-debt-audit` 调研 session，产出 failure 清单按模块归类 + 修复路线图
   - 14 分钟的 pytest 长耗时也是独立优化课题（ECS 上应考虑 `pytest -x` 或模块级跑法的默认化）

---

## 执行 Handoff 选择

**Plan complete and saved to `docs/plans/2026-04-24-haofenshu-s1-bank-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 每个 Task 派一个新 subagent 独立实现 + 两阶段 review

**2. Inline Execution** — 在新 session 用 superpowers:executing-plans 按 batch + checkpoint 推进

**注意**：CLAUDE.md `session_guard` 硬拦同会话 writing-plans + executing-plans，两个选项都必须在**新会话**执行。当前会话到此停手，commit plan → 触发 codex-review plan R1。
