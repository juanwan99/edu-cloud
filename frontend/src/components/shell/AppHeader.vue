<template>
  <header class="app-header">
    <div class="app-header__left">
      <div class="app-header__brand" @click="$router.push('/')">
        <span class="app-header__logo">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="8" fill="var(--macaron-mint)"/>
            <path d="M8 10h12M8 14h8M8 18h10" stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </span>
        <span class="app-header__title">edu-cloud 智能平台</span>
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
          placeholder="搜索..."
          disabled
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
  height: 68px;
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid var(--color-border-light);
  z-index: var(--z-header);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: env(safe-area-inset-top) 24px 0;
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
  font-size: 18px;
  font-weight: 800;
  color: var(--color-primary);
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.app-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-header__search {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  background: var(--color-bg-alt);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
}

.search-icon {
  flex-shrink: 0;
}

.search-input {
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--color-text-muted);
  width: 120px;
  cursor: not-allowed;
  font-family: inherit;
}

.search-input::placeholder {
  color: var(--color-text-muted);
}
</style>
