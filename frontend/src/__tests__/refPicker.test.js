import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import RefPicker from '../components/ai/RefPicker.vue'

vi.mock('../api/ai.js', () => ({
  getRefTypes: vi.fn().mockResolvedValue({
    data: [
      { type_code: 'exam', label: '考试', icon: 'exam', children_type: 'subject', searchable: true },
      { type_code: 'class', label: '班级', icon: 'class', children_type: 'student', searchable: true },
    ],
  }),
  getRefs: vi.fn().mockResolvedValue({
    data: {
      items: [
        { id: 'e1', label: '2026春季期中', subtitle: 'completed', children_type: 'subject' },
        { id: 'e2', label: '2026春季月考', subtitle: 'draft', children_type: 'subject' },
      ],
      total: 2,
    },
  }),
}))

describe('RefPicker', () => {
  it('renders tabs from ref types', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    expect(wrapper.text()).toContain('考试')
    expect(wrapper.text()).toContain('班级')
  })

  it('loads items when tab selected', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    expect(wrapper.text()).toContain('2026春季期中')
  })

  it('emits select on confirm', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    const items = wrapper.findAll('.ref-item')
    await items[0].trigger('click')
    await flushPromises()
    await wrapper.find('.ref-confirm').trigger('click')
    const emitted = wrapper.emitted('select')
    expect(emitted).toBeTruthy()
    expect(emitted[0][0].id).toBe('e1')
  })

  it('emits close on backdrop click', async () => {
    const wrapper = mount(RefPicker)
    await flushPromises()
    await wrapper.find('.ref-backdrop').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
