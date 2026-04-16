import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

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

vi.mock('../../api/exams', () => ({
  getExam: vi.fn().mockResolvedValue({
    data: {
      id: 'exam-route-params-id',
      name: 'Test Exam',
      status: 'draft',
      card_title: '',
    },
  }),
  updateExam: vi.fn().mockResolvedValue({ data: { ok: true } }),
}))

vi.mock('../../api/subjects', () => ({
  listSubjects: vi.fn().mockResolvedValue({
    data: [{ id: 'subject-abc', name: '数学', code: 'SX' }],
  }),
  createSubject: vi.fn().mockResolvedValue({ data: {} }),
}))

vi.mock('../../api/rubrics', () => ({
  getRubric: vi.fn().mockResolvedValue({ data: null }),
  upsertRubric: vi.fn().mockResolvedValue({ data: {} }),
}))
vi.mock('../../api/cards', () => ({
  generateBarcode: vi.fn(),
  parseAnswers: vi.fn(),
  previewByWeights: vi.fn(),
  generateCardV2: vi.fn(),
}))
vi.mock('../../api/scan', () => ({
  scanDirectory: vi.fn(),
  startPipeline: vi.fn(),
  getPipelineProgress: vi.fn(),
  stopPipeline: vi.fn(),
  previewScan: vi.fn(),
  importTpl: vi.fn(),
}))

vi.mock('../../card-editor/export.js', () => ({
  publishCard: publishCardSpy,
  getCleanHTML: vi.fn().mockReturnValue('<html/>'),
}))

describe('F003 Task 10 V3: ExamDetailPage publishCard 3-arg 调用', () => {
  let router

  beforeEach(() => {
    setActivePinia(createPinia())
    publishCardSpy.mockClear()
    dialogStub.warning.mockClear()

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/exams/:id', name: 'ExamDetail', component: { template: '<div/>' } },
      ],
    })
  })

  it('V3: handlePublishCard 调用 publishCard 时 examId = route.params.id', { timeout: 15000 }, async () => {
    const testExamId = 'exam-route-params-id'
    router.push(`/exams/${testExamId}`)
    await router.isReady()

    const ExamDetailPage = (await import('../ExamDetailPage.vue')).default
    const wrapper = mount(ExamDetailPage, {
      global: {
        plugins: [router],
        stubs: {
          CardEditor: true,
          NDataTable: true,
        },
      },
    })
    await flushPromises()

    wrapper.vm.visualEditorSubjectId = 'subject-abc'
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
    const testExamId = 'exam-route-params-id'
    router.push(`/exams/${testExamId}`)
    await router.isReady()

    const ExamDetailPage = (await import('../ExamDetailPage.vue')).default
    const wrapper = mount(ExamDetailPage, {
      global: {
        plugins: [router],
        stubs: { CardEditor: true, NDataTable: true },
      },
    })
    await flushPromises()

    const btn = wrapper.find('[data-testid="publish-card-btn"]')
    expect(btn.exists()).toBe(true)
    expect(btn.attributes('disabled')).toBeDefined()
  })
})
