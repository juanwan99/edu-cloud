<template>
  <div class="selector-bar">
    <n-select
      :value="examId"
      :options="examOptions"
      placeholder="选择考试"
      style="width: 280px"
      :loading="loadingExams"
      @update:value="$emit('update:examId', $event)"
    />
    <n-select
      v-if="examId"
      :value="subjectId"
      :options="subjectOptions"
      placeholder="选择科目"
      style="width: 200px"
      :loading="loadingSubjects"
      @update:value="$emit('update:subjectId', $event)"
    />
  </div>
</template>

<script setup>
import { NSelect } from 'naive-ui'

defineProps({
  examId: { type: [String, Number], default: null },
  subjectId: { type: [String, Number], default: null },
  examOptions: { type: Array, default: () => [] },
  subjectOptions: { type: Array, default: () => [] },
  loadingExams: { type: Boolean, default: false },
  loadingSubjects: { type: Boolean, default: false },
})

defineEmits(['update:examId', 'update:subjectId'])
</script>

<style scoped>
.selector-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
