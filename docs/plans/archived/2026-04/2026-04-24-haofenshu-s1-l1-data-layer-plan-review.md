# S1 L1 数据层 Plan Review R1（FAIL）

**Date**: 2026-04-24
**Reviewer**: GPT-5.4 (Codex CLI, session 019dbd42-f08e-7702-a9b7-baa2c96fe013)
**Reviewed Plan**: [2026-04-24-haofenshu-s1-l1-data-layer-plan.md](./2026-04-24-haofenshu-s1-l1-data-layer-plan.md) (commit `24d4e2b`)
**Parent Design**: [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md)
**Raw Log**: `.codex-plan-review-raw-20260424_101253.log` (7575 lines, 545KB)

---

## 结论：R1 FAIL

存在多条 `code-bug` / `test-gap` 的 HIGH/MED finding，当前 plan 不应进入执行。

按 [review-templates.md](~/.claude/rules-t3/review-templates.md#L174) 口径：HIGH/MED 未修复 → FAIL。

---

## Findings 汇总

| ID | Severity | Category | Type | 概括 |
|---|---|---|---|---|
| F001 | HIGH | code-bug | defect_fix | Alembic down_revision 绑错：plan 写 `f7a3b2c1d456`，真实 head 是 `36e25241e55d` |
| F002 | HIGH | code-bug | defect_fix | ORM 注册机制误解：`models/__init__.py` 是空的；真正注册走 `alembic/env.py` 显式 import + `api/app.py` 启动导入 |
| F003 | HIGH | code-bug | defect_fix | smoke test INSERT 缺 `sample_count/created_at/updated_at` 必填列 |
| F004 | HIGH | test-gap | defect_fix | 行为变更 Task 无 5 字段测试契约段（入口/反例/边界/回归/命令），无 3 边界条件段 |
| F005 | HIGH | test-gap | defect_fix | plan 缺 Contract Pack（invariants / counter_examples / risk_modules / test_debt） |
| F006 | HIGH | test-gap | defect_fix | Task 2 depth_level 枚举测试是逻辑镜像（`VALID == {"subject",...}`），错实现不会 fail |
| F007 | MED | test-gap | defect_fix | `school` fixture 不在 root `tests/conftest.py`，Task 7 新测试会直接报 fixture 不存在 |
| F008 | MED | design-concern | defect_fix | Evidence Block 缺真实 file:line / grep 输出 / 命令结果；负面断言（"S1 不改 conduct/AI Agent"）无 Grep 零结果证据 |
| F009 | MED | code-bug | defect_fix | 新端点 `/profile/students/{id}/view` 暴露 `subject_code`，但现有 profile API 用 `course_code`，且 `subject_code` 只过滤 trend/error，knowledge_map 不参与，语义不自洽 |

---

## 核心 Findings 详述

### F001（HIGH）Alembic down_revision 绑错

**Before**: plan 绑定 `down_revision = 'f7a3b2c1d456'`，并把 Gate G1 的 downgrade 回滚目标也写成该 revision。

**After**: 必须绑定到仓库真实单 head `36e25241e55d`。

**Evidence**:
- plan L966 写 "现最新 migration `add_teacher_profile_fields`"
- plan L1022/L1259 回滚到 `f7a3b2c1d456`
- 本地验证 `alembic heads` → `36e25241e55d (head)`
- `alembic current` → `e241e1568792`（生产库当前位置）
- 完整链路：`36e25241e55d ← e241e1568792 ← 874f6f9c14cc（merge）← (45c9d83d780e, f7a3b2c1d456)`
- `f7a3b2c1d456_add_teacher_profile_fields.py:9` 其实 `down_revision = None`（是早期分支根）

**Impact**: Task 8/9/10 的迁移链、回滚声明、G1 证据全部失真；破坏性操作回滚方案不成立。

**Repair 方向**:
- 正确 `down_revision = '36e25241e55d'`
- 所有 "`downgrade f7a3b2c1d456`" 改为 "`downgrade 36e25241e55d`"
- Task 9 生产库 spike 的 current revision 期望改为 `e241e1568792` 或 `36e25241e55d`

---

### F002（HIGH）ORM 注册机制误解

**Before**: plan 把 TeachingPlan 放 `src/edu_cloud/modules/calendar/teaching_plan_models.py`，只要求改 `src/edu_cloud/models/__init__.py` 暴露入口。

**After**: 遵循代码库既有约定：
- 模块 ORM 放 `modules/<name>/models.py`（不是 `teaching_plan_models.py`）
- Alembic 发现走 `alembic/env.py` 显式 import 列表
- 应用启动 `src/edu_cloud/api/app.py` 显式 import
- 测试期 `Base.metadata.create_all()` 需要模型已在 Base registry

**Evidence**:
- `docs/arch/orm-placement.md:201-215` 规定 "模块 ORM 只放 `modules/<name>/models.py`"
- `alembic/env.py:39` 是显式 import 列表（不自动扫描）
- `api/app.py:28-64` 显式 import 所有模型
- `src/edu_cloud/models/__init__.py` 当前**是空文件**

**Impact**: `TeachingPlan` 大概率不会被 Alembic autogenerate、启动 `create_all`、测试建库发现；`Grade` 同样缺 app/test/alembic 注册步骤。

**Repair 方向**:
- TeachingPlan 合并到 `modules/calendar/models.py`（或 create 该文件如不存在）
- Grade 放 `src/edu_cloud/models/grade.py` 后，同时改 `alembic/env.py` + `api/app.py` 注册
- 不依赖 `__init__.py` 暗注册

---

### F003（HIGH）smoke test 数据构造不满足现 schema

**Before**: Task 8 Step 8.2 test_s1_migration_preserves_existing_data 用 `INSERT INTO bank_questions (id, question_type, max_score, school_id, tags, bloom_level) VALUES ...`。

**After**: 必须加上现 schema 的必填列。

**Evidence**:
- `8b3f659c1a2a_initial_merged_schema.py:510` `sample_count` nullable=False
- `8b3f659c1a2a_initial_merged_schema.py:517-518` `created_at/updated_at` nullable=False

**Impact**: G1 核心 smoke test 会直接在数据构造阶段报 NOT NULL violation。

**Repair 方向**: INSERT 补齐 `sample_count=0, created_at=datetime.utcnow(), updated_at=datetime.utcnow()`。

---

### F004（HIGH）测试契约段缺失

**Before**: 每个行为变更 Task 直接从 "Step 1" 开始写步骤，无独立的 `**测试契约**` 段（5 字段：入口/反例/边界/回归/命令）和 `**边界条件**` 段（至少 3 个）。

**After**: 按 CLAUDE.md/tdd-policy.md 和 review-templates.md:206-236 硬要求，每个行为变更 Task 必须补齐结构化测试契约。

**Evidence**: `rg -n "^\*\*测试契约|^\*\*边界条件" plan.md` → 0 matches。

**Impact**: Executor 无法据此覆盖入口级测试 / 反例 / 边界 / 回归 / 完整命令；Plan Review D/D+ 硬失守。

**Repair 方向**:
- 每个 Task 在 Steps 之前增加：
  ```
  **测试契约**:
  - 入口: {API 端点 / 函数签名}
  - 反例: {错误实现会如何失败}
  - 边界: {≥3 个边界条件}
  - 回归: {影响面清单 + 回归测试方法}
  - 命令: {完整 pytest / alembic 命令}
  ```

---

### F005（HIGH）Contract Pack 缺失

**Before**: plan 有 `semantic_regression` 段（ORC-001~005），但没有结构化 Contract Pack。

**After**: 按 `~/.claude/config/contract-pack-schema.md:7-44` 补齐：
- `invariants` ≥3（含 verification 映射）
- `counter_examples` ≥2（含 tests_that_still_pass 和 mitigation）
- `risk_modules`（覆盖 public API 变更 + 治理基础设施）
- `test_debt`（具体理由 + deadline）

**Evidence**: `rg -n "Contract Pack|contract_pack:" plan.md` → 0 matches。

**Impact**: F 项（Contract Pack 完整性）硬失败。

**Repair 方向**：参 contract-pack-schema.md 标准 YAML 结构增补。禁用不可验证 prose 和空 test_debt。

---

### F006（HIGH）depth_level 枚举测试是逻辑镜像

**Before**: Task 2 Step 2.1 `test_depth_level_valid_values()` 断言 `{"subject","unit","core","point"} == {"subject","unit","core","point"}`。

**After**: 测试应验证真实契约——model 层或 migration 层对 depth_level 值域的实际约束，或者端到端 round-trip 存取。

**Evidence**: review-templates.md:277-280 明确逻辑镜像测试是 test-gap HIGH。

**Impact**: `depth_level` 即使没有任何约束、甚至完全忽略值域，测试照样通过。

**Repair 方向**: 移除自我比较；改为 round-trip test（插入 {subject,unit,core,point} 之外的值应被拒绝，或应用层有校验器）。

---

### F007（MED）`school` fixture 不存在

**Before**: Task 7 Step 7.1 声称 `school` 来自 `tests/conftest.py`。

**After**: 引用真实存在的共享 fixture，或显式在测试文件/同级 conftest.py 定义。

**Evidence**: `rg -n "@pytest\.fixture.*school|async def school\(" tests/conftest.py` → 0 matches。实际 `school` fixture 只在具体测试模块本地（如 `test_api/test_academic_semester.py`）出现。

**Impact**: 新测试 `tests/modules/profile/test_student_profile_view.py` 会在 collection 期 fixture-not-found error。

**Repair 方向**: 用现有 `seed_school` 或 `admin` 替代；或在 `tests/modules/profile/conftest.py` 定义 `school` fixture。

---

### F008（MED）Evidence Block 缺真实证据

**Before**: plan 的 Evidence Block（L26-41 + L200-213）均无代码行号 / grep 输出 / 命令结果；负面断言 "S1 不改 conduct/AI Agent/..."（L93）无 Grep 零结果证据。

**After**: 按 `~/.claude/rules/decision-evidence.md:33-52` 和 L72-77，Evidence Block 必须是可跳转、可复现、可反证的证据包。

**Repair 方向**:
- 关键决策附具体 `file:line`（如 `src/edu_cloud/modules/bank/models.py:13` 而非 "附录 C §Gap#5"）
- 负面断言附 Grep 命令 + 零结果输出
- 命令结果贴真实 terminal 输出

---

### F009（MED）参数命名不一致

**Before**: 新端点 `GET /api/v1/profile/students/{id}/view?subject_code=...`，但现有 `profile/router.py:67-77` `get_student_knowledge_map()` 用 `course_code`。且新 VO service 里 `subject_code` 只传给 trend/error，不传给 knowledge_map。

**After**: 统一参数命名和过滤语义。

**Evidence**:
- `profile/router.py:67-77` 用 `course_code`
- `profile/service.py:26-38` `get_student_knowledge_map(course_code=...)`
- plan L838-866 `get_student_profile_view(subject_code=...)` 没把参数传给 knowledge_map
- plan L915-925 新端点暴露 `subject_code`

**Impact**: `/view?subject_code=...` 返回 "趋势和错因被筛选，但知识掌握未筛选" 的混合语义，接口契约不自洽。

**Repair 方向**:
- 决定聚合视图的统一过滤语义（是按学科还是按课程）
- 统一参数命名，或明确拆分 `subject_code` vs `course_code`
- 测试契约里显式声明过滤语义

---

## Gate 决策

按 `~/.claude/skills/codex-review/SKILL.md` §Gate 条件：

- **R1 FAIL**
- **是否允许 R2？** 判断 3 条件：
  - Tier = T4？否（声明为 T3）
  - topic 含 `remote/deploy/publish`？否
  - 跨模块重构（≥2 模块 + ≥2 文件修改）？**是**（bank / knowledge_tree / student / calendar / paper / profile / alembic 均触达）
- **结论：允许 R2**

但 finding 面很广（5 HIGH 中 F004/F005 是 plan 结构问题，F001/F002 是根本认知错误），**不建议立刻 R2 重审**——应该先拆成更小的 topic 或全面重写 plan 后再走新 R1。

---

## 建议的后续路径

### 路径 A：拆 topic 重写（推荐）

把 S1 拆成更小的子 Sprint：
- S1-A：bank_question 扩展（Task 1 + 对应 migration + 测试契约完整版）
- S1-B：concept depth_level（Task 2 + migration + 去逻辑镜像测试）
- S1-C：grades + Class.grade_id + teaching_plans + Alembic 集成（含 F002 正确注册链路）
- S1-D：StudentProfileView VO + 端点（含 F009 参数语义决策）

每个子 Sprint 独立 R1 plan review。

### 路径 B：同 topic 全面重写后 R2

一次性修复 9 findings + 补齐 Contract Pack + 5 字段测试契约 + 正确 down_revision，然后 R2 重审。风险：R2 再 FAIL 就必须拆 topic（不接受 R3+）。

### 路径 C：回 design 层修正

F002（ORM 注册）和 F009（参数语义）可能需要回到 design doc 补充接口契约章节，再重写 plan。

---

## Raw Evidence

Full Codex output: `docs/plans/.codex-plan-review-raw-20260424_101253.log`（545KB）
