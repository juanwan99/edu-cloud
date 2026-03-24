const SIDEBAR_ITEMS = {
  platform_admin: [
    { icon: 'dashboard', label: '平台概览', route: '/' },
    { icon: 'school', label: '学校管理', route: '/schools' },
    { icon: 'exam', label: '联考管理', route: '/exams' },
    { icon: 'settings', label: '系统设置', route: '/analysis' },
  ],
  district_admin: [
    { icon: 'dashboard', label: '区域概览', route: '/' },
    { icon: 'school', label: '学校管理', route: '/schools' },
    { icon: 'exam', label: '联考管理', route: '/exams' },
    { icon: 'chart', label: '跨校分析', route: '/analysis' },
  ],
  principal: [
    { icon: 'dashboard', label: '校务概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'document', label: '文档中心', route: '/analysis' },
    { icon: 'calendar', label: '校历通知', route: '/analysis' },
  ],
  academic_director: [
    { icon: 'dashboard', label: '教务概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'exam', label: '联考管理', route: '/exams' },
    { icon: 'marking', label: '阅卷调度', route: '/grading/tasks' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'document', label: '文档中心', route: '/analysis' },
  ],
  grade_leader: [
    { icon: 'dashboard', label: '年级概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'document', label: '文档', route: '/analysis' },
  ],
  homeroom_teacher: [
    { icon: 'dashboard', label: '我的工作台', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'marking', label: '阅卷', route: '/marking' },
    { icon: 'chart', label: '成绩分析', route: '/analysis' },
    { icon: 'notification', label: '通知管理', route: '/analysis' },
    { icon: 'document', label: '文档', route: '/analysis' },
  ],
  subject_teacher: [
    { icon: 'dashboard', label: '我的工作台', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'marking', label: '阅卷', route: '/marking' },
    { icon: 'chart', label: '成绩分析', route: '/analysis' },
    { icon: 'paper', label: '论文写作', route: '/analysis' },
    { icon: 'document', label: '文档', route: '/analysis' },
  ],
  parent: [
    { icon: 'score', label: '孩子成绩', route: '/' },
    { icon: 'notification', label: '学校通知', route: '/' },
  ],
}

export function getSidebarItems(role) {
  return SIDEBAR_ITEMS[role] || SIDEBAR_ITEMS.subject_teacher
}
