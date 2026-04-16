# 知识图谱教师工作台 Phase 2.5 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理 Phase 2 Contract Pack 中记录的 2 条 test_debt——焦点模式节点淡化（设计 §2 D2）+ 跨模块徽标悬停展开 peer 列表（设计 §2 D4），落地到 ConceptMapPanel.vue 单一改动点。

**Architecture:** 纯前端增量。`relatedNodeIds`/`relatedEdgeIds` computed + `graph.setElementState()` 状态驱动 node/edge style 切换 + G6 内置 `Tooltip` plugin。无新依赖、无后端改动、无架构变更。

**Tech Stack:** Vue 3 Composition API + @antv/g6 ^5.1.0（setElementState + Tooltip plugin）+ Vitest + @vue/test-utils

**设计文档:** `docs/plans/2026-04-10-teacher-workbench-phase2.5-design.md`
**前置 Phase 2（已实现完成）:** `docs/plans/2026-04-10-teacher-workbench-design.md`（commits 7a5ecfb..549e298）

---

## 文件结构

### 新增文件

无（Phase 2.5 全部增量落在 Phase 2 既有文件内）。

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` | +relatedNodeIds / relatedEdgeIds computed + updateElementStates() + watch focusedNodeId + node/edge state spec + Tooltip plugin 配置 + renderPeersHtml 纯函数 |
| `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` | +INV-006..INV-010 + CE-004..CE-006 测试（≥8 新测试） |

### 删除文件

无。

---

## Batch 1: 焦点淡化 + 徽标悬停（Tasks 1-3，单 Batch 完成）

### Task 1: relatedNodeIds / relatedEdgeIds computed + 纯函数测试

**Files:**
- Modify: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（新增 2 个 computed + defineExpose 扩展）
- Modify: `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（新增 INV-006 测试 describe block）

> **R1 修复（F001/F002/F003）**：focusedNodeId 是**组件内部 ref**（Phase 2 现状，见 `ConceptMapPanel.vue:87`），不是 prop。测试入口用 `graph.handlers['node:click']` 事件驱动（Phase 2 mock 现成结构，见 `ConceptMapPanel.test.js:7-27`）。defineExpose **增量扩展**，保留 Phase 2 已暴露的 `focusedNodeId` 和 `clearFocus`。边 id 规则使用共享 helper `buildVisibleEdgeList()` 与 `buildG6Data` 对齐过滤后索引。

**测试契约:**

1. focusedNodeId=null 时 relatedNodeIds / relatedEdgeIds 均为空 Set
   - 入口: `mount(ConceptMapPanel, { props: baseProps })` 初始化后 `wrapper.vm.focusedNodeId` 应为 null（Phase 2 既定初值）；读 `wrapper.vm.relatedNodeIds.value` 和 `wrapper.vm.relatedEdgeIds.value`（注意是 ComputedRef，测试 .value）
   - 反例: 错误实现返回 `new Set([null])` 或 `undefined`——本测试断言 `size === 0`
   - 边界: focusedNodeId 初始 null / 被 clearFocus() 置 null / 从 'A' 切回 null
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-006"`

2. 通过 `graph.handlers['node:click']` 事件驱动 focus 到 'B'，relatedNodeIds 包含焦点自身 + 前置 + 后继（hard 和 soft 都算）
   - 入口: `graphInstances[last].handlers['node:click']({ target: { id: 'B' } })` → 触发 Phase 2 既有 handleNodeClick → `focusedNodeId.value = 'B'` → computed 更新 → `await nextTick()` → 读 `wrapper.vm.relatedNodeIds.value`
   - 反例: 错误实现只处理 `e.source===focus`（漏反向）——本测试断言 `has('A')` 和 `has('D')` 均为 true（CE-004）
   - 边界: 焦点无任何边（孤立节点）→ 仅含自身；焦点有 1 前置 1 后继 → 3 个元素；焦点处于链中间 多前置多后继
   - 回归: N/A
   - 命令: 同上

3. relatedEdgeIds 使用 buildVisibleEdgeList helper 的 `edge-${visibleIndex}` 格式，与 buildG6Data 对齐
   - 入口: 通过 handlers['node:click'] 驱动 focus='B'，读 `wrapper.vm.relatedEdgeIds.value`
   - 反例 1: 错误实现按原始 `props.edges` 索引生成 id——当 nodes 集合中缺一个节点时，`buildG6Data` 过滤后 id 会偏移，setElementState 打不中实际 element（F003 根因）
   - 反例 2: 错误实现用 `${source}-${target}` 替代索引——同源同目标多条平行边会碰撞
   - 边界: 构造一个被过滤掉的边（source 不在 nodes 集合）验证 id 规则对齐
   - 回归: N/A
   - 命令: 同上

- [ ] **Step 1: 新增 buildVisibleEdgeList helper + 两个 computed + 扩展 defineExpose**

在 `ConceptMapPanel.vue` 的 `<script setup>` 内、`crossModulePeers` computed **之后**、`buildG6Data` 之前插入：

```javascript
// Phase 2.5 R1: 共享的可见边列表生成器
// 与 buildG6Data() 共用同一过滤规则：只保留 source 和 target 都在 props.nodes 集合内的边
// 返回 [{originalEdge, visibleIndex, visibleId}]，visibleId = `edge-${visibleIndex}`
// 这样 relatedEdgeIds / updateElementStates / buildG6Data 三处都用同一个 id 映射，不存在偏移
function buildVisibleEdgeList() {
  const visibleNodeIds = new Set(props.nodes.map(n => n.id))
  const out = []
  let idx = 0
  for (const e of props.edges) {
    if (!visibleNodeIds.has(e.source) || !visibleNodeIds.has(e.target)) continue
    out.push({ originalEdge: e, visibleIndex: idx, visibleId: `edge-${idx}` })
    idx++
  }
  return out
}

// Phase 2.5 INV-006: 1 跳邻居集合（焦点模式视觉淡化的数据源）
// 数据源: 组件内部的 focusedNodeId ref（Phase 2 既定），不是 props.focusedNodeId
// 反例护栏: CE-004——必须同时处理 source === focus 和 target === focus 两个方向
const relatedNodeIds = computed(() => {
  const focus = focusedNodeId.value
  if (!focus) return new Set()
  const related = new Set([focus])
  for (const e of props.edges) {
    if (e.type !== 'prerequisite_hard' && e.type !== 'prerequisite_soft') continue
    if (e.source === focus) related.add(e.target)
    if (e.target === focus) related.add(e.source)
  }
  return related
})

// Phase 2.5 R1 F003 修复: relatedEdgeIds 使用 buildVisibleEdgeList 的 visibleId，与 buildG6Data 严格对齐
const relatedEdgeIds = computed(() => {
  const focus = focusedNodeId.value
  if (!focus) return new Set()
  const ids = new Set()
  for (const { originalEdge: e, visibleId } of buildVisibleEdgeList()) {
    if (e.type !== 'prerequisite_hard' && e.type !== 'prerequisite_soft') continue
    if (e.source === focus || e.target === focus) {
      ids.add(visibleId)
    }
  }
  return ids
})
```

