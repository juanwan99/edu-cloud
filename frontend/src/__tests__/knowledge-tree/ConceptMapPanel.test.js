import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// Mock G6 Graph to avoid canvas rendering in happy-dom.
// 额外捕获 on(event, cb) 注册的回调，供测试触发 node:click/canvas:click 等事件。
const graphCtorCalls = []
const graphInstances = []
vi.mock('@antv/g6', () => {
  class Graph {
    constructor(cfg) {
      graphCtorCalls.push(cfg)
      this.handlers = {}
      this.render = vi.fn()
      this.destroy = vi.fn()
      this.on = vi.fn((event, cb) => {
        this.handlers[event] = cb
      })
      // Phase 2.5 R1 F005: setElementState spy，测试直接断言真实调用参数
      this.setElementState = vi.fn().mockResolvedValue(undefined)
      // R2 F003: setData spy，用于 watch([colorMode, nodesWithMastery]) 重绘路径断言。
      // ConceptMapPanel.vue:463 watch 在 setData 调用失败时被 try/catch 吞掉；
      // 这里提供真实函数让 watch 完整走完 setData → render → focus replay 路径。
      this.setData = vi.fn()
      graphInstances.push(this)
    }
  }
  return { Graph }
})

beforeEach(() => {
  graphCtorCalls.length = 0
  graphInstances.length = 0
})

import ConceptMapPanel from '../../components/knowledge-tree/ConceptMapPanel.vue'

const mockNavigation = [
  {
    id: 'M1',
    name: '分子与细胞',
    big_concepts: [
      { id: 'BC1', name: '细胞分子组成', concept_ids: ['A', 'B'] },
      { id: 'BC2', name: '细胞基本结构', concept_ids: ['C'] },
    ],
  },
]
const mockNodes = [
  { id: 'A', name: '蛋白质', module: 'M1', big_concept_id: 'BC1', review_status: 'teacher_reviewed' },
  { id: 'B', name: '酶', module: 'M1', big_concept_id: 'BC1', review_status: 'ai_draft' },
  { id: 'C', name: '细胞膜', module: 'M1', big_concept_id: 'BC2', review_status: 'published' },
]
const mockEdges = [
  { source: 'A', target: 'B', type: 'prerequisite_hard' },
]

describe('ConceptMapPanel', () => {
  it('renders toolbar with module name and review progress', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: mockNodes,
        edges: mockEdges,
        navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    expect(wrapper.text()).toContain('分子与细胞')
    expect(wrapper.text()).toContain('审核 2/3')
  })

  it('emits back-to-overview on back button click', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: mockNodes,
        edges: mockEdges,
        navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    const backBtn = wrapper.findAll('button').find(b => b.text().includes('返回概览'))
    expect(backBtn).toBeDefined()
    await backBtn.trigger('click')
    expect(wrapper.emitted('back-to-overview')).toBeTruthy()
  })

  it('renders BigConcept bands from layoutEngine', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: mockNodes,
        edges: mockEdges,
        navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    expect(wrapper.html()).toContain('细胞分子组成')
    expect(wrapper.html()).toContain('细胞基本结构')
  })

  it('shows HIGH badge when quality issues contain HIGH', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: mockNodes,
        edges: mockEdges,
        navigation: mockNavigation,
        qualityIssues: [{ rule_id: 'Q1', severity: 'HIGH', message: 'test' }],
      },
    })
    expect(wrapper.text()).toContain('1 HIGH')
  })

  it('generates cross-module badges from node.external_hard_refs.out (F002)', () => {
    // 节点 B 有指向 M2/M3 的跨模块硬前置（模拟 Phase 1 Graph API module 过滤后的数据）
    const nodesWithRefs = [
      { id: 'A', name: '蛋白质', module: 'M1', big_concept_id: 'BC1', review_status: 'ai_draft' },
      {
        id: 'B',
        name: '酶',
        module: 'M1',
        big_concept_id: 'BC1',
        review_status: 'ai_draft',
        external_hard_refs: {
          in: [],
          out: [
            { id: 'X1', name: '代谢', module: 'M2' },
            { id: 'X2', name: '调控', module: 'M2' },
            { id: 'Y1', name: '反馈', module: 'M3' },
          ],
        },
      },
      { id: 'C', name: '细胞膜', module: 'M1', big_concept_id: 'BC2', review_status: 'ai_draft' },
    ]
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: nodesWithRefs,
        edges: [],
        navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    const vm = wrapper.vm
    expect(vm.crossModuleBadges).toBeDefined()
    expect(vm.crossModuleBadges.B).toEqual({ M2: 2, M3: 1 })
    // 节点 A、C 无 external_hard_refs → 不在 badgeMap 中
    expect(vm.crossModuleBadges.A).toBeUndefined()
    expect(vm.crossModuleBadges.C).toBeUndefined()
  })

  it('crossModuleBadges empty when no nodes have external_hard_refs', () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: mockNodes,
        edges: mockEdges,
        navigation: mockNavigation,
        qualityIssues: [],
      },
    })
    expect(wrapper.vm.crossModuleBadges).toEqual({})
  })

  it('INV-005: G6 Graph must use layout.type=preset', async () => {
    mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: mockNodes,
        edges: mockEdges,
        navigation: mockNavigation,
        qualityIssues: [],
      },
      attachTo: document.body,
    })
    // createGraph 在 onMounted nextTick 内调用——flush microtasks
    await Promise.resolve()
    await Promise.resolve()
    expect(graphCtorCalls.length).toBeGreaterThan(0)
    expect(graphCtorCalls[0].layout).toEqual({ type: 'preset' })
  })
})

