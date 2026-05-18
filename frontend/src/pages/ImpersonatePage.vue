<template>
  <div class="impersonate-page">
    <h1 class="page-title">角色模拟</h1>
    <p class="page-desc">以任意学校的任意角色视角查看系统</p>

    <div class="impersonate-page__grid">
      <!-- 左列：学校选择 -->
      <div class="impersonate-page__schools">
        <n-input v-model:value="schoolSearch" placeholder="搜索学校..." clearable size="large" />
        <div class="school-list">
          <div
            v-for="school in filteredSchools"
            :key="school.id"
            class="school-card"
            :class="{ 'school-card--active': selectedSchool?.id === school.id }"
            @click="selectedSchool = school"
          >
            <span class="school-card__name">{{ school.name }}</span>
            <span class="school-card__code">{{ school.code }}</span>
          </div>
          <div v-if="filteredSchools.length === 0 && !loadingSchools" class="school-list__empty">
            无匹配学校
          </div>
        </div>
      </div>

      <!-- 右列：角色 + scope 选择 -->
      <div class="impersonate-page__config">
        <template v-if="selectedSchool">
          <h3>选择角色</h3>
          <div class="role-grid">
            <div
              v-for="r in availableRoles"
              :key="r.value"
              class="role-chip"
              :class="{ 'role-chip--active': selectedRole === r.value }"
              @click="selectRole(r.value)"
            >
              {{ r.label }}
            </div>
          </div>

          <template v-if="needsScope">
            <h3>选择范围</h3>
            <div class="scope-selectors">
              <n-select
                v-if="needsGrade"
                v-model:value="selectedGradeIds"
                :options="gradeOptions"
                multiple
                placeholder="选择年级"
              />
              <n-select
                v-if="needsClass"
                v-model:value="selectedClassIds"
                :options="classOptions"
                multiple
                placeholder="选择班级"
                filterable
              />
              <n-select
                v-if="needsSubject"
                v-model:value="selectedSubjectCodes"
                :options="subjectOptions"
                multiple
                placeholder="选择学科"
              />
            </div>
          </template>

          <n-button
            type="primary"
            size="large"
            :disabled="!canImpersonate"
            :loading="loading"
            @click="doImpersonate"
            style="margin-top: 24px; width: 100%;"
          >
            进入模拟
          </n-button>
        </template>
        <template v-else>
          <div class="config-placeholder">← 请先选择学校</div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { NInput, NSelect, NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import client from '../api/client.js'
import router from '../router/index.js'
import { ROLE_LABELS, normalizeRole } from '../config/roles.js'

const auth = useAuthStore()
const message = useMessage()

const schoolSearch = ref('')
const schools = ref([])
const loadingSchools = ref(false)
const selectedSchool = ref(null)
const selectedRole = ref(null)
const selectedGradeIds = ref([])
const selectedClassIds = ref([])
const selectedSubjectCodes = ref([])
const loading = ref(false)

const classes = ref([])
const grades = ref([])

const IMPERSONATABLE_ROLES = [
  { value: 'school_admin', label: ROLE_LABELS.school_admin || '校管理员' },
  { value: 'principal', label: ROLE_LABELS.principal || '校长' },
  { value: 'academic_director', label: ROLE_LABELS.academic_director || '教务主任' },
  { value: 'teaching_research_leader', label: ROLE_LABELS.teaching_research_leader || '教研组长' },
  { value: 'grade_leader', label: ROLE_LABELS.grade_leader || '年级组长' },
  { value: 'lesson_prep_leader', label: ROLE_LABELS.lesson_prep_leader || '备课组长' },
  { value: 'homeroom_teacher', label: ROLE_LABELS.homeroom_teacher || '班主任' },
  { value: 'subject_teacher', label: ROLE_LABELS.subject_teacher || '科任教师' },
]

const SUBJECT_OPTIONS = [
  { value: 'chinese', label: '语文' },
  { value: 'math', label: '数学' },
  { value: 'english', label: '英语' },
  { value: 'physics', label: '物理' },
  { value: 'chemistry', label: '化学' },
  { value: 'biology', label: '生物' },
  { value: 'politics', label: '政治' },
  { value: 'history', label: '历史' },
  { value: 'geography', label: '地理' },
]

const filteredSchools = computed(() => {
  if (!schoolSearch.value) return schools.value
  const q = schoolSearch.value.toLowerCase()
  return schools.value.filter(s =>
    s.name.toLowerCase().includes(q) || (s.code || '').toLowerCase().includes(q)
  )
})

const availableRoles = computed(() => IMPERSONATABLE_ROLES)

const needsScope = computed(() =>
  ['grade_leader', 'lesson_prep_leader', 'homeroom_teacher', 'subject_teacher', 'teaching_research_leader'].includes(selectedRole.value)
)
const needsGrade = computed(() => ['grade_leader', 'lesson_prep_leader'].includes(selectedRole.value))
const needsClass = computed(() => ['homeroom_teacher', 'subject_teacher'].includes(selectedRole.value))
const needsSubject = computed(() => ['subject_teacher', 'teaching_research_leader', 'lesson_prep_leader'].includes(selectedRole.value))

const gradeOptions = computed(() => grades.value.map(g => ({ value: g.id, label: g.name })))
const classOptions = computed(() => classes.value.map(c => ({ value: c.id, label: c.name })))
const subjectOptions = computed(() => SUBJECT_OPTIONS)

const canImpersonate = computed(() => {
  if (!selectedSchool.value || !selectedRole.value) return false
  if (needsClass.value && selectedClassIds.value.length === 0) return false
  if (needsSubject.value && selectedSubjectCodes.value.length === 0) return false
  if (needsGrade.value && selectedGradeIds.value.length === 0) return false
  return true
})

function selectRole(role) {
  selectedRole.value = role
  selectedClassIds.value = []
  selectedGradeIds.value = []
  selectedSubjectCodes.value = []
}

watch(selectedSchool, async (school) => {
  if (!school) return
  selectedRole.value = null
  selectedClassIds.value = []
  selectedGradeIds.value = []
  selectedSubjectCodes.value = []
  try {
    const [classResp, gradeResp] = await Promise.all([
      client.get('/classes', { params: { school_id: school.id } }),
      client.get('/grades', { params: { school_id: school.id } }),
    ])
    classes.value = classResp.data?.items || classResp.data || []
    grades.value = gradeResp.data?.items || gradeResp.data || []
  } catch { /* non-fatal */ }
})

onMounted(async () => {
  loadingSchools.value = true
  try {
    const { data } = await client.get('/schools')
    schools.value = data?.items || data || []
  } catch { /* non-fatal */ }
  loadingSchools.value = false
})

async function doImpersonate() {
  loading.value = true
  try {
    const scope = {}
    if (needsClass.value) scope.class_ids = selectedClassIds.value
    if (needsSubject.value) scope.subject_codes = selectedSubjectCodes.value
    if (needsGrade.value) scope.grade_ids = selectedGradeIds.value

    await auth.impersonate(selectedSchool.value.id, selectedRole.value, scope)
    message.success(`已进入模拟: ${selectedSchool.value.name} · ${ROLE_LABELS[normalizeRole(selectedRole.value)] || selectedRole.value}`)
    router.push('/')
  } catch (e) {
    message.error(e.response?.data?.detail || '模拟失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.impersonate-page {
  padding: 32px;
  max-width: 1100px;
  margin: 0 auto;
}
.page-title { font-size: 24px; font-weight: 700; color: var(--color-text); margin-bottom: 4px; }
.page-desc { color: var(--color-text-muted); margin-bottom: 24px; }
.impersonate-page__grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.school-list { margin-top: 12px; max-height: 60vh; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; }
.school-card { padding: 12px 16px; border-radius: var(--radius-sm, 6px); border: 1px solid var(--color-border-light, #333); cursor: pointer; transition: all 0.15s; display: flex; justify-content: space-between; align-items: center; }
.school-card:hover { border-color: var(--color-primary, #644CF0); }
.school-card--active { border-color: var(--color-primary, #644CF0); background: rgba(100, 76, 240, 0.08); }
.school-card__name { font-weight: 500; }
.school-card__code { font-size: 12px; color: var(--color-text-muted, #888); }
.role-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.role-chip { padding: 8px 16px; border-radius: 20px; border: 1px solid var(--color-border-light, #333); cursor: pointer; font-size: 13px; transition: all 0.15s; }
.role-chip:hover { border-color: var(--color-primary, #644CF0); }
.role-chip--active { background: var(--color-primary, #644CF0); border-color: var(--color-primary, #644CF0); color: #fff; }
.scope-selectors { display: flex; flex-direction: column; gap: 12px; margin-top: 8px; }
.config-placeholder { display: flex; align-items: center; justify-content: center; height: 200px; color: var(--color-text-muted, #888); font-size: 16px; }
.school-list__empty { text-align: center; padding: 24px; color: var(--color-text-muted, #888); }
</style>
