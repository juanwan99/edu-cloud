<template>
  <div>
    <n-page-header title="积分记录" subtitle="查看和管理所有操行积分变动" style="margin-bottom: 16px;" />

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <!-- Filters -->
      <n-card size="small" style="margin-bottom: 16px;">
        <n-space>
          <n-input
            v-model:value="filterStudent"
            placeholder="搜索学生姓名"
            clearable
            style="width: 180px;"
            @update:value="debouncedLoad"
          />
          <n-date-picker
            v-model:value="dateRange"
            type="daterange"
            clearable
            @update:value="loadRecords"
          />
          <n-button @click="resetFilters">重置</n-button>
        </n-space>
      </n-card>

      <!-- Records table -->
      <n-card>
        <n-spin :show="loading">
          <n-data-table
            :columns="columns"
            :data="records"
            :pagination="pagination"
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
  NSpace, NSpin, NTag, NPopconfirm, NAlert, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import { getRecords, deleteRecord } from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const records = ref([])
const loading = ref(false)
const filterStudent = ref('')
const dateRange = ref(null)
const page = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

const pagination = computed(() => ({
  page: page.value,
  pageSize: pageSize.value,
  pageCount: Math.ceil(totalCount.value / pageSize.value),
  itemCount: totalCount.value,
  showSizePicker: true,
  pageSizes: [10, 20, 50],
}))

const columns = [
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

async function loadRecords() {
  if (!classId.value) return
  loading.value = true
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
  dateRange.value = null
  page.value = 1
  loadRecords()
}

async function handleDelete(recordId) {
  try {
    await deleteRecord(classId.value, recordId)
    message.success('记录已删除')
    await loadRecords()
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => {
  if (classId.value) loadRecords()
})
</script>
