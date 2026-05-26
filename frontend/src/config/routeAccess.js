import { hasPermission } from './permissions.js'
import { normalizeRole } from './roles.js'
import { OVERVIEW_NAV_ITEM, getRoleHeaderNav } from './roleEntryMatrix.js'

export const ROUTE_ACCESS_REQUIREMENTS = {
  '/exams': { permission: 'view_exams', moduleCode: 'exam' },
  '/exam-import': { permission: 'import_exams', moduleCode: 'exam' },
  '/marking': { permission: 'view_grading', moduleCode: 'grading' },
  '/grading/tasks': { permission: 'manage_grading', moduleCode: 'grading' },
  '/ai-grading': { permission: 'manage_grading', moduleCode: 'grading' },
  '/analytics/report': { permission: 'view_scores', moduleCode: 'study_analytics' },
  '/analytics/ai-report': { permission: 'view_scores', moduleCode: 'study_analytics' },
  '/homework': { permission: ['view_homework', 'manage_homework'], moduleCode: 'homework' },
  '/question-bank': { permission: 'view_question_bank', moduleCode: 'research' },
  '/knowledge-tree': { permission: 'view_knowledge_tree', moduleCode: 'research' },
  '/error-book': { permission: 'view_scores', moduleCode: 'research' },
  '/students': { permission: ['view_students', 'manage_scheduling'] },
  '/conduct': { permission: 'view_conduct', moduleCode: 'conduct' },
  '/conduct/settings': { permission: 'manage_conduct_rules', moduleCode: 'conduct' },
  '/joint-exams': { permission: 'view_joint_exam' },
  '/school-settings': { permission: 'manage_school_config' },
  '/academic/teaching-plans': { permission: 'manage_scheduling' },
  '/academic/timetable': { permission: 'manage_scheduling' },
  '/academic/semesters': { permission: 'manage_scheduling' },
  '/assignments': { permission: 'manage_scheduling' },
  '/selections': { permission: 'manage_scheduling' },
  '/teachers': { permission: 'manage_teachers' },
  '/schools': { permission: 'manage_schools' },
  '/admin/impersonate': { permission: 'manage_schools' },
  '/calendar': { moduleCode: 'calendar' },
}

export function getRouteAccessRequirement(route) {
  return ROUTE_ACCESS_REQUIREMENTS[route] || null
}

export function permissionMatches(role, permission) {
  if (!permission) return true
  const normalized = normalizeRole(role)
  const required = Array.isArray(permission) ? permission : [permission]
  return required.some(perm => hasPermission(normalized, perm))
}

export function moduleMatches(moduleCode, enabledModules = []) {
  if (!moduleCode) return true
  if (!enabledModules || enabledModules.length === 0) return true
  return enabledModules.includes(moduleCode)
}

export function canAccessRequirementForRole(role, requirement, enabledModules = []) {
  if (!requirement) return true
  return permissionMatches(role, requirement.permission) && moduleMatches(requirement.moduleCode, enabledModules)
}

export function canAccessRouteForRole(role, route, enabledModules = []) {
  return canAccessRequirementForRole(role, getRouteAccessRequirement(route), enabledModules)
}


export function getHeaderNavItems(role, enabledModules = []) {
  const normalized = normalizeRole(role)
  const configuredItems = getRoleHeaderNav(normalized)
  const visibleItems = configuredItems.filter(item => canAccessRouteForRole(normalized, item.route, enabledModules))
  return [OVERVIEW_NAV_ITEM, ...visibleItems]
}
