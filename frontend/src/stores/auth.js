import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import client from '../api/client.js'
import router from '../router/index.js'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)
  const roles = ref([])
  const currentRoleIndex = ref(0)

  const currentRole = computed(() => roles.value[currentRoleIndex.value] || null)
  const displayName = computed(() => user.value?.display_name || '')
  const roleName = computed(() => currentRole.value?.role || '')

  async function login(username, password) {
    const { data } = await client.post('/auth/login', { username, password })
    token.value = data.access_token
    user.value = data.user
    roles.value = data.roles
    currentRoleIndex.value = roles.value.findIndex(r => r.is_primary) || 0
    localStorage.setItem('token', data.access_token)
    router.push('/')
  }

  async function switchRole(index) {
    currentRoleIndex.value = index
    const roleId = roles.value[index]?.id
    if (roleId) {
      const { data } = await client.post('/auth/switch-role', { role_id: roleId })
      token.value = data.access_token
      localStorage.setItem('token', data.access_token)
    }
  }

  function logout() {
    token.value = ''
    user.value = null
    roles.value = []
    localStorage.removeItem('token')
    router.push('/login')
  }

  return { token, user, roles, currentRole, currentRoleIndex, displayName, roleName, login, switchRole, logout }
})
