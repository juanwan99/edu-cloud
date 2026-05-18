<template>
  <div>
    <div class="page-header page-header-row">
      <div>
        <h1 class="page-title">教师管理</h1>
        <p class="page-subtitle">管理教师档案、学科与班级分配，支持 Excel 批量导入导出</p>
      </div>
      <div class="action-buttons">
        <n-button class="btn-pill" @click="handleDownloadTemplate">下载导入模板</n-button>
        <n-button class="btn-pill" @click="handleExport">导出花名册</n-button>
        <n-button class="btn-pill" @click="showImport = true">导入 Excel</n-button>
        <n-button type="primary" class="btn-pill" @click="openCreate">添加教师</n-button>
      </div>
    </div>

    <div class="filter-bar">
      <n-select v-if="isPlatformAdmin || schoolOptions.length > 1" v-model:value="selectedSchool" :options="schoolOptions"
        style="width: 200px;" data-testid="school-select" @update:value="onSchoolChange" />
      <n-input v-model:value="searchQuery" placeholder="搜索姓名或账号" clearable style="width: 240px;"
        @update:value="handleSearch" />
      <n-tag v-if="teachers.length" :bordered="false">共 {{ teachers.length }} 人</n-tag>
    </div>

    <n-data-table :columns="columns" :data="teachers" :loading="loading"
      :pagination="{ pageSize: 50 }" :row-key="(r) => r.id" :scroll-x="1200" />

    <!-- 添加/编辑教师 -->
    <n-modal v-model:show="showForm" preset="card" :title="editingId ? '编辑教师' : '添加教师'" style="width: 640px;">
      <n-form :model="form" label-placement="top">
        <div class="form-grid">
          <n-form-item label="姓名" required>
            <n-input v-model:value="form.display_name" placeholder="教师姓名" />
          </n-form-item>
          <n-form-item v-if="!editingId" label="用户名/工号" required>
            <n-input v-model:value="form.username" placeholder="登录账号" />
          </n-form-item>
          <n-form-item v-if="!editingId" label="初始密码">
            <n-input v-model:value="form.password" placeholder="默认 123456" />
          </n-form-item>
          <n-form-item label="性别">
            <n-select v-model:value="form.gender" :options="genderOptions" clearable placeholder="选择" />
          </n-form-item>
          <n-form-item label="手机号">
            <n-input v-model:value="form.phone" placeholder="选填" />
          </n-form-item>
          <n-form-item label="办公电话">
            <n-input v-model:value="form.office_phone" placeholder="选填" />
          </n-form-item>
          <n-form-item label="邮箱">
            <n-input v-model:value="form.email" placeholder="选填" />
          </n-form-item>
          <n-form-item label="工号">
            <n-input v-model:value="form.employee_id" placeholder="选填" />
          </n-form-item>
          <n-form-item label="身份证号">
            <n-input v-model:value="form.id_card" placeholder="选填" />
          </n-form-item>
          <n-form-item label="职称">
            <n-input v-model:value="form.title" placeholder="如：一级教师" />
          </n-form-item>
          <n-form-item label="入职日期">
            <n-input v-model:value="form.hire_date" placeholder="2020-09-01" />
          </n-form-item>
          <n-form-item label="学历">
            <n-select v-model:value="form.education" :options="eduOptions" clearable placeholder="选择" />
          </n-form-item>
          <n-form-item label="毕业院校">
            <n-input v-model:value="form.university" placeholder="选填" />
          </n-form-item>
          <n-form-item v-if="editingId" label="状态">
            <n-switch v-model:value="form.is_active" />
          </n-form-item>
        </div>
        <n-divider class="form-divider" />
        <h4 class="form-section-title">角色与任教分配</h4>
        <div class="form-grid">
          <n-form-item v-if="!editingId" label="角色（可多选）">
            <n-select v-model:value="form.roles" :options="createRoleOptions" multiple placeholder="可多选" />
          </n-form-item>
          <n-form-item v-if="!editingId" label="任教学科">
            <n-select v-model:value="form.subject_codes" :options="subjectOptions" multiple clearable placeholder="可多选" />
          </n-form-item>
          <n-form-item v-if="!editingId" label="任教班级">
            <n-select v-model:value="form.class_ids" :options="classOptions" multiple clearable
              placeholder="可多选" :loading="classesLoading" filterable />
          </n-form-item>
        </div>
        <n-form-item label="备注">
          <n-input v-model:value="form.notes" type="textarea" placeholder="选填" :rows="2" />
        </n-form-item>
      </n-form>
      <div class="form-actions">
        <n-button class="btn-pill" @click="showForm = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="saving" @click="handleSave">保存</n-button>
      </div>
    </n-modal>

    <!-- 导入 Excel -->
    <n-modal v-model:show="showImport" preset="card" title="导入教师（Excel）" style="width: 520px;">
      <n-form label-placement="top">
        <n-form-item label="默认角色（Excel 中未填角色列时使用）">
          <n-select v-model:value="importRole" :options="importRoleOptions" />
        </n-form-item>
        <n-form-item label="Excel 文件">
          <n-upload :max="1" accept=".xlsx,.xls" :default-upload="false" @change="handleFileChange">
            <n-button>选择文件</n-button>
          </n-upload>
          <div class="help-text">
            <p>建议先<a href="#" @click.prevent="handleDownloadTemplate" class="help-link">下载导入模板</a>，按模板格式填写。</p>
            <p>支持 15 列：姓名/工号/手机/邮箱/性别/身份证/职称/入职日期/学历/毕业院校/办公电话/角色/任教学科/任教班级/备注</p>
            <p>最少只需「姓名」列，其余自动补全。默认密码 123456。</p>
          </div>
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
import { NButton, NTag, useMessage, useDialog } from 'naive-ui'
import { listTeachers, createTeacher, updateTeacher, deleteTeacher, importTeachers, exportTeachers, downloadTemplate } from '../api/teachers'
import client from '../api/client'
import { listSchools } from '../api/schools'
import { useAuthStore } from '../stores/auth'

