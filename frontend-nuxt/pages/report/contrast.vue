<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <div v-if="loading" v-loading="true" class="loading-area" />

    <template v-else-if="aggregates">
      <el-card class="chart-card">
        <template #header>班级对比</template>
        <v-chart :option="contrastOption" style="height: 350px" autoresize />
      </el-card>

      <el-card class="table-card">
        <template #header>班级数据</template>
        <el-table :data="aggregates.class_rankings ?? []" stripe>
          <el-table-column prop="class_name" label="班级" width="140" />
          <el-table-column prop="student_count" label="人数" width="80" />
          <el-table-column prop="avg_score" label="均分" width="80">
            <template #default="{ row }">{{ row.avg_score?.toFixed(1) ?? '-' }}</template>
          </el-table-column>
          <el-table-column prop="rank" label="排名" width="80" />
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const filterRef = ref()
const po = computed(() => filterRef.value?.po)
const api = useApi()

const loading = ref(false)
const aggregates = ref<any>(null)

const contrastOption = computed(() => {
  const data = aggregates.value?.class_rankings ?? []
  if (!data.length) return {}
  const names = data.map((c: any) => c.class_name)
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: ['均分'] },
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value' },
    series: [
      { name: '均分', type: 'bar', data: data.map((c: any) => c.avg_score) },
    ],
  }
})

watch(() => po.value?.analysisParams?.value, async (params) => {
  if (!params?.exam_id) return
  loading.value = true
  try {
    aggregates.value = await api.getExamGradeAggregates(params.exam_id, {
      subject_id: params.subject_id,
    })
  } finally {
    loading.value = false
  }
}, { deep: true })
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.chart-card, .table-card { margin-bottom: 16px; }
</style>