同时**修改 `buildG6Data()` 改用 helper**（避免两套过滤逻辑漂移）。找到现有的边过滤段落（`ConceptMapPanel.vue:~178`）：

```javascript
// 原：
const visibleIds = new Set(g6Nodes.map(n => n.id))
const g6Edges = props.edges
  .filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
  .map((e, i) => ({
    id: `edge-${i}`,
    source: e.source,
    target: e.target,
    data: { type: e.type },
  }))

// 改为：
const g6Edges = buildVisibleEdgeList().map(({ originalEdge: e, visibleId }) => ({
  id: visibleId,
  source: e.source,
  target: e.target,
  data: { type: e.type },
}))
```

找到文件末尾已有的 `defineExpose({ crossModuleBadges, crossModulePeers, focusedNodeId, clearFocus })`（Phase 2 Batch 2），**增量扩展**为：

```javascript
// R1 修复 F002: defineExpose 只能增量扩展，必须保留 Phase 2 已暴露的 focusedNodeId 和 clearFocus
defineExpose({
  crossModuleBadges,
  crossModulePeers,
  focusedNodeId,  // Phase 2 保留
  clearFocus,     // Phase 2 保留
  relatedNodeIds, // Phase 2.5 新增
  relatedEdgeIds, // Phase 2.5 新增
})
```

- [ ] **Step 2: 写失败测试**

在 `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` 末尾、最后一个 `})` 之前追加 describe block：

```javascript
// R1 修复: focus 驱动用 Phase 2 既有的 graph.handlers['node:click'] 入口，不用 setProps；
// relatedNodeIds/relatedEdgeIds 是 ComputedRef，访问用 .value
describe('Phase 2.5 INV-006: relatedNodeIds / relatedEdgeIds computed', () => {
  const makeNodes = () => [
    { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1' },
    { id: 'B', name: 'B', big_concept_id: 'BC1', module: 'M1' },
    { id: 'C', name: 'C', big_concept_id: 'BC1', module: 'M1' },
    { id: 'D', name: 'D', big_concept_id: 'BC2', module: 'M1' },
    { id: 'E', name: 'E', big_concept_id: 'BC2', module: 'M1' },
    { id: 'F', name: 'F', big_concept_id: 'BC2', module: 'M1' },
  ]
  const makeEdges = () => [
    { source: 'A', target: 'B', type: 'prerequisite_hard' },  // visible edge-0
    { source: 'B', target: 'C', type: 'prerequisite_soft' },  // visible edge-1
    { source: 'D', target: 'B', type: 'prerequisite_hard' },  // visible edge-2
    { source: 'E', target: 'F', type: 'prerequisite_soft' },  // visible edge-3 (unrelated)
  ]
  const baseProps = {
    moduleId: 'M1',
    moduleName: '分子与细胞',
    nodes: makeNodes(),
    edges: makeEdges(),
    navigation: [{ id: 'M1', name: '分子与细胞', big_concepts: [
      { id: 'BC1', name: 'BC1', concept_ids: ['A', 'B', 'C'] },
      { id: 'BC2', name: 'BC2', concept_ids: ['D', 'E', 'F'] },
    ]}],
    qualityIssues: [],
  }

  // Helper: 通过既有 node:click 事件入口驱动 focus
  async function focusOn(wrapper, nodeId) {
    const graph = graphInstances[graphInstances.length - 1]
    graph.handlers['node:click']({ target: { id: nodeId } })
    await nextTick()
  }

  it('relatedNodeIds is empty Set when focusedNodeId is null (initial state)', () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    // Phase 2 初始 focusedNodeId=null
    expect(wrapper.vm.focusedNodeId).toBeNull()
    expect(wrapper.vm.relatedNodeIds).toBeInstanceOf(Set)
    expect(wrapper.vm.relatedNodeIds.size).toBe(0)
    expect(wrapper.vm.relatedEdgeIds).toBeInstanceOf(Set)
    expect(wrapper.vm.relatedEdgeIds.size).toBe(0)
  })

  it('relatedNodeIds is empty Set after clearFocus() returns focus to null', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    await focusOn(wrapper, 'B')
    expect(wrapper.vm.relatedNodeIds.size).toBeGreaterThan(0)
    wrapper.vm.clearFocus()
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBeNull()
    expect(wrapper.vm.relatedNodeIds.size).toBe(0)
    expect(wrapper.vm.relatedEdgeIds.size).toBe(0)
  })

  it('relatedNodeIds includes focus self + predecessors + successors (hard and soft) — CE-004 guard', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    await focusOn(wrapper, 'B')
    // focus=B: 前置 A (hard) + D (hard), 后继 C (soft); 期望 {A, B, C, D}
    const r = wrapper.vm.relatedNodeIds
    expect(r.has('B')).toBe(true)  // 焦点自身
    expect(r.has('A')).toBe(true)  // hard 前置
    expect(r.has('D')).toBe(true)  // hard 前置（反向边）——CE-004 护栏
    expect(r.has('C')).toBe(true)  // soft 后继
    expect(r.has('E')).toBe(false) // 不相关
    expect(r.has('F')).toBe(false)
    expect(r.size).toBe(4)
  })

  it('relatedNodeIds returns {focus, peer} when focus has single edge', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    await focusOn(wrapper, 'F')
    // F 只在 edge-3 (E→F) 中，所以 related = {E, F}
    const r = wrapper.vm.relatedNodeIds
    expect(r.has('F')).toBe(true)
    expect(r.has('E')).toBe(true)
    expect(r.size).toBe(2)
  })

  it('relatedEdgeIds uses buildVisibleEdgeList visibleId (edge-${visibleIndex}) aligned with buildG6Data', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    await focusOn(wrapper, 'B')
    const e = wrapper.vm.relatedEdgeIds
    // B 关联的边: edge-0 (A→B), edge-1 (B→C), edge-2 (D→B)
    expect(e.has('edge-0')).toBe(true)
    expect(e.has('edge-1')).toBe(true)
    expect(e.has('edge-2')).toBe(true)
    expect(e.has('edge-3')).toBe(false)  // E→F 不相关
    expect(e.size).toBe(3)
  })

  it('F003 guard: buildVisibleEdgeList skips edges whose endpoint is filtered out, keeping id alignment', async () => {
    // 构造一条 dangling 边（target='GHOST' 不在 nodes 集合）
    // 这条边在 buildG6Data 和 relatedEdgeIds 中都应被过滤掉，visibleIndex 不计入
    const edgesWithDangling = [
      { source: 'A', target: 'B', type: 'prerequisite_hard' },       // visible edge-0
      { source: 'A', target: 'GHOST', type: 'prerequisite_hard' },   // filtered out
      { source: 'B', target: 'C', type: 'prerequisite_soft' },       // visible edge-1 (!)
    ]
    const wrapper = mount(ConceptMapPanel, {
      props: { ...baseProps, edges: edgesWithDangling },
    })
    await focusOn(wrapper, 'B')
    // B 关联的可见边: edge-0 (A→B) + edge-1 (B→C)
    // 如果 F003 未修复（使用原始索引）, B→C 的 id 会是 edge-2 而不是 edge-1，导致 setElementState 打不中
    expect(wrapper.vm.relatedEdgeIds.has('edge-0')).toBe(true)
    expect(wrapper.vm.relatedEdgeIds.has('edge-1')).toBe(true)
    expect(wrapper.vm.relatedEdgeIds.has('edge-2')).toBe(false)
    expect(wrapper.vm.relatedEdgeIds.size).toBe(2)
  })

  it('relatedEdgeIds excludes edges of irrelevant types (non-prerequisite)', async () => {
    // 'bridge' 类型的边（Phase 3 可能扩展）应被忽略
    const edgesWithBridge = [
      { source: 'A', target: 'B', type: 'prerequisite_hard' },  // visible edge-0
      { source: 'A', target: 'B', type: 'bridge' },             // visible edge-1 (fake type)
    ]
    const wrapper = mount(ConceptMapPanel, {
      props: { ...baseProps, edges: edgesWithBridge },
    })
    await focusOn(wrapper, 'A')
    expect(wrapper.vm.relatedEdgeIds.has('edge-0')).toBe(true)
    expect(wrapper.vm.relatedEdgeIds.has('edge-1')).toBe(false)  // bridge 被忽略
  })
})
```

