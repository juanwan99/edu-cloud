import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import { SCHOOL_ADMIN_ROLES, EXAM_ROLES, MARKING_ROLES, normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'

export const routes = [
  // Auth — outside AppShell
  { path: '/login', name: 'Login', component: () => import('../pages/LoginPage.vue') },

  // All authenticated routes under AppShell
  {
    path: '/',
    component: AppShell,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('../pages/DashboardPage.vue') },

      // Exam management
      { path: 'exams', name: 'ExamList', component: () => import('../pages/ExamListPage.vue'), meta: { roles: EXAM_ROLES } },
      { path: 'exams/:id', name: 'ExamDetail', component: () => import('../pages/ExamDetailPage.vue'), meta: { roles: EXAM_ROLES } },

      // Card editor
      { path: 'card-dev/:examId', name: 'CardEditorDev', component: () => import('../pages/CardEditorDevPage.vue'), meta: { roles: EXAM_ROLES } },

      // Analytics
      { path: 'analytics/:examId', name: 'Analytics', component: () => import('../pages/AnalyticsPage.vue'), meta: { roles: EXAM_ROLES } },

      // Manual marking
      { path: 'marking', name: 'MarkingSelect', component: () => import('../pages/MarkingSelectPage.vue'), meta: { roles: MARKING_ROLES } },
      { path: 'marking/grade/:questionId', name: 'Marking', component: () => import('../pages/MarkingPage.vue'), meta: { roles: MARKING_ROLES } },
      { path: 'marking/assign', name: 'MarkingAssign', component: () => import('../pages/MarkingAssignPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
      { path: 'marking/progress', name: 'MarkingProgress', component: () => import('../pages/MarkingProgressPage.vue'), meta: { roles: MARKING_ROLES } },

      // AI grading
      { path: 'grading/tasks', name: 'GradingTasks', component: () => import('../pages/GradingTasksPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
      { path: 'grading/tasks/:id', name: 'GradingResults', component: () => import('../pages/GradingResultsPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
      { path: 'grading/review', name: 'TeacherReview', component: () => import('../pages/TeacherReviewPage.vue'), meta: { roles: [...SCHOOL_ADMIN_ROLES, 'subject_teacher', 'homeroom_teacher'] } },

      // Platform workbench (AI analysis)
      { path: 'analysis', name: 'Analysis', component: () => import('../pages/AnalysisPage.vue'), meta: { permissions: ['use_ai_chat'] } },

      // Teacher assignments & subject selections
      { path: 'assignments', name: 'TeacherAssignments', component: () => import('../pages/TeacherAssignmentsPage.vue'), meta: { roles: ['principal', 'academic_director'] } },
      { path: 'selections', name: 'SubjectSelections', component: () => import('../pages/SubjectSelectionsPage.vue'), meta: { roles: ['principal', 'academic_director'] } },

      // School settings (school-scoped admin roles)
      { path: 'school-settings', name: 'SchoolSettings', component: () => import('../pages/SchoolSettingsPage.vue'), meta: { roles: ['principal', 'academic_director'] } },

      // Admin
      { path: 'schools', name: 'Schools', component: () => import('../pages/SchoolsPage.vue'), meta: { permissions: ['manage_schools'] } },
      { path: 'settings', name: 'Settings', component: () => import('../pages/DashboardPage.vue') },

      // Placeholder routes (sidebar navigation targets)
      { path: 'studio', name: 'Studio', component: () => import('../pages/AnalysisPage.vue'), meta: { permissions: ['use_ai_chat'] } },
      { path: 'calendar', name: 'Calendar', component: () => import('../pages/DashboardPage.vue') },
      { path: 'notifications', name: 'Notifications', component: () => import('../pages/DashboardPage.vue') },
      { path: 'paper', name: 'Paper', component: () => import('../pages/AnalysisPage.vue'), meta: { permissions: ['use_ai_chat'] } },
    ]
  }
]

const router = createRouter({ history: createWebHistory(), routes })

export function authGuard(to, from, next) {
  const requiresAuth = to.matched.some(r => r.meta.requiresAuth)
  const token = localStorage.getItem('token')

  if (requiresAuth && !token) {
    return next('/login')
  }

  if (token && to.path === '/login') {
    return next('/')
  }

  // Role/permission check for authenticated routes (fail-closed: deny if auth_state missing/corrupt)
  const meta = to.meta
  if (meta.roles || meta.permissions) {
    const authState = localStorage.getItem('auth_state')
    if (!authState) {
      return next('/')
    }
    try {
      const { roles, currentRoleIndex } = JSON.parse(authState)
      const currentRole = roles?.[currentRoleIndex]
      const roleName = normalizeRole(currentRole?.role || '')

      if (meta.roles && !meta.roles.includes(roleName)) {
        return next('/')
      }
      if (meta.permissions) {
        const allowed = meta.permissions.some(p => hasPermission(roleName, p))
        if (!allowed) return next('/')
      }
    } catch {
      return next('/')
    }
  }

  next()
}

router.beforeEach(authGuard)

export default router
