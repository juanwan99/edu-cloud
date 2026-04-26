---
type: plan
topic: haofenshu-s1-admin
baseline_command: .venv/bin/python -m pytest --tb=no -q
baseline_verified_at: 2026-04-24T20:14:00+08:00
baseline_count: 2102 passed / 21 failed / 23 skipped (post-S1-A @ commit c155ab5 实测 2026-04-24T20:14，旧记录 2079 passed / 22 failed / 1 error 为 S1-A review 时点 17:27)
baseline_method: pytest
task_tier: T3
parent_topic: haofenshu-s1-l1-data-layer
parent_design: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md
parent_plan: docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan.md
linear_chain_prev: haofenshu-s1-bank (S1-A T2 slug a88094ee4ea6)
---

> **⚠️ Baseline 诚实披露**（L015 反虚假完成）：当前 HEAD（`c155ab5` conduct 批次 1 收尾，S1-A 已闭环 @ `86b4ca5`）baseline 2026-04-24T20:14 实测 **2102 passed / 21 failed / 23 skipped**（pre-S1-A 既有技术债，见 S1-A plan §Deferred 第 7 条；较 S1-A plan R1 时点 17:27 的 `2079 / 22 failed / 1 error` 因新 S1-A 测试落地 + flaky 收敛变化）。S1-C Gate 只要求"不新增 failure + 新测试全绿"，不承担既有技术债处置。

# haofenshu-s1-admin Implementation Plan (S1-C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 edu-cloud 补齐 parent design §4.1 deliverables **1.3 / 1.4 / 1.5**：新建 `grades` 独立表 + `classes.grade_id` FK（守旧 `grade/grade_number` 字段不动），新建 `teaching_plans` 骨架表（仅 schema，不含任何 lesson_plans 等未建表的外部 FK），新增 `PaperAccessLevel` 枚举常量。**同条 migration 闭环 TD-S1A-002**（S1-A 遗留，2026-05-08 deadline）：`batch_alter_table + alter_column + create_foreign_key` 给 `bank_questions.grade_id` 补齐 FK constraint 到 `grades.id`，同步修正 S1-A 期 Integer 类型 → String(36) 的 UUID 类型（IdMixin 全项目一致性）。

**Architecture:** Linear chain 第 2 环，`down_revision='a88094ee4ea6'`（S1-A T2 slug 实测，commit `a3731d6`；实施前 Task 4 Step 4.1 先跑 `alembic heads` 再核实，若 chain 已被后续 session 推进取最新 head）。所有 DDL 用 `batch_alter_table` 包装以保持 SQLite 测试 + PostgreSQL 生产双方言中立（参考 `docs/plans/2026-04-13-migration-gate-repair-design.md` 6 migration 修复教训）。新表用独立 `create_table`，FK 字段类型统一 `String(36)` UUID（IdMixin 约定）。ORM 注册走 `alembic/env.py` + `src/edu_cloud/api/app.py` + `tests/conftest.py` 三处显式 import（R1 F001 修正：测试期 `Base.metadata.create_all()` 入口独立于 app.py），不依赖 `src/edu_cloud/models/__init__.py`（已验证是空文件，见 E-003）。

**Tech Stack:** Python 3.11 / SQLAlchemy 2.0 async / Alembic 1.13 / Pydantic v2 / pytest-asyncio / SQLite（测试）+ PostgreSQL（生产，asyncpg）

**Parent Design:** [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md) §4.1 (deliverables 1.3/1.4/1.5) + §8.2 (跨层共享实体 Grade / TeachingPlan / PaperAccessLevel) + §12 (ORC-001~005)

**Parent Plan Review:** [2026-04-24-haofenshu-s1-l1-data-layer-plan-review.md](./2026-04-24-haofenshu-s1-l1-data-layer-plan-review.md) R1 FAIL（9 findings，路径 A 拆 topic 方案落地本 plan 的 F002/F004/F005/F006/F008 修复）

**Deferred to S1-D:** F009（`subject_code` vs `course_code` 参数语义）不归本 S1-C scope（本 plan 无新端点）；S1-D `StudentProfileView` VO plan 再处置。

---

## Evidence Block

### Evidence: E-001 — linear chain 第 2 环锚点（基线 `a88094ee4ea6`）

**decision**: S1-C migration 的 `down_revision` 字段必须是 `'a88094ee4ea6'`（S1-A T2 实际落地 slug）。严禁其他值。

**evidence_refs**:
- `.venv/bin/alembic heads` 实测输出（2026-04-24T20:12 本会话调研 Task #3）：
  ```
  a88094ee4ea6 (head)
  ```
- `alembic/versions/a88094ee4ea6_s1a_bank_question_extension.py:15-16`：
  ```python
  revision: str = 'a88094ee4ea6'
  down_revision: Union[str, Sequence[str], None] = 'a8c7d2e4f135'
  ```
- 完整链路（S1-A 后向 base 追溯）：`a88094ee4ea6 (S1-A T2) ← a8c7d2e4f135 (conduct updated_at + FK indexes) ← 36e25241e55d ← e241e1568792 ← 874f6f9c14cc (merge) ← (45c9d83d780e, f7a3b2c1d456)`
- 负面断言：grep 其他潜在 head
  ```bash
  grep -l "down_revision:.*None" alembic/versions/*.py
  ```
  仅返回 `8b3f659c1a2a` / `f7a3b2c1d456`（早期分支根，非 head；不构成 linear chain 竞争节点）

**Q1**: evidence_source: code-read + command-output, evidence_state: verified
**Q2_excluded**:
- "绑到 `a8c7d2e4f135`（S1-A 的 down_revision）": 反证路径: 这是 S1-A T2 的前一环，绑它会和 `a88094ee4ea6` 并列形成 2 heads，`alembic heads` 会返回 2 行破坏 linear chain。
- "绑到 plan review 时的旧 head `36e25241e55d`": 反证路径: 该 head 已被 `a8c7d2e4f135` → `a88094ee4ea6` 推进两环，绑它会产生多 head。
**impact_scope**: module (alembic-migrations)
**unknowns**:
  - 实施前当前 head 是否已被新 session 推进（Task 4 Step 4.1 再跑 `alembic heads` 核实，取当时最新 head 为准；若已漂移到 `a88094ee4ea6` 之后的新 slug，按"最新 head"替换）
**followup_spike**: Task 4 Step 4.1 强制复跑 `alembic heads`

---

### Evidence: E-002 — IdMixin 全项目 UUID String(36) 约定（FK 类型冲突依据）

**decision**: `grades.id` 用 `String(36)` UUID（Base + IdMixin 约定），因此 `classes.grade_id` / `teaching_plans.grade_id` / `bank_questions.grade_id` 的 FK 字段全部采用 `String(36)`。S1-A 期 `bank_questions.grade_id` 误用 `Integer` 是偏差，S1-C migration 同步 alter 回 `String(36)`（数据迁移零成本——列全为 NULL）。

**evidence_refs**:
- `src/edu_cloud/models/base.py:11-14` IdMixin 定义：
  ```python
  class IdMixin:
      id: Mapped[str] = mapped_column(
          String(36), primary_key=True, default=lambda: str(uuid.uuid4())
      )
  ```
- `src/edu_cloud/modules/bank/models.py:41` S1-A 现状：`grade_id: Mapped[int | None] = mapped_column(Integer, default=None)`
- `src/edu_cloud/modules/student/models.py:15-18` 既有 FK 用 `String(36)`：
  ```python
  head_teacher_id: Mapped[str | None] = mapped_column(
      String(36), ForeignKey("users.id"), default=None
  )
  school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
  ```
- S1-A bank plan test_debt 第 2 条（`docs/plans/2026-04-24-haofenshu-s1-bank-plan.md:234-236`）：
  > "bank_questions.grade_id 字段未加 ForeignKey('grades.id') constraint。reason: grades 表归 S1-C scope，当前仓库不存在该表；S1-A 先加 grade_id Integer nullable 占位，S1-C migration 用 batch_alter_table + create_foreign_key 补齐。deadline: 2026-05-08"
- 数据零成本证据：
  ```bash
  grep -c "grade_id" tests/test_services_exam/test_bank_service.py
  ```
  S1-A 已加 Integer 字段但无生产数据写入（新字段全 nullable，S1-A 测试后未发布）

**Q1**: evidence_source: code-read + test-debt-doc, evidence_state: verified
**Q2_excluded**:
- "grades.id 用 Integer（顺应 S1-A bank_questions.grade_id 的 Integer）": 反证路径: 新建跨模块共享表应沿用 IdMixin UUID 约定（grep `class.*IdMixin` 在 `src/edu_cloud/models/*.py` + `src/edu_cloud/modules/*/models.py` 共见 60+ 处印证），与既有 schools/users/classes 等核心业务表保持一致；仓库中少量历史 Integer PK 表（`analytics/models.py` / `menu/models.py` / `knowledge_tree/models.py`）为遗留分析/平台表的设计，不作为 S1-C Grade 类型参照（这些遗留表独立成域，无跨表 FK 约束压力）。R1 F007 修正：不再用"全项目零 Integer PK"这种失真的负面断言支撑决策。
- "保留 bank_questions.grade_id 为 Integer，不加 FK constraint": 反证路径: 违反用户要求"闭环 TD-S1A-002"；且 S1-A plan test_debt 第 2 条 deadline 2026-05-08 明确要求本 S1-C scope 落地。
**impact_scope**: module (bank + grades)
**unknowns**: none

---

### Evidence: E-003 — ORM 注册链路（F002 repair 方向）

**decision** (R2-F001 修复后的最终形态): Grade 放 `src/edu_cloud/models/grade.py`（跨模块共享表，`orm-placement.md:§7` 反模式"跨模块共享表下沉到某模块"）。**TeachingPlan 放 `src/edu_cloud/models/teaching_plan.py`**（同样跨模块共享 platform-level，与 Grade 策略一致；R2-F001 修正前曾规划放 `modules/calendar/models.py`，但 Planner 误读了 app.py/env.py 的 `import edu_cloud.models.calendar` 语义——那条 import 加载的是 `models/calendar.py` CalendarEvent/NotificationRule，不触发 `modules/calendar/models.py` 加载）。**注册方式**：`alembic/env.py` + `src/edu_cloud/api/app.py` + `tests/conftest.py` 三处**各加 Grade + TeachingPlan 两行独立 import**；`src/edu_cloud/models/__init__.py` **不**参与（已验证空文件，R2-F002 INV-S1C-008 以 SHA256 字节锚点保障）。

