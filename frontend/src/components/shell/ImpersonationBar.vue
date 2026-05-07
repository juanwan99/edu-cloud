<template>
  <div v-if="auth.isImpersonating" class="impersonation-bar">
    <span class="impersonation-bar__icon">⚡</span>
    <span class="impersonation-bar__text">
      模拟中: {{ auth.impersonation?.schoolName }} · {{ roleLabel }}
      <template v-if="scopeText"> · {{ scopeText }}</template>
    </span>
    <button class="impersonation-bar__exit" @click="handleExit">
      退出模拟
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth.js'
import { ROLE_LABELS, normalizeRole } from '../../config/roles.js'
import router from '../../router/index.js'

const auth = useAuthStore()

const roleLabel = computed(() => {
  const role = auth.impersonation?.effectiveRole
  return role ? (ROLE_LABELS[normalizeRole(role)] || role) : ''
})

const scopeText = computed(() => {
  const scope = auth.impersonation?.scope
  if (!scope) return ''
  const parts = []
  if (scope.class_ids?.length) parts.push(`${scope.class_ids.length}个班级`)
  if (scope.subject_codes?.length) parts.push(`${scope.subject_codes.length}个学科`)
  if (scope.grade_ids?.length) parts.push(`${scope.grade_ids.length}个年级`)
  return parts.join(' · ')
})

async function handleExit() {
  await auth.stopImpersonation()
  router.push('/admin/impersonate')
}
</script>

<style scoped>
.impersonation-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 36px;
  background: linear-gradient(90deg, #ED9A51, #F4DA4C);
  color: #09061B;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  z-index: 9999;
}

.impersonation-bar__exit {
  margin-left: 16px;
  padding: 2px 12px;
  border: 1.5px solid #09061B;
  border-radius: 4px;
  background: transparent;
  color: #09061B;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.impersonation-bar__exit:hover {
  background: rgba(9, 6, 27, 0.1);
}
</style>
