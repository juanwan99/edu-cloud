import { describe, expect, it } from 'vitest'
import {
  getRouteAccessRequirement,
  canAccessRouteForRole,
  canAccessMatchedRoute,
  getHeaderNavItems,
  createModuleGate,
  moduleGateFromAuth,
  moduleMatches,
} from '../config/routeAccess.js'

describe('route access requirements', () => {
  it('guards school settings with school config permission', () => {
    expect(getRouteAccessRequirement('/school-settings')).toEqual({
      permission: 'manage_school_config',
    })
  })

  it('guards grading dispatch separately from personal marking', () => {
    expect(getRouteAccessRequirement('/grading/tasks')).toEqual({
      permission: 'manage_grading',
      moduleCode: 'grading',
    })
    expect(getRouteAccessRequirement('/marking')).toEqual({
      permission: 'view_grading',
      moduleCode: 'grading',
    })
  })

  it('covers operational routes used by router guards', () => {
    expect(getRouteAccessRequirement('/conduct/settings')).toEqual({
      permission: 'manage_conduct_rules',
      moduleCode: 'conduct',
    })
    expect(getRouteAccessRequirement('/selections')).toEqual({
      permission: 'manage_scheduling',
    })
    expect(getRouteAccessRequirement('/schools')).toEqual({
      permission: 'manage_schools',
    })
    expect(getRouteAccessRequirement('/admin/impersonate')).toEqual({
      permission: 'impersonate_roles',
    })
  })

  it('allows school admin into school settings but not parent', () => {
    expect(canAccessRouteForRole('school_admin', '/school-settings', [])).toBe(true)
    expect(canAccessRouteForRole('parent', '/school-settings', [])).toBe(false)
  })

  it('requires enabled module when module list is loaded', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', ['exam'])).toBe(false)
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', ['grading'])).toBe(true)
  })

  // Phase 0.7A（R5 F-001 MED security_design）：翻转旧 fail-open 契约。空列表 = 学校无模块/加载
  // 失败 → 学校用户对模块 route 一律 fail-closed 拦截，不再「空=不过滤」放行。与 authGuard 一致。
  it('fail-closed: empty enabledModules blocks module route for school user (legacy array form)', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', [])).toBe(false)
  })
})

// Phase 0.7A 门控上下文：显式区分 4 态（未加载 / 加载失败 / 学校无模块 / admin 豁免），
// 取代「空数组同时表达 4 态」。fail-closed 语义与 authGuard(router/index.js) 数学等价。
describe('module gate fail-closed semantics (Phase 0.7A F-001)', () => {
  const schoolGate = (enabledModules, modulesLoaded = true) =>
    createModuleGate({ schoolScoped: true, modulesLoaded, enabledModules })

  it('school user with module loaded + enabled is allowed', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', schoolGate(['grading']))).toBe(true)
  })

  it('school user with module loaded but NOT enabled is blocked', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', schoolGate(['exam']))).toBe(false)
  })

  it('school user with empty enabledModules (no module / load failed) is blocked', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', schoolGate([]))).toBe(false)
  })

  it('school user with modules NOT yet loaded is blocked (fail-closed during load window)', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', schoolGate([], false))).toBe(false)
  })

  it('admin / no school_id is exempt even with empty modules', () => {
    const adminGate = createModuleGate({ schoolScoped: false, modulesLoaded: false, enabledModules: [] })
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', adminGate)).toBe(true)
  })

  it('non-module route is unaffected by gate (permission only)', () => {
    expect(canAccessRouteForRole('school_admin', '/school-settings', schoolGate([]))).toBe(true)
    expect(canAccessRouteForRole('parent', '/school-settings', schoolGate(['exam']))).toBe(false)
  })

  it('moduleMatches: null moduleCode always true; exempt always true; school fail-closed otherwise', () => {
    expect(moduleMatches(null, schoolGate([]))).toBe(true)
    expect(moduleMatches('grading', createModuleGate({ schoolScoped: false }))).toBe(true)
    expect(moduleMatches('grading', schoolGate(['grading']))).toBe(true)
    expect(moduleMatches('grading', schoolGate([]))).toBe(false)
    expect(moduleMatches('grading', schoolGate(['grading'], false))).toBe(false)
  })

  it('moduleGateFromAuth mirrors authGuard: school_id present → scoped; absent → exempt', () => {
    const schoolAuth = { currentRole: { school_id: 1 }, modulesLoaded: true, enabledModules: ['grading'] }
    expect(moduleGateFromAuth(schoolAuth)).toEqual({ exempt: false, modulesLoaded: true, enabledModules: ['grading'] })

    const adminAuth = { currentRole: { role: 'platform_admin' }, modulesLoaded: false, enabledModules: [] }
    expect(moduleGateFromAuth(adminAuth).exempt).toBe(true)

    const loadFailedAuth = { currentRole: { school_id: 1 }, modulesLoaded: true, enabledModules: [] }
    expect(moduleMatches('grading', moduleGateFromAuth(loadFailedAuth))).toBe(false)
  })
})

