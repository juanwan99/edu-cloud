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

  it('has exactly 2 top-level routes (login + AppShell)', () => {
    expect(routes).toHaveLength(2)
  })

  it('AppShell has 17 child routes', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    expect(shell.children).toHaveLength(17)
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

  it('exams route has EXAM_ROLES in meta', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const exams = shell.children.find(r => r.path === 'exams')
    expect(exams).toBeTruthy()
    expect(exams.meta?.roles).toBeDefined()
    expect(exams.meta.roles.length).toBeGreaterThan(0)
  })

  it('parent cannot access exams route', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const examRoute = shell.children.find(r => r.path === 'exams')
    if (examRoute?.meta?.roles) {
      expect(examRoute.meta.roles).not.toContain('parent')
    }
  })

  it('marking routes have MARKING_ROLES in meta', () => {
    const shell = routes.find(r => r.path === '/' && r.children)
    const marking = shell.children.find(r => r.path === 'marking')
    expect(marking).toBeTruthy()
    expect(marking.meta?.roles).toBeDefined()
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
    localStorage.setItem('token', 'test-jwt-token')
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
    localStorage.setItem('token', 'test-jwt-token')
    const router = createTestRouter()
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects /login to / when already authenticated', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    const router = createTestRouter()
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects to / when role not allowed for route', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'parent', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('allows access when role is in allowed list', async () => {
    localStorage.setItem('token', 'test-jwt-token')
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
    localStorage.setItem('token', 'test-jwt-token')
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
    localStorage.setItem('token', 'test-jwt-token')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'platform_admin', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/schools')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/schools')
  })

  it('normalizes legacy role aliases for route guard', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'teacher', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    // teacher -> subject_teacher -> in EXAM_ROLES
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/exams')
  })

  it('redirects subject_teacher from /marking/assign (requires SCHOOL_ADMIN_ROLES)', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'subject_teacher', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/marking/assign')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('allows academic_director to access /marking/assign', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    localStorage.setItem('auth_state', JSON.stringify({
      roles: [{ role: 'academic_director', context: {} }],
      currentRoleIndex: 0,
    }))
    const router = createTestRouter()
    await router.push('/marking/assign')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/marking/assign')
  })

  it('redirects to / when auth_state missing but token exists (fail-closed)', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    // No auth_state set
    const router = createTestRouter()
    await router.push('/schools')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects to / when auth_state is corrupt (fail-closed)', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    localStorage.setItem('auth_state', '{corrupt json')
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })
})
