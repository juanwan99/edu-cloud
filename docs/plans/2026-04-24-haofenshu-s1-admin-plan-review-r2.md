# S1-C Admin Plan Review R2（FAIL）

**Date**: 2026-04-24T21:01+08:00
**Reviewer**: GPT-5.4 (Codex CLI via codex-review skill)
**Reviewed Plan**: [2026-04-24-haofenshu-s1-admin-plan.md](./2026-04-24-haofenshu-s1-admin-plan.md) (commit `20a84ad`)
**R1 Report**: [-plan-review.md](./2026-04-24-haofenshu-s1-admin-plan-review.md) (commit `20a84ad`)
**Raw Log**: `.codex-plan-review-raw-s1c-r2-20260424_210142.log` (约 4.8 千行 / 约 316KB)
**Raw Log SHA256**: `bcd7d213a0420cbce2978fd06ed4811ea760ee48ad77b1eeb869ce347f745d99`

---

## 结论：R2 FAIL

R1 的 7 个 findings 中 F001/F002/F004/F006/F007 已闭环。剩余两类问题：
- **R1 F005 未完全闭环** → R2-F002 contested
- **R1 F003 残留** → 未单独 finding（R2-F001/F002 已足够判 FAIL，R1 F003 残留列为附录）
- **2 HIGH + 1 MED 新问题** → R2-F001/F002/F003

按 codex-review skill §Gate 条件：**R2 FAIL → 禁 R3+**，必须拆 topic 或 manual_override（用户决策）。

---

## Findings 汇总

| ID | Severity | Category | Type | 概括 |
|---|---|---|---|---|
| R2-F001 | HIGH | code-bug | defect_fix | TeachingPlan 在 Alembic/app 入口**实际无法发现**：plan 声称 `app.py` 已有 `import edu_cloud.modules.calendar.models` 无需改，但代码库实测 `app.py:47` 只 `import edu_cloud.models.calendar`（加载 CalendarEvent/NotificationRule）；modules/calendar/models.py 根本不被任何生产代码加载。TeachingPlan 只在 conftest.py 注册 → Alembic autogenerate 和应用启动建表均看不到 |
| R2-F002 | HIGH | test-gap | defect_fix | R1 F005 contested：3 条 invariant 声明比测试断言宽。INV-S1C-002 说"3 个 FK 含 created_by→users"，test 只断"至少 2 FK + subset"；INV-S1C-001 说"school_id 带 FK + sort_order default=0"，test 没测 FK 也没测 default；INV-S1C-008 说"字节级一致"，test 只检查"0 非空行"（空白字符漂移假绿） |
| R2-F003 | MED | test-gap | defect_fix | Task 1/2/3 的"入口"都是 import + 实例化 + `__table__` introspection，属于内部结构验证，没有 CLI/startup/service/API 级入口——按 review-templates.md test-gap 判定规则"无入口级验证"→ test-gap MED |

**R1 残留（未单独编号，列为附录）**:
- R1 F003 核心方向已改 `alembic current`，但正文仍有残留：Task 4 测试契约段还写"downgrade 后 `alembic heads` 返回 `a88094ee4ea6`"（期望条件描述错），Task 5 函数体附近残留旧测试名——机械性清理未做彻底

---

## 核心 Findings 详述

### R2-F001（HIGH）TeachingPlan 注册链路断裂

**Before**: plan §Evidence E-003 + ORC-S1C-005 + File Structure + Task 1 的修复策略：
- Grade 放 `src/edu_cloud/models/grade.py` + 三入口 import（env.py + app.py + conftest.py） ✓
- TeachingPlan 放 `src/edu_cloud/modules/calendar/models.py` + **仅 conftest.py 加 import**（plan 声称"app.py 已有 `import edu_cloud.modules.calendar.models` 无需改"）

**After**: TeachingPlan 必须在 3 条入口（Alembic autogenerate / 应用启动 `Base.metadata.create_all()` / 测试建库）都可见，不能只在测试入口注册。

**Evidence（GPT 独立核查代码库实测）**:
- plan Evidence E-003 + ORC-S1C-005 + File Structure + Task 1 Step 1.6 指令把 TeachingPlan 仅放进 `tests/conftest.py`
- plan E-003 声称 `src/edu_cloud/api/app.py` "已有 `import edu_cloud.modules.calendar.models` 无需改" — **实测错**
- `src/edu_cloud/api/app.py` 实际是 `import edu_cloud.models.calendar`（加载 `models/calendar.py`，定义 CalendarEvent/NotificationRule，不等于 `modules/calendar/models.py`）
- `alembic/env.py` 同样只有 `import edu_cloud.models.calendar`，不触发 `modules/calendar/models.py` 加载
- `src/edu_cloud/models/calendar.py` 只定义 CalendarEvent + NotificationRule（plan 把 TeachingPlan 追加到 `modules/calendar/models.py` 文件，与 `models/calendar.py` 是两个独立文件）
- Task 5 `test_orm_registration_three_entry_points` 只验证三处有 Grade + 仅 conftest.py 有 calendar.models，没验证 TeachingPlan 的 Alembic/app 入口可见性

