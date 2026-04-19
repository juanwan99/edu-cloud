import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import { SCHOOL_ADMIN_ROLES, EXAM_ROLES, MARKING_ROLES, normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'

export const routes = [
  // Auth — outside AppShell
  { path: '/login', name: 'Login', component: () => import('../pages/LoginPage.vue') },

  // Parent portal — independent layout, no AppShell
  { path: '/parent/login', name: 'ParentLogin', component: () => import('../pages/parent/ParentLogin.vue') },
  { path: '/parent/register', name: 'ParentRegister', component: () => import('../pages/parent/ParentRegister.vue') },
  {
    path: '/parent',
    component: () => import('../layouts/ParentLayout.vue'),
    children: [
      { path: '', name: 'ParentOverview', component: () => import('../pages/parent/ParentOverview.vue') },
      { path: 'bind', name: 'ParentBind', component: () => import('../pages/parent/ParentBind.vue') },
      { path: 'details', name: 'ParentDetails', component: () => import('../pages/parent/ParentDetails.vue') },
      { path: 'rankings', name: 'ParentRankings', component: () => import('../pages/parent/ParentRankings.vue') },
      { path: 'rules', name: 'ParentRules', component: () => import('../pages/parent/ParentRules.vue') },
      { path: 'profile', name: 'ParentProfile', component: () => import('../pages/parent/ParentProfile.vue') },
    ]
  },

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

      // Analytics report & trend
      { path: 'analytics/report', name: 'AnalyticsReport', component: () => import('../pages/AnalyticsReportPage.vue'), meta: { permissions: ['view_scores'] } },
      { path: 'analytics/trend', name: 'AnalyticsTrend', component: () => import('../pages/AnalyticsTrendPage.vue'), meta: { permissions: ['view_scores'] } },
      // Analytics (parameterized — must come after literal paths)
      { path: 'analytics/:examId', name: 'Analytics', component: () => import('../pages/AnalyticsPage.vue'), meta: { roles: EXAM_ROLES } },

      // Manual marking + AI 校对（同一 ReviewPage；按题目维度进入）
      { path: 'marking', name: 'MarkingSelect', component: () => import('../pages/MarkingSelectPage.vue'), meta: { roles: MARKING_ROLES } },
      { path: 'marking/grade/:questionId', name: 'Review', component: () => import('../pages/ReviewPage.vue'), meta: { roles: MARKING_ROLES } },
      { path: 'marking/assign', name: 'MarkingAssign', component: () => import('../pages/MarkingAssignPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
      { path: 'marking/progress', name: 'MarkingProgress', component: () => import('../pages/MarkingProgressPage.vue'), meta: { roles: MARKING_ROLES } },

      // AI grading
      { path: 'grading/tasks', name: 'GradingDispatch', component: () => import('../pages/GradingDispatchPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },
      { path: 'grading/tasks/:id', name: 'GradingResults', component: () => import('../pages/GradingResultsPage.vue'), meta: { roles: SCHOOL_ADMIN_ROLES } },

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

      // Knowledge tree
      { path: 'knowledge-tree', name: 'KnowledgeTree', component: () => import('../pages/KnowledgeTreePage.vue'), meta: { permissions: ['view_knowledge_tree'] } },

      // Conduct management
      { path: 'conduct', name: 'ConductDashboard', component: () => import('../pages/conduct/ConductDashboard.vue'), meta: { permissions: ['view_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/points', name: 'ConductPoints', component: () => import('../pages/conduct/ConductPoints.vue'), meta: { permissions: ['manage_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/rules', name: 'ConductRules', component: () => import('../pages/conduct/ConductRules.vue'), meta: { permissions: ['manage_conduct_rules'], moduleCode: 'conduct' } },
      { path: 'conduct/rankings', name: 'ConductRankings', component: () => import('../pages/conduct/ConductRankings.vue'), meta: { permissions: ['view_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/records', name: 'ConductRecords', component: () => import('../pages/conduct/ConductRecords.vue'), meta: { permissions: ['view_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/groups', name: 'ConductGroups', component: () => import('../pages/conduct/ConductGroups.vue'), meta: { permissions: ['manage_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/settings', name: 'ConductSettings', component: () => import('../pages/conduct/ConductSettings.vue'), meta: { permissions: ['manage_conduct_parents'], moduleCode: 'conduct' } },
      { path: 'conduct/export', name: 'ConductExport', component: () => import('../pages/conduct/ConductExport.vue'), meta: { permissions: ['export_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/parents', name: 'ConductParents', component: () => import('../pages/conduct/ConductParents.vue'), meta: { permissions: ['manage_conduct_parents'], moduleCode: 'conduct' } },
    ]
  }
]

const router = createRouter({ history: createWebHistory(), routes })

export function authGuard(to, from, next) {
  // Parent portal has its own auth (cp_token), skip platform auth checks
  if (to.path.startsWith('/parent')) {
    return next()
  }

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
