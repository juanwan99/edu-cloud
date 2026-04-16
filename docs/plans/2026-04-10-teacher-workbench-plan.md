# 知识图谱教师工作台 Phase 2 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 替换 G6 力导向 GraphPanel 为固定分层的教师工作台：ModuleOverviewPanel（5 模块卡片）+ ConceptMapPanel（BigConcept 分带 + 跨模块徽标）+ ConceptFocusOverlay（单击焦点面板）。

**Architecture:** 前端纯增量。自定义 JS toposort 算法 + BigConcept 分带坐标分配 → G6 preset 渲染。KnowledgeTreePage 按 `selectedModule` 分支切换 ModuleOverview/ConceptMap。Phase 1 审查工作台与 Tab 切换不变。

**Tech Stack:** Vue 3 (Composition API) + Naive UI + @antv/g6 ^5.1.0 (只用 preset layout) + Vitest + @vue/test-utils

**设计文档:** `docs/plans/2026-04-10-teacher-workbench-design.md`

---

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `frontend/src/components/knowledge-tree/layoutEngine.js` | 纯函数式布局算法：toposort + BigConcept 分带 + 坐标分配 |
| `frontend/src/components/knowledge-tree/ModuleStatCard.vue` | 单个模块卡片（概念数/大概念数/审核进度/质量徽章） |
| `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue` | 5 模块卡片 + 跨模块关系列表 |
| `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` | 骨架概念图主组件（G6 preset + 分带 + 徽标 + 交互） |
| `frontend/src/components/knowledge-tree/ConceptFocusOverlay.vue` | 单击节点后的焦点面板 |
| `frontend/src/__tests__/knowledge-tree/layoutEngine.test.js` | layoutEngine 单元测试 |
| `frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js` | ModuleOverviewPanel 组件测试 |
| `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` | ConceptMapPanel 组件测试 |
| `frontend/src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js` | ConceptFocusOverlay 组件测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/pages/KnowledgeTreePage.vue:35-42` | graph-side 按 `selectedModule` 分支：`all` → ModuleOverviewPanel / `Mx` → ConceptMapPanel |
| `frontend/src/components/knowledge-tree/useKnowledgeTree.js:42-46` | 新增 `loadAllModulesQuality()` 批量拉 5 模块质量数据 |

### 删除文件

| 文件 | 原因 |
|------|------|
| `frontend/src/components/knowledge-tree/GraphPanel.vue` | 替换为 ConceptMapPanel（single-version-discipline） |

---

## Batch 1: 基础算法与概览面板（Tasks 1-3）

### Task 1: layoutEngine.js（布局算法 + 单元测试）

**Files:**
- Create: `frontend/src/components/knowledge-tree/layoutEngine.js`
- Create: `frontend/src/__tests__/knowledge-tree/layoutEngine.test.js`

**测试契约:**
1. toposort 对硬 DAG 返回正确 rank
   - 入口: `computeLayout({ nodes, edges, bigConceptOrder })` 调用
   - 反例: 错误实现把所有节点都放在 rank=0——本测试断言 A→B 时 B.rank > A.rank
   - 边界: 空节点数组 / 单节点 / 线性链 / 分叉（一个节点多个后继）
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js`
2. 同输入多次调用返回完全相同的坐标（确定性）
   - 入口: `computeLayout(input)` 连续调用两次
   - 反例: 错误实现使用 Math.random 或 Set 迭代顺序不稳定——本测试比较两次输出 deep equal
   - 边界: 节点数 25 / 所有节点同 BigConcept / 每个节点独立 BigConcept
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js -t determinism`
3. 同 BigConcept 节点 Y 坐标落在对应 band 范围内
   - 入口: `computeLayout(input)` 返回 `{ positions, bands }`
   - 反例: 错误实现让节点 Y 跨越 band 边界——本测试断言每个节点的 Y 在 `bands[bcId].yMin..yMax` 范围内
   - 边界: band 数 1（所有节点同 BC）/ band 数 5 / 某 BigConcept 下只有 1 个节点
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js -t band`
4. 环形 DAG 降级为 rank+1 平铺
   - 入口: `computeLayout` 接收含环的输入（A→B→A）
   - 反例: 错误实现无限循环或崩溃——本测试断言函数正常返回且记录警告
   - 边界: 2 节点环 / 3 节点环 / 环外有自由节点
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js -t cycle`

- [ ] **Step 1: 写失败测试**

创建 `frontend/src/__tests__/knowledge-tree/layoutEngine.test.js`：

```javascript
import { describe, it, expect } from 'vitest'
import { computeLayout } from '../../components/knowledge-tree/layoutEngine'

const nodeA = { id: 'A', big_concept_id: 'BC1', module: 'M1' }
const nodeB = { id: 'B', big_concept_id: 'BC1', module: 'M1' }
const nodeC = { id: 'C', big_concept_id: 'BC2', module: 'M1' }
const hard = (src, tgt) => ({ source: src, target: tgt, type: 'prerequisite_hard' })

describe('layoutEngine', () => {
  describe('toposort rank', () => {
    it('empty nodes returns empty positions', () => {
      const result = computeLayout({ nodes: [], edges: [], bigConceptOrder: [] })
      expect(result.positions).toEqual({})
      expect(result.bands).toEqual({})
    })

    it('single node is centered', () => {
      const result = computeLayout({
        nodes: [nodeA], edges: [],
        bigConceptOrder: [{ id: 'BC1', name: 'BC 1' }],
      })
      expect(result.positions.A).toBeDefined()
      expect(result.positions.A.x).toBeGreaterThan(0)
      expect(result.positions.A.y).toBeGreaterThan(0)
    })

    it('linear chain A→B→C: ranks are 0,1,2', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB, nodeC],
        edges: [hard('A', 'B'), hard('B', 'C')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      // B 必须在 A 右边
      expect(result.positions.B.x).toBeGreaterThan(result.positions.A.x)
      expect(result.positions.C.x).toBeGreaterThan(result.positions.B.x)
    })

    it('diverging: A→B, A→C', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB, nodeC],
        edges: [hard('A', 'B'), hard('A', 'C')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      expect(result.positions.B.x).toBeGreaterThan(result.positions.A.x)
      expect(result.positions.C.x).toBeGreaterThan(result.positions.A.x)
    })
  })

  describe('determinism', () => {
    it('same input produces identical output on repeated calls', () => {
      const input = {
        nodes: [nodeA, nodeB, nodeC],
        edges: [hard('A', 'B')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      }
      const r1 = computeLayout(input)
      const r2 = computeLayout(input)
      expect(r1.positions).toEqual(r2.positions)
      expect(r1.bands).toEqual(r2.bands)
    })
  })

  describe('band layout', () => {
    it('nodes of same BigConcept fall within their band Y range', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB, nodeC],
        edges: [hard('A', 'B')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      const bc1Band = result.bands.BC1
      const bc2Band = result.bands.BC2
      expect(result.positions.A.y).toBeGreaterThanOrEqual(bc1Band.yMin)
      expect(result.positions.A.y).toBeLessThanOrEqual(bc1Band.yMax)
      expect(result.positions.B.y).toBeGreaterThanOrEqual(bc1Band.yMin)
      expect(result.positions.B.y).toBeLessThanOrEqual(bc1Band.yMax)
      expect(result.positions.C.y).toBeGreaterThanOrEqual(bc2Band.yMin)
      expect(result.positions.C.y).toBeLessThanOrEqual(bc2Band.yMax)
    })

    it('bands are ordered by bigConceptOrder', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeC],
        edges: [],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      // BC1 在 BC2 上方
      expect(result.bands.BC1.yMax).toBeLessThanOrEqual(result.bands.BC2.yMin)
    })
  })

  describe('cycle handling', () => {
    it('cycle does not crash, records warning', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB],
        edges: [hard('A', 'B'), hard('B', 'A')],
        bigConceptOrder: [{ id: 'BC1', name: 'BC 1' }],
      })
      expect(result.positions.A).toBeDefined()
      expect(result.positions.B).toBeDefined()
      expect(result.warnings).toContain('cycle_detected')
    })
  })
})
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js`
Expected: FAIL — layoutEngine 不存在

- [ ] **Step 3: 实现 layoutEngine.js**

创建 `frontend/src/components/knowledge-tree/layoutEngine.js`：

```javascript
/**
 * 知识图谱骨架布局算法（Phase 2）
 *
 * 输入：{ nodes, edges, bigConceptOrder }
 *   - nodes: [{ id, big_concept_id, module, ...其他字段 }]
 *   - edges: [{ source, target, type }]（只关心 prerequisite_hard）
 *   - bigConceptOrder: [{ id, name }]（按 display_order 排列）
 *
 * 输出：{ positions, bands, warnings }
 *   - positions: { [nodeId]: { x, y } }
 *   - bands: { [bigConceptId]: { yMin, yMax, label } }
 *   - warnings: string[]
 *
 * 算法：
 * 1. 过滤 hard DAG（只保留 prerequisite_hard 边，两端都在 nodes 内）
 * 2. Kahn toposort 计算每个节点的 rank
 * 3. 按 bigConceptOrder 顺序分配 band Y 范围
 * 4. band 内按 rank 排 X，同 rank 多节点 Y 微调避让
 */

// 布局常量
const CANVAS_WIDTH = 1200
const CANVAS_HEIGHT = 720
const LEFT_PADDING = 80
const RIGHT_PADDING = 80
const TOP_PADDING = 40
const BOTTOM_PADDING = 40
const BAND_GAP = 16
const COLUMN_WIDTH = 140
const NODE_HEIGHT = 44

