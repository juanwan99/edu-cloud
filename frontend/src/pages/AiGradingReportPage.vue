<template>
  <div class="page-wrap ai-grading-report">
    <div class="page-header">
      <h1 class="page-title">AI 阅卷报告</h1>
    </div>

    <n-space vertical :size="16">
      <n-space wrap>
        <n-select
          v-model:value="selectedExamId"
          :options="examOptions"
          filterable
          placeholder="选择考试"
          style="min-width: 320px"
        />
        <n-select
          v-model:value="selectedSubjectId"
          :options="subjectOptions"
          placeholder="科目"
          style="min-width: 160px"
          clearable
        />
        <n-select
          v-model:value="selectedClassId"
          :options="classOptions"
          placeholder="班级"
          style="min-width: 160px"
          clearable
        />
        <n-button type="primary" :loading="loading" @click="loadReport">
          生成报告
        </n-button>
      </n-space>

      <n-spin :show="loading">
        <template v-if="report">
          <n-alert
            v-for="warning in report.data_warnings || []"
            :key="warning.type"
            type="warning"
            class="report-alert"
          >
            {{ warning.message || formatWarning(warning) }}
          </n-alert>

          <n-card title="AI 阅卷总览" size="small">
            <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen">
              <n-gi>
                <n-statistic label="答题记录" :value="coverage.answer_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="AI 已评分" :value="coverage.ai_scored_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="人工已确认" :value="coverage.confirmed_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="待复核" :value="coverage.pending_review_count || 0" />
              </n-gi>
            </n-grid>
          </n-card>

          <n-card title="置信度分布" size="small">
            <div class="confidence-layout">
              <div class="metric-stack">
                <div class="metric-line">
                  <span>平均置信度</span>
                  <strong>{{ pct(confidence.avg_confidence) }}</strong>
                </div>
                <div class="metric-line">
                  <span>低置信度</span>
                  <strong>{{ confidence.low_confidence_count || 0 }}</strong>
                </div>
              </div>
              <v-chart class="chart-height-sm confidence-chart" :option="confidenceChartOption" />
            </div>
          </n-card>

          <n-card title="质量审计" size="small">
            <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen">
              <n-gi>
                <n-statistic label="AI/最终分样本" :value="quality.ai_human_delta_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="平均绝对差" :value="quality.avg_abs_delta ?? '-'" />
              </n-gi>
              <n-gi>
                <n-statistic label="人工改分数" :value="quality.override_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="改分率" :value="pct(quality.override_rate)" />
              </n-gi>
            </n-grid>
            <n-data-table
              v-if="quality.question_delta_top?.length"
              class="section-table"
              :columns="deltaColumns"
              :data="quality.question_delta_top"
              size="small"
              :pagination="false"
            />
          </n-card>

          <n-card title="OCR 与流水线" size="small">
            <n-grid :cols="4" :x-gap="12" :y-gap="12" responsive="screen">
              <n-gi>
                <n-statistic label="流水线日志" :value="pipeline.log_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="空白识别" :value="pipeline.blank_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="错误日志" :value="pipeline.error_count || 0" />
              </n-gi>
              <n-gi>
                <n-statistic label="平均耗时(ms)" :value="pipeline.avg_total_ms ?? '-'" />
              </n-gi>
            </n-grid>
          </n-card>

          <n-card title="题目诊断" size="small">
            <n-data-table
              :columns="questionColumns"
              :data="report.question_diagnostics || []"
              size="small"
              :pagination="{ pageSize: 10 }"
            />
          </n-card>

          <n-card title="学生预警" size="small">
            <n-data-table
              :columns="studentColumns"
              :data="report.student_watchlist || []"
              size="small"
              :pagination="{ pageSize: 10 }"
            />
          </n-card>

          <n-card title="教学建议" size="small">
            <n-data-table
              :columns="actionColumns"
              :data="report.teaching_actions || []"
              size="small"
              :pagination="false"
            />
          </n-card>
        </template>
      </n-spin>
    </n-space>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import client from '../api/client'
import { getAiGradingReport, getExamSummary } from '../api/analytics'
import { CHART_DEFAULTS, CHART_PALETTE } from '../config/chartTheme.js'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const message = useMessage()
const loading = ref(false)
const selectedExamId = ref(null)
const selectedSubjectId = ref(null)
const selectedClassId = ref(null)
const examOptions = ref([])
const subjectOptions = ref([])
const classOptions = ref([])
const report = ref(null)