**evidence_refs**:
- `src/edu_cloud/models/__init__.py` 空文件证据：SHA256 = `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空字节 SHA256 锚点，R2-F002 INV-S1C-008）
- `alembic/env.py:85-87` 显式 import 列表末尾，S1-C 追加 2 行：`from edu_cloud.models.grade import Grade` + `from edu_cloud.models.teaching_plan import TeachingPlan`
- `src/edu_cloud/api/app.py:65-67` 启动 lifespan 内 import 列表末尾，S1-C 追加 2 行：`import edu_cloud.models.grade` + `import edu_cloud.models.teaching_plan`
- `tests/conftest.py:47-49` 测试期 `Base.metadata.create_all()` 入口 import 列表末尾，S1-C 追加 2 行：`import edu_cloud.models.grade` + `import edu_cloud.models.teaching_plan`
- `docs/arch/orm-placement.md:§7` 反模式：
  - "跨模块共享表下沉到某模块 → 上浮到 `models/`" → Grade 和 TeachingPlan 都被 S2/S3/S4 多模块消费（design §8.2），符合"跨模块共享"
  - "模块内 ORM 文件起非 `models.py` 的名字" → 反模式 → 不新建 `teaching_plan_models.py`（F002 parent review L65-67 否决）
- `src/edu_cloud/modules/calendar/models.py:1-3` 现状（re-export stub，**保持不动**）：
  ```python
  """Calendar 模块模型 — CalendarEvent + NotificationRule + Notification（从 models/ 合入）。"""
  from edu_cloud.models.calendar import CalendarEvent, NotificationRule  # noqa: F401
  from edu_cloud.models.notification import Notification  # noqa: F401
  ```
  TeachingPlan 不追加到此文件（R2-F001 修正）。

**Q1**: evidence_source: code-read + doc-read + runtime-verified, evidence_state: verified (R2-F001 修复后 Gate 2 Code Review R1 PASS 独立复核)
**Q2_excluded**:
- "TeachingPlan 放 `modules/calendar/teaching_plan_models.py`（parent L1 plan Task 4 的建议）": 反证路径: parent plan review F002 L65-67 + `orm-placement.md:§7` 反模式"模块内 ORM 文件起非 models.py 名字"双否决。
- "Grade 放 `modules/student/models.py`（随 Class）": 反证路径: Grade 被 S2 组卷引擎 / S4 教学计划 / S3 学情画像多模块消费（design §8.2），不是学生模块专用；按 orm-placement.md §7"跨模块共享表"必须上浮。
- "TeachingPlan 追加到 `modules/calendar/models.py` 只在 conftest.py 加 import"（R1 原方案，R2-F001 HIGH 否决）: 反证路径: app.py/env.py 中的 `import edu_cloud.models.calendar` 加载的是 models/calendar.py，不触发 modules/calendar/models.py；此路径下 TeachingPlan 只在测试期注册，生产 Base.metadata.create_all 会遗漏——必须三入口独立 import 才 fail-closed。
**impact_scope**: cross-module (bank + student + calendar + alembic + api)
**unknowns**: none

---

### Evidence: E-004 — Class 守旧字段保留（ORC"不动守旧字段"依据）

**decision**: Class 既有 `grade: String(50) NOT NULL` + `grade_number: Integer nullable` 守旧字段**一字不动**。S1-C 仅新增 `grade_id: String(36) nullable FK → grades.id`，3 字段并存实现渐进式迁移（design §4 1.3 + parent L1 plan Task 3 Step 3.5 明确"同时保留原 Class.grade 字符串列以支持渐进式迁移"）。

**evidence_refs**:
- `src/edu_cloud/modules/student/models.py:12-14` Class 现状：
  ```python
  name: Mapped[str] = mapped_column(String(100))
  grade: Mapped[str] = mapped_column(String(50))
  grade_number: Mapped[int | None] = mapped_column(Integer, default=None)
  ```
- `grade` 字段 NOT NULL：确认 SQL 层无 default，但所有现有数据行已写入具体值（seed demo 数据 36 班 / 生产数据同）
- 负面断言：grep 全项目所有引用 `Class.grade` / `ClassGroup.grade`：
  ```bash
  grep -rn "\.grade\b" src/edu_cloud/ --include="*.py" | grep -v "grade_id\|grade_number\|grade_leader"
  ```
  预期命中至少 5 处消费者（classes API / students import-export / dashboard 聚合）——证明改动守旧字段会破坏大量代码
- parent L1 plan Task 3 Step 3.5 docstring（`docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan.md:372-375`）：
  > "Class.grade_id 为新 FK，同时保留原 Class.grade 字符串列以支持渐进式迁移。"
- ORC-001（parent design §12）：L1 数据模型冻结后上层 Sprint 不得扩展 L1 字段——反过来说，S1 自己可以新增但不应破坏"上层已在消费的字段"。守旧 grade 字段被上层广泛消费。

**Q1**: evidence_source: code-read + grep, evidence_state: verified
**Q2_excluded**:
- "把 grade 字段 deprecate / 改 nullable / 迁数据到 grades 表后删 grade": 反证路径: 触发多处调用侧改动，违反拆 topic scope（S1-C 只做 schema 新增）；数据迁移脚本属 T3 独立任务，非本 plan。
**impact_scope**: module (student)
**unknowns**:
  - 后续 Sprint 何时弃用 grade 字段（不归 S1-C，归 S2 或 S4 后续补丁）

---

### Evidence: E-005 — teaching_plans 骨架不含外部 FK（ORC"骨架不含未建表 FK"依据）

**decision**: `teaching_plans` 表仅含 4 个 FK：`school_id → schools.id` / `grade_id → grades.id`（本 S1-C 新建）/ `created_by → users.id` / `subject_code: String`（非 FK，业务编码字符串）。**不含** `lesson_plan_id` / `resource_id` / `course_id` 等 design §7.1 4.3 S4 才建的表引用。

**evidence_refs**:
- parent design §4.1 1.4（`docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md:164`）：
  > "`teaching_plans` 表骨架（仅 schema） | 附录 C Gap#6 + `haofenshu-clone/server/config/schema.sql:284-302`"
- parent L1 plan Task 4 骨架定义（`docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan.md:505-517`）：
  ```python
  class TeachingPlan(Base, IdMixin, TimestampMixin):
      __tablename__ = "teaching_plans"
      __table_args__ = (UniqueConstraint("school_id", "subject_code", "grade_id", "semester", ...),)
      school_id: FK schools.id
      subject_code: String(50)  # not FK
      grade_id: FK grades.id    # new in S1-C
      semester: String(30)
      weeks_json: JSON nullable
      created_by: FK users.id
  ```
  4 个 FK 全部指向已存在或本 plan 新建的表，**零**指向未建表。
- design §8.2 跨层共享（`docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md:352`）：
  > "`TeachingPlan`（骨架） | 1.4 | 2.2 ChapterCompose / 4.3"
  S4 4.3 `calendar.teaching_plan_service` 才扩展业务字段（lesson_plans / resources 等），S1 阶段明确不触及。
- 负面断言：grep "lesson_plans" / "resources" 表是否存在：
  ```bash
  grep -rn "lesson_plans\|__tablename__.*=.*[\"']resources[\"']" src/edu_cloud/ --include="*.py"
  ```
  零匹配 → 证明这些表确实不存在，FK 指向会触发 migration autogenerate 错误。

**Q1**: evidence_source: code-read + doc-read + negative-grep, evidence_state: verified
**Q2_excluded**:
- "顺手加 lesson_plan_id FK 为 S4 预留": 反证路径: lesson_plans 表 S4 才建，本 plan 加 FK autogenerate 会抛"referenced table 'lesson_plans' not found"；即使注释掉 FK 只保留 String 列，也违反 ORC-005 "Sprint Gate 串行不可并跳"（S4 未启动）。
**impact_scope**: module (calendar)
**unknowns**: none

---

## semantic_regression（ORC from parent design §12）

本 S1-C 实施期间**不可违反**以下 ORC。Executor 每完成 Task 必须自审对应 ORC；codex-review code 阶段会独立复核。

**required**: true
**risk_tags**: [state_machine, resource_path]
  - state_machine: linear chain 环序 + migration 可逆性
  - resource_path: FK 类型一致性（string vs int）影响所有消费侧 query path

### ORC-S1C-001: linear chain 第 2 环约束

- **Rule**: S1-C migration 的 `down_revision` 字段必须等于字符串 `'a88094ee4ea6'`（S1-A T2 slug）。实施前 Task 4 Step 4.1 跑 `alembic heads` 再核实，若已漂移到新 head 按当时最新值替换，但禁止绑到 `a8c7d2e4f135`（S1-A 的前一环，会产生 2 heads）或 `36e25241e55d`（更早的历史 head）。
- **Why**: E-001 根因。`a88094ee4ea6` 是 S1-A 落地的 head；绑错会让 `alembic heads` 返回多行，破坏 linear chain（parent review F001 教训）。
- **How to apply**: Task 5 smoke test `test_migration_file_down_revision_matches_prev_head` 字符串匹配断言；Task 4 `alembic heads` 三阶段 smoke（stamp→upgrade→downgrade→upgrade）每步确认单 head。
- **Violation reporter**: Task 5 `test_migration_chain_head_is_single` 跑 `alembic heads` subprocess，若 down_revision 绑错会返回 2 行 → assert 失败。
- **type**: forbidden_strategy
- **protects**: [state_machine]
- **verification**: pending_test
- **statement**: S1-C migration 文件 head 处 `down_revision` 字符串字面值必须等于 S1-A T2 slug（当前实测 `'a88094ee4ea6'`），严禁其他历史 head 或 base revision（待 Task 5 落地 `tests/test_alembic_s1c_admin.py::test_migration_file_down_revision_matches_prev_head`）

### ORC-S1C-002: Class 守旧字段一字不动

- **Rule**: `src/edu_cloud/modules/student/models.py` 的 `Class` 类中 `grade: Mapped[str] = mapped_column(String(50))` 和 `grade_number: Mapped[int | None] = mapped_column(Integer, default=None)` 两行**精确字符匹配保持**，禁止改类型、nullability、默认值、或加 deprecated 注释。只**追加**新字段 `grade_id`。
- **Why**: E-004 根因。grade 字段被项目多处消费，改动会触发大量回归；design §4 1.3 + parent L1 plan Task 3 明确"守旧字段与新 FK 并存"的渐进式迁移路径。
- **How to apply**:
  1. Task 1 在 `Class` 类中 `school_id` 行之前、`grade_number` 行之后追加 `grade_id` 一行，禁改 `grade` / `grade_number` 两行
  2. Task 5 smoke test `test_class_legacy_grade_fields_unchanged` 断言 `Class.__table__.columns['grade'].type.length == 50 and nullable is False`
- **Violation reporter**: `git diff -U0 src/edu_cloud/modules/student/models.py` 预期仅新增行，不应含 `-` 删除行对 `grade:` / `grade_number:` 两行。
- **type**: state_invariant
- **protects**: [resource_path]
- **verification**: pending_test
- **statement**: S1-C 出口处 `Class.__table__` 包含 `grade: VARCHAR(50) NOT NULL` + `grade_number: INTEGER NULLABLE` + `grade_id: VARCHAR(36) NULLABLE FK→grades.id` 三列并存，前两列类型/nullability 与 S1-C 入口一致（待 Task 5 落地 `tests/test_alembic_s1c_admin.py::test_class_legacy_grade_fields_unchanged`）

### ORC-S1C-003: teaching_plans 骨架零外部未建表 FK

- **Rule**: `TeachingPlan.__table__.foreign_keys` 只允许指向本 plan 之前已存在或本 plan 新建的 4 张表之一：`schools.id` / `grades.id` / `users.id`（FK 字段仅 3 个，外加 `subject_code: String(50)` 非 FK）。严禁 `lesson_plans` / `courses` / `resources` / `course_resources` 等 S4 才建的表 FK。
- **Why**: E-005 根因 + ORC-005 Sprint Gate 串行。设 S4 表 FK 会触发 autogenerate "referenced table not found" 或在运行时引用链断裂。
- **How to apply**: Task 2 TeachingPlan 定义中 `ForeignKey(...)` 调用必须字符串匹配 `schools.id` / `grades.id` / `users.id` 之一；Task 5 smoke test `test_teaching_plans_table_schema_complete`（越界综合断言）+ `test_teaching_plans_{schools,grades,users}_fk_exists` 三个独立 FK 断言（R2-F002 拆分）遍历 `TeachingPlan.__table__.foreign_keys` 精确断言。
- **Violation reporter**: Task 5 `test_teaching_plans_table_schema_complete` 枚举所有 FK target 集合 `⊂ {"schools.id", "grades.id", "users.id"}`，任何越界 FK 立即 fail；`test_teaching_plans_users_fk_exists`（R2-F002 核心）防止漏 `created_by → users` FK 的"子集断言"假绿。
- **type**: forbidden_strategy
- **protects**: [state_machine]
- **verification**: existing_test
- **test_ref**: `tests/test_alembic_s1c_admin.py::test_teaching_plans_table_schema_complete` + `::test_teaching_plans_schools_fk_exists` + `::test_teaching_plans_grades_fk_exists` + `::test_teaching_plans_users_fk_exists`
- **statement**: S1-C 出口处 TeachingPlan 表所有 ForeignKey 的 target_fullname 集合 ⊂ {"schools.id", "grades.id", "users.id"}，且 schools/grades/users 三目标各至少有 1 FK 指向（R2-F002 修复后）

### ORC-S1C-004: FK 类型统一 String(36) + TD-S1A-002 闭环

- **Rule**: `grades.id` / `classes.grade_id` / `teaching_plans.grade_id` / `bank_questions.grade_id` 全部 `String(36)`。S1-C migration 必须包含 `batch_alter_table('bank_questions') + alter_column('grade_id', type_=Integer→String(36))` + `create_foreign_key('fk_bank_questions_grade_id', ..., ['grade_id'], ['id'])` 两步闭环 TD-S1A-002。
- **Why**: E-002 根因。IdMixin 全项目一致性；S1-A 期 Integer 是偏差，数据零成本（列全 NULL）。TD-S1A-002 deadline 2026-05-08 由 S1-A plan 明确交接到 S1-C。
- **How to apply**:
  1. Task 1 Grade ORM 用 Base+IdMixin（隐式 String(36) id）；Class.grade_id 用 `String(36) FK`
  2. Task 3 bank ORM 修正 `grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None)`
  3. Task 4 migration `batch_alter_table('bank_questions')` 内 `alter_column('grade_id', existing_type=sa.Integer(), type_=sa.String(length=36), existing_nullable=True)` + `create_foreign_key(...)`
  4. Task 5 smoke test `test_bank_questions_grade_id_is_string36_with_fk` 断言 `cols['grade_id']['type'].length == 36` + `fk.target_fullname == 'grades.id'`
- **Violation reporter**: smoke test 在 upgrade 后 inspect bank_questions 列类型；若仍是 INTEGER 或缺 FK → fail。
- **type**: state_invariant
- **protects**: [resource_path]
- **verification**: pending_test
- **statement**: S1-C 出口处 bank_questions.grade_id 列类型为 VARCHAR(36) + 带 ForeignKey 约束 target_fullname='grades.id'；所有 grade_id 相关 FK 字段类型统一（待 Task 5 落地 `tests/test_alembic_s1c_admin.py::test_bank_questions_grade_id_is_string36_with_fk` + `::test_all_grade_id_fks_are_string36`）

### ORC-S1C-005: ORM 注册走 env.py + app.py + tests/conftest.py 三处同步，零 __init__.py 依赖

- **Rule** (R2-F001 修复后最终形态): S1-C 新增 Grade + TeachingPlan 两个模型，三处入口**各加两行独立 import**：
  1. `alembic/env.py` 加 `from edu_cloud.models.grade import Grade  # noqa: F401` + `from edu_cloud.models.teaching_plan import TeachingPlan  # noqa: F401`
  2. `src/edu_cloud/api/app.py` 加 `import edu_cloud.models.grade  # noqa: F401` + `import edu_cloud.models.teaching_plan  # noqa: F401`
  3. `tests/conftest.py` 加 `import edu_cloud.models.grade  # noqa: F401` + `import edu_cloud.models.teaching_plan  # noqa: F401`
  禁止新增 `src/edu_cloud/models/__init__.py` 的 import（空文件不参与注册，以 SHA256 字节锚点保障——INV-S1C-008）。