export function computeLayout({ nodes, edges, bigConceptOrder }) {
  const positions = {}
  const bands = {}
  const warnings = []

  if (!nodes || nodes.length === 0) {
    return { positions, bands, warnings }
  }

  // Step 1: 构建 hard DAG adjacency（仅包含输入节点集合）
  const nodeIds = new Set(nodes.map(n => n.id))
  const adj = new Map()
  const inDegree = new Map()
  for (const n of nodes) {
    adj.set(n.id, [])
    inDegree.set(n.id, 0)
  }
  for (const e of edges || []) {
    if (e.type !== 'prerequisite_hard') continue
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) continue
    adj.get(e.source).push(e.target)
    inDegree.set(e.target, inDegree.get(e.target) + 1)
  }

  // Step 2: Kahn toposort 计算 rank
  const rank = new Map()
  const queue = []
  // 按 id 排序保证确定性
  const sortedIds = [...nodeIds].sort()
  for (const id of sortedIds) {
    if (inDegree.get(id) === 0) {
      queue.push(id)
      rank.set(id, 0)
    }
  }
  let head = 0
  while (head < queue.length) {
    const u = queue[head++]
    for (const v of adj.get(u).slice().sort()) {  // 按 id 排序
      const newRank = rank.get(u) + 1
      if (!rank.has(v) || rank.get(v) < newRank) {
        rank.set(v, newRank)
      }
      inDegree.set(v, inDegree.get(v) - 1)
      if (inDegree.get(v) === 0) {
        queue.push(v)
      }
    }
  }

  // 环检测：未分配 rank 的节点 = 有环
  const cyclicNodes = nodes.filter(n => !rank.has(n.id))
  if (cyclicNodes.length > 0) {
    warnings.push('cycle_detected')
    const maxRank = Math.max(0, ...Array.from(rank.values())) + 1
    for (const n of cyclicNodes) {
      rank.set(n.id, maxRank)
    }
  }

  // Step 3: 按 BigConcept 分组节点 + 分配 band
  const nodesByBC = new Map()
  for (const bc of bigConceptOrder) {
    nodesByBC.set(bc.id, [])
  }
  // 兜底：节点的 big_concept_id 不在 bigConceptOrder 中 → 归入"unknown" band
  for (const n of nodes) {
    const bcId = nodesByBC.has(n.big_concept_id) ? n.big_concept_id : null
    if (bcId) {
      nodesByBC.get(bcId).push(n)
    } else {
      if (!nodesByBC.has('__unknown__')) nodesByBC.set('__unknown__', [])
      nodesByBC.get('__unknown__').push(n)
    }
  }

  // 过滤空 band
  const activeBcs = bigConceptOrder.filter(bc => (nodesByBC.get(bc.id) || []).length > 0)
  if (nodesByBC.get('__unknown__')?.length > 0) {
    activeBcs.push({ id: '__unknown__', name: '未分类' })
  }

  if (activeBcs.length === 0) {
    return { positions, bands, warnings }
  }

  // Step 4: 分配 band Y 范围
  const usableHeight = CANVAS_HEIGHT - TOP_PADDING - BOTTOM_PADDING - BAND_GAP * (activeBcs.length - 1)
  const bandHeight = usableHeight / activeBcs.length
  let yCursor = TOP_PADDING
  for (const bc of activeBcs) {
    bands[bc.id] = {
      yMin: yCursor,
      yMax: yCursor + bandHeight,
      label: bc.name,
    }
    yCursor += bandHeight + BAND_GAP
  }

  // Step 5: band 内分配坐标
  const maxRank = Math.max(0, ...Array.from(rank.values()))
  const usableWidth = CANVAS_WIDTH - LEFT_PADDING - RIGHT_PADDING
  const effectiveCols = Math.max(1, maxRank + 1)
  const colWidth = maxRank === 0 ? COLUMN_WIDTH : Math.min(COLUMN_WIDTH, usableWidth / effectiveCols)

  for (const bc of activeBcs) {
    const bandNodes = nodesByBC.get(bc.id) || []
    // 按 rank 分桶
    const rankBuckets = new Map()
    for (const n of bandNodes) {
      const r = rank.get(n.id) ?? 0
      if (!rankBuckets.has(r)) rankBuckets.set(r, [])
      rankBuckets.get(r).push(n)
    }
    const band = bands[bc.id]
    const bandMidY = (band.yMin + band.yMax) / 2
    const availableVerticalSpread = Math.min(bandHeight * 0.7, NODE_HEIGHT * 3)

    for (const [r, bucket] of rankBuckets) {
      const x = LEFT_PADDING + r * colWidth + colWidth / 2
      // 同 rank 同 band 多节点 → Y 均匀分布在 band 中部
      // 按 id 排序保证确定性
      const sorted = bucket.slice().sort((a, b) => a.id.localeCompare(b.id))
      const count = sorted.length
      if (count === 1) {
        positions[sorted[0].id] = { x, y: bandMidY }
      } else {
        const step = availableVerticalSpread / (count - 1)
        const yStart = bandMidY - availableVerticalSpread / 2
        for (let i = 0; i < count; i++) {
          positions[sorted[i].id] = { x, y: yStart + i * step }
        }
      }
    }
  }

  return { positions, bands, warnings }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js`
Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/knowledge-tree/layoutEngine.js frontend/src/__tests__/knowledge-tree/layoutEngine.test.js
git commit -m "feat(knowledge-tree): layoutEngine — toposort + BigConcept band layout"
```

**边界条件:**
- 空节点数组 → 返回空 positions/bands，不报错
- 单节点 → 居中放置
- 所有节点 rank 相同（无 hard 边）→ 都在 col 0，Y 均匀分布
- 跨 band 的 hard 边 → 不影响布局算法，由渲染层画
- 节点 big_concept_id 不在 bigConceptOrder 中 → 归入 `__unknown__` band

**审查清单:**
- ✓ computeLayout 是纯函数（无副作用、无随机、无全局状态）
- ✓ 两次同输入返回完全相同的 positions 和 bands
- ✓ toposort 排序使用 id 字母序而非 Set 迭代顺序（保证确定性）
- ✓ 环节点降级为 rank+1 平铺，不抛异常
- ✗ 内部使用 Math.random 或 Date.now 导致不确定性
- ✗ 节点集合用 Set 遍历（JS Set 顺序依赖插入顺序，跨 JS 引擎可能不稳定）

---

### Task 2: ModuleStatCard.vue（单模块卡片）

**Files:**
- Create: `frontend/src/components/knowledge-tree/ModuleStatCard.vue`
- Create: `frontend/src/__tests__/knowledge-tree/ModuleStatCard.test.js`

**测试契约:**
1. 卡片渲染时展示模块名、概念数、大概念数、审核进度百分比
   - 入口: `mount(ModuleStatCard, { props: { moduleId, moduleName, conceptCount, bigConceptCount, reviewedCount } })`
   - 反例: 错误实现把 conceptCount 和 bigConceptCount 显示反了——本测试用明确数值（22/3）精确断言文本
   - 边界: conceptCount=0 / conceptCount=22 / reviewedCount=0 / reviewedCount=conceptCount（100%）
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleStatCard.test.js -t renders`
2. 点击卡片发射 select 事件
   - 入口: `wrapper.trigger('click')`
   - 反例: 错误实现发射错误事件名或未发射——本测试断言 `emitted('select')` 且无 payload
   - 边界: N/A
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleStatCard.test.js -t click`
3. 仅在 highCount/medCount > 0 时显示徽章
   - 入口: mount with 三种组合：都 >0 / HIGH=0,MED>0 / 都为 0
   - 反例: 错误实现总是渲染徽章（包括 0）或永不渲染——本测试用三组数据断言 DOM 条件渲染
   - 边界: highCount=0, medCount=0（无徽章）/ highCount=3, medCount=0 / highCount=0, medCount=5
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleStatCard.test.js -t badges`

- [ ] **Step 1: 实现 ModuleStatCard.vue**

```vue
<!-- frontend/src/components/knowledge-tree/ModuleStatCard.vue -->
<template>
  <n-card
    class="module-stat-card"
    hoverable
    :style="{ borderLeftColor: moduleColor }"
    @click="$emit('select')"
  >
    <div class="card-header">
      <span class="module-name">{{ moduleName }}</span>
    </div>
    <div class="stats-row">
      <div class="stat-item">
        <span class="stat-value">{{ conceptCount }}</span>
        <span class="stat-label">概念</span>
      </div>
      <div class="stat-item">
        <span class="stat-value">{{ bigConceptCount }}</span>
        <span class="stat-label">大概念</span>
      </div>
    </div>
    <div class="progress-section">
      <n-progress
        type="line"
        :percentage="reviewPercent"
        :height="6"
        :show-indicator="false"
        :color="progressColor"
      />
      <div class="progress-label">
        审核 {{ reviewedCount }}/{{ conceptCount }} ({{ reviewPercent }}%)
      </div>
    </div>
    <div class="badges" v-if="highCount > 0 || medCount > 0">
      <n-tag v-if="highCount > 0" type="error" size="small" round>
        ⚠ {{ highCount }} HIGH
      </n-tag>
      <n-tag v-if="medCount > 0" type="warning" size="small" round>
        ○ {{ medCount }} MED
      </n-tag>
    </div>
  </n-card>
</template>

<script setup>
import { computed } from 'vue'
import { NCard, NProgress, NTag } from 'naive-ui'

