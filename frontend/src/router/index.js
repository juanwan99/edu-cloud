import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import { normalizeRole } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'
import { getRouteAccessRequirement } from '../config/routeAccess.js'
import clientLogger from '../utils/clientLogger.js'

function decodeJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + (4 - base64.length % 4) % 4, '=')
    return JSON.parse(atob(padded))
  } catch { return null }
}

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
      { path: 'workbench-preview', name: 'RoleWorkbenchPreview', component: () => import('../pages/RoleWorkbenchPreviewPage.vue') },

      // 考试
      { path: 'exam-import', name: 'ExamImport', component: () => import('../pages/ExamImportPage.vue'), meta: { permissions: ['import_exams'], moduleCode: 'exam' } },
      { path: 'exams', name: 'ExamList', component: () => import('../pages/ExamListPage.vue'), meta: { permissions: ['view_exams'], moduleCode: 'exam' } },
      { path: 'exams/:id', name: 'ExamDetail', component: () => import('../pages/ExamDetailPage.vue'), meta: { permissions: ['view_exams'], moduleCode: 'exam' } },
      { path: 'card-dev/:examId', name: 'CardEditorDev', component: () => import('../pages/CardEditorDevPage.vue'), meta: { permissions: ['manage_exams'], moduleCode: 'exam' } },

      // 阅卷
      { path: 'grading/tasks', name: 'GradingDispatch', component: () => import('../pages/GradingDispatchPage.vue'), meta: { permissions: ['manage_grading'], moduleCode: 'grading' } },
      { path: 'grading/tasks/:id', name: 'GradingResults', component: () => import('../pages/GradingResultsPage.vue'), meta: { permissions: ['manage_grading'], moduleCode: 'grading' } },
      { path: 'marking', name: 'MarkingSelect', component: () => import('../pages/MarkingSelectPage.vue'), meta: { permissions: ['view_grading'], moduleCode: 'grading' } },
      { path: 'marking/grade/:questionId', name: 'Review', component: () => import('../pages/ReviewPage.vue'), meta: { permissions: ['view_grading'], moduleCode: 'grading', shellMode: 'workspace' } },
      { path: 'marking/assign', redirect: { name: 'GradingDispatch', query: { tab: 'assign' } } },
      { path: 'marking/progress', redirect: { name: 'GradingDispatch', query: { tab: 'progress' } } },
      { path: 'ai-grading', name: 'AiGradingEntry',
        component: () => import('../pages/AiGradingPage.vue'),
        meta: { permissions: ['manage_grading'], moduleCode: 'grading' } },
      { path: 'exams/:examId/ai-grading/:subjectId', name: 'AiGrading',
        component: () => import('../pages/AiGradingPage.vue'),
        meta: { permissions: ['manage_grading'], moduleCode: 'grading' } },

      // 学生画像
      { path: 'profile/student/:studentId', name: 'StudentProfile', component: () => import('../pages/StudentProfilePage.vue'), meta: { permissions: ['view_scores'] } },

      // 知识图谱
      { path: 'knowledge-tree', name: 'KnowledgeTree', component: () => import('../pages/KnowledgeTreePage.vue'), meta: { permissions: ['view_knowledge_tree'], shellMode: 'workspace' } },

      // 题库
      { path: 'question-bank', name: 'QuestionBank', component: () => import('../pages/QuestionBankPage.vue'), meta: { permissions: ['view_question_bank'] } },

      // 错题本
      { path: 'error-book', name: 'ErrorBook', component: () => import('../pages/ErrorBookPage.vue'), meta: { permissions: ['view_scores'] } },

      // 联考管理
      { path: 'joint-exams', name: 'JointExams', component: () => import('../pages/JointExamPage.vue'), meta: { permissions: ['view_joint_exam'] } },
      { path: 'joint-exams/:id', name: 'JointExamDetail', component: () => import('../pages/JointExamDetailPage.vue'), meta: { permissions: ['view_joint_exam'] } },

      // 成绩分析
      { path: 'analytics/report', name: 'AnalyticsReport', component: () => import('../pages/AnalyticsReportPage.vue'), meta: { permissions: ['view_scores'], moduleCode: 'study_analytics' } },
      { path: 'analytics/ai-report', name: 'AiGradingReport', component: () => import('../pages/AiGradingReportPage.vue'), meta: { permissions: ['view_scores'], moduleCode: 'study_analytics' } },
      { path: 'analytics/trend', redirect: { name: 'AnalyticsReport', query: { tab: 'trend' } } },
      { path: 'analytics/grade', redirect: { name: 'AnalyticsReport', query: { tab: 'classes' } } },
      { path: 'analytics/:examId', name: 'Analytics', component: () => import('../pages/AnalyticsPage.vue'), meta: { permissions: ['view_scores'], moduleCode: 'study_analytics' } },
      { path: 'analytics', redirect: { name: 'AnalyticsReport' } },

      // 作业
      { path: 'homework', name: 'Homework', component: () => import('../pages/HomeworkPage.vue'), meta: { permissions: ['view_homework', 'manage_homework'] } },

      // 校历
      { path: 'calendar', name: 'Calendar', component: () => import('../pages/CalendarPage.vue'), meta: { permissions: ['view_scores'] } },

      // 教务管理
      { path: 'academic/semesters', name: 'Semesters', component: () => import('../pages/SemesterPage.vue'), meta: { permissions: ['manage_scheduling'] } },
      { path: 'academic/timetable', name: 'Timetable', component: () => import('../pages/TimetablePage.vue'), meta: { permissions: ['manage_scheduling'] } },
      { path: 'academic/teaching-plans', name: 'TeachingPlans', component: () => import('../pages/TeachingPlanPage.vue'), meta: { permissions: ['manage_scheduling'] } },

      // 人员信息
      { path: 'students', name: 'Students', component: () => import('../pages/StudentsPage.vue'), meta: { permissions: ['view_students', 'manage_scheduling'] } },
      { path: 'teachers', name: 'Teachers', component: () => import('../pages/TeachersPage.vue'), meta: { permissions: ['manage_teachers'] } },
      { path: 'schools', name: 'Schools', component: () => import('../pages/SchoolsPage.vue'), meta: { permissions: ['manage_schools'] } },
      { path: 'school-settings', name: 'SchoolSettings', component: () => import('../pages/SchoolSettingsPage.vue'), meta: { permissions: ['manage_school_config'] } },
      { path: 'assignments', name: 'TeacherAssignments', component: () => import('../pages/TeacherAssignmentsPage.vue'), meta: { permissions: ['manage_scheduling'] } },
      { path: 'selections', name: 'SubjectSelections', component: () => import('../pages/SubjectSelectionsPage.vue'), meta: { permissions: ['manage_scheduling'] } },

      // 德育管理 — 工作台 + 设置两个入口
      { path: 'conduct', name: 'ConductWorkbench', component: () => import('../pages/conduct/ConductWorkbench.vue'), meta: { permissions: ['view_conduct'], moduleCode: 'conduct' } },
      { path: 'conduct/settings', name: 'ConductSettingsHub', component: () => import('../pages/conduct/ConductSettingsHub.vue'), meta: { permissions: ['manage_conduct_rules'], moduleCode: 'conduct' } },
      // 旧路径重定向 → 工作台 Tab
      { path: 'conduct/points', redirect: { name: 'ConductWorkbench', query: { tab: 'points' } } },
      { path: 'conduct/records', redirect: { name: 'ConductWorkbench', query: { tab: 'records' } } },
      { path: 'conduct/rankings', redirect: { name: 'ConductWorkbench', query: { tab: 'rankings' } } },
      { path: 'conduct/export', redirect: { name: 'ConductWorkbench', query: { tab: 'records' } } },
      // 旧路径重定向 → 设置 Tab
      { path: 'conduct/rules', redirect: { name: 'ConductSettingsHub', query: { tab: 'rules' } } },
      { path: 'conduct/groups', redirect: { name: 'ConductSettingsHub', query: { tab: 'groups' } } },
      { path: 'conduct/parents', redirect: { name: 'ConductSettingsHub', query: { tab: 'parents' } } },

      // 超管工具
      { path: 'admin/impersonate', name: 'Impersonate', component: () => import('../pages/ImpersonatePage.vue'), meta: { permissions: ['impersonate_roles'] } },
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
      { path: 'conduct', name: 'ParentConduct', component: () => import('../pages/parent/ParentConduct.vue') },
      { path: 'profile', name: 'ParentProfile', component: () => import('../pages/parent/ParentProfile.vue') },
      // Redirects for old routes — preserve semantic via query tab
      { path: 'rankings', redirect: { name: 'ParentConduct', query: { tab: 'rankings' } } },
      { path: 'rules', redirect: { name: 'ParentConduct', query: { tab: 'rules' } } },
      { path: 'details', redirect: { name: 'ParentConduct', query: { tab: 'records' } } },
    ]
  },

  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