// F-004 修复：Task 5 焦点模式核心交互测试
describe('ConceptMapPanel focus mode interactions (Task 5)', () => {
  async function mountAndWaitForGraph(props = {}) {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: '分子与细胞',
        nodes: mockNodes,
        edges: mockEdges,
        navigation: mockNavigation,
        qualityIssues: [],
        canEdit: true,
        ...props,
      },
      attachTo: document.body,
    })
    // nextTick 触发 onMounted → createGraph
    await nextTick()
    await nextTick()
    return wrapper
  }

  it('node:click handler opens focus overlay (focusedNodeId updated)', async () => {
    const wrapper = await mountAndWaitForGraph()
    expect(graphInstances.length).toBeGreaterThan(0)
    const graph = graphInstances[graphInstances.length - 1]
    expect(graph.handlers['node:click']).toBeDefined()

    // 初始无焦点
    expect(wrapper.vm.focusedNodeId).toBeNull()

    // 触发 G6 node:click 事件，带节点 A
    graph.handlers['node:click']({ target: { id: 'A' } })
    await nextTick()

    expect(wrapper.vm.focusedNodeId).toBe('A')
    // ConceptFocusOverlay 应该被渲染
    expect(wrapper.find('.focus-overlay').exists()).toBe(true)
    expect(wrapper.text()).toContain('蛋白质')
  })

  it('canvas:click handler clears focus when one is active (F005)', async () => {
    const wrapper = await mountAndWaitForGraph()
    const graph = graphInstances[graphInstances.length - 1]
    expect(graph.handlers['canvas:click']).toBeDefined()

    // 先点节点进入焦点
    graph.handlers['node:click']({ target: { id: 'B' } })
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBe('B')
    expect(wrapper.find('.focus-overlay').exists()).toBe(true)

    // 再点画布空白
    graph.handlers['canvas:click']()
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBeNull()
    expect(wrapper.find('.focus-overlay').exists()).toBe(false)
  })

  it('ESC keydown clears focus when one is active', async () => {
    const wrapper = await mountAndWaitForGraph()
    const graph = graphInstances[graphInstances.length - 1]

    graph.handlers['node:click']({ target: { id: 'C' } })
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBe('C')

    // 触发 window keydown ESC
    const event = new KeyboardEvent('keydown', { key: 'Escape' })
    window.dispatchEvent(event)
    await nextTick()

    expect(wrapper.vm.focusedNodeId).toBeNull()
  })

  it('ESC keydown is noop when no focus is active', async () => {
    const wrapper = await mountAndWaitForGraph()
    expect(wrapper.vm.focusedNodeId).toBeNull()

    const event = new KeyboardEvent('keydown', { key: 'Escape' })
    window.dispatchEvent(event)
    await nextTick()

    // 仍然 null，不抛异常
    expect(wrapper.vm.focusedNodeId).toBeNull()
  })

  it('moduleId change clears focus (prevents stale focus from previous module)', async () => {
    const wrapper = await mountAndWaitForGraph()
    const graph = graphInstances[graphInstances.length - 1]

    graph.handlers['node:click']({ target: { id: 'A' } })
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBe('A')

    // 切换模块
    await wrapper.setProps({ moduleId: 'M2', moduleName: '遗传与进化' })
    // watch(moduleId) 同步执行
    await nextTick()

    expect(wrapper.vm.focusedNodeId).toBeNull()
  })

  it('canvas:click is noop when no focus (does not toggle state)', async () => {
    const wrapper = await mountAndWaitForGraph()
    const graph = graphInstances[graphInstances.length - 1]
    expect(wrapper.vm.focusedNodeId).toBeNull()

    graph.handlers['canvas:click']()
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBeNull()
  })

  it('node:click with unknown id does not open overlay', async () => {
    const wrapper = await mountAndWaitForGraph()
    const graph = graphInstances[graphInstances.length - 1]

    // 点击不存在的节点 id
    graph.handlers['node:click']({ target: { id: 'NONEXISTENT' } })
    await nextTick()

    // focusedNodeId 保持 null（handleNodeClick 被 node.find 守卫）
    expect(wrapper.vm.focusedNodeId).toBeNull()
  })
})

// ============================================================================
// Phase 2.5: 焦点淡化 + 徽标悬停 Tooltip
// ============================================================================
// R1 修复：focusedNodeId 是组件内部 ref（Phase 2 事件驱动模式），不是 prop；
// 测试入口用 Phase 2 既有的 graph.handlers['node:click'] 事件驱动；
// relatedNodeIds/relatedEdgeIds 是 ComputedRef，Vue 3 unref 通过 vm 访问返回 .value；
// setElementState 通过 G6 mock spy 真实断言调用参数，非逻辑镜像。

