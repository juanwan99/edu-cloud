# S1-C Admin Code Review Handoff（Executor → GPT Reviewer, Gate 2）

**Date**: 2026-04-24T22:35+08:00
**Topic**: haofenshu-s1-admin
**Tier**: T3
**Gate**: Gate 2 Code Review (MCP 路径)
**Plan**: [2026-04-24-haofenshu-s1-admin-plan.md](./2026-04-24-haofenshu-s1-admin-plan.md)
**Plan R1 Review**: [2026-04-24-haofenshu-s1-admin-plan-review.md](./2026-04-24-haofenshu-s1-admin-plan-review.md)
**Plan R2 Review (FAIL)**: [2026-04-24-haofenshu-s1-admin-plan-review-r2.md](./2026-04-24-haofenshu-s1-admin-plan-review-r2.md)
**Gate 决策**: Plan R2 FAIL → 用户 A 路径授权 `manual_override` → Executor 实现阶段闭环 R2 findings

---

## Commit Range

`git log --oneline 2207723~1..6717a89`

| commit | Task | 摘要 |
|---|---|---|
| `2207723` | T1 | Grade 独立表 + Class.grade_id FK + 三入口 import（env.py/app.py/conftest.py 各 1 行 Grade） |
| `9268b4a` | T2 | TeachingPlan **canonical 挪到 `src/edu_cloud/models/teaching_plan.py`**（R2-F001 核心修复）+ 三入口各 1 行 TeachingPlan import |
| `5e84f8f` | T3 | PaperAccessLevel 枚举（F006 反镜像 round-trip 测试）+ bank.grade_id Integer→String(36) + FK（闭环 TD-S1A-002）+ S1-A 遗留 3 test grade_id UUID 化 |
| `974c33c` | T4 | Alembic linear chain 第 2 环 migration `f311eb126798`（down_revision='a88094ee4ea6'）；upgrade/downgrade 双方言 batch_alter_table 包装 |
| `612a6ce` | T5 | migration smoke test（15 个）+ Gate G1 verification；包含 R2-F001/F002 修复对应断言 |
| `6717a89` | 收尾 | plan 文本 R2-F003 登记 test_debt #5 + R1 F003 残余 `alembic heads`→`alembic current` 清理 |

**Diff stat**: 20 files changed, 1000 insertions, 7 deletions（含 ORM 5 + migration 1 + tests 4 新 + conftest/env/app 三入口 3 处各 2 行 + CLAUDE.md + governance 派生产物 + plan 文本）

---

## Goal 与 Deliverables

Parent design §4.1 deliverables：
- **1.3** — Grade 独立表 + Class.grade_id FK（ORM + migration 双层）
- **1.4** — TeachingPlan 骨架表（仅 schema）
- **1.5** — PaperAccessLevel 枚举（3 值 str+Enum）
- **TD-S1A-002 闭环** — bank_questions.grade_id 类型 Integer→String(36) + FK→grades.id（S1-A 遗留 deadline 2026-05-08）

---

## R2 修复闭环对照表（必须复核）

