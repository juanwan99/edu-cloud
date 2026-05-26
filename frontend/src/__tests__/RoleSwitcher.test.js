import { describe, expect, it, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'fs'
import { resolve } from 'path'
import RoleSwitcher from '../components/shell/RoleSwitcher.vue'

const push = vi.hoisted(() => vi.fn())
const switchRole = vi.hoisted(() => vi.fn())
const route = vi.hoisted(() => ({ path: '/marking' }))
const source = readFileSync(resolve(process.cwd(), 'src/components/shell/RoleSwitcher.vue'), 'utf-8')

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => route,
}))

vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => ({
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
  }),
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
})
