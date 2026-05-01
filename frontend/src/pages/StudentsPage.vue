<template>
  <div>
    <div class="page-header page-header-row">
      <div>
        <h1 class="page-title">学生管理</h1>
        <p class="page-subtitle">管理学生信息，支持 Excel 批量导入</p>
      </div>
      <div class="action-buttons">
        <n-dropdown :options="exportOptions" @select="handleExportSelect">
          <n-button class="btn-pill">导出 Excel</n-button>
        </n-dropdown>
        <n-button class="btn-pill" @click="showImport = true">导入 Excel</n-button>
        <n-button type="primary" class="btn-pill" @click="showCreate = true">添加学生</n-button>
      </div>
    </div>

    <div class="filter-bar">
      <n-select v-model:value="filterGrade" :options="gradeOptions" placeholder="按年级筛选"
        clearable style="width: 140px;" @update:value="handleGradeChange" />
      <n-select v-model:value="filterClassId" :options="filteredClassOptions" placeholder="按班级筛选"
        clearable style="width: 200px;" @update:value="loadStudents" />
      <n-select v-model:value="filterSelectionId" :options="selectionOptions" placeholder="按选课组合筛选"
        clearable style="width: 200px;" @update:value="loadStudents" />
      <n-select v-model:value="filterSubjectCode" :options="subjectOptions" placeholder="按学科筛选"
        clearable style="width: 160px;" @update:value="loadStudents" />
      <n-input v-model:value="searchQuery" placeholder="搜索姓名" clearable style="width: 200px;"
        @update:value="handleSearch" />
    </div>

    <n-data-table :columns="columns" :data="students" :loading="loading" :pagination="{ pageSize: 50 }" />

    <!-- 添加学生 -->
    <n-modal v-model:show="showCreate" preset="card" title="添加学生" style="width: 420px;">
      <n-form :model="createForm" label-placement="top">
        <n-form-item label="姓名" required>
          <n-input v-model:value="createForm.name" placeholder="学生姓名" />
        </n-form-item>
        <n-form-item label="学号/准考证号" required>
          <n-input v-model:value="createForm.student_number" placeholder="学号" />
        </n-form-item>
        <n-form-item label="年级">
          <n-select v-model:value="createForm.grade" :options="gradeOptions" placeholder="选择年级" clearable />
        </n-form-item>
        <n-form-item label="班级">
          <n-select v-model:value="createForm.class_id" :options="classOptions" placeholder="选择班级" clearable />
        </n-form-item>
        <n-form-item label="性别">
          <n-select v-model:value="createForm.gender" :options="genderOptions" placeholder="选择性别" clearable />
        </n-form-item>
        <n-form-item label="身份证号">
          <n-input v-model:value="createForm.id_card" placeholder="选填" />
        </n-form-item>
        <n-form-item label="选课组合">
          <n-select v-model:value="createForm.selection_id" :options="selectionOptions" placeholder="选择组合" clearable />
        </n-form-item>
      </n-form>
      <div class="form-actions">
        <n-button class="btn-pill" @click="showCreate = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="saving" @click="handleCreate">保存</n-button>
      </div>
    </n-modal>

    <!-- 编辑学生 -->
    <n-modal v-model:show="showEdit" preset="card" title="编辑学生" style="width: 420px;">
      <n-form :model="editForm" label-placement="top">
        <n-form-item label="姓名">
          <n-input v-model:value="editForm.name" />
        </n-form-item>
        <n-form-item label="学号/准考证号">
          <n-input v-model:value="editForm.student_number" />
        </n-form-item>
        <n-form-item label="年级">
          <n-select v-model:value="editForm.grade" :options="gradeOptions" placeholder="选择年级" clearable />
        </n-form-item>
        <n-form-item label="班级">
          <n-select v-model:value="editForm.class_id" :options="classOptions" placeholder="选择班级" clearable />
        </n-form-item>
        <n-form-item label="性别">
          <n-select v-model:value="editForm.gender" :options="genderOptions" placeholder="选择性别" clearable />
        </n-form-item>
        <n-form-item label="身份证号">
          <n-input v-model:value="editForm.id_card" />
        </n-form-item>
        <n-form-item label="选课组合">
          <n-select v-model:value="editForm.selection_id" :options="selectionOptions" placeholder="选择组合" clearable />
        </n-form-item>
      </n-form>
      <div class="form-actions">
        <n-button class="btn-pill" @click="showEdit = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="saving" @click="handleUpdate">保存</n-button>
      </div>
    </n-modal>

    <!-- 导入 Excel -->
    <n-modal v-model:show="showImport" preset="card" title="导入学生（Excel）" style="width: 480px;">
      <n-form label-placement="top">
        <n-form-item label="年级">
          <n-select v-model:value="importGrade" :options="gradeOptions" placeholder="选择年级（限定班级匹配范围）" clearable
            @update:value="importClassId = null" />
        </n-form-item>
        <n-form-item label="目标班级">
          <n-select v-model:value="importClassId" :options="importClassOptions"
            placeholder="不选则按 Excel 中「班级」列自动分配" clearable />
        </n-form-item>
        <n-form-item label="Excel 文件">
          <n-upload :max="1" accept=".xlsx,.xls" :default-upload="false" @change="handleFileChange">
            <n-button>选择文件</n-button>
          </n-upload>
          <p class="help-text">
            必填列：「姓名」「学号/准考证号」<br/>
            可选列：「班级」「性别」「选课组合」<br/>
            不选班级时，Excel 必须包含「班级」列（班级名需与系统一致）
          </p>
        </n-form-item>
      </n-form>
      <div class="form-actions">
        <n-button class="btn-pill" @click="showImport = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="importing" @click="handleImport">导入</n-button>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NDropdown, useMessage, useDialog } from 'naive-ui'
