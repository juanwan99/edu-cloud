# S1-C Admin Plan Review R1（FAIL）

**Date**: 2026-04-24T20:43+08:00
**Reviewer**: GPT-5.4 (Codex CLI via codex-review skill)
**Reviewed Plan**: [2026-04-24-haofenshu-s1-admin-plan.md](./2026-04-24-haofenshu-s1-admin-plan.md) (commit `93108e9`)
**Parent Design**: [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md)
**Parent Plan (aborted)**: [2026-04-24-haofenshu-s1-l1-data-layer-plan.md](./2026-04-24-haofenshu-s1-l1-data-layer-plan.md) + R1 review
**Raw Log**: `.codex-plan-review-raw-s1c-20260424_203300.log` (约 4 千行 / 258KB)
**Raw Log SHA256**: `c6b1bad96fe1607024dc16a25b0994ec6e9f1df681e1e846e486fd6f9cdcce1f`

---

## 结论：R1 FAIL

存在 5 条 HIGH（code-bug × 3 + test-gap × 2）和 2 条 MED（code-bug + design-concern）finding。按 review-templates.md 判定：HIGH/MED 未修复 → FAIL。

GPT 阅读规则文件 + 对照项目实际代码完成审查，所有 finding 均附可验证证据（file:line）。

---

## Findings 汇总

| ID | Severity | Category | Type | 概括 |
|---|---|---|---|---|
| F001 | HIGH | code-bug | defect_fix | `tests/conftest.py` 模型导入清单不含 `edu_cloud.models.grade`；`db_engine` 直接对 `Base.metadata` 执行 `create_all()`，Grade/TeachingPlan 未进 Base registry 时测试建库阶段即失败 |
| F002 | HIGH | code-bug | defect_fix | Task 4 smoke 用空库 `alembic stamp a88094ee4ea6` + 直接 upgrade S1-C，但 S1-C migration 要 `batch_alter_table('classes')` / `batch_alter_table('bank_questions')`，空库无这两张表——起点是不可能态 |
| F003 | HIGH | code-bug | defect_fix | `alembic heads` 是脚本目录 head 列表，不是数据库当前 revision。`downgrade -1` 后 heads 不变而 current 才变；现有 `tests/test_alembic_migration.py` 已正确用 schema 检查而非 heads 断言回滚 |
| F004 | HIGH | test-gap | defect_fix | Task 5 测试契约声明 `test_existing_tables_data_preserved`（Seed 数据 upgrade 不丢），但实际 Task 5 Step 5.1 给出的测试文件中没有这个函数；`tests/test_alembic_s1a_bank.py` 已有 `test_existing_data_preserved_through_migration` 样板 |
| F005 | HIGH | test-gap | defect_fix | INV-S1C-001/002 把 `UniqueConstraint(...)` 写成 invariant，但 `test_grades_table_created_with_expected_schema` / `test_teaching_plans_table_and_fks_ok` 只断言列/FK/nullability，没有唯一约束断言；plan 多处引用 `test_migration_file_down_revision_matches_prev_head` 等测试名与实际定义 `test_migration_file_exists_and_down_revision_matches_prev_head` 漂移 |
| F006 | MED | code-bug | defect_fix | plan 用 `tests/models/` + `tests/modules/<name>/` 目录路径，但仓库实际约定是 `tests/test_models/` + `tests/test_modules/test_<name>/`；Task 2 回归命令 `tests/test_modules/test_calendar/` 路径不存在 |
| F007 | MED | design-concern | defect_fix | Evidence E-002 写"全项目零 Integer primary key"作为负面断言证据，但 `analytics/models.py` / `menu/models.py` / `knowledge_tree/models.py` 实际存在 Integer 主键——负面断言证据失真 |

---

## 核心 Findings 详述

### F001（HIGH）tests/conftest.py 缺 Grade/TeachingPlan 注册

**Before**: plan ORC-S1C-005 只要求加 `alembic/env.py` + `src/edu_cloud/api/app.py` 两处 import，认为 Grade/TeachingPlan 通过 `app.py` import 就能进 Base registry。同时 Task 3 Step 3.5 回归命令跑 `pytest tests/test_services_exam/test_bank_service.py`，依赖 `tests/conftest.py` 的 `db` fixture。

**After**: `tests/conftest.py` 的模型导入清单必须显式包含 `edu_cloud.models.grade`（和 `edu_cloud.modules.calendar.models`，如果 calendar/models.py 本就没被 conftest import）。测试启动链路走 `Base.metadata.create_all()` 而非 Alembic，需要 Base registry 完整。

