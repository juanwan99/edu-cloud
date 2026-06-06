<template>
  <n-dropdown
    :options="roleOptions"
    :value="auth.currentRoleIndex"
    @select="handleSwitch"
    placement="bottom-end"
    trigger="click"
    :style="{ maxHeight: '70vh', overflowY: 'auto' }"
    scrollable
  >
    <button
      type="button"
      class="role-switcher"
      :title="displayLabel"
      :aria-label="`切换身份：${displayLabel}`"
    >
      <span class="role-switcher__avatar">
        {{ auth.displayName?.[0] || 'U' }}
      </span>
      <span v-if="compact" class="role-switcher__compact-role">{{ displayLabel }}</span>
      <span v-if="!compact" class="role-switcher__info">
        <span class="role-switcher__name">{{ auth.displayName }}</span>
        <span class="role-switcher__role">{{ displayLabel }}</span>
      </span>
    </button>
  </n-dropdown>
</template>

<script setup>
import { h, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NTag } from 'naive-ui'
import { useAuthStore } from '../../stores/auth.js'
import { normalizeRole, ROLE_LABELS } from '../../config/roles.js'
import { canAccessRouteForRole, moduleGateFromAuth } from '../../config/routeAccess.js'
import { getRoleEntryPolicy } from '../../config/roleEntryMatrix.js'
import { routeBelongsToRoleEntry } from '../../config/identityRouting.js'

defineProps({
  compact: { type: Boolean, default: false },
})

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const displayLabel = computed(() => {
  const raw = auth.currentRole?.role
  if (!raw) return ''
  const normalized = normalizeRole(raw)
  const roleName = ROLE_LABELS[normalized] || raw
  const ctxName = auth.currentContext?.name
  return ctxName ? `${roleName} - ${ctxName}` : roleName
})

const roleOptions = computed(() => {
  const items = []

  // User info header
  items.push({
    key: 'header',
    type: 'render',
    render: () =>
      h('div', { style: 'padding: var(--space-2) var(--space-4); border-bottom: 1px solid var(--color-border-light);' }, [
        h('div', { style: 'font-weight: var(--fw-semibold); font-size: var(--fs-base); color: var(--color-text);' }, auth.displayName || ''),
        h('div', { style: 'font-size: var(--fs-base); color: var(--color-text-muted); margin-top: 2px;' }, `${auth.roles.length} 个角色`),
      ]),
  })

  // Role entries
  auth.roles.forEach((role, index) => {
    const normalized = normalizeRole(role.role)
    const label = ROLE_LABELS[normalized] || role.role
    const ctxName = role.context?.name || ''
    const isCurrent = index === auth.currentRoleIndex
    const primaryText = role.is_primary ? '主身份' : '可切换'

    items.push({
      key: index,
      type: 'render',
      render: () =>
        h('div', {
          style: `padding: var(--space-2) var(--space-4); display: flex; align-items: center; gap: var(--space-2); cursor: pointer; ${isCurrent ? 'background: var(--color-bg-alt);' : ''}`,
          onClick: () => { if (!isCurrent) handleSwitch(index) },
        }, [
          h(NTag, {
            size: 'small',
            round: true,
            type: isCurrent ? 'success' : 'default',
            bordered: !isCurrent,
          }, { default: () => label }),
          ctxName ? h('span', { style: 'font-size: var(--fs-base); color: var(--color-text-muted);' }, ctxName) : null,
          h('span', { style: 'font-size: var(--fs-base); color: var(--color-text-muted);' }, primaryText),
          isCurrent ? h('span', { style: 'margin-left: auto; font-size: var(--fs-base); color: var(--color-primary);' }, '当前') : null,
        ]),
    })
  })

  // Divider + logout
  items.push({ type: 'divider', key: 'divider' })
  items.push({ label: '退出登录', key: 'logout' })

  return items
})

async function handleSwitch(key) {
  if (key === 'logout') {
    auth.logout()
    return
  }
  if (key === 'header' || key === 'divider') return
  if (typeof key === 'number' && key !== auth.currentRoleIndex) {
    const targetRole = auth.roles[key]?.role
    const targetRoleKey = normalizeRole(targetRole)
    const switched = await auth.switchRole(key)
    if (!switched) return
    // Phase 0.7A：用门控上下文取代「modulesLoaded ? enabledModules : []」fail-open 兜底。
    // 切换后若目标身份（学校用户）模块未加载/失败/未启用该模块，则不视为「当前路由可达」→ 回 '/'。
    const routeAllowed = canAccessRouteForRole(targetRoleKey, route.path, moduleGateFromAuth(auth))
    const routeInWorkbench = routeBelongsToRoleEntry(route.path, targetRoleKey, getRoleEntryPolicy(targetRoleKey))
    if (!routeAllowed || !routeInWorkbench) {
      router.push('/')
    }
  }
}

defineExpose({ handleSwitch })
</script>

<style scoped>
.role-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: var(--transition);
}

.role-switcher:hover {
  background: rgba(255, 255, 255, 0.1);
}

.role-switcher__avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  border: 2px solid rgba(255, 255, 255, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--fw-semibold);
  font-size: var(--fs-base);
  color: #ffffff;
  flex-shrink: 0;
  transition: var(--transition);
}

.role-switcher:hover .role-switcher__avatar {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.role-switcher__info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.role-switcher__compact-role {
  max-width: 132px;
  color: rgba(255, 255, 255, 0.88);
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  line-height: var(--lh-snug);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-switcher__name {
  font-size: var(--fs-base);
  font-weight: var(--fw-semibold);
  color: rgba(255, 255, 255, 0.95);
  line-height: var(--lh-snug);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-switcher__role {
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.6);
  line-height: var(--lh-snug);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}
</style>
