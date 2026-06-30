import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAiChatStore } from '../stores/aiChat.js'

vi.mock('../api/client.js', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

vi.mock('../router/index.js', () => ({
  default: { push: vi.fn() },
}))

function sseResponse(payload) {
  const encoder = new TextEncoder()
  let sent = false
  return {
    ok: true,
    headers: {
      get(name) {
        return name === 'X-Session-Id' ? 'sess-persist' : null
      },
    },
    body: {
      getReader() {
        return {
          async read() {
            if (sent) return { done: true }
            sent = true
            return { done: false, value: encoder.encode(payload) }
          },
        }
      },
    },
  }
}

describe('aiChat store persistence warnings', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('shows a localized warning when generated chat history is not saved', async () => {
    localStorage.setItem('token', 'fake-jwt')
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(sseResponse([
      'data: {"type":"answer","data":{"content":"已生成回答"}}\n',
      'data: {"type":"done","data":{"session_id":"sess-persist","persistence":{"status":"failed","reason":"chat_history_unavailable"}}}\n',
    ].join('')))

    const store = useAiChatStore()

    await store.sendMessage('请分析这次考试')

    expect(store.error).toBe('AI 已生成回复，但聊天记录未保存。请复制重要内容或稍后重试。')
    expect(store.sessionId).toBe('sess-persist')
    expect(store.messages[1].persistence).toEqual({
      status: 'failed',
      reason: 'chat_history_unavailable',
    })
  })
})
