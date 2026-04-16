import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref, defineComponent } from 'vue'
import DefaultLayout from '~/layouts/default.vue'
import { AuthError } from '~/composables/useApi'
import { useAuthStore } from '~/stores/auth'

describe('layouts/default.vue auth lifecycle (Slice 4 / ORC-auth-fail-closed)', () => {
  let loadMenusMock: ReturnType<typeof vi.fn>
  let tokenRef: ReturnType<typeof ref<string | null>>
  let logoutSpy: ReturnType<typeof vi.fn>

  beforeEach(() => {
    tokenRef = ref<string | null>(null)
    loadMenusMock = vi.fn()
    ;(globalThis as any).useAuthStore = useAuthStore
    ;(globalThis as any).useCookie = (_name: string) => tokenRef
    ;(globalThis as any).useMenus = () => ({
      loadMenus: loadMenusMock,
      activeModule: ref(null),
      currentSubMenus: ref([]),
      navigateToModule: vi.fn(),
    })
    ;(globalThis as any).navigateTo = vi.fn()
    ;(globalThis as any).useApi = () => ({
      login: vi.fn(),
      switchRole: vi.fn(),
      getMenus: vi.fn().mockResolvedValue({ menus: [] }),
      token: tokenRef,
    })
    logoutSpy = vi.fn()
  })

  function mountLayout() {
    return mount(DefaultLayout, {
      global: {
        stubs: {
          TopNav: defineComponent({ template: '<div />' }),
          SubNav: defineComponent({ template: '<div />' }),
        },
      },
      slots: { default: '<div>content</div>' },
    })
  }

  it('token 出现 + loadMenus 抛 AuthError(401) → 触发 authStore.logout', async () => {
    loadMenusMock.mockRejectedValue(new AuthError(401, 'auth failed'))
    const wrapper = mountLayout()
    const store = useAuthStore()
    store.logout = logoutSpy

    tokenRef.value = 'stale-token-abc'
    await flushPromises()

    expect(loadMenusMock).toHaveBeenCalled()
    expect(logoutSpy).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('token 出现 + loadMenus 抛 AuthError(403) → 触发 authStore.logout', async () => {
    loadMenusMock.mockRejectedValue(new AuthError(403, 'forbidden'))
    const wrapper = mountLayout()
    const store = useAuthStore()
    store.logout = logoutSpy

    tokenRef.value = 'another-token'
    await flushPromises()

    expect(logoutSpy).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it('token 出现 + loadMenus 抛非 AuthError（500）→ 不触发 logout，保留 session', async () => {
    loadMenusMock.mockRejectedValue(new Error('server error'))
    const wrapper = mountLayout()
    const store = useAuthStore()
    store.logout = logoutSpy
    const userRef = { value: { id: 'u1' } }
    Object.defineProperty(store, 'user', { get: () => userRef.value, configurable: true })

    tokenRef.value = 'valid-token'
    await flushPromises()

    expect(loadMenusMock).toHaveBeenCalled()
    // 核心断言: 500 错误不触发 logout, session 得以保留 (ORC-menu-degrade)
    expect(logoutSpy).not.toHaveBeenCalled()
    // session 保留证据: authStore.user 仍存在 (未被 logout 清空)
    expect(store.user).toBeTruthy()
    wrapper.unmount()
  })

  it('token=null 时不触发 loadMenus，也不触发 logout', async () => {
    const wrapper = mountLayout()
    const store = useAuthStore()
    store.logout = logoutSpy

    // token 保持 null，不动
    await flushPromises()

    expect(loadMenusMock).not.toHaveBeenCalled()
    expect(logoutSpy).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
