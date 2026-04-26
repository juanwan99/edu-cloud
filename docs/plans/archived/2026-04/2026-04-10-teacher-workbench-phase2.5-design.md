# 知识图谱教师工作台 Phase 2.5 设计

> [2026-04-10 22:48:28 实现完成] Commits: b909ccf..f948089（Batch 1 实现 b909ccf + R2 test-gap 修复 f948089）。Gate 2 GPT 审查 R1 FAIL（F001/F002/F003 test-gap，全部 defect_fix）→ R2 PASS（三个 finding 终态 resolved-correct）。前端全量 17 files / 182 tests（Phase 2 160 + Phase 2.5 22）。视觉验收待用户手动确认（design §8 三条路径）。
>
> **前置：** Phase 2（本体）`docs/plans/2026-04-10-teacher-workbench-design.md` [实现完成]（commits 7a5ecfb..549e298）
>
> **范围：** 清理 Phase 2 Contract Pack 中记录的 2 条 test_debt——焦点模式节点淡化 + 跨模块徽标悬停展开 peer 列表。
>
> **独立 design 的理由：** Phase 2 design.md 已 `[实现完成]` 冻结；Phase 2.5 作为独立增量在新文件记录，避免 design_freeze_guard 拦截。

## §0 范围界定与非目标

### 本 Phase 覆盖

1. **焦点模式节点淡化**（对应 Phase 2 design.md:227-230 四项延后子弹）
   - 选中节点的 1 跳邻居节点保持完全不透明
   - 其他节点透明度降低到 30%
   - 与焦点不相关的边透明度降低到 20%
   - 相关的边（连接焦点节点和其邻居）视觉强调（粗细 +1px 或颜色）
2. **跨模块徽标悬停展开**（对应 Phase 2 design.md:194）
   - 节点右上角徽标 `→M2×3` 鼠标悬停时弹出对端节点名列表
   - 数据源：Batch 2 已 `defineExpose({crossModulePeers})`，无需新取数

### 明确不做（转交 Phase 3 或废弃）

- **桥接/对比边条件显示**（Phase 2 design.md:231）：**延后到 Phase 3**。当前边类型只有 `prerequisite_hard` / `prerequisite_soft`，没有 bridge/contrast 语义。等 Phase 3 edge schema 扩展后再处理。此条 test_debt 在本 Phase 的 plan Contract Pack 中统一标为 `deferred`，deadline=`Phase 3`，与 §7 保持一致（R1 修复 F007 语义矛盾）。
- **透明度过渡动画细调**：本 Phase 用 G6 `setElementState(id, state, true)` 默认动画时长（150ms），不暴露配置项。
- **键盘导航焦点切换**（Tab / 方向键跳选）：延后 Phase 3。
- **徽标悬停的点击打开 NodeDetailDrawer**：本 Phase 只做悬停展示，点击进入详情延后（如用户有需求再追加）。

## §1 前置能力 spike 结论

本 Phase 开工前对 `@antv/g6 ^5.1.0` API 做了一次 spike（无代码落盘，仅 `.d.ts` 读证）：

| 能力需求 | G6 v5.1 API | 证据 |
|---------|-------------|------|
| 节点/边状态驱动 style 切换 | `Graph.setElementState(id, state, animation?) : Promise<void>` + 批量重载 | `frontend/node_modules/@antv/g6/esm/runtime/graph.d.ts:1173-1182` |
| state → style 映射声明 | node/edge spec 支持 `state: { [stateName]: StyleProps }` | G6 v5.1 runtime element state 机制 |
| 悬停 tooltip | `@antv/g6` 内置 `Tooltip` plugin：`trigger: 'hover'` + `enable: (event, items) => boolean` + `getContent: (event, items) => HTMLElement \| string` | `frontend/node_modules/@antv/g6/esm/plugins/tooltip.d.ts:1-134` |

**结论**：Phase 2 test_debt 原因（"G6 API 不成熟"）**已不成立**，两项延后项可以实现，无架构风险，无新依赖。

## §2 核心决策（4 项）

### D1. 1 跳邻居的关系类型范围

**决策**：1 跳邻居 = 通过 `prerequisite_hard` ∪ `prerequisite_soft` 边连接的节点。

**理由**：
- 教师的视觉直觉是"前置依赖/后继"，不区分硬/软——两者都是认知前置链
- 跨模块（`external_hard_refs`）不纳入 1 跳，因为跨模块已通过节点右上徽标单独表达
- layoutEngine 只用 hard 边做 toposort 是另一回事（确定性布局算法），视觉高亮可以更宽

**反例**：如果只算 hard 边，含 soft 前置的概念（例如"细胞周期"有多个 soft prerequisites）在焦点模式下会看起来孤立，教师会误以为缺前置。

### D2. G6 v5 动态 style 更新方式

