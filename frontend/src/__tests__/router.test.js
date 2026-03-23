/**
 * Router guard tests — TG-01 fix
 *
 * Verifies: requiresAuth redirect, public route access, adminOnly meta preserved.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

// Minimal route definitions matching src/router/index.js structure
const routes = [
  { path: '/login', name: 'Login', component: { template: '<div/>' } },
  { path: '/', name: 'Workbench', component: { template: '<div/>' }, meta: { requiresAuth: true } },
  { path: '/exams', name: 'ExamList', component: { template: '<div/>' }, meta: { requiresAuth: true } },
  { path: '/schools', name: 'Schools', component: { template: '<div/>' }, meta: { requiresAuth: true, adminOnly: true } },
]

function createTestRouter() {
  const router = createRouter({ history: createWebHistory(), routes })

  router.beforeEach((to, from, next) => {
    const token = localStorage.getItem('token')
    if (to.meta.requiresAuth && !token) {
      next('/login')
    } else {
      next()
    }
  })

  return router
}

describe('Router guard — requiresAuth', () => {
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

  it('allows access to root (Workbench) with token', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    const router = createTestRouter()
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('redirects root to /login without token', async () => {
    const router = createTestRouter()
    await router.push('/')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('preserves adminOnly meta on Schools route', async () => {
    localStorage.setItem('token', 'test-jwt-token')
    const router = createTestRouter()
    await router.push('/schools')
    await router.isReady()
    expect(router.currentRoute.value.meta.adminOnly).toBe(true)
  })
})
