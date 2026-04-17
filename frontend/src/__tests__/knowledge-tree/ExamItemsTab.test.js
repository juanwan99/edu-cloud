import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../../api/knowledgeTree', () => ({
  getExamItems: vi.fn(),
}))
import { getExamItems } from '../../api/knowledgeTree'
import ExamItemsTab from '../../components/knowledge-tree/ExamItemsTab.vue'

describe('ExamItemsTab', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('shows empty state when no items', async () => {
    getExamItems.mockResolvedValue({ items: [], total: 0 })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'X' } })
    await flushPromises()
    expect(wrapper.text()).toContain('暂无关联高考真题')
  })

  it('renders items list', async () => {
    getExamItems.mockResolvedValue({
      items: [
        { id: '1', exam_id: 'GK_2019_ZJ', question_type: 'single_choice', stem: '光合作用相关题干' },
      ],
      total: 1,
    })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'Y' } })
    await flushPromises()
    expect(wrapper.text()).toContain('光合作用相关题干')
    expect(wrapper.text()).toContain('2019 ZJ')
  })

  it('pagination triggers reload', async () => {
    getExamItems.mockResolvedValue({ items: [{ id: '1', stem: 's' }], total: 30 })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'Z' } })
    await flushPromises()
    expect(getExamItems).toHaveBeenCalledWith('Z', 1, 10)
  })
})
