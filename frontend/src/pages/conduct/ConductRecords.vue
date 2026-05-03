<template>
  <div>
    <n-page-header title="积分记录" subtitle="查看和管理所有操行积分变动" style="margin-bottom: var(--space-4);" />

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: var(--space-4);">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <!-- Stat cards -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-label">本周记录数</div>
          <div class="stat-value">{{ statCards.weekCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">加分总额</div>
          <div class="stat-value">
            {{ statCards.plusTotal }}<span class="stat-suffix" style="color: var(--color-success);">+</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">扣分总额</div>
          <div class="stat-value">
            {{ statCards.minusTotal }}<span class="stat-suffix" style="color: var(--color-danger);">-</span>
          </div>
        </div>
      </div>

      <!-- Filters -->
      <n-card size="small" style="margin-bottom: var(--space-4);">
        <n-space>
          <n-input
            v-model:value="filterStudent"
            placeholder="搜索学生姓名"
            clearable
            style="width: 180px;"
            @update:value="debouncedLoad"
          />
          <n-select
            v-model:value="filterType"
            :options="typeOptions"
            placeholder="类型"
            clearable
            style="width: 120px;"
            @update:value="handleFilterChange"
          />
          <n-select
            v-model:value="filterRule"
            :options="ruleOptions"
            placeholder="班规项"
            clearable
            style="width: 160px;"
            @update:value="handleFilterChange"
          />
          <n-date-picker
            v-model:value="dateRange"
            type="daterange"
            clearable
            @update:value="handleFilterChange"
          />
          <n-button @click="resetFilters">重置</n-button>
        </n-space>
      </n-card>

      <!-- Batch delete bar -->
      <div v-if="checkedRowKeys.length > 0" style="margin-bottom: var(--space-3);">
        <n-space align="center">
          <span style="color: rgba(255,255,255,0.65);">已选 {{ checkedRowKeys.length }} 条</span>
          <n-popconfirm @positive-click="handleBatchDelete">
            <template #trigger>
              <n-button type="error" size="small">批量删除</n-button>
            </template>
            确定删除选中的 {{ checkedRowKeys.length }} 条记录？
          </n-popconfirm>
        </n-space>
      </div>

      <!-- Records table -->
      <n-card>
        <n-spin :show="loading">
          <n-data-table
            :columns="columns"
            :data="filteredRecords"
            :pagination="pagination"
            :row-key="(row) => row.id"
            v-model:checked-row-keys="checkedRowKeys"
            size="small"
            remote
            @update:page="handlePageChange"
            @update:page-size="handlePageSizeChange"
          />
        </n-spin>
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import {
  NPageHeader, NCard, NDataTable, NInput, NDatePicker, NButton,
  NSpace, NSpin, NTag, NPopconfirm, NAlert, NSelect, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import { getRecords, deleteRecord } from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const records = ref([])
const loading = ref(false)
const filterStudent = ref('')
const filterType = ref(null)
const filterRule = ref(null)
const dateRange = ref(null)
const page = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)
const checkedRowKeys = ref([])

const statCards = ref({ weekCount: 0, plusTotal: 0, minusTotal: 0 })

const typeOptions = [
  { label: '全部', value: null },
  { label: '加分', value: 'plus' },
  { label: '扣分', value: 'minus' },
]

const ruleOptions = computed(() => {
  const names = new Set()
  records.value.forEach(r => { if (r.rule_name) names.add(r.rule_name) })
  return Array.from(names).map(n => ({ label: n, value: n }))
})

const filteredRecords = computed(() => {
  let data = records.value
  if (filterType.value === 'plus') {
    data = data.filter(r => r.points > 0)
  } else if (filterType.value === 'minus') {
    data = data.filter(r => r.points < 0)
  }
  if (filterRule.value) {
    data = data.filter(r => r.rule_name === filterRule.value)
  }
  return data
})

const pagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  pageCount: Math.ceil(totalCount.value / pageSize.value),
  itemCount: totalCount.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
}))

const columns = [
  { type: 'selection', width: 40 },
  {
    title: '日期',
    key: 'created_at',
    width: 160,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-',
  },
  { title: '学生姓名', key: 'student_name', width: 100 },
  {
    title: '积分',
    key: 'points',
    width: 80,
    render: (row) => h(NTag, {
      type: row.points >= 0 ? 'success' : 'error',
      size: 'small',
    }, () => `${row.points >= 0 ? '+' : ''}${row.points}`),
  },
  { title: '原因', key: 'note', ellipsis: { tooltip: true } },
  { title: '班规项', key: 'rule_name', width: 120, ellipsis: { tooltip: true } },
  { title: '操作人', key: 'operator_name', width: 100 },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render: (row) => h(NPopconfirm, {
      onPositiveClick: () => handleDelete(row.id),
    }, {
      trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, () => '删除'),
      default: () => '确定删除这条记录？',
    }),
  },
]

let debounceTimer = null
function debouncedLoad() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    page.value = 1
    loadRecords()
  }, 300)
}

function handleFilterChange() {
  page.value = 1
  loadRecords()
}

async function loadRecords() {
  if (!classId.value) return
  loading.value = true
  checkedRowKeys.value = []
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filterStudent.value) params.student_name = filterStudent.value
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_date = new Date(dateRange.value[0]).toISOString().split('T')[0]
      params.end_date = new Date(dateRange.value[1]).toISOString().split('T')[0]
    }
    const res = await getRecords(classId.value, params)
    records.value = res.data.items || res.data || []
    totalCount.value = res.data.total || records.value.length
  } catch {
    records.value = []
  } finally {
    loading.value = false
  }
}

async function loadWeekStats() {
  if (!classId.value) return
  try {
    const now = new Date()
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
    const res = await getRecords(classId.value, {
      page: 1,
      page_size: 200,
      start_date: weekAgo.toISOString().split('T')[0],
    })
    const items = res.data.items || res.data || []
    statCards.value.weekCount = items.length
    statCards.value.plusTotal = items.filter(r => r.points > 0).reduce((s, r) => s + r.points, 0)
    statCards.value.minusTotal = Math.abs(items.filter(r => r.points < 0).reduce((s, r) => s + r.points, 0))
  } catch {
    statCards.value = { weekCount: 0, plusTotal: 0, minusTotal: 0 }
  }
}

function handlePageChange(p) {
  page.value = p
  loadRecords()
}

function handlePageSizeChange(s) {
  pageSize.value = s
  page.value = 1
  loadRecords()
}

function resetFilters() {
  filterStudent.value = ''
  filterType.value = null
  filterRule.value = null
  dateRange.value = null
  page.value = 1
  loadRecords()
}

async function handleDelete(recordId) {
  try {
    await deleteRecord(classId.value, recordId)
    message.success('记录已删除')
    await loadRecords()
    await loadWeekStats()
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleBatchDelete() {
  const ids = [...checkedRowKeys.value]
  let successCount = 0
  for (const id of ids) {
    try {
      await deleteRecord(classId.value, id)
      successCount++
    } catch {
      // continue with remaining
    }
  }
  if (successCount > 0) {
    message.success(`已删除 ${successCount} 条记录`)
    checkedRowKeys.value = []
    await loadRecords()
    await loadWeekStats()
  } else {
    message.error('删除失败')
  }
}

onMounted(() => {
  if (classId.value) {
    loadRecords()
    loadWeekStats()
  }
})
</script>
