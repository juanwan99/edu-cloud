<template>
  <div class="analytics-trend">
    <n-card title="成绩趋势">
      <n-space vertical :size="16">
        <!-- 筛选器行 -->
        <n-space wrap>
          <n-select
            v-model:value="selectedExamIds"
            :options="examOptions"
            multiple
            placeholder="选择考试（至少2次）"
            style="min-width: 300px"
          />
          <n-radio-group v-model:value="dimension">
            <n-radio-button value="grade">年级</n-radio-button>
            <n-radio-button value="class">班级</n-radio-button>
            <n-radio-button value="student">学生</n-radio-button>
          </n-radio-group>
          <n-select
            v-if="dimension === 'class'"
            v-model:value="selectedClassId"
            :options="classOptions"
            placeholder="选择班级"
            style="min-width: 150px"
          />
          <n-select
            v-if="dimension === 'student'"
            v-model:value="selectedStudentId"
            :options="studentOptions"
            placeholder="选择学生"
            filterable
            style="min-width: 150px"
          />
          <n-button type="primary" @click="loadTrend" :loading="loading">
            查看趋势
          </n-button>
        </n-space>

        <!-- 对比模式：选择 2 个班级/学生同图对比 -->
        <n-space v-if="dimension === 'class' || dimension === 'student'" align="center">
          <span style="font-size: 13px; color: rgba(255,255,255,0.5);">对比模式：</span>
          <n-select
            v-model:value="compareIds"
            :options="dimension === 'class' ? classOptions : studentOptions"
            multiple
            :max-tag-count="2"
            placeholder="选择 2 个对比对象（可选）"
            :filterable="dimension === 'student'"
            style="min-width: 280px"
          />
        </n-space>

        <!-- 指标选择器 -->
        <n-space v-if="trendData" align="center">
          <span style="font-size: 13px; color: rgba(255,255,255,0.5);">显示指标：</span>
          <n-checkbox-group v-model:value="visibleMetrics">
            <n-space>
              <n-checkbox value="avg" label="均分" />
              <n-checkbox value="pass_rate" label="及格率" />
              <n-checkbox value="excellent_rate" label="优秀率" />
              <n-checkbox value="score" label="得分" v-if="dimension === 'student'" />
            </n-space>
          </n-checkbox-group>
        </n-space>

        <!-- 图表区域 -->
        <div v-if="chartOption" style="position: relative;">
          <n-button
            size="small"
            quaternary
            style="position: absolute; right: 8px; top: 0; z-index: 2;"
            @click="exportChart"
          >
            导出图片
          </n-button>
          <v-chart ref="chartRef" class="chart-height-xl" :option="chartOption" />
        </div>
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, DataZoomComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getGradeTrend, getClassTrend, getStudentTrend } from '../api/analytics'
import client from '../api/client'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer])

const message = useMessage()
const chartRef = ref(null)
const loading = ref(false)
const selectedExamIds = ref([])
const dimension = ref('grade')
const selectedClassId = ref(null)
const selectedStudentId = ref(null)
const compareIds = ref([])
const examOptions = ref([])
const classOptions = ref([])
const studentOptions = ref([])
const trendData = ref(null)
const visibleMetrics = ref(['avg', 'pass_rate'])

// 暗色主题样式常量
const DARK_TEXT = 'rgba(255, 255, 255, 0.65)'
const DARK_SPLIT = 'rgba(255, 255, 255, 0.08)'
const DARK_AXIS = 'rgba(255, 255, 255, 0.35)'
const SERIES_COLORS = ['#18a058', '#2080f0', '#f0a020', '#d03050', '#9254de', '#36cfc9']

