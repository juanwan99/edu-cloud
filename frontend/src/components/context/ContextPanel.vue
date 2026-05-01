<template>
  <div style="padding: var(--space-4)">
    <n-h4>考试</n-h4>
    <n-menu
      :options="examOptions"
      :value="contextStore.selectedExamId"
      @update:value="contextStore.selectExam"
    />
    <n-divider />
    <n-h4>班级</n-h4>
    <n-list>
      <n-list-item v-for="cls in contextStore.classes" :key="cls.id">
        {{ cls.name }}
      </n-list-item>
    </n-list>
    <n-divider />
    <CalendarPanel />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useContextStore } from '../../stores/context.js'
import { formatExamStatus } from '../../utils/examStatus.js'
import CalendarPanel from '../calendar/CalendarPanel.vue'

const contextStore = useContextStore()

const examOptions = computed(() =>
  contextStore.exams.map(e => {
    const statusLabel = formatExamStatus(e.status)
    return {
      label: statusLabel ? `${e.name} (${statusLabel})` : e.name,
      key: e.id,
    }
  })
)

onMounted(() => contextStore.loadContext())
</script>
