import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { getNotifications } from '../api/notifications.js'

vi.mock('../api/notifications.js', () => ({
  getNotifications: vi.fn(),
}))

vi.mock('naive-ui', () => ({
  NPopover: {
    template: '<div><slot name="trigger" /><slot /></div>',
    props: ['trigger', 'placement', 'width'],
  },
  NBadge: {
    template: '<div><span v-if="show">{{ value }}</span><slot /></div>',
    props: ['value', 'max', 'show'],
  },
  NSpin: {
    template: '<span />',
  },
}))

const loadFailedText = '\u901a\u77e5\u52a0\u8f7d\u5931\u8d25'
const emptyText = '\u6682\u65e0\u901a\u77e5'
const unreadText = '\u6761\u672a\u8bfb'
const titleText = '\u7cfb\u7edf\u901a\u77e5'

let NotificationBell

beforeAll(async () => {
  NotificationBell = (await import('../components/shell/NotificationBell.vue')).default
})

function mountBell() {
  return mount(NotificationBell)
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.mocked(getNotifications).mockReset()
  })

  it('renders loaded notifications and unread count without an error state', async () => {
    vi.mocked(getNotifications).mockResolvedValueOnce({
      data: [
        {
          id: 'n-1',
          title: titleText,
          summary: 'ok',
          unread: true,
          created_at: new Date().toISOString(),
        },
        {
          id: 'n-2',
          kind: 'task',
          summary: 'done',
          unread: false,
          created_at: new Date().toISOString(),
        },
      ],
    })

    const wrapper = mountBell()
    await flushPromises()
    await wrapper.vm.$nextTick()
    const text = wrapper.text()

    expect(text).toContain(titleText)
    expect(text).toContain(`1 ${unreadText}`)
    expect(text).not.toContain(loadFailedText)
  })

  it('shows a load failure state instead of the empty notification state', async () => {
    vi.mocked(getNotifications).mockRejectedValueOnce(new Error('network down'))

    const wrapper = mountBell()
    await flushPromises()
    await wrapper.vm.$nextTick()
    const text = wrapper.text()

    expect(text).toContain(loadFailedText)
    expect(text).not.toContain(emptyText)
    expect(wrapper.find('.notification-error').exists()).toBe(true)
  })
})
