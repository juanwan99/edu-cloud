import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

const dialogStub = {
  warning: vi.fn(() => ({ destroy: vi.fn() })),
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
    data: { id: 'exam-unmount-test', name: 'U', status: 'draft', card_title: '' },
  }),
  updateExam: vi.fn().mockResolvedValue({ data: { ok: true } }),
}))
vi.mock('../../api/subjects', () => ({
  listSubjects: vi.fn().mockResolvedValue({ data: [] }),
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
  publishCard: vi.fn(),
  getCleanHTML: vi.fn().mockReturnValue('<html/>'),
}))

describe('ExamDetailPage unmount cleanup — 回归守护', () => {
  let router
  let consoleErrorSpy

  beforeEach(() => {
    setActivePinia(createPinia())
    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/exams/:id', name: 'ExamDetail', component: { template: '<div/>' } }],
    })
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('卸载时不应抛 ReferenceError: stopScanPolling is not defined（历史迁移残留回归）', async () => {
    router.push('/exams/exam-unmount-test')
    await router.isReady()

    const ExamDetailPage = (await import('../ExamDetailPage.vue')).default
    const wrapper = mount(ExamDetailPage, {
      global: {
        plugins: [router],
        stubs: { CardEditor: true, NDataTable: true },
      },
    })
    await flushPromises()

    wrapper.unmount()
    await flushPromises()

    const errorOutput = consoleErrorSpy.mock.calls
      .flat()
      .map((a) => (a instanceof Error ? `${a.name}: ${a.message}` : String(a)))
      .join('\n')

    expect(errorOutput).not.toMatch(/stopScanPolling is not defined/)
    expect(errorOutput).not.toMatch(/ReferenceError.*stopScanPolling/)
  })
})
