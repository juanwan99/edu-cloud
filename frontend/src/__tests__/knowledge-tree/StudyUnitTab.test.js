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

  it('planning_weight 0 values render as "0" not "—" (R2 F004 mutant: ?? → || 必红)', () => {
    const wrapper = mount(StudyUnitTab, {
      props: {
        node: {
          study_unit_id: 'su:zero',
          estimated_minutes: 30,
          prerequisite_depth: 1,
          planning_weight: { exam_frequency: 0, error_prone: 0, priority_score: 0 },
          textbook_chapters: [],
        }
      }
    })
    const values = wrapper.findAll('.weight-value').map(el => el.text())
    // 反例: 若实现用 `||` 代替 `??`，0 会被当 falsy 替换为 '—'
    expect(values.filter(v => v === '0')).toHaveLength(3)
    // transfer_value 未提供 → nullish → '—'；其余 3 项精确 '0'
    expect(values.filter(v => v === '—')).toHaveLength(1)
  })
})
