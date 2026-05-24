import { describe, expect, it } from 'vitest'
import {
  buildAdminPriorityActions,
  buildRoleActionPanel,
} from '../config/roleWorkbenches.js'

describe('role workbench runtime mapping', () => {
  it('builds school admin priorities from live dashboard and exam data', () => {
    const actions = buildAdminPriorityActions({
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

  it('uses recent exam count when no pending grading is available', () => {
    const actions = buildAdminPriorityActions({
      summary: { total_staff: 0, total_students: 0, total_exams: 5 },
      recentExams: [{ status: 'draft' }, { status: 'published' }],
      todoItems: [],
    })

    expect(actions[2].tag).toBe('2 场')
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
      '/academic/timetable',
      '/exams',
      '/grading/tasks',
      '/assignments',
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