- [ ] **Step 3: 运行测试确认 PASS**

Run: `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-006"`
Expected: 7 tests PASS（含 F003 新增的 dangling edge 对齐测试）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/knowledge-tree/ConceptMapPanel.vue frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js
git commit -m "feat(knowledge-tree): Phase 2.5 T1 — buildVisibleEdgeList helper + relatedNodeIds/relatedEdgeIds + 7 tests"
```

**边界条件:**
- focusedNodeId 初始 null / clearFocus() 置 null → 空 Set，不抛异常
- 焦点无任何边（孤立节点）→ `{focus}` 自身
- 焦点处于链末端（只有前置没有后继 或 反之）→ 正确包含单向邻居
- 非 prerequisite 类型的边（如 'bridge'）→ 被忽略，不计入 relatedEdgeIds
- props.edges 含 dangling 边（endpoint 不在 nodes 集合）→ helper 过滤掉，visibleIndex 不计入，relatedEdgeIds 的 id 仍与 buildG6Data 对齐（F003 硬约束）
- props.edges 为空数组 → relatedNodeIds 仅含 focus（如有）

**审查清单:**
- ✓ focusedNodeId 使用组件内部 ref（Phase 2 现状），未改为 prop（F001 硬约束）
- ✓ defineExpose 增量扩展，保留 focusedNodeId 和 clearFocus（F002 硬约束）
- ✓ buildVisibleEdgeList helper 被 buildG6Data 和 relatedEdgeIds 两处共用（F003 硬约束）
- ✓ 同时处理 `e.source===focus` 和 `e.target===focus`（CE-004 护栏）
- ✓ soft 和 hard 两种 prerequisite 类型都被纳入邻居
- ✓ relatedEdgeIds 使用 `edge-${i}` 格式，与 buildG6Data 一致
- ✓ 焦点自身始终在 relatedNodeIds 中
- ✓ 空焦点返回空 Set 实例（不是 null/undefined）
- ✓ defineExpose 扩展了 relatedNodeIds 和 relatedEdgeIds
- ✗ 用 Array 而非 Set（破坏 O(1) has 查询契约）
- ✗ 遗漏 source===focus 或 target===focus 任一方向

---

### Task 2: G6 state spec + updateElementStates wire-up

> **R1 修复（F001/F004/F005）**：updateElementStates 读组件内部 `focusedNodeId.value`（非 props）；`createGraph()` 末尾补重放焦点 state（F004 护栏）；测试通过 Phase 2 既有 `graph.handlers['node:click']` 事件入口驱动，断言 G6 mock 的 `setElementState` spy 真实调用参数（F005 从逻辑镜像升级为行为验证）。

**Files:**
- Modify: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（扩展 node/edge state spec + 新增 updateElementStates + watch focusedNodeId + createGraph 末尾重放）
- Modify: `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（扩展 G6 mock 加 setElementState spy + 新增 INV-007/INV-008 + CE-005 测试）

**测试契约:**

1. 通过 node:click 事件驱动焦点进入后，graph.setElementState 被调用；调用参数的 state map 中非相关节点=`['faded']`，相关节点=`[]`
   - 入口: mount → `graphInstances[last].handlers['node:click']({target:{id:'B'}})` → `await nextTick()` → 读 `graphInstances[last].setElementState.mock.calls[last][0]` 断言 state map
   - 反例 1: 错误实现不 watch focusedNodeId 变化 → setElementState 从未被调用 → `mock.calls.length === 0`
   - 反例 2: 错误实现把所有节点都 faded（包括焦点自身）→ `stateMap.B` 不是 `[]`
   - 反例 3: 错误实现忘记处理边 → stateMap 缺 edge-* 键
   - 边界: 焦点无任何相关节点 / 焦点连接所有节点 / 焦点有反向前置
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-007"`

2. 退出焦点（`clearFocus()`）时 graph.setElementState 被调用，参数为空对象 `{}`（CE-005）
   - 入口: mount → focus B → `wrapper.vm.clearFocus()` → `await nextTick()` → 断言最后一次 setElementState 调用 `args[0] === {}` 且 `args[1] === true`
   - 反例 1: 错误实现退出焦点时不清状态 → mock.calls 最后一次不是空对象
   - 反例 2: 错误实现用 undefined 清空 → `args[0] !== {}` 会 fail
   - 边界: 从焦点状态切到 null / 直接 unmount
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-008"`

3. 切换焦点（B→F）时，新 state map 反映新关系
   - 入口: mount → focus B → focus F → 断言最后一次 setElementState 调用的 state map 中 A/D=faded（之前是 B 的前置，现在不相关）、E/F=[]（现在相关）
   - 反例: 错误实现缓存上次 related 集合，切换时未重算
   - 边界: 连续切换多个焦点 / 切回 null
   - 回归: N/A
   - 命令: 同上

