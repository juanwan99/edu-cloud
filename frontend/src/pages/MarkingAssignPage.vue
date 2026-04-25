<template>
  <div>
    <div class="page-header">
      <n-button text style="margin-bottom: 8px;" @click="$router.push('/marking')">← 返回阅卷</n-button>
      <h1 class="page-title">阅卷任务分配</h1>
      <p class="page-subtitle">将题目分配给指定教师阅卷</p>
    </div>

    <!-- 管理员/校长视图：分配面板 -->
    <template v-if="isManager">
      <div style="display: flex; gap: 16px; margin-bottom: 16px; align-items: center;">
        <n-select
          v-model:value="selectedExamId"
          :options="examOptions"
          placeholder="选择考试"
          style="width: 280px;"
          @update:value="loadData"
        />
      </div>

      <!-- 统计卡片区 -->
      <div v-if="selectedExamId" class="stats-row">
        <n-card size="small" class="stat-card">
          <n-statistic label="已分配题目">
            <template #default>
              {{ assignedCount }} / {{ totalQuestionCount }}
            </template>
          </n-statistic>
        </n-card>
        <n-card size="small" class="stat-card">
          <n-statistic label="参与教师数" :value="participatingTeacherCount" />
        </n-card>
        <n-card size="small" class="stat-card">
          <n-statistic label="未分配题目" :value="unassignedCount">
            <template #suffix>
              <n-tag v-if="unassignedCount > 0" size="tiny" type="warning" round>待处理</n-tag>
            </template>
          </n-statistic>
        </n-card>
      </div>

      <div v-if="selectedExamId" style="display: flex; gap: 24px;">
        <!-- 左侧：题目表格 -->
        <div style="flex: 2;">
          <n-card title="题目列表" size="small">
            <n-data-table
              v-if="tableData.length"
              :columns="questionColumns"
              :data="tableData"
              :row-key="(row) => row.questionId"
              size="small"
              :checked-row-keys="checkedKeys"
              @update:checked-row-keys="handleCheck"
            />
            <n-empty v-else description="请先选择考试" />
          </n-card>
        </div>

        <!-- 右侧：教师列表 -->
        <div style="flex: 1;">
          <n-card title="教师" size="small">
            <div v-for="t in teachers" :key="t.id" class="teacher-row">
              <span style="font-weight: 500;">{{ t.display_name }}</span>
              <n-tag :type="teacherWorkload[t.id] ? 'info' : 'default'" size="small" round>
                {{ teacherWorkload[t.id] || 0 }} 题
              </n-tag>
              <n-tag size="small" round>{{ t.role }}</n-tag>
              <span v-if="t.subject_code" class="text-muted">{{ t.subject_code }}</span>
            </div>
            <n-empty v-if="!teachers.length" description="无教师数据" />
          </n-card>
        </div>
      </div>

      <!-- 批量操作浮动栏 -->
      <div v-if="checkedKeys.length > 0" class="batch-bar">
        <span>已选中 {{ checkedKeys.length }} 题</span>
        <n-select
          v-model:value="batchTeacherId"
          :options="teacherOptions"
          placeholder="选择教师"
          size="small"
          style="width: 200px;"
          clearable
        />
        <n-button
          type="primary"
          size="small"
          :loading="batchLoading"
          :disabled="!batchTeacherId"
          @click="handleBatchAssign"
        >
          批量分配
        </n-button>
      </div>
    </template>

    <!-- 教师视图：我的任务 -->
    <template v-else>
      <n-card title="我的阅卷任务" size="small">
        <n-data-table :columns="myColumns" :data="myAssignments" size="small" />
        <n-empty v-if="!myAssignments.length" description="暂无分配给您的阅卷任务" />
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { NButton, NTag, NSelect, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import client from '../api/client'

const auth = useAuthStore()
const message = useMessage()
const router = useRouter()
const isManager = computed(() => auth.isAdmin)

const selectedExamId = ref(null)
const exams = ref([])
const subjects = ref([])
const teachers = ref([])
const assignments = ref([])
const myAssignments = ref([])
const assignMap = ref({})  // questionId → teacherId
const checkedKeys = ref([])
const batchTeacherId = ref(null)
const batchLoading = ref(false)

const examOptions = computed(() => exams.value.map(e => ({ label: e.name, value: e.id })))
const teacherOptions = computed(() => teachers.value.map(t => ({
  label: `${t.display_name}${t.subject_code ? ` (${t.subject_code})` : ''}`,
  value: t.id,
})))

// --- 统计 computed ---
const allQuestions = computed(() => subjects.value.flatMap(s => s.questions || []))
const totalQuestionCount = computed(() => allQuestions.value.length)
const assignedCount = computed(() => allQuestions.value.filter(q => assignMap.value[q.id]).length)
const unassignedCount = computed(() => totalQuestionCount.value - assignedCount.value)
const participatingTeacherCount = computed(() => {
  const ids = new Set(Object.values(assignMap.value).filter(Boolean))
  return ids.size
})

// --- 教师工作量 computed ---
const teacherWorkload = computed(() => {
  const counts = {}
  for (const tid of Object.values(assignMap.value)) {
    if (tid) counts[tid] = (counts[tid] || 0) + 1
  }
  return counts
})

// --- NDataTable 数据 ---
const tableData = computed(() => {
  const rows = []
  for (const subj of subjects.value) {
    for (const q of (subj.questions || [])) {
      rows.push({
        questionId: q.id,
        questionName: q.name,
        maxScore: q.max_score,
        subjectName: subj.name,
        assignee: getAssignee(q.id),
        assignedTeacherId: assignMap.value[q.id] || null,
      })
    }
  }
  return rows
})

const questionColumns = computed(() => [
  { type: 'selection' },
  { title: '题号', key: 'questionName', width: 120, sorter: 'default' },
  { title: '满分', key: 'maxScore', width: 80, sorter: (a, b) => a.maxScore - b.maxScore },
  { title: '科目', key: 'subjectName', width: 120, sorter: 'default' },
  {
    title: '当前分配教师',
    key: 'assignee',
    width: 140,
    render: (row) => row.assignee
      ? h(NTag, { size: 'small', type: 'success', round: true }, { default: () => row.assignee })
      : h(NTag, { size: 'small', type: 'default', round: true }, { default: () => '未分配' }),
  },
  {
    title: '分配操作',
    key: 'action',
    width: 180,
    render: (row) => h(NSelect, {
      value: row.assignedTeacherId,
      options: teacherOptions.value,
      placeholder: '分配给...',
      size: 'small',
      clearable: true,
      style: 'width: 160px;',
      onUpdateValue: (v) => handleAssign(row.questionId, v),
    }),
  },
])

function handleCheck(keys) {
  checkedKeys.value = keys
}

function getAssignee(questionId) {
  const tid = assignMap.value[questionId]
  if (!tid) return null
  const t = teachers.value.find(t => t.id === tid)
  return t ? t.display_name : null
}

async function loadExams() {
  try {
    const { data } = await client.get('/exams')
    exams.value = data
    if (data.length > 0 && !selectedExamId.value) {
      selectedExamId.value = data[0].id
      await loadData()
    }
  } catch { /* interceptor */ }
}

async function loadData() {
  if (!selectedExamId.value) return
  try {
    const { data: subjData } = await client.get(`/marking/subjects?exam_id=${selectedExamId.value}`)
    subjects.value = subjData

    const { data: teacherData } = await client.get('/marking/teachers')
    teachers.value = teacherData

    const { data: assignData } = await client.get(`/marking/assignments?exam_id=${selectedExamId.value}`)
    assignments.value = assignData
    assignMap.value = {}
    for (const a of assignData) {
      assignMap.value[a.question_id] = a.teacher_id
    }
  } catch { /* interceptor */ }
}

async function handleAssign(questionId, teacherId) {
  if (!teacherId) return
  try {
    await client.post('/marking/assign', {
      exam_id: selectedExamId.value,
      question_id: questionId,
      teacher_id: teacherId,
    })
    assignMap.value[questionId] = teacherId
    message.success('分配成功')
  } catch (e) {
    message.error(e.response?.data?.detail || '分配失败')
  }
}

async function handleBatchAssign() {
  if (!batchTeacherId.value || checkedKeys.value.length === 0) return
  batchLoading.value = true
  try {
    const results = await Promise.all(
      checkedKeys.value.map(questionId =>
        client.post('/marking/assign', {
          exam_id: selectedExamId.value,
          question_id: questionId,
          teacher_id: batchTeacherId.value,
        }).then(() => {
          assignMap.value[questionId] = batchTeacherId.value
          return { questionId, ok: true }
        }).catch(() => ({ questionId, ok: false }))
      )
    )
    const success = results.filter(r => r.ok).length
    const fail = results.filter(r => !r.ok).length
    if (fail === 0) {
      message.success(`批量分配成功：${success} 题`)
    } else {
      message.warning(`${success} 题成功，${fail} 题失败`)
    }
    checkedKeys.value = []
    batchTeacherId.value = null
  } catch (e) {
    message.error('批量分配失败')
  } finally {
    batchLoading.value = false
  }
}

async function loadMyAssignments() {
  try {
    const { data } = await client.get('/marking/my-assignments')
    myAssignments.value = data
  } catch { /* interceptor */ }
}

const myColumns = [
  { title: '题目', key: 'question_id', width: 200 },
  { title: '状态', key: 'status', width: 100,
    render: (row) => h(NTag, { size: 'small', round: true,
      type: row.status === 'completed' ? 'success' : row.status === 'in_progress' ? 'warning' : 'default' },
      { default: () => ({ pending: '待批改', in_progress: '进行中', completed: '已完成' }[row.status] || row.status) }),
  },
  { title: '操作', key: 'actions', width: 100,
    render: (row) => row.status !== 'completed'
      ? h(NButton, { size: 'small', type: 'primary', text: true,
          onClick: () => router.push(`/marking/grade/${row.question_id}`) },
          { default: () => '去阅卷' })
      : null,
  },
]

onMounted(async () => {
  if (isManager.value) {
    await loadExams()
  } else {
    await loadMyAssignments()
  }
})
</script>

<style scoped>
.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  flex: 1;
}
.teacher-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border-light, rgba(0, 0, 0, 0.06));
}
.text-muted {
  color: var(--color-text-muted, rgba(0, 0, 0, 0.35));
  font-size: 12px;
}
.batch-bar {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  background: var(--color-bg-card, rgba(255, 255, 255, 0.95));
  border: 1px solid var(--color-border, rgba(0, 0, 0, 0.08));
  border-radius: var(--radius-lg, 20px);
  box-shadow: var(--shadow-lg, 0 12px 32px rgba(26, 46, 31, 0.08));
  z-index: 100;
}
</style>
