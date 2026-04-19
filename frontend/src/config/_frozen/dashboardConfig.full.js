const DASHBOARD_CONFIGS = {
  platform_admin: {
    title: '平台概览',
    kpis: [
      { id: 'total_schools', label: '学校总数', color: 'mint', source: 'schools' },
      { id: 'active_schools', label: '活跃学校', color: 'yellow', source: 'schools' },
      { id: 'joint_exams', label: '联考进行中', color: 'coral', source: 'joint_exams' },
      { id: 'system_users', label: '系统用户', color: 'purple', source: null },
    ],
    widgets: [
      { type: 'module', id: 'schools', title: '学校管理', icon: 'school', route: '/schools' },
      { type: 'module', id: 'joint_exams', title: '联考管理', icon: 'exam', route: '/exams' },
      { type: 'module', id: 'settings', title: '系统设置', icon: 'settings', route: '/analysis' },
      { type: 'module', id: 'users', title: '用户管理', icon: 'users', route: null, planned: true },
    ],
  },
  district_admin: {
    title: '管辖区域概览',
    kpis: [
      { id: 'district_schools', label: '管辖学校', color: 'mint', source: 'schools' },
      { id: 'joint_exams', label: '联考进行中', color: 'yellow', source: 'joint_exams' },
      { id: 'cross_avg', label: '跨校均分', color: 'coral', source: null },
      { id: 'pending', label: '待处理', color: 'purple', source: null },
    ],
    widgets: [
      { type: 'module', id: 'schools', title: '学校管理', icon: 'school', route: '/schools' },
      { type: 'module', id: 'joint_exams', title: '联考管理', icon: 'exam', route: '/exams' },
      { type: 'module', id: 'cross_analysis', title: '跨校分析', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'users', title: '用户管理', icon: 'users', route: null, planned: true },
    ],
  },
  principal: {
    title: '学校全局',
    kpis: [
      { id: 'total_students', label: '在校学生', color: 'mint', source: 'dashboard_summary' },
      { id: 'total_staff', label: '教职工', color: 'yellow', source: 'dashboard_summary' },
      { id: 'pending_approvals', label: '待审批', color: 'purple', source: 'notifications' },
      { id: 'week_notifications', label: '本周通知', color: 'coral', source: 'notifications' },
    ],
    widgets: [
      { type: 'module', id: 'teaching', title: '教学质量', icon: 'chart', route: '/exams' },
      { type: 'module', id: 'admin', title: '校务行政', icon: 'calendar', route: '/analysis' },
      { type: 'module', id: 'ai', title: 'AI 助手', icon: 'ai', route: '/analysis' },
      { type: 'module', id: 'docs', title: '文档中心', icon: 'document', route: '/analysis' },
      { type: 'module', id: 'hr', title: '师资人事', icon: 'users', route: null, planned: true },
      { type: 'module', id: 'logistics', title: '后勤安全', icon: 'shield', route: null, planned: true },
    ],
  },
  academic_director: {
    title: '教务中心',
    kpis: [
      { id: 'total_exams', label: '本学期考试', color: 'mint', source: 'dashboard_summary' },
      { id: 'pending_subjects', label: '待阅卷科目', color: 'yellow', source: 'dashboard_summary' },
      { id: 'joint_exams', label: '联考进行中', color: 'coral', source: 'joint_exams' },
      { id: 'ai_rate', label: 'AI批改完成率', color: 'purple', source: null },
    ],
    widgets: [
      { type: 'module', id: 'exams', title: '考试管理', icon: 'exam', route: '/exams' },
      { type: 'module', id: 'joint_exams', title: '联考管理', icon: 'exam', route: '/exams' },
      { type: 'module', id: 'grading', title: '阅卷调度', icon: 'marking', route: '/grading/tasks' },
      { type: 'module', id: 'analytics', title: '数据分析', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'docs', title: '文档中心', icon: 'document', route: '/analysis' },
      { type: 'module', id: 'ai', title: 'AI 助手', icon: 'ai', route: '/analysis' },
    ],
  },
  teaching_research_leader: {
    title: '学科教研',
    kpis: [
      { id: 'subject_classes', label: '教授班级', color: 'mint', source: 'dashboard_summary' },
      { id: 'subject_avg', label: '学科均分', color: 'yellow', source: null },
      { id: 'recent_exam', label: '最近考试', color: 'coral', source: null },
      { id: 'ai_tools', label: 'AI工具', color: 'purple', source: 'ai_health' },
    ],
    widgets: [
      { type: 'module', id: 'subject_scores', title: '学科成绩', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'exams', title: '考试管理', icon: 'exam', route: '/exams' },
      { type: 'module', id: 'knowledge', title: '知识图谱', icon: 'chart', route: '/knowledge-tree' },
      { type: 'module', id: 'paper', title: '论文写作', icon: 'paper', route: '/paper' },
    ],
  },
  grade_leader: {
    title: '年级概览',
    kpis: [
      { id: 'total_classes', label: '年级班级', color: 'mint', source: 'dashboard_summary' },
      { id: 'total_students', label: '年级学生', color: 'yellow', source: 'dashboard_summary' },
      { id: 'grade_avg', label: '年级均分', color: 'coral', source: null },
      { id: 'recent_exam', label: '最近考试', color: 'purple', source: null },
    ],
    widgets: [
      { type: 'module', id: 'grade_overview', title: '年级成绩', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'exams', title: '考试管理', icon: 'exam', route: '/exams' },
      { type: 'module', id: 'analytics', title: '数据分析', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'notifications', title: '年级通知', icon: 'notification', route: '/notifications' },
    ],
  },
  lesson_prep_leader: {
    title: '备课工作台',
    kpis: [
      { id: 'total_classes', label: '平行班级', color: 'mint', source: 'dashboard_summary' },
      { id: 'subject_avg', label: '学科均分', color: 'yellow', source: null },
      { id: 'pending_grading', label: '待批改', color: 'coral', source: 'dashboard_summary' },
      { id: 'ai_tools', label: 'AI工具', color: 'purple', source: 'ai_health' },
    ],
    widgets: [
      { type: 'module', id: 'my_grading', title: '我的阅卷', icon: 'marking', route: '/marking' },
      { type: 'module', id: 'subject_scores', title: '学科成绩', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'ai', title: 'AI 助手', icon: 'ai', route: '/analysis' },
      { type: 'module', id: 'paper', title: '论文写作', icon: 'paper', route: '/paper' },
    ],
  },
  homeroom_teacher: {
    title: '班级工作台',
    kpis: [
      { id: 'my_class', label: '我的班级', color: 'mint', source: 'local' },
      { id: 'total_students', label: '班级人数', color: 'yellow', source: 'dashboard_summary' },
      { id: 'class_avg', label: '班级均分', color: 'coral', source: null },
      { id: 'pending_grading', label: '待批改', color: 'purple', source: 'dashboard_summary' },
    ],
    widgets: [
      { type: 'module', id: 'my_class', title: '我的班级', icon: 'class', route: '/analysis' },
      { type: 'module', id: 'todos', title: '待办事项', icon: 'todo', route: '/marking' },
      { type: 'module', id: 'analytics', title: '成绩分析', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'notifications', title: '通知管理', icon: 'notification', route: '/analysis' },
      { type: 'module', id: 'ai', title: 'AI 助手', icon: 'ai', route: '/analysis' },
      { type: 'module', id: 'docs', title: '文档中心', icon: 'document', route: '/analysis' },
    ],
  },
  subject_teacher: {
    title: '教学工作台',
    kpis: [
      { id: 'total_classes', label: '教授班级', color: 'mint', source: 'local' },
      { id: 'subject_avg', label: '学科均分', color: 'yellow', source: null },
      { id: 'pending_grading', label: '待批改', color: 'coral', source: 'dashboard_summary' },
      { id: 'ai_tools', label: 'AI工具', color: 'purple', source: 'ai_health' },
    ],
    widgets: [
      { type: 'module', id: 'my_grading', title: '我的阅卷', icon: 'marking', route: '/marking' },
      { type: 'module', id: 'subject_scores', title: '学科成绩', icon: 'chart', route: '/analysis' },
      { type: 'module', id: 'ai', title: 'AI 助手', icon: 'ai', route: '/analysis' },
      { type: 'module', id: 'paper', title: '论文写作', icon: 'paper', route: '/analysis' },
    ],
  },
  parent: {
    title: '家校互通',
    kpis: [
      { id: 'child_score', label: '孩子成绩', color: 'mint', source: null },
      { id: 'school_notice', label: '学校通知', color: 'yellow', source: 'notifications' },
    ],
    widgets: [
      { type: 'module', id: 'notices', title: '学校通知', icon: 'notification', route: '/' },
      { type: 'module', id: 'child_scores', title: '孩子成绩', icon: 'score', route: null, planned: true },
      { type: 'module', id: 'child_profile', title: '学习画像', icon: 'profile', route: null, planned: true },
    ],
  },
}

export function getDashboardConfig(role) {
  return DASHBOARD_CONFIGS[role] || DASHBOARD_CONFIGS.subject_teacher
}
