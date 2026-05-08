import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

// --- Mock data ---

const MOCK_GRADE_TREND = {
  points: [
    { exam_name: '月考', avg: 72.5, pass_rate: 0.82, excellent_rate: 0.15 },
    { exam_name: '期中考试', avg: 78.3, pass_rate: 0.88, excellent_rate: 0.22 },
  ],
}

const MOCK_CLASS_TREND = {
  points: [
    { exam_name: '月考', class_avg: 70.1, grade_avg: 72.5, pass_rate: 0.78, excellent_rate: 0.12 },
    { exam_name: '期中考试', class_avg: 76.0, grade_avg: 78.3, pass_rate: 0.85, excellent_rate: 0.20 },
  ],
}

const MOCK_EMPTY_TREND = { points: [] }

// --- Mocks ---

const mockGetGradeTrend = vi.fn(() => Promise.resolve({ data: MOCK_GRADE_TREND }))
const mockGetClassTrend = vi.fn(() => Promise.resolve({ data: MOCK_CLASS_TREND }))
const mockGetStudentTrend = vi.fn(() => Promise.resolve({ data: MOCK_EMPTY_TREND }))

vi.mock('../../../api/analytics', () => ({
  getGradeTrend: (...args) => mockGetGradeTrend(...args),
  getClassTrend: (...args) => mockGetClassTrend(...args),
  getStudentTrend: (...args) => mockGetStudentTrend(...args),
}))

vi.mock('vue-echarts', () => ({
  default: {
    name: 'VChart',
    template: '<div class="vchart-stub" />',
    props: ['option'],
  },
}))

const stubs = {
  'n-spin': { template: '<div class="n-spin"><slot /></div>', props: ['show'] },
  'n-space': { template: '<div class="n-space"><slot /></div>' },
  'n-radio-group': {
    template: '<div class="n-radio-group"><slot /></div>',
    props: ['value'],
    emits: ['update:value'],
  },
  'n-radio-button': {
    template: '<button class="n-radio-button" @click="$emit(\'click\')"><slot /></button>',
    props: ['value'],
    emits: ['click'],
  },
  'n-checkbox-group': {
    template: '<div class="n-checkbox-group"><slot /></div>',
    props: ['value'],
    emits: ['update:value'],
  },
  'n-checkbox': {
    template: '<label class="n-checkbox">{{ label }}</label>',
    props: ['value', 'label'],
  },
  'n-empty': {
    template: '<div class="n-empty" :data-description="description" />',
    props: ['description'],
  },
}

async function createWrapper(propsData = {}) {
  const comp = (await import('../TrendPanel.vue')).default
  const wrapper = mount(comp, {
    props: { gradeId: 'g1', ...propsData },
    global: { stubs },
  })
  await flushPromises()
  return wrapper
}

describe('TrendPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetGradeTrend.mockResolvedValue({ data: MOCK_GRADE_TREND })
    mockGetClassTrend.mockResolvedValue({ data: MOCK_CLASS_TREND })
    mockGetStudentTrend.mockResolvedValue({ data: MOCK_EMPTY_TREND })
  })

  it('renders chart with grade trend data on mount', async () => {
    const wrapper = await createWrapper()

    // Should have called getGradeTrend
    expect(mockGetGradeTrend).toHaveBeenCalledTimes(1)

    // VChart stub should be rendered
    expect(wrapper.find('.vchart-stub').exists()).toBe(true)

    // No empty state
    expect(wrapper.find('.n-empty').exists()).toBe(false)
  })

  it('shows empty state when no trend data', async () => {
    mockGetGradeTrend.mockResolvedValue({ data: MOCK_EMPTY_TREND })
    const wrapper = await createWrapper()

    // Empty state should appear
    const empty = wrapper.find('.n-empty')
    expect(empty.exists()).toBe(true)
    expect(empty.attributes('data-description')).toBe('暂无趋势数据')

    // No chart
    expect(wrapper.find('.vchart-stub').exists()).toBe(false)
  })

  it('builds correct chart option with grade dimension series', async () => {
    const wrapper = await createWrapper()
    const vm = wrapper.vm

    expect(vm.chartOption).not.toBeNull()
    // Default metrics: avg + pass_rate
    const seriesNames = vm.chartOption.series.map(s => s.name)
    expect(seriesNames).toContain('均分')
    expect(seriesNames).toContain('及格率')
    // excellent_rate not visible by default
    expect(seriesNames).not.toContain('优秀率')
  })

  it('dimension switch triggers data reload with correct API', async () => {
    const wrapper = await createWrapper({ gradeId: 'g1', classId: 'c1' })
    const vm = wrapper.vm

    expect(mockGetGradeTrend).toHaveBeenCalledTimes(1)

    // Switch to class dimension
    vm.dimension = 'class'
    vm.onDimensionChange()
    await flushPromises()

    expect(mockGetClassTrend).toHaveBeenCalledTimes(1)
    expect(mockGetClassTrend).toHaveBeenCalledWith(
      expect.objectContaining({ class_id: 'c1' })
    )
  })

  it('dimension switch to student triggers getStudentTrend', async () => {
    const wrapper = await createWrapper({ gradeId: 'g1', classId: 'c1' })
    const vm = wrapper.vm

    vm.dimension = 'student'
    vm.onDimensionChange()
    await flushPromises()

    expect(mockGetStudentTrend).toHaveBeenCalledTimes(1)
  })

  it('reloads data when props change', async () => {
    const wrapper = await createWrapper({ gradeId: 'g1' })
    expect(mockGetGradeTrend).toHaveBeenCalledTimes(1)

    // Simulate prop change
    await wrapper.setProps({ gradeId: 'g2' })
    await flushPromises()

    expect(mockGetGradeTrend).toHaveBeenCalledTimes(2)
    expect(mockGetGradeTrend).toHaveBeenLastCalledWith(
      expect.objectContaining({ grade_id: 'g2' })
    )
  })

  it('class dimension renders class_avg and grade_avg series', async () => {
    const wrapper = await createWrapper({ gradeId: 'g1', classId: 'c1' })
    const vm = wrapper.vm

    vm.dimension = 'class'
    vm.onDimensionChange()
    await flushPromises()

    const seriesNames = vm.chartOption.series.map(s => s.name)
    expect(seriesNames).toContain('班级均分')
    expect(seriesNames).toContain('年级均分')
  })

  it('handles API error gracefully and shows empty state', async () => {
    mockGetGradeTrend.mockRejectedValue(new Error('network error'))
    const wrapper = await createWrapper()

    // Should show empty state, no crash
    expect(wrapper.find('.n-empty').exists()).toBe(true)
    expect(wrapper.find('.vchart-stub').exists()).toBe(false)
  })
})
