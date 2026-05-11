import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const publishCardSpy = vi.fn().mockResolvedValue(new Blob(['%PDF'], { type: 'application/pdf' }))

const dialogStub = {
  warning: vi.fn((options) => {
    if (options?.onPositiveClick) {
      Promise.resolve().then(() => options.onPositiveClick())
    }
    return { destroy: vi.fn() }
  }),
}
const messageStub = { success: vi.fn(), warning: vi.fn(), error: vi.fn(), info: vi.fn() }

vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useDialog: () => dialogStub,
    useMessage: () => messageStub,
  }
})

vi.mock('../../card-editor/export.js', () => ({
  publishCard: publishCardSpy,
  getCleanHTML: vi.fn().mockReturnValue('<html/>'),
  batchExportPdf: vi.fn(),
}))

describe('F003 Task 10 V3: VisualEditorTab publishCard 3-arg 调用', () => {
  beforeEach(() => {
    publishCardSpy.mockClear()
    dialogStub.warning.mockClear()
  })

  it('V3: handlePublishCard 调用 publishCard 时 examId = props.examId', { timeout: 15000 }, async () => {
    const testExamId = 'exam-route-params-id'
    const VisualEditorTab = (await import('../exam-detail/VisualEditorTab.vue')).default
    const wrapper = mount(VisualEditorTab, {
      props: {
        examId: testExamId,
        exam: { id: testExamId, name: 'Test Exam', status: 'draft', card_title: '' },
        subjects: [{ id: 'subject-abc', name: '数学', code: 'SX' }],
        subjectOptions: [{ label: '数学 (SX)', value: 'subject-abc' }],
        visualEditorSubjectId: 'subject-abc',
        pendingQuestions: null,
      },
      global: {
        stubs: { CardEditor: true },
      },
    })
    await flushPromises()

    await wrapper.vm.handlePublishCard()
    await flushPromises()
    await flushPromises()

    expect(dialogStub.warning).toHaveBeenCalledTimes(1)
    expect(publishCardSpy).toHaveBeenCalledTimes(1)

    const callArgs = publishCardSpy.mock.calls[0]
    expect(callArgs[0]).toBe('subject-abc')
    expect(callArgs[1]).toBe(testExamId)
    expect(typeof callArgs[2]).toBe('string')
    expect(callArgs[2]).toContain('答题卡')
  })

  it('V3b: 按钮 data-testid 存在且 disabled 行为正确', async () => {
    const VisualEditorTab = (await import('../exam-detail/VisualEditorTab.vue')).default
    const wrapper = mount(VisualEditorTab, {
      props: {
        examId: 'exam-route-params-id',
        exam: { id: 'exam-route-params-id', name: 'Test Exam', status: 'draft', card_title: '' },
        subjects: [],
        subjectOptions: [],
        visualEditorSubjectId: null,
        pendingQuestions: null,
      },
      global: {
        stubs: { CardEditor: true },
      },
    })
    await flushPromises()

    const btn = wrapper.find('[data-testid="publish-card-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeDefined()
  })
})
