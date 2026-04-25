[edu-cloud] GPT Reviewer | 2026-04-11 21:55:00

<!-- anchor: finding-classification -->
## 审查报告: F003 Question 写入责任链重设 Plan Review — Round 1

**审查对象**:
- design: `docs/plans/2026-04-11-f003-question-writeback-design.md` (commit `7ad6416`)
- plan: `docs/plans/2026-04-11-f003-question-writeback-plan.md` (commit `0e3d247`)

**审查路径**: `codex exec -s danger-full-access -C /c/Users/Administrator/edu-cloud`
**原始输出日志**: `docs/plans/.codex-raw-plan_review-r1-20260411-215737.log`
**原始输出 SHA256**: `29779e3bc9a2f9712c8305aef7d4d890b81789c3f0b185cf41ddc556ca5b4bd2`
**Token used**: 153605
**结论**: **FAIL**

---

### 第一段：测试充分性（Test Adequacy）

发现 3 个 test-gap finding（F004/F005/F006），其中 2 个 HIGH 1 个 MED。详见"发现清单"段。

### 第二段：行为正确性（Behavioral Correctness）

发现 3 个 design-concern finding（F001/F002/F003），其中 F003 是事实错误，F002 是契约冲突，F001 是规范硬要求缺失。详见"发现清单"段。

### 第三段：未测试风险（Non-tested Risks）

本轮未独立提出新的第三段风险（F004/F005 已经暴露了测试护栏的不充分）。

---

### 发现清单

#### F001 — HIGH — design-concern — defect_fix

**Before-behavior**: Plan 以 prose 形式列了 I1-I6 invariants，但没有结构化 Contract Pack 段落，缺少 `risk_modules` / `counter_examples` / `test_debt` 可验证载体

**After-behavior**: Gate 1 通过前需要有符合 `~/.claude/config/contract-pack-schema.md` 的 `contract_pack:` 根段，每条 invariant 有 verification 映射，所有 public API / 治理基础设施变更进入 `risk_modules`

**Evidence**:
- plan.md 全文无 `contract_pack:` 根键
- contract-pack-schema.md L7/13/22/31/38 明确要求 `contract_pack:` 根键 + `invariants` + `counter_examples` + `risk_modules` + `test_debt` 为必要段落

**Impact**: Contract Pack 完整性直接不达标，本计划含 `/api/v1/card/publish`、scan pipeline 写回、Alembic migration 等高风险变更，没有可机审的语义护栏

**Repair hypothesis** (advisory): 先把现有 invariant / 风险面重写为结构化 contract_pack，并把 `/api/v1/card/publish`、`pipeline/start`、Question/StudentAnswer 约束纳入 risk_modules。Forbidden: 仅把 prose 搬成 YAML、existing_test 不填 test_ref、"系统应正确运行" 这类不可验证语句

**Status**: verified（规则硬要求，事实明确）
**Terminal**: pending（等待修复）

---

#### F002 — HIGH — design-concern — defect_fix

**Before-behavior**: Task 4 边界条件表允许"只有 B 面 → 1 条 + tpl_a=None"

**After-behavior**: 模板契约必须与设计保持一致——A 面必存，或在发布阶段把"仅 B 面输入" 正规化/拒绝

**Evidence**:
- design.md:171 明确写 "A 面必存，B 面可选"
- plan.md:29 invariant I5 把 `(subject_id, side)` 作为双面模板主契约
- plan.md:870 却写 "只有 B 面 → 1 条 + tpl_a=None"
- pipeline_router.py 和 card/export.py 的下游消费者默认按 A 面取模板

**Impact**: Task 4 实现后，publish 可能成功但默认 A 面消费者拿不到模板，形成隐藏运行时故障（下游按 A 面查 Template 查不到）

**Repair hypothesis** (advisory): 统一"单面 publish"语义——只允许 A-only，或在 `upsert_template_both_sides` 内部正规化。Forbidden: 继续允许 tpl_a=None；把 A/B fallback 散落到多个消费端

**Status**: verified
**Terminal**: pending

---

#### F003 — HIGH — design-concern — defect_fix

**Before-behavior**: Task 0 和 design §5.5 以 `(exam_id, subject_id, student_id, question_id)` 四列作为 StudentAnswer 唯一约束前提

**After-behavior**: 计划必须对齐现有真实 schema，再决定 save 策略和是否需要 migration

**Evidence**:
- plan.md:55 / design.md:248 写了四列键
- `src/edu_cloud/modules/scan/models.py:23` 实际是 `UniqueConstraint("exam_id", "student_id", "question_id")` **三列**

**Impact**: 这会把后续 `save_answer_fn` 的 conflict target、migration 判断、幂等语义都带偏。最坏情况生成不必要的 migration 或按错误约束写 ON CONFLICT 语句

**Repair hypothesis** (advisory): 修 Task 0 为"核对现有三列唯一键是否满足写回语义；若满足，直接采用 INSERT + IntegrityError 捕获策略，无需 migration"。修 design.md §5.5 同步

**Status**: verified（事实错误，已通过读 models.py L21-35 证实）
**Terminal**: pending

---

#### F004 — HIGH — test-gap — defect_fix

**Before-behavior**: S7 测试名义验证 IntegrityError retry，实际走 `existing_by_name` 分支，计划自己注释 "可能直接 PASS"

**After-behavior**: S7 必须在错误实现下先失败——真正命中 retry 分支，而不是用"已有记录" 替代并发冲突

**Evidence**:
- plan.md:1305 "本 session 再次 upsert 同 name，应走 existing 分支（简单情况）"
- plan.md:1322 "SQLite in-memory 不一定触发真正的 race，本测试简化为'先已有记录的场景'"
- plan.md:1330 "Expected: 依赖 T3 当前的 existing_by_name 逻辑已覆盖此场景 → 可能直接 PASS"
- review-templates.md L278/283 "错误实现下仍通过的测试 → test-gap HIGH"

**Impact**: 并发 publish 是本方案显式高风险点，当前 plan 没有任何会在"缺少 retry 防御"时失败的测试护栏

**Repair hypothesis** (advisory): 用 monkeypatch 拦截 `db.flush` 让其在首次调用抛 IntegrityError，第二次正常。验证 try/except 分支被真正执行。Forbidden: 继续用 existing 分支冒充

**Status**: verified
**Terminal**: pending

---

#### F005 — HIGH — test-gap — defect_fix

**Before-behavior**: S9/R1 在测试契约表写"publish → pipeline → marking/subjects GET"作为 F003 总验证入口，但样例测试又明确 "**不涉及** scan pipeline 的 StudentAnswer 写入"，只断言 `questions` 非空

**After-behavior**: 要么降格为 publish-only 测试（契约表同步缩小），要么补真实的 publish→scan→marking 合同并至少验证 `total_answers>0` / StudentAnswer 可见性