- **Why**: F002 parent review + R1 F001 + R2-F001 根因（E-003）。`models/__init__.py` 空文件不被引用；三条独立入口分别驱动 Alembic autogenerate / 应用启动 `Base.metadata.create_all()` / 测试期 `Base.metadata.create_all()`。R2-F001 修正：TeachingPlan 不再通过 `modules/calendar/models.py` 间接注册，必须独立 import 以 fail-closed。
- **How to apply**: Task 1 + Task 2 最终 diff 合起来三入口各含 Grade + TeachingPlan 两行 import；禁止修改 `src/edu_cloud/models/__init__.py`。
- **Violation reporter**: Task 5 smoke `test_orm_registration_three_entry_points` grep 三处各 Grade + TeachingPlan import 各命中（共 6 条 import）；`models/__init__.py` SHA256 字节锚点比对。
- **type**: forbidden_strategy
- **protects**: [state_machine]
- **verification**: existing_test
- **test_ref**: `tests/test_alembic_s1c_admin.py::test_orm_registration_three_entry_points`
- **statement**: S1-C 出口处 `src/edu_cloud/models/__init__.py` SHA256 = `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（空文件锚点）；`alembic/env.py` + `src/edu_cloud/api/app.py` + `tests/conftest.py` 三处各含 Grade + TeachingPlan 两行独立 import（R2-F001 修复后的三入口 fail-closed 护栏）

---

## Contract Pack

```yaml
contract_pack:
  # 字段命名严格对齐 ~/.claude/config/contract-pack-schema.md 真源
  # verification 枚举: existing_test / pending_test / uncovered
  # test_ref 仅限 existing_test（pending_test 把待验证测试名写入 statement 尾部）
  invariants:
    - id: INV-S1C-001
      statement: "upgrade 后 grades 表存在且含列 {id: VARCHAR(36) PK, school_id: VARCHAR(36) NOT NULL FK→schools.id, name: VARCHAR(50) NOT NULL, grade_level: INTEGER NULLABLE, xueduan: VARCHAR(20) NULLABLE, sort_order: INTEGER NOT NULL default 0, created_at: TIMESTAMP NOT NULL, updated_at: TIMESTAMP NOT NULL}，且含 UniqueConstraint(school_id, name)；R2-F002 修复：补 school_id→schools.id FK 独立断言 + sort_order server_default='0' 独立断言"
      verification: existing_test
      test_ref: "tests/test_alembic_s1c_admin.py::test_grades_table_created_with_expected_schema + ::test_grades_unique_constraint"

    - id: INV-S1C-002
      statement: "upgrade 后 teaching_plans 表存在且含 9 列 {id, school_id FK→schools.id, subject_code VARCHAR(50) NOT NULL, grade_id FK→grades.id NULLABLE, semester VARCHAR(30) NOT NULL, weeks_json JSON NULLABLE, created_by FK→users.id NULLABLE, created_at, updated_at}；R2-F002 修复后拆成 3 个独立 FK 断言（schools/grades/users 各断言 1 个 FK 存在）+ 1 个越界综合断言（FK 目标 ⊂ {schools,grades,users} 禁 lesson_plans 等未建表引用）；且含 UniqueConstraint(school_id, subject_code, grade_id, semester)"
      verification: existing_test
      test_ref: "tests/test_alembic_s1c_admin.py::test_teaching_plans_table_schema_complete + ::test_teaching_plans_schools_fk_exists + ::test_teaching_plans_grades_fk_exists + ::test_teaching_plans_users_fk_exists + ::test_teaching_plans_unique_constraint"

    - id: INV-S1C-003
      statement: "upgrade 后 classes 表新增 grade_id VARCHAR(36) NULLABLE FK→grades.id，同时守旧字段 grade: VARCHAR(50) NOT NULL 和 grade_number: INTEGER NULLABLE 精确保持"
      verification: existing_test
      test_ref: "tests/test_alembic_s1c_admin.py::test_classes_grade_id_added_legacy_unchanged"

    - id: INV-S1C-004
      statement: "upgrade 后 bank_questions.grade_id 列类型为 VARCHAR(36) 且含 ForeignKey 约束 target_fullname='grades.id'（闭环 TD-S1A-002；S1-A 入口处是 INTEGER 无 FK，S1-C migration 通过 batch_alter_table alter_column + create_foreign_key 完成类型迁移 + FK 绑定）"
      verification: existing_test
      test_ref: "tests/test_alembic_s1c_admin.py::test_bank_questions_grade_id_is_string36_with_fk + ::test_all_grade_id_fks_are_string36"

    - id: INV-S1C-005
      statement: "PaperAccessLevel 枚举严格有 3 个成员值 {teacher_private, school_shared, district_shared}，且实例是 str+Enum 可参与字符串比较（非逻辑镜像断言，通过 round-trip 构造/序列化/反序列化验证，参见 F006 修正）"
      verification: existing_test
      test_ref: "tests/test_models/test_paper_access_level.py::test_paper_access_level_roundtrip_via_value + ::test_paper_access_level_has_exactly_three_members + ::test_paper_access_level_rejects_unknown_value"

    - id: INV-S1C-006
      statement: "S1-C migration 文件 head 处 down_revision 字符串字面值等于 Task 4 Step 4.1 实测的 alembic heads 当前单 head（实际落地为 'a88094ee4ea6'，slug=f311eb126798；严禁绑定历史 head 'a8c7d2e4f135' 或 base revision None）"
      verification: existing_test
      test_ref: "tests/test_alembic_s1c_admin.py::test_migration_file_down_revision_matches_prev_head"

    - id: INV-S1C-007
      statement: "S1-C upgrade 后 `alembic heads` subprocess 输出过滤空行后恰好 1 行（linear chain 单 head，脚本目录层）；`alembic downgrade -1` 后 `alembic current` 输出等于 'a88094ee4ea6'（DB revision 层，R1 F003 修正：不用 heads 因它反映脚本目录不是 DB 状态）"
      verification: existing_test
      test_ref: "tests/test_alembic_s1c_admin.py::test_migration_chain_head_is_single + ::test_downgrade_restores_s1a_revision"

    - id: INV-S1C-008
      statement: "S1-C 出口处 src/edu_cloud/models/__init__.py SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'（空文件字节锚点，R2-F002 修复：从'0 非空行'升级为字节级对比）；alembic/env.py + src/edu_cloud/api/app.py + tests/conftest.py 三处各含 Grade + TeachingPlan 两行独立 import（R2-F001 修复：TeachingPlan canonical 挪到 models/teaching_plan.py 后必须独立 import，不再依赖 modules.calendar.models）"
      verification: existing_test
      test_ref: "tests/test_alembic_s1c_admin.py::test_orm_registration_three_entry_points"

  counter_examples:
    - id: CE-S1C-001
      scenario: "Task 4 误绑 down_revision='a8c7d2e4f135'（S1-A 的前一环 conduct updated_at + FK indexes），alembic upgrade head 后 heads 返回 2 行（S1-A slug + S1-C slug 并列）"
      tests_that_still_pass: "Task 1/2/3 的 ORM 属性 round-trip（Grade/TeachingPlan/PaperAccessLevel import + 字段存在）不依赖 alembic chain，依然通过；test_grades_table_created_with_expected_schema 若走 Base.metadata.create_all 而非 alembic 也可能通过"
      mitigation: "Task 5 test_migration_file_down_revision_matches_prev_head 字符串匹配断言 + test_migration_chain_head_is_single 跑 alembic heads subprocess 断言 1 行，任一都会捕获"

    - id: CE-S1C-002
      scenario: "Task 4 migration 给 teaching_plans 添 lesson_plan_id FK 指向 lesson_plans 表（S4 才建），autogenerate 本地跑不报错但 alembic upgrade 在 `op.create_foreign_key` 阶段失败或指向悬空表"
      tests_that_still_pass: "Task 2 TeachingPlan ORM 的 `test_teaching_plan_import_from_models` 和字段断言不检测 FK 数量（只检测 schools/users 存在）；pytest collection 不报错"
      mitigation: "Task 5 test_teaching_plans_table_schema_complete 枚举 TeachingPlan.__table__.foreign_keys 集合断言 ⊂ {'schools.id','grades.id','users.id'}，违反立即 fail；R2-F002 拆分后 test_teaching_plans_{schools,grades,users}_fk_exists 三个独立断言兜底防 '子集断言' 漏 created_by→users FK"

    - id: CE-S1C-003
      scenario: "Task 4 migration 只跑 create_foreign_key 不跑 alter_column，bank_questions.grade_id 保留 Integer 类型；migration 在 SQLite 上跑成功（SQLite 对 FK 类型宽松）但 PostgreSQL 或 smoke inspect 发现类型不一致"
      tests_that_still_pass: "Task 3 bank ORM 的 `test_bank_questions_grade_id_has_fk_to_grades` 若只断言 FK 存在不检查类型，会通过；现有 bank_service.py tests 不读 grade_id 类型"
      mitigation: "Task 5 test_bank_questions_grade_id_is_string36_with_fk 同时断言 type.length == 36 AND FK target_fullname == 'grades.id'，类型错位立即 fail；additionally test_all_grade_id_fks_are_string36 遍历四张表 grade_id 类型一致性"

    - id: CE-S1C-004
      scenario: "Task 5 PaperAccessLevel 测试写成逻辑镜像 `assert {lvl.value for lvl in PaperAccessLevel} == {'teacher_private','school_shared','district_shared'}`（parent L1 plan Task 5 Step 5.1 的 test_paper_access_level_all_values 正是此模式），enum 即使值漂移到 `{teacher_pr, school_sh, district_sh}` 只要集合相同测试也通过，缺少外部锚点"
      tests_that_still_pass: "所有 3 个旧断言（直接等值 / 集合相等 / 反序列化自值）依然通过；enum 名字可以任意改但通过 value 锚定测试"
      mitigation: "新增 test_paper_access_level_roundtrip_via_value 通过字符串 'teacher_private' 精确构造 PaperAccessLevel('teacher_private') 断言 is PaperAccessLevel.TEACHER_PRIVATE（反向 ser/de），其他 2 值同款；F006 修正——外部字符串→枚举 round-trip 能检测值漂移"

  risk_modules:
    - module: src/edu_cloud/models/grade.py
      reason: "Grade 新表 ORM 定义。表结构影响 S2 组卷 / S3 学情画像 / S4 教学计划三个 Sprint；UniqueConstraint(school_id, name) 错位会在 seed 数据阶段报 integrity error"

    - module: src/edu_cloud/models/teaching_plan.py
      reason: "TeachingPlan 骨架 ORM 新文件（R2-F001 修正：canonical 挪到 models/ 顶层 platform-level，与 Grade 策略一致）。表结构被 S4 4.3 calendar.teaching_plan_service 消费；UniqueConstraint(school_id, subject_code, grade_id, semester) 错位会在业务层 insert 时报 integrity error；三入口 import 缺失会让 Alembic autogenerate / 应用启动 create_all / 测试期 create_all 任一入口漏建表（R2-F001 修正）"

    - module: src/edu_cloud/modules/student/models.py
      reason: "Class 表加 grade_id 字段。ORC-S1C-002 禁改 grade / grade_number 两行；Task 5 git diff 守卫防止 executor 顺手改纯 string 字段（违反拆 topic scope）"

    - module: src/edu_cloud/modules/bank/models.py
      reason: "bank_questions.grade_id 类型从 Integer 改 String(36)（闭环 TD-S1A-002）。现有 bank_service 6 个测试不触 grade_id 列类型；若 autogenerate 漏改 ORM 层，migration 后运行时 type mismatch"

    - module: alembic/versions/{slug}_s1c_admin_schema.py
      reason: "Linear chain 第 2 环 migration。down_revision / create_table / batch_alter_table 多操作，单处写错阻塞 S1-B/S1-D；Task 4 三阶段 smoke + Task 5 migration smoke 双重验证"

    - module: alembic/env.py
      reason: "ORC-S1C-005 新增 1 行 Grade import。错位（拼错模块路径）会导致 Alembic autogenerate 找不到 Grade 元数据；Task 1 Step 1.7 grep 验证"

    - module: src/edu_cloud/api/app.py
      reason: "ORC-S1C-005 新增 1 行 Grade import。错位会导致应用启动 Base.metadata.create_all() 不建 grades 表，测试 fixture 加载 ClassGroup fixture 级联失败"

    - module: src/edu_cloud/modules/paper/constants.py
      reason: "PaperAccessLevel 新增常量模块（paper 模块下）。F006 要求避免逻辑镜像测试；错位（重名冲突/imported 但未被使用导致 pyflakes 警告）虽非功能 bug 但会污染 linting"

    - module: tests/test_alembic_s1c_admin.py
      reason: "S1-C 专属 migration smoke 新文件。若 subprocess env DATABASE_URL 传递错（scheme 错把 sqlite+aiosqlite 传给同步 alembic）会导致测试跑不起来，表现为 returncode != 0 即便 migration 本身正确"

  test_debt:
    - item: "Class.grade 字段废弃 / 数据从 grade 字符串迁移到 grade_id 外键"
      reason: "S1-C scope 固守 '守旧字段不动'（ORC-S1C-002），渐进式迁移路径由后续 Sprint 评估；需要 seed 数据对齐 + 上层消费者改造（classes API / students import-export / dashboard 聚合），单独 T3 任务"
      deadline: "2026-06-15"

    - item: "PaperAccessLevel 值域 DB CHECK 约束 或 SQLAlchemy Enum 列类型（应用层保证已足够 S1-C）"
      reason: "S1-C 只定义 Python 枚举常量，不涉及 DB 列；design §8.2 说枚举在 S4 4.2 paper.access_policy 消费时与 paper 表字段一起绑；S1-C 过早上 Enum 会和 S4 设计冲突"
      deadline: "2026-06-30"

    - item: "grades 表 seed 数据（各学校的年级列表，如高一/高二/高三 + grade_level/xueduan 填充）"
      reason: "seed 数据属业务配置，需校方输入/教务决策；S1-C 只建 schema，S4 4.3 TeachingPlanEditor 启动时由教务填入；或 S3 学情画像页上线前由运营批量导入"
      deadline: "2026-07-15"

    - item: "TeachingPlan 表业务服务（calendar.teaching_plan_service）+ router + 前端编辑器"
      reason: "S1-C 只建骨架表，design §7.1 4.3 明确归 S4 scope，S1-C 越权会违反 ORC-005（Sprint Gate 串行不可并跳）"
      deadline: "2026-08-31"

    - item: "Task 1/2/3 入口级验证（CLI/startup/service/API）—— Grade/TeachingPlan/PaperAccessLevel 三个 ORM 的用户可触达入口断言（目前 Task 1-3 入口全部是 import + 实例化 + __table__ introspection，属内部结构验证；Task 5 migration smoke 已通过 alembic subprocess 提供了部分 CLI 级入口覆盖，但 service/API 层入口缺位）"
      reason: "R2-F003 登记（manual_override 授权范围）：S1-C 是纯 data-layer plan 无新 service/router 端点；TeachingPlan service/router 归 S4 4.3 calendar.teaching_plan_service（同已有 test_debt 第 4 条），PaperAccessLevel 归 S4 4.2 paper.access_policy，Grade 的业务 API 归 S4 TeachingPlanEditor。S4 补业务时必须同步补入口级断言，不允许继续把 introspection 当作完整入口覆盖"
      deadline: "2026-08-31"
```

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/edu_cloud/models/grade.py` | **新建** | Grade ORM 定义（跨模块共享表下沉 models/ 顶层，orm-placement.md §7） |
| `src/edu_cloud/models/teaching_plan.py` | **新建**（R2-F001 修正：原规划到 modules/calendar/models.py 已废弃）| TeachingPlan 骨架 ORM 定义（跨模块共享 platform-level，与 Grade 策略一致；被 S4 4.3 calendar.teaching_plan_service 消费扩展业务字段）|
| `src/edu_cloud/modules/calendar/models.py` | **不动** | 保持原 re-export stub（CalendarEvent/NotificationRule/Notification），TeachingPlan 不追加到此文件（R2-F001 修正）|
| `src/edu_cloud/modules/paper/constants.py` | **新建** | PaperAccessLevel 枚举常量（str + Enum） |
| `src/edu_cloud/modules/student/models.py` | **修改（追加 1 行）** | Class 类内 `grade_number` 行之后、`head_teacher_id` 行之前追加 `grade_id: Mapped[str \| None] = mapped_column(String(36), ForeignKey("grades.id"), default=None, nullable=True)`；**禁改** `grade` / `grade_number` 两行（ORC-S1C-002） |
| `src/edu_cloud/modules/bank/models.py` | **修改（改 1 行）** | `grade_id: Mapped[int \| None] = mapped_column(Integer, default=None)` → `grade_id: Mapped[str \| None] = mapped_column(String(36), ForeignKey("grades.id"), default=None)`；其余 4 个 S1-A 新字段及所有现有字段不动 |
| `alembic/env.py` | **修改（追加 2 行）** | 在现有 import 列表末尾追加 `from edu_cloud.models.grade import Grade  # noqa: F401` + `from edu_cloud.models.teaching_plan import TeachingPlan  # noqa: F401`（R2-F001 修正：TeachingPlan 独立 import）|
| `src/edu_cloud/api/app.py` | **修改（追加 2 行）** | 在 lifespan 内 import 列表追加 `import edu_cloud.models.grade  # noqa: F401 — Grade` + `import edu_cloud.models.teaching_plan  # noqa: F401 — TeachingPlan`（R2-F001 修正：原设计依赖 `import edu_cloud.modules.calendar.models` 已被证伪） |
| `tests/conftest.py` | **修改（追加 2 行）** | conftest.py 维护独立的测试期模型 import 列表（`Base.metadata.create_all()` 入口）。追加 `import edu_cloud.models.grade  # noqa: F401` 和 `import edu_cloud.models.teaching_plan  # noqa: F401`（R2-F001 修正：TeachingPlan 独立 canonical 路径，替代原 `import edu_cloud.modules.calendar.models` 方案），保证 Grade / TeachingPlan 在 Base registry 中 → FK 建表成功 |
| `alembic/versions/{YYYYMMDD_HHMMSS}_s1c_admin_schema.py` | **新建** | Linear chain 第 2 环 migration（down_revision='a88094ee4ea6'）；upgrade: create_table grades, create_table teaching_plans, batch_alter_table classes add_column+FK, batch_alter_table bank_questions alter_column+FK |
| `tests/test_alembic_s1c_admin.py` | **新建** | S1-C migration smoke test（chain head / new tables / column types / FK targets / ORM registration zero-drift） |
| `tests/test_models/test_grade.py` | **新建** | Grade ORM roundtrip（import / fields / FK to schools / UniqueConstraint） |
| `tests/test_models/test_class_grade_id.py` | **新建** | Class.grade_id 新增字段 + 守旧字段不动验证 |
| `tests/test_models/test_teaching_plan.py` | **新建** | TeachingPlan ORM roundtrip（import / fields / 3 FK targets 限定） |
| `tests/test_models/test_paper_access_level.py` | **新建** | PaperAccessLevel 枚举 3 成员 + round-trip via value（F006 反逻辑镜像） |
| `src/edu_cloud/models/__init__.py` | **不动** | ORC-S1C-005 禁改，空文件不参与注册 |

---

## Task 1: Grade ORM + Class.grade_id FK + ORM registration

**Files:**
- Create: `src/edu_cloud/models/grade.py`
- Modify: `src/edu_cloud/modules/student/models.py`（Class 内加 1 行 `grade_id`）
- Modify: `alembic/env.py`（加 1 行 import）
- Modify: `src/edu_cloud/api/app.py`（加 1 行 import）
- Test: `tests/test_models/test_grade.py`（new）+ `tests/test_models/test_class_grade_id.py`（new）

**测试契约** (F004):
- **入口**:
  - `from edu_cloud.models.grade import Grade` 可 import
  - `Grade(school_id=..., name=...)` 可实例化
  - `Class.grade_id` 存在且 FK 指向 `grades.id`
