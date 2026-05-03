<template>
  <div>
    <div class="toolbar">
      <n-button :loading="exporting" size="small" @click="handleExport">导出成绩 CSV</n-button>
      <div style="flex: 1;" />
      <n-button
        :loading="refreshing"
        :disabled="refreshing"
        secondary
        size="small"
        @click="manualRefresh"
      >
        <template #icon>
          <n-icon :class="{ 'spin-icon': refreshing }">
            <RefreshCw :size="16" />
          </n-icon>
        </template>
        刷新
      </n-button>
      <div class="auto-refresh-group">
        <n-switch v-model:value="autoRefresh" size="small" />
        <span class="auto-refresh-label">自动刷新</span>
        <span v-if="lastUpdateTime" class="last-update">{{ lastUpdateTime }}</span>
      </div>
    </div>

    <n-spin :show="loading">
      <n-card v-if="progress" class="overall-card" size="small">
        <div class="overall-stats">
          <div class="stat-card">
            <div class="stat-label">已批改</div>
            <div class="stat-value">{{ progress.overall.graded }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">总计</div>
            <div class="stat-value">{{ progress.overall.total }}</div>
          </div>
          <div class="stat-item">
            <n-progress
              type="circle"
              :percentage="progress.overall.percentage"
              :stroke-width="8"
              style="width: 80px;"
            />
          </div>
          <div class="stat-card">
            <div class="stat-label">剩余待批改</div>
            <div class="stat-value">{{ remainingCount }} <n-tag size="tiny" :bordered="false">题</n-tag></div>
          </div>
        </div>
      </n-card>

      <div v-for="subj in progress?.subjects || []" :key="subj.id" class="subject-card">
        <div class="subject-header">
          <h3>{{ subj.name }}</h3>
          <n-progress
            type="circle"
            :percentage="subjectPercentage(subj)"
            :stroke-width="6"
            :color="subjectPercentage(subj) >= 100 ? '#2a9d8f' : '#f4a261'"
            class="subject-progress"
          />
        </div>
        <n-data-table
          :columns="columns"
          :data="subj.questions"
          :bordered="false"
          size="small"
          :row-props="rowProps"
        />
      </div>

      <n-empty v-if="!progress && !loading" description="请先选择考试" />
    </n-spin>
  </div>
</template>

<script setup>
import { ref, h, computed, watch, onUnmounted } from 'vue'
import { NProgress, NIcon, useMessage } from 'naive-ui'
import { RefreshCw } from 'lucide-vue-next'
import { getProgress, exportCsv } from '../../api/marking'

const props = defineProps({
  examId: { type: [String, Number], default: null },
})

const message = useMessage()
const loading = ref(false)
const refreshing = ref(false)
const exporting = ref(false)
const progress = ref(null)
const autoRefresh = ref(false)
const lastUpdateTime = ref('')
let pollTimer = null

const remainingCount = computed(() => {
  if (!progress.value) return 0
  return progress.value.overall.total - progress.value.overall.graded
})

function subjectPercentage(subj) {
  if (!subj.questions || subj.questions.length === 0) return 0
  let graded = 0, total = 0
  for (const q of subj.questions) {
    graded += q.graded_count
    total += q.total_answers
  }
  return total > 0 ? Math.round(graded / total * 100) : 0
}

function questionColorBand(row) {
  const pct = row.total_answers > 0 ? row.graded_count / row.total_answers * 100 : 0
  if (pct >= 100) return '#2a9d8f'
  if (pct >= 50) return '#f4a261'
  return '#e76f51'
}

function rowProps(row) {
  return { style: `border-left: 4px solid ${questionColorBand(row)};` }
}

const columns = [
  { title: '题号', key: 'name', width: 120 },
  { title: '满分', key: 'max_score', width: 80 },
  { title: '已批', key: 'graded_count', width: 80 },
  { title: '总数', key: 'total_answers', width: 80 },
  {
    title: '进度', key: 'progress',
    render(row) {
      const pct = row.total_answers > 0 ? Math.round(row.graded_count / row.total_answers * 100) : 0
      return h(NProgress, { type: 'line', percentage: pct, indicatorPlacement: 'inside' })
    },
  },
]

function updateTimestamp() {
  const now = new Date()
  const hh = String(now.getHours()).padStart(2, '0')
  const mm = String(now.getMinutes()).padStart(2, '0')
  const ss = String(now.getSeconds()).padStart(2, '0')
  lastUpdateTime.value = `上次更新: ${hh}:${mm}:${ss}`
}

async function loadProgress() {
  if (!props.examId) return
  loading.value = true
  try {
    const { data } = await getProgress(props.examId)
    progress.value = data
    updateTimestamp()
  } catch {}
  loading.value = false
}

async function manualRefresh() {
  if (!props.examId) return
  refreshing.value = true
  try {
    const { data } = await getProgress(props.examId)
    progress.value = data
    updateTimestamp()
  } catch {}
  refreshing.value = false
}

function startPolling() {
  stopPolling()
  if (!props.examId) return
  pollTimer = setInterval(async () => {
    try {
      const { data } = await getProgress(props.examId)
      progress.value = data
      updateTimestamp()
    } catch {}
  }, 30000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

watch(autoRefresh, (val) => { val ? startPolling() : stopPolling() })

watch(() => props.examId, (val) => {
  progress.value = null
  if (val) {
    loadProgress()
    if (autoRefresh.value) startPolling()
  } else {
    stopPolling()
  }
}, { immediate: true })

async function handleExport() {
  if (!props.examId) return
  exporting.value = true
  try {
    const { data } = await exportCsv(props.examId)
    const url = URL.createObjectURL(new Blob([data], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'scores.csv'
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch { message.error('导出失败') }
  exporting.value = false
}

onUnmounted(() => stopPolling())
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: var(--space-3);
  align-items: center;
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.auto-refresh-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.auto-refresh-label { font-size: var(--fs-base); color: var(--color-text-muted); white-space: nowrap; }
.last-update { font-size: var(--fs-base); color: var(--color-text-muted); white-space: nowrap; }
.overall-card { margin-bottom: var(--space-4); }
.overall-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-12);
  flex-wrap: wrap;
}
.stat-item { display: flex; flex-direction: column; align-items: center; gap: var(--space-1); }
.subject-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}
.subject-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}
.subject-card h3 { font-size: var(--fs-base); font-weight: var(--fw-semibold); margin: 0; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
.spin-icon { animation: spin 1s linear infinite; }
.subject-progress { width: 56px; height: 56px; }
:deep(.subject-progress .n-progress-text) { font-size: 12px !important; }
:deep(.overall-card .n-progress-text) { font-size: 14px !important; }
</style>
