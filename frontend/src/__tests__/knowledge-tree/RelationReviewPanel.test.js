import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RelationReviewPanel from '../../components/knowledge-tree/RelationReviewPanel.vue'
import ConceptReviewList from '../../components/knowledge-tree/ConceptReviewList.vue'
import RelationDetailCard from '../../components/knowledge-tree/RelationDetailCard.vue'
import QualityBadge from '../../components/knowledge-tree/QualityBadge.vue'

const mockNodes = [
  { id: 'A', name: '概念A', module: 'M1', review_status: 'ai_draft', description: '描述A' },
  { id: 'B', name: '概念B', module: 'M1', review_status: 'teacher_reviewed', description: '描述B' },
  { id: 'C', name: '概念C', module: 'M2', review_status: 'published', description: '描述C' },
]

const mockEdges = [
  { id: 1, source: 'A', target: 'B', type: 'prerequisite_hard', strength: 1.0, confidence: 0.5, review_status: 'ai_draft' },
  { id: 2, source: 'B', target: 'C', type: 'prerequisite_hard', strength: 1.0, confidence: 0.9, review_status: 'teacher_reviewed' },
]

const mockIssues = [
  { rule_id: 'Q1', severity: 'HIGH', message: '孤立概念', node_ids: ['A'], edge_ids: [] },
]

describe('RelationReviewPanel', () => {
  it('renders concept list with nodes', () => {
    const wrapper = mount(RelationReviewPanel, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: [], canEdit: true },
    })
    expect(wrapper.text()).toContain('概念A')
    expect(wrapper.text()).toContain('概念B')
  })

  it('shows empty hint when no concept selected', () => {
    const wrapper = mount(RelationReviewPanel, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: [], canEdit: true },
    })
    expect(wrapper.text()).toContain('选择一个概念查看关系')
  })

  it('emits edit with set_review_status after confirm via component method', async () => {
    const wrapper = mount(RelationReviewPanel, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: [], canEdit: true },
    })
    // 选中第一个概念
    const listItems = wrapper.findAll('.concept-item')
    await listItems[0].trigger('click')
    await wrapper.vm.$nextTick()

    // 通过子组件的 confirmEdge 方法触发（真实用户路径）
    const detail = wrapper.findComponent(RelationDetailCard)
    expect(detail.exists()).toBe(true)
    detail.vm.confirmEdge(mockEdges[0])
    expect(wrapper.emitted('edit')).toBeTruthy()
    expect(wrapper.emitted('edit')[0][0]).toEqual([
      { op: 'set_review_status', edge_id: 1, status: 'teacher_reviewed' },
    ])
  })

  it('resets selectedConcept when nodes change', async () => {
    const wrapper = mount(RelationReviewPanel, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: [], canEdit: true },
    })
    // 选中概念A
    const listItems = wrapper.findAll('.concept-item')
    await listItems[0].trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent(RelationDetailCard).exists()).toBe(true)

    // 模拟节点列表变化（不含概念A）
    await wrapper.setProps({ nodes: [mockNodes[1], mockNodes[2]] })
    await wrapper.vm.$nextTick()
    // 详情卡片应消失
    expect(wrapper.text()).toContain('选择一个概念查看关系')
  })
})

describe('ConceptReviewList', () => {
  it('sorts by quality priority by default', () => {
    const wrapper = mount(ConceptReviewList, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: mockIssues, selectedId: null },
    })
    const items = wrapper.findAll('.concept-item')
    // A has HIGH issue → should be first
    expect(items[0].text()).toContain('概念A')
  })

  it('shows progress bar with reviewed count', () => {
    const wrapper = mount(ConceptReviewList, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: [], selectedId: null },
    })
    // 1 of 2 edges is reviewed (teacher_reviewed)
    expect(wrapper.text()).toContain('1/2')
  })

  it('shows quality badge for nodes with issues', () => {
    const wrapper = mount(ConceptReviewList, {
      props: { nodes: mockNodes, edges: mockEdges, qualityIssues: mockIssues, selectedId: null },
    })
    const badges = wrapper.findAllComponents(QualityBadge)
    expect(badges.length).toBeGreaterThan(0)
  })
})

describe('RelationDetailCard', () => {
  const concept = mockNodes[0]

  it('renders concept name and description', () => {
    const wrapper = mount(RelationDetailCard, {
      props: { concept, edges: mockEdges, allNodes: mockNodes, canEdit: true },
    })
    expect(wrapper.text()).toContain('概念A')
    expect(wrapper.text()).toContain('描述A')
  })

  it('disables buttons when canEdit=false', () => {
    const wrapper = mount(RelationDetailCard, {
      props: { concept, edges: mockEdges, allNodes: mockNodes, canEdit: false },
    })
    const buttons = wrapper.findAll('button')
    const disabledButtons = buttons.filter(b => b.attributes('disabled') !== undefined)
    expect(disabledButtons.length).toBeGreaterThan(0)
  })

  it('emits review-edge with teacher_reviewed for ai_draft edge', async () => {
    const wrapper = mount(RelationDetailCard, {
      props: { concept, edges: mockEdges, allNodes: mockNodes, canEdit: true },
    })
    // 直接调用 confirmEdge
    wrapper.vm.confirmEdge(mockEdges[0])
    expect(wrapper.emitted('review-edge')).toBeTruthy()
    expect(wrapper.emitted('review-edge')[0][0].status).toBe('teacher_reviewed')
  })

  it('emits review-edge with ai_draft for rejected edge (recovery)', async () => {
    const rejectedEdge = { ...mockEdges[0], review_status: 'rejected' }
    const wrapper = mount(RelationDetailCard, {
      props: { concept, edges: [rejectedEdge], allNodes: mockNodes, canEdit: true },
    })
    wrapper.vm.confirmEdge(rejectedEdge)
    expect(wrapper.emitted('review-edge')[0][0].status).toBe('ai_draft')
  })

  it('emits review-edge with rejected for reject action', async () => {
    const wrapper = mount(RelationDetailCard, {
      props: { concept, edges: mockEdges, allNodes: mockNodes, canEdit: true },
    })
    wrapper.vm.rejectEdge(mockEdges[0])
    expect(wrapper.emitted('review-edge')[0][0].status).toBe('rejected')
  })

  it('batch confirm only processes ai_draft edges', async () => {
    const mixedEdges = [
      { ...mockEdges[0], review_status: 'ai_draft' },
      { ...mockEdges[1], review_status: 'teacher_reviewed' },
    ]
    const wrapper = mount(RelationDetailCard, {
      props: { concept: { ...concept, id: 'A' }, edges: mixedEdges, allNodes: mockNodes, canEdit: true },
    })
    wrapper.vm.batchConfirm(mixedEdges)
    // Only ai_draft edge should be confirmed
    const emitted = wrapper.emitted('review-edge') || []
    expect(emitted.length).toBe(1)
    expect(emitted[0][0].edgeId).toBe(1)
  })

  it('highlights low confidence edges', () => {
    const wrapper = mount(RelationDetailCard, {
      props: { concept, edges: mockEdges, allNodes: mockNodes, canEdit: true },
    })
    // Edge with confidence 0.5 should show warning tag
    expect(wrapper.text()).toContain('0.50')
  })
})

describe('QualityBadge', () => {
  it('renders nothing when severity is null', () => {
    const wrapper = mount(QualityBadge, { props: { severity: null, label: '!' } })
    expect(wrapper.text()).toBe('')
  })

  it('renders error type for HIGH severity', () => {
    const wrapper = mount(QualityBadge, { props: { severity: 'HIGH', label: '!' } })
    expect(wrapper.text()).toContain('!')
  })
})
