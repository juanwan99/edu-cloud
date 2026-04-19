// Frozen 2026-04-19: only exam + grading + personnel
// Full version: config/_frozen/sidebarConfig.full.js

const EXAM_GRADING_ITEMS = [
  { icon: 'exam', label: '考试管理', route: '/exams' },
  { icon: 'marking', label: '阅卷分派', route: '/grading/tasks' },
  { icon: 'marking', label: '阅卷', route: '/marking' },
  { icon: 'marking', label: '阅卷分配', route: '/marking/assign' },
  { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
]

const PERSONNEL_ITEMS = [
  { icon: 'school', label: '学校管理', route: '/schools' },
  { icon: 'settings', label: '学校配置', route: '/school-settings' },
  { icon: 'settings', label: '教师分配', route: '/assignments' },
  { icon: 'exam', label: '选科管理', route: '/selections' },
]

const SIDEBAR_ITEMS = {
  platform_admin: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_GRADING_ITEMS,
    ...PERSONNEL_ITEMS,
  ],
  district_admin: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_GRADING_ITEMS,
    ...PERSONNEL_ITEMS,
  ],
  principal: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_GRADING_ITEMS,
    ...PERSONNEL_ITEMS,
  ],
  academic_director: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_GRADING_ITEMS,
    ...PERSONNEL_ITEMS,
  ],
  teaching_research_leader: [
    { icon: 'dashboard', label: '概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'marking', label: '阅卷', route: '/marking' },
    { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
  ],
  grade_leader: [
    { icon: 'dashboard', label: '概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'marking', label: '阅卷', route: '/marking' },
    { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
  ],
  lesson_prep_leader: [
    { icon: 'dashboard', label: '概览', route: '/' },
    ...EXAM_GRADING_ITEMS,
  ],
  homeroom_teacher: [
    { icon: 'dashboard', label: '概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'marking', label: '阅卷', route: '/marking' },
    { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
  ],
  subject_teacher: [
    { icon: 'dashboard', label: '概览', route: '/' },
    { icon: 'exam', label: '考试管理', route: '/exams' },
    { icon: 'marking', label: '阅卷', route: '/marking' },
    { icon: 'marking', label: '阅卷进度', route: '/marking/progress' },
  ],
  parent: [
    { icon: 'dashboard', label: '概览', route: '/' },
  ],
}

export function getSidebarItems(role) {
  return SIDEBAR_ITEMS[role] || SIDEBAR_ITEMS.subject_teacher
}
