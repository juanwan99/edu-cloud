# Migration Gate 恢复 — 独立修复设计（F001 R1 处置）

> 创建: 2026-04-13 10:51:02
> 归属: `2026-04-12-haofenshu-phase1` Batch 1 Code Review R1 F001 的独立修复
> 状态: 设计完成，待用户批准
> 触发规则: review-templates.md — risk_modules finding 要求 "independent fix design + Semantic Regression Gate"
> 禁止的修复模式（来自 F001 repair_hypothesis）：
> - ❌ `pytest --deselect tests/test_alembic_migration.py`（继续跳过）
> - ❌ 把 INV-04 事后降格为"已知债务"
> - ❌ 在 handoff 中把 migration smoke 标记 skipped

---

## §0 本次修复不做什么（non-goals，锚定边界）

- **不**新增业务表 / 不改业务模型字段（纯方言兼容修复）
- **不**修改 `52af1c37bf14_add_menu_and_analysis_tables.py`（本批次新增 migration 本身 OK）
- **不**改动 `alembic/env.py`（当前 env.py 已正确）
- **不**改动 `tests/test_alembic_migration.py` 的断言（保持 gate 强度，不降格）
- **不**改动 entity_memory / project_state / questions 三张表的业务字段、索引、唯一约束语义
- **不**引入新的数据库方言开关（单一真源：migration 本身跨方言可执行）

## §1 背景与根因

### 1.1 F001 审查结论（从 codex-code-review-batch1-raw.log 摘取）

> Before-behavior: 这个 batch 改了 `alembic/versions/`，但 migration 的 upgrade/downgrade 路径没有通过任何有效 gate；handoff 直接把该项标成 `skipped`，全量回归还显式排除了 migration smoke。
> After-behavior: 触及 schema 的批次在通过审查前，必须有可执行且通过的 migration 升级/回滚验证。
> Impact: INV-03/INV-04 没有被满足，`alembic/versions/` 这个 risk module 仍处于未验证状态。

### 1.2 实测复现（2026-04-13 10:49）

```
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_alembic_migration.py -q
```

结果：`1 failed, 1 passed, 1 error`。错误位于 `test_migration_creates_all_expected_tables` 的 fixture `migration_db`：

```
File "alembic/versions/1a325e38e941_add_entity_memory_and_project_state_.py", line 40
    op.create_unique_constraint(
...
File "alembic/ddl/sqlite.py", line 81, in add_constraint
    raise NotImplementedError(
NotImplementedError: No support for ALTER of constraints in SQLite dialect.
Please refer to the batch mode feature which allows for SQLite migrations
using a copy-and-move strategy.
```

### 1.3 根因（single root cause）

SQLite 不支持 `ALTER TABLE ... ADD CONSTRAINT`。Alembic 的 `op.create_unique_constraint(...)` 在 SQLite 方言下会尝试 `ALTER` → `NotImplementedError`。两个历史 migration 违反方言中立性：

| Migration | 用法 | SQLite 兼容方案 |
|-----------|------|----------------|
| `1a325e38e941_add_entity_memory_and_project_state_.py` (L40-43, L71-74) | `create_unique_constraint` **刚创建完表**就独立添加 | 将 `UniqueConstraint` 内嵌进 `create_table` 的参数 |
| `b08103b3a6f5_add_unique_constraint_on_questions_.py` (L22-26) | 对**已存在**的 `questions` 表添加约束 | 用 `with op.batch_alter_table(...) as batch_op:` 包装 |

两者在 PostgreSQL 上的最终 DDL 等价：
- `CREATE TABLE ... UNIQUE (...)` ≡ `CREATE TABLE ... ; ALTER TABLE ... ADD CONSTRAINT ... UNIQUE (...)`
- Alembic 对 PostgreSQL 的 `batch_alter_table` 默认 fallback 为直接 `ALTER TABLE`（batch mode 只在 SQLite 上触发 copy-and-move）

这是纯 DDL 构造方式的差异，不涉及任何业务语义变化。

## §2 修复方案

### 2.1 Migration `1a325e38e941`（新建表场景）

**修改点：** 将 `op.create_unique_constraint` 合并进 `op.create_table` 的参数。

**Before（当前，会在 SQLite 失败）:**
```python
op.create_table(
    'entity_memory',
    sa.Column('entity_type', sa.String(30), nullable=False),
    ...
    sa.PrimaryKeyConstraint('id'),
)
op.create_index('ix_entity_memory_lookup', 'entity_memory',
                ['school_id', 'entity_type', 'entity_id'], unique=False)
op.create_unique_constraint(
    'uq_entity_memory_lookup', 'entity_memory',
    ['school_id', 'entity_type', 'entity_id'],
)
```

