<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">选考组合</h1>
        <p class="page-subtitle">管理学校提供的选考科目组合</p>
      </div>
      <n-button type="primary" @click="showCreate = true">新增组合</n-button>
    </div>

    <n-space v-if="selections.length" wrap>
      <n-card v-for="s in selections" :key="s.id" style="width: 280px" :title="s.name" size="small">
        <template #header-extra>
          <n-switch :value="s.is_active" size="small" @update:value="(v) => handleToggle(s.id, v)" />
        </template>
        <n-space>
          <n-tag v-for="code in s.subject_codes" :key="code" type="info" size="small">{{ code }}</n-tag>
        </n-space>
        <n-text depth="3" style="display: block; margin-top: 8px">模式: {{ s.mode }}</n-text>
        <template #action>
          <n-button size="small" type="error" @click="handleDelete(s.id)">删除</n-button>
        </template>
      </n-card>
    </n-space>
    <n-empty v-else description="暂无选考组合" />

    <n-modal v-model:show="showCreate" preset="dialog" title="新增选考组合" positive-text="确认" negative-text="取消"
      @positive-click="handleCreate">
      <n-space vertical>
        <n-input v-model:value="form.name" placeholder="组合名称 (如 物化生)" />
        <n-input v-model:value="form.codes_raw" placeholder="科目代码（逗号分隔，如 physics,chemistry,biology）" />
        <n-select v-model:value="form.mode" :options="modeOptions" placeholder="选考模式" />
      </n-space>
    </n-modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useAuthStore } from '../stores/auth.js'
import { getSelections, createSelection, updateSelection, deleteSelection } from '../api/subjectSelections.js'

const auth = useAuthStore()
const message = useMessage()
const selections = ref([])
const showCreate = ref(false)
const form = ref({ name: '', codes_raw: '', mode: 'custom' })

const modeOptions = [
  { label: '3+1+2', value: '3+1+2' },
  { label: '3+3', value: '3+3' },
  { label: '自定义', value: 'custom' },
]

const schoolId = () => auth.currentRole?.school_id

async function loadData() {
  if (!schoolId()) return
  try {
    const { data } = await getSelections(schoolId())
    selections.value = data
  } catch { message.error('加载失败') }
}

async function handleCreate() {
  try {
    const codes = form.value.codes_raw.split(',').map(s => s.trim()).filter(Boolean)
    await createSelection(schoolId(), { name: form.value.name, subject_codes: codes, mode: form.value.mode })
    message.success('组合创建成功')
    showCreate.value = false
    form.value = { name: '', codes_raw: '', mode: 'custom' }
    await loadData()
  } catch (e) { message.error(e.response?.data?.detail || '创建失败') }
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
