<template>
  <WorkbenchLayout>
    <template #header>
      <n-h3 style="margin: 0">edu-cloud 智能平台</n-h3>
      <n-space align="center">
        <n-text>{{ authStore.displayName }}</n-text>
        <n-dropdown :options="roleOptions" @select="handleRoleSwitch">
          <n-tag type="info" style="cursor: pointer">{{ authStore.roleName }}</n-tag>
        </n-dropdown>
        <n-button size="small" @click="authStore.logout">登出</n-button>
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
import { computed } from 'vue'
import WorkbenchLayout from '../layouts/WorkbenchLayout.vue'
import ContextPanel from '../components/context/ContextPanel.vue'
import DataView from '../components/workspace/DataView.vue'
import StudioPanel from '../components/studio/StudioPanel.vue'
import { useAuthStore } from '../stores/auth.js'

const authStore = useAuthStore()

const roleOptions = computed(() =>
  authStore.roles.map((r, i) => ({ label: r.role, key: i }))
)

function handleRoleSwitch(index) {
  authStore.switchRole(index)
}
</script>
