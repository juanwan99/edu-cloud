<template>
  <el-card class="stat-card" shadow="hover">
    <div class="stat-value">
      {{ formattedValue }}
      <span v-if="trend != null" :class="['trend', trend > 0 ? 'up' : trend < 0 ? 'down' : '']">
        {{ trend > 0 ? '↑' : trend < 0 ? '↓' : '→' }}
      </span>
    </div>
    <div class="stat-label">{{ label }}</div>
    <div v-if="subtitle" class="stat-subtitle">{{ subtitle }}</div>
  </el-card>
</template>

<script setup lang="ts">
const props = defineProps<{
  value: number | string | null
  label: string
  subtitle?: string
  trend?: number | null
  format?: 'number' | 'percent' | 'score'
}>()

const formattedValue = computed(() => {
  if (props.value == null) return '-'
  if (props.format === 'percent' && typeof props.value === 'number') return (props.value * 100).toFixed(1) + '%'
  if (props.format === 'score' && typeof props.value === 'number') return props.value.toFixed(1)
  return String(props.value)
})
</script>

<style scoped>
.stat-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: 700; color: var(--el-color-primary); line-height: 1.2; }
.stat-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 6px; }
.stat-subtitle { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 2px; }
.trend { font-size: 18px; margin-left: 4px; }
.trend.up { color: var(--el-color-success); }
.trend.down { color: var(--el-color-danger); }
</style>
