<template>
  <Transition name="slide-right">
    <div v-if="visible" class="ai-panel-overlay" @click.self="$emit('close')">
      <aside class="ai-panel">
        <header class="ai-panel-header">
          <span class="ai-panel-title">AI 助手</span>
          <div class="ai-panel-actions">
            <button v-if="chat.messages.length" class="ai-btn-icon" title="清空对话" @click="chat.clearChat()">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M5 2V1h6v1h3v1H2V2h3zm1 3v8h1V5H6zm3 0v8h1V5H9zM3 4l1 10h8l1-10H3z"/>
              </svg>
            </button>
            <button class="ai-btn-icon" title="关闭" @click="$emit('close')">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M3.7 3.7a1 1 0 011.4 0L8 6.6l2.9-2.9a1 1 0 111.4 1.4L9.4 8l2.9 2.9a1 1 0 01-1.4 1.4L8 9.4l-2.9 2.9a1 1 0 01-1.4-1.4L6.6 8 3.7 5.1a1 1 0 010-1.4z"/>
              </svg>
            </button>
          </div>
        </header>

        <div ref="bodyRef" class="ai-panel-body">
          <div v-if="!chat.messages.length" class="ai-empty">
            <p class="ai-empty-title">有什么可以帮你的？</p>
            <p class="ai-empty-hint">试试问"列出最近的考试"或"帮我分析高二3班的成绩"</p>
          </div>

          <div v-for="(msg, i) in chat.messages" :key="i" :class="['ai-msg', `ai-msg--${msg.role}`]">
            <div v-if="msg.role === 'user'" class="ai-msg-bubble ai-msg-bubble--user">{{ msg.content }}</div>

            <div v-else class="ai-msg-assistant">
              <div v-if="msg.thinking" class="ai-thinking">
                <span class="ai-thinking-label">思考中</span>
                <span class="ai-thinking-text">{{ msg.thinking.trim() }}</span>
              </div>

              <div v-if="msg.plan && msg.plan.length" class="ai-plan">
                <div v-for="task in msg.plan" :key="task.id" class="ai-plan-step">
                  <span :class="['ai-plan-dot', task.status === 'completed' ? 'ai-plan-dot--done' : '']" />
                  <span class="ai-plan-desc">{{ task.description }}</span>
                </div>
              </div>

              <div v-for="(tool, j) in (msg.tools || [])" :key="j" class="ai-tool">
                <span :class="['ai-tool-dot', tool.status === 'done' ? 'ai-tool-dot--done' : 'ai-tool-dot--spin']" />
                <span class="ai-tool-name">{{ tool.name }}</span>
                <span class="ai-tool-status">{{ tool.status === 'done' ? '完成' : '执行中...' }}</span>
              </div>

              <div v-if="msg.content" class="ai-msg-bubble ai-msg-bubble--assistant">
                <div class="ai-content" v-text="msg.content" />
              </div>
            </div>
          </div>

          <div v-if="chat.isLoading && !lastAssistantHasContent" class="ai-loading">
            <span class="ai-loading-dot" /><span class="ai-loading-dot" /><span class="ai-loading-dot" />
          </div>

          <div v-if="chat.error" class="ai-error">{{ chat.error }}</div>
        </div>

        <form class="ai-panel-footer" @submit.prevent="send">
          <input
            ref="inputRef"
            v-model="inputText"
            class="ai-input"
            type="text"
            placeholder="输入问题..."
            :disabled="chat.isLoading"
            autocomplete="off"
          />
          <button class="ai-send" type="submit" :disabled="!inputText.trim() || chat.isLoading" title="发送">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </form>
      </aside>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, nextTick, computed, onMounted } from 'vue'
import { useAiChatStore } from '../../stores/aiChat.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
defineEmits(['close'])

const chat = useAiChatStore()
const inputText = ref('')
const inputRef = ref(null)
const bodyRef = ref(null)

const lastAssistantHasContent = computed(() => {
  const msgs = chat.messages
  if (!msgs.length) return false
  const last = msgs[msgs.length - 1]
  return last.role === 'assistant' && (last.content || last.tools?.length)
})

async function send() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  await chat.sendMessage(text)
}

function scrollToBottom() {
  nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  })
}

watch(() => props.visible, (v) => {
  if (v) {
    chat.checkHealth()
    nextTick(() => inputRef.value?.focus())
    scrollToBottom()
  }
})

watch(() => chat.messages, scrollToBottom, { deep: true })

