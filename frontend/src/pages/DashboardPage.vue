<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h1 class="page-title">{{ config?.title || '概览' }}</h1>
      <p class="page-subtitle">欢迎回来，{{ auth.user?.display_name }}</p>
    </div>

    <!-- KPI Row -->
    <div class="kpi-row">
      <KpiCard
        v-for="kpi in config?.kpis"
        :key="kpi.id"
        :value="getKpiValue(kpi)"
        :label="kpi.label"
        :color="kpi.color"
      />
    </div>

    <!-- Module Cards Grid -->
    <WidgetGrid :columns="2" class="module-grid">
      <DashboardCard
        v-for="widget in config?.widgets"
        :key="widget.id"
        :title="widget.title"
        :icon="widget.icon"
        :route="widget.route"
        :planned="widget.planned"
      />
    </WidgetGrid>

    <!-- Activity Feed -->
    <ActivityFeed :items="activityItems" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getDashboardConfig } from '../config/dashboardConfig'
import { normalizeRole } from '../config/roles'
import KpiCard from '../components/dashboard/KpiCard.vue'
import DashboardCard from '../components/dashboard/DashboardCard.vue'
import WidgetGrid from '../components/dashboard/WidgetGrid.vue'
import ActivityFeed from '../components/dashboard/ActivityFeed.vue'
import client from '../api/client.js'

const auth = useAuthStore()
const role = computed(() => normalizeRole(auth.currentRole?.role || ''))
const config = computed(() => getDashboardConfig(role.value))

// KPI data from API
const kpiData = ref({})
const loading = ref(true)

onMounted(async () => {
  try {
    const { data } = await client.get('/dashboard/summary')
    kpiData.value = data
  } catch { /* API error — will show "--" for missing values */ }
  loading.value = false
})

function getKpiValue(kpi) {
  if (kpi.source === 'dashboard_summary') return kpiData.value[kpi.id] ?? '--'
  if (kpi.source === 'local') return '--'
  if (kpi.source === 'notifications') return '--'
  if (kpi.source === 'schools') return kpiData.value[kpi.id] ?? '--'
  if (kpi.source === 'joint_exams') return kpiData.value[kpi.id] ?? '--'
  if (kpi.source === 'ai_health') return '--'
  return '--'
}

// Placeholder activity items
const activityItems = [
  { time: '今天 14:30', text: '系统已就绪', type: 'system' },
]
</script>

<style scoped>
.dashboard-page {
  max-width: 1200px;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 32px;
}

.module-grid {
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
