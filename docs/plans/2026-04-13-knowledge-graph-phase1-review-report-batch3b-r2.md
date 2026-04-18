[edu-cloud] GPT Reviewer | 2026-04-18 08:32:00

<!-- anchor: finding-classification -->
## 审查报告: Task 11-12（Batch 3.b，Round 2）

- 结论: **FAIL**
- Reviewer: GPT Codex (gpt-5.4) via codex-cli aiproxy
- Subject: commits `66ab2b8..317dfb6`（R2 5 finding 修复 + handoff commit `9844199`）
- Raw output: `docs/plans/.codex-raw-code_review_batch3b-r2-20260418-083502.log`（SHA256 `138d66e4d9db38d1fcbd6d19e34632ea11e5bd4e005508ffd1e6cba642ca4f45`）
- gates.json key: `code_review_batch3b` / round=2 / status=fail
- R1 report: `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b.md`（5 findings FAIL）
- R2 handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3b-r2.md`
- Worktree: `/home/ops/projects/edu-cloud-w2`

## 变更理解

R2 修复 R1 5 个 finding，5 个独立 commit + CLAUDE.md 2 次追加:

- `66ab2b8` F001: ExamItemsTab.vue 加 `let fetchSeq = 0` + `mySeq = ++fetchSeq` + try/catch/finally `if (mySeq !== fetchSeq) return` 早退（参 NodeDetailDrawer:148 pattern）
- `fce6412` F002: ExamItemsTab.test.js 追加 2 mutant test（nextPage click → page=2 请求 + nodeId change → page reset）
- `6806f2b` F003: TreeNavPanel.test.js 6 个 UI 测试改 DOM/emit 入口（radio.setValue + findComponent(NTree).$emit）
- `9d1e6c7` F004: StudyUnitTab.test.js 追加 0 值 fixture test（断言 weight-value text 分布 3×'0' + 1×'—'）
- `317dfb6` F005: TreeNavPanel.vue 移除 `defineExpose({ navMode, handleSelect })` + CLAUDE.md 追加 R2 说明（方案 A 用户批准）

基线: R1 153 → R2 knowledge-tree 子集 14 files / **156 tests PASS**（+3 mutant）。

## 对抗性审查

GPT 独立 verify 各 R2 修复:

1. **F002 mutant 验证**: 删掉 `page++` 或 watch `page.value = 1` 后，新测试红 ✓
2. **F003 DOM 入口验证**: 删掉 `<n-radio-group>` 或 v-model 断开，"chapter mode via radio click" 测试红 ✓
3. **F004 0 值语义验证**: 退回 `??` → `||`，0 变 '—'，`toHaveLength(3)` 断言红 ✓
4. **F005 消解验证**: 运行时无仓内消费者引用 `defineExpose` 暴露的 navMode/handleSelect，子集测试全通过 ✓
5. **F001 fetchSeq guard 验证**: 实现层面看 code 正确（mySeq 比较），但**回归测试层面**: 把 `mySeq !== fetchSeq` 早退或 `finally` 守卫删掉 → knowledge-tree 156 测仍全绿 → HIGH test-gap ❌

## 第一段: 测试充分性（Test Adequacy）

F002/F003/F004 R2 修复**达标**。

**F001 R2 修复不达标**: code 修复正确但测试未锁 — R2 handoff 已 pre-declare "Executor 未逐条跑实测 mutant，F001 反证属说明型"。GPT 明确判 HIGH test-gap。

## 第二段: 行为正确性

无新 code-bug。TreeNavPanel `select-module` / `select-node` 契约仍保持（plan §4036），KnowledgeTreePage.vue:13 集成未破坏。

## 第三段: 未测试风险

仍集中在 F001 的异步时序。F001 code 修复存在但无异步竞态测试证明 "旧请求晚到不会覆盖新状态"。

## Phase 0 — Contract Pack 验证

- INV-001/002/003/004/005: 本轮无 freshness 问题 ✓
- CE-001/002/003: 未被本批改动推翻 ✓
- TD-001/002/003: 未受本批影响 ✓
- plan 中确实没有 `semantic_regression` section（ORACLE_PACK = 'No semantic_regression section found'）

---

<!-- anchor: finding-type -->

## 发现清单

### R2-F001 — ExamItemsTab `fetchSeq` 守卫无回归测试锁

Severity: HIGH
Category: test-gap
Type: defect_fix

Before-behavior: `ExamItemsTab` 的竞态修复依赖 `fetchSeq` 守卫（R2 `66ab2b8` 已落地），但本轮新增测试（F002 的 2 个 mutant 测试）仍只验证请求参数和页码变化；把 `mySeq !== fetchSeq` 早退或 `finally` 守卫删掉 → knowledge-tree 156 测仍全绿。

After-behavior: 需要一个可控异步竞态测试证明 A→B 快速切换时，旧请求晚到不会改写 `items` / `total` / `loading`，页面最终只展示最新 `nodeId` 的结果。

Evidence:
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue:50`（fetchSeq 定义）
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue:56,60,64`（3 处 mySeq guard）
- `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:40`（F002 nextPage test 不覆盖 race）
- `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:54`（F002 nodeId change test 不覆盖 race）

Impact: F001 的核心修复没有被回归测试锁住，后续若有人删掉 `mySeq !== fetchSeq` 早退或 `finally` 守卫，knowledge-tree 全套 156 测仍可保持绿色。按审查规范属于"删除核心逻辑后测试不失败"的 HIGH test-gap，阻塞 PASS。

Red-flag: ✅ lifecycle / race condition（触发 "requires independent fix design + Semantic Regression Gate"）

Repair hypothesis:
1. 方向: 增加入口级异步竞态测试，用两个受控 Promise mock `getExamItems`，先挂起 A（deferred promise），再触发 B 切换（setProps），按 "B resolve → A resolve" 和 "B reject → A resolve" 两条路径断言 UI 仍停留在 B（DOM 文本 + loading state）
2. 禁止 fix patterns: 只断言 `getExamItems` 调用次数/参数；继续使用同步 `mockResolvedValue`；用 `sleep` / 定时器碰运气制造竞态
3. `requires independent fix design + Semantic Regression Gate`

三态标注: **pending**（等 Planner 判决）

---

## R2 合格性分析（skill §Gate 条件）

R2 FAIL → 按 skill 规则: **"R2 仍 FAIL → 拆 topic 或 WONTFIX，不接受 R3 重审"**

gates_lib 入口校验: `round=3 and status != 'blocked'` raise `ValueError` → 写 R3 receipt 会被硬拦截。

## 与 R1 report 的对比

| R1 Finding | R1 Verdict | R2 修复结果 |
|---|---|---|
| F001 MED code-bug | FAIL | code 修复正确 ✓；但测试未锁 → R2-F001 HIGH test-gap 重现（同 subject，finding 维度从 code-bug 变 test-gap）|
| F002 HIGH test-gap | FAIL | **resolved-correct** ✓（R2 实测 mutant 红）|
| F003 MED test-gap | FAIL | **resolved-correct** ✓（DOM/emit 入口 mutant 红）|
| F004 MED test-gap | FAIL | **resolved-correct** ✓（0 值 fixture mutant 红）|
| F005 MED design-concern | FAIL | **resolved-correct** ✓（defineExpose 移除，子集测试全通过）|

**净进展**: R1 5 FAIL → R2 4 resolved / 1 新 test-gap（从 F001 code-bug 衍生出 R2-F001 test-gap）

## Planner 决策点（待回传）

按 skill 硬约束，R3 被 gates_lib 拒绝写入。可选路径:

1. **拆 batch 3.b.iii（推荐）**: 起新子 batch 仅含 R2-F001 异步竞态测试补全（3.b.iii.plan / 3.b.iii R1 → 独立 Gate 2），不改已修复 F002-F005 的代码
2. **WONTFIX + pre-declare**: 在 Contract Pack `test_debt` 追加 TD-004 "ExamItemsTab race test"，deadline 显式标注，但需 Planner 强理由（race 属于可见用户错误数据展示 → WONTFIX 说服力弱）
3. **manual_override**: Planner 显式 override skill 规则，允许 R3 写入（需修 gates_lib 或传 status='blocked' 伪绕过，非常规路径）
4. **部分 WONTFIX + 部分推后**: 接受当前 R2-F001 为已知 test-gap，在 Batch 3.c 合并修复 race test

## 送审后续

1. gates.json 已写 `code_review_batch3b=fail` R2 回执（round=2, raw_hash `138d66e4...`, diff_hash `<compute_range_hash>`）
2. Executor 无权自行进入 R3（gates_lib 入口拒绝）
3. 等 Planner 裁决: 方案 1/2/3/4 或其他

---

status: reviewed-by-gpt-r2 / verdict: FAIL / planner-decision: pending / remaining-finding: 1 (R2-F001 HIGH test-gap)
