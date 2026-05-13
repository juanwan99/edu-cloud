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
        <n-button
          v-if="selectedExamId"
          type="primary"
          ghost
          class="btn-pill"
          @click="openAiDiagnosis"
        >
          AI 深度诊断
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
            <OverviewPanel :report="basicReport" />
          </n-tab-pane>

          <n-tab-pane name="subjects" tab="科目分析">
            <SubjectAnalysisPanel :report="basicReport" />
          </n-tab-pane>

          <n-tab-pane name="classes" tab="班级对比">
            <ClassComparePanel :report="basicReport" />
          </n-tab-pane>

          <n-tab-pane name="students" tab="学生排名">
            <StudentRankPanel :report="basicReport" @export-rank="exportStudentRank" />
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
import { inject, ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useMessage } from 'naive-ui'
import { getBasicReport } from '../api/analytics'
import client from '../api/client'
import { fmt } from '../composables/useTableColumns'
import PowerOptionsSelector from '../components/analytics/PowerOptionsSelector.vue'
import OverviewPanel from '../components/analytics/OverviewPanel.vue'
import SubjectAnalysisPanel from '../components/analytics/SubjectAnalysisPanel.vue'
import ClassComparePanel from '../components/analytics/ClassComparePanel.vue'
import StudentRankPanel from '../components/analytics/StudentRankPanel.vue'
import KnowledgeDiagnosisPanel from '../components/analytics/KnowledgeDiagnosisPanel.vue'
import LayerAnalysisPanel from '../components/analytics/LayerAnalysisPanel.vue'
import TrendPanel from '../components/analytics/TrendPanel.vue'
import AiDiagnosisReport from '../components/analytics/AiDiagnosisReport.vue'
import { useReportExport } from '../composables/useReportExport'

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
const currentGradeId = ref(null)
const currentSubjectCode = ref(null)

const openAiWithContext = inject('openAiWithContext', null)
function openAiDiagnosis() {
  if (!openAiWithContext || !selectedExamId.value) return
  const examName = basicReport.value?.exam?.name || '考试'
  const refsArr = [{ type: 'exam', id: selectedExamId.value, label: examName }]
  if (selectedSubjectId.value) {
    const subj = (basicReport.value?.subjects || []).find(s => (s.subject_id || s.id) === selectedSubjectId.value)
    if (subj) refsArr.push({ type: 'subject', id: selectedSubjectId.value, label: subj.subject_name || subj.name })
  }
  openAiWithContext({
    type: 'exam_diagnosis',
    label: `${examName} 深度诊断`,
    refs: refsArr,
    suggestedPrompt: '请对这次考试做全面诊断分析',
  })
}

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
}
</style>
