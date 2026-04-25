<template>
  <div>
    <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
      <div>
        <h1 class="page-title">学校管理</h1>
        <p class="page-subtitle">管理系统中的学校信息</p>
      </div>
      <n-button type="primary" class="btn-pill" @click="showCreate = true">添加学校</n-button>
    </div>

    <n-data-table :columns="columns" :data="schools" :loading="loading" />

    <n-modal v-model:show="showCreate" preset="dialog" title="添加学校" positive-text="添加"
      negative-text="取消" :positive-button-props="{ class: 'btn-pill' }"
      :negative-button-props="{ class: 'btn-pill' }" @positive-click="handleCreate">
      <n-form :model="form" label-placement="top">
        <n-form-item label="学校名称">
          <n-input v-model:value="form.name" placeholder="例如：第一中学" />
        </n-form-item>
        <n-form-item label="学校代码">
          <n-input v-model:value="form.code" placeholder="例如：SCHOOL01" />
        </n-form-item>
        <n-form-item label="学区">
          <n-input v-model:value="form.district" placeholder="例如：河源市源城区" />
        </n-form-item>
      </n-form>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { listSchools, createSchool } from '../api/schools'

const message = useMessage()
const loading = ref(true)
const schools = ref([])
const showCreate = ref(false)
const form = reactive({ name: '', code: '', district: '' })

const columns = [
  { title: '学校名称', key: 'name' },
  { title: '学校代码', key: 'code', width: 150 },
  {
    title: '创建时间', key: 'created_at', width: 140,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleDateString('zh-CN') : '-',
  },
]

async function loadSchools() {
  loading.value = true
  try {
    const { data } = await listSchools()
    schools.value = data
  } catch { /* interceptor */ }
  loading.value = false
}

async function handleCreate() {
  if (!form.name || !form.code || !form.district) { message.warning('请填写完整'); return false }
  try {
    await createSchool({ name: form.name, code: form.code, district: form.district })
    message.success('学校添加成功')
    form.name = ''
    form.code = ''
    form.district = ''
    showCreate.value = false
    await loadSchools()
  } catch (e) {
    message.error(e.response?.data?.detail || '添加失败')
    return false
  }
}

onMounted(loadSchools)
</script>
