<template>
  <n-spin :show="loading">
    <div v-if="!modelValue || modelValue.length === 0" class="re-empty">暂无评分细则</div>
    <div v-else>
      <div v-for="(item, idx) in modelValue" :key="idx" class="re-row">
        <div class="re-head">
          <span class="re-idx">{{ item.subQ || item.blankNo || idx + 1 }}</span>
          <n-input size="small" :value="item.standardAnswer || item.answer" placeholder="标准答案"
            style="flex:1" @update:value="v => update(idx, 'standardAnswer', v)" />
          <n-input-number size="tiny" :value="item.score" :min="0" :max="200" :step="0.5"
            style="width:68px" @update:value="v => update(idx, 'score', v)" />
          <span class="re-unit">分</span>
          <a class="re-del" @click="removeItem(idx)">✕</a>
        </div>
        <n-input v-if="item.context || expanded === idx" size="small" type="textarea"
          :value="item.context" placeholder="背景与逻辑：题目情境 + 推理链"
          :autosize="{ minRows: 1, maxRows: 4 }"
          @update:value="v => update(idx, 'context', v)" />
        <n-input v-if="item.judgingRules || expanded === idx" size="small" type="textarea"
          :value="item.judgingRules" placeholder="判分规则：满分/部分分/0分条件 + 典型错误"
          :autosize="{ minRows: 1, maxRows: 4 }"
          @update:value="v => update(idx, 'judgingRules', v)" />
        <a v-if="!item.context && !item.judgingRules && expanded !== idx"
          class="re-more" @click="expanded = idx">展开详细</a>
        <div v-if="hasLegacyFields(item)" class="re-legacy">
          <span v-if="item.intent">意图: {{ item.intent }}</span>
          <span v-if="item.coreRequirement">要求: {{ item.coreRequirement }}</span>
        </div>
      </div>
      <div class="re-foot">
        <a class="re-add" @click="addItem">+ 添加</a>
        <span class="re-total" :class="{ warn: totalScore !== maxScore }">
          {{ totalScore }}/{{ maxScore }}
        </span>
      </div>
    </div>
  </n-spin>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NSpin, NInput, NInputNumber } from 'naive-ui'

const props = defineProps({ modelValue: Array, maxScore: Number, loading: Boolean })
const emit = defineEmits(['update:modelValue'])
const expanded = ref(null)

const totalScore = computed(() =>
  (props.modelValue || []).reduce((s, i) => s + (Number(i.score) || 0), 0)
)

function hasLegacyFields(item) {
  return (item.intent || item.coreRequirement) && !item.context && !item.judgingRules
}

function update(idx, field, value) {
  const items = [...props.modelValue]
  items[idx] = { ...items[idx], [field]: value }
  emit('update:modelValue', items)
}

function removeItem(idx) {
  const items = [...props.modelValue]
  items.splice(idx, 1)
  emit('update:modelValue', items)
  if (expanded.value === idx) expanded.value = null
}

function addItem() {
  const items = [...(props.modelValue || [])]
  const n = items.length ? Math.max(...items.map(i => parseInt(i.blankNo) || 0)) + 1 : 1
  items.push({ subQ: '', blankNo: String(n), score: 1, standardAnswer: '', context: '', judgingRules: '' })
  emit('update:modelValue', items)
  expanded.value = items.length - 1
}
</script>

<style scoped>
.re-empty { color: #8a9a8e; font-size: 13px; padding: 12px 0; text-align: center; }

.re-row {
  display: flex; flex-direction: column; gap: 4px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, #2e3e34);
}
.re-row:last-of-type { border-bottom: none; }

.re-head { display: flex; align-items: center; gap: 6px; }

.re-idx {
  font-size: 13px; font-weight: 700; color: #6ee7a0;
  min-width: 20px; text-align: center; flex-shrink: 0;
}
.re-unit { font-size: 12px; color: #8a9a8e; flex-shrink: 0; }
.re-del {
  font-size: 12px; color: #8a9a8e; cursor: pointer; flex-shrink: 0;
  opacity: 0.3; transition: opacity 0.15s; text-decoration: none;
}
.re-del:hover { opacity: 1; color: #f87171; }

.re-more {
  font-size: 11px; color: #5a7a60; cursor: pointer;
  padding: 2px 0; text-decoration: none;
}
.re-more:hover { color: #6ee7a0; }

.re-legacy {
  display: flex; flex-direction: column; gap: 2px;
  font-size: 11px; color: #6a7a6e; line-height: 1.4;
  padding-left: 20px; opacity: 0.6;
}

.re-foot {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 0 0;
}
.re-add { font-size: 12px; color: #5a7a60; cursor: pointer; text-decoration: none; }
.re-add:hover { color: #6ee7a0; }

.re-total { font-size: 13px; font-weight: 600; color: #8a9a8e; }
.re-total.warn { color: #f59e0b; }
</style>
