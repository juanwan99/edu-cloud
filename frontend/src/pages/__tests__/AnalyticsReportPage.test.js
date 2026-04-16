import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import AnalyticsReportPage from '../AnalyticsReportPage.vue'

const mockQueryReport = vi.fn()
const mockExportGradeReport = vi.fn()
const mockGetExamSummary = vi.fn().mockResolvedValue({ data: { subjects: [] } })
const mockDownloadBlob = vi.fn()

vi.mock('../../api/analytics', () => ({
  queryReport: (...args) => mockQueryReport(...args),
  exportGradeReport: (...args) => mockExportGradeReport(...args),
  getExamSummary: (...args) => mockGetExamSummary(...args),
  downloadBlob: (...args) => mockDownloadBlob(...args),
}))

vi.mock('../../api/client', () => ({
  default: { get: vi.fn().mockResolvedValue({ data: [] }) },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div />', props: ['option'] },
}))

const mockWarning = vi.fn()
const mockError = vi.fn()
const mockSuccess = vi.fn()
vi.mock('naive-ui', () => ({
  useMessage: () => ({ warning: mockWarning, error: mockError, success: mockSuccess }),
}))

function createWrapper() {
  return mount(AnalyticsReportPage, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'n-card': { template: '<div><slot /></div>', props: ['title'] },
        'n-space': { template: '<div><slot /></div>' },
        'n-select': { template: '<div />', props: ['modelValue', 'options', 'multiple', 'placeholder'], emits: ['update:modelValue'] },
        'n-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
        'n-tabs': { template: '<div><slot /></div>' },
        'n-tab-pane': { template: '<div><slot /></div>' },
        'n-descriptions': true,
        'n-descriptions-item': true,
        'n-data-table': true,
      },
    },
  })
}

describe('AnalyticsReportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders query controls', () => {
    const wrapper = createWrapper()
    expect(wrapper.html()).toBeTruthy()
    expect(wrapper.text()).toContain('生成分析')
  })

  it('warns when querying without exam selection', async () => {
    const wrapper = createWrapper()
    const buttons = wrapper.findAll('button')
    const queryBtn = buttons.find(b => b.text().includes('生成分析'))
    await queryBtn.trigger('click')
    await flushPromises()
    expect(mockWarning).toHaveBeenCalledWith('请至少选择一次考试')
    expect(mockQueryReport).not.toHaveBeenCalled()
  })

  it('calls queryReport with correct params on successful query', async () => {
    mockQueryReport.mockResolvedValue({
      data: { exam_ids: ['e1'], metrics: { summary: { total_students: 10 } } },
    })
    const wrapper = createWrapper()
    wrapper.vm.selectedExamIds = ['exam-1']
    wrapper.vm.selectedMetrics = ['summary']
    await wrapper.vm.runQuery()
    await flushPromises()
    expect(mockQueryReport).toHaveBeenCalledWith({
      exam_ids: ['exam-1'],
      metrics: ['summary'],
    })
    expect(wrapper.vm.reportData).toBeTruthy()
    expect(wrapper.vm.reportData.metrics.summary.total_students).toBe(10)
  })

  it('warns when downloading without exam + subject', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.handleDownload('pdf')
    expect(mockWarning).toHaveBeenCalledWith('请选择 1 次考试 + 1 个科目后再导出')
    expect(mockExportGradeReport).not.toHaveBeenCalled()
  })

  it('calls exportGradeReport + downloadBlob on download action', async () => {
    mockExportGradeReport.mockResolvedValue({
      data: new Blob(['fake-pdf'], { type: 'application/pdf' }),
      headers: { 'content-disposition': "attachment; filename*=UTF-8''report.pdf" },
    })
    const wrapper = createWrapper()
    wrapper.vm.selectedExamIds = ['exam-1']
    wrapper.vm.exportSubjectId = 'subj-1'
    await wrapper.vm.handleDownload('xlsx')
    await flushPromises()
    expect(mockExportGradeReport).toHaveBeenCalledWith('exam-1', 'subj-1', 'xlsx')
    expect(mockDownloadBlob).toHaveBeenCalled()
    expect(mockError).not.toHaveBeenCalled()
  })
})
