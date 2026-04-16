import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ModuleStatCard from '../../components/knowledge-tree/ModuleStatCard.vue'

describe('ModuleStatCard', () => {
  it('renders module name, counts, and progress', () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        conceptCount: 22, bigConceptCount: 3,
        reviewedCount: 12, highCount: 0, medCount: 0,
      },
    })
    expect(wrapper.text()).toContain('分子与细胞')
    expect(wrapper.text()).toContain('22')
    expect(wrapper.text()).toContain('3')
    // 审核进度 12/22 = 55%
    expect(wrapper.text()).toContain('12/22')
    expect(wrapper.text()).toContain('55%')
  })

  it('emits select on click', async () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: '分子与细胞',
        conceptCount: 22, bigConceptCount: 3, reviewedCount: 0,
      },
    })
    await wrapper.trigger('click')
    expect(wrapper.emitted('select')).toBeTruthy()
    expect(wrapper.emitted('select').length).toBe(1)
  })

  it('shows 0% progress when conceptCount is 0', () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Empty',
        conceptCount: 0, bigConceptCount: 0, reviewedCount: 0,
      },
    })
    expect(wrapper.text()).toContain('0/0')
    expect(wrapper.text()).toContain('0%')
  })

  it('shows 100% progress when fully reviewed', () => {
    const wrapper = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Full',
        conceptCount: 10, bigConceptCount: 2, reviewedCount: 10,
      },
    })
    expect(wrapper.text()).toContain('10/10')
    expect(wrapper.text()).toContain('100%')
  })

  it('renders HIGH/MED badges only when counts > 0', () => {
    const withBoth = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Test',
        conceptCount: 5, bigConceptCount: 1, reviewedCount: 0,
        highCount: 3, medCount: 5,
      },
    })
    expect(withBoth.text()).toContain('3 HIGH')
    expect(withBoth.text()).toContain('5 MED')

    const medOnly = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Test',
        conceptCount: 5, bigConceptCount: 1, reviewedCount: 0,
        highCount: 0, medCount: 2,
      },
    })
    expect(medOnly.text()).not.toContain('HIGH')
    expect(medOnly.text()).toContain('2 MED')

    const none = mount(ModuleStatCard, {
      props: {
        moduleId: 'M1', moduleName: 'Test',
        conceptCount: 5, bigConceptCount: 1, reviewedCount: 0,
        highCount: 0, medCount: 0,
      },
    })
    expect(none.text()).not.toContain('HIGH')
    expect(none.text()).not.toContain('MED')
  })
})