**Evidence**:
- plan.md:2208-2210 仅断言 `len(math_subj["questions"]) == 14`
- plan.md:2324 明确 "**不涉及** scan pipeline 的 StudentAnswer 写入"
- plan.md:2370 测试契约表仍写入口为 "publish → pipeline → marking/subjects GET"
- `marking/scorer.py:36` 的 questions 列表本来就直接从 Question 表取
- `marking/scorer.py:43` StudentAnswer 只影响 total_answers 统计

**Impact**: 即使 Question 创建修好了、pipeline 写回仍然断裂，这个"E2E"也会通过——无法防住 F003 核心症状

**Repair hypothesis** (advisory): 把 S9 拆成两个测试：
1. `test_S9a_publish_creates_questions_visible` — publish 后 Question/Template/marking 可见
2. `test_S9b_pipeline_writeback_creates_student_answers` — publish + 直接调 save_answer_fn 或 mock pipeline → 断言 `StudentAnswer.count > 0` + `marking/subjects total_answers > 0`

**Status**: verified
**Terminal**: pending

---

#### F006 — MED — test-gap — defect_fix

**Before-behavior**: Task 10 是前端行为变更 Task 但缺 `**测试契约:**` + `**边界条件:**` 段；伪示例写 `props.exam.id`（当前组件没有 props.exam 结构）

**After-behavior**: Task 10 需要独立 V3 测试契约（入口/反例/边界/回归/命令）+ 边界条件段 + 改掉 `props.exam.id` 伪示例

**Evidence**:
- plan.md:1719 Task 10 到下一 Task 前无测试契约段
- plan.md:1740 示例调用 `await exportModule.publishCard(subjectId, props.exam.id, filename)`
- `ExamDetailPage.vue:471` 实际已有 `const examId = route.params.id`（组件 scope 内的 ref）
- review-templates.md L217 规则要求行为变更 Task 必须带测试契约段

**Impact**: T9/T10 接口契约未闭合，执行者容易把错误 state 接到 publish 新签名，"全量 vitest pass"不能证明 publish 按钮真的带正确 examId

**Repair hypothesis** (advisory): 给 T10 单列 V3 测试契约 + 边界条件段，覆盖"点击发布按钮时 fetch 被调用 1 次，目标 /card/publish，body.exam_id === route.params.id"的入口级断言；删除 props.exam.id 伪示例改为 `examId`（已在组件 scope）

**Status**: verified
**Terminal**: pending

---

<!-- anchor: pass-fail -->
### PASS/FAIL 判定

- **HIGH test-gap**: F004, F005 → 阻塞 PASS
- **MED test-gap**: F006 → 阻塞 PASS
- **HIGH design-concern**: F001, F002, F003 → 不强制阻塞 PASS，但含事实错误和规范硬要求缺失，Planner 必须处置

**最终判定**: **FAIL**（R1 首轮）

### 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| — | — | — | 无 behavior_change finding，全部 defect_fix |

---

## 处置计划（Claude 响应 GPT finding）

按 review-templates.md Finding 转换规则，Type 保持 GPT 原标注（全部 defect_fix，无红旗模式命中）。

| Finding | 处置动作 | 涉及文件 |
|---------|---------|---------|
| F001 | 在 plan.md 头部追加 `## Contract Pack` 段（按 schema 结构化 invariants/counter_examples/risk_modules/test_debt）| plan.md |
| F002 | 改 publish_service.upsert_template_both_sides 契约：regions_by_side["A"] 为空但 B 非空 → raise HTTPException(400)；修 Task 4 边界条件表；修 design.md §5.1 | plan.md Task 4 + design.md §5.1 |
| F003 | 修 Task 0 Step 1-3 为"验证三列唯一键满足写回语义，无需 migration"；修 design.md §5.5 | plan.md Task 0 + design.md §5.5 |
| F004 | 改 S7 测试用 monkeypatch 拦截 `db.flush` 抛 IntegrityError 首次，验证真 retry 分支 | plan.md Task 7 |
| F005 | 拆 S9/R1 为 S9a（publish-only marking 可见）+ S9b（pipeline writeback total_answers）| plan.md Task 12 + 测试契约表 |
| F006 | Task 10 追加 `**测试契约:**` + `**边界条件:**` 段 + 改 props.exam.id → examId（组件 scope 已有） | plan.md Task 10 |

**处置范围**:
- plan.md: 新增 Contract Pack 段 + 修 Task 0 / 4 / 7 / 10 / 12 + 测试契约表
- design.md: 修 §5.1 + §5.5

**处置后**:
1. Commit 修改（"fix: Plan Review R1 finding F001-F006 处置"）— 已完成 commit `406af8b`
2. 进入 Round 2 — 重新调 codex-review 对新 plan/design 做再审 — 已完成（下方 R2 报告）
3. R2 结果见下方 Round 2 段
4. R2 FAIL → 进入 R3（还剩 2 轮）

---

[edu-cloud] GPT Reviewer | 2026-04-11 22:18:35

## Round 2 审查报告 — FAIL（5 new findings）

**审查对象**（R1 处置后的 draft）:
- design: 已 commit `406af8b`（R1 F002/F003 修正）
- plan: 已 commit `406af8b`（R1 F001-F006 全部处置）

**原始输出日志**: `docs/plans/.codex-raw-plan_review-r2-20260411-221835.log`
**SHA256**: `132098bc14685d3c99617d27a8a211bf7b4e36ee4b7f92d78048e68e6e7a432e`
**Token used**: 333530
**结论**: **FAIL**

### R2 Finding 清单

GPT R2 并未重复 R1 的 6 个 finding（证明 R1 处置已落地），而是发现了 Claude 在 R1 处置过程中**新引入的 5 个问题**。R2 Finding 编号重置为 F001-F005。

#### R2-F001 — HIGH — code-bug — defect_fix

**Before-behavior**: Task 7 S7 的 IntegrityError retry 实现在 `upsert_questions_from_skeleton` 循环内遇到单题冲突时直接 `await db.rollback()`。而 Task 6 publish_card_atomic 把这个函数和 Template 写入都放在**同一事务**里（design §6.1 + plan invariant I2）。单题 rollback 会把**同次 publish 的前面已成功 upsert 的其他 Question** 一并回滚，但后续循环只补救当前冲突的那一题。

**After-behavior**: 单题并发冲突只能收敛该题自身，不能破坏同一事务中前面已 upsert 的 Question 集合。推荐做法：使用 savepoint（SAVEPOINT / ROLLBACK TO SAVEPOINT）让单题冲突的 rollback 只回滚当前题的子事务。

**Evidence**:
- plan.md:1373 定义事务边界（publish_card_atomic 整个事务）
- plan.md:1553 单题冲突分支 `await db.rollback()`
- plan.md:1560 之后只 re-select 当前 name

**Impact**: 并发 publish 会提交"不完整的题目集合"，直接破坏 INV-002 / INV-005，对 Template 写入和 question_map 完整性造成隐性数据损坏

**Repair hypothesis** (advisory): 把冲突收敛限定在单题级别（savepoint 或先 `SELECT ... FOR UPDATE` 占位），而不是回滚整个发布事务。Forbidden: 在循环内全局 rollback 后继续跑剩余题目 / 吞冲突但不重建 state / 无限重试

