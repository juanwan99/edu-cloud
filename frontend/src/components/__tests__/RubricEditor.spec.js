import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import RubricEditor from '../RubricEditor.vue'

const NAIVE_STUBS = {
  'n-spin': { template: '<div><slot /></div>' },
  'n-space': { template: '<div><slot /></div>' },
  'n-tag': { template: '<span><slot /></span>' },
}

describe('RubricEditor', () => {
  const items = [
    { blankNo: '1', score: 4, answer: 'A1', intent: 'I1', coreRequirement: 'C1' },
    { blankNo: '2', score: 4, answer: 'A2', intent: 'I2', coreRequirement: 'C2' },
  ]

  it('renders items', () => {
    const w = mount(RubricEditor, {
      props: { modelValue: items, maxScore: 8 },
      global: { stubs: NAIVE_STUBS },
    })
    expect(w.findAll('.rubric-item')).toHaveLength(2)
  })

  it('shows total', () => {
    const w = mount(RubricEditor, {
      props: { modelValue: items, maxScore: 8 },
      global: { stubs: NAIVE_STUBS },
    })
    expect(w.text()).toContain('8 / 8')
  })

  it('warns mismatch', () => {
    const w = mount(RubricEditor, {
      props: { modelValue: items, maxScore: 10 },
      global: { stubs: NAIVE_STUBS },
    })
    expect(w.find('.warning').exists()).toBe(true)
  })

  it('empty state', () => {
    const w = mount(RubricEditor, {
      props: { modelValue: [], maxScore: 8 },
      global: { stubs: NAIVE_STUBS },
    })
    expect(w.text()).toContain('暂无')
  })
})
