import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import AiGradingReportPage from '../AiGradingReportPage.vue'

const mockGetAiGradingReport = vi.fn()
const mockGetExamSummary = vi.fn().mockResolvedValue({
  data: { subjects: [{ subject_id: 'subj-1', subject_name: '语文' }] },
})
const mockClientGet = vi.fn().mockResolvedValue({ data: [{ id: 'exam-1', name: '期中考试' }] })

vi.mock('../../api/analytics', () => ({
  getAiGradingReport: (...args) => mockGetAiGradingReport(...args),
  getExamSummary: (...args) => mockGetExamSummary(...args),
}))

vi.mock('../../api/client', () => ({
  default: { get: (...args) => mockClientGet(...args) },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="chart-stub" />', props: ['option'] },
}))

const mockWarning = vi.fn()
const mockError = vi.fn()
vi.mock('naive-ui', () => {
  const stub = (name) => ({ name, template: '<div><slot /></div>', props: { value: null, options: Array } })
  return {
    useMessage: () => ({ warning: mockWarning, error: mockError, success: vi.fn(), info: vi.fn() }),
    NSelect: stub('NSelect'), NButton: stub('NButton'), NCard: stub('NCard'),
    NSpace: stub('NSpace'), NTabs: stub('NTabs'), NTabPane: stub('NTabPane'),
    NDataTable: stub('NDataTable'), NSpin: stub('NSpin'), NTag: stub('NTag'),
    NInput: stub('NInput'), NImage: stub('NImage'), NAlert: stub('NAlert'),
    NGi: stub('NGi'), NGrid: stub('NGrid'), NStatistic: stub('NStatistic'),
  }
})

function createWrapper() {
  return mount(AiGradingReportPage, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'n-space': { template: '<div><slot /></div>' },
        'n-select': { template: '<div />', props: ['modelValue', 'options', 'placeholder'] },
        'n-button': { template: '<button @click="$emit(\'click\')"><slot /></button>', emits: ['click'] },
        'n-card': { template: '<section><h3>{{ title }}</h3><slot /></section>', props: ['title'] },
        'n-data-table': true,
        'n-alert': { template: '<div><slot /></div>' },
        'n-tag': { template: '<span><slot /></span>' },
        'n-progress': true,
        'n-statistic': true,
        'n-grid': { template: '<div><slot /></div>' },
        'n-gi': { template: '<div><slot /></div>' },
        'n-spin': { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('AiGradingReportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetExamSummary.mockResolvedValue({
      data: { subjects: [{ subject_id: 'subj-1', subject_name: '语文' }] },
    })
    mockClientGet.mockResolvedValue({ data: [{ id: 'exam-1', name: '期中考试' }] })
  })

  it('renders AI grading report controls and sections', async () => {
    mockGetAiGradingReport.mockResolvedValue({
      data: {
        coverage: { answer_count: 3, ai_scored_count: 2, confirmed_count: 1, pending_review_count: 1 },
        confidence: { avg_confidence: 0.7, low_confidence_count: 1, buckets: { high: 1, medium: 0, low: 1 } },
        quality: { avg_abs_delta: 1, override_count: 1, question_delta_top: [] },
        ocr_pipeline: { log_count: 2, error_count: 1, blank_count: 1, avg_total_ms: 1500 },
        question_diagnostics: [{ question_id: 'q1', question_name: '12', score_rate: 0.5, low_confidence_count: 1, error_causes: [] }],
        student_watchlist: [{ student_id: 's1', student_name: '学生1', score_rate: 0.4, low_confidence_count: 1 }],
        teaching_actions: [{ title: '优先讲评第 12 题', priority: 'high' }],
        data_warnings: [{ type: 'missing_knowledge_links', message: '题目暂未绑定知识点，知识点诊断不可用。' }],
      },
    })
    const wrapper = createWrapper()
    await flushPromises()

    wrapper.vm.selectedExamId = 'exam-1'
    await wrapper.vm.loadReport()
    await flushPromises()

    expect(mockGetAiGradingReport).toHaveBeenCalledWith('exam-1', {})
    expect(wrapper.text()).toContain('AI 阅卷报告')
    expect(wrapper.text()).toContain('AI 阅卷总览')
    expect(wrapper.text()).toContain('质量审计')
    expect(wrapper.text()).toContain('OCR 与流水线')
    expect(wrapper.text()).toContain('题目诊断')
    expect(wrapper.text()).toContain('学生预警')
    expect(wrapper.text()).toContain('教学建议')
  })

  it('passes subject and class filters to the report api', async () => {
    mockGetAiGradingReport.mockResolvedValue({ data: { coverage: {} } })
    const wrapper = createWrapper()
    wrapper.vm.selectedExamId = 'exam-1'
    wrapper.vm.selectedSubjectId = 'subj-1'
    wrapper.vm.selectedClassId = 'class-1'

    await wrapper.vm.loadReport()
    await flushPromises()

    expect(mockGetAiGradingReport).toHaveBeenCalledWith('exam-1', {
      subject_id: 'subj-1',
      class_id: 'class-1',
    })
  })

  it('warns before loading without exam selection', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.loadReport()
    expect(mockWarning).toHaveBeenCalledWith('请选择考试')
    expect(mockGetAiGradingReport).not.toHaveBeenCalled()
  })
})
