<template>
  <header class="app-header">
    <div class="app-header__left">
      <div class="app-header__brand" @click="$router.push('/')">
        <span class="app-header__logo">
          <img src="../../assets/images/logo.svg" alt="微与积" width="28" height="28" />
        </span>
        <span class="app-header__title">微与积</span>
      </div>
      <SchoolContext />
    </div>

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
import SchoolContext from './SchoolContext.vue'
import NotificationBell from './NotificationBell.vue'
import RoleSwitcher from './RoleSwitcher.vue'
</script>

<style scoped>
.app-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 64px;
  background: var(--color-bg-deep);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  z-index: var(--z-header);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: env(safe-area-inset-top) 24px 0;
  color: #ffffff;
}

.app-header__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.app-header__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.app-header__logo {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.app-header__title {
  font-size: var(--fs-xl);
  font-weight: var(--fw-heavy);
  color: #ffffff;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.app-header__search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: var(--fs-base);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: var(--radius-sm);
  color: rgba(255, 255, 255, 0.6);
}

.search-icon {
  flex-shrink: 0;
}

.search-input {
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--fs-base);
  color: rgba(255, 255, 255, 0.9);
  width: 140px;
  font-family: inherit;
}

.search-input::placeholder {
  color: rgba(255, 255, 255, 0.5);
}
</style>
