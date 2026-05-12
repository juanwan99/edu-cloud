<template>
  <div class="student-rank-panel">
    <div class="report-panel">
      <div class="student-rank-tools">
        <h3>学生排名</h3>
        <div class="student-rank-actions">
          <n-input
            v-model:value="studentKeyword"
            placeholder="搜索学生姓名/学号/班级"
            clearable
            size="small"
            class="student-search"
          />
          <n-button
            size="small"
            :disabled="!filteredStudentRows.length"
            @click="$emit('export-rank')"
          >
            导出排名
          </n-button>
        </div>
      </div>
      <n-data-table
        :columns="studentColumns"
        :data="filteredStudentRows"
        :pagination="{ pageSize: 30 }"
        :scroll-x="studentTableScrollX"
        size="small"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getStudentColumns } from '../../composables/useTableColumns'

const props = defineProps({
  report: { type: Object, default: null },
})

defineEmits(['export-rank'])

const studentKeyword = ref('')

const studentColumns = computed(() => getStudentColumns(props.report?.subjects))
const studentTableScrollX = computed(() => 820 + (props.report?.subjects || []).length * 96)

const studentRows = computed(() => props.report?.students || [])
const filteredStudentRows = computed(() => {
  const keyword = studentKeyword.value.trim().toLowerCase()
  if (!keyword) return studentRows.value
  return studentRows.value.filter(row => [
    row.name,
    row.student_number,
    row.class_name,
  ].some(value => String(value || '').toLowerCase().includes(keyword)))
})
</script>

<style scoped>
.report-panel {
  padding-top: var(--space-3, 12px);
}

.report-panel h3 {
  margin: 0 0 var(--space-3, 12px);
  font-size: var(--fs-md, 16px);
  font-weight: var(--fw-semibold, 600);
}

.student-rank-tools {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3, 12px);
}

.student-rank-actions {
  display: flex;
  gap: var(--space-2, 8px);
  align-items: center;
}

.student-search {
  width: 220px;
}
</style>
