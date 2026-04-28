<template>
  <div class="relation-detail-card" v-if="concept">
    <div class="concept-header">
      <h3>{{ concept.name }}</h3>
      <n-tag :type="reviewTagType" size="small">{{ concept.review_status || 'ai_draft' }}</n-tag>
      <p v-if="concept.description" class="desc">{{ concept.description }}</p>
    </div>

    <div v-for="group in relationGroups" :key="group.type" class="relation-group">
      <div class="group-header">
        <span class="group-label">{{ group.label }}</span>
        <n-button size="tiny" quaternary @click="batchConfirm(group.edges)" :disabled="!canEdit">
          全部确认
        </n-button>
      </div>
      <div v-for="edge in group.edges" :key="edgeKey(edge)" class="relation-row">
        <span class="direction">{{ edge._direction === 'in' ? '←' : '→' }}</span>
        <span class="peer-name">{{ edge._peerName }}</span>
        <n-tag v-if="edge.confidence < 0.7" type="warning" size="tiny">{{ edge.confidence.toFixed(2) }}</n-tag>
        <span class="edge-status" :class="edge.review_status || 'ai_draft'">
          {{ statusLabel(edge.review_status) }}
        </span>
        <n-button-group size="tiny">
          <n-button type="success" :disabled="!canEdit" @click="confirmEdge(edge)">确认</n-button>
          <n-button type="error" :disabled="!canEdit" @click="rejectEdge(edge)">驳回</n-button>
          <n-button :disabled="!canEdit" @click="editEdge(edge)">编辑</n-button>
        </n-button-group>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NTag, NButton, NButtonGroup } from 'naive-ui'

const props = defineProps({
  concept: { type: Object, default: null },
  edges: { type: Array, default: () => [] },
  allNodes: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['review-edge', 'edit-edge'])

const nodeMap = computed(() => {
  const m = {}
  for (const n of props.allNodes) m[n.id] = n
  return m
})

const reviewTagType = computed(() => {
  const s = props.concept?.review_status || 'ai_draft'
  if (s === 'published') return 'success'
  if (s === 'teacher_reviewed') return 'info'
  return 'default'
})

const relatedEdges = computed(() => {
  if (!props.concept) return []
  const cid = props.concept.id
  return props.edges
    .filter(e => e.source === cid || e.target === cid)
    .map(e => ({
      ...e,
      _direction: e.target === cid ? 'in' : 'out',
      _peerId: e.target === cid ? e.source : e.target,
      _peerName: nodeMap.value[e.target === cid ? e.source : e.target]?.name || '未知',
    }))
})

const typeConfig = [
  { type: 'prerequisite_hard', label: '硬前置依赖' },
  { type: 'prerequisite_soft', label: '软前置依赖' },
  { type: 'bridge_to', label: '跨域桥接' },
  { type: 'contrast', label: '边界对比' },
]

const relationGroups = computed(() =>
  typeConfig
    .map(tc => ({
      ...tc,
      edges: relatedEdges.value.filter(e => e.type === tc.type),
    }))
    .filter(g => g.edges.length > 0)
)

function edgeKey(e) {
  return `${e.source}-${e.target}-${e.type}`
}

function statusLabel(s) {
  const labels = { ai_draft: '待审', teacher_reviewed: '已审', published: '已发布', rejected: '已驳回' }
  return labels[s || 'ai_draft'] || s
}

function confirmEdge(edge) {
  const current = edge.review_status || 'ai_draft'
  // rejected 边需先回退到 ai_draft，再由教师重新确认
  if (current === 'rejected') {
    emit('review-edge', { edgeId: edge.id, status: 'ai_draft' })
  } else {
    emit('review-edge', { edgeId: edge.id, status: 'teacher_reviewed' })
  }
}

function rejectEdge(edge) {
  emit('review-edge', { edgeId: edge.id, status: 'rejected' })
}

function editEdge(edge) {
  emit('edit-edge', {
    edgeId: edge.id, source: edge.source, target: edge.target,
    type: edge.type, strength: edge.strength,
  })
}

function batchConfirm(edges) {
  for (const e of edges) {
    const s = e.review_status || 'ai_draft'
    // 跳过已审核/已发布/已驳回（rejected 需单独恢复）
    if (s === 'ai_draft') {
      emit('review-edge', { edgeId: e.id, status: 'teacher_reviewed' })
    }
  }
}
</script>

<style scoped>
.concept-header { margin-bottom: 16px; }
.concept-header h3 { margin: 0 0 4px; }
.desc { color: rgba(255,255,255,0.5); font-size: 16px; margin: 4px 0 0; }
.relation-group { margin-bottom: 16px; }
.group-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.group-label { font-weight: 600; font-size: 16px; color: rgba(255,255,255,0.7); }
.relation-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
.direction { font-family: monospace; color: rgba(255,255,255,0.4); width: 20px; text-align: center; }
.peer-name { flex: 1; }
.edge-status { font-size: 16px; color: rgba(255,255,255,0.4); min-width: 40px; }
.edge-status.rejected { color: #e88080; text-decoration: line-through; }
.edge-status.teacher_reviewed { color: #63e2b7; }
</style>
