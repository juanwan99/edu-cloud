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

      <!-- Boxplot: class score distribution -->
      <n-card v-if="boxplotData && boxplotData.classes?.length" title="班级分数分布（箱线图）" size="small">
        <v-chart class="chart-height-lg" :option="boxplotOption" />
      </n-card>

      <!-- Knowledge heatmap -->
      <n-card v-if="knowledgeData && knowledgeData.knowledge_points?.length" title="知识点掌握热力图" size="small">
        <v-chart class="chart-height-xl" :option="heatmapOption" />
      </n-card>
    </n-space>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart, LineChart, RadarChart, BoxplotChart, HeatmapChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, LegendComponent, RadarComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import {
  getGradeOverview, getGradeExamTrend, getGradeSubjects,
  getClassBoxplot, getClassKnowledge,
} from '../api/analytics'
import client from '../api/client'
import { CHART_DEFAULTS, CHART_PALETTE } from '../config/chartTheme.js'

use([
  BarChart, LineChart, RadarChart, BoxplotChart, HeatmapChart,
  GridComponent, TooltipComponent, LegendComponent, RadarComponent,
  VisualMapComponent, CanvasRenderer,
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
const boxplotData = ref(null)
const knowledgeData = ref(null)

// Bar chart: class comparison
const barOption = computed(() => {
  if (!overviewData.value?.classes?.length) return {}
  const classes = overviewData.value.classes
  const names = classes.map(c => c.class_name)
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { ...CHART_DEFAULTS.legend },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: names },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [
      {
        name: '均分',
        type: 'bar',
        data: classes.map(c => c.avg_score),
        itemStyle: { color: CHART_PALETTE[0] },
      },
      {
        name: '最高分',
        type: 'bar',
        data: classes.map(c => c.max_score),
        itemStyle: { color: CHART_PALETTE[3] },
      },
      {
        name: '最低分',
        type: 'bar',
        data: classes.map(c => c.min_score),
        itemStyle: { color: CHART_PALETTE[2] },
      },
    ],
  }
})

// Line chart: trend
const lineOption = computed(() => {
  if (!trendData.value?.points?.length) return {}
  const points = trendData.value.points
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { ...CHART_DEFAULTS.legend },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: points.map(p => p.exam_name) },
    yAxis: [
      { ...CHART_DEFAULTS.yAxis, type: 'value', name: '分数', nameTextStyle: { color: CHART_DEFAULTS.textStyle.color } },
      { ...CHART_DEFAULTS.yAxis, type: 'value', name: '比率', max: 1, nameTextStyle: { color: CHART_DEFAULTS.textStyle.color }, axisLabel: { ...CHART_DEFAULTS.yAxis.axisLabel, formatter: v => `${(v * 100).toFixed(0)}%` } },
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
    ...CHART_DEFAULTS,
    grid: undefined,
    xAxis: undefined,
    yAxis: undefined,
    tooltip: { ...CHART_DEFAULTS.tooltip },
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

// Boxplot: class score distribution
const boxplotOption = computed(() => {
  if (!boxplotData.value?.classes?.length) return {}
  const classes = boxplotData.value.classes
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'item' },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: classes.map(c => c.name) },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value', name: '分数' },
    series: [{
      type: 'boxplot',
      data: classes.map(c => [c.min, c.p25, c.median, c.p75, c.max]),
      itemStyle: { color: CHART_PALETTE[0], borderColor: CHART_PALETTE[1] },
    }],
  }
})

// Heatmap: class × knowledge point mastery
// 后端返回 { knowledge_points: [kp_id...], classes: [{name, mastery: [{kp_id, name, rate}]}] }
const heatmapOption = computed(() => {
  const cls = knowledgeData.value?.classes
  if (!cls?.length || !cls[0]?.mastery?.length) return {}
  const classNames = cls.map(c => c.name)
  const kpNames = cls[0].mastery.map(m => m.name)
  const data = []
  cls.forEach((c, xi) => {
    c.mastery.forEach((m, yi) => {
      data.push([xi, yi, m.rate ?? 0])
    })
  })
  return {
    ...CHART_DEFAULTS,
    tooltip: {
      ...CHART_DEFAULTS.tooltip,
      formatter: (p) => `${classNames[p.data[0]] || ''} / ${kpNames[p.data[1]] || ''}: ${(p.data[2] * 100).toFixed(0)}%`,
    },
    grid: { left: 120, right: 60, bottom: 60, top: 30 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: classNames, axisLabel: { ...CHART_DEFAULTS.xAxis?.axisLabel, rotate: 30 } },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'category', data: kpNames },
    visualMap: {
      min: 0, max: 1, calculable: true, orient: 'horizontal',
      left: 'center', bottom: 0,
      inRange: { color: ['#d94e5d', '#eac736', '#50a3ba'] },
      textStyle: { color: CHART_DEFAULTS.textStyle.color },
      formatter: v => `${(v * 100).toFixed(0)}%`,
    },
    series: [{
      type: 'heatmap',
      data,
      label: { show: data.length <= 60, formatter: p => `${(p.data[2] * 100).toFixed(0)}%`, fontSize: 10 },
    }],
  }
})

async function onGradeChange() {
  overviewData.value = null
  trendData.value = null
  subjectsData.value = null
  boxplotData.value = null
  knowledgeData.value = null
  selectedExamId.value = null
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

    // Load overview, subjects, boxplot, knowledge if exam selected
    if (selectedExamId.value) {
      const [overviewResp, subjectsResp, boxplotResp, knowledgeResp] = await Promise.all([
        getGradeOverview(selectedGradeId.value, selectedExamId.value),
        getGradeSubjects(selectedGradeId.value, selectedExamId.value),
        getClassBoxplot(selectedExamId.value).catch(() => ({ data: { classes: [] } })),
        getClassKnowledge(selectedExamId.value).catch(() => ({ data: { knowledge_points: [], classes: [] } })),
      ])
      overviewData.value = overviewResp.data
      subjectsData.value = subjectsResp.data
      boxplotData.value = boxplotResp.data
      knowledgeData.value = knowledgeResp.data
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