**Evidence**:
- plan Task 1 Step 1.5 / Task 3 Step 3.5 / Task 5 Step 5.3 / Gate G1-S1C
- `tests/conftest.py` 直接用 `Base.metadata.create_all()`
- `tests/conftest.py` 的模型导入清单（grep 验证）不含 `edu_cloud.models.grade`
- Parent R1 review 已明确点出过此模式："测试期 `Base.metadata.create_all()` 需要模型已在 Base registry"

**Impact**: Task 3 Step 3.5 回归路径 `pytest tests/test_services_exam/test_bank_service.py` 在建库阶段（conftest create_all）即失败，因为 bank ORM 已 `ForeignKey("grades.id")` 但 `grades` 不在 Base registry → `sqlalchemy.exc.NoReferencedTableError`。Plan 的执行顺序 + Gate G1 验证路径全部不成立。

**Repair 方向**:
- 在 `tests/conftest.py` 的模型导入清单中显式加 `from edu_cloud.models.grade import Grade` 和 `from edu_cloud.modules.calendar.models import TeachingPlan`
- ORC-S1C-005 改为"测试 + alembic + app 三处同步"，不再声称"零 __init__.py 依赖"（conftest.py 不是 __init__.py 但同属测试启动链路）
- Task 1 File Structure / Step 1.5/1.6 补充 conftest.py 修改步骤 + 对应 grep 断言

---

### F002（HIGH）Task 4 smoke 起点是不可能态

**Before**: Task 4 Step 4.6 smoke 命令：
```bash
.venv/bin/alembic stamp a88094ee4ea6    # 空库上只写 alembic_version 标记
.venv/bin/alembic upgrade head           # 直接跑 S1-C migration
```

而 S1-C `upgrade()` 内含：
```python
with op.batch_alter_table('classes', schema=None) as batch_op:
    batch_op.add_column(sa.Column('grade_id', ...))
with op.batch_alter_table('bank_questions', schema=None) as batch_op:
    batch_op.alter_column('grade_id', ...)
```

**After**: S1-C smoke 必须从"真实的 pre-S1-C schema 已存在"的数据库状态起步——即先跑全链路到 `a88094ee4ea6`（让 `classes` / `bank_questions` / 等约九十张表全部 upgrade 就位），再跑 S1-C migration。

**Evidence**:
- plan Task 4 Step 4.6 / Step 4.4 upgrade body
- 本地验证：对空库 `alembic stamp a88094ee4ea6` 后，仅 `alembic_version` 一张表
- S1-A migration 对比：`a88094ee4ea6` 自身也依赖 `bank_questions` 存在（S1-A 也是 batch_alter_table）——S1-A 的 smoke `tests/test_alembic_s1a_bank.py` 走 `upgrade head` 而不是 `stamp + upgrade`

**Impact**: G1-S1C 可逆性证据失效——smoke 是在缺失前置表的库上跑 S1-C，migration 本身行为未被真实验证。

