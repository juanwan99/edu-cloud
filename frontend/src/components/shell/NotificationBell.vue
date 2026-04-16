<template>
  <n-popover trigger="click" placement="bottom-end" :width="280">
    <template #trigger>
      <div class="bell-btn" title="通知">
        <n-badge :value="count" :max="99" :show="count > 0">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 2a5 5 0 00-5 5v3l-1.3 2.6a.5.5 0 00.45.7h11.7a.5.5 0 00.45-.7L15 10V7a5 5 0 00-5-5z"
                  stroke="currentColor" stroke-width="1.4" fill="none"/>
            <path d="M8 14a2 2 0 004 0" stroke="currentColor" stroke-width="1.4" fill="none"/>
          </svg>
        </n-badge>
      </div>
    </template>
    <div class="notification-panel">
      <div class="notification-panel__header">
        <span class="notification-panel__title">通知</span>
      </div>
      <div class="notification-panel__body">
        <div class="notification-empty">暂无通知</div>
      </div>
    </div>
  </n-popover>
</template>

<script setup>
import { ref } from 'vue'

// Placeholder count — will connect to notifications API later
const count = ref(0)
</script>

<style scoped>
.bell-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition);
}

.bell-btn:hover {
  background: var(--color-bg-alt);
  color: var(--color-primary);
}

.notification-panel__header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light);
}

.notification-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
}

.notification-panel__body {
  padding: 8px 0;
}

.notification-empty {
  padding: 24px 16px;
  text-align: center;
  color: var(--color-text-muted);
  font-size: 13px;
}
</style>