- **反例**:
  - 若 Task 1 漏 import `Grade` 到 `alembic/env.py` / `app.py` / `tests/conftest.py`：Alembic autogenerate 发现不到 Grade（env.py 漏）或测试期 `Base.metadata.create_all()` 建不出 grades（conftest.py 漏，R1 F001 根因）→ `test_orm_registration_three_entry_points` 断言失败（grep 命令输出匹配校验）
  - 若 Task 1 顺手改 `Class.grade` 列类型：`test_class_legacy_grade_fields_unchanged` 断言 `columns['grade'].type.length == 50` 失败
  - 若 Grade UniqueConstraint 写 `(name, school_id)` 顺序反或 name 错（如 `uq_grades_school_name` vs `uq_grade_school_name`）：`test_grade_unique_school_name` 断言失败
- **边界**:
  1. `Grade` 不传 `grade_level` / `xueduan` / `sort_order` 也能实例化（3 字段 nullable/有 default）
  2. 同一 school_id 下允许多个不同 name 的 Grade（高一/高二/高三）
  3. 不同 school_id 下允许相同 name 的 Grade（校 A 的高一 ≠ 校 B 的高一，UniqueConstraint 范围是 `(school_id, name)` 组合）
  4. `Class.grade_id` 可为 None（渐进式迁移期兼容只有 grade 字符串的历史数据）
- **回归**: 现有 `tests/test_models/test_class*.py` / `tests/test_api/test_classes*.py` 继续通过；现有 `grade` 字段消费者（`classes` API / `students` 导出 / dashboard）零改动
- **命令**:
  ```bash
  .venv/bin/python -m pytest tests/test_models/test_grade.py tests/test_models/test_class_grade_id.py -v --tb=short
  ```
  Expected: 全部 test PASS（5 + 3 = 8 个）

**边界条件**（至少 3 条）:
1. Grade 必填字段只有 `school_id` 和 `name`，其他 3 字段可省略
2. `UniqueConstraint(school_id, name)` 组合级约束（非单字段）
3. `Class.grade_id` 字段是 `String(36) nullable FK`，不是 `Integer`（ORC-S1C-004）

- [ ] **Step 1.1: 写 Grade 失败测试**

Create `tests/test_models/test_grade.py`:

```python
"""S1-C Task 1: Grade 独立表 ORM + Class.grade_id FK 断言。

refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.3
refs: docs/plans/2026-04-24-haofenshu-s1-l1-data-layer-plan.md Task 3
refs: haofenshu-clone/server/routes/baseinfo.js（对照源）
"""
from sqlalchemy import UniqueConstraint


def test_grade_model_can_import():
    """ORM 入口可 import（走 edu_cloud.models.grade canonical location）"""
    from edu_cloud.models.grade import Grade  # noqa: F401


def test_grade_required_fields():
    """Grade 包含 8 列核心字段（id+school_id+name+grade_level+xueduan+sort_order+created_at+updated_at）"""
    from edu_cloud.models.grade import Grade

    columns = {c.name for c in Grade.__table__.columns}
    required = {"id", "school_id", "name", "grade_level", "xueduan", "sort_order", "created_at", "updated_at"}
    assert required.issubset(columns), f"Missing: {required - columns}"


def test_grade_school_fk_target():
    """Grade.school_id FK 指向 schools.id（IdMixin String(36) 一致）"""
    from edu_cloud.models.grade import Grade

    col = Grade.__table__.columns.get("school_id")
    assert col is not None
    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "schools.id" in fks
    assert col.type.length == 36


def test_grade_id_is_string36_not_integer():
    """ORC-S1C-004: grades.id 是 VARCHAR(36) UUID（IdMixin 约定），不是 Integer"""
    from edu_cloud.models.grade import Grade
    from sqlalchemy import String

    id_col = Grade.__table__.columns.get("id")
    assert id_col is not None
    assert isinstance(id_col.type, String)
    assert id_col.type.length == 36
    assert id_col.primary_key is True


def test_grade_unique_school_name():
    """Grade 含 UniqueConstraint(school_id, name) 组合级约束"""
    from edu_cloud.models.grade import Grade

    uq_cols = {
        tuple(sorted(c.name for c in uq.columns))
        for uq in Grade.__table__.constraints
        if isinstance(uq, UniqueConstraint)
    }
    # 断言存在一个 UniqueConstraint 恰好覆盖 {school_id, name}
    assert ("name", "school_id") in uq_cols or ("school_id", "name") in uq_cols, \
        f"Missing UniqueConstraint(school_id, name) in {uq_cols}"
```

Create `tests/test_models/test_class_grade_id.py`:

```python
"""S1-C Task 1: Class.grade_id 新增字段 + 守旧字段不动验证。

ORC-S1C-002: 禁改 Class.grade / Class.grade_number 两行。
refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.3
"""
from sqlalchemy import String


def test_class_has_grade_id_fk_to_grades():
    """新增 Class.grade_id: VARCHAR(36) NULLABLE FK→grades.id"""
    from edu_cloud.modules.student.models import Class

    col = Class.__table__.columns.get("grade_id")
    assert col is not None, "Class 必须有 grade_id 列"
    assert isinstance(col.type, String)
    assert col.type.length == 36, f"grade_id 必须 VARCHAR(36)，实际 {col.type.length}"
    assert col.nullable is True

    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "grades.id" in fks, f"FK target 必须是 grades.id，实际 {fks}"


def test_class_legacy_grade_fields_unchanged():
    """ORC-S1C-002: 守旧字段 grade/grade_number 一字不动"""
    from edu_cloud.modules.student.models import Class

    grade_col = Class.__table__.columns.get("grade")
    assert grade_col is not None, "守旧字段 Class.grade 必须保留"
    assert isinstance(grade_col.type, String)
    assert grade_col.type.length == 50, f"grade 必须 VARCHAR(50)，实际 {grade_col.type.length}"
    assert grade_col.nullable is False, "grade 必须 NOT NULL（守旧字段）"

    gn_col = Class.__table__.columns.get("grade_number")
    assert gn_col is not None, "守旧字段 Class.grade_number 必须保留"
    assert gn_col.nullable is True


def test_class_grade_id_instantiation_optional():
    """Class 不传 grade_id 也能实例化（NULL 是合法值，渐进式迁移）"""
    from edu_cloud.modules.student.models import Class

    c = Class(name="高一1班", grade="高一", school_id="x")  # 不传 grade_id
    assert getattr(c, "grade_id", None) is None
```

- [ ] **Step 1.2: 跑测试确认 FAIL**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_models/test_grade.py tests/test_models/test_class_grade_id.py -v --tb=short
```

Expected: 全部 8 个 test FAIL（ImportError on `edu_cloud.models.grade` + AttributeError on `Class.grade_id`）。

- [ ] **Step 1.3: 实现 Grade ORM**

Create `src/edu_cloud/models/grade.py`:

```python
"""Grade 独立表（S1-C 1.3，refs: design §4 1.3 / 附录 D §Gap#1 / haofenshu-clone/server/routes/baseinfo.js）。

跨模块共享表下沉 models/ 顶层（orm-placement.md §7）；被 S2 组卷 / S3 学情画像 / S4 教学计划消费。

Class.grade_id 为本 plan 新加 FK 指向本表，
同时保留 Class.grade 字符串列以支持渐进式迁移（ORC-S1C-002）。
"""
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Grade(Base, IdMixin, TimestampMixin):
    """年级实体（校内按 name 唯一，跨校允许重名）。"""
    __tablename__ = "grades"
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_grade_school_name"),)

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(50))
    grade_level: Mapped[int | None] = mapped_column(Integer, default=None)
    xueduan: Mapped[str | None] = mapped_column(String(20), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 1.4: 在 Class 类追加 grade_id（ORC-S1C-002 关键）**

Edit `src/edu_cloud/modules/student/models.py`，定位到 `Class` 类的 `school_id` 行之前（约 L18 之前），**追加一行不改动 L12-14 的 grade/grade_number 两行**：

```python
    # S1-C 1.3 新增独立年级引用（refs: design §4 1.3）
    grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None, nullable=True)
```

**手动验证位置** —— 追加后 Class 类字段顺序应为：
```
name (L12) → grade (L13, 守旧) → grade_number (L14, 守旧) → [新行 grade_id] → head_teacher_id (原 L15) → school_id (原 L18)
```

- [ ] **Step 1.5: 注册 Grade 到 alembic/env.py**

Edit `alembic/env.py`，在现有 32 条显式 import 列表末尾（`from edu_cloud.modules.academic.models import ...` 之后）追加：

```python
from edu_cloud.models.grade import Grade  # noqa: F401
```

- [ ] **Step 1.6: 注册 Grade 到 api/app.py**

Edit `src/edu_cloud/api/app.py`，在 `import edu_cloud.modules.analytics.models` 行之后追加（紧邻既有 import 列表末尾，保持前后格式一致）：

```python
    import edu_cloud.models.grade  # noqa: F401 — Grade
```

**注意缩进**：这组 import 在 `async def create_tables()` 或 lifespan 内部，保持 4 空格缩进与兄弟行一致。

- [ ] **Step 1.7: 注册 Grade 到 tests/conftest.py（R1 F001 修正；TeachingPlan import 延后到 Task 2）**

`tests/conftest.py` 维护独立的测试期模型 import 列表（`Base.metadata.create_all()` 入口不走 app.py）。必须同步 import，否则后续 Task 3 回归命令（跑 `tests/test_services_exam/test_bank_service.py`）会在 conftest 建库阶段抛 `NoReferencedTableError: grades`。

Edit `tests/conftest.py`，在既有 `import edu_cloud.models.*` / `import edu_cloud.modules.*.models` 列表中追加（位置推荐：紧邻 `import edu_cloud.modules.academic.models` 之后）：

```python
import edu_cloud.models.grade  # noqa: F401 — Grade（S1-C 新表，触发 FK grades.id 建表）
```

**R2-F001 修正说明**：原 R1 plan 在此处还要加 `import edu_cloud.modules.calendar.models` 以触发 TeachingPlan 测试期注册，但 R2 review 揭示该入口实际在 app.py/env.py 不存在——现 TeachingPlan canonical 挪到 `src/edu_cloud/models/teaching_plan.py`，其 conftest.py import 延后到 Task 2 Step 2.4 加（独立一行 `import edu_cloud.models.teaching_plan`）。

**验证未破坏既有 imports**：
```bash
grep -c "^import edu_cloud\|^from edu_cloud" tests/conftest.py
```
Expected: 相比改动前 +1（Task 1 仅 Grade；TeachingPlan 由 Task 2 再 +1，合计 +2）。

- [ ] **Step 1.8: 跑测试确认 PASS + ORM 三入口注册断言（仅 Grade）**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_models/test_grade.py tests/test_models/test_class_grade_id.py -v --tb=short

# ORC-S1C-005 手动守卫（Task 1 阶段仅 Grade；TeachingPlan 三处在 Task 2 阶段补）
grep -n "from edu_cloud.models.grade import Grade" alembic/env.py
grep -n "import edu_cloud.models.grade" src/edu_cloud/api/app.py
grep -n "import edu_cloud.models.grade" tests/conftest.py

# __init__.py 零改动
git diff --stat src/edu_cloud/models/__init__.py
```

Expected:
- 9 个 pytest test PASS（R2-F002 修复：5 Grade + 1 sort_order default + 3 Class.grade_id = 9）
- 三处 Grade grep 各命中 1 行
- `src/edu_cloud/models/__init__.py` 零改动输出

- [ ] **Step 1.9: Commit Task 1**

```bash
git add src/edu_cloud/models/grade.py src/edu_cloud/modules/student/models.py alembic/env.py src/edu_cloud/api/app.py tests/conftest.py tests/test_models/test_grade.py tests/test_models/test_class_grade_id.py
git commit -m "$(cat <<'EOF'
feat(models): S1-C T1 Grade 独立表 + Class.grade_id FK + ORM 三入口注册

为 S1-C 子 topic 首 Task（linear chain 第 2 环）。
Parent design §4.1 deliverable 1.3，refs 附录 D §Gap#1。

- Grade 新建 src/edu_cloud/models/grade.py：8 字段（id/school_id FK/name/grade_level/xueduan/sort_order/created_at/updated_at）+ UniqueConstraint(school_id, name)
- Class.grade_id: VARCHAR(36) NULLABLE FK→grades.id 追加（ORC-S1C-002 守旧字段 grade/grade_number 一字不动）
- alembic/env.py + api/app.py + tests/conftest.py 三处各追加 1 行 Grade import（ORC-S1C-005；R1 F001 修正：之前漏 conftest 导致 FK 建表失败）
- TeachingPlan 的三入口 import 由 Task 2 追加（R2-F001 修正：canonical 挪到 models/teaching_plan.py 后独立 import）
- models/__init__.py 零改动（验证为空文件）

新增 8 测试（5 Grade + 3 Class.grade_id）全绿。
grades 表 + bank_questions.grade_id FK 由 Task 4 migration 落地。

refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 1
EOF
)"
```

---

## Task 2: TeachingPlan ORM 骨架（canonical → src/edu_cloud/models/teaching_plan.py，R2-F001 修正）

> **R2-F001 修正**（2026-04-24 Gate 1 R2 FAIL → manual_override 授权）：原规划把 TeachingPlan 追加到 `modules/calendar/models.py` 仅在 conftest.py 加 import；R2 review 证实 app.py/env.py 中的 `import edu_cloud.models.calendar` 加载的是 `models/calendar.py`（CalendarEvent/NotificationRule），不触发 `modules/calendar/models.py` 加载——此路径下 TeachingPlan 只在测试期注册，生产 Base.metadata.create_all 会遗漏。修正后：canonical 改到 `src/edu_cloud/models/teaching_plan.py`（与 Grade 一致 platform-level），env.py + app.py + conftest.py 三入口各加独立 import。

**Files:**
- Create: `src/edu_cloud/models/teaching_plan.py`（R2-F001 修正：canonical 挪到 models/ 顶层 platform-level）
- Modify: `alembic/env.py` + `src/edu_cloud/api/app.py` + `tests/conftest.py`（三入口各追加 1 行 TeachingPlan import）
- Test: `tests/test_models/test_teaching_plan.py`（new，含 R2-F002 的 3 个独立 FK 断言）
- 不动: `src/edu_cloud/modules/calendar/models.py` 保持原 re-export stub

**测试契约** (F004):
- **入口**:
  - `from edu_cloud.models.teaching_plan import TeachingPlan` 可 import
  - `TeachingPlan(school_id=..., subject_code=..., semester=...)` 可实例化（grade_id / weeks_json / created_by 全可省）
  - `TeachingPlan.__table__.foreign_keys` 的 target_fullname 集合 ⊂ `{"schools.id", "grades.id", "users.id"}`
- **反例**:
  - 若 Task 2 顺手加 `lesson_plan_id FK("lesson_plans.id")`（S4 才建）：`test_teaching_plans_fk_targets_no_excess` 越界综合断言失败
  - 若 Task 2 漏 `created_by FK→users.id`（R2-F002 核心防御）：`test_teaching_plan_created_by_fk_targets_users` 独立断言立即失败（原"子集 + 至少 2 FK"的子集断言不会捕获）
  - 若 Task 2 错误挪回 `modules/calendar/models.py`：env.py/app.py 无独立 import 会让 Alembic autogenerate + 生产 create_all 建不出表（R2-F001 根源）；`test_orm_registration_three_entry_points` 三入口 grep 立即 fail
  - 若 calendar/models.py 的 CalendarEvent re-export 被不小心删除：`from edu_cloud.modules.calendar.models import CalendarEvent` 报 ImportError，现有 tests 级联 fail
- **边界**:
  1. TeachingPlan 必填字段只有 `school_id` / `subject_code` / `semester` 三列（其他 4 字段 nullable 或 有默认）
  2. `weeks_json` 接受 `None` / `[]` / `list[dict]` 三种形态（JSON 列无 schema 约束）
  3. `UniqueConstraint(school_id, subject_code, grade_id, semester)` 组合唯一：同 school 同 subject 同年级同学期只能有 1 个 plan
  4. grade_id 可以为 NULL（跨年级统一教学计划场景）
- **回归**: 现有 `tests/test_models/test_calendar.py` 继续绿；CalendarEvent/NotificationRule/Notification 三个 re-export 仍可 import
- **命令**:
  ```bash
  .venv/bin/python -m pytest tests/test_models/test_teaching_plan.py tests/test_models/test_calendar.py -v --tb=short
  ```
  Expected: 新增 7 test（R2-F002 拆分后）+ 现有 calendar tests 全 PASS

**边界条件**（至少 3 条）:
1. TeachingPlan canonical location 在 `src/edu_cloud/models/teaching_plan.py`（R2-F001 修正；不是 `modules/calendar/models.py` 也不是 `teaching_plan_models.py`）
2. FK 目标集合 ⊂ 3 张现有/本 plan 新建的表，且 schools/grades/users 三目标各自独立断言存在（R2-F002 拆分，ORC-S1C-003）
3. calendar/models.py 保持 re-export stub 不动（不删 CalendarEvent 等）

- [ ] **Step 2.1: 写失败测试**

Create `tests/test_models/test_teaching_plan.py`:

```python
"""S1-C Task 2: TeachingPlan 骨架 ORM 断言。

ORC-S1C-003: 骨架 FK 目标 ⊂ {schools.id, grades.id, users.id}，不含 lesson_plans 等未建表。
refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.4
refs: haofenshu-clone/server/config/schema.sql:284-302
"""
from sqlalchemy import UniqueConstraint


