import { describe, expect, it } from 'vitest'
import { WORKBENCH_PROFILE_KEYS } from '../config/workbenchProfiles.js'
import {
  ROLE_ENTRY_MATRIX,
  buildRoleActionPanel,
  buildRolePriorityActions,
  getRoleDashboardKpis,
  getRoleEntryPolicy,
  getRoleHeaderNav,
  getRoleSidebarPolicy,
} from '../config/roleEntryMatrix.js'
import { getRouteAccessRequirement } from '../config/routeAccess.js'

describe('role entry matrix', () => {
  it('covers every workbench profile role', () => {
    for (const role of WORKBENCH_PROFILE_KEYS) {
      expect(ROLE_ENTRY_MATRIX[role], role).toBeTruthy()
    }
  })

  it('keeps principal separate from school admin', () => {
    expect(getRoleEntryPolicy('principal').primaryRoutes).toContain('/analytics/report')
    expect(getRoleEntryPolicy('principal').hiddenRoutes).toContain('/school-settings')
    expect(getRoleEntryPolicy('school_admin').primaryRoutes).toContain('/school-settings')
  })

  it('keeps subject teacher away from grading dispatch primary entries', () => {
    const policy = getRoleEntryPolicy('subject_teacher')
    expect(policy.primaryRoutes).toContain('/marking')
    expect(policy.primaryRoutes).not.toContain('/grading/tasks')
    expect(policy.hiddenRoutes).toContain('/grading/tasks')
  })

  it('keeps lesson prep leader in subject exam and grading control flow', () => {
    const policy = getRoleEntryPolicy('lesson_prep_leader')
    expect(policy.primaryRoutes).toEqual([
      '/exams',
      '/grading/tasks',
      '/ai-grading',
      '/analytics/report',
    ])
  })

  it('only references known routes or explicitly unguarded overview routes', () => {
    for (const policy of Object.values(ROLE_ENTRY_MATRIX)) {
      for (const route of [...policy.primaryRoutes, ...policy.secondaryRoutes]) {
        expect(route === '/' || getRouteAccessRequirement(route), route).toBeTruthy()
      }
    }
  })

  it('derives header and sidebar policy from the same source', () => {
    expect(getRoleHeaderNav('school_admin').map(item => item.label)).toEqual([
      '学校配置',
      '教师与职务',
      '组织关系',
      '数据导入',
      '数据报告',
    ])
    expect(getRoleSidebarPolicy('principal').groups).toEqual(['exam', 'student', 'school'])
  })

  it('derives dashboard kpis from role entry matrix instead of legacy dashboard widgets', () => {
    expect(getRoleDashboardKpis('principal').map(kpi => kpi.label)).toEqual([
      '考试结果',
      '覆盖学生',
      '质量风险',
      '覆盖班级',
    ])
    expect(getRoleDashboardKpis('platform_admin')).toEqual(getRoleDashboardKpis('school_admin'))
    expect(getRoleDashboardKpis('parent')).toEqual([])
  })

  it('builds school admin priorities from live dashboard and exam data', () => {
    const actions = buildRolePriorityActions('school_admin', {
      summary: {
        total_staff: 12,
        total_students: 486,
        total_exams: 7,
        pending_grading: 3,
      },
      recentExams: [
        { status: 'grading' },
        { status: 'completed' },
      ],
      todoItems: [{ count: 2 }],
    })

    expect(actions.map(action => action.route)).toEqual([
      '/school-settings',
      '/assignments',
      '/exams',
      '/students',
    ])
    expect(actions[0].tag).toBe('待核对')
    expect(actions[1].tag).toBe('12 人')
    expect(actions[2].tag).toBe('3 项')
    expect(actions[3].tag).toBe('486 人')
    expect(actions.map(action => action.route)).not.toContain('/marking')
  })

  it('uses profile priorities for principal instead of school admin operations', () => {
    const actions = buildRolePriorityActions('principal', {
      profile: {
        priorities: [
          { title: '查看学校质量风险', desc: '先看总览', meta: '5 项', route: '/analytics/report', tone: 'yellow' },
          { title: '处理审批和通知事项', desc: '集中处理审批', meta: '4 项', route: '/analytics/ai-report', tone: 'orange' },
        ],
      },
    })

    expect(actions.map(action => action.route)).toEqual(['/analytics/report', '/analytics/ai-report'])
    expect(actions[0].tag).toBe('5 项')
    expect(actions[1].tagType).toBe('warning')
    expect(actions.map(action => action.route)).not.toContain('/school-settings')
  })

  it('builds a dedicated principal governance panel', () => {
    const panel = buildRoleActionPanel('principal', {
      summary: { total_students: 486, total_exams: 7, pending_grading: 3 },
      recentExams: [{ status: 'draft' }, { status: 'published' }],
    })

    expect(panel.title).toBe('学校治理中心')
    expect(panel.items.map(item => item.route)).toEqual([
      '/analytics/report',
      '/exams',
      '/analytics/ai-report',
      '/joint-exams',
    ])
    expect(panel.items.map(item => item.route)).not.toContain('/school-settings')
  })

  it('builds governance panel items with operational metrics for school admin', () => {
    const panel = buildRoleActionPanel('school_admin', {
      summary: {
        total_staff: 12,
        total_students: 486,
        total_exams: 7,
        pending_grading: 3,
      },
      recentExams: [{ status: 'grading' }],
    })

    expect(panel.title).toBe('运行治理中心')
    expect(panel.items.map(item => item.route)).toEqual([
      '/school-settings',
      '/assignments',
      '/exams',
      '/students',
    ])
    expect(panel.items[1].desc).toContain('12 人')
    expect(panel.items[2].desc).toContain('3 项')
    expect(panel.items[3].desc).toContain('486 人')
  })

  it('builds a teaching operations panel for academic director', () => {
    const panel = buildRoleActionPanel('academic_director', {
      summary: { total_staff: 12, total_exams: 7, pending_grading: 3 },
      recentExams: [{ status: 'grading' }],
    })

    expect(panel.title).toBe('教学运行中心')
    expect(panel.sub).toContain('课表')
    expect(panel.items.map(item => item.route)).toEqual([
      '/assignments',
      '/exams',
      '/grading/tasks',
      '/analytics/report',
    ])
    expect(panel.items.map(item => item.route)).not.toContain('/marking')
  })

  it('builds a grade coordination panel for grade leader', () => {
    const panel = buildRoleActionPanel('grade_leader', {
      summary: { total_students: 486, total_exams: 7, pending_grading: 3 },
      recentExams: [{ status: 'draft' }, { status: 'published' }],
    })

    expect(panel.title).toBe('年级协同中心')
    expect(panel.items.map(item => item.route)).toEqual([
      '/analytics/report',
      '/students',
      '/conduct',
      '/joint-exams',
    ])
    expect(panel.items[1].desc).toContain('486 人')
  })

  it('builds a class follow-up panel for homeroom teacher', () => {
    const panel = buildRoleActionPanel('homeroom_teacher', {
      summary: { total_students: 486, total_exams: 7 },
      todoItems: [{ count: 2 }, { count: 1 }],
    })

    expect(panel.title).toBe('班级跟进中心')
    expect(panel.items.map(item => item.route)).toEqual([
      '/students',
      '/conduct',
      '/analytics/report',
      '/homework',
    ])
    expect(panel.items[0].desc).toContain('486 人')
  })

  it('lets subject teacher use the generic report action panel', () => {
    expect(buildRoleActionPanel('subject_teacher')).toBeNull()
  })
})