const message = useMessage()
const dialog = useDialog()
const loading = ref(true)
const teachers = ref([])
const searchQuery = ref('')
const showForm = ref(false)
const showImport = ref(false)
const saving = ref(false)
const importing = ref(false)
const editingId = ref(null)
const importRole = ref('subject_teacher')
const importFile = ref(null)
const classOptions = ref([])
const classesLoading = ref(false)
const classMap = ref({})  // id → { name, grade }
const schoolOptions = ref([])
const selectedSchool = ref(null)

const roleLabels = {
  subject_teacher: '科任教师', homeroom_teacher: '班主任',
  teaching_research_leader: '教研组长', grade_leader: '年级组长',
  lesson_prep_leader: '备课组长', school_admin: '校管理员',
  principal: '校长', academic_director: '教务主任', district_admin: '区管理员',
}
const subjectLabels = {
  YW: '语文', SX: '数学', YY: '英语', WL: '物理', HX: '化学',
  SW: '生物', ZZ: '政治', LS: '历史', DL: '地理', TY: '体育',
  YS: '音乐', MS: '美术', XX: '信息技术',
}

const isPlatformAdmin = computed(() => {
  const auth = useAuthStore()
  return auth.currentRole?.role === 'platform_admin'
})

const ROLE_OPTIONS_ALL = Object.entries(roleLabels).map(([value, label]) => ({ label, value }))
const ROLE_OPTIONS_CROSS_SCHOOL = [
  { label: '校管理员', value: 'school_admin' },
  { label: '校长', value: 'principal' },
  { label: '教务主任', value: 'academic_director' },
]

const createRoleOptions = computed(() => {
  if (isPlatformAdmin.value && selectedSchool.value) {
    return ROLE_OPTIONS_CROSS_SCHOOL
  }
  return ROLE_OPTIONS_ALL
})

const importRoleOptions = ROLE_OPTIONS_ALL
const subjectOptions = Object.entries(subjectLabels).map(([value, label]) => ({ label, value }))
const genderOptions = [{ label: '男', value: '男' }, { label: '女', value: '女' }]
const eduOptions = [
  { label: '大专', value: '大专' }, { label: '本科', value: '本科' },
  { label: '硕士', value: '硕士' }, { label: '博士', value: '博士' },
]

const defaultForm = () => ({
  display_name: '', username: '', password: '123456',
  roles: ['subject_teacher'], phone: '', email: '',
  employee_id: '', gender: null, id_card: '', title: '',
  hire_date: '', education: null, university: '', office_phone: '',
  notes: '', subject_codes: [], class_ids: [], is_active: true,
})
const form = reactive(defaultForm())

