// Frozen 2026-04-19: only exam + grading + personnel
// Full version: config/_frozen/sidebarConfig.full.js

import { hasPermission } from './permissions.js'

export const CONDUCT_ITEMS = [
  { icon: 'conduct', label: '德育概览', route: '/conduct',          perm: 'view_conduct',           moduleCode: 'conduct' },
  { icon: 'conduct', label: '积分操作', route: '/conduct/points',   perm: 'manage_conduct',         moduleCode: 'conduct' },
  { icon: 'conduct', label: '积分记录', route: '/conduct/records',  perm: 'view_conduct',           moduleCode: 'conduct' },
  { icon: 'conduct', label: '排行榜',   route: '/conduct/rankings', perm: 'view_conduct',           moduleCode: 'conduct' },
  { icon: 'conduct', label: '班规管理', route: '/conduct/rules',    perm: 'manage_conduct_rules',   moduleCode: 'conduct' },
  { icon: 'conduct', label: '小组管理', route: '/conduct/groups',   perm: 'manage_conduct',         moduleCode: 'conduct' },
  { icon: 'conduct', label: '家长管理', route: '/conduct/parents',  perm: 'manage_conduct_parents', moduleCode: 'conduct' },
  { icon: 'conduct', label: '德育设置', route: '/conduct/settings', perm: 'manage_conduct_rules',   moduleCode: 'conduct' },
  { icon: 'conduct', label: '数据导出', route: '/conduct/export',   perm: 'export_conduct',         moduleCode: 'conduct' },
]

function filterConductByRole(role) {
  return CONDUCT_ITEMS.filter(it => hasPermission(role, it.perm))
}

// 教务级：全流程管控 + 备课组长全部能力
const EXAM_ADMIN_ITEMS = [
  { icon: 'exam', label: '考试管理', route: '/exams' },
  { icon: 'scan', label: '阅卷调度', route: '/grading/tasks' },
  { icon: 'marking', label: 'AI 阅卷', route: '/ai-grading' },
  { icon: 'marking', label: '人工阅卷/审核', route: '/marking' },
  { icon: 'marking', label: '阅卷分配', route: '/marking/assign' },
  { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
  { icon: 'exam', label: '作业管理', route: '/homework' },
]

// 备课组长级：管本学科（题目/细则/AI阅卷/审核）
const SUBJECT_LEAD_ITEMS = [
  { icon: 'marking', label: 'AI 阅卷', route: '/ai-grading' },
  { icon: 'marking', label: '人工阅卷/审核', route: '/marking' },
  { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
]

// 教师级：纯阅卷
const TEACHER_GRADING_ITEMS = [
  { icon: 'marking', label: '我的阅卷', route: '/marking' },
  { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
]

const ANALYTICS_ITEMS = [
  { icon: 'chart', label: '分析报告', route: '/analytics/report', moduleCode: 'study_analytics' },
  { icon: 'chart', label: '成绩趋势', route: '/analytics/trend', moduleCode: 'study_analytics' },
  { icon: 'score', label: '错题本', route: '/error-book', moduleCode: 'study_analytics' },
]

const JOINT_EXAM_ITEMS = [
  { icon: 'exam', label: '联考管理', route: '/joint-exams' },
]

const STUDENT_TEACHER_ITEMS = [
  { icon: 'school', label: '学生管理', route: '/students' },
  { icon: 'school', label: '教师管理', route: '/teachers' },
]

const SCHOOL_CONFIG_ITEMS = [
  { icon: 'school', label: '学校管理', route: '/schools' },
  { icon: 'settings', label: '学校配置', route: '/school-settings' },
]

const CALENDAR_ITEMS = [
  { icon: 'calendar', label: '校历管理', route: '/calendar' },
]

const SCHEDULING_ITEMS = [
  { icon: 'settings', label: '学期管理', route: '/academic/semesters' },
  { icon: 'exam', label: '课程表', route: '/academic/timetable' },
  { icon: 'settings', label: '教师分配', route: '/assignments' },
  { icon: 'exam', label: '选科管理', route: '/selections' },
]

const SIDEBAR_ITEMS = {
  platform_admin: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_ADMIN_ITEMS,
    ...JOINT_EXAM_ITEMS,
    ...ANALYTICS_ITEMS,
    ...CALENDAR_ITEMS,
    ...STUDENT_TEACHER_ITEMS,
    ...SCHOOL_CONFIG_ITEMS,
    ...SCHEDULING_ITEMS,
    ...filterConductByRole('platform_admin'),
  ],
  district_admin: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_ADMIN_ITEMS,
    ...JOINT_EXAM_ITEMS,
    ...ANALYTICS_ITEMS,
    ...CALENDAR_ITEMS,
    ...STUDENT_TEACHER_ITEMS,
    ...SCHOOL_CONFIG_ITEMS,
    ...SCHEDULING_ITEMS,
    ...filterConductByRole('district_admin'),
  ],
  principal: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_ADMIN_ITEMS,
    ...JOINT_EXAM_ITEMS,
    ...ANALYTICS_ITEMS,
    ...CALENDAR_ITEMS,
    ...STUDENT_TEACHER_ITEMS,
    ...SCHOOL_CONFIG_ITEMS,
    ...SCHEDULING_ITEMS,
    ...filterConductByRole('principal'),
  ],
  academic_director: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_ADMIN_ITEMS,
    ...JOINT_EXAM_ITEMS,
    ...ANALYTICS_ITEMS,
    ...CALENDAR_ITEMS,
    ...STUDENT_TEACHER_ITEMS,
    ...SCHEDULING_ITEMS,
    ...filterConductByRole('academic_director'),
  ],
  teaching_research_leader: [
    { icon: 'dashboard', label: '概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    ...SUBJECT_LEAD_ITEMS,
    ...ANALYTICS_ITEMS,
    ...filterConductByRole('teaching_research_leader'),
  ],
  grade_leader: [
    { icon: 'dashboard', label: '概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    ...SUBJECT_LEAD_ITEMS,
    ...ANALYTICS_ITEMS,
    ...filterConductByRole('grade_leader'),
  ],
  lesson_prep_leader: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...SUBJECT_LEAD_ITEMS,
    ...ANALYTICS_ITEMS,
    ...filterConductByRole('lesson_prep_leader'),
  ],
  homeroom_teacher: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...TEACHER_GRADING_ITEMS,
    ...ANALYTICS_ITEMS,
    ...filterConductByRole('homeroom_teacher'),
  ],
  subject_teacher: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...TEACHER_GRADING_ITEMS,
    ...ANALYTICS_ITEMS,
    ...filterConductByRole('subject_teacher'),
  ],
  parent: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...filterConductByRole('parent'),
  ],
}

export function getSidebarItems(role) {
  return SIDEBAR_ITEMS[role] || SIDEBAR_ITEMS.subject_teacher
}
