import { describe, expect, it } from 'vitest'
import { CANONICAL_ROLES } from '../config/roles.js'
import {
  WORKBENCH_PROFILES,
  WORKBENCH_PROFILE_KEYS,
  getWorkbenchProfile,
} from '../config/workbenchProfiles.js'

const WORKBENCH_ROLES = [
  'school_admin',
  'subject_teacher',
  'homeroom_teacher',
  'lesson_prep_leader',
  'grade_leader',
  'teaching_research_leader',
  'academic_director',
]

describe('workbench profiles', () => {
  it('covers all workbench roles', () => {
    expect(WORKBENCH_PROFILE_KEYS).toEqual(WORKBENCH_ROLES)
    for (const role of WORKBENCH_ROLES) {
      expect(WORKBENCH_PROFILES[role], role).toBeTruthy()
      expect(CANONICAL_ROLES).toContain(role)
    }
  })

  it('uses a school admin profile instead of falling back to subject teacher', () => {
    const profile = getWorkbenchProfile('school_admin')
    expect(profile.key).toBe('school_admin')
    expect(profile.label).toBe('校管理员')
    expect(profile.title).toContain('学校基础数据')
    expect(profile.flow.map(stage => stage.route)).toContain('/school-settings')
    expect(profile.flow.map(stage => stage.route)).not.toContain('/marking')
  })

  it('maps broader admin roles to the school admin workbench instead of subject teacher', () => {
    expect(getWorkbenchProfile('platform_admin').key).toBe('school_admin')
    expect(getWorkbenchProfile('district_admin').key).toBe('school_admin')
    expect(getWorkbenchProfile('principal').key).toBe('school_admin')
  })

  it('returns subject teacher profile as fallback', () => {
    expect(getWorkbenchProfile('unknown_role').key).toBe('subject_teacher')
  })

  it('defines boundaries, actions, priorities, flow, modules, and overlap for each profile', () => {
    for (const role of WORKBENCH_ROLES) {
      const profile = getWorkbenchProfile(role)
      expect(profile.label).toBeTruthy()
      expect(profile.owns).toBeTruthy()
      expect(profile.hides).toBeTruthy()
      expect(profile.primaryAction.route).toMatch(/^\//)
      expect(profile.secondaryAction.route).toMatch(/^\//)
      expect(profile.kpis.length).toBeGreaterThan(0)
      expect(profile.priorities.length).toBeGreaterThan(0)
      expect(profile.flow.length).toBeGreaterThan(0)
      expect(profile.modules.length).toBeGreaterThan(0)
      expect(profile.overlap.other.length).toBeGreaterThan(0)
    }
  })
})