export async function authGuard(to, from, next) {
  if (to.path.startsWith('/parent')) return next()

  const requiresAuth = to.matched.some(r => r.meta.requiresAuth)
  let token = localStorage.getItem('token')

  if (token) {
    const payload = decodeJwtPayload(token)
    if (!payload || (payload.exp && payload.exp * 1000 < Date.now())) {
      localStorage.removeItem('token')
      localStorage.removeItem('auth_state')
      token = null
    }
  }

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

  // Phase 0.6 直达 URL 模块门控（fail-closed）：roles/permissions 通过后，按学校 enabledModules 二次门控，
  // 堵住「有权限但模块已关」经直达 URL 绕过 sidebar/routeAccess 的缺口。
  //   moduleCode 真源：routeAccess（静态 route 全覆盖）∪ to.meta.moduleCode（动态路由 /exams/:id 等，
  //     getRouteAccessRequirement 精确 key 不匹配模板，靠 Vue Router 合并的 meta 兜底，F-001 R3）。
  //   DP1：modulesLoaded=false（刷新瞬间）先 await loadModules，不在加载空窗放行。
  //   F-002 R3 fail-closed：有 school_id 的登录用户，模块态必须「已成功加载且 moduleCode 在真实启用列表」，
  //     否则拦截（不再因 enabledModules 空/加载失败而放行）。admin/平台角色无 school_id → 不受学校模块限制（保留）。
  //   DP2：命中拦截 → next('/')。moduleCode 缺失 / null route（不受门控）→ 跳过。
  const requirement = getRouteAccessRequirement(to.path)
  const moduleCode = requirement?.moduleCode || to.meta?.moduleCode
  if (moduleCode) {
    const { useAuthStore } = await import('../stores/auth.js')
    const auth = useAuthStore()
    if (!auth.modulesLoaded) {
      try { await auth.loadModules() } catch { /* 失败→enabledModules 空，有校身份下方 fail-closed 拦截 */ }
    }
    const hasSchool = !!auth.currentRole?.school_id
    if (hasSchool && !(auth.modulesLoaded && auth.enabledModules.includes(moduleCode))) {
      return next('/')
    }
  }
  next()
}

router.beforeEach(authGuard)

router.onError((err, to) => {
  clientLogger.routeError(err, to)
  if (err.message?.includes('Failed to fetch dynamically imported module') ||
      err.message?.includes('Importing a module script failed') ||
      err.message?.includes('error loading dynamically imported module') ||
      err.name === 'ChunkLoadError') {
    const reloaded = sessionStorage.getItem('chunk_reload')
    if (reloaded !== to.fullPath) {
      sessionStorage.setItem('chunk_reload', to.fullPath)
      window.location.assign(to.fullPath)
    }
  }
})

export default router
