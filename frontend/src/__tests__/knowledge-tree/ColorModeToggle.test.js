import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ColorModeToggle from '../../components/knowledge-tree/ColorModeToggle.vue'

describe('ColorModeToggle', () => {
  it('renders all three mode labels', () => {
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency' },
    })
    const text = wrapper.text()
    expect(text).toContain('考频')
    expect(text).toContain('掌握度')
    expect(text).toContain('审核状态')
  })

  it('emits update:modelValue when onChange called', () => {
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency', hasStudent: true },
    })
    wrapper.vm.onChange('mastery')
    const events = wrapper.emitted()['update:modelValue']
    expect(events).toBeDefined()
    expect(events.length).toBe(1)
    expect(events[0]).toEqual(['mastery'])
  })

  it('syncs localMode from parent modelValue prop', async () => {
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency', hasStudent: true },
    })
    await wrapper.setProps({ modelValue: 'review_status' })
    // 反例: 若 watch props.modelValue 未实现, localMode 仍是 exam_frequency
    expect(wrapper.vm.localMode).toBe('review_status')
  })

  it('disables mastery when hasStudent=false', () => {
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency', hasStudent: false },
    })
    // 断言 DOM 里 disabled 属性存在于掌握度 radio 上
    const masteryButton = wrapper.findAll('.n-radio-button').find(
      (el) => el.text().includes('掌握度')
    )
    expect(masteryButton).toBeDefined()
    // Naive 会把 disabled 状态反映到 input / class 上
    expect(masteryButton.html()).toMatch(/disabled/i)
  })

  it('does NOT disable mastery when hasStudent=true', () => {
    // 反例: 若 disabled 绑定是 hasStudent 而非 !hasStudent, true 会变 disabled
    const wrapper = mount(ColorModeToggle, {
      props: { modelValue: 'exam_frequency', hasStudent: true },
    })
    const masteryInput = wrapper
      .findAll('.n-radio-button')
      .find((el) => el.text().includes('掌握度'))
      .find('input')
    if (masteryInput && masteryInput.element) {
      expect(masteryInput.element.disabled).toBe(false)
    }
  })
})