**Status**: verified
**Terminal**: pending

---

#### R2-F002 — HIGH — code-bug — defect_fix

**Before-behavior**: Task 11 示例代码读取 `body.exam_id`，但现有 `src/edu_cloud/modules/scan/pipeline_router.py:25` 的 PipelineStartRequest 请求体**只有** `subject_id/side/image_dir/tpl_path`，没有 `exam_id` 字段。现有实现 `pipeline_router.py:145` 通过 `subject.exam_id` 派生。

**After-behavior**: Task 11 必须选定单一 exam_id 来源——要么保持现有契约用 `subject.exam_id`，要么显式修改 PipelineStartRequest + 测试 + 文档三者，不能偷偷引入当前不存在的请求字段

**Evidence**:
- `pipeline_router.py:25` PipelineStartRequest 无 exam_id
- `pipeline_router.py:145` 用 `subject.exam_id` 派生
- plan.md:2251 实现代码读 `body.exam_id`
- plan.md:2147 测试请求体也没发 exam_id

**Impact**: 执行者照 plan 实现会在"字段不存在报错" vs "静默扩展公开 API 契约" 之间二选一，接口契约不一致

**Repair hypothesis** (advisory): 锁定 start_pipeline 单一来源（推荐 subject.exam_id 派生，保持现有契约），让设计/实现/测试共享同一入口。Forbidden: 同时接受两套来源做隐式优先级 / 只改实现不改设计 / 路由里复制归属推断逻辑

**Status**: verified
**Terminal**: pending

---

#### R2-F003 — HIGH — test-gap — defect_fix

**Before-behavior**: Task 12 S9b 名义上是"pipeline writeback 总验证"，但测试体手工构造 `region_map` 并直接 `db.add(StudentAnswer)`，完全绕过 Task 11 的 pipeline_router 闭包装配路径

**After-behavior**: S9b 必须经过真实用户可达入口（`/api/v1/scan/pipeline/start`）或至少 pipeline_router 公开的闭包装配接口——否则 broken pipeline 仍然能绿

**Evidence**:
- plan.md:2471 S9b 目标描述
- plan.md:2544 手工构建 region_map
- plan.md:2550 直接 db.add(StudentAnswer)
- plan.md:93 Contract Pack CE-002 的缓解寄托在 S9b

**Impact**: 即使 pipeline_router 根本没传 save_answer_fn、region 反查错误、或 orphan/幂等逻辑全坏，S9b 仍可通过 → 总验证失真 → CE-002 缓解失效

**Repair hypothesis** (advisory): 让至少一条高层验证真实经过 `/api/v1/scan/pipeline/start` 端点；或者把 save_answer_fn 闭包构建抽出独立函数，测试调用该函数拿到闭包再调用。Forbidden: 测试里直接 ORM 落库代替 pipeline 写回 / 只看 marking/subjects 聚合不触达写回入口 / 把闭包装配整体 mock

**Status**: verified
**Terminal**: pending

---

#### R2-F004 — MED — test-gap — defect_fix

**Before-behavior**: Task 10 V3 测试声称验证 ExamDetailPage.vue 调用签名已改，但测试体只 `import publishCard` 直接三参调用——没 mount ExamDetailPage 组件，也没触发组件上的发布按钮

**After-behavior**: V3 必须触达 ExamDetailPage.vue:868 的真实调用点——通过组件挂载 + 触发点击 + spy 拦截

**Evidence**:
- `ExamDetailPage.vue:868` 当前仍是两参形式 `publishCard(subjectId, filename)`
- plan.md:1952 V3 测试定义
- plan.md:1972 直接 `import('../../card-editor/export.js')`
- plan.md:1974 直接 `publishCard(...)` 调用

**Impact**: 执行者漏改 ExamDetailPage.vue:868 的话，V3 仍然通过，前端运行时真实按钮可能仍发送旧签名（无 examId）

**Repair hypothesis** (advisory): V3 应以组件点击流或对组件内 import 的 spy 为入口，或用 Vue Test Utils mount 后触发 click

**Status**: verified
**Terminal**: pending

---

#### R2-F005 — HIGH — test-gap — defect_fix

**Before-behavior**: Contract Pack 把 INV-006 (pipeline orphan region skip) 映射到 S8。但 Task 11 的 S8 方案包含 `pytest.skip(...)`、`TODO` 注释和 "FAIL 或 skip" 的预期描述——不是确定性可执行测试

**After-behavior**: 被 Contract Pack 引用的 verification 必须是确定性、可运行的测试，不能依赖"实现时再调整"

**Evidence**:
- plan.md:70 INV-006 映射到 S8
- plan.md:2072 Task 11 首版测试 `pytest.skip(...)`
- plan.md:2158 替代测试里写 TODO
- plan.md:2177 预期为 "FAIL 或 skip"

**Impact**: Contract Pack 对 pipeline 风险模块的 verification 映射目前不可执行 → Gate 1 无法据此证明 INV-006

**Repair hypothesis** (advisory): 先定义稳定同步测试缝隙，再把 S8 收敛成单一确定性断言路径。Forbidden: 保留 skip 占位进入执行批次 / TODO 型测试契约 / 靠后台 task 时序做最终验收

**Status**: verified
**Terminal**: pending

---

### R2 PASS/FAIL 判定

- HIGH code-bug: R2-F001 + R2-F002 → 阻塞 PASS
- HIGH test-gap: R2-F003 + R2-F005 → 阻塞 PASS
- MED test-gap: R2-F004 → 阻塞 PASS

**R2 结论: FAIL**

### R2 处置范围预估

| Finding | 处置复杂度 | 涉及文件 |
|---------|----------|---------|
| R2-F001 | 高（事务边界重设 + savepoint 机制）| plan.md Task 7 + design.md §6.1 + §6.2 |
| R2-F002 | 中（Task 11 示例代码改回 subject.exam_id 派生）| plan.md Task 11 |
| R2-F003 | 高（S9b 改走真实 `/pipeline/start` 或抽出闭包工厂函数）| plan.md Task 12 S9b |
| R2-F004 | 中（V3 改用 Vue Test Utils mount + 触发）| plan.md Task 10 V3 |
| R2-F005 | 中（S8 移除 skip + TODO，收敛为确定性测试）| plan.md Task 11 S8 |

**R2 → R3 处置必须由新会话承担**。本会话对话已长，处置量估计 400-600 行 plan.md 修改 + design.md §6 重写。

**Round 循环状态**: R1 FAIL (6 finding) → R2 FAIL (5 new finding) → 还剩 1 轮 (R3) 可跑。若 R3 仍 FAIL → 按 review-templates 规则分类：code-bug 继续修 / design-concern 记入 design.md §待处置。但本次 R2 全部是 code-bug 或 test-gap，必须在 R3 修好。

---

[edu-cloud] GPT Reviewer | 2026-04-11 22:56:00

## Round 3 审查报告 — FAIL（5 new findings）

