import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockDiagnosis = {
  worstKnowledges: [
    { concept_id: 'c1', name: '函数极值', rate: 0.32 },
    { concept_id: 'c2', name: '三角函数', rate: 0.55 },
    { concept_id: 'c3', name: '导数应用', rate: 0.78 },
  ],
  unmasterMaxCntKnowledges: [
    { concept_id: 'c1', name: '函数极值', count: 28 },
    { concept_id: 'c4', name: '概率统计', count: 15 },
  ],
  maxScoreDiffKnowledges: [
    { concept_id: 'c1', name: '函数极值', diff: 0.63 },
    { concept_id: 'c5', name: '立体几何', diff: 0.41 },
  ],
}

vi.mock('../../../api/analytics', () => ({
  getClassDiagnosis: vi.fn().mockResolvedValue({ data: mockDiagnosis }),
  getClassErrorPatterns: vi.fn().mockResolvedValue({ data: {} }),
  getQuestionInsights: vi.fn().mockResolvedValue({ data: {} }),
}))

const NAIVE_STUBS = {
  'n-spin': { template: '<div class="n-spin" :data-show="show"><slot /></div>', props: ['show'] },
  'n-empty': { template: '<div class="n-empty">{{ description }}</div>', props: ['description'] },
  'n-grid': { template: '<div class="n-grid"><slot /></div>', props: ['cols', 'xGap', 'yGap'] },
  'n-gi': { template: '<div class="n-gi"><slot /></div>' },
  'n-card': { template: '<div class="n-card"><slot /></div>', props: ['title', 'size'] },
  'n-space': { template: '<div class="n-space"><slot /></div>', props: ['vertical', 'size'] },
  'n-progress': { template: '<div class="n-progress" :data-percentage="percentage" :data-color="color" />', props: ['type', 'percentage', 'color', 'railColor', 'showIndicator'] },
  'n-tag': { template: '<span class="n-tag"><slot /></span>', props: ['size', 'bordered', 'type'] },
}

function createWrapper(props = {}) {
  return mount(
    (async () => (await import('../KnowledgeDiagnosisPanel.vue')).default)(),
    {
      props: { examId: 'exam-1', ...props },
      global: { stubs: NAIVE_STUBS },
    },
  )
}

describe('KnowledgeDiagnosisPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders normal data correctly', async () => {
    const wrapper = mount(
      (await import('../KnowledgeDiagnosisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    // 3 columns rendered
    const cards = wrapper.findAll('.n-card')
    expect(cards.length).toBe(3)

    // Check worst knowledges items
    const progressBars = wrapper.findAll('.n-progress')
    expect(progressBars.length).toBe(3) // 3 worstKnowledges

    // Check text content includes knowledge names
    expect(wrapper.text()).toContain('函数极值')
    expect(wrapper.text()).toContain('三角函数')
    expect(wrapper.text()).toContain('导数应用')

    // Check count tags
    expect(wrapper.text()).toContain('28人')
    expect(wrapper.text()).toContain('15人')

    // Check diff values
    expect(wrapper.text()).toContain('0.63')
    expect(wrapper.text()).toContain('0.41')
  })

  it('renders empty state when no data', async () => {
    const { getClassDiagnosis } = await import('../../../api/analytics')
    getClassDiagnosis.mockResolvedValueOnce({
      data: { worstKnowledges: [], unmasterMaxCntKnowledges: [], maxScoreDiffKnowledges: [] },
    })

    const wrapper = mount(
      (await import('../KnowledgeDiagnosisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    expect(wrapper.find('.n-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无知识点诊断数据')
  })

  it('shows loading spinner while fetching', async () => {
    let resolvePromise
    const { getClassDiagnosis } = await import('../../../api/analytics')
    getClassDiagnosis.mockImplementation(() => new Promise(r => { resolvePromise = r }))

    const mod = await import('../KnowledgeDiagnosisPanel.vue')
    const wrapper = mount(mod.default, {
      props: { examId: 'exam-1' },
      global: { stubs: NAIVE_STUBS },
    })

    // Spinner is visible during loading
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.loading).toBe(true)

    // Resolve the promise
    resolvePromise({ data: mockDiagnosis })
    await flushPromises()

    expect(wrapper.vm.loading).toBe(false)

    // Restore default mock
    getClassDiagnosis.mockResolvedValue({ data: mockDiagnosis })
  })

  it('reloads data when props change', async () => {
    const { getClassDiagnosis } = await import('../../../api/analytics')

    const wrapper = mount(
      (await import('../KnowledgeDiagnosisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    // First load
    expect(getClassDiagnosis).toHaveBeenCalledTimes(1)

    // Change examId
    await wrapper.setProps({ examId: 'exam-2' })
    await flushPromises()

    expect(getClassDiagnosis).toHaveBeenCalledTimes(2)
    expect(getClassDiagnosis).toHaveBeenLastCalledWith('exam-2', {})
  })

  it('rateColor returns correct colors', async () => {
    const wrapper = mount(
      (await import('../KnowledgeDiagnosisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    const vm = wrapper.vm
    expect(vm.rateColor(0.3)).toBe('#dc2626')   // red < 0.4
    expect(vm.rateColor(0.5)).toBe('#ED9A51')    // yellow < 0.7
    expect(vm.rateColor(0.8)).toBe('#22C55E')    // green >= 0.7
  })

  it('passes subject_id and class_id params', async () => {
    const { getClassDiagnosis } = await import('../../../api/analytics')

    mount(
      (await import('../KnowledgeDiagnosisPanel.vue')).default,
      {
        props: { examId: 'exam-1', subjectId: 'math', classId: 'cls-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    expect(getClassDiagnosis).toHaveBeenCalledWith('exam-1', {
      subject_id: 'math',
      class_id: 'cls-1',
    })
  })
})
