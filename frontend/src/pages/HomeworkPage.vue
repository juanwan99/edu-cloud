<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">作业管理</h1>
        <p class="page-subtitle">布置、发布、批改作业</p>
      </div>
      <n-space v-if="canManageHomework">
        <n-button type="primary" @click="showCreate = true">布置作业</n-button>
        <n-button type="warning" @click="showRemedial = true">考后推送</n-button>
      </n-space>
    </div>

    <!-- 筛选栏 -->
    <n-space style="margin-bottom: 16px;">
      <n-select v-model:value="filterStatus" :options="statusOptions" placeholder="状态" clearable style="width: 120px;" @update:value="loadTasks" />
      <n-select v-model:value="filterSubject" :options="subjectOptions" placeholder="科目" clearable style="width: 120px;" @update:value="loadTasks" />
      <n-select v-model:value="filterClass" :options="classOptions" placeholder="班级" clearable style="width: 160px;" @update:value="loadTasks" />
    </n-space>

    <n-spin :show="loading">
      <n-data-table :columns="columns" :data="tasks" :bordered="false" size="small" :pagination="{ pageSize: 20 }" />
    </n-spin>

    <!-- 新建作业弹窗 -->
    <n-modal v-model:show="showCreate" preset="dialog" title="布置作业" positive-text="创建" negative-text="取消"
      @positive-click="handleCreate" style="width: 520px;">
      <n-form :model="form" label-placement="left" label-width="70">
        <n-form-item label="标题">
          <n-input v-model:value="form.title" placeholder="作业标题" />
        </n-form-item>
        <n-form-item label="科目">
          <n-select v-model:value="form.subject_code" :options="subjectOptions" placeholder="选择科目" />
        </n-form-item>
        <n-form-item label="班级">
          <n-select v-model:value="form.class_id" :options="classOptions" placeholder="选择班级" />
        </n-form-item>
        <n-form-item label="类型">
          <n-radio-group v-model:value="form.task_type">
            <n-radio value="regular">常规作业</n-radio>
            <n-radio value="pre_exam">考前练习</n-radio>
            <n-radio value="post_exam">考后巩固</n-radio>
          </n-radio-group>
        </n-form-item>
        <n-form-item label="截止时间">
          <n-date-picker v-model:value="form.deadline_ts" type="datetime" style="width: 100%;" />
        </n-form-item>
        <n-form-item label="内容">
          <n-input v-model:value="form.content" type="textarea" :rows="4" placeholder="作业内容描述" />
        </n-form-item>
      </n-form>
    </n-modal>

    <!-- 提交列表/批改弹窗 -->
    <n-modal v-model:show="showSubmissions" preset="card" title="提交情况" style="width: 700px;">
      <div v-if="taskStats" style="margin-bottom: 16px;">
        <n-space>
          <n-tag type="info">总计 {{ taskStats.total }}</n-tag>
          <n-tag type="warning">待提交 {{ taskStats.pending }}</n-tag>
          <n-tag type="success">已提交 {{ taskStats.submitted }}</n-tag>
          <n-tag>已批改 {{ taskStats.graded }}</n-tag>
          <n-tag v-if="taskStats.avg_score != null" type="primary">均分 {{ taskStats.avg_score }}</n-tag>
        </n-space>
      </div>
      <n-data-table :columns="subColumns" :data="submissions" :bordered="false" size="small" :pagination="{ pageSize: 30 }" />
    </n-modal>

    <!-- 考后推送弹窗 -->
    <n-modal v-model:show="showRemedial" preset="dialog" title="考后推送" positive-text="创建补救作业" negative-text="取消"
      @positive-click="handleCreateRemedial" style="width: 520px;">
      <n-form label-placement="left" label-width="70">
        <n-form-item label="选择考试">
          <n-select v-model:value="remedialForm.exam_id" :options="examOptions" placeholder="选择考试" filterable
            @update:value="handleExamSelect" />
        </n-form-item>
        <n-form-item label="选择班级">
          <n-select v-model:value="remedialForm.class_id" :options="classOptions" placeholder="选择班级" />
        </n-form-item>
        <div v-if="remedialPreview" style="margin-top: 8px; padding: 12px; background: rgba(255,255,255,0.04); border-radius: 6px;">
          <p style="margin: 0 0 8px; font-weight: 500;">预览：将推送 {{ remedialPreview.high_error_count }} 道高错题相关练习</p>
          <n-tag v-if="remedialPreview.high_error_count === 0" type="info" size="small">该考试无高错题，将创建空内容作业</n-tag>
        </div>
      </n-form>
    </n-modal>

    <!-- 关联题目详情弹窗 -->
    <n-modal v-model:show="showContentDetail" preset="card" title="关联题目" style="width: 700px;">
      <n-empty v-if="!contentDetailQuestions.length" description="暂无关联题目" />
      <n-list v-else bordered>
        <n-list-item v-for="q in contentDetailQuestions" :key="q.id">
          <n-thing>
            <template #header>
              <n-space align="center" size="small">
                <n-tag :type="q.question_type === 'choice' ? 'info' : q.question_type === 'fill' ? 'warning' : 'success'" size="small">
                  {{ { choice: '选择', fill: '填空', essay: '解答' }[q.question_type] || q.question_type }}
                </n-tag>
                <span>满分 {{ q.max_score }}</span>
                <n-tag v-if="q.difficulty != null" size="small">难度 {{ q.difficulty }}</n-tag>
              </n-space>
            </template>
            <template #description>{{ q.content_text || '(无题干)' }}</template>
          </n-thing>
        </n-list-item>
      </n-list>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, computed, onMounted } from 'vue'
