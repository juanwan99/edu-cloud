import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import AnalyticsReportPage from '../AnalyticsReportPage.vue'

const mocks = vi.hoisted(() => ({
  getBasicReport: vi.fn(),
  exportGradeReport: vi.fn(),
  downloadBlob: vi.fn(),
  clientGet: vi.fn().mockResolvedValue({ data: [] }),
  warning: vi.fn(),
  error: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
}))

vi.mock('../../api/analytics', () => ({
  getBasicReport: (...args) => mocks.getBasicReport(...args),
  exportGradeReport: (...args) => mocks.exportGradeReport(...args),
  downloadBlob: (...args) => mocks.downloadBlob(...args),
}))

vi.mock('../../components/analytics/KnowledgeDiagnosisPanel.vue', () => ({
  default: { name: 'KnowledgeDiagnosisPanel', template: '<div />', props: ['examId', 'subjectId', 'classId'] },
}))
vi.mock('../../components/analytics/LayerAnalysisPanel.vue', () => ({
  default: { name: 'LayerAnalysisPanel', template: '<div />', props: ['examId', 'subjectId', 'classId'] },
}))
vi.mock('../../components/analytics/TrendPanel.vue', () => ({
  default: { name: 'TrendPanel', template: '<div />', props: ['gradeId', 'classId', 'subjectCode'] },
}))

vi.mock('../../api/client', () => ({
  default: { get: (...args) => mocks.clientGet(...args) },
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div />', props: ['option'] },
}))

vi.mock('naive-ui', () => ({
  useMessage: () => ({ warning: mocks.warning, error: mocks.error }),
}))

function basicReportPayload() {
  return {
    exam: { id: 'exam-1', name: '期中考试' },
    overview: {
      student_count: 10,
      avg_score: 82.5,
      max_score: 99,
      min_score: 60,
      median_score: 83,
      score_rate: 0.825,
      pass_rate: 0.8,
      excellent_rate: 0.2,
      subject_count: 1,
      total_full_score: 100,
    },
    subjects: [{
      subject_id: 'subj-1',
      subject_code: 'YW',
      subject_name: '语文',
      avg_score: 82.5,
      full_score: 100,
      score_rate: 0.825,
      student_count: 10,
      max_score: 99,
      min_score: 60,
      median_score: 83,
      pass_rate: 0.8,
      excellent_rate: 0.2,
    }],
    classes: [{
      class_id: 'class-1',
      class_name: '七年级1班',
      avg_score: 82.5,
      student_count: 10,
      rank: 1,
      max_score: 99,
      min_score: 60,
      score_rate: 0.825,
      pass_rate: 0.8,
      excellent_rate: 0.2,
      subjects: [{
        subject_id: 'subj-1',
        subject_code: 'YW',
        subject_name: '语文',
        avg_score: 82.5,
        full_score: 100,
        score_rate: 0.825,
        student_count: 10,
        max_score: 99,
        min_score: 60,
        pass_rate: 0.8,
        excellent_rate: 0.2,
      }],
    }],
    students: [{
      student_id: 's1',
      name: '张三',
      student_number: 'A001',
      class_name: '七年级1班',
      total_score: 82.5,
      score_rate: 0.825,
      grade_rank: 1,
      class_rank: 1,
      delta_grade: 2,
      delta_class: 1,
      subject_scores: { YW: { score: 82.5 } },
    }],
    distribution: [{
      label: '80-90',
      count: 6,
      percentage: 0.6,
      boundary_min: 80,
      boundary_max: 90,
    }],
    scope: {
      subject_id: 'subj-1',
      subject_name: '语文',
      subject_code: 'YW',
      class_id: 'class-1',
      class_name: '七年级1班',
      has_previous_exam: true,
      previous_exam: { id: 'exam-0', name: '上次考试' },
    },
  }
}

function createWrapper() {
  return mount(AnalyticsReportPage, {
    global: {
      plugins: [createPinia()],
      stubs: {
        'n-space': { template: '<div><slot /></div>' },
        'n-select': {
          template: '<div />',
          props: ['value', 'options', 'placeholder', 'clearable'],
          emits: ['update:value'],
        },
        'n-button': {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
          props: ['loading', 'disabled', 'type'],
          emits: ['click'],
        },
        'n-tabs': { template: '<div><slot /></div>', props: ['value', 'type', 'animated'] },
        'n-tab-pane': {
          template: '<div><span>{{ tab }}</span><slot /></div>',
          props: ['name', 'tab'],
        },
        'n-empty': {
          template: '<div>{{ description }}<slot /></div>',
          props: ['description', 'size'],
        },
        'n-data-table': true,
      },
    },
  })
}