const coverage = computed(() => report.value?.coverage || {})
const confidence = computed(() => report.value?.confidence || {})
const quality = computed(() => report.value?.quality || {})
const pipeline = computed(() => report.value?.ocr_pipeline || {})

const confidenceChartOption = computed(() => {
  const buckets = confidence.value.buckets || {}
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    grid: { ...CHART_DEFAULTS.grid, left: 40, right: 20, top: 20, bottom: 30 },
    xAxis: {
      ...CHART_DEFAULTS.xAxis,
      type: 'category',
      data: ['高', '中', '低'],
    },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [{
      type: 'bar',
      data: [buckets.high || 0, buckets.medium || 0, buckets.low || 0],
      itemStyle: { color: CHART_PALETTE[0] },
      barWidth: '42%',
    }],
  }
})

const deltaColumns = [
  { title: '题目', key: 'question_name' },
  { title: '改分样本', key: 'count' },
  { title: '平均差', key: 'avg_abs_delta' },
  { title: '最大差', key: 'max_abs_delta' },
]

const questionColumns = [
  { title: '题目', key: 'question_name' },
  { title: '科目', key: 'subject_name' },
  { title: '得分率', key: 'score_rate', render: row => pct(row.score_rate) },
  { title: '低置信度', key: 'low_confidence_count' },
  { title: '平均差', key: 'avg_abs_delta', render: row => row.avg_abs_delta ?? '-' },
  { title: '主要错因', key: 'error_causes', render: row => row.error_causes?.[0]?.cause || '-' },
]

const studentColumns = [
  { title: '学生', key: 'student_name', render: row => row.student_name || row.student_id },
  { title: '得分率', key: 'score_rate', render: row => pct(row.score_rate) },
  { title: '低置信度', key: 'low_confidence_count' },
  { title: '待复核', key: 'pending_review_count' },
  { title: '异常', key: 'anomaly_count' },
]

const actionColumns = [
  { title: '优先级', key: 'priority' },
  { title: '建议', key: 'title' },
  { title: '类型', key: 'type' },
]

function pct(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function formatWarning(warning) {
  if (warning.type === 'unmatched_student_ids') {
    return `有 ${warning.count} 个学生条码未匹配：${(warning.samples || []).join('、')}`
  }
  return warning.type
}

async function loadReport() {
  if (!selectedExamId.value) {
    message.warning('请选择考试')
    return
  }
  loading.value = true
  try {
    const params = {}
    if (selectedSubjectId.value) params.subject_id = selectedSubjectId.value
    if (selectedClassId.value) params.class_id = selectedClassId.value
    const { data } = await getAiGradingReport(selectedExamId.value, params)
    report.value = data
  } catch (e) {
    message.error(e.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadSubjects(examId) {
  selectedSubjectId.value = null
  subjectOptions.value = []
  if (!examId) return
  try {
    const { data } = await getExamSummary(examId)
    subjectOptions.value = (data.subjects || []).map(subject => ({
      label: subject.subject_name,
      value: subject.subject_id,
    }))
  } catch { /* ignore */ }
}

onMounted(async () => {
  try {
    const { data } = await client.get('/exams')
    examOptions.value = (data || []).map(exam => ({ label: exam.name, value: exam.id }))
  } catch { /* ignore */ }
  try {
    const { data } = await client.get('/classes')
    classOptions.value = (data || []).map(cls => ({ label: cls.name, value: cls.id }))
  } catch { /* ignore */ }
})

watch(selectedExamId, async (examId) => {
  report.value = null
  await loadSubjects(examId)
})
</script>

<style scoped>
.report-alert {
  margin-bottom: var(--space-3);
}

.confidence-layout {
  display: grid;
  grid-template-columns: minmax(180px, 240px) 1fr;
  gap: var(--space-4);
  align-items: center;
}

.metric-stack {
  display: grid;
  gap: var(--space-3);
}

.metric-line {
  display: flex;
  justify-content: space-between;
  padding: var(--space-3);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-soft);
}

.confidence-chart {
  min-height: 180px;
}

.section-table {
  margin-top: var(--space-4);
}

@media (max-width: 720px) {
  .confidence-layout {
    grid-template-columns: 1fr;
  }
}
</style>