import { NButton, NTag, NSpace, NInputNumber, useMessage, useDialog } from 'naive-ui'
import { listTasks, createTask, publishTask, closeTask, deleteTask, listSubmissions, gradeSingle, createFromExam, getContentDetail } from '../api/homework.js'
import { listClasses } from '../api/students.js'
import { listExams } from '../api/exams.js'
import { useAuthStore } from '../stores/auth.js'
import { normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'

const auth = useAuthStore()
const normalizedRole = computed(() => normalizeRole(auth.currentRole?.role || ''))
const canManageHomework = computed(() => hasPermission(normalizedRole.value, 'manage_homework'))
const message = useMessage()
const dialog = useDialog()
const loading = ref(false)
const tasks = ref([])
const classes = ref([])

const showCreate = ref(false)
const showSubmissions = ref(false)
const showRemedial = ref(false)
const showContentDetail = ref(false)
const submissions = ref([])
const taskStats = ref(null)
const currentTaskId = ref(null)
const exams = ref([])
const remedialForm = ref({ exam_id: null, class_id: null })
const remedialPreview = ref(null)
const contentDetailQuestions = ref([])

const filterStatus = ref(null)
const filterSubject = ref(null)
const filterClass = ref(null)

const form = ref({ title: '', subject_code: '', class_id: '', task_type: 'regular', deadline_ts: null, content: '' })

const SUBJECTS = [
  { value: 'YW', label: '语文' }, { value: 'SX', label: '数学' }, { value: 'YY', label: '英语' },
  { value: 'WL', label: '物理' }, { value: 'HX', label: '化学' }, { value: 'SW', label: '生物' },
  { value: 'ZZ', label: '政治' }, { value: 'LS', label: '历史' }, { value: 'DL', label: '地理' },
]
const subjectOptions = SUBJECTS
const statusOptions = [
  { value: 'draft', label: '草稿' }, { value: 'active', label: '进行中' },
  { value: 'expired', label: '已截止' }, { value: 'closed', label: '已关闭' },
]

const classOptions = computed(() => classes.value.map(c => ({ value: c.id, label: c.name })))

const statusColor = { draft: 'default', active: 'success', expired: 'warning', closed: 'error' }
const statusLabel = { draft: '草稿', active: '进行中', expired: '已截止', closed: '已关闭' }
const typeLabel = { regular: '常规', pre_exam: '考前', post_exam: '考后', remedial: '补救' }
const examOptions = computed(() => exams.value.map(e => ({ value: e.id, label: e.name })))

const columns = [
  { title: '标题', key: 'title', ellipsis: { tooltip: true } },
  { title: '科目', key: 'subject_code', width: 70 },
  { title: '类型', key: 'task_type', width: 70, render: (row) => typeLabel[row.task_type] || row.task_type },
  { title: '状态', key: 'status', width: 90,
    render: (row) => h(NTag, { type: statusColor[row.status], size: 'small' }, { default: () => statusLabel[row.status] || row.status }),
  },
  { title: '班级', key: 'class_name', width: 100 },
  { title: '截止', key: 'deadline', width: 140, render: (row) => row.deadline?.slice(0, 16)?.replace('T', ' ') || '-' },
  { title: '创建', key: 'created_at', width: 100, render: (row) => row.created_at?.slice(0, 10) || '' },
  {
    title: '操作', key: 'actions', width: 200,
    render: (row) => h(NSpace, { size: 4 }, { default: () => [
      h(NButton, { text: true, type: 'info', size: 'small', onClick: () => openSubmissions(row) }, { default: () => '详情' }),
      (row.task_type === 'remedial' || row.task_type === 'post_exam') ? h(NButton, { text: true, type: 'info', size: 'small', onClick: () => openContentDetail(row) }, { default: () => '题目' }) : null,
      canManageHomework.value && row.status === 'draft' ? h(NButton, { text: true, type: 'success', size: 'small', onClick: () => handlePublish(row) }, { default: () => '发布' }) : null,
      canManageHomework.value && row.status === 'active' ? h(NButton, { text: true, type: 'warning', size: 'small', onClick: () => handleClose(row) }, { default: () => '关闭' }) : null,
      canManageHomework.value && row.status === 'draft' ? h(NButton, { text: true, type: 'error', size: 'small', onClick: () => handleDelete(row) }, { default: () => '删除' }) : null,
    ].filter(Boolean) }),
  },
]

const subColumns = [
  { title: '学生', key: 'student_id', width: 120, ellipsis: true },
  { title: '状态', key: 'status', width: 90,
    render: (row) => {
      const map = { pending: ['warning', '待提交'], submitted: ['info', '已提交'], graded: ['success', '已批改'] }
      const [type, label] = map[row.status] || ['default', row.status]
      return h(NTag, { type, size: 'small' }, { default: () => label })
    },
  },
  { title: '提交时间', key: 'submit_time', width: 140, render: (row) => row.submit_time?.slice(0, 16)?.replace('T', ' ') || '-' },
  { title: '分数', key: 'score', width: 80, render: (row) => row.score != null ? row.score : '-' },
  { title: '反馈', key: 'feedback', ellipsis: { tooltip: true } },
]

async function loadTasks() {
  loading.value = true
  try {
    const params = {}
    if (filterStatus.value) params.status = filterStatus.value
    if (filterSubject.value) params.subject_code = filterSubject.value
    if (filterClass.value) params.class_id = filterClass.value
    const { data } = await listTasks(params)
    const items = Array.isArray(data) ? data : (data?.items || [])
    const classMap = Object.fromEntries(classes.value.map(c => [c.id, c.name]))
    tasks.value = items.map(t => ({ ...t, class_name: classMap[t.class_id] || t.class_id?.slice(0, 8) || '-' }))
  } catch { message.error('加载作业失败') }
  loading.value = false
}

async function handleCreate() {
  if (!canManageHomework.value) return
  if (!form.value.title || !form.value.subject_code) { message.warning('请填写标题和科目'); return }
  try {
    const payload = { ...form.value }
    if (payload.deadline_ts) payload.deadline = new Date(payload.deadline_ts).toISOString()
    delete payload.deadline_ts
    await createTask(payload)
    message.success('作业创建成功')
    showCreate.value = false
    form.value = { title: '', subject_code: '', class_id: '', task_type: 'regular', deadline_ts: null, content: '' }
    await loadTasks()
  } catch (e) { message.error(e.response?.data?.detail || '创建失败') }
}

async function handlePublish(row) {
  if (!canManageHomework.value) return
  try {
    await publishTask(row.id)
    message.success('作业已发布')
    await loadTasks()
  } catch (e) { message.error(e.response?.data?.detail || '发布失败') }
}

async function handleClose(row) {
  if (!canManageHomework.value) return
  try {
    await closeTask(row.id)
    message.success('作业已关闭')
    await loadTasks()
  } catch (e) { message.error(e.response?.data?.detail || '关闭失败') }
}

async function handleDelete(row) {
  if (!canManageHomework.value) return
  dialog.warning({
    title: '确认删除', content: `确定删除「${row.title}」？`,
    positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      try { await deleteTask(row.id); message.success('已删除'); await loadTasks() }
      catch (e) { message.error(e.response?.data?.detail || '删除失败') }
    },
  })
}

