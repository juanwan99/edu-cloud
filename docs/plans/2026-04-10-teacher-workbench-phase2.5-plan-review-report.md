[edu-cloud] GPT Reviewer | 2026-04-10 21:45:00

<!-- anchor: finding-classification -->
## 审查报告: Phase 2.5 Gate 1 Plan Review — Round 2

**结论: PASS**（Round 2，覆盖 R1 修复 commit a8e4495）

**R1 审查报告**: `docs/plans/.codex-plan-review-phase2.5-raw.log`（FAIL, 7 finding）
**R1 修复 commit**: `a8e4495 fix(plan): Phase 2.5 Gate 1 R1 修复 7 个 finding`
**R2 原始输出**: `docs/plans/.codex-raw-plan_review-phase2.5-r2-20260410T214500.log`（sha256: `bfc1b66a4ffdcbb6e923c55be04821365c15a6776e642d27c9faa98fff1e7d33`）
**送审范围**: Phase 2.5 plan + design 全量审查（commit a8e4495..HEAD）

### 变更理解

Phase 2.5 是 Phase 2 已实现完成（commits 7a5ecfb..549e298）的**纯增量跟进**，目标是清理 Phase 2 Contract Pack 记录的 2 条 test_debt：

1. **焦点模式节点/边淡化**：利用 G6 v5.1 `Graph.setElementState` + node/edge state spec 声明式配置，在 `focusedNodeId` 进入/切换/退出时，将非 1 跳邻居节点/无关边置为 `faded`/`dimmed`，相关边置为 `emphasized`；退出焦点时批量清空 state 防止泄漏。
2. **跨模块徽标悬停展开 peer 列表**：接入 G6 内置 `Tooltip` plugin（`trigger='hover'` + `enable` 谓词仅在有 `badgeText` 的节点触发 + `async getContent` 返回 HTML 字符串），数据源复用 Batch 2 已暴露的 `crossModulePeers` ComputedRef。

**范围边界**：
- 所有改动集中在 `ConceptMapPanel.vue` 单一组件（新增 `buildVisibleEdgeList` helper + `relatedNodeIds` / `relatedEdgeIds` computed + `updateElementStates` + `renderPeersHtml` 纯函数 + node/edge state spec + Tooltip plugin 配置 + `createGraph` 末尾 focus replay + watch 内部 `focusedNodeId` ref），以及 `ConceptMapPanel.test.js` 扩展 G6 mock 的 `setElementState` spy + 追加 8 个测试。
- **不改** Phase 2 任何既有行为：layoutEngine 调用 / G6 preset 布局 / 现有 crossModuleBadges 渲染 / node:click 事件驱动 / destroyGraph 生命周期 / module watch 全部保持原样。
- **不引入**新依赖，不改动后端。
- **桥接/对比边**明确延后到 Phase 3（数据模型缺少 bridge/contrast edge type）。
- **节点淡化的 1 跳邻居**定义：通过 `prerequisite_hard` ∪ `prerequisite_soft` 边直连的节点（双向，焦点自身算相关）；跨模块 `external_hard_refs` 不纳入 1 跳（通过徽标单独表达）。

**意图一致性**：Phase 2 当时延后这两项的理由是"G6 API 不成熟"，Phase 2.5 开工前的 spike（design §1）已通过读 `@antv/g6/esm/runtime/graph.d.ts:1173` 和 `@antv/g6/esm/plugins/tooltip.d.ts:1-134` 证明该理由不再成立，这是本 Phase 立项的技术前提。

### 三段审查

#### 第一段：测试充分性

R1 的核心缺口已补齐：
- **F005 修复**: Task 2 通过真实 `graph.handlers['node:click']` 入口驱动焦点，直接断言 `setElementState` spy 的最后一次调用参数（非逻辑镜像）
- **F006 修复**: Task 3 改为读取 `graphCtorCalls[last].plugins` 上的真实 Tooltip 配置，`await` 真实 `getContent` 返回值
- **CE-007 / CE-008 新增**: 边 id 对齐 + graph rebuild 回放的反例测试

#### 第二段：行为正确性

Plan 已回到与 Phase 2 当前组件一致的内部焦点模型：
- ConceptMapPanel.vue:87 内部 `ref` → plan 所有计算读 `focusedNodeId.value`
- ConceptMapPanel.vue:289 defineExpose `{focusedNodeId, clearFocus}` → plan 3 处 defineExpose 全部增量扩展，保留 Phase 2 字段
- createGraph 末尾补 focus replay（R1 F004 硬约束）

