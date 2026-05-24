import { describe, it, expect } from 'vitest'
import { ROLE_PERMISSIONS, hasPermission } from '@/config/permissions'

describe('T1 — lesson_prep_leader conduct 权限回收', () => {
  it('lesson_prep_leader 不含 view_conduct', () => {
    expect(hasPermission('lesson_prep_leader', 'view_conduct')).toBe(false)
  })

  it('lesson_prep_leader 不含 manage_conduct', () => {
    expect(hasPermission('lesson_prep_leader', 'manage_conduct')).toBe(false)
  })

  it('subject_teacher 仍含 view_conduct / manage_conduct', () => {
    expect(hasPermission('subject_teacher', 'view_conduct')).toBe(true)
    expect(hasPermission('subject_teacher', 'manage_conduct')).toBe(true)
  })

  it('homeroom_teacher 仍含完整 conduct 5 权限', () => {
    const expected = [
      'view_conduct', 'manage_conduct',
      'manage_conduct_rules', 'manage_conduct_parents', 'export_conduct',
    ]
    for (const perm of expected) {
      expect(hasPermission('homeroom_teacher', perm)).toBe(true)
    }
  })

  it('lesson_prep_leader 其他教师基线权限保留', () => {
    expect(hasPermission('lesson_prep_leader', 'view_students')).toBe(true)
    expect(hasPermission('lesson_prep_leader', 'view_homework')).toBe(true)
    expect(hasPermission('lesson_prep_leader', 'manage_homework')).toBe(true)
    expect(hasPermission('lesson_prep_leader', 'use_ai_chat')).toBe(true)
  })
})


describe('教师管理权限镜像', () => {
  it('前端镜像包含后端教师管理权限 manage_teachers', () => {
    expect(hasPermission('school_admin', 'manage_teachers')).toBe(true)
    expect(hasPermission('principal', 'manage_teachers')).toBe(true)
    expect(hasPermission('academic_director', 'manage_teachers')).toBe(true)
  })

  it('普通教师不具备教师 CRUD 权限', () => {
    expect(hasPermission('subject_teacher', 'manage_teachers')).toBe(false)
    expect(hasPermission('homeroom_teacher', 'manage_teachers')).toBe(false)
  })
})
