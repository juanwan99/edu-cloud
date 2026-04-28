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
        <span class="nav-item__icon"><SidebarIcon name="dashboard" /></span>
        <span v-show="!collapsed" class="nav-item__label">概览</span>
      </router-link>

      <div v-for="group in visibleGroups" :key="group.key" class="nav-group">
        <div
          :class="['nav-group__header', { 'nav-group__header--active': isGroupActive(group) }]"
          :title="collapsed ? group.label : ''"
          @click="handleGroupClick(group.key)"
        >
          <span class="nav-item__icon"><SidebarIcon :name="group.icon || 'dashboard'" /></span>
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
import SidebarIcon from '../icons/SidebarIcons.vue'

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
  gap: 10px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 13.5px;
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
  padding: 6px 14px 6px 38px;
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
  transition: opacity 0.2s ease, max-height 0.2s ease;
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
