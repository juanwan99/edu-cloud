<template>
  <div v-if="contextName" class="school-context">
    <span class="school-context__icon">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M8 1L1 5v2h14V5L8 1zM2 8v5a1 1 0 001 1h10a1 1 0 001-1V8H2z"
              stroke="currentColor" stroke-width="1.2" fill="none"/>
      </svg>
    </span>
    <span class="school-context__name">{{ contextName }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth.js'

const auth = useAuthStore()
const contextName = computed(() => auth.currentContext?.name || '')
</script>

<style scoped>
.school-context {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-pill);
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.9);
  font-weight: var(--fw-medium);
  max-width: 200px;
}

.school-context__icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.school-context__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
