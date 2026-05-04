<template>
  <div>
    <n-page-header title="德育工作台" class="section-gap">
      <template #extra>
        <n-space :size="12" align="center">
          <n-tag v-if="scopeLabel" :type="scopeTagType" size="small">{{ scopeLabel }}</n-tag>
        </n-space>
      </template>
    </n-page-header>

    <n-tabs v-model:value="activeTab" type="line" animated @update:value="onTabChange">
      <n-tab-pane name="overview" tab="概览">
        <ConductDashboard />
      </n-tab-pane>
      <n-tab-pane v-if="canManageConduct" name="points" tab="记积分">
        <ConductPoints />
      </n-tab-pane>
      <n-tab-pane name="records" tab="记录">
        <ConductRecords />
      </n-tab-pane>
      <n-tab-pane name="rankings" tab="排行">
        <ConductRankings />
      </n-tab-pane>
    </n-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NPageHeader, NTabs, NTabPane, NTag, NSpace } from 'naive-ui'
import { useAuthStore } from '../../stores/auth'
import { hasPermission } from '../../config/permissions.js'
import ConductDashboard from './ConductDashboard.vue'
import ConductPoints from './ConductPoints.vue'
import ConductRecords from './ConductRecords.vue'
import ConductRankings from './ConductRankings.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeTab = ref(route.query.tab || 'overview')

const role = computed(() => auth.currentRole?.role || '')
const canManageConduct = computed(() => hasPermission(role.value, 'manage_conduct'))

const scopeLabel = computed(() => {
  const r = role.value
  if (r === 'district_admin') return '区域视图'
  if (r === 'principal' || r === 'academic_director') return '全校视图'
  if (r === 'grade_leader') return '年级视图'
  if (r === 'homeroom_teacher') return '班级视图'
  if (r === 'subject_teacher') return '任教班视图'
  return null
})

const scopeTagType = computed(() => {
  const r = role.value
  if (r === 'district_admin') return 'warning'
  if (r === 'principal' || r === 'academic_director') return 'info'
  return 'default'
})

function onTabChange(tab) {
  router.replace({ query: { ...route.query, tab } })
}

onMounted(() => {
  if (route.query.tab && ['overview', 'points', 'records', 'rankings'].includes(route.query.tab)) {
    activeTab.value = route.query.tab
  }
})
</script>

<style scoped>
.section-gap {
  margin-bottom: var(--space-4);
}
</style>
