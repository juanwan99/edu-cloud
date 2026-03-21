<template>
  <WorkbenchLayout>
    <template #header>
      <n-h3 style="margin: 0">edu-cloud 智能平台</n-h3>
      <n-space>
        <n-text>{{ authStore.displayName }}</n-text>
        <n-tag type="info">{{ authStore.currentRole }}</n-tag>
      </n-space>
    </template>
    <template #left>
      <ContextPanel />
    </template>
    <template #center>
      <DataView />
    </template>
    <template #right>
      <StudioPanel />
    </template>
  </WorkbenchLayout>
</template>
<script setup>
import WorkbenchLayout from '../layouts/WorkbenchLayout.vue'
import ContextPanel from '../components/context/ContextPanel.vue'
import DataView from '../components/workspace/DataView.vue'
import StudioPanel from '../components/studio/StudioPanel.vue'
import { useAuthStore } from '../stores/auth.js'
const authStore = useAuthStore()
</script>
