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
      <ConceptFocusOverlay
        v-if="focusedConcept"
        :concept="focusedConcept"
        :edges="edges"
        :all-nodes="nodes"
        :can-edit="canEdit"
        @close="clearFocus"
        @view-detail="(c) => emit('view-detail', c)"
        @mark-reviewed="(c) => emit('mark-reviewed', c)"
        @focus-peer="focusPeer"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { NButton, NTag } from 'naive-ui'
import { Graph } from '@antv/g6'
import { computeLayout } from './layoutEngine'
import ConceptFocusOverlay from './ConceptFocusOverlay.vue'
import {
  heatmapColor,
  masteryColor,
  reviewStatusColor,
  nodeSizeFromImportance,
} from './heatmapUtils'

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
  canEdit: { type: Boolean, default: false },
  // Phase 1 T10: 节点着色模式
  colorMode: { type: String, default: 'exam_frequency' },
  // Phase 1 T10: 学生掌握度（colorMode='mastery' 时使用）
  nodesWithMastery: { type: Array, default: () => [] },
})
const emit = defineEmits([
  'back-to-overview', 'refresh', 'node-click',
  'view-detail', 'mark-reviewed',
])

const containerRef = ref(null)
const g6ContainerRef = ref(null)
let graph = null

const focusedNodeId = ref(null)
const focusedConcept = computed(() =>
  focusedNodeId.value ? props.nodes.find(n => n.id === focusedNodeId.value) : null
)

const moduleColor = computed(() => MODULE_COLORS[props.moduleId] || '#64748b')

const bigConceptOrder = computed(() => {
  const mod = props.navigation.find(m => m.id === props.moduleId)
  return mod?.big_concepts?.map(bc => ({ id: bc.id, name: bc.name })) ?? []
})

const layout = computed(() => {
  return computeLayout({
    nodes: props.nodes,
    edges: props.edges,
    bigConceptOrder: bigConceptOrder.value,
  })
})

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
  const badgeMap = {}
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

// Phase 2.5 R1 F003: 共享的可见边列表生成器
// 与 buildG6Data() 共用同一过滤规则：只保留 source 和 target 都在 props.nodes 集合内的边
// 返回 [{originalEdge, visibleIndex, visibleId}]，visibleId = `edge-${visibleIndex}`
// 三处共用（buildG6Data / relatedEdgeIds / updateElementStates）保证 id 规则对齐
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
// 数据源: 组件内部 focusedNodeId ref（Phase 2 既定事件驱动模式），不是 props
// CE-004 护栏: 必须同时处理 e.source===focus 和 e.target===focus 两个方向
// 1 跳邻居定义: prerequisite_hard ∪ prerequisite_soft（不含 external_hard_refs，后者走徽标）
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

// Phase 2.5 R1 F003: 使用 buildVisibleEdgeList 的 visibleId 与 buildG6Data 严格对齐
// 反例: dangling edge 会让原始索引偏移，导致 setElementState 打不中实际 element
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

function buildG6Data() {
  const positions = layout.value.positions
  const maxFreq = Math.max(1, ...props.nodes.map(n => n.exam_frequency || 0))
  const masteryMap = {}
  for (const m of props.nodesWithMastery || []) {
    if (m && m.id) masteryMap[m.id] = m.mastery_state || 'unseen'
  }

  const g6Nodes = props.nodes
    .filter(n => positions[n.id])
    .map(n => {
      const pos = positions[n.id]
      const reviewStatus = n.review_status || 'ai_draft'
      const badges = crossModuleBadges.value[n.id] || {}
      const badgeText = Object.entries(badges).map(([m, c]) => `→${m}×${c}`).join(' ')

      // Phase 1 T10: 节点大小反映 importance_score
      const importance = Number.isFinite(n.importance_score) ? n.importance_score : 0
      const size = nodeSizeFromImportance(importance)

      // Phase 1 T10: fill 按 colorMode 三分支
      let fill
      if (props.colorMode === 'mastery') {
        fill = masteryColor(masteryMap[n.id] || 'unseen')
      } else if (props.colorMode === 'review_status') {
        fill = reviewStatusColor(reviewStatus)
      } else { // exam_frequency (default)
        fill = heatmapColor(n.exam_frequency || 0, maxFreq)
      }

      return {
        id: n.id,
        data: {
          label: n.name.length > 10 ? n.name.slice(0, 10) + '…' : n.name,
          fullName: n.name,
          badgeText,
          reviewStatus,
          importance,
          examFrequency: n.exam_frequency || 0,
        },
        style: {
          x: pos.x,
          y: pos.y,
          size: [size, Math.round(size * 0.6)],
          fill,
        },
      }
    })
  // Phase 2.5 R1 F003: 边 id 规则通过 buildVisibleEdgeList helper 与 relatedEdgeIds 严格共用
  const g6Edges = buildVisibleEdgeList().map(({ originalEdge: e, visibleId }) => ({
    id: visibleId,
    source: e.source,
    target: e.target,
    data: { type: e.type },
  }))
  return { nodes: g6Nodes, edges: g6Edges }
}

