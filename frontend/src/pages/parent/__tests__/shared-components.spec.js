import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ParentSkeleton from '../../../components/parent/ParentSkeleton.vue'
import ParentEmpty from '../../../components/parent/ParentEmpty.vue'
import NumberRoll from '../../../components/parent/NumberRoll.vue'
import PullRefresh from '../../../components/parent/PullRefresh.vue'
import ChildSwitcher from '../../../components/parent/ChildSwitcher.vue'

describe('ParentSkeleton', () => {
  it('renders skeleton cards', () => {
    const wrapper = mount(ParentSkeleton, { props: { rows: 3 } })
    expect(wrapper.findAll('.skeleton-card').length).toBe(3)
  })
  it('defaults to 2 rows', () => {
    const wrapper = mount(ParentSkeleton)
    expect(wrapper.findAll('.skeleton-card').length).toBe(2)
  })
})

describe('ParentEmpty', () => {
  it('renders message', () => {
    const wrapper = mount(ParentEmpty, { props: { message: '暂无数据' } })
    expect(wrapper.text()).toContain('暂无数据')
  })
  it('renders action slot', () => {
    const wrapper = mount(ParentEmpty, {
      props: { message: 'test' },
      slots: { action: '<button>Retry</button>' },
    })
    expect(wrapper.find('button').text()).toBe('Retry')
  })
})

describe('NumberRoll', () => {
  it('renders the value', () => {
    const wrapper = mount(NumberRoll, { props: { value: 42 } })
    expect(wrapper.text()).toContain('42')
  })
  it('renders dash for null', () => {
    const wrapper = mount(NumberRoll, { props: { value: null } })
    expect(wrapper.text()).toContain('-')
  })
})

describe('PullRefresh', () => {
  it('renders slot content', () => {
    const wrapper = mount(PullRefresh, {
      props: { loading: false },
      slots: { default: '<div class="inner">content</div>' },
    })
    expect(wrapper.find('.inner').text()).toBe('content')
  })
  it('shows update time when provided', () => {
    const wrapper = mount(PullRefresh, {
      props: { loading: false, lastUpdate: '21:08' },
      slots: { default: 'content' },
    })
    expect(wrapper.text()).toContain('21:08')
  })
})

describe('ChildSwitcher', () => {
  const children = [
    { student_id: 1, student_name: '张小明', class_name: '七年级3班' },
    { student_id: 2, student_name: '张小红', class_name: '三年级1班' },
  ]
  it('renders children list', () => {
    const wrapper = mount(ChildSwitcher, { props: { show: true, children, currentId: 1 } })
    expect(wrapper.text()).toContain('张小明')
    expect(wrapper.text()).toContain('张小红')
  })
  it('emits select on child click', async () => {
    const wrapper = mount(ChildSwitcher, { props: { show: true, children, currentId: 1 } })
    await wrapper.findAll('.child-item')[1].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual([2])
  })
})
