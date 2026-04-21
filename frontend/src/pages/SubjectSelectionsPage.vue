<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">选考组合</h1>
        <p class="page-subtitle">管理学校提供的选考科目组合（新高考 3+1+2）</p>
      </div>
      <n-button type="primary" :disabled="!toAdd.length" @click="handleBatchCreate">
        批量添加 ({{ toAdd.length }})
      </n-button>
    </div>

    <n-spin :show="loading">
      <div class="combo-grid">
        <div v-for="combo in allCombos" :key="combo.name" class="combo-card"
          :class="{ added: combo.exists, checked: combo.checked }"
          @click="toggleCombo(combo)">
          <div class="combo-header">
            <n-checkbox :checked="combo.checked" :disabled="combo.exists" @click.stop
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
        <n-card v-for="s in selections" :key="s.id" style="width: 280px" :title="s.name" size="small">
          <template #header-extra>
            <n-switch :value="s.is_active" size="small" @update:value="(v) => handleToggle(s.id, v)" />
          </template>
          <n-space size="small">
            <n-tag v-for="code in s.subject_codes" :key="code" type="info" size="small">{{ subjectLabel(code) }}</n-tag>
          </n-space>
          <template #action>
            <n-button size="small" type="error" @click="handleDelete(s.id)">删除</n-button>
          </template>
        </n-card>
      </n-space>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { getSelections, createSelection, updateSelection, deleteSelection } from '../api/subjectSelections.js'

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
const message = useMessage()
const selections = ref([])
const loading = ref(false)
const allCombos = ref(generateCombos())

const toAdd = computed(() => allCombos.value.filter(c => c.checked && !c.exists))
const schoolId = () => auth.currentRole?.school_id

function subjectLabel(code) {
  return SUBJECTS[code] || code
}

function toggleCombo(combo) {
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

async function loadData() {
  if (!schoolId()) return
  loading.value = true
  try {
    const { data } = await getSelections(schoolId())
    selections.value = data
    syncExistsState()
  } catch { message.error('加载失败') }
  loading.value = false
}

async function handleBatchCreate() {
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
  try {
    await updateSelection(schoolId(), id, { is_active: active })
    await loadData()
  } catch { message.error('操作失败') }
}

async function handleDelete(id) {
  try {
    await deleteSelection(schoolId(), id)
    message.success('已删除')
    await loadData()
  } catch { message.error('删除失败') }
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
  transition: all 0.15s;
}
.combo-card:hover:not(.added) { border-color: #63e2b7; }
.combo-card.checked { border-color: #63e2b7; background: rgba(99, 226, 183, 0.08); }
.combo-card.added { opacity: 0.5; cursor: default; }
.combo-header { display: flex; align-items: center; gap: 8px; }
.combo-name { font-weight: 500; flex: 1; }
</style>
