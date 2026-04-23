<template>
  <div>
    <div class="page-header">
      <n-button text style="margin-bottom: 8px;" @click="$router.push('/marking')">← 返回阅卷</n-button>
      <h1 class="page-title">阅卷进度</h1>
      <p class="page-subtitle">查看各科目、各题的批改进度</p>
    </div>

    <div class="toolbar">
      <n-select
        v-model:value="selectedExamId"
        :options="examOptions"
        placeholder="选择考试"
        style="width: 300px;"
        @update:value="loadProgress"
      />
      <n-button :loading="exporting" @click="handleExport">
        导出成绩 CSV
      </n-button>
    </div>

    <n-spin :show="loading">
      <!-- 总进度 -->
      <n-card v-if="progress" class="overall-card" size="small">
        <div class="overall-stats">
          <div class="stat-item">
            <span class="stat-value">{{ progress.overall.graded }}</span>
            <span class="stat-label">已批改</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ progress.overall.total }}</span>
            <span class="stat-label">总计</span>
          </div>
          <div class="stat-item">
            <n-progress
              type="circle"
              :percentage="progress.overall.percentage"
              :stroke-width="8"
              style="width: 80px;"
            />
          </div>
        </div>
      </n-card>

      <!-- 各科目 -->
      <div v-for="subj in progress?.subjects || []" :key="subj.id" class="subject-card">
        <h3>{{ subj.name }}</h3>
        <n-data-table
          :columns="columns"
          :data="subj.questions"
          :bordered="false"
          size="small"
        />
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { NProgress, useMessage } from 'naive-ui'
import { getProgress, exportCsv } from '../api/marking'
import client from '../api/client'

const message = useMessage()
const loading = ref(false)
const exporting = ref(false)
const selectedExamId = ref(null)
const examOptions = ref([])
const progress = ref(null)

const columns = [
  { title: '题号', key: 'name', width: 120 },
  { title: '满分', key: 'max_score', width: 80 },
  { title: '已批', key: 'graded_count', width: 80 },
  { title: '总数', key: 'total_answers', width: 80 },
  {
    title: '进度',
    key: 'progress',
    render(row) {
      const pct = row.total_answers > 0
        ? Math.round(row.graded_count / row.total_answers * 100)
        : 0
      return h(NProgress, {
        type: 'line',
        percentage: pct,
        indicatorPlacement: 'inside',
      })
    },
  },
]

async function loadExams() {
  try {
    const { data } = await client.get('/exams')
    examOptions.value = data.map(e => ({ label: e.name, value: e.id }))
    if (data.length > 0) {
      selectedExamId.value = data[0].id
      await loadProgress(data[0].id)
    }
  } catch {}
}

async function loadProgress(examId) {
  if (!examId) return
  loading.value = true
  try {
    const { data } = await getProgress(examId)
    progress.value = data
  } catch {}
  loading.value = false
}

async function handleExport() {
  if (!selectedExamId.value) return
  exporting.value = true
  try {
    const { data } = await exportCsv(selectedExamId.value)
    const url = URL.createObjectURL(new Blob([data], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'scores.csv'
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch {
    message.error('导出失败')
  }
  exporting.value = false
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

.overall-card {
  margin-bottom: 24px;
}

.overall-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 48px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-size: 32px;
  font-weight: 800;
  color: var(--color-primary);
}

.stat-label {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.subject-card {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 20px;
  margin-bottom: 16px;
}

.subject-card h3 {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 12px;
}
</style>