describe('AnalyticsReportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.clientGet.mockResolvedValue({ data: [] })
  })

  it('renders basic report controls', () => {
    const wrapper = createWrapper()
    expect(wrapper.html()).toBeTruthy()
    expect(wrapper.text()).toContain('查看基础数据')
  })

  it('warns when querying without exam selection', async () => {
    const wrapper = createWrapper()
    const queryBtn = wrapper.findAll('button').find(b => b.text().includes('查看基础数据'))
    await queryBtn.trigger('click')
    await flushPromises()
    expect(mocks.warning).toHaveBeenCalledWith('请选择一次考试')
    expect(mocks.getBasicReport).not.toHaveBeenCalled()
  })

  it('calls getBasicReport with selected filters on successful query', async () => {
    mocks.getBasicReport.mockResolvedValue({ data: basicReportPayload() })
    const wrapper = createWrapper()
    wrapper.vm.selectedExamId = 'exam-1'
    wrapper.vm.selectedSubjectId = 'subj-1'
    wrapper.vm.selectedClassId = 'class-1'
    wrapper.vm.activeTab = 'students'
    await wrapper.vm.runQuery()
    await flushPromises()
    expect(mocks.getBasicReport).toHaveBeenCalledWith('exam-1', {
      subject_id: 'subj-1',
      class_id: 'class-1',
    })
    expect(wrapper.vm.basicReport.overview.student_count).toBe(10)
    expect(wrapper.vm.activeTab).toBe('overview')
    expect(wrapper.text()).toContain('科目：语文')
    expect(wrapper.text()).toContain('班级：七年级1班')
    expect(wrapper.text()).toContain('对比：上次考试')
    expect(wrapper.text()).toContain('总览')
    expect(wrapper.text()).toContain('班级对比')
    expect(wrapper.text()).toContain('科目分析')
    expect(wrapper.text()).toContain('知识点诊断')
    expect(wrapper.text()).toContain('学生排名')
  })

  it('builds tab data from returned basic report', async () => {
    mocks.getBasicReport.mockResolvedValue({ data: basicReportPayload() })
    const wrapper = createWrapper()
    wrapper.vm.selectedExamId = 'exam-1'
    await wrapper.vm.runQuery()
    await flushPromises()
    expect(wrapper.vm.studentColumns.map(col => col.title)).toContain('语文')
    expect(wrapper.vm.studentColumns.map(col => col.title)).toEqual(expect.arrayContaining(['学号', '班级进退']))
    expect(wrapper.vm.classColumns.map(col => col.title)).toContain('得分率')
    expect(wrapper.vm.classSubjectColumns.map(col => col.title)).toEqual(
      expect.arrayContaining(['参考人数', '最高分', '最低分', '及格率', '优秀率']),
    )
    expect(wrapper.vm.studentRows).toHaveLength(1)
    expect(wrapper.vm.studentTableScrollX).toBeGreaterThan(760)
    expect(wrapper.vm.classSubjectRows[0].subject_name).toBe('语文')
    expect(wrapper.vm.segmentChartOption.xAxis.data).toEqual(['80-90'])
    expect(wrapper.vm.subjectRateChartOption.xAxis.data).toEqual(['语文'])
  })

  it('shows empty states before and after empty report', async () => {
    const wrapper = createWrapper()
    expect(wrapper.text()).toContain('请选择考试后查看基础数据')
    const payload = basicReportPayload()
    mocks.getBasicReport.mockResolvedValue({
      data: {
        ...payload,
        overview: { ...payload.overview, student_count: 0 },
        subjects: [],
        classes: [],
        students: [],
        distribution: [],
        scope: { has_previous_exam: false },
      },
    })
    wrapper.vm.selectedExamId = 'exam-1'
    await wrapper.vm.runQuery()
    await flushPromises()
    expect(wrapper.text()).toContain('当前筛选范围暂无成绩数据')
  })

  it('warns when downloading without exam + subject', async () => {
    const wrapper = createWrapper()
    await wrapper.vm.handleDownload('pdf')
    expect(mocks.warning).toHaveBeenCalledWith('请选择 1 次考试 + 1 个科目后再导出')
    expect(mocks.exportGradeReport).not.toHaveBeenCalled()
  })

  it('calls exportGradeReport + downloadBlob on download action', async () => {
    mocks.exportGradeReport.mockResolvedValue({
      data: new Blob(['fake-pdf'], { type: 'application/pdf' }),
      headers: { 'content-disposition': "attachment; filename*=UTF-8''report.pdf" },
    })
    const wrapper = createWrapper()
    wrapper.vm.selectedExamId = 'exam-1'
    wrapper.vm.exportSubjectId = 'subj-1'
    await wrapper.vm.handleDownload('xlsx')
    await flushPromises()
    expect(mocks.exportGradeReport).toHaveBeenCalledWith('exam-1', 'subj-1', 'xlsx')
    expect(mocks.downloadBlob).toHaveBeenCalled()
    expect(mocks.error).not.toHaveBeenCalled()
  })
})
