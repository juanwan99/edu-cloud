<template>
  <div>

    <n-alert v-if="!classId" type="warning" title="未选择班级" class="section-gap">
      当前角色未关联班级，请切换到班主任角色。
    </n-alert>

    <template v-if="classId">
      <!-- Invite code section -->
      <n-card size="small" class="section-gap">
        <n-space align="center" :size="12">
          <span class="text-secondary">班级邀请码：</span>
          <n-tag size="large" :bordered="false" class="code-tag">
            {{ inviteCode || '未生成' }}
          </n-tag>
          <n-button size="small" @click="copyInviteLink" :disabled="!inviteCode">复制邀请链接</n-button>
          <n-button size="small" :loading="regenerating" @click="handleRegenerate">重新生成</n-button>
        </n-space>
      </n-card>

      <!-- Stat cards -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-label">已注册家长数</div>
          <div class="stat-value">{{ parents.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">已绑定学生数</div>
          <div class="stat-value">{{ boundStudentCount }}</div>
        </div>
      </div>

      <!-- Search + Batch actions -->
      <n-card>
        <template #header>
          <n-space align="center" justify="space-between" class="full-width">
            <n-input
              v-model:value="searchText"
              placeholder="搜索姓名或手机号"
              clearable
              class="search-input"
            />
            <n-space v-if="checkedKeys.length > 0" :size="8">
              <span class="text-secondary">已选 {{ checkedKeys.length }} 项</span>
              <n-popconfirm @positive-click="handleBatchRemove">
                <template #trigger>
                  <n-button size="small" type="error">批量移除</n-button>
                </template>
                确定移除已选的 {{ checkedKeys.length }} 位家长？此操作将解除所有绑定关系。
              </n-popconfirm>
            </n-space>
          </n-space>
        </template>

        <n-spin :show="loading">
          <n-data-table
            :columns="columns"
            :data="filteredParents"
            :pagination="{ pageSize: 20 }"
            :row-key="rowKey"
            v-model:checked-row-keys="checkedKeys"
            size="small"
          />
        </n-spin>
      </n-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import {
  NPageHeader, NCard, NDataTable, NSpin, NButton, NPopconfirm,
  NAlert, NTag, NInput, NSpace,
  useMessage,
} from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import {
  getParentsList, removeParent,
  getConductConfig, regenerateInviteCode,
} from '../../api/conduct'

const auth = useAuthStore()
const message = useMessage()

const classId = computed(() => auth.currentRole?.class_ids?.[0] || null)

const parents = ref([])
const loading = ref(false)
const searchText = ref('')
const checkedKeys = ref([])
const inviteCode = ref('')
const regenerating = ref(false)

const rowKey = (row) => row.user_id || row.id

const boundStudentCount = computed(() => {
  const ids = new Set()
  parents.value.forEach((p) => {
    const children = p.children || p.bound_students || []
    children.forEach((c) => {
      ids.add(c.student_id || c.id || c.student_name)
    })
  })
  return ids.size
})

const filteredParents = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  if (!q) return parents.value
  return parents.value.filter((p) => {
    const name = (p.display_name || '').toLowerCase()
    const phone = (p.phone || '').toLowerCase()
    return name.includes(q) || phone.includes(q)
  })
})

const columns = [
  { type: 'selection' },
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
    title: '绑定学生数',
    key: 'bound_count',
    width: 100,
    render: (row) => {
      const count = (row.children || row.bound_students || []).length
      return h(NTag, { size: 'small', type: count > 0 ? 'success' : 'default', bordered: false }, () => count)
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

async function loadInviteCode() {
  if (!classId.value) return
  try {
    const res = await getConductConfig(classId.value)
    inviteCode.value = res.data.invite_code || ''
  } catch {
    inviteCode.value = ''
  }
}

async function handleRegenerate() {
  if (!classId.value) return
  regenerating.value = true
  try {
    const res = await regenerateInviteCode(classId.value)
    inviteCode.value = res.data.invite_code || res.data.code || inviteCode.value
    message.success('邀请码已刷新')
  } catch (e) {
    message.error(e.response?.data?.detail || '刷新失败')
  } finally {
    regenerating.value = false
  }
}

function copyInviteLink() {
  if (!inviteCode.value) return
  const link = `${window.location.origin}/parent/register?code=${inviteCode.value}`
  navigator.clipboard.writeText(link).then(() => {
    message.success('邀请链接已复制')
  }).catch(() => {
    message.error('复制失败，请手动复制')
  })
}

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
    checkedKeys.value = checkedKeys.value.filter((k) => k !== userId)
    await loadParents()
  } catch (e) {
    message.error(e.response?.data?.detail || '移除失败')
  }
}

async function handleBatchRemove() {
  if (checkedKeys.value.length === 0) return
  const keys = [...checkedKeys.value]
  let successCount = 0
  for (const userId of keys) {
    try {
      await removeParent(classId.value, userId)
      successCount++
    } catch {
      // continue with remaining
    }
  }
  message.success(`已移除 ${successCount} 位家长`)
  checkedKeys.value = []
  await loadParents()
}

onMounted(() => {
  if (classId.value) {
    loadParents()
    loadInviteCode()
  }
})
</script>

<style scoped>
.section-gap {
  margin-bottom: var(--space-4);
}

.text-secondary {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.5);
}

.code-tag {
  font-family: monospace;
  font-size: var(--fs-base);
}

.full-width {
  width: 100%;
}

.search-input {
  width: 240px;
}
</style>
