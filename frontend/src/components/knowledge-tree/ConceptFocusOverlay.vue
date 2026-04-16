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
