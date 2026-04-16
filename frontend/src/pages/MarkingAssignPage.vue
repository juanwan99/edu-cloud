<template>
  <div>
    <div class="page-header">
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

      <div v-if="selectedExamId" style="display: flex; gap: 24px;">
        <!-- 左侧：科目和题目 -->
        <div style="flex: 2;">
          <n-card title="题目列表" size="small">
            <div v-for="subj in subjects" :key="subj.id" style="margin-bottom: 16px;">
              <h4 style="margin: 0 0 8px;">{{ subj.name }}</h4>
              <div v-for="q in subj.questions" :key="q.id"
                   style="display: flex; align-items: center; gap: 12px; padding: 8px; border: 1px solid #f0f0f0; border-radius: 8px; margin-bottom: 6px;">
                <span style="min-width: 80px; font-weight: 500;">{{ q.name }}</span>
                <span style="color: #888; font-size: 12px;">{{ q.max_score }}分</span>
                <n-tag v-if="getAssignee(q.id)" size="small" type="success" round>
                  {{ getAssignee(q.id) }}
                </n-tag>
                <n-tag v-else size="small" type="default" round>未分配</n-tag>
                <n-select
                  :value="assignMap[q.id] || null"
                  :options="teacherOptions"
                  placeholder="分配给..."
                  size="small"
                  style="width: 160px; margin-left: auto;"
                  clearable
                  @update:value="(v) => handleAssign(q.id, v)"
                />
              </div>
            </div>
            <n-empty v-if="!subjects.length" description="请先选择考试" />
          </n-card>
        </div>

        <!-- 右侧：教师列表 -->
        <div style="flex: 1;">
          <n-card title="教师" size="small">
            <div v-for="t in teachers" :key="t.id"
                 style="display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px solid #f5f5f5;">
              <span style="font-weight: 500;">{{ t.display_name }}</span>
              <n-tag size="small" round>{{ t.role }}</n-tag>
              <span v-if="t.subject_code" style="color: #888; font-size: 12px;">{{ t.subject_code }}</span>
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
import { h, ref, computed, onMounted } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
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

const examOptions = computed(() => exams.value.map(e => ({ label: e.name, value: e.id })))
const teacherOptions = computed(() => teachers.value.map(t => ({
  label: `${t.display_name}${t.subject_code ? ` (${t.subject_code})` : ''}`,
  value: t.id,
})))

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
  } catch { /* interceptor */ }
}

async function loadData() {
  if (!selectedExamId.value) return
  try {
    // Load subjects with questions
    const { data: subjData } = await client.get(`/marking/subjects?exam_id=${selectedExamId.value}`)
    subjects.value = subjData

    // Load teachers list (admin/principal only endpoint)
    const { data: teacherData } = await client.get('/marking/teachers')
    teachers.value = teacherData

    // Load ALL assignments for this exam (admin view)
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
