[edu-cloud] GPT Reviewer | 2026-04-10 22:34:50

## 审查报告: Phase 2.5 Batch 1 Task 1-3 (Round 1)

**结论**: FAIL

**审查对象**:
- commit: `b909ccf feat(knowledge-tree): Phase 2.5 Batch 1 — 焦点淡化 + 徽标 Tooltip (T1-T3)`
- 改动文件:
  - `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（+176 / −10）
  - `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（+416）
  - `CLAUDE.md`（+1 / −1）
- handoff: `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-handoff-batch1.md`
- plan: `docs/plans/2026-04-10-teacher-workbench-phase2.5-plan.md`

**GPT 原始输出**: `docs/plans/.codex-raw-code_review-20260410-222742.log`
**SHA256**: `5bc909d9abf962006f513af0d4d9785088d2dbcae6ea2a40c5ce707d1e754706`

**GPT 环境限制**: 本次审查 codex exec shell 工具启动失败，GPT 无法直接运行 `git log` / `git diff`。改为通过 `.git/logs/refs/heads/master` 确认审查对象（`39301fc → b909ccf`），并读取 handoff 声明的改动文件全文。`b909ccf` 之后的 reflog 记录（d41ba1e/c3bc647）均是 handoff/review-handoff 文档提交，不影响代码审查结论。

---

### 第一段：测试充分性（Test Adequacy）

Phase 2.5 不是"完全无效测试"——现有 19 个测试能抓住一部分回归（CE-004/CE-005/CE-007/CE-008/F006 五项反证已验证有效）。但 GPT 指出三个具体的 test-gap：

- **F001 HIGH** — INV-009 真实入口链路未锁住：所有 Tooltip 测试都手写 `items=[{data:{badgeText:'→M2×1'}}]` 喂给 plugin.enable/getContent，从未验证 G6 真实 graph data.nodes 的 `badgeText` 字段是否经 `buildG6Data()` 正确注入。如果 `buildG6Data()` 未来丢掉徽标写入逻辑，现有测试仍全绿。
- **F002 MED** — INV-010 同模块内 peer 顺序未锁住：删除 `renderPeersHtml` 里 `sortedList.sort((a,b) => (a.name||'').localeCompare(b.name||''))` 后，INV-010 的 determinism 测试只断言"模块间顺序"和"内容包含"，未断言同模块 peer 的相对顺序——测试仍会通过。
- **F003 MED** — INV-006/INV-007 孤立节点边界未覆盖：plan 边界条件段明确列出"焦点无任何边（孤立节点）/ props.edges 为空数组"场景，但 INV-006 describe 实际测试块只覆盖 null、多邻居、单边、dangling、bridge 五个场景；孤立节点没有经 node:click 真实入口 + stateMap 完整断言。

### 第二段：行为正确性（Behavioral Correctness）

#### 变更理解（GPT 复述）

本批次是 Phase 2 延后项清理，纯前端单点增量：在 `ConceptMapPanel.vue` 内新增 `buildVisibleEdgeList()` 共享 helper（与 `buildG6Data` 共用过滤索引，防止 dangling edge 导致 edge-id 偏移）、`relatedNodeIds`/`relatedEdgeIds` 两个 computed（1 跳邻居集合）、`updateElementStates()` 函数（通过 `graph.setElementState(stateMap, true)` 批量驱动 G6 node/edge state），并在 G6 Graph config 中追加 `node.state.faded` / `edge.state.dimmed/emphasized` 样式规范、`plugins: [{type:'tooltip', trigger:'hover', enable, getContent}]` 配置，`createGraph()` 末尾追加 `if (focusedNodeId.value) nextTick(updateElementStates)` 焦点重放；`watch(focusedNodeId, ...)` 监听组件内部 ref 变化；新增 `renderPeersHtml(peers)` 纯函数生成 Tooltip HTML 内容（null/{}/空列表返回 ''、模块字母序 + 同模块 name 字母序 + HTML escape 防注入）；`defineExpose` 增量扩展；G6 mock 追加 `setElementState = vi.fn().mockResolvedValue(undefined)` spy；新增 19 个测试覆盖 INV-006/INV-007/INV-008/INV-009/INV-010/CE-004/CE-005/CE-006/CE-007/CE-008。意图是实现 Phase 2 test_debt 中的两项：焦点模式视觉淡化 + 跨模块徽标悬停展开 peer 列表。无后端改动、无新依赖、无架构变更；桥接/对比边 deferred 到 Phase 3。

#### Executor 自审抽检

从审查交接单的"逐 Task 自审表"和"预审自检"中随机抽检：
- T1 自审"buildVisibleEdgeList helper 被 buildG6Data 和 relatedEdgeIds 两处共用"——GPT 通过读 `ConceptMapPanel.vue:213`（buildG6Data 调 helper）和 `:191`（relatedEdgeIds 调 helper）确认属实。
- T2 自审"F004 graph rebuild 测试通过真实 node:click 入口驱动 + 新 graph 实例 setElementState 断言重放"——GPT 通过读 `:551` 行测试断言确认属实（`newGraph.setElementState.mock.calls.length > 0`）。
- 5 项反证验证（CE-004/CE-005/CE-007/CE-008/F006）——GPT 未独立执行反证命令（shell 不可用），但相信 Executor 提供的"破坏点 + 精确 fail 行号"记录的可信度。

