<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <div v-if="loading" v-loading="true" class="loading-area" />

    <template v-else-if="summary">
      <div class="stats-row">
        <el-card v-for="stat in statsCards" :key="stat.label" class="stat-card">
          <div class="stat-value">{{ stat.value }}</div>
          <div class="stat-label">{{ stat.label }}</div>
        </el-card>
      </div>

      <el-card class="chart-card">
        <template #header>分数分布</template>
        <v-chart :option="distributionOption" style="height: 300px" autoresize />
      </el-card>

      <el-card v-if="questions.length" class="table-card">
        <template #header>题目分析</template>
        <el-table :data="questions" stripe>
          <el-table-column prop="name" label="题号" width="100" />
          <el-table-column prop="question_type" label="题型" width="100" />
          <el-table-column prop="max_score" label="满分" width="80" />
          <el-table-column prop="avg_score" label="均分" width="80" />
          <el-table-column prop="score_rate" label="得分率" width="100">
            <template #default="{ row }">
              {{ row.score_rate != null ? (row.score_rate * 100).toFixed(1) + '%' : '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="discrimination" label="区分度" width="100">
            <template #default="{ row }">
              {{ row.discrimination != null ? row.discrimination.toFixed(2) : '-' }}
            </template>
          </el-table-column>
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
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, TitleComponent])

const filterRef = ref()
const po = computed(() => filterRef.value?.po)
const api = useApi()

const loading = ref(false)
const summary = ref<any>(null)
const distribution = ref<any>(null)
const questions = ref<any[]>([])

const statsCards = computed(() => {
  if (!summary.value) return []
  const s = summary.value
  return [
    { label: '平均分', value: s.avg_score?.toFixed(1) ?? '-' },
    { label: '最高分', value: s.max_score ?? '-' },
    { label: '最低分', value: s.min_score ?? '-' },
    { label: '及格率', value: s.pass_rate != null ? (s.pass_rate * 100).toFixed(1) + '%' : '-' },
  ]
})

const distributionOption = computed(() => {
  const d = distribution.value
  if (!d?.segments) return {}
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: d.segments },
    yAxis: { type: 'value', name: '人数' },
    series: [{ type: 'bar', data: d.counts, itemStyle: { color: '#409eff' } }],
  }
})

watch(() => po.value?.analysisParams?.value, async (params) => {
  if (!params?.exam_id) return
  loading.value = true
  try {
    const [sum, dist] = await Promise.all([
      api.getExamSummary(params.exam_id, { subject_id: params.subject_id }),
      api.getExamDistribution(params.exam_id, { subject_id: params.subject_id }),
    ])
    summary.value = sum
    distribution.value = dist
    if (params.subject_id) {
      const q = await api.getSubjectQuestions(params.subject_id)
      questions.value = q.questions ?? q ?? []
    } else {
      questions.value = []
    }
  } finally {
    loading.value = false
  }
}, { deep: true })
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.stats-row { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 150px; text-align: center; }
.stat-value { font-size: 24px; font-weight: bold; color: #409eff; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }
.chart-card, .table-card { margin-bottom: 16px; }
</style>
