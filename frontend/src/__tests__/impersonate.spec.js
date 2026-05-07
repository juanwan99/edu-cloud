import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '../stores/auth.js'

vi.mock('../api/client.js', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

vi.mock('../router/index.js', () => ({
  default: { push: vi.fn() },
}))

vi.mock('../api/schoolSettings.js', () => ({
  getEnabledModules: vi.fn().mockResolvedValue({ data: ['exam', 'grading'] }),
}))

vi.mock('../api/impersonate.js', () => ({
  startImpersonation: vi.fn(),
  exitImpersonation: vi.fn(),
}))

describe('auth store impersonation', () => {
  let auth

  beforeEach(() => {
    setActivePinia(createPinia())
    auth = useAuthStore()
    localStorage.clear()
    sessionStorage.clear()
    // Seed initial state
    auth.token = 'original-token'
    auth.user = { id: 'admin-id', display_name: 'Admin' }
    auth.roles = [{ id: 'r1', role: 'platform_admin', school_id: null, context: { type: 'platform', name: '全平台' } }]
    auth.currentRoleIndex = 0
    localStorage.setItem('token', 'original-token')
  })

  it('impersonate sets impersonation state and token', async () => {
    const { startImpersonation } = await import('../api/impersonate.js')
    startImpersonation.mockResolvedValueOnce({
      data: {
        access_token: 'imp-token',
        effective_role: 'subject_teacher',
        effective_school_id: 'school-1',
        effective_school_name: '景炎中学',
        scope: { class_ids: ['c1'], subject_codes: ['math'], grade_ids: null },
        is_impersonation: true,
      },
    })

    await auth.impersonate('school-1', 'subject_teacher', { class_ids: ['c1'], subject_codes: ['math'] })

    expect(auth.isImpersonating).toBe(true)
    expect(auth.impersonation.effectiveRole).toBe('subject_teacher')
    expect(auth.impersonation.schoolName).toBe('景炎中学')
    expect(auth.token).toBe('imp-token')
    expect(localStorage.getItem('token')).toBe('imp-token')
    expect(sessionStorage.getItem('impersonation')).toBeTruthy()
  })

  it('currentRole returns virtualRole during impersonation', async () => {
    const { startImpersonation } = await import('../api/impersonate.js')
    startImpersonation.mockResolvedValueOnce({
      data: {
        access_token: 'imp-token',
        effective_role: 'principal',
        effective_school_id: 'school-1',
        effective_school_name: '景炎中学',
        scope: { class_ids: null, subject_codes: null, grade_ids: null },
        is_impersonation: true,
      },
    })

    await auth.impersonate('school-1', 'principal', {})

    expect(auth.currentRole.role).toBe('principal')
    expect(auth.currentRole.school_id).toBe('school-1')
    expect(auth.currentRole.context.name).toBe('景炎中学')
  })

  it('stopImpersonation restores original state', async () => {
    // Setup impersonation state
    auth.impersonation = {
      effectiveRole: 'subject_teacher',
      schoolId: 'school-1',
      schoolName: '景炎中学',
      scope: {},
      originalToken: 'original-token',
      virtualRole: { id: 'imp', role: 'subject_teacher', school_id: 'school-1', context: { type: 'school', id: 'school-1', name: '景炎中学' } },
    }
    auth.token = 'imp-token'
    sessionStorage.setItem('impersonation', JSON.stringify(auth.impersonation))

    const { exitImpersonation } = await import('../api/impersonate.js')
    exitImpersonation.mockResolvedValueOnce({
      data: { access_token: 'restored-token' },
    })

    await auth.stopImpersonation()

    expect(auth.isImpersonating).toBe(false)
    expect(auth.token).toBe('restored-token')
    expect(sessionStorage.getItem('impersonation')).toBeNull()
  })

  it('stopImpersonation falls back to originalToken on API failure', async () => {
    auth.impersonation = {
      effectiveRole: 'principal',
      schoolId: 'school-1',
      schoolName: '景炎中学',
      scope: {},
      originalToken: 'original-token',
      virtualRole: { id: 'imp', role: 'principal', school_id: 'school-1', context: {} },
    }
    auth.token = 'imp-token'

    const { exitImpersonation } = await import('../api/impersonate.js')
    exitImpersonation.mockRejectedValueOnce(new Error('Network error'))

    await auth.stopImpersonation()

    expect(auth.isImpersonating).toBe(false)
    expect(auth.token).toBe('original-token')
  })

  it('impersonation state persists in sessionStorage across reload', () => {
    const impState = {
      effectiveRole: 'principal',
      schoolId: 'school-1',
      schoolName: '景炎中学',
      scope: {},
      originalToken: 'orig',
      virtualRole: { id: 'imp', role: 'principal', school_id: 'school-1', context: { type: 'school', id: 'school-1', name: '景炎中学' } },
    }
    sessionStorage.setItem('impersonation', JSON.stringify(impState))

    // Re-create store (simulates reload)
    setActivePinia(createPinia())
    const freshAuth = useAuthStore()

    expect(freshAuth.isImpersonating).toBe(true)
    expect(freshAuth.impersonation.effectiveRole).toBe('principal')
    expect(freshAuth.currentRole.role).toBe('principal')
  })
})