onMounted(() => { chat.checkHealth() })
</script>

<style scoped>
.ai-panel-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  background: rgba(0, 0, 0, 0.15);
}

.ai-panel {
  position: absolute;
  top: 0;
  right: 0;
  width: 420px;
  max-width: 100vw;
  height: 100dvh;
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
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-border-light);
  flex-shrink: 0;
}

.ai-panel-title {
  font-size: 15px;
  font-weight: var(--fw-semibold);
  color: var(--color-text);
}

.ai-panel-actions {
  display: flex;
  gap: 4px;
}

.ai-btn-icon {
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
}

.ai-btn-icon:hover {
  background: var(--color-bg-alt);
  color: var(--color-text);
}

/* Body */
.ai-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ai-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--color-text-secondary);
}

.ai-empty-title {
  font-size: 16px;
  font-weight: var(--fw-medium);
  margin-bottom: 8px;
}

.ai-empty-hint {
  font-size: 13px;
  opacity: 0.7;
  max-width: 260px;
}

/* Messages */
.ai-msg--user {
  display: flex;
  justify-content: flex-end;
}

.ai-msg-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}

.ai-msg-bubble--user {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.ai-msg-bubble--assistant {
  background: var(--color-bg-alt);
  color: var(--color-text);
  border-bottom-left-radius: 4px;
}

.ai-msg-bubble--assistant :deep(p) {
  margin: 0 0 8px;
}

.ai-msg-bubble--assistant :deep(p:last-child) {
  margin-bottom: 0;
}

.ai-msg-bubble--assistant :deep(table) {
  border-collapse: collapse;
  font-size: 13px;
  margin: 8px 0;
  width: 100%;
}

.ai-msg-bubble--assistant :deep(th),
.ai-msg-bubble--assistant :deep(td) {
  border: 1px solid var(--color-border-light);
  padding: 4px 8px;
  text-align: left;
}

.ai-msg-bubble--assistant :deep(h2),
.ai-msg-bubble--assistant :deep(h3) {
  font-size: 14px;
  font-weight: var(--fw-semibold);
  margin: 12px 0 4px;
}

.ai-msg-bubble--assistant :deep(ul),
.ai-msg-bubble--assistant :deep(ol) {
  padding-left: 20px;
  margin: 4px 0;
}

/* Thinking */
.ai-thinking {
  font-size: 13px;
  color: var(--color-text-secondary);
  padding: 6px 10px;
  background: var(--color-bg-alt);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--color-primary);
  margin-bottom: 8px;
}

.ai-thinking-label {
  font-weight: var(--fw-semibold);
  margin-right: 6px;
}

.ai-thinking-text {
  opacity: 0.8;
  white-space: pre-wrap;
}

/* Plan */
.ai-plan {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.ai-plan-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.ai-plan-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border);
  flex-shrink: 0;
}

.ai-plan-dot--done {
  background: #22c55e;
}

/* Tool calls */
.ai-tool {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 4px 0;
  color: var(--color-text-secondary);
}

.ai-tool-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ai-tool-dot--spin {
  background: var(--color-primary);
  animation: pulse 1.2s infinite;
}

.ai-tool-dot--done {
  background: #22c55e;
}

.ai-tool-name {
  font-family: monospace;
  font-size: 12px;
}

.ai-tool-status {
  opacity: 0.7;
}

/* Loading */
.ai-loading {
  display: flex;
  gap: 4px;
  padding: 8px 0;
}

.ai-loading-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-secondary);
  animation: pulse 1.2s infinite;
}

.ai-loading-dot:nth-child(2) { animation-delay: 0.2s; }
.ai-loading-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1); }
}

/* Error */
.ai-error {
  font-size: 13px;
  color: #ef4444;
  padding: 8px 12px;
  background: #fef2f2;
  border-radius: var(--radius-sm);
}

/* Footer */
.ai-panel-footer {
  padding: 12px 20px 16px;
  border-top: 1px solid var(--color-border-light);
  flex-shrink: 0;
  display: flex;
  gap: 8px;
}

.ai-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-alt);
  color: var(--color-text);
  font-size: 14px;
  outline: none;
  transition: var(--transition);
}

.ai-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px rgba(100, 76, 240, 0.15);
}

.ai-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ai-send {
  width: 40px;
  height: 40px;
  border: none;
  border-radius: var(--radius-md);
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: var(--transition);
}

.ai-send:hover:not(:disabled) {
  background: var(--color-primary-light);
}

.ai-send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Slide transition */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
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
