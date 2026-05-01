<template>
  <div class="chat-panel">
    <div class="chat-messages" ref="messagesContainer">
      <div v-for="(msg, i) in chatStore.messages" :key="i" :class="['message', msg.role]">
        <div v-if="msg.role === 'user'" class="user-msg">{{ msg.content }}</div>
        <div v-else class="assistant-msg">
          <div v-if="msg.toolCalls?.length" class="tool-tags">
            <n-tag v-for="tc in msg.toolCalls" :key="tc.tool" size="small" type="info">
              {{ tc.tool }}
            </n-tag>
          </div>
          <div v-if="msg.content" class="answer-content" v-html="renderMarkdown(msg.content)" />
          <n-spin v-else-if="chatStore.isStreaming && i === chatStore.messages.length - 1" size="small" />
        </div>
      </div>
    </div>
    <n-alert v-if="chatStore.error" type="error" closable style="margin: var(--space-2)">{{ chatStore.error }}</n-alert>
    <div class="chat-input">
      <n-input v-model:value="inputText" placeholder="问一个关于教学数据的问题..." :disabled="chatStore.isStreaming" @keyup.enter="handleSend" />
      <n-button type="primary" :loading="chatStore.isStreaming" :disabled="!inputText.trim()" @click="handleSend">发送</n-button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'
import DOMPurify from 'dompurify'
import { useAiChatStore } from '../../stores/aiChat.js'

const chatStore = useAiChatStore()
const inputText = ref('')
const messagesContainer = ref(null)

function renderMarkdown(text) {
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const html = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
  return DOMPurify.sanitize(html)
}

async function handleSend() {
  if (!inputText.value.trim()) return
  const text = inputText.value
  inputText.value = ''
  await chatStore.sendMessage(text)
}

watch(() => chatStore.messages.length, async () => {
  await nextTick()
  if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
})
</script>

<style scoped>
.chat-panel { display: flex; flex-direction: column; height: 100%; border-top: 1px solid var(--n-border-color); }
.chat-messages { flex: 1; overflow-y: auto; padding: 12px; }
.message { margin-bottom: 12px; }
.user-msg { background: var(--color-primary-light); color: white; padding: 8px 12px; border-radius: 12px 12px 0 12px; max-width: 80%; margin-left: auto; }
.assistant-msg { background: var(--color-bg-deep, #2d2d3d); padding: 8px 12px; border-radius: 12px 12px 12px 0; max-width: 90%; }
.tool-tags { margin-bottom: 6px; display: flex; gap: 4px; flex-wrap: wrap; }
.chat-input { display: flex; gap: 8px; padding: 8px 12px; border-top: 1px solid var(--n-border-color); }
</style>
