<template>
  <div class="ai-fab" title="AI 助手">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
      <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 3a2 2 0 110 4 2 2 0 010-4zm-3 8h6v1a3 3 0 01-6 0v-1z"
            fill="currentColor"/>
    </svg>
  </div>
</template>

<script setup>
// Placeholder — Task 12 will add AI chat panel toggle
</script>

<style scoped>
.ai-fab {
  position: fixed;
  bottom: 24px;
  right: 24px;
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-lg);
  transition: var(--transition);
  z-index: 1100;
}

.ai-fab:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-xl);
  background: var(--color-primary-light);
}
</style>
