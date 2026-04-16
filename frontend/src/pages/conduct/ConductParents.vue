<template>
  <div>
    <n-page-header title="家长管理" subtitle="查看和管理已注册家长" style="margin-bottom: 16px;" />

    <n-alert v-if="!classId" type="warning" title="未选择班级" style="margin-bottom: 16px;">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <n-card v-if="classId">
      <n-spin :show="loading">
        <n-data-table
          :columns="columns"
          :data="parents"
          :pagination="{ pageSize: 20 }"
          size="small"
        />
      </n-spin>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import {
  NPageHeader, NCard, NDataTable, NSpin, NButton, NPopconfirm,
  NAlert, NTag, useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import { getParentsList, removeParent } from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const parents = ref([])
const loading = ref(false)

const columns = [
  { title: '姓名', key: 'display_name', width: 120 },
  { title: '手机号', key: 'phone', width: 140 },
  {
    title: '绑定学生',
    key: 'children',
    render: (row) => {
      const children = row.children || row.bound_students || []
      if (children.length === 0) return '-'
      return h('span', {}, children.map(c => c.student_name || c.name).join('、'))
    },
  },
  {
    title: '注册时间',
    key: 'created_at',
    width: 160,
    render: (row) => row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render: (row) => h(NPopconfirm, {
      onPositiveClick: () => handleRemove(row.user_id || row.id),
    }, {
      trigger: () => h(NButton, { size: 'tiny', quaternary: true, type: 'error' }, () => '移除'),
      default: () => `确定移除家长「${row.display_name || ''}」？此操作将解除所有绑定关系。`,
    }),
  },
]

async function loadParents() {
  if (!classId.value) return
  loading.value = true
  try {
    const res = await getParentsList(classId.value)
    parents.value = res.data.parents || res.data || []
  } catch {
    parents.value = []
  } finally {
    loading.value = false
  }
}

async function handleRemove(userId) {
  try {
    await removeParent(classId.value, userId)
    message.success('家长已移除')
    await loadParents()
  } catch (e) {
    message.error(e.response?.data?.detail || '移除失败')
  }
}

onMounted(() => {
  if (classId.value) loadParents()
})
</script>
