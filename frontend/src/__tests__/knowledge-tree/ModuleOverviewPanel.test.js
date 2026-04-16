import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ModuleOverviewPanel from '../../components/knowledge-tree/ModuleOverviewPanel.vue'
import ModuleStatCard from '../../components/knowledge-tree/ModuleStatCard.vue'

const mockNavigation = [
  { id: 'M1', name: '分子与细胞', big_concepts: [
    { id: 'BC1', name: 'BC 1', concept_ids: ['A', 'B'] },
  ]},
  { id: 'M2', name: '遗传与进化', big_concepts: [
    { id: 'BC2', name: 'BC 2', concept_ids: ['C'] },
  ]},
]
const mockNodes = [
  { id: 'A', module: 'M1', review_status: 'teacher_reviewed' },
  { id: 'B', module: 'M1', review_status: 'ai_draft' },
  { id: 'C', module: 'M2', review_status: 'published' },
]
const mockEdges = [
  { source: 'A', target: 'C', type: 'prerequisite_hard' },
]

describe('ModuleOverviewPanel', () => {
  it('renders one card per navigation module', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {} },
    })
    const cards = wrapper.findAllComponents(ModuleStatCard)
    expect(cards.length).toBe(2)
  })

  it('emits select-module on card click', async () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {} },
    })
    const cards = wrapper.findAllComponents(ModuleStatCard)
    await cards[0].trigger('click')
    expect(wrapper.emitted('select-module')).toBeTruthy()
    expect(wrapper.emitted('select-module')[0]).toEqual(['M1'])
  })

  it('aggregates cross-module hard prerequisite links', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {} },
    })
    expect(wrapper.text()).toContain('M1')
    expect(wrapper.text()).toContain('M2')
    expect(wrapper.text()).toContain('1 条')
  })

  it('uses modulesQuality to populate high/med counts', () => {
    const wrapper = mount(ModuleOverviewPanel, {
      props: {
        navigation: mockNavigation, nodes: mockNodes, edges: mockEdges,
        modulesQuality: { M1: { highCount: 3, medCount: 5 } },
      },
    })
    expect(wrapper.text()).toContain('3 HIGH')
    expect(wrapper.text()).toContain('5 MED')
  })
})