def test_teaching_plan_import_from_calendar_models():
    """必须 canonical location 在 calendar/models.py（F002 修正）"""
    from edu_cloud.models.teaching_plan import TeachingPlan  # noqa: F401


def test_teaching_plan_required_fields():
    """骨架含 9 列（id + 7 业务 + timestamps）"""
    from edu_cloud.models.teaching_plan import TeachingPlan

    cols = {c.name for c in TeachingPlan.__table__.columns}
    required = {"id", "school_id", "subject_code", "grade_id", "semester", "weeks_json", "created_by", "created_at", "updated_at"}
    assert required.issubset(cols), f"Missing: {required - cols}"


def test_teaching_plans_fk_targets_are_limited():
    """ORC-S1C-003 机械化：FK target_fullname ⊂ 3 张表"""
    from edu_cloud.models.teaching_plan import TeachingPlan

    all_targets = set()
    for col in TeachingPlan.__table__.columns:
        for fk in col.foreign_keys:
            all_targets.add(fk.target_fullname)

    allowed = {"schools.id", "grades.id", "users.id"}
    assert all_targets.issubset(allowed), \
        f"TeachingPlan 有未建表 FK：{all_targets - allowed}（ORC-S1C-003 违反）"
    # 至少有 schools.id 和 grades.id 两个 FK（created_by 可 nullable）
    assert "schools.id" in all_targets
    assert "grades.id" in all_targets


def test_teaching_plan_unique_constraint():
    """含 UniqueConstraint(school_id, subject_code, grade_id, semester)"""
    from edu_cloud.models.teaching_plan import TeachingPlan

    uq_cols_sets = [
        frozenset(c.name for c in uq.columns)
        for uq in TeachingPlan.__table__.constraints
        if isinstance(uq, UniqueConstraint)
    ]
    expected = frozenset({"school_id", "subject_code", "grade_id", "semester"})
    assert expected in uq_cols_sets, \
        f"Missing UniqueConstraint(school_id, subject_code, grade_id, semester) in {uq_cols_sets}"


def test_calendar_re_exports_still_work():
    """ORC: 不破坏既有 re-export 语义"""
    from edu_cloud.modules.calendar.models import CalendarEvent, NotificationRule, Notification  # noqa: F401
```

- [ ] **Step 2.2: 跑测试确认 FAIL**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_models/test_teaching_plan.py -v --tb=short
```

Expected: 7 个新测试 FAIL（ImportError on TeachingPlan canonical）+ test_calendar_re_exports_still_work PASS。

- [ ] **Step 2.3: 新建 TeachingPlan canonical 文件（R2-F001 修正）**

Create `src/edu_cloud/models/teaching_plan.py`（与 Grade 一致 platform-level；calendar/models.py 保持 re-export stub 不动）：

```python
"""TeachingPlan 骨架表（S1-C 1.4，R2-F001 修正：canonical 挪到 models/ 顶层）。

refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.4
refs: 附录 C §Gap#6 / haofenshu-clone/server/config/schema.sql:284-302
ORC-S1C-003: 骨架仅含 schools/grades/users 三表 FK；lesson_plans 等 S4 才建的表 FK 严禁加。
"""
from sqlalchemy import String, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class TeachingPlan(Base, IdMixin, TimestampMixin):
    """教学计划骨架表（学期→周次→知识点，S4 扩展关联资源与审批工作流）。"""
    __tablename__ = "teaching_plans"
    __table_args__ = (
        UniqueConstraint(
            "school_id", "subject_code", "grade_id", "semester",
            name="uq_teaching_plan_scope",
        ),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None)
    semester: Mapped[str] = mapped_column(String(30))
    weeks_json: Mapped[list | None] = mapped_column(JSON, default=None)
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), default=None)
```

- [ ] **Step 2.4: 三入口追加 TeachingPlan import（R2-F001 fail-closed 护栏）**

1. Edit `alembic/env.py` 追加 `from edu_cloud.models.teaching_plan import TeachingPlan  # noqa: F401`
2. Edit `src/edu_cloud/api/app.py` 追加 `import edu_cloud.models.teaching_plan  # noqa: F401 — TeachingPlan`
3. Edit `tests/conftest.py` 追加 `import edu_cloud.models.teaching_plan  # noqa: F401 — TeachingPlan`

- [ ] **Step 2.5: 跑测试确认 PASS**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_models/test_teaching_plan.py tests/test_models/test_calendar.py -v --tb=short 2>&1 | tail -30

# 三入口 TeachingPlan import 各命中 1 条（R2-F001 护栏）
grep -n "from edu_cloud.models.teaching_plan import TeachingPlan" alembic/env.py
grep -n "import edu_cloud.models.teaching_plan" src/edu_cloud/api/app.py
grep -n "import edu_cloud.models.teaching_plan" tests/conftest.py
```

Expected: 8 个 test PASS（7 TeachingPlan + 1 re-export 回归）+ 既有 calendar tests 全绿；三处 grep 各命中 1 行。

- [ ] **Step 2.6: Commit Task 2**

```bash
git add src/edu_cloud/models/teaching_plan.py alembic/env.py src/edu_cloud/api/app.py tests/conftest.py tests/test_models/test_teaching_plan.py
git commit -m "$(cat <<'EOF'
feat(models): S1-C T2 TeachingPlan 骨架 (canonical → models/teaching_plan.py)

Parent design §4.1 deliverable 1.4，refs 附录 C §Gap#6。

R2-F001 修复（canonical location 迁移）:
- 新建 src/edu_cloud/models/teaching_plan.py（与 Grade 一致 platform-level）
- env.py + api/app.py + tests/conftest.py 三入口各加独立 import
- 不再依赖 calendar-models/conftest-only 注册

R2-F002 修复（INV-S1C-002 拆分）:
- 3 个独立 FK 断言（schools/grades/users）+ 1 个越界综合断言

calendar/models.py 保持 re-export stub 不动；业务 service/router 归 S4 4.3（test_debt #4 deadline 2026-08-31）。
teaching_plans 表由 Task 4 migration 落地。

refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 2
EOF
)"
```

---

## Task 3: PaperAccessLevel 枚举 + bank_questions.grade_id ORM 类型修正

**Files:**
- Create: `src/edu_cloud/modules/paper/constants.py`
- Modify: `src/edu_cloud/modules/bank/models.py:41`（S1-A 的 `grade_id: Integer` 改 String(36) FK）
- Test: `tests/test_models/test_paper_access_level.py`（new）

**测试契约** (F004):
- **入口**:
  - `from edu_cloud.modules.paper.constants import PaperAccessLevel`
  - `PaperAccessLevel.TEACHER_PRIVATE.value == "teacher_private"` 三成员值
  - `PaperAccessLevel("teacher_private") is PaperAccessLevel.TEACHER_PRIVATE` 反序列化
  - `BankQuestion.__table__.columns['grade_id'].type.length == 36` + FK to grades.id
- **反例**:
  - 若 PaperAccessLevel 成员值漂移（`teacher_pr` 代替 `teacher_private`）：`test_paper_access_level_roundtrip_via_value` round-trip 失败（`PaperAccessLevel("teacher_private")` 抛 ValueError）—— F006 修正锚点
  - 若 `bank/models.py:41` 漏改：`test_bank_grade_id_is_string36_fk` 断言 type.length == 36 失败
  - 若 bank/models.py 其他 S1-A 新字段被顺手改了（source / explanation / etc.）：`test_s1a_fields_preserved` 断言类型一致性失败
- **边界**:
  1. PaperAccessLevel 3 成员值全部小写下划线形式（`teacher_private` / `school_shared` / `district_shared`）
  2. `PaperAccessLevel` 是 `str + Enum`（成员可参与字符串比较：`PaperAccessLevel.TEACHER_PRIVATE == "teacher_private"` → True）
  3. `BankQuestion.grade_id` 改动是"ORM 层 Mapped 类型改写"，不动 S1-A 已落地 migration（migration 层改动在 Task 4）
- **回归**: 现有 `tests/test_services_exam/test_bank_service.py` 所有 test 继续绿（包括 `test_bank_question_new_fields_roundtrip` 等 S1-A 3 个新 test）
- **命令**:
  ```bash
  .venv/bin/python -m pytest tests/test_models/test_paper_access_level.py tests/test_services_exam/test_bank_service.py -v --tb=short
  ```
  Expected: 新 5 + 既有 9 = 14 个 test PASS

**边界条件**（至少 3 条）:
1. PaperAccessLevel 不依赖数据库，纯 Python 枚举（Task 3 ORM 断言测试不需要 DB fixture）
2. PaperAccessLevel 测试避免"集合相等镜像"（F006）——用外部字符串 round-trip 锚定每个成员值
3. bank/models.py:41 改动是单行 grade_id 的类型定义，禁止触及同模块其他 19 行

- [ ] **Step 3.1: 写 PaperAccessLevel 失败测试（F006 反镜像）**

Create `tests/test_models/test_paper_access_level.py`:

```python
"""S1-C Task 3: PaperAccessLevel 枚举常量 + bank_questions.grade_id 类型修正断言。

F006 反逻辑镜像修正：不用 `{e.value for e in Enum} == {"a","b","c"}` 这种集合相等断言，
改用外部字符串 round-trip 锚定每个值，防止重命名漂移。
refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.5
"""
from enum import Enum

import pytest


def test_paper_access_level_import():
    from edu_cloud.modules.paper.constants import PaperAccessLevel  # noqa: F401


def test_paper_access_level_is_str_enum():
    """PaperAccessLevel 是 str + Enum 双继承（支持字符串比较）"""
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    assert issubclass(PaperAccessLevel, str)
    assert issubclass(PaperAccessLevel, Enum)


@pytest.mark.parametrize("external_value,expected_member_name", [
    ("teacher_private", "TEACHER_PRIVATE"),
    ("school_shared", "SCHOOL_SHARED"),
    ("district_shared", "DISTRICT_SHARED"),
])
def test_paper_access_level_roundtrip_via_value(external_value: str, expected_member_name: str):
    """F006 反镜像：外部字符串 → 枚举成员 → 回到字符串，每个成员独立断言。

    错误实现（值漂移到 `teacher_pr`）会让 `PaperAccessLevel("teacher_private")` 抛 ValueError，立即 fail。
    集合相等断言（parent L1 plan Task 5 Step 5.1 的 `assert values == {"teacher_private",...}`）
    在值漂移 + 名字漂移同步发生时会假绿——本 test 钉死字符串值。
    """
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    member = PaperAccessLevel(external_value)  # 值→成员
    assert member.name == expected_member_name
    assert member.value == external_value      # 成员→值
    assert member == external_value            # str-Enum 字符串比较


def test_paper_access_level_rejects_unknown_value():
    """F006 反镜像：未知值必须抛 ValueError（而非静默退化）"""
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    with pytest.raises(ValueError):
        PaperAccessLevel("platform_shared")  # 不在 3 成员值中


def test_paper_access_level_has_exactly_three_members():
    """成员数量钉死为 3（多加/少加都 fail）"""
    from edu_cloud.modules.paper.constants import PaperAccessLevel

    assert len(list(PaperAccessLevel)) == 3


def test_bank_grade_id_is_string36_fk():
    """ORC-S1C-004: bank_questions.grade_id ORM 层改 String(36) + FK → grades.id"""
    from edu_cloud.modules.bank.models import BankQuestion
    from sqlalchemy import String

    col = BankQuestion.__table__.columns.get("grade_id")
    assert col is not None
    assert isinstance(col.type, String), f"grade_id 必须 String 类型，实际 {type(col.type).__name__}"
    assert col.type.length == 36, f"grade_id 必须 VARCHAR(36)，实际 {col.type.length}"
    assert col.nullable is True

    fks = {fk.target_fullname for fk in col.foreign_keys}
    assert "grades.id" in fks, f"FK target 必须是 grades.id，实际 {fks}"


def test_bank_s1a_fields_preserved():
    """ORC-S1C-002 扩展：S1-A 新加 5 字段中除 grade_id 外，其他 4 个字段不动"""
    from edu_cloud.modules.bank.models import BankQuestion
    from sqlalchemy import String, Text, JSON

    def _col(name):
        return BankQuestion.__table__.columns.get(name)

    source_col = _col("source")
    assert source_col is not None
    assert isinstance(source_col.type, String)
    assert source_col.type.length == 20

    explanation_col = _col("explanation")
    assert explanation_col is not None
    assert isinstance(explanation_col.type, Text)

    kp_col = _col("knowledge_point_ids")
    assert kp_col is not None
    assert isinstance(kp_col.type, JSON)

    dl_col = _col("difficulty_level")
    assert dl_col is not None
    assert isinstance(dl_col.type, String)
    assert dl_col.type.length == 10
```

- [ ] **Step 3.2: 跑测试确认 FAIL**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_models/test_paper_access_level.py -v --tb=short
```

Expected: ImportError 级 fail（6 个 PaperAccessLevel test）+ `test_bank_grade_id_is_string36_fk` fail（S1-A 仍是 Integer）。

- [ ] **Step 3.3: 实现 PaperAccessLevel**

Create `src/edu_cloud/modules/paper/constants.py`:

```python
"""Paper 模块常量（S1-C 1.5）。

refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.5
refs: 附录 C §Gap#4（试卷权限分层）

S4 4.2 paper.access_policy 消费本枚举做 3 层分享工作流（teacher_private / school_shared / district_shared）。
S1-C 只定义常量，不上 DB CHECK 或 SQLAlchemy Enum 列（见 test_debt #2 deadline 2026-06-30）。
"""
from enum import Enum


class PaperAccessLevel(str, Enum):
    """试卷访问层级（S4 4.2 分享工作流使用）."""
    TEACHER_PRIVATE = "teacher_private"
    SCHOOL_SHARED = "school_shared"
    DISTRICT_SHARED = "district_shared"
```

- [ ] **Step 3.4: 修正 bank/models.py:41 的 grade_id 类型**

Edit `src/edu_cloud/modules/bank/models.py`，把第 41 行：