**决策**：`graph.setElementState(id, state, true)`（带动画）+ node/edge spec 的 `state: { ... }` 声明式配置。

**拒绝的替代方案**：
- ❌ `graph.updateNodeData()` 全量 rebuild：每次 focus 切换都重 diff，性能差且可能触发布局重算
- ❌ 自定义 canvas 层手动画：绕开 G6 体系，维护成本高

**状态名命名**：
- 节点：`'faded'`（透明度 30%）/ `'highlighted'`（可选，目前只做"非相关变淡"，焦点本身保持 default）
- 边：`'dimmed'`（透明度 20%）/ `'emphasized'`（lineWidth + 1px）
- 清空焦点时调用 `graph.setElementState({}, true)` 批量清零

**不变量**：退出焦点后所有 element 无 state（回到 default style），不允许状态泄漏。

### D3. 桥接/对比边的处理

**决策**：作废，不在 Phase 2.5 范围。

**理由**：Phase 1/2 edge schema 只有 `prerequisite_hard` / `prerequisite_soft`。"桥接"（bridge）"对比"（contrast）在当前数据模型中不存在，纯视觉实现是无源之水。

**落地动作**：在 Phase 2.5 plan.md 的 Contract Pack `test_debt` 段，将 Phase 2 原条目的 resolution 改为 `deferred`，reason=`"数据模型缺少 bridge/contrast edge type，待 Phase 3 扩展"`，deadline=`"Phase 3"`。

### D4. 徽标悬停 Tooltip 实现路径

**决策**：G6 v5 内置 `Tooltip` plugin，`trigger: 'hover'` + `enable` 谓词仅在徽标节点触发。

**配置要点**：
```js
{
  type: 'tooltip',
  key: 'badge-tooltip',
  trigger: 'hover',
  enable: (event, items) => {
    // 只在有跨模块徽标的节点触发
    const item = items[0]
    return !!(item && item.data && item.data.badgeText)
  },
  getContent: (event, items) => {
    const nodeId = items[0].id
    // peers: { M2: [{id, name}, ...], M3: [...] }
    const peers = crossModulePeers.value[nodeId] || {}
    return renderPeersHtml(peers)  // 返回 HTML 字符串
  },
  onOpenChange: (open) => { /* 可选日志 */ }
}
```

**`renderPeersHtml` 输出格式**：
```html
<div class="peer-tooltip">
  <div class="peer-section">
    <span class="peer-module">→ M2</span>
    <ul>
      <li>细胞膜流动性</li>
      <li>主动运输</li>
    </ul>
  </div>
  <div class="peer-section">
    <span class="peer-module">→ M3</span>
    <ul><li>基因表达</li></ul>
  </div>
</div>
```

**拒绝的替代方案**：
- ❌ Naive UI `NPopover`：需要手动坐标转换（canvas → 屏幕），复杂
- ❌ 自研 DOM 浮层：重复造轮子

## §3 组件与数据流

### 依赖关系

```
ConceptMapPanel.vue（单一改动点）
├── props 不变
├── 新增 computed: relatedNodeIds, relatedEdgeIds（依赖 focusedNodeId + props.edges）
├── 新增 watch: focusedNodeId → updateElementStates()
├── 新增 function: updateElementStates()（调 graph.setElementState）
├── 新增 function: renderPeersHtml(peers)（纯函数，返回 HTML 字符串）
└── G6 Graph 配置扩展:
    ├── node.state.faded = { opacity: 0.3 }
    ├── edge.state.dimmed = { opacity: 0.2 }
    ├── edge.state.emphasized = { lineWidth: +1 }
    └── plugins: [{ type: 'tooltip', ... }]
```

### `relatedNodeIds` 计算规则

> **R2 修复 F008**: 数据源是组件内部 `focusedNodeId` ref（与 Phase 2 现状一致），不是 prop。

```js
const relatedNodeIds = computed(() => {
  const focus = focusedNodeId.value  // 内部 ref
  if (!focus) return new Set()
  const related = new Set([focus])  // 焦点自身算相关
  for (const e of props.edges) {
    if (e.type !== 'prerequisite_hard' && e.type !== 'prerequisite_soft') continue
    if (e.source === focus) related.add(e.target)  // 后继
    if (e.target === focus) related.add(e.source)  // 前置
  }
  return related
})
```

**纯函数属性**：
- 返回 Set 实例（测试断言用 `has()` / `size`）
- 无 Math.random / Date.now / 副作用
- 输入相同 → 输出相同（Set 内容同）

### `relatedEdgeIds` 计算规则

> **R2 修复 F008**: 使用 `buildVisibleEdgeList()` helper 的 `visibleId`，与 `buildG6Data` 过滤后索引严格对齐（避免 dangling edge 导致的索引偏移）。

