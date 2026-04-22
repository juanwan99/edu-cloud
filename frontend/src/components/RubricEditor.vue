<template>
  <n-spin :show="loading">
    <div v-if="!modelValue || modelValue.length === 0" class="empty">暂无评分细则</div>
    <div v-else>
      <div v-for="(item, idx) in modelValue" :key="idx" class="rubric-item">
        <n-space align="center">
          <n-tag size="small">第{{ item.blankNo }}空</n-tag>
          <span>{{ item.score }}分</span>
          <span>{{ item.answer }}</span>
        </n-space>
        <div v-if="item.coreRequirement" class="detail">{{ item.coreRequirement }}</div>
      </div>
      <div class="total">
        <span>总分: {{ totalScore }} / {{ maxScore }}</span>
        <span v-if="totalScore !== maxScore" class="warning">分值不匹配</span>
      </div>
    </div>
  </n-spin>
</template>

<script setup>
import { computed } from 'vue'
import { NSpin, NSpace, NTag } from 'naive-ui'

const props = defineProps({
  modelValue: Array,
  maxScore: Number,
  loading: Boolean,
})

defineEmits(['update:modelValue'])

const totalScore = computed(() => {
  if (!props.modelValue) return 0
  return props.modelValue.reduce((sum, item) => sum + (Number(item.score) || 0), 0)
})
</script>

<style scoped>
.empty {
  color: #8a9a8e;
  font-size: 13px;
  padding: 16px 0;
  text-align: center;
}
.rubric-item {
  padding: 8px 12px;
  border: 1px solid var(--border-color, #e2e8e4);
  border-radius: 8px;
  margin-bottom: 8px;
}
.detail {
  font-size: 12px;
  color: #8a9a8e;
  margin-top: 4px;
  padding-left: 4px;
}
.total {
  font-size: 13px;
  font-weight: 600;
  color: #555;
  padding: 8px 0 0;
  display: flex;
  align-items: center;
  gap: 10px;
}
.warning {
  color: #d97706;
  font-weight: 500;
}
</style>
