<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">学期管理</h1>
        <p class="page-subtitle">管理学年学期、节次时间</p>
      </div>
      <n-button type="primary" @click="showCreate = true">新建学期</n-button>
    </div>

    <!-- 统计卡片 -->
    <n-grid :cols="3" :x-gap="16" :y-gap="16" style="margin-bottom: 20px;">
      <n-gi>
        <n-card size="small">
          <n-statistic label="当前学期" :value="activeSemester?.name || '未设置'" />
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small">
          <n-statistic label="剩余天数" :value="remainingDays">
            <template #suffix>天</template>
          </n-statistic>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card size="small">
          <n-statistic label="已配置节次" :value="periods.length">
            <template #suffix>节</template>
          </n-statistic>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- 学期时间线 -->
    <n-card v-if="semesters.length > 0" size="small" title="学期时间线" style="margin-bottom: 20px;">
      <n-timeline>
        <n-timeline-item
          v-for="s in sortedSemesters"
          :key="s.id"
          :type="s.is_current ? 'success' : 'default'"
          :title="s.name"
          :content="`${s.start_date} ~ ${s.end_date}`"
          :time="s.school_year + ' 第' + s.term + '学期'"
        />
      </n-timeline>
    </n-card>

    <!-- 学期列表 -->
    <n-spin :show="loading">
      <n-data-table
        :columns="columns"
        :data="semesters"
        :bordered="false"
        size="small"
        :row-class-name="rowClassName"
      />
    </n-spin>

    <!-- 节次配置区 -->
    <div v-if="activeSemester" style="margin-top: 32px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h2 style="font-size: 17px; font-weight: 600; margin: 0;">
          节次时间 · {{ activeSemester.name }}
        </h2>
        <n-button size="small" type="primary" @click="handleAddPeriod">添加节次</n-button>
      </div>
      <n-data-table :columns="periodColumns" :data="periods" :bordered="false" size="small" />
    </div>

    <!-- 新建学期弹窗 -->
    <n-modal v-model:show="showCreate" preset="dialog" title="新建学期" positive-text="创建" negative-text="取消"
      @positive-click="handleCreate">
      <n-form :model="form" label-placement="left" label-width="80">
        <n-form-item label="名称">
          <n-input v-model:value="form.name" placeholder="如: 2025-2026学年第二学期" />
        </n-form-item>
        <n-form-item label="学年">
          <n-input v-model:value="form.school_year" placeholder="如: 2025-2026" />
        </n-form-item>
        <n-form-item label="学期">
          <n-radio-group v-model:value="form.term">
            <n-radio :value="1">第一学期</n-radio>
            <n-radio :value="2">第二学期</n-radio>
          </n-radio-group>
        </n-form-item>
        <n-form-item label="起止日期">
          <n-date-picker v-model:value="dateRange" type="daterange" style="width: 100%;" />
        </n-form-item>
      </n-form>
    </n-modal>

    <!-- 编辑学期弹窗 -->
    <n-modal v-model:show="showEdit" preset="dialog" title="编辑学期" positive-text="保存" negative-text="取消"
      @positive-click="handleEdit">
      <n-form :model="editForm" label-placement="left" label-width="80">
        <n-form-item label="名称">
          <n-input v-model:value="editForm.name" placeholder="学期名称" />
        </n-form-item>
        <n-form-item label="学年">
          <n-input v-model:value="editForm.school_year" placeholder="如: 2025-2026" />
        </n-form-item>
        <n-form-item label="学期">
          <n-radio-group v-model:value="editForm.term">
            <n-radio :value="1">第一学期</n-radio>
            <n-radio :value="2">第二学期</n-radio>
          </n-radio-group>
        </n-form-item>
        <n-form-item label="起止日期">
          <n-date-picker v-model:value="editDateRange" type="daterange" style="width: 100%;" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, computed, onMounted } from 'vue'
import { NButton, NTag, NStatistic, NTimePicker, useMessage, useDialog } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import {
  listSemesters, createSemester, activateSemester, getPeriods,
  updateSemester, setPeriods,
} from '../api/academic.js'

const message = useMessage()
const dialog = useDialog()
const auth = useAuthStore()
const loading = ref(false)
const semesters = ref([])
const periods = ref([])
const showCreate = ref(false)
const showEdit = ref(false)
const dateRange = ref(null)
const editDateRange = ref(null)
const form = ref({ name: '', school_year: '', term: 1 })
const editForm = ref({ id: null, name: '', school_year: '', term: 1 })

const activeSemester = computed(() => semesters.value.find(s => s.is_current))

const sortedSemesters = computed(() =>
  [...semesters.value].sort((a, b) => (b.start_date || '').localeCompare(a.start_date || ''))
)

