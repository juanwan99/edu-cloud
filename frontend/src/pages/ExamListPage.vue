<template>
  <div>
    <div class="page-header page-header-row">
      <div>
        <h1 class="page-title">考试管理</h1>
        <p class="page-subtitle">管理所有考试和科目</p>
      </div>
      <n-button v-if="canManageExams" type="primary" class="btn-pill" @click="showCreate = true">创建考试</n-button>
    </div>

    <!-- Stats Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon stat-icon--yellow">
          <AppIcon name="exam" :size="20" />
        </div>
        <div class="stat-label">考试总数</div>
        <div class="stat-value">{{ stats.total ?? '--' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon--purple">
          <AppIcon name="marking" :size="20" />
        </div>
        <div class="stat-label">进行中</div>
        <div class="stat-value">{{ stats.active ?? '--' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon--orange">
          <AppIcon name="chart" :size="20" />
        </div>
        <div class="stat-label">已完成</div>
        <div class="stat-value">{{ stats.completed ?? '--' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon stat-icon--ink">
          <AppIcon name="document" :size="20" />
        </div>
        <div class="stat-label">草稿</div>
        <div class="stat-value">{{ stats.draft ?? '--' }}</div>
      </div>
    </div>

    <!-- Search + Filter Bar -->
    <div class="filter-bar">
      <n-input
        v-model:value="searchText"
        placeholder="搜索考试名称..."
        clearable
        style="max-width: 320px;"
      >
        <template #prefix>
          <span style="opacity: 0.5;">&#128269;</span>
        </template>
      </n-input>
      <n-select
        v-model:value="statusFilter"
        :options="statusFilterOptions"
        placeholder="筛选状态"
        clearable
        style="width: 160px;"
      />
      <n-button
        v-if="searchText || statusFilter"
        quaternary
        size="small"
        @click="clearFilters"
      >
        清除筛选
      </n-button>
    </div>

    <!-- Data Table -->
    <n-data-table
      v-if="filteredExams.length > 0 || loading"
      :columns="columns"
      :data="filteredExams"
      :loading="loading"
      :row-props="rowProps"
      :default-sort="{ columnKey: 'created_at', order: 'descend' }"
    />

    <!-- Empty State -->
    <div v-if="!loading && filteredExams.length === 0" class="empty-state">
      <n-empty
        v-if="exams.length === 0"
        description="还没有创建考试"
        size="large"
      >
        <template #extra>
          <n-button v-if="canManageExams" type="primary" class="btn-pill" @click="showCreate = true">创建第一场考试</n-button>
        </template>
      </n-empty>
      <n-empty
        v-else
        description="没有匹配的考试"
        size="large"
      >
        <template #extra>
          <n-button quaternary size="small" @click="clearFilters">清除筛选条件</n-button>
        </template>
      </n-empty>
    </div>

    <!-- Create Exam Modal -->
    <n-modal v-model:show="showCreate" preset="card" title="创建考试" style="width: 480px;" :mask-closable="true">
      <n-form ref="createFormRef" :model="createForm" :rules="createRules" label-placement="top">
        <n-form-item label="考试名称" path="name">
          <n-input v-model:value="createForm.name" placeholder="例如：2026年春季期中考试" />
        </n-form-item>
        <n-form-item label="答题卡标题" path="card_title">
          <n-input v-model:value="createForm.card_title" placeholder="显示在答题卡上的标题" />
        </n-form-item>
        <n-form-item label="考试日期" path="exam_date">
          <n-date-picker v-model:value="createForm.exam_date" type="date" style="width: 100%;" />
        </n-form-item>
        <n-form-item label="考试描述" path="description">
          <n-input
            v-model:value="createForm.description"
            type="textarea"
            placeholder="可选：补充考试说明"
            :rows="3"
          />
        </n-form-item>
      </n-form>
      <div class="modal-footer">
        <n-button class="btn-pill" @click="showCreate = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="creating" @click="handleCreate">创建</n-button>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { NTag, NButton, NPopconfirm, useMessage } from 'naive-ui'
import { listExams, createExam, archiveExam, deleteExam } from '../api/exams'
import { useAuthStore } from '../stores/auth.js'
import { normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'
import AppIcon from '../components/AppIcon.vue'

const router = useRouter()
const message = useMessage()
const auth = useAuthStore()
const normalizedRole = computed(() => normalizeRole(auth.currentRole?.role || ''))
const canManageExams = computed(() => hasPermission(normalizedRole.value, 'manage_exams'))
const loading = ref(true)
const exams = ref([])
const showCreate = ref(false)
const createFormRef = ref(null)
const creating = ref(false)
const searchText = ref('')
const statusFilter = ref(null)

const createForm = reactive({
  name: '',
  card_title: '',
  exam_date: null,
  description: '',
})

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
  published: { label: '已发布', type: 'success' },
  archived: { label: '已归档', type: 'default' },
}

const statusFilterOptions = [
  { label: '草稿', value: 'draft' },
  { label: '扫描中', value: 'scanning' },
  { label: '批改中', value: 'grading' },
  { label: '复核中', value: 'reviewing' },
  { label: '已完成', value: 'completed' },
  { label: '已发布', value: 'published' },
  { label: '已归档', value: 'archived' },
]

// Stats computed from exams list
const stats = computed(() => {
  const list = exams.value
  const activeStatuses = ['scanning', 'grading', 'reviewing']
  return {
    total: list.length,
    active: list.filter(e => activeStatuses.includes(e.status)).length,
    completed: list.filter(e => e.status === 'completed' || e.status === 'published').length,
    draft: list.filter(e => e.status === 'draft').length,
  }
})

// Filtered exams (search + status filter)
const filteredExams = computed(() => {
  let result = exams.value
  if (statusFilter.value) {
    result = result.filter(e => e.status === statusFilter.value)
  }
  if (searchText.value) {
    const keyword = searchText.value.toLowerCase()
    result = result.filter(e => e.name?.toLowerCase().includes(keyword))
  }
  return result
})

function clearFilters() {
  searchText.value = ''
  statusFilter.value = null
}

const columns = [
  {
    title: '考试名称',
    key: 'name',
    ellipsis: { tooltip: true },
    sorter: (a, b) => (a.name || '').localeCompare(b.name || ''),
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    filterOptions: statusFilterOptions.map(o => ({ label: o.label, value: o.value })),
    render: (row) => h(NTag, {
      type: statusMap[row.status]?.type || 'default',
      round: true,
      size: 'small',
    }, { default: () => statusMap[row.status]?.label || row.status }),
  },
  {
    title: '科目数',
    key: 'subject_count',
    width: 90,
    sorter: (a, b) => (a.subject_count || 0) - (b.subject_count || 0),
    render: (row) => row.subject_count ?? '-',
  },
  {
    title: '学生数',
    key: 'student_count',
    width: 90,
    sorter: (a, b) => (a.student_count || 0) - (b.student_count || 0),
    render: (row) => row.student_count ?? '-',
  },
  {
    title: '考试日期',
    key: 'exam_date',
    width: 120,
    sorter: (a, b) => new Date(a.exam_date || 0) - new Date(b.exam_date || 0),
    render: (row) => row.exam_date ? new Date(row.exam_date).toLocaleDateString('zh-CN') : '-',
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 140,
    sorter: (a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0),
    defaultSortOrder: 'descend',
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    render: (row) => {
      const buttons = [
        h(NButton, {
          text: true,
          type: 'primary',
          size: 'small',
          onClick: () => router.push(`/exams/${row.id}`),
        }, { default: () => '详情' }),
        h(NButton, {
          text: true,
          type: 'info',
          size: 'small',
          onClick: () => router.push(`/analytics/${row.id}`),
        }, { default: () => '分析' }),
      ]

      // Archive button (only for completed exams)
      if (canManageExams.value && row.status === 'completed') {
        buttons.push(
          h(NPopconfirm, {
            onPositiveClick: () => handleArchive(row.id),
          }, {
            trigger: () => h(NButton, {
              text: true,
              type: 'warning',
              size: 'small',
            }, { default: () => '归档' }),
            default: () => '确认归档此考试？',
          })
        )
      }

      if (canManageExams.value && row.status === 'draft') {
        buttons.push(
          h(NPopconfirm, {
            onPositiveClick: () => handleDelete(row.id),
          }, {
            trigger: () => h(NButton, {
              text: true,
              type: 'error',
              size: 'small',
            }, { default: () => '删除' }),
            default: () => '确认删除此考试？删除后不可恢复。',
          })
        )
      }

      if (canManageExams.value) {
        buttons.push(
          h(NButton, {
            text: true,
            type: 'default',
            size: 'small',
            onClick: () => handleCopy(row),
          }, { default: () => '复制' })
        )
      }

      return h('div', {
        style: 'display: flex; gap: 8px;',
        onClick: (e) => e.stopPropagation(),
      }, buttons)
    },
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
  if (!canManageExams.value) return
  try {
    await createFormRef.value?.validate()
  } catch { return }
  creating.value = true
  try {
    const payload = {
      name: createForm.name,
      card_title: createForm.card_title,
    }
    if (createForm.exam_date) {
      payload.exam_date = new Date(createForm.exam_date).toISOString().split('T')[0]
    }
    if (createForm.description) {
      payload.description = createForm.description
    }
    await createExam(payload)
    message.success('考试创建成功')
    createForm.name = ''
    createForm.card_title = ''
    createForm.exam_date = null
    createForm.description = ''
    showCreate.value = false
    await loadExams()
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function handleArchive(examId) {
  if (!canManageExams.value) return
  try {
    await archiveExam(examId)
    message.success('考试已归档')
    await loadExams()
  } catch (e) {
    message.error(e.response?.data?.detail || '归档失败')
  }
}

async function handleDelete(examId) {
  if (!canManageExams.value) return
  try {
    await deleteExam(examId)
    message.success('考试已删除')
    await loadExams()
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
  }
}

function handleCopy(exam) {
  if (!canManageExams.value) return
  createForm.name = `${exam.name} (副本)`
  createForm.card_title = exam.card_title || ''
  createForm.exam_date = null
  createForm.description = exam.description || ''
  showCreate.value = true
}

onMounted(loadExams)
</script>

<style scoped>
.page-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-icon--yellow {
  background: var(--color-accent);
  color: var(--color-bg-deep);
}

.stat-icon--purple {
  background: var(--color-primary);
  color: #ffffff;
}

.stat-icon--orange {
  background: var(--color-warning);
  color: #ffffff;
}

.stat-icon--ink {
  background: var(--color-bg-deep);
  color: var(--color-accent);
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.empty-state {
  text-align: center;
  padding: 48px 24px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
