import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick, reactive } from 'vue'

const mockRouterPush = vi.hoisted(() => vi.fn())

// Mock sidebarConfig to return predictable grouped items.
// Phase 0.7A：AppSidebar.vue 现调用 getSidebarGroups(role, moduleGateFromAuth(auth))，第二参数是
// 门控上下文 {exempt, modulesLoaded, enabledModules}。mock 按 fail-closed 语义过滤：
//   可见 IFF 无 moduleCode || exempt || (modulesLoaded && enabledModules.includes(code))
vi.mock('../config/sidebarConfig.js', () => ({
  getSidebarGroups: (role, gate = {}) => {
    const exempt = !!gate.exempt
    const loaded = !!gate.modulesLoaded
    const enabled = new Set(Array.isArray(gate.enabledModules) ? gate.enabledModules : [])
    const visible = code => !code || exempt || (loaded && enabled.has(code))
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
    return groups
      .map(g => ({ ...g, children: g.children.filter(c => visible(c.moduleCode)) }))
      .filter(g => g.children.length > 0)
  },
}))

vi.mock('../config/roles.js', () => ({
  normalizeRole: (r) => r || 'subject_teacher',
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/' }),
  useRouter: () => ({ push: mockRouterPush }),
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
    mockRouterPush.mockClear()
  })

  // Phase 0.7A（R5 F-001）：翻转旧 fail-open。学校用户模块未加载 → 模块组 fail-closed 隐藏。
  it('fail-closed: hides all module groups when modulesLoaded=false (school user, not yet loaded)', async () => {
    mockAuth.modulesLoaded = false
    const wrapper = mount(AppSidebar)
    await nextTick()
    const groupHeaders = wrapper.findAll('.nav-group__header')
    expect(groupHeaders).toHaveLength(0)
    // 概览入口始终保留（非模块组）
    expect(wrapper.text()).toContain('概览')
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

  // Phase 0.7A（R5 F-001）：翻转旧 fail-open。学校用户空 enabledModules（加载失败/无模块）→
  // 模块组全部 fail-closed 隐藏，仅保留概览。这是本任务修复的核心漏洞面。
  it('fail-closed: hides ALL module groups when enabledModules=[], keeps overview', async () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = []
    const wrapper = mount(AppSidebar)
    await nextTick()
    const groupHeaders = wrapper.findAll('.nav-group__header')
    expect(groupHeaders).toHaveLength(0)
    expect(wrapper.text()).toContain('概览')
  })

  // admin / 无 school_id → gate.exempt → 模块组全显示（即使未加载），保留豁免 feature。
  it('exempt: admin without school_id shows all module groups even when not loaded', async () => {
    mockAuth.currentRole = { role: 'platform_admin' }
    mockAuth.modulesLoaded = false
    mockAuth.enabledModules = []
    const wrapper = mount(AppSidebar)
    await nextTick()
    const groupHeaders = wrapper.findAll('.nav-group__header')
    expect(groupHeaders).toHaveLength(3)
  })

  it('navigates to the first child when clicking a group on forced-collapsed screens', async () => {
    // 学校用户需已加载且启用模块，模块组才可见可点（fail-closed 下未加载无组可点）
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = ['exam']
    const originalMatchMedia = window.matchMedia
    window.matchMedia = vi.fn().mockReturnValue({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })

    let wrapper
    try {
      wrapper = mount(AppSidebar)
      await nextTick()
      await wrapper.find('.nav-group__header').trigger('click')
      expect(mockRouterPush).toHaveBeenCalledWith('/exams')
    } finally {
      wrapper?.unmount()
      window.matchMedia = originalMatchMedia
    }
  })
})
