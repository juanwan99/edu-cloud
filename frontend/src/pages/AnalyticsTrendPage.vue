<template>
  <div class="analytics-trend">
    <n-card title="成绩趋势">
      <n-space vertical :size="16">
        <n-space>
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

        <v-chart v-if="chartOption" :option="chartOption" style="height: 400px" />
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getGradeTrend, getClassTrend, getStudentTrend } from '../api/analytics'
import client from '../api/client'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const message = useMessage()
const loading = ref(false)
const selectedExamIds = ref([])
const dimension = ref('grade')
const selectedClassId = ref(null)
const selectedStudentId = ref(null)
const examOptions = ref([])
const classOptions = ref([])
const studentOptions = ref([])
const trendData = ref(null)

const chartOption = computed(() => {
  if (!trendData.value?.points?.length) return null
  const points = trendData.value.points
  const xData = points.map(p => p.exam_name)

  if (dimension.value === 'grade') {
    return {
      tooltip: { trigger: 'axis' },
      legend: {},
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [
        { name: '均分', type: 'line', data: points.map(p => p.avg), smooth: true },
        { name: '及格率', type: 'line', data: points.map(p => (p.pass_rate * 100).toFixed(1)), yAxisIndex: 0 },
      ],
    }
  } else if (dimension.value === 'class') {
    return {
      tooltip: { trigger: 'axis' },
      legend: {},
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [
        { name: '班级均分', type: 'line', data: points.map(p => p.class_avg), smooth: true },
        { name: '年级均分', type: 'line', data: points.map(p => p.grade_avg), smooth: true, lineStyle: { type: 'dashed' } },
      ],
    }
  } else {
    return {
      tooltip: { trigger: 'axis' },
      legend: {},
      xAxis: { type: 'category', data: xData },
      yAxis: { type: 'value' },
      series: [
        { name: '得分', type: 'line', data: points.map(p => p.score), smooth: true },
        { name: '班级均分', type: 'line', data: points.map(p => p.class_avg), smooth: true, lineStyle: { type: 'dashed' } },
      ],
    }
  }
})

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
  if (val === 'student' && studentOptions.value.length === 0) {
    try {
      const resp = await client.get('/students')
      studentOptions.value = (resp.data || []).map(s => ({ label: `${s.name} (${s.student_number})`, value: s.id }))
    } catch { /* ignore */ }
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
  } catch (e) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}
</script>
