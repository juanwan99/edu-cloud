<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">排课管理</h1>
        <p class="page-subtitle">管理教师排课信息</p>
      </div>
      <n-button type="primary" @click="showCreate = true">新增排课</n-button>
    </div>

    <n-space style="margin-bottom: 16px">
      <n-input v-model:value="filterSemester" placeholder="学期 (如 2025-2026-2)" clearable style="width: 200px" />
      <n-button @click="loadData">查询</n-button>
    </n-space>

    <n-data-table :columns="columns" :data="rows" :loading="loading" />

    <n-modal v-model:show="showCreate" preset="dialog" title="新增排课" positive-text="确认" negative-text="取消"
      @positive-click="handleCreate">
      <n-space vertical>
        <n-input v-model:value="form.user_id" placeholder="教师 ID" />
        <n-input v-model:value="form.subject_code" placeholder="科目代码 (如 math)" />
        <n-input v-model:value="form.semester" placeholder="学期 (如 2025-2026-2)" />
        <n-input v-model:value="form.class_ids_raw" placeholder="班级 ID（逗号分隔）" />
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, h, onMounted } from 'vue'
import { NButton, useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { getAssignments, createAssignments, deleteAssignment } from '../api/teacherAssignments.js'

const auth = useAuthStore()
const message = useMessage()
const rows = ref([])
const loading = ref(false)
const showCreate = ref(false)
const filterSemester = ref('')

const form = ref({ user_id: '', subject_code: '', semester: '', class_ids_raw: '' })

const schoolId = () => auth.currentRole?.school_id

const columns = [
  { title: '教师 ID', key: 'user_id', ellipsis: true, width: 200 },
  { title: '班级 ID', key: 'class_id', ellipsis: true, width: 200 },
  { title: '科目', key: 'subject_code', width: 100 },
  { title: '学期', key: 'semester', width: 120 },
  {
    title: '操作', key: 'actions', width: 80,
    render(row) {
      return h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row.id) }, () => '删除')
    }
  },
]

async function loadData() {
  if (!schoolId()) return
  loading.value = true
  try {
    const params = {}
    if (filterSemester.value) params.semester = filterSemester.value
    const { data } = await getAssignments(schoolId(), params)
    rows.value = data
  } catch { message.error('加载失败') }
  loading.value = false
}

async function handleCreate() {
  try {
    const classIds = form.value.class_ids_raw.split(',').map(s => s.trim()).filter(Boolean)
    await createAssignments(schoolId(), {
      user_id: form.value.user_id,
      class_ids: classIds,
      subject_code: form.value.subject_code,
      semester: form.value.semester,
    })
    message.success('排课创建成功')
    showCreate.value = false
    form.value = { user_id: '', subject_code: '', semester: '', class_ids_raw: '' }
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '创建失败') }
}

async function handleDelete(id) {
  try {
    await deleteAssignment(schoolId(), id)
    message.success('已删除')
    await loadData()
  } catch (e) { message.error('删除失败') }
}

onMounted(loadData)
</script>
