[edu-cloud] GPT Reviewer | 2026-04-14 08:39:04

<!-- anchor: finding-classification -->
## 审查报告: Task 9-10（Batch 3.a，Round 1）

- 结论: **FAIL**
- Reviewer: GPT Codex (gpt-5.4)
- Subject: commits `2f7ddad..ebfa83f`（T9 + T10，8 文件含 CLAUDE.md）
- Raw output: `docs/plans/.codex-raw-code_review_batch3a-20260414-083904.log`（SHA256 `597201509daec57ab89ea1c5efc296af7aeb3f7dc6cd9fe7aa9377386db41a57`）
- Range diff hash: `c2a54d3a438150bd2387c8131a9ded393e921b1ad602021592df65feb0b76998`

## 变更理解

Batch 3.a 落盘的是知识图谱可视化 Phase 1 T9 + T10 两个前端 Task：

- **T9（commit `2f7ddad`）**：新增 `heatmapUtils.js`（4 个纯函数：`heatmapColor` log 尺度考频热力色 / `masteryColor` 4 态 / `reviewStatusColor` 3 态 / `nodeSizeFromImportance` 线性映射到 `[20,60]`）+ `ColorModeToggle.vue`（Naive UI n-radio-group 三模式切换 + `hasStudent` disabled 守卫）+ 对应两套单元测试（20 + 5 断言）。

- **T10（commit `ebfa83f`）**：改动 `ConceptMapPanel.vue`——接收 `colorMode` / `nodesWithMastery` 两个新 prop，在 `buildG6Data()` 每个 node 上追加 `style.size=[W, W*0.6]`（按 importance_score）与 `style.fill`（三分支：考频/掌握度/审核状态），新增 `watch([colorMode, nodesWithMastery])` 触发 `graph.setData()/render()` 并保留 `focusedNodeId`，`defineExpose` 追加 `buildG6Data`。同步改动 `KnowledgeTreePage.vue`——挂载 `<ColorModeToggle>`、增 `colorMode` ref + `watch(selectedStudentId)` 自动切换 `mastery/exam_frequency`、把 `color-mode` / `nodes-with-mastery` 绑定到 ConceptMapPanel。测试文件 `ConceptMapPanel.test.js` 追加 3 个行为断言（importance 差异 / colorMode fill 变化 / mastery weak R>G）。CLAUDE.md 两次追加 T9-T10 描述（doc-sync-guard 强制）。

意图层面：让教师工作台在选中学生时把知识图谱节点视觉从"审核状态"切换到"学生掌握度"，并让所有节点大小反映 `importance_score`，考频无学生时默认 log 尺度热力色。

## 对抗性审查

从审查者视角，我用三种手段独立核查了 Executor 交接单的关键声明：

1. **工具函数正确性**：`ColorModeToggle / ConceptMapPanel / heatmapUtils` 三个测试文件 vitest 复跑 64/64 PASS，组件纯函数层面没有异议。
2. **删除被测逻辑的可失败性**：对 T10 新 3 个断言的核心实现路径（`watch([colorMode, nodesWithMastery])` 的 `graph.setData()/render()` + focus replay）做 mutant 假设——**删除整个 watch 块，3 个 T10 断言仍全绿**，因为断言入口走的是 `wrapper.vm.buildG6Data()`（纯函数），没有触发 watch。见 F003。
3. **数据流追踪**：沿 `selectedStudentId` 的生命周期追踪：KnowledgeTreePage `:119` 本地 `ref(null)` → `:123` watch → `:50` `:has-student` 绑定 → `:144` `studentId` computed → `:160/:226` `loadMastery(studentId.value)`。全链路引用本地 ref，而本地 ref 没有任何写入路径。对照 `useKnowledgeTree.js:13/:37-38/:81`——composable 内部自有 `selectedStudentId` ref 且 `loadMastery` 会更新 composable ref，但未导出。得出 F001：state 双真源。
4. **集成测试 stub 契约审查**：读 `KnowledgeTreePage.mount.test.js:167-168` ConceptMapPanel stub 的 props 列表，确认其未含 `colorMode/nodesWithMastery`；grep 全文件未见 `ColorModeToggle` 引用——集成层对 T10 接线零覆盖。得出 F002。

上述三项证据均为文件级可 grep 验证，非推测。

## 第一段：测试充分性（Test Adequacy）

发现 2 个 HIGH test-gap：测试只锁组件纯函数返回值，真实集成路径（页面挂载 + G6 watch）未被覆盖。现有单测全绿但无法在错误实现下红——不满足"测试真的会在错误实现下失败"的硬判定。

## 第二段：行为正确性（Behavioral Correctness）

发现 1 个 HIGH code-bug：页面级 `selectedStudentId` 状态分裂（本地 ref 与 composable 内部 ref 无同步），T10 新功能（掌握度着色 auto-switch）在集成层完全不可用。