const phase25Nodes = () => [
  { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1' },
  { id: 'B', name: 'B', big_concept_id: 'BC1', module: 'M1' },
  { id: 'C', name: 'C', big_concept_id: 'BC1', module: 'M1' },
  { id: 'D', name: 'D', big_concept_id: 'BC2', module: 'M1' },
  { id: 'E', name: 'E', big_concept_id: 'BC2', module: 'M1' },
  { id: 'F', name: 'F', big_concept_id: 'BC2', module: 'M1' },
]
const phase25Edges = () => [
  { source: 'A', target: 'B', type: 'prerequisite_hard' },  // visible edge-0
  { source: 'B', target: 'C', type: 'prerequisite_soft' },  // visible edge-1
  { source: 'D', target: 'B', type: 'prerequisite_hard' },  // visible edge-2
  { source: 'E', target: 'F', type: 'prerequisite_soft' },  // visible edge-3 (unrelated)
]
const phase25Navigation = [
  { id: 'M1', name: '分子与细胞', big_concepts: [
    { id: 'BC1', name: 'BC1', concept_ids: ['A', 'B', 'C'] },
    { id: 'BC2', name: 'BC2', concept_ids: ['D', 'E', 'F'] },
  ]},
]
const phase25BaseProps = () => ({
  moduleId: 'M1',
  moduleName: '分子与细胞',
  nodes: phase25Nodes(),
  edges: phase25Edges(),
  navigation: phase25Navigation,
  qualityIssues: [],
})

async function mountPhase25(propsOverride = {}) {
  const wrapper = mount(ConceptMapPanel, {
    props: { ...phase25BaseProps(), ...propsOverride },
    attachTo: document.body,
  })
  // 等待 onMounted → nextTick → createGraph 完成
  await nextTick()
  await nextTick()
  return wrapper
}

async function focusOnNode(nodeId) {
  const graph = graphInstances[graphInstances.length - 1]
  graph.handlers['node:click']({ target: { id: nodeId } })
  await nextTick()
  await nextTick()  // watch(focusedNodeId) → nextTick(updateElementStates)
  return graph
}

describe('Phase 2.5 INV-006: relatedNodeIds / relatedEdgeIds computed', () => {
  it('relatedNodeIds is empty Set when focusedNodeId is null (initial state)', async () => {
    const wrapper = await mountPhase25()
    // Phase 2 初始 focusedNodeId=null
    expect(wrapper.vm.focusedNodeId).toBeNull()
    expect(wrapper.vm.relatedNodeIds).toBeInstanceOf(Set)
    expect(wrapper.vm.relatedNodeIds.size).toBe(0)
    expect(wrapper.vm.relatedEdgeIds).toBeInstanceOf(Set)
    expect(wrapper.vm.relatedEdgeIds.size).toBe(0)
  })

  it('relatedNodeIds is empty Set after clearFocus() returns focus to null', async () => {
    const wrapper = await mountPhase25()
    await focusOnNode('B')
    expect(wrapper.vm.relatedNodeIds.size).toBeGreaterThan(0)
    wrapper.vm.clearFocus()
    await nextTick()
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBeNull()
    expect(wrapper.vm.relatedNodeIds.size).toBe(0)
    expect(wrapper.vm.relatedEdgeIds.size).toBe(0)
  })

  it('relatedNodeIds includes focus self + predecessors + successors (hard and soft) — CE-004 guard', async () => {
    const wrapper = await mountPhase25()
    await focusOnNode('B')
    // focus=B: 前置 A (hard) + D (hard), 后继 C (soft); 期望 {A, B, C, D}
    const r = wrapper.vm.relatedNodeIds
    expect(r.has('B')).toBe(true)   // 焦点自身
    expect(r.has('A')).toBe(true)   // hard 前置
    expect(r.has('D')).toBe(true)   // hard 前置（反向边）——CE-004 护栏
    expect(r.has('C')).toBe(true)   // soft 后继
    expect(r.has('E')).toBe(false)  // 不相关
    expect(r.has('F')).toBe(false)
    expect(r.size).toBe(4)
  })

  it('relatedNodeIds returns {focus, peer} when focus has single edge', async () => {
    const wrapper = await mountPhase25()
    await focusOnNode('F')
    // F 只在 edge-3 (E→F) 中，所以 related = {E, F}
    const r = wrapper.vm.relatedNodeIds
    expect(r.has('F')).toBe(true)
    expect(r.has('E')).toBe(true)
    expect(r.size).toBe(2)
  })

  it('relatedEdgeIds uses buildVisibleEdgeList visibleId (edge-${visibleIndex}) aligned with buildG6Data', async () => {
    const wrapper = await mountPhase25()
    await focusOnNode('B')
    const e = wrapper.vm.relatedEdgeIds
    // B 关联的边: edge-0 (A→B), edge-1 (B→C), edge-2 (D→B)
    expect(e.has('edge-0')).toBe(true)
    expect(e.has('edge-1')).toBe(true)
    expect(e.has('edge-2')).toBe(true)
    expect(e.has('edge-3')).toBe(false)  // E→F 不相关
    expect(e.size).toBe(3)
  })

  it('F003 guard: buildVisibleEdgeList skips edges whose endpoint is filtered out, keeping id alignment', async () => {
    // 构造一条 dangling 边（target='GHOST' 不在 nodes 集合）
    // 这条边应被 helper 过滤掉，visibleIndex 不计入
    const edgesWithDangling = [
      { source: 'A', target: 'B', type: 'prerequisite_hard' },      // visible edge-0
      { source: 'A', target: 'GHOST', type: 'prerequisite_hard' },  // filtered out
      { source: 'B', target: 'C', type: 'prerequisite_soft' },      // visible edge-1 (!)
    ]
    const wrapper = await mountPhase25({ edges: edgesWithDangling })
    await focusOnNode('B')
    // B 关联的可见边: edge-0 (A→B) + edge-1 (B→C)
    // 如果 F003 未修复（使用原始索引）, B→C 的 id 会是 edge-2 而不是 edge-1
    expect(wrapper.vm.relatedEdgeIds.has('edge-0')).toBe(true)
    expect(wrapper.vm.relatedEdgeIds.has('edge-1')).toBe(true)
    expect(wrapper.vm.relatedEdgeIds.has('edge-2')).toBe(false)
    expect(wrapper.vm.relatedEdgeIds.size).toBe(2)
  })

  it('relatedEdgeIds excludes edges of irrelevant types (non-prerequisite)', async () => {
    // 'bridge' 类型的边（Phase 3 可能扩展）应被忽略
    const edgesWithBridge = [
      { source: 'A', target: 'B', type: 'prerequisite_hard' },  // visible edge-0
      { source: 'A', target: 'B', type: 'bridge' },             // visible edge-1 (fake type)
    ]
    const wrapper = await mountPhase25({ edges: edgesWithBridge })
    await focusOnNode('A')
    expect(wrapper.vm.relatedEdgeIds.has('edge-0')).toBe(true)
    expect(wrapper.vm.relatedEdgeIds.has('edge-1')).toBe(false)  // bridge 被忽略
  })
})

describe('Phase 2.5 INV-007/INV-008: updateElementStates real setElementState wire-up', () => {
  it('INV-007: entering focus triggers graph.setElementState with precise state map', async () => {
    const wrapper = await mountPhase25()
    const graph = graphInstances[graphInstances.length - 1]
    const callsBefore = graph.setElementState.mock.calls.length

    await focusOnNode('B')

    // 进入焦点后 spy 必须被调用
    expect(graph.setElementState.mock.calls.length).toBeGreaterThan(callsBefore)

    // 取最后一次调用的 state map 参数（setElementState(stateMap, animation)）
    const lastCall = graph.setElementState.mock.calls[graph.setElementState.mock.calls.length - 1]
    const stateMap = lastCall[0]
    const animation = lastCall[1]

    // 相关节点 = []，非相关节点 = ['faded']
    expect(stateMap.A).toEqual([])         // A 是 B 的前置
    expect(stateMap.B).toEqual([])         // 焦点自身
    expect(stateMap.C).toEqual([])         // B 的后继
    expect(stateMap.D).toEqual([])         // D 是 B 的反向前置（CE-004 护栏）
    expect(stateMap.E).toEqual(['faded'])
    expect(stateMap.F).toEqual(['faded'])

    // 相关边 = ['emphasized']，非相关边 = ['dimmed']
    expect(stateMap['edge-0']).toEqual(['emphasized'])  // A→B
    expect(stateMap['edge-1']).toEqual(['emphasized'])  // B→C
    expect(stateMap['edge-2']).toEqual(['emphasized'])  // D→B
    expect(stateMap['edge-3']).toEqual(['dimmed'])      // E→F 不相关

    expect(animation).toBe(true)
  })

  it('INV-008 + CE-005: clearFocus triggers graph.setElementState({}, true)', async () => {
    const wrapper = await mountPhase25()
    const graph = graphInstances[graphInstances.length - 1]

    await focusOnNode('B')
    // 清焦点前记录 spy 次数
    const callsBefore = graph.setElementState.mock.calls.length

    wrapper.vm.clearFocus()
    await nextTick()
    await nextTick()

    // 清焦点后必须新增一次 spy 调用
    expect(graph.setElementState.mock.calls.length).toBeGreaterThan(callsBefore)

    // 最后一次调用参数必须是空对象 + animation=true
    const lastCall = graph.setElementState.mock.calls[graph.setElementState.mock.calls.length - 1]
    expect(lastCall[0]).toEqual({})  // CE-005: 退出焦点必须清空所有 state
    expect(lastCall[1]).toBe(true)
  })

  it('switching focus B→F recalculates state map (no stale related set)', async () => {
    const wrapper = await mountPhase25()
    const graph = graphInstances[graphInstances.length - 1]

    await focusOnNode('B')
    await focusOnNode('F')

    const lastCall = graph.setElementState.mock.calls[graph.setElementState.mock.calls.length - 1]
    const stateMap = lastCall[0]
    // 切换到 F 后：E 和 F 应该是 [], A/B/C/D 应该是 ['faded']
    expect(stateMap.F).toEqual([])
    expect(stateMap.E).toEqual([])
    expect(stateMap.A).toEqual(['faded'])
    expect(stateMap.B).toEqual(['faded'])
    expect(stateMap.C).toEqual(['faded'])
    expect(stateMap.D).toEqual(['faded'])
  })

  it('F004 graph rebuild: createGraph replays focus state after destroy/create cycle', async () => {
    const wrapper = await mountPhase25()
    await focusOnNode('B')

    // 触发 nodes 更新 → destroy→create 循环（watch [moduleId, nodes, edges]）
    const newNodes = [
      ...phase25Nodes(),
      { id: 'G', name: 'G', big_concept_id: 'BC2', module: 'M1' },
    ]
    await wrapper.setProps({ nodes: newNodes })
    await nextTick()
    await nextTick()  // destroy→create
    await nextTick()  // createGraph 末尾的 nextTick(updateElementStates) 重放

    // 新 graph 实例应该存在
    expect(graphInstances.length).toBeGreaterThanOrEqual(2)
    const newGraph = graphInstances[graphInstances.length - 1]

    // 新 graph 的 setElementState 应该被调用至少一次（重放焦点）
    expect(newGraph.setElementState.mock.calls.length).toBeGreaterThan(0)

    // 最后一次调用的 state map 反映当前焦点 B 的关系（包括新节点 G 应为 faded）
    const lastCall = newGraph.setElementState.mock.calls[newGraph.setElementState.mock.calls.length - 1]
    const stateMap = lastCall[0]
    expect(stateMap.B).toEqual([])         // 焦点保持
    expect(stateMap.G).toEqual(['faded'])  // 新节点未相关
  })

  // R2 F003 修复：INV-006/INV-007 孤立节点边界——构造一个完全不被任何边触及的节点，
  // 通过 graph.handlers['node:click'] 真实入口驱动 focus，断言 relatedNodeIds 和 stateMap
  // 反证：将 relatedNodeIds 的 new Set([focus]) 改为 new Set() 后，本测试必须 fail
  //       （relatedNodeIds.has('ISOLATED') 为 false 且 stateMap.ISOLATED 变为 faded）
  it('F003 isolated node: real node:click on a node with zero edges → relatedNodeIds = {self}, stateMap all others faded', async () => {
    const nodesWithIsolated = [
      { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1' },
      { id: 'B', name: 'B', big_concept_id: 'BC1', module: 'M1' },
      { id: 'ISOLATED', name: 'ISOLATED', big_concept_id: 'BC2', module: 'M1' },
      { id: 'C', name: 'C', big_concept_id: 'BC2', module: 'M1' },
    ]
    // edges 中没有任何一条触及 ISOLATED
    const edgesWithoutIsolated = [
      { source: 'A', target: 'B', type: 'prerequisite_hard' },
      { source: 'B', target: 'C', type: 'prerequisite_soft' },
    ]
    const wrapper = await mountPhase25({ nodes: nodesWithIsolated, edges: edgesWithoutIsolated })
    const graph = graphInstances[graphInstances.length - 1]

    // 通过真实 node:click 入口驱动焦点
    await focusOnNode('ISOLATED')

    // 断言 relatedNodeIds 只含焦点自身（CE-004/INV-006 arity=1 退化）
    expect(wrapper.vm.relatedNodeIds).toBeInstanceOf(Set)
    expect(wrapper.vm.relatedNodeIds.size).toBe(1)
    expect(wrapper.vm.relatedNodeIds.has('ISOLATED')).toBe(true)

    // 断言 relatedEdgeIds 为空 Set（孤立节点不相关任何边）
    expect(wrapper.vm.relatedEdgeIds.size).toBe(0)

    // 断言 setElementState 真实被调用且 stateMap 精确反映孤立态
    const lastCall = graph.setElementState.mock.calls[graph.setElementState.mock.calls.length - 1]
    const stateMap = lastCall[0]
    expect(stateMap.ISOLATED).toEqual([])        // 焦点自身
    expect(stateMap.A).toEqual(['faded'])        // 其他节点全部 faded
    expect(stateMap.B).toEqual(['faded'])
    expect(stateMap.C).toEqual(['faded'])
    // 所有边都不相关 → dimmed（本场景有 2 条可见边 edge-0 / edge-1）
    expect(stateMap['edge-0']).toEqual(['dimmed'])
    expect(stateMap['edge-1']).toEqual(['dimmed'])
    expect(lastCall[1]).toBe(true)
  })
})

describe('Phase 2.5 INV-009/INV-010 + CE-006: Tooltip plugin + renderPeersHtml', () => {
  const singleNodeProps = () => ({
    moduleId: 'M1',
    moduleName: '分子与细胞',
    nodes: [{ id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1' }],
    edges: [],
    navigation: [{ id: 'M1', name: '分子与细胞', big_concepts: [
      { id: 'BC1', name: 'BC1', concept_ids: ['A'] },
    ]}],
    qualityIssues: [],
  })

  it('INV-010: renderPeersHtml output contains module labels and node names for multi-module peers', async () => {
    const wrapper = mount(ConceptMapPanel, { props: singleNodeProps() })
    await nextTick()
    const html = wrapper.vm.renderPeersHtml({
      M2: [{ id: 'x1', name: '细胞膜流动性' }, { id: 'x2', name: '主动运输' }],
      M3: [{ id: 'y1', name: '基因表达' }],
    })
    expect(html).toContain('→ M2')
    expect(html).toContain('细胞膜流动性')
    expect(html).toContain('主动运输')
    expect(html).toContain('→ M3')
    expect(html).toContain('基因表达')
    expect(html).toContain('peer-tooltip')
    expect(html).toContain('peer-section')
  })

  it('INV-010 determinism: module entries sorted alphabetically', async () => {
    const wrapper = mount(ConceptMapPanel, { props: singleNodeProps() })
    await nextTick()
    const html = wrapper.vm.renderPeersHtml({
      M3: [{ id: 'y', name: 'B-concept' }],
      M2: [{ id: 'x', name: 'A-concept' }],
    })
    // M2 应出现在 M3 之前（字母序）
    const m2Index = html.indexOf('→ M2')
    const m3Index = html.indexOf('→ M3')
    expect(m2Index).toBeGreaterThan(-1)
    expect(m3Index).toBeGreaterThan(-1)
    expect(m2Index).toBeLessThan(m3Index)
  })

  it('CE-006: renderPeersHtml returns empty string for null / undefined / {} / empty arrays', async () => {
    const wrapper = mount(ConceptMapPanel, { props: singleNodeProps() })
    await nextTick()
    expect(wrapper.vm.renderPeersHtml(null)).toBe('')
    expect(wrapper.vm.renderPeersHtml(undefined)).toBe('')
    expect(wrapper.vm.renderPeersHtml({})).toBe('')
    expect(wrapper.vm.renderPeersHtml({ M2: [] })).toBe('')  // 所有列表为空 → 过滤后无条目
  })

  it('CE-006: renderPeersHtml escapes HTML in module id and node name', async () => {
    const wrapper = mount(ConceptMapPanel, { props: singleNodeProps() })
    await nextTick()
    const html = wrapper.vm.renderPeersHtml({
      '<script>alert(1)</script>': [{ id: 'x', name: '<img src=x>' }],
    })
    expect(html).not.toContain('<script>alert(1)</script>')
    expect(html).toContain('&lt;script&gt;')
    expect(html).not.toContain('<img src=x>')
    expect(html).toContain('&lt;img src=x&gt;')
  })

  // R1 F006: 直接读 graphCtorCalls[last].plugins 真实 wiring，不再手写"等价"
  it('INV-009: Tooltip plugin is wired to Graph with correct type/key/trigger', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...singleNodeProps(),
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
            external_hard_refs: { in: [], out: [{ id: 'x', name: '跨模块节点', module: 'M2' }] } },
        ],
      },
      attachTo: document.body,
    })
    await nextTick()
    await nextTick()
    // 读 new Graph() 调用时传入的 cfg
    expect(graphCtorCalls.length).toBeGreaterThan(0)
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    expect(cfg.plugins).toBeDefined()
    expect(Array.isArray(cfg.plugins)).toBe(true)

    const tooltipPlugin = cfg.plugins.find(p => p && p.type === 'tooltip')
    expect(tooltipPlugin).toBeDefined()
    expect(tooltipPlugin.key).toBe('badge-tooltip')
    expect(tooltipPlugin.trigger).toBe('hover')
    expect(typeof tooltipPlugin.enable).toBe('function')
    expect(typeof tooltipPlugin.getContent).toBe('function')
  })

  it('INV-009: Tooltip plugin enable returns true only for items with badgeText (real plugin config)', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...singleNodeProps(),
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
            external_hard_refs: { in: [], out: [{ id: 'x', name: 'Xpeer', module: 'M2' }] } },
        ],
      },
      attachTo: document.body,
    })
    await nextTick()
    await nextTick()
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    const enable = cfg.plugins.find(p => p.type === 'tooltip').enable

    // 正例: 有 badgeText
    expect(enable(null, [{ data: { badgeText: '→M2×3' } }])).toBe(true)
    // 反例 1: 空字符串 badgeText
    expect(enable(null, [{ data: { badgeText: '' } }])).toBe(false)
    // 反例 2: 无 badgeText 字段
    expect(enable(null, [{ data: {} }])).toBe(false)
    // 反例 3: 空 items
    expect(enable(null, [])).toBe(false)
    // 反例 4: null items
    expect(enable(null, null)).toBe(false)
  })

  it('INV-009: Tooltip plugin getContent returns renderPeersHtml(crossModulePeers[nodeId]) via real wiring', async () => {
    // 构造节点 A 带 external_hard_refs.out，让 crossModulePeers.A 非空
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...singleNodeProps(),
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
            external_hard_refs: {
              in: [],
              out: [
                { id: 'x1', name: '膜流动性', module: 'M2' },
                { id: 'y1', name: '基因表达', module: 'M3' },
              ],
            },
          },
        ],
      },
      attachTo: document.body,
    })
    await nextTick()
    await nextTick()
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    const getContent = cfg.plugins.find(p => p.type === 'tooltip').getContent

    // 真实调用 getContent（async）
    const html = await getContent(null, [{ id: 'A', data: { badgeText: '→M2×1 →M3×1' } }])
    expect(typeof html).toBe('string')
    expect(html).toContain('→ M2')
    expect(html).toContain('膜流动性')
    expect(html).toContain('→ M3')
    expect(html).toContain('基因表达')
  })

  it('INV-009: Tooltip getContent returns empty string for node without peers', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: singleNodeProps(),
      attachTo: document.body,
    })
    await nextTick()
    await nextTick()
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    const getContent = cfg.plugins.find(p => p.type === 'tooltip').getContent
    const html = await getContent(null, [{ id: 'A', data: {} }])
    expect(html).toBe('')
  })

  // R2 F001 修复：INV-009 真实入口链路——不手写 items，从 graphCtorCalls[last].data.nodes
  // 取 buildG6Data 真实生成的 node data 对象，喂给 plugin.enable/getContent，
  // 锁住 external_hard_refs → badgeText → tooltip 的完整链路。
  // 反证：删除 buildG6Data 中 badgeText 字段写入后，本测试必须 fail（enable 返回 false）。
  it('INV-009 F001 real link: plugin consumes real buildG6Data badgeText end-to-end', async () => {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        ...singleNodeProps(),
        nodes: [
          { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
            external_hard_refs: {
              in: [],
              out: [
                { id: 'x1', name: '膜流动性', module: 'M2' },
                { id: 'y1', name: '基因表达', module: 'M3' },
              ],
            },
          },
        ],
      },
      attachTo: document.body,
    })
    await nextTick()
    await nextTick()
    // 步骤 1：从 G6 收到的真实 cfg.data 取 buildG6Data 生成的 node data
    const cfg = graphCtorCalls[graphCtorCalls.length - 1]
    expect(cfg.data).toBeDefined()
    expect(Array.isArray(cfg.data.nodes)).toBe(true)
    const nodeA = cfg.data.nodes.find(n => n.id === 'A')
    expect(nodeA).toBeDefined()
    // 步骤 2：真实链路必须生成非空 badgeText（如果 buildG6Data 丢失 badgeText 写入，这里会 fail）
    expect(nodeA.data).toBeDefined()
    expect(typeof nodeA.data.badgeText).toBe('string')
    expect(nodeA.data.badgeText.length).toBeGreaterThan(0)
    expect(nodeA.data.badgeText).toContain('→M2')
    expect(nodeA.data.badgeText).toContain('→M3')

    // 步骤 3：把真实 nodeA 对象传入 plugin.enable（不是手写 items）
    const plugin = cfg.plugins.find(p => p.type === 'tooltip')
    const enableResult = plugin.enable(null, [nodeA])
    expect(enableResult).toBe(true)

    // 步骤 4：把真实 nodeA 对象传入 plugin.getContent（async）
    const html = await plugin.getContent(null, [nodeA])
    expect(typeof html).toBe('string')
    expect(html).toContain('→ M2')
    expect(html).toContain('膜流动性')
    expect(html).toContain('→ M3')
    expect(html).toContain('基因表达')
  })

  // R2 F002 修复：INV-010 同模块内 peer 顺序——构造乱序输入，用严格 indexOf 比较。
  // 反证：删除 renderPeersHtml 中 sortedList.sort(...) 后，本测试必须 fail（A 不在 M 之前）。
  it('INV-010 F002 intra-module sort: peers within same module sorted by name strictly', async () => {
    const wrapper = mount(ConceptMapPanel, { props: singleNodeProps() })
    await nextTick()
    // 输入同模块内乱序：Zebra / Apple / Mango
    const html = wrapper.vm.renderPeersHtml({
      M2: [
        { id: 'z1', name: 'Zebra-concept' },
        { id: 'a1', name: 'Apple-concept' },
        { id: 'm1', name: 'Mango-concept' },
      ],
    })
    const appleIdx = html.indexOf('Apple-concept')
    const mangoIdx = html.indexOf('Mango-concept')
    const zebraIdx = html.indexOf('Zebra-concept')
    expect(appleIdx).toBeGreaterThan(-1)
    expect(mangoIdx).toBeGreaterThan(-1)
    expect(zebraIdx).toBeGreaterThan(-1)
    // 严格 index 比较：Apple < Mango < Zebra（按 name 字母序）
    expect(appleIdx).toBeLessThan(mangoIdx)
    expect(mangoIdx).toBeLessThan(zebraIdx)
  })
})

