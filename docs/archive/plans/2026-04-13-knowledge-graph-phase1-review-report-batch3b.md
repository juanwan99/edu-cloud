[edu-cloud] GPT Reviewer | 2026-04-18 06:30:00

<!-- anchor: finding-classification -->
## 审查报告: Task 11-12（Batch 3.b，Round 1）

- 结论: **FAIL**
- Reviewer: GPT Codex (gpt-5.4) via codex-cli aiproxy
- Subject: commits `f2e9ba9..5607a9a`（T11 + T12，10 文件含 CLAUDE.md + 审查单 commit `26f2af5`）
- Raw output: `docs/plans/.codex-raw-code_review_batch3b-20260418-065245.log`（SHA256 `dd6a4fea44079fac2ec41a81dd34793f91b39a8afa56cf8e0b442ddac5fa3786`）
- gates.json key: `code_review_batch3b` / round=1 / status=fail
- Worktree: `/home/ops/projects/edu-cloud-w2`（独立 W2 worktree，主 wt 借给 W4）

## 变更理解

Batch 3.b 落盘了知识图谱可视化 Phase 1 T11 + T12 两个前端 Task：

- **T11（commits `f2e9ba9` + `191a169` CLAUDE.md 补）**: NodeDetailDrawer 追加 `exam_items` + `study_unit` 2 个 n-tab-pane（F007 保留原 5 tab，0 删除行），新组件 ExamItemsTab.vue（分页 + 空/有/加载三态，从 API unwrapped data 消费）+ StudyUnitTab.vue（SU id/estimated_minutes/prerequisite_depth/planning_weight/textbook_chapters），api/knowledgeTree.js 新增 `getExamItems` + `getStatsOverview` 2 函数（async + return resp.data，下游 unwrap 消费）。对应测试 3 + 2 = 5 tests。

- **T12（commit `5607a9a`）**: useKnowledgeTree.js 追加模块级导出 `buildChapterTree(nodes)` 纯函数（book→chapter→section 聚合 + sort + concept_ids dedup）。TreeNavPanel.vue 内部新增 `navMode` ref（module/chapter 双模式）+ chapterTreeData computed + handleSelect 对聚合 key `book:/chapter:/section:` 早退 + `defineExpose({ navMode, handleSelect })` 供测试入口。F002 硬契约: props/emit 不变；F010: select-node 仍 emit 完整 node 对象。测试 3 buildChapterTree + 6 TreeNavPanel = 9 tests。

意图层面: 扩展 NodeDetailDrawer 支持"高考真题分页浏览"和"学习单元规划信息"；TreeNavPanel 在现有模块树之外提供教材章节导航视角。

## 对抗性审查

从审查者视角，GPT 独立核查了 Executor 交接单的关键声明:

1. **实际运行新增 3 个前端测试文件**: 14/14 PASS，问题不在"跑不通"而在"覆盖不到关键错误实现"。
2. **异步加载竞态追踪**: 沿 ExamItemsTab `load()` 的生命周期审视——`watch(props.nodeId, () => { page.value = 1; load() }, { immediate: true })` + `load()` 无 seq guard / AbortController。对照同目录下 NodeDetailDrawer.vue:140-183 已有 `fetchSeq` 序号守卫 pattern——Executor 未沿用。得出 F001。
3. **分页测试 mutant 假设**: ExamItemsTab.test.js 的 "pagination triggers reload" 测试名承诺验证分页，但实际断言 `expect(getExamItems).toHaveBeenCalledWith('Z', 1, 10)`——这是 immediate 首屏调用而非翻页。假设删除 `prevPage/nextPage` 函数实现 → 测试仍 PASS（test 不触发它们）；删除 `watch(nodeId)` 中 `page.value = 1` 重置 → 测试仍 PASS（只发了 1 次调用，page reset 未被断言）。得出 F002。
4. **入口级测试合规审查**: TreeNavPanel.test.js 的"导航模式切换"用 `wrapper.vm.navMode = 'chapter'`、`wrapper.vm.handleSelect([...])` 直接操作组件实例。根据 plan T12 测试契约 §3185"模拟点击'按教材章节' radio button"，该测试入口偏离 plan。假设删除 `<n-radio-group v-model:value="navMode">` 或断开 `v-model`——测试仍 PASS（未触发 DOM 层）。得出 F003。
5. **0 值语义 mutant**: StudyUnitTab.test.js fixture 只有 `planning_weight: { priority_score: 8.5, exam_frequency: 9 }` 两个非零值。假设把实现的 `?? '—'` 回退为 `|| '—'`——测试仍 PASS（fixture 无 0 值可检）。得出 F004。
6. **Contract Pack freshness**: plan §3181 明文 "navMode 作为组件内部状态，不暴露到外部"。当前 `defineExpose({ navMode, handleSelect })` 引入未列出 public API，按 Phase 0 verification 判 freshness process finding。得出 F005。

