import { AuthError } from '~/composables/useApi'

export function useMenus() {
  const authStore = useAuthStore()
  const api = useApi()

  async function loadMenus() {
    try {
      const res = await api.getMenus()
      authStore.setMenus(res?.menus || [])
    } catch (err) {
      if (err instanceof AuthError) {
        authStore.setMenus([])
        throw err
      }
      // 非 AuthError 错误降级为空菜单（ORC-menu-degrade），Phase 1 静默；Phase 2 接入 logger 模块
      authStore.setMenus([])
    }
  }

  const activeModule = computed(() => {
    const route = useRoute()
    return (
      authStore.menus.find((m) =>
        m.children?.some((c: any) => route.path.startsWith(c.path)),
      ) || null
    )
  })

  const currentSubMenus = computed(() => activeModule.value?.children || [])

  function navigateToModule(menu: any) {
    const router = useRouter()
    if (menu.children?.length) {
      router.push(menu.children[0].path)
    }
  }

  return { loadMenus, activeModule, currentSubMenus, navigateToModule }
}