4. createGraph 后焦点状态被重放（F004 护栏）
   - 入口: mount → focus B（记录 setElementState 调用次数）→ `wrapper.setProps({ nodes: [...newNodes] })` 触发 destroy→create → 断言新 graph 实例的 setElementState 被额外调用一次，且参数 state map 正确（焦点仍为 B，新 graph 有相应 faded 节点）
   - 反例: 错误实现不在 createGraph 末尾重放 state → 新 graph 焦点不淡化（视觉失真）
   - 边界: nodes 变化 / edges 变化 / nodes+edges 同时变化
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "F004 graph rebuild"`

- [ ] **Step 1: 扩展 G6 mock — 添加 setElementState spy**

首先扩展 Phase 2 既有的 G6 mock（`ConceptMapPanel.test.js:7-27` 范围）。找到 `class Graph` mock 内部，添加 `setElementState` 方法：

```javascript
// ConceptMapPanel.test.js mock 扩展
vi.mock('@antv/g6', () => {
  const graphCtorCalls = []
  const graphInstances = []
  class Graph {
    constructor(cfg) {
      graphCtorCalls.push(cfg)
      this.handlers = {}
      this.setElementState = vi.fn().mockResolvedValue(undefined)  // R1 F005 新增 spy
      graphInstances.push(this)
    }
    on(ev, cb) { this.handlers[ev] = cb }
    render() { return Promise.resolve() }
    destroy() {}
  }
  return { Graph, __graphCtorCalls: graphCtorCalls, __graphInstances: graphInstances }
})
```

（如果 Phase 2 mock 的具体结构与上面不同，以现有结构为准，只追加 `this.setElementState = vi.fn().mockResolvedValue(undefined)` 一行）。

- [ ] **Step 2: 扩展 node/edge state spec 并新增 updateElementStates 函数**

找到 `ConceptMapPanel.vue` 的 `createGraph()` 函数，修改其中的 `node.style` 和 `edge.style` 配置为带 state 的形式。在 node 配置中加入 `state`：

```javascript
    node: {
      style: {
        size: 28,
        fill: d => REVIEW_COLORS[d.data.reviewStatus] || REVIEW_COLORS.ai_draft,
        stroke: 'rgba(255,255,255,0.25)',
        lineWidth: 1.5,
        labelText: d => d.data.label,
        labelFill: '#e2e8f0',
        labelFontSize: 11,
        labelPlacement: 'right',
        labelOffsetX: 6,
        badgeText: d => d.data.badgeText || '',
        badgePlacement: 'right-top',
        badgeFill: '#fbbf24',
        badgeFontSize: 9,
      },
      // Phase 2.5 INV-007: 焦点模式淡化非相关节点
      state: {
        faded: {
          opacity: 0.3,
        },
      },
    },
```

edge 配置同样扩展：

```javascript
    edge: {
      style: {
        stroke: d => {
          if (d.data.type === 'prerequisite_hard') return 'rgba(100,116,139,0.6)'
          if (d.data.type === 'prerequisite_soft') return 'rgba(100,116,139,0.35)'
          return 'rgba(99,102,241,0.3)'
        },
        lineDash: d => d.data.type === 'prerequisite_soft' ? [4, 3] : [0],
        endArrow: true,
      },
      // Phase 2.5 INV-007: 焦点模式强调相关边，淡化无关边
      state: {
        dimmed: {
          opacity: 0.2,
        },
        emphasized: {
          lineWidth: 2.5,  // 默认 1px，焦点相关边粗化
        },
      },
    },
