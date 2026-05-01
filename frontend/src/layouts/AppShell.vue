<template>
  <div class="app-shell">
    <AppHeader />
    <div class="app-body">
      <AppSidebar />
      <main class="app-main">
        <router-view />
      </main>
    </div>
    <AiFloatingButton @toggle="aiPanelOpen = !aiPanelOpen" />
    <AiSlidePanel :visible="aiPanelOpen" @close="aiPanelOpen = false" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/shell/AppHeader.vue'
import AppSidebar from '../components/shell/AppSidebar.vue'
import AiFloatingButton from '../components/ai/AiFloatingButton.vue'
import AiSlidePanel from '../components/ai/AiSlidePanel.vue'
import { useAuthStore } from '../stores/auth.js'

const aiPanelOpen = ref(false)
const route = useRoute()
const auth = useAuthStore()

onMounted(() => {
  if (auth.token && auth.currentRole?.school_id && !auth.modulesLoaded) {
    auth.loadModules()
  }
})

watch(() => route.path, () => { aiPanelOpen.value = false })
</script>

<style scoped>
.app-shell {
  height: 100dvh;
  display: flex;
  flex-direction: column;
}

.app-body {
  display: flex;
  flex: 1;
  margin-top: 64px;
  height: calc(100dvh - 64px);
  overflow: hidden;
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 32px;
  background: var(--color-bg);
}
</style>