#### 第三段：未测试风险

无阻塞性 code-bug / test-gap。额外抽查对齐点：
- `setElementState` / Tooltip 类型签名匹配（graph.d.ts:1173 / tooltip.d.ts:22）
- `badge-tooltip` 插件 key 无冲突
- Mock 扩展写在 Graph constructor 内，对所有新实例生效
- 现有测试文件顶部的 `graphCtorCalls` / `graphInstances` 可被 Phase 2.5 追加测试复用

### 对抗性审查（R2 独立验证）

GPT 在 R2 过程中不依赖 R1 修复声明，而是独立构造反证和抽检：

**边界输入构造**：
- **Dangling edge 对齐**：构造 `{source:'A', target:'GHOST'}` 的边（endpoint 不在 nodes 集合）验证 `buildVisibleEdgeList` 是否正确过滤并保持 visibleIndex 连续；读 Task 1 测试 6（`F003 guard: buildVisibleEdgeList skips edges whose endpoint is filtered out`）确认存在该断言。如果 F003 未真正修复，dangling 边会让 `edge-1` 原本应该命中 B→C 变成命中 GHOST，断言会 fail。
- **双向边覆盖**：构造 `A→B + D→B` 两条前置边 focus='B'，验证 CE-004 护栏（`r.has('D')` 必须 true）覆盖 `target===focus` 反向分支。

**异常路径追踪**：
- **退出焦点状态泄漏**：假设 `updateElementStates` 的 `!focusedNodeId.value` 清空分支被删除——Task 2 的"INV-008 + CE-005: clearFocus triggers graph.setElementState({}, true)"测试读 `graph.setElementState.mock.calls` 最后一次的 `args[0]`，若不等于 `{}` 则 fail。该断言不经过任何 computed，直接验证 spy 行为。
- **createGraph 重建焦点残留**：假设 createGraph 末尾不重放 focus state——Task 2 的"F004 graph rebuild"测试构造 `setProps({nodes: newNodes})` 触发 destroy→create 循环，然后断言**新** graph 实例（非旧实例）的 spy 被额外调用，且 state map 反映当前焦点 B 关系（含新节点 G 为 faded）。

**假阴性检测**：
- **Tooltip plugin wiring 假在**：如果实现根本没注册 plugin、trigger 写错、key 写错、getContent 没接 crossModulePeers，F006 修复前的测试都会绿；R2 要求读 `graphCtorCalls[last].plugins` 数组存在性断言 + 真实调用 `plugin.enable`/`plugin.getContent`，打破假阴性。
- **状态名冲突**：G6 保留态包括 `selected` / `active` / `disabled`；Phase 2.5 使用 `faded` / `dimmed` / `emphasized`——GPT 读 design §4 确认无冲突，且未与 Phase 2 既有 state 重名（Phase 2 未使用 state 机制）。
- **getContent 异步签名**：`tooltip.d.ts:28` 声明 `getContent?: (event, items) => Promise<HTMLElement | string>`——若用同步返回 string，G6 内部可能 auto-wrap，但为稳妥 plan 改为 `async (event, items) => ...` 显式返回 Promise；测试用 `await` 捕获。

**Mock 层对齐抽检**：
- R2 读 `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js:7-27` 确认 Phase 2 现有 mock 结构确实导出 `graphCtorCalls` / `graphInstances`，以及 `on(event, cb)` 会 push 到 `this.handlers[event]`——这些都是 Phase 2.5 测试计划的依赖前提，GPT 独立验证其真实可用。
- `setElementState` spy 只需在 Graph constructor 内 `this.setElementState = vi.fn().mockResolvedValue(undefined)` 一行，无需破坏既有 mock 结构，每个新实例都有独立 spy，切模块后可区分新旧 graph 的调用。

### 发现清单（R1 finding 处置状态）

