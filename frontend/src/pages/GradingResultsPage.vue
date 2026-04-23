<template>
  <div>
    <div class="page-header">
      <n-button text style="margin-bottom: 8px;" @click="$router.push('/grading/tasks')">← 返回阅卷任务</n-button>
      <h1 class="page-title">批改结果</h1>
      <div style="display: flex; gap: 12px; margin-top: 12px;">
        <n-tag v-if="task" :type="taskStatusType(task.status)" round>{{ taskStatusLabel(task.status) }}</n-tag>
        <span v-if="task" style="color: var(--color-text-secondary);">
          已完成 {{ task.completed }} / {{ task.total }}
        </span>
      </div>
    </div>

    <div style="margin-bottom: 16px;">
      <n-space>
        <n-select v-model:value="filter" :options="filterOptions" style="width: 160px;" />
      </n-space>
    </div>

    <n-spin :show="loading">
      <n-data-table :columns="columns" :data="filteredResults" :row-props="() => ({ style: 'cursor: pointer;' })" />
      <n-empty v-if="!loading && filteredResults.length === 0" description="暂无结果" />
    </n-spin>

    <!-- 详情弹窗 -->
    <n-modal v-model:show="showDetail" preset="card" title="批改详情" style="width: 600px;">
      <template v-if="selectedResult">
        <n-descriptions bordered :column="1" size="small">
          <n-descriptions-item label="学生ID">{{ selectedResult.student_id || '-' }}</n-descriptions-item>
          <n-descriptions-item label="AI 评分">
            {{ selectedResult.score }} / {{ selectedResult.max_score }}
          </n-descriptions-item>
          <n-descriptions-item label="置信度">
            <n-tag :type="selectedResult.confidence >= 0.8 ? 'success' : 'warning'" size="small" round>
              {{ (selectedResult.confidence * 100).toFixed(0) }}%
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="复核状态">
            <n-tag :type="reviewStatusType(selectedResult.review_status)" size="small" round>
              {{ reviewStatusLabel(selectedResult.review_status) }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="AI 反馈">
            <div style="white-space: pre-wrap;">{{ selectedResult.feedback || '无' }}</div>
          </n-descriptions-item>
        </n-descriptions>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NTag, NButton } from 'naive-ui'
import { getTask, listResults } from '../api/grading'

const route = useRoute()
const taskId = route.params.id
const loading = ref(true)
const task = ref(null)
const results = ref([])
const filter = ref('all')
const showDetail = ref(false)
const selectedResult = ref(null)

const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '待复核', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已改分', value: 'overridden' },
]

const taskStatusMap = {
  pending: { label: '等待中', type: 'default' },
  processing: { label: '处理中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'error' },
}
const taskStatusLabel = (s) => taskStatusMap[s]?.label || s
const taskStatusType = (s) => taskStatusMap[s]?.type || 'default'

const reviewStatusMap = {
  pending: { label: '待复核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  overridden: { label: '已改分', type: 'info' },
}
const reviewStatusLabel = (s) => reviewStatusMap[s]?.label || s
const reviewStatusType = (s) => reviewStatusMap[s]?.type || 'default'

const filteredResults = computed(() =>
  filter.value === 'all' ? results.value : results.value.filter((r) => r.review_status === filter.value),
)

const columns = [
  { title: '题目', key: 'question_id', ellipsis: { tooltip: true }, width: 200 },
  {
    title: 'AI 评分', key: 'score', width: 120,
    render: (row) => `${row.score} / ${row.max_score}`,
  },
  {
    title: '置信度', key: 'confidence', width: 100,
    render: (row) => h(NTag, { size: 'small', round: true, type: row.confidence >= 0.8 ? 'success' : 'warning' },
      { default: () => `${(row.confidence * 100).toFixed(0)}%` }),
  },
  {
    title: '复核状态', key: 'review_status', width: 100,
    render: (row) => h(NTag, { size: 'small', round: true, type: reviewStatusType(row.review_status) },
      { default: () => reviewStatusLabel(row.review_status) }),
  },
  {
    title: '操作', key: 'actions', width: 80,
    render: (row) => h(NButton, { text: true, type: 'primary', size: 'small', onClick: () => { selectedResult.value = row; showDetail.value = true } },
      { default: () => '详情' }),
  },
]

onMounted(async () => {
  try {
    const [taskRes, resultsRes] = await Promise.all([
      getTask(taskId),
      listResults({ task_id: taskId }),
    ])
    task.value = taskRes.data
    results.value = resultsRes.data
  } catch { /* interceptor */ }
  loading.value = false
})
</script>
