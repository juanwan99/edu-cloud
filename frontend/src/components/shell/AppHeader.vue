<template>
  <header class="app-header">
    <div class="app-header__left">
      <div class="app-header__brand" @click="$router.push('/')">
        <span class="app-header__logo">
          <img src="../../assets/images/logo.png" alt="微与积" width="36" height="36" />
        </span>
        <span class="app-header__title">微与积</span>
      </div>
      <SchoolContext />
    </div>

    <nav class="app-header__nav" aria-label="主导航">
      <router-link
        v-for="item in navItems"
        :key="item.route"
        :to="item.route"
        :class="['app-header__nav-item', { 'app-header__nav-item--active': isNavActive(item) }]"
      >
        {{ item.label }}
      </router-link>
    </nav>

    <div class="app-header__right">
      <!-- Search placeholder -->
      <div class="app-header__search">
        <svg class="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="7" cy="7" r="5" stroke="currentColor" stroke-width="1.4"/>
          <path d="M11 11l3 3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
        </svg>
        <input
          class="search-input"
          type="text"
          placeholder="搜索…"
        />
      </div>

      <!-- Notification bell -->
      <NotificationBell />

      <!-- Role switcher + avatar menu -->
      <RoleSwitcher compact />
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import SchoolContext from './SchoolContext.vue'
import NotificationBell from './NotificationBell.vue'
import RoleSwitcher from './RoleSwitcher.vue'
import { useAuthStore } from '../../stores/auth.js'
import { getHeaderNavItems, moduleGateFromAuth } from '../../config/routeAccess.js'
import { normalizeRole } from '../../config/roles.js'

const route = useRoute()
const auth = useAuthStore()

// Phase 0.7A：移除 moduleFallbacks 放行（模块未加载即放 4 个默认模块入口的 fail-open）。
// 改用门控上下文：学校用户在未加载/加载失败/空列表时模块导航 fail-closed 隐藏，admin 豁免。
const navItems = computed(() => {
  const role = normalizeRole(auth.currentRole?.role)
  return getHeaderNavItems(role, moduleGateFromAuth(auth))
})

function isNavActive(item) {
  if (item.exact) return route.path === item.route
  return route.path.startsWith(item.match || item.route)
}
</script>

<style scoped>
.app-header {
  position: static;
  flex: 0 0 64px;
  width: 100%;
  height: 64px;
  background: var(--surface-header-gradient);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: none;
  z-index: auto;
  display: grid;
  grid-template-columns: minmax(280px, auto) 1fr auto;
  align-items: center;
  gap: 24px;
  padding: 0 32px;
  color: #ffffff;
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.app-header__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
  user-select: none;
  min-width: 0;
}

.app-header__logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.app-header__logo img {
  width: 36px;
  height: 36px;
  display: block;
}

.app-header__title {
  font-size: 19px;
  font-weight: var(--fw-heavy);
  color: #ffffff;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.app-header__nav {
  justify-self: center;
  display: flex;
  align-items: center;
  gap: 3px;
  max-width: 100%;
  padding: 4px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.07);
  overflow: hidden;
}

.app-header__nav-item {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 24px;
  border-radius: var(--radius-pill);
  color: #838093;
  font-size: 15px;
  font-weight: 600;
  line-height: 1;
  text-decoration: none;
  white-space: nowrap;
  transition: color 0.15s ease, background-color 0.15s ease, box-shadow 0.2s ease;
}

.app-header__nav-item:hover {
  color: #bbb8cc;
}

.app-header__nav-item--active {
  background: var(--color-accent);
  color: var(--color-bg-deep);
  font-weight: 700;
  box-shadow: 0 2px 12px rgba(244, 218, 76, 0.30);
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.app-header__search {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 0 14px;
  font-size: 15px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  color: #838093;
  transition: var(--transition);
}

.app-header__search:focus-within,
.app-header__search:hover {
  background: rgba(255, 255, 255, 0.09);
  color: #bbb8cc;
}

.search-icon {
  flex-shrink: 0;
}

.search-input {
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  color: rgba(255, 255, 255, 0.9);
  width: 132px;
  font-family: inherit;
}

.search-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}

:deep(.school-context) {
  min-height: 34px;
  padding: 0 14px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.72);
  font-size: 13px;
}

:deep(.bell-btn) {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  color: #838093;
}

:deep(.bell-btn:hover) {
  background: rgba(255, 255, 255, 0.06);
  color: #bbb8cc;
}

:deep(.role-switcher) {
  border-radius: 12px;
  padding: 0;
}

:deep(.role-switcher:hover) {
  background: transparent;
}

:deep(.role-switcher__avatar) {
  width: 42px;
  height: 42px;
  border: none;
  background: var(--color-accent);
  color: var(--color-bg-deep);
  font-size: 15px;
  font-weight: 800;
  box-shadow: 0 3px 12px rgba(244, 218, 76, 0.25);
}

@media (max-width: 1180px) {
  .app-header {
    grid-template-columns: minmax(220px, auto) auto;
  }

  .app-header__nav {
    display: none;
  }
}

@media (max-width: 860px) {
  .app-header {
    grid-template-columns: minmax(0, 1fr) auto;
    padding-right: 16px;
    padding-left: 16px;
    gap: 12px;
  }

  .app-header__search {
    display: none;
  }

  :deep(.school-context) {
    display: none;
  }
}
</style>
