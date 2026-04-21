<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">教师管理</h1>
        <p class="page-subtitle">管理教师账号，支持 Excel 批量导入</p>
      </div>
      <div style="display: flex; gap: 8px;">
        <n-button class="btn-pill" @click="showImport = true">导入 Excel</n-button>
        <n-button type="primary" class="btn-pill" @click="showCreate = true">添加教师</n-button>
      </div>
    </div>

    <div style="margin-bottom: 16px;">
      <n-input v-model:value="searchQuery" placeholder="搜索姓名或账号" clearable style="width: 240px;"
        @update:value="handleSearch" />
    </div>

    <n-data-table :columns="columns" :data="teachers" :loading="loading" :pagination="{ pageSize: 50 }" />

    <!-- 添加教师 -->
    <n-modal v-model:show="showCreate" preset="card" title="添加教师" style="width: 460px;">
      <n-form :model="createForm" label-placement="top">
        <n-form-item label="姓名" required>
          <n-input v-model:value="createForm.display_name" placeholder="教师姓名" />
        </n-form-item>
        <n-form-item label="用户名/账号" required>
          <n-input v-model:value="createForm.username" placeholder="登录账号" />
        </n-form-item>
        <n-form-item label="初始密码">
          <n-input v-model:value="createForm.password" placeholder="默认 123456" />
        </n-form-item>
        <n-form-item label="角色">
          <n-select v-model:value="createForm.role" :options="roleOptions" />
        </n-form-item>
        <n-form-item label="电话">
          <n-input v-model:value="createForm.phone" placeholder="选填" />
        </n-form-item>
      </n-form>
      <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px;">
        <n-button class="btn-pill" @click="showCreate = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="saving" @click="handleCreate">保存</n-button>
      </div>
    </n-modal>

    <!-- 编辑教师 -->
    <n-modal v-model:show="showEdit" preset="card" title="编辑教师" style="width: 420px;">
      <n-form :model="editForm" label-placement="top">
        <n-form-item label="姓名">
          <n-input v-model:value="editForm.display_name" />
        </n-form-item>
        <n-form-item label="电话">
          <n-input v-model:value="editForm.phone" />
        </n-form-item>
        <n-form-item label="启用状态">
          <n-switch v-model:value="editForm.is_active" />
        </n-form-item>
      </n-form>
      <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px;">
        <n-button class="btn-pill" @click="showEdit = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="saving" @click="handleUpdate">保存</n-button>
      </div>
    </n-modal>

    <!-- 导入 Excel -->
    <n-modal v-model:show="showImport" preset="card" title="导入教师（Excel）" style="width: 480px;">
      <n-form label-placement="top">
        <n-form-item label="角色">
          <n-select v-model:value="importRole" :options="roleOptions" />
        </n-form-item>
        <n-form-item label="Excel 文件">
          <n-upload :max="1" accept=".xlsx,.xls" :default-upload="false" @change="handleFileChange">
            <n-button>选择文件</n-button>
          </n-upload>
          <p style="font-size: 12px; color: #999; margin-top: 4px;">
            表头需包含「姓名」列；可选：「用户名/账号/工号」「电话/手机」列。<br/>
            默认密码 123456，用户名自动以 t_ 前缀 + 姓名生成。
          </p>
        </n-form-item>
      </n-form>
      <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px;">
        <n-button class="btn-pill" @click="showImport = false">取消</n-button>
        <n-button type="primary" class="btn-pill" :loading="importing" @click="handleImport">导入</n-button>
      </div>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, reactive, onMounted } from 'vue'
import { NButton, NTag, useMessage, useDialog } from 'naive-ui'
import { listTeachers, createTeacher, updateTeacher, deleteTeacher, importTeachers } from '../api/teachers'

const message = useMessage()
const dialog = useDialog()
const loading = ref(true)
const teachers = ref([])
const searchQuery = ref('')
const showCreate = ref(false)
const showEdit = ref(false)
const showImport = ref(false)
const saving = ref(false)
const importing = ref(false)
const editingId = ref(null)
const importRole = ref('subject_teacher')
const importFile = ref(null)

const roleLabels = {
  subject_teacher: '科任教师', homeroom_teacher: '班主任',
  teaching_research_leader: '教研组长', grade_leader: '年级组长',
  lesson_prep_leader: '备课组长', principal: '校长',
  academic_director: '教务主任', district_admin: '区管理员',
}

const roleOptions = Object.entries(roleLabels).map(([value, label]) => ({ label, value }))

const createForm = reactive({
  display_name: '', username: '', password: '123456',
  role: 'subject_teacher', phone: '',
})
const editForm = reactive({ display_name: '', phone: '', is_active: true })

const columns = [
  { title: '姓名', key: 'display_name', width: 120 },
  { title: '账号', key: 'username', width: 140 },
  { title: '电话', key: 'phone', width: 130, render: (row) => row.phone || '-' },
  {
    title: '角色', key: 'roles', width: 200,
    render: (row) => h('div', { style: 'display: flex; gap: 4px; flex-wrap: wrap;' },
      (row.roles || []).map(r =>
        h(NTag, { size: 'small', round: true, type: 'info' }, { default: () => roleLabels[r.role] || r.role })
      )
    ),
  },
  {
    title: '状态', key: 'is_active', width: 70,
    render: (row) => h(NTag, { type: row.is_active ? 'success' : 'default', size: 'small', round: true },
      { default: () => row.is_active ? '启用' : '停用' }),
  },
  {
    title: '操作', key: 'actions', width: 140,
    render: (row) => h('div', { style: 'display: flex; gap: 8px;' }, [
      h(NButton, { text: true, type: 'primary', size: 'small', onClick: () => openEdit(row) }, { default: () => '编辑' }),
      h(NButton, { text: true, type: 'error', size: 'small', onClick: () => handleDelete(row) }, { default: () => '删除' }),
    ]),
  },
]

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
    const { data } = await listTeachers(params)
    teachers.value = data
  } catch {}
  loading.value = false
}

async function handleCreate() {
  if (!createForm.display_name || !createForm.username) {
    message.warning('姓名和账号为必填')
    return
  }
  saving.value = true
  try {
    await createTeacher(createForm)
    message.success('添加成功')
    showCreate.value = false
    Object.assign(createForm, { display_name: '', username: '', password: '123456', role: 'subject_teacher', phone: '' })
    await loadTeachers()
  } catch (e) {
    message.error(e.response?.data?.detail || '添加失败')
  } finally { saving.value = false }
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(editForm, {
    display_name: row.display_name,
    phone: row.phone || '',
    is_active: row.is_active,
  })
  showEdit.value = true
}

async function handleUpdate() {
  saving.value = true
  try {
    await updateTeacher(editingId.value, editForm)
    message.success('更新成功')
    showEdit.value = false
    await loadTeachers()
  } catch (e) {
    message.error(e.response?.data?.detail || '更新失败')
  } finally { saving.value = false }
}

function handleDelete(row) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除教师「${row.display_name}」吗？此操作将移除该教师在本校的所有角色。`,
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
    message.success(`导入完成：新增 ${data.created} 人，跳过 ${data.skipped} 人`)
    showImport.value = false
    importFile.value = null
    await loadTeachers()
  } catch (e) {
    message.error(e.response?.data?.detail || '导入失败')
  } finally { importing.value = false }
}

onMounted(loadTeachers)
</script>
