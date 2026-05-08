<template>
  <div class="page-wrap analytics-report">
    <div class="page-header">
      <h1 class="page-title">成绩分析</h1>
    </div>

    <n-space vertical :size="16">
      <div class="report-toolbar">
        <n-select
          v-model:value="selectedExamId"
          :options="examOptions"
          placeholder="选择考试"
          class="toolbar-select"
        />
        <n-select
          v-model:value="selectedSubjectId"
          :options="subjectFilterOptions"
          placeholder="全部科目"
          class="toolbar-select"
          clearable
        />
        <n-select
          v-model:value="selectedClassId"
          :options="classOptions"
          placeholder="全部班级"
          class="toolbar-select"
          clearable
        />
        <n-select
          v-model:value="exportSubjectId"
          :options="subjectOptions"
          placeholder="选择导出科目"
          class="toolbar-select"
          clearable
        />
        <n-button type="primary" @click="runQuery" :loading="loading">
          查看基础数据
        </n-button>
        <n-button
          @click="() => handleDownload('pdf')"
          :loading="exporting"
          :disabled="!canExport"
        >
          导出 PDF
        </n-button>
        <n-button
          @click="() => handleDownload('xlsx')"
          :loading="exporting"
          :disabled="!canExport"
        >
          导出 Excel
        </n-button>
      </div>

      <template v-if="basicReport">
        <section class="report-head">
          <div>
            <p class="section-kicker">成绩分析</p>
            <h2>{{ basicReport.exam?.name || '考试成绩' }}</h2>
          </div>
          <div class="report-meta-wrap">
            <div class="report-meta">
              <span>科目 {{ basicReport.overview?.subject_count ?? (basicReport.subjects || []).length }}</span>
              <span>满分 {{ fmt(basicReport.overview?.total_full_score) }}</span>
              <span v-if="!basicReport.scope?.has_previous_exam">暂无进退步</span>
            </div>
            <div class="scope-tags">
              <span v-for="tag in scopeTags" :key="tag">{{ tag }}</span>
            </div>
          </div>
        </section>

        <n-empty
          v-if="!hasReportData"
          description="当前筛选范围暂无成绩数据"
          class="report-empty"
        />
        <n-tabs v-else v-model:value="activeTab" type="line" animated>
          <n-tab-pane name="overview" tab="总览">
            <div class="overview-card-grid">
              <div
                v-for="item in overviewCards"
                :key="item.label"
                class="stat-card"
              >
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>
            <div class="panel-grid">
              <div class="report-panel">
                <h3>分数分布</h3>
                <v-chart class="chart-height-xl" :option="segmentChartOption" />
              </div>
              <div class="report-panel">
                <h3>年级排名趋势</h3>
                <v-chart class="chart-height-xl" :option="rankTrendChartOption" />
              </div>
            </div>
          </n-tab-pane>

          <n-tab-pane name="subjects" tab="科目分析">
            <div class="panel-grid">
              <div class="report-panel">
                <h3>各科平均得分率</h3>
                <v-chart class="chart-height-xl" :option="subjectRateChartOption" />
              </div>
              <div class="report-panel">
                <h3>科目详情</h3>
                <n-data-table
                  :columns="subjectColumns"
                  :data="basicReport.subjects || []"
                  :pagination="false"
                  :scroll-x="920"
                  size="small"
                />
              </div>
            </div>
          </n-tab-pane>

          <n-tab-pane name="classes" tab="班级对比">
            <div class="stack-layout">
              <div class="report-panel">
                <h3>班级平均分对比</h3>
                <v-chart class="chart-height-xl" :option="classCompareChartOption" />
              </div>
              <div class="report-panel">
                <h3>班级详细数据</h3>
                <n-data-table
                  :columns="classColumns"
                  :data="basicReport.classes || []"
                  :pagination="{ pageSize: 30 }"
                  :scroll-x="920"
                  size="small"
                />
              </div>
            </div>
          </n-tab-pane>

          <n-tab-pane name="students" tab="学生排名">
            <div class="report-panel">
              <div class="student-rank-tools">
                <h3>学生排名</h3>
                <div class="student-rank-actions">
                  <n-input
                    v-model:value="studentKeyword"
                    placeholder="搜索学生姓名/学号/班级"
                    clearable
                    size="small"
                    class="student-search"
                  />
                  <n-button
                    size="small"
                    :disabled="!filteredStudentRows.length"
                    @click="exportStudentRank"
                  >
                    导出排名
                  </n-button>
                </div>
              </div>
              <n-data-table
                :columns="studentColumns"
                :data="filteredStudentRows"
                :pagination="{ pageSize: 30 }"
                :scroll-x="studentTableScrollX"
                size="small"
              />
            </div>
          </n-tab-pane>

          <n-tab-pane name="knowledge" tab="知识点诊断">
            <KnowledgeDiagnosisPanel
              v-if="selectedExamId"
              :exam-id="selectedExamId"
              :subject-id="selectedSubjectId"
              :class-id="selectedClassId"
            />
            <n-empty v-else description="请先选择考试" />
          </n-tab-pane>

          <n-tab-pane name="layers" tab="学生/分层学情">
            <div class="report-panel" v-if="filteredStudentRows.length">
              <div class="student-rank-tools">
                <h3>学生排名</h3>
                <n-input
                  v-model:value="studentKeyword"
                  placeholder="搜索学生姓名/学号/班级"
                  clearable
                  size="small"
                  class="student-search"
                />
              </div>
              <n-data-table
                :columns="studentColumns"
                :data="filteredStudentRows"
                :pagination="{ pageSize: 20 }"
                :scroll-x="studentTableScrollX"
                size="small"
              />
            </div>
            <n-divider v-if="filteredStudentRows.length" />
            <LayerAnalysisPanel
              v-if="selectedExamId"
              :exam-id="selectedExamId"
              :subject-id="selectedSubjectId"
              :class-id="selectedClassId"
            />
            <n-empty v-if="!selectedExamId" description="请先选择考试" />
          </n-tab-pane>

          <n-tab-pane name="trend" tab="趋势追踪">
            <TrendPanel
              :grade-id="currentGradeId"
              :class-id="selectedClassId"
              :subject-code="currentSubjectCode"
            />
          </n-tab-pane>

          <n-tab-pane name="ai-report" tab="AI 综合报告">
            <AiDiagnosisReport
              :exam-id="selectedExamId || ''"
              :subject-id="selectedSubjectId"
              :class-id="selectedClassId"
            />
          </n-tab-pane>
        </n-tabs>
      </template>
      <n-empty
        v-else
        description="请选择考试后查看基础数据"
        class="report-empty"
      />
    </n-space>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getBasicReport, exportGradeReport, downloadBlob } from '../api/analytics'
