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
        to="/"
        :class="['nav-item', { 'nav-item--active': isActive('/') }]"
        :title="collapsed ? '概览' : ''"
      >
        <span class="nav-item__icon" v-html="iconMap.dashboard"></span>
        <span v-show="!collapsed" class="nav-item__label">概览</span>
      </router-link>

      <div v-for="group in visibleGroups" :key="group.key" class="nav-group">
        <div
          :class="['nav-group__header', { 'nav-group__header--active': isGroupActive(group) }]"
          :title="collapsed ? group.label : ''"
          @click="handleGroupClick(group.key)"
        >
          <span class="nav-item__icon" v-html="iconMap[group.icon] || iconMap.dashboard"></span>
          <span v-show="!collapsed" class="nav-group__label">{{ group.label }}</span>
          <svg v-show="!collapsed" :class="['nav-group__arrow', { 'nav-group__arrow--open': expandedGroups[group.key] }]" width="12" height="12" viewBox="0 0 12 12">
            <path d="M4 4.5l2 2 2-2" stroke="currentColor" stroke-width="1.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <transition name="slide">
          <div v-show="!collapsed && expandedGroups[group.key]" class="nav-group__children">
            <router-link
              v-for="item in group.children"
              :key="item.route"
              :to="item.route"
              :class="['nav-item nav-item--child', { 'nav-item--active': isActive(item.route) }]"
            >
              <span class="nav-item__label">{{ item.label }}</span>
            </router-link>
          </div>
        </transition>
      </div>
    </nav>
  </aside>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { normalizeRole } from '../../config/roles.js'
import { getSidebarGroups } from '../../config/sidebarConfig.js'

const route = useRoute()
const auth = useAuthStore()
const collapsed = ref(false)
const expandedGroups = reactive({})

const currentNormalizedRole = computed(() => {
  const raw = auth.currentRole?.role
  return raw ? normalizeRole(raw) : 'subject_teacher'
})

const visibleGroups = computed(() => {
  const modules = auth.modulesLoaded ? auth.enabledModules : []
  return getSidebarGroups(currentNormalizedRole.value, modules)
})

function handleGroupClick(key) {
  if (collapsed.value) {
    collapsed.value = false
    expandedGroups[key] = true
  } else {
    expandedGroups[key] = !expandedGroups[key]
  }
}

function isActive(itemRoute) {
  if (itemRoute === '/') return route.path === '/'
  if (itemRoute === '/analytics/report') return route.path.startsWith('/analytics')
  if (itemRoute === '/conduct') return route.path === '/conduct'
  return route.path.startsWith(itemRoute)
}

function isGroupActive(group) {
  return group.children.some(item => isActive(item.route))
}

function autoExpandCurrentGroup() {
  for (const group of visibleGroups.value) {
    if (isGroupActive(group)) {
      expandedGroups[group.key] = true
    }
  }
}

watch(() => route.path, autoExpandCurrentGroup, { immediate: true })
watch(visibleGroups, autoExpandCurrentGroup)

const iconMap = {
  dashboard: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="1" y="1" width="7" height="7" rx="2" stroke="currentColor" stroke-width="1.3"/><rect x="10" y="1" width="7" height="4" rx="1.5" stroke="currentColor" stroke-width="1.3"/><rect x="10" y="7" width="7" height="10" rx="2" stroke="currentColor" stroke-width="1.3"/><rect x="1" y="10" width="7" height="7" rx="2" stroke="currentColor" stroke-width="1.3"/></svg>',
  exam: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="3" y="1" width="12" height="16" rx="2" stroke="currentColor" stroke-width="1.3"/><path d="M6 5h6M6 8h6M6 11h4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  book: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M2 3h5a2 2 0 012 2v10a1.5 1.5 0 00-1.5-1.5H2V3z" stroke="currentColor" stroke-width="1.3"/><path d="M16 3h-5a2 2 0 00-2 2v10a1.5 1.5 0 011.5-1.5H16V3z" stroke="currentColor" stroke-width="1.3"/></svg>',
  academic: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 1L1 5l8 4 8-4-8-4z" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/><path d="M3 7v5c0 2 2.7 3 6 3s6-1 6-3V7" stroke="currentColor" stroke-width="1.3"/><path d="M15 5v7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  people: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="7" cy="5" r="2.5" stroke="currentColor" stroke-width="1.3"/><path d="M2 15a5 5 0 0110 0" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/><circle cx="13" cy="6" r="2" stroke="currentColor" stroke-width="1.3"/><path d="M13 10c2 0 4 1.5 4 4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  school: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 2L2 6v2h14V6L9 2z" stroke="currentColor" stroke-width="1.3"/><path d="M3 9v6h12V9" stroke="currentColor" stroke-width="1.3"/><rect x="7" y="11" width="4" height="4" stroke="currentColor" stroke-width="1.3"/></svg>',
  marking: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M4 9l3 3 7-7" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  chart: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="10" width="3" height="6" rx="1" stroke="currentColor" stroke-width="1.3"/><rect x="7.5" y="6" width="3" height="10" rx="1" stroke="currentColor" stroke-width="1.3"/><rect x="13" y="2" width="3" height="14" rx="1" stroke="currentColor" stroke-width="1.3"/></svg>',
  settings: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="3" stroke="currentColor" stroke-width="1.3"/><path d="M9 1v2M9 15v2M1 9h2M15 9h2M3.3 3.3l1.4 1.4M13.3 13.3l1.4 1.4M3.3 14.7l1.4-1.4M13.3 4.7l1.4-1.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
  calendar: '<svg width="18" height="18" viewBox="0 0 18 18" fill="none"><rect x="2" y="3" width="14" height="13" rx="2" stroke="currentColor" stroke-width="1.3"/><path d="M2 7h14M6 1v4M12 1v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
}
</script>

<style scoped>
.sidebar {
  width: 220px;
  background: var(--color-bg);
  border-right: 1px solid var(--color-border-light);
  transition: width 0.2s ease-out;
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

.nav-item--child {
  padding: 8px 16px 8px 42px;
  font-size: 13px;
  border-left: none;
}

.nav-item--child.nav-item--active {
  border-left: none;
  color: var(--color-primary);
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

.nav-group {
  margin-top: 4px;
}

.nav-group__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
  white-space: nowrap;
  user-select: none;
}

.nav-group__header:hover {
  background: var(--color-bg-alt);
  color: var(--color-primary);
}

.nav-group__header--active {
  color: var(--color-primary);
}

.nav-group__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-group__arrow {
  flex-shrink: 0;
  transition: transform 0.2s ease;
  opacity: 0.5;
}

.nav-group__arrow--open {
  transform: rotate(180deg);
}

.nav-group__children {
  overflow: hidden;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
}

/* Collapsed state */
.sidebar--collapsed .nav-item {
  justify-content: center;
  padding: 10px;
  border-left-width: 0;
}

.sidebar--collapsed .nav-item--active {
  border-left-width: 0;
  border-bottom: 2px solid var(--color-primary);
}

.sidebar--collapsed .nav-group__header {
  justify-content: center;
  padding: 10px;
}
</style>
