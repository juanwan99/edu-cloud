import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import { SCHOOL_ADMIN_ROLES, EXAM_ROLES, MARKING_ROLES, GRADING_DISPATCH_ROLES, normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'

// Frozen 2026-04-19: only exam + grading + personnel
// Full version: router/_frozen/index.full.js

export const routes = [
  { path: '/login', name: 'Login', component: () => import('../pages/LoginPage.vue') },

  {
    path: '/',
    component: AppShell,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('../pages/DashboardPage.vue') },

      // 考试
      { path: 'exams', name: 'ExamList', component: () => import('../pages/ExamListPage.vue'), meta: { roles: EXAM_ROLES } },
      { path: 'exams/:id', name: 'ExamDetail', component: () => import('../pages/ExamDetailPage.vue'), meta: { roles: EXAM_ROLES } },
      { path: 'card-dev/:examId', name: 'CardEditorDev', component: () => import('../pages/CardEditorDevPage.vue'), meta: { roles: EXAM_ROLES } },

      // 阅卷
      { path: 'grading/tasks', name: 'GradingDispatch', component: () => import('../pages/GradingDispatchPage.vue'), meta: { roles: GRADING_DISPATCH_ROLES } },
      { path: 'grading/tasks/:id', name: 'GradingResults', component: () => import('../pages/GradingResultsPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
      { path: 'marking', name: 'MarkingSelect', component: () => import('../pages/MarkingSelectPage.vue'), meta: { roles: MARKING_ROLES } },
      { path: 'marking/grade/:questionId', name: 'Review', component: () => import('../pages/ReviewPage.vue'), meta: { roles: MARKING_ROLES } },
      { path: 'marking/assign', name: 'MarkingAssign', component: () => import('../pages/MarkingAssignPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
      { path: 'marking/progress', name: 'MarkingProgress', component: () => import('../pages/MarkingProgressPage.vue'), meta: { roles: MARKING_ROLES } },
      { path: 'ai-grading', name: 'AiGradingEntry',
        component: () => import('../pages/AiGradingPage.vue'),
        meta: { roles: GRADING_DISPATCH_ROLES } },
      { path: 'exams/:examId/ai-grading/:subjectId', name: 'AiGrading',
        component: () => import('../pages/AiGradingPage.vue'),
        meta: { roles: GRADING_DISPATCH_ROLES } },

      // 学生画像
      { path: 'profile/student/:studentId', name: 'StudentProfile', component: () => import('../pages/StudentProfilePage.vue'), meta: { permissions: ['view_scores'] } },

      // 知识图谱
      { path: 'knowledge-tree', name: 'KnowledgeTree', component: () => import('../pages/KnowledgeTreePage.vue'), meta: { permissions: ['view_knowledge_tree'] } },

      // 题库
      { path: 'question-bank', name: 'QuestionBank', component: () => import('../pages/QuestionBankPage.vue'), meta: { permissions: ['view_question_bank'] } },

      // 错题本
      { path: 'error-book', name: 'ErrorBook', component: () => import('../pages/ErrorBookPage.vue'), meta: { permissions: ['view_scores'] } },

      // 联考管理
      { path: 'joint-exams', name: 'JointExams', component: () => import('../pages/JointExamPage.vue'), meta: { permissions: ['view_joint_exam'] } },
      { path: 'joint-exams/:id', name: 'JointExamDetail', component: () => import('../pages/JointExamDetailPage.vue'), meta: { permissions: ['view_joint_exam'] } },

      // 成绩分析
      { path: 'analytics/report', name: 'AnalyticsReport', component: () => import('../pages/AnalyticsReportPage.vue'), meta: { permissions: ['view_scores'] } },
      { path: 'analytics/trend', name: 'AnalyticsTrend', component: () => import('../pages/AnalyticsTrendPage.vue'), meta: { permissions: ['view_scores'] } },
      { path: 'analytics/grade', name: 'GradeAnalytics', component: () => import('../pages/GradeAnalyticsPage.vue'), meta: { permissions: ['view_scores'] } },
      { path: 'analytics/:examId', name: 'Analytics', component: () => import('../pages/AnalyticsPage.vue'), meta: { roles: EXAM_ROLES } },

      // 作业
      { path: 'homework', name: 'Homework', component: () => import('../pages/HomeworkPage.vue'), meta: { permissions: ['manage_grading'] } },

      // 校历
      { path: 'calendar', name: 'Calendar', component: () => import('../pages/CalendarPage.vue'), meta: { permissions: ['view_scores'] } },

      // 教务管理
      { path: 'academic/semesters', name: 'Semesters', component: () => import('../pages/SemesterPage.vue'), meta: { permissions: ['manage_scheduling'] } },
      { path: 'academic/timetable', name: 'Timetable', component: () => import('../pages/TimetablePage.vue'), meta: { permissions: ['manage_scheduling'] } },
      { path: 'academic/teaching-plans', name: 'TeachingPlans', component: () => import('../pages/TeachingPlanPage.vue'), meta: { permissions: ['manage_scheduling'] } },

      // 人员信息
      { path: 'students', name: 'Students', component: () => import('../pages/StudentsPage.vue'), meta: { permissions: ['view_students', 'manage_scheduling'] } },
      { path: 'teachers', name: 'Teachers', component: () => import('../pages/TeachersPage.vue'), meta: { permissions: ['manage_scheduling', 'manage_school_config'] } },
      { path: 'schools', name: 'Schools', component: () => import('../pages/SchoolsPage.vue'), meta: { permissions: ['manage_schools'] } },
      { path: 'school-settings', name: 'SchoolSettings', component: () => import('../pages/SchoolSettingsPage.vue'), meta: { permissions: ['manage_school_config'] } },
      { path: 'assignments', name: 'TeacherAssignments', component: () => import('../pages/TeacherAssignmentsPage.vue'), meta: { permissions: ['manage_scheduling'] } },
      { path: 'selections', name: 'SubjectSelections', component: () => import('../pages/SubjectSelectionsPage.vue'), meta: { permissions: ['manage_scheduling'] } },

      // 德育管理
      { path: 'conduct', name: 'ConductDashboard', component: () => import('../pages/conduct/ConductDashboard.vue'), meta: { permissions: ['view_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/points', name: 'ConductPoints', component: () => import('../pages/conduct/ConductPoints.vue'), meta: { permissions: ['manage_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/rules', name: 'ConductRules', component: () => import('../pages/conduct/ConductRules.vue'), meta: { permissions: ['manage_conduct_rules'], moduleCode: 'conduct' } },
      { path: 'conduct/rankings', name: 'ConductRankings', component: () => import('../pages/conduct/ConductRankings.vue'), meta: { permissions: ['view_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/records', name: 'ConductRecords', component: () => import('../pages/conduct/ConductRecords.vue'), meta: { permissions: ['view_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/groups', name: 'ConductGroups', component: () => import('../pages/conduct/ConductGroups.vue'), meta: { permissions: ['manage_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/settings', name: 'ConductSettings', component: () => import('../pages/conduct/ConductSettings.vue'), meta: { permissions: ['manage_conduct_rules'], moduleCode: 'conduct' } },
      { path: 'conduct/export', name: 'ConductExport', component: () => import('../pages/conduct/ConductExport.vue'), meta: { permissions: ['export_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/parents', name: 'ConductParents', component: () => import('../pages/conduct/ConductParents.vue'), meta: { permissions: ['manage_conduct_parents'], moduleCode: 'conduct' } },
    ]
  },

  // 家长端
  { path: '/parent/login', name: 'ParentLogin', component: () => import('../pages/parent/ParentLogin.vue') },
  { path: '/parent/register', name: 'ParentRegister', component: () => import('../pages/parent/ParentRegister.vue') },
  {
    path: '/parent',
    component: () => import('../layouts/ParentLayout.vue'),
    children: [
      { path: '', name: 'ParentOverview', component: () => import('../pages/parent/ParentOverview.vue') },
      { path: 'bind', name: 'ParentBind', component: () => import('../pages/parent/ParentBind.vue') },
      { path: 'scores', name: 'ParentScores', component: () => import('../pages/parent/ParentScores.vue') },
      { path: 'details', name: 'ParentDetails', component: () => import('../pages/parent/ParentDetails.vue') },
      { path: 'rankings', name: 'ParentRankings', component: () => import('../pages/parent/ParentRankings.vue') },
      { path: 'rules', name: 'ParentRules', component: () => import('../pages/parent/ParentRules.vue') },
      { path: 'profile', name: 'ParentProfile', component: () => import('../pages/parent/ParentProfile.vue') },
    ]
  },

  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

export function authGuard(to, from, next) {
  if (to.path.startsWith('/parent')) return next()

  const requiresAuth = to.matched.some(r => r.meta.requiresAuth)
  const token = localStorage.getItem('token')

  if (requiresAuth && !token) return next('/login')
  if (token && to.path === '/login') return next('/')

  const meta = to.meta
  if (meta.roles || meta.permissions) {
    const authState = localStorage.getItem('auth_state')
    if (!authState) return next('/')
    try {
      const { roles, currentRoleIndex } = JSON.parse(authState)
      const currentRole = roles?.[currentRoleIndex]
      const roleName = normalizeRole(currentRole?.role || '')
      if (meta.roles && !meta.roles.includes(roleName)) return next('/')
      if (meta.permissions) {
        const allowed = meta.permissions.some(p => hasPermission(roleName, p))
        if (!allowed) return next('/')
      }
    } catch { return next('/') }
  }
  next()
}

router.beforeEach(authGuard)
export default router