| R2 Finding | 修复位置 | 具体变更 | 验证测试 |
|---|---|---|---|
| **R2-F001 HIGH** TeachingPlan 注册链路断裂 | T2 commit `9268b4a` | canonical 从 `modules/calendar/models.py` 挪到 **`src/edu_cloud/models/teaching_plan.py`**（与 Grade 一致 platform-level）；env.py + app.py + conftest.py 三入口**各加独立 import**（不再依赖"import edu_cloud.modules.calendar.models"——Planner 调研阶段误判 app.py `import edu_cloud.models.calendar` 语义的根源） | `test_orm_registration_three_entry_points` 三入口各断言 Grade + TeachingPlan import |
| **R2-F002 HIGH** INV-S1C-001 子句缺失 | T1 `test_grade_sort_order_has_default_zero`（ORM 层）+ T5 `test_grades_table_created_with_expected_schema`（migration 层补 FK + sort_order server_default='0' 断言） | - ORM 层：断言 `col.default.arg == 0`<br>- Migration 层：断言 `fk.referred_table=='schools'` + `server_default='0'` | T1 `test_grade_school_fk_target` + T5 同名 test |
| **R2-F002 HIGH** INV-S1C-002 子集断言漏 created_by→users | T2 拆 3 个独立断言 + T5 migration 层同步拆 | `test_teaching_plan_{school_id,grade_id,created_by}_fk_targets_*`（ORM 层 3 个）+ `test_teaching_plans_{schools,grades,users}_fk_exists`（migration 层 3 个） | 共 6 个独立 FK 断言 |
| **R2-F002 HIGH** INV-S1C-008 "0 非空行"可被漂移绕过 | T5 升级为字节级 SHA256 | 硬编码空文件 SHA256 锚点 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`，对 `models/__init__.py` 做精确字节比对 | `test_orm_registration_three_entry_points` 断言 4 |
| **R2-F003 MED** 入口只有 introspection | 收尾 commit `6717a89` 登记 test_debt | plan `contract_pack.test_debt` 追加第 5 条，deadline 2026-08-31（S4 补 service/API 时同步补入口级断言） | plan 文本变更 |
| **R1 F003 残余** 测试契约段"alembic heads"错误口径 | 收尾 commit `6717a89` | plan Task 4 测试契约段 `alembic heads` 改为 `alembic current`（只在这 1 处；其他"alembic heads"引用是正确的脚本目录 DAG 判定） | plan 文本变更 |

---

## Semantic Regression Oracles（ORC-S1C-001~005）

本 plan 已在 `## semantic_regression` 段给出 5 条 ORC（state_machine + resource_path tags）。GPT reviewer 对每条 finding 的 Repair hypothesis **必须不违反**这些 ORC：

- **ORC-S1C-001** linear chain 第 2 环 `down_revision='a88094ee4ea6'`
- **ORC-S1C-002** Class 守旧字段 `grade`/`grade_number` 字符匹配保持
- **ORC-S1C-003** teaching_plans FK 目标 ⊂ {schools.id, grades.id, users.id}
- **ORC-S1C-004** FK 类型统一 String(36)；bank.grade_id 闭环 TD-S1A-002
- **ORC-S1C-005** ORM 注册走 env/app/conftest 三入口，零 __init__.py 依赖

完整 statement 见 plan.md `## semantic_regression` 段。

---

## Gate G1-S1C 验收证据（@ 2026-04-24T22:24）

```
.venv/bin/python -m pytest --tb=no -q
```

结果（粘贴自实际输出最后一行）：
```
21 failed, 2143 passed, 23 skipped, 33 warnings in 890.62s (0:14:50)
```

- **基线** @ 2026-04-24T20:14（post-S1-A commit c155ab5）：`2102 passed / 21 failed / 23 skipped`
- **S1-C 实施后** @ 2026-04-24T22:24（HEAD `6717a89`）：`2143 passed / 21 failed / 23 skipped`
- **增量**：+41 passed（9 T1 + 8 T2 + 9 T3 + 15 T5）/ 21 failed **保持**（零新增）/ 23 skipped **保持**

21 pre-existing failed 是 S1-A 之前的既有技术债，在 plan.md Deferred 第 6 条和 S1-A plan §Deferred 第 7 条明确披露，**不归本 S1-C scope**。

### Alembic linear chain 单 head 实测

```
.venv/bin/alembic heads
→ f311eb126798 (head)
```

本地 SQLite smoke 四阶段全过（从 base 跑全链路到 S1-A → upgrade S1-C → current=f311eb126798 → downgrade -1 → current=a88094ee4ea6 → upgrade 幂等 → current=f311eb126798 → heads 单行）。

---

## 重点审查请求

请 GPT 以 **defect_fix / test_gap / design_concern** 三分视角独立核查（L017 职责边界）：

