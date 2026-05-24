<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">排课管理</h1>
        <p class="page-subtitle">管理教师排课信息，查看工作量统计</p>
      </div>
      <n-button v-if="canManageScheduling" type="primary" class="btn-pill" @click="openCreate">新增排课</n-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">总排课数</div>
        <div class="stat-value">{{ summaryStats.totalAssignments }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已排课教师</div>
        <div class="stat-value">{{ summaryStats.teacherCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均课时</div>
        <div class="stat-value">{{ summaryStats.avgLoad }}</div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap;">
      <n-select
        v-model:value="filterSemester"
        :options="semesterOptions"
        placeholder="选择学期"
        clearable
        style="width: 220px;"
        @update:value="loadData"
      />
      <n-select
        v-model:value="filterTeacherId"
        :options="teacherFilterOptions"
        placeholder="按教师筛选"
        filterable
        clearable
        style="width: 200px;"
        @update:value="loadData"
      />
      <n-select
        v-model:value="filterSubjectCode"
        :options="allSubjectOptions"
        placeholder="按科目筛选"
        clearable
        style="width: 160px;"
        @update:value="loadData"
      />
    </div>

    <!-- 排课列表 -->
    <n-data-table
      :columns="columns"
      :data="rows"
      :loading="loading"
      :pagination="{ pageSize: 20 }"
    />

    <!-- 新增排课弹窗 -->
    <n-modal v-model:show="showCreate" preset="card" title="新增排课" style="width: 520px;">
      <n-form :model="form" label-placement="top">
        <n-form-item label="学期" required>
          <n-select
            v-model:value="form.semester"
            :options="semesterOptions"
            placeholder="选择学期"
          />
        </n-form-item>
        <n-form-item label="教师" required>
          <n-select
            v-model:value="form.user_id"
            :options="teacherSelectOptions"
            placeholder="搜索并选择教师"
            filterable
            @update:value="handleTeacherChange"
          />
        </n-form-item>
        <n-form-item label="科目" required>
          <n-select
            v-model:value="form.subject_code"
            :options="teacherSubjectOptions"
            placeholder="选择科目"
            :disabled="!form.user_id"
          />
        </n-form-item>
        <n-form-item label="班级" required>
          <n-select
            v-model:value="form.class_ids"
            :options="classSelectOptions"
            placeholder="选择班级（可多选）"
            multiple
            filterable
          />
        </n-form-item>
      </n-form>
      <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px;">
        <n-button class="btn-pill" @click="showCreate = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="saving" @click="handleCreate">确认创建</n-button>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue'
import { NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'
import { getAssignments, createAssignments, deleteAssignment, getAssignmentSummary } from '../api/teacherAssignments.js'
import { listTeachers } from '../api/teachers.js'
import { listClasses } from '../api/students.js'
import { listSemesters, getCurrentSemester } from '../api/academic.js'

const SUBJECTS = [
  { code: 'YW', label: '语文' }, { code: 'SX', label: '数学' }, { code: 'YY', label: '英语' },
  { code: 'WL', label: '物理' }, { code: 'HX', label: '化学' }, { code: 'SW', label: '生物' },
  { code: 'ZZ', label: '政治' }, { code: 'LS', label: '历史' }, { code: 'DL', label: '地理' },
  { code: 'TY', label: '体育' }, { code: 'YL', label: '音乐' }, { code: 'MS', label: '美术' },
  { code: 'XX', label: '信息' }, { code: 'TJ', label: '通技' },
]

const SUBJECT_MAP = Object.fromEntries(SUBJECTS.map(s => [s.code, s.label]))

const allSubjectOptions = SUBJECTS.map(s => ({ value: s.code, label: `${s.label} (${s.code})` }))

function subjectLabel(code) {
  return SUBJECT_MAP[code] || code
}

const auth = useAuthStore()
const normalizedRole = computed(() => normalizeRole(auth.currentRole?.role || ''))
const canManageScheduling = computed(() => hasPermission(normalizedRole.value, 'manage_scheduling'))
const message = useMessage()
const rows = ref([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)

// Reference data
const teachers = ref([])
const classes = ref([])
const semesters = ref([])
const currentSemesterId = ref(null)

// Filters
const filterSemester = ref(null)
const filterTeacherId = ref(null)
const filterSubjectCode = ref(null)

// Create form
const form = ref({
  user_id: null,
  subject_code: null,
  semester: null,
  class_ids: [],
})

// Summary
const summaryStats = ref({ totalAssignments: 0, teacherCount: 0, avgLoad: 0 })

const schoolId = () => auth.currentRole?.school_id

// Teacher name lookup
const teacherMap = computed(() => {
  const map = {}
  teachers.value.forEach(t => { map[t.id] = t.display_name || t.username })
  return map
})

// Class name lookup
const classMap = computed(() => {
  const map = {}
  classes.value.forEach(c => { map[c.id] = c.name })
  return map
})

// Semester lookup
const semesterOptions = computed(() =>
  semesters.value.map(s => ({
    value: s.semester || s.name,
    label: s.name || s.semester,
  }))
)

// Teacher select options (for create form)
const teacherSelectOptions = computed(() =>
  teachers.value.map(t => ({
    value: t.id,
    label: `${t.display_name || t.username}${t.subject_codes?.length ? ' (' + t.subject_codes.map(c => subjectLabel(c)).join('/') + ')' : ''}`,
  }))
)

// Teacher filter options (for filter bar, same as select but simpler label)
const teacherFilterOptions = computed(() =>
  teachers.value.map(t => ({
    value: t.id,
    label: t.display_name || t.username,
  }))
)

// Class select options (for create form)
const classSelectOptions = computed(() =>
  classes.value
    .slice()
    .sort((a, b) => {
      if (a.grade !== b.grade) return (a.grade || '').localeCompare(b.grade || '')
      return (a.name || '').localeCompare(b.name || '')
    })
    .map(c => ({
      value: c.id,
      label: c.grade ? `${c.grade} - ${c.name}` : c.name,
    }))
)

// Subject options filtered by selected teacher's subject_codes
const selectedTeacher = computed(() =>
  teachers.value.find(t => t.id === form.value.user_id) || null
)

const teacherSubjectOptions = computed(() => {
  const t = selectedTeacher.value
  if (t?.subject_codes?.length) {
    return t.subject_codes.map(code => ({
      value: code,
      label: `${subjectLabel(code)} (${code})`,
    }))
  }
  // Fallback: show all subjects
  return allSubjectOptions
})

// Table columns
const columns = [
  {
    title: '教师',
    key: 'user_id',
    width: 120,
    render(row) {
      return teacherMap.value[row.user_id] || row.user_id?.slice(0, 8) || '-'
    },
  },
  {
    title: '科目',
    key: 'subject_code',
    width: 100,
    render(row) {
      return subjectLabel(row.subject_code)
    },
  },
  {
    title: '班级',
    key: 'class_id',
    width: 160,
    render(row) {
      return classMap.value[row.class_id] || row.class_id?.slice(0, 8) || '-'
    },
  },
  { title: '学期', key: 'semester', width: 140 },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render(row) {
      if (!canManageScheduling.value) return null
      return h(NButton, {
        size: 'small',
        type: 'error',
        onClick: () => handleDelete(row.id),
      }, () => '删除')
    },
  },
]

// Load reference data
async function loadRefData() {
  const sid = schoolId()
  if (!sid) return

  const promises = [
    listTeachers().then(r => { teachers.value = r.data || [] }).catch(() => {}),
    listClasses().then(r => { classes.value = r.data || [] }).catch(() => {}),
    listSemesters().then(r => { semesters.value = r.data || [] }).catch(() => {}),
  ]

  // Get current semester for default selection
  promises.push(
    getCurrentSemester()
      .then(r => {
        if (r.data) {
          currentSemesterId.value = r.data.semester || r.data.name
          if (!filterSemester.value) {
            filterSemester.value = currentSemesterId.value
          }
        }
      })
      .catch(() => {})
  )

  await Promise.all(promises)
}

// Load assignments
async function loadData() {
  const sid = schoolId()
  if (!sid) return
  loading.value = true
  try {
    const params = {}
    if (filterSemester.value) params.semester = filterSemester.value
    if (filterTeacherId.value) params.user_id = filterTeacherId.value
    if (filterSubjectCode.value) params.subject_code = filterSubjectCode.value
    const { data } = await getAssignments(sid, params)
    rows.value = data || []
  } catch {
    message.error('加载排课数据失败')
    rows.value = []
  }
  loading.value = false
}

// Load summary stats
async function loadSummary() {
  const sid = schoolId()
  if (!sid) return
  try {
    const params = {}
    if (filterSemester.value) params.semester = filterSemester.value
    const { data } = await getAssignmentSummary(sid, params)
    if (Array.isArray(data)) {
      summaryStats.value = {
        totalAssignments: data.reduce((sum, t) => sum + (t.assignment_count || 0), 0),
        teacherCount: data.length,
        avgLoad: data.length > 0
          ? Math.round(data.reduce((sum, t) => sum + (t.assignment_count || 0), 0) / data.length * 10) / 10
          : 0,
      }
    }
  } catch {
    // Summary is non-critical, silently fall back
  }
}

// Create assignment
async function handleCreate() {
  if (!canManageScheduling.value) return
  if (!form.value.user_id || !form.value.subject_code || !form.value.semester || !form.value.class_ids.length) {
    message.warning('请填写所有必填项')
    return
  }
  saving.value = true
  try {
    await createAssignments(schoolId(), {
      user_id: form.value.user_id,
      class_ids: form.value.class_ids,
      subject_code: form.value.subject_code,
      semester: form.value.semester,
    })
    message.success('排课创建成功')
    showCreate.value = false
    resetForm()
    await Promise.all([loadData(), loadSummary()])
  } catch (e) {
    message.error(e.response?.data?.detail || '创建失败')
  }
  saving.value = false
}

// Delete assignment
async function handleDelete(id) {
  if (!canManageScheduling.value) return
  try {
    await deleteAssignment(schoolId(), id)
    message.success('已删除')
    await Promise.all([loadData(), loadSummary()])
  } catch {
    message.error('删除失败')
  }
}

// Open create modal with defaults
function openCreate() {
  if (!canManageScheduling.value) return
  resetForm()
  if (currentSemesterId.value) {
    form.value.semester = currentSemesterId.value
  } else if (filterSemester.value) {
    form.value.semester = filterSemester.value
  }
  showCreate.value = true
}

// Handle teacher selection change — auto-pick subject if teacher has exactly one
function handleTeacherChange(teacherId) {
  form.value.subject_code = null
  if (teacherId) {
    const t = teachers.value.find(tt => tt.id === teacherId)
    if (t?.subject_codes?.length === 1) {
      form.value.subject_code = t.subject_codes[0]
    }
  }
}

function resetForm() {
  form.value = { user_id: null, subject_code: null, semester: null, class_ids: [] }
}

onMounted(async () => {
  await loadRefData()
  await Promise.all([loadData(), loadSummary()])
})
</script>
