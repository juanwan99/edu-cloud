<template>
  <div class="parent-skeleton">
    <div v-for="i in rows" :key="i" class="skeleton-card">
      <div class="skeleton-line skeleton-line--title" />
      <div class="skeleton-line skeleton-line--body" />
      <div class="skeleton-line skeleton-line--body skeleton-line--short" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 2 },
})
</script>

<style scoped>
.skeleton-card {
  background: var(--p-card-bg, #181433);
  border-radius: var(--p-card-radius, 12px);
  padding: var(--p-card-padding, 16px);
  margin-bottom: var(--p-space-5, 20px);
}
.skeleton-line {
  height: 14px;
  border-radius: 4px;
  background: var(--p-surface-3, #211B42);
  margin-bottom: 12px;
  position: relative;
  overflow: hidden;
}
.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--p-surface-raised, #272050), transparent);
  animation: shimmer 1.5s infinite;
}
.skeleton-line--title { width: 40%; height: 18px; margin-bottom: 16px; }
.skeleton-line--short { width: 60%; margin-bottom: 0; }
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>