## 第三段：未测试风险（Non-tested Risks）

- 明显"只把组件纯函数测绿"倾向——真实风险集中在页面集成和 G6 生命周期，新测试未覆盖
- 组件级 vitest 复跑 `ColorModeToggle / ConceptMapPanel / heatmapUtils` 64 条全绿，但不改变集成缺口

## Phase 0 — Contract Pack 验证

- INV-001 / INV-003 / INV-005 verification 映射可对上已落盘测试 ✓
- CE-001 mitigation 已实施，T10 不再只测 prop 传递 ✓
- INV-002 强校验仍停留在 plan 的 T14 Step 0，当前 revision 未实现（batch 3.c 范围，**不是 3.a 新鲜度偏离**）
- freshness 未见新增未列出 public API ✓
- test_debt TD-001/TD-003 对本批次可接受，TD-002 与本 diff 无关

---

<!-- anchor: finding-type -->

## 发现清单

### F001 — KnowledgeTreePage `selectedStudentId` 状态分裂导致 mastery 模式永远不可用

- ID: F001
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Status: verified
- Inv-conflict: none
- Before-behavior: 即使掌握度数据已通过 `useKnowledgeTree.loadMastery()` 加载，页面上的"掌握度"模式仍被视为"无学生"，保持 disabled；auto-switch 到 `mastery` 永远不触发
- After-behavior: 页面应从实际学生选择状态读取 `hasStudent` 和 auto-switch 条件；一旦学生选中并加载掌握度，`mastery` 模式必须可用
- Evidence: `frontend/src/pages/KnowledgeTreePage.vue:108` 解构未包含 `selectedStudentId`；`:119` 新建本地 `const selectedStudentId = ref(null)`；`:123` watch 本地 ref；`:50` ColorModeToggle `:has-student="!!selectedStudentId"` 绑定本地 ref。`frontend/src/components/knowledge-tree/useKnowledgeTree.js:13` composable 自有 `const selectedStudentId = ref(null)`，`:37-38` `loadMastery(studentId)` 内部更新的是 composable 的 ref，`:81` composable 返回值未导出 `selectedStudentId`
- Impact: T10 学生掌握度着色在页面集成层**完全不可用**。根因是页面自建本地 ref + composable 内部 ref 双真源，二者无同步
- Repair hypothesis: 方向——统一 `selectedStudentId` 单一真源（从 composable 导出 + 页面解构使用，或改由 composable 驱动）。禁止模式——继续维护两套 `selectedStudentId` ref。**requires independent fix design + Semantic Regression Gate**（涉及 composable 公共接口变更 + scope_guard `严禁修改 useKnowledgeTree.js` 约束）

**Claude 核查**：
- 数据流追踪：L119 本地 ref → L123 watch → L50 ColorModeToggle prop → L160/226 `studentId.value` 全链路依赖本地 ref 值，而本地 ref 无任何写入路径 → GPT 定位正确
- 溯源：`git show 2f7ddad^:frontend/src/pages/KnowledgeTreePage.vue` 显示 pre-existing 状态分裂（T10 之前 `selectedStudentId = ref(null)` 已存在）。T10 新增 ColorModeToggle + auto-switch watch **显现并放大**了这个 pre-existing bug
- Type 红旗复查：defect_fix 正确（非状态机/fallback/选择策略/阈值/时序变更，是 state 合并修复）

### F002 — 页面级测试 stub 吞掉 T10 新增 props，删除接线仍全绿

- ID: F002
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Status: verified
- Inv-conflict: none
- Before-behavior: 删除 `KnowledgeTreePage` 新增的 `colorMode`/`hasStudent`/`nodesWithMastery` 页面接线后，`KnowledgeTreePage.mount.test.js` / `KnowledgeTreePage.test.js` 现有测试仍全部通过
- After-behavior: 页面级测试应在真实挂载下覆盖 `selectedStudentId → ColorModeToggle → ConceptMapPanel` 链路；删除接线必须红
- Evidence: `frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js:167-168` ConceptMapPanel stub 的 props 列表只含 `moduleId/moduleName/nodes/edges/navigation/qualityIssues/canEdit`，未含 `colorMode/nodesWithMastery`，stub 会静默吞掉新 prop。测试未 import `ColorModeToggle`（grep 全文件 0 命中）。整个测试文件未断言 `selectedStudentId/hasStudent/colorMode`
- Impact: 集成层回归保护为零。T10 接线一旦退化（例如 KnowledgeTreePage 误删 `:color-mode="colorMode"` 或 `v-model="colorMode"`），无任何测试会 fail
- Repair hypothesis: 方向——增加真实页面级挂载断言，覆盖学生已选中时 `hasStudent=true`、自动切换到 `mastery`、传给 ConceptMapPanel 的 `colorMode` 值正确。禁止模式——继续用吞掉新 props 的 stub；只补 "render without error" 类弱断言。**requires independent fix design + Semantic Regression Gate**