### Phase 0 — Contract Pack freshness
- R2-F001 修复是否真正落地：TeachingPlan 的 canonical location 是否在 `src/edu_cloud/models/teaching_plan.py`（不是 `modules/calendar/models.py`）
- env.py/app.py/conftest.py 三处的 TeachingPlan import 是否均能在 `grep "import edu_cloud.models.teaching_plan"` 命中（每处各 1 条）

### Phase 1 — 测试充分性
- INV-S1C-002 拆分后 ORM 层 3 个独立 FK test（`_school_id_fk_targets_schools` / `_grade_id_fk_targets_grades` / `_created_by_fk_targets_users`）是否真能捕获"漏 created_by→users FK"的错误实现
- INV-S1C-008 SHA256 锚点是否在任何空白/BOM 漂移下都会失败（反证：构造一个加了尾随空格的 __init__.py 应立即 fail）
- Migration 层 `test_grades_table_created_with_expected_schema` 对 `server_default='0'` 的断言在 SQLite 和 PostgreSQL 的 inspect 输出差异下是否 robust（SQLite 返回 "'0'"，PG 返回 "0"）

### Phase 2 — 行为正确性
- Class ORM 中 grade_id 插入位置（`grade_number` 之后、`head_teacher_id` 之前）是否违反 ORC-S1C-002 守旧字段"字符匹配保持"
- bank.grade_id migration 中 `postgresql_using='grade_id::text'` 在生产 PG（数据全 NULL 的前提已 grep 验证）上是否安全
- Migration downgrade 的 LIFO 顺序（drop_fk → alter_column 回 Integer → drop_fk → drop_column → drop teaching_plans → drop grades）是否有依赖倒置

### Phase 3 — 未测试风险
- Base.metadata.create_all() 在生产 app.py 启动路径下是否真的能发现 Grade 和 TeachingPlan（app.py 中的 import 是在 `async def create_tables()` 内部还是顶层？scope 是否正确）
- 三入口 import 顺序是否会触发循环导入（Grade import → edu_cloud.models.base → ...）

---

## 禁区（L017 + ORC）

- **禁止产出替代设计方案**（如"建议把 Grade 改成放 modules/student/models.py"——违反 E-003 跨模块共享表下沉策略）
- **禁止对 ORC 标记的 5 个不变量提修复方向的具体代码**，只能标注"conflicts with ORC-XXX" + 建议修复方向（按 skill §semantic-regression）
- **禁止评审 TeachingPlan 业务字段是否够用**（test_debt #4 归 S4，本 plan 只建骨架）

---

## 审查产物要求

`docs/plans/2026-04-24-haofenshu-s1-admin-code-review.md`（R1，按 review-templates.md 格式）

每个 finding 含：ID / Severity / Category / Type（defect_fix/test_gap/design_concern）/ Before / After / Evidence（file:line）/ Impact / (optional) Repair hypothesis。

---

## Audit

- **first_commit**: `2207723`
- **last_commit**: `6717a89`
- **diff_hash command**: `gates_lib.compute_range_hash('2207723..6717a89', project_dir)`
- **GPT 原始输出保存**: `docs/plans/.codex-code-review-raw-s1c-{timestamp}.log` + SHA256 计算 → 写入 gates receipt raw_output_hash

---

