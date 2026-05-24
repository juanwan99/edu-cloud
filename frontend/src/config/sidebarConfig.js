import { hasPermission } from './permissions.js'
import { canAccessRouteForRole, getRouteAccessRequirement } from './routeAccess.js'

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
      { label: '角色模拟', route: '/admin/impersonate', perm: 'manage_schools' },
    ],
  },
]

const SCHOOL_OPERATION_LABELS = {
  groups: {
    school: '学校基础',
    academic: '人员组织',
    exam: '考试流程',
    student: '学生数据',
  },
  routes: {
    '/teachers': '教师与职务',
    '/assignments': '任课关系',
    '/academic/semesters': '学期管理',
    '/academic/timetable': '课程表',
    '/exams': '考试管理',
    '/grading/tasks': '阅卷流程',
    '/analytics/report': '数据报告',
  },
}

const ACADEMIC_OPERATION_LABELS = {
  groups: {
    academic: '教学运行',
    exam: '考试质量',
    student: '学生数据',
    school: '学校基础',
    research: '教研资源',
  },
  routes: {
    '/assignments': '任课关系',
    '/selections': '选科管理',
    '/academic/semesters': '学期管理',
    '/academic/timetable': '课程表',
    '/exams': '考试管理',
    '/exam-import': '成绩导入',
    '/grading/tasks': '阅卷流程',
    '/analytics/report': '数据报告',
    '/analytics/ai-report': '质量报告',
    '/students': '学生档案',
    '/conduct': '德育协同',
    '/conduct/settings': '德育规则',
    '/teachers': '教师与职务',
    '/joint-exams': '联考复盘',
    '/calendar': '校历管理',
    '/knowledge-tree': '知识图谱',
    '/homework': '作业管理',
    '/question-bank': '题库建设',
    '/academic/teaching-plans': '教学计划',
  },
}

const GRADE_OPERATION_LABELS = {
  groups: {
    student: '年级学生',
    exam: '年级考试',
    school: '年级协同',
  },
  routes: {
    '/students': '重点学生',
    '/conduct': '德育协同',
    '/conduct/settings': '德育规则',
    '/exams': '考试管理',
    '/analytics/report': '数据报告',
    '/analytics/ai-report': '质量报告',
    '/joint-exams': '联考复盘',
    '/calendar': '年级校历',
  },
}

const HOMEROOM_OPERATION_LABELS = {
  groups: {
    student: '班级学生',
    exam: '班级考试',
    research: '教学巩固',
  },
  routes: {
    '/students': '学生档案',
    '/conduct': '德育记录',
    '/conduct/settings': '德育规则',
    '/exams': '考试管理',
    '/marking': '人工阅卷',
    '/analytics/report': '班级报告',
    '/analytics/ai-report': '质量报告',
    '/knowledge-tree': '知识图谱',
    '/homework': '作业跟进',
    '/question-bank': '题库管理',
    '/error-book': '错题本',
  },
}

const LESSON_PREP_OPERATION_LABELS = {
  groups: {
    exam: '学科考试',
    research: '资源沉淀',
  },
  routes: {
    '/exams': '考试管理',
    '/grading/tasks': '阅卷分工',
    '/ai-grading': 'AI 阅卷',
    '/marking': '人工阅卷',
    '/analytics/report': '学科报告',
    '/analytics/ai-report': '质量报告',
    '/knowledge-tree': '知识图谱',
    '/homework': '作业巩固',
    '/question-bank': '题库沉淀',
    '/error-book': '错题本',
  },
}

const TEACHING_RESEARCH_OPERATION_LABELS = {
  groups: {
    research: '教研资源',
    exam: '质量证据',
  },
  routes: {
    '/knowledge-tree': '知识体系',
    '/homework': '作业观察',
    '/question-bank': '题库建设',
    '/error-book': '错题追踪',
    '/exams': '考试证据',
    '/marking': '人工阅卷',
    '/analytics/report': '学科趋势',
    '/analytics/ai-report': '质量报告',
  },
}

const ROLE_SIDEBAR_POLICY = {
  platform_admin: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
    labels: SCHOOL_OPERATION_LABELS,
  },
  district_admin: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
    labels: SCHOOL_OPERATION_LABELS,
  },
  school_admin: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
    labels: SCHOOL_OPERATION_LABELS,
  },
  principal: {
    groups: ['school', 'academic', 'exam', 'student'],
    hiddenRoutes: ['/marking', '/homework', '/question-bank', '/knowledge-tree', '/error-book'],
    labels: SCHOOL_OPERATION_LABELS,
  },
  academic_director: {
    groups: ['academic', 'exam', 'student', 'school', 'research'],
    hiddenRoutes: ['/marking', '/error-book'],
    labels: ACADEMIC_OPERATION_LABELS,
  },
  teaching_research_leader: {
    groups: ['research', 'exam'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/students', '/conduct'],
    labels: TEACHING_RESEARCH_OPERATION_LABELS,
  },
  grade_leader: {
    groups: ['student', 'exam', 'school'],
    hiddenRoutes: ['/marking', '/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/question-bank', '/knowledge-tree'],
    labels: GRADE_OPERATION_LABELS,
  },
  lesson_prep_leader: {
    groups: ['exam', 'research'],
    hiddenRoutes: ['/school-settings', '/assignments', '/teachers', '/students', '/conduct', '/academic/timetable', '/academic/semesters'],
    labels: LESSON_PREP_OPERATION_LABELS,
  },
  homeroom_teacher: {
    groups: ['student', 'exam', 'research'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/academic/timetable', '/academic/semesters'],
    labels: HOMEROOM_OPERATION_LABELS,
  },
  subject_teacher: {
    groups: ['exam', 'research'],
    hiddenRoutes: ['/grading/tasks', '/ai-grading', '/school-settings', '/assignments', '/teachers', '/students', '/conduct', '/academic/timetable', '/academic/semesters'],
  },
  parent: {
    groups: ['student', 'research'],
    hiddenRoutes: ['/exams', '/exam-import', '/grading/tasks', '/ai-grading', '/marking', '/school-settings', '/assignments', '/teachers'],
  },
}

function policyFor(role) {
  return ROLE_SIDEBAR_POLICY[role] || null
}

function applyRolePolicy(role, groups) {
  const policy = policyFor(role)
  if (!policy) return groups
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
