<template>
  <n-spin :show="loading">
    <div v-if="!modelValue || modelValue.length === 0" class="empty">暂无评分细则</div>
    <div v-else class="rubric-list">
      <div v-for="(item, idx) in modelValue" :key="idx" class="rubric-item">
        <div class="rubric-top">
          <span class="blank-badge">{{ item.subQ || item.blankNo || idx + 1 }}</span>
          <div class="score-pill">
            <n-input-number size="tiny" :value="item.score" :min="0" :max="200" :step="0.5"
              style="width:64px" @update:value="v => update(idx, 'score', v)" />
            <span class="score-unit">分</span>
          </div>
          <n-input size="small" :value="item.standardAnswer || item.answer" placeholder="标准答案"
            style="flex:1" @update:value="v => update(idx, 'standardAnswer', v)" />
          <n-button size="tiny" quaternary type="error" @click="removeItem(idx)" style="flex-shrink:0">
            <template #icon><span style="font-size:14px">✕</span></template>
          </n-button>
        </div>

        <div class="rubric-fields">
          <div class="field-group">
            <div class="field-label">背景与逻辑</div>
            <n-input size="small" type="textarea" :value="item.context"
              placeholder="题目情境 + 从题目信息到答案的推理链（让阅卷AI理解为什么这是正确答案）"
              :autosize="{ minRows: 1, maxRows: 5 }"
              @update:value="v => update(idx, 'context', v)" />
          </div>
          <div class="field-group">
            <div class="field-label">判分规则</div>
            <n-input size="small" type="textarea" :value="item.judgingRules"
              placeholder="满分条件 → 部分分条件 → 0分条件 → 典型错误/排除规则"
              :autosize="{ minRows: 1, maxRows: 5 }"
              @update:value="v => update(idx, 'judgingRules', v)" />
          </div>
        </div>

        <div v-if="hasLegacyFields(item)" class="rubric-fields legacy">
          <div v-if="item.intent" class="field-group">
            <div class="field-label">考查意图 <span class="legacy-tag">旧</span></div>
            <div class="legacy-text">{{ item.intent }}</div>
          </div>
          <div v-if="item.coreRequirement" class="field-group">
            <div class="field-label">得分要求 <span class="legacy-tag">旧</span></div>
            <div class="legacy-text">{{ item.coreRequirement }}</div>
          </div>
        </div>
      </div>

      <div class="rubric-footer">
        <n-button size="small" dashed @click="addItem" style="font-size:13px">+ 添加评分项</n-button>
        <div class="total-bar">
          <span class="total-label">总分</span>
          <span class="total-num" :class="{ mismatch: totalScore !== maxScore }">
            {{ totalScore }} / {{ maxScore }}
          </span>
          <span v-if="totalScore !== maxScore" class="mismatch-warn">不匹配</span>
          <span v-else class="match-ok">✓</span>
        </div>
      </div>
    </div>
  </n-spin>
</template>

<script setup>
import { computed } from 'vue'
import { NSpin, NInput, NInputNumber, NButton } from 'naive-ui'

const props = defineProps({
  modelValue: Array,
  maxScore: Number,
  loading: Boolean,
})

const emit = defineEmits(['update:modelValue'])

const totalScore = computed(() => {
  if (!props.modelValue) return 0
  return props.modelValue.reduce((sum, item) => sum + (Number(item.score) || 0), 0)
})

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
}

function addItem() {
  const items = [...(props.modelValue || [])]
  const nextNum = items.length ? Math.max(...items.map(i => parseInt(i.blankNo) || 0)) + 1 : 1
  items.push({ subQ: '', blankNo: String(nextNum), score: 1, standardAnswer: '', context: '', judgingRules: '' })
  emit('update:modelValue', items)
}
</script>

<style scoped>
.empty {
  color: #8a9a8e;
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
}

.rubric-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rubric-item {
  padding: 10px 12px;
  border: 1px solid var(--border-color, #2e3e34);
  border-radius: 10px;
  background: var(--body-color, #1a2220);
  transition: border-color 0.15s;
}
.rubric-item:hover {
  border-color: #4a6a50;
}

.rubric-top {
  display: flex;
  align-items: center;
  gap: 8px;
}

.blank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  padding: 0 6px;
  border-radius: 6px;
  background: #1a3020;
  color: #4ade80;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.score-pill {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.score-unit {
  font-size: 12px;
  color: #8a9a8e;
}

.rubric-fields {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--border-color, #2e3e34);
}
.rubric-fields.legacy {
  border-top-style: dotted;
  opacity: 0.7;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.field-label {
  font-size: 11px;
  font-weight: 600;
  color: #6a8a70;
  display: flex;
  align-items: center;
  gap: 4px;
}

.legacy-tag {
  font-size: 9px;
  padding: 0 4px;
  border-radius: 3px;
  background: #3a3a0a;
  color: #d4a017;
}

.legacy-text {
  font-size: 12px;
  color: #8a9a8e;
  line-height: 1.5;
  white-space: pre-wrap;
}

.rubric-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 4px;
}

.total-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}
.total-label {
  font-size: 12px;
  color: #8a9a8e;
}
.total-num {
  font-size: 14px;
  font-weight: 700;
  color: #4ade80;
}
.total-num.mismatch {
  color: #f59e0b;
}
.mismatch-warn {
  font-size: 11px;
  color: #f59e0b;
  font-weight: 500;
}
.match-ok {
  font-size: 14px;
  color: #4ade80;
  font-weight: 700;
}
</style>