// canAccessMatchedRoute：对「当前已匹配路由」综合判定，覆盖静态精确表 ∪ 动态 route.meta（权限+模块），
// 与 authGuard 同源。动态子路由（/exams/:id、/exams/:examId/ai-grading/:subjectId）精确表匹配不到，
// 靠 meta 兜底——堵 RoleSwitcher 切换路径上的 perm/module fail-open（R6/R7 F-001）。
describe('canAccessMatchedRoute: static∪dynamic perm+module (Phase 0.7A R6/R7 F-001)', () => {
  const schoolGate = (mods, loaded = true) =>
    createModuleGate({ schoolScoped: true, modulesLoaded: loaded, enabledModules: mods })
  const exemptGate = createModuleGate({ schoolScoped: false })

  it('static route gates by table permission + module', () => {
    expect(canAccessMatchedRoute('homeroom_teacher', '/grading/tasks', {}, schoolGate(['grading']))).toBe(true)
    expect(canAccessMatchedRoute('homeroom_teacher', '/grading/tasks', {}, schoolGate([]))).toBe(false) // 模块未启用
    expect(canAccessMatchedRoute('subject_teacher', '/grading/tasks', {}, schoolGate(['grading']))).toBe(false) // 无 manage_grading
  })

  it('dynamic route gates module via meta.moduleCode (school fail-closed; exempt bypass)', () => {
    const meta = { moduleCode: 'exam' }
    expect(canAccessMatchedRoute('school_admin', '/exams/123', meta, schoolGate(['grading']))).toBe(false) // exam 未启用
    expect(canAccessMatchedRoute('school_admin', '/exams/123', meta, schoolGate(['exam']))).toBe(true)
    expect(canAccessMatchedRoute('school_admin', '/exams/123', meta, exemptGate)).toBe(true) // admin 模块豁免
  })

  it('dynamic route gates permission via meta.permissions (NOT bypassed by module exemption)', () => {
    const meta = { permissions: ['manage_grading'], moduleCode: 'grading' }
    expect(canAccessMatchedRoute('homeroom_teacher', '/exams/1/ai-grading/2', meta, schoolGate(['grading']))).toBe(true)
    expect(canAccessMatchedRoute('subject_teacher', '/exams/1/ai-grading/2', meta, schoolGate(['grading']))).toBe(false) // 无 manage_grading
    expect(canAccessMatchedRoute('homeroom_teacher', '/exams/1/ai-grading/2', meta, schoolGate([]))).toBe(false) // 模块未启用
    expect(canAccessMatchedRoute('subject_teacher', '/exams/1/ai-grading/2', meta, exemptGate)).toBe(false) // 模块豁免不豁免权限
  })
})


describe('route access phase2 alignment', () => {
  it('guards teacher management with the backend teacher CRUD permission', () => {
    expect(getRouteAccessRequirement('/teachers')).toEqual({
      permission: 'manage_teachers',
    })
    expect(canAccessRouteForRole('academic_director', '/teachers', [])).toBe(true)
    expect(canAccessRouteForRole('grade_leader', '/teachers', [])).toBe(false)
  })

  it('assigns research module ownership to knowledge and bank routes', () => {
    expect(getRouteAccessRequirement('/question-bank')).toEqual({
      permission: 'view_question_bank',
      moduleCode: 'research',
    })
    expect(getRouteAccessRequirement('/knowledge-tree')).toEqual({
      permission: 'view_knowledge_tree',
      moduleCode: 'research',
    })
    expect(getRouteAccessRequirement('/error-book')).toEqual({
      permission: 'view_scores',
      moduleCode: 'research',
    })
  })

  it('blocks research entries when research module is disabled', () => {
    expect(canAccessRouteForRole('subject_teacher', '/question-bank', ['exam', 'grading'])).toBe(false)
    expect(canAccessRouteForRole('subject_teacher', '/question-bank', ['research'])).toBe(true)
  })
})


const fullModules = ['exam', 'grading', 'calendar', 'homework', 'study_analytics', 'research', 'conduct']
const headerLabelsFor = (role, modules = fullModules) => getHeaderNavItems(role, modules).map(item => item.label)
const headerRoutesFor = (role, modules = fullModules) => getHeaderNavItems(role, modules).map(item => item.route)

describe('header navigation registry', () => {
  it('builds school admin header from school operation priorities', () => {
    expect(headerLabelsFor('school_admin')).toEqual(['概览', '学校配置', '教师与职务', '组织关系', '数据导入', '数据报告'])
    expect(headerRoutesFor('school_admin')).not.toContain('/marking')
    expect(headerRoutesFor('school_admin')).not.toContain('/grading/tasks')
  })

  it('builds principal header from overview and approval priorities', () => {
    expect(headerLabelsFor('principal')).toEqual(['概览', '质量总览', '考试结果', '审批查看', '年级德育', '联考复盘'])
    expect(headerRoutesFor('principal')).not.toContain('/school-settings')
    expect(headerRoutesFor('principal')).not.toContain('/teachers')
    expect(headerRoutesFor('principal')).not.toContain('/assignments')
  })

  it('builds subject teacher header from personal teaching work', () => {
    const modules = ['exam', 'grading', 'study_analytics', 'homework']
    expect(headerLabelsFor('subject_teacher', modules)).toEqual(['概览', '相关考试', '我的阅卷', '成绩分析', '作业管理'])
    expect(headerRoutesFor('subject_teacher', modules)).not.toContain('/grading/tasks')
    expect(headerRoutesFor('subject_teacher', modules)).not.toContain('/teachers')
  })

  it('builds lesson prep leader header from subject collaboration work', () => {
    expect(headerLabelsFor('lesson_prep_leader')).toEqual(['概览', '学科考试', '阅卷分工', '学科报告', '题库沉淀'])
    expect(headerRoutesFor('lesson_prep_leader')).not.toContain('/students')
    expect(headerRoutesFor('lesson_prep_leader')).not.toContain('/teachers')
  })

  it('hides header entries whose route module is disabled', () => {
    const routes = headerRoutesFor('teaching_research_leader', ['exam', 'study_analytics'])
    expect(routes).not.toContain('/knowledge-tree')
    expect(routes).not.toContain('/question-bank')
    expect(routes).toContain('/analytics/report')
    expect(routes).toContain('/exams')
  })
})