```

在 `createGraph()` 之后新增 `updateElementStates()` 函数：

```javascript
// Phase 2.5 INV-007/INV-008: 根据组件内部 focusedNodeId ref 批量更新节点/边 state
// - null: 清空所有 state（INV-008 反泄漏护栏，CE-005 测试点）
// - 有值: 非相关节点 ['faded']，相关节点 []；非相关边 ['dimmed']，相关边 ['emphasized']
// R1 修复 F001: 读 focusedNodeId.value（组件内部 ref），不是 props.focusedNodeId
// R1 修复 F003: 边 id 通过 buildVisibleEdgeList 获取，与 buildG6Data 严格对齐
function updateElementStates() {
  if (!graph) return
  if (!focusedNodeId.value) {
    // 退出焦点：批量清空（第二个参数 true 启用默认动画）
    try {
      graph.setElementState({}, true)
    } catch (err) {
      console.warn('[ConceptMapPanel] setElementState clear failed:', err)
    }
    return
  }
  const related = relatedNodeIds.value
  const relatedEdges = relatedEdgeIds.value
  const stateMap = {}
  for (const n of props.nodes) {
    stateMap[n.id] = related.has(n.id) ? [] : ['faded']
  }
  for (const { visibleId } of buildVisibleEdgeList()) {
    stateMap[visibleId] = relatedEdges.has(visibleId) ? ['emphasized'] : ['dimmed']
  }
  try {
    graph.setElementState(stateMap, true)
  } catch (err) {
    console.warn('[ConceptMapPanel] setElementState apply failed:', err)
  }
}
```

**R1 修复 F004**：在 `createGraph()` 函数末尾（`graph.on(...)` 监听注册之后）追加重放：

```javascript
function createGraph() {
  // ...existing code: new Graph + graph.on('node:click', ...) + graph.on('canvas:click', ...)
  // R1 修复 F004: 如果当前处于焦点态，重放 state 到新 graph（避免 nodes/edges 变化 destroy→create 后焦点视觉丢失）
  if (focusedNodeId.value) {
    nextTick(updateElementStates)
  }
}
```

新增 watch 监听组件内部 `focusedNodeId` ref（不是 props）：

```javascript
// R1 修复 F001: watch 组件内部 focusedNodeId ref
watch(focusedNodeId, () => {
  nextTick(updateElementStates)
})
```

**R1 修复 F002**：扩展 Phase 2 既有的 `defineExpose`，**增量**追加，保留 `focusedNodeId` 和 `clearFocus`：

```javascript
defineExpose({
  crossModuleBadges,
  crossModulePeers,
  focusedNodeId,    // Phase 2 保留（测试依赖）
  clearFocus,       // Phase 2 保留（测试依赖）
  relatedNodeIds,   // Phase 2.5 T1 新增
  relatedEdgeIds,   // Phase 2.5 T1 新增
  updateElementStates, // Phase 2.5 T2 新增（供测试调用验证）
})
```

- [ ] **Step 2: 写失败测试**

在 `ConceptMapPanel.test.js` 的 Phase 2.5 describe block 末尾追加：

```javascript
// R1 修复 F005: 测试直接断言 G6 mock 的 setElementState spy 调用，不再只测 computed
// 焦点驱动用 Phase 2 既有的 graph.handlers['node:click'] 事件入口
describe('Phase 2.5 INV-007/INV-008: updateElementStates real setElementState wire-up', () => {
  const makeNodes = () => [
    { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1' },
    { id: 'B', name: 'B', big_concept_id: 'BC1', module: 'M1' },
    { id: 'C', name: 'C', big_concept_id: 'BC1', module: 'M1' },
    { id: 'D', name: 'D', big_concept_id: 'BC2', module: 'M1' },
    { id: 'E', name: 'E', big_concept_id: 'BC2', module: 'M1' },
    { id: 'F', name: 'F', big_concept_id: 'BC2', module: 'M1' },
  ]
  const makeEdges = () => [
    { source: 'A', target: 'B', type: 'prerequisite_hard' },
    { source: 'B', target: 'C', type: 'prerequisite_soft' },
    { source: 'D', target: 'B', type: 'prerequisite_hard' },
    { source: 'E', target: 'F', type: 'prerequisite_soft' },
  ]
  const baseProps = {
    moduleId: 'M1',
    moduleName: '分子与细胞',
    nodes: makeNodes(),
    edges: makeEdges(),
    navigation: [{ id: 'M1', name: '分子与细胞', big_concepts: [
      { id: 'BC1', name: 'BC1', concept_ids: ['A', 'B', 'C'] },
      { id: 'BC2', name: 'BC2', concept_ids: ['D', 'E', 'F'] },
    ]}],
    qualityIssues: [],
  }

  async function focusOn(nodeId) {
    const graph = graphInstances[graphInstances.length - 1]
    graph.handlers['node:click']({ target: { id: nodeId } })
    await nextTick()
    return graph
  }

  it('INV-007: entering focus triggers graph.setElementState with precise state map', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    const graph = graphInstances[graphInstances.length - 1]
    // 记录进入焦点前 spy 调用次数（可能因 mount 时初始化为 0）
    const callsBefore = graph.setElementState.mock.calls.length

    await focusOn('B')

    // 进入焦点后 spy 必须被调用
    expect(graph.setElementState.mock.calls.length).toBeGreaterThan(callsBefore)

    // 取最后一次调用的 state map 参数（setElementState(stateMap, animation)）
    const lastCall = graph.setElementState.mock.calls[graph.setElementState.mock.calls.length - 1]
    const stateMap = lastCall[0]
    const animation = lastCall[1]

    // 相关节点 = []，非相关节点 = ['faded']
    expect(stateMap.A).toEqual([])   // A 是 B 的前置
    expect(stateMap.B).toEqual([])   // 焦点自身
    expect(stateMap.C).toEqual([])   // B 的后继
    expect(stateMap.D).toEqual([])   // D 是 B 的反向前置（CE-004 护栏）
    expect(stateMap.E).toEqual(['faded'])
    expect(stateMap.F).toEqual(['faded'])

    // 相关边 = ['emphasized']，非相关边 = ['dimmed']
    expect(stateMap['edge-0']).toEqual(['emphasized'])  // A→B
    expect(stateMap['edge-1']).toEqual(['emphasized'])  // B→C
    expect(stateMap['edge-2']).toEqual(['emphasized'])  // D→B
    expect(stateMap['edge-3']).toEqual(['dimmed'])      // E→F 不相关

    expect(animation).toBe(true)
  })

  it('INV-008 + CE-005: clearFocus triggers graph.setElementState({}, true)', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    const graph = graphInstances[graphInstances.length - 1]

    await focusOn('B')
    // 清焦点前记录 spy 次数
    const callsBefore = graph.setElementState.mock.calls.length

    wrapper.vm.clearFocus()
    await nextTick()

    // 清焦点后必须新增一次 spy 调用
    expect(graph.setElementState.mock.calls.length).toBeGreaterThan(callsBefore)

    // 最后一次调用参数必须是空对象 + animation=true
    const lastCall = graph.setElementState.mock.calls[graph.setElementState.mock.calls.length - 1]
    expect(lastCall[0]).toEqual({})  // CE-005: 退出焦点必须清空所有 state
    expect(lastCall[1]).toBe(true)
  })

  it('switching focus B→F recalculates state map (no stale related set)', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    const graph = graphInstances[graphInstances.length - 1]

    await focusOn('B')
    await focusOn('F')

    const lastCall = graph.setElementState.mock.calls[graph.setElementState.mock.calls.length - 1]
    const stateMap = lastCall[0]
    // 切换到 F 后：E 和 F 应该是 [], A/B/C/D 应该是 ['faded']
    expect(stateMap.F).toEqual([])
    expect(stateMap.E).toEqual([])
    expect(stateMap.A).toEqual(['faded'])
    expect(stateMap.B).toEqual(['faded'])
    expect(stateMap.C).toEqual(['faded'])
    expect(stateMap.D).toEqual(['faded'])
  })

  it('F004 graph rebuild: createGraph replays focus state after destroy/create cycle', async () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    await focusOn('B')

    // 触发 nodes 更新 → destroy→create 循环（watch [moduleId, nodes, edges]）
    const newNodes = [
      ...makeNodes(),
      { id: 'G', name: 'G', big_concept_id: 'BC2', module: 'M1' },
    ]
    await wrapper.setProps({ nodes: newNodes })
    await nextTick()
    await nextTick()  // 两次 tick：一次给 watch destroy→create，一次给 createGraph 末尾的重放

    // 新 graph 实例应该存在
    expect(graphInstances.length).toBeGreaterThanOrEqual(2)
    const newGraph = graphInstances[graphInstances.length - 1]

    // 新 graph 的 setElementState 应该被调用至少一次（重放焦点）
    expect(newGraph.setElementState.mock.calls.length).toBeGreaterThan(0)

    // 最后一次调用的 state map 反映当前焦点 B 的关系（包括新节点 G 应为 faded）
    const lastCall = newGraph.setElementState.mock.calls[newGraph.setElementState.mock.calls.length - 1]
    const stateMap = lastCall[0]
    expect(stateMap.B).toEqual([])   // 焦点保持
    expect(stateMap.G).toEqual(['faded'])  // 新节点未相关
  })
})
```

- [ ] **Step 3: 运行测试确认 PASS**

Run: `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-007"`
Expected: 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/knowledge-tree/ConceptMapPanel.vue frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js
git commit -m "feat(knowledge-tree): Phase 2.5 T2 — G6 state spec + updateElementStates wire-up + 4 tests"
```

**边界条件:**
- focusedNodeId null → setElementState({}, true) 清空
- focusedNodeId 切换（B→F）→ 重算 relatedNodeIds + 重调 setElementState
- graph 尚未创建（mount 早期）→ 早 return，不抛异常
- setElementState 抛异常 → console.warn + 不中断 UX
- 同一焦点重复设置（幂等）→ 允许多次调用（G6 内部会 diff）

**审查清单:**
- ✓ node.state.faded 和 edge.state.dimmed/emphasized 声明在 G6 Graph config 中
- ✓ watch 监听**组件内部** `focusedNodeId` ref，不是 `props.focusedNodeId`（F001 硬约束）
- ✓ updateElementStates 读 `focusedNodeId.value`，不是 `props.focusedNodeId`
- ✓ 边 id 通过 `buildVisibleEdgeList()` helper 获取（F003 硬约束）
- ✓ createGraph 末尾 `if (focusedNodeId.value) nextTick(updateElementStates)` 重放焦点（F004 护栏）
- ✓ 退出焦点调 setElementState({}, true) 清空（CE-005 护栏）
- ✓ graph === null 时早 return
- ✓ try/catch 包裹 setElementState 调用，防 G6 内部异常中断 UX
- ✓ updateElementStates 暴露在 defineExpose 供测试调用（增量扩展，保留 Phase 2 已暴露的 focusedNodeId/clearFocus）
- ✓ G6 mock 扩展 `setElementState = vi.fn().mockResolvedValue(undefined)` 供测试 spy（F005 硬约束）
- ✓ 测试通过真实 `graph.handlers['node:click']` 入口驱动焦点，断言 spy 调用参数精确（非逻辑镜像）
- ✗ 使用 updateNodeData 重建节点（性能差，触发布局重算）
- ✗ 把焦点自身也 faded（视觉自相矛盾）
- ✗ 依赖 setTimeout 而不是 nextTick
- ✗ 测试不断言真实 setElementState 调用，只测 computed（逻辑镜像 test-gap HIGH）

---

### Task 3: G6 Tooltip plugin + renderPeersHtml 纯函数

**Files:**
- Modify: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（import Tooltip + 插件配置 + renderPeersHtml 纯函数）
- Modify: `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（新增 INV-009/INV-010 + CE-006 测试）

**测试契约:**

