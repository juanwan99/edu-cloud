<template>
  <div class="ref-backdrop" @click.self="$emit('close')">
    <div class="ref-picker">
      <div class="ref-tabs">
        <button v-for="t in types" :key="t.type_code"
                :class="['ref-tab', { active: activeType === t.type_code }]"
                @click="switchType(t.type_code)">
          {{ t.label }}
        </button>
      </div>

      <div class="ref-search">
        <input v-model="searchText" type="text" placeholder="搜索..." @input="onSearch" />
      </div>

      <div class="ref-list">
        <div v-for="item in items" :key="item.id"
             :class="['ref-item', { selected: selectedId === item.id }]"
             @click="selectItem(item)">
          <span class="ref-item-label">{{ item.label }}</span>
          <span v-if="item.subtitle" class="ref-item-sub">{{ item.subtitle }}</span>
        </div>
        <div v-if="!items.length && !loading" class="ref-empty">暂无数据</div>
        <div v-if="loading" class="ref-loading">加载中...</div>
      </div>

      <div v-if="children.length" class="ref-children">
        <div class="ref-children-label">选择{{ childLabel }}（可选）</div>
        <div v-for="c in children" :key="c.id"
             :class="['ref-item ref-child', { selected: selectedChildId === c.id }]"
             @click="selectedChildId = selectedChildId === c.id ? null : c.id">
          <span class="ref-item-label">{{ c.label }}</span>
          <span v-if="c.subtitle" class="ref-item-sub">{{ c.subtitle }}</span>
        </div>
      </div>

      <div class="ref-footer">
        <button class="ref-confirm" :disabled="!selectedId" @click="confirm">确定引用</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getRefTypes, getRefs } from '../../api/ai.js'

const emit = defineEmits(['select', 'close'])

const types = ref([])
const activeType = ref('')
const items = ref([])
const children = ref([])
const searchText = ref('')
const selectedId = ref(null)
const selectedChildId = ref(null)
const loading = ref(false)
const childLabel = ref('')

let searchTimer = null

onMounted(async () => {
  const { data } = await getRefTypes()
  types.value = data
  if (data.length) switchType(data[0].type_code)
})

async function switchType(code) {
  activeType.value = code
  searchText.value = ''
  selectedId.value = null
  selectedChildId.value = null
  children.value = []
  await loadItems()
}

async function loadItems(search) {
  loading.value = true
  try {
    const { data } = await getRefs(activeType.value, { search, limit: 30 })
    items.value = data.items
  } finally {
    loading.value = false
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => loadItems(searchText.value || undefined), 300)
}

async function selectItem(item) {
  selectedId.value = item.id
  selectedChildId.value = null
  children.value = []
  if (item.children_type) {
    childLabel.value = types.value.find(t => t.type_code === item.children_type)?.label || ''
    const { data } = await getRefs(item.children_type, { parentId: item.id, limit: 30 })
    children.value = data.items
  }
}

function confirm() {
  const item = items.value.find(i => i.id === selectedId.value)
  if (!item) return
  const result = { type: activeType.value, id: item.id, label: item.label }
  if (selectedChildId.value) {
    const child = children.value.find(c => c.id === selectedChildId.value)
    if (child) {
      const childType = types.value.find(t => t.type_code === activeType.value)?.children_type
      result.label += ` · ${child.label}`
      result.children = [{ type: childType, id: child.id, label: child.label }]
    }
  }
  emit('select', result)
}
</script>

<style scoped>
.ref-backdrop {
  position: fixed;
  inset: 0;
  z-index: calc(var(--z-modal) + 1);
  background: rgba(0, 0, 0, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.ref-picker {
  background: var(--color-bg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  width: 340px;
  max-height: 480px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.ref-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.ref-tab {
  flex: 1;
  padding: 10px 4px;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--color-text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: var(--transition);
}

.ref-tab.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: var(--fw-semibold);
}

.ref-search {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.ref-search input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
  background: var(--color-bg-alt);
  color: var(--color-text);
}

.ref-search input:focus {
  border-color: var(--color-primary);
}

.ref-list {
  flex: 1;
  overflow-y: auto;
  max-height: 200px;
}

.ref-item {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  transition: background 0.15s;
}

.ref-item:hover { background: var(--color-bg-alt); }
.ref-item.selected { background: rgba(100, 76, 240, 0.08); color: var(--color-primary); }

.ref-item-label { font-weight: var(--fw-medium); }
.ref-item-sub { font-size: 12px; color: var(--color-text-secondary); }

.ref-children {
  border-top: 1px solid var(--color-border-light);
  max-height: 150px;
  overflow-y: auto;
}

.ref-children-label {
  padding: 6px 12px;
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: var(--fw-semibold);
}

.ref-empty, .ref-loading {
  padding: 20px;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.ref-footer {
  padding: 8px 12px;
  border-top: 1px solid var(--color-border-light);
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

.ref-confirm {
  padding: 6px 16px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 13px;
  cursor: pointer;
  transition: var(--transition);
}

.ref-confirm:hover:not(:disabled) { opacity: 0.9; }
.ref-confirm:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
