<template>
  <div>
    <n-card v-if="currentChild" title="学生信息" style="margin-bottom: 16px;">
      <n-descriptions :column="1" label-placement="left" bordered size="small">
        <n-descriptions-item label="姓名">{{ currentChild.student_name }}</n-descriptions-item>
        <n-descriptions-item label="班级">{{ currentChild.class_name || '-' }}</n-descriptions-item>
        <n-descriptions-item label="总积分">{{ currentChild.total_points ?? 0 }}</n-descriptions-item>
      </n-descriptions>
    </n-card>

    <!-- Sparkline trend chart -->
    <n-card v-if="trendData.length > 1" style="margin-bottom: 16px;">
      <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">积分走势（近30天）</div>
      <v-chart :option="trendOption" class="chart-height-sm" style="height: 120px;" autoresize />
    </n-card>

    <!-- Filters -->
    <n-card style="margin-bottom: 16px;">
      <div class="filter-row">
        <n-date-picker
          v-model:value="dateRange"
          type="daterange"
          clearable
          size="small"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="flex: 1;"
          @update:value="handleFilterChange"
        />
        <n-select
          v-model:value="typeFilter"
          :options="typeOptions"
          size="small"
          style="width: 100px; flex-shrink: 0;"
          @update:value="handleFilterChange"
        />
      </div>
    </n-card>

    <n-card title="操行记录">
      <n-data-table
        :columns="columns"
        :data="filteredRecords"
        :loading="loading"
        :pagination="pagination"
        remote
        @update:page="handlePageChange"
        size="small"
      />
    </n-card>
  </div>
</template>

<script setup>
import { ref, watch, h, computed } from 'vue'
import { NCard, NDataTable, NDescriptions, NDescriptionsItem, NTag, NDatePicker, NSelect } from 'naive-ui'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getChildRecords } from '../../api/conduct'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  currentChild: { type: Object, default: null },
})

const records = ref([])
const allRecords = ref([])
const loading = ref(false)
const pagination = ref({ page: 1, pageSize: 15, itemCount: 0 })
const dateRange = ref(null)
const typeFilter = ref('all')
const trendData = ref([])

const typeOptions = [
  { label: '全部', value: 'all' },
  { label: '加分', value: 'positive' },
  { label: '扣分', value: 'negative' },
]

const columns = [
  {
    title: '日期',
    key: 'created_at',
    width: 100,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-',
  },
  {
    title: '项目',
    key: 'rule_name',
    ellipsis: true,
    render: (row) => {
      const children = []
      children.push(h('div', null, row.rule_name || row.note || '-'))
      if (row.rule_category) {
        children.push(h(NTag, { size: 'tiny', type: 'info', style: 'margin-top: 2px;' }, () => row.rule_category))
      }
      return h('div', null, children)
    },
  },
  {
    title: '分值',
    key: 'points',
    width: 70,
    render: (row) => h(NTag, {
      type: row.points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => (row.points >= 0 ? '+' : '') + row.points),
  },
  {
    title: '教师',
    key: 'operator_name',
    width: 70,
    ellipsis: true,
    render: (row) => row.operator_name || '-',
  },
]

const filteredRecords = computed(() => {
  // Client-side type filtering applied on top of server data
  if (typeFilter.value === 'all') return records.value
  if (typeFilter.value === 'positive') return records.value.filter(r => r.points >= 0)
  return records.value.filter(r => r.points < 0)
})

// Sparkline chart option
const trendOption = computed(() => {
  const dates = trendData.value.map(d => d.date)
  const values = trendData.value.map(d => d.cumulative)

  return {
    grid: { top: 8, right: 8, bottom: 20, left: 40 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(30, 30, 46, 0.95)',
      borderColor: 'rgba(255,255,255,0.1)',
      textStyle: { color: 'rgba(255,255,255,0.85)', fontSize: 12 },
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>累计积分: ${p.value}`
      },
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { fontSize: 10, color: 'rgba(255,255,255,0.35)' },
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: 'rgba(255,255,255,0.35)' },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
    },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color: '#63e2b7', width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(99, 226, 183, 0.25)' },
            { offset: 1, color: 'rgba(99, 226, 183, 0.02)' },
          ],
        },
      },
    }],
  }
})

function handleFilterChange() {
  pagination.value.page = 1
  fetchRecords()
}

async function fetchRecords() {
  if (!props.currentChild) return
  loading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
    }

    // Apply date range filter
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = new Date(dateRange.value[0]).toISOString().split('T')[0]
      params.end_date = new Date(dateRange.value[1]).toISOString().split('T')[0]
    }

    const res = await getChildRecords(props.currentChild.student_id, params)
    const data = res.data
    records.value = data.items || data || []
    pagination.value.itemCount = data.total || records.value.length
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

async function fetchAllForTrend() {
  if (!props.currentChild) return
  try {
    // Fetch recent records for trend calculation
    const res = await getChildRecords(props.currentChild.student_id, {
      page: 1,
      page_size: 200,
    })
    const data = res.data
    allRecords.value = data.items || data || []
    buildTrendData()
  } catch {
    allRecords.value = []
    trendData.value = []
  }
}

function buildTrendData() {
  // Build cumulative points by day for the last 30 days
  const now = new Date()
  const thirtyDaysAgo = new Date(now)
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

  // Group points by date
  const dailyPoints = {}
  for (const r of allRecords.value) {
    if (!r.created_at) continue
    const d = new Date(r.created_at)
    if (d < thirtyDaysAgo) continue
    const key = d.toISOString().split('T')[0]
    dailyPoints[key] = (dailyPoints[key] || 0) + (r.points || 0)
  }

  // Build continuous date series
  const result = []
  let cumulative = 0

  // Calculate initial cumulative from older records
  for (const r of allRecords.value) {
    if (!r.created_at) continue
    const d = new Date(r.created_at)
    if (d < thirtyDaysAgo) {
      cumulative += r.points || 0
    }
  }

  const current = new Date(thirtyDaysAgo)
  while (current <= now) {
    const key = current.toISOString().split('T')[0]
    cumulative += dailyPoints[key] || 0
    result.push({
      date: `${current.getMonth() + 1}/${current.getDate()}`,
      cumulative,
    })
    current.setDate(current.getDate() + 1)
  }

  trendData.value = result
}

function handlePageChange(page) {
  pagination.value.page = page
  fetchRecords()
}

watch(() => props.currentChild, () => {
  pagination.value.page = 1
  dateRange.value = null
  typeFilter.value = 'all'
  fetchRecords()
  fetchAllForTrend()
}, { immediate: true })
</script>

<style scoped>
.filter-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

@media (max-width: 480px) {
  .filter-row {
    flex-direction: column;
  }
  .filter-row > * {
    width: 100% !important;
  }
}
</style>
