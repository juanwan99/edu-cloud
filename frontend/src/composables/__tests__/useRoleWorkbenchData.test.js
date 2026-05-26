import { describe, expect, it } from 'vitest'
import {
  buildRoleWorkbenchSummary,
  normalizeRecentExams,
} from '../useRoleWorkbenchData.js'

describe('role workbench data adapter', () => {
  it('keeps empty state stable when optional API data is missing', () => {
    const summary = buildRoleWorkbenchSummary('principal', {
      dashboard: {},
      exams: [],
      markingAssignments: [],
      conductOverview: null,
    })

    expect(summary.kpiData).toEqual({})
    expect(summary.recentExams).toEqual([])
    expect(summary.todoItems).toEqual([])
  })

  it('normalizes recent exams without leaking raw backend shape into the page', () => {
    expect(normalizeRecentExams([
      { id: 'e1', name: '期中', status: 'grading', subjects: [{}, {}], created_at: '2026-05-01', grading_progress: 50 },
      { id: 'e2', name: '月考', status: 'published', subject_count: 3 },
      { id: 'e3', name: '联考', status: 'completed' },
      { id: 'e4', name: '多余考试', status: 'draft' },
    ])).toEqual([
      { id: 'e1', name: '期中', status: 'grading', subject_count: 2, created_at: '2026-05-01', grading_progress: 50 },
      { id: 'e2', name: '月考', status: 'published', subject_count: 3, created_at: undefined, grading_progress: null },
      { id: 'e3', name: '联考', status: 'completed', subject_count: null, created_at: undefined, grading_progress: null },
    ])
  })

  it('turns marking assignments into teacher todo items', () => {
    const summary = buildRoleWorkbenchSummary('subject_teacher', {
      dashboard: { pending_grading: 0 },
      exams: [],
      markingAssignments: [{ id: 'a1' }, { id: 'a2' }],
      conductOverview: null,
    })

    expect(summary.todoItems).toEqual([
      { label: '我的阅卷任务', count: 2, route: '/marking', color: 'yellow', tagType: 'warning' },
    ])
  })

  it('keeps grading dispatch todos away from roles whose entry policy hides dispatch', () => {
    const summary = buildRoleWorkbenchSummary('homeroom_teacher', {
      gradingTasks: [{ status: 'processing' }],
      markingAssignments: [{ id: 'a1' }],
    })

    expect(summary.todoItems).toEqual([
      { label: '我的阅卷任务', count: 1, route: '/marking', color: 'yellow', tagType: 'warning' },
    ])
  })

  it('keeps school admin todos on operational routes', () => {
    const summary = buildRoleWorkbenchSummary('school_admin', {
      exams: [{ status: 'grading' }, { status: 'completed' }],
      gradingTasks: [{ status: 'processing' }, { status: 'done' }],
      homeworkTasks: [{ status: 'active' }],
    })

    expect(summary.todoItems).toEqual([
      { label: '1 个阅卷任务进行中', count: 1, route: '/grading/tasks', color: 'coral', tagType: 'warning' },
      { label: '1 场考试待阅卷', count: 1, route: '/exams', color: 'yellow', tagType: 'info' },
    ])
  })
})
