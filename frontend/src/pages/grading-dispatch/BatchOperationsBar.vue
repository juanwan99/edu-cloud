<template>
  <div>
    <!-- 一键全科检测（仅教务主任+） -->
    <div class="batch-bar" v-if="canManageAll && detectableCount > 0">
      <n-button size="small" @click="$emit('batch-detect')" :loading="batchDetectLoading">
        一键全科检测（{{ detectableCount }} 科待检测）
      </n-button>
      <span class="batch-progress" v-if="batchDetectLoading">{{ batchProgressText }}</span>
    </div>

    <!-- 批量操作 -->
    <div class="batch-bar" v-if="selectedCount > 0">
      <span>已选 <b>{{ selectedCount }}</b> 科</span>
      <n-button size="tiny" type="primary" @click="$emit('batch-cut')" :disabled="!canBatchCut">批量切割</n-button>
    </div>
  </div>
</template>

<script setup>
import { NButton } from 'naive-ui'

defineProps({
  canManageAll: { type: Boolean, default: false },
  detectableCount: { type: Number, default: 0 },
  batchDetectLoading: { type: Boolean, default: false },
  batchProgressText: { type: String, default: '' },
  selectedCount: { type: Number, default: 0 },
  canBatchCut: { type: Boolean, default: false },
})

defineEmits(['batch-detect', 'batch-cut'])
</script>

<style scoped>
.batch-bar { display: flex; align-items: center; gap: 10px; padding: var(--space-2) var(--space-4); background: var(--color-success-bg-subtle); border: 1px solid var(--color-success-border); border-radius: var(--radius-md); margin-bottom: var(--space-3); font-size: var(--fs-base); }
.batch-progress { font-size: var(--fs-base); color: var(--color-text-secondary); margin-left: var(--space-2); }
</style>
