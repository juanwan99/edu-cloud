<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">学期管理</h1>
        <p class="page-subtitle">管理学年学期、节次时间</p>
      </div>
      <n-button type="primary" @click="showCreate = true">新建学期</n-button>
    </div>

    <n-spin :show="loading">
      <n-data-table :columns="columns" :data="semesters" :bordered="false" size="small" />
    </n-spin>

    <!-- 节次配置区 -->
    <div v-if="activeSemester" style="margin-top: 32px;">
      <h2 style="font-size: 17px; font-weight: 600; margin-bottom: 16px;">
        节次时间 · {{ activeSemester.name }}
      </h2>
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
  </div>
</template>

<script setup>
import { ref, h, computed, onMounted } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import {
  listSemesters, createSemester, activateSemester, getPeriods,
} from '../api/academic.js'

const message = useMessage()
const loading = ref(false)
const semesters = ref([])
const periods = ref([])
const showCreate = ref(false)
const dateRange = ref(null)
const form = ref({ name: '', school_year: '', term: 1 })

const activeSemester = computed(() => semesters.value.find(s => s.is_current))

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
    title: '操作', key: 'actions', width: 120,
    render: (row) => row.is_current ? null : h(NButton, {
      text: true, type: 'primary', size: 'small',
      onClick: () => handleActivate(row.id),
    }, { default: () => '设为当前' }),
  },
]

const periodColumns = [
  { title: '序号', key: 'period_number', width: 60 },
  { title: '名称', key: 'name', width: 100 },
  { title: '开始', key: 'start_time', width: 100 },
  { title: '结束', key: 'end_time', width: 100 },
  {
    title: '类型', key: 'period_type', width: 100,
    render: (row) => {
      const map = { class: '上课', break: '课间', activity: '活动', self_study: '自习' }
      const color = row.period_type === 'class' ? 'success' : row.period_type === 'break' ? 'default' : 'info'
      return h(NTag, { type: color, size: 'small' }, { default: () => map[row.period_type] || row.period_type })
    },
  },
]

async function loadData() {
  loading.value = true
  try {
    const { data } = await listSemesters()
    semesters.value = data
    const current = data.find(s => s.is_current)
    if (current) {
      const { data: p } = await getPeriods(current.id)
      periods.value = p
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

async function handleActivate(id) {
  try {
    await activateSemester(id)
    message.success('已设为当前学期')
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '操作失败') }
}

onMounted(loadData)
</script>
