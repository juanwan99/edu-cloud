// Frozen 2026-04-19: only exam + grading + personnel
// Full version: config/_frozen/dashboardConfig.full.js

const ADMIN_CONFIG = {
  title: '管理概览',
  kpis: [
    { id: 'total_exams', label: '考试总数', color: 'mint', source: 'dashboard_summary' },
    { id: 'total_students', label: '在校学生', color: 'yellow', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待阅卷', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_staff', label: '教职工', color: 'purple', source: 'dashboard_summary' },
  ],
  widgets: [
    { type: 'module', id: 'exams', title: '考试管理', icon: 'exam', route: '/exams' },
    { type: 'module', id: 'grading', title: '阅卷分派', icon: 'marking', route: '/grading/tasks' },
    { type: 'module', id: 'schools', title: '学校管理', icon: 'school', route: '/schools' },
    { type: 'module', id: 'assignments', title: '教师分配', icon: 'settings', route: '/assignments' },
  ],
}

const TEACHER_CONFIG = {
  title: '教学工作台',
  kpis: [
    { id: 'total_classes', label: '教授班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待批改', color: 'coral', source: 'dashboard_summary' },
  ],
  widgets: [
    { type: 'module', id: 'exams', title: '考试管理', icon: 'exam', route: '/exams' },
    { type: 'module', id: 'my_grading', title: '我的阅卷', icon: 'marking', route: '/marking' },
  ],
}

const DASHBOARD_CONFIGS = {
  platform_admin: ADMIN_CONFIG,
  district_admin: ADMIN_CONFIG,
  school_admin: ADMIN_CONFIG,
  principal: ADMIN_CONFIG,
  academic_director: ADMIN_CONFIG,
  teaching_research_leader: TEACHER_CONFIG,
  grade_leader: TEACHER_CONFIG,
  lesson_prep_leader: TEACHER_CONFIG,
  homeroom_teacher: TEACHER_CONFIG,
  subject_teacher: TEACHER_CONFIG,
  parent: {
    title: '家长端',
    kpis: [],
    widgets: [],
  },
}

export function getDashboardConfig(role) {
  return DASHBOARD_CONFIGS[role] || DASHBOARD_CONFIGS.subject_teacher
}