1. renderPeersHtml(peers) 返回含模块分组和节点名的 HTML 字符串
   - 入口: `renderPeersHtml({ M2: [{id:'x', name:'细胞膜流动性'}], M3: [{id:'y', name:'基因表达'}] })`
   - 反例: 错误实现漏掉模块 label 或漏掉节点 name——本测试断言返回字符串同时包含 `→ M2` 和 `细胞膜流动性` 和 `→ M3` 和 `基因表达`
   - 边界: 单模块单节点 / 多模块多节点 / 空对象 / null / 某模块数组为空
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "INV-010"`

2. renderPeersHtml(null) 和 renderPeersHtml({}) 返回空字符串不抛异常（CE-006）
   - 入口: 逐一调用
   - 反例: 错误实现对 null 直接 Object.entries 崩溃
   - 边界: null / undefined / {} / { M2: [] }（空数组）
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "CE-006"`

3. Tooltip plugin enable 谓词：对有 badgeText 的节点返回 true，对无 badgeText 的返回 false
   - 入口: 直接调用 plugin 配置对象中的 enable 函数，mock items 参数
   - 反例: 错误实现不检查 badgeText，导致所有节点都弹 tooltip（干扰非徽标节点的交互）
   - 边界: items=[{data:{badgeText:'→M2×3'}}] / items=[{data:{badgeText:''}}] / items=[{data:{}}] / items=[]
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "INV-009"`

- [ ] **Step 1: 新增 renderPeersHtml 纯函数 + Tooltip plugin 配置**

在 ConceptMapPanel.vue 的 `<script setup>` 顶部、imports 之后，新增纯函数（放在 script setup 内以便 defineExpose 暴露；也可提到模块顶层作为独立 export）：

```javascript
// Phase 2.5 INV-010 + CE-006: 纯函数，生成 Tooltip HTML 内容
// peers 结构: { M2: [{id, name}, ...], M3: [...] }
// null/undefined/{} → 空字符串（CE-006 护栏）
function renderPeersHtml(peers) {
  if (!peers || typeof peers !== 'object') return ''
  const entries = Object.entries(peers).filter(([, list]) => Array.isArray(list) && list.length > 0)
  if (entries.length === 0) return ''
  entries.sort(([a], [b]) => a.localeCompare(b))  // 模块字母序，确定性
  const sections = entries.map(([modId, list]) => {
    const sortedList = [...list].sort((a, b) => (a.name || '').localeCompare(b.name || ''))
    const items = sortedList.map(p => `<li>${escapeHtml(p.name || '')}</li>`).join('')
    return `<div class="peer-section"><span class="peer-module">→ ${escapeHtml(modId)}</span><ul>${items}</ul></div>`
  }).join('')
  return `<div class="peer-tooltip">${sections}</div>`
}

// 最小 HTML 转义（防注入）
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
```

修改 import 语句引入 Tooltip plugin：

```javascript
import { Graph } from '@antv/g6'
// Phase 2.5 D4: 内置 Tooltip plugin（trigger=hover + enable 谓词 + getContent）
```

在 `createGraph()` 的 `new Graph({...})` 配置中加入 `plugins`（**R1 API 核对**：Tooltip.getContent 签名是 `(event, items) => Promise<HTMLElement | string>`，所以用 async 函数更稳）：

```javascript
  graph = new Graph({
    container: g6ContainerRef.value,
    data,
    autoFit: 'view',
    layout: { type: 'preset' },
    node: { /* ...existing... */ },
    edge: { /* ...existing... */ },
    // Phase 2.5 INV-009: 仅在有跨模块徽标的节点触发 tooltip
    plugins: [
      {
        type: 'tooltip',
        key: 'badge-tooltip',
        trigger: 'hover',
        enable: (event, items) => {
          const item = items && items[0]
          return !!(item && item.data && item.data.badgeText)
        },
        // R1 API 核对: getContent 签名 Promise<HTMLElement|string>，async 显式返回
        getContent: async (event, items) => {
          const item = items && items[0]
          if (!item) return ''
          const nodeId = item.id
          return renderPeersHtml(crossModulePeers.value[nodeId] || {})
        },
      },
    ],
  })
