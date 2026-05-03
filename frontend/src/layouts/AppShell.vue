<template>
  <div :class="['app-shell', { 'app-shell--workspace': shellMode === 'workspace' }]">
    <div class="app-body">
      <AppSidebar />
      <div class="app-stage">
        <AppHeader />
        <main class="app-main">
          <router-view />
        </main>
      </div>
    </div>
    <AiFloatingButton @toggle="aiPanelOpen = !aiPanelOpen" />
    <AiSlidePanel :visible="aiPanelOpen" @close="aiPanelOpen = false" />
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/shell/AppHeader.vue'
import AppSidebar from '../components/shell/AppSidebar.vue'
import AiFloatingButton from '../components/ai/AiFloatingButton.vue'
import AiSlidePanel from '../components/ai/AiSlidePanel.vue'
import { useAuthStore } from '../stores/auth.js'

const aiPanelOpen = ref(false)
const route = useRoute()
const auth = useAuthStore()
const shellMode = computed(() => route.meta.shellMode)

onMounted(() => {
  if (auth.token && auth.currentRole?.school_id && !auth.modulesLoaded) {
    auth.loadModules()
  }
})

watch(() => route.path, () => { aiPanelOpen.value = false })
</script>

<style scoped>
.app-shell {
  min-height: 100dvh;
  padding: 28px 24px;
  background: var(--surface-page-gradient);
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.app-body {
  width: min(1610px, 100%);
  height: calc(100dvh - 56px);
  display: flex;
  gap: 20px;
  min-width: 0;
}

.app-stage {
  flex: 1 1 auto;
  max-width: 1340px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-stage);
  overflow: hidden;
}

.app-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 28px 36px 40px;
  background: #fff;
}

.app-shell--workspace .app-stage {
  max-width: none;
}

.app-shell--workspace .app-main {
  padding: 0;
  overflow: hidden;
}

:deep(.sidebar) {
  height: 100%;
  border-radius: var(--radius-xl);
  box-shadow: 0 18px 50px rgba(9, 6, 27, 0.12);
}

@media (max-width: 1180px) {
  .app-shell {
    padding: 20px 16px;
  }

  .app-body {
    height: calc(100dvh - 40px);
    gap: 16px;
  }

  :deep(.sidebar) {
    width: 68px !important;
  }

  :deep(.sidebar .nav-item__label),
  :deep(.sidebar .nav-group__label) {
    display: none !important;
  }
}

@media (max-width: 860px) {
  .app-shell {
    padding: 0;
  }

  .app-body {
    width: 100%;
    height: 100dvh;
    gap: 0;
  }

  .app-stage,
  :deep(.sidebar) {
    border-radius: 0;
    box-shadow: none;
  }

  .app-stage {
    max-width: none;
  }
}
</style>
