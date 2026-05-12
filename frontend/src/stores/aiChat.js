import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useAuthStore } from './auth'
import { createSSEProcessor } from '../utils/sseParser'
import client from '../api/client'

export const useAiChatStore = defineStore('aiChat', () => {
  const messages = ref([])
  const isLoading = ref(false)
  const isAvailable = ref(false)
  const sessionId = ref(null)
  const error = ref(null)
  const pendingConfirmations = ref([])

  const authStore = useAuthStore()

  async function checkHealth() {
    try {
      const resp = await client.get('/ai/health')
      isAvailable.value = resp.data.status === 'available'
    } catch {
      isAvailable.value = false
    }
  }

  async function sendMessage(content, refs = []) {
    if (!content.trim() || isLoading.value) return

    messages.value.push({ role: 'user', content, refs: refs.length ? refs : undefined })
    isLoading.value = true
    error.value = null

    try {
      // SSE 流式请求：必须保留 fetch，Axios 不支持 ReadableStream (response.body.getReader)
      const resp = await fetch('/api/v1/ai/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify((() => {
          const body = { message: content, session_id: sessionId.value }
          if (refs.length) body.refs = refs
          return body
        })()),
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

      const processor = createSSEProcessor({
        onThinking(text) { assistantMsg.thinking = (assistantMsg.thinking || '') + text + '\n' },
        onPlan(tasks) { assistantMsg.plan = tasks },
        onTaskUpdate(data) {
          if (assistantMsg.plan) {
            const t = assistantMsg.plan.find(x => x.id === data.id)
            if (t) t.status = data.status
          }
        },
        onAnswer(content) { assistantMsg.content += content },
        onToolCall(tool) { assistantMsg.tools.push({ name: tool, status: 'running' }) },
        onToolResult(tool) {
          const t = assistantMsg.tools.find(x => x.name === tool && x.status === 'running')
          if (t) t.status = 'done'
        },
        onConfirmation(data) {
          const conf = {
            id: data.tool_call_id,
            runId: data.run_id,
            toolName: data.tool_name,
            args: data.args || {},
            status: 'pending',
          }
          pendingConfirmations.value.push(conf)
          assistantMsg.confirmations = assistantMsg.confirmations || []
          assistantMsg.confirmations.push(conf)
        },
        onError(msg) { error.value = msg },
        onDone(sid) { if (sid) sessionId.value = sid },
      })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        processor.push(decoder.decode(value, { stream: true }))
      }
    } catch (e) {
      error.value = e.message
    } finally {
      isLoading.value = false
    }
  }

  async function resolveConfirmation(confirmationId, decision) {
    const conf = pendingConfirmations.value.find(c => c.id === confirmationId)
    if (!conf || conf.status !== 'pending') return

    conf.status = decision === 'approve' ? 'approved' : 'rejected'

    try {
      const resp = await fetch(`/api/v1/ai/runs/${conf.runId}/confirmations/${confirmationId}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${authStore.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ decision }),
      })

      if (!resp.ok) return

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      const lastMsg = messages.value[messages.value.length - 1]

      const processor = createSSEProcessor({
        onAnswer(content) { if (lastMsg) lastMsg.content += content },
        onToolCall(tool) { if (lastMsg) { lastMsg.tools = lastMsg.tools || []; lastMsg.tools.push({ name: tool, status: 'running' }) } },
        onToolResult(tool) { if (lastMsg) { const t = (lastMsg.tools || []).find(x => x.name === tool && x.status === 'running'); if (t) t.status = 'done' } },
        onError(msg) { error.value = msg },
        onDone(sid) { if (sid) sessionId.value = sid },
      })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        processor.push(decoder.decode(value, { stream: true }))
      }
    } catch (e) {
      error.value = e.message
    } finally {
      pendingConfirmations.value = pendingConfirmations.value.filter(c => c.id !== confirmationId)
    }
  }

  function clearChat() {
    messages.value = []
    sessionId.value = null
    error.value = null
    pendingConfirmations.value = []
  }

  return {
    messages,
    isLoading,
    isAvailable,
    sessionId,
    error,
    pendingConfirmations,
    checkHealth,
    sendMessage,
    resolveConfirmation,
    clearChat,
  }
})
