import { describe, expect, it } from 'vitest'
import { getRouteAccessRequirement, canAccessRouteForRole, getHeaderNavItems } from '../config/routeAccess.js'

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
      permission: 'manage_schools',
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

  it('treats empty enabledModules as no module filter', () => {
    expect(canAccessRouteForRole('school_admin', '/grading/tasks', [])).toBe(true)
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