**Claude 核查**：
- mount.test.js 的 stub 定义：`defineComponent({ props: ['moduleId', 'moduleName', 'nodes', 'edges', 'navigation', 'qualityIssues', 'canEdit'], emits: [...] })` — 确实缺 colorMode/nodesWithMastery
- ColorModeToggle.test.js 只测 `<ColorModeToggle>` 组件自身，没测页面挂载情况
- ConceptMapPanel.test.js 新 3 个 T10 断言只验证 props 传入后 `buildG6Data()` 返回值，没测 KnowledgeTreePage 层
- Type 红旗复查：defect_fix 正确（补测试覆盖既有意图，非新行为）

### F003 — ConceptMapPanel watch colorMode 的 setData/render/focus replay 路径无测试覆盖

- ID: F003
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Status: verified
- Inv-conflict: none
- Before-behavior: 删除 `ConceptMapPanel.vue` 里 `watch(() => [props.colorMode, props.nodesWithMastery], ...)` 的重绘逻辑（setData/render/focus replay），T10 新 3 个测试仍会通过
- After-behavior: 测试应直接验证：切换 colorMode 后 `graph.setData()`/`graph.render()` 被调用，焦点态被重放到新 graph
- Evidence: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue:439-454` watch colorMode 的 setData/render/`updateElementStates` 路径。`frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js:8-26` G6 mock 未实现 `setData`（mock 只有 render/destroy/on/setElementState），`:871-923` 新 3 个 T10 测试只断言 `wrapper.vm.buildG6Data()` 返回值。组件内 `try/catch` 吞掉 mock 抛出的 `setData is not a function`（`ConceptMapPanel.vue:444-446`）
- Impact: 真正的 G6 重绘路径 + Phase 2.5 焦点模式回归保护都没被锁住。watch 退化（例如被误删或 focusedNodeId 重放漏写）无任何测试会 fail
- Repair hypothesis: 方向——(a) G6 mock 补 `setData` spy；(b) 测试断言 `setProps({colorMode})` 后 graph.setData 被调用一次；(c) 测试 focus replay：click node → setProps colorMode → updateElementStates 被再次调用。禁止模式——继续只测 `buildG6Data()` 纯函数返回值。**requires independent fix design + Semantic Regression Gate**

**Claude 核查**：
- Mock 定义 `__tests__/knowledge-tree/ConceptMapPanel.test.js:9-25` 只 stub `render/destroy/on/setElementState`，**确实未定义 setData**
- 组件 watch 代码 `ConceptMapPanel.vue:444-446` 有 try/catch `console.warn`，`setData is not a function` 不会 throw 到测试
- 新 T10 断言都走 `wrapper.vm.buildG6Data()`（暴露的方法），没触发 watch
- Type 红旗复查：defect_fix 正确

---

<!-- anchor: pass-fail -->
## PASS/FAIL 判定

- F001 (HIGH code-bug, verified) 未修复 → **FAIL**
- F002 (HIGH test-gap, verified) 未修复 → **FAIL**
- F003 (HIGH test-gap, verified) 未修复 → **FAIL**

综合：**Round 1 FAIL**

## 行为变更审批记录

本轮**无 behavior_change finding**（3 个全部为 defect_fix，Claude 按红旗模式清单逐项复查确认）。无需用户按 intent-guard 分组批准。

## R2 处置建议（Executor → Planner 接力）

**F001 修复 scope 分析**：handoff-batch3a 明确 "严禁修改 ... useKnowledgeTree.js"。修复 F001 的任何选项都要触碰 scope 之外：
- 选项 A：`useKnowledgeTree.js` 返回值增 `selectedStudentId` export + KnowledgeTreePage 解构使用 → 违反 scope
- 选项 B：添加 student selector UI 让本地 ref 有写入路径 → 超出 3.a 范围
- 选项 C：accepted-risk（暂时接受 mastery 模式在无 student selector UI 场景下 disabled） + deferred 到 3.b/3.c → Planner 决策

**F002/F003 修复 scope 分析**：
- F003 修改 `ConceptMapPanel.test.js`（在 scope 内）+ G6 mock 定义扩展
- F002 修改 `KnowledgeTreePage.mount.test.js`（**超出** handoff 7 文件清单） + stub 契约升级

**建议流程**：
1. Planner 决策 F001 处置（修复 / accepted-risk / deferred）
2. 如决定 Round 2 修复，Planner 在 handoff-batch3a-r2 明确扩容后的 scope 白名单
3. Executor Round 2 在新 scope 内修复 + 重审

**Round 1 产物已落盘**：
- commits: `2f7ddad..ebfa83f`（代码）+ `8eacce4`（交接单）
- review-report 本文件
- gates.json code_review_batch3a=fail 待写入