const columns = [
  { title: '姓名', key: 'display_name', width: 90, fixed: 'left' },
  { title: '工号', key: 'employee_id', width: 100, render: (row) => row.employee_id || row.username },
  {
    title: '任教学科', key: 'subjects', width: 140,
    render: (row) => {
      const codes = new Set()
      ;(row.roles || []).forEach(r => (r.subject_codes || []).forEach(c => codes.add(c)))
      if (!codes.size) return h('span', { style: 'color: var(--color-text-muted);' }, '未分配')
      return h('div', { style: 'display: flex; gap: var(--space-1); flex-wrap: wrap;' },
        [...codes].map(c => h(NTag, { size: 'small', round: true, type: 'success' }, { default: () => subjectLabels[c] || c }))
      )
    },
  },
  {
    title: '年级', key: 'grades', width: 70,
    render: (row) => {
      const grades = new Set()
      ;(row.roles || []).filter(r => r.role === 'subject_teacher').forEach(r =>
        (r.class_ids || []).forEach(cid => { const c = classMap.value[cid]; if (c?.grade) grades.add(c.grade) })
      )
      if (!grades.size) return h('span', { style: 'color: var(--color-text-muted);' }, '-')
      return [...grades].join('、')
    },
  },
  {
    title: '任教班级', key: 'classes', width: 180,
    render: (row) => {
      const seen = new Set()
      const names = []
      ;(row.roles || []).filter(r => r.role === 'subject_teacher').forEach(r =>
        (r.class_ids || []).forEach(cid => {
          if (seen.has(cid)) return
          seen.add(cid)
          const c = classMap.value[cid]
          if (c) names.push(c.name)
        })
      )
      if (!names.length) return h('span', { style: 'color: var(--color-text-muted);' }, '未分配')
      return h('div', { style: 'display: flex; gap: var(--space-1); flex-wrap: wrap;' },
        names.map(n => h(NTag, { size: 'small', round: true }, { default: () => n }))
      )
    },
  },
  {
    title: '角色', key: 'role', width: 140,
    render: (row) => {
      const parts = []
      ;(row.roles || []).forEach(r => {
        const label = roleLabels[r.role] || r.role
        if (r.role === 'homeroom_teacher') {
          const cid = (r.class_ids || [])[0]
          const cname = cid ? classMap.value[cid]?.name : null
          parts.push(cname ? `${label}(${cname})` : label)
        } else if (r.role !== 'subject_teacher') {
          parts.push(label)
        }
      })
      if ((row.roles || []).some(r => r.role === 'subject_teacher')) {
        parts.push('科任教师')
      }
      return parts.join('、') || '-'
    },
  },
  { title: '手机', key: 'phone', width: 120, render: (row) => row.phone || '-' },
  {
    title: '操作', key: 'actions', width: 100, fixed: 'right',
    render: (row) => h('div', { style: 'display: flex; gap: var(--space-2);' }, [
      h(NButton, { text: true, type: 'primary', size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
      h(NButton, { text: true, type: 'error', size: 'small', onClick: () => handleDelete(row) }, { default: () => '删除' }),
    ]),
  },
]

function onSchoolChange() {
  loadTeachers()
  loadClasses()
}

let searchTimer = null
function handleSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadTeachers, 300)
}

async function loadTeachers() {
  loading.value = true
  try {
    const params = {}
    if (searchQuery.value) params.q = searchQuery.value
    if (selectedSchool.value) params.school_id = selectedSchool.value
    const { data } = await listTeachers(params)
    teachers.value = data
  } catch {}
  loading.value = false
}

async function loadClasses() {
  classesLoading.value = true
  try {
    const params = {}
    if (selectedSchool.value) params.school_id = selectedSchool.value
    const { data } = await client.get('/classes', { params })
    classOptions.value = data.map(c => ({ label: `${c.grade || ''} ${c.name}`, value: c.id }))
    const map = {}
    data.forEach(c => { map[c.id] = { name: c.name, grade: c.grade } })
    classMap.value = map
  } catch {}
  classesLoading.value = false
}

function openCreate() {
  editingId.value = null
  Object.assign(form, defaultForm())
  if (isPlatformAdmin.value && selectedSchool.value) {
    form.roles = ['principal']
  }
  showForm.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    display_name: row.display_name || '',
    phone: row.phone || '',
    email: row.email || '',
    employee_id: row.employee_id || '',
    gender: row.gender || null,
    id_card: row.id_card || '',
    title: row.title || '',
    hire_date: row.hire_date || '',
    education: row.education || null,
    university: row.university || '',
    office_phone: row.office_phone || '',
    notes: row.notes || '',
    is_active: row.is_active !== false,
  })
  showForm.value = true
}

