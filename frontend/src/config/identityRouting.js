import { normalizeRole } from './roles.js'

export const ROLE_PRIORITY = [
  'platform_admin',
  'district_admin',
  'school_admin',
  'principal',
  'academic_director',
  'grade_leader',
  'teaching_research_leader',
  'lesson_prep_leader',
  'homeroom_teacher',
  'subject_teacher',
]

export const ROLE_KEY_BY_LABEL = {
  校管理员: 'school_admin',
  教务主任: 'academic_director',
  年级组长: 'grade_leader',
  教研组长: 'teaching_research_leader',
  备课组长: 'lesson_prep_leader',
  班主任: 'homeroom_teacher',
  科任教师: 'subject_teacher',
}

export function chooseDefaultRoleIndex(roles = []) {
  const primaryIndex = roles.findIndex(role => role.is_primary)
  if (primaryIndex >= 0) return primaryIndex

  let bestIndex = 0
  let bestRank = Number.POSITIVE_INFINITY
  roles.forEach((role, index) => {
    const normalized = normalizeRole(role.role)
    const rank = ROLE_PRIORITY.indexOf(normalized)
    if (rank >= 0 && rank < bestRank) {
      bestRank = rank
      bestIndex = index
    }
  })
  return bestIndex
}

export function getRoleKeyByLabel(label) {
  return ROLE_KEY_BY_LABEL[label] || ''
}

export function toRoleQuery(roleKey) {
  return { role: roleKey }
}
