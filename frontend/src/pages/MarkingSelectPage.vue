<template>
  <div>
    <div class="page-header">
      <h1 class="page-title">人工阅卷</h1>
      <p class="page-subtitle">选择科目和题目开始阅卷</p>
    </div>

    <div class="toolbar">
      <n-select
        v-model:value="selectedExamId"
        :options="examOptions"
        placeholder="选择考试"
        style="width: 300px;"
        @update:value="loadSubjects"
      />
      <n-select
        v-model:value="statusFilter"
        :options="filterOptions"
        placeholder="筛选状态"
        style="width: 180px;"
      />
    </div>

    <!-- Statistics summary -->
    <div v-if="subjects.length > 0" class="stats-row">
      <n-card size="small" class="stat-card">
        <n-statistic label="总题目数" :value="totalQuestions" />
      </n-card>
      <n-card size="small" class="stat-card">
        <n-statistic label="已完成" :value="completedQuestions">
          <template #prefix>
            <span class="stat-dot stat-dot--success" />
          </template>
        </n-statistic>
      </n-card>
      <n-card size="small" class="stat-card">
        <n-statistic label="待批改" :value="pendingQuestions">
          <template #prefix>
            <span class="stat-dot stat-dot--warning" />
          </template>
        </n-statistic>
      </n-card>
    </div>

    <n-spin :show="loading">
      <!-- Subject list -->
      <div v-for="subj in filteredSubjects" :key="subj.id" class="subject-card">
        <div class="subject-header">
          <h3 class="subject-name">{{ subj.name }}</h3>
          <n-progress
            type="circle"
            :percentage="subjectProgress(subj)"
            :stroke-width="5"
            :show-indicator="true"
            style="width: 40px; height: 40px;"
          />
        </div>
        <n-data-table
          :columns="questionColumns"
          :data="filterQuestions(subj.questions)"
          :bordered="false"
          :row-class-name="rowClassName"
          size="small"
        />
      </div>
      <n-empty v-if="!loading && filteredSubjects.length === 0" :description="subjects.length === 0 ? '请先选择考试' : '没有匹配的题目'">
        <template #extra>
          <n-button v-if="subjects.length > 0 && statusFilter !== 'all'" size="small" @click="statusFilter = 'all'">清除筛选</n-button>
        </template>
      </n-empty>
    </n-spin>

  </div>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NProgress, NStatistic, NCard } from 'naive-ui'
import { listSubjects } from '../api/marking'
import client from '../api/client'

const router = useRouter()

const loading = ref(false)
const subjects = ref([])
const selectedExamId = ref(null)
const examOptions = ref([])
const statusFilter = ref('all')

const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '待批改', value: 'pending' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
]

// --- Statistics (computed from subjects) ---
const allQuestions = computed(() => subjects.value.flatMap(s => s.questions || []))
const totalQuestions = computed(() => allQuestions.value.length)
const completedQuestions = computed(() =>
  allQuestions.value.filter(q => q.total_answers > 0 && q.graded_count >= q.total_answers).length
)
const pendingQuestions = computed(() => totalQuestions.value - completedQuestions.value)

// --- Filtering ---
function questionStatus(q) {
  if (q.total_answers <= 0) return 'pending'
  if (q.graded_count >= q.total_answers) return 'completed'
  if (q.graded_count > 0) return 'in_progress'
  return 'pending'
}

function filterQuestions(questions) {
  if (statusFilter.value === 'all') return questions
  return questions.filter(q => questionStatus(q) === statusFilter.value)
}

const filteredSubjects = computed(() => {
  if (statusFilter.value === 'all') return subjects.value
  return subjects.value.filter(subj => filterQuestions(subj.questions || []).length > 0)
})

// --- Subject-level progress ---
function subjectProgress(subj) {
  const qs = subj.questions || []
  const total = qs.reduce((sum, q) => sum + (q.total_answers || 0), 0)
  const graded = qs.reduce((sum, q) => sum + (q.graded_count || 0), 0)
  return total > 0 ? Math.round(graded / total * 100) : 0
}

// --- Row class for status color band ---
function rowClassName(row) {
  const s = questionStatus(row)
  if (s === 'completed') return 'row--completed'
  if (s === 'in_progress') return 'row--in-progress'
  return 'row--pending'
}

const questionColumns = [
  { title: '题号', key: 'name', width: 120 },
  { title: '满分', key: 'max_score', width: 80 },
  {
    title: '进度',
    key: 'progress',
    render(row) {
      const pct = row.total_answers > 0 ? Math.round(row.graded_count / row.total_answers * 100) : 0
      return h('div', { style: 'display: flex; align-items: center; gap: 8px;' }, [
        h(NProgress, {
          type: 'line',
          percentage: pct,
          indicatorPlacement: 'inside',
          style: 'flex: 1;',
        }),
        h('span', { style: 'font-size: 12px; color: var(--color-text-secondary); white-space: nowrap;' },
          `${row.graded_count}/${row.total_answers}`),
      ])
    },
  },
  {
    title: '操作',
    key: 'action',
    width: 120,
    render(row) {
      const done = row.graded_count >= row.total_answers && row.total_answers > 0
      return h(
        NButton,
        {
          size: 'small',
          type: done ? 'default' : 'primary',
          onClick: () => router.push(`/marking/grade/${row.id}`),
        },
        { default: () => done ? '查看' : '开始阅卷' },
      )
    },
  },
]

async function loadExams() {
  try {
    const { data } = await client.get('/exams')
    examOptions.value = data.map(e => ({ label: e.name, value: e.id }))
    if (data.length > 0) {
      selectedExamId.value = data[0].id
      await loadSubjects(data[0].id)
    }
  } catch {}
}

async function loadSubjects(examId) {
  if (!examId) return
  loading.value = true
  try {
    const { data } = await listSubjects(examId)
    subjects.value = data
  } catch {}
  loading.value = false
}

onMounted(loadExams)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 24px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: var(--color-bg-card, rgba(255,255,255,0.04));
  border: 1px solid var(--color-border-light, rgba(255,255,255,0.09));
}

.stat-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.stat-dot--success { background: #2a9d8f; }
.stat-dot--warning { background: #f4a261; }

.subject-card {
  background: var(--color-bg-card, rgba(255,255,255,0.04));
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light, rgba(255,255,255,0.09));
  padding: 20px;
  margin-bottom: 16px;
}

.subject-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.subject-name {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
  color: var(--color-text);
}

/* Question row status color bands */
:deep(.row--completed td:first-child) {
  box-shadow: inset 3px 0 0 #2a9d8f;
}
:deep(.row--in-progress td:first-child) {
  box-shadow: inset 3px 0 0 #f4a261;
}
:deep(.row--pending td:first-child) {
  box-shadow: inset 3px 0 0 rgba(255,255,255,0.15);
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>
