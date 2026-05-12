<template>
  <div class="page-wrap analytics-report">
    <div class="page-header">
      <h1 class="page-title">成绩分析</h1>
    </div>

    <n-space vertical :size="16">
      <div class="report-toolbar">
        <PowerOptionsSelector @change="onFilterChange" />
        <n-select
          v-model:value="exportSubjectId"
          :options="subjectOptions"
          placeholder="选择导出科目"
          class="toolbar-select"
          clearable
          style="min-width: 160px"
        />
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

          <n-tab-pane name="layers" tab="分层学情">
            <LayerAnalysisPanel
              v-if="selectedExamId"
              :exam-id="selectedExamId"
              :subject-id="selectedSubjectId"
              :class-id="selectedClassId"
            />
            <n-empty v-else description="请先选择考试" />
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
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getBasicReport } from '../api/analytics'
import client from '../api/client'
import PowerOptionsSelector from '../components/analytics/PowerOptionsSelector.vue'
import KnowledgeDiagnosisPanel from '../components/analytics/KnowledgeDiagnosisPanel.vue'
import LayerAnalysisPanel from '../components/analytics/LayerAnalysisPanel.vue'
import TrendPanel from '../components/analytics/TrendPanel.vue'
import AiDiagnosisReport from '../components/analytics/AiDiagnosisReport.vue'
import { buildSegmentChart, buildSubjectRateChart, buildRankTrendChart, buildClassCompareChart } from '../composables/useChartOptions'
import { getSubjectColumns, getClassColumns, getStudentColumns, fmt, pct } from '../composables/useTableColumns'
import { useReportExport } from '../composables/useReportExport'

use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const route = useRoute()
const message = useMessage()
const { exporting, handleDownload: doDownload, exportStudentRank: doExportRank } = useReportExport()

const loading = ref(false)
const basicReport = ref(null)
const selectedExamId = ref(null)
const selectedSubjectId = ref(null)
const selectedClassId = ref(null)
const exportSubjectId = ref(null)
const availableSubjects = ref([])
const validTabs = ['overview', 'subjects', 'classes', 'students', 'knowledge', 'layers', 'trend', 'ai-report']
const activeTab = ref(validTabs.includes(route.query.tab) ? route.query.tab : 'overview')
const studentKeyword = ref('')
const currentGradeId = ref(null)
const currentSubjectCode = ref(null)

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
    `科目：${scope.subject_name || currentSubjectCode.value || '全部科目'}`,
    `班级：${scope.class_name || (selectedClassId.value ? '' : '全部班级') || ''}`,
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

const segmentChartOption = computed(() => buildSegmentChart(basicReport.value?.distribution))
const subjectRateChartOption = computed(() => buildSubjectRateChart(basicReport.value?.subjects))
const rankTrendChartOption = computed(() => buildRankTrendChart(basicReport.value?.overview, basicReport.value?.exam?.name))
const classCompareChartOption = computed(() => buildClassCompareChart(basicReport.value?.classes))

const subjectColumns = getSubjectColumns()
const classColumns = getClassColumns()
const studentColumns = computed(() => getStudentColumns(basicReport.value?.subjects))
const studentTableScrollX = computed(() => 820 + (basicReport.value?.subjects || []).length * 96)

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

function buildQueryParams() {
  const params = {}
  if (selectedSubjectId.value) params.subject_id = selectedSubjectId.value
  if (selectedClassId.value) params.class_id = selectedClassId.value
  return params
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

async function runQuery() {
  if (!selectedExamId.value) return
  loading.value = true
  try {
    const resp = await getBasicReport(selectedExamId.value, buildQueryParams())
    basicReport.value = resp.data
    if (!activeTab.value || activeTab.value === 'overview') activeTab.value = 'overview'
    if (!exportSubjectId.value && subjectOptions.value.length === 1) {
      exportSubjectId.value = subjectOptions.value[0].value
    }
  } catch (e) {
    message.error(e.response?.data?.detail || '查询失败')
  } finally {
    loading.value = false
  }
}

let filterSeq = 0
async function onFilterChange(payload) {
  const seq = ++filterSeq
  selectedExamId.value = payload.examId
  selectedSubjectId.value = payload.subjectId
  selectedClassId.value = payload.classId
  currentGradeId.value = payload.gradeId
  currentSubjectCode.value = payload.subjectCode
  exportSubjectId.value = null
  basicReport.value = null
  await loadSubjects(payload.examId)
  if (seq !== filterSeq) return
  if (payload.examId) await runQuery()
}

function handleDownload(format) {
  if (!canExport.value) {
    message.warning('请选择 1 次考试 + 1 个科目后再导出')
    return
  }
  doDownload(selectedExamId.value, exportSubjectId.value, format)
}

function exportStudentRank() {
  if (!filteredStudentRows.value.length) return
  if (!selectedExamId.value) return
  const subjectId = exportSubjectId.value || (subjectOptions.value[0]?.value)
  if (!subjectId) {
    message.warning('请先选择导出科目')
    return
  }
  doExportRank(selectedExamId.value, subjectId)
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
