import { hasPermission } from './permissions.js'

const SIDEBAR_GROUPS = [
  {
    key: 'exam',
    label: '考试阅卷',
    icon: 'exam',
    children: [
      { label: '考试管理', route: '/exams', moduleCode: 'exam', perm: 'view_exams' },
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
      { label: '知识图谱', route: '/knowledge-tree', perm: 'view_knowledge_tree' },
      { label: '作业管理', route: '/homework', moduleCode: 'homework', perm: 'view_homework' },
      { label: '题库管理', route: '/question-bank', perm: 'view_question_bank' },
      { label: '错题本', route: '/error-book', perm: 'view_scores' },
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
      { label: '教师管理', route: '/teachers', perm: 'manage_scheduling' },
      { label: '学校管理', route: '/schools', perm: 'manage_schools' },
      { label: '学校配置', route: '/school-settings', perm: 'manage_school_config' },
      { label: '联考管理', route: '/joint-exams', perm: 'view_joint_exam' },
      { label: '校历管理', route: '/calendar', moduleCode: 'calendar' },
      { label: '角色模拟', route: '/admin/impersonate', perm: 'manage_schools' },
    ],
  },
]

export { SIDEBAR_GROUPS }

export const CONDUCT_ITEMS = SIDEBAR_GROUPS
  .find(g => g.key === 'student')
  .children.filter(c => c.moduleCode === 'conduct')

export function getSidebarGroups(role, enabledModules = []) {
  const enabled = new Set(enabledModules)
  return SIDEBAR_GROUPS
    .map(group => {
      const visibleChildren = group.children.filter(item => {
        if (item.perm && !hasPermission(role, item.perm)) return false
        if (item.moduleCode && enabled.size > 0 && !enabled.has(item.moduleCode)) return false
        return true
      })
      if (visibleChildren.length === 0) return null
      return { ...group, children: visibleChildren }
    })
    .filter(Boolean)
}

export function getSidebarItems(role) {
  const groups = getSidebarGroups(role)
  const items = [{ icon: 'dashboard', label: '概览', route: '/' }]
  for (const group of groups) {
    for (const child of group.children) {
      items.push({ icon: group.icon, label: child.label, route: child.route, moduleCode: child.moduleCode })
    }
  }
  return items
}
