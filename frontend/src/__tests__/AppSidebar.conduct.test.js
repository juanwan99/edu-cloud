import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, nextTick } from 'vue'

vi.mock('../config/roles.js', () => ({
  normalizeRole: (r) => r || 'subject_teacher',
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/' }),
  RouterLink: {
    template: '<a v-bind="$attrs"><slot /></a>',
    props: ['to'],
    inheritAttrs: false,
  },
}))

const mockAuth = reactive({
  currentRole: { role: 'academic_director', school_id: 'school-1' },
  enabledModules: ['conduct'],
  modulesLoaded: true,
  checkPermission: () => true,
})

vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => mockAuth,
}))

import AppSidebar from '../components/shell/AppSidebar.vue'

describe('AppSidebar conduct 入口级渲染', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('academic_director 侧边栏 conduct 段渲染 8 项', async () => {
    mockAuth.currentRole = { role: 'academic_director', school_id: 'school-1' }
    mockAuth.enabledModules = ['conduct']
    mockAuth.modulesLoaded = true
    const wrapper = mount(AppSidebar)
    await nextTick()
    const conductItems = wrapper.findAll('[data-module="conduct"]')
    expect(conductItems.length).toBe(8)
  })
})