| ID | Severity | Category | Type | R2 Status | 处置 |
|----|----------|----------|------|-----------|------|
| F001 | HIGH | code-bug | behavior_change | **resolved-correct** | 保持 focusedNodeId 为组件内部 ref（Phase 2 现状） |
| F002 | HIGH | code-bug | behavior_change | **resolved-correct** | defineExpose 3 处全部增量扩展，保留 focusedNodeId/clearFocus |
| F003 | MEDIUM | code-bug | defect_fix | **resolved-correct** | 抽 buildVisibleEdgeList helper 供 buildG6Data 和 relatedEdgeIds 共用 + CE-007 |
| F004 | MEDIUM | code-bug | defect_fix | **resolved-correct** | createGraph 末尾补 focus replay + INV-011 + CE-008 |
| F005 | HIGH | test-gap | defect_fix | **resolved-correct** | G6 mock 扩展 setElementState spy + 真实 node:click 驱动 |
| F006 | HIGH | test-gap | defect_fix | **resolved-correct** | 测试读 graphCtorCalls[last].plugins + 直接调 plugin.enable/getContent + async 适配 |
| F007 | MEDIUM | design-concern | defect_fix | **resolved-correct** | 桥接/对比边统一为 deferred → Phase 3（design/plan 语义一致） |

### R2 新发现 finding（suggestion 类，不阻塞 PASS）

#### F008

- **Severity**: MEDIUM
- **Category**: design-concern
- **Type**: defect_fix
- **Status**: resolved-correct（本次 R2 已立即修复）
- **Before-behavior**: design.md §3 `relatedNodeIds` / `relatedEdgeIds` 代码示例仍保留 R1 前的 `props.focusedNodeId` / `props.edges.forEach((e, i))` 原始索引写法，与 plan 已修的最终版本出现文档漂移
- **After-behavior**: design §3 两个代码块更新为 plan 最终口径（`focusedNodeId.value` 内部 ref + `buildVisibleEdgeList()` helper）
- **Evidence**:
  - `docs/plans/2026-04-10-teacher-workbench-phase2.5-design.md:145`（旧 relatedNodeIds 示例）
  - `docs/plans/2026-04-10-teacher-workbench-phase2.5-design.md:166`（旧 relatedEdgeIds 示例）
  - `docs/plans/2026-04-10-teacher-workbench-phase2.5-plan.md:91`（plan 最终版本）
- **Impact**: 不阻塞 PASS，但 Executor 如果参考 design 而非 plan，会把 F001/F003 老问题写回去
- **Repair**: R2 已立即修复 design §3 两处代码块

#### F009

- **Severity**: LOW
- **Category**: suggestion
- **Type**: defect_fix
- **Status**: resolved-correct（本次 R2 已立即修复）
- **Before-behavior**: plan 对全量测试总数预期自相矛盾——L981 写 `178 tests`，L1017 写 `175 tests`
- **After-behavior**: 统一为 `17 files / 178 tests PASS`（Phase 2 的 160 + Phase 2.5 的 18）
- **Evidence**: `docs/plans/2026-04-10-teacher-workbench-phase2.5-plan.md:981, :1017`
- **Impact**: 不影响设计正确性，但会给 Executor 自检制造噪音
- **Repair**: R2 已立即修复 L1017

<!-- anchor: pass-fail -->
### PASS/FAIL 判定

- F001-F007 (R1) → 全部 resolved-correct
- F008/F009 (R2 新发现) → 全部 resolved-correct（R2 立即修复）
- 无阻塞性 code-bug / test-gap / behavior_change 未处置

**判定**: **PASS**（R2 resolved F001-F007，R2 新增 F008/F009 已即时处置）

### Finding 分组呈现

<!-- anchor: finding-type -->
**缺陷修复组 (defect_fix)**: F003/F004/F005/F006/F007/F008/F009 — 全部 resolved-correct
**行为变更组 (behavior_change)**: F001/F002 — 均为"拒绝 After-behavior（接口改造）、保持 Before-behavior（内部 ref）"方向处置，已在 R1 修复中落实

### 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| F001 | plan 建议把 focusedNodeId 从内部 ref 改为 props.focusedNodeId | **rejected** | "批准 F001" — 用户明确同意拒绝 After-behavior，保持 Before-behavior（Phase 2 内部 ref 模式） |
| F002 | plan 建议 defineExpose 删除 focusedNodeId/clearFocus | **rejected** | "批准 F002" — 用户明确同意拒绝 After-behavior，保留 Phase 2 已暴露字段 |

### 下一步

- Gate 1 receipt 写入 `docs/plans/2026-04-10-teacher-workbench-phase2.5-gates.json`（status=pass, report_path 指向本报告）
- 创建 `teacher-workbench-phase2.5-state.json` task sidecar（本已就位，需同步更新 updated_at）
- 写 Executor handoff card 派发新会话执行 Batch 1（Tasks 1-3）