describe('Phase 1 T10: buildG6Data visual encoding', () => {
  const visualNavigation = [
    {
      id: 'M1',
      name: '分子与细胞',
      big_concepts: [
        { id: 'BC1', name: 'BC1', concept_ids: ['A', 'B'] },
      ],
    },
  ]

  const basePropsFor = (nodes, extras = {}) => ({
    moduleId: 'M1',
    moduleName: '分子与细胞',
    nodes,
    edges: [],
    navigation: visualNavigation,
    qualityIssues: [],
    ...extras,
  })

  it('node size reflects importance_score — importance=10 produces larger size than importance=2', () => {
    // 反例: 若 size 硬编码为常量，两节点 size[0] 相等 → 严格 > 断言失败
    const wrapper = mount(ConceptMapPanel, {
      props: basePropsFor([
        { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
          importance_score: 10, exam_frequency: 100 },
        { id: 'B', name: 'B', big_concept_id: 'BC1', module: 'M1',
          importance_score: 2, exam_frequency: 100 },
      ], { colorMode: 'exam_frequency' }),
    })
    const data = wrapper.vm.buildG6Data()
    const nodeA = data.nodes.find(n => n.id === 'A')
    const nodeB = data.nodes.find(n => n.id === 'B')
    expect(nodeA).toBeDefined()
    expect(nodeB).toBeDefined()
    const sizeA = Array.isArray(nodeA.style.size) ? nodeA.style.size[0] : nodeA.style.size
    const sizeB = Array.isArray(nodeB.style.size) ? nodeB.style.size[0] : nodeB.style.size
    expect(sizeA).toBeGreaterThan(sizeB)
    // importance=10 → size∈[50,70]
    expect(sizeA).toBeGreaterThanOrEqual(50)
    expect(sizeA).toBeLessThanOrEqual(70)
    // importance=2 → size∈[20,30]
    expect(sizeB).toBeGreaterThanOrEqual(20)
    expect(sizeB).toBeLessThanOrEqual(30)
  })

  it('fill color changes with colorMode (exam_frequency vs review_status)', async () => {
    // 反例: 若 colorMode 被忽略，两次 fill 相同 → 断言失败
    const wrapper = mount(ConceptMapPanel, {
      props: basePropsFor([
        { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
          exam_frequency: 500, review_status: 'published', importance_score: 5 },
      ], { colorMode: 'exam_frequency' }),
    })
    const examFill = wrapper.vm.buildG6Data().nodes[0].style.fill
    expect(examFill.toLowerCase()).toMatch(/^#[0-9a-f]{6}$/)

    await wrapper.setProps({ colorMode: 'review_status' })
    const reviewFill = wrapper.vm.buildG6Data().nodes[0].style.fill
    expect(reviewFill.toLowerCase()).toMatch(/^#[0-9a-f]{6}$/)
    expect(examFill).not.toBe(reviewFill)
  })

  it('mastery mode uses mastery state — weak produces red (R > G)', async () => {
    // 反例: 若 mastery 分支走错（例如回落到 review_status），R>G 不成立
    const wrapper = mount(ConceptMapPanel, {
      props: basePropsFor([
        { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
          review_status: 'published', importance_score: 5 },
      ], {
        colorMode: 'mastery',
        nodesWithMastery: [{ id: 'A', mastery_state: 'weak' }],
      }),
    })
    const fill = wrapper.vm.buildG6Data().nodes[0].style.fill
    expect(fill.toLowerCase()).toMatch(/^#[0-9a-f]{6}$/)
    const r = parseInt(fill.slice(1, 3), 16)
    const g = parseInt(fill.slice(3, 5), 16)
    expect(r).toBeGreaterThan(g)
  })
})

// R2 F003：watch([colorMode, nodesWithMastery]) 重绘路径 + focus replay 断言
//
// 反证矩阵（Executor 手动验证）：
//   a) 删除 ConceptMapPanel.vue:463-475 整个 watch([colorMode, nodesWithMastery], ...)
//      → "colorMode 切换触发 graph.setData 重绘" + "focus replay" 两个断言必须全部 fail
//      （setData 永远不被调用，setElementState 初次调用计数不再增长）
//   b) 删除 watch 内部 `if (focusedNodeId.value) { nextTick(updateElementStates) }`
//      → "focus replay" 断言必须 fail（setElementState 不会在 setData 之后被再次调用）
describe('Phase 1 T10 — watch colorMode 重绘 + focus replay (F003)', () => {
  const t10Navigation = [
    { id: 'M1', name: 'M1', big_concepts: [
      { id: 'BC1', name: 'BC1', concept_ids: ['A', 'B'] },
    ]},
  ]
  const t10Nodes = [
    { id: 'A', name: 'A', big_concept_id: 'BC1', module: 'M1',
      review_status: 'teacher_reviewed', importance_score: 5, exam_frequency: 100 },
    { id: 'B', name: 'B', big_concept_id: 'BC1', module: 'M1',
      review_status: 'ai_draft', importance_score: 3, exam_frequency: 50 },
  ]
  const t10Edges = [{ source: 'A', target: 'B', type: 'prerequisite_hard' }]

  async function mountT10(propsOverride = {}) {
    const wrapper = mount(ConceptMapPanel, {
      props: {
        moduleId: 'M1',
        moduleName: 'M1',
        nodes: t10Nodes,
        edges: t10Edges,
        navigation: t10Navigation,
        qualityIssues: [],
        colorMode: 'exam_frequency',
        nodesWithMastery: [],
        ...propsOverride,
      },
      attachTo: document.body,
    })
    // onMounted → nextTick → createGraph
    await nextTick()
    await nextTick()
    return wrapper
  }

  it('切换 colorMode 触发 graph.setData() 重绘——setData 被调用一次，入参含节点数组', async () => {
    // 反例: watch 被删/条件漏写 → setData 永远不调用 → 断言 fail
    const wrapper = await mountT10()
    expect(graphInstances.length).toBeGreaterThan(0)
    const graph = graphInstances[graphInstances.length - 1]
    expect(graph.setData).toBeDefined()
    // 初始 mount 后 setData 应未被调用（createGraph 用的是 addNode/addEdge，不走 setData）
    const setDataCountsBefore = graph.setData.mock.calls.length

    // 切换 colorMode 触发 watch([colorMode, nodesWithMastery])
    await wrapper.setProps({ colorMode: 'review_status' })
    await nextTick()
    await nextTick()

    expect(graph.setData.mock.calls.length).toBeGreaterThan(setDataCountsBefore)
    // 断言 setData 入参是 buildG6Data() 结构（{ nodes, edges }）
    const payload = graph.setData.mock.calls[graph.setData.mock.calls.length - 1][0]
    expect(payload).toBeDefined()
    expect(Array.isArray(payload.nodes)).toBe(true)
    expect(Array.isArray(payload.edges)).toBe(true)
    expect(payload.nodes.map(n => n.id).sort()).toEqual(['A', 'B'])
    // graph.render 也应该被调用
    expect(graph.render.mock.calls.length).toBeGreaterThan(0)
  })

  it('focus 态下切换 colorMode：setData 之后 setElementState 被再次调用（focus replay）', async () => {
    // 反例: watch 内部 focus replay 分支被删 → setElementState 调用计数不再增长 → 断言 fail
    const wrapper = await mountT10()
    const graph = graphInstances[graphInstances.length - 1]

    // 先点击节点 A 进入焦点态（focusedNodeId='A' 触发一次 setElementState）
    graph.handlers['node:click']({ target: { id: 'A' } })
    await nextTick()
    await nextTick()
    expect(wrapper.vm.focusedNodeId).toBe('A')
    const setElemCountsAfterFocus = graph.setElementState.mock.calls.length
    const setDataCountsBefore = graph.setData.mock.calls.length

    // 切换 colorMode 触发 watch：setData → nextTick → updateElementStates(focusedNodeId)
    await wrapper.setProps({ colorMode: 'mastery' })
    await nextTick()
    await nextTick()

    // setData 先被调用
    expect(graph.setData.mock.calls.length).toBeGreaterThan(setDataCountsBefore)
    // 之后 setElementState 又被调用（focus replay）
    expect(graph.setElementState.mock.calls.length).toBeGreaterThan(setElemCountsAfterFocus)
  })
})