```

**R1 修复 F002**：扩展 defineExpose，**增量**追加 Task 3 的新增项，保留所有前置项：

```javascript
defineExpose({
  crossModuleBadges,
  crossModulePeers,
  focusedNodeId,         // Phase 2 保留
  clearFocus,            // Phase 2 保留
  relatedNodeIds,        // Phase 2.5 T1
  relatedEdgeIds,        // Phase 2.5 T1
  updateElementStates,   // Phase 2.5 T2
  renderPeersHtml,       // Phase 2.5 T3 新增
})
```

- [ ] **Step 2: 写失败测试**

在 ConceptMapPanel.test.js Phase 2.5 describe block 末尾追加：

```javascript
describe('Phase 2.5 INV-009/INV-010 + CE-006: Tooltip plugin + renderPeersHtml', () => {
  const baseProps = {
    moduleId: 'M1',
    moduleName: '分子与细胞',
    nodes: [{ id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1' }],
    edges: [],
    navigation: [{ id: 'M1', name: '分子与细胞', big_concepts: [
      { id: 'BC1', name: 'BC1', concept_ids: ['A'] },
    ]}],
    qualityIssues: [],
  }

  it('INV-010: renderPeersHtml output contains module labels and node names for multi-module peers', () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    const html = wrapper.vm.renderPeersHtml({
      M2: [{ id: 'x1', name: '细胞膜流动性' }, { id: 'x2', name: '主动运输' }],
      M3: [{ id: 'y1', name: '基因表达' }],
    })
    expect(html).toContain('→ M2')
    expect(html).toContain('细胞膜流动性')
    expect(html).toContain('主动运输')
    expect(html).toContain('→ M3')
    expect(html).toContain('基因表达')
    expect(html).toContain('peer-tooltip')
    expect(html).toContain('peer-section')
  })

  it('INV-010 determinism: module entries sorted alphabetically', () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    const html = wrapper.vm.renderPeersHtml({
      M3: [{ id: 'y', name: 'B-concept' }],
      M2: [{ id: 'x', name: 'A-concept' }],
    })
    // M2 应出现在 M3 之前（字母序）
    const m2Index = html.indexOf('→ M2')
    const m3Index = html.indexOf('→ M3')
    expect(m2Index).toBeGreaterThan(-1)
    expect(m3Index).toBeGreaterThan(-1)
    expect(m2Index).toBeLessThan(m3Index)
  })

  it('CE-006: renderPeersHtml returns empty string for null / undefined / {} / empty arrays', () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    expect(wrapper.vm.renderPeersHtml(null)).toBe('')
    expect(wrapper.vm.renderPeersHtml(undefined)).toBe('')
    expect(wrapper.vm.renderPeersHtml({})).toBe('')
    expect(wrapper.vm.renderPeersHtml({ M2: [] })).toBe('')  // 所有列表为空 → 过滤后无条目
  })

  it('CE-006: renderPeersHtml escapes HTML in module id and node name', () => {
    const wrapper = mount(ConceptMapPanel, { props: baseProps })
    const html = wrapper.vm.renderPeersHtml({
      '<script>alert(1)</script>': [{ id: 'x', name: '<img src=x>' }],
    })
    expect(html).not.toContain('<script>alert(1)</script>')
    expect(html).toContain('&lt;script&gt;')
    expect(html).not.toContain('<img src=x>')
    expect(html).toContain('&lt;img src=x&gt;')
  })

  // R1 修复 F006: 直接读 graphCtorCalls[0].plugins 真实 wiring，不再手写 "等价"
  it('INV-009: Tooltip plugin is wired to Graph with correct type/key/trigger', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...baseProps,
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
            external_hard_refs: { in: [], out: [{ id: 'x', name: '跨模块节点', module: 'M2' }] } },
        ],
      },
    })
    // 读 new Graph() 调用时传入的 cfg
    expect(graphCtorCalls.length).toBeGreaterThan(0)
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    expect(cfg.plugins).toBeDefined()
    expect(Array.isArray(cfg.plugins)).toBe(true)

    const tooltipPlugin = cfg.plugins.find(p => p && p.type === 'tooltip')
    expect(tooltipPlugin).toBeDefined()
    expect(tooltipPlugin.key).toBe('badge-tooltip')
    expect(tooltipPlugin.trigger).toBe('hover')
    expect(typeof tooltipPlugin.enable).toBe('function')
    expect(typeof tooltipPlugin.getContent).toBe('function')
  })

  it('INV-009: Tooltip plugin enable returns true only for items with badgeText (real plugin config)', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...baseProps,
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
            external_hard_refs: { in: [], out: [{ id: 'x', name: 'Xpeer', module: 'M2' }] } },
        ],
      },
    })
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    const enable = cfg.plugins.find(p => p.type === 'tooltip').enable

    // 正例: 有 badgeText
    expect(enable(null, [{ data: { badgeText: '→M2×3' } }])).toBe(true)
    // 反例 1: 空字符串 badgeText
    expect(enable(null, [{ data: { badgeText: '' } }])).toBe(false)
    // 反例 2: 无 badgeText 字段
    expect(enable(null, [{ data: {} }])).toBe(false)
    // 反例 3: 空 items
    expect(enable(null, [])).toBe(false)
    // 反例 4: null items
    expect(enable(null, null)).toBe(false)
  })

  it('INV-009: Tooltip plugin getContent returns renderPeersHtml(crossModulePeers[nodeId]) via real wiring', async () => {
    // 构造节点 A 带 external_hard_refs.out，让 crossModulePeers.A 非空
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...baseProps,
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
            external_hard_refs: {
              in: [],
              out: [
                { id: 'x1', name: '膜流动性', module: 'M2' },
                { id: 'y1', name: '基因表达', module: 'M3' },
              ],
            },
          },
        ],
      },
    })
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    const getContent = cfg.plugins.find(p => p.type === 'tooltip').getContent

    // 真实调用 getContent（async）
    const html = await getContent(null, [{ id: 'A', data: { badgeText: '→M2×1 →M3×1' } }])
    expect(typeof html).toBe('string')
    expect(html).toContain('→ M2')
    expect(html).toContain('膜流动性')
    expect(html).toContain('→ M3')
    expect(html).toContain('基因表达')
  })

  it('INV-009: Tooltip getContent returns empty string for node without peers', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...baseProps,
        nodes: [{ id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1' }],  // 无 external_hard_refs
      },
    })
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    const getContent = cfg.plugins.find(p => p.type === 'tooltip').getContent
    const html = await getContent(null, [{ id: 'A', data: {} }])
    expect(html).toBe('')
  })
})
```

- [ ] **Step 3: 运行测试确认 PASS**

Run: `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5"`
Expected: 18 tests PASS（Task 1 的 7 + Task 2 的 4 + Task 3 的 7）

- [ ] **Step 4: 全量前端测试**

Run: `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 17 files / 178 tests PASS（Phase 2 的 160 + Phase 2.5 的 18）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/knowledge-tree/ConceptMapPanel.vue frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js
git commit -m "feat(knowledge-tree): Phase 2.5 T3 — Tooltip plugin + renderPeersHtml + 5 tests"
```

**边界条件:**
- peers=null → '' 不崩溃（CE-006）
- peers={} → '' 不崩溃
- peers={M2: []} → '' （所有列表为空视为无条目）
- 多模块多节点 → 模块按字母序，同模块内节点按 name 字母序
- HTML 转义：`<script>` / `<img>` / `&` / 引号 均被 escape
- enable 谓词：items 空 / 无 data / 无 badgeText / badgeText 空字符串 → 全部 false

**审查清单:**
- ✓ renderPeersHtml 是纯函数（无副作用）
- ✓ null/undefined/{} 输入返回 ''，不抛异常（CE-006）
- ✓ HTML 转义覆盖 `<`, `>`, `&`, `"`, `'`
- ✓ 模块按字母序排序（确定性）
- ✓ 同模块内节点按 name 字母序排序（确定性）
- ✓ Tooltip plugin trigger='hover'（非 click）
- ✓ enable 谓词检查 `items[0].data.badgeText` 非空字符串
- ✓ getContent 从 crossModulePeers.value 取数（复用 Batch 2 computed）
- ✗ 直接插入未 escape 的用户数据到 HTML（XSS 风险）
- ✗ 用 Naive UI NPopover 替代（额外坐标计算复杂度）
- ✗ enable 永远返回 true（导致所有节点都弹 tooltip）

---

## 自审流程（Executor 收尾动作）

Batch 1 Tasks 1-3 完成后，Executor 必须：

