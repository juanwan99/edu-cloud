const CONDUCT_ITEMS_FULL = [
  { icon: 'conduct', label: '德育概览', route: '/conduct', moduleCode: 'conduct' },
  { icon: 'conduct', label: '积分操作', route: '/conduct/points', moduleCode: 'conduct' },
  { icon: 'conduct', label: '积分记录', route: '/conduct/records', moduleCode: 'conduct' },
  { icon: 'conduct', label: '排行榜', route: '/conduct/rankings', moduleCode: 'conduct' },
  { icon: 'conduct', label: '班规管理', route: '/conduct/rules', moduleCode: 'conduct' },
  { icon: 'conduct', label: '小组管理', route: '/conduct/groups', moduleCode: 'conduct' },
  { icon: 'conduct', label: '家长管理', route: '/conduct/parents', moduleCode: 'conduct' },
  { icon: 'conduct', label: '德育设置', route: '/conduct/settings', moduleCode: 'conduct' },
  { icon: 'conduct', label: '数据导出', route: '/conduct/export', moduleCode: 'conduct' },
]

const CONDUCT_ITEMS_VIEWER = [
  { icon: 'conduct', label: '德育概览', route: '/conduct', moduleCode: 'conduct' },
  { icon: 'conduct', label: '排行榜', route: '/conduct/rankings', moduleCode: 'conduct' },
  { icon: 'conduct', label: '数据导出', route: '/conduct/export', moduleCode: 'conduct' },
]

const CONDUCT_ITEMS_TEACHER = [
  { icon: 'conduct', label: '积分操作', route: '/conduct/points', moduleCode: 'conduct' },
  { icon: 'conduct', label: '排行榜', route: '/conduct/rankings', moduleCode: 'conduct' },
]

const SIDEBAR_ITEMS = {
  platform_admin: [
    { icon: 'dashboard', label: '平台概览', route: '/' },
    { icon: 'school', label: '学校管理', route: '/schools' },
    { icon: 'exam', label: '联考管理', route: '/exams' },
    { icon: 'settings', label: '系统设置', route: '/settings' },
    ...CONDUCT_ITEMS_FULL,
  ],
  district_admin: [
    { icon: 'dashboard', label: '区域概览', route: '/' },
    { icon: 'school', label: '学校管理', route: '/schools' },
    { icon: 'exam', label: '联考管理', route: '/exams' },
    { icon: 'chart', label: '跨校分析', route: '/analysis' },
    ...CONDUCT_ITEMS_FULL,
  ],
  // 校长：偏审批/配置/全局概览，排课归教务；conduct 按前端权限镜像给 VIEWER（view + export）
  principal: [
    { icon: 'dashboard', label: '校务概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷概览', route: '/grading/tasks', moduleCode: 'grading' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'report', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
    { icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
    { icon: 'document', label: '文档中心', route: '/studio', moduleCode: 'studio' },
    { icon: 'calendar', label: '校历通知', route: '/calendar', moduleCode: 'calendar' },
    { icon: 'settings', label: '学校配置', route: '/school-settings' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
    ...CONDUCT_ITEMS_VIEWER,
  ],
  // 教务主任：日常运营——考试/排课/阅卷/选考
  academic_director: [
    { icon: 'dashboard', label: '教务概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷调度', route: '/grading/tasks', moduleCode: 'grading' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'report', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
    { icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
    { icon: 'document', label: '文档中心', route: '/studio', moduleCode: 'studio' },
    { icon: 'settings', label: '排课管理', route: '/assignments' },
    { icon: 'exam', label: '选考组合', route: '/selections' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
    ...CONDUCT_ITEMS_VIEWER,
  ],
  // 教研组长：跨年级单学科视角
  teaching_research_leader: [
    { icon: 'dashboard', label: '学科概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'chart', label: '学科分析', route: '/analysis' },
    { icon: 'report', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
    { icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
    { icon: 'paper', label: '论文写作', route: '/paper' },
    { icon: 'document', label: '文档', route: '/studio', moduleCode: 'studio' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
  ],
  // 年级组长：单年级全科行政管理
  grade_leader: [
    { icon: 'dashboard', label: '年级概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'chart', label: '数据分析', route: '/analysis' },
    { icon: 'report', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
    { icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
    { icon: 'notification', label: '年级通知', route: '/notifications' },
    { icon: 'document', label: '文档', route: '/studio', moduleCode: 'studio' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
    ...CONDUCT_ITEMS_VIEWER,
  ],
  // 备课组长：单年级单学科全平行班（导航同科任教师，数据 scope 不同）
  lesson_prep_leader: [
    { icon: 'dashboard', label: '备课工作台', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷', route: '/marking', moduleCode: 'grading' },
    { icon: 'chart', label: '学科分析', route: '/analysis' },
    { icon: 'report', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
    { icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
    { icon: 'paper', label: '论文写作', route: '/paper' },
    { icon: 'document', label: '文档', route: '/studio', moduleCode: 'studio' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
  ],
  // 班主任：教师基线 + 班级通知 + 德育全部
  homeroom_teacher: [
    { icon: 'dashboard', label: '我的工作台', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷', route: '/marking', moduleCode: 'grading' },
    { icon: 'chart', label: '成绩分析', route: '/analysis' },
    { icon: 'report', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
    { icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
    { icon: 'notification', label: '通知管理', route: '/notifications' },
    { icon: 'paper', label: '论文写作', route: '/paper' },
    { icon: 'document', label: '文档', route: '/studio', moduleCode: 'studio' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
    ...CONDUCT_ITEMS_FULL,
  ],
  // 科任教师：教师基线 + 德育积分操作 + 排行
  subject_teacher: [
    { icon: 'dashboard', label: '我的工作台', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams', moduleCode: 'exam' },
    { icon: 'marking', label: '阅卷', route: '/marking', moduleCode: 'grading' },
    { icon: 'chart', label: '成绩分析', route: '/analysis' },
    { icon: 'report', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
    { icon: 'trend', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
    { icon: 'paper', label: '论文写作', route: '/paper' },
    { icon: 'document', label: '文档', route: '/studio', moduleCode: 'studio' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
    ...CONDUCT_ITEMS_TEACHER,
  ],
  parent: [
    { icon: 'score', label: '孩子成绩', route: '/' },
    { icon: 'notification', label: '学校通知', route: '/notifications' },
    { icon: 'chart', label: '知识图谱', route: '/knowledge-tree', moduleCode: 'research' },
  ],
}

export function getSidebarItems(role) {
  return SIDEBAR_ITEMS[role] || SIDEBAR_ITEMS.subject_teacher
}
