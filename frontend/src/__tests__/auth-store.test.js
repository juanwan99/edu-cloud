import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth.js'

describe('auth store persistence', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('hydrates state from localStorage on init', () => {
    const saved = {
      user: { id: '1', display_name: 'Test' },
      roles: [{ id: 'r1', role: 'principal', context: { type: 'school', name: '测试校' } }],
      currentRoleIndex: 0
    }
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    expect(store.user).toEqual(saved.user)
    expect(store.roles).toHaveLength(1)
  })

  it('ignores corrupt auth_state gracefully', () => {
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', '{bad json')
    const store = useAuthStore()
    expect(store.user).toBeNull()
    expect(store.roles).toEqual([])
  })

  it('clears auth_state on logout', () => {
    localStorage.setItem('auth_state', '{}')
    localStorage.setItem('token', 'test')
    const store = useAuthStore()
    store.logout()
    expect(localStorage.getItem('auth_state')).toBeNull()
    expect(localStorage.getItem('token')).toBeNull()
  })
})

describe('auth store role normalization', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('isAdmin recognizes legacy "admin" role via normalization', () => {
    const saved = {
      user: { id: '1', display_name: 'Admin' },
      roles: [{ id: 'r1', role: 'admin', context: null }],
      currentRoleIndex: 0
    }
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    expect(store.isAdmin).toBe(true)
  })

  it('currentContext returns role context object', () => {
    const ctx = { type: 'school', id: 's1', name: '北京一中' }
    const saved = {
      user: { id: '1', display_name: 'Test' },
      roles: [{ id: 'r1', role: 'principal', context: ctx }],
      currentRoleIndex: 0
    }
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    expect(store.currentContext).toEqual(ctx)
  })

  it('currentContext returns null when role has no context', () => {
    const saved = {
      user: { id: '1', display_name: 'Test' },
      roles: [{ id: 'r1', role: 'principal' }],
      currentRoleIndex: 0
    }
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    expect(store.currentContext).toBeNull()
  })
})

describe('auth store hasPermission', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('checks permission against current role', () => {
    const saved = {
      user: { id: '1', display_name: 'Admin' },
      roles: [{ id: 'r1', role: 'platform_admin', context: null }],
      currentRoleIndex: 0
    }
    localStorage.setItem('token', 'fake-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    expect(store.checkPermission('manage_schools')).toBe(true)
    expect(store.checkPermission('nonexistent_perm')).toBe(false)
  })

  it('returns false when no role is active', () => {
    const store = useAuthStore()
    expect(store.checkPermission('manage_schools')).toBe(false)
  })
})