1. 运行 `cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run` → 期望 17 files / 178 tests PASS（Phase 2 的 160 + Phase 2.5 的 18）
2. 反证验证（counter-proof）：对每个新增 INV/CE 条目至少做 1 个反证（破坏源代码对应逻辑行，确认新测试精确 fail）
3. 写 `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-handoff-batch1.md` 审查交接单（含逐 Task 自审表 + 预审自检 5 字段 + 自查四要素）
4. 调用 `codex-review` skill 进行 GPT Code Review (Gate 2)
5. **不得自行声明"Phase 2.5 完成"**——按 design §8 的自治边界规则，视觉任务最终验收在用户（浏览器手动验证三条路径）

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-006
      statement: "relatedNodeIds 包含焦点自身 + 所有通过 prerequisite_hard/soft 边直连的节点（前置和后继双向）；focusedNodeId 为 null/undefined/'' 时返回空 Set"
      verification: pending_test
      test_ref: frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js::describe("Phase 2.5 INV-006")
    - id: INV-007
      statement: "通过 graph.handlers['node:click'] 事件驱动焦点进入时，graph.setElementState 的 spy 被调用；参数 state map 中相关节点（含焦点自身）=[]，非相关节点=['faded']，相关边=['emphasized']，非相关边=['dimmed']；第二参数 animation=true"
      verification: pending_test
      test_ref: frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js::it("INV-007: entering focus triggers graph.setElementState with precise state map")
    - id: INV-008
      statement: "通过 wrapper.vm.clearFocus() 退出焦点时，graph.setElementState 的 spy 被调用且最后一次调用参数 args[0]==={} 且 args[1]===true；退出后无 state 泄漏（CE-005 护栏）"
      verification: pending_test
      test_ref: frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js::it("INV-008 + CE-005: clearFocus triggers graph.setElementState")
    - id: INV-009
      statement: "Tooltip plugin 通过 graphCtorCalls[last].plugins 真实注入 Graph 配置；plugin 的 type='tooltip'/key='badge-tooltip'/trigger='hover'；其 enable 谓词对有 badgeText 的 item 返回 true，对空 badgeText/无 data/空 items/null items 返回 false；其 getContent（async）对有 external_hard_refs.out 的节点返回含 peer 模块 label 和节点 name 的 HTML 字符串，对无 peers 的节点返回空字符串"
      verification: pending_test
      test_ref: frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js::describe("Phase 2.5 INV-009/INV-010")
    - id: INV-010
      statement: "renderPeersHtml({M2:[...], M3:[...]}) 返回包含所有模块 label 和节点 name 的 HTML 字符串；模块按字母序排序，同模块内节点按 name 字母序排序；HTML 特殊字符被 escape"
      verification: pending_test
      test_ref: frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js::describe("Phase 2.5 INV-009/INV-010")
    - id: INV-011
      statement: "graph 重建循环（watch [moduleId, nodes, edges] 触发 destroy→create）完成后，如果当前 focusedNodeId.value 非空，新 graph 实例的 setElementState 必须被重放调用至少一次，参数反映当前焦点关系（R1 F004 护栏）"
      verification: pending_test
      test_ref: frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js::it("F004 graph rebuild: createGraph replays focus state after destroy/create cycle")

  counter_examples:
    - id: CE-004
      scenario: "relatedNodeIds 只处理 e.source===focus 方向，遗漏 e.target===focus，导致焦点的前置节点被错误淡化"
      tests_that_still_pass: "焦点自身和后继包含性断言（如果错实现仍会 add 焦点本身和后继）"
      mitigation: "Task 1 测试构造 A→B 场景 focus=B，断言 relatedNodeIds.has('A')=true；破坏 source/target 任一方向分支时测试 fail"
    - id: CE-005
      scenario: "退出焦点（clearFocus() 或 focusedNodeId→null）时未清空 element state，状态泄漏到切模块/下次进入后仍显示为 faded"
      tests_that_still_pass: "进入焦点的 state map 断言（泄漏只在退出后才显现）"
      mitigation: "Task 2 测试用 wrapper.vm.clearFocus() 触发退出，断言 graph.setElementState spy 最后一次调用 args[0]==={}；破坏清空分支时测试精确 fail"
    - id: CE-006
      scenario: "renderPeersHtml(null) 或 renderPeersHtml({}) 崩溃（直接 Object.entries(null) 或未过滤空列表）"
      tests_that_still_pass: "多模块多节点 happy path 断言"
      mitigation: "Task 3 显式测试 null/undefined/{}/{M2:[]} 四种退化输入均返回空字符串"
    - id: CE-007
      scenario: "buildG6Data 和 relatedEdgeIds 使用不同的边过滤规则（一个按过滤后索引，一个按原始索引），导致 edge-${i} 命中错误 element（F003 根因）"
      tests_that_still_pass: "常规 happy path 测试（nodes 和 edges 完全对齐时两种规则结果相同）"
      mitigation: "Task 1 新增 dangling edge 测试：构造 target='GHOST' 不在 nodes 集合的边，验证 buildVisibleEdgeList helper 的过滤索引与 buildG6Data 一致；破坏 helper 共用约定时测试精确 fail"
    - id: CE-008
      scenario: "watch [moduleId, nodes, edges] 触发 destroy→create 循环后，createGraph 末尾不重放焦点 state，导致用户焦点仍在但新 graph 显示全不透明（F004 根因）"
      tests_that_still_pass: "单次进入焦点的 state map 断言（不涉及 graph 重建）"
      mitigation: "Task 2 新增 F004 重放测试：focus B 后 setProps 改 nodes 触发重建，断言新 graph 实例的 setElementState 被额外调用且参数含当前焦点；删除 createGraph 末尾 replay 分支时测试精确 fail"

  risk_modules:
    - module: frontend/src/components/knowledge-tree/ConceptMapPanel.vue
      reason: "Phase 2.5 所有改动集中在此单一组件：新增 2 个 computed + updateElementStates + watch + Tooltip plugin + renderPeersHtml 纯函数；原 Phase 2 risk_module 继续生效"

  test_debt:
    - item: "ConceptMapPanel 焦点模式下的节点/边视觉淡化"
      phase_2_status: "deferred (Phase 2 plan.md:2242-2244)"
      phase_2_5_resolution: "resolved"
      phase_2_5_tasks: [T1, T2]
      phase_2_5_evidence: "INV-006/INV-007/INV-008 + CE-004/CE-005 测试覆盖"
    - item: "跨模块徽标悬停展开对端列表"
      phase_2_status: "deferred (Phase 2 plan.md:2245-2247)"
      phase_2_5_resolution: "resolved"
      phase_2_5_tasks: [T3]
      phase_2_5_evidence: "INV-009/INV-010 + CE-006 测试覆盖"
    - item: "桥接/对比边条件显示"
      phase_2_status: "deferred（隐含在 Phase 2 节点淡化条目内）"
      phase_2_5_resolution: "deferred"
      deferred_reason: "数据模型缺少 bridge/contrast edge type，等 Phase 3 edge schema 扩展"
      deferred_deadline: "Phase 3"
```

---

## 与 Phase 2 的兼容性

- **focusedNodeId 保持组件内部 ref**（R1 F001 硬约束）：不改为 prop，不破坏 Phase 2 事件驱动模式（node:click/clearFocus/focusPeer）
- **buildG6Data 改用 helper** 是本 Phase 唯一修改 Phase 2 既有函数的点：抽 `buildVisibleEdgeList()` helper，原始过滤逻辑语义不变（同一 visibleNodeIds 集合过滤），relatedEdgeIds 与 buildG6Data 共用 helper 保证 id 规则对齐（R1 F003 硬约束）
- **createGraph 末尾新增重放分支**（R1 F004）：`if (focusedNodeId.value) nextTick(updateElementStates)` — 语义上只在处于焦点态时生效，不改变空焦点的既有 createGraph 行为
- **不改 Phase 2 其它既有逻辑**：layoutEngine 调用 / G6 preset 布局 / 现有 crossModuleBadges 渲染 / destroyGraph / module watch 全部保持原样
- **不影响 Phase 2 Contract Pack**：INV-001 ~ INV-005、CE-001 ~ CE-003 的断言和对应测试继续全绿
- **defineExpose 增量扩展**（R1 F002 硬约束）：从 Phase 2 的 `{crossModuleBadges, crossModulePeers, focusedNodeId, clearFocus}` 增量扩展到 `{crossModuleBadges, crossModulePeers, focusedNodeId, clearFocus, relatedNodeIds, relatedEdgeIds, updateElementStates, renderPeersHtml}` — **严禁**删除 focusedNodeId 和 clearFocus（否则 Phase 2 多处测试红）
- **G6 mock 扩展**（R1 F005）：既有 Graph mock 的 constructor 内增加 `this.setElementState = vi.fn().mockResolvedValue(undefined)` 一行 — 不改其它现有 mock 行为
- **测试文件增量追加**：全部新测试放在 ConceptMapPanel.test.js 末尾的 `describe('Phase 2.5 ...')` 块内，不动 Phase 2 原测试
