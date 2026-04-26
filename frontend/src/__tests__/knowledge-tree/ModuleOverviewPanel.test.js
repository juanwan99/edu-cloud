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

  // Phase 1 T13: statsOverview 渲染（F004 入口级 + INV-004 null 降级）
  // 设计契约 (派发 plan T13 Step 4):
  //   - statsOverview.module_stats[Mx].avg_freq → 'Math.round(v)' 整数，null → '—'
  //   - statsOverview.module_stats[Mx].exam_coverage → 'Math.round(v*100)%'，null → '—'
  // 反证锁定：若忽略 statsOverview prop (mutant: 删 formatAvgFreq 直接 return '—') → 真实值测试红
  describe('statsOverview 渲染（F004 + INV-004）', () => {
    const statsOverview = {
      module_stats: {
        M1: { concepts: 2, edges: 1, avg_freq: 300, exam_coverage: 0.667 },
        M2: { concepts: 1, edges: 0, avg_freq: 150, exam_coverage: 1.0 },
      },
    }

    it('renders avg_freq integer from statsOverview (F004 入口级：反例若忽略 statsOverview 则显示 "—")', () => {
      const wrapper = mount(ModuleOverviewPanel, {
        props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {}, statsOverview },
      })
      const text = wrapper.text()
      expect(text).toContain('平均考频: 300')
      expect(text).toContain('平均考频: 150')
    })

    it('renders exam_coverage as percentage (0.667 → 67% / 1.0 → 100%)', () => {
      const wrapper = mount(ModuleOverviewPanel, {
        props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {}, statsOverview },
      })
      const text = wrapper.text()
      expect(text).toContain('考频覆盖: 67%')
      expect(text).toContain('考频覆盖: 100%')
    })

    it('degrades gracefully when statsOverview is null (INV-004: 不崩溃 + 显示 "—")', () => {
      // 反例：如果强依赖 statsOverview (mutant: 删 null safe) → 崩溃
      const wrapper = mount(ModuleOverviewPanel, {
        props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {}, statsOverview: null },
      })
      const text = wrapper.text()
      // 所有模块显示 '—'
      const avgDashCount = (text.match(/平均考频: —/g) || []).length
      const covDashCount = (text.match(/考频覆盖: —/g) || []).length
      expect(avgDashCount).toBe(2)  // 2 modules
      expect(covDashCount).toBe(2)
      // 空数字精准不出现
      expect(text).not.toContain('平均考频: 0')
      expect(text).not.toContain('考频覆盖: 0%')
    })

    it('degrades gracefully when statsOverview.module_stats missing for some module', () => {
      // M1 有 stats，M2 缺 → M1 显示数字，M2 显示 '—'
      const partialStats = { module_stats: { M1: { avg_freq: 500, exam_coverage: 0.8 } } }
      const wrapper = mount(ModuleOverviewPanel, {
        props: { navigation: mockNavigation, nodes: mockNodes, edges: mockEdges, modulesQuality: {}, statsOverview: partialStats },
      })
      const text = wrapper.text()
      expect(text).toContain('平均考频: 500')
      expect(text).toContain('考频覆盖: 80%')
      expect(text).toContain('平均考频: —')  // M2
      expect(text).toContain('考频覆盖: —')
    })

    it('renders freq distribution bar from nodes.exam_frequency (前端派生)', () => {
      // M1 = {A:600(high), B:100(mid)} → 50/50/0；M2 = {C:0(low)} → 0/0/100
      const nodesWithFreq = [
        { id: 'A', module: 'M1', review_status: 'teacher_reviewed', exam_frequency: 600 },
        { id: 'B', module: 'M1', review_status: 'ai_draft', exam_frequency: 100 },
        { id: 'C', module: 'M2', review_status: 'published', exam_frequency: 0 },
      ]
      const wrapper = mount(ModuleOverviewPanel, {
        props: { navigation: mockNavigation, nodes: nodesWithFreq, edges: mockEdges, modulesQuality: {}, statsOverview },
      })
      const html = wrapper.html()
      // 分布条样式 width 50% / 50% / 100%（低频段）应落盘
      expect(html).toMatch(/freq-seg high[^"]*"\s+style="width:\s*50%/i)
      expect(html).toMatch(/freq-seg low[^"]*"\s+style="width:\s*100%/i)
    })
  })
})