import client from '../api/client'
import { CHART_DEFAULTS, CHART_PALETTE } from '../config/chartTheme.js'
import KnowledgeDiagnosisPanel from '../components/analytics/KnowledgeDiagnosisPanel.vue'
import LayerAnalysisPanel from '../components/analytics/LayerAnalysisPanel.vue'
import TrendPanel from '../components/analytics/TrendPanel.vue'
import AiDiagnosisReport from '../components/analytics/AiDiagnosisReport.vue'

use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const route = useRoute()
const message = useMessage()
const loading = ref(false)
const exporting = ref(false)
const basicReport = ref(null)
const selectedExamId = ref(null)
const selectedSubjectId = ref(null)
const selectedClassId = ref(null)
const exportSubjectId = ref(null)
const examOptions = ref([])
const classOptions = ref([])
const availableSubjects = ref([])
const validTabs = ['overview', 'subjects', 'classes', 'students', 'knowledge', 'layers', 'trend', 'ai-report']
const activeTab = ref(validTabs.includes(route.query.tab) ? route.query.tab : 'overview')
const studentKeyword = ref('')

const currentGradeId = computed(() => basicReport.value?.scope?.grade_id || null)
const currentSubjectCode = computed(() => {
  if (!selectedSubjectId.value || !availableSubjects.value.length) return null
  const s = availableSubjects.value.find(s => (s.subject_id || s.id) === selectedSubjectId.value)
  return s?.code || s?.subject_code || null
})

