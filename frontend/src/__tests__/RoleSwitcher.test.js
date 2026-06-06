import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import RoleSwitcher from '../components/shell/RoleSwitcher.vue'

const push = vi.hoisted(() => vi.fn())
const switchRole = vi.hoisted(() => vi.fn())
const route = vi.hoisted(() => ({ path: '/marking', meta: {} }))
const source = readFileSync(resolve(process.cwd(), 'src/components/shell/RoleSwitcher.vue'), 'utf-8')

const DEFAULT_AUTH = () => ({
  displayName: 'Gao',
  roles: [
    { id: 'r1', role: 'subject_teacher', context: { name: 'Yucai' }, is_primary: true },
    { id: 'r2', role: 'school_admin', context: { name: 'Yucai' }, is_primary: false },
  ],
  currentRoleIndex: 0,
  currentRole: { id: 'r1', role: 'subject_teacher', context: { name: 'Yucai' } },
  currentContext: { name: 'Yucai' },
  enabledModules: ['exam', 'grading', 'study_analytics'],
  modulesLoaded: true,
  switchRole,
  logout: vi.fn(),
})
const mockAuth = vi.hoisted(() => ({}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => route,
}))

vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => mockAuth,
}))

vi.mock('naive-ui', () => ({
  NDropdown: {
    template: '<div><slot /></div>',
    props: ['options', 'value', 'trigger'],
  },
  NTag: {
    template: '<span><slot /></span>',
  },
}))

describe('RoleSwitcher route safety', () => {
  beforeEach(() => {
    push.mockClear()
    switchRole.mockReset()
    route.path = '/marking'
    route.meta = {}
    Object.keys(mockAuth).forEach(k => delete mockAuth[k])
    Object.assign(mockAuth, DEFAULT_AUTH())
  })

  it('returns to dashboard after switching identity away from a personal-only route', async () => {
    switchRole.mockResolvedValueOnce(true)
    const wrapper = mount(RoleSwitcher, { props: { compact: true } })
    await wrapper.vm.handleSwitch(1)
    expect(push).toHaveBeenCalledWith('/')
  })

  it('keeps the current route when the target role owns that matrix entry', async () => {
    route.path = '/analytics/report'
    switchRole.mockResolvedValueOnce(true)
    const wrapper = mount(RoleSwitcher, { props: { compact: true } })

    await wrapper.vm.handleSwitch(1)

    expect(push).not.toHaveBeenCalled()
  })

  it('renders identity switcher as an explicit click button', () => {
    const wrapper = mount(RoleSwitcher, { props: { compact: true } })
    const trigger = wrapper.find('button.role-switcher')

    expect(trigger.exists()).toBe(true)
    expect(trigger.attributes('type')).toBe('button')
    expect(trigger.attributes('aria-label')).toContain('切换身份')
  })

  it('uses role-entry matrix ownership and explicit identity copy', () => {
    expect(source).toContain('routeBelongsToRoleEntry(route.path, targetRoleKey, getRoleEntryPolicy(targetRoleKey))')
    expect(source).not.toContain('getSidebar' + 'Items')
    expect(source).toContain("role.is_primary ? '主身份' : '可切换'")
    expect(source).toContain("'当前'")
  })

  // Phase 0.7A（R5 F-001）：切换身份后用门控上下文判定当前路由可达，移除
  // `auth.modulesLoaded ? auth.enabledModules : []` fail-open 兜底。
  it('uses module gate context instead of fail-open empty-array fallback', () => {
    expect(source).toContain('moduleGateFromAuth(auth)')
    expect(source).not.toContain('auth.modulesLoaded ? auth.enabledModules : []')
    // R6/R7 F-001：当前路由可达性走 canAccessMatchedRoute（静态∪动态 meta，权限+模块）
    expect(source).toContain('canAccessMatchedRoute(targetRoleKey, route.path, route.meta, moduleGateFromAuth(auth))')
  })

  // R6 F-001（MED security_design）：停留动态模块页 → 切到未启用该模块的学校身份 → 必须回退 /。
  // 修复前 /exams/123 在 routeAccess 精确表匹配不到 moduleCode → 模块维度 fail-open 放行（不回退）。
  it('fail-closed: redirects to / when switching to a school identity lacking the dynamic route module', async () => {
    route.path = '/exams/123'
    route.meta = { moduleCode: 'exam' }
    mockAuth.currentRole = { id: 'r2', role: 'school_admin', school_id: 's1', context: { name: 'Yucai' } }
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = ['grading'] // exam 未启用
    switchRole.mockResolvedValueOnce(true)
    const wrapper = mount(RoleSwitcher, { props: { compact: true } })
    await wrapper.vm.handleSwitch(1)
    expect(push).toHaveBeenCalledWith('/')
  })

  // R7 F-001（MED security_design）：停留高权动态页（meta.permissions）→ 切到无该权限的身份 → 必须回退 /。
  // 修复前 /exams/:examId/ai-grading/:subjectId 精确表匹配不到 → 权限维度 fail-open（低权身份滞留高权页）。
  it('fail-closed: redirects to / when target identity lacks the dynamic route permission', async () => {
    route.path = '/exams/1/ai-grading/2'
    route.meta = { permissions: ['manage_grading'], moduleCode: 'grading' }
    mockAuth.currentRoleIndex = 1 // 当前 school_admin，切到 index 0 的 subject_teacher
    mockAuth.currentRole = { id: 'r1', role: 'subject_teacher', school_id: 's1', context: { name: 'Yucai' } }
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = ['grading'] // 模块已启用，但 subject_teacher 无 manage_grading
    switchRole.mockResolvedValueOnce(true)
    const wrapper = mount(RoleSwitcher, { props: { compact: true } })
    await wrapper.vm.handleSwitch(0)
    expect(push).toHaveBeenCalledWith('/')
  })
})