**Impact**: migration smoke 可绿（smoke 走 alembic subprocess，subprocess 会 import env.py 里的完整列表，若 env.py 不 import `modules/calendar/models` 则 teaching_plans 表压根不在 autogenerate 视野），但生产启动 `Base.metadata.create_all()` 和 Alembic autogenerate 都看不到 TeachingPlan。真实部署时 S1-C migration 即使包含 `op.create_table('teaching_plans')`（硬编码 DDL）能跑成功，但后续 S1-B/D/S2 想用 `TeachingPlan.__table__` 做任何 query/insert/seed 都会失败（TeachingPlan 未在 Base registry）。

**Repair 方向**:
- 把 TeachingPlan 的 canonical location 改为 `src/edu_cloud/models/teaching_plan.py`（与 Grade 策略完全一致，platform-level 表）；三入口（env.py + app.py + conftest.py）各加 1 行 `import edu_cloud.models.teaching_plan`
- 或保留 `modules/calendar/models.py` 不动，但在 env.py + app.py + conftest.py 三入口**各加 1 行** `import edu_cloud.modules.calendar.models`
- 禁止：继续依赖"只在 conftest.py 注册"；TeachingPlan 重复定义到第二个 ORM 位置；改 `src/edu_cloud/models/__init__.py` 绕过
- **requires independent fix design + Semantic Regression Gate**

---

### R2-F002（HIGH）Contract Pack invariant 比测试宽（R1 F005 contested）

**Before**: 3 条 invariant 的 statement 比 Task 5 给出的测试实际断言强，核心偏差实现能假绿。

**After**: 每条 invariant 的关键子句都应被直接断言；做不到的子句降级为 `uncovered` 或记 `test_debt`。

**Evidence**:
1. **INV-S1C-002 vs test_teaching_plans_fk_targets_are_existing_tables**:
   - invariant 说"全部 3 个 FK 目标"含 `created_by FK→users.id`
   - test 只断言"FK 目标 ⊂ {schools, grades, users} 且含 schools + grades"
   - 漏写 `created_by → users` FK 时 test 仍 PASS（assert 只要求"子集 + 至少 2 FK"）

2. **INV-S1C-001 vs test_grades_table_created_with_expected_schema**:
   - invariant 说 `school_id FK→schools.id` + `sort_order default 0`
   - test 只验证表存在 / 列集合 / id 类型 / 2 个 nullable 位，**零 FK 断言、零 default 断言**

3. **INV-S1C-008 vs test_orm_registration_three_entry_points**:
   - invariant 说 `models/__init__.py` "字节级一致（未修改）"
   - test 只检查"0 非空行"，加空白字符 / 空行 / 尾随空格 / BOM 都不会 fail

**Impact**: Gate G1 可能在 contract 实际破损时假绿。尤其 `TeachingPlan.created_by → users` FK 漏掉 / `grades.sort_order` default 丢失 / `models/__init__.py` 被 executor 无意改了空白字符，都能通过审查却破坏 L1 契约。

**Repair 方向**:
- 把 invariant 拆到可机械验证的粒度（每个子句独立 assert）；INV-S1C-002 含 3 个 FK 可拆为 INV-S1C-002a/b/c，每个对应 1 测试函数
- 或降级弱测试子句为 `uncovered` 并登记 `test_debt`（不接受"子集 + 数量下限"这种松绑）
- 禁止：削弱 invariant prose 以适配弱测试；继续用"子集断言"替代"必须存在"；把"字节级一致"偷换为"非空行为空"
- **requires independent fix design + Semantic Regression Gate**

---

### R2-F003（MED）Task 入口只有 introspection，无入口级验证

**Before**: Task 1/2/3 的"入口"字段全部是 import / 实例化 / `__table__` introspection。

**After**: 每个行为变更 Task 至少有一个 CLI/startup/service/API 级入口验证，否则遗漏 wiring 失败。

**Evidence**:
- Task 1 入口：`from edu_cloud.models.grade import Grade` / `Grade(...)` / `Class.grade_id` 存在
- Task 2 入口：`from edu_cloud.modules.calendar.models import TeachingPlan` / 实例化 / `TeachingPlan.__table__.foreign_keys`
- Task 3 入口：`from edu_cloud.modules.paper.constants import PaperAccessLevel` / 枚举 round-trip / `BankQuestion.__table__.columns['grade_id']`
- `~/.claude/rules-t3/review-templates.md` test-gap 判定段明确"无入口级验证（测试只调内部函数，不经过用户可触达的入口）"→ test-gap MED

**Impact**: 即使内部 ORM/Enum 结构正确，真实 Alembic / app startup / service 消费路径仍可能出错——"结构看对、入口仍坏"的假绿风险。