const MODULE_COLORS = {
  M1: '#6366f1', M2: '#8b5cf6', M3: '#ec4899', M4: '#f97316', M5: '#14b8a6',
}

const props = defineProps({
  moduleId: { type: String, required: true },
  moduleName: { type: String, required: true },
  conceptCount: { type: Number, default: 0 },
  bigConceptCount: { type: Number, default: 0 },
  reviewedCount: { type: Number, default: 0 },
  highCount: { type: Number, default: 0 },
  medCount: { type: Number, default: 0 },
})

defineEmits(['select'])

const moduleColor = computed(() => MODULE_COLORS[props.moduleId] || '#64748b')

const reviewPercent = computed(() => {
  if (props.conceptCount === 0) return 0
  return Math.round((props.reviewedCount / props.conceptCount) * 100)
})

const progressColor = computed(() => {
  if (reviewPercent.value >= 80) return '#22c55e'
  if (reviewPercent.value >= 40) return '#eab308'
  return '#94a3b8'
})
</script>

<style scoped>
.module-stat-card {
  cursor: pointer;
  border-left: 4px solid;
  transition: transform 0.15s;
}
.module-stat-card:hover {
  transform: translateY(-2px);
}
.card-header {
  margin-bottom: 12px;
}
.module-name {
  font-size: 16px;
  font-weight: 600;
}
.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}
.stat-item {
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-size: 20px;
  font-weight: 600;
}
.stat-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
}
.progress-section {
  margin-bottom: 12px;
}
.progress-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 4px;
}
.badges {
  display: flex;
  gap: 6px;
}
</style>
```

- [ ] **Step 2: 写 ModuleStatCard 测试**

```javascript
// frontend/src/__tests__/knowledge-tree/ModuleStatCard.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ModuleStatCard from '../../components/knowledge-tree/ModuleStatCard.vue'

describe('ModuleStatCard', () => {
  it('renders module name, counts, and progress', () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        conceptCount: 22, bigConceptCount: 3,
        reviewedCount: 12, highCount: 0, medCount: 0,
      },
    })
    expect(wrapper.text()).toContain('分子与细胞')
    expect(wrapper.text()).toContain('22')
    expect(wrapper.text()).toContain('3')
    // 审核进度 12/22 = 55%
    expect(wrapper.text()).toContain('12/22')
    expect(wrapper.text()).toContain('55%')
  })

  it('emits select on click', async () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        conceptCount: 22, bigConceptCount: 3, reviewedCount: 0,
      },
    })
    await wrapper.trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select').length).toBe(1)
  })

  it('shows 0% progress when conceptCount is 0', () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Empty',
        conceptCount: 0, bigConceptCount: 0, reviewedCount: 0,
      },
    })
    expect(wrapper.text()).toContain('0/0')
    expect(wrapper.text()).toContain('0%')
  })

  it('shows 100% progress when fully reviewed', () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Full',
        conceptCount: 10, bigConceptCount: 2, reviewedCount: 10,
      },
    })
    expect(wrapper.text()).toContain('10/10')
    expect(wrapper.text()).toContain('100%')
  })

  it('renders HIGH/MED badges only when counts > 0', () => {
    const withBoth = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Test',
        conceptCount: 5, bigConceptCount: 1, reviewedCount: 0,
        highCount: 3, medCount: 5,
      },
    })
    expect(withBoth.text()).toContain('3 HIGH')
    expect(withBoth.text()).toContain('5 MED')

    const medOnly = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Test',
        conceptCount: 5, bigConceptCount: 1, reviewedCount: 0,
        highCount: 0, medCount: 2,
      },
    })
    expect(medOnly.text()).not.toContain('HIGH')
    expect(medOnly.text()).toContain('2 MED')

    const none = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Test',
        conceptCount: 5, bigConceptCount: 1, reviewedCount: 0,
        highCount: 0, medCount: 0,
      },
    })
    expect(none.text()).not.toContain('HIGH')
    expect(none.text()).not.toContain('MED')
  })
})
```

- [ ] **Step 3: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ModuleStatCard.test.js`
Expected: 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/knowledge-tree/ModuleStatCard.vue frontend/src/__tests__/knowledge-tree/ModuleStatCard.test.js
git commit -m "feat(knowledge-tree): ModuleStatCard — single module stats display + tests"
```

**边界条件:**
- conceptCount=0 → reviewPercent=0，不报 NaN / division-by-zero
- conceptCount=100, reviewedCount=100 → 显示 100%
- highCount=0 且 medCount=0 → 徽章区域不渲染
- moduleId 不在 MODULE_COLORS 中 → 使用 fallback 颜色 `#64748b`

**审查清单:**
- ✓ 单一职责：纯展示组件，所有数据从 props 进来
- ✓ click 事件通过 emit('select') 向上传递
- ✓ MODULE_COLORS 常量与 Phase 1 GraphPanel 一致
- ✓ reviewPercent 在 conceptCount=0 时返回 0（避免 NaN）
- ✗ 组件内部直接调用 API（破坏纯展示）
- ✗ 样式写死颜色导致无法通过 props 主题化

---

### Task 3: ModuleOverviewPanel.vue + loadAllModulesQuality

**Files:**
- Create: `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue`
- Modify: `frontend/src/components/knowledge-tree/useKnowledgeTree.js:42-46`
- Create: `frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js`

**测试契约:**
1. ModuleOverviewPanel 渲染 5 个模块卡片
   - 入口: `mount(ModuleOverviewPanel, { props: { navigation, nodes, edges, moduleQuality } })`
   - 反例: 错误实现只渲染部分模块——本测试断言 DOM 中 5 张卡片
   - 边界: navigation 空数组（0 卡片）/ navigation 含 3 个模块（3 卡片）/ 5 模块完整
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js`
2. 点击卡片发射 select-module 事件
   - 入口: `wrapper.findAllComponents(ModuleStatCard)[0].trigger('click')`
   - 反例: 错误实现发射错误事件名或 payload——本测试断言 `wrapper.emitted('select-module')[0][0] === 'M1'`
   - 边界: 点击第一个卡片 / 点击最后一个卡片
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js -t select-module`
3. loadAllModulesQuality 并发调用 5 次 qualityCheck
   - 入口: `useKnowledgeTree().loadAllModulesQuality()`
   - 反例: 错误实现串行或跳过某模块——本测试断言 qualityCheck 被调 5 次，每次参数是 M1..M5
   - 边界: 部分模块 API 失败（依然等全部 settled）
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js -t loadAllModulesQuality`

- [ ] **Step 1: 修改 useKnowledgeTree.js 新增 loadAllModulesQuality**

在 `loadQuality` 函数后新增：

```javascript
  // 新增 state：5 模块质量聚合（ModuleOverviewPanel 消费）
  const modulesQuality = ref({})  // { M1: { highCount, medCount }, ... }

  async function loadAllModulesQuality() {
    const modules = ['M1', 'M2', 'M3', 'M4', 'M5']
    const results = await Promise.allSettled(
      modules.map(m => qualityCheck(m))
    )
    const next = {}
    results.forEach((r, i) => {
      const mod = modules[i]
      if (r.status === 'fulfilled') {
        const summary = r.value.data.summary?.issues_by_severity ?? {}
        next[mod] = { highCount: summary.HIGH ?? 0, medCount: summary.MED ?? 0 }
      } else {
        next[mod] = { highCount: 0, medCount: 0 }
      }
    })
    modulesQuality.value = next
  }
```

然后在 `return { ... }` 中加入 `modulesQuality, loadAllModulesQuality`。

- [ ] **Step 2: 写 useKnowledgeTree 测试**

在 `frontend/src/__tests__/knowledge-tree/useKnowledgeTree.test.js` 末尾新增：

```javascript
  it('loadAllModulesQuality calls qualityCheck for M1-M5', async () => {
    qualityCheck.mockResolvedValue({
      data: { module: 'M1', summary: { issues_by_severity: { HIGH: 1, MED: 2 } }, issues: [] },
    })
    const { loadAllModulesQuality, modulesQuality } = useKnowledgeTree()
    await loadAllModulesQuality()
    expect(qualityCheck).toHaveBeenCalledTimes(5)
    const calls = qualityCheck.mock.calls.map(c => c[0])
    expect(calls.sort()).toEqual(['M1', 'M2', 'M3', 'M4', 'M5'])
    expect(modulesQuality.value.M1).toEqual({ highCount: 1, medCount: 2 })
  })

  it('loadAllModulesQuality tolerates partial failures', async () => {
    qualityCheck
      .mockResolvedValueOnce({ data: { summary: { issues_by_severity: { HIGH: 1 } }, issues: [] } })
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue({ data: { summary: { issues_by_severity: {} }, issues: [] } })
    const { loadAllModulesQuality, modulesQuality } = useKnowledgeTree()
    await loadAllModulesQuality()
    expect(modulesQuality.value).toBeDefined()
    // M1 success, M2 failure → defaults
    const failedMod = Object.entries(modulesQuality.value).find(([, v]) => v.highCount === 0 && v.medCount === 0)
    expect(failedMod).toBeDefined()
  })
```

- [ ] **Step 3: 运行 composable 测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js -t loadAllModulesQuality`
Expected: 2 tests PASS

- [ ] **Step 4: 创建 ModuleOverviewPanel.vue**

