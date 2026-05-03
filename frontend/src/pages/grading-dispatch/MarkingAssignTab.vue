<template>
  <div>
    <template v-if="isManager">
      <div v-if="examId" class="stats-row">
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
          <div class="stat-value">{{ unassignedCount }}</div>
        </div>
      </div>

      <div v-if="examId" style="display: flex; gap: 24px;">
        <div style="flex: 2;">
          <div v-for="subj in subjects" :key="subj.id">
            <h3 style="margin: 16px 0 8px;">{{ subj.name }}</h3>
            <div v-for="q in (subj.questions || [])" :key="q.id" class="question-card">
              <div class="question-header">
                <span class="question-name">{{ q.name }}</span>
                <n-tag size="small" round>满分 {{ q.max_score }}</n-tag>
              </div>
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
                >分配</n-button>
              </div>
            </div>
          </div>
          <n-empty v-if="!subjects.length && examId" description="暂无科目数据" />
          <n-empty v-if="!examId" description="请先选择考试" />
        </div>

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

    <template v-else>
      <n-card title="我的阅卷任务" size="small">
        <n-data-table :columns="myColumns" :data="myAssignments" size="small" />
        <n-empty v-if="!myAssignments.length" description="暂无分配给您的阅卷任务" />
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { h, ref, reactive, computed, watch } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'
import client from '../../api/client'

const props = defineProps({
  examId: { type: [String, Number], default: null },
})

const auth = useAuthStore()
const message = useMessage()
const router = useRouter()
const isManager = computed(() => auth.isAdmin)

const subjects = ref([])
const teachers = ref([])
const assignments = ref([])
const myAssignments = ref([])
const newAssign = reactive({})

const teacherOptions = computed(() => teachers.value.map(t => ({
  label: `${t.display_name}${t.subject_code ? ` (${t.subject_code})` : ''}`,
  value: t.id,
})))

const allQuestions = computed(() => subjects.value.flatMap(s => s.questions || []))
const totalQuestionCount = computed(() => allQuestions.value.length)
const assignedQuestionCount = computed(() => {
  const assignedQids = new Set(assignments.value.map(a => a.question_id))
  return allQuestions.value.filter(q => assignedQids.has(q.id)).length
})
const unassignedCount = computed(() => totalQuestionCount.value - assignedQuestionCount.value)
const participatingTeacherCount = computed(() => new Set(assignments.value.map(a => a.teacher_id)).size)

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

async function loadData() {
  if (!props.examId) return
  try {
    const [subjRes, teacherRes, assignRes] = await Promise.all([
      client.get(`/marking/subjects?exam_id=${props.examId}`),
      client.get('/marking/teachers'),
      client.get(`/marking/assignments?exam_id=${props.examId}`),
    ])
    subjects.value = subjRes.data
    teachers.value = teacherRes.data
    assignments.value = assignRes.data
  } catch {}
}

async function handleAssign(questionId) {
  const teacherId = newAssign[questionId + '_teacher']
  if (!teacherId) return
  const answerCount = newAssign[questionId + '_count'] || 0
  try {
    await client.post('/marking/assign', {
      exam_id: props.examId,
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
  } catch {}
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

watch(() => props.examId, (val) => {
  if (val && isManager.value) loadData()
}, { immediate: true })

if (!isManager.value) loadMyAssignments()
</script>

<style scoped>
.stats-row {
  display: flex;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}
.stat-card { flex: 1; }
.question-card {
  background: var(--color-bg-card, rgba(255, 255, 255, 0.95));
  border: 1px solid rgba(255, 255, 255, 0.15);
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
.question-name { font-weight: var(--fw-semibold); font-size: var(--fs-base); }
.assign-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
}
.assign-detail { color: var(--color-text-muted); font-size: var(--fs-base); }
.add-teacher-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px dashed rgba(255, 255, 255, 0.1);
}
.teacher-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.text-muted { color: var(--color-text-muted); font-size: var(--fs-base); }
</style>
