<template>
  <div class="widget-grid" :style="gridStyle">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  columns: { type: Number, default: 2 },
})

const gridStyle = computed(() => ({
  '--grid-columns': props.columns,
}))
</script>

<style scoped>
.widget-grid {
  display: grid;
  grid-template-columns: repeat(var(--grid-columns, 2), 1fr);
  gap: 24px;
}

@media (max-width: 768px) {
  .widget-grid {
    grid-template-columns: 1fr;
  }
}
</style>
