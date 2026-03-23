import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'

export const useAiChatStore = defineStore('aiChat', () => {
  const messages = ref([])
  const isLoading = ref(false)
  const isAvailable = ref(false)
  const sessionId = ref(null)
  const error = ref(null)

  const authStore = useAuthStore()

  async function checkHealth() {
    try {
      const resp = await fetch('/api/v1/ai/health', {
        headers: { Authorization: `Bearer ${authStore.token}` },
      })
      const data = await resp.json()
      isAvailable.value = data.status === 'available'
    } catch {
      isAvailable.value = false
    }
  }

  async function sendMessage(content) {
    if (!content.trim() || isLoading.value) return

    messages.value.push({ role: 'user', content })
    isLoading.value = true
    error.value = null

    try {
      const resp = await fetch('/api/v1/ai/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: content,
          session_id: sessionId.value,
        }),
      })

      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}))
        throw new Error(errBody.detail || `HTTP ${resp.status}`)
      }

      // 读取 session_id
      const sid = resp.headers.get('X-Session-Id')
      if (sid) sessionId.value = sid

      // SSE 解析
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let assistantMsg = { role: 'assistant', content: '', tools: [] }
      messages.value.push(assistantMsg)

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() // 保留未完成的行

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const jsonStr = line.slice(6).trim()
          if (!jsonStr) continue

          try {
            const event = JSON.parse(jsonStr)
            if (event.type === 'answer') {
              assistantMsg.content += event.data?.content || ''
            } else if (event.type === 'tool_call') {
              assistantMsg.tools.push({ name: event.data?.tool, status: 'running' })
            } else if (event.type === 'tool_result') {
              const tool = assistantMsg.tools.find(t => t.name === event.data?.tool && t.status === 'running')
              if (tool) tool.status = 'done'
            } else if (event.type === 'error') {
              error.value = event.data?.message || 'Unknown error'
            } else if (event.type === 'done') {
              if (event.session_id) sessionId.value = event.session_id
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (e) {
      error.value = e.message
    } finally {
      isLoading.value = false
    }
  }

  function clearChat() {
    messages.value = []
    sessionId.value = null
    error.value = null
  }

  return {
    messages,
    isLoading,
    isAvailable,
    sessionId,
    error,
    checkHealth,
    sendMessage,
    clearChat,
  }
})
