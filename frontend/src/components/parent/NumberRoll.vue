<template>
  <span class="number-roll" :style="{ fontSize: size }">{{ display }}</span>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
const props = defineProps({
  value: { type: [Number, null], default: null },
  size: { type: String, default: 'inherit' },
  duration: { type: Number, default: 400 },
})
const current = ref(props.value ?? 0)
const display = computed(() => props.value == null ? '-' : Math.round(current.value))
watch(() => props.value, (to, from) => {
  if (to == null || from == null) { current.value = to ?? 0; return }
  const start = from
  const delta = to - from
  const startTime = performance.now()
  function step(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / props.duration, 1)
    const ease = 1 - Math.pow(1 - progress, 3)
    current.value = start + delta * ease
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
})
</script>

<style scoped>
.number-roll { font-variant-numeric: tabular-nums; display: inline-block; }
</style>
