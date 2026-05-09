<template>
  <div>
    <div class="page-header">
      <n-button text style="margin-bottom: 8px;" @click="$router.push('/grading/tasks')">
        <template #icon><n-icon><ArrowLeft :size="16" /></n-icon></template>
        返回阅卷任务
      </n-button>
      <h1 class="page-title">批改结果</h1>
      <div style="display: flex; gap: 12px; margin-top: 12px;">
        <n-tag v-if="task" :type="taskStatusType(task.status)" round>{{ taskStatusLabel(task.status) }}</n-tag>
        <span v-if="task" style="color: var(--color-text-secondary);">
          已完成 {{ task.completed }} / {{ task.total }}
        </span>
      </div>
    </div>

    <!-- 整体进度条 -->
    <div v-if="task" style="margin-bottom: 20px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
        <span style="font-size: var(--fs-base); color: var(--color-text-secondary);">批改进度</span>
        <span style="font-size: var(--fs-base); color: var(--color-text-secondary);">{{ progressPercent }}%</span>
      </div>
      <n-progress :percentage="progressPercent" :show-indicator="false"
        :color="progressPercent >= 100 ? '#22C55E' : '#644CF0'" rail-color="var(--macaron-mint-light)" />
    </div>

    <!-- 统计摘要卡片 -->
    <div v-if="results.length > 0" class="stats-row">
      <div class="stat-card">
        <div class="stat-label">已批改 / 总数</div>
        <div class="stat-value">{{ gradedCount }} / {{ results.length }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均分</div>
        <div class="stat-value">{{ avgScore }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均置信度</div>
        <div class="stat-value">{{ avgConfidence }}<span class="stat-suffix">%</span></div>
      </div>
      <div class="stat-card">
        <div class="stat-label">待复核数</div>
        <div class="stat-value">{{ pendingReviewCount }}</div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div v-if="results.length > 0" style="display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap;">
      <!-- 分数分布柱图 -->
      <n-card size="small" style="flex: 2; min-width: 360px;">
        <template #header><span style="font-size: var(--fs-base); font-weight: var(--fw-semibold);">分数分布</span></template>
        <v-chart class="chart-height-md" :option="scoreDistOption" autoresize />
      </n-card>
      <!-- 置信度饼图 -->
      <n-card size="small" style="flex: 1; min-width: 280px;">
        <template #header><span style="font-size: var(--fs-base); font-weight: var(--fw-semibold);">置信度分布</span></template>
        <v-chart class="chart-height-md" :option="confidenceDistOption" autoresize />
      </n-card>
    </div>

    <!-- 筛选 + 排序 -->
    <div style="margin-bottom: var(--space-4);">
      <n-space>
        <n-select v-model:value="filter" :options="filterOptions" style="width: 160px;" />
        <n-select v-model:value="sortBy" :options="sortOptions" style="width: 160px;" placeholder="排序方式" clearable />
      </n-space>
    </div>

    <n-spin :show="loading">
      <n-data-table :columns="columns" :data="sortedResults" :row-props="() => ({ style: 'cursor: pointer;' })" />
      <n-empty v-if="!loading && sortedResults.length === 0" description="暂无结果">
        <template #extra>
          <n-button v-if="filter !== 'all'" size="small" @click="filter = 'all'">清除筛选</n-button>
        </template>
      </n-empty>
    </n-spin>

    <!-- 详情弹窗 -->
    <n-modal v-model:show="showDetail" preset="card" title="批改详情" style="width: 640px;">
      <template v-if="selectedResult">
        <n-descriptions bordered :column="1" size="small">
          <n-descriptions-item label="题目序号">
            {{ questionLabel(selectedResult) }}
          </n-descriptions-item>
          <n-descriptions-item label="学生ID">{{ selectedResult.student_id || '-' }}</n-descriptions-item>
          <n-descriptions-item label="AI 评分">
            <div style="display: flex; align-items: center; gap: 12px;">
              <span>{{ selectedResult.score }} / {{ selectedResult.max_score }}</span>
              <n-progress type="line" :percentage="scorePercent(selectedResult)" :show-indicator="false"
                :color="scoreColor(selectedResult)" style="width: 120px;" />
              <span style="font-size: var(--fs-base); color: var(--color-text-secondary);">
                {{ scorePercent(selectedResult) }}%
              </span>
            </div>
          </n-descriptions-item>
          <n-descriptions-item label="置信度">
            <n-tag :type="confidenceType(selectedResult.confidence)" size="small" round>
              {{ (selectedResult.confidence * 100).toFixed(0) }}%
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="复核状态">
            <n-tag :type="reviewStatusType(selectedResult.review_status)" size="small" round>
              {{ reviewStatusLabel(selectedResult.review_status) }}
            </n-tag>
          </n-descriptions-item>
          <n-descriptions-item label="AI 反馈">
            <n-blockquote v-if="selectedResult.feedback" style="margin: 0;">
              <div style="white-space: pre-wrap;">{{ selectedResult.feedback }}</div>
            </n-blockquote>
            <span v-else style="color: var(--color-text-secondary);">无</span>
          </n-descriptions-item>
        </n-descriptions>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NTag, NButton, NProgress, NIcon } from 'naive-ui'
import { ArrowLeft } from 'lucide-vue-next'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { getTask, listResults } from '../api/grading'
import { CHART_DEFAULTS, CHART_PALETTE } from '../config/chartTheme.js'

use([CanvasRenderer, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const route = useRoute()
const taskId = route.params.id
const loading = ref(true)
const task = ref(null)
const results = ref([])
const filter = ref('all')
const sortBy = ref(null)
const showDetail = ref(false)
const selectedResult = ref(null)

const filterOptions = [
  { label: '全部', value: 'all' },
  { label: '待复核', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已改分', value: 'overridden' },
]

const sortOptions = [
  { label: '置信度 升序', value: 'confidence_asc' },
  { label: '置信度 降序', value: 'confidence_desc' },
  { label: '分数 升序', value: 'score_asc' },
  { label: '分数 降序', value: 'score_desc' },
  { label: '得分率 升序', value: 'rate_asc' },
  { label: '得分率 降序', value: 'rate_desc' },
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

// --- Computed aggregations ---
const progressPercent = computed(() => {
  if (!task.value || !task.value.total) return 0
  return Math.round((task.value.completed / task.value.total) * 100)
})

const gradedCount = computed(() => results.value.length)

const avgScore = computed(() => {
  if (results.value.length === 0) return 0
  const total = results.value.reduce((sum, r) => sum + (r.score || 0), 0)
  return (total / results.value.length).toFixed(1)
})

const avgConfidence = computed(() => {
  if (results.value.length === 0) return 0
  const total = results.value.reduce((sum, r) => sum + (r.confidence || 0), 0)
  return ((total / results.value.length) * 100).toFixed(0)
})

const pendingReviewCount = computed(() =>
  results.value.filter((r) => r.review_status === 'pending').length,
)

// --- Score distribution chart ---
const scoreDistOption = computed(() => {
  if (results.value.length === 0) return {}
  const buckets = [0, 0, 0, 0, 0]
  const labels = ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%']
  results.value.forEach((r) => {
    const pct = r.max_score > 0 ? (r.score / r.max_score) * 100 : 0
    if (pct < 20) buckets[0]++
    else if (pct < 40) buckets[1]++
    else if (pct < 60) buckets[2]++
    else if (pct < 80) buckets[3]++
    else buckets[4]++
  })
  return {
    ...CHART_DEFAULTS,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
    xAxis: {
      ...CHART_DEFAULTS.xAxis,
      type: 'category',
      data: labels,
    },
    yAxis: {
      ...CHART_DEFAULTS.yAxis,
      type: 'value',
      name: '人数',
      nameTextStyle: { color: CHART_DEFAULTS.textStyle.color },
    },
    series: [{
      type: 'bar',
      data: buckets,
      itemStyle: {
        color: CHART_PALETTE[0],
        borderRadius: [6, 6, 0, 0],
      },
      barWidth: '50%',
    }],
    grid: { ...CHART_DEFAULTS.grid, left: 60, right: 20, top: 40, bottom: 40 },
  }
})

// --- Confidence distribution pie chart ---
const confidenceDistOption = computed(() => {
  if (results.value.length === 0) return {}
  let high = 0
  let mid = 0
  let low = 0
  results.value.forEach((r) => {
    const pct = (r.confidence || 0) * 100
    if (pct >= 80) high++
    else if (pct >= 50) mid++
    else low++
  })
  return {
    ...CHART_DEFAULTS,
    grid: undefined,
    xAxis: undefined,
    yAxis: undefined,
    tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: {
      ...CHART_DEFAULTS.legend,
      bottom: 0,
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '45%'],
      data: [
        { value: high, name: '高 (>=80%)', itemStyle: { color: CHART_PALETTE[3] } },
        { value: mid, name: '中 (50-80%)', itemStyle: { color: CHART_PALETTE[2] } },
        { value: low, name: '低 (<50%)', itemStyle: { color: '#dc2626' } },
      ].filter((d) => d.value > 0),
      label: { color: CHART_DEFAULTS.textStyle.color },
    }],
  }
})

// --- Helpers ---
function questionLabel(row) {
  if (row.question_name) return row.question_name
  if (row.question_index != null) return `第 ${row.question_index + 1} 题`
  // Fallback: show shortened UUID
  const id = row.question_id || ''
  return id.length > 8 ? id.substring(0, 8) + '...' : id
}

function scorePercent(row) {
  if (!row.max_score) return 0
  return Math.round((row.score / row.max_score) * 100)
}

function scoreColor(row) {
  const pct = scorePercent(row)
  if (pct < 60) return '#dc2626'
  if (pct < 80) return '#ED9A51'
  return '#22C55E'
}

function confidenceType(c) {
  const pct = (c || 0) * 100
  if (pct >= 80) return 'success'
  if (pct >= 50) return 'warning'
  return 'error'
}

// --- Filtering + Sorting ---
const filteredResults = computed(() =>
  filter.value === 'all' ? results.value : results.value.filter((r) => r.review_status === filter.value),
)

const sortedResults = computed(() => {
  const arr = [...filteredResults.value]
  if (!sortBy.value) return arr
  const [field, dir] = sortBy.value.split('_')
  const asc = dir === 'asc' ? 1 : -1
  arr.sort((a, b) => {
    let va, vb
    if (field === 'confidence') {
      va = a.confidence || 0
      vb = b.confidence || 0
    } else if (field === 'score') {
      va = a.score || 0
      vb = b.score || 0
    } else if (field === 'rate') {
      va = a.max_score ? a.score / a.max_score : 0
      vb = b.max_score ? b.score / b.max_score : 0
    } else {
      return 0
    }
    return (va - vb) * asc
  })
  return arr
})

// --- Table columns ---
const columns = [
  {
    title: '题目', key: 'question_id', ellipsis: { tooltip: true }, width: 180,
    render: (row) => questionLabel(row),
  },
  {
    title: 'AI 评分', key: 'score', width: 180, sorter: (a, b) => a.score - b.score,
    render: (row) => {
      const pct = scorePercent(row)
      return h('div', { style: 'display: flex; align-items: center; gap: var(--space-2);' }, [
        h('span', {}, `${row.score} / ${row.max_score}`),
        h(NProgress, { type: 'line', percentage: pct, showIndicator: false, color: scoreColor(row), style: 'width: 60px;' }),
      ])
    },
  },
  {
    title: '得分率', key: 'score_rate', width: 80, sorter: (a, b) => scorePercent(a) - scorePercent(b),
    render: (row) => `${scorePercent(row)}%`,
  },
  {
    title: '置信度', key: 'confidence', width: 110, sorter: (a, b) => (a.confidence || 0) - (b.confidence || 0),
    render: (row) => h(NTag, { size: 'small', round: true, type: confidenceType(row.confidence) },
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
    const rd = resultsRes.data
    results.value = Array.isArray(rd) ? rd : rd.items
  } catch { /* interceptor */ }
  loading.value = false
})
</script>