上述证据均为文件级 grep / 行号可验证，非推测。

## 第一段: 测试充分性（Test Adequacy）

发现 3 个 test-gap（F002 HIGH + F003 MED + F004 MED）: 测试全绿但无法在错误实现下红。

1. ExamItemsTab 分页测试不触发翻页 → 删 prevPage/nextPage 仍 PASS（F002 HIGH）
2. TreeNavPanel 测试直接操作组件实例不走 DOM → 删 radio group 仍 PASS（F003 MED）
3. StudyUnitTab `??` 0 值语义 fixture 无 0 值 → 回退 `||` 仍 PASS（F004 MED）

不满足"测试真的会在错误实现下失败"的硬判定。

## 第二段: 行为正确性（Behavioral Correctness）

发现 1 个 code-bug（F001 MED）: ExamItemsTab 异步请求竞态 — A→B 快速切换，A 旧请求晚于 B 覆盖状态。对照 NodeDetailDrawer.vue:148 同目录已有 `fetchSeq` 守卫 pattern，Executor 未复用 → lifecycle/race red-flag。

## 第三段: 未测试风险（Non-tested Risks）

- F001 竞态未被任何测试覆盖
- 明显"测试覆盖纯函数返回 + immediate 加载"倾向，真实风险（DOM 交互 + 异步生命周期 + 0 值边界）未覆盖
- 组件级 vitest 14/14 全绿但不改变集成缺口

## Phase 0 — Contract Pack 验证

- INV-001 / INV-003 / INV-005 verification 映射在仓库中能找到对应测试 ✓
- INV-002 仍按 plan 标记为 Batch 3.c deferred 项，本批次不构成新增偏离 ✓
- INV-004（TreeNavPanel 相关）"部分落地但验证偏弱"，且出现 freshness 偏离（F005）⚠️
- `test_debt` 三项理由和 deadline 可接受，本轮不构成阻断 finding ✓

---

<!-- anchor: finding-type -->

## 发现清单

### F001 — ExamItemsTab 异步请求竞态

Severity: MED
Category: code-bug
Type: defect_fix

Before-behavior: 在"高考真题全集" tab 已打开时，若用户快速从节点 A 切到节点 B，A 的旧请求晚于 B 返回时，仍会覆盖当前组件状态，导致抽屉显示的是 B 节点，但题目列表回退成 A 的结果。

After-behavior: 只有当前 `nodeId` 对应的最新请求可以写回 `items/total/loading`。

Evidence:
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue:48`（load 函数入口）
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue:52`（await getExamItems 无 seq guard）
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue:66`（watch immediate，无 abort）
- `frontend/src/components/knowledge-tree/NodeDetailDrawer.vue:166`（参考 pattern：已有 fetchSeq 守卫）

Impact: 用户会在错误节点下看到别的概念的高考题，属于可见错误数据展示；plan 明确把"切换节点时 page 重置为 1"列为边界条件，但这里连基本的最新请求守卫都没有。

Red-flag: ✅ lifecycle / race condition（触发 "requires independent fix design + Semantic Regression Gate"）

Repair hypothesis:
1. 方向: 为 tab 异步加载补"仅最新请求生效"生命周期保护（seq guard 或 AbortController）
2. 禁止: 请求返回后比对文本是否像当前节点、延时/节流掩盖
3. `requires independent fix design + Semantic Regression Gate`

三态标注: **pending**（等 Planner 判决）

---

### F002 — ExamItemsTab 分页测试不验证实际分页

Severity: HIGH
Category: test-gap
Type: defect_fix

Before-behavior: `ExamItemsTab` 的 "pagination triggers reload" 测试并没有点击分页按钮，也没有断言翻页后的第二次请求；即使删掉 `prevPage` / `nextPage` 或删掉"切换节点时 page 重置为 1"的核心逻辑，现有测试仍会通过。

After-behavior: 测试应在错误实现下失败，至少覆盖"点击下一页发起第 2 页请求"和"切换 nodeId 后 page 重置为 1"。

Evidence:
- `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:33`（断言入口）
- `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:37`（仅断言首屏调用参数）
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue:63,64`（prevPage / nextPage 未被测试触发）
- `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:2796`（plan 边界: 分页）
- `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:3164`（plan 边界: 切节点 page=1）