## 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|---|---|---|---|---|
| T1 Grade ORM + Class.grade_id + 三入口 | 新建 models/grade.py；Class 追加 grade_id（禁改 grade/grade_number）；env.py/app.py/conftest.py 各加 1 行 Grade import；新增 8 test（5 Grade + 3 Class） | commit `2207723`：Grade ORM（8 字段 + UQ(school_id,name)）+ Class 新增 grade_id 插在 grade_number/head_teacher_id 之间 + 三入口各 1 行 Grade import + 9 个 test（R2-F002 补 `test_grade_sort_order_has_default_zero` → 5+1=6 Grade + 3 Class）全绿 | ✓ 完成 | R2-F002 INV-S1C-001 子句拆分：补 `test_grade_school_fk_target` FK→schools.id + `test_grade_sort_order_has_default_zero` default=0 断言 |
| T2 TeachingPlan 骨架 | 追加到 modules/calendar/models.py（原 plan 设计）+ conftest.py 加 import；5 test（4 TeachingPlan + 1 calendar re-export） | commit `9268b4a`：**canonical 改到 `src/edu_cloud/models/teaching_plan.py`**（R2-F001 修复）+ env.py/app.py/conftest.py 三入口**各加独立 TeachingPlan import** + 8 test（FK 拆 3 独立 + 不含越界 + required fields + re-export + uq_constraint）全绿 | ✓ 完成（scope 扩展 R2-F001 修复） | R2-F001 HIGH 修复核心：Planner 原设计依赖 "modules.calendar.models import" 的假设在 app.py/env.py 层面不成立（实测它们 import 的是 `models.calendar`），导致 TeachingPlan 只在 conftest 注册链路；R2-F002 INV-S1C-002 拆成 schools/grades/users 3 个独立 FK 断言 |
| T3 PaperAccessLevel + bank.grade_id | 新建 modules/paper/constants.py；改 bank/models.py:41 Integer→String(36)+FK；S1-A 3 遗留 test 的 grade_id 值 UUID 化；F006 反镜像 round-trip 测试 | commit `5e84f8f`：PaperAccessLevel 3 成员 str+Enum（pytest.parametrize round-trip）+ bank.grade_id 类型改 + 3 遗留 test grade_id 从 `9`/`7`（Integer）改为 `"00000000-0000-0000-0000-000000000001"`/`"...002"` + 9 新 test + S1-A 9 遗留 test = 18 PASS | ✓ 完成 | 闭环 TD-S1A-002（deadline 2026-05-08 达成） |
| T4 Linear chain 第 2 环 migration | 生成 down_revision='a88094ee4ea6' migration；upgrade 含 create_table grades/teaching_plans + batch_alter_table classes/bank_questions；downgrade 反向 LIFO；SQLite 本地 smoke 四阶段 | commit `974c33c`：slug `f311eb126798`；upgrade 4 步（grades/teaching_plans/classes.grade_id/bank_questions.grade_id type+FK）；downgrade LIFO；本地 SQLite smoke `upgrade a88094ee4ea6 → upgrade head → downgrade -1 → upgrade head` 四阶段过；alembic heads 单行 | ✓ 完成 | 用 `alembic current` 判回滚（R1 F003）；`postgresql_using='grade_id::text'` PG 安全转换 |
| T5 Migration smoke test + Gate G1 | 9 个 test 机械化 ORC+INV；R1 F004/F005 补 3 个；R1 F001 conftest 断言；验收 baseline 22 failed 不新增 | commit `612a6ce`：15 个 test（扩展到 R2 修复）：down_revision 字符串断言 / orm_registration_three_entry_points 含 Grade+TP 各三入口+SHA256 字节级锚点 / chain_single_head / downgrade_restores（alembic current）/ grades schema + FK + default / grades UQ / teaching_plans 三个独立 FK + no-excess + UQ / classes legacy + grade_id / bank grade_id + FK / all_grade_id_string36 / existing_data_preserved | ✓ 完成 | Gate G1-S1C 全量 pytest 2143 passed / 21 failed（基线保持）/ 23 skipped；S1-C 新增 41 test 全绿 |
| 收尾 plan 清理 | 登记 R2-F003 test_debt；清理 R1 F003 Task 4 测试契约段 | commit `6717a89`：contract_pack.test_debt 追加第 5 条（deadline 2026-08-31）+ Task 4 测试契约段 `alembic heads` 改 `alembic current`（仅此 1 处；其他 heads 引用保持） | ✓ 完成 | manual_override 授权范围内的 plan 文本 freshness 收尾 |

---

## 验证清单自检

