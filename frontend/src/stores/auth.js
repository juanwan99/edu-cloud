import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import client from '../api/client.js'
import router from '../router/index.js'
import { normalizeRole, SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'
import { chooseDefaultRoleIndex } from '../config/identityRouting.js'
import { getEnabledModules } from '../api/schoolSettings.js'

/** Persist auth state to localStorage */
function saveAuthState(userVal, rolesVal, indexVal) {
  try {
    localStorage.setItem('auth_state', JSON.stringify({
      user: userVal,
      roles: rolesVal,
      currentRoleIndex: indexVal,
    }))
  } catch { /* quota exceeded — non-fatal */ }
}

/** Restore auth state from localStorage (returns null on failure) */
function loadAuthState() {
  try {
    const raw = localStorage.getItem('auth_state')
    if (!raw) return null
    if (!localStorage.getItem('token')) {
      localStorage.removeItem('auth_state')
      return null
    }
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')

  // Hydrate from localStorage if token exists
  const saved = token.value ? loadAuthState() : null
  const user = ref(saved?.user ?? null)
  const roles = ref(saved?.roles ?? [])
  const currentRoleIndex = ref(saved?.currentRoleIndex ?? 0)

  const enabledModules = ref([])
  const modulesLoaded = ref(false)

  // Impersonation state — sessionStorage (关标签页即清)
  const impersonation = ref(JSON.parse(sessionStorage.getItem('impersonation') || 'null'))

  const isImpersonating = computed(() => !!impersonation.value)

  const currentRole = computed(() => {
    if (impersonation.value?.virtualRole) return impersonation.value.virtualRole
    return roles.value[currentRoleIndex.value] || null
  })
  const displayName = computed(() => user.value?.display_name || '')
  const roleName = computed(() => currentRole.value?.role || '')
  const currentContext = computed(() => currentRole.value?.context || null)

  const ADMIN_ROLES = new Set(SCHOOL_ADMIN_ROLES)
  const isAdmin = computed(() => {
    const raw = currentRole.value?.role
    return raw ? ADMIN_ROLES.has(normalizeRole(raw)) : false
  })

  function checkPermission(perm) {
    const raw = currentRole.value?.role
    if (!raw) return false
    return hasPermission(normalizeRole(raw), perm)
  }

  async function login(username, password) {
    const { data } = await client.post('/auth/login', { username, password })
    token.value = data.access_token
    user.value = data.user
    roles.value = data.roles
    currentRoleIndex.value = chooseDefaultRoleIndex(roles.value)
    localStorage.setItem('token', data.access_token)
    saveAuthState(user.value, roles.value, currentRoleIndex.value)
    await loadModules()
    try { router.push('/') } catch { /* test env */ }
  }

  async function switchRole(index) {
    const oldIndex = currentRoleIndex.value
    const roleId = roles.value[index]?.id
    if (roleId) {
      try {
        const { data } = await client.post('/auth/switch-role', { role_id: roleId })
        currentRoleIndex.value = index
        token.value = data.access_token
        localStorage.setItem('token', data.access_token)
      } catch {
        currentRoleIndex.value = oldIndex
        return false
      }
    } else {
      currentRoleIndex.value = index
    }
    saveAuthState(user.value, roles.value, currentRoleIndex.value)
    await loadModules()
    return true
  }

  async function loadModules() {
    const role = currentRole.value
    if (!role?.school_id) {
      enabledModules.value = []
      modulesLoaded.value = false
      return
    }
    try {
      const { data } = await getEnabledModules(role.school_id)
      enabledModules.value = data
      modulesLoaded.value = true
    } catch {
      enabledModules.value = ['exam', 'grading', 'calendar', 'studio']
      modulesLoaded.value = true
    }
  }

  async function impersonate(schoolId, role, scope = {}) {
    const { startImpersonation } = await import('../api/impersonate.js')
    const { data } = await startImpersonation(schoolId, role, scope)

    // 保存原始 token 到 sessionStorage（关标签页即清，比 localStorage 安全）
    const originalToken = token.value

    // 构造虚拟角色对象（保证路由守卫和菜单正常工作）
    const virtualRole = {
      id: 'impersonated',
      role: data.effective_role,
      school_id: data.effective_school_id,
      context: { type: 'school', id: data.effective_school_id, name: data.effective_school_name },
      class_ids: data.scope?.class_ids || null,
      subject_codes: data.scope?.subject_codes || null,
      is_primary: false,
    }

    impersonation.value = {
      effectiveRole: data.effective_role,
      schoolId: data.effective_school_id,
      schoolName: data.effective_school_name,
      scope: data.scope,
      originalToken,
      virtualRole,
    }
    sessionStorage.setItem('impersonation', JSON.stringify(impersonation.value))

    // 切换到 impersonation token
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)

    await loadModules()
  }

  async function stopImpersonation() {
    const { exitImpersonation } = await import('../api/impersonate.js')
    try {
      const { data } = await exitImpersonation()
      token.value = data.access_token
      localStorage.setItem('token', data.access_token)
    } catch {
      // Fallback: 恢复原始 token
      if (impersonation.value?.originalToken) {
        token.value = impersonation.value.originalToken
        localStorage.setItem('token', impersonation.value.originalToken)
      }
    }

    impersonation.value = null
    sessionStorage.removeItem('impersonation')
    await loadModules()
  }

  function logout() {
    token.value = ''
    user.value = null
    roles.value = []
    currentRoleIndex.value = 0
    enabledModules.value = []
    modulesLoaded.value = false
    impersonation.value = null
    sessionStorage.removeItem('impersonation')
    localStorage.removeItem('token')
    localStorage.removeItem('auth_state')
    try { router.push('/login') } catch { /* test env */ }
  }

  return {
    token, user, roles, currentRole, currentRoleIndex,
    displayName, roleName, currentContext, isAdmin,
    enabledModules, modulesLoaded,
    impersonation, isImpersonating,
    checkPermission, login, switchRole, logout, loadModules,
    impersonate, stopImpersonation,
  }
})
