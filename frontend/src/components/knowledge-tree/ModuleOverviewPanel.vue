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
