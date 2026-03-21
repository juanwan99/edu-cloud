// frontend/src/stores/auth.js
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const displayName = ref('开发模式')
  const currentRole = ref('platform_admin')
  const roles = ref([])
  const scope = ref({})
  return { token, displayName, currentRole, roles, scope }
})