**Repair 方向**:
- Task 1/2 至少各补 1 个实际入口 slice：如"跑 `alembic upgrade head` subprocess 后在 `Base.metadata.tables` 里能看到 `grades` / `teaching_plans`"、"app 启动 lifespan 后 `create_all` 建出 grades 表行"
- Task 3 补 PaperAccessLevel 真实消费 service/API 入口——但本 plan scope 没有 paper service/API（归 S4）→ 可登记 `test_debt`
- 如实在做不到入口验证，登记到 `test_debt` 并明确 deadline，不接受继续把 introspection 当完整入口

---

## Gate 决策

按 codex-review skill §Gate 条件：
- R1 FAIL → R2（已走）
- **R2 FAIL → 禁 R3+**（gates_lib 入口硬拒绝 round≥3 非 blocked 写入）
- **可选路径：**
  1. **拆 topic**：把 S1-C 拆成 S1-C-base（Grade + Class.grade_id + PaperAccessLevel + bank.grade_id FK 闭环 TD-S1A-002）+ S1-C-teaching（TeachingPlan 单独 topic，可同时修正 R2-F001 的注册策略），每个子 topic 重新走 R1
  2. **manual_override**：用户授权接受当前 FAIL 进入执行，R2-F001/F002 修复责任委托给 Executor（Executor 可在执行期自主修正注册策略 + 补 FK/default 断言），R2-F003 登记 test_debt

---

## 两条路径对比

| 维度 | 拆 topic | manual_override |
|---|---|---|
| **R2-F001 修复责任** | 新 topic 的 Planner 重写 | Executor 执行期自主修正（Plan 外修复） |
| **R2-F002 修复责任** | 新 topic 的 Contract Pack 重写 | Executor 补 FK/default 断言（算"Executor 扩展 test 契约"） |
| **R2-F003 修复责任** | 新 topic 补入口级 slice | 登记 test_debt（S4 补业务 service 时一并做） |
| **Alembic chain 影响** | 新增 1 环（S1-C-base → S1-C-teaching → 链长 +1） | 无影响（linear chain 保持 S1-C → S1-A） |
| **Gate 开销** | 2 次 Gate 1 R1（两个子 topic 各一次） | 1 次 Gate 2（code review） |
| **7 天 deadline (2026-05-01)** | 紧张（R1 review 本身 10 分钟，两 plan 各 R1 至少 1 小时 + 修复迭代） | 宽松（可立即进入 Executor） |
| **下游 (S1-B / S1-D) 依赖对齐** | 需 update（down_revision 变链序） | 无变化 |
| **审计可追溯性** | 清晰（每个子 topic 独立 R1 PASS 记录） | 有污点（manual_override 记录需说明风险承担） |

---

## 建议（非授权）

**推荐 manual_override**（理由）：
1. R2-F001/F002/F003 的修复方向都已明确，不涉及设计方向重构，**Executor 可在执行阶段自主完成**
2. 拆 topic 引入 alembic chain 新环，下游 S1-B/D 还得重新串链，7 天 deadline 紧张
3. 本 plan 主体结构（5 ORC / 8 INV / 4 CE / 5 Tasks）在 R2 review 里已被 GPT 认可，R2-F001/F002/F003 属**局部细节加固**而非方案错误
4. manual_override 需用户明示授权，不是 Planner 单方决定

**反向考虑**（支持拆 topic）：
1. L017 教训：GPT finding 即使是 defect_fix 也要人工决策 — 不自动 manual_override
2. 拆 topic 让每个子 plan 的 Gate 1 R1 PASS，审计链更清晰
3. TeachingPlan 的 ORM 注册策略错选是**规划阶段的 fact 错**（我调研时误读 `import edu_cloud.models.calendar` 的语义），拆 topic 可彻底重写 TeachingPlan 的注册设计

---

## Raw Evidence

Full Codex output: `docs/plans/.codex-plan-review-raw-s1c-r2-20260424_210142.log`（约 4.8 千行 / ~316KB）
SHA256: `bcd7d213a0420cbce2978fd06ed4811ea760ee48ad77b1eeb869ce347f745d99`

R1 report: `docs/plans/2026-04-24-haofenshu-s1-admin-plan-review.md`
R1 raw log: `docs/plans/.codex-plan-review-raw-s1c-20260424_203300.log`（c6b1bad9...）

---

## 待用户决策

用户已在 prompt 明示"R2 FAIL → manual_override 或拆更细 topic，禁 R3+"。具体选哪条，需要用户确认：
- **选 A. manual_override**：我写 override receipt（reason 含 R2 finding 摘要 + Executor 修复分工），plan commit 不动，会话进入 executor 阶段
- **选 B. 拆 topic**：我出拆分方案（topic 边界 + Alembic chain 串链方案 + deadline 时序），用户批准后我把当前 plan archive，重新起两个 R1
