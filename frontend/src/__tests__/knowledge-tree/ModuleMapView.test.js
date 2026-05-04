import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ModuleMapView from '../../components/knowledge-tree/ModuleMapView.vue'

const mockData = {
  module_id: 'M1',
  module_name: '分子与细胞',
  tagline: '从分子到细胞',
  total_hours: 45.5,
  study_units: [
    { id: 'su:m1_001', name: '细胞学说', description: '描述', estimated_minutes: 90, prerequisites: ['su:m1_000名'], concept_names: ['概念A'] },
    { id: 'su:m1_002', name: '细胞膜', description: null, estimated_minutes: 45, prerequisites: [], concept_names: [] },
  ],
  concept_clusters: [{ big_concept: '细胞学说', concepts: ['概念A', '概念B'] }],
  curriculum: [{ big_concept: '概念1', requirements: ['能描述细胞结构'] }],
  exam_profile: { total_items: 50, near_pct: 0.4, mid_pct: 0.35, far_pct: 0.25 },
  outgoing_bridges: [{ source_name: 'A', target_name: 'B', source_module: 'M1', target_module: 'M3' }],
}

describe('ModuleMapView', () => {
  it('renders module header', () => {
    const wrapper = mount(ModuleMapView, { props: { data: mockData } })
    expect(wrapper.text()).toContain('分子与细胞')
    expect(wrapper.text()).toContain('45.5')
  })

  it('renders study unit cards', () => {
    const wrapper = mount(ModuleMapView, { props: { data: mockData } })
    expect(wrapper.text()).toContain('细胞学说')
    expect(wrapper.text()).toContain('细胞膜')
  })

  it('emits select-unit on card click', async () => {
    const wrapper = mount(ModuleMapView, { props: { data: mockData } })
    const cards = wrapper.findAll('[data-testid="su-card"]')
    expect(cards.length).toBeGreaterThan(0)
    await cards[0].trigger('click')
    expect(wrapper.emitted('select-unit')).toBeTruthy()
    expect(wrapper.emitted('select-unit')[0]).toEqual(['su:m1_001'])
  })

  it('emits back on back button click', async () => {
    const wrapper = mount(ModuleMapView, { props: { data: mockData } })
    const back = wrapper.find('[data-testid="back-btn"]')
    await back.trigger('click')
    expect(wrapper.emitted('back')).toBeTruthy()
  })

  it('renders null data gracefully', () => {
    const wrapper = mount(ModuleMapView, { props: { data: null } })
    expect(wrapper.text()).toContain('') // no crash
  })
})