import { listStudents, createStudent, updateStudent, deleteStudent, importStudents, listClasses, listGrades, listSelections, exportStudents } from '../api/students'

const router = useRouter()

const message = useMessage()
const dialog = useDialog()
const loading = ref(true)
const students = ref([])
const classes = ref([])
const grades = ref([])
const selections = ref([])
const filterGrade = ref(null)
const filterClassId = ref(null)
const filterSelectionId = ref(null)
const filterSubjectCode = ref(null)
const searchQuery = ref('')
const showCreate = ref(false)
const showEdit = ref(false)
const showImport = ref(false)
const saving = ref(false)
const importing = ref(false)
const editingId = ref(null)
const importGrade = ref(null)
const importClassId = ref(null)
const importFile = ref(null)

const importClassOptions = computed(() => {
  const list = importGrade.value
    ? classes.value.filter(c => c.grade === importGrade.value)
    : classes.value
  return list.map(c => ({ label: c.name, value: c.id }))
})

const createForm = reactive({ name: '', student_number: '', class_id: null, grade: null, gender: null, id_card: '', selection_id: null })
const editForm = reactive({ name: '', student_number: '', class_id: null, grade: null, gender: null, id_card: '', selection_id: null })

const genderOptions = [
  { label: '男', value: '男' },
  { label: '女', value: '女' },
]

const gradeOptions = computed(() =>
  grades.value.map(g => ({ label: g.name, value: g.name }))
)

const classOptions = computed(() =>
  classes.value.map(c => ({ label: c.name, value: c.id }))
)

const filteredClassOptions = computed(() => {
  const list = filterGrade.value
    ? classes.value.filter(c => c.grade === filterGrade.value)
    : classes.value
  return list.map(c => ({ label: c.name, value: c.id }))
})

const SUBJECT_LABELS = {
  YW: '语文', SX: '数学', YY: '英语', WL: '物理', HX: '化学',
  SW: '生物', ZZ: '政治', LS: '历史', DL: '地理', JS: '技术',
}

const selectionOptions = computed(() =>
  selections.value.map(s => ({ label: `${s.name} (${s.subject_codes.join('/')})`, value: s.id }))
)

const subjectOptions = computed(() => {
  const codes = new Set()
  selections.value.forEach(s => (s.subject_codes || []).forEach(c => codes.add(c)))
  return [...codes].map(c => ({ label: SUBJECT_LABELS[c] || c, value: c }))
})

const classMap = computed(() => {
  const m = {}
  classes.value.forEach(c => { m[c.id] = c.name })
  return m
})

const selectionMap = computed(() => {
  const m = {}
  selections.value.forEach(s => { m[s.id] = s.name })
  return m
})

const columns = [
  { title: '姓名', key: 'name', width: 100 },
  { title: '学号', key: 'student_number', width: 130 },
  { title: '年级', key: 'grade', width: 80, render: (row) => row.grade || '-' },
  {
    title: '班级', key: 'class_id', width: 120,
    render: (row) => classMap.value[row.class_id] || '-',
  },
  { title: '性别', key: 'gender', width: 55, render: (row) => row.gender || '-' },
  {
    title: '选课组合', key: 'selection_id', width: 140,
    render: (row) => selectionMap.value[row.selection_id] || '-',
  },
  {
    title: '操作', key: 'actions', width: 200,
    render: (row) => h('div', { style: 'display: flex; gap: var(--space-2);' }, [
      h(NButton, { text: true, type: 'info', size: 'small', onClick: () => router.push({ name: 'StudentProfile', params: { studentId: row.id } }) }, { default: () => '画像' }),
      h(NButton, { text: true, type: 'primary', size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
      h(NButton, { text: true, type: 'error', size: 'small', onClick: () => handleDelete(row) }, { default: () => '删除' }),
    ]),
  },
]

let searchTimer = null
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadStudents, 300)
}