- [x] **G1 migration 可逆性**：本地 SQLite `upgrade a88094ee4ea6 → upgrade head (current=f311eb126798) → downgrade -1 (current=a88094ee4ea6) → upgrade head (幂等 current=f311eb126798)` 四阶段全过（见 T4 commit 974c33c 描述）
- [x] **G1 chain 单 head**：`.venv/bin/alembic heads` → `f311eb126798 (head)` 单行
- [x] **G1 全量测试基线保持**：2143 passed / **21 failed** / 23 skipped @ 2026-04-24T22:24，对比基线 2102/21/23（20:14）零新增 failure
- [x] **G1 S1-C 新增 41 test 全绿**：9 T1 + 8 T2 + 9 T3 + 15 T5 = 41；联合既有 test_models/test_calendar (5) + test_services_exam/test_bank_service (9) 无 regression
- [x] **G1 ORM 三入口注册**：env.py/app.py/conftest.py 各含 `Grade` + `TeachingPlan` import（grep 各处 1 条）；`models/__init__.py` SHA256 = `e3b0c442...`（空文件锚点保持）
- [x] **G1 grade_id 类型统一**：classes/teaching_plans/bank_questions 三张表 grade_id 全 VARCHAR(36)（`test_all_grade_id_fks_are_string36`）
- [x] **G1 TD-S1A-002 闭环**：bank_questions.grade_id 带 FK → grades.id（deadline 2026-05-08 提前达成）
- [x] **R2-F001 修复**：TeachingPlan canonical 在 `src/edu_cloud/models/teaching_plan.py`（grep 确认）；三入口各 1 条独立 TeachingPlan import
- [x] **R2-F002 INV-S1C-001 拆分**：sort_order default=0（ORM + migration 双层）+ school_id→schools.id FK（migration 层）独立断言
- [x] **R2-F002 INV-S1C-002 拆分**：teaching_plans schools/grades/users 三个独立 FK 断言（ORM 层 3 个 + migration 层 3 个 = 6 个 test）
- [x] **R2-F002 INV-S1C-008 升级**：`models/__init__.py` 字节级 SHA256 == 空文件锚点（`test_orm_registration_three_entry_points` 断言 4）
- [x] **R2-F003 登记**：plan `contract_pack.test_debt` 追加第 5 条，deadline 2026-08-31
- [x] **R1 F003 残余清理**：plan Task 4 测试契约段"alembic heads"改"alembic current"（commit `6717a89`）
- [x] **scope 诚实**：本 plan 不含 service/router/API 端点变更；governance 派生产物 (modules.yaml/dependency-graph.md/debt-report.md) 按 hook 要求重新聚合
- [ ] **Gate 2 code review R1 PASS**：本次审查本身（未完成——本文件生成时 R1 尚未启动）

---

## 自查

- 三入口 Grade import 实在:
  构造输入: 检查 env.py/app.py/conftest.py 是否各含 `edu_cloud.models.grade` 或 `Grade` 字样
  运行命令: `grep -c "models.grade" /home/ops/projects/edu-cloud/alembic/env.py /home/ops/projects/edu-cloud/src/edu_cloud/api/app.py /home/ops/projects/edu-cloud/tests/conftest.py`
  实际输出:
  ```
  /home/ops/projects/edu-cloud/alembic/env.py:1
  /home/ops/projects/edu-cloud/src/edu_cloud/api/app.py:1
  /home/ops/projects/edu-cloud/tests/conftest.py:1
  ```
  结论: 三入口各 1 处 Grade import 命中，ORC-S1C-005 断言满足

- 三入口 TeachingPlan import 实在（R2-F001 修复验证）:
  构造输入: 检查 env.py/app.py/conftest.py 是否各含 `edu_cloud.models.teaching_plan` 字样
  运行命令: `grep -c "edu_cloud.models.teaching_plan" /home/ops/projects/edu-cloud/alembic/env.py /home/ops/projects/edu-cloud/src/edu_cloud/api/app.py /home/ops/projects/edu-cloud/tests/conftest.py`
  实际输出:
  ```
  /home/ops/projects/edu-cloud/alembic/env.py:1
  /home/ops/projects/edu-cloud/src/edu_cloud/api/app.py:1
  /home/ops/projects/edu-cloud/tests/conftest.py:1
  ```
  结论: 三入口各 1 处独立 TeachingPlan import 命中，R2-F001 修复落地

