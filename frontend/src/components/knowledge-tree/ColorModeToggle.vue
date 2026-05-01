<template>
  <div class="color-mode-toggle">
    <span class="label">着色模式：</span>
    <n-radio-group :value="localMode" @update:value="onChange" size="small">
      <n-radio-button value="exam_frequency">考频</n-radio-button>
      <n-radio-button value="mastery" :disabled="!hasStudent">掌握度</n-radio-button>
      <n-radio-button value="review_status">审核状态</n-radio-button>
    </n-radio-group>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { NRadioGroup, NRadioButton } from 'naive-ui'

const props = defineProps({
  modelValue: { type: String, default: 'exam_frequency' },
  hasStudent: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const localMode = ref(props.modelValue)
watch(() => props.modelValue, (v) => { localMode.value = v })

function onChange(val) {
  localMode.value = val
  emit('update:modelValue', val)
}

defineExpose({ onChange })
</script>

<style scoped>
.color-mode-toggle {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.label {
  font-size: var(--fs-base);
  color: var(--text-color-2);
}
</style>