**审查对象**（R2 处置后）:
- plan: 已 commit `f4053b9`（R2-F001~R2-F005 全部处置）
- design: 已 commit `f4053b9`（§6.1 §6.2 SAVEPOINT 事务边界更新）
- CLAUDE.md: 同步了 R1→R2→R3 状态和 SAVEPOINT / 工厂函数引用

**原始输出日志**: `docs/plans/.codex-f003-plan-review-r3-raw.log`
**SHA256**: `294e4c1b43f252a1d74312497d92a41c0ec28dac0c72d2ffefb57601a867fa15`
**Token used**: 199994
**结论**: **FAIL**

### R3 Finding 清单

GPT R3 核实：R2-F002 契约锁定（`StartPipelineRequest` 4 字段 / `exam_id` 从 subject 派生）和 design §6.1/§6.2 SAVEPOINT 修复方向**均属实**。但 R2 的测试方案和 `start_pipeline` 装配仍有阻塞问题——全部是 R2 修复本身引入的"新孔洞"。

#### R3-F001 — HIGH — test-gap — defect_fix

**Before-behavior**: S7 应证明"单题冲突时，错误实现若在循环内全局 `rollback()` 会丢掉前面已 upsert 的题"，从而为 R2-F001 的 SAVEPOINT 修复提供回归护栏。

**After-behavior**: 当前 S7 方案把 rival `"14"` 先提交，再调用被测函数；这样被测代码首次 `SELECT` 就可能直接看到 `"14"`，根本不进入 `IntegrityError` / SAVEPOINT 分支。并且它使用的还是**未绑定到 `db` fixture 的全局 `async_session`**（in-memory SQLite session 隔离问题）。

**Evidence**:
- plan.md:1464 / 1493 / 1512（独立 `async_session` 预插 rival）
- tests/conftest.py:59 / 94（`db` fixture 的 in-memory SQLite 不经过全局 `async_session`）

**Impact**: 错误实现即使继续用"循环内全局 rollback"也可能通过 S7，R2-F001 的核心 concern 仍未被有效守住。

**Repair hypothesis** (advisory)：修复方向应是让冲突在"同一测试数据库、且首次 `SELECT` 之后"确定性发生，并显式证明 retry 分支被命中。禁止继续使用"预提交 rival 行 + 期待 flush 冲突"这种模式；禁止在测试里调用未绑定 fixture 的全局 `async_session`。**requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

#### R3-F002 — HIGH — test-gap — defect_fix

**Before-behavior**: S8a/S8b/S8c 应作为 R2-F005 的确定性合同，直接验证工厂闭包的 orphan skip、正常写入、重复幂等。

**After-behavior**: 计划里的工厂闭包实现使用全局 `async_session()` 写库，而 S8a/S8b/S8c 只持有 `db` fixture 查询结果；在当前测试基建下，这两者**并没有被同一个 fixture 绑定**。闭包写入的是生产配置 DB（或全新 session），测试 fixture 的 in-memory SQLite 查询看不到。

**Evidence**:
- plan.md:2184 / 2218 / 2251 / 2353（工厂闭包用 `async_session()` + S8 用 `db` fixture）
- tests/conftest.py:59 / 94（`db` fixture 实现）

**Impact**: S8 系列要么误打到真实 DB，要么与断言查询的 test DB 脱节；INV-006 的 `test_ref` 因此不能成立。

**Repair hypothesis** (advisory)：修复方向应统一测试所见数据库与闭包实际写入数据库。禁止继续让"db fixture 断言"依赖未注入的全局 session。**requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

#### R3-F003 — HIGH — test-gap — defect_fix

**Before-behavior**: R2-F003 声称抽出 `build_pipeline_save_answer_fn` 后，S8/S9b 就与 `start_pipeline` 共享装配路径，从而堵住 CE-002。

**After-behavior**: 新增测试全部是"直接 import 工厂 + 手动驱动闭包"，**并没有任何一个入口级测试验证 `start_pipeline` 真的创建了闭包并把 `save_answer_fn` 传给 `run_pipeline`**。

**Evidence**:
- plan.md:97 / 2132 / 2404 / 2603（S8a/b/c + S9b 全部 `import build_pipeline_save_answer_fn` 直接调）
- tests/test_services_exam/test_scan_pipeline.py:222（现有 pipeline 测试未覆盖 wiring）
- src/edu_cloud/modules/scan/pipeline_router.py:146（start_pipeline 装配点）

**Impact**: 如果实现时漏掉 `start_pipeline -> save_answer_fn` 这根线，S8 和 S9b 仍然都能过，运行时却继续"只切图不写 StudentAnswer"；CE-002 的 mitigation 被高估了。

**Repair hypothesis** (advisory)：修复方向应补一个入口级合同，验证 `/api/v1/scan/pipeline/start` 的真实装配。禁止把"工厂单测通过"当作"端点 wiring 正确"的替代证明。**requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

#### R3-F004 — MED — test-gap — defect_fix

**Before-behavior**: V3 应通过真实挂载 `ExamDetailPage.vue` 并点击发布按钮，证明 `ExamDetailPage.vue:868` 的调用点确实改成了三参 `publishCard(subjectId, examId, filename)`。

**After-behavior**: 计划里的 V3 mock/setup 与真实组件不对齐：
1. 把 `listSubjects` **错 mock 到 `api/exams.js`**，而真实组件从 `api/subjects` 导入
2. 返回裸对象，但 `loadExam()` 实际读取 `examRes.data / subjRes.data`
3. 没有保证 `visualEditorSubjectId` 已选中，当前按钮默认**不可用**
4. 源码里也**还没有 `data-testid="publish-card-btn"`**

**Evidence**:
- plan.md:1997 / 2040（V3 测试 + mock 路径）
- ExamDetailPage.vue:246 / 446 / 447 / 652 / 868（组件真实 import + state + 按钮 disabled 条件 + 调用点）

**Impact**: V3 按计划实现后，不能稳定触达真实按钮调用链，R2-F004 仍然没有被可靠验证。

**Repair hypothesis** (advisory)：修复方向应让 mock 模块路径、返回形状、按钮前置状态与真实组件一致；并把按钮定位方式写成明确要求而不是备注。

**Status**: verified
**Terminal**: pending

---

#### R3-F005 — MED — code-bug — defect_fix

**Before-behavior**: Task 11 计划保留 `tpl_path` 这条 `StartPipelineRequest` 分支，同时把 save-answer 工厂接入 `start_pipeline`。

**After-behavior**: 计划示例在 `start_pipeline` 中调用 `build_pipeline_save_answer_fn(template=tpl, ...)`，但 `req.tpl_path` 分支**实际只有 `template = parse_tpl_file(req.tpl_path)` 这个 dict**，没有 `tpl` 变量。按 plan 直译实现会在该分支产生 `NameError: name 'tpl' is not defined`。

**Evidence**:
- plan.md:2378 / 2404（start_pipeline 修改示例）
- src/edu_cloud/modules/scan/pipeline_router.py:114（`tpl_path` 分支现状）

**Impact**: 按计划直译实现会把 `tpl_path` 请求分支做成未定义变量错误，属于 R2 改造本身引入的新孔洞。

