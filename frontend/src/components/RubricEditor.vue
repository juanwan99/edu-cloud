<template>
  <n-spin :show="loading">
    <div v-if="!modelValue || modelValue.length === 0" class="empty">暂无评分细则</div>
    <div v-else>
      <div v-for="(item, idx) in modelValue" :key="idx" class="rubric-item">
        <div class="rubric-row">
          <n-input size="small" :value="item.blankNo" placeholder="序号" style="width:56px"
            @update:value="v => update(idx, 'blankNo', v)" />
          <n-input-number size="small" :value="item.score" :min="0" :max="200" :step="0.5" placeholder="分"
            style="width:80px" @update:value="v => update(idx, 'score', v)" />
          <n-input size="small" :value="item.answer || item.standardAnswer" placeholder="标准答案" style="flex:1"
            @update:value="v => update(idx, 'answer', v)" />
          <n-button size="small" text type="error" @click="removeItem(idx)">删除</n-button>
        </div>
        <n-input size="small" type="textarea" :value="item.coreRequirement || item.subQ" placeholder="评分要求（可选）"
          :rows="1" :autosize="{ minRows: 1, maxRows: 3 }" style="margin-top:4px"
          @update:value="v => update(idx, 'coreRequirement', v)" />
      </div>
      <div class="footer">
        <n-button size="small" dashed @click="addItem">+ 添加评分项</n-button>
        <div class="total">
          <span>总分: {{ totalScore }} / {{ maxScore }}</span>
          <span v-if="totalScore !== maxScore" class="warning">分值不匹配</span>
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
  items.push({ blankNo: String(nextNum), score: 1, answer: '', coreRequirement: '' })
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
.rubric-item {
  padding: 8px 10px;
  border: 1px solid var(--border-color, #2e3e34);
  border-radius: 8px;
  margin-bottom: 8px;
}
.rubric-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
}
.total {
  font-size: 13px;
  font-weight: 600;
  color: #8a9a8e;
  display: flex;
  align-items: center;
  gap: 10px;
}
.warning {
  color: #d97706;
  font-weight: 500;
}
</style>
