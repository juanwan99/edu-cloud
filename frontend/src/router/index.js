import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  // Auth
  { path: '/login', name: 'Login', component: () => import('../pages/LoginPage.vue') },

  // Platform workbench (edu-cloud original)
  { path: '/', name: 'Workbench', component: () => import('../pages/WorkbenchPage.vue'), meta: { requiresAuth: true } },

  // Exam management (from exam-ai)
  { path: '/exams', name: 'ExamList', component: () => import('../pages/ExamListPage.vue'), meta: { requiresAuth: true } },
  { path: '/exams/:id', name: 'ExamDetail', component: () => import('../pages/ExamDetailPage.vue'), meta: { requiresAuth: true } },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../pages/DashboardPage.vue'), meta: { requiresAuth: true } },

  // Card editor
  { path: '/card-dev/:examId', name: 'CardEditorDev', component: () => import('../pages/CardEditorDevPage.vue'), meta: { requiresAuth: true } },

  // AI grading
  { path: '/grading/tasks', name: 'GradingTasks', component: () => import('../pages/GradingTasksPage.vue'), meta: { requiresAuth: true } },
  { path: '/grading/tasks/:id', name: 'GradingResults', component: () => import('../pages/GradingResultsPage.vue'), meta: { requiresAuth: true } },
  { path: '/grading/review', name: 'TeacherReview', component: () => import('../pages/TeacherReviewPage.vue'), meta: { requiresAuth: true } },

  // Manual marking
  { path: '/marking', name: 'MarkingSelect', component: () => import('../pages/MarkingSelectPage.vue'), meta: { requiresAuth: true } },
  { path: '/marking/grade/:questionId', name: 'Marking', component: () => import('../pages/MarkingPage.vue'), meta: { requiresAuth: true } },
  { path: '/marking/assign', name: 'MarkingAssign', component: () => import('../pages/MarkingAssignPage.vue'), meta: { requiresAuth: true } },
  { path: '/marking/progress', name: 'MarkingProgress', component: () => import('../pages/MarkingProgressPage.vue'), meta: { requiresAuth: true } },

  // Analytics
  { path: '/analytics/:examId', name: 'Analytics', component: () => import('../pages/AnalyticsPage.vue'), meta: { requiresAuth: true } },

  // Admin
  { path: '/schools', name: 'Schools', component: () => import('../pages/SchoolsPage.vue'), meta: { requiresAuth: true, adminOnly: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