async function handleSave() {
  if (!form.display_name) { message.warning('姓名为必填'); return }
  if (!editingId.value && !form.username) { message.warning('用户名为必填'); return }
  saving.value = true
  try {
    if (editingId.value) {
      const payload = {}
      for (const k of ['display_name', 'phone', 'email', 'employee_id', 'gender',
        'id_card', 'title', 'hire_date', 'education', 'university', 'office_phone', 'notes', 'is_active']) {
        if (form[k] !== '' && form[k] !== null) payload[k] = form[k]
      }
      await updateTeacher(editingId.value, payload)
      message.success('更新成功')
    } else {
      const payload = { ...form }
      if (!payload.subject_codes?.length) delete payload.subject_codes
      if (!payload.class_ids?.length) delete payload.class_ids
      if (isPlatformAdmin.value && selectedSchool.value) {
        payload.school_id = selectedSchool.value
      }
      await createTeacher(payload)
      message.success('添加成功')
    }
    showForm.value = false
    await loadTeachers()
  } catch (e) {
    message.error(e.response?.data?.detail || '操作失败')
  } finally { saving.value = false }
}

function handleDelete(row) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除教师「${row.display_name}」吗？将移除该教师在本校的所有角色。`,
    positiveText: '删除',
    negativeText: '取消',
    onPositive: async () => {
      try {
        await deleteTeacher(row.id)
        message.success('已删除')
        await loadTeachers()
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
    const { data } = await importTeachers(importFile.value, importRole.value)
    message.success(`导入完成：新增 ${data.created} 人，更新 ${data.updated} 人，跳过 ${data.skipped} 人`)
    showImport.value = false
    importFile.value = null
    await loadTeachers()
  } catch (e) {
    message.error(e.response?.data?.detail || '导入失败')
  } finally { importing.value = false }
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function schoolParams() {
  return selectedSchool.value ? { school_id: selectedSchool.value } : {}
}

async function handleDownloadTemplate() {
  try {
    const { data } = await downloadTemplate(schoolParams())
    triggerDownload(data, 'teachers_template.xlsx')
    message.success('模板已下载')
  } catch { message.error('下载失败') }
}

async function handleExport() {
  try {
    const { data } = await exportTeachers(schoolParams())
    triggerDownload(data, 'teachers.xlsx')
    message.success('导出成功')
  } catch { message.error('导出失败') }
}

async function initSchools() {
  const auth = useAuthStore()
  if (isPlatformAdmin.value) {
    try {
      const { data } = await listSchools()
      schoolOptions.value = data.map((s) => ({ label: s.name, value: s.id }))
      if (schoolOptions.value.length) {
        selectedSchool.value = schoolOptions.value[0].value
      }
    } catch {
      message.error('加载学校列表失败')
    }
    return
  }
  const seen = new Map()
  for (const r of (auth.roles || [])) {
    const ctx = r.context
    if (ctx?.id && ctx?.name && !seen.has(ctx.id)) {
      seen.set(ctx.id, ctx.name)
    }
  }
  schoolOptions.value = [...seen.entries()].map(([id, name]) => ({ label: name, value: id }))
  const current = auth.currentRole
  if (current?.context?.id) {
    selectedSchool.value = current.context.id
  } else if (schoolOptions.value.length) {
    selectedSchool.value = schoolOptions.value[0].value
  }
}

defineExpose({
  form,
  isPlatformAdmin,
  createRoleOptions,
  importRoleOptions,
  schoolOptions,
  selectedSchool,
  openCreate,
  handleSave,
})

onMounted(async () => {
  await initSchools()
  loadTeachers()
  loadClasses()
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
  align-items: center;
  margin-bottom: var(--space-4);
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 var(--space-4);
}

.form-divider {
  margin: var(--space-3) 0;
}

.form-section-title {
  margin: 0 0 var(--space-3);
  font-size: var(--fs-base);
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
  margin-top: var(--space-2);
  line-height: 1.8;
}

.help-text p {
  margin: 0;
}

.help-link {
  color: var(--color-accent);
}
</style>