**Repair hypothesis** (advisory)：修复方向应先统一两条分支的装配输入，再做闭包构造。禁止以"该分支只是调试路径"为理由保留不完整装配。**requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

### R3 PASS/FAIL 判定

- HIGH test-gap: R3-F001 + R3-F002 + R3-F003 → 阻塞 PASS
- MED test-gap: R3-F004 → 阻塞 PASS
- MED code-bug: R3-F005 → 阻塞 PASS

**R3 结论: FAIL**

### 3 轮硬额度已用尽

R1 FAIL (6 finding) → R2 FAIL (5 finding) → R3 FAIL (5 finding)。review-templates.md 规则：每批最多 3 轮。2 轮后仍 FAIL → 分类处置：code-bug 必须修复 / design-concern 记入 design.md §待处置。R3 的 5 条全部是 code-bug / test-gap，**没有可以记入 §待处置的 design-concern**。

### 根因观察（Claude 附注）

R3 的 5 条 finding 并非"又发现新问题"，而是揭示了**R2 处置方案本身的共同缺陷**：Claude 在没有真正读取 `tests/conftest.py` / `ExamDetailPage.vue` / `pipeline_router.py` 现实代码的情况下，凭假设构造了测试方案和实现代码。

- R3-F001 / R3-F002 共同根因：**未验证 SQLite in-memory session 隔离**。`db` fixture 不是通过生产 `async_session()` 工厂拿到的——Claude 凭空假设"全局 async_session() 和 db fixture 同库"，这在测试基建里不成立。
- R3-F003 共同根因：**把工厂单测等同于 wiring 证明**。抽工厂解决了"手工 db.add 伪验证"问题，但没补入口级测试验证 start_pipeline 真的调工厂 + 真的传参给 run_pipeline。
- R3-F004 根因：**未读真实 ExamDetailPage.vue**。mock 路径 / state 前置 / disabled 条件 / testid 存在性全部靠直觉构造。
- R3-F005 根因：**未读真实 pipeline_router.py 的 tpl_path 分支**。L114 分支 template 是 dict 不是 Template model，Claude 直接把 DB 分支的示例套到了 file 分支。

这 5 条本质上是**同一个问题的 5 个表现**：R2 修复时缺少"写 plan 前先 Grep/Read 现实代码"这一步。

### 必须向用户汇报

按 handoff.md §R3 结果分支规则，R3 FAIL 且有 code-bug / test-gap HIGH/MED 时：
> **必须向用户汇报 + 请求决策**：(a) 降级为 deferred/accepted-risk（需具体 reason）(b) 重启 R4 循环（review-templates 允许但非标准）(c) 推翻方案 D 整体重做设计

**用户决策**: 选 A (R4 循环)，条件是 Claude 先 Read conftest.py / pipeline_router.py / ExamDetailPage.vue / api/subjects.js，将事实锚抄进 plan，再基于事实修复。

---

[edu-cloud] GPT Reviewer | 2026-04-11 23:39:46

## Round 4 审查报告 — FAIL（5 new findings，2 HIGH / 2 MED / 1 LOW）

**审查对象**（R3 处置后）:
- plan: 已 commit `0c7c0c4`（新增"现实代码锚点"段 CR-1/CR-2/CR-3/CR-4 + R3 五 finding 处置）
- design: 未改动（§6.1/§6.2 R2 后已定稿）
- CLAUDE.md: 参考文档描述同步

**原始输出日志**: `docs/plans/.codex-f003-plan-review-r4-raw.log`
**SHA256**: `64b226769c7d92043d2c663c32c7d9e7d271dfa1f4ea7594e32ed7069133161d`
**Token used**: 150816
**结论**: **FAIL**

### R4 Finding 清单

GPT R4 核实 R3 处置：
- **R3-F004 基本成立** (锚点 CR-3/CR-4 + V3 mock 路径/shape/dialog/按钮 disabled 都对)
- **R3-F005 基本成立** (工厂 `regions: list[dict]` signature 统一两条分支)
- **R3-F001 只部分成立**：S7a/S7b 合理，**S7c 当前写法逻辑上不可证**
- **R3-F002 不成立**：根因不在 fixture 组合，而在 plan 后文的 `async_session` 模块顶层绑定 + `await db.expire_all()` API 误用
- **R3-F003 只部分成立**：S8d 比"只看 200"强，但**`callable(save_answer_fn)` 断言过弱**，哑闭包可绕过

#### R4-F001 — HIGH — code-bug — defect_fix — Inv-conflict: direct (INV-009)

**Before-behavior**: 计划认为 `client` fixture 对 `edu_cloud.database.async_session` 的 monkey-patch 足以让 `build_pipeline_save_answer_fn` 闭包写入测试库。

**After-behavior**: 若继续沿用 `from edu_cloud.database import async_session` 写法，S8a/S8b/S8c/S9b 并不能可靠打到测试 DB；必须改成**运行时模块属性查找** (`import edu_cloud.database as db_mod` + 闭包内 `db_mod.async_session()`)，或显式注入 `session_factory`。

**Evidence**:
- plan.md:90（CR-1 中"monkey-patch 让工厂闭包内 async_session() 打到测试 DB"的错误断言）
- plan.md:101（"测试中 app 代码 from edu_cloud.database import async_session 后调用 async_session() 会拿到指向测试 DB 的 factory"——Python import 语义错误）
- plan.md:3114 / 3171（S8a/S8b 测试预期）
- plan.md:2761（工厂函数顶部 `from edu_cloud.database import async_session`）
- tests/conftest.py:76 / 92（`client` fixture 的 `create_app()` 在 monkey-patch **之前**已导入 scan.pipeline_router）
- src/edu_cloud/api/app.py:302（create_app 导入 pipeline_router）

**Python import 语义事实**：`from edu_cloud.database import async_session` 在模块加载时将 **函数对象引用** 绑定到当前模块命名空间。`_db_mod.async_session = new_factory` 只改变 `edu_cloud.database` 模块的属性，**不影响已经 import 到其他模块命名空间的旧引用**。pipeline_router 的闭包内 `async_session()` 会继续调用旧 factory。

**Impact**: R3-F002 **实际未解决**。`client` fixture 的 monkey-patch 发生在 `create_app()` 之后，而 `create_app()` 内部已触发 `from edu_cloud.database import async_session`。工厂闭包在测试期间仍使用生产配置的 session，与 `db` fixture 的 in-memory SQLite 完全隔离。S8a/b/c/S9b 的断言查询会查不到闭包的写入。

**Repair hypothesis** (advisory)：
- 方案 A（推荐，单行改动）：`pipeline_router.py` 改 `import edu_cloud.database as db_mod`，闭包内 `async with db_mod.async_session() as db2:`——每次调用时运行时查找模块属性，monkey-patch 生效
- 方案 B：`build_pipeline_save_answer_fn` 接受可选 `session_factory` 参数，测试显式注入 `async_sessionmaker(db_engine, ...)`；生产时默认 `db_mod.async_session`
- **Forbidden**：继续用 `from ... import async_session` 模块顶层绑定；依赖 client fixture 的 monkey-patch 传递到已绑定的模块引用