```js
const relatedEdgeIds = computed(() => {
  const focus = focusedNodeId.value  // 内部 ref
  if (!focus) return new Set()
  const related = new Set()
  for (const { originalEdge: e, visibleId } of buildVisibleEdgeList()) {
    if (e.type !== 'prerequisite_hard' && e.type !== 'prerequisite_soft') continue
    if (e.source === focus || e.target === focus) {
      related.add(visibleId)  // edge-${visibleIndex}，与 buildG6Data 共用 helper
    }
  }
  return related
})
```

**约束**：edge id 必须与 `ConceptMapPanel.buildG6Data()` 生成的 id 规则一致（均通过 `buildVisibleEdgeList()` helper 产出 `edge-${visibleIndex}`，visibleIndex 是过滤 dangling edge 后的连续索引）。Task 1 新增 dangling-edge 回归测试 protects this alignment（见 plan Task 1 测试 6）。

### `updateElementStates()` 行为

```js
// R1 修复 F001/F002: focusedNodeId 是组件内部 ref（与 Phase 2 现状一致），不是 prop
// R1 修复 F003: 边 id 规则须与 buildG6Data() 过滤后索引一致 — 用共用 helper
// R1 修复（API 核对）: G6 Graph 无 getElementDataById 公开 API — 改用可见 edge helper 的返回集判断

function buildVisibleEdgeList() {
  // R1 helper: 返回 [{originalEdge, visibleIndex, visibleId}]
  // 与 buildG6Data 共用同一过滤规则（visibleIds 节点集合）
  const visibleNodeIds = new Set(props.nodes.map(n => n.id))  // 与 buildG6Data 对齐
  const out = []
  let visibleIdx = 0
  for (const e of props.edges) {
    if (!visibleNodeIds.has(e.source) || !visibleNodeIds.has(e.target)) continue
    out.push({ originalEdge: e, visibleIndex: visibleIdx, visibleId: `edge-${visibleIdx}` })
    visibleIdx++
  }
  return out
}

function updateElementStates() {
  if (!graph) return
  if (!focusedNodeId.value) {
    // 退出焦点：清空所有 state（反 state 泄漏，CE-005 护栏）
    try { graph.setElementState({}, true) }
    catch (err) { console.warn('[ConceptMapPanel] clear state failed:', err) }
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
  try { graph.setElementState(stateMap, true) }
  catch (err) { console.warn('[ConceptMapPanel] apply state failed:', err) }
}
```

**生命周期绑定（R1 修复 F004）**：
- `watch(focusedNodeId, () => nextTick(updateElementStates))` — 监听组件内部 ref
- `createGraph()` 末尾：如果当前 `focusedNodeId.value` 非空，`nextTick(updateElementStates)` 重放状态，避免 `watch([moduleId, nodes, edges], destroy→create)` 触发时焦点视觉丢失
- `onUnmounted`：destroyGraph 已清理 graph 引用；state 自然消失
- 切换 module 时：既有 `watch(() => props.moduleId, () => focusedNodeId.value=null)` 会清焦点，随后 destroy→create 产生全新 graph，无残留

**与 Phase 2 接口不变**：`focusedNodeId` 仍是组件内部 ref，`clearFocus()` 仍存在；`defineExpose` 只增量扩展，保留 Phase 2 已暴露的 `focusedNodeId` 和 `clearFocus`。

## §4 失败路径与回退

| 故障场景 | 行为 | 回退策略 |
|---------|------|---------|
| `graph.setElementState` 抛异常（G6 内部 bug）| console.warn + 当次 updateElementStates 静默失败 | 不中断焦点模式 UX；overlay 仍正常工作 |
| `crossModulePeers.value` 为空对象 | `enable` 谓词返回 false，tooltip 不触发 | 正常行为（无徽标节点） |
| `renderPeersHtml` 输入畸形（peers 非对象）| 返回空字符串 `''` | tooltip 显示空框；需写测试覆盖此分支 |
| 节点 id 冲突 G6 内置 state 名 | 本设计状态名 `faded` / `dimmed` / `emphasized` 与 G6 保留态无冲突（G6 保留 `selected` / `active` / `disabled`）| N/A |

## §5 测试策略（概要，细节在 plan.md）

新增测试对应的不变量：

- **INV-006**: `relatedNodeIds` 计算纯函数确定性 + 包含焦点自身 + 硬软边都覆盖 + 无 focusedNodeId 时返回空 Set
- **INV-007**: 进入焦点 → `graph.setElementState` 被调用，state map 中非相关节点 = `['faded']`，相关节点 = `[]`
- **INV-008**: 退出焦点（focusedNodeId → null）→ `graph.setElementState({}, true)` 被调用一次清空
- **INV-009**: Tooltip plugin 的 `enable` 谓词对无 badgeText 的节点返回 false，对有徽标的返回 true
- **INV-010**: `renderPeersHtml({M2: [{id:'x', name:'A'}], M3: [{id:'y', name:'B'}]})` 输出含 `→ M2`、`A`、`→ M3`、`B` 四个文本片段

