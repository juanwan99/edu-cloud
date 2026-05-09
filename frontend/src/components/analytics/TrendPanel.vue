<template>
  <div class="trend-panel">
    <n-space vertical :size="16">
      <!-- Dimension radio -->
      <n-radio-group v-model:value="dimension" @update:value="onDimensionChange">
        <n-radio-button v-if="canViewGrade" value="grade">年级</n-radio-button>
        <n-radio-button value="class">班级</n-radio-button>
        <n-radio-button value="student">学生</n-radio-button>
      </n-radio-group>

      <!-- Metric checkboxes -->
      <n-checkbox-group v-model:value="visibleMetrics">
        <n-space>
          <n-checkbox value="avg" label="均分" />
          <n-checkbox value="pass_rate" label="及格率" />
          <n-checkbox value="excellent_rate" label="优秀率" />
        </n-space>
      </n-checkbox-group>

      <!-- Chart or empty state -->
      <n-spin :show="loading">
        <div v-if="chartOption">
          <v-chart class="chart-height-xl" :option="chartOption" />
        </div>
        <n-empty v-else-if="!loading" description="暂无趋势数据" />
      </n-spin>
    </n-space>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getGradeTrend, getClassTrend, getStudentTrend } from '../../api/analytics'
import { CHART_DEFAULTS, CHART_PALETTE } from '../../config/chartTheme.js'
import { useAuthStore } from '../../stores/auth.js'
import { normalizeRole, SCHOOL_ADMIN_ROLES } from '../../config/roles.js'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  gradeId: { type: String, default: null },
  classId: { type: String, default: null },
  subjectCode: { type: String, default: null },
})

const SERIES_COLORS = CHART_PALETTE

const auth = useAuthStore()
const currentRole = normalizeRole(auth.currentRole?.role || '')
const canViewGrade = SCHOOL_ADMIN_ROLES.includes(currentRole)
const dimension = ref(canViewGrade ? 'grade' : 'class')
const visibleMetrics = ref(['avg', 'pass_rate'])
const loading = ref(false)
const trendData = ref(null)

// --- Chart option builder (adapted from AnalyticsTrendPage) ---

function buildChartBase(xData) {
  return {
    ...CHART_DEFAULTS,
    tooltip: {
      ...CHART_DEFAULTS.tooltip,
      trigger: 'axis',
    },
    grid: { ...CHART_DEFAULTS.grid, left: 60, right: 60, bottom: 40, top: 50 },
    xAxis: {
      ...CHART_DEFAULTS.xAxis,
      type: 'category',
      data: xData,
      splitLine: { show: false },
    },
    yAxis: [
      {
        ...CHART_DEFAULTS.yAxis,
        type: 'value',
        name: '分数',
        nameTextStyle: { color: CHART_DEFAULTS.textStyle.color },
      },
      {
        ...CHART_DEFAULTS.yAxis,
        type: 'value',
        name: '百分比 (%)',
        nameTextStyle: { color: CHART_DEFAULTS.textStyle.color },
        axisLabel: { ...CHART_DEFAULTS.yAxis.axisLabel, formatter: '{value}%' },
        splitLine: { show: false },
        min: 0,
        max: 100,
      },
    ],
    series: [],
  }
}

const chartOption = computed(() => {
  if (!trendData.value?.points?.length) return null
  const points = trendData.value.points
  const xData = points.map(p => p.exam_name)
  const opt = buildChartBase(xData)
  const vm = visibleMetrics.value

  if (dimension.value === 'grade') {
    if (vm.includes('avg')) {
      opt.series.push({
        name: '均分', type: 'line', yAxisIndex: 0,
        data: points.map(p => p.avg), smooth: true,
        itemStyle: { color: SERIES_COLORS[0] },
      })
    }
    if (vm.includes('pass_rate')) {
      opt.series.push({
        name: '及格率', type: 'line', yAxisIndex: 1,
        data: points.map(p => +(p.pass_rate * 100).toFixed(1)), smooth: true,
        itemStyle: { color: SERIES_COLORS[1] },
      })
    }
    if (vm.includes('excellent_rate')) {
      opt.series.push({
        name: '优秀率', type: 'line', yAxisIndex: 1,
        data: points.map(p => +((p.excellent_rate || 0) * 100).toFixed(1)), smooth: true,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: SERIES_COLORS[2] },
      })
    }
  } else if (dimension.value === 'class') {
    if (vm.includes('avg')) {
      opt.series.push({
        name: '班级均分', type: 'line', yAxisIndex: 0,
        data: points.map(p => p.class_avg), smooth: true,
        itemStyle: { color: SERIES_COLORS[0] },
      })
      opt.series.push({
        name: '年级均分', type: 'line', yAxisIndex: 0,
        data: points.map(p => p.grade_avg), smooth: true,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: SERIES_COLORS[1] },
      })
    }
    if (vm.includes('pass_rate')) {
      opt.series.push({
        name: '及格率', type: 'line', yAxisIndex: 1,
        data: points.map(p => +((p.pass_rate || 0) * 100).toFixed(1)), smooth: true,
        itemStyle: { color: SERIES_COLORS[2] },
      })
    }
    if (vm.includes('excellent_rate')) {
      opt.series.push({
        name: '优秀率', type: 'line', yAxisIndex: 1,
        data: points.map(p => +((p.excellent_rate || 0) * 100).toFixed(1)), smooth: true,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: SERIES_COLORS[3] },
      })
    }
  } else {
    // student dimension
    if (vm.includes('avg')) {
      opt.series.push({
        name: '班级均分', type: 'line', yAxisIndex: 0,
        data: points.map(p => p.class_avg), smooth: true,
        lineStyle: { type: 'dashed' },
        itemStyle: { color: SERIES_COLORS[1] },
      })
    }
    if (vm.includes('pass_rate')) {
      opt.series.push({
        name: '及格率', type: 'line', yAxisIndex: 1,
        data: points.map(p => +((p.pass_rate || 0) * 100).toFixed(1)), smooth: true,
        itemStyle: { color: SERIES_COLORS[2] },
      })
    }
  }

  return opt
})

// --- Data loading ---

async function loadTrend() {
  loading.value = true
  trendData.value = null
  try {
    let resp
    const params = {}
    if (props.subjectCode) params.subject_code = props.subjectCode

    if (dimension.value === 'grade') {
      if (!props.gradeId || !canViewGrade) return
      params.grade_id = props.gradeId
      resp = await getGradeTrend(params)
    } else if (dimension.value === 'class') {
      if (!props.classId) return
      params.class_id = props.classId
      resp = await getClassTrend(params)
    } else {
      // student: requires classId for context
      if (!props.classId) return
      params.class_id = props.classId
      resp = await getStudentTrend(params)
    }
    trendData.value = resp.data
  } catch {
    // silently fail — empty state will show
    trendData.value = null
  } finally {
    loading.value = false
  }
}

function onDimensionChange() {
  visibleMetrics.value = ['avg', 'pass_rate']
  loadTrend()
}

// Reload when props change
watch(() => [props.gradeId, props.classId, props.subjectCode], () => {
  loadTrend()
})

onMounted(() => {
  loadTrend()
})
</script>
