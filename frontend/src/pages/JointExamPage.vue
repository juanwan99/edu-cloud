<template>
  <div>
    <div class="page-header">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h1 class="page-title">联考管理</h1>
          <p class="page-subtitle">跨校联合考试的创建、下发与成绩管理</p>
        </div>
        <n-button v-if="canCreate" type="primary" @click="showCreate = true">创建联考</n-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-bar">
      <n-radio-group v-model:value="statusFilter" @update:value="loadExams">
        <n-radio-button value="">全部</n-radio-button>
        <n-radio-button value="draft">草稿</n-radio-button>
        <n-radio-button value="active">进行中</n-radio-button>
        <n-radio-button value="done">已完成</n-radio-button>
      </n-radio-group>
    </div>

    <n-spin :show="loading">
      <n-data-table
        v-if="exams.length"
        :columns="columns"
        :data="exams"
        :pagination="{ pageSize: 15 }"
        :bordered="false"
        size="small"
      />
      <n-empty v-else-if="!loading" description="暂无联考数据" style="margin-top: 40px;" />
    </n-spin>

    <!-- 创建联考弹窗 -->
    <n-modal v-model:show="showCreate" title="创建联考" preset="card" style="width: 520px;">
      <n-form ref="formRef" :model="form" label-placement="top">
        <n-form-item label="联考名称" path="name">
          <n-input v-model:value="form.name" placeholder="例：2026年春季期中联考" />
        </n-form-item>
        <n-form-item label="描述">
          <n-input v-model:value="form.description" type="textarea" placeholder="可选" :rows="2" />
        </n-form-item>
        <n-form-item label="科目（JSON）">
          <n-input v-model:value="form.subjectsText" type="textarea" placeholder='[{"code":"chinese","name":"语文"}]' :rows="3" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <n-button @click="showCreate = false">取消</n-button>
          <n-button type="primary" :loading="creating" @click="handleCreate">创建</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<script setup>
import { h, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { NButton, NTag } from 'naive-ui'
import { listJointExams, createJointExam } from '../api/jointExams.js'

const router = useRouter()
const auth = useAuthStore()

const loading = ref(false)
const exams = ref([])
const statusFilter = ref('')
const showCreate = ref(false)
const creating = ref(false)
const form = ref({ name: '', description: '', subjectsText: '[]' })

const canCreate = computed(() => auth.checkPermission('create_joint_exam'))

const STATUS_MAP = {
  draft: { label: '草稿', type: 'default' },
  active: { label: '进行中', type: 'info' },
  distributing: { label: '下发中', type: 'warning' },
  done: { label: '已完成', type: 'success' },
  archived: { label: '已归档', type: 'default' },
}

const columns = computed(() => [
  { title: '联考名称', key: 'name', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const info = STATUS_MAP[row.status] || { label: row.status, type: 'default' }
      return h(NTag, { size: 'small', type: info.type }, () => info.label)
    },
  },
  {
    title: '科目',
    key: 'subjects',
    width: 200,
    render: (row) => {
      if (!row.subjects?.length) return '-'
      return row.subjects.map(s => s.name || s.code).join('、')
    },
  },
  { title: '创建时间', key: 'created_at', width: 180 },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) => h(NButton, {
      size: 'small', text: true, type: 'primary',
      onClick: () => router.push(`/joint-exams/${row.id}`),
    }, () => '详情'),
  },
])

async function loadExams() {
  loading.value = true
  try {
    const params = {}
    if (statusFilter.value) params.status = statusFilter.value
    const { data } = await listJointExams(params)
    exams.value = Array.isArray(data) ? data : []
  } catch {
    exams.value = []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  let subjects
  try {
    subjects = JSON.parse(form.value.subjectsText)
  } catch {
    return
  }
  creating.value = true
  try {
    const schoolId = auth.currentRole?.school_id || ''
    await createJointExam({
      name: form.value.name,
      description: form.value.description,
      subjects,
      creator_school_id: schoolId,
    })
    showCreate.value = false
    form.value = { name: '', description: '', subjectsText: '[]' }
    await loadExams()
  } finally {
    creating.value = false
  }
}

onMounted(loadExams)
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-title { font-size: 24px; font-weight: 700; margin: 0; }
.page-subtitle { font-size: 14px; color: var(--color-text-muted); margin: 4px 0 0; }
.filter-bar { display: flex; align-items: center; margin-bottom: 16px; gap: 12px; }
</style>
