<template>
  <header class="top-nav">
    <div class="logo">
      <span class="logo-icon">🎓</span>
      <span class="logo-text">edu-cloud</span>
    </div>
    <nav class="nav-items">
      <div
        v-for="menu in authStore.menus"
        :key="menu.code"
        class="nav-item"
        :class="{ active: activeModule?.code === menu.code }"
        @click="navigateToModule(menu)"
      >
        {{ menu.name }}
      </div>
    </nav>
    <div class="nav-right">
      <div class="ai-trigger" title="AI 助手" @click="$emit('toggle-ai')">
        🤖
      </div>
      <UserDropdown />
    </div>
  </header>
</template>

<script setup lang="ts">
const authStore = useAuthStore()
const { activeModule, navigateToModule } = useMenus()

defineEmits(['toggle-ai'])
</script>

<style scoped lang="scss">
.top-nav {
  height: var(--hfs-header-height);
  background: linear-gradient(135deg, var(--hfs-primary), #53a8ff);
  display: flex;
  align-items: center;
  padding: 0 20px;
  color: #fff;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-right: 30px;
  font-weight: bold;
  font-size: 16px;
  flex-shrink: 0;
}

.nav-items {
  display: flex;
  gap: 4px;
  flex: 1;
  justify-content: center;
}

.nav-item {
  padding: 6px 16px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;

  &:hover {
    background: rgba(255, 255, 255, 0.15);
  }

  &.active {
    background: rgba(255, 255, 255, 0.3);
    font-weight: 600;
  }
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.ai-trigger {
  cursor: pointer;
  font-size: 18px;
}
</style>
