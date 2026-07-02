import { describe, expect, it, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NotificationBell from '../components/shell/NotificationBell.vue'
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
    template: '<div><slot /></div>',
    props: ['value', 'max', 'show'],
  },
  NSpin: {
    template: '<span />',
    props: ['size'],
  },
}))

describe('NotificationBell fail-visible loading', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loaded notifications and unread count', async () => {
    getNotifications.mockResolvedValueOnce({
      data: [
        { id: 'n1', title: 'Action required', summary: 'Please confirm', unread: true, created_at: new Date().toISOString() },
      ],
    })

    const wrapper = mount(NotificationBell)
    await flushPromises()

    expect(wrapper.text()).toContain('Action required')
    expect(wrapper.text()).toContain('1 \u6761\u672a\u8bfb')
    expect(wrapper.text()).not.toContain('\u901a\u77e5\u52a0\u8f7d\u5931\u8d25')
  })

  it('shows a visible error instead of an empty notification state when loading fails', async () => {
    getNotifications.mockRejectedValueOnce(new Error('network down'))

    const wrapper = mount(NotificationBell)
    await flushPromises()

    expect(wrapper.find('.notification-error').text()).toContain('\u901a\u77e5\u52a0\u8f7d\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5')
    expect(wrapper.text()).not.toContain('\u6682\u65e0\u901a\u77e5')
  })
})
