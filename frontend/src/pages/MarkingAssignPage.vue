<template>
  <div>
    <div class="page-header">
      <n-button text style="margin-bottom: 8px;" @click="$router.push('/marking')">
        <template #icon><n-icon><ArrowLeft :size="16" /></n-icon></template>
        返回阅卷
      </n-button>
      <h1 class="page-title">阅卷任务分配</h1>
      <p class="page-subtitle">将题目分配给指定教师阅卷，支持一题多人</p>
    </div>

    <!-- 管理员/校长视图：分配面板 -->
    <template v-if="isManager">
      <div style="display: flex; gap: var(--space-4); margin-bottom: var(--space-4); align-items: center;">
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
        <div class="stat-card">
          <div class="stat-label">已分配题目</div>
          <div class="stat-value">{{ assignedQuestionCount }} / {{ totalQuestionCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">参与教师数</div>
          <div class="stat-value">{{ participatingTeacherCount }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">未分配题目</div>
          <div class="stat-value">
            {{ unassignedCount }}
            <n-tag v-if="unassignedCount > 0" size="tiny" type="warning" round>待处理</n-tag>
          </div>
        </div>
      </div>

      <div v-if="selectedExamId" style="display: flex; gap: 24px;">
        <!-- 左侧：按题分配卡片 -->
        <div style="flex: 2;">
          <div v-for="subj in subjects" :key="subj.id">
            <h3 style="margin: 16px 0 8px;">{{ subj.name }}</h3>
            <div v-for="q in (subj.questions || [])" :key="q.id" class="question-card">
              <div class="question-header">
                <span class="question-name">{{ q.name }}</span>
                <n-tag size="small" round>满分 {{ q.max_score }}</n-tag>
              </div>
              <!-- 已分配教师列表 -->
              <div v-for="assign in getAssignsForQuestion(q.id)" :key="assign.id" class="assign-row">
                <n-tag size="small" type="success" round>{{ getTeacherName(assign.teacher_id) }}</n-tag>
                <span class="assign-detail">
                  {{ assign.answer_count > 0 ? `${assign.graded_count}/${assign.answer_count} 份` : '不限' }}
                </span>
                <n-tag size="tiny" round :type="assign.status === 'completed' ? 'success' : assign.status === 'in_progress' ? 'warning' : 'default'">
                  {{ { pending: '待批改', in_progress: '进行中', completed: '已完成' }[assign.status] || assign.status }}
                </n-tag>
                <n-button text type="error" size="tiny" @click="removeAssign(assign.id)">删除</n-button>
              </div>
              <!-- 添加教师行 -->
              <div class="add-teacher-row">
                <n-select
                  v-model:value="newAssign[q.id + '_teacher']"
                  :options="teacherOptions"
                  placeholder="选择教师"
                  size="small"
                  style="width: 180px;"
                  clearable
                />
                <n-input-number
                  v-model:value="newAssign[q.id + '_count']"
                  placeholder="数量(0=不限)"
                  size="small"
                  :min="0"
                  style="width: 140px;"
                />
                <n-button
                  type="primary"
                  size="small"
                  :disabled="!newAssign[q.id + '_teacher']"
                  @click="handleAssign(q.id)"
                >
                  分配
                </n-button>
              </div>
            </div>
          </div>
          <n-empty v-if="!subjects.length" description="请先选择考试" />
        </div>

        <!-- 右侧：教师列表 -->
        <div style="flex: 1;">
          <n-card title="教师" size="small">
            <div v-for="t in teachers" :key="t.id" class="teacher-row">
              <span style="font-weight: 500;">{{ t.display_name }}</span>
              <n-tag :type="teacherWorkload[t.id] ? 'info' : 'default'" size="small" round>
                {{ teacherWorkload[t.id] || 0 }} 份
              </n-tag>
              <n-tag size="small" round>{{ t.role }}</n-tag>
              <span v-if="t.subject_code" class="text-muted">{{ t.subject_code }}</span>
            </div>
            <n-empty v-if="!teachers.length" description="无教师数据" />
          </n-card>
        </div>
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
import { h, ref, reactive, computed, onMounted } from 'vue'
import { NButton, NTag, NSelect, NIcon, useMessage } from 'naive-ui'
import { ArrowLeft } from 'lucide-vue-next'
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
const newAssign = reactive({})

const examOptions = computed(() => exams.value.map(e => ({ label: e.name, value: e.id })))
const teacherOptions = computed(() => teachers.value.map(t => ({
  label: `${t.display_name}${t.subject_code ? ` (${t.subject_code})` : ''}`,
  value: t.id,
})))

// --- 统计 computed ---
const allQuestions = computed(() => subjects.value.flatMap(s => s.questions || []))
const totalQuestionCount = computed(() => allQuestions.value.length)
const assignedQuestionCount = computed(() => {
  const assignedQids = new Set(assignments.value.map(a => a.question_id))
  return allQuestions.value.filter(q => assignedQids.has(q.id)).length
})
const unassignedCount = computed(() => totalQuestionCount.value - assignedQuestionCount.value)
const participatingTeacherCount = computed(() => {
  const ids = new Set(assignments.value.map(a => a.teacher_id))
  return ids.size
})

// --- 教师工作量 computed（基于 answer_count）---
const teacherWorkload = computed(() => {
  const counts = {}
  for (const a of assignments.value) {
    counts[a.teacher_id] = (counts[a.teacher_id] || 0) + (a.answer_count || 0)
  }
  return counts
})

function getAssignsForQuestion(qid) {
  return assignments.value.filter(a => a.question_id === qid)
}

function getTeacherName(tid) {
  const t = teachers.value.find(t => t.id === tid)
  return t ? t.display_name : tid
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
  } catch { /* interceptor */ }
}

async function handleAssign(questionId) {
  const teacherId = newAssign[questionId + '_teacher']
  if (!teacherId) return
  const answerCount = newAssign[questionId + '_count'] || 0
  try {
    await client.post('/marking/assign', {
      exam_id: selectedExamId.value,
      question_id: questionId,
      teacher_id: teacherId,
      answer_count: answerCount,
    })
    newAssign[questionId + '_teacher'] = null
    newAssign[questionId + '_count'] = null
    message.success('分配成功')
    await loadData()
  } catch (e) {
    message.error(e.response?.data?.detail || '分配失败')
  }
}

async function removeAssign(assignId) {
  try {
    await client.delete(`/marking/assignments/${assignId}`)
    message.success('已删除')
    await loadData()
  } catch (e) {
    message.error(e.response?.data?.detail || '删除失败')
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
  { title: '分配数量', key: 'answer_count', width: 100,
    render: (row) => row.answer_count > 0 ? `${row.answer_count}` : '不限',
  },
  { title: '已批改', key: 'graded_count', width: 80 },
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
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.stat-card {
  flex: 1;
}
.question-card {
  background: var(--color-bg-card, rgba(255, 255, 255, 0.95));
  border: 1px solid var(--color-border, rgba(0, 0, 0, 0.08));
  border-radius: var(--r-sm);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-3);
}
.question-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.question-name {
  font-weight: var(--fw-semibold);
  font-size: var(--fs-base);
}
.assign-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}
.assign-detail {
  color: var(--color-text-muted, rgba(0, 0, 0, 0.45));
  font-size: var(--fs-base);
}
.add-teacher-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed var(--color-border-light, rgba(0, 0, 0, 0.06));
}
.teacher-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border-light, rgba(0, 0, 0, 0.06));
}
.text-muted {
  color: var(--color-text-muted, rgba(0, 0, 0, 0.35));
  font-size: var(--fs-base);
}
</style>
