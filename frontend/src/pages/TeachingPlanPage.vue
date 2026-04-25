<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">教学计划</h1>
        <p class="page-subtitle">管理学期教学计划，安排每周教学内容与知识点</p>
      </div>
      <n-button type="primary" @click="showCreate = true">新建计划</n-button>
    </div>

    <!-- 过滤栏 -->
    <n-space style="margin-bottom: 16px;">
      <n-select v-model:value="filter.semester" :options="semesterOptions" placeholder="学期"
        clearable style="width: 200px;" @update:value="loadPlans" />
      <n-select v-model:value="filter.subject_code" :options="subjectOptions" placeholder="科目"
        clearable style="width: 150px;" @update:value="loadPlans" />
      <n-select v-model:value="filter.grade_id" :options="gradeOptions" placeholder="年级"
        clearable style="width: 150px;" @update:value="loadPlans" />
    </n-space>

    <!-- 计划列表 -->
    <n-spin :show="loading">
      <n-data-table :columns="columns" :data="plans" :bordered="false" size="small"
        :row-props="rowProps" />
    </n-spin>

    <!-- 周次编辑抽屉 -->
    <n-drawer v-model:show="showDetail" :width="640" placement="right">
      <n-drawer-content :title="detailPlan ? `${detailPlan.subject_code} · ${detailPlan.semester}` : '教学计划详情'">
        <template #footer>
          <n-space>
            <n-button @click="showDetail = false">关闭</n-button>
            <n-button type="primary" @click="handleSaveWeeks" :loading="saving">保存修改</n-button>
          </n-space>
        </template>

        <div v-if="detailPlan">
          <n-space justify="end" style="margin-bottom: 12px;">
            <n-button size="small" @click="addWeek">添加一周</n-button>
          </n-space>

          <n-data-table :columns="weekColumns" :data="editWeeks" :bordered="false" size="small" />
        </div>
      </n-drawer-content>
    </n-drawer>

    <!-- 新建计划弹窗 -->
    <n-modal v-model:show="showCreate" preset="dialog" title="新建教学计划"
      positive-text="创建" negative-text="取消" @positive-click="handleCreate">
      <n-form :model="createForm" label-placement="left" label-width="80">
        <n-form-item label="学期">
          <n-input v-model:value="createForm.semester" placeholder="如: 2025-2026-1" />
        </n-form-item>
        <n-form-item label="科目">
          <n-input v-model:value="createForm.subject_code" placeholder="如: SX" />
        </n-form-item>
        <n-form-item label="年级">
          <n-select v-model:value="createForm.grade_id" :options="gradeOptions"
            placeholder="选择年级" clearable />
        </n-form-item>
      </n-form>
    </n-modal>

    <!-- 删除确认 -->
    <n-modal v-model:show="showDeleteConfirm" preset="dialog" title="确认删除"
      positive-text="删除" negative-text="取消" type="warning"
      @positive-click="handleDelete">
      <p>确定删除该教学计划吗？此操作不可恢复。</p>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { NButton, NTag, NInput, NSpace, useMessage } from 'naive-ui'
import {
  createTeachingPlan, listTeachingPlans, getTeachingPlan,
  updateTeachingPlan, deleteTeachingPlan, listSemesters,
} from '../api/academic.js'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const plans = ref([])
const showCreate = ref(false)
const showDetail = ref(false)
const showDeleteConfirm = ref(false)
const detailPlan = ref(null)
const editWeeks = ref([])
const deleteTargetId = ref(null)

const filter = ref({ semester: null, subject_code: null, grade_id: null })

const semesterOptions = ref([])
const gradeOptions = ref([])
const subjectOptions = [
  { label: '数学', value: 'SX' },
  { label: '语文', value: 'YW' },
  { label: '英语', value: 'YY' },
  { label: '物理', value: 'WL' },
  { label: '化学', value: 'HX' },
  { label: '生物', value: 'SW' },
  { label: '政治', value: 'ZZ' },
  { label: '历史', value: 'LS' },
  { label: '地理', value: 'DL' },
]

const createForm = ref({ semester: '', subject_code: '', grade_id: null })

