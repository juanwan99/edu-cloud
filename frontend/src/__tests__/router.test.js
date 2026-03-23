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
const stubbedRoutes = routes.map(r => ({
  ...r,
  component: { template: '<div/>' },
}))

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

  it('all non-login routes require auth', () => {
    const protectedRoutes = routes.filter(r => r.path !== '/login')
    for (const route of protectedRoutes) {
      expect(route.meta?.requiresAuth, `${route.path} should require auth`).toBe(true)
    }
  })

  it('schools route has adminOnly meta', () => {
    const schools = routes.find(r => r.path === '/schools')
    expect(schools).toBeTruthy()
    expect(schools.meta?.adminOnly).toBe(true)
  })

  it('has exactly 15 routes', () => {
    expect(routes).toHaveLength(15)
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

  it('allows access to protected route with token', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    const router = createTestRouter()
    await router.push('/exams')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/exams')
  })

  it('redirects root (Workbench) to /login without token', async () => {
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
})
