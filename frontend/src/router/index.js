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
      { path: 'exams/:examId/ai-grading/:subjectId', name: 'AiGrading',
        component: () => import('../pages/AiGradingPage.vue'),
        meta: { roles: GRADING_DISPATCH_ROLES } },

      // 人员信息
      { path: 'students', name: 'Students', component: () => import('../pages/StudentsPage.vue'), meta: { permissions: ['view_students', 'manage_scheduling'] } },
      { path: 'teachers', name: 'Teachers', component: () => import('../pages/TeachersPage.vue'), meta: { permissions: ['manage_scheduling', 'manage_school_config'] } },
      { path: 'schools', name: 'Schools', component: () => import('../pages/SchoolsPage.vue'), meta: { permissions: ['manage_schools'] } },
      { path: 'school-settings', name: 'SchoolSettings', component: () => import('../pages/SchoolSettingsPage.vue'), meta: { permissions: ['manage_school_config'] } },
      { path: 'assignments', name: 'TeacherAssignments', component: () => import('../pages/TeacherAssignmentsPage.vue'), meta: { permissions: ['manage_scheduling'] } },
      { path: 'selections', name: 'SubjectSelections', component: () => import('../pages/SubjectSelectionsPage.vue'), meta: { permissions: ['manage_scheduling'] } },
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