function buildDarkThemeBase(xData) {
  return {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 30, 30, 0.95)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: DARK_TEXT },
    },
    legend: {
      textStyle: { color: DARK_TEXT },
    },
    grid: { left: 60, right: 60, bottom: 40, top: 50 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLabel: { color: DARK_TEXT },
      axisLine: { lineStyle: { color: DARK_AXIS } },
      splitLine: { show: false },
    },
    yAxis: [
      {
        type: 'value',
        name: '分数',
        nameTextStyle: { color: DARK_TEXT },
        axisLabel: { color: DARK_TEXT },
        splitLine: { lineStyle: { color: DARK_SPLIT } },
      },
      {
        type: 'value',
        name: '百分比 (%)',
        nameTextStyle: { color: DARK_TEXT },
        axisLabel: { color: DARK_TEXT, formatter: '{value}%' },
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
  const opt = buildDarkThemeBase(xData)
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
    // 对比模式：多班级叠加
    if (compareIds.value.length && trendData.value.compare_series) {
      trendData.value.compare_series.forEach((cs, i) => {
        opt.series.push({
          name: cs.label,
          type: 'line', yAxisIndex: 0,
          data: cs.points.map(p => p.class_avg),
          smooth: true,
          lineStyle: { type: 'dotted' },
          itemStyle: { color: SERIES_COLORS[(i + 3) % SERIES_COLORS.length] },
        })
      })
    }
  } else {
    if (vm.includes('score')) {
      opt.series.push({
        name: '得分', type: 'line', yAxisIndex: 0,
        data: points.map(p => p.score), smooth: true,
        itemStyle: { color: SERIES_COLORS[0] },
      })
    }
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
    // 对比模式：多学生叠加
    if (compareIds.value.length && trendData.value.compare_series) {
      trendData.value.compare_series.forEach((cs, i) => {
        opt.series.push({
          name: cs.label,
          type: 'line', yAxisIndex: 0,
          data: cs.points.map(p => p.score),
          smooth: true,
          lineStyle: { type: 'dotted' },
          itemStyle: { color: SERIES_COLORS[(i + 3) % SERIES_COLORS.length] },
        })
      })
    }
  }

  return opt
})

function exportChart() {
  const chart = chartRef.value?.chart
  if (!chart) {
    message.warning('图表未就绪')
    return
  }
  const url = chart.getDataURL({ type: 'png', backgroundColor: '#1e1e1e', pixelRatio: 2 })
  const a = document.createElement('a')
  a.href = url
  a.download = `trend-${dimension.value}-${Date.now()}.png`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  message.success('图表已导出')
}

onMounted(async () => {
  try {
    const resp = await client.get('/exams')
    examOptions.value = (resp.data || []).map(e => ({ label: e.name, value: e.id }))
  } catch { /* ignore */ }
  try {
    const resp = await client.get('/classes')
    classOptions.value = (resp.data || []).map(c => ({ label: c.name, value: c.id }))
  } catch { /* ignore */ }
})

watch(dimension, async (val) => {
  compareIds.value = []
  if (val === 'student' && studentOptions.value.length === 0) {
    try {
      const resp = await client.get('/students')
      studentOptions.value = (resp.data || []).map(s => ({ label: `${s.name} (${s.student_number})`, value: s.id }))
    } catch { /* ignore */ }
  }
  // Reset metrics to reasonable defaults per dimension
  if (val === 'student') {
    visibleMetrics.value = ['score', 'avg']
  } else {
    visibleMetrics.value = ['avg', 'pass_rate']
  }
})

async function loadTrend() {
  if (selectedExamIds.value.length < 1) {
    message.warning('请至少选择一次考试')
    return
  }
  loading.value = true
  try {
    const examIdsStr = selectedExamIds.value.join(',')
    let resp
    if (dimension.value === 'grade') {
      resp = await getGradeTrend({ exam_ids: examIdsStr })
    } else if (dimension.value === 'class') {
      if (!selectedClassId.value) { message.warning('请选择班级'); loading.value = false; return }
      resp = await getClassTrend({ exam_ids: examIdsStr, class_id: selectedClassId.value })
    } else {
      if (!selectedStudentId.value) { message.warning('请选择学生'); loading.value = false; return }
      resp = await getStudentTrend({ exam_ids: examIdsStr, student_id: selectedStudentId.value })
    }
    trendData.value = resp.data

    // 对比模式：并发加载对比系列
    if (compareIds.value.length > 0 && compareIds.value.length <= 2) {
      const compareSeries = []
      for (const cid of compareIds.value) {
        try {
          let cResp
          if (dimension.value === 'class') {
            cResp = await getClassTrend({ exam_ids: examIdsStr, class_id: cid })
            const cls = classOptions.value.find(o => o.value === cid)
            compareSeries.push({ label: cls?.label || `班级${cid}`, points: cResp.data?.points || [] })
          } else {
            cResp = await getStudentTrend({ exam_ids: examIdsStr, student_id: cid })
            const stu = studentOptions.value.find(o => o.value === cid)
            compareSeries.push({ label: stu?.label || `学生${cid}`, points: cResp.data?.points || [] })
          }
        } catch { /* skip failed compare */ }
      }
      trendData.value = { ...trendData.value, compare_series: compareSeries }
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}
</script>