```vue
<!-- frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue -->
<template>
  <div class="module-overview-panel">
    <div class="panel-header">
      <h2>知识图谱 · 全模块概览</h2>
      <n-button size="small" quaternary @click="$emit('refresh-quality')">刷新质量</n-button>
    </div>
    <div class="cards-grid">
      <ModuleStatCard
        v-for="mod in modulesData"
        :key="mod.id"
        :module-id="mod.id"
        :module-name="mod.name"
        :concept-count="mod.conceptCount"
        :big-concept-count="mod.bigConceptCount"
        :reviewed-count="mod.reviewedCount"
        :high-count="mod.highCount"
        :med-count="mod.medCount"
        @select="$emit('select-module', mod.id)"
      />
    </div>
    <div class="cross-module-section" v-if="crossModuleLinks.length > 0">
      <h3>模块间硬前置关系</h3>
      <div class="cross-module-list">
        <n-tag
          v-for="link in crossModuleLinks"
          :key="`${link.from}-${link.to}`"
          size="medium"
          round
        >
          {{ link.from }} → {{ link.to }} &nbsp; {{ link.count }} 条
        </n-tag>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NButton, NTag } from 'naive-ui'
import ModuleStatCard from './ModuleStatCard.vue'

const props = defineProps({
  navigation: { type: Array, default: () => [] },
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  modulesQuality: { type: Object, default: () => ({}) },
})
defineEmits(['select-module', 'refresh-quality'])

// 聚合每个模块的 stats
const modulesData = computed(() => {
  return props.navigation.map(mod => {
    const conceptIds = new Set()
    for (const bc of mod.big_concepts) {
      for (const cid of bc.concept_ids) conceptIds.add(cid)
    }
    const modNodes = props.nodes.filter(n => conceptIds.has(n.id))
    const reviewedCount = modNodes.filter(
      n => n.review_status === 'teacher_reviewed' || n.review_status === 'published'
    ).length
    const q = props.modulesQuality[mod.id] || { highCount: 0, medCount: 0 }
    return {
      id: mod.id,
      name: mod.name,
      conceptCount: conceptIds.size,
      bigConceptCount: mod.big_concepts.length,
      reviewedCount,
      highCount: q.highCount,
      medCount: q.medCount,
    }
  })
})

// 聚合跨模块硬前置关系
const crossModuleLinks = computed(() => {
  const nodeModule = {}
  for (const n of props.nodes) nodeModule[n.id] = n.module
  const counts = new Map()
  for (const e of props.edges) {
    if (e.type !== 'prerequisite_hard') continue
    const srcMod = nodeModule[e.source]
    const tgtMod = nodeModule[e.target]
    if (!srcMod || !tgtMod || srcMod === tgtMod) continue
    const key = `${srcMod}->${tgtMod}`
    counts.set(key, (counts.get(key) || 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([key, count]) => {
      const [from, to] = key.split('->')
      return { from, to, count }
    })
    .sort((a, b) => a.from.localeCompare(b.from) || a.to.localeCompare(b.to))
})
</script>

<style scoped>
.module-overview-panel {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.panel-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
.cross-module-section h3 {
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.6);
  margin: 0 0 12px;
}
.cross-module-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
```

- [ ] **Step 5: 写 ModuleOverviewPanel 测试**

```javascript
// frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ModuleOverviewPanel from '../../components/knowledge-tree/ModuleOverviewPanel.vue'
import ModuleStatCard from '../../components/knowledge-tree/ModuleStatCard.vue'

const mockNavigation = [
  { id: 'M1', name: '分子与细胞', big_concepts: [
    { id: 'BC1', name: 'BC 1', concept_ids: ['A', 'B'] },
  ]},
  { id: 'M2', name: '遗传与进化', big_concepts: [
    { id: 'BC2', name: 'BC 2', concept_ids: ['C'] },
  ]},
]
const mockNodes = [
  { id: 'A', module: 'M1', review_status: 'teacher_reviewed' },
  { id: 'B', module: 'M1', review_status: 'ai_draft' },
  { id: 'C', module: 'M2', review_status: 'published' },
]
const mockEdges = [
  { source: 'A', target: 'C', type: 'prerequisite_hard' },
]

describe('ModuleOverviewPanel', () => {
  it('renders one card per navigation module', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {} },
    })
    const cards = wrapper.findAllComponents(ModuleStatCard)
    expect(cards.length).toBe(2)
  })

  it('emits select-module on card click', async () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {} },
    })
    const cards = wrapper.findAllComponents(ModuleStatCard)
    await cards[0].trigger('click')
    expect(wrapper.emitted('select-module')).toBeTruthy()
    expect(wrapper.emitted('select-module')[0]).toEqual(['M1'])
  })

  it('aggregates cross-module hard prerequisite links', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {} },
    })
    expect(wrapper.text()).toContain('M1')
    expect(wrapper.text()).toContain('M2')
    expect(wrapper.text()).toContain('1 条')
  })

  it('uses modulesQuality to populate high/med counts', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: {
        navigation: mockNavigation, nodes: mockNodes, edges: mockEdges,
        modulesQuality: { M1: { highCount: 3, medCount: 5 } },
      },
    })
    expect(wrapper.text()).toContain('3 HIGH')
    expect(wrapper.text()).toContain('5 MED')
  })
})
```

- [ ] **Step 6: 运行组件测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js`
Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue frontend/src/components/knowledge-tree/useKnowledgeTree.js frontend/src/__tests__/knowledge-tree/
git commit -m "feat(knowledge-tree): ModuleOverviewPanel + loadAllModulesQuality composable"
```

**边界条件:**
- navigation 为空 → 渲染零卡片，不报错
- modulesQuality 缺某模块 key → 该卡片显示 0 HIGH/0 MED
- 无跨模块硬前置 → crossModuleLinks 为空，该 section 不渲染
- 部分 quality API 失败 → loadAllModulesQuality 使用 Promise.allSettled，失败模块填 0

**审查清单:**
- ✓ 卡片数据从 navigation + nodes 聚合计算（computed）
- ✓ 跨模块关系从 edges 聚合（排除同模块）
- ✓ loadAllModulesQuality 用 Promise.allSettled，部分失败不阻塞整体
- ✓ select-module 事件 payload 是 module id 字符串
- ✗ 组件内直接调 API（违反纯展示原则）
- ✗ 跨模块聚合用对象而非 Map，丢失顺序确定性

---

## Batch 2: ConceptMapPanel + Focus + Integration（Tasks 4-6）

### Task 4: ConceptMapPanel.vue（骨架概念图）

**Files:**
- Create: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`
- Create: `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`

**测试契约:**
1. ConceptMapPanel 使用 layoutEngine 计算位置
   - 入口: `mount(ConceptMapPanel, { props: { module: 'M1', nodes, edges, navigation } })`
   - 反例: 错误实现用 G6 默认布局不调 layoutEngine——本测试断言 computeLayout 被调用且传入 nodes/edges/bigConceptOrder
   - 边界: nodes 为空 / 单节点 / module 切换后重算
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t layoutEngine`
2. 头部工具栏显示正确的模块名和审核进度
   - 入口: mount 后检查 DOM 文本
   - 反例: 错误实现显示硬编码字符串或错的统计——本测试用已知数据断言文本精确匹配
   - 边界: 所有节点未审核（0%）/ 全部审核（100%）
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t toolbar`
3. 返回概览按钮 emit back-to-overview
   - 入口: 点击 `← 返回概览` 按钮
   - 反例: 错误实现不 emit 或 emit 错误事件——本测试断言 emitted('back-to-overview')
   - 边界: N/A
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t back`

- [ ] **Step 1: 创建 ConceptMapPanel.vue**

