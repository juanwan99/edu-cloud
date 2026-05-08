import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const mockLayerData = {
  exam_id: 'exam-1',
  layers: [
    {
      label: '优秀',
      count: 12,
      avgScoreRate: 0.92,
      knowledgeMastery: [
        { knpId: 'K031', avgRate: 0.88 },
        { knpId: 'K045', avgRate: 0.95 },
      ],
    },
    {
      label: '良好',
      count: 25,
      avgScoreRate: 0.71,
      knowledgeMastery: [
        { knpId: 'K031', avgRate: 0.65 },
      ],
    },
    {
      label: '待提升',
      count: 8,
      avgScoreRate: 0.45,
      knowledgeMastery: [
        { knpId: 'K031', avgRate: 0.32 },
      ],
    },
  ],
  maxDiffKnowledges: [
    { knpId: 'K031', topLayerRate: 0.95, bottomLayerRate: 0.32, diff: 0.63 },
    { knpId: 'K045', topLayerRate: 0.88, bottomLayerRate: 0.41, diff: 0.47 },
  ],
}

vi.mock('../../../api/analytics', () => ({
  getLayerAnalysis: vi.fn().mockResolvedValue({ data: mockLayerData }),
}))

vi.mock('vue-echarts', () => ({
  default: { name: 'VChart', template: '<div class="vchart-stub" />', props: ['option', 'autoresize'] },
}))

vi.mock('echarts/core', () => ({
  use: vi.fn(),
}))

vi.mock('echarts/charts', () => ({
  BarChart: {},
}))

vi.mock('echarts/components', () => ({
  GridComponent: {},
  TooltipComponent: {},
  LegendComponent: {},
}))

vi.mock('echarts/renderers', () => ({
  CanvasRenderer: {},
}))

const NAIVE_STUBS = {
  'n-spin': { template: '<div class="n-spin" :data-show="show"><slot /></div>', props: ['show'] },
  'n-empty': { template: '<div class="n-empty">{{ description }}</div>', props: ['description'] },
  'n-grid': { template: '<div class="n-grid"><slot /></div>', props: ['cols', 'xGap'] },
  'n-gi': { template: '<div class="n-gi"><slot /></div>' },
  'n-card': { template: '<div class="n-card" :data-title="title"><slot /></div>', props: ['title', 'size'] },
  'n-space': { template: '<div class="n-space"><slot /></div>', props: ['vertical', 'size'] },
  'n-progress': { template: '<div class="n-progress" :data-percentage="percentage" />', props: ['type', 'percentage', 'color', 'railColor', 'showIndicator'] },
  'n-collapse': { template: '<div class="n-collapse"><slot /></div>' },
  'n-collapse-item': { template: '<div class="n-collapse-item"><slot /></div>', props: ['title'] },
}

describe('LayerAnalysisPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders normal data with stat cards and chart', async () => {
    const wrapper = mount(
      (await import('../LayerAnalysisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    // 3 layer stat cards + 1 diff chart card + 1 collapse card = 5 n-card
    const cards = wrapper.findAll('.n-card')
    expect(cards.length).toBe(5)

    // Layer counts rendered
    expect(wrapper.text()).toContain('12')
    expect(wrapper.text()).toContain('25')
    expect(wrapper.text()).toContain('8')

    // Layer labels
    expect(wrapper.text()).toContain('优秀')
    expect(wrapper.text()).toContain('良好')
    expect(wrapper.text()).toContain('待提升')

    // avgScoreRate displayed
    expect(wrapper.text()).toContain('92.0%')
    expect(wrapper.text()).toContain('71.0%')
    expect(wrapper.text()).toContain('45.0%')

    // ECharts chart rendered
    expect(wrapper.find('.vchart-stub').exists()).toBe(true)
  })

  it('renders empty state when layers are empty', async () => {
    const { getLayerAnalysis } = await import('../../../api/analytics')
    getLayerAnalysis.mockResolvedValueOnce({
      data: { exam_id: 'exam-1', layers: [], maxDiffKnowledges: [] },
    })

    const wrapper = mount(
      (await import('../LayerAnalysisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    expect(wrapper.find('.n-empty').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无分层学情数据')
  })

  it('shows loading spinner while fetching', async () => {
    let resolvePromise
    const { getLayerAnalysis } = await import('../../../api/analytics')
    getLayerAnalysis.mockImplementation(() => new Promise(r => { resolvePromise = r }))

    const mod = await import('../LayerAnalysisPanel.vue')
    const wrapper = mount(mod.default, {
      props: { examId: 'exam-1' },
      global: { stubs: NAIVE_STUBS },
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.vm.loading).toBe(true)

    resolvePromise({ data: mockLayerData })
    await flushPromises()

    expect(wrapper.vm.loading).toBe(false)

    // Restore default mock
    getLayerAnalysis.mockResolvedValue({ data: mockLayerData })
  })

  it('reloads data when props change', async () => {
    const { getLayerAnalysis } = await import('../../../api/analytics')

    const wrapper = mount(
      (await import('../LayerAnalysisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    expect(getLayerAnalysis).toHaveBeenCalledTimes(1)

    await wrapper.setProps({ examId: 'exam-2' })
    await flushPromises()

    expect(getLayerAnalysis).toHaveBeenCalledTimes(2)
    expect(getLayerAnalysis).toHaveBeenLastCalledWith('exam-2', {})
  })

  it('layerColor returns correct colors per label', async () => {
    const wrapper = mount(
      (await import('../LayerAnalysisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    const vm = wrapper.vm
    expect(vm.layerColor('优秀')).toBe('#22C55E')
    expect(vm.layerColor('良好')).toBe('#644CF0')
    expect(vm.layerColor('待提升')).toBe('#ED9A51')
  })

  it('diffChartOption has correct structure', async () => {
    const wrapper = mount(
      (await import('../LayerAnalysisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    const opt = wrapper.vm.diffChartOption
    expect(opt.yAxis.data).toEqual(['K031', 'K045'])
    expect(opt.series).toHaveLength(2)
    expect(opt.series[0].name).toBe('优秀层')
    expect(opt.series[0].data).toEqual([0.95, 0.88])
    expect(opt.series[1].name).toBe('待提升层')
    expect(opt.series[1].data).toEqual([0.32, 0.41])
  })

  it('passes subject_id and class_id params', async () => {
    const { getLayerAnalysis } = await import('../../../api/analytics')

    mount(
      (await import('../LayerAnalysisPanel.vue')).default,
      {
        props: { examId: 'exam-1', subjectId: 'math', classId: 'cls-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    expect(getLayerAnalysis).toHaveBeenCalledWith('exam-1', {
      subject_id: 'math',
      class_id: 'cls-1',
    })
  })

  it('handles API error gracefully', async () => {
    const { getLayerAnalysis } = await import('../../../api/analytics')
    getLayerAnalysis.mockRejectedValueOnce(new Error('Network error'))

    const wrapper = mount(
      (await import('../LayerAnalysisPanel.vue')).default,
      {
        props: { examId: 'exam-1' },
        global: { stubs: NAIVE_STUBS },
      },
    )
    await flushPromises()

    // Should show empty state after error
    expect(wrapper.vm.isEmpty).toBe(true)
    expect(wrapper.vm.loading).toBe(false)
  })
})