Impact: Task 11 宣称已覆盖的分页边界其实未被验证，回归时很容易出现"永远只请求第一页"而测试仍全绿。

Red-flag: ❌

Repair hypothesis: 补点击下一页 trigger 断言第 2 次请求 `getExamItems(nodeId, 2, 10)` + 切 nodeId 后断言 page 回到 1 的反证。

三态标注: **pending**

---

### F003 — TreeNavPanel 测试未从 radio button 用户入口触发

Severity: MED
Category: test-gap
Type: defect_fix

Before-behavior: `TreeNavPanel` 的"导航模式切换"与 emits 契约测试直接操作 `wrapper.vm.navMode` / `wrapper.vm.handleSelect`，没有按 plan 要求从 radio button 的用户入口触发；如果模板里的 `<n-radio-group>` 被删掉、`v-model` 断开，当前测试仍可通过。

After-behavior: 测试应通过真实 DOM 交互切换模式，并通过树组件选择路径验证 emit 契约。

Evidence:
- `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:3185`（plan 测试契约: "模拟点击'按教材章节' radio button"）
- `frontend/src/components/knowledge-tree/TreeNavPanel.vue:5`（n-radio-group 模板节点）
- `frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js:76,83,103`（测试走 wrapper.vm 直接操作）

Impact: Task 12 的"用户入口级验证"没有落地，CE-001 所警告的"逻辑镜像测试"问题在这里又回来了，Contract Pack 对 INV-004 的验证力度被高估。

Red-flag: ❌

Repair hypothesis: 改走 DOM 事件 trigger（`wrapper.find('[value="chapter"]').trigger('click')` 或 `.setValue()`），移除对 `wrapper.vm.navMode` 的直接操作。与 F005 关联——DOM 化后 `defineExpose` 可移除。

三态标注: **pending**（与 F005 联动修复）

---

### F004 — StudyUnitTab `??` 0 值语义未测

Severity: MED
Category: test-gap
Type: defect_fix

Before-behavior: `StudyUnitTab` 实现专门把 `planning_weight` 的显示从 `||` 改成了 `??` 以保留 0 值语义，但测试数据只覆盖 `9` 和 `8.5`；若把实现退回 `||`，现有测试仍会全部通过。

After-behavior: 测试应显式断言 `0` 会显示为 `0`，而不是退化成 `'—'`。

Evidence:
- `frontend/src/components/knowledge-tree/StudyUnitTab.vue:21`（exam_frequency ?? '—'）
- `frontend/src/components/knowledge-tree/StudyUnitTab.vue:34`（priority_score ?? '—'）
- `frontend/src/__tests__/knowledge-tree/StudyUnitTab.test.js:13`（fixture 无 0 值）

Impact: handoff 把这次偏离 plan 的理由建立在"0 值语义保留"上，但当前测试并不能锁住这条语义，后续很容易无声回退。

Red-flag: ❌

Repair hypothesis: 新增 fixture `planning_weight: { exam_frequency: 0, error_prone: 0 }` + 断言文本包含 `'0'`（非 `'—'`）。

三态标注: **pending**

---

### F005 — `defineExpose({ navMode, handleSelect })` 新增未登记 public API

Severity: MED
Category: design-concern
Type: behavior_change

Before-behavior: plan 明确要求 `navMode` 作为组件内部状态，"不暴露到外部"；`TreeNavPanel` 的公共契约仅限现有 props/emits。

After-behavior: 当前实现通过 `defineExpose({ navMode, handleSelect })` 新增了实例级公开表面，测试和任何父组件 ref 都可以直接操纵内部状态/方法。

Evidence:
- `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:3181`（plan 硬约束: navMode 不暴露）
- `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:4108`（plan Contract Pack 定义的公共 API 不含 expose）
- `frontend/src/components/knowledge-tree/TreeNavPanel.vue:190`（defineExpose 调用）

Impact: 这是 Contract Pack freshness 明确要求上报的 process finding。虽然它没有改 props/emits，但确实引入了未列出的 public API，后续 review 会误判真实契约边界。

