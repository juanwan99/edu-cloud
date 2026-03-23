<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">AI 批改任务</h1>
        <p class="page-subtitle">管理 AI 自动批改任务</p>
      </div>
      <n-button type="primary" class="btn-pill" @click="showCreate = true">创建批改任务</n-button>
    </div>

    <n-spin :show="loading">
      <div class="task-cards">
        <div v-for="task in tasks" :key="task.id" class="task-card" @click="$router.push(`/grading/tasks/${task.id}`)">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <n-tag :type="taskStatusType(task.status)" round size="small">{{ taskStatusLabel(task.status) }}</n-tag>
            <span style="font-size: 13px; color: var(--color-text-muted);">
              {{ formatDate(task.created_at) }}
            </span>
          </div>
          <n-progress type="line" :percentage="taskPct(task)" :indicator-placement="'inside'" />
          <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 13px; color: var(--color-text-secondary);">
            <span>已完成 {{ task.completed }} / {{ task.total }}</span>
            <span v-if="task.failed > 0" style="color: #dc3545;">失败 {{ task.failed }}</span>
          </div>
        </div>
        <n-empty v-if="!loading && tasks.length === 0" description="暂无批改任务" />
      </div>
    </n-spin>

    <n-modal v-model:show="showCreate" preset="dialog" title="创建批改任务" positive-text="创建"
      negative-text="取消" :positive-button-props="{ class: 'btn-pill' }"
      :negative-button-props="{ class: 'btn-pill' }" @positive-click="handleCreate">
      <n-form label-placement="top">
        <n-form-item label="选择考试">
          <n-select v-model:value="createForm.examId" :options="examOptions" placeholder="选择考试"
            @update:value="onExamChange" />
        </n-form-item>
        <n-form-item label="选择科目">
          <n-select v-model:value="createForm.subjectId" :options="subjectOptions" placeholder="选择科目"
            :disabled="!createForm.examId" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { listExams } from '../api/exams'
import { listSubjects } from '../api/subjects'
import { listTasks, createTask } from '../api/grading'

const message = useMessage()
const loading = ref(true)
const tasks = ref([])
const showCreate = ref(false)

const examOptions = ref([])
const subjectOptions = ref([])
const createForm = reactive({ examId: null, subjectId: null })

const taskStatusMap = {
  pending: { label: '等待中', type: 'default' },
  processing: { label: '处理中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'error' },
}
const taskStatusLabel = (s) => taskStatusMap[s]?.label || s
const taskStatusType = (s) => taskStatusMap[s]?.type || 'default'
const taskPct = (t) => t.total > 0 ? Math.round((t.completed / t.total) * 100) : 0

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-CN')
}

async function loadTasks() {
  try {
    const { data } = await listTasks()
    tasks.value = data
  } catch { /* interceptor */ }
  loading.value = false
}

async function loadExams() {
  try {
    const { data } = await listExams()
    examOptions.value = data.map((e) => ({ label: e.name, value: e.id }))
  } catch { /* interceptor */ }
}

async function onExamChange(examId) {
  createForm.subjectId = null
  subjectOptions.value = []
  if (!examId) return
  try {
    const { data } = await listSubjects(examId)
    subjectOptions.value = data.map((s) => ({ label: `${s.name} (${s.code})`, value: s.id }))
  } catch { /* interceptor */ }
}

async function handleCreate() {
  if (!createForm.subjectId) { message.warning('请选择科目'); return false }
  try {
    const { data } = await createTask({ subject_id: createForm.subjectId })
    message.success('批改任务已创建')
    showCreate.value = false
    createForm.examId = null
    createForm.subjectId = null
    // 新任务直接加入列表
    tasks.value.unshift(data)
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
    return false
  }
}

onMounted(async () => {
  await Promise.all([loadTasks(), loadExams()])
})
</script>

<style scoped>
.task-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.task-card {
  background: white;
  padding: 24px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  cursor: pointer;
  transition: var(--transition);
}

.task-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

@media (max-width: 768px) {
  .task-cards { grid-template-columns: 1fr; }
}
</style>