function getSchoolId() {
  try {
    const state = JSON.parse(localStorage.getItem('auth_state') || '{}')
    const role = state.roles?.[state.currentRoleIndex]
    return role?.school_id
  } catch { return null }
}

function handleGradeChange() {
  filterClassId.value = null
  loadStudents()
}

async function loadGrades() {
  try {
    const { data } = await listGrades()
    grades.value = data
  } catch {}
}

async function loadClasses() {
  try {
    const { data } = await listClasses()
    classes.value = data
  } catch {}
}

async function loadSelections() {
  const schoolId = getSchoolId()
  if (!schoolId) return
  try {
    const { data } = await listSelections(schoolId)
    selections.value = data
  } catch {}
}

async function loadStudents() {
  loading.value = true
  try {
    const params = {}
    if (filterGrade.value) params.grade = filterGrade.value
    if (filterClassId.value) params.class_id = filterClassId.value
    if (filterSelectionId.value) params.selection_id = filterSelectionId.value
    if (filterSubjectCode.value) params.subject_code = filterSubjectCode.value
    if (searchQuery.value) params.q = searchQuery.value
    const { data } = await listStudents(params)
    students.value = data
  } catch {}
  loading.value = false
}

async function handleCreate() {
  if (!createForm.name || !createForm.student_number) {
    message.warning('姓名和学号为必填')
    return
  }
  saving.value = true
  try {
    await createStudent(createForm)
    message.success('添加成功')
    showCreate.value = false
    Object.assign(createForm, { name: '', student_number: '', class_id: null, grade: null, gender: null, id_card: '', selection_id: null })
    await loadStudents()
  } catch (e) {
    message.error(e.response?.data?.detail || '添加失败')
  } finally { saving.value = false }
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(editForm, {
    name: row.name, student_number: row.student_number,
    class_id: row.class_id, grade: row.grade,
    gender: row.gender, id_card: row.id_card || '',
    selection_id: row.selection_id,
  })
  showEdit.value = true
}

async function handleUpdate() {
  saving.value = true
  try {
    await updateStudent(editingId.value, editForm)
    message.success('更新成功')
    showEdit.value = false
    await loadStudents()
  } catch (e) {
    message.error(e.response?.data?.detail || '更新失败')
  } finally { saving.value = false }
}

function handleDelete(row) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除学生「${row.name}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositive: async () => {
      try {
        await deleteStudent(row.id)
        message.success('已删除')
        await loadStudents()
      } catch (e) {
        message.error(e.response?.data?.detail || '删除失败')
      }
    },
  })
}

function handleFileChange({ fileList }) {
  importFile.value = fileList.length > 0 ? fileList[0].file : null
}

async function handleImport() {
  if (!importFile.value) { message.warning('请选择文件'); return }
  importing.value = true
  try {
    const { data } = await importStudents(importFile.value, { classId: importClassId.value, grade: importGrade.value })
    const parts = [`新增 ${data.created} 人`]
    if (data.updated) parts.push(`更新 ${data.updated} 人`)
    parts.push(`跳过 ${data.skipped} 人`)
    if (data.class_not_found) parts.push(`${data.class_not_found} 人班级未匹配`)
    if (data.selection_not_found) parts.push(`${data.selection_not_found} 人选课组合未匹配（请先在选科管理中创建组合）`)
    message.success(`导入完成：${parts.join('，')}`)
    showImport.value = false
    importFile.value = null
    await loadStudents()
  } catch (e) {
    message.error(e.response?.data?.detail || '导入失败')
  } finally { importing.value = false }
}

const exportOptions = [
  { label: '导出标准模板（空表）', key: 'template' },
  { label: '导出现有学生数据', key: 'data' },
]

async function handleExportSelect(key) {
  try {
    const params = {}
    if (key === 'template') params.template = '1'
    if (filterClassId.value) params.class_id = filterClassId.value
    const { data } = await exportStudents(params)
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = key === 'template' ? 'students_template.xlsx' : 'students.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    message.success(key === 'template' ? '模板导出成功' : '导出成功')
  } catch (e) {
    message.error('导出失败')
  }
}

onMounted(async () => {
  await Promise.all([loadGrades(), loadClasses(), loadSelections()])
  await loadStudents()
})
</script>

<style scoped>
.page-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: var(--space-2);
}

.filter-bar {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

.help-text {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin-top: var(--space-1);
}
</style>