- 全量 pytest baseline 21 failed 保持:
  构造输入: S1-C 实施后跑全套，对比 baseline（2102/21/23 @ 20:14）
  运行命令: `.venv/bin/python -m pytest --tb=no -q 2>&1 | tail -1`
  实际输出:
  ```
  21 failed, 2143 passed, 23 skipped, 33 warnings in 890.62s (0:14:50)
  ```
  结论: 21 failed 保持零新增；+41 passed 全部为 S1-C 新增 test（9+8+9+15），符合 Gate G1 验收条件

- Alembic linear chain 单 head:
  构造输入: 查询脚本目录 DAG 终点
  运行命令: `.venv/bin/alembic heads`
  实际输出:
  ```
  f311eb126798 (head)
  ```
  结论: 单 head 无分叉，ORC-S1C-001 满足

- Downgrade 回滚用 alembic current 判定（R1 F003 修正）:
  构造输入: 本地 SQLite DB 上 upgrade head 后执行 downgrade -1
  运行命令: `DATABASE_URL="sqlite+aiosqlite:////tmp/tmp_s1c_smoke.db" .venv/bin/alembic downgrade -1 && DATABASE_URL="..." .venv/bin/alembic current`
  实际输出:
  ```
  INFO  [alembic.runtime.migration] Running downgrade f311eb126798 -> a88094ee4ea6, s1c_admin_schema
  a88094ee4ea6
  ```
  结论: 回滚后 current='a88094ee4ea6'，R1 F003 修正后的判定口径准确（不是 alembic heads）

- models/__init__.py 字节级不变（R2-F002 INV-S1C-008 升级）:
  构造输入: S1-C 实施后重新计算 __init__.py 的 SHA256
  运行命令: `sha256sum /home/ops/projects/edu-cloud/src/edu_cloud/models/__init__.py`
  实际输出:
  ```
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  /home/ops/projects/edu-cloud/src/edu_cloud/models/__init__.py
  ```
  结论: SHA256 等于空文件锚点，ORC-S1C-005 "零 __init__.py 依赖"不可绕过

---

## 语义回归自检

本 plan `## semantic_regression` 段声明 5 条 ORC（state_machine + resource_path 风险域）。逐条核验：

| ORC | Rule 要点 | 验证方式 | 结果 |
|---|---|---|---|
| ORC-S1C-001 | down_revision='a88094ee4ea6' | `test_migration_file_down_revision_matches_prev_head` 字符串精确匹配 + `test_migration_chain_head_is_single` alembic heads 单行 | ✓ |
| ORC-S1C-002 | Class.grade/grade_number 字符匹配保持 | `test_class_legacy_grade_fields_unchanged`（ORM 层）+ `test_classes_grade_id_added_legacy_unchanged`（migration 层）断言 VARCHAR(50) NOT NULL + INTEGER NULLABLE | ✓ |
| ORC-S1C-003 | TeachingPlan FK 目标 ⊂ {schools,grades,users} | `test_teaching_plans_table_schema_complete` + ORM/migration 层 6 个独立 FK 存在断言 | ✓ |
| ORC-S1C-004 | FK 类型统一 String(36) + TD-S1A-002 闭环 | `test_bank_questions_grade_id_is_string36_with_fk` + `test_all_grade_id_fks_are_string36` | ✓ |
| ORC-S1C-005 | ORM 注册走三入口，零 __init__.py 依赖 | `test_orm_registration_three_entry_points` 三入口 Grade+TeachingPlan 各断言 + `__init__.py` SHA256 字节锚点 | ✓ |

未观察到任何 ORC 违反。本 plan 影响面 state_machine（linear chain 环序 + migration 可逆性）与 resource_path（FK 类型一致性影响消费侧 query path），两维度均有专项 test 锚定。