**After（方言中立）:**
```python
op.create_table(
    'entity_memory',
    sa.Column('entity_type', sa.String(30), nullable=False),
    ...
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('school_id', 'entity_type', 'entity_id',
                        name='uq_entity_memory_lookup'),
)
op.create_index('ix_entity_memory_lookup', 'entity_memory',
                ['school_id', 'entity_type', 'entity_id'], unique=False)
# op.create_unique_constraint(...) 已合并进 create_table，删除
```

对 `project_state` 表（L71-74）做对称修改：将 `uq_project_state_project` 合并进其 `create_table`。

**downgrade 对称修改**：`op.drop_constraint(...)` 保留（DROP CONSTRAINT 在 SQLite 上同样不支持，但 SQLite 模式下 downgrade 若失败不影响主要 gate；本次直接改为——若通过 `drop_table` 整表删除则无需独立 drop_constraint，因为约束随表一起消失。检查现有 downgrade 顺序：entity_memory 的 `drop_table` 会一并删约束，所以独立的 `drop_constraint` 可安全删除）。

### 2.2 Migration `b08103b3a6f5`（已存在表场景）

**修改点：** 用 `batch_alter_table` 包装 `create_unique_constraint`。Alembic 在 PostgreSQL 上自动走普通 `ALTER`，在 SQLite 上走 copy-and-move；语义等价。

**Before:**
```python
def upgrade() -> None:
    op.create_unique_constraint(
        "uq_question_subject_name",
        "questions",
        ["subject_id", "name"],
    )

def downgrade() -> None:
    op.drop_constraint("uq_question_subject_name", "questions", type_="unique")
```

**After:**
```python
def upgrade() -> None:
    with op.batch_alter_table("questions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_question_subject_name",
            ["subject_id", "name"],
        )

def downgrade() -> None:
    with op.batch_alter_table("questions") as batch_op:
        batch_op.drop_constraint("uq_question_subject_name", type_="unique")
```

### 2.3 Handoff 与审查交接单回滚 test_debt 声明

原 batch1 审查交接单把"Migration upgrade/downgrade"列为 `skipped`，并把全量回归命令写为 `pytest --deselect tests/test_alembic_migration.py`——这是导致 F001 的 handoff 层根因。

在 R2 审查交接单中，自审表对 Task 1 (Migration) 的"实际执行"列必须改为：
- migration 52af1c37bf14（本批次新增）在 SQLite + PostgreSQL 均可 upgrade + downgrade
- 历史 migration `1a325e38e941` / `b08103b3a6f5` 同步修复方言兼容性
- `tests/test_alembic_migration.py` **不 deselect**，PASS
- 全量回归命令：`python -m pytest --tb=short -q`（不排除 migration smoke）

## §3 Fix Intent Card（Semantic Regression Gate 输入）

```yaml
root_cause: |
  两个历史 migration 使用独立 op.create_unique_constraint()，SQLite 方言不支持
  ALTER TABLE ADD CONSTRAINT，导致 migration smoke gate 在 SQLite 上断裂。
  这是 DDL 构造方式的方言中立性缺陷，不涉及业务语义。

preserved_invariants:
  - ORC-migration-rollback: "52af1c37bf14 upgrade + downgrade 可逆（原 plan INV-04）"
  - ORC-schema-equivalence: "entity_memory / project_state / questions 三表在 PG 上的最终 schema（列+索引+唯一约束+FK）与修复前完全一致"
  - ORC-orm-metadata-parity: "alembic upgrade head 后的表集合与 Base.metadata.tables 一致（test_migration_creates_all_expected_tables 断言）"
  - ORC-baseline-sqlite-chain: "完整 alembic upgrade head 在空 SQLite 上无异常"

non_goals:
  - 不改动 entity_memory / project_state / questions 的任何字段、索引、约束语义
  - 不引入新的数据库方言分支逻辑（不加 if dialect == 'sqlite'）
  - 不修改 tests/test_alembic_migration.py 的断言强度
  - 不删除 handoff 中的 migration smoke gate（相反：恢复其有效性）
  - 不改动其他 migration 文件

allowed_change_surface:
  - alembic/versions/1a325e38e941_add_entity_memory_and_project_state_.py
  - alembic/versions/b08103b3a6f5_add_unique_constraint_on_questions_.py
  # 2026-04-13 扩展（用户批准）：同类方言缺陷一次修完（systematic-debugging scope check 同模式）
  - alembic/versions/a370e2771c6d_add_knowledge_hierarchy_columns.py  # alter_column + drop_column
  - alembic/versions/2a40f59215de_add_edge_review_status.py            # drop_column (downgrade)
  - alembic/versions/52af1c37bf14_add_menu_and_analysis_tables.py      # drop_column (downgrade, exam_results rank_*)
  - alembic/versions/c9587c787c6b_add_agent_profiles_and_agent_runs_.py  # drop_column (downgrade, llm_slots.tier)
  - docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch1-r2.md（新建 R2 交接单，含修复后的自审表）

verification:
  - "cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_alembic_migration.py -q"
    期望: 2 passed, 0 failed, 0 error（修复前：1 passed, 1 failed, 1 error）
  - "cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_menu/ -q"
    期望: 9 passed, 0 failed（确认本批次 menu 模块不回归）
  - "cd C:/Users/Administrator/edu-cloud && python -m pytest --tb=short -q"
    期望: 1895+ tests PASS（项目级全量，不 deselect migration smoke）
  - "cd C:/Users/Administrator/edu-cloud && python -c \"from sqlalchemy import create_engine, inspect; ...\""
    （对比 SQLite + PG schema 等价性——通过 test_migration_creates_all_expected_tables 已覆盖）
```

