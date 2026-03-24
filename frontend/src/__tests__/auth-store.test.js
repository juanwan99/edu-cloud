import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth.js'
import client from '../api/client.js'

vi.mock('../api/client.js', () => ({
  default: { post: vi.fn(), get: vi.fn() },
}))

vi.mock('../router/index.js', () => ({
  default: { push: vi.fn() },
}))

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

describe('auth store login()', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('login persists token and auth_state to localStorage', async () => {
    client.post.mockResolvedValueOnce({
      data: {
        access_token: 'jwt-123',
        user: { id: 'u1', display_name: 'Alice' },
        roles: [
          { id: 'r1', role: 'principal', is_primary: true, context: { type: 'school', name: 'X中' } },
          { id: 'r2', role: 'subject_teacher', is_primary: false, context: null },
        ],
      },
    })
    const store = useAuthStore()
    await store.login('alice', 'pass')
    expect(localStorage.getItem('token')).toBe('jwt-123')
    const saved = JSON.parse(localStorage.getItem('auth_state'))
    expect(saved.user.display_name).toBe('Alice')
    expect(saved.roles).toHaveLength(2)
    expect(saved.currentRoleIndex).toBe(0) // is_primary at index 0
  })

  it('login defaults to index 0 when no is_primary role', async () => {
    client.post.mockResolvedValueOnce({
      data: {
        access_token: 'jwt-456',
        user: { id: 'u2', display_name: 'Bob' },
        roles: [
          { id: 'r1', role: 'subject_teacher', is_primary: false, context: null },
        ],
      },
    })
    const store = useAuthStore()
    await store.login('bob', 'pass')
    // findIndex returns -1 when no match, || 0 should fallback to 0
    expect(store.currentRoleIndex).toBe(0)
  })
})

describe('auth store switchRole()', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('switchRole updates index and token on success', async () => {
    const saved = {
      user: { id: 'u1', display_name: 'Alice' },
      roles: [
        { id: 'r1', role: 'principal', context: null },
        { id: 'r2', role: 'subject_teacher', context: null },
      ],
      currentRoleIndex: 0,
    }
    localStorage.setItem('token', 'old-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    client.post.mockResolvedValueOnce({
      data: { access_token: 'new-jwt' },
    })
    await store.switchRole(1)
    expect(store.currentRoleIndex).toBe(1)
    expect(store.token).toBe('new-jwt')
    expect(localStorage.getItem('token')).toBe('new-jwt')
  })

  it('switchRole rolls back index on API failure', async () => {
    const saved = {
      user: { id: 'u1', display_name: 'Alice' },
      roles: [
        { id: 'r1', role: 'principal', context: null },
        { id: 'r2', role: 'subject_teacher', context: null },
      ],
      currentRoleIndex: 0,
    }
    localStorage.setItem('token', 'old-jwt')
    localStorage.setItem('auth_state', JSON.stringify(saved))
    const store = useAuthStore()
    client.post.mockRejectedValueOnce(new Error('network error'))
    await store.switchRole(1)
    expect(store.currentRoleIndex).toBe(0) // rolled back
    expect(store.token).toBe('old-jwt') // unchanged
  })
})