const canExport = computed(
  () => !!selectedExamId.value && !!exportSubjectId.value && !exporting.value,
)

const subjectOptions = computed(() => {
  const reportSubjects = basicReport.value?.subjects || []
  const source = reportSubjects.length ? reportSubjects : availableSubjects.value
  return source.map(subject => ({
    label: subject.subject_name || subject.name,
    value: subject.subject_id || subject.id,
  }))
})

const subjectFilterOptions = computed(() => [
  { label: '全部科目', value: null },
  ...subjectOptions.value,
])

const hasReportData = computed(() => {
  const overview = basicReport.value?.overview || {}
  return Number(overview.student_count || 0) > 0
    || (basicReport.value?.students || []).length > 0
    || (basicReport.value?.classes || []).length > 0
    || (basicReport.value?.subjects || []).length > 0
})

const scopeTags = computed(() => {
  const report = basicReport.value
  if (!report) return []
  const scope = report.scope || {}
  return [
    `科目：${scope.subject_name || selectedLabel(subjectFilterOptions.value, selectedSubjectId.value, '全部科目')}`,
    `班级：${scope.class_name || selectedLabel(classOptions.value, selectedClassId.value, '全部班级')}`,
    scope.previous_exam?.name ? `对比：${scope.previous_exam.name}` : null,
  ].filter(Boolean)
})

const overviewCards = computed(() => {
  const overview = basicReport.value?.overview || {}
  const students = basicReport.value?.students || []
  const fullScore = Number(overview.total_full_score)
  const fullScoreCount = overview.full_score_count ?? (
    Number.isFinite(fullScore)
      ? students.filter(row => Math.abs(Number(row.total_score) - fullScore) < 0.01).length
      : 0
  )
  return [
    { label: '平均分', value: fmt(overview.avg_score) },
    { label: '及格率', value: pct(overview.pass_rate) },
    { label: '优秀率', value: pct(overview.excellent_rate) },
    { label: '满分人数', value: fullScoreCount },
  ]
})

const subjectColumns = [
  { title: '科目', key: 'subject_name', width: 100 },
  { title: '满分', key: 'full_score', width: 80, render: row => fmt(row.full_score) },
  { title: '参考人数', key: 'student_count', width: 90 },
  { title: '平均分', key: 'avg_score', width: 90, render: row => fmt(row.avg_score) },
  { title: '最高分', key: 'max_score', width: 90, render: row => fmt(row.max_score) },
  { title: '最低分', key: 'min_score', width: 90, render: row => fmt(row.min_score) },
  { title: '得分率', key: 'score_rate', width: 90, render: row => pct(row.score_rate) },
  { title: '及格率', key: 'pass_rate', width: 90, render: row => pct(row.pass_rate) },
  { title: '优秀率', key: 'excellent_rate', width: 90, render: row => pct(row.excellent_rate) },
]

const classColumns = [
  { title: '排名', key: 'rank', width: 70 },
  { title: '班级', key: 'class_name', width: 120 },
  { title: '参考人数', key: 'student_count', width: 90 },
  { title: '平均分', key: 'avg_score', width: 90, render: row => fmt(row.avg_score) },
  { title: '最高分', key: 'max_score', width: 90, render: row => fmt(row.max_score) },
  { title: '最低分', key: 'min_score', width: 90, render: row => fmt(row.min_score) },
  { title: '得分率', key: 'score_rate', width: 90, render: row => pct(row.score_rate) },
  { title: '及格率', key: 'pass_rate', width: 90, render: row => pct(row.pass_rate) },
  { title: '优秀率', key: 'excellent_rate', width: 90, render: row => pct(row.excellent_rate) },
]

