import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { buildChapterTree } from '../../components/knowledge-tree/useKnowledgeTree'
import TreeNavPanel from '../../components/knowledge-tree/TreeNavPanel.vue'

describe('buildChapterTree', () => {
  it('aggregates concepts into book→chapter→section tree', () => {
    const nodes = [
      { id: 'C1', textbook_chapters: [{ book: 'b1', chapter: 'ch01', section: 's01', title: '第1节' }] },
      { id: 'C2', textbook_chapters: [{ book: 'b1', chapter: 'ch01', section: 's01', title: '第1节' }] },
      { id: 'C3', textbook_chapters: [{ book: 'b1', chapter: 'ch02', section: 's01', title: '第1节' }] },
    ]
    const tree = buildChapterTree(nodes)
    expect(tree).toHaveLength(1)
    expect(tree[0].id).toBe('b1')
    expect(tree[0].chapters).toHaveLength(2)
    expect(tree[0].chapters[0].sections[0].concept_ids).toEqual(['C1', 'C2'])
  })

  it('handles cross-book concepts', () => {
    const nodes = [
      {
        id: 'Shared',
        textbook_chapters: [
          { book: 'b1', chapter: 'ch01', section: 's01', title: 'a' },
          { book: 'xe1', chapter: 'ch02', section: 's02', title: 'b' },
        ],
      },
    ]
    const tree = buildChapterTree(nodes)
    expect(tree).toHaveLength(2)
    expect(tree.map(b => b.id).sort()).toEqual(['b1', 'xe1'])
  })

  it('returns empty when all nodes have empty textbook_chapters', () => {
    const nodes = [{ id: 'C1', textbook_chapters: [] }]
    const tree = buildChapterTree(nodes)
    expect(tree).toHaveLength(0)
  })
})

describe('TreeNavPanel — nav mode + emits contract', () => {
  const sampleNavigation = [
    {
      id: 'M1',
      name: '分子与细胞',
      big_concepts: [{ id: 'BC1', name: '细胞学说', concept_ids: ['C1'] }],
    },
  ]
  const sampleNodes = [
    {
      id: 'C1',
      name: '细胞膜',
      module: 'M1',
      textbook_chapters: [{ book: 'b1', chapter: 'ch01', section: 's01', title: '第1节 细胞膜' }],
    },
  ]

  function mountPanel() {
    return mount(TreeNavPanel, {
      props: {
        navigation: sampleNavigation,
        moduleMastery: [],
        nodesWithMastery: sampleNodes,
        selectedModule: 'all',
      },
    })
  }

  it('default module mode shows module name but not book title', () => {
    const wrapper = mountPanel()
    expect(wrapper.text()).toContain('分子与细胞')
    expect(wrapper.text()).not.toContain('必修1')
  })

  it('chapter mode shows book title "必修1"', async () => {
    const wrapper = mountPanel()
    wrapper.vm.navMode = 'chapter'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('必修1')
  })

  it('select-module emits module id string for M1 key', () => {
    const wrapper = mountPanel()
    wrapper.vm.handleSelect(['M1'])
    const emitted = wrapper.emitted('select-module')
    expect(emitted).toHaveLength(1)
    expect(emitted[0]).toEqual(['M1'])
  })

  it('select-node emits full node object (F010) in module mode', () => {
    const wrapper = mountPanel()
    wrapper.vm.handleSelect(['C1'])
    const emitted = wrapper.emitted('select-node')
    expect(emitted).toHaveLength(1)
    const payload = emitted[0][0]
    expect(typeof payload).toBe('object')
    expect(payload.id).toBe('C1')
    expect(payload.name).toBe('细胞膜')
    expect(payload.module).toBe('M1')
  })

  it('select-node keeps full node object across chapter mode (F010 persistence)', async () => {
    const wrapper = mountPanel()
    wrapper.vm.navMode = 'chapter'
    await wrapper.vm.$nextTick()
    wrapper.vm.handleSelect(['C1'])
    const emitted = wrapper.emitted('select-node')
    expect(emitted).toHaveLength(1)
    const payload = emitted[0][0]
    expect(payload.id).toBe('C1')
    expect(payload.module).toBe('M1')
  })

  it('aggregate keys (book:/chapter:/section:) do not emit', async () => {
    const wrapper = mountPanel()
    wrapper.vm.navMode = 'chapter'
    await wrapper.vm.$nextTick()
    wrapper.vm.handleSelect(['book:b1'])
    wrapper.vm.handleSelect(['chapter:b1:ch01'])
    wrapper.vm.handleSelect(['section:b1:ch01:s01'])
    expect(wrapper.emitted('select-module')).toBeUndefined()
    expect(wrapper.emitted('select-node')).toBeUndefined()
  })
})
