import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import CourseMapOverview from '../../components/knowledge-tree/CourseMapOverview.vue'

const mockData = {
  modules: [
    { id: 'M1', name: '分子与细胞', tagline: 'tag', study_unit_count: 20, concept_count: 30, total_hours: 45.5, exam_tags: ['基础调用'] },
    { id: 'M3', name: '稳态与调节', tagline: 'tag2', study_unit_count: 15, concept_count: 25, total_hours: 30.0, exam_tags: [] },
  ],
  bridges: [{ source_name: 'A', target_name: 'B', source_module: 'M1', target_module: 'M3', evidence: 'link' }],
  curriculum: { content_count: 4, academic_count: 3, big_concepts: ['概念1'] },
  exam: { total_items: 150, near_count: 60, mid_count: 50, far_count: 40 },
}

describe('CourseMapOverview', () => {
  it('renders module cards', () => {
    const wrapper = mount(CourseMapOverview, { props: { data: mockData } })
    expect(wrapper.text()).toContain('分子与细胞')
    expect(wrapper.text()).toContain('稳态与调节')
    expect(wrapper.text()).toContain('20 个单元')
  })

  it('renders bridge info', () => {
    const wrapper = mount(CourseMapOverview, { props: { data: mockData } })
    expect(wrapper.text()).toContain('A')
    expect(wrapper.text()).toContain('B')
  })

  it('emits select-module on card click', async () => {
    const wrapper = mount(CourseMapOverview, { props: { data: mockData } })
    const cards = wrapper.findAll('[data-testid="module-card"]')
    expect(cards.length).toBeGreaterThan(0)
    await cards[0].trigger('click')
    expect(wrapper.emitted('select-module')).toBeTruthy()
    expect(wrapper.emitted('select-module')[0]).toEqual(['M1'])
  })

  it('renders null data gracefully', () => {
    const wrapper = mount(CourseMapOverview, { props: { data: null } })
    expect(wrapper.text()).toContain('') // no crash
  })
})
