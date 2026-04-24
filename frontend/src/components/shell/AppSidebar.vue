<template>
  <aside :class="['sidebar', { 'sidebar--collapsed': collapsed }]">
    <div class="sidebar__toggle" @click="collapsed = !collapsed">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path v-if="collapsed" d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        <path v-else d="M10 3L5 8l5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <nav class="sidebar__nav">
      <router-link
        v-for="item in navItems"
        :key="item.route"
        :to="item.route"
        :class="['nav-item', { 'nav-item--active': isActive(item.route) }]"
        :title="collapsed ? item.label : ''"
        :data-module="item.moduleCode"
      >
        <span class="nav-item__icon" v-html="iconMap[item.icon] || iconMap.dashboard"></span>
        <span v-show="!collapsed" class="nav-item__label">{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { normalizeRole } from '../../config/roles.js'
import { getSidebarItems } from '../../config/sidebarConfig.js'

const route = useRoute()
const auth = useAuthStore()
const collapsed = ref(false)

const currentNormalizedRole = computed(() => {
  const raw = auth.currentRole?.role
  return raw ? normalizeRole(raw) : 'subject_teacher'
})

const navItems = computed(() => {
  const items = getSidebarItems(currentNormalizedRole.value)
  if (!auth.currentRole?.school_id) return items
  if (!auth.modulesLoaded) return items
  const enabled = new Set(auth.enabledModules)
  return items.filter(item => {
    if (!item.moduleCode) return true
    return enabled.has(item.moduleCode)
  })
})

// Re-compute on role change (watch is implicit via computed, but kept for clarity)
watch(() => auth.currentRole, () => {
  // navItems will re-compute automatically
}, { deep: true })

function isActive(itemRoute) {
  if (itemRoute === '/') return route.path === '/'
  return route.path.startsWith(itemRoute)
}

const iconMap = {
  dashboard: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="7" height="7" rx="2" stroke="currentColor" stroke-width="1.3"/><rect x="10" y="1" width="7" height="4" rx="1.5" stroke="currentColor" stroke-width="1.3"/><rect x="10" y="7" width="7" height="10" rx="2" stroke="currentColor" stroke-width="1.3"/><rect x="1" y="10" width="7" height="7" rx="2" stroke="currentColor" stroke-width="1.3"/></svg>',
  school: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 2L2 6v2h14V6L9 2z" stroke="currentColor" stroke-width="1.3"/><path d="M3 9v6h12V9" stroke="currentColor" stroke-width="1.3"/><rect x="7" y="11" width="4" height="4" stroke="currentColor" stroke-width="1.3"/></svg>',
  exam: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="3" y="1" width="12" height="16" rx="2" stroke="currentColor" stroke-width="1.3"/><path d="M6 5h6M6 8h6M6 11h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  chart: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="10" width="3" height="6" rx="1" stroke="currentColor" stroke-width="1.3"/><rect x="7.5" y="6" width="3" height="10" rx="1" stroke="currentColor" stroke-width="1.3"/><rect x="13" y="2" width="3" height="14" rx="1" stroke="currentColor" stroke-width="1.3"/></svg>',
  settings: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="3" stroke="currentColor" stroke-width="1.3"/><path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.3 3.3l1.4 1.4M13.3 13.3l1.4 1.4M3.3 14.7l1.4-1.4M13.3 4.7l1.4-1.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  marking: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 9l3 3 7-7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  document: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 2h7l4 4v10a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" stroke-width="1.3"/><path d="M11 2v4h4" stroke="currentColor" stroke-width="1.3"/></svg>',
  calendar: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="3" width="14" height="13" rx="2" stroke="currentColor" stroke-width="1.3"/><path d="M2 7h14M6 1v4M12 1v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  notification: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 2a4.5 4.5 0 00-4.5 4.5v3L3.2 11.8a.5.5 0 00.4.7h10.8a.5.5 0 00.4-.7L13.5 9.5v-3A4.5 4.5 0 009 2z" stroke="currentColor" stroke-width="1.3"/><path d="M7 13a2 2 0 004 0" stroke="currentColor" stroke-width="1.3"/></svg>',
  paper: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M3 2h12a1 1 0 011 1v12a1 1 0 01-1 1H3a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" stroke-width="1.3"/><path d="M5 6h8M5 9h8M5 12h5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  score: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1.3"/><path d="M9 5v4l3 2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
}
</script>

<style scoped>
.sidebar {
  width: 220px;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border-light);
  transition: width 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

.sidebar--collapsed {
  width: 64px;
}

.sidebar__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  margin: 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--color-text-muted);
  transition: var(--transition);
}

.sidebar__toggle:hover {
  background: var(--color-bg-alt);
  color: var(--color-primary);
}

.sidebar__nav {
  flex: 1;
  padding: 0 8px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: var(--transition);
  white-space: nowrap;
  border-left: 3px solid transparent;
}

.nav-item:hover {
  background: var(--color-bg-alt);
  color: var(--color-primary);
}

.nav-item--active {
  color: var(--color-primary);
  background: var(--color-bg-alt);
  border-left-color: var(--color-primary);
  font-weight: 600;
}

.nav-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.nav-item__label {
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Collapsed state: center icon */
.sidebar--collapsed .nav-item {
  justify-content: center;
  padding: 10px;
  border-left-width: 0;
}

.sidebar--collapsed .nav-item--active {
  border-left-width: 0;
  border-bottom: 2px solid var(--color-primary);
}
</style>
