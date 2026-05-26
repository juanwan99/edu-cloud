import { describe, expect, it } from 'vitest'
import { WORKBENCH_PROFILE_KEYS } from '../config/workbenchProfiles.js'
import {
  ROLE_ENTRY_MATRIX,
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
})
