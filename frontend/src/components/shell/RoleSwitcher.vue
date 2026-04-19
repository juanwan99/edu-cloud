<template>
  <n-dropdown
    :options="roleOptions"
    :value="auth.currentRoleIndex"
    @select="handleSwitch"
    placement="bottom-end"
  >
    <div class="role-switcher" :title="displayLabel">
      <span class="role-switcher__avatar">
        {{ auth.displayName?.[0] || 'U' }}
      </span>
      <span v-if="!compact" class="role-switcher__info">
        <span class="role-switcher__name">{{ auth.displayName }}</span>
        <span class="role-switcher__role">{{ displayLabel }}</span>
      </span>
    </div>
  </n-dropdown>
</template>

<script setup>
import { h, computed } from 'vue'
import { NTag } from 'naive-ui'
import { useAuthStore } from '../../stores/auth.js'
import { normalizeRole, ROLE_LABELS } from '../../config/roles.js'

defineProps({
  compact: { type: Boolean, default: false },
})

const auth = useAuthStore()

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
      h('div', { style: 'padding: 8px 16px; border-bottom: 1px solid var(--color-border-light);' }, [
        h('div', { style: 'font-weight: 700; font-size: 14px; color: var(--color-text);' }, auth.displayName || ''),
        h('div', { style: 'font-size: 12px; color: var(--color-text-muted); margin-top: 2px;' }, `${auth.roles.length} 个角色`),
      ]),
  })

  // Role entries
  auth.roles.forEach((role, index) => {
    const normalized = normalizeRole(role.role)
    const label = ROLE_LABELS[normalized] || role.role
    const ctxName = role.context?.name || ''
    const isCurrent = index === auth.currentRoleIndex

    items.push({
      key: index,
      type: 'render',
      render: () =>
        h('div', {
          style: `padding: 8px 16px; display: flex; align-items: center; gap: 8px; cursor: pointer; ${isCurrent ? 'background: var(--color-bg-alt);' : ''}`,
          onClick: () => { if (!isCurrent) handleSwitch(index) },
        }, [
          h(NTag, {
            size: 'small',
            round: true,
            type: isCurrent ? 'success' : 'default',
            bordered: !isCurrent,
          }, { default: () => label }),
          ctxName ? h('span', { style: 'font-size: 12px; color: var(--color-text-muted);' }, ctxName) : null,
          isCurrent ? h('span', { style: 'margin-left: auto; font-size: 12px; color: var(--color-primary);' }, '\u2713') : null,
        ]),
    })
  })

  // Divider + logout
  items.push({ type: 'divider', key: 'divider' })
  items.push({ label: '退出登录', key: 'logout' })

  return items
})

function handleSwitch(key) {
  if (key === 'logout') {
    auth.logout()
    return
  }
  if (key === 'header' || key === 'divider') return
  if (typeof key === 'number' && key !== auth.currentRoleIndex) {
    auth.switchRole(key)
  }
}
</script>

<style scoped>
.role-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-sm);
  transition: var(--transition);
}

.role-switcher:hover {
  background: var(--color-bg-alt);
}

.role-switcher__avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--macaron-mint-light);
  border: 2px solid var(--macaron-mint);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 15px;
  color: var(--color-primary);
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

.role-switcher__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-switcher__role {
  font-size: 11px;
  color: var(--color-text-muted);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 160px;
}
</style>
