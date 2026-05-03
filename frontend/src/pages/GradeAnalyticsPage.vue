<template>
  <div class="page-wrap grade-analytics">
    <div class="page-header">
      <h1 class="page-title">年级分析</h1>
    </div>

    <n-space vertical :size="16">
      <!-- Selectors -->
      <n-space>
        <n-select
          v-model:value="selectedGradeId"
          :options="gradeOptions"
          placeholder="选择年级"
          style="min-width: 150px"
          @update:value="onGradeChange"
        />
        <n-select
          v-model:value="selectedExamId"
          :options="examOptions"
          placeholder="选择考试"
          style="min-width: 250px"
        />
        <n-button type="primary" @click="loadAll" :loading="loading">
          查看分析
        </n-button>
      </n-space>

      <!-- Overview: class comparison bar chart -->
      <n-card v-if="overviewData" title="班级对比" size="small">
        <v-chart class="chart-height-lg" :option="barOption" />
      </n-card>

      <!-- Trend: grade trend line chart -->
      <n-card v-if="trendData && trendData.points.length" title="考情趋势" size="small">
        <v-chart class="chart-height-lg" :option="lineOption" />
      </n-card>

      <!-- Subjects: radar chart -->
      <n-card v-if="subjectsData && subjectsData.subjects.length" title="科目对比" size="small">
        <v-chart class="chart-height-xl" :option="radarOption" />
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart, LineChart, RadarChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent, RadarComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import {
  getGradeOverview, getGradeExamTrend, getGradeSubjects,
} from '../api/analytics'
import client from '../api/client'

use([
  BarChart, LineChart, RadarChart,
  GridComponent, TooltipComponent, LegendComponent, RadarComponent,
  CanvasRenderer,
])

const message = useMessage()
const loading = ref(false)

const selectedGradeId = ref(null)
const selectedExamId = ref(null)
const gradeOptions = ref([])
const examOptions = ref([])

const overviewData = ref(null)
const trendData = ref(null)
const subjectsData = ref(null)

// Bar chart: class comparison
const barOption = computed(() => {
  if (!overviewData.value?.classes?.length) return {}
  const classes = overviewData.value.classes
  const names = classes.map(c => c.class_name)
  return {
    tooltip: { trigger: 'axis' },
    legend: {},
    xAxis: { type: 'category', data: names },
    yAxis: { type: 'value' },
    series: [
      {
        name: '均分',
        type: 'bar',
        data: classes.map(c => c.avg_score),
        itemStyle: { color: getComputedStyle(document.documentElement).getPropertyValue('--color-info').trim() || '#3b82f6' },
      },
      {
        name: '最高分',
        type: 'bar',
        data: classes.map(c => c.max_score),
        itemStyle: { color: getComputedStyle(document.documentElement).getPropertyValue('--color-success').trim() || '#22C55E' },
      },
      {
        name: '最低分',
        type: 'bar',
        data: classes.map(c => c.min_score),
        itemStyle: { color: getComputedStyle(document.documentElement).getPropertyValue('--color-warning').trim() || '#f59e0b' },
      },
    ],
  }
})

// Line chart: trend
const lineOption = computed(() => {
  if (!trendData.value?.points?.length) return {}
  const points = trendData.value.points
  return {
    tooltip: { trigger: 'axis' },
    legend: {},
    xAxis: { type: 'category', data: points.map(p => p.exam_name) },
    yAxis: [
      { type: 'value', name: '分数' },
      { type: 'value', name: '比率', max: 1, axisLabel: { formatter: v => `${(v * 100).toFixed(0)}%` } },
    ],
    series: [
      {
        name: '均分',
        type: 'line',
        data: points.map(p => p.avg_score),
        smooth: true,
      },
      {
        name: '及格率',
        type: 'line',
        yAxisIndex: 1,
        data: points.map(p => p.pass_rate),
        smooth: true,
        lineStyle: { type: 'dashed' },
      },
      {
        name: '优秀率',
        type: 'line',
        yAxisIndex: 1,
        data: points.map(p => p.excellent_rate),
        smooth: true,
        lineStyle: { type: 'dotted' },
      },
    ],
  }
})

// Radar chart: subject comparison
const radarOption = computed(() => {
  if (!subjectsData.value?.subjects?.length) return {}
  const subjects = subjectsData.value.subjects
  return {
    tooltip: {},
    radar: {
      indicator: subjects.map(s => ({
        name: s.subject_name,
        max: 1,
      })),
    },
    series: [{
      type: 'radar',
      data: [{
        name: '得分率',
        value: subjects.map(s => s.score_rate),
        areaStyle: { opacity: 0.3 },
      }],
    }],
  }
})

async function onGradeChange() {
  overviewData.value = null
  trendData.value = null
  subjectsData.value = null
  selectedExamId.value = null
  // Reload exams might be needed in future
}

async function loadAll() {
  if (!selectedGradeId.value) {
    message.warning('请选择年级')
    return
  }
  loading.value = true
  try {
    // Load trend (no exam needed)
    const trendResp = await getGradeExamTrend(selectedGradeId.value)
    trendData.value = trendResp.data

    // Load overview and subjects if exam selected
    if (selectedExamId.value) {
      const [overviewResp, subjectsResp] = await Promise.all([
        getGradeOverview(selectedGradeId.value, selectedExamId.value),
        getGradeSubjects(selectedGradeId.value, selectedExamId.value),
      ])
      overviewData.value = overviewResp.data
      subjectsData.value = subjectsResp.data
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // Load grades
  try {
    const resp = await client.get('/grades')
    gradeOptions.value = (resp.data || []).map(g => ({
      label: g.name,
      value: g.id,
    }))
  } catch { /* ignore */ }

  // Load exams for exam selector
  try {
    const resp = await client.get('/exams')
    examOptions.value = (resp.data || []).map(e => ({
      label: e.name,
      value: e.id,
    }))
  } catch { /* ignore */ }
})
</script>
