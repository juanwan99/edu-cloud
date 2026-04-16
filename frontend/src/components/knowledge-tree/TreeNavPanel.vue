<template>
  <div class="tree-nav-panel">
    <div class="nav-header">
      <slot name="student-selector" />
      <n-input
        v-model:value="searchQuery"
        placeholder="搜索知识点..."
        clearable
        size="small"
        style="margin-bottom: 8px"
      />
    </div>
    <n-tree
      :data="treeData"
      :expanded-keys="expandedKeys"
      :selected-keys="selectedKeys"
      :pattern="searchQuery"
      :render-suffix="renderSuffix"
      @update:selected-keys="handleSelect"
      @update:expanded-keys="keys => manualExpandedKeys = keys"
      block-line
    />
    <div v-if="weakConcepts.length" class="weak-section">
      <div class="section-title">薄弱概念 Top 5</div>
      <div v-for="c in weakConcepts" :key="c.concept_id" class="weak-item">
        <span>{{ c.name }}</span>
        <span :style="{ color: masteryColor(c.mastery) }">
          {{ Math.round(c.mastery * 100) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, h, watch } from 'vue'
import { NTree, NInput } from 'naive-ui'

const props = defineProps({
  navigation: { type: Array, default: () => [] },
  moduleMastery: { type: Array, default: () => [] },
  nodesWithMastery: { type: Array, default: () => [] },
  selectedModule: { type: String, default: 'all' },
})
const emit = defineEmits(['select-module', 'select-node'])

const searchQuery = ref('')
const manualExpandedKeys = ref(null)

const reviewStatusIcons = {
  ai_draft: '🤖',
  teacher_reviewed: '✅',
  published: '📗',
}

function masteryColor(mastery) {
  if (mastery >= 0.85) return '#22c55e'
  if (mastery >= 0.6) return '#eab308'
  if (mastery >= 0.3) return '#ef4444'
  return '#6b7280'
}

// 从 nodesWithMastery 构建 id→node 映射
const nodeMap = computed(() => {
  const map = {}
  for (const n of props.nodesWithMastery) {
    map[n.id] = n
  }
  return map
})

// 从 navigation 构建三级树
const treeData = computed(() => {
  if (!props.navigation || props.navigation.length === 0) {
    return []
  }
  return props.navigation.map(mod => {
    const modMastery = props.moduleMastery.find(m => m.module === mod.id)
    return {
      key: mod.id,
      label: mod.name,
      mastery: modMastery?.mastery ?? 0,
      children: (mod.big_concepts || []).map(bc => ({
        key: bc.id,
        label: bc.name,
        children: (bc.concept_ids || []).map(cid => {
          const node = nodeMap.value[cid]
          return {
            key: cid,
            label: node?.name || cid,
            isLeaf: true,
            mastery: node?.mastery ?? 0,
            reviewStatus: node?.review_status,
          }
        }),
      })),
    }
  })
})

const expandedKeys = computed(() => {
  if (manualExpandedKeys.value !== null) return manualExpandedKeys.value
  if (props.selectedModule !== 'all') return [props.selectedModule]
  return []
})

// 搜索时清除手动展开状态，让 NTree pattern 自动展开匹配路径
watch(searchQuery, () => {
  manualExpandedKeys.value = null
})

const selectedKeys = computed(() =>
  props.selectedModule !== 'all' ? [props.selectedModule] : []
)

const weakConcepts = computed(() => {
  return [...props.nodesWithMastery]
    .filter(n => n.mastery_state === 'weak' || n.mastery_state === 'fragile')
    .sort((a, b) => a.mastery - b.mastery)
    .slice(0, 5)
    .map(n => ({ concept_id: n.id, name: n.name, mastery: n.mastery }))
})

function renderSuffix({ option }) {
  const parts = []
  if (option.reviewStatus) {
    const icon = reviewStatusIcons[option.reviewStatus] || ''
    if (icon) parts.push(h('span', { style: { fontSize: '12px', marginRight: '4px' } }, icon))
  }
  const m = option.mastery ?? 0
  if (m > 0) {
    parts.push(h('span', {
      style: { color: masteryColor(m), fontSize: '12px' },
    }, Math.round(m * 100) + '%'))
  }
  return parts.length ? h('span', { style: { marginLeft: '4px' } }, parts) : null
}

function handleSelect(keys) {
  if (keys.length > 0) {
    const key = keys[0]
    if (['M1', 'M2', 'M3', 'M4', 'M5'].includes(key)) {
      emit('select-module', key)
    } else if (!key.startsWith('BC_')) {
      // 叶子节点（概念）点击 → 触发节点详情
      const node = nodeMap.value[key]
      if (node) emit('select-node', node)
    }
  }
}
</script>

<style scoped>
.tree-nav-panel {
  height: 100%;
  overflow-y: auto;
  padding: 12px;
}
.nav-header {
  margin-bottom: 12px;
}
.weak-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}
.section-title {
  font-size: 12px;
  color: #888;
  margin-bottom: 8px;
}
.weak-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 4px 0;
}
</style>
