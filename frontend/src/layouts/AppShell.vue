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
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '../components/shell/AppHeader.vue'
import AppSidebar from '../components/shell/AppSidebar.vue'
import AiFloatingButton from '../components/ai/AiFloatingButton.vue'
import AiSlidePanel from '../components/ai/AiSlidePanel.vue'

const aiPanelOpen = ref(false)
const route = useRoute()

// Close AI panel on route change (e.g. "open in workbench" link)
watch(() => route.path, () => { aiPanelOpen.value = false })
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-body {
  display: flex;
  flex: 1;
  margin-top: 68px;
  min-height: calc(100vh - 68px);
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: var(--color-bg-alt);
}
</style>