Red-flag: ✅ behavior_change（触发 "requires independent fix design + Semantic Regression Gate"）

Repair hypothesis:
1. 方向 A: 把测试入口收回到真实用户入口（与 F003 同方向）→ 移除 defineExpose
2. 方向 B: 把实例表面纳入契约文档 → 正式 plan 追加 `expose` 契约（与 plan §3181 冲突，需 plan R7+ 修订）
3. 禁止: 继续依赖未登记 `defineExpose` 表面扩散更多测试或调用方
4. `requires independent fix design + Semantic Regression Gate`

三态标注: **pending**（与 F003 联动修复，方向 A 一次改动消解两 finding）

---

## R2 合格性分析

按 codex-review skill §Gate 条件，R1 FAIL 后评估 R2 升级条件（任一满足即可）:

1. Tier = T4 → ❌ 本 Batch 3.b Tier = T3
2. topic 标签含 `remote` / `deploy` / `publish` → ❌ topic `kg-phase1-batch3b` 无此标签
3. 跨模块重构（plan 声明修改文件数 ≥2 且涉及 ≥2 模块）→ ❌ 单模块（`frontend/src/components/knowledge-tree/` + 同模块 `__tests__/` + `api/`，均前端 kg 单模块）

**判定**: R2 条件 3 条均不满足。按 skill §Gate 条件: **"不满足 → 直接拆 topic（例如把 batch 切成 batch4a + batch4b），每个子 batch 重新算 R1"**。

## 与全局设计 / handoff 的潜在冲突（L017 自审）

| Finding | 与 handoff/plan 冲突点 | 决议方向 |
|---------|--------------------|---------|
| F001 | plan 示例 ExamItemsTab.vue 本身无 seq guard；Executor 严格按 plan 示例实现 | plan 示例遗漏该保护；NodeDetailDrawer.vue:148 已有 pattern 可参考。defect_fix 补救合理 |
| F002 | plan T11 Step 5 给出的示例测试就是 `expect(getExamItems).toHaveBeenCalledWith('Z', 1, 10)`，Executor 严格抄写 | plan 示例测试 weak；反证"删 prevPage/nextPage 测试仍 PASS"成立。plan 示例瑕疵 → plan R7+ 或现场补救 |
| F003 | handoff 前置"测试风格约束"要求"入口级：测试走 API / 用户可触达入口" + Batch 3.a F002 教训；Executor 未完全兑现 | handoff 明文约束被违反；defineExpose 是 scope 内可能的入口选择之一，但不是"用户可触达入口" |
| F004 | Executor 🔀 偏离 3 自称"0 值语义保留"，但未测 0 | Executor 偏离声明未配反证，contract 口说无凭 |
| F005 | plan §3181 明文 "navMode 作为组件内部状态，不暴露到外部" vs Executor 🔀 偏离 6 自述"defineExpose 新增" | plan 硬契约 vs Executor 偏离 — 显式冲突，属 freshness process finding；behavior_change 需 Planner 独立设计 |

F003 + F005 **本质同源**: 测试入口选择。改用 DOM 触发（F003 修复），defineExpose 可移除（F005 自动消解）。

## Planner 决策点（待回传）

1. 拆 batch 3.b → 3.b.1 + 3.b.2 + ...？粒度建议:
   - **3.b.i (Code + Test 修)**: F001 race guard + F002 分页测试 + F004 0 值测试（defect_fix 集中修）
   - **3.b.ii (Contract / 入口)**: F003 + F005 测试入口 DOM 化 + 移除 defineExpose（behavior_change 独立设计 + Semantic Regression Gate）
2. 或 WONTFIX 部分 finding（需强理由）
3. 或 F005 升级 → 正式 plan 追加 `expose` 契约追认 defineExpose（与 plan §3181 冲突，需 plan 修订）

## 送审后续

1. Executor 在当前分支 `feat/kg-batch3b` 无权自行进入 R2 修复（skill 明文: 不满足 R2 条件 → 必须拆 topic）
2. 等 Planner 裁决: (a) 拆 batch 粒度 (b) behavior_change 处置方式 (c) gates.json 回执 round/reason 最终写入格式
3. 当前已写入 gates.json `code_review_batch3b=fail` R1 回执（见 gates.json）

---

status: reviewed-by-gpt / verdict: FAIL / planner-decision: pending