```python
    grade_id: Mapped[int | None] = mapped_column(Integer, default=None)
```

改为：

```python
    grade_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("grades.id"), default=None)
```

**注意**：
- `String` 和 `ForeignKey` 已经在文件顶部 `from sqlalchemy import` 语句中 import（第 4 行），无需新增 import
- `Integer` 仍被 `difficulty_level` 等字段间接使用（不，实际 `difficulty_level` 是 String）——检查 Integer 是否仍被其他列使用（`sample_count` / `retry_count` 等），保留 Integer import 不动

- [ ] **Step 3.5: 跑测试确认 PASS**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_models/test_paper_access_level.py tests/test_services_exam/test_bank_service.py -v --tb=short 2>&1 | tail -40
```

Expected: 14 个 test PASS（7 新 + 既有 9 bank service 包含 S1-A 3 个）。

**注意潜在回归**：S1-A 的 `test_bank_question_new_fields_roundtrip` 原本用 `grade_id=9`（Integer 值）。本 plan 改 grade_id 为 String(36)，原 test 会 fail。**需要同步更新 S1-A 遗留 3 个 test 中的 grade_id 值**，见 Step 3.6。

- [ ] **Step 3.6: 更新 S1-A 遗留 test 中的 grade_id 值**

Edit `tests/test_services_exam/test_bank_service.py`，定位 S1-A 新加的 3 个 test（`test_bank_question_new_fields_roundtrip` / `_all_nullable` / `_visible_via_service`）：
- `test_bank_question_new_fields_roundtrip` 原 `grade_id=9` → 改为 `grade_id="00000000-0000-0000-0000-000000000001"`（UUID 格式字符串）
- `test_bank_question_new_fields_all_nullable` 原 `assert q.grade_id is None` 保持不变
- `test_bank_question_new_fields_visible_via_service` 原 `grade_id=7` → 改为 `grade_id="00000000-0000-0000-0000-000000000002"`

**更新后再跑**：

```bash
.venv/bin/python -m pytest tests/test_services_exam/test_bank_service.py -v --tb=short
```

Expected: 9 个 test 全 PASS（S1-A 3 个新 test 使用新 UUID 值 grade_id）。

- [ ] **Step 3.7: Commit Task 3**

```bash
git add src/edu_cloud/modules/paper/constants.py src/edu_cloud/modules/bank/models.py tests/test_models/test_paper_access_level.py tests/test_services_exam/test_bank_service.py
git commit -m "$(cat <<'EOF'
feat(paper,bank): S1-C T3 PaperAccessLevel 枚举 + bank_questions.grade_id 类型修正

Parent design §4.1 deliverable 1.5（PaperAccessLevel）+ TD-S1A-002 闭环（bank.grade_id）。

- PaperAccessLevel: str+Enum 3 成员（teacher_private/school_shared/district_shared）
- 测试采用外部字符串 round-trip 反镜像锚定（F006 修正），拒绝集合相等镜像断言
- bank_questions.grade_id ORM 层 Integer → String(36) + FK→grades.id（ORC-S1C-004）
- S1-A 遗留 3 个 test 的 grade_id 从 Integer 值改 UUID 字符串（新契约对齐）

migration 层 alter_column + create_foreign_key 由 Task 4 落地。

refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 3
EOF
)"
```

---

## Task 4: Linear chain 第 2 环 migration

**Files:**
- Create: `alembic/versions/{YYYYMMDD_HHMMSS}_s1c_admin_schema.py`（alembic revision 自动生成 slug）

**测试契约** (F004):
- **入口**:
  - `alembic upgrade head`（CLI）和 `alembic downgrade -1`（CLI）双向成功
  - migration 本身是 `upgrade()` / `downgrade()` 两个函数
  - `alembic current` 在 upgrade 后返回新 slug，downgrade 后返回 `a88094ee4ea6`（R1 F003 残余清理 @ 2026-04-24T22:30：`alembic heads` 反映脚本目录 DAG 与 DB 状态无关，downgrade 后 heads 不变——用 `alembic current` 才是 DB revision 判定）
- **反例**:
  - 若 down_revision 绑错（如 `'a8c7d2e4f135'`，S1-A 的前一环）：ORC-S1C-001 违反，`test_migration_chain_head_is_single` 捕获（Task 5）
  - 若 migration 只 `create_foreign_key` 不 `alter_column`：bank_questions.grade_id 保留 Integer 类型，PG 建 FK 时报类型不匹配；SQLite 建 FK 成功但运行时 inspect 类型不一致
  - 若 bank_questions.grade_id 走 `batch_alter_table` 外 `op.alter_column`：SQLite 不支持直接 ALTER COLUMN 类型（ORC-S1A-004 教训），failed on SQLite smoke
- **边界**:
  1. 本 migration 在 SQLite in-memory 上 upgrade/downgrade 闭环（ORC-S1C 双方言）
  2. 本 migration 在 PostgreSQL 上 DDL 合法
  3. downgrade 顺序 LIFO：drop FK → alter_column 回 Integer → drop FK → drop classes.grade_id → drop teaching_plans → drop grades
  4. upgrade 重复运行幂等（alembic 天然幂等）
- **回归**: migration chain 单 head 保持；现有 25+ migration 全部可 upgrade 到新 head 成功
- **命令**:
  ```bash
  .venv/bin/alembic heads  # 核实脚本目录 head 是 'a88094ee4ea6'
  .venv/bin/alembic revision -m "s1c_admin_schema"
  # 手动填 upgrade/downgrade body

  # R1 F002 修正：不用 stamp（只写 version 标记不建表），用 upgrade 真跑到 S1-A head 让 classes/bank_questions 就位
  .venv/bin/alembic upgrade a88094ee4ea6

  # R1 F003 修正：回滚验证用 alembic current 读 DB revision，不用 heads（heads 是脚本目录列表）
  .venv/bin/alembic upgrade head && .venv/bin/alembic current       # 期望：新 S1-C slug
  .venv/bin/alembic downgrade -1 && .venv/bin/alembic current       # 期望：a88094ee4ea6
  .venv/bin/alembic upgrade head && .venv/bin/alembic current       # 期望：新 S1-C slug（幂等）
  .venv/bin/alembic heads                                            # 期望：单行（chain 无分叉）
  ```
  Expected: 四阶段全部成功

**边界条件**（至少 3 条）:
1. `batch_alter_table` 包装是 SQLite 兼容强制（ORC-S1A-004 教训 + 2026-04-13-migration-gate-repair-design.md）
2. 所有 JSON 用 `sa.JSON()` 不用 `postgresql.JSONB`（ORC-S1A-004 教训）
3. FK constraint 名字必须显式（`fk_classes_grade_id` / `fk_bank_questions_grade_id`），方便 downgrade 定位

- [ ] **Step 4.1: 实施前核实当前 head**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/alembic heads
```

Expected: `a88094ee4ea6 (head)`（与 E-001 一致）。

**漂移处置（如果输出不是 `a88094ee4ea6`）**：
- 若输出是新 head（如 `abc123def456`）：Task 4 后续步骤的 `down_revision` 值替换为新 head；ORC-S1C-001 `statement` 同步更新；Contract Pack INV-S1C-006 更新
- 若输出是多 head（`>1` 行）：立即停止 Task 4，报告用户（说明 chain 已被其他 session 破坏），等待用户决策（是否先修多 head）

**断言**：本 Step 的实际输出写入 plan 的 `baseline_verified_at` 旁边作为审计证据。

