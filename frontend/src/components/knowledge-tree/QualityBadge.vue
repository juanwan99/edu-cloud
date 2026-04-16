<template>
  <n-tag v-if="severity" :type="tagType" size="small" round>
    {{ label }}
  </n-tag>
</template>

<script setup>
import { computed } from 'vue'
import { NTag } from 'naive-ui'

const props = defineProps({
  severity: { type: String, default: null },
  label: { type: String, default: '' },
})

const tagType = computed(() => {
  if (props.severity === 'HIGH') return 'error'
  if (props.severity === 'MED') return 'warning'
  return 'default'
})
</script>