const classSubjectColumns = [
  { title: '班级', key: 'class_name', width: 120 },
  { title: '科目', key: 'subject_name', width: 100 },
  { title: '满分', key: 'full_score', width: 80, render: row => fmt(row.full_score) },
  { title: '参考人数', key: 'student_count', width: 90 },
  { title: '平均分', key: 'avg_score', width: 90, render: row => fmt(row.avg_score) },
  { title: '最高分', key: 'max_score', width: 90, render: row => fmt(row.max_score) },
  { title: '最低分', key: 'min_score', width: 90, render: row => fmt(row.min_score) },
  { title: '得分率', key: 'score_rate', width: 90, render: row => pct(row.score_rate) },
  { title: '及格率', key: 'pass_rate', width: 90, render: row => pct(row.pass_rate) },
  { title: '优秀率', key: 'excellent_rate', width: 90, render: row => pct(row.excellent_rate) },
]

const segmentColumns = [
  { title: '分数段', key: 'label' },
  { title: '区间', key: 'range', render: row => segmentRange(row) },
  { title: '人数', key: 'count' },
  { title: '占比', key: 'percentage', render: row => pct(row.percentage) },
]

const studentColumns = computed(() => [
  { title: '排名', key: 'grade_rank', width: 70 },
  { title: '姓名', key: 'name', width: 100 },
  { title: '班级', key: 'class_name', width: 120 },
  { title: '学号', key: 'student_number', width: 110, render: row => row.student_number || '-' },
  ...subjectScoreColumns.value,
  { title: '总分', key: 'total_score', width: 90, render: row => fmt(row.total_score) },
  { title: '得分率', key: 'score_rate', width: 90, render: row => pct(row.score_rate) },
  { title: '班级排名', key: 'class_rank', width: 90 },
  { title: '年级进退', key: 'delta_grade', width: 100, render: row => formatDelta(row.delta_grade) },
  { title: '班级进退', key: 'delta_class', width: 100, render: row => formatDelta(row.delta_class) },
])

const subjectScoreColumns = computed(() => (basicReport.value?.subjects || []).map(subject => ({
  title: subject.subject_name,
  key: `subject_${subject.subject_code}`,
  width: 90,
  render: row => fmt(row.subject_scores?.[subject.subject_code]?.score),
})))

const studentRows = computed(() => basicReport.value?.students || [])

const filteredStudentRows = computed(() => {
  const keyword = studentKeyword.value.trim().toLowerCase()
  if (!keyword) return studentRows.value
  return studentRows.value.filter(row => [
    row.name,
    row.student_number,
    row.class_name,
  ].some(value => String(value || '').toLowerCase().includes(keyword)))
})

const studentTableScrollX = computed(() => 820 + subjectScoreColumns.value.length * 96)

const classSubjectRows = computed(() => (basicReport.value?.classes || []).flatMap(row => (
  row.subjects || []
).map(subject => ({
  ...subject,
  class_id: row.class_id,
  class_name: row.class_name,
}))))

const segmentChartOption = computed(() => {
  const segments = basicReport.value?.distribution || []
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    grid: { left: 36, right: 16, top: 32, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: segments.map(s => s.label) },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [{
      type: 'bar',
      data: segments.map(s => s.count),
      barMaxWidth: 34,
      label: { show: true, position: 'top' },
      itemStyle: { color: CHART_PALETTE[3] },
    }],
  }
})

const subjectRateChartOption = computed(() => {
  const subjects = basicReport.value?.subjects || []
  return {
    ...CHART_DEFAULTS,
    tooltip: {
      ...CHART_DEFAULTS.tooltip,
      trigger: 'axis',
      valueFormatter: value => `${fmt(value)}%`,
    },
    grid: { left: 44, right: 16, top: 32, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: subjects.map(s => s.subject_name) },
    yAxis: {
      ...CHART_DEFAULTS.yAxis,
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%' },
    },
    series: [{
      name: '得分率',
      type: 'bar',
      data: subjects.map(s => rateNumber(s.score_rate)),
      barMaxWidth: 34,
      label: { show: true, position: 'top', formatter: '{c}%' },
      itemStyle: { color: CHART_PALETTE[0] },
    }],
  }
})

