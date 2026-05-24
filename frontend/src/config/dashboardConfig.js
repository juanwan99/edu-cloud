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
    { id: 'pending_grading', label: '待处理阅卷', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_exams', label: '相关考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '学科表现', color: 'purple', source: 'dashboard_summary' },
  ],
  widgets: [
    { type: 'module', id: 'exams', title: '相关考试', icon: 'exam', route: '/exams' },
    { type: 'module', id: 'my_marking', title: '我的阅卷', icon: 'marking', route: '/marking' },
    { type: 'module', id: 'analytics', title: '成绩分析', icon: 'chart', route: '/analytics/report' },
    { type: 'module', id: 'homework', title: '作业管理', icon: 'book', route: '/homework' },
    { type: 'module', id: 'question_bank', title: '题库管理', icon: 'book', route: '/question-bank' },
    { type: 'module', id: 'knowledge_tree', title: '知识图谱', icon: 'chart', route: '/knowledge-tree' },
  ],
}

const HOMEROOM_CONFIG = {
  title: '班级工作台',
  kpis: [
    { id: 'total_classes', label: '负责班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待处理阅卷', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_exams', label: '班级考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '班级表现', color: 'purple', source: 'dashboard_summary' },
  ],
  widgets: [
    { type: 'module', id: 'exams', title: '班级考试', icon: 'exam', route: '/exams' },
    { type: 'module', id: 'grading_tasks', title: '阅卷任务', icon: 'marking', route: '/grading/tasks' },
    { type: 'module', id: 'analytics', title: '成绩分析', icon: 'chart', route: '/analytics/report' },
    { type: 'module', id: 'homework', title: '作业管理', icon: 'book', route: '/homework' },
    { type: 'module', id: 'students', title: '学生档案', icon: 'people', route: '/students' },
    { type: 'module', id: 'conduct', title: '德育工作台', icon: 'people', route: '/conduct' },
  ],
}

const LESSON_PREP_CONFIG = {
  title: '备课组工作台',
  kpis: [
    { id: 'total_classes', label: '覆盖班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待统筹阅卷', color: 'coral', source: 'dashboard_summary' },
    { id: 'total_exams', label: '组内考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '学科表现', color: 'purple', source: 'dashboard_summary' },
  ],
  widgets: [
    { type: 'module', id: 'exams', title: '考试管理', icon: 'exam', route: '/exams' },
    { type: 'module', id: 'grading_tasks', title: '阅卷调度', icon: 'marking', route: '/grading/tasks' },
    { type: 'module', id: 'analytics', title: '成绩分析', icon: 'chart', route: '/analytics/report' },
    { type: 'module', id: 'homework', title: '作业管理', icon: 'book', route: '/homework' },
    { type: 'module', id: 'question_bank', title: '题库管理', icon: 'book', route: '/question-bank' },
    { type: 'module', id: 'knowledge_tree', title: '知识图谱', icon: 'chart', route: '/knowledge-tree' },
  ],
}

const TEACHING_RESEARCH_CONFIG = {
  title: '教研工作台',
  kpis: [
    { id: 'total_classes', label: '覆盖班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'total_exams', label: '相关考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '学科表现', color: 'purple', source: 'dashboard_summary' },
  ],
  widgets: [
    { type: 'module', id: 'exams', title: '相关考试', icon: 'exam', route: '/exams' },
    { type: 'module', id: 'analytics', title: '成绩分析', icon: 'chart', route: '/analytics/report' },
    { type: 'module', id: 'question_bank', title: '题库管理', icon: 'book', route: '/question-bank' },
    { type: 'module', id: 'knowledge_tree', title: '知识图谱', icon: 'chart', route: '/knowledge-tree' },
  ],
}

const GRADE_LEADER_CONFIG = {
  title: '年级工作台',
  kpis: [
    { id: 'total_classes', label: '年级班级', color: 'mint', source: 'dashboard_summary' },
    { id: 'total_exams', label: '年级考试', color: 'yellow', source: 'dashboard_summary' },
    { id: 'pending_grading', label: '待关注阅卷', color: 'coral', source: 'dashboard_summary' },
    { id: 'subject_avg', label: '年级表现', color: 'purple', source: 'dashboard_summary' },
  ],
  widgets: [
    { type: 'module', id: 'exams', title: '年级考试', icon: 'exam', route: '/exams' },
    { type: 'module', id: 'analytics', title: '成绩分析', icon: 'chart', route: '/analytics/report' },
    { type: 'module', id: 'students', title: '学生档案', icon: 'people', route: '/students' },
    { type: 'module', id: 'joint_exams', title: '联考管理', icon: 'exam', route: '/joint-exams' },
    { type: 'module', id: 'conduct', title: '德育工作台', icon: 'people', route: '/conduct' },
  ],
}

const DASHBOARD_CONFIGS = {
  platform_admin: ADMIN_CONFIG,
  district_admin: ADMIN_CONFIG,
  school_admin: ADMIN_CONFIG,
  principal: ADMIN_CONFIG,
  academic_director: ADMIN_CONFIG,
  teaching_research_leader: TEACHING_RESEARCH_CONFIG,
  grade_leader: GRADE_LEADER_CONFIG,
  lesson_prep_leader: LESSON_PREP_CONFIG,
  homeroom_teacher: HOMEROOM_CONFIG,
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
