import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, reactive } from 'vue'

// Mock sidebarConfig to return predictable items
vi.mock('../config/sidebarConfig.js', () => ({
  getSidebarItems: () => [
    { icon: 'dashboard', label: 'Dashboard', route: '/' },
    { icon: 'exam', label: 'Exams', route: '/exams', moduleCode: 'exam' },
    { icon: 'calendar', label: 'Calendar', route: '/analysis', moduleCode: 'calendar' },
    { icon: 'document', label: 'Studio', route: '/analysis', moduleCode: 'studio' },
  ],
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

  it('shows all items when modulesLoaded=false (not yet loaded)', async () => {
    mockAuth.modulesLoaded = false
    const wrapper = mount(AppSidebar)
    await nextTick()
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Exams')
    expect(wrapper.text()).toContain('Calendar')
    expect(wrapper.text()).toContain('Studio')
  })

  it('hides calendar when modulesLoaded=true and enabledModules=[exam,studio]', async () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = ['exam', 'studio']
    const wrapper = mount(AppSidebar)
    await nextTick()
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Exams')
    expect(wrapper.text()).toContain('Studio')
    expect(wrapper.text()).not.toContain('Calendar')
  })

  it('hides ALL module-bound items when enabledModules=[], keeps non-module items', async () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = []
    const wrapper = mount(AppSidebar)
    await nextTick()
    // Dashboard has no moduleCode -> always shown
    expect(wrapper.text()).toContain('Dashboard')
    // All module-bound items hidden
    expect(wrapper.text()).not.toContain('Exams')
    expect(wrapper.text()).not.toContain('Calendar')
    expect(wrapper.text()).not.toContain('Studio')
  })
})
