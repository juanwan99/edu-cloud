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
    </div>

    <n-spin :show="loading">
      <!-- 科目列表 -->
      <div v-for="subj in subjects" :key="subj.id" class="subject-card">
        <div class="subject-header">
          <h3 class="subject-name">{{ subj.name }}</h3>
        </div>
        <n-data-table
          :columns="questionColumns"
          :data="subj.questions"
          :bordered="false"
          size="small"
        />
      </div>
      <n-empty v-if="!loading && subjects.length === 0" description="请先选择考试" />
    </n-spin>

  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NProgress } from 'naive-ui'
import { listSubjects } from '../api/marking'
import client from '../api/client'

const router = useRouter()

const loading = ref(false)
const subjects = ref([])
const selectedExamId = ref(null)
const examOptions = ref([])

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

.subject-card {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
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
}
</style>