const rankTrendChartOption = computed(() => {
  const overview = basicReport.value?.overview || {}
  const examName = basicReport.value?.exam?.name || '本次考试'
  const fullScore = Number(overview.total_full_score)
  const passLine = Number.isFinite(fullScore) && fullScore > 0 ? roundNumber(fullScore * 0.6) : null
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { top: 0, data: ['平均分', '最高分', '及格线'] },
    grid: { left: 44, right: 16, top: 42, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: [examName] },
    yAxis: { ...CHART_DEFAULTS.yAxis, type: 'value' },
    series: [
      {
        name: '平均分',
        type: 'line',
        data: [chartNumber(overview.avg_score)],
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[0] },
      },
      {
        name: '最高分',
        type: 'line',
        data: [chartNumber(overview.max_score)],
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[1] },
      },
      {
        name: '及格线',
        type: 'line',
        data: [passLine],
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[2] },
      },
    ],
  }
})

const classCompareChartOption = computed(() => {
  const classes = basicReport.value?.classes || []
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    legend: { top: 0, data: ['平均分', '及格率'] },
    grid: { left: 44, right: 44, top: 42, bottom: 34 },
    xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: classes.map(row => row.class_name) },
    yAxis: [
      { ...CHART_DEFAULTS.yAxis, type: 'value' },
      { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    ],
    series: [
      {
        name: '平均分',
        type: 'bar',
        data: classes.map(row => chartNumber(row.avg_score)),
        barMaxWidth: 34,
        label: { show: true, position: 'top' },
        itemStyle: { color: CHART_PALETTE[0] },
      },
      {
        name: '及格率',
        type: 'line',
        yAxisIndex: 1,
        data: classes.map(row => rateNumber(row.pass_rate)),
        smooth: true,
        symbolSize: 8,
        itemStyle: { color: CHART_PALETTE[2] },
      },
    ],
  }
})

function roundNumber(value) {
  if (value == null || Number.isNaN(Number(value))) return null
  return Math.round(Number(value) * 10) / 10
}

function chartNumber(value) {
  return roundNumber(value)
}

function rateNumber(value) {
  if (value == null || Number.isNaN(Number(value))) return 0
  return Math.round(Number(value) * 1000) / 10
}

function fmt(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  const n = Number(value)
  return Number.isInteger(n) ? String(n) : n.toFixed(1)
}

