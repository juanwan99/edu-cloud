import { describe, it, expect } from 'vitest'
import { useAuthStore } from '~/stores/auth'

describe('useAuthStore', () => {
  describe('applyLoginResponse', () => {
    it('applyLoginResponse 选中 is_primary 角色', () => {
      const store = useAuthStore()
      store.applyLoginResponse({
        access_token: 't', token_type: 'bearer',
        user: { id: 'u1', username: 'a', display_name: 'A', role: 'subject_teacher' },
        roles: [
          { id: 'r1', role: 'subject_teacher', is_primary: false },
          { id: 'r2', role: 'homeroom_teacher', is_primary: true },
        ],
      } as any)
      expect(store.user?.active_role.id).toBe('r2')
      expect(store.user?.roles.length).toBe(2)
    })

    it('所有角色均非 is_primary 时回退到 roles[0]', () => {
      const store = useAuthStore()
      store.applyLoginResponse({
        access_token: 't', token_type: 'bearer',
        user: { id: 'u1', username: 'a', display_name: 'A', role: 'subject_teacher' },
        roles: [
          { id: 'r1', role: 'subject_teacher', is_primary: false },
          { id: 'r2', role: 'homeroom_teacher', is_primary: false },
        ],
      } as any)
      expect(store.user?.active_role.id).toBe('r1')
    })

    it('单角色场景', () => {
      const store = useAuthStore()
      store.applyLoginResponse({
        access_token: 't', token_type: 'bearer',
        user: { id: 'u1', username: 'a', display_name: 'A', role: 'principal' },
        roles: [{ id: 'r1', role: 'principal', is_primary: true }],
      } as any)
      expect(store.user?.active_role.id).toBe('r1')
      expect(store.user?.roles.length).toBe(1)
    })
  })

  describe('applySwitchRoleResponse', () => {
    it('applySwitchRoleResponse 保留 user/roles，只改 active_role', () => {
      const store = useAuthStore()
      store.setUser({
        id: 'u1', username: 'a', display_name: 'A',
        roles: [
          { id: 'r1', role: 'subject_teacher' },
          { id: 'r2', role: 'homeroom_teacher' },
        ],
        active_role: { id: 'r1', role: 'subject_teacher' },
      } as any)
      store.applySwitchRoleResponse({
        access_token: 't2', token_type: 'bearer',
        active_role: { id: 'r2', role: 'homeroom_teacher' },
      } as any)
      expect(store.user?.active_role.id).toBe('r2')
      expect(store.user?.roles.length).toBe(2)
    })

    it('user=null 时静默忽略，不抛异常', () => {
      const store = useAuthStore()
      expect(() => {
        store.applySwitchRoleResponse({
          access_token: 't', token_type: 'bearer',
          active_role: { id: 'r1', role: 'principal' },
        } as any)
      }).not.toThrow()
      expect(store.user).toBeNull()
    })
  })

  describe('restoreFromStorage', () => {
    it('restoreFromStorage JSON 损坏时不崩溃', () => {
      const store = useAuthStore()
      localStorage.setItem('edu_user', '{broken json')
      expect(() => store.restoreFromStorage()).not.toThrow()
      expect(store.user).toBeNull()
    })

    it('localStorage 空时保持 null', () => {
      const store = useAuthStore()
      store.restoreFromStorage()
      expect(store.user).toBeNull()
    })

    it('有效 JSON 正确恢复', () => {
      const store = useAuthStore()
      const mockUser = {
        id: 'u1', username: 'a', display_name: 'Alice',
        roles: [{ id: 'r1', role: 'principal' }],
        active_role: { id: 'r1', role: 'principal' },
      }
      localStorage.setItem('edu_user', JSON.stringify(mockUser))
      store.restoreFromStorage()
      expect(store.user?.display_name).toBe('Alice')
      expect(store.user?.active_role.id).toBe('r1')
    })
  })
})