反例（CE）：

- **CE-004**: relatedNodeIds 遗漏反向边（只处理 `e.source===focus`，漏掉 `e.target===focus`）→ 前置节点被淡化 → 测试必须构造 A→B→C 然后 focus B，断言 A 和 C 都在 related 集内
- **CE-005**: 退出焦点后未清空 state，state 泄漏到下次进入 → 测试断言退出时 `setElementState` 被调用且参数为空对象 `{}`
- **CE-006**: `renderPeersHtml` 对 null 输入崩溃 → 测试 `renderPeersHtml(null)` 和 `renderPeersHtml({})` 返回空字符串不抛错

## §6 架构适配检查

| 维度 | 结论 |
|------|------|
| 职责单一 | ConceptMapPanel 增量，不拆新文件（除非 `renderPeersHtml` 独立为纯函数模块——本设计倾向放在同文件 `<script setup>` 外以便单测） |
| 依赖方向 | 无变化：ConceptMapPanel → layoutEngine（已有）+ @antv/g6 |
| 接口隔离 | `defineExpose` 已暴露 `crossModuleBadges` / `crossModulePeers`（Batch 2），新增 expose `relatedNodeIds` / `relatedEdgeIds` 供测试访问 |
| 配置集中 | 状态名 / 透明度阈值硬编码在 ConceptMapPanel（Phase 2.5 不引入配置系统） |
| 单功能影响面 | 仅 1 个源文件（ConceptMapPanel.vue）+ 1 个测试文件扩展（ConceptMapPanel.test.js）。满足"单功能变更影响 ≤3 文件"约束 |

## §7 Phase 2 Contract Pack 的 test_debt 处置

Phase 2.5 实施完成后，须**新增** Phase 2.5 plan.md 的 Contract Pack，其中 test_debt 段对原 Phase 2 的两条条目做最终处置：

```yaml
test_debt:
  - item: "ConceptMapPanel 焦点模式下的节点/边视觉淡化"
    phase_2_status: "deferred"
    phase_2_5_resolution: "resolved"
    phase_2_5_tasks: [T1, T2]
    phase_2_5_evidence: "INV-006/INV-007/INV-008 + CE-004/CE-005 测试覆盖"
  - item: "跨模块徽标悬停展开对端列表"
    phase_2_status: "deferred"
    phase_2_5_resolution: "resolved"
    phase_2_5_tasks: [T3]
    phase_2_5_evidence: "INV-009/INV-010 + CE-006 测试覆盖"
  - item: "桥接/对比边条件显示"
    phase_2_status: "deferred（隐含在节点淡化条目内）"
    phase_2_5_resolution: "deferred"
    deferred_reason: "数据模型缺少 bridge/contrast edge type，等 Phase 3 edge schema 扩展"
    deferred_deadline: "Phase 3"
```

## §8 验收路径（用户手动验证）

Phase 2.5 实施完成后，用户在浏览器 `http://localhost:5273/knowledge-tree` 验收三条路径：

1. **焦点淡化路径**：教师登录 → 进 M1 ConceptMap → 单击任一概念节点 → 底部 overlay 弹出 + **画布上非 1 跳邻居节点明显变淡**（30% opacity）+ 相关边粗化 + 无关边变淡；ESC 退出 → **所有节点/边恢复正常不透明**
2. **徽标悬停路径**：教师进入含跨模块关系的模块（M1 或 M2）→ 鼠标悬停在有 `→Mx×N` 徽标的节点 → **弹出 tooltip** 显示对端模块分组 + 节点 name 列表 → 移开鼠标 tooltip 消失
3. **切模块路径**：在焦点模式下切换模块（通过侧栏 TreeNavPanel 或返回概览）→ **新模块进入时无残留焦点状态**，所有节点正常不透明

**自治边界**：Phase 2.5 属视觉任务，Executor 不得自行声明"视觉验收通过"。必须：
- 输出"实现完成，待用户验收"状态
- 列出具体验收步骤供用户操作
- 禁止输出全绿汇总表

## §9 规模估计

| 文件 | 变更 | 估算 LOC |
|------|------|---------|
| `ConceptMapPanel.vue` | +relatedNodeIds/relatedEdgeIds/updateElementStates/renderPeersHtml/node&edge state spec/tooltip plugin 配置 | +120 ~ +150 |
| `ConceptMapPanel.test.js` | +INV-006..010 + CE-004..006 测试 | +150 ~ +200 |

总计 ~300 LOC，3 Tasks 1 Batch 足够。
