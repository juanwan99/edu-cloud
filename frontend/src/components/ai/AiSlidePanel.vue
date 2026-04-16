<template>
  <Transition name="slide-right">
    <div v-if="visible" class="ai-panel-overlay" @click.self="$emit('close')">
      <aside class="ai-panel">
        <header class="ai-panel-header">
          <span class="ai-panel-title">AI 助手</span>
          <div class="ai-panel-actions">
            <router-link to="/analysis" class="ai-panel-expand" title="在工作台中打开">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2 1h5v1H3v4H2V1zm12 0h-5v1h4v4h1V1zM2 15h5v-1H3v-4H2v5zm12 0h-5v-1h4v-4h1v5z"/>
              </svg>
            </router-link>
            <button class="ai-panel-close" title="关闭" @click="$emit('close')">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M3.7 3.7a1 1 0 011.4 0L8 6.6l2.9-2.9a1 1 0 111.4 1.4L9.4 8l2.9 2.9a1 1 0 01-1.4 1.4L8 9.4l-2.9 2.9a1 1 0 01-1.4-1.4L6.6 8 3.7 5.1a1 1 0 010-1.4z"/>
              </svg>
            </button>
          </div>
        </header>

        <div class="ai-panel-body">
          <div class="ai-panel-placeholder">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" style="opacity: 0.3;">
              <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 3a2 2 0 110 4 2 2 0 010-4zm-3 8h6v1a3 3 0 01-6 0v-1z"
                    fill="currentColor"/>
            </svg>
            <p class="ai-panel-placeholder-text">AI 助手功能即将上线</p>
            <p class="ai-panel-placeholder-hint">完整 AI 对话请前往<router-link to="/analysis">分析工作台</router-link></p>
          </div>
        </div>

        <div class="ai-panel-footer">
          <input class="ai-panel-input" type="text" placeholder="输入问题..." disabled />
        </div>
      </aside>
    </div>
  </Transition>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
})
defineEmits(['close'])
</script>

<style scoped>
.ai-panel-overlay {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(0, 0, 0, 0.15);
}

.ai-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 400px;
  max-width: 100vw;
  height: 100vh;
  background: var(--color-bg);
  border-left: 1px solid var(--color-border-light);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
}

.ai-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.ai-panel-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
}

.ai-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-panel-expand,
.ai-panel-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: var(--transition);
  text-decoration: none;
}

.ai-panel-expand:hover,
.ai-panel-close:hover {
  background: var(--color-bg-alt);
  color: var(--color-text);
}

.ai-panel-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-panel-placeholder {
  text-align: center;
  color: var(--color-text-secondary);
}

.ai-panel-placeholder-text {
  margin-top: 12px;
  font-size: 15px;
  font-weight: 500;
}

.ai-panel-placeholder-hint {
  margin-top: 8px;
  font-size: 13px;
  opacity: 0.7;
}

.ai-panel-placeholder-hint a {
  color: var(--color-primary);
  text-decoration: none;
}

.ai-panel-placeholder-hint a:hover {
  text-decoration: underline;
}

.ai-panel-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.ai-panel-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-alt);
  color: var(--color-text-secondary);
  font-size: 14px;
  outline: none;
  cursor: not-allowed;
}

/* Slide transition */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.3s ease;
}

.slide-right-enter-active .ai-panel,
.slide-right-leave-active .ai-panel {
  transition: transform 0.3s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  opacity: 0;
}

.slide-right-enter-from .ai-panel,
.slide-right-leave-to .ai-panel {
  transform: translateX(100%);
}
</style>
