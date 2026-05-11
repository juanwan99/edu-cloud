import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import ParentLayout from '../../../layouts/ParentLayout.vue'

vi.mock('../../../api/conduct', () => ({
  getParentMe: vi.fn().mockResolvedValue({ data: { display_name: 'Parent' } }),
  getChildren: vi.fn().mockResolvedValue({ data: { children: [
    { student_id: 1, student_name: '张小明', class_name: '七年级3班', total_points: 38 },
  ] } }),
}))

function makeRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/parent', component: { template: '<div>overview</div>' } },
      { path: '/parent/scores', component: { template: '<div>scores</div>' } },
      { path: '/parent/conduct', component: { template: '<div>conduct</div>' } },
      { path: '/parent/profile', component: { template: '<div>profile</div>' } },
      { path: '/parent/login', component: { template: '<div>login</div>' } },
    ],
  })
}

describe('ParentLayout', () => {
  beforeEach(() => {
    localStorage.setItem('cp_token', 'fake-token')
    localStorage.setItem('parent_theme', 'dark')
  })

  it('renders 4 tab items', async () => {
    const router = makeRouter()
    await router.push('/parent')
    await router.isReady()
    const wrapper = mount(ParentLayout, { global: { plugins: [router] } })
    await vi.dynamicImportSettled()
    const tabs = wrapper.findAll('.tab-item')
    expect(tabs.length).toBe(4)
  })

  it('uses Lucide icons instead of emoji', async () => {
    const router = makeRouter()
    await router.push('/parent')
    await router.isReady()
    const wrapper = mount(ParentLayout, { global: { plugins: [router] } })
    await vi.dynamicImportSettled()
    // No emoji characters should be present in tab bar
    const tabBar = wrapper.find('.bottom-tabs')
    expect(tabBar.text()).not.toMatch(/[📊📝🏆📋👤]/)
  })

  it('sets data-theme attribute', async () => {
    const router = makeRouter()
    await router.push('/parent')
    await router.isReady()
    const wrapper = mount(ParentLayout, { global: { plugins: [router] } })
    await vi.dynamicImportSettled()
    expect(wrapper.find('[data-theme]').exists()).toBe(true)
  })
})