**此项触及 INV-009 与 risk_modules: pipeline_router，requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

#### R4-F002 — HIGH — code-bug — defect_fix — Inv-conflict: possible

**Before-behavior**: 计划把跨 session 可见性的刷新写成 `await db.expire_all()`。

**After-behavior**: `AsyncSession.expire_all()` 是**同步方法**（不返回 coroutine），`await` 它会 `TypeError: object NoneType can't be used in 'await' expression`。必须改为同步 `db.expire_all()`，或改用新查询 session。

**Evidence**:
- plan.md:99（CR-1 段的"await db.expire_all() 获取跨 session 可见性"错误描述）
- plan.md:2833 / 2867 / 2905 / 3529（S8a/b/c + S9b 测试代码中的 `await db.expire_all()`）
- tests/conftest.py:61（`db` fixture 是 AsyncSession；SQLAlchemy `expire_all()` 是同步方法）

**Impact**: S8a/S8b/S8c/S9b 按计划实现会因 `TypeError` 失败，R3-F002 的"fixture 组合已可运行"判断不成立。

**Repair hypothesis** (advisory)：全面替换 `await db.expire_all()` → `db.expire_all()`。禁止在 `AsyncSession` 上 await 同步 API。

**Status**: verified
**Terminal**: pending

---

#### R4-F003 — MED — test-gap — defect_fix — Inv-conflict: direct (INV-010)

**Before-behavior**: 计划把 S7c 描述为"best-effort 不稳定"，但给出的实现实际上**在逻辑上自相矛盾**。

**After-behavior**: 若要验证 retry 分支，rival 记录必须来自**独立 session/事务并已提交**；当前"同 session、同 SAVEPOINT 内偷插 rival"在 SAVEPOINT 退出时会被一起 rollback，re-SELECT 永远找不到它。

**Evidence**:
- plan.md:1886 / 1900 / 1912（S7c 的 flaky_flush 实现——monkeypatch 在 nested 上下文内 `self.add(rival) + original_flush` + raise）
- design.md:297 / 300（retry 分支 "re-SELECT 同 (subject_id, name) 的 Question (rival 方已 commit，可见)"——对 rival 来源的假设）

**事务语义事实**：`async with db.begin_nested():` 内部任何插入都在 SAVEPOINT 子事务；`raise IntegrityError` 退出时 SAVEPOINT 整体 rollback，包括偷插的 rival。re-SELECT 看不到被回滚的记录。

**Impact**: Task 7 里对 retry 分支的"可实现草稿"是假的；S7a/S7b 可成立，但 S7c 不能按当前方案证明任何东西。

**Repair hypothesis** (advisory)：要么把 S7c 降格为**纯 test_debt**（删除当前伪实现代码，只保留 test_debt 条目 + 具体理由 + deadline）；要么单独设计双 session / PostgreSQL 用例（需要独立测试基建）。禁止"在同一 SAVEPOINT 里注入 rival 再期待 rollback 后仍可 re-SELECT"。

**此项触及 INV-010，requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

#### R4-F004 — MED — test-gap — defect_fix — Inv-conflict: direct (INV-009)

**Before-behavior**: S8d 声称能证明 `start_pipeline` "真的调了 `build_pipeline_save_answer_fn` 并把其结果传给 `run_pipeline`"。

**After-behavior**: 现有断言只证明传了一个非空 callable；`async def noop(**kwargs): pass` 这类哑闭包也会通过 `callable(save_answer_fn)` + `save_fn is not None` + `await save_fn(...)` 无异常退出（orphan skip 分支）。

**Evidence**:
- plan.md:2917（S8d 断言 2：`"save_answer_fn" in captured_kwargs`）
- plan.md:2924（断言 `save_fn is not None` + `callable(save_fn)`）
- plan.md:3001 / 3007 / 3011（S8d-b tpl_path 分支同样的弱断言）

**Impact**: R3-F003 只修到了"不是 200-only"，但还没修到"真实 wiring 被守住"；INV-009 仍可被哑闭包绕过。错误实现 `start_pipeline` 内传 `save_answer_fn=lambda **_: None` 会通过 S8d。

**Repair hypothesis** (advisory)：
- 方案 A：S8d 显式 `spy_factory = mock.patch("edu_cloud.modules.scan.pipeline_router.build_pipeline_save_answer_fn", wraps=original)`，断言 `spy_factory.called` + `spy_factory.call_args.kwargs["regions"] == tpl_a.regions`
- 方案 B：`mock.patch("...build_pipeline_save_answer_fn", return_value=sentinel_closure)`，断言 `captured_kwargs["save_answer_fn"] is sentinel_closure`（identity 透传）
- **Forbidden**：只断言 `callable(save_answer_fn)` 或 `is not None`

**此项触及 INV-009，requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

#### R4-F005 — LOW — design-concern — defect_fix — Inv-conflict: none

**Before-behavior**: CR-2 锚点段把 `list_scan_images()` 记录成直接调用。

**After-behavior**: 锚点段应准确记录真实代码里存在 `except FileNotFoundError → HTTPException(400)` 的异常翻译。

**Evidence**:
- plan.md:158（CR-2 锚点段的 list_scan_images 行）
- pipeline_router.py:135 / 137（真实代码的 try/except FileNotFoundError → raise HTTPException(400)）

**Impact**: "现实代码锚点"未达到字节级对齐；小缺陷，不阻塞 PASS。

**Repair hypothesis** (advisory)：补 CR-2 锚点段的异常翻译描述。

**Status**: verified
**Terminal**: pending

---

### R4 PASS/FAIL 判定

- HIGH code-bug: R4-F001 + R4-F002 → 阻塞 PASS
- MED test-gap: R4-F003 + R4-F004 → 阻塞 PASS
- LOW design-concern: R4-F005 → 不阻塞（按 review-templates 规则）

**R4 结论: FAIL**

### R4 核实结论摘要

| R3 Finding | R4 判定 | 说明 |
|-----------|---------|------|
| R3-F001 (S7 拆 a/b/c) | **部分成立** | S7a/S7b 合理；S7c 逻辑不可证（R4-F003）|
| R3-F002 (S8 fixture 改 client+db) | **不成立** | 根因在 `async_session` 模块顶层绑定 + expire_all API 误用（R4-F001/F002）|
| R3-F003 (S8d 入口级装配) | **部分成立** | 比"只看 200"强，但 callable 断言太弱（R4-F004）|
| R3-F004 (V3 基于真实 mock 重写) | **基本成立** | CR-3/CR-4 对齐 + dialog 中转 + disabled 前置都对 |
| R3-F005 (工厂 signature → regions) | **基本成立** | 统一两条分支方向与真实 start_pipeline 一致 |

### R4 的好消息

与 R3 不同，R4 的 5 条 finding 都是**具体、可修复的技术 bug**，不是设计矛盾或"凭假设构造"的方法论问题：

