<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <el-card>
      <template #header>
        <div class="table-header">
          <span>数据表格</span>
          <el-button type="primary" size="small" :disabled="!tableData.length" @click="exportCsv">
            导出 CSV
          </el-button>
        </div>
      </template>

      <div v-if="loading" v-loading="true" class="loading-area" />

      <el-table v-else :data="tableData" stripe max-height="600">
        <el-table-column v-for="col in visibleColumns" :key="col.prop" :prop="col.prop" :label="col.label" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
const filterRef = ref()
const po = computed(() => filterRef.value?.po)
const api = useApi()

const loading = ref(false)
const tableData = ref<any[]>([])

const allColumns = [
  { prop: 'rank', label: '排名' },
  { prop: 'name', label: '姓名' },
  { prop: 'student_number', label: '学号' },
  { prop: 'class_name', label: '班级' },
  { prop: 'total_score', label: '总分' },
]
const visibleColumns = ref([...allColumns])

watch(() => po.value?.analysisParams?.value, async (params) => {
  if (!params?.exam_id) return
  loading.value = true
  try {
    const result = await api.queryReport({
      exam_ids: [params.exam_id],
      metrics: ['ranking'],
      class_ids: params.class_id ? [params.class_id] : undefined,
    })
    const ranking = result.metrics?.ranking ?? result.ranking ?? {}
    tableData.value = ranking.students ?? []
  } finally {
    loading.value = false
  }
}, { deep: true })

function exportCsv() {
  if (!tableData.value.length) return
  const headers = visibleColumns.value.map(c => c.label)
  const rows = tableData.value.map(row =>
    visibleColumns.value.map(c => row[c.prop] ?? '')
  )
  const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '成绩表.csv'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.table-header { display: flex; justify-content: space-between; align-items: center; }
</style>
