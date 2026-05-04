<template>
  <div>
    <n-page-header title="德育设置" class="section-gap" />

    <n-tabs v-model:value="activeTab" type="line" animated @update:value="onTabChange">
      <n-tab-pane name="rules" tab="班规管理">
        <ConductRules />
      </n-tab-pane>
      <n-tab-pane name="groups" tab="小组管理">
        <ConductGroups />
      </n-tab-pane>
      <n-tab-pane v-if="canManageParents" name="parents" tab="家长绑定">
        <ConductParents />
      </n-tab-pane>
      <n-tab-pane name="config" tab="预警与学期">
        <ConductSettings />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NPageHeader, NTabs, NTabPane } from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions.js'
import ConductRules from './ConductRules.vue'
import ConductGroups from './ConductGroups.vue'
import ConductParents from './ConductParents.vue'
import ConductSettings from './ConductSettings.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeTab = ref(route.query.tab || 'rules')

const role = computed(() => auth.currentRole?.role || '')
const canManageParents = computed(() => hasPermission(role.value, 'manage_conduct_parents'))

const validTabs = ['rules', 'groups', 'parents', 'config']

watch(() => route.query.tab, (tab) => {
  if (tab && validTabs.includes(tab)) {
    activeTab.value = tab
  }
})

function onTabChange(tab) {
  router.replace({ query: { ...route.query, tab } })
}
</script>

<style scoped>
.section-gap {
  margin-bottom: var(--space-4);
}
</style>
