import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import { AuthError, useApi } from '~/composables/useApi'
import { useMenus } from '~/composables/useMenus'
import { useAuthStore } from '~/stores/auth'

describe('useMenus', () => {
  let getMenusMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    // useMenus.ts 依赖 Nuxt auto-import 的 useAuthStore；测试环境需手动注入
    ;(globalThis as any).useAuthStore = useAuthStore
    getMenusMock = vi.fn()
    ;(globalThis as any).useApi = () => ({
      getMenus: getMenusMock,
      login: vi.fn(),
      switchRole: vi.fn(),
      token: ref(null),
    })
  })

  describe('loadMenus AuthError 向上抛（Slice 2 / ORC-auth-fail-closed）', () => {
    it('getMenus 抛 AuthError 时 loadMenus 向上抛并清空 menus', async () => {
      const authError = new AuthError(401, 'auth failed')
      getMenusMock.mockRejectedValue(authError)

      const store = useAuthStore()
      store.setMenus([
        { code: 'stale', name: '过期菜单', icon: '', sort: 0, children: [] } as any,
      ])
      expect(store.menus.length).toBe(1)

      const { loadMenus } = useMenus()

      await expect(loadMenus()).rejects.toBeInstanceOf(AuthError)
      expect(store.menus).toEqual([])
    })

    it('getMenus 抛 AuthError(403) 时 loadMenus 同样向上抛', async () => {
      const authError = new AuthError(403, 'forbidden')
      getMenusMock.mockRejectedValue(authError)

      const store = useAuthStore()
      const { loadMenus } = useMenus()

      await expect(loadMenus()).rejects.toBeInstanceOf(AuthError)
      expect(store.menus).toEqual([])
    })
  })

  describe('loadMenus 降级空菜单（Slice 3 / ORC-menu-degrade）', () => {
    it('非 AuthError（网络错误）时 loadMenus 不抛，menus 降级为空', async () => {
      getMenusMock.mockRejectedValue(new Error('network timeout'))

      const store = useAuthStore()
      store.setMenus([
        { code: 'old', name: '旧菜单', icon: '', sort: 0, children: [] } as any,
      ])

      const { loadMenus } = useMenus()

      await expect(loadMenus()).resolves.toBeUndefined()
      expect(store.menus).toEqual([])
    })

    it('getMenus 返回 null/undefined 时 loadMenus 不崩溃，menus 为空数组', async () => {
      getMenusMock.mockResolvedValue(undefined)

      const store = useAuthStore()
      const { loadMenus } = useMenus()

      await expect(loadMenus()).resolves.toBeUndefined()
      expect(store.menus).toEqual([])
    })
  })

  describe('getMenus 在 401/403 时转为 AuthError（Slice 1）', () => {
    it('$fetch 响应 status=401 时 getMenus 抛 AuthError(401)', async () => {
      ;(globalThis as any).$fetch = vi
        .fn()
        .mockRejectedValue({ response: { status: 401 } })

      const api = useApi()

      await expect(api.getMenus()).rejects.toBeInstanceOf(AuthError)
      try {
        await api.getMenus()
      } catch (e: any) {
        expect(e.status).toBe(401)
        expect(e.name).toBe('AuthError')
      }
    })

    it('$fetch 响应 statusCode=403 时 getMenus 抛 AuthError(403)', async () => {
      ;(globalThis as any).$fetch = vi
        .fn()
        .mockRejectedValue({ statusCode: 403 })

      const api = useApi()

      await expect(api.getMenus()).rejects.toBeInstanceOf(AuthError)
      try {
        await api.getMenus()
      } catch (e: any) {
        expect(e.status).toBe(403)
      }
    })

    it('$fetch 抛非 401/403（500）时 getMenus 原样抛，不转 AuthError', async () => {
      ;(globalThis as any).$fetch = vi
        .fn()
        .mockRejectedValue({ response: { status: 500 }, message: 'server error' })

      const api = useApi()

      await expect(api.getMenus()).rejects.not.toBeInstanceOf(AuthError)
    })

    it('$fetch 抛无 status 错误（网络超时）时 getMenus 原样抛，不转 AuthError', async () => {
      ;(globalThis as any).$fetch = vi
        .fn()
        .mockRejectedValue(new Error('ECONNREFUSED'))

      const api = useApi()

      await expect(api.getMenus()).rejects.not.toBeInstanceOf(AuthError)
    })
  })

  describe('activeModule 路径匹配分隔符护栏（前置-1 / startsWith 误匹配修复）', () => {
    it('route=/examples 时不误匹配 c.path=/exam 菜单项（分隔符护栏）', () => {
      ;(globalThis as any).useRoute = () => ({ path: '/examples' })

      const store = useAuthStore()
      store.setMenus([
        {
          code: 'exam',
          name: '考试',
          icon: '',
          sort: 0,
          children: [
            { path: '/exam', name: '考试中心', icon: '', sort: 0 },
          ],
        } as any,
      ])

      const { activeModule } = useMenus()

      expect(activeModule.value).toBeNull()
    })
  })
})