```vue
<!-- frontend/src/components/knowledge-tree/ConceptMapPanel.vue -->
<template>
  <div class="concept-map-panel">
    <div class="panel-toolbar">
      <n-button size="small" quaternary @click="$emit('back-to-overview')">
        ← 返回概览
      </n-button>
      <div class="toolbar-title">
        <span class="module-dot" :style="{ background: moduleColor }" />
        {{ moduleName }}
      </div>
      <div class="toolbar-stats">
        <span>审核 {{ reviewedCount }}/{{ totalCount }}</span>
        <n-tag v-if="highCount > 0" type="error" size="small" round>⚠ {{ highCount }} HIGH</n-tag>
        <n-tag v-if="medCount > 0" type="warning" size="small" round>○ {{ medCount }} MED</n-tag>
      </div>
      <n-button size="small" quaternary @click="$emit('refresh')">刷新</n-button>
    </div>
    <div class="map-container" ref="containerRef">
      <!-- BigConcept 分带背景 -->
      <svg class="band-layer" :width="1200" :height="720" preserveAspectRatio="xMidYMid meet">
        <g v-for="(band, bcId) in layout.bands" :key="bcId">
          <rect
            :x="0" :y="band.yMin - 8"
            :width="1200" :height="band.yMax - band.yMin + 16"
            :fill="moduleColor" fill-opacity="0.06"
          />
          <rect
            :x="0" :y="band.yMin - 8"
            :width="4" :height="band.yMax - band.yMin + 16"
            :fill="moduleColor" fill-opacity="0.8"
          />
          <text
            :x="12" :y="band.yMin + 8"
            fill="rgba(255,255,255,0.65)" font-size="13" font-weight="500"
          >{{ band.label }}</text>
        </g>
      </svg>
      <div ref="g6ContainerRef" class="g6-container" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { NButton, NTag } from 'naive-ui'
import { Graph } from '@antv/g6'
import { computeLayout } from './layoutEngine'

const MODULE_COLORS = {
  M1: '#6366f1', M2: '#8b5cf6', M3: '#ec4899', M4: '#f97316', M5: '#14b8a6',
}
const REVIEW_COLORS = {
  ai_draft: '#64748b',
  teacher_reviewed: '#3b82f6',
  published: '#22c55e',
}

const props = defineProps({
  moduleId: { type: String, required: true },
  moduleName: { type: String, required: true },
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  navigation: { type: Array, default: () => [] },
  qualityIssues: { type: Array, default: () => [] },
  focusedNodeId: { type: String, default: null },
})
const emit = defineEmits(['back-to-overview', 'refresh', 'node-click', 'node-focus'])

const containerRef = ref(null)
const g6ContainerRef = ref(null)
let graph = null

const moduleColor = computed(() => MODULE_COLORS[props.moduleId] || '#64748b')

// 从 navigation 取当前模块的 BigConcept 顺序
const bigConceptOrder = computed(() => {
  const mod = props.navigation.find(m => m.id === props.moduleId)
  return mod?.big_concepts?.map(bc => ({ id: bc.id, name: bc.name })) ?? []
})

// 计算布局
const layout = computed(() => {
  return computeLayout({
    nodes: props.nodes,
    edges: props.edges,
    bigConceptOrder: bigConceptOrder.value,
  })
})

// 统计
const totalCount = computed(() => props.nodes.length)
const reviewedCount = computed(() =>
  props.nodes.filter(n => n.review_status === 'teacher_reviewed' || n.review_status === 'published').length
)
const highCount = computed(() =>
  props.qualityIssues.filter(i => i.severity === 'HIGH').length
)
const medCount = computed(() =>
  props.qualityIssues.filter(i => i.severity === 'MED').length
)

// 跨模块徽标：数据源是 Phase 1 Graph API 的 node.external_hard_refs（module 过滤时才有值）
// 结构: external_hard_refs = { in: [{id, name, module}], out: [{id, name, module}] }
// 徽标显示 "out" 方向——本节点指向其他模块的概念
// 注意：Phase 1 后端在 module 过滤时会过滤掉跨模块 edge，所以不能扫 props.edges
const crossModuleBadges = computed(() => {
  const badgeMap = {}  // { nodeId: { M2: 3, M3: 1 } }
  for (const n of props.nodes) {
    const refs = n.external_hard_refs
    if (!refs || !refs.out || refs.out.length === 0) continue
    const byModule = {}
    for (const peer of refs.out) {
      if (!peer.module) continue
      byModule[peer.module] = (byModule[peer.module] || 0) + 1
    }
    if (Object.keys(byModule).length > 0) {
      badgeMap[n.id] = byModule
    }
  }
  return badgeMap
})

// 跨模块对端列表（悬停展开用）：{ nodeId: { M2: [{id,name}, ...] } }
const crossModulePeers = computed(() => {
  const peersMap = {}
  for (const n of props.nodes) {
    const refs = n.external_hard_refs
    if (!refs || !refs.out || refs.out.length === 0) continue
    const byModule = {}
    for (const peer of refs.out) {
      if (!peer.module) continue
      if (!byModule[peer.module]) byModule[peer.module] = []
      byModule[peer.module].push({ id: peer.id, name: peer.name })
    }
    peersMap[n.id] = byModule
  }
  return peersMap
})

function buildG6Data() {
  const positions = layout.value.positions
  const g6Nodes = props.nodes
    .filter(n => positions[n.id])
    .map(n => {
      const pos = positions[n.id]
      const reviewStatus = n.review_status || 'ai_draft'
      const badges = crossModuleBadges.value[n.id] || {}
      const badgeText = Object.entries(badges).map(([m, c]) => `→${m}×${c}`).join(' ')
      return {
        id: n.id,
        data: {
          label: n.name.length > 10 ? n.name.slice(0, 10) + '…' : n.name,
          fullName: n.name,
          badgeText,
          reviewStatus,
        },
        style: {
          x: pos.x,
          y: pos.y,
        },
      }
    })
  const visibleIds = new Set(g6Nodes.map(n => n.id))
  const g6Edges = props.edges
    .filter(e => visibleIds.has(e.source) && visibleIds.has(e.target))
    .map((e, i) => ({
      id: `edge-${i}`,
      source: e.source,
      target: e.target,
      data: { type: e.type },
    }))
  return { nodes: g6Nodes, edges: g6Edges }
}

function createGraph() {
  if (!g6ContainerRef.value) return
  const data = buildG6Data()
  graph = new Graph({
    container: g6ContainerRef.value,
    data,
    autoFit: 'view',
    layout: { type: 'preset' },
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
    },
    edge: {
      style: {
        stroke: d => {
          if (d.data.type === 'prerequisite_hard') return 'rgba(100,116,139,0.6)'
          if (d.data.type === 'prerequisite_soft') return 'rgba(100,116,139,0.35)'
          return 'rgba(99,102,241,0.3)'
        },
        lineDash: d => d.data.type === 'prerequisite_soft' ? [4, 3] : [0],
        endArrow: true,
        lineWidth: 1.5,
      },
    },
    behaviors: ['drag-canvas', 'zoom-canvas'],
  })
  graph.on('node:click', (evt) => {
    const nodeId = evt.target?.id
    if (nodeId) {
      const node = props.nodes.find(n => n.id === nodeId)
      if (node) emit('node-click', node)
    }
  })
  graph.render()
}

function destroyGraph() {
  if (graph) {
    graph.destroy()
    graph = null
  }
}

watch(() => [props.moduleId, props.nodes, props.edges], () => {
  destroyGraph()
  nextTick(createGraph)
}, { deep: true })

onMounted(() => nextTick(createGraph))
onUnmounted(destroyGraph)
</script>

<style scoped>
.concept-map-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.panel-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.toolbar-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  flex: 1;
}
.module-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.toolbar-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
}
.map-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}
.band-layer {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  z-index: 1;
}
.g6-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
}
</style>
```

- [ ] **Step 2: 写 ConceptMapPanel 测试**

```javascript
// frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Mock G6 Graph to avoid canvas rendering in jsdom
vi.mock('@antv/g6', () => ({
  Graph: vi.fn().mockImplementation(() => ({
    render: vi.fn(),
    destroy: vi.fn(),
    on: vi.fn(),
  })),
}))

import ConceptMapPanel from '../../components/knowledge-tree/ConceptMapPanel.vue'

const mockNavigation = [
  { id: 'M1', name: '分子与细胞', big_concepts: [
    { id: 'BC1', name: '细胞分子组成', concept_ids: ['A', 'B'] },
    { id: 'BC2', name: '细胞基本结构', concept_ids: ['C'] },
  ]},
]
const mockNodes = [
  { id: 'A', name: '蛋白质', module: 'M1', big_concept_id: 'BC1', review_status: 'teacher_reviewed' },
  { id: 'B', name: '酶', module: 'M1', big_concept_id: 'BC1', review_status: 'ai_draft' },
  { id: 'C', name: '细胞膜', module: 'M1', big_concept_id: 'BC2', review_status: 'published' },
]
const mockEdges = [
  { source: 'A', target: 'B', type: 'prerequisite_hard' },
]

describe('ConceptMapPanel', () => {
  it('renders toolbar with module name and review progress', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        nodes: mockNodes, edges: mockEdges, navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    expect(wrapper.text()).toContain('分子与细胞')
    expect(wrapper.text()).toContain('审核 2/3')
  })

  it('emits back-to-overview on back button click', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        nodes: mockNodes, edges: mockEdges, navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    const backBtn = wrapper.findAll('button').find(b => b.text().includes('返回概览'))
    expect(backBtn).toBeDefined()
    await backBtn.trigger('click')
    expect(wrapper.emitted('back-to-overview')).toBeTruthy()
  })

  it('renders BigConcept bands based on layoutEngine', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        nodes: mockNodes, edges: mockEdges, navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    expect(wrapper.html()).toContain('细胞分子组成')
    expect(wrapper.html()).toContain('细胞基本结构')
  })

  it('shows HIGH badge when quality issues contain HIGH', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        nodes: mockNodes, edges: mockEdges, navigation: mockNavigation,
        qualityIssues: [{ rule_id: 'Q1', severity: 'HIGH', message: 'test' }],
      },
    })
    expect(wrapper.text()).toContain('1 HIGH')
  })

  it('generates cross-module badges from node.external_hard_refs.out', () => {
    // 节点 B 有指向 M2/M3 的跨模块硬前置
    const nodesWithRefs = [
      { id: 'A', name: '蛋白质', module: 'M1', big_concept_id: 'BC1', review_status: 'ai_draft' },
      {
        id: 'B', name: '酶', module: 'M1', big_concept_id: 'BC1', review_status: 'ai_draft',
        external_hard_refs: {
          in: [],
          out: [
            { id: 'X1', name: '代谢', module: 'M2' },
            { id: 'X2', name: '调控', module: 'M2' },
            { id: 'Y1', name: '反馈', module: 'M3' },
          ],
        },
      },
      { id: 'C', name: '细胞膜', module: 'M1', big_concept_id: 'BC2', review_status: 'ai_draft' },
    ]
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        nodes: nodesWithRefs, edges: [], navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    // 断言 crossModuleBadges computed 产出正确结构
    // 通过暴露到 DOM 或通过 vm 检查
    const vm = wrapper.vm
    expect(vm.crossModuleBadges).toBeDefined()
    expect(vm.crossModuleBadges.B).toEqual({ M2: 2, M3: 1 })
    // 节点 A、C 无 external_hard_refs → 不在 badgeMap 中
    expect(vm.crossModuleBadges.A).toBeUndefined()
    expect(vm.crossModuleBadges.C).toBeUndefined()
  })

  it('crossModuleBadges empty when no nodes have external_hard_refs', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        nodes: mockNodes, edges: mockEdges, navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    expect(wrapper.vm.crossModuleBadges).toEqual({})
  })
})
```