- **R4-F001**: Python import 语义——单行 `import ... as db_mod` 即可修
- **R4-F002**: `expire_all` 是同步 API——正则替换 `await db.expire_all()` → `db.expire_all()`
- **R4-F003**: S7c 降级为纯 test_debt——删除伪实现代码
- **R4-F004**: S8d 加 spy 或 sentinel——中等改动
- **R4-F005**: 锚点补一行异常描述——最小改动

估计修复成本：~100-200 行 plan 修改，无需重写 Task。

### 3 轮硬额度 + R4 扩展用尽

按 review-templates.md 规则，每批最多 3 轮；R4 是用户授权的扩展。现在需要再次向用户决策：
1. **R5 循环（再扩展）** — 4 条 finding 都是可修复的，修复后 Gate 1 PASS 概率 >85%
2. **accepted-risk 降级** — 把 4 条 finding 记录为风险进入执行
3. **design abandonment** — 不合理（这些是测试实现问题，不是设计问题）

**用户决策**: 选 A (R5 循环)

---

[edu-cloud] GPT Reviewer | 2026-04-12 07:04:00

## Round 5 审查报告 — FAIL（2 new findings，1 HIGH / 1 MED）

**审查对象**（R4 处置后）:
- plan: 已 commit `40da245`（R4 五 finding 处置）
- design: 未改动

**原始输出日志**: `docs/plans/.codex-f003-plan-review-r5-raw.log`
**SHA256**: `000335e00b33911b15939eb1ae7bda320b1fe945e0b310e1fa6894bcd3623013`
**Token used**: 240213
**结论**: **FAIL**

### R5 核实结论摘要

| R4 Finding | R5 判定 | 说明 |
|-----------|---------|------|
| R4-F001 | **成立** | Task 11 Step 3 已改 `import edu_cloud.database as db_mod` + `db_mod.async_session()` 运行时查找 |
| R4-F002 | **成立** | CR-1 fact 6 在；可执行片段里没有 `await db.expire_all()` |
| R4-F003 | **成立** | S7c 实现体删除，改为 disposition + test_debt |
| R4-F004 | **不成立** | spy_return API 在 Python 3.11 不存在（R5-F002）|
| R4-F005 | **成立** | CR-2 已补 FileNotFoundError → HTTP 400 翻译，与 pipeline_router.py:136 对齐 |

### R5 Finding 清单

#### R5-F001 — MED — code-bug — defect_fix

**Before-behavior**: 计划把 CR-1..CR-4 标为"现实代码锚点/真源"，应当可作为字节级摘抄依据。

**After-behavior**: 当前锚点段仍是"改写版摘录"，混入 `...` 省略符、重写注释、插入说明性 HTML 注释、并省略了真实源码行，未达到 byte-level accurate 要求。

**Evidence**:
- plan.md:57 / 59 / 67（CR-1 代码块使用 `...` 省略和改写）
- tests/conftest.py:67 / 71 / 88（真实源码对应行）
- plan.md:129 / 159（CR-2 代码块省略）
- pipeline_router.py:113 / 145 / 156（真实源码对应行）
- plan.md:185 / 193（CR-3 代码块插入 HTML 注释和省略）
- ExamDetailPage.vue:468 / 470（真实源码对应行）

**Impact**: 这不是文风问题，而是"锚点真源"失真。后续 reviewer / executor 无法机械地用锚点反查现实代码，且不满足用户本轮要求的"先读 anchor files 并验证锚点段 byte-level accurate"。

**Repair hypothesis** (advisory)：用源码原文替换 4 个 CR 代码块，禁止 `...`、禁止改写/补写注释、禁止插入不在源码里的说明标签；若要解释事实，放到代码块外（不放代码块内）。

**Status**: verified
**Terminal**: pending

---

#### R5-F002 — HIGH — test-gap — defect_fix — Inv-conflict: direct (INV-009)

**Before-behavior**: R4-F004 原问题是 S8d 只有 `callable` / `is not None` 弱断言，无法证明 `start_pipeline` 真正把"工厂返回的那个闭包对象"传给 `run_pipeline`。

**After-behavior**: R5 方案把断言升级为 `captured_kwargs["save_answer_fn"] is spy_factory.spy_return`，但**该 API 在当前仓库支持的 Python 3.11.9 环境并不存在**。GPT 自行在 Python 3.11.9 环境用最小样例实测 `patch.object(..., wraps=...)` 返回的 `MagicMock` **不带 `spy_return` 属性**——断言会 `AttributeError`，测试在断言阶段直接失效。

**Evidence**:
- plan.md:2989 / 3078 / 3085 / 3282（S8d-a / S8d-b 测试代码的 `spy_factory.spy_return` 引用）
- pyproject.toml:4（Python 3.11 版本约束）
- GPT 实测验证：Python 3.11.9 环境下 `patch.object + wraps` 返回的 MagicMock 无 `spy_return` 属性

**Impact**: INV-009 的入口级 wiring 护栏仍然缺失。S8d 不能证明 DB 分支和 tpl_path 分支都把"工厂真实返回值"透传给 `run_pipeline`，R4-F004 处置结论**实际不成立**。

**Repair hypothesis** (advisory)：不要依赖 `spy_return`。改为**显式 wrapper / side_effect 捕获真实返回闭包**，再做 identity 断言：

```python
# 正确方案: 自定义 tracked_factory 用外部列表捕获真实返回值
original_factory = pr_mod.build_pipeline_save_answer_fn
factory_returns = []

def tracked_factory(**kwargs):
    result = original_factory(**kwargs)
    factory_returns.append(result)
    return result

with patch.object(
    pr_mod, "build_pipeline_save_answer_fn",
    side_effect=tracked_factory,
) as spy_factory:
    # ... start_pipeline
    pass

assert spy_factory.called
assert len(factory_returns) == 1
assert captured_kwargs["save_answer_fn"] is factory_returns[0]  # identity 成立
```

**禁止模式**：
- ❌ 退回 `callable(...)` 或 `is not None`
- ❌ 使用 `spy_factory.spy_return`（Python 3.11 下不存在）
- ❌ 另造 closure 然后 `is` 断言（会必然失败，等于没测）
- ❌ 用 `MagicMock()` 占位通过测试

**此项触及 pipeline_router.py 风险模块与 INV-009，requires independent fix design + Semantic Regression Gate**

**Status**: verified
**Terminal**: pending

---

### R5 PASS/FAIL 判定

- HIGH test-gap: R5-F002 → 阻塞 PASS
- MED code-bug: R5-F001 → 阻塞 PASS

**R5 结论: FAIL**

### R5 的好消息

与 R3/R4 一样，R5 的 2 条 finding 都是**具体、可修复的技术细节**：

- **R5-F001 (MED)**：用源码原文替换 4 个 CR 锚点代码块。机械工作，无设计讨论。
- **R5-F002 (HIGH)**：S8d 改用外部列表 `factory_returns` + `side_effect=tracked_factory` 捕获真实返回值。GPT 已给出具体修复草稿。

修复量：R5-F001 重写 4 个代码块 + R5-F002 改两个测试函数 = ~150 行 plan 修改。

### R4 缩窄成效

