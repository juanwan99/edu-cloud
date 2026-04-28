<template>
  <div v-if="canUseAi" class="ai-fab" title="AI 助手" @click="$emit('toggle')">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 3a2 2 0 110 4 2 2 0 010-4zm-3 8h6v1a3 3 0 01-6 0v-1z"
            fill="currentColor"/>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth.js'

defineEmits(['toggle'])

const authStore = useAuthStore()
const canUseAi = computed(() => authStore.checkPermission('use_ai_chat'))
</script>

<style scoped>
.ai-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-lg);
  transition: var(--transition);
  z-index: var(--z-overlay);
}

.ai-fab:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-xl);
  background: var(--color-primary-light);
}
</style>
