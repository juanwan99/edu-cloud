<template>
  <div class="relation-review-panel">
    <div class="review-left">
      <ConceptReviewList
        :nodes="nodes"
        :edges="edges"
        :quality-issues="qualityIssues"
        :selected-id="selectedConcept?.id"
        @select="selectedConcept = $event"
      />
    </div>
    <div class="review-right">
      <RelationDetailCard
        v-if="selectedConcept"
        :concept="selectedConcept"
        :edges="edges"
        :all-nodes="nodes"
        :can-edit="canEdit"
        @review-edge="handleReviewEdge"
        @edit-edge="handleEditEdge"
      />
      <div v-else class="empty-hint">
        ← 选择一个概念查看关系
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import ConceptReviewList from './ConceptReviewList.vue'
import RelationDetailCard from './RelationDetailCard.vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  qualityIssues: { type: Array, default: () => [] },
  canEdit: { type: Boolean, default: false },
})
const emit = defineEmits(['edit'])

const selectedConcept = ref(null)

// 节点列表变化时重置选中（模块切换/图谱刷新后防止旧引用）
watch(() => props.nodes, () => {
  if (selectedConcept.value && !props.nodes.some(n => n.id === selectedConcept.value.id)) {
    selectedConcept.value = null
  }
})

function handleReviewEdge({ edgeId, status }) {
  emit('edit', [{ op: 'set_review_status', edge_id: edgeId, status }])
}

function handleEditEdge({ edgeId, source, target, type, strength }) {
  emit('edit', [{ op: 'update_edge', source, target, type, fields: { strength } }])
}
</script>

<style scoped>
.relation-review-panel { display: flex; height: 100%; }
.review-left { width: 260px; border-right: 1px solid rgba(255,255,255,0.08); flex-shrink: 0; overflow: hidden; }
.review-right { flex: 1; padding: 16px; overflow-y: auto; }
.empty-hint { display: flex; align-items: center; justify-content: center; height: 100%; color: rgba(255,255,255,0.3); }
</style>