为了让测试能访问 `crossModuleBadges`，在 `<script setup>` 末尾通过 `defineExpose` 暴露：

```javascript
defineExpose({ crossModuleBadges, crossModulePeers })
```

- [ ] **Step 3: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js`
Expected: 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/knowledge-tree/ConceptMapPanel.vue frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js
git commit -m "feat(knowledge-tree): ConceptMapPanel — G6 preset rendering + BigConcept bands + cross-module badges"
```

**边界条件:**
- nodes 为空 → layoutEngine 返回空 positions，band 层不渲染
- 所有 node 的 external_hard_refs 为 null → crossModuleBadges 为空对象
- moduleId 不在 navigation 中 → bigConceptOrder 为空，layoutEngine 返回空
- quality issues 全为 LOW → 工具栏不显示任何徽章
- module='all' → 后端不返回 external_hard_refs（Phase 1 契约），徽标自动为空

**测试契约（补充 F004）：**
5. 跨模块徽标生成基于 node.external_hard_refs.out
   - 入口: `mount(ConceptMapPanel, { props: { nodes: [...含 external_hard_refs...] } })`
   - 反例: 错误实现扫 props.edges 得到空徽标——本测试用已知 out=[M2,M2,M3] 断言 badgeMap={M2:2, M3:1}
   - 边界: 节点无 external_hard_refs / out 为空数组 / out 含同模块对端（不该发生但防御性测试）
   - 回归: 防止错误实现在 module 过滤场景下徽标永远为空
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t cross-module`

**审查清单:**
- ✓ layout 用 Vue computed 缓存（依赖 props 变化自动重算）
- ✓ G6 只用 preset layout，位置完全由 layoutEngine 决定
- ✓ BigConcept 分带用 SVG 在 G6 容器下层渲染
- ✓ moduleId/nodes/edges 变化时 destroy + 重建 graph
- ✓ crossModuleBadges 使用 `node.external_hard_refs.out`（Phase 1 契约），不扫 props.edges
- ✗ 布局数据直接在 buildG6Data 里重算（应该用 layout.value）
- ✗ crossModuleBadges 扫 props.edges 导致 module 过滤下永远为空（F002 修复）

---

### Task 5: ConceptFocusOverlay.vue（焦点模式）

**Files:**
- Create: `frontend/src/components/knowledge-tree/ConceptFocusOverlay.vue`
- Create: `frontend/src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js`
- Modify: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（集成 overlay + 键盘事件 + 画布空白点击退出；节点淡化延后 Phase 2.5）

**测试契约:**
1. ConceptFocusOverlay 显示选中概念的分组关系
   - 入口: `mount(ConceptFocusOverlay, { props: { concept, edges, allNodes } })`
   - 反例: 错误实现混淆方向（入边当出边）——本测试用 A→B 断言 A 的后继包含 B，B 的前置包含 A
   - 边界: 无任何关系 / 只有入边 / 只有出边 / 桥接+对比边
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js`
2. 点击关闭按钮发射 close 事件
   - 入口: 点击`关闭`按钮
   - 反例: 错误实现只 hide 不 emit——本测试断言 emitted('close')
   - 边界: N/A
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js -t close`
3. 查看详情按钮发射 view-detail 事件
   - 入口: 点击`查看详情`按钮
   - 反例: 错误实现调用全局 drawer——本测试断言 emitted('view-detail') 且 payload 是完整 concept 对象
   - 边界: N/A
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js -t view-detail`

- [ ] **Step 1: 创建 ConceptFocusOverlay.vue**

```vue
<!-- frontend/src/components/knowledge-tree/ConceptFocusOverlay.vue -->
<template>
  <div class="focus-overlay" v-if="concept">
    <div class="overlay-header">
      <div class="concept-title">
        <h3>{{ concept.name }}</h3>
        <n-tag :type="statusTagType" size="small">
          {{ statusLabel }}
        </n-tag>
      </div>
      <p v-if="concept.description" class="concept-desc">{{ concept.description }}</p>
    </div>
    <div class="relations-section">
      <div class="relation-group">
        <span class="group-label">前置依赖（{{ prereqs.length }}）</span>
        <span v-if="prereqs.length === 0" class="empty">无</span>
        <n-tag
          v-for="p in prereqs" :key="p.id"
          size="small" class="peer-tag"
          @click="$emit('focus-peer', p)"
        >← {{ p.name }}</n-tag>
      </div>
      <div class="relation-group">
        <span class="group-label">后继概念（{{ successors.length }}）</span>
        <span v-if="successors.length === 0" class="empty">无</span>
        <n-tag
          v-for="s in successors" :key="s.id"
          size="small" class="peer-tag"
          @click="$emit('focus-peer', s)"
        >→ {{ s.name }}</n-tag>
      </div>
      <div class="relation-group" v-if="bridgeContrast.length > 0">
        <span class="group-label">桥接/对比（{{ bridgeContrast.length }}）</span>
        <n-tag
          v-for="b in bridgeContrast" :key="b.id"
          size="small" :type="b.type === 'bridge_to' ? 'info' : 'warning'" class="peer-tag"
          @click="$emit('focus-peer', b)"
        >⇔ {{ b.name }}</n-tag>
      </div>
    </div>
    <div class="overlay-actions">
      <n-button size="small" @click="$emit('view-detail', concept)">查看详情</n-button>
      <n-button
        size="small" type="primary"
        :disabled="!canEdit || !canMarkReviewed"
        @click="$emit('mark-reviewed', concept)"
      >
        标为已审核
      </n-button>
      <n-button size="small" quaternary @click="$emit('close')">关闭</n-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NButton, NTag } from 'naive-ui'

const props = defineProps({
  concept: { type: Object, default: null },
  edges: { type: Array, default: () => [] },
  allNodes: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
})
defineEmits(['close', 'view-detail', 'mark-reviewed', 'focus-peer'])

const nodeMap = computed(() => {
  const m = {}
  for (const n of props.allNodes) m[n.id] = n
  return m
})

const prereqs = computed(() => {
  if (!props.concept) return []
  return props.edges
    .filter(e => e.type === 'prerequisite_hard' && e.target === props.concept.id)
    .map(e => nodeMap.value[e.source])
    .filter(Boolean)
})

const successors = computed(() => {
  if (!props.concept) return []
  return props.edges
    .filter(e => e.type === 'prerequisite_hard' && e.source === props.concept.id)
    .map(e => nodeMap.value[e.target])
    .filter(Boolean)
})

const bridgeContrast = computed(() => {
  if (!props.concept) return []
  return props.edges
    .filter(e =>
      (e.type === 'bridge_to' || e.type === 'contrast') &&
      (e.source === props.concept.id || e.target === props.concept.id)
    )
    .map(e => {
      const peerId = e.source === props.concept.id ? e.target : e.source
      const peer = nodeMap.value[peerId]
      return peer ? { ...peer, type: e.type } : null
    })
    .filter(Boolean)
})

const statusTagType = computed(() => {
  const s = props.concept?.review_status || 'ai_draft'
  if (s === 'published') return 'success'
  if (s === 'teacher_reviewed') return 'info'
  return 'default'
})
const statusLabel = computed(() => {
  const s = props.concept?.review_status || 'ai_draft'
  const labels = { ai_draft: '草稿', teacher_reviewed: '已审', published: '已发布' }
  return labels[s] || s
})

const canMarkReviewed = computed(() => {
  const s = props.concept?.review_status || 'ai_draft'
  return s === 'ai_draft'
})
</script>

<style scoped>
.focus-overlay {
  position: absolute;
  bottom: 16px;
  left: 15%;
  right: 15%;
  background: rgba(30, 30, 40, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  padding: 16px 20px;
  z-index: 20;
}
.overlay-header {
  margin-bottom: 12px;
}
.concept-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.concept-title h3 {
  margin: 0;
  font-size: 16px;
}
.concept-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
}
.relations-section {
  margin-bottom: 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.relation-group {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.group-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  min-width: 100px;
}
.empty {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
}
.peer-tag {
  cursor: pointer;
}
.overlay-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
```

- [ ] **Step 2: 写 ConceptFocusOverlay 测试**