function pct(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function formatDelta(value) {
  if (value == null || Number.isNaN(Number(value))) return '-'
  const n = Number(value)
  if (n > 0) return `进 ${n}`
  if (n < 0) return `退 ${Math.abs(n)}`
  return '持平'
}

function segmentRange(row) {
  if (row.boundary_min == null || row.boundary_max == null) return '-'
  if (row.boundary_min <= 0) return `${row.boundary_max}%以下`
  if (row.boundary_max >= 101) return `${row.boundary_min}%及以上`
  return `${row.boundary_min}%-${row.boundary_max}%`
}

function selectedLabel(options, value, fallback) {
  if (!value) return fallback
  return options.find(option => option.value === value)?.label || fallback
}

function buildQueryParams() {
  const params = {}
  if (selectedSubjectId.value) params.subject_id = selectedSubjectId.value
  if (selectedClassId.value) params.class_id = selectedClassId.value
  return params
}

async function loadExams() {
  try {
    const resp = await client.get('/exams')
    examOptions.value = (resp.data || []).map(e => ({
      label: e.name,
      value: e.id,
    }))
  } catch { /* ignore */ }
}

async function loadClasses() {
  try {
    const resp = await client.get('/classes')
    classOptions.value = (resp.data || []).map(c => ({
      label: c.name,
      value: c.id,
    }))
  } catch { /* ignore */ }
}

async function loadSubjects(examId) {
  if (!examId) {
    availableSubjects.value = []
    return
  }
  try {
    const resp = await client.get(`/exams/${examId}/subjects`)
    availableSubjects.value = resp.data || []
  } catch {
    availableSubjects.value = []
  }
}

onMounted(async () => {
  await Promise.all([loadExams(), loadClasses()])
})

async function runQuery() {
  if (!selectedExamId.value) {
    message.warning('请选择一次考试')
    return
  }
  loading.value = true
  try {
    const resp = await getBasicReport(selectedExamId.value, buildQueryParams())
    basicReport.value = resp.data
    activeTab.value = 'overview'
    if (!exportSubjectId.value && subjectOptions.value.length === 1) {
      exportSubjectId.value = subjectOptions.value[0].value
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

watch(selectedExamId, async (examId) => {
  selectedSubjectId.value = null
  selectedClassId.value = null
  exportSubjectId.value = null
  basicReport.value = null
  activeTab.value = 'overview'
  await loadSubjects(examId)
})

async function handleDownload(format) {
  if (!canExport.value) {
    message.warning('请选择 1 次考试 + 1 个科目后再导出')
    return
  }
  exporting.value = true
  try {
    const resp = await exportGradeReport(
      selectedExamId.value, exportSubjectId.value, format,
    )
    downloadBlob(resp, `年级报告.${format}`)
  } catch (e) {
    message.error(e.response?.data?.detail || '导出失败')
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.analytics-report {
  --panel-border: 1px solid var(--border-color, #e5e7eb);
}

.report-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3, 12px);
  align-items: center;
}

.toolbar-select {
  min-width: 180px;
}

.report-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4, 16px);
  align-items: flex-end;
  padding: var(--space-4, 16px) 0;
  border-bottom: var(--panel-border);
}

.section-kicker {
  margin: 0 0 var(--space-1, 4px);
  color: var(--text-secondary, #6b7280);
  font-size: var(--fs-sm, 14px);
}

.report-head h2 {
  margin: 0;
  font-size: var(--fs-xl, 24px);
  font-weight: var(--fw-semibold, 600);
}

.report-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-3, 12px);
  color: var(--text-secondary, #6b7280);
  font-size: var(--fs-sm, 14px);
}

.report-meta-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-2, 8px);
}

.scope-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2, 8px);
}

.scope-tags span {
  padding: 2px 8px;
  border: var(--panel-border);
  border-radius: 999px;
  color: var(--text-secondary, #6b7280);
  font-size: var(--fs-sm, 14px);
  background: var(--surface-color, #fff);
}

.report-empty {
  padding: var(--space-8, 32px) 0;
}

.chart-height-xl {
  height: 320px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--space-3, 12px);
}

.metric-cell {
  padding: var(--space-3, 12px) 0;
  border-bottom: var(--panel-border);
}

.metric-cell span,
.detail-list span {
  display: block;
  color: var(--text-secondary, #6b7280);
  font-size: var(--fs-sm, 14px);
}

.metric-cell strong {
  display: block;
  margin-top: var(--space-1, 4px);
  font-size: var(--fs-xl, 24px);
  font-weight: var(--fw-semibold, 600);
}

.panel-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr);
  gap: var(--space-4, 16px);
}

.stack-layout {
  display: grid;
  gap: var(--space-4, 16px);
}

.report-panel {
  padding-top: var(--space-3, 12px);
}

.report-panel h3 {
  margin: 0 0 var(--space-3, 12px);
  font-size: var(--fs-md, 16px);
  font-weight: var(--fw-semibold, 600);
}

.detail-list {
  display: grid;
  gap: var(--space-3, 12px);
}

.detail-list div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3, 12px);
  padding-bottom: var(--space-2, 8px);
  border-bottom: var(--panel-border);
}

.detail-list strong {
  font-weight: var(--fw-semibold, 600);
}

@media (max-width: 760px) {
  .toolbar-select {
    min-width: 100%;
  }

  .report-head {
    display: block;
  }

  .report-meta-wrap {
    align-items: flex-start;
    margin-top: var(--space-2, 8px);
  }

  .scope-tags,
  .report-meta {
    justify-content: flex-start;
  }

  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