## §4 测试契约

### Slice 1: SQLite 迁移 upgrade 成功
- 入口: `python -m alembic upgrade head`（DATABASE_URL=sqlite+aiosqlite:///...）
- 反例: 错误实现（独立 create_unique_constraint 保留）→ `NotImplementedError: No support for ALTER of constraints in SQLite dialect`
- 边界: 空库上执行 upgrade head、已 upgrade 后再次 upgrade 幂等
- 回归: 防止 F001 复发（migration gate 在 SQLite 上可执行）
- 命令: `python -m pytest tests/test_alembic_migration.py::test_migration_creates_all_expected_tables -v`

### Slice 2: SQLite 迁移 downgrade 可逆
- 入口: `python -m alembic downgrade base`（on fresh upgraded SQLite）
- 反例: 错误实现（drop_constraint 保留独立调用）→ 同样 NotImplementedError 或表残留
- 边界: 空库、部分表、全表
- 回归: INV-04（可逆性）
- 命令: `python -m pytest tests/test_alembic_migration.py::test_migration_downgrade_is_clean -v`

### Slice 3: PG schema 等价性（soft verify via ORM metadata）
- 入口: `inspect(sqlite_engine).get_unique_constraints('entity_memory')`
- 反例: 错误实现（UniqueConstraint 丢失）→ 返回空或与 Base.metadata 不一致
- 边界: entity_memory / project_state / questions 三张表的 uq_* 约束
- 回归: ORC-schema-equivalence
- 命令: `python -m pytest tests/test_alembic_migration.py::test_migration_creates_all_expected_tables -v`（已覆盖表集合对比；约束等价性由 Base.metadata 隐含保证）

## §5 风险评估

| 维度 | 评估 | 依据 |
|------|------|------|
| PostgreSQL 运行时行为变化 | 零 | UniqueConstraint 在 CREATE TABLE 中 vs ALTER TABLE 中，PG 最终 DDL 等价 |
| SQLite 运行时行为变化 | 零 | 之前 SQLite 根本无法 upgrade；现在可以——从"断裂"到"可用" |
| 现有数据迁移风险 | 零 | 本次不重跑 migration，只修 migration 文件源码。已部署的 PG 数据库已经 stamped 到 head，不会重跑这两个历史 migration |
| 下游 migration 风险 | 零 | revision ID、down_revision 均不变，migration 链拓扑不变 |
| 生产 PostgreSQL 回滚风险 | 零 | 生产已 stamped，不会触发修复后的 upgrade 路径 |

> **关键断言：** 修复不需要对已部署 PG 数据库重跑 migration。`alembic_version` 表已记录 head revision，alembic 不会回头执行已应用的 migration。本次修复仅使 smoke test 和新环境 provisioning 在 SQLite 上可通过。

## §6 实施顺序

1. 修改 `1a325e38e941_add_entity_memory_and_project_state_.py`（upgrade + downgrade）
2. 修改 `b08103b3a6f5_add_unique_constraint_on_questions_.py`（upgrade + downgrade）
3. 跑 Slice 1-3 验证命令
4. 合并到 F003 修复（弱断言）commit，以 "fix(migrations): SQLite-compatible constraint creation (F001 repair)" 单独 commit
5. 跑全量回归 `python -m pytest --tb=short -q`
6. 输出 R2 审查交接单，自审表 Task 1 行更新为"实际执行：历史 migration 方言兼容性修复 + 新 migration smoke PASS"

## §7 变更类型

**变更类型：非行为变更**（纯 DDL 方言兼容性修复 + test_debt 偿还）。

不触发新的 Plan Review。F001 的 repair 完成即 R2 审查材料的一部分，由 codex-review 代码审查重新验证。