function handleNodeClick(node) {
  focusedNodeId.value = node.id
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
      // Phase 2.5 INV-007: 焦点模式淡化非相关节点
      state: {
        faded: {
          opacity: 0.3,
        },
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
      // Phase 2.5 INV-007: 焦点模式强调相关边 / 淡化无关边
      state: {
        dimmed: {
          opacity: 0.2,
        },
        emphasized: {
          lineWidth: 2.5,
        },
      },
    },
    // Phase 2.5 INV-009 / D4: 徽标悬停 Tooltip plugin（enable 谓词 + async getContent）
    plugins: [
      {
        type: 'tooltip',
        key: 'badge-tooltip',
        trigger: 'hover',
        enable: (event, items) => {
          const item = items && items[0]
          return !!(item && item.data && item.data.badgeText)
        },
        getContent: async (event, items) => {
          const item = items && items[0]
          if (!item) return ''
          const nodeId = item.id
          return renderPeersHtml(crossModulePeers.value[nodeId] || {})
        },
      },
    ],
    behaviors: ['drag-canvas', 'zoom-canvas'],
  })
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
  graph.render()
  // Phase 2.5 R1 F004: 如果当前仍处于焦点态，destroy→create 后必须重放 state 到新 graph
  // 否则 nodes/edges 变化触发 watch 重建后，焦点 overlay 仍在但 G6 视觉全不透明
  if (focusedNodeId.value) {
    nextTick(updateElementStates)
  }
}

// Phase 2.5 INV-007/INV-008: 根据组件内部 focusedNodeId ref 批量更新节点/边 state
// - null: 批量清空所有 state（CE-005 反泄漏护栏）
// - 有值: 非相关节点 ['faded']，相关节点 []；非相关边 ['dimmed']，相关边 ['emphasized']
// R1 F001: 读 focusedNodeId.value（组件内部 ref），不是 props.focusedNodeId
// R1 F003: 边 id 通过 buildVisibleEdgeList helper 与 buildG6Data 严格对齐
function updateElementStates() {
  if (!graph) return
  if (!focusedNodeId.value) {
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

// Phase 2.5 INV-010 + CE-006: 生成 Tooltip HTML 内容的纯函数
// 输入: peers = { M2: [{id, name}, ...], M3: [...] }
// 行为: null/undefined/{}/全空数组 → ''；模块按字母序，节点按 name 字母序；HTML 特殊字符 escape
function renderPeersHtml(peers) {
  if (!peers || typeof peers !== 'object') return ''
  const entries = Object.entries(peers).filter(([, list]) => Array.isArray(list) && list.length > 0)
  if (entries.length === 0) return ''
  entries.sort(([a], [b]) => a.localeCompare(b))
  const sections = entries.map(([modId, list]) => {
    const sortedList = [...list].sort((a, b) => (a.name || '').localeCompare(b.name || ''))
    const items = sortedList.map(p => `<li>${escapeHtml(p.name || '')}</li>`).join('')
    return `<div class="peer-section"><span class="peer-module">→ ${escapeHtml(modId)}</span><ul>${items}</ul></div>`
  }).join('')
  return `<div class="peer-tooltip">${sections}</div>`
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
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

watch(() => props.moduleId, () => {
  focusedNodeId.value = null
})

// Phase 2.5 R1 F001: watch 组件内部 focusedNodeId ref（不是 props.focusedNodeId）
// 焦点值变化（由 node:click/canvas:click/ESC/clearFocus/focusPeer 触发）后
// 在 nextTick 里调 updateElementStates 应用淡化/强调
watch(focusedNodeId, () => {
  nextTick(updateElementStates)
})

// Phase 1 T10: colorMode / nodesWithMastery 变化时轻量重绘（不 destroy graph）
// 必须保留 focusedNodeId 状态（Phase 2.5 焦点模式回归）
watch(() => [props.colorMode, props.nodesWithMastery], () => {
  if (!graph) return
  const data = buildG6Data()
  try {
    graph.setData(data)
    graph.render()
  } catch (err) {
    console.warn('[ConceptMapPanel] colorMode setData/render failed:', err)
  }
  if (focusedNodeId.value) {
    nextTick(updateElementStates)
  }
}, { deep: true })

onMounted(() => {
  nextTick(createGraph)
  window.addEventListener('keydown', onKeyDown)
})
onUnmounted(() => {
  destroyGraph()
  window.removeEventListener('keydown', onKeyDown)
})

// Phase 2.5 R1 F002: defineExpose 增量扩展，保留 Phase 2 已暴露的 focusedNodeId / clearFocus
defineExpose({
  crossModuleBadges,
  crossModulePeers,
  focusedNodeId,        // Phase 2 保留（Phase 2 测试依赖）
  clearFocus,           // Phase 2 保留（Phase 2 测试依赖）
  relatedNodeIds,       // Phase 2.5 T1
  relatedEdgeIds,       // Phase 2.5 T1
  updateElementStates,  // Phase 2.5 T2（供测试调用验证）
  renderPeersHtml,      // Phase 2.5 T3（供测试直接调用）
  buildG6Data,          // Phase 1 T10（供视觉编码断言使用；happy-dom G6 canvas 不渲染）
})
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
  font-size: var(--fs-base);
  font-weight: var(--fw-medium);
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
  font-size: 16px;
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
