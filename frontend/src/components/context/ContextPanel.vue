<template>
  <div style="padding: 16px">
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
import CalendarPanel from '../calendar/CalendarPanel.vue'

const contextStore = useContextStore()

const examOptions = computed(() =>
  contextStore.exams.map(e => ({
    label: `${e.name} (${e.subject_code})`,
    key: e.id,
  }))
)

onMounted(() => contextStore.loadContext())
</script>
