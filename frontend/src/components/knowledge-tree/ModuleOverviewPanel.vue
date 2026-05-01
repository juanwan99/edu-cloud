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
    <!-- Phase 1 T13: 模块考频统计（F004 入口级渲染 + null 降级 — 派发 handoff §INV-004） -->
    <div class="freq-stats-section">
      <h3>模块考频统计</h3>
      <div class="freq-stats-list">
        <div v-for="mod in modulesData" :key="mod.id" class="freq-stat-item">
          <span class="freq-mod-name">{{ mod.name }}</span>
          <span class="freq-avg">平均考频: {{ formatAvgFreq(mod.id) }}</span>
          <span class="freq-cov">考频覆盖: {{ formatCoverage(mod.id) }}</span>
          <div class="freq-bar" aria-label="考频分布">
            <div class="freq-seg high" :style="{width: freqDist(mod.id).high + '%'}"></div>
            <div class="freq-seg mid" :style="{width: freqDist(mod.id).mid + '%'}"></div>
            <div class="freq-seg low" :style="{width: freqDist(mod.id).low + '%'}"></div>
          </div>
        </div>
      </div>
      <div class="freq-legend">
        <span class="dot high"></span>高频(≥500)
        <span class="dot mid"></span>中频(50-499)
        <span class="dot low"></span>低频/零
      </div>
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
  // Phase 1 T13: 后端 stats/overview 返回的 { module_stats: { M1: { avg_freq, exam_coverage, ... } } }
  // null → 加载失败降级，UI 所有 avg/cov 显示 '—'（派发 handoff §INV-004 契约）
  statsOverview: { type: Object, default: null },
})
defineEmits(['select-module', 'refresh-quality'])

// 派生工具：读 statsOverview.module_stats[moduleId]，null safe
function getModuleStats(moduleId) {
  return props.statsOverview?.module_stats?.[moduleId]
}

// 派生展示：avg_freq（Math.round 整数），null/undefined → '—'
function formatAvgFreq(moduleId) {
  const v = getModuleStats(moduleId)?.avg_freq
  if (v == null || isNaN(v)) return '—'
  return String(Math.round(v))
}

// 派生展示：exam_coverage 0.667 → '67%'，null/undefined → '—'
function formatCoverage(moduleId) {
  const v = getModuleStats(moduleId)?.exam_coverage
  if (v == null || isNaN(v)) return '—'
  return `${Math.round(v * 100)}%`
}

// 从 nodes 派生模块考频分布（前端计算，不依赖 statsOverview）
// 高频 ≥500 / 中频 50-499 / 低频 <50
function freqDist(moduleId) {
  const concepts = modulesData.value.find(m => m.id === moduleId)?.conceptIds
  if (!concepts || concepts.size === 0) return { high: 0, mid: 0, low: 0 }
  const modNodes = props.nodes.filter(n => concepts.has(n.id))
  if (modNodes.length === 0) return { high: 0, mid: 0, low: 0 }
  let high = 0, mid = 0, low = 0
  for (const n of modNodes) {
    const f = n.exam_frequency || 0
    if (f >= 500) high++
    else if (f >= 50) mid++
    else low++
  }
  const total = modNodes.length
  return {
    high: Math.round(100 * high / total),
    mid: Math.round(100 * mid / total),
    low: Math.round(100 * low / total),
  }
}

// 聚合每个模块的 stats
const modulesData = computed(() => {
  return props.navigation.map(mod => {
    const conceptIds = new Set()
    for (const bc of mod.big_concepts || []) {
      for (const cid of bc.concept_ids || []) conceptIds.add(cid)
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
      bigConceptCount: (mod.big_concepts || []).length,
      reviewedCount,
      highCount: q.highCount,
      medCount: q.medCount,
      conceptIds,  // T13: freqDist() 复用，避免重复构建 Set
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
  font-size: var(--fs-lg);
  font-weight: var(--fw-semibold);
}
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 32px;
}
.cross-module-section h3 {
  font-size: var(--fs-base);
  font-weight: var(--fw-medium);
  color: rgba(255, 255, 255, 0.6);
  margin: 0 0 12px;
}
.cross-module-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
/* T13: 模块考频统计 */
.freq-stats-section {
  margin-bottom: 24px;
}
.freq-stats-section h3 {
  font-size: var(--fs-base);
  font-weight: var(--fw-medium);
  color: rgba(255, 255, 255, 0.6);
  margin: 0 0 12px;
}
.freq-stats-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.freq-stat-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 12px;
  align-items: center;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  font-size: 16px;
}
.freq-mod-name {
  font-weight: var(--fw-medium);
}
.freq-avg,
.freq-cov {
  color: rgba(255, 255, 255, 0.7);
  font-size: 16px;
  white-space: nowrap;
}
.freq-bar {
  grid-column: 1 / -1;
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.08);
  margin-top: 4px;
}
.freq-seg.high { background: #3b5998; }
.freq-seg.mid { background: #8fa3d1; }
.freq-seg.low { background: #d0daed; }
.freq-legend {
  display: flex;
  gap: 16px;
  font-size: 16px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 8px;
}
.freq-legend .dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 4px;
  vertical-align: middle;
}
.freq-legend .dot.high { background: #3b5998; }
.freq-legend .dot.mid { background: #8fa3d1; }
.freq-legend .dot.low { background: #d0daed; }
</style>