```javascript
// frontend/src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConceptFocusOverlay from '../../components/knowledge-tree/ConceptFocusOverlay.vue'

const mockConcept = {
  id: 'B', name: '蛋白质', description: '生物大分子',
  review_status: 'ai_draft',
}
const mockAllNodes = [
  { id: 'A', name: '氨基酸' },
  { id: 'B', name: '蛋白质' },
  { id: 'C', name: '酶' },
  { id: 'D', name: '核糖体' },
  { id: 'E', name: '脂质' },
]
const mockEdges = [
  { source: 'A', target: 'B', type: 'prerequisite_hard' },  // A 是 B 的前置
  { source: 'B', target: 'C', type: 'prerequisite_hard' },  // C 是 B 的后继
  { source: 'B', target: 'D', type: 'prerequisite_hard' },  // D 是 B 的后继
  { source: 'B', target: 'E', type: 'contrast' },           // 对比
]

describe('ConceptFocusOverlay', () => {
  it('renders prerequisites and successors in correct direction', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    expect(wrapper.text()).toContain('前置依赖（1）')
    expect(wrapper.text()).toContain('氨基酸')
    expect(wrapper.text()).toContain('后继概念（2）')
    expect(wrapper.text()).toContain('酶')
    expect(wrapper.text()).toContain('核糖体')
  })

  it('renders bridge/contrast relations', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    expect(wrapper.text()).toContain('桥接/对比（1）')
    expect(wrapper.text()).toContain('脂质')
  })

  it('emits close when close button clicked', async () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    const closeBtn = wrapper.findAll('button').find(b => b.text() === '关闭')
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits view-detail with concept on view-detail button click', async () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    const detailBtn = wrapper.findAll('button').find(b => b.text() === '查看详情')
    await detailBtn.trigger('click')
    expect(wrapper.emitted('view-detail')).toBeTruthy()
    expect(wrapper.emitted('view-detail')[0][0]).toEqual(mockConcept)
  })

  it('mark-reviewed button disabled when canEdit=false', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: false },
    })
    const markBtn = wrapper.findAll('button').find(b => b.text() === '标为已审核')
    expect(markBtn.attributes('disabled')).toBeDefined()
  })

  it('mark-reviewed button disabled when concept is already reviewed', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: {
        concept: { ...mockConcept, review_status: 'teacher_reviewed' },
        edges: mockEdges, allNodes: mockAllNodes, canEdit: true,
      },
    })
    const markBtn = wrapper.findAll('button').find(b => b.text() === '标为已审核')
    expect(markBtn.attributes('disabled')).toBeDefined()
  })
})
```

- [ ] **Step 3: 运行测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js`
Expected: 6 tests PASS

- [ ] **Step 4: 集成 Overlay 到 ConceptMapPanel**

修改 ConceptMapPanel.vue：

在 `<template>` 的 `.map-container` 内、`.g6-container` 之后添加：

```vue
      <ConceptFocusOverlay
        v-if="focusedConcept"
        :concept="focusedConcept"
        :edges="edges"
        :all-nodes="nodes"
        :can-edit="canEdit"
        @close="clearFocus"
        @view-detail="$emit('view-detail', $event)"
        @mark-reviewed="$emit('mark-reviewed', $event)"
        @focus-peer="focusPeer"
      />
