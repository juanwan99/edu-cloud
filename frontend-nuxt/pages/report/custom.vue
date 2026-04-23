<template>
  <div class="report-page">
    <PowerFilter ref="filterRef" />

    <el-card class="metrics-card">
      <template #header>选择分析指标</template>
      <el-checkbox-group v-model="selectedMetrics">
        <el-checkbox v-for="m in availableMetrics" :key="m.value" :label="m.value">
          {{ m.label }}
        </el-checkbox>
      </el-checkbox-group>
      <el-button type="primary" :disabled="!canQuery" @click="queryData" style="margin-top: 12px">
        开始分析
      </el-button>
    </el-card>

    <div v-if="loading" v-loading="true" class="loading-area" />

    <template v-else-if="reportData">
      <el-card v-if="reportData.summary" class="result-card">
        <template #header>总览</template>
        <pre>{{ JSON.stringify(reportData.summary, null, 2) }}</pre>
      </el-card>

      <el-card v-if="reportData.segments" class="result-card">
        <template #header>分数段</template>
        <v-chart :option="segmentsOption" style="height: 300px" autoresize />
      </el-card>

      <el-card v-if="reportData.ranking" class="result-card">
        <template #header>班级排名</template>
        <el-table :data="reportData.ranking.class_rankings ?? []" stripe max-height="400">
          <el-table-column prop="rank" label="排名" width="80" />
          <el-table-column prop="class_name" label="班级" width="140" />
          <el-table-column prop="avg_score" label="均分" width="100" />
          <el-table-column prop="student_count" label="人数" width="100" />
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
const reportData = ref<any>(null)

const availableMetrics = [
  { label: '总览', value: 'summary' },
  { label: '分数段', value: 'segments' },
  { label: '排名', value: 'ranking' },
  { label: '题目分析', value: 'questions' },
  { label: '尖子生/后进生', value: 'top_bottom' },
]
const selectedMetrics = ref(['summary', 'segments'])

const canQuery = computed(() => po.value?.hasSelection?.value && selectedMetrics.value.length > 0)

const segmentsOption = computed(() => {
  const segs = reportData.value?.segments
  if (!segs?.intervals?.length) return {}
  return {
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: segs.intervals.map((i: any) => i.label) },
    yAxis: { type: 'value', name: '人数' },
    series: [{ type: 'bar', data: segs.intervals.map((i: any) => i.count), itemStyle: { color: '#67c23a' } }],
  }
})

async function queryData() {
  const params = po.value?.analysisParams?.value
  if (!params?.exam_id) return
  loading.value = true
  try {
    const selectedSubject = po.value?.subjectOptions?.value?.find(
      (s: any) => s.id === params.subject_id
    )
    const result = await api.queryReport({
      exam_ids: [params.exam_id],
      metrics: selectedMetrics.value,
      subject_codes: selectedSubject ? [selectedSubject.code] : undefined,
      class_ids: params.class_id ? [params.class_id] : undefined,
    })
    reportData.value = result.metrics ?? result
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.report-page { padding: 16px; }
.loading-area { height: 200px; }
.metrics-card, .result-card { margin-bottom: 16px; }
</style>
