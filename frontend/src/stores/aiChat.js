import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAiChatStore = defineStore('aiChat', () => {
  const messages = ref([])
  const isStreaming = ref(false)
  const error = ref('')

  async function sendMessage(text) {
    if (!text.trim() || isStreaming.value) return
    messages.value.push({ role: 'user', content: text })
    isStreaming.value = true
    error.value = ''

    const token = localStorage.getItem('token')
    try {
      const response = await fetch('/api/v1/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ message: text }),
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      const msgIndex = messages.value.length
      messages.value.push({ role: 'assistant', content: '', toolCalls: [], toolResults: [] })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))
            if (data.type === 'tool_call') messages.value[msgIndex].toolCalls.push(data.data)
            else if (data.type === 'tool_result') messages.value[msgIndex].toolResults.push(data.data)
            else if (data.type === 'answer') messages.value[msgIndex].content = data.data.content
            else if (data.type === 'error') error.value = data.data.message
          } catch (e) { /* skip malformed lines */ }
        }
      }
    } catch (e) {
      error.value = e.message || 'AI 服务不可用'
    } finally {
      isStreaming.value = false
    }
  }

  function clearMessages() {
    messages.value = []
    error.value = ''
  }

  return { messages, isStreaming, error, sendMessage, clearMessages }
})
