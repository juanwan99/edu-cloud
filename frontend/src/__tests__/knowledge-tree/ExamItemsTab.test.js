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

  // R3 Batch 3.b.iii — R2-F001 fetchSeq guard race mutant 测试锁定
  // 设计契约 (handoff-batch3biii §Fix Intent Card):
  //   - 用 deferred promise 受控挂起 getExamItems（禁 mockResolvedValue 同步 / 禁 sleep）
  //   - 通过 setProps({ nodeId }) 触发 nodeId 切换入口，fetchSeq++ 递增
  //   - 两路径：resolve race (try guard) + reject race (catch guard)
  //   - 断言最终 DOM 停在新请求 B，旧请求 A 晚到不覆盖
  // 反证矩阵 (ExamItemsTab.vue):
  //   - 删 L56 try 块 `if (mySeq !== fetchSeq) return` → Test A 红（A 覆盖 B：含 'stem-A' + '99'）
  //   - 删 L60 catch 块 `if (mySeq !== fetchSeq) return` → Test B 红（A reject 清空：不含 'stem-B'/'11'）

  it('race condition: B resolve → A resolve, UI 停在 B (try guard 锁)', async () => {
    let resolveA, resolveB
    const promiseA = new Promise((r) => { resolveA = r })
    const promiseB = new Promise((r) => { resolveB = r })
    getExamItems.mockReturnValueOnce(promiseA).mockReturnValueOnce(promiseB)

    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'A' } })
    await flushPromises()  // fetchSeq=1, promiseA 挂起

    await wrapper.setProps({ nodeId: 'B' })
    await flushPromises()  // fetchSeq=2, promiseB 挂起

    resolveB({ items: [{ id: 'B1', exam_id: 'GK_2020_B', question_type: 'single_choice', stem: 'stem-B' }], total: 11 })
    await flushPromises()  // B 先 resolve：items=B, total=11

    resolveA({ items: [{ id: 'A1', exam_id: 'GK_2019_A', question_type: 'single_choice', stem: 'stem-A' }], total: 99 })
    await flushPromises()  // A 晚到：mySeq=1 !== fetchSeq=2 → try guard return，不覆盖

    const text = wrapper.text()
    expect(text).toContain('stem-B')
    expect(text).not.toContain('stem-A')
    expect(text).toContain('11')
    expect(text).not.toContain('99')
  })

  it('race condition: B resolve → A reject, UI 停在 B (catch guard 锁)', async () => {
    let resolveA, rejectA, resolveB
    const promiseA = new Promise((res, rej) => { resolveA = res; rejectA = rej })
    const promiseB = new Promise((res) => { resolveB = res })
    getExamItems.mockReturnValueOnce(promiseA).mockReturnValueOnce(promiseB)

    const wrapper = mount(ExamItemsTab, { props: { nodeId: 'A' } })
    await flushPromises()  // fetchSeq=1

    await wrapper.setProps({ nodeId: 'B' })
    await flushPromises()  // fetchSeq=2

    resolveB({ items: [{ id: 'B1', exam_id: 'GK_2020_B', question_type: 'single_choice', stem: 'stem-B' }], total: 11 })
    await flushPromises()  // items=B, total=11

    rejectA(new Error('stale A failed'))
    await flushPromises()  // A 晚到 reject：mySeq=1 !== fetchSeq=2 → catch guard return，不清空

    const text = wrapper.text()
    expect(text).toContain('stem-B')
    expect(text).toContain('11')
    // unused hoist to avoid lint (keep 引用)
    void resolveA
  })
})
