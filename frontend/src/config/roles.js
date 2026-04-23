export const CANONICAL_ROLES = [
  'platform_admin', 'district_admin', 'principal', 'academic_director',
  'teaching_research_leader', 'grade_leader', 'lesson_prep_leader',
  'homeroom_teacher', 'subject_teacher', 'parent',
]

export const LEGACY_ALIAS_MAP = {
  admin: 'platform_admin',
  teacher: 'subject_teacher',
  head_teacher: 'homeroom_teacher',
}

export function normalizeRole(role) {
  return LEGACY_ALIAS_MAP[role] || role
}

export const SCHOOL_ADMIN_ROLES = ['platform_admin', 'district_admin', 'principal', 'academic_director']
export const TEACHING_LEADER_ROLES = ['teaching_research_leader', 'lesson_prep_leader']
export const EXAM_ROLES = [...SCHOOL_ADMIN_ROLES, ...TEACHING_LEADER_ROLES, 'grade_leader', 'homeroom_teacher', 'subject_teacher']
export const GRADING_DISPATCH_ROLES = [...SCHOOL_ADMIN_ROLES, ...TEACHING_LEADER_ROLES, 'grade_leader', 'homeroom_teacher', 'subject_teacher']
export const MARKING_ROLES = [...SCHOOL_ADMIN_ROLES, 'homeroom_teacher', 'subject_teacher']

export const ROLE_LABELS = {
  platform_admin: '平台管理员', district_admin: '区管理员', principal: '校长',
  academic_director: '教务主任', teaching_research_leader: '教研组长',
  grade_leader: '年级组长', lesson_prep_leader: '备课组长',
  homeroom_teacher: '班主任', subject_teacher: '科任教师', parent: '家长',
}
