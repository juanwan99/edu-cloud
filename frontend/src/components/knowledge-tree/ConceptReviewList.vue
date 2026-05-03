<template>
  <div class="concept-review-list">
    <div class="filters">
      <n-select v-model:value="filterModule" :options="moduleOptions" size="small" placeholder="模块" clearable style="width: 100%" />
      <n-select v-model:value="filterStatus" :options="statusOptions" size="small" placeholder="审核状态" clearable style="width: 100%; margin-top: 6px" />
      <n-select v-model:value="sortBy" :options="sortOptions" size="small" style="width: 100%; margin-top: 6px" />
    </div>
    <div class="progress-bar" v-if="totalEdges > 0">
      <n-progress :percentage="Math.round(reviewedEdges / totalEdges * 100)" :height="8" />
      <span class="progress-label">{{ reviewedEdges }}/{{ totalEdges }} 关系已审核</span>
    </div>
    <n-list hoverable clickable class="concept-list">
      <n-list-item v-for="concept in sortedConcepts" :key="concept.id"
        :class="{ active: concept.id === selectedId }"
        @click="$emit('select', concept)">
        <div class="concept-item">
          <span class="status-dot" :class="statusClass(concept)" />
          <span class="concept-name">{{ concept.name }}</span>
          <QualityBadge v-if="conceptIssue(concept.id)" :severity="conceptIssue(concept.id)" label="!" />
        </div>
      </n-list-item>
    </n-list>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NSelect, NList, NListItem, NProgress } from 'naive-ui'
import QualityBadge from './QualityBadge.vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  qualityIssues: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
})
defineEmits(['select'])

const filterModule = ref(null)
const filterStatus = ref(null)
const sortBy = ref('priority')

const moduleOptions = [
  { label: 'M1 分子与细胞', value: 'M1' }, { label: 'M2 遗传与进化', value: 'M2' },
  { label: 'M3 稳态与调节', value: 'M3' }, { label: 'M4 生态与环境', value: 'M4' },
  { label: 'M5 生物技术', value: 'M5' },
]
const statusOptions = [
  { label: 'AI 草稿', value: 'ai_draft' },
  { label: '教师已审', value: 'teacher_reviewed' },
  { label: '已发布', value: 'published' },
]
const sortOptions = [
  { label: '按优先级', value: 'priority' },
  { label: '按名称', value: 'name' },
  { label: '按排序', value: 'order' },
]

const issueMap = computed(() => {
  const m = {}
  for (const issue of props.qualityIssues) {
    for (const nid of issue.node_ids || []) {
      if (!m[nid] || severityRank(issue.severity) > severityRank(m[nid])) {
        m[nid] = issue.severity
      }
    }
  }
  return m
})

function severityRank(s) {
  return s === 'HIGH' ? 3 : s === 'MED' ? 2 : 1
}

function conceptIssue(id) {
  return issueMap.value[id] || null
}

const totalEdges = computed(() => props.edges.length)
const reviewedEdges = computed(() =>
  props.edges.filter(e => e.review_status && e.review_status !== 'ai_draft').length
)

const filteredConcepts = computed(() => {
  let list = [...props.nodes]
  if (filterModule.value) list = list.filter(n => n.module === filterModule.value)
  if (filterStatus.value) list = list.filter(n => (n.review_status || 'ai_draft') === filterStatus.value)
  return list
})

const sortedConcepts = computed(() => {
  const list = [...filteredConcepts.value]
  if (sortBy.value === 'priority') {
    list.sort((a, b) => severityRank(issueMap.value[b.id] || '') - severityRank(issueMap.value[a.id] || ''))
  } else if (sortBy.value === 'name') {
    list.sort((a, b) => a.name.localeCompare(b.name, 'zh'))
  } else if (sortBy.value === 'order') {
    // 按 display_order（BigConcept 内排序）
  }
  return list
})

function statusClass(concept) {
  const s = concept.review_status || 'ai_draft'
  const hasUnreviewedEdge = props.edges.some(e =>
    (e.source === concept.id || e.target === concept.id) && (e.review_status || 'ai_draft') === 'ai_draft'
  )
  if (s === 'published' && !hasUnreviewedEdge) return 'published'
  if (hasUnreviewedEdge) return 'warning'
  return 'draft'
}
</script>

<style scoped>
.concept-review-list { display: flex; flex-direction: column; height: 100%; }
.filters { padding: var(--space-3); border-bottom: 1px solid rgba(255,255,255,0.08); }
.progress-bar { padding: var(--space-2) var(--space-3); }
.progress-label { font-size: var(--fs-base); color: rgba(255,255,255,0.5); }
.concept-list { flex: 1; overflow-y: auto; }
.concept-item { display: flex; align-items: center; gap: var(--space-2); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.published { background: #F4DA4C; }
.status-dot.warning { background: #f2c97d; }
.status-dot.draft { background: rgba(255,255,255,0.3); }
.concept-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.active { background: rgba(99, 226, 183, 0.1) !important; }
</style>
