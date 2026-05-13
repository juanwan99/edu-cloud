import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AiSlidePanel from '../AiSlidePanel.vue'
import { useAiChatStore } from '../../../stores/aiChat.js'

vi.mock('../RefPicker.vue', () => ({ default: { template: '<div />' } }))

function mountPanel(options = {}) {
  return mount(AiSlidePanel, {
    props: { visible: true, ...options.props },
    global: { plugins: [createPinia()] },
  })
}

function makeConf(overrides = {}) {
  return {
    id: 'c-1',
    runId: 'r-1',
    toolName: 'generate_report',
    args: { exam_id: '123' },
    status: 'pending',
    expiresAt: Date.now() + 120_000,
    ...overrides,
  }
}

describe('AiSlidePanel', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('renders empty state when no messages', () => {
    const w = mountPanel()
    expect(w.text()).toContain('有什么可以帮你的')
  })

  it('renders user and assistant messages', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    chat.messages.push({ role: 'user', content: '你好' })
    chat.messages.push({ role: 'assistant', content: '我是AI助手' })
    await w.vm.$nextTick()
    expect(w.findAll('.ai-msg--user')).toHaveLength(1)
    expect(w.findAll('.ai-msg--assistant')).toHaveLength(1)
  })

  it('renders tool call process indicator', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    chat.messages.push({
      role: 'assistant',
      content: '',
      tools: [{ name: 'get_exam_list', status: 'running' }],
    })
    await w.vm.$nextTick()
    expect(w.text()).toContain('正在查询')
  })

  it('shows done state when all tools finish', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    chat.messages.push({
      role: 'assistant',
      content: '结果',
      tools: [{ name: 'get_exam_list', status: 'done' }],
    })
    await w.vm.$nextTick()
    expect(w.text()).toContain('查询了 1 个数据源')
  })
})

describe('AiSlidePanel confirmation card', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('renders pending confirmation with approve/reject buttons', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    const conf = makeConf()
    chat.messages.push({ role: 'assistant', content: '', confirmations: [conf] })
    await w.vm.$nextTick()
    expect(w.text()).toContain('写操作确认')
    expect(w.text()).toContain('generate_report')
    expect(w.findAll('.ai-confirm-btn--approve')).toHaveLength(1)
    expect(w.findAll('.ai-confirm-btn--reject')).toHaveLength(1)
  })

  it('shows countdown for pending confirmation', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    const conf = makeConf({ expiresAt: Date.now() + 90_000 })
    chat.messages.push({ role: 'assistant', content: '', confirmations: [conf] })
    await w.vm.$nextTick()
    expect(w.find('.ai-confirm-countdown').text()).toMatch(/\d:\d{2}/)
  })

  it('shows expired state when confirmation times out', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    const conf = makeConf({ expiresAt: Date.now() - 1000 })
    chat.messages.push({ role: 'assistant', content: '', confirmations: [conf] })
    await w.vm.$nextTick()
    expect(w.text()).toContain('已超时，操作未执行')
    expect(w.findAll('.ai-confirm-btn--approve')).toHaveLength(0)
  })

  it('shows approved state', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    const conf = makeConf({ status: 'approved' })
    chat.messages.push({ role: 'assistant', content: '', confirmations: [conf] })
    await w.vm.$nextTick()
    expect(w.text()).toContain('已批准')
  })

  it('shows rejected state', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    const conf = makeConf({ status: 'rejected' })
    chat.messages.push({ role: 'assistant', content: '', confirmations: [conf] })
    await w.vm.$nextTick()
    expect(w.text()).toContain('已拒绝')
  })

  it('renders tool args as chips', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    const conf = makeConf({ args: { exam_id: 'e1', class_id: 'c1' } })
    chat.messages.push({ role: 'assistant', content: '', confirmations: [conf] })
    await w.vm.$nextTick()
    const chips = w.findAll('.ai-confirm-arg')
    expect(chips).toHaveLength(2)
    expect(chips[0].text()).toContain('exam_id')
  })
})

describe('AiSlidePanel timer lifecycle', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })
  afterEach(() => { vi.useRealTimers() })

  it('cleans up interval on unmount', () => {
    const w = mountPanel()
    const spy = vi.spyOn(global, 'clearInterval')
    w.unmount()
    expect(spy).toHaveBeenCalled()
  })
})

describe('AiSlidePanel context injection (S2)', () => {
  beforeEach(() => { setActivePinia(createPinia()) })

  it('shows context card when initialContext is set via prop change', async () => {
    const w = mountPanel()
    const ctx = { type: 'exam_analysis', label: '期中考试 · 数学', refs: [{ type: 'exam', id: 'e1', label: '期中考试' }] }
    await w.setProps({ initialContext: ctx })
    expect(w.find('.ai-context-card').exists()).toBe(true)
    expect(w.text()).toContain('期中考试 · 数学')
  })

  it('fills suggestedPrompt into input on context change', async () => {
    const w = mountPanel()
    const ctx = { type: 'exam_analysis', label: '期中考试', suggestedPrompt: '请分析这次考试', refs: [] }
    await w.setProps({ initialContext: ctx })
    expect(w.find('.ai-input').element.value).toBe('请分析这次考试')
  })

  it('removes context card on close button click', async () => {
    const w = mountPanel()
    await w.setProps({ initialContext: { type: 'exam_analysis', label: '测试', refs: [] } })
    expect(w.find('.ai-context-card').exists()).toBe(true)
    await w.find('.ai-context-remove').trigger('click')
    expect(w.find('.ai-context-card').exists()).toBe(false)
  })

  it('clears context when initialContext changes to null', async () => {
    const w = mountPanel()
    await w.setProps({ initialContext: { type: 'exam_analysis', label: '测试', refs: [] } })
    expect(w.find('.ai-context-card').exists()).toBe(true)
    await w.setProps({ initialContext: null })
    expect(w.find('.ai-context-card').exists()).toBe(false)
  })

  it('updates context card and prompt when initialContext changes', async () => {
    const w = mountPanel()
    await w.setProps({ initialContext: { type: 'exam_analysis', label: '考试A', suggestedPrompt: 'promptA', refs: [] } })
    expect(w.text()).toContain('考试A')
    expect(w.find('.ai-input').element.value).toBe('promptA')
    await w.setProps({ initialContext: { type: 'exam_diagnosis', label: '考试B', suggestedPrompt: 'promptB', refs: [] } })
    expect(w.text()).toContain('考试B')
    expect(w.find('.ai-input').element.value).toBe('promptB')
  })

  it('no context card when initialContext is null', () => {
    const w = mountPanel({ props: { initialContext: null } })
    expect(w.find('.ai-context-card').exists()).toBe(false)
  })

  it('send attaches context refs to chat.sendMessage', async () => {
    const w = mountPanel()
    const chat = useAiChatStore()
    const spy = vi.spyOn(chat, 'sendMessage').mockResolvedValue()
    const ctxRefs = [{ type: 'exam', id: 'e1', label: '期中考试' }]
    await w.setProps({ initialContext: { type: 'exam_analysis', label: '测试', refs: ctxRefs } })
    await w.find('.ai-input').setValue('hello')
    await w.find('form').trigger('submit')
    expect(spy).toHaveBeenCalledWith('hello', expect.arrayContaining([
      expect.objectContaining({ type: 'exam', id: 'e1' }),
    ]))
    spy.mockRestore()
  })
})
