<template>
  <div class="exam-items-tab">
    <div v-if="loading" class="loading">加载中…</div>
    <div v-else-if="total === 0" class="empty">该概念暂无关联高考真题</div>
    <div v-else>
      <div class="summary">共 {{ total }} 道关联题，显示第 {{ (page-1)*pageSize + 1 }}-{{ Math.min(page*pageSize, total) }} 条</div>
      <div class="item-list">
        <div v-for="item in items" :key="item.id" class="item">
          <div class="item-header">
            <span class="type-tag">{{ itemTypeLabel(item.question_type) }}</span>
            <span class="exam-year">{{ formatExamId(item.exam_id) }}</span>
            <span v-if="item.score != null" class="score">分值: {{ item.score }} 分</span>
          </div>
          <div class="item-stem">{{ truncate(item.stem, 200) }}</div>
          <details v-if="item.answer || item.explanation" class="item-detail">
            <summary>查看答案与解析</summary>
            <div v-if="item.answer" class="answer">答案: {{ item.answer }}</div>
            <div v-if="item.explanation" class="explanation">解析: {{ item.explanation }}</div>
          </details>
        </div>
      </div>
      <div class="pagination">
        <n-button :disabled="page <= 1" @click="prevPage" size="small">上一页</n-button>
        <span>{{ page }} / {{ totalPages }}</span>
        <n-button :disabled="page >= totalPages" @click="nextPage" size="small">下一页</n-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { NButton } from 'naive-ui'
import { getExamItems } from '../../api/knowledgeTree'

const props = defineProps({
  nodeId: { type: String, required: true },
})

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const loading = ref(false)

let fetchSeq = 0

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

async function load() {
  if (!props.nodeId) return
  const mySeq = ++fetchSeq
  loading.value = true
  try {
    const data = await getExamItems(props.nodeId, page.value, pageSize.value)
    if (mySeq !== fetchSeq) return
    items.value = data.items || []
    total.value = data.total || 0
  } catch (e) {
    if (mySeq !== fetchSeq) return
    items.value = []
    total.value = 0
  } finally {
    if (mySeq === fetchSeq) loading.value = false
  }
}

function prevPage() { if (page.value > 1) { page.value--; load() } }
function nextPage() { if (page.value < totalPages.value) { page.value++; load() } }

watch(() => props.nodeId, () => { page.value = 1; load() }, { immediate: true })

function truncate(text, n) {
  if (!text) return ''
  return text.length > n ? text.slice(0, n) + '…' : text
}
function itemTypeLabel(type) {
  return { single_choice: '单选', multiple_choice: '多选', non_choice: '主观题' }[type] || type
}
function formatExamId(examId) {
  const m = /GK_(\d{4})_([A-Z]+)/.exec(examId || '')
  return m ? `${m[1]} ${m[2]}` : examId
}
</script>

<style scoped>
.exam-items-tab { padding: var(--space-2); }
.loading, .empty { text-align: center; color: var(--text-color-3); padding: var(--space-5); }
.summary { font-size: var(--fs-base); color: var(--text-color-2); margin-bottom: 10px; }
.item { border: 1px solid var(--border-color); border-radius: var(--r-xs); padding: 10px; margin-bottom: 8px; }
.item-header { display: flex; gap: 8px; margin-bottom: 6px; font-size: var(--fs-base); }
.type-tag { background: var(--primary-color-hover); color: white; padding: 2px 6px; border-radius: 3px; }
.exam-year { color: var(--text-color-2); }
.score { color: var(--text-color-3); }
.item-stem { font-size: var(--fs-base); line-height: 1.5; }
.item-detail { margin-top: var(--space-2); }
.item-detail summary { cursor: pointer; font-size: var(--fs-base); color: var(--primary-color); }
.answer { margin-top: 6px; color: var(--success-color); font-size: var(--fs-base); }
.explanation { margin-top: 4px; color: var(--text-color-2); font-size: var(--fs-base); }
.pagination { display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: var(--space-3); }
</style>
