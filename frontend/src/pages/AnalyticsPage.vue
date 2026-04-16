<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">数据分析</h1>
      <p class="page-subtitle">{{ examName }}</p>
    </div>

    <n-spin :show="loading">
      <!-- 概览统计卡片 -->
      <div class="stats-grid" v-if="summary">
        <div class="stat-card" style="background: var(--macaron-mint-light);">
          <div class="stat-value">{{ summary.total_students }}</div>
          <div class="stat-label">参加人数</div>
        </div>
        <div v-for="subj in summary.subjects" :key="subj.subject_id" class="stat-card"
          style="background: var(--macaron-purple-light);">
          <div class="stat-value">{{ subj.avg_score ?? '-' }}</div>
          <div class="stat-label">{{ subj.subject_name }} 平均分</div>
          <div style="font-size: 12px; color: var(--color-text-muted); margin-top: 4px;">
            最高 {{ subj.highest ?? '-' }} · 最低 {{ subj.lowest ?? '-' }}
          </div>
        </div>
      </div>

      <!-- 成绩分布图 -->
      <div style="margin-top: 40px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <h2 style="font-size: 20px; font-weight: 700;">成绩分布</h2>
          <n-select v-model:value="distSubjectId" :options="subjectFilterOptions" style="width: 180px;"
            @update:value="loadDistribution" />
        </div>
        <div style="background: white; padding: 24px; border-radius: var(--radius-lg); border: 1px solid var(--color-border-light);">
          <v-chart :option="distributionChartOption" style="height: 360px;" autoresize />
        </div>
      </div>

      <!-- 题目分析表 -->
      <div style="margin-top: 40px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <h2 style="font-size: 20px; font-weight: 700;">题目分析</h2>
          <div style="display: flex; gap: 8px; align-items: center;">
            <n-select v-model:value="questionSubjectId" :options="subjectSelectOptions" style="width: 180px;"
              placeholder="选择科目" @update:value="loadQuestionAnalysis" />
            <n-button :disabled="!questionSubjectId || exporting" :loading="exporting"
              @click="() => handleExport('pdf')">
              导出 PDF
            </n-button>
            <n-button :disabled="!questionSubjectId || exporting" :loading="exporting"
              @click="() => handleExport('xlsx')">
              导出 Excel
            </n-button>
          </div>
        </div>
        <n-data-table v-if="questionStats.length > 0" :columns="questionColumns" :data="questionStats" size="small" />
        <n-empty v-else-if="questionSubjectId && !loading" description="暂无题目数据" />
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NProgress, NTag } from 'naive-ui'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'

import { useMessage } from 'naive-ui'
import { getExamSummary, getDistribution, getSubjectQuestions, exportGradeReport, downloadBlob } from '../api/analytics'
import { getExam } from '../api/exams'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const route = useRoute()
const examId = route.params.examId
const loading = ref(true)

const examName = ref('')
const summary = ref(null)
const distribution = ref(null)
const questionStats = ref([])

const distSubjectId = ref(null)
const questionSubjectId = ref(null)
const exporting = ref(false)
const message = useMessage()

const subjectFilterOptions = computed(() => {
  const opts = [{ label: '全科', value: null }]
  if (summary.value?.subjects) {
    opts.push(...summary.value.subjects.map((s) => ({ label: s.subject_name, value: s.subject_id })))
  }
  return opts
})

const subjectSelectOptions = computed(() =>
  (summary.value?.subjects || []).map((s) => ({ label: s.subject_name, value: s.subject_id })),
)

const distributionChartOption = computed(() => {
  if (!distribution.value) return {}
  const intervals = distribution.value.intervals || []
  return {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: intervals.map((i) => i.range),
      axisLabel: { color: '#5a6b5e' },
    },
    yAxis: {
      type: 'value',
      name: '人数',
      axisLabel: { color: '#5a6b5e' },
    },
    series: [{
      type: 'bar',
      data: intervals.map((i) => i.count),
      itemStyle: {
        color: '#2d5a3d',
        borderRadius: [6, 6, 0, 0],
      },
      barWidth: '50%',
    }],
    grid: { left: 60, right: 20, top: 40, bottom: 40 },
  }
})

const questionColumns = [
  { title: '题目', key: 'question_name', ellipsis: { tooltip: true } },
  {
    title: '类型', key: 'question_type', width: 80,
    render: (row) => h(NTag, { size: 'small', round: true }, { default: () => row.question_type === 'subjective' ? '主观' : '客观' }),
  },
  { title: '满分', key: 'max_score', width: 60 },
  { title: '平均分', key: 'avg_score', width: 80 },
  {
    title: '得分率', key: 'score_rate', width: 200,
    render: (row) => {
      const pct = Math.round((row.score_rate || 0) * 100)
      const color = pct < 60 ? '#dc3545' : pct < 80 ? '#d97706' : '#16a34a'
      return h(NProgress, {
        type: 'line',
        percentage: pct,
        indicatorPlacement: 'inside',
        color,
        railColor: pct < 60 ? 'var(--macaron-coral-light)' : pct < 80 ? 'var(--macaron-yellow-light)' : 'var(--macaron-mint-light)',
        style: 'width: 160px;',
      })
    },
  },
  { title: '批改数', key: 'graded_count', width: 80 },
]

async function loadDistribution() {
  try {
    const params = distSubjectId.value ? { subject_id: distSubjectId.value } : {}
    const { data } = await getDistribution(examId, params)
    distribution.value = data
  } catch { /* interceptor */ }
}

async function loadQuestionAnalysis(subjectId) {
  if (!subjectId) { questionStats.value = []; return }
  try {
    const { data } = await getSubjectQuestions(subjectId)
    questionStats.value = data.questions || []
  } catch { /* interceptor */ }
}

async function handleExport(format) {
  if (!questionSubjectId.value) {
    message.warning('请先选择科目')
    return
  }
  exporting.value = true
  try {
    const resp = await exportGradeReport(examId, questionSubjectId.value, format)
    downloadBlob(resp, `年级报告.${format}`)
  } catch (e) {
    message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(async () => {
  try {
    const [examRes, summaryRes] = await Promise.all([
      getExam(examId),
      getExamSummary(examId),
    ])
    examName.value = examRes.data.name
    summary.value = summaryRes.data
    await loadDistribution()
  } catch { /* interceptor */ }
  loading.value = false
})
</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}
</style>
