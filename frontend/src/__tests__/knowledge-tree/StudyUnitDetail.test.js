import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StudyUnitDetail from '../../components/knowledge-tree/StudyUnitDetail.vue'

const mockData = {
  id: 'su:m1_001',
  name: '细胞学说',
  description: '关于细胞的基本学说',
  estimated_minutes: 90,
  textbook: [{ book: '必修1 分子与细胞', section: '第1章第1节', page_range: 'P3-P8' }],
  prerequisites: [{ category: '必经前置', target_name: '基础化学', target_module: 'M1', evidence: '需要化学基础' }],
  successors: [{ category: '后续单元', target_name: '细胞膜', target_module: 'M1' }],
  contrasts: [{ category: '对比关系', target_name: '原核细胞', evidence: '结构差异' }],
  concepts: [{ id: 'BIO_SR_CP_M1_A', name: '概念A', level: 'L1', description: '描述A' }],
  curriculum: [{ mastery_verb: '描述', text: '能描述细胞的基本结构', requirement_type: 'content_requirement' }],
  exam_patterns: [
    { band: '基础调用', count: 15, sample_items: [{ id: 'ai1', stem: '下列关于细胞的说法...', type: 'choice' }] },
    { band: '情境应用', count: 8, sample_items: [] },
    { band: '综合迁移', count: 3, sample_items: [] },
  ],
}

describe('StudyUnitDetail', () => {
  it('renders unit name and textbook', () => {
    const wrapper = mount(StudyUnitDetail, { props: { data: mockData } })
    expect(wrapper.text()).toContain('细胞学说')
    expect(wrapper.text()).toContain('必修1 分子与细胞')
  })

  it('renders prerequisite relations', () => {
    const wrapper = mount(StudyUnitDetail, { props: { data: mockData } })
    expect(wrapper.text()).toContain('必经前置')
    expect(wrapper.text()).toContain('基础化学')
  })

  it('renders exam pattern bands', () => {
    const wrapper = mount(StudyUnitDetail, { props: { data: mockData } })
    expect(wrapper.text()).toContain('基础调用')
    expect(wrapper.text()).toContain('情境应用')
    expect(wrapper.text()).toContain('综合迁移')
  })

  it('emits select-concept on concept click', async () => {
    const wrapper = mount(StudyUnitDetail, { props: { data: mockData } })
    const pills = wrapper.findAll('[data-testid="concept-pill"]')
    expect(pills.length).toBeGreaterThan(0)
    await pills[0].trigger('click')
    expect(wrapper.emitted('select-concept')).toBeTruthy()
    expect(wrapper.emitted('select-concept')[0]).toEqual(['BIO_SR_CP_M1_A'])
  })

  it('emits back on back button click', async () => {
    const wrapper = mount(StudyUnitDetail, { props: { data: mockData } })
    const back = wrapper.find('[data-testid="back-btn"]')
    await back.trigger('click')
    expect(wrapper.emitted('back')).toBeTruthy()
  })

  it('renders null data gracefully', () => {
    const wrapper = mount(StudyUnitDetail, { props: { data: null } })
    expect(wrapper.text()).toContain('') // no crash
  })
})
