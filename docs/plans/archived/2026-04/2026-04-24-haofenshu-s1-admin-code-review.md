# S1-C Admin Code Review（Gate 2）

**时间**: 2026-04-24 22:44:30 +0800  
**审查范围**: `2207723~1..6717a89`（Task 1-5 + 收尾）  
**结论**: PASS

## 第一段：测试充分性（Test Adequacy）

- 已执行：`.venv/bin/python -m pytest tests/test_models/ tests/test_alembic_s1c_admin.py tests/test_services_exam/test_bank_service.py -v`，结果 `102 passed in 45.26s`。
- 已执行 Alembic smoke：临时 SQLite 上 `alembic upgrade head` → `alembic current` → `alembic downgrade -1` → `alembic current`，实测从 `f311eb126798` 回到 `a88094ee4ea6`，命令通过。
- Contract Pack 对应实现层面的关键断言已落地：
  - R2-F001：`TeachingPlan` canonical 已在 `src/edu_cloud/models/teaching_plan.py:1`，且三入口独立 import 已在 `alembic/env.py:86`、`src/edu_cloud/api/app.py:66`、`tests/conftest.py:48`。
  - R2-F002 / INV-S1C-001：`tests/test_alembic_s1c_admin.py:157` 已补 `grades.school_id -> schools.id` 与 `sort_order default=0` 断言。
  - R2-F002 / INV-S1C-002：ORM 层 3 个 FK 独立断言在 `tests/test_models/test_teaching_plan.py:37`、`tests/test_models/test_teaching_plan.py:46`、`tests/test_models/test_teaching_plan.py:55`；migration 层 3 个 FK 独立断言在 `tests/test_alembic_s1c_admin.py:220`、`tests/test_alembic_s1c_admin.py:233`、`tests/test_alembic_s1c_admin.py:246`。
  - R2-F002 / INV-S1C-008：`tests/test_alembic_s1c_admin.py:72` 已使用字节级 SHA256 校验 `src/edu_cloud/models/__init__.py`。
  - R2-F003：`contract_pack.test_debt` 第 5 条已登记，deadline 为 `2026-08-31`，见 `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:387`。
  - R1 F003 残余：Task 4 回滚判定已改为 `alembic current`，见 `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:1117`、`docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:1139`。
- 未发现会导致当前实现“只测 happy path 即假绿”的缺口；新增 migration 测试中多数断言在删除核心 DDL/FK/default 逻辑后都会失败。

## 第二段：行为正确性（Behavioral Correctness）

- Grade ORM、TeachingPlan ORM、PaperAccessLevel、`Class.grade_id`、`bank_questions.grade_id` 与 migration 文件彼此对齐；`Class.grade` / `grade_number` 仅追加 `grade_id`，未改守旧字段，见 `src/edu_cloud/modules/student/models.py:12`。
- `alembic/versions/f311eb126798_s1c_admin_schema.py:22` 的 `down_revision='a88094ee4ea6'` 与线性链约束一致；独立 smoke 也验证了升级/回滚路径。
- `bank_questions.grade_id` 的 PG 迁移表达式 `grade_id::text` 在“既有数据全 NULL”的已声明前提下与当前测试覆盖一致；本次数据保全测试也仅构造 NULL 历史值，见 `tests/test_alembic_s1c_admin.py:365`。
- `app.py` 中 Grade / TeachingPlan import 位于 `lifespan()` 内、且在 `Base.metadata.create_all()` 之前执行，作用域正确，见 `src/edu_cloud/api/app.py:23` 与 `src/edu_cloud/api/app.py:69`。
- 未发现新增跨层反向依赖、额外未声明 API、或违反 ORC-S1C-001~005 的实现。

## 第三段：未测试风险（Non-tested Risks）

- 已登记且我认可的 test debt：Task 1/2/3 仍缺 service/API 级入口验证，但该批次是 data-layer 任务、未新增业务入口，且计划已在 `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:387` 明确登记到 S4，deadline `2026-08-31` 可接受。
- 未被本轮直接动态覆盖的剩余风险主要是“升级后写入新 UUID grade_id 数据，再执行 downgrade -1”的场景；当前 contract 明确以“既有数据全 NULL”的迁移前提为验证边界，因此我将其视为残余风险而非本轮 defect。

## Findings

### F001
- ID: F001
- Severity: MED
- Category: design_concern
- Type: design_concern
- Before-behavior: 计划文档的 Contract Pack / ORC / File Structure / 任务片段仍将 TeachingPlan 描述为放在 `modules/calendar/models.py`，并把验证映射指向旧测试名 `test_teaching_plans_fk_targets_are_existing_tables`，同时把 INV/ORC 的 `verification` 维持为 `pending_test`。
- After-behavior: 实际实现已经切换为 `src/edu_cloud/models/teaching_plan.py` + env/app/conftest 三入口独立 import，并把 teaching_plans FK 验证拆成 3 个 migration 测试与 3 个 ORM 测试，但 plan 未同步刷新，导致仅依赖 Contract Pack 无法还原真实实现与验证闭环。
- Evidence:
  - `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:108`
  - `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:242`
  - `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:269`
  - `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:294`
  - `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:318`
  - `docs/plans/2026-04-24-haofenshu-s1-admin-plan.md:399`
  - `src/edu_cloud/models/teaching_plan.py:1`
  - `tests/test_alembic_s1c_admin.py:72`
  - `tests/test_alembic_s1c_admin.py:220`
  - `tests/test_alembic_s1c_admin.py:233`
  - `tests/test_alembic_s1c_admin.py:246`
- Impact: 这是审计/契约层漂移风险，不影响当前代码运行结果，但会降低后续 reviewer/Planner 仅凭计划文本复核 ORC/INV 的准确性；尤其 INV-S1C-002、INV-S1C-008 与 ORC-S1C-005 已不再是 plan 文本所描述的那套验证机制。
- Repair hypothesis: 此为设计层面关注点，需设计者决策，审查者不提供修复方案。

## 结论

- 未发现阻塞性的 `defect_fix` 或 `test_gap`。
- 发现 1 条不阻塞 PASS 的 `design_concern`：计划/Contract Pack 文本与实际实现存在 freshness 漂移。
- 最终结论：PASS
