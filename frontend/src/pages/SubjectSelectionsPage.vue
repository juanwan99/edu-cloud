<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">选考组合</h1>
        <p class="page-subtitle">管理学校提供的选考科目组合（新高考 3+1+2）</p>
      </div>
      <n-button v-if="canManageScheduling" type="primary" :disabled="!toAdd.length" @click="handleBatchCreate">
        批量添加 ({{ toAdd.length }})
      </n-button>
    </div>

    <!-- 统计摘要 -->
    <div v-if="selections.length" class="stats-row">
      <div class="stat-card">
        <div class="stat-label">已启用组合</div>
        <div class="stat-value">{{ activeCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">总组合数</div>
        <div class="stat-value">{{ selections.length }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已分配学生</div>
        <div class="stat-value">{{ totalAssigned }}</div>
      </div>
    </div>

    <n-spin :show="loading">
      <div class="combo-grid">
        <div v-for="combo in allCombos" :key="combo.name" class="combo-card"
          :class="{ added: combo.exists, checked: combo.checked }"
          @click="toggleCombo(combo)">
          <div class="combo-header">
            <n-checkbox :checked="combo.checked" :disabled="!canManageScheduling || combo.exists" @click.stop
              @update:checked="(v) => combo.checked = v" />
            <span class="combo-name">{{ combo.name }}</span>
            <n-tag v-if="combo.exists" type="success" size="small" :bordered="false">已添加</n-tag>
          </div>
          <n-space size="small" style="margin-top: 6px">
            <n-tag v-for="label in combo.labels" :key="label" size="small" :type="combo.exists ? 'default' : 'info'">
              {{ label }}
            </n-tag>
          </n-space>
        </div>
      </div>
    </n-spin>

    <div v-if="selections.length" style="margin-top: 24px">
      <h2 style="font-size: 16px; margin-bottom: 12px">已添加的组合</h2>
      <n-space wrap>
        <n-card v-for="s in selections" :key="s.id" style="width: 300px" :title="s.name" size="small">
          <template #header-extra>
            <n-space :size="8" align="center">
              <n-tag :type="modeTagType(s.mode)" size="small">{{ s.mode }}</n-tag>
              <n-switch :value="s.is_active" size="small" :disabled="!canManageScheduling" @update:value="(v) => handleToggle(s.id, v)" />
            </n-space>
          </template>
          <n-space size="small" align="center">
            <n-tag v-for="code in s.subject_codes" :key="code" type="info" size="small">{{ subjectLabel(code) }}</n-tag>
            <n-tag v-if="studentCounts[s.id] != null" size="small" :bordered="false">
              {{ studentCounts[s.id] }} 人
            </n-tag>
          </n-space>
          <template #action>
            <n-space v-if="canManageScheduling" :size="8">
              <n-button size="small" @click="openEdit(s)">编辑</n-button>
              <n-popconfirm @positive-click="handleDelete(s.id)">
                <template #trigger>
                  <n-button size="small" type="error">删除</n-button>
                </template>
                确定删除组合「{{ s.name }}」吗？
              </n-popconfirm>
            </n-space>
          </template>
        </n-card>
      </n-space>
    </div>

    <!-- 编辑名称弹窗 -->
    <n-modal v-model:show="editVisible" preset="dialog" title="编辑组合名称" positive-text="保存" negative-text="取消"
      :loading="editSaving" @positive-click="handleEditSave">
      <n-input v-model:value="editName" placeholder="请输入组合名称" />
    </n-modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'
import { getSelections, createSelection, updateSelection, deleteSelection } from '../api/subjectSelections.js'
import { listStudents } from '../api/students.js'

const SUBJECTS = {
  physics: '物理', history: '历史',
  chemistry: '化学', biology: '生物', politics: '政治', geography: '地理',
}

const FIRST_CHOICES = ['physics', 'history']
const SECOND_CHOICES = ['chemistry', 'biology', 'politics', 'geography']

function generateCombos() {
  const combos = []
  for (const first of FIRST_CHOICES) {
    for (let i = 0; i < SECOND_CHOICES.length; i++) {
      for (let j = i + 1; j < SECOND_CHOICES.length; j++) {
        const codes = [first, SECOND_CHOICES[i], SECOND_CHOICES[j]]
        const labels = codes.map(c => SUBJECTS[c])
        combos.push({ name: labels.join(''), codes, labels, checked: false, exists: false })
      }
    }
  }
  return combos
}

const auth = useAuthStore()
const normalizedRole = computed(() => normalizeRole(auth.currentRole?.role || ''))
const canManageScheduling = computed(() => hasPermission(normalizedRole.value, 'manage_scheduling'))
const message = useMessage()
const selections = ref([])
const loading = ref(false)
const allCombos = ref(generateCombos())
const studentCounts = ref({})

// Edit state
const editVisible = ref(false)
const editSaving = ref(false)
const editId = ref(null)
const editName = ref('')

const toAdd = computed(() => allCombos.value.filter(c => c.checked && !c.exists))
const schoolId = () => auth.currentRole?.school_id

const activeCount = computed(() => selections.value.filter(s => s.is_active).length)
const totalAssigned = computed(() => Object.values(studentCounts.value).reduce((sum, n) => sum + n, 0))

function modeTagType(mode) {
  if (mode === '3+1+2') return 'success'
  if (mode === '3+3') return 'info'
  return 'warning'
}

function subjectLabel(code) {
  return SUBJECTS[code] || code
}

function toggleCombo(combo) {
  if (!canManageScheduling.value) return
  if (combo.exists) return
  combo.checked = !combo.checked
}

function syncExistsState() {
  const existingNames = new Set(selections.value.map(s => s.name))
  for (const combo of allCombos.value) {
    combo.exists = existingNames.has(combo.name)
    if (combo.exists) combo.checked = false
  }
}

async function loadStudentCounts() {
  const counts = {}
  const promises = selections.value.map(async (s) => {
    try {
      const { data } = await listStudents({ selection_id: s.id })
      counts[s.id] = Array.isArray(data) ? data.length : 0
    } catch {
      counts[s.id] = 0
    }
  })
  await Promise.all(promises)
  studentCounts.value = counts
}

async function loadData() {
  if (!schoolId()) return
  loading.value = true
  try {
    const { data } = await getSelections(schoolId())
    selections.value = data
    syncExistsState()
    loadStudentCounts()
  } catch { message.error('加载失败') }
  loading.value = false
}

async function handleBatchCreate() {
  if (!canManageScheduling.value) return
  const items = toAdd.value
  if (!items.length) return
  loading.value = true
  let ok = 0
  for (const combo of items) {
    try {
      await createSelection(schoolId(), { name: combo.name, subject_codes: combo.codes, mode: '3+1+2' })
      ok++
    } catch (e) { message.error(`${combo.name}: ${e.response?.data?.detail || '创建失败'}`) }
  }
  if (ok) message.success(`成功添加 ${ok} 个组合`)
  await loadData()
  loading.value = false
}

async function handleToggle(id, active) {
  if (!canManageScheduling.value) return
  try {
    await updateSelection(schoolId(), id, { is_active: active })
    await loadData()
  } catch { message.error('操作失败') }
}

async function handleDelete(id) {
  if (!canManageScheduling.value) return
  try {
    await deleteSelection(schoolId(), id)
    message.success('已删除')
    await loadData()
  } catch { message.error('删除失败') }
}

function openEdit(s) {
  if (!canManageScheduling.value) return
  editId.value = s.id
  editName.value = s.name
  editVisible.value = true
}

async function handleEditSave() {
  if (!canManageScheduling.value) return false
  if (!editName.value.trim()) {
    message.warning('名称不能为空')
    return false
  }
  editSaving.value = true
  try {
    await updateSelection(schoolId(), editId.value, { name: editName.value.trim() })
    message.success('已更新')
    editVisible.value = false
    await loadData()
  } catch (e) {
    message.error(e.response?.data?.detail || '更新失败')
  }
  editSaving.value = false
}

onMounted(loadData)
</script>

<style scoped>
.combo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.combo-card {
  padding: 10px 12px;
  border: 1px solid #333;
  border-radius: 6px;
  cursor: pointer;
  transition: transform 0.15s ease-out, box-shadow 0.15s ease-out;
}
.combo-card:hover:not(.added) { border-color: #F4DA4C; }
.combo-card.checked { border-color: #F4DA4C; background: rgba(100, 76, 240, 0.08); }
.combo-card.added { opacity: 0.5; cursor: default; }
.combo-header { display: flex; align-items: center; gap: 8px; }
.combo-name { font-weight: var(--fw-medium); flex: 1; }
</style>
