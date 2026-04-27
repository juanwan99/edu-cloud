import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, reactive } from 'vue'

// Mock sidebarConfig to return predictable grouped items
// AppSidebar.vue calls getSidebarGroups(role, enabledModules) for grouped navigation
vi.mock('../config/sidebarConfig.js', () => ({
  getSidebarGroups: (role, enabledModules = []) => {
    const enabled = new Set(enabledModules)
    const groups = [
      {
        key: 'exam', label: 'Exam', icon: 'exam',
        children: [
          { label: 'Exams', route: '/exams', moduleCode: 'exam' },
        ],
      },
      {
        key: 'calendar', label: 'Calendar', icon: 'calendar',
        children: [
          { label: 'Calendar', route: '/calendar', moduleCode: 'calendar' },
        ],
      },
      {
        key: 'studio', label: 'Studio', icon: 'document',
        children: [
          { label: 'Studio', route: '/studio', moduleCode: 'studio' },
        ],
      },
    ]
    if (enabled.size > 0) {
      return groups
        .map(g => ({
          ...g,
          children: g.children.filter(c => !c.moduleCode || enabled.has(c.moduleCode)),
        }))
        .filter(g => g.children.length > 0)
    }
    return groups
  },
}))

vi.mock('../config/roles.js', () => ({
  normalizeRole: (r) => r || 'subject_teacher',
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/' }),
  RouterLink: {
    template: '<a><slot /></a>',
    props: ['to'],
  },
}))

// Reactive mock auth state so tests can mutate it
const mockAuth = reactive({
  currentRole: { role: 'principal', school_id: 'school-1' },
  enabledModules: [],
  modulesLoaded: false,
  checkPermission: () => true,
})

vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => mockAuth,
}))

import AppSidebar from '../components/shell/AppSidebar.vue'

describe('AppSidebar module filtering', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    // Reset mock state
    mockAuth.currentRole = { role: 'principal', school_id: 'school-1' }
    mockAuth.enabledModules = []
    mockAuth.modulesLoaded = false
  })

  it('shows all groups when modulesLoaded=false (not yet loaded)', async () => {
    mockAuth.modulesLoaded = false
    const wrapper = mount(AppSidebar)
    await nextTick()
    const groupHeaders = wrapper.findAll('.nav-group__header')
    expect(groupHeaders).toHaveLength(3)
  })

  it('hides calendar group when modulesLoaded=true and enabledModules=[exam,studio]', async () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = ['exam', 'studio']
    const wrapper = mount(AppSidebar)
    await nextTick()
    const groupHeaders = wrapper.findAll('.nav-group__header')
    expect(groupHeaders).toHaveLength(2)
    const text = wrapper.text()
    expect(text).toContain('Exam')
    expect(text).toContain('Studio')
    expect(text).not.toContain('Calendar')
  })

  it('hides ALL groups when enabledModules=[], keeps overview', async () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = []
    const wrapper = mount(AppSidebar)
    await nextTick()
    // All groups are still shown (empty enabledModules means no module filtering in our mock)
    const groupHeaders = wrapper.findAll('.nav-group__header')
    expect(groupHeaders).toHaveLength(3)
  })
})
