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

  it('nextPage click triggers page=2 request (R2 F002 mutant: 删 nextPage/page++ 必红)', async () => {
    getExamItems.mockResolvedValue({ items: [{ id: '1', stem: 's1' }], total: 30 })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'Z' } })
    await flushPromises()
    expect(getExamItems).toHaveBeenNthCalledWith(1, 'Z', 1, 10)

    const nextBtn = wrapper.findAll('button').find(b => b.text().includes('下一页'))
    await nextBtn.trigger('click')
    await flushPromises()

    expect(getExamItems).toHaveBeenCalledTimes(2)
    expect(getExamItems).toHaveBeenNthCalledWith(2, 'Z', 2, 10)
  })

  it('nodeId change resets page to 1 (R2 F002 mutant: 删 watch page 重置必红)', async () => {
    getExamItems.mockResolvedValue({ items: [{ id: '1', stem: 's' }], total: 30 })
    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'A' } })
    await flushPromises()

    const nextBtn = wrapper.findAll('button').find(b => b.text().includes('下一页'))
    await nextBtn.trigger('click')
    await flushPromises()
    expect(getExamItems).toHaveBeenLastCalledWith('A', 2, 10)

    await wrapper.setProps({ nodeId: 'B' })
    await flushPromises()
    expect(getExamItems).toHaveBeenLastCalledWith('B', 1, 10)
  })
})