#### 对抗性审查（边界/异常/假阴性）

GPT 采用三轴对抗性审查：

**边界输入构造**：
- 孤立节点（`edges=[]` 或 edges 完全不触及该节点）——plan 边界条件段已声明，但实测 INV-006/INV-007 测试块未通过 node:click 真实入口覆盖此场景 → **F003 test-gap**
- 同模块内 ≥2 peer 且输入已乱序（如 `[{name:'Z'},{name:'A'}]`）——INV-010 determinism 测试只验证"模块间"顺序，未构造同模块内乱序输入 → **F002 test-gap**

**异常路径追踪**：
- 从 `external_hard_refs` 到 `badgeText` 再到 Tooltip 的真实链路——从 `buildG6Data` 的 badgeText 字符串拼接到 plugin.getContent 读 `crossModulePeers.value` 之间存在多个节点，但现有测试完全用手写 `items=[{data:{badgeText:...}}]` 伪造，绕过 `buildG6Data` 实际行为 → **F001 test-gap**
- `updateElementStates` 中 `graph===null` 早退 / try-catch 包裹的 G6 异常路径——GPT 确认源代码有保护但未在测试中构造异常场景，属残余风险不阻断

**假阴性检测**：
- INV-009 wiring 测试 (`ConceptMapPanel.test.js:646`) 只断言 `tooltipPlugin.key === 'badge-tooltip'` + `tooltipPlugin.trigger === 'hover'`；修改 `buildG6Data()` 让所有节点的 `badgeText=''` 后，plugin wiring 仍存在 → 现有测试全部 PASS，但 CI 不会捕获"徽标节点链路断裂"这一真实故障模式。
- INV-010 determinism 测试 (`ConceptMapPanel.test.js:593`) 只对比 `m2Index < m3Index`；删除 `sortedList.sort(...)` 后 M2 下的 `[Apple, Mango]` 会保留输入顺序，如果输入刚好按字母序给出，测试仍会 PASS——属于"测试只保护给定的输入对，不保护排序行为"的假阴性。

GPT 确认静态代码本身没有更高优先级的直接实现错误：
- 调用面 `KnowledgeTreePage.vue:47` 未变化，向后兼容
- `layoutEngine.js:14` 会为输入节点分配坐标，helper 过滤语义无额外漂移风险
- Tooltip 回调形状（async getContent + Promise<HTMLElement|string>）与 G6 官方文档一致（https://g6.antv.antgroup.com/en/manual/plugin/tooltip）

### 第三段：未测试风险（Non-tested Risks）

真实浏览器中的 G6 渲染时序、Tooltip DOM 定位/z-index、`faded/dimmed/emphasized` 的最终视觉效果仍未被自动化测试覆盖。handoff 已明确交给手工验收（design §8 三条路径），GPT 记为残余风险，不作为本次 FAIL 主因。

---

### 发现清单

#### F001

- **Severity**: HIGH
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: 即使 `buildG6Data()` 不再把徽标节点的 `badgeText` 正确写进 G6 数据，现有 Tooltip 测试仍会全部通过。
- **After-behavior**: 一旦真实链路 `external_hard_refs → badgeText → tooltip.enable/getContent` 断裂，测试必须失败。
- **Inv-conflict**: direct (INV-009)
- **Evidence**:
  - `ConceptMapPanel.vue:213`（buildG6Data 生成 badgeText）
  - `ConceptMapPanel.vue:306`（plugins 配置）
  - `ConceptMapPanel.test.js:646`（INV-009 wiring 测试，只断言 plugin 存在）
  - `ConceptMapPanel.test.js:667`（enable 测试，用手写 items）
  - `ConceptMapPanel.test.js:691`（getContent 测试，用手写 items）
- **Impact**: 浏览器里最核心的 D4 行为可以失效，但 CI 仍然全绿；当前测试只验证"插件对象存在"和"手写 items 可工作"，没有验证真实图数据会触发 Tooltip。
- **Repair direction**（advisory，无执行权）:
  可能的修复方向是补一条入口级测试，直接约束真实 graph data 上的 `badgeText` 与 Tooltip 触发链路。
  **禁止的修复模式**：继续用手写 `items` 伪造 `badgeText`、只断言 plugin wiring、或通过改 invariant 文案来回避缺口。

#### F002

- **Severity**: MED
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: 删除 `renderPeersHtml()` 里"同模块内按 `name` 排序"的逻辑后，现有 INV-010 测试仍会通过。
- **After-behavior**: 同模块内顺序一旦失去确定性，测试必须失败。
- **Inv-conflict**: direct (INV-010)
- **Evidence**:
  - `ConceptMapPanel.vue:387`（sortedList.sort 同模块排序）
  - `ConceptMapPanel.test.js:579`（INV-010 content 测试，只用 `toContain`）
  - `ConceptMapPanel.test.js:593`（INV-010 determinism 测试，只断言 M2 在 M3 之前，未验证同模块内部顺序）
