import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StudyUnitTab from '../../components/knowledge-tree/StudyUnitTab.vue'

describe('StudyUnitTab', () => {
  it('shows empty when no study_unit_id', () => {
    const wrapper = mount(StudyUnitTab, {
      props: { node: { study_unit_id: null } }
    })
    expect(wrapper.text()).toContain('暂无关联学习单元')
  })

  it('renders SU info when present', () => {
    const wrapper = mount(StudyUnitTab, {
      props: {
        node: {
          study_unit_id: 'su:bio_sr:m1_test',
          estimated_minutes: 70,
          prerequisite_depth: 2,
          planning_weight: { priority_score: 8.5, exam_frequency: 9 },
          textbook_chapters: [{ book: 'b1', chapter: 'ch03', title: '第3章' }],
        }
      }
    })
    expect(wrapper.text()).toContain('su:bio_sr:m1_test')
    expect(wrapper.text()).toContain('70 分钟')
    expect(wrapper.text()).toContain('8.5')
    expect(wrapper.text()).toContain('第3章')
  })
})