| Round | Finding 数量 | 严重度 |
|-------|-------------|-------|
| R1 | 6 | 4 HIGH / 2 MED |
| R2 | 5 | 3 HIGH / 2 MED |
| R3 | 5 | 3 HIGH / 2 MED |
| R4 | 5 | 2 HIGH / 2 MED / 1 LOW |
| **R5** | **2** | **1 HIGH / 1 MED** |

循环正在收敛。R5 修复后 R6 的 finding 数预期 ≤1。

---

## Round 6 审查报告 — FAIL（1 new finding，1 MED）

**审查对象**（R5 处置后）:
- plan: commit `fd2e9bd`（R5 两 finding 处置：CR-1/CR-2/CR-3 字节级重写 + S8d 改 tracked_factory）
- design: 未改动

**原始输出日志**: `docs/plans/.codex-f003-plan-review-r6-raw.log`
**SHA256**: `f41878519a8db37100a3219a22f90724622bc392603acfe0698e76fde4bacc13`
**Token used**: 112,566
**结论**: **FAIL**

### R6 核实结论摘要

| R5 Finding | R6 判定 | 说明 |
|-----------|---------|------|
| R5-F001 | **部分成立** | CR-1 / CR-3 已字节级对齐；CR-2 拼接段多 1 空行；CR-4 import 后丢失空行（见 R6-F001）|
| R5-F002 | **成立 resolved** | GPT 本地 Python 3.11.9 实测 `side_effect=tracked_factory` 下 `spy_factory.called/.call_args` 正常工作；`factory_returns[0]` identity 护栏语义正确；INV-009 test_ref、Task 11 测试名、审查清单均已切到新函数名；`spy_return` 只在解释性文字保留 |

### R6 Finding 清单

#### R6-F001 — MED — code-bug — defect_fix

**Before-behavior**: 计划声明 CR-1..CR-4 已全部改成与源码逐字符对齐的锚点，可作为后续实现和审查真源。

**After-behavior**: CR-2 与 CR-4 仍未完全对齐源码：
- CR-2 在 `tpl_path` 字段后、`@router.post("/start")` 前多了 1 个空行（源码按 CR-3 "段间单空行拼接" 约定应为 1 空行）
- CR-4 丢了 `import client from './client'` 之后的空白行（源码 `subjects.js:L2` 是空行）

CR-1 已对齐；CR-3 按"4 段之间单个空行拼接"的约定已对齐。

**Evidence**:
- `docs/plans/2026-04-11-f003-question-writeback-plan.md:117`（CR-2 拼接段）
- `src/edu_cloud/modules/scan/pipeline_router.py:25`（CR-2 源码锚点）
- `docs/plans/2026-04-11-f003-question-writeback-plan.md:324`（CR-4 代码块起始）
- `frontend/src/api/subjects.js:1`（CR-4 源码锚点）

**Inv-conflict**: none

**Impact**: R5-F001 "已完全修复"结论不成立，B 类"代码库对齐"仍未过关。不影响代码实现语义，但破坏锚点"字节级真源"承诺。

**Repair hypothesis** (advisory): CR-2 删除多出的 1 个空行；CR-4 补回 `import` 后的空白行；修后再按同一方式复比。

**Status**: verified
**Terminal**: resolved-correct（见 R7）

### R6 PASS/FAIL 判定

- MED code-bug: R6-F001 → 阻塞 PASS
- **R6 结论: FAIL**

### R6 的好消息

1. **R5-F002 彻底消解**：GPT 本地实测 `side_effect=tracked_factory` 模式语义正确，HIGH test-gap 已 resolved
2. **Finding 降到 1 条**：纯粹的文档空白行偏差，不改变代码实现语义
3. **收敛信号强**：6 → 5 → 5 → 5 → 2 → 1 单调下降
4. **修复成本极低**：2 处 Edit，约 1 分钟

用户授权第 4 次扩展 R7，纯格式修复。

---

## Round 7 审查报告 — PASS（0 finding）

**审查对象**（R6 处置后）:
- plan: commit `7a7fa1e`（R6-F001 处置：CR-2 删 1 空行 + CR-4 补 import 后空行）
- design: 未改动

**原始输出日志**: `docs/plans/.codex-f003-plan-review-r7-raw.log`
**SHA256**: `38d0f392575b034c6178e8b419ba7f15124eb1e28301e6248c842c4cd6996d8f`
**Token used**: 89,198
**结论**: **PASS**

### R7 核实结论摘要

| R6 Finding | R7 判定 | 说明 |
|-----------|---------|------|
| R6-F001 CR-2 | **resolved-correct** | GPT 直读 plan L122 `tpl_path` + L124 `@router.post("/start")`，单空行拼接，符合 R6 要求 |
| R6-F001 CR-4 | **resolved-correct** | GPT 用 PowerShell 对 plan L324-327 4 行 JS 块与 `frontend/src/api/subjects.js` L1-L4 做 `TEXT_EXACT_EQUAL` + `BYTE_EQUAL_LF` 双重字节级比对，完全一致 |
| `spy_return` 排查 | **通过** | GPT grep `tests/` / `src/` / `frontend/` 未发现匹配；仅剩计划/评审/交接文档和 CLAUDE.md 解释性文字中说明该模式已废弃 |

### R7 Finding 清单

**无新 finding。**

### R7 Plan Verdict

> **PASS**。R6-F001 已实质解决，本轮未发现新的自洽性、锚点对齐、架构适配、测试契约或 Contract Pack 阻塞项；该计划可批准，R7 可作为最终轮结束。

### Gate 1 最终收敛轨迹

| Round | Finding | 严重度 | 核心问题类 |
|-------|---------|--------|-----------|
| R1 | 6 | 4 HIGH / 2 MED | Contract Pack 缺失、E2E 断言漏洞 |
| R2 | 5 | 3 HIGH / 2 MED | 测试契约不完整、工厂函数抽取设计 |
| R3 | 5 | 3 HIGH / 2 MED | 现实代码锚点缺失、fixture 选型 |
| R4 | 5 | 2 HIGH / 2 MED / 1 LOW | monkey-patch 语义、expire_all 同步 API、S7c 伪实现 |
| R5 | 2 | 1 HIGH / 1 MED | 锚点非字节级、spy_return API 不存在 |
| R6 | 1 | 1 MED | CR-2/CR-4 空白行对齐 |
| **R7** | **0** | **—** | **Gate 1 PASS** |

**Gate 1 总耗时**: 7 rounds / 用户第 4 次扩展授权 / finding 单调收敛 6→5→5→5→2→1→0

**语义层风险消除路径**:
- R3 引入"现实代码锚点" CR-1..CR-4 段
- R4 修正 `import ... as db_mod` 运行时查找、`expire_all()` 同步 API、S7c 延期 PostgreSQL CI
- R5 追加 S8d 工厂 identity 断言（初版用 spy.spy_return，不存在于 Python 3.11）
- R6 S8d 改用 `side_effect=tracked_factory` + `factory_returns` 外部列表
- R7 锚点段完成字节级对齐

**Gate 1 批准**: 计划可进入执行阶段。