const remainingDays = computed(() => {
  const active = activeSemester.value
  if (!active?.end_date) return '--'
  const end = new Date(active.end_date + 'T23:59:59')
  const now = new Date()
  const diff = Math.ceil((end - now) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : 0
})

function rowClassName(row) {
  return row.is_current ? 'semester-current-row' : ''
}

const columns = [
  { title: '学期名称', key: 'name' },
  { title: '学年', key: 'school_year', width: 120 },
  { title: '学期', key: 'term', width: 80, render: (row) => `第${row.term}学期` },
  { title: '开始', key: 'start_date', width: 120 },
  { title: '结束', key: 'end_date', width: 120 },
  {
    title: '状态', key: 'is_current', width: 100,
    render: (row) => row.is_current
      ? h(NTag, { type: 'success', size: 'small' }, { default: () => '当前' })
      : h(NTag, { size: 'small', bordered: false }, { default: () => '历史' }),
  },
  {
    title: '操作', key: 'actions', width: 180,
    render: (row) => {
      const buttons = []
      buttons.push(h(NButton, {
        text: true, type: 'info', size: 'small',
        onClick: () => openEdit(row),
        style: 'margin-right: 8px',
      }, { default: () => '编辑' }))
      if (!row.is_current) {
        buttons.push(h(NButton, {
          text: true, type: 'primary', size: 'small',
          onClick: () => handleActivate(row.id),
        }, { default: () => '设为当前' }))
      }
      return buttons
    },
  },
]

const periodColumns = computed(() => [
  { title: '序号', key: 'period_number', width: 60 },
  { title: '名称', key: 'name', width: 120 },
  {
    title: '开始时间', key: 'start_time', width: 180,
    render: (row, index) => h(NTimePicker, {
      value: timeToTimestamp(row.start_time),
      format: 'HH:mm',
      'onUpdate:value': (val) => updatePeriodTime(index, 'start_time', val),
      size: 'small',
      style: 'width: 140px',
    }),
  },
  {
    title: '结束时间', key: 'end_time', width: 180,
    render: (row, index) => h(NTimePicker, {
      value: timeToTimestamp(row.end_time),
      format: 'HH:mm',
      'onUpdate:value': (val) => updatePeriodTime(index, 'end_time', val),
      size: 'small',
      style: 'width: 140px',
    }),
  },
  {
    title: '类型', key: 'period_type', width: 100,
    render: (row) => {
      const map = { class: '上课', break: '课间', activity: '活动', self_study: '自习' }
      const color = row.period_type === 'class' ? 'success' : row.period_type === 'break' ? 'default' : 'info'
      return h(NTag, { type: color, size: 'small' }, { default: () => map[row.period_type] || row.period_type })
    },
  },
  {
    title: '操作', key: 'period_actions', width: 80,
    render: (_row, index) => h(NButton, {
      text: true, type: 'error', size: 'small',
      onClick: () => handleDeletePeriod(index),
    }, { default: () => '删除' }),
  },
])

// Time conversion helpers for NTimePicker (expects ms-since-midnight timestamp)
function timeToTimestamp(timeStr) {
  if (!timeStr) return null
  const parts = timeStr.split(':')
  const h = parseInt(parts[0], 10)
  const m = parseInt(parts[1] || '0', 10)
  // NTimePicker uses ms since midnight
  return (h * 60 + m) * 60 * 1000
}

function timestampToTime(ts) {
  if (ts == null) return '08:00'
  const totalMinutes = Math.floor(ts / 60000)
  const h = Math.floor(totalMinutes / 60)
  const m = totalMinutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

function updatePeriodTime(index, field, val) {
  periods.value[index][field] = timestampToTime(val)
  savePeriods()
}

async function savePeriods() {
  const active = activeSemester.value
  if (!active) return
  const schoolId = auth.currentRole?.school_id
  if (!schoolId) return
  try {
    await setPeriods({
      semester_id: active.id,
      school_id: schoolId,
      periods: periods.value,
    })
  } catch (e) {
    message.error(e.response?.data?.detail || '保存节次失败')
  }
}

function handleAddPeriod() {
  const nextNum = periods.value.length + 1
  periods.value.push({
    period_number: nextNum,
    name: `第${nextNum}节`,
    start_time: '08:00',
    end_time: '08:45',
    period_type: 'class',
  })
  savePeriods()
}

function handleDeletePeriod(index) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除"${periods.value[index]?.name || '该节次'}"吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: () => {
      periods.value.splice(index, 1)
      // Re-number
      periods.value.forEach((p, i) => { p.period_number = i + 1 })
      savePeriods()
    },
  })
}

function openEdit(row) {
  editForm.value = {
    id: row.id,
    name: row.name,
    school_year: row.school_year,
    term: row.term,
  }
  if (row.start_date && row.end_date) {
    editDateRange.value = [
      new Date(row.start_date).getTime(),
      new Date(row.end_date).getTime(),
    ]
  } else {
    editDateRange.value = null
  }
  showEdit.value = true
}

async function loadData() {
  loading.value = true
  try {
    const { data } = await listSemesters()
    semesters.value = data
    const current = data.find(s => s.is_current)
    if (current) {
      const { data: p } = await getPeriods(current.id)
      periods.value = p
    } else {
      periods.value = []
    }
  } catch { message.error('加载学期失败') }
  loading.value = false
}

async function handleCreate() {
  if (!dateRange.value || dateRange.value.length !== 2) {
    message.warning('请选择起止日期'); return
  }
  try {
    const toDate = (ts) => new Date(ts).toISOString().split('T')[0]
    await createSemester({
      ...form.value,
      start_date: toDate(dateRange.value[0]),
      end_date: toDate(dateRange.value[1]),
    })
    message.success('学期创建成功')
    showCreate.value = false
    form.value = { name: '', school_year: '', term: 1 }
    dateRange.value = null
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '创建失败') }
}

async function handleEdit() {
  if (!editDateRange.value || editDateRange.value.length !== 2) {
    message.warning('请选择起止日期'); return
  }
  try {
    const toDate = (ts) => new Date(ts).toISOString().split('T')[0]
    await updateSemester(editForm.value.id, {
      name: editForm.value.name,
      school_year: editForm.value.school_year,
      term: editForm.value.term,
      start_date: toDate(editDateRange.value[0]),
      end_date: toDate(editDateRange.value[1]),
    })
    message.success('学期更新成功')
    showEdit.value = false
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '更新失败') }
}

async function handleActivate(id) {
  try {
    await activateSemester(id)
    message.success('已设为当前学期')
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '操作失败') }
}

onMounted(loadData)
</script>

<style scoped>
:deep(.semester-current-row td) {
  background-color: rgba(24, 160, 88, 0.08) !important;
}
</style>
