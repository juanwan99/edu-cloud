import { hasPermission } from './permissions.js'
import { canAccessRouteForRole, getRouteAccessRequirement } from './routeAccess.js'
import { getRoleSidebarPolicy } from './roleEntryMatrix.js'

const SIDEBAR_GROUPS = [
  {
    key: 'exam',
    label: '考试阅卷',
    icon: 'exam',
    children: [
      { label: '考试管理', route: '/exams', moduleCode: 'exam', perm: 'view_exams' },
      { label: '成绩导入', route: '/exam-import', moduleCode: 'exam', perm: 'import_exams' },
      { label: '阅卷调度', route: '/grading/tasks', moduleCode: 'grading', perm: 'manage_grading' },
      { label: 'AI 阅卷', route: '/ai-grading', moduleCode: 'grading', perm: 'manage_grading' },
      { label: '人工阅卷', route: '/marking', moduleCode: 'grading', perm: 'view_grading' },
      { label: '成绩分析', route: '/analytics/report', moduleCode: 'study_analytics', perm: 'view_scores' },
      { label: '阅卷质量报告', route: '/analytics/ai-report', moduleCode: 'study_analytics', perm: 'view_scores' },
    ],
  },
  {
    key: 'research',
    label: '教研教学',
    icon: 'book',
    children: [
      { label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research', perm: 'view_knowledge_tree' },
      { label: '作业管理', route: '/homework', moduleCode: 'homework', perm: 'view_homework' },
      { label: '题库管理', route: '/question-bank', moduleCode: 'research', perm: 'view_question_bank' },
      { label: '错题本', route: '/error-book', moduleCode: 'research', perm: 'view_scores' },
      { label: '教学计划', route: '/academic/teaching-plans', perm: 'manage_scheduling' },
    ],
  },
  {
    key: 'academic',
    label: '教务管理',
    icon: 'academic',
    children: [
      { label: '教师分配', route: '/assignments', perm: 'manage_scheduling' },
      { label: '选科管理', route: '/selections', perm: 'manage_scheduling' },
      { label: '学期管理', route: '/academic/semesters', perm: 'manage_scheduling' },
      { label: '课程表', route: '/academic/timetable', perm: 'manage_scheduling' },
    ],
  },
  {
    key: 'student',
    label: '学生管理',
    icon: 'people',
    children: [
      { label: '学生档案', route: '/students', perm: 'view_students' },
      { label: '德育工作台', route: '/conduct', moduleCode: 'conduct', perm: 'view_conduct' },
      { label: '德育设置', route: '/conduct/settings', moduleCode: 'conduct', perm: 'manage_conduct_rules' },
    ],
  },
  {
    key: 'school',
    label: '学校管理',
    icon: 'school',
    children: [
      { label: '教师管理', route: '/teachers', perm: 'manage_teachers' },
      { label: '学校管理', route: '/schools', perm: 'manage_schools' },
      { label: '学校配置', route: '/school-settings', perm: 'manage_school_config' },
      { label: '联考管理', route: '/joint-exams', perm: 'view_joint_exam' },
      { label: '校历管理', route: '/calendar', moduleCode: 'calendar' },
      { label: '角色模拟', route: '/admin/impersonate', perm: 'impersonate_roles' },
    ],
  },
]

function applyRolePolicy(role, groups) {
  const policy = getRoleSidebarPolicy(role)
  const groupRank = new Map(policy.groups.map((key, index) => [key, index]))
  const hiddenRoutes = new Set(policy.hiddenRoutes || [])
  const groupLabels = policy.labels?.groups || {}
  const routeLabels = policy.labels?.routes || {}
  return groups
    .filter(group => groupRank.has(group.key))
    .map(group => ({
      ...group,
      label: groupLabels[group.key] || group.label,
      children: group.children
        .filter(item => !hiddenRoutes.has(item.route))
        .map(item => ({
          ...item,
          label: routeLabels[item.route] || item.label,
        })),
    }))
    .filter(group => group.children.length > 0)
    .sort((a, b) => groupRank.get(a.key) - groupRank.get(b.key))
}

export { SIDEBAR_GROUPS }

export const CONDUCT_ITEMS = SIDEBAR_GROUPS
  .find(g => g.key === 'student')
  .children.filter(c => c.moduleCode === 'conduct')

function canAccessSidebarItem(role, item, enabledModules) {
  if (getRouteAccessRequirement(item.route)) {
    return canAccessRouteForRole(role, item.route, enabledModules)
  }
  const enabled = new Set(enabledModules)
  if (item.perm && !hasPermission(role, item.perm)) return false
  if (item.moduleCode && enabled.size > 0 && !enabled.has(item.moduleCode)) return false
  return true
}

export function getSidebarGroups(role, enabledModules = []) {
  const permissionFiltered = SIDEBAR_GROUPS
    .map(group => {
      const visibleChildren = group.children.filter(item => canAccessSidebarItem(role, item, enabledModules))
      if (visibleChildren.length === 0) return null
      return { ...group, children: visibleChildren }
    })
    .filter(Boolean)
  return applyRolePolicy(role, permissionFiltered)
}

export function getSidebarItems(role, enabledModules = []) {
  const groups = getSidebarGroups(role, enabledModules)
  const items = [{ icon: 'dashboard', label: '概览', route: '/' }]
  for (const group of groups) {
    for (const child of group.children) {
      items.push({ icon: group.icon, label: child.label, route: child.route, moduleCode: child.moduleCode })
    }
  }
  return items
}
