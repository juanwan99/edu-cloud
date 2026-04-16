interface UserRole {
  id: string
  role: string
  school_id?: string
  is_primary?: boolean
  context?: {
    type: string
    id: string
    name: string
  }
}

interface UserInfo {
  id: string
  username: string
  display_name: string
  roles: UserRole[]
  active_role: UserRole
}

interface LoginResponse {
  access_token: string
  token_type: string
  user: { id: string; username: string; display_name: string; role: string }
  roles: UserRole[]
}

interface SwitchRoleResponse {
  access_token: string
  token_type: string
  active_role: UserRole
}

interface MenuItem {
  code: string
  name: string
  icon: string
  sort: number
  children: { name: string; path: string; icon: string }[]
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null as UserInfo | null,
    menus: [] as MenuItem[],
  }),

  getters: {
    isLoggedIn: (state) => !!state.user,
    userName: (state) => state.user?.display_name || '',
    activeRole: (state) => state.user?.active_role || null,
    roleName: (state) => {
      const role = state.user?.active_role?.role
      const ROLE_NAMES: Record<string, string> = {
        platform_admin: '平台管理员',
        district_admin: '区域管理员',
        principal: '校长',
        academic_director: '教务主任',
        teaching_research_leader: '教研组长',
        grade_leader: '年级组长',
        lesson_prep_leader: '备课组长',
        homeroom_teacher: '班主任',
        subject_teacher: '科任教师',
        parent: '家长',
      }
      return role ? ROLE_NAMES[role] || role : ''
    },
    schoolName: (state) => state.user?.active_role?.context?.name || '',
  },

  actions: {
    setUser(user: UserInfo) {
      this.user = user
      if (typeof window !== 'undefined') {
        localStorage.setItem('edu_user', JSON.stringify(user))
      }
    },
    setMenus(menus: MenuItem[]) {
      this.menus = menus
    },

    applyLoginResponse(res: LoginResponse) {
      const activeRole = res.roles.find((r) => r.is_primary) || res.roles[0]
      const user: UserInfo = {
        id: res.user.id,
        username: res.user.username,
        display_name: res.user.display_name,
        roles: res.roles,
        active_role: activeRole,
      }
      this.setUser(user)
    },

    applySwitchRoleResponse(res: SwitchRoleResponse) {
      if (!this.user) return
      const updated: UserInfo = { ...this.user, active_role: res.active_role }
      this.setUser(updated)
    },

    restoreFromStorage() {
      if (typeof window === 'undefined') return
      const raw = localStorage.getItem('edu_user')
      if (raw) {
        try { this.user = JSON.parse(raw) as UserInfo } catch { /* noop */ }
      }
    },

    async switchRole(roleId: string) {
      const api = useApi()
      const res = await api.switchRole(roleId) as SwitchRoleResponse
      if (res.access_token) {
        const token = useCookie('edu_token')
        token.value = res.access_token
      }
      this.applySwitchRoleResponse(res)
      const { loadMenus } = useMenus()
      await loadMenus()
    },
    logout() {
      this.user = null
      this.menus = []
      const token = useCookie('edu_token')
      token.value = null
      if (typeof window !== 'undefined') {
        localStorage.removeItem('edu_user')
      }
      navigateTo('/login')
    },
  },
})
