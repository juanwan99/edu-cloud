import { describe, expect, it, vi, beforeEach, beforeAll } from 'vitest'
import { mount } from '@vue/test-utils'

const mockAuth = vi.hoisted(() => ({
  currentRole: { role: 'school_admin' },
  enabledModules: ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'research', 'conduct'],
  modulesLoaded: true,
  checkPermission: vi.fn(),
}))

const permissionByRole = {
  school_admin: ['manage_school_config', 'manage_teachers', 'manage_exams', 'view_exams', 'view_scores', 'manage_grading', 'view_grading'],
  subject_teacher: ['view_exams', 'view_scores', 'view_grading', 'view_homework', 'manage_homework'],
}

vi.mock('../stores/auth.js', () => ({
  useAuthStore: () => mockAuth,
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ path: '/' }),
}))

vi.mock('../components/shell/SchoolContext.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('../components/shell/NotificationBell.vue', () => ({
  default: { template: '<button type="button" />' },
}))

vi.mock('../components/shell/RoleSwitcher.vue', () => ({
  default: { template: '<button type="button" />' },
}))

let AppHeader

beforeAll(async () => {
  AppHeader = (await import('../components/shell/AppHeader.vue')).default
})

function mountHeader() {
  return mount(AppHeader, {
    global: {
      mocks: { $router: { push: vi.fn() } },
      stubs: {
        SchoolContext: true,
        NotificationBell: true,
        RoleSwitcher: true,
        RouterLink: {
          props: ['to'],
          template: '<a class="router-link"><slot /></a>',
        },
      },
    },
  })
}

describe('AppHeader role navigation', () => {
  beforeEach(() => {
    mockAuth.enabledModules = ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'research', 'conduct']
    mockAuth.modulesLoaded = true
    mockAuth.currentRole = { role: 'school_admin' }
    mockAuth.checkPermission = vi.fn(perm => permissionByRole[mockAuth.currentRole.role]?.includes(perm) || false)
  })

  it('renders school administrator operation shortcuts instead of personal teaching actions', () => {
    const wrapper = mountHeader()
    const text = wrapper.find('.app-header__nav').text()

    expect(text).toContain('学校配置')
    expect(text).toContain('教师与职务')
    expect(text).toContain('数据导入')
    expect(text).toContain('数据报告')
    expect(text).not.toContain('阅卷调度')
    expect(text).not.toContain('我的阅卷')
  })

  it('renders subject teacher personal workflow shortcuts', () => {
    mockAuth.currentRole = { role: 'subject_teacher' }
    mockAuth.enabledModules = ['exam', 'grading', 'study_analytics', 'homework']
    mockAuth.checkPermission = vi.fn(perm => permissionByRole[mockAuth.currentRole.role]?.includes(perm) || false)

    const wrapper = mountHeader()
    const text = wrapper.find('.app-header__nav').text()

    expect(text).toContain('相关考试')
    expect(text).toContain('我的阅卷')
    expect(text).toContain('成绩分析')
    expect(text).toContain('作业管理')
    expect(text).not.toContain('阅卷调度')
    expect(text).not.toContain('教师与职务')
  })
})

// Phase 0.7A（R5 F-001 MED security_design）：移除 moduleFallbacks 放行后，学校用户在模块
// 未加载/加载失败/空列表时，header 模块导航 fail-closed 隐藏（概览始终保留）；加载并启用后恢复。
describe('AppHeader module gating fail-closed (Phase 0.7A)', () => {
  beforeEach(() => {
    mockAuth.currentRole = { role: 'subject_teacher', school_id: 'school-1' }
    mockAuth.checkPermission = vi.fn(perm => permissionByRole.subject_teacher?.includes(perm) || false)
  })

  it('fail-closed: hides module nav when modules loaded but empty (load failed / no module)', () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = []
    const text = mountHeader().find('.app-header__nav').text()
    expect(text).not.toContain('相关考试')
    expect(text).not.toContain('我的阅卷')
    expect(text).not.toContain('成绩分析')
    expect(text).not.toContain('作业管理')
    expect(text).toContain('概览')
  })

  it('fail-closed: hides module nav when modules not yet loaded (no fallback放行)', () => {
    mockAuth.modulesLoaded = false
    mockAuth.enabledModules = []
    const text = mountHeader().find('.app-header__nav').text()
    expect(text).not.toContain('相关考试')
    expect(text).not.toContain('我的阅卷')
    expect(text).toContain('概览')
  })

  it('shows module nav once modules are loaded and enabled', () => {
    mockAuth.modulesLoaded = true
    mockAuth.enabledModules = ['exam', 'grading', 'study_analytics', 'homework']
    const text = mountHeader().find('.app-header__nav').text()
    expect(text).toContain('相关考试')
    expect(text).toContain('我的阅卷')
  })
})