**Repair 方向**:
- Step 4.6 命令改为 `alembic upgrade a88094ee4ea6 && alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
- Task 5 smoke test 也需相应改动——在 `_run_alembic(['upgrade', 'head'], ...)` 之前必须让 classes/bank_questions 先就位（默认 `upgrade head` 从 base 跑全链路自动建这些表，问题出在 Task 4 手动 `stamp` 起步）
- 禁止：删 classes/bank_questions DDL 或降低 smoke 断言强度"让命令通过"
- **requires independent fix design + Semantic Regression Gate**

---

### F003（HIGH）回滚验证用错指标

**Before**: Task 4 Step 4.6 + Task 5 `test_downgrade_restores_s1a_head` 用 `alembic heads` 的输出断言 downgrade 结果。

**After**: `alembic heads` 是脚本目录的 head 列表（跟脚本文件打包决定，不跟数据库当前状态），永远反映目录里最新的 revision。downgrade 之后 heads 不变，只有 `current` 变。回滚验证必须用 `alembic current` 或直接 inspect `alembic_version` 表。

**Evidence**:
- plan Step 4.6 命令 `alembic heads` 期望 `a88094ee4ea6` / Task 5 `test_downgrade_restores_s1a_head`
- 本地实测：
  - `upgrade head` 后：`alembic heads` = `a88094ee4ea6 (head)`，`alembic current` = `a88094ee4ea6`
  - `downgrade -1` 后：`alembic heads` **仍是** `a88094ee4ea6 (head)`，但 `alembic current` = `a8c7d2e4f135`
- 现有正确样板：`tests/test_alembic_migration.py`（inspect schema 而非 heads）；`tests/test_alembic_s1a_bank.py` 也没用 heads 判回滚

**Impact**: 回滚门禁用错误指标——migration 实际未回滚时断言依然 PASS；Gate G1-S1C 可逆性证据不成立。

**Repair 方向**:
- Step 4.6 downgrade 后的断言改为 `alembic current` 输出等于 `a88094ee4ea6`
- Task 5 `test_downgrade_restores_s1a_head` 改为跑 `alembic current` subprocess 或 inspect `alembic_version` 表
- 禁止：把 `heads` 当数据库状态；或仅靠脚本文件字符串匹配替代回滚验证
- **requires independent fix design + Semantic Regression Gate**

---

### F004（HIGH）声明的 test_existing_tables_data_preserved 未落地

**Before**: Task 5 测试契约（"边界"第 2 条）明确写 `test_existing_tables_data_preserved` / "预置 seed 数据后 upgrade 不丢现有表数据"；但 Task 5 Step 5.1 给出的 `tests/test_alembic_s1c_admin.py` 9 个 test 中没有这个函数。

**After**: 类型迁移路径（bank_questions.grade_id Integer → String(36)）+ 新建 classes.grade_id + 新建 teaching_plans，必须有"预置 pre-S1-C 数据 → upgrade → 核对数据保留"的入口级测试。

**Evidence**:
- plan 契约声明 / 边界第 2 条 / Task 5 给出完整测试列表仅 9 个，无此函数
- 正确样板：`tests/test_alembic_s1a_bank.py::test_existing_data_preserved_through_migration`（S1-A 的做法是 pre-revision upgrade + INSERT 测试数据 + upgrade head + 校验数据保留）

**Impact**: 本 plan 最高风险路径（带历史数据 migration）零测试覆盖；对真实库迁移的风险评估失真。

**Repair 方向**:
- 在 `tests/test_alembic_s1c_admin.py` 补一个 `test_existing_data_preserved_through_s1c_migration`：
  1. `alembic upgrade a88094ee4ea6`（起点 S1-A head）
  2. INSERT 若干 `classes` / `bank_questions` 行（带齐 NOT NULL 必填列）
  3. `alembic upgrade head`（跑 S1-C）
  4. 校验行数、关键列值保留；新列 `classes.grade_id` / `bank_questions.grade_id` 为 NULL（对齐 S1-C 预期：不反向填充）

---

### F005（HIGH）Contract Pack invariant 与测试不对齐

**Before**:
1. INV-S1C-001 statement 写"含 `UniqueConstraint(school_id, name)`"，INV-S1C-002 写"含 `UniqueConstraint(school_id, subject_code, grade_id, semester)`"
2. verification 映射指向 `test_grades_table_created_with_expected_schema` / `test_teaching_plans_table_and_fks_ok`
3. 但 Task 5 这两个 test 只检查列/FK/nullability，**没有**唯一约束断言
4. plan 文本多处引用 `test_migration_file_down_revision_matches_prev_head`，实际函数名是 `test_migration_file_exists_and_down_revision_matches_prev_head`；类似 `test_teaching_plans_fk_targets_are_existing_tables` vs 实际 `test_teaching_plans_table_and_fks_ok`

**After**: 每条 invariant 必须映射到真实存在、且真正断言了该 invariant 的测试。Contract Pack 的 verification 映射必须可执行。

**Evidence**:
- plan INV-S1C-001 / INV-S1C-002 / test_grades_... 函数体 / test_teaching_plans_... 函数体
- GPT 独立核对：两个 test 只用 `insp.get_columns()` / `insp.get_foreign_keys()`，没有 `insp.get_unique_constraints()`

**Impact**: migration 即使漏了 UniqueConstraint 也可能在 Gate G1 假绿。

**Repair 方向**:
- `test_grades_table_created_with_expected_schema` 追加 `insp.get_unique_constraints('grades')` 断言含 `{school_id, name}` 列集
- `test_teaching_plans_table_and_fks_ok` 追加 `insp.get_unique_constraints('teaching_plans')` 断言含 `{school_id, subject_code, grade_id, semester}` 列集
- 全 plan 文本 grep `test_migration_file_down_revision_matches_prev_head` / `test_teaching_plans_fk_targets_are_existing_tables` 等引用名与 Task 5 函数体对齐
- 禁止：只改 prose 名字不补断言
- **requires independent fix design + Semantic Regression Gate**

---

### F006（MED）测试目录路径不符仓库布局

**Before**: plan File Structure 表格 + Task 1/2/3/5 的测试路径写 `tests/models/` + `tests/modules/<name>/`；Task 2 Step 2.4 回归命令引用 `tests/test_modules/test_calendar/`。

**After**: 仓库实际约定（见 `orm-placement.md` + `ls tests/`）是 `tests/test_models/` + `tests/test_modules/test_<name>/`。

**Evidence**:
- plan File Structure 表 `tests/models/test_grade.py` / Task 1 Create / Task 2 Create / Task 2 回归命令 `tests/test_modules/test_calendar/`
- `orm-placement.md` 明示 `tests/test_modules/test_<name>/test_models.py`
- `ls tests/test_modules/test_calendar` → `No such file or directory`

**Impact**: 至少 Task 2 回归命令路径不存在直接失败；plan 引入了与现有代码库并行的第二套目录规范，未来 executor 执行时 pytest collection error。

**Repair 方向**:
- 全局替换：
  - `tests/models/test_grade.py` → `tests/test_models/test_grade.py`
  - `tests/modules/student/test_class_grade_id.py` → `tests/test_modules/test_student/test_class_grade_id.py`
  - `tests/modules/calendar/test_teaching_plan_model.py` → `tests/test_modules/test_calendar/test_teaching_plan_model.py`
  - `tests/modules/paper/test_access_level.py` → `tests/test_modules/test_paper/test_access_level.py`
  - Task 2 回归命令 `tests/test_modules/test_calendar/` 改为实际存在的 `tests/test_api/test_calendar*.py` 或去掉该路径（只跑新 test）
- File Structure / Task 命令 / 回归指令同步对齐

---

### F007（MED）E-002 负面断言证据失真

**Before**: Evidence E-002 Q2_excluded 第 1 条写：
> grep 现有表证明全项目零 Integer primary key：`grep -l "Integer, primary_key" src/edu_cloud/modules/*/models.py src/edu_cloud/models/*.py` 零匹配。

**After**: 实测仓库中仍存在 Integer 主键：
- `src/edu_cloud/modules/analytics/models.py`（多处）
- `src/edu_cloud/modules/menu/models.py`
- `src/edu_cloud/modules/knowledge_tree/models.py`（多处）

**Evidence**: GPT 独立 grep + 读文件验证。

**Impact**: "grades.id 应沿用 IdMixin String(36)"决策方向仍合理，但证据基础不实——负面断言证据失真降低 plan 可审计性（E+ 决策证据纪律不满足）。

**Repair 方向**:
- E-002 Q2_excluded 第 1 条改写为："新建跨模块共享表沿用 IdMixin UUID 约定（grep `class.*IdMixin` 在 models/*.py 见 60+ 处印证），仓库中少量历史 Integer PK 表（analytics/menu/knowledge_tree）为遗留设计，不作为 S1-C grades.id 类型参照"
- 保留大方向判断，把证据精度收窄到"新建 Grade 沿用 IdMixin 约定"而非"全项目零 Integer PK"

---

## Gate 决策

按 codex-review skill §Gate 条件：

- **R1 FAIL**
- **R2 条件判断**：
  - Tier = T4？否（T3）
  - topic 含 `remote`/`deploy`/`publish`？否
  - 跨模块重构（plan 声明修改文件数 ≥2 且涉及 ≥2 模块）？**是**（bank / student / calendar / paper / models / alembic/env.py / api/app.py / tests/conftest.py —— 跨 7+ 文件 / 6+ 模块）
- **结论：允许 R2**

**7 findings 性质评估**（决定 R2 vs 拆 topic）：
- F001-F007 全部为结构性修复，不触发根本设计方向变动
- F001 `conftest.py` 加 import 行：1 处 + 对应 test + ORC 表述修正
- F002 smoke 起点修正：命令改 1 行
- F003 回滚指标改 `current`：机械化 3 处
- F004 补 1 个 test
- F005 补 2 处 UniqueConstraint 断言 + 全局测试名对齐
- F006 测试路径全局替换（机械化）
- F007 E-002 证据描述改写
- 修复总范围：plan 文件内部改动 + 不触发设计层面重写 → R2 可行

**结论：走 R2**（一次性修复 7 findings 后重审）。R2 仍 FAIL 时按 Gate 条件拆 topic 或 manual_override，禁 R3+。

---

## 后续路径

1. 按本报告 Repair 方向修复 F001-F007，**保持**已有 5 条 ORC / 8 条 INV / 4 条 CE / Task 结构不变
2. git commit plan（single commit，覆盖 plan 文件）
3. 走 codex-review plan R2（reason 写明"跨模块重构触发 R2"+ 修复范围摘要）
4. R2 PASS → 写 pass receipt → 独立新会话执行
5. R2 FAIL → 拆 topic（S1-C-i/ii/iii）或 manual_override（需用户决策）

**Deadline 锚点**：2026-05-01 前 S1-A/B/C/D 全 R1 PASS 关闭 parent `haofenshu-s1-l1-data-layer` 的 manual_override。本 R1 FAIL + R2 修复应在 7 天 deadline 内完成。

---

## Raw Evidence

Full Codex output: `docs/plans/.codex-plan-review-raw-s1c-20260424_203300.log`（约 4 千行 / 258KB）
SHA256: `c6b1bad96fe1607024dc16a25b0994ec6e9f1df681e1e846e486fd6f9cdcce1f`
