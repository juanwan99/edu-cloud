import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConceptFocusOverlay from '../../components/knowledge-tree/ConceptFocusOverlay.vue'

const mockConcept = {
  id: 'B', name: '蛋白质', description: '生物大分子',
  review_status: 'ai_draft',
}
const mockAllNodes = [
  { id: 'A', name: '氨基酸' },
  { id: 'B', name: '蛋白质' },
  { id: 'C', name: '酶' },
  { id: 'D', name: '核糖体' },
  { id: 'E', name: '脂质' },
]
const mockEdges = [
  { source: 'A', target: 'B', type: 'prerequisite_hard' },   // A 是 B 的前置
  { source: 'B', target: 'C', type: 'prerequisite_hard' },   // C 是 B 的后继
  { source: 'B', target: 'D', type: 'prerequisite_hard' },   // D 是 B 的后继
  { source: 'B', target: 'E', type: 'contrast' },            // 对比
]

describe('ConceptFocusOverlay', () => {
  it('renders prerequisites and successors in correct direction (CE-003)', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    expect(wrapper.text()).toContain('前置依赖（1）')
    expect(wrapper.text()).toContain('氨基酸')
    expect(wrapper.text()).toContain('后继概念（2）')
    expect(wrapper.text()).toContain('酶')
    expect(wrapper.text()).toContain('核糖体')
  })

  it('renders bridge/contrast relations', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    expect(wrapper.text()).toContain('桥接/对比（1）')
    expect(wrapper.text()).toContain('脂质')
  })

  it('does not render when concept is null', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: null, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    expect(wrapper.find('.focus-overlay').exists()).toBe(false)
  })

  it('emits close when close button clicked', async () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    const closeBtn = wrapper.findAll('button').find(b => b.text() === '关闭')
    await closeBtn.trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })

  it('emits view-detail with concept on view-detail button click', async () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    const detailBtn = wrapper.findAll('button').find(b => b.text() === '查看详情')
    await detailBtn.trigger('click')
    expect(wrapper.emitted('view-detail')).toBeTruthy()
    expect(wrapper.emitted('view-detail')[0][0]).toEqual(mockConcept)
  })

  it('mark-reviewed button disabled when canEdit=false', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: false },
    })
    const markBtn = wrapper.findAll('button').find(b => b.text() === '标为已审核')
    expect(markBtn.attributes('disabled')).toBeDefined()
  })

  it('mark-reviewed button disabled when concept already teacher_reviewed', () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: {
        concept: { ...mockConcept, review_status: 'teacher_reviewed' },
        edges: mockEdges, allNodes: mockAllNodes, canEdit: true,
      },
    })
    const markBtn = wrapper.findAll('button').find(b => b.text() === '标为已审核')
    expect(markBtn.attributes('disabled')).toBeDefined()
  })

  it('focus-peer event fired when peer tag clicked', async () => {
    const wrapper = mount(ConceptFocusOverlay, {
      props: { concept: mockConcept, edges: mockEdges, allNodes: mockAllNodes, canEdit: true },
    })
    // 点击后继 "酶" tag
    const peerTags = wrapper.findAll('.peer-tag')
    const enzymeTag = peerTags.find(t => t.text().includes('酶'))
    await enzymeTag.trigger('click')
    expect(wrapper.emitted('focus-peer')).toBeTruthy()
    expect(wrapper.emitted('focus-peer')[0][0].id).toBe('C')
  })
})
