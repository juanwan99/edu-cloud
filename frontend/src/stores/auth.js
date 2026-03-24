import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import client from '../api/client.js'
import router from '../router/index.js'
import { normalizeRole, SCHOOL_ADMIN_ROLES } from '../config/roles.js'
import { hasPermission } from '../config/permissions.js'

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

  const currentRole = computed(() => roles.value[currentRoleIndex.value] || null)
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
    currentRoleIndex.value = roles.value.findIndex(r => r.is_primary) || 0
    localStorage.setItem('token', data.access_token)
    saveAuthState(user.value, roles.value, currentRoleIndex.value)
    try { router.push('/') } catch { /* test env */ }
  }

  async function switchRole(index) {
    currentRoleIndex.value = index
    const roleId = roles.value[index]?.id
    if (roleId) {
      const { data } = await client.post('/auth/switch-role', { role_id: roleId })
      token.value = data.access_token
      localStorage.setItem('token', data.access_token)
    }
    saveAuthState(user.value, roles.value, currentRoleIndex.value)
  }

  function logout() {
    token.value = ''
    user.value = null
    roles.value = []
    currentRoleIndex.value = 0
    localStorage.removeItem('token')
    localStorage.removeItem('auth_state')
    try { router.push('/login') } catch { /* test env */ }
  }

  return {
    token, user, roles, currentRole, currentRoleIndex,
    displayName, roleName, currentContext, isAdmin,
    checkPermission, login, switchRole, logout,
  }
})
