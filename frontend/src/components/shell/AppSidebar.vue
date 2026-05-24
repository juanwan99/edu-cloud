<template>
  <aside :class="['sidebar', { 'sidebar--collapsed': effectiveCollapsed }]">
    <div class="sidebar__toggle" @click="collapsed = !collapsed">
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path v-if="effectiveCollapsed" d="M6 3l5 5-5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        <path v-else d="M10 3L5 8l5 5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <nav class="sidebar__nav">
      <router-link
        to="/"
        :class="['nav-item', { 'nav-item--active': isActive('/') }]"
        :title="effectiveCollapsed ? '概览' : ''"
      >
        <span class="nav-item__icon"><AppIcon name="dashboard" :size="18" /></span>
        <span v-show="!effectiveCollapsed" class="nav-item__label">概览</span>
      </router-link>

      <div v-for="group in visibleGroups" :key="group.key" class="nav-group">
        <div
          :class="['nav-group__header', { 'nav-group__header--active': isGroupActive(group) }]"
          :title="effectiveCollapsed ? group.label : ''"
          @click="handleGroupClick(group)"
        >
          <span class="nav-item__icon"><AppIcon :name="group.icon || 'dashboard'" :size="18" /></span>
          <span v-show="!effectiveCollapsed" class="nav-group__label">{{ group.label }}</span>
          <svg v-show="!effectiveCollapsed" :class="['nav-group__arrow', { 'nav-group__arrow--open': expandedGroups[group.key] }]" width="12" height="12" viewBox="0 0 12 12">
            <path d="M4 4.5l2 2 2-2" stroke="currentColor" stroke-width="1.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <transition name="slide">
          <div v-show="!effectiveCollapsed && expandedGroups[group.key]" class="nav-group__children">
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
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth.js'
import { normalizeRole } from '../../config/roles.js'
import { getSidebarGroups } from '../../config/sidebarConfig.js'
import AppIcon from '../AppIcon.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const sidebarCollapseQuery = '(max-width: 1180px)'
const collapsed = ref(false)
const isNarrowScreen = ref(false)
const expandedGroups = reactive({})
let mediaQueryList = null
let mediaQueryListener = null

mediaQueryList = createMediaQueryList()
if (mediaQueryList) {
  isNarrowScreen.value = mediaQueryList.matches
}

const currentNormalizedRole = computed(() => {
  const raw = auth.currentRole?.role
  return raw ? normalizeRole(raw) : 'subject_teacher'
})

const visibleGroups = computed(() => {
  const modules = auth.modulesLoaded ? auth.enabledModules : []
  return getSidebarGroups(currentNormalizedRole.value, modules)
})

const effectiveCollapsed = computed(() => collapsed.value || isNarrowScreen.value)

function createMediaQueryList() {
  if (typeof window === 'undefined' || !window.matchMedia) return null
  return window.matchMedia(sidebarCollapseQuery)
}

function handleGroupClick(group) {
  if (effectiveCollapsed.value && group.children?.length > 0) {
    router.push(group.children[0].route)
  } else {
    expandedGroups[group.key] = !expandedGroups[group.key]
  }
}

function isActive(itemRoute) {
  if (itemRoute === '/') return route.path === '/'
  if (itemRoute === '/analytics/report') return route.path === '/analytics/report' || route.path.startsWith('/analytics/report/')
  if (itemRoute === '/conduct') return route.path === '/conduct'
  if (itemRoute === '/marking') return route.path === '/marking'
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

onMounted(() => {
  mediaQueryList = mediaQueryList || createMediaQueryList()
  if (!mediaQueryList) return
  mediaQueryListener = event => {
    isNarrowScreen.value = event.matches
  }
  isNarrowScreen.value = mediaQueryList.matches
  if (mediaQueryList.addEventListener) {
    mediaQueryList.addEventListener('change', mediaQueryListener)
  } else {
    mediaQueryList.addListener?.(mediaQueryListener)
  }
})

onUnmounted(() => {
  if (mediaQueryList && mediaQueryListener) {
    if (mediaQueryList.removeEventListener) {
      mediaQueryList.removeEventListener('change', mediaQueryListener)
    } else {
      mediaQueryList.removeListener?.(mediaQueryListener)
    }
  }
})

</script>

<style scoped>
.sidebar {
  width: 200px;
  background: linear-gradient(180deg, #09061B 0%, #0d0a1f 100%);
  border-right: none;
  transition: width 0.2s ease-out;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.85);
}

.sidebar--collapsed {
  width: 68px;
}

.sidebar__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  margin: 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: rgba(255, 255, 255, 0.6);
  transition: var(--transition);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 8px;
}

.sidebar__toggle:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
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
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  color: rgba(255, 255, 255, 0.78);
  text-decoration: none;
  font-size: 15px;
  font-weight: var(--fw-medium);
  transition: var(--transition);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border-left: 3px solid transparent;
}

.nav-item:hover:not(.nav-item--active) {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.95);
}

.nav-item--active {
  background: var(--color-sidebar-active);
  color: var(--color-bg-deep);
  font-weight: 700;
  box-shadow: 0 2px 12px rgba(244, 218, 76, 0.25);
  border-radius: var(--radius-sm);
  border-left-color: transparent;
}

.nav-item--child {
  padding: 8px 16px 8px 48px;
  font-size: 14px;
  border-left: none;
}

.nav-item--child.nav-item--active {
  border-left: none;
  color: var(--color-bg-deep);
  background: var(--color-sidebar-active);
  font-weight: 700;
}

.nav-item__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
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
  padding: 11px 16px;
  border-radius: var(--radius-sm);
  color: rgba(255, 255, 255, 0.85);
  font-size: 15px;
  font-weight: var(--fw-semibold);
  cursor: pointer;
  transition: var(--transition);
  white-space: nowrap;
  user-select: none;
}

.nav-group__header:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
}

.nav-group__header--active {
  color: #ffffff;
}

.nav-group__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 13px;
  letter-spacing: 0.02em;
  color: rgba(255, 255, 255, 0.5);
  font-weight: 600;
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
  border-bottom: 2px solid var(--color-sidebar-active);
}

.sidebar--collapsed .nav-group__header {
  justify-content: center;
  padding: 10px;
}
</style>
