<template>
  <div class="module-cards">
    <div
      v-for="mod in modules"
      :key="mod.module"
      class="module-card"
      @click="$emit('select', mod.module)"
    >
      <div class="card-header">
        <span class="module-name">{{ moduleNames[mod.module] || mod.module }}</span>
        <span class="mastery-pct" :style="{ color: masteryColor(mod.mastery) }">
          {{ mod.mastery > 0 ? Math.round(mod.mastery * 100) + '%' : '--' }}
        </span>
      </div>
      <n-progress
        type="circle"
        :percentage="Math.round(mod.mastery * 100)"
        :color="masteryColor(mod.mastery)"
        :rail-color="'rgba(255,255,255,0.1)'"
        :stroke-width="6"
        :show-indicator="false"
        style="width: 80px; height: 80px; margin: 12px auto"
      />
    </div>
  </div>
</template>

<script setup>
import { NProgress } from 'naive-ui'

defineProps({
  modules: { type: Array, default: () => [] },
})
defineEmits(['select'])

const moduleNames = {
  M1: '分子与细胞',
  M2: '遗传与进化',
  M3: '稳态与调节',
  M4: '生物与环境',
  M5: '生物技术与工程',
}

function masteryColor(mastery) {
  if (mastery >= 0.85) return '#22c55e'
  if (mastery >= 0.6) return '#eab308'
  if (mastery >= 0.3) return '#ef4444'
  return '#6b7280'
}
</script>

<style scoped>
.module-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-3);
  padding: var(--space-4);
}
.module-card {
  background: rgba(255, 255, 255, 0.05);
  border-radius: var(--r-md);
  padding: var(--space-4);
  cursor: pointer;
  transition: background 0.2s;
  text-align: center;
}
.module-card:hover {
  background: rgba(255, 255, 255, 0.1);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.module-name {
  font-size: var(--fs-base);
  font-weight: var(--fw-medium);
}
.mastery-pct {
  font-size: var(--fs-lg);
  font-weight: var(--fw-semibold);
}
</style>