async function openSubmissions(row) {
  currentTaskId.value = row.id
  showSubmissions.value = true
  try {
    const { data } = await listSubmissions(row.id)
    submissions.value = Array.isArray(data) ? data : (data?.items || [])
    taskStats.value = { total: submissions.value.length,
      pending: submissions.value.filter(s => s.status === 'pending').length,
      submitted: submissions.value.filter(s => s.status === 'submitted').length,
      graded: submissions.value.filter(s => s.status === 'graded').length,
      avg_score: (() => { const scored = submissions.value.filter(s => s.score != null); return scored.length ? Math.round(scored.reduce((a, s) => a + s.score, 0) / scored.length * 10) / 10 : null })(),
    }
  } catch { message.error('加载提交列表失败') }
}

async function handleExamSelect() {
  // 简单预览：选择考试后显示提示
  if (remedialForm.value.exam_id) {
    remedialPreview.value = { high_error_count: '?' }
  } else {
    remedialPreview.value = null
  }
}

async function handleCreateRemedial() {
  if (!canManageHomework.value) return
  if (!remedialForm.value.exam_id || !remedialForm.value.class_id) {
    message.warning('请选择考试和班级')
    return
  }
  try {
    await createFromExam(remedialForm.value.exam_id, remedialForm.value.class_id)
    message.success('补救作业创建成功')
    showRemedial.value = false
    remedialForm.value = { exam_id: null, class_id: null }
    remedialPreview.value = null
    await loadTasks()
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
  }
}

async function openContentDetail(row) {
  showContentDetail.value = true
  contentDetailQuestions.value = []
  try {
    const { data } = await getContentDetail(row.id)
    contentDetailQuestions.value = data.questions || []
  } catch {
    message.error('加载题目详情失败')
  }
}

async function init() {
  const [classesRes, examsRes] = await Promise.all([
    listClasses().catch(() => ({ data: [] })),
    listExams().catch(() => ({ data: [] })),
  ])
  classes.value = Array.isArray(classesRes.data) ? classesRes.data : (classesRes.data?.items || [])
  exams.value = Array.isArray(examsRes.data) ? examsRes.data : (examsRes.data?.items || [])
  await loadTasks()
}

onMounted(init)
</script>
