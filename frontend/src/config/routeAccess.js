import { hasPermission } from './permissions.js'
import { normalizeRole } from './roles.js'

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
  '/joint-exams': { permission: 'view_joint_exam' },
  '/school-settings': { permission: 'manage_school_config' },
  '/academic/teaching-plans': { permission: 'manage_scheduling' },
  '/academic/timetable': { permission: 'manage_scheduling' },
  '/academic/semesters': { permission: 'manage_scheduling' },
  '/assignments': { permission: 'manage_scheduling' },
  '/teachers': { permission: 'manage_teachers' },
  '/calendar': { moduleCode: 'calendar' },
}

const SCHOOL_ADMIN_HEADER = [
  { label: '学校配置', route: '/school-settings', match: '/school-settings' },
  { label: '教师与职务', route: '/teachers', match: '/teachers' },
  { label: '组织关系', route: '/assignments', match: '/assignments' },
  { label: '数据导入', route: '/exam-import', match: '/exam-import' },
  { label: '数据报告', route: '/analytics/report', match: '/analytics' },
]

const PRINCIPAL_HEADER = [
  { label: '质量总览', route: '/analytics/report', match: '/analytics' },
  { label: '考试结果', route: '/exams', match: '/exams' },
  { label: '审批查看', route: '/analytics/ai-report', match: '/analytics/ai-report' },
  { label: '年级德育', route: '/conduct', match: '/conduct' },
  { label: '联考复盘', route: '/joint-exams', match: '/joint-exams' },
]

export const HEADER_NAV_BY_ROLE = {
  platform_admin: SCHOOL_ADMIN_HEADER,
  district_admin: SCHOOL_ADMIN_HEADER,
  school_admin: SCHOOL_ADMIN_HEADER,
  principal: PRINCIPAL_HEADER,
  academic_director: [
    { label: '教学运行', route: '/assignments', match: '/assignments' },
    { label: '考试管理', route: '/exams', match: '/exams' },
    { label: '阅卷调度', route: '/grading/tasks', match: '/grading' },
    { label: '数据报告', route: '/analytics/report', match: '/analytics' },
  ],
  grade_leader: [
    { label: '年级学生', route: '/students', match: '/students' },
    { label: '年级考试', route: '/exams', match: '/exams' },
    { label: '数据报告', route: '/analytics/report', match: '/analytics' },
    { label: '德育协同', route: '/conduct', match: '/conduct' },
  ],
  teaching_research_leader: [
    { label: '知识图谱', route: '/knowledge-tree', match: '/knowledge-tree' },
    { label: '题库建设', route: '/question-bank', match: '/question-bank' },
    { label: '学科趋势', route: '/analytics/report', match: '/analytics' },
    { label: '考试证据', route: '/exams', match: '/exams' },
  ],
  lesson_prep_leader: [
    { label: '学科考试', route: '/exams', match: '/exams' },
    { label: '阅卷分工', route: '/grading/tasks', match: '/grading' },
    { label: '学科报告', route: '/analytics/report', match: '/analytics' },
    { label: '题库沉淀', route: '/question-bank', match: '/question-bank' },
  ],
  homeroom_teacher: [
    { label: '班级学生', route: '/students', match: '/students' },
    { label: '德育记录', route: '/conduct', match: '/conduct' },
    { label: '班级报告', route: '/analytics/report', match: '/analytics' },
    { label: '作业跟进', route: '/homework', match: '/homework' },
  ],
  subject_teacher: [
    { label: '相关考试', route: '/exams', match: '/exams' },
    { label: '我的阅卷', route: '/marking', match: '/marking' },
    { label: '成绩分析', route: '/analytics/report', match: '/analytics' },
    { label: '作业管理', route: '/homework', match: '/homework' },
  ],
  parent: [
    { label: '成绩查看', route: '/analytics/report', match: '/analytics' },
    { label: '作业查看', route: '/homework', match: '/homework' },
  ],
}

const DEFAULT_HEADER_NAV = HEADER_NAV_BY_ROLE.subject_teacher
const OVERVIEW_NAV_ITEM = { label: '概览', route: '/', exact: true }

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
  const configuredItems = HEADER_NAV_BY_ROLE[normalized] || DEFAULT_HEADER_NAV
  const visibleItems = configuredItems.filter(item => canAccessRouteForRole(normalized, item.route, enabledModules))
  return [OVERVIEW_NAV_ITEM, ...visibleItems]
}