- **Impact**: Contract Pack 把 INV-010 标成已覆盖，但当前只验证了"模块顺序"和"内容包含"，没有保护模块内 peer 顺序，Tooltip 输出会出现非确定性回归。
- **Repair direction**（advisory）:
  可能的修复方向是补一条直接约束单模块内部相对顺序的断言。
  **禁止的修复模式**：复制实现里的排序逻辑到测试、只做 `toContain` 弱断言、或下调 invariant 要求。

#### F003

- **Severity**: MED
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: 如果"孤立节点 / `edges=[]`"场景下的焦点逻辑退化，当前 Phase 2.5 测试仍可能通过。
- **After-behavior**: 对无 prerequisite 邻居的节点，`relatedNodeIds` 和 `setElementState` 的结果一旦错误，测试必须失败。
- **Inv-conflict**: direct (INV-006, INV-007)
- **Evidence**:
  - `ConceptMapPanel.vue:175`（relatedNodeIds computed）
  - `ConceptMapPanel.test.js:352`（INV-006 describe 起点）
  - `ConceptMapPanel.test.js:399`（CE-004 guard 多邻居测试）
  - `ConceptMapPanel.test.js:442`（F003 dangling edge 测试）
  - `docs/plans/2026-04-10-teacher-workbench-phase2.5-plan.md`（边界条件段）
- **Impact**: plan 明确列了"焦点无任何边 / `props.edges` 为空数组"边界，但测试块只覆盖了 null、多邻居、单边、dangling、bridge；稀疏图上的真实用户路径没有被锁住。
- **Repair direction**（advisory）:
  可能的修复方向是补一条通过真实 `node:click` 入口驱动的孤立节点测试，同时校验 `relatedNodeIds` 与 `stateMap`。
  **禁止的修复模式**：直接改内部 ref、只断言 `size > 0`、或只测 computed 不测 `setElementState`。

---

### PASS/FAIL 判定

按 `~/.claude/rules-t3/review-templates.md` PASS/FAIL 规则：
- F001 (test-gap HIGH) → 阻断 PASS
- F002 (test-gap MED) → 阻断 PASS
- F003 (test-gap MED) → 阻断 PASS

**结论**: FAIL（3 个 test-gap finding 均 HIGH/MED，必须修复后重审）。

---

### 行为变更审批记录

三个 finding 全部 `type=defect_fix`（补测试以锁住现有已实现行为，不引入新状态机/fallback/选择策略/阈值/生命周期/评估节奏改变）。无 `behavior_change` finding，按"分组呈现规则"缺陷修复组可批量处置。

**红旗模式自动检测**：
- F001 修复 = 补一条真实入口测试 → 不触发状态机/fallback/策略等红旗模式 → defect_fix ✓
- F002 修复 = 补一条顺序断言 → defect_fix ✓
- F003 修复 = 补一条孤立节点场景测试 → defect_fix ✓

三条均可在下一轮 R2 修复循环中由 Executor 直接处置，无需用户 behavior_change 单独批准。

---

### Round 1 → Round 2 修复计划

Executor 将在同一文件 `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` 中追加 3 条测试（不改实现代码）：

1. **F001 修复**（INV-009 入口级链路）：
   - 挂载带 `external_hard_refs.out` 的真实节点
   - 通过 `graphCtorCalls[last].data.nodes.find(n => n.id === 'A').data.badgeText` 取**真实** badgeText
   - 把真实 node data 对象（不是手写 items）传入 `plugin.enable(null, [{data: realNodeData}])` 和 `plugin.getContent(null, [{id, data: realNodeData}])`
   - 断言 enable 返回 true 且 getContent 返回包含 peer 名称的 HTML
   - **反证**：删除 `buildG6Data()` 中 `badgeText: Object.entries(badges)...` 行后，本测试必须 fail

2. **F002 修复**（INV-010 同模块内 peer 顺序）：
   - 构造 `{ M2: [{name: 'Zebra'}, {name: 'Apple'}, {name: 'Mango'}] }` 乱序输入
   - 断言输出 HTML 中 `Apple` 的 indexOf 小于 `Mango` 的 indexOf 小于 `Zebra` 的 indexOf
   - 不使用 `toContain` 弱断言，使用严格 index 比较
   - **反证**：删除 `sortedList.sort(...)` 行后，本测试必须 fail

3. **F003 修复**（INV-006/INV-007 孤立节点边界）：
   - 构造一个孤立节点（nodes 包含 'ISOLATED'，edges 完全不触及它）
   - 通过 `graph.handlers['node:click']({target: {id: 'ISOLATED'}})` 真实入口驱动 focus
   - 断言 `wrapper.vm.relatedNodeIds.size === 1`，`has('ISOLATED') === true`
   - 断言 `graph.setElementState` 最后一次调用的 stateMap：`stateMap.ISOLATED === []`，所有其他节点 `=== ['faded']`
   - **反证**：将 `relatedNodeIds` 初始化改为 `new Set()` 不含 focus 自身后，本测试必须 fail
