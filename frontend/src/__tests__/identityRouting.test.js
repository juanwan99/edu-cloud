import { describe, expect, it } from 'vitest'
import {
  chooseDefaultRoleIndex,
  findRoleIndexByKey,
  getRoleKeyByLabel,
  routeBelongsToRoleEntry,
  toRoleQuery,
} from '../config/identityRouting.js'
import { getRoleEntryPolicy } from '../config/roleEntryMatrix.js'

const roles = [
  { id: 'r1', role: 'subject_teacher', is_primary: false },
  { id: 'r2', role: 'grade_leader', is_primary: true },
  { id: 'r3', role: 'homeroom_teacher', is_primary: false },
]

describe('identity routing', () => {
  it('prefers primary role', () => {
    expect(chooseDefaultRoleIndex(roles)).toBe(1)
  })

  it('falls back to highest priority when no primary role exists', () => {
    expect(chooseDefaultRoleIndex([
      { role: 'subject_teacher' },
      { role: 'homeroom_teacher' },
    ])).toBe(1)
  })

  it('prefers school admin over teacher identities when no primary role exists', () => {
    expect(chooseDefaultRoleIndex([
      { role: 'subject_teacher' },
      { role: 'school_admin' },
      { role: 'academic_director' },
    ])).toBe(1)
  })

  it('prefers broader admin roles over school staff identities when no primary role exists', () => {
    expect(chooseDefaultRoleIndex([
      { role: 'subject_teacher' },
      { role: 'principal' },
      { role: 'academic_director' },
    ])).toBe(1)
  })

  it('falls back to first role when no known role exists', () => {
    expect(chooseDefaultRoleIndex([{ role: 'unknown_role' }])).toBe(0)
  })

  it('maps Chinese labels to role keys', () => {
    expect(getRoleKeyByLabel('校管理员')).toBe('school_admin')
    expect(getRoleKeyByLabel('班主任')).toBe('homeroom_teacher')
    expect(getRoleKeyByLabel('科任教师')).toBe('subject_teacher')
  })

  it('generates route query for a target role', () => {
    expect(toRoleQuery('grade_leader')).toEqual({ role: 'grade_leader' })
  })

  it('finds a role index by normalized role key', () => {
    expect(findRoleIndexByKey([
      { role: 'teacher' },
      { role: 'grade_leader' },
    ], 'subject_teacher')).toBe(0)
    expect(findRoleIndexByKey(roles, 'principal')).toBe(-1)
  })

  it('checks whether a route belongs to the target role entry policy', () => {
    expect(routeBelongsToRoleEntry(
      '/analytics/report/student/42',
      'principal',
      getRoleEntryPolicy('principal'),
    )).toBe(true)
    expect(routeBelongsToRoleEntry(
      '/school-settings',
      'principal',
      getRoleEntryPolicy('principal'),
    )).toBe(false)
    expect(routeBelongsToRoleEntry(
      '/grading/tasks',
      'subject_teacher',
      getRoleEntryPolicy('subject_teacher'),
    )).toBe(false)
  })
})
