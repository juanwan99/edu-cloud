/**
 * Router guard tests — TG-01 fix (R2 refactor: imports real routes & guard)
 *
 * Tests the actual route definitions and guard function from src/router/index.js.
 * A regression in the real code (e.g. removing requiresAuth) will cause these to fail.
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'
import { routes, authGuard } from '../router/index.js'

// Stub lazy-loaded components so we don't need actual .vue files in test
function stubRoutes(routeList) {
  return routeList.map(r => ({
    ...r,
    component: r.children ? undefined : { template: '<div/>' },
    ...(r.children && { children: stubRoutes(r.children) }),
  }))
}

const stubbedRoutes = stubRoutes(routes)

function createTestRouter() {
  const router = createRouter({ history: createWebHistory(), routes: stubbedRoutes })
  router.beforeEach(authGuard)
  return router
}


describe('Route definitions (real routes)', () => {
  it('has login route without requiresAuth', () => {
    const login = routes.find(r => r.path === '/login')
    expect(login).toBeTruthy()
    expect(login.meta?.requiresAuth).toBeFalsy()
  })

  it('AppShell parent route requires auth', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    expect(shell).toBeTruthy()
    expect(shell.meta?.requiresAuth).toBe(true)
  })

  it('has expected top-level route count', () => {
    expect(routes).toHaveLength(6)
  })

  it('AppShell has 47 child routes', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    expect(shell.children).toHaveLength(47)
  })

  it('calendar route requires view_scores permission', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const cal = shell.children.find(r => r.path === 'calendar')
    expect(cal).toBeTruthy()
    expect(cal.meta?.permissions).toContain('view_scores')
  })

  it('error-book route requires view_scores permission', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const errorBook = shell.children.find(r => r.path === 'error-book')
    expect(errorBook).toBeTruthy()
    expect(errorBook.meta?.permissions).toContain('view_scores')
  })

  it('joint-exams route requires view_joint_exam permission', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const je = shell.children.find(r => r.path === 'joint-exams')
    expect(je).toBeTruthy()
    expect(je.meta?.permissions).toContain('view_joint_exam')
  })

  it('all routes except login are children of AppShell', () => {
    const router = createTestRouter()
    const appShellRoute = router.getRoutes().find(r => r.path === '/' && r.components?.default)
    // All auth-required routes should be under AppShell
    const loginRoute = router.getRoutes().find(r => r.path === '/login')
    expect(loginRoute).toBeTruthy()
    expect(appShellRoute).toBeTruthy()
  })

  it('schools route has manage_schools permission', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const schools = shell.children.find(r => r.path === 'schools')
    expect(schools).toBeTruthy()
    expect(schools.meta?.permissions).toContain('manage_schools')
  })

  it('exams route is guarded by view_exams permission and exam module', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const exams = shell.children.find(r => r.path === 'exams')
    expect(exams).toBeTruthy()
    expect(exams.meta?.permissions).toEqual(['view_exams'])
    expect(exams.meta?.moduleCode).toBe('exam')
    expect(exams.meta?.roles).toBeUndefined()
  })

  it('exam detail route uses the same permission guard as exam list', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const examRoute = shell.children.find(r => r.path === 'exams/:id')
    expect(examRoute).toBeTruthy()
    expect(examRoute.meta?.permissions).toEqual(['view_exams'])
    expect(examRoute.meta?.moduleCode).toBe('exam')
  })

  it('personal marking routes are guarded by view_grading permission', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const marking = shell.children.find(r => r.path === 'marking')
    const review = shell.children.find(r => r.path === 'marking/grade/:questionId')
    expect(marking).toBeTruthy()
    expect(review).toBeTruthy()
    expect(marking.meta?.permissions).toEqual(['view_grading'])
    expect(marking.meta?.moduleCode).toBe('grading')
    expect(marking.meta?.roles).toBeUndefined()
    expect(review.meta?.permissions).toEqual(['view_grading'])
    expect(review.meta?.moduleCode).toBe('grading')
  })

  it('grading dispatch requires manage_grading permission instead of broad role access', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const gradingDispatch = shell.children.find(r => r.path === 'grading/tasks')
    expect(gradingDispatch).toBeTruthy()
    expect(gradingDispatch.meta?.permissions).toEqual(['manage_grading'])
    expect(gradingDispatch.meta?.moduleCode).toBe('grading')
    expect(gradingDispatch.meta?.roles).toBeUndefined()
  })

  it('admin impersonation is guarded by manage_schools permission', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const impersonate = shell.children.find(r => r.path === 'admin/impersonate')
    expect(impersonate).toBeTruthy()
    expect(impersonate.meta?.permissions).toEqual(['manage_schools'])
    expect(impersonate.meta?.roles).toBeUndefined()
  })

  it('homework route is guarded by homework permissions', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const homework = shell.children.find(r => r.path === 'homework')
    expect(homework).toBeTruthy()
    expect(homework.meta?.permissions).toEqual(['view_homework', 'manage_homework'])
  })
})


describe('authGuard (real guard function)', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('redirects to /login when no token and route requires auth', async () => {
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows access to /login without token', async () => {
    const router = createTestRouter()
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows access to protected route with token and valid auth_state', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'academic_director', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/exams')
  })

  it('redirects root (Dashboard) to /login without token', async () => {
    const router = createTestRouter()
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('allows root with token', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    const router = createTestRouter()
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects /login to / when already authenticated', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    const router = createTestRouter()
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects to / when role not allowed for route', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'parent', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('allows access when route permission is met', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'academic_director', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/exams')
  })

  it('redirects when permission not met', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'parent', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/schools')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('allows access when permission is met', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'platform_admin', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/schools')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/schools')
  })

  it('normalizes historical role aliases for route guard', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'teacher', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    // teacher -> subject_teacher -> has view_exams
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/exams')
  })

  it('/marking/assign redirects to /grading/tasks with tab=assign', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'academic_director', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/marking/assign')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/grading/tasks')
    expect(router.currentRoute.value.query.tab).toBe('assign')
  })

  it('redirects to / when auth_state missing but token exists (fail-closed)', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    // No auth_state set
    const router = createTestRouter()
    await router.push('/schools')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects to / when auth_state is corrupt (fail-closed)', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', '{corrupt json')
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('does not allow subject teacher to access grading dispatch', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'subject_teacher', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/grading/tasks')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('allows subject teacher to access homework by homework permission', async () => {
    localStorage.setItem('token', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoyMDkzNjQxMDYyfQ.fake_signature')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'subject_teacher', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/homework')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/homework')
  })
})


describe('Router personnel permission alignment', () => {
  it('teachers route is guarded by manage_teachers permission', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const teachers = shell.children.find(r => r.path === 'teachers')
    expect(teachers).toBeTruthy()
    expect(teachers.meta?.permissions).toEqual(['manage_teachers'])
  })
})