```

在 `<script setup>` 顶部新增 import：

```javascript
import ConceptFocusOverlay from './ConceptFocusOverlay.vue'
```

在 props 中新增 `canEdit`：

```javascript
const props = defineProps({
  moduleId: { type: String, required: true },
  moduleName: { type: String, required: true },
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  navigation: { type: Array, default: () => [] },
  qualityIssues: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits([
  'back-to-overview', 'refresh', 'node-click',
  'view-detail', 'mark-reviewed',
])
```

在 script 中新增 focus state 和方法：

```javascript
import { ref as vueRef } from 'vue'

const focusedNodeId = ref(null)
const focusedConcept = computed(() =>
  focusedNodeId.value ? props.nodes.find(n => n.id === focusedNodeId.value) : null
)

function handleNodeClick(node) {
  focusedNodeId.value = node.id
  // 同时 emit node-click 以便 KnowledgeTreePage 也能处理
  emit('node-click', node)
}

function clearFocus() {
  focusedNodeId.value = null
}

function focusPeer(peer) {
  focusedNodeId.value = peer.id
}

function onKeyDown(e) {
  if (e.key === 'Escape' && focusedNodeId.value) {
    clearFocus()
  }
}

onMounted(() => {
  nextTick(createGraph)
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  destroyGraph()
  window.removeEventListener('keydown', onKeyDown)
})
```

同时修改 G6 `graph.on('node:click')` 回调，改为调用本地 `handleNodeClick`。并新增画布空白点击退出焦点（F005 修复）：

```javascript
  graph.on('node:click', (evt) => {
    const nodeId = evt.target?.id
    if (nodeId) {
      const node = props.nodes.find(n => n.id === nodeId)
      if (node) handleNodeClick(node)
    }
  })

  // F005 修复：点击画布空白区域退出焦点模式
  graph.on('canvas:click', () => {
    if (focusedNodeId.value) {
      clearFocus()
    }
  })
```

模块切换时清除焦点：

```javascript
watch(() => props.moduleId, () => {
  focusedNodeId.value = null
})
```

- [ ] **Step 5: 运行 ConceptMapPanel 所有测试**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js`
Expected: 10 tests PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/knowledge-tree/ConceptFocusOverlay.vue frontend/src/components/knowledge-tree/ConceptMapPanel.vue frontend/src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js
git commit -m "feat(knowledge-tree): ConceptFocusOverlay + integrate into ConceptMapPanel with ESC key"
```

**边界条件:**
- concept 为 null → overlay 不渲染
- 节点无任何关系 → 前置/后继显示"无"
- canEdit=false → 标为已审核按钮禁用
- review_status 不是 ai_draft → 标为已审核按钮禁用（无可推进状态）
- ESC 键在焦点模式外不触发任何行为（focusedNodeId 为 null 时 noop）

**审查清单:**
- ✓ Overlay 独立组件，不访问外部 state
- ✓ 所有数据从 props 计算，关系方向（前置/后继）正确
- ✓ 模块切换时清除焦点（避免残留旧模块的 focus）
- ✓ ESC 键监听在 mount/unmount 对称
- ✗ Overlay 显示时 G6 画布节点没有淡化（视觉上无焦点效果——接受 Phase 2 v1 不做，留给 2.5）
- ✗ focus-peer 切换时 overlay 闪烁（接受 v1 硬切换）

---

### Task 6: KnowledgeTreePage 集成 + 删除 GraphPanel

**Files:**
- Modify: `frontend/src/pages/KnowledgeTreePage.vue`
- Delete: `frontend/src/components/knowledge-tree/GraphPanel.vue`

**入口状态机（F001 修复）：**

KnowledgeTreePage 有两层入口控制：
1. **外层 `showCards`**：控制是否显示旧 ModuleCards（家长/学生的掌握度卡片欢迎页）
2. **内层 `selectedModule`**：在 main-layout 内，`all` → ModuleOverviewPanel / `Mx` → ConceptMapPanel

**角色分支：**

| 角色 | canEdit | studentId | 默认入口 | 行为 |
|------|---------|-----------|---------|------|
| 教师 (platform_admin/subject_teacher 等) | true | null | 直接 main-layout（showCards=false） | `selectedModule='all'` → ModuleOverviewPanel（Phase 2 新默认） |
| 家长 (parent) | false | 有 | ModuleCards（showCards=true） | 点击模块 → main-layout + ConceptMapPanel(module=Mx) |
| 学生 (student) | false | 有 | ModuleCards（showCards=true） | 点击模块 → main-layout + ConceptMapPanel(module=Mx) |

**关键点：**
- Phase 2 不删除 ModuleCards 组件——它仍为家长/学生提供掌握度欢迎页
- Phase 2 ModuleOverviewPanel 是**教师专属**的默认入口（不显示掌握度，显示审核进度 + 质量问题）
- 教师通过 `init()` 中的 `!studentId.value && needsStudentSelector.value` 条件自动 `showCards.value = false`，直接进入 main-layout
- 家长/学生点击 ModuleCards 进入 main-layout 后，因为 `handleModuleSelect(mod)` 已设置 `selectedModule=mod` 且 `showCards=false`，会直接进入 ConceptMapPanel
- 家长/学生不会看到 ModuleOverviewPanel（因为他们点击 ModuleCards 时已经选了具体模块）

**验收路径（教师）：**
1. 教师登录 → init() → canEdit=true, studentId=null
2. `!studentId.value && needsStudentSelector.value` → `showCards.value = false`
3. main-layout 渲染，`selectedModule='all'`
4. graph-side 显示 ModuleOverviewPanel（因为 selectedModule='all'）

**验收路径（家长）：**
1. 家长登录 → init() → canEdit=false, studentId=有
2. showCards 保持 true → 渲染 ModuleCards（掌握度）
3. 家长点击模块 M1 → `handleModuleSelect('M1')` → showCards=false, selectedModule='M1'
4. main-layout 渲染，graph-side 显示 ConceptMapPanel(M1)

- [ ] **Step 1: 修改 KnowledgeTreePage.vue 集成新组件**

替换 `<template>` 中 `.graph-side` 内部的 GraphPanel 为条件渲染：

```vue
      <div class="graph-side">
        <div class="view-tabs" v-if="canEdit">
          <n-tabs v-model:value="activeTab" type="segment" size="small">
            <n-tab-pane name="graph" tab="图谱视图" />
            <n-tab-pane name="review" tab="审查工作台" />
          </n-tabs>
        </div>
        <template v-if="activeTab === 'graph'">
          <ModuleOverviewPanel
            v-if="selectedModule === 'all'"
            :navigation="navigationData"
            :nodes="nodesWithMastery"
            :edges="graphData.edges"
            :modules-quality="modulesQuality"
            style="flex: 1; min-height: 0"
            @select-module="handleModuleSelect"
            @refresh-quality="loadAllModulesQuality"
          />
          <ConceptMapPanel
            v-else
            :module-id="selectedModule"
            :module-name="currentModuleName"
            :nodes="nodesWithMastery"
            :edges="graphData.edges"
            :navigation="navigationData"
            :quality-issues="qualityIssues"
            :can-edit="canEdit"
            style="flex: 1; min-height: 0"
            @back-to-overview="handleBackToOverview"
            @refresh="handleRefreshModule"
            @node-click="handleNodeClick"
            @view-detail="handleNodeClick"
            @mark-reviewed="handleMarkReviewed"
          />
        </template>
        <RelationReviewPanel
          v-if="activeTab === 'review'"
          :nodes="nodesWithMastery"
          :edges="graphData.edges"
          :quality-issues="qualityIssues"
          :can-edit="canEdit"
          style="flex: 1; min-height: 0"
          @edit="handleEdit"
        />
      </div>
```

在 `<script setup>` 中替换 import：

```javascript
import { ref, computed, watch, onMounted } from 'vue'
import { NButton, NTabs, NTabPane, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { useKnowledgeTree } from '../components/knowledge-tree/useKnowledgeTree'
import ModuleCards from '../components/knowledge-tree/ModuleCards.vue'
import TreeNavPanel from '../components/knowledge-tree/TreeNavPanel.vue'
import ModuleOverviewPanel from '../components/knowledge-tree/ModuleOverviewPanel.vue'
import ConceptMapPanel from '../components/knowledge-tree/ConceptMapPanel.vue'
import NodeDetailDrawer from '../components/knowledge-tree/NodeDetailDrawer.vue'
import RelationReviewPanel from '../components/knowledge-tree/RelationReviewPanel.vue'
```

在 composable 解构中新增 `modulesQuality, loadAllModulesQuality`：

```javascript
const {
  navigationData, graphData, loading, selectedModule, moduleMastery,
  nodesWithMastery, qualityIssues, modulesQuality,
  loadGraph, loadMastery, loadQuality, loadAllModulesQuality, applyEdit,
} = useKnowledgeTree()
```

新增 computed / methods：

```javascript
const currentModuleName = computed(() => {
  const mod = navigationData.value.find(m => m.id === selectedModule.value)
  return mod?.name ?? selectedModule.value
})

async function handleBackToOverview() {
  selectedModule.value = 'all'
  await loadGraph('all')
  await loadAllModulesQuality()
}

async function handleRefreshModule() {
  await loadGraph(selectedModule.value)
  if (canEdit.value) {
    await loadQuality(selectedModule.value)
  }
}

async function handleMarkReviewed(concept) {
  // 推进 review_status: ai_draft → teacher_reviewed
  await handleEdit([{
    op: 'set_review_status', id: concept.id, status: 'teacher_reviewed',
  }])
}
```

修改 `init()`：

```javascript
async function init() {
  await loadGraph()
  if (canEdit.value) {
    await loadQuality(selectedModule.value)
    await loadAllModulesQuality()
  }
  if (studentId.value) {
    await loadMastery(studentId.value)
  }
  if (!studentId.value && needsStudentSelector.value) {
    showCards.value = false
  }
}
```

修改 `handleModuleSelect(mod)` — 确保模块切换到非 all 时不误触 overview：

```javascript
async function handleModuleSelect(mod) {
  showCards.value = false
  selectedModule.value = mod
  await loadGraph(mod)
  if (canEdit.value && mod !== 'all') {
    await loadQuality(mod)
  }
  if (canEdit.value && mod === 'all') {
    await loadAllModulesQuality()
  }
}
```

- [ ] **Step 2: 删除 GraphPanel.vue**

```bash
cd C:/Users/Administrator/edu-cloud
git rm frontend/src/components/knowledge-tree/GraphPanel.vue
```

- [ ] **Step 3: 全量前端测试确认无回归**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run`
Expected: 全部通过（包括 Phase 1 已有测试）

- [ ] **Step 4: 启动前端验证集成（人工验证）**

Run: `cd C:/Users/Administrator/edu-cloud/frontend && python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev`

验证清单（要求截图/文字描述）：
1. 打开 /knowledge-tree，默认看到 ModuleOverviewPanel（5 张模块卡片）
2. 点击 M1 卡片 → 切到 ConceptMapPanel，看到 BigConcept 分带
3. 点击节点 → 底部弹出 ConceptFocusOverlay
4. 按 ESC → overlay 关闭
5. 点击"返回概览" → 切回 ModuleOverviewPanel
6. 切换到"审查工作台" tab → 显示 Phase 1 的 RelationReviewPanel（无回归）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/KnowledgeTreePage.vue
git commit -m "feat(knowledge-tree): wire ModuleOverviewPanel + ConceptMapPanel into KnowledgeTreePage; remove GraphPanel"
```

**测试契约:**
1. module=all 时渲染 ModuleOverviewPanel，module=Mx 时渲染 ConceptMapPanel
   - 入口: KnowledgeTreePage mount with selectedModule='all' → ModuleOverviewPanel 存在；selectedModule='M1' → ConceptMapPanel 存在
   - 反例: 错误实现同时渲染两者或都不渲染——本测试用 `wrapper.findComponent(ModuleOverviewPanel).exists()` 精确断言
   - 边界: 初始 all / 切到 M1 / 从 M1 返回 all
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/KnowledgeTreePage.test.js -t routing`
2. 点击模块卡片触发 handleModuleSelect
   - 入口: wrapper emit 'select-module' with 'M1'
   - 反例: 错误实现未更新 selectedModule——本测试断言后续 findComponent(ConceptMapPanel).exists() === true
   - 边界: N/A
   - 回归: N/A
   - 命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/KnowledgeTreePage.test.js -t select-module`

**边界条件:**
- selectedModule 初始为 'all' → ModuleOverviewPanel 渲染
- 用户从 M1 点返回 → 切回 all → ModuleOverviewPanel 重新渲染
- canEdit=false → 审查工作台 tab 隐藏，但 ModuleOverview/ConceptMap 仍可用（都在 graph tab 内）
- loadAllModulesQuality 在非 canEdit 时不调用（节省 5 次 API 调用）

**审查清单:**
- ✓ 条件渲染严格互斥（v-if/v-else）
- ✓ GraphPanel.vue 被 git rm 删除
- ✓ 切换到 all 时重新调 loadAllModulesQuality
- ✓ handleMarkReviewed 走 handleEdit 路径，触发审核状态推进 + 后续刷新
- ✗ 删除 GraphPanel.vue 后仍有残留 import（需要检查）
- ✗ 模块切换时 ConceptMapPanel 没有 destroy 旧 graph（Task 4 的 watch 已覆盖）

---

## Contract Pack

```yaml
contract_pack:
  invariants:
    - id: INV-001
      statement: "computeLayout 是纯函数：同一 {nodes, edges, bigConceptOrder} 输入多次调用返回完全相同的 {positions, bands, warnings}"
      verification: pending_test
    - id: INV-002
      statement: "所有 prerequisite_hard 边两端节点的 X 坐标满足 target.x > source.x（rank 严格递增），除非环节点降级到 max rank+1"
      verification: pending_test
    - id: INV-003
      statement: "每个节点的 Y 坐标落在其 big_concept_id 对应的 band [yMin, yMax] 范围内"
      verification: pending_test
    - id: INV-004
      statement: "KnowledgeTreePage 在 selectedModule='all' 时只渲染 ModuleOverviewPanel，非 all 时只渲染 ConceptMapPanel，两者互斥"
      verification: pending_test
    - id: INV-005
      statement: "ConceptMapPanel 的 G6 Graph 使用 layout.type='preset'，节点位置完全由 computeLayout 决定，不允许 G6 重新排布"
      verification: pending_test

  counter_examples:
    - id: CE-001
      scenario: "computeLayout 使用 Math.random 或依赖 Set 迭代顺序——同输入多次调用返回不同坐标"
      tests_that_still_pass: "结构完整性测试（positions 有所有节点 key）"
      mitigation: "determinism 测试对比两次调用的 positions 深度相等"
    - id: CE-002
      scenario: "ConceptMapPanel 未调用 layoutEngine，使用 G6 内置 dagre 布局"
      tests_that_still_pass: "节点/边数量断言（G6 dagre 也能渲染所有节点）"
      mitigation: "断言 ConceptMapPanel 的 computed layout 来自 computeLayout；G6 Graph 配置 layout.type='preset'"
    - id: CE-003
      scenario: "ConceptFocusOverlay 混淆前置/后继方向（将入边当出边处理）"
      tests_that_still_pass: "关系数量断言（总数正确）"
      mitigation: "测试用 A→B 明确断言 B 的前置包含 A，B 的后继不包含 A"

  risk_modules:
    - module: frontend/src/components/knowledge-tree/layoutEngine.js
      reason: "核心算法模块：toposort 正确性 + 确定性保证 + 环检测，决定整个 Phase 2 的视觉输出；后续 Phase 2.5/3/4 都依赖此算法"
    - module: frontend/src/components/knowledge-tree/ConceptMapPanel.vue
      reason: "单一最大组件（~350 行）：集成 G6 渲染 + 布局算法 + 焦点模式 + 跨模块徽标 + 工具栏，回归面最广；跨模块徽标读取 Phase 1 API 的 node.external_hard_refs 契约"
    - module: frontend/src/pages/KnowledgeTreePage.vue
      reason: "顶层路由决策：all/module 互斥渲染 + 删除 GraphPanel + Phase 1 审查工作台共存 + showCards 角色分支"
    - module: frontend/src/components/knowledge-tree/useKnowledgeTree.js
      reason: "新增公共 composable API loadAllModulesQuality() + modulesQuality state，被 ModuleOverviewPanel/KnowledgeTreePage 消费"

  test_debt:
    - item: "ConceptMapPanel 焦点模式下的节点/边视觉淡化"
      reason: "v1 不做节点透明度变化（needs G6 节点 style 动态更新，开发成本高）。v1 仅通过 overlay 面板提供焦点信息"
      deadline: "2026-05-31"
    - item: "跨模块徽标悬停展开对端列表"
      reason: "G6 5.x 的节点 badge 点击/悬停 API 不成熟，v1 先展示徽标不做交互"
      deadline: "2026-05-31"
```