const columns = [
  { title: '科目', key: 'subject_code', width: 80 },
  { title: '学期', key: 'semester', width: 140 },
  {
    title: '周数', key: 'weeks_count', width: 80,
    render: (row) => h(NTag, { type: 'info', size: 'small', bordered: false }, { default: () => `${row.weeks_count} 周` }),
  },
  {
    title: '创建时间', key: 'created_at', width: 170,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-',
  },
  {
    title: '操作', key: 'actions', width: 120,
    render: (row) => h(NSpace, { size: 'small' }, {
      default: () => [
        h(NButton, { text: true, type: 'primary', size: 'small', onClick: () => openDetail(row.id) }, { default: () => '编辑' }),
        h(NButton, { text: true, type: 'error', size: 'small', onClick: () => confirmDelete(row.id) }, { default: () => '删除' }),
      ],
    }),
  },
]

const weekColumns = [
  { title: '周次', key: 'week_number', width: 60 },
  {
    title: '主题', key: 'topic',
    render: (row, idx) => h(NInput, {
      value: row.topic, size: 'small',
      onUpdateValue: (v) => { editWeeks.value[idx].topic = v },
    }),
  },
  {
    title: '知识点', key: 'knowledge_points',
    render: (row) => h(NSpace, { size: 4 }, {
      default: () => (row.knowledge_points || []).map(
        kp => h(NTag, { size: 'tiny', bordered: false }, { default: () => kp }),
      ),
    }),
  },
  {
    title: '备注', key: 'notes', width: 140,
    render: (row, idx) => h(NInput, {
      value: row.notes, size: 'small',
      onUpdateValue: (v) => { editWeeks.value[idx].notes = v },
    }),
  },
]

function rowProps(row) {
  return { style: 'cursor: pointer;' }
}

async function loadSemesters() {
  try {
    const { data } = await listSemesters()
    semesterOptions.value = data.map(s => ({ label: s.name, value: s.school_year + '-' + s.term }))
  } catch { /* ignore */ }
}

async function loadGrades() {
  try {
    const client = (await import('../api/client.js')).default
    const { data } = await client.get('/grades')
    gradeOptions.value = data.map(g => ({ label: g.name, value: g.id }))
  } catch { /* ignore */ }
}

async function loadPlans() {
  loading.value = true
  try {
    const params = {}
    if (filter.value.semester) params.semester = filter.value.semester
    if (filter.value.subject_code) params.subject_code = filter.value.subject_code
    if (filter.value.grade_id) params.grade_id = filter.value.grade_id
    const { data } = await listTeachingPlans(params)
    plans.value = data
  } catch { message.error('加载教学计划失败') }
  loading.value = false
}

async function openDetail(id) {
  try {
    const { data } = await getTeachingPlan(id)
    detailPlan.value = data
    editWeeks.value = JSON.parse(JSON.stringify(data.weeks_json || []))
    showDetail.value = true
  } catch { message.error('加载详情失败') }
}

function addWeek() {
  const nextNum = editWeeks.value.length + 1
  editWeeks.value.push({ week_number: nextNum, topic: '', knowledge_points: [], notes: '' })
}

async function handleSaveWeeks() {
  if (!detailPlan.value) return
  saving.value = true
  try {
    await updateTeachingPlan(detailPlan.value.id, { weeks_json: editWeeks.value })
    message.success('保存成功')
    await loadPlans()
  } catch (e) { message.error(e.response?.data?.detail || '保存失败') }
  saving.value = false
}

async function handleCreate() {
  if (!createForm.value.semester || !createForm.value.subject_code) {
    message.warning('请填写学期和科目'); return
  }
  try {
    const initialWeek = [{ week_number: 1, topic: '', knowledge_points: [], notes: '' }]
    await createTeachingPlan({
      ...createForm.value,
      weeks_json: initialWeek,
    })
    message.success('教学计划创建成功')
    showCreate.value = false
    createForm.value = { semester: '', subject_code: '', grade_id: null }
    await loadPlans()
  } catch (e) {
    if (e.response?.status === 409) {
      message.error('该科目+年级+学期的教学计划已存在')
    } else {
      message.error(e.response?.data?.detail || '创建失败')
    }
  }
}

function confirmDelete(id) {
  deleteTargetId.value = id
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!deleteTargetId.value) return
  try {
    await deleteTeachingPlan(deleteTargetId.value)
    message.success('已删除')
    deleteTargetId.value = null
    await loadPlans()
  } catch (e) { message.error(e.response?.data?.detail || '删除失败') }
}

onMounted(async () => {
  await Promise.all([loadSemesters(), loadGrades()])
  await loadPlans()
})
</script>
