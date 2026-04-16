<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">考试管理</h1>
        <p class="page-subtitle">管理所有考试和科目</p>
      </div>
      <n-button type="primary" class="btn-pill" @click="showCreate = true">创建考试</n-button>
    </div>

    <n-data-table :columns="columns" :data="exams" :loading="loading" :row-props="rowProps" />

    <n-modal v-model:show="showCreate" preset="card" title="创建考试" style="width: 420px;" :mask-closable="true">
      <n-form ref="createFormRef" :model="createForm" :rules="createRules" label-placement="top">
        <n-form-item label="考试名称" path="name">
          <n-input v-model:value="createForm.name" placeholder="例如：2026年春季期中考试" />
        </n-form-item>
        <n-form-item label="答题卡标题" path="card_title">
          <n-input v-model:value="createForm.card_title" placeholder="显示在答题卡上的标题" />
        </n-form-item>
      </n-form>
      <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px;">
        <n-button class="btn-pill" @click="showCreate = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="creating" @click="handleCreate">创建</n-button>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NTag, NButton, useMessage } from 'naive-ui'
import { listExams, createExam } from '../api/exams'

const router = useRouter()
const message = useMessage()
const loading = ref(true)
const exams = ref([])
const showCreate = ref(false)
const createFormRef = ref(null)
const creating = ref(false)
const createForm = reactive({ name: '', card_title: '' })
const createRules = {
  name: { required: true, message: '请输入考试名称', trigger: 'blur' },
  card_title: { required: true, message: '请输入答题卡标题', trigger: 'blur' },
}

const statusMap = {
  draft: { label: '草稿', type: 'default' },
  scanning: { label: '扫描中', type: 'info' },
  grading: { label: '批改中', type: 'warning' },
  reviewing: { label: '复核中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
}

const columns = [
  { title: '考试名称', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '状态', key: 'status', width: 100,
    render: (row) => h(NTag, { type: statusMap[row.status]?.type || 'default', round: true, size: 'small' },
      { default: () => statusMap[row.status]?.label || row.status }),
  },
  {
    title: '创建时间', key: 'created_at', width: 140,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-',
  },
  {
    title: '操作', key: 'actions', width: 180,
    render: (row) => h('div', { style: 'display: flex; gap: 8px;', onClick: (e) => e.stopPropagation() }, [
      h(NButton, { text: true, type: 'primary', size: 'small', onClick: () => router.push(`/exams/${row.id}`) },
        { default: () => '详情' }),
      h(NButton, { text: true, type: 'info', size: 'small', onClick: () => router.push(`/analytics/${row.id}`) },
        { default: () => '分析' }),
    ]),
  },
]

function rowProps(row) {
  return {
    style: 'cursor: pointer;',
    onClick: () => router.push(`/exams/${row.id}`),
  }
}

async function loadExams() {
  loading.value = true
  try {
    const { data } = await listExams()
    exams.value = data
  } catch { /* interceptor handles */ }
  loading.value = false
}

async function handleCreate() {
  try {
    await createFormRef.value?.validate()
  } catch { return }
  creating.value = true
  try {
    await createExam({ name: createForm.name, card_title: createForm.card_title })
    message.success('考试创建成功')
    createForm.name = ''
    createForm.card_title = ''
    showCreate.value = false
    await loadExams()
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

onMounted(loadExams)
</script>