- [ ] **Step 4.2: 生成 migration 骨架**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/alembic revision -m "s1c_admin_schema"
```

Expected: 输出类似 `Generating /home/ops/projects/edu-cloud/alembic/versions/{NEW_SLUG}_s1c_admin_schema.py ... done`。

**立刻记录 `{NEW_SLUG}` 值**（12 位十六进制），后续 Task 5 要引用。

- [ ] **Step 4.3: 验证并修正 down_revision（ORC-S1C-001 核心）**

打开刚生成的文件，查找 `down_revision` 行。Alembic 默认自动填前一个 head，应该是 `'a88094ee4ea6'`（若 Step 4.1 观察到漂移则填当时 head）。

**手动断言**：
```bash
grep -n "down_revision" alembic/versions/*s1c_admin_schema.py
```

Expected: `down_revision: Union[str, Sequence[str], None] = 'a88094ee4ea6'`（或 Step 4.1 实测 head）。

若不是实测 head → 手动修正。

- [ ] **Step 4.4: 实现 upgrade() body**

覆盖 migration 文件的 `upgrade()` 函数：

```python
def upgrade() -> None:
    """S1-C: 行政配置 schema（grades 新表 / teaching_plans 新表 / classes.grade_id + FK / bank_questions.grade_id 类型修正 + FK）。

    refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 4
    refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverables 1.3/1.4
    ORC-S1C-003: teaching_plans FK 仅指向 schools/grades/users（禁 lesson_plans 等未建表）
    ORC-S1C-004: 所有 grade_id FK 类型统一 String(36)；bank.grade_id 从 Integer 改 String(36) 闭环 TD-S1A-002
    ORC-S1A-004 传承: JSON 用 sa.JSON()，DDL 用 batch_alter_table 保持双方言中立
    """
    # 1.3 grades 新表
    op.create_table(
        'grades',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('grade_level', sa.Integer(), nullable=True),
        sa.Column('xueduan', sa.String(length=20), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], name='fk_grades_school_id'),
        sa.UniqueConstraint('school_id', 'name', name='uq_grade_school_name'),
    )

    # 1.4 teaching_plans 新表（ORC-S1C-003: 仅 3 个 FK 指向 schools/grades/users）
    op.create_table(
        'teaching_plans',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('subject_code', sa.String(length=50), nullable=False),
        sa.Column('grade_id', sa.String(length=36), nullable=True),
        sa.Column('semester', sa.String(length=30), nullable=False),
        sa.Column('weeks_json', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], name='fk_teaching_plans_school_id'),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], name='fk_teaching_plans_grade_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_teaching_plans_created_by'),
        sa.UniqueConstraint(
            'school_id', 'subject_code', 'grade_id', 'semester',
            name='uq_teaching_plan_scope',
        ),
    )

    # 1.3 classes.grade_id + FK（ORC-S1C-002: 守旧 grade/grade_number 不动，只加 1 列）
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grade_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_classes_grade_id', 'grades', ['grade_id'], ['id'],
        )

    # TD-S1A-002 闭环: bank_questions.grade_id 类型 Integer → String(36) + FK（ORC-S1C-004）
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.alter_column(
            'grade_id',
            existing_type=sa.Integer(),
            type_=sa.String(length=36),
            existing_nullable=True,
            postgresql_using='grade_id::text',  # PG 上 Integer→Text 转换（列全 NULL 无实际转换）
        )
        batch_op.create_foreign_key(
            'fk_bank_questions_grade_id', 'grades', ['grade_id'], ['id'],
        )
```

**关键要点**：
- `batch_alter_table` 包装是 SQLite 兼容强制（ORC-S1A-004）
- `sa.JSON()` 不是 `postgresql.JSONB`
- 所有 FK 名字显式（downgrade 好定位）
- `postgresql_using='grade_id::text'` 仅 PG 走（SQLite 忽略）；列全 NULL 无真实数据转换

- [ ] **Step 4.5: 实现 downgrade() body**

追加 downgrade 函数（LIFO 顺序，每步对称撤销 upgrade）：

```python
def downgrade() -> None:
    """S1-C downgrade: LIFO 顺序撤销 upgrade 全部操作。

    依赖顺序：先 drop FK 再 drop 表/列，防止"referencing still active"。
    """
    # TD-S1A-002 反向: bank_questions.grade_id FK 去除 + 类型回 Integer
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_bank_questions_grade_id', type_='foreignkey')
        batch_op.alter_column(
            'grade_id',
            existing_type=sa.String(length=36),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using='NULLIF(grade_id, \'\')::integer',  # PG 空字符串→NULL→Integer
        )

    # classes.grade_id FK + 列去除
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_classes_grade_id', type_='foreignkey')
        batch_op.drop_column('grade_id')

    # teaching_plans 表去除（LIFO 先于 grades，因为 teaching_plans.grade_id FK 指向 grades）
    op.drop_table('teaching_plans')

    # grades 表去除
    op.drop_table('grades')
```

- [ ] **Step 4.6: 本地 smoke — upgrade → downgrade → upgrade 三阶段**

```bash
cd /home/ops/projects/edu-cloud

# 方案 A: 使用临时 SQLite 文件库（避免污染测试库）
export DATABASE_URL="sqlite+aiosqlite:///tmp_s1c_smoke.db"
rm -f tmp_s1c_smoke.db

# R1 F002 修正：从 base 跑全链路 upgrade 到 S1-A head，让 classes/bank_questions
# 等前置表真实建好——`alembic stamp` 只写 alembic_version 不建表，起点会是不可能态
.venv/bin/alembic upgrade a88094ee4ea6

# 1) upgrade：跑到新 head
.venv/bin/alembic upgrade head
.venv/bin/alembic current
# 期望输出：{NEW_SLUG} (head)（`alembic current` 反映 DB 当前 revision，R1 F003 修正）

# 2) downgrade：回到 a88094ee4ea6
.venv/bin/alembic downgrade -1
.venv/bin/alembic current
# 期望输出：a88094ee4ea6（R1 F003 修正：用 current 断言 DB revision，不是 heads；heads 是脚本目录列表，downgrade 后不变）

# 3) upgrade：再跑到新 head 验证幂等
.venv/bin/alembic upgrade head
.venv/bin/alembic current
# 期望输出：{NEW_SLUG} (head)

# 4) 脚本目录 linear chain 校验（用 heads，和 DB 状态无关）
.venv/bin/alembic heads
# 期望输出：{NEW_SLUG} (head) 单行（ORC-S1C-001，linear chain 单 head）

# 清理
rm -f tmp_s1c_smoke.db
unset DATABASE_URL
```

Expected: 四阶段全部成功。三次 `alembic current` 按升→降→升顺序精确切换；`alembic heads` 始终单 head；无 SQL 语法错误；无 NOT NULL violation。

- [ ] **Step 4.7: Commit Task 4**

```bash
git add alembic/versions/*s1c_admin_schema.py
git commit -m "$(cat <<'EOF'
feat(alembic): S1-C T4 linear chain 第 2 环 migration (admin schema)

down_revision='a88094ee4ea6'（S1-A T2 实测 head，ORC-S1C-001）。
upgrade():
- create_table grades（8 列 + FK→schools + UniqueConstraint(school_id, name)）
- create_table teaching_plans（9 列 + 3 FK 限定 schools/grades/users + 4 列 UniqueConstraint）
- batch_alter_table classes: add_column grade_id + create_fk → grades.id（守旧 grade/grade_number 不动）
- batch_alter_table bank_questions: alter_column grade_id Integer→String(36) + create_fk → grades.id（闭环 TD-S1A-002）

downgrade() 反向 LIFO：drop_fk → alter_column 回 Integer → drop_fk → drop_column grade_id → drop teaching_plans → drop grades。
使用 sa.JSON() + batch_alter_table 保持 SQLite/PG 双方言兼容（ORC-S1A-004 传承）。

refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 4
EOF
)"
```

---

## Task 5: Migration smoke test + Gate G1-S1C

**Files:**
- Create: `tests/test_alembic_s1c_admin.py`

**测试契约** (F004):
- **入口**: pytest 收集并运行 `tests/test_alembic_s1c_admin.py`
- **反例**:
  - 若 Task 4 误绑 down_revision：`test_migration_file_down_revision_matches_prev_head` fail
  - 若 Task 4 漏 alter_column：`test_bank_questions_grade_id_is_string36_with_fk` 在 upgrade 后 inspect 发现 INTEGER 立即 fail
  - 若 Task 2 骨架加了 `lesson_plans` FK：`test_teaching_plans_table_schema_complete` 越界综合断言 fail；R2-F002 拆分后即使构造"包含 lesson_plans 但也包含 schools/grades/users"的 FK 集合，`test_teaching_plans_table_schema_complete` 的 excess 断言仍会捕获
  - 若 Task 1 改了 `Class.grade`：`test_class_legacy_grade_fields_unchanged` fail
  - 若 Task 1 改了 `models/__init__.py`：`test_orm_registration_three_entry_points` git diff 检测 fail
- **边界**:
  1. 空 DB 上从头 upgrade head 到 S1-C slug 全链路通过（覆盖 26 个 migration）
  2. 预置 seed 数据后 upgrade 不丢现有表数据（`test_existing_tables_data_preserved`）
  3. upgrade → downgrade → upgrade 三阶段闭环
- **回归**: 现有 `tests/test_alembic_migration.py` 3 个 test 继续绿（因本文件独立，不触碰）
- **命令**:
  ```bash
  .venv/bin/python -m pytest tests/test_alembic_s1c_admin.py tests/test_alembic_migration.py tests/test_alembic_s1a_bank.py -v --tb=short
  ```
  Expected: 本文件 9 test + 既有 alembic tests 全绿

**边界条件**（至少 3 条）:
1. 本测试用 SQLite 文件 DB（不是 in-memory），便于 alembic subprocess 访问同一 DB
2. INSERT smoke 数据带齐所有 NOT NULL 列（F003 教训传承）
3. 所有断言使用 SQLAlchemy inspect 精确匹配（type.length 等），不做宽松 substring 匹配（F006 教训传承）

- [ ] **Step 5.1: 新建 tests/test_alembic_s1c_admin.py**

Create `tests/test_alembic_s1c_admin.py`:

```python
"""S1-C admin migration smoke tests.

覆盖 ORC-S1C-001（linear chain 第 2 环）/ ORC-S1C-002（守旧字段不动）
    / ORC-S1C-003（teaching_plans FK 限定）/ ORC-S1C-004（FK 类型统一）
    / ORC-S1C-005（ORM 注册零 __init__.py 依赖）。
refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 5
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, text

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture()
def sqlite_db(tmp_path):
    """Per-test SQLite file DB（文件路径便于 alembic subprocess 访问）."""
    db_file = tmp_path / 's1c_admin.db'
    yield f'sqlite:///{db_file}'


def _run_alembic(cmd_args: list[str], db_url: str) -> subprocess.CompletedProcess:
    """运行 alembic CLI（async URL 对 alembic async env 必须）."""
    async_url = db_url.replace('sqlite:///', 'sqlite+aiosqlite:///')
    return subprocess.run(
        [sys.executable, '-m', 'alembic', *cmd_args],
        cwd=PROJECT_ROOT,
        env={**os.environ, 'DATABASE_URL': async_url},
        capture_output=True,
        text=True,
    )


# ───────────────── 静态文件断言（无需 DB） ─────────────────


def test_migration_file_down_revision_matches_prev_head():
    """INV-S1C-006 + ORC-S1C-001: S1-C migration 文件 head 处 down_revision 是 S1-A slug 'a88094ee4ea6'.

    实施前 Task 4 Step 4.1 实测 head，若已漂移需同步更新本断言。
    本 test 对 plan 契约机械化——写错立即 fail。
    """
    versions_dir = os.path.join(PROJECT_ROOT, 'alembic', 'versions')
    matches = [f for f in os.listdir(versions_dir) if 's1c_admin_schema' in f]
    assert len(matches) == 1, f"Expected exactly 1 S1-C migration file, got {matches}"

    with open(os.path.join(versions_dir, matches[0])) as fp:
        content = fp.read()
    # 精确字符串匹配 down_revision
    assert "down_revision: Union[str, Sequence[str], None] = 'a88094ee4ea6'" in content, \
        "ORC-S1C-001 违反：down_revision 必须是 'a88094ee4ea6'（S1-A T2 slug）"


def test_orm_registration_three_entry_points():
    """ORC-S1C-005 + INV-S1C-008（R1 F001 修正）:
    env.py + api/app.py + tests/conftest.py 三处都含 Grade import；
    conftest.py 另需 calendar.models import（TeachingPlan 的测试期注册）；
    models/__init__.py 仍零内容。
    """
    # 1) alembic/env.py 含 Grade import
    env_path = os.path.join(PROJECT_ROOT, 'alembic', 'env.py')
    with open(env_path) as fp:
        env_content = fp.read()
    assert "from edu_cloud.models.grade import Grade" in env_content, \
        "alembic/env.py 缺 Grade import（ORC-S1C-005 入口 1/3）"

    # 2) api/app.py 含 Grade import
    app_path = os.path.join(PROJECT_ROOT, 'src', 'edu_cloud', 'api', 'app.py')
    with open(app_path) as fp:
        app_content = fp.read()
    assert "import edu_cloud.models.grade" in app_content, \
        "api/app.py 缺 Grade import（ORC-S1C-005 入口 2/3）"

    # 3) tests/conftest.py 含 Grade import + calendar.models import（R1 F001 修正）
    conftest_path = os.path.join(PROJECT_ROOT, 'tests', 'conftest.py')
    with open(conftest_path) as fp:
        conftest_content = fp.read()
    assert "import edu_cloud.models.grade" in conftest_content, \
        "tests/conftest.py 缺 Grade import（R1 F001 根因，ORC-S1C-005 入口 3/3）"
    assert "import edu_cloud.models.teaching_plan" in conftest_content, \
        "tests/conftest.py 缺 TeachingPlan import（R2-F001 修复：TeachingPlan canonical 挪到 models/teaching_plan.py 后测试期注册走独立 import）"

    # 4) R2-F002 INV-S1C-008 升级：字节级 SHA256 对比空文件锚点（原 "0 非空行" 会被加空白/BOM 漂移绕过）
    import hashlib
    init_path = os.path.join(PROJECT_ROOT, 'src', 'edu_cloud', 'models', '__init__.py')
    with open(init_path, 'rb') as fp:
        init_bytes = fp.read()
    EMPTY_FILE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    actual_sha = hashlib.sha256(init_bytes).hexdigest()
    assert actual_sha == EMPTY_FILE_SHA256, (
        f"ORC-S1C-005 违反：models/__init__.py SHA256 与空文件不一致。\n"
        f"  期望: {EMPTY_FILE_SHA256}\n"
        f"  实际: {actual_sha}\n"
        f"  文件字节数: {len(init_bytes)}"
    )


# ───────────────── 结构断言（需 upgrade） ─────────────────


def test_migration_chain_head_is_single(sqlite_db):
    """INV-S1C-007 上半段: upgrade 后脚本目录 `alembic heads` 恰好 1 行（linear chain 无分叉）.

    这里用 heads 是对的——heads 反映脚本目录（alembic/versions/*.py）的 DAG 终点，
    linear chain 应始终返回单个 head slug。与 DB revision 无关。
    R1 F003 教训：回滚检测必须用 `alembic current`（见 test_downgrade_restores_s1a_revision）。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade failed: {r.stderr}"

    r = _run_alembic(['heads'], sqlite_db)
    assert r.returncode == 0
    non_empty_lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(non_empty_lines) == 1, f"Expected 1 head, got {len(non_empty_lines)}: {r.stdout}"


def test_downgrade_restores_s1a_revision(sqlite_db):
    """INV-S1C-007 下半段: downgrade -1 后 DB current revision 回到 'a88094ee4ea6'.

    R1 F003 修正：`alembic heads` 是脚本目录的 head 列表（跟脚本打包绝对无关数据库状态），
    downgrade 后 heads 永远不变；只有 `alembic current` 反映 DB 当前 revision。
    样板：tests/test_alembic_migration.py 走 schema inspect 判回滚。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0
    r = _run_alembic(['downgrade', '-1'], sqlite_db)
    assert r.returncode == 0

    # 用 alembic current 读 DB alembic_version 表
    r = _run_alembic(['current'], sqlite_db)
    assert r.returncode == 0, f"alembic current failed: {r.stderr}"
    # `alembic current` 输出形如 "a88094ee4ea6 (head)" 或 "a88094ee4ea6"
    current_rev = r.stdout.strip().split()[0] if r.stdout.strip() else ''
    assert current_rev == 'a88094ee4ea6', \
        f"Expected DB current revision a88094ee4ea6 after downgrade, got {current_rev!r} (raw: {r.stdout!r})"


def test_grades_table_created_with_expected_schema(sqlite_db):
    """INV-S1C-001 上半段: upgrade 后 grades 表存在且列完整、类型/nullability 精确."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    assert 'grades' in insp.get_table_names()

    cols = {c['name']: c for c in insp.get_columns('grades')}
    expected = {'id', 'school_id', 'name', 'grade_level', 'xueduan', 'sort_order', 'created_at', 'updated_at'}
    assert expected.issubset(set(cols.keys())), f"Missing cols: {expected - set(cols.keys())}"

    # 精确类型断言（F006 反镜像 —— 不只看字段存在）
    id_type = str(cols['id']['type']).upper()
    assert 'VARCHAR(36)' in id_type or 'STRING(36)' in id_type, f"grades.id 类型必须 VARCHAR(36)，实际 {id_type}"
    assert cols['school_id']['nullable'] is False
    assert cols['name']['nullable'] is False


def test_grades_unique_constraint(sqlite_db):
    """INV-S1C-001 下半段（R1 F005 修正）: grades 表含 UniqueConstraint(school_id, name).

    无此 test 则 migration 即使漏写 UniqueConstraint 也能在 Gate G1 假绿。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    uqs = insp.get_unique_constraints('grades')
    uq_col_sets = [frozenset(u['column_names']) for u in uqs]
    assert frozenset({'school_id', 'name'}) in uq_col_sets, \
        f"grades 缺 UniqueConstraint(school_id, name)，实际 unique_constraints: {uqs}"


def test_teaching_plans_table_schema_complete(sqlite_db):
    """INV-S1C-002 + ORC-S1C-003 综合断言（R2-F002 拆分后）:
    teaching_plans 表列完整 + FK 目标 ⊂ {schools, grades, users}.

    核心防守：禁止骨架表加 lesson_plans/resources 等 S4 才建的表 FK。
    三个 FK 独立存在断言拆到 test_teaching_plans_{schools,grades,users}_fk_exists 三个独立 test。
    """
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    assert 'teaching_plans' in insp.get_table_names()

    cols = {c['name']: c for c in insp.get_columns('teaching_plans')}
    expected = {'id', 'school_id', 'subject_code', 'grade_id', 'semester', 'weeks_json', 'created_by', 'created_at', 'updated_at'}
    assert expected.issubset(set(cols.keys()))

    fks = insp.get_foreign_keys('teaching_plans')
    referred = {fk['referred_table'] for fk in fks}
    excess = referred - {'schools', 'grades', 'users'}
    assert not excess, \
        f"ORC-S1C-003 违反：teaching_plans FK 目标含未建表 {excess}"


def test_teaching_plans_schools_fk_exists(sqlite_db):
    """R2-F002 INV-S1C-002a: teaching_plans.school_id → schools.id FK 独立断言."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0
    engine = create_engine(sqlite_db)
    fks = inspect(engine).get_foreign_keys('teaching_plans')
    matches = [fk for fk in fks
               if 'school_id' in fk['constrained_columns']
               and fk['referred_table'] == 'schools']
    assert len(matches) == 1


def test_teaching_plans_grades_fk_exists(sqlite_db):
    """R2-F002 INV-S1C-002b: teaching_plans.grade_id → grades.id FK 独立断言."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0
    engine = create_engine(sqlite_db)
    fks = inspect(engine).get_foreign_keys('teaching_plans')
    matches = [fk for fk in fks
               if 'grade_id' in fk['constrained_columns']
               and fk['referred_table'] == 'grades']
    assert len(matches) == 1


def test_teaching_plans_users_fk_exists(sqlite_db):
    """R2-F002 INV-S1C-002c: teaching_plans.created_by → users.id FK 独立断言（R2 核心：原 '子集断言' 会漏此条）."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0
    engine = create_engine(sqlite_db)
    fks = inspect(engine).get_foreign_keys('teaching_plans')
    matches = [fk for fk in fks
               if 'created_by' in fk['constrained_columns']
               and fk['referred_table'] == 'users']
    assert len(matches) == 1


def test_teaching_plans_unique_constraint(sqlite_db):
    """INV-S1C-002 下半段（R1 F005 修正）: teaching_plans 含 UniqueConstraint(school_id, subject_code, grade_id, semester)."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    uqs = insp.get_unique_constraints('teaching_plans')
    uq_col_sets = [frozenset(u['column_names']) for u in uqs]
    expected_uq = frozenset({'school_id', 'subject_code', 'grade_id', 'semester'})
    assert expected_uq in uq_col_sets, \
        f"teaching_plans 缺 UniqueConstraint(school_id, subject_code, grade_id, semester)，实际 unique_constraints: {uqs}"


def test_classes_grade_id_added_legacy_unchanged(sqlite_db):
    """INV-S1C-003 + ORC-S1C-002: classes 新增 grade_id；守旧 grade/grade_number 类型不变."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('classes')}

    # 新增
    assert 'grade_id' in cols, "classes 必须新增 grade_id 列"
    grade_id_type = str(cols['grade_id']['type']).upper()
    assert 'VARCHAR(36)' in grade_id_type or 'STRING(36)' in grade_id_type, \
        f"classes.grade_id 必须 VARCHAR(36)，实际 {grade_id_type}"
    assert cols['grade_id']['nullable'] is True

    # FK 指向 grades.id
    fks = insp.get_foreign_keys('classes')
    fk_targets = {(fk['referred_table'], tuple(fk['referred_columns'])) for fk in fks}
    assert ('grades', ('id',)) in fk_targets, f"classes.grade_id 必须 FK→grades.id，实际 FK {fk_targets}"

    # 守旧字段不动（ORC-S1C-002 机械化）
    grade_type = str(cols['grade']['type']).upper()
    assert 'VARCHAR(50)' in grade_type or 'STRING(50)' in grade_type, \
        f"守旧 classes.grade 必须 VARCHAR(50)，实际 {grade_type}"
    assert cols['grade']['nullable'] is False, "守旧 classes.grade 必须 NOT NULL"

    assert 'grade_number' in cols
    gn_type = str(cols['grade_number']['type']).upper()
    assert 'INTEGER' in gn_type, f"守旧 classes.grade_number 必须 INTEGER，实际 {gn_type}"


def test_bank_questions_grade_id_is_string36_with_fk(sqlite_db):
    """INV-S1C-004 + ORC-S1C-004: bank_questions.grade_id 类型 VARCHAR(36) + FK→grades.id (闭环 TD-S1A-002)."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)
    cols = {c['name']: c for c in insp.get_columns('bank_questions')}

    assert 'grade_id' in cols
    grade_id_type = str(cols['grade_id']['type']).upper()
    assert 'VARCHAR(36)' in grade_id_type or 'STRING(36)' in grade_id_type, \
        f"bank_questions.grade_id 必须 VARCHAR(36)（TD-S1A-002 闭环），实际 {grade_id_type}"
    assert cols['grade_id']['nullable'] is True

    # FK 指向 grades.id
    fks = insp.get_foreign_keys('bank_questions')
    grade_fk = [fk for fk in fks if 'grade_id' in fk['constrained_columns']]
    assert len(grade_fk) == 1, f"bank_questions.grade_id 必须有 1 个 FK，实际 {len(grade_fk)}"
    assert grade_fk[0]['referred_table'] == 'grades'
    assert grade_fk[0]['referred_columns'] == ['id']


def test_all_grade_id_fks_are_string36(sqlite_db):
    """ORC-S1C-004 扩展：遍历所有 grade_id 字段类型一致（classes/teaching_plans/bank_questions 三张表）."""
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0

    engine = create_engine(sqlite_db)
    insp = inspect(engine)

    for table in ('classes', 'teaching_plans', 'bank_questions'):
        cols = {c['name']: c for c in insp.get_columns(table)}
        assert 'grade_id' in cols, f"{table} 必须有 grade_id 列"
        type_str = str(cols['grade_id']['type']).upper()
        assert 'VARCHAR(36)' in type_str or 'STRING(36)' in type_str, \
            f"{table}.grade_id 必须 VARCHAR(36)，实际 {type_str}"


def test_existing_data_preserved_through_s1c_migration(sqlite_db):
    """R1 F004 修正：类型迁移 bank_questions.grade_id Integer→String(36) 的数据保全验证.

    流程（参 tests/test_alembic_s1a_bank.py::test_existing_data_preserved_through_migration 样板）：
      1. alembic upgrade a88094ee4ea6（到 S1-A head，pre-S1-C schema 就位）
      2. INSERT 若干 classes / bank_questions 行（带齐 NOT NULL 列；bank_questions.grade_id 故意留 NULL，
         因为 S1-A 时该列是 Integer 可留 NULL；S1-C alter 后应安全转为 String(36) NULL）
      3. alembic upgrade head（跑 S1-C）
      4. 校验：行数保持 + 关键列值保留；新列 classes.grade_id / teaching_plans 为 NULL（对齐 ORC"只加不填"）
    """
    from datetime import datetime, timezone

    # Step 1: upgrade 到 S1-A head
    r = _run_alembic(['upgrade', 'a88094ee4ea6'], sqlite_db)
    assert r.returncode == 0, f"upgrade a88094ee4ea6 failed: {r.stderr}"

    engine = create_engine(sqlite_db)

    # Step 2: INSERT 测试数据（带齐 NOT NULL 列，F003 教训传承）
    now = datetime.now(timezone.utc).isoformat()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO schools (id, code, name, is_active, created_at, updated_at)
            VALUES ('sch-s1c-smoke', 'S1C_SMOKE', '测试学校', 1, :now, :now)
        """), {'now': now})
        conn.execute(text("""
            INSERT INTO classes (id, name, grade, school_id, created_at, updated_at)
            VALUES ('cls-s1c-001', '高一1班', '高一', 'sch-s1c-smoke', :now, :now)
        """), {'now': now})
        conn.execute(text("""
            INSERT INTO bank_questions (id, question_type, max_score, sample_count, school_id, created_at, updated_at)
            VALUES ('bq-s1c-001', 'essay', 10.0, 0, 'sch-s1c-smoke', :now, :now)
        """), {'now': now})

    # Step 3: upgrade 到 S1-C head
    r = _run_alembic(['upgrade', 'head'], sqlite_db)
    assert r.returncode == 0, f"upgrade head (S1-C) failed: {r.stderr}"

    # Step 4: 校验数据保留 + 新列对齐
    with engine.connect() as conn:
        # classes 行保留，新 grade_id 列 NULL（ORC"只加不填"）
        row = conn.execute(text(
            "SELECT id, name, grade, grade_id FROM classes WHERE id='cls-s1c-001'"
        )).mappings().first()
        assert row is not None, "classes 行丢失（migration 破坏）"
        assert row['name'] == '高一1班'
        assert row['grade'] == '高一'
        assert row['grade_id'] is None, "classes.grade_id 应为 NULL（S1-C migration 不反向填充）"

        # bank_questions 行保留，grade_id 从 Integer NULL 迁移到 String(36) NULL
        row = conn.execute(text(
            "SELECT id, question_type, max_score, grade_id FROM bank_questions WHERE id='bq-s1c-001'"
        )).mappings().first()
        assert row is not None, "bank_questions 行丢失（migration 破坏）"
        assert row['question_type'] == 'essay'
        assert abs(row['max_score'] - 10.0) < 1e-6
        assert row['grade_id'] is None, \
            "bank_questions.grade_id 应为 NULL（S1-A NULL→S1-C NULL 安全迁移）"

        # teaching_plans 表新建但无数据（默认空）
        count = conn.execute(text("SELECT COUNT(*) FROM teaching_plans")).scalar()
        assert count == 0, f"teaching_plans 新表应为空，实际 {count} 行"

        # grades 表新建但无 seed 数据（见 test_debt #3）
        count = conn.execute(text("SELECT COUNT(*) FROM grades")).scalar()
        assert count == 0, f"grades 新表应为空（seed 归 test_debt #3），实际 {count} 行"
```

- [ ] **Step 5.2: 跑测试确认 PASS**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_alembic_s1c_admin.py -v --tb=short 2>&1 | tail -40
```

Expected: 12 个 test 全 PASS（原 9 个 + R1 F004/F005 补 3 个：test_grades_unique_constraint / test_teaching_plans_unique_constraint / test_existing_data_preserved_through_s1c_migration）。

- [ ] **Step 5.3: 回归验证 — 全量测试**

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest --tb=no -q 2>&1 | tail -10
```

Expected:
- 原 22 failed + 1 error 保持（不新增 failure）
- S1-C 新增测试全绿（Task 1 的 8 + Task 2 的 5 + Task 3 的 7 + Task 5 的 12 = **32 个新 test**；R1→R2 Task 5 从 9 增至 12 新增 F004/F005 对应断言）
- 预期总计：`(2079 + 29) passed / 22 failed / 1 error / 23 skipped = 2108 passed`（若 S1-A 测试数变化按实测调整）

- [ ] **Step 5.4: Commit Task 5**

```bash
git add tests/test_alembic_s1c_admin.py
git commit -m "$(cat <<'EOF'
test(alembic): S1-C T5 migration smoke + Gate G1-S1C 通过

12 个 test 机械化 5 条 ORC + F004/F005 repair：
- ORC-S1C-001: test_migration_file_down_revision_matches_prev_head / test_migration_chain_head_is_single / test_downgrade_restores_s1a_revision
- ORC-S1C-002: test_classes_grade_id_added_legacy_unchanged（守旧字段精确长度/nullability 断言）
- ORC-S1C-003: test_teaching_plans_table_schema_complete（越界综合断言）+ test_teaching_plans_{schools,grades,users}_fk_exists 三个独立 FK 断言（R2-F002 拆分）
- ORC-S1C-004: test_bank_questions_grade_id_is_string36_with_fk / test_all_grade_id_fks_are_string36
- ORC-S1C-005: test_orm_registration_three_entry_points（__init__.py 零内容 + 2 处 import 命中）
- INV-S1C-001/002: test_grades_table_created_with_expected_schema / teaching_plans

S1-C Gate G1 证据：全量测试 baseline 21 failed 保持（不新增，2102 passed 基线 @ 2026-04-24T20:14），新加 32 test 全绿。

refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 5
EOF
)"
```

---

## Gate G1-S1C 通过条件

执行完 Task 1-5 后验收：

1. **migration 可逆**: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 在空 DB 三阶段成功
2. **chain 单 head**: `alembic heads` 返回 1 行 {S1-C slug}
3. **全量测试**: baseline 21 failed 保持（不新增，S1-A 后实测 2102 passed / 21 failed / 23 skipped @ 2026-04-24T20:14），S1-C 32 个新 test 全绿
4. **ORM 注册三入口断言**: `alembic/env.py` + `src/edu_cloud/api/app.py` + `tests/conftest.py` 各含 Grade import；`tests/conftest.py` 额外含 `edu_cloud.modules.calendar.models` import（TeachingPlan 测试期注册）；`src/edu_cloud/models/__init__.py` 零改动
5. **类型一致**: classes/teaching_plans/bank_questions 三张表的 grade_id 全部 VARCHAR(36)
6. **TD-S1A-002 闭环**: bank_questions.grade_id FK 建立，deadline 2026-05-08 前达成

---

## Deferred / Design Concerns

1. **F009 不归本 S1-C**: `subject_code` vs `course_code` 参数语义决策归 S1-D `StudentProfileView` VO plan（本 plan 无新端点）
2. **Grade seed 数据**: 各学校年级列表由 S4 4.3 TeachingPlanEditor 启动时由教务填入（test_debt #3 deadline 2026-07-15）
3. **Class.grade 字段废弃**: 固守 ORC-S1C-002 守旧字段不动，弃用方案独立 T3 任务（test_debt #1 deadline 2026-06-15）
4. **TeachingPlan 业务 service/router/frontend**: 归 S4 4.3 `calendar.teaching_plan_service`（test_debt #4 deadline 2026-08-31）
5. **PaperAccessLevel DB CHECK 约束 / SQLAlchemy Enum 列**: 归 S4 4.2 `paper.access_policy`（test_debt #2 deadline 2026-06-30）
6. **S1-A 既有 22 failed + 1 error 技术债**: 独立 T3 任务评估是否构成 L019 打地鼠模式，不归 S1-C scope
7. **生产库 mcu.asia migration**: 7 天 deadline 前 S1-A/B/C/D 全 R1 PASS 后由独立 T3 执行；S1-C 只保证空 DB 与 SQLite smoke 可逆，生产库 spike 走独立 Task

---

## Self-Review（writing-plans skill 强制）

1. **Spec coverage**: parent design §4.1 deliverables 1.3 ✓ (Task 1+4) / 1.4 ✓ (Task 2+4) / 1.5 ✓ (Task 3) / TD-S1A-002 闭环 ✓ (Task 3+4)。F009 明确 Deferred 到 S1-D。**零 spec 遗漏**。

2. **Placeholder scan**:
   - 未出现 "TBD" / "TODO" / "implement later" / "fill in details" / "appropriate error handling" / "Similar to Task N"
   - 每个 Step 含可执行 bash / 完整代码块 / 精确 Expected 输出
   - F006 反镜像测试用 `@pytest.mark.parametrize` 真实校验，不是"写测试"占位

3. **Type consistency**:
   - `grade_id` 一致 `String(36)`（Grade.id / Class.grade_id / TeachingPlan.grade_id / BankQuestion.grade_id 四处统一）
   - Grade ORM 类名 / `grades` 表名 / `fk_grades_school_id` FK 名 / `uq_grade_school_name` Unique 名，均前后一致
   - TeachingPlan ORM 类名 / `teaching_plans` 表名 / `uq_teaching_plan_scope` Unique 名，均前后一致
   - PaperAccessLevel 3 成员值 `teacher_private` / `school_shared` / `district_shared`，全 plan 引用 10+ 处字面一致

4. **ORC 对齐**:
   - ORC-S1C-001 linear chain 第 2 环 → Task 4 Step 4.3 验证 + Task 5 Step 5.1 机械化
   - ORC-S1C-002 Class 守旧字段不动 → Task 1 Step 1.4 追加禁改 + Task 5 Step 5.1 精确类型断言
   - ORC-S1C-003 teaching_plans FK 限定 → Task 2 Step 2.3 + Task 5 FK 集合断言
   - ORC-S1C-004 FK 类型统一 → Task 3 Step 3.4 ORM + Task 4 Step 4.4 migration + Task 5 三表断言
   - ORC-S1C-005 ORM 注册路径 → Task 1 Step 1.5/1.6 加行 + Task 5 Step 5.1 `test_orm_registration_three_entry_points`

5. **Evidence Block 真实性（F008 传承）**:
   - E-001 真实 `alembic heads` 实测输出（2026-04-24T20:12）+ 负面 grep 命令 + 完整 chain
   - E-002 真实 `src/edu_cloud/models/base.py:11-14` IdMixin 源码引用 + **R1 F007 修正**：去除"全项目零 Integer PK"失真断言，改为"新建跨模块共享表沿用 IdMixin 约定（analytics/menu/knowledge_tree 历史 Integer PK 为遗留设计）"
   - E-003 真实 `wc -l __init__.py` 输出 + `orm-placement.md §7` 反模式表
   - E-004 真实 Class 源码 L12-14 引用 + 负面 grep (Class.grade 消费者)
   - E-005 真实 design §8.2 跨层清单引用 + 负面 grep (lesson_plans 零结果)

---

## R1 → R2 修复记录（2026-04-24T20:49）

R1 FAIL → 7 findings 一次性修复（跨模块重构触发 R2 允许条件）。所有修复保持 5 条 ORC / 8 条 INV / 4 条 CE 的主体结构不变，不引入新 Task。

| R1 Finding | 修复位置 | 修复摘要 |
|---|---|---|
| F001 HIGH conftest.py 缺 Grade/TP 注册 | File Structure 新增 tests/conftest.py 行 / ORC-S1C-005 三入口化 / INV-S1C-008 更新 / Task 1 新加 Step 1.7 补 conftest import + Step 1.8 grep 断言 / Task 5 test_orm_registration_three_entry_points 追加 conftest 断言 | ORM 注册从"env+app 两处"扩为"env+app+conftest 三处"，保证测试期 Base.metadata.create_all 能发现 Grade/TeachingPlan |
| F002 HIGH smoke 起点不可能态 | Task 4 Step 4.6 | `alembic stamp a88094ee4ea6` → `alembic upgrade a88094ee4ea6`（从 base 真跑到 S1-A head，让 classes/bank_questions 前置表就位再跑 S1-C） |
| F003 HIGH heads 误作回滚指标 | Task 4 Step 4.6 + Task 5 test_downgrade_restores_s1a_revision（改名 + 逻辑改用 `alembic current`）+ INV-S1C-007 statement | `alembic heads` 只判脚本目录 chain 单 head；回滚验证走 `alembic current` 读 DB revision |
| F004 HIGH test_existing_tables_data_preserved 未落地 | Task 5 新加 test_existing_data_preserved_through_s1c_migration | 预置 S1-A 期 classes/bank_questions 数据 → 跑 S1-C → 校验行数保留 + grade_id NULL 安全迁移 |
| F005 HIGH invariant 与测试不对齐 | Task 5 新加 test_grades_unique_constraint + test_teaching_plans_unique_constraint / 所有测试名引用统一（`test_migration_file_down_revision_matches_prev_head` / `test_teaching_plans_fk_targets_are_existing_tables` / `test_downgrade_restores_s1a_revision`）| UniqueConstraint 断言从 table 综合 test 拆出独立 test；plan 引用名与函数体精确对齐 |
| F006 MED 测试目录路径错 | File Structure + 全局 tests/models/ → tests/test_models/ + tests/modules/...→tests/test_models/ 机械替换 | 4 个新 test 文件统一放 tests/test_models/（跟既有 test_calendar.py / test_user_model.py 同级）避免建新目录；Task 2 回归命令 `tests/test_modules/test_calendar/` → `tests/test_models/test_calendar.py` |
| F007 MED E-002 证据失真 | E-002 Q2_excluded 第 1 条改写 | 去除"全项目零 Integer PK"负面断言，明确历史 Integer PK 表（analytics/menu/knowledge_tree）为遗留设计，"新建表沿用 IdMixin"才是决策依据 |

**修复侧总测试增量变化**: Task 5 从 9 个 test 增至 12 个（+3）。R2 总增量 8+5+7+12 = **32 个新 test**。

---

## 交接提示

- **Plan commit 后的下一步**: `codex-review plan` R1（gates.json 硬拦截）
- **R1 FAIL 处置**: 拆更细 topic 或 manual_override（按 finding 严重度 + 用户决策）
- **R1 PASS 后执行**: 独立新会话，用 `superpowers:executing-plans` 或 `subagent-driven-development`
- **Deadline 锚点**: 2026-05-01 前 S1-A/B/C/D 全 R1 PASS，关闭 parent `haofenshu-s1-l1-data-layer` 的 manual_override
