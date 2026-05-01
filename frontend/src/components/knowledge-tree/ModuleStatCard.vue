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
  border-left: var(--space-1) solid;
  transition: transform 0.15s;
}
.module-stat-card:hover {
  transform: translateY(-2px);
}
.card-header {
  margin-bottom: var(--space-3);
}
.module-name {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
}
.stats-row {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
}
.stat-item {
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-size: var(--fs-xl);
  font-weight: var(--fw-semibold);
}
.stat-label {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.5);
}
.progress-section {
  margin-bottom: var(--space-3);
}
.progress-label {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.6);
  margin-top: var(--space-1);
}
.badges {
  display: flex;
  gap: 6px;
}
</style>
