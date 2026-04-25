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

    <!-- Charts Row -->
    <div class="charts-row" v-if="trendOption || classOption">
      <div class="chart-card" v-if="trendOption">
        <h3 class="chart-title">考试成绩趋势</h3>
        <v-chart :option="trendOption" style="height: 280px;" autoresize />
      </div>
      <div class="chart-card" v-if="classOption">
        <h3 class="chart-title">班级平均分对比</h3>
        <v-chart :option="classOption" style="height: 280px;" autoresize />
      </div>
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
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getDashboardConfig } from '../config/dashboardConfig'
import { normalizeRole } from '../config/roles'
import KpiCard from '../components/dashboard/KpiCard.vue'
import DashboardCard from '../components/dashboard/DashboardCard.vue'
import WidgetGrid from '../components/dashboard/WidgetGrid.vue'
import ActivityFeed from '../components/dashboard/ActivityFeed.vue'
import client from '../api/client.js'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const auth = useAuthStore()
const role = computed(() => normalizeRole(auth.currentRole?.role || ''))
const config = computed(() => getDashboardConfig(role.value))

const kpiData = ref({})
const loading = ref(true)
const trendOption = ref(null)
const classOption = ref(null)
const activityItems = ref([])

async function fetchKpiData() {
  loading.value = true
  kpiData.value = {}
  try {
    const { data } = await client.get('/dashboard/summary')
    kpiData.value = data
  } catch { /* will show "--" */ }
  loading.value = false
}

async function fetchCharts() {
  try {
    const { data: exams } = await client.get('/exams', { params: { limit: 10 } })
    const examList = Array.isArray(exams) ? exams : (exams.items || [])
    const completed = examList.filter(e => e.status === 'completed' || e.status === 'published')
    if (completed.length < 1) return

    const examIds = completed.slice(0, 5).map(e => e.id).join(',')

    // Grade trend
    try {
      const { data: trend } = await client.get('/analytics/report/trend/grade', { params: { exam_ids: examIds } })
      if (trend.points?.length >= 2) {
        trendOption.value = {
          tooltip: { trigger: 'axis' },
          grid: { left: 50, right: 20, top: 30, bottom: 40 },
          xAxis: { type: 'category', data: trend.points.map(p => p.exam_name?.slice(0, 10) || '') },
          yAxis: { type: 'value', name: '分数' },
          series: [
            { name: '平均分', type: 'line', smooth: true, data: trend.points.map(p => p.avg?.toFixed(1)), itemStyle: { color: '#2a9d8f' } },
            { name: '及格率%', type: 'line', smooth: true, data: trend.points.map(p => (p.pass_rate * 100)?.toFixed(1)), itemStyle: { color: '#f4a261' } },
          ],
        }
      }
    } catch { /* no trend data */ }

    // Class comparison (use first completed exam, top 10 classes by median)
    try {
      const firstExam = completed[0]
      const { data: classData } = await client.get(`/analytics/exam/${firstExam.id}/class-boxplot`)
      const classes = classData.classes || []
      if (classes.length > 0) {
        const sorted = [...classes].sort((a, b) => (b.median || 0) - (a.median || 0)).slice(0, 10)
        classOption.value = {
          tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>中位数: ${p[0].value}` },
          grid: { left: 50, right: 20, top: 20, bottom: 60 },
          xAxis: { type: 'category', data: sorted.map(c => c.name || ''), axisLabel: { rotate: 30, fontSize: 11 } },
          yAxis: { type: 'value', name: '中位数' },
          series: [{
            type: 'bar',
            data: sorted.map(c => c.median ?? 0),
            itemStyle: { color: '#6c5ce7', borderRadius: [4, 4, 0, 0] },
          }],
        }
      }
    } catch { /* no class data */ }
  } catch { /* no exams */ }
}

async function fetchActivity() {
  const items = []
  try {
    const { data: exams } = await client.get('/exams', { params: { limit: 5 } })
    const examList = Array.isArray(exams) ? exams : (exams.items || [])
    for (const e of examList.slice(0, 3)) {
      const date = e.created_at ? new Date(e.created_at) : new Date()
      const dateStr = date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
      const timeStr = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      const statusText = { draft: '已创建', published: '已发布', completed: '已完成' }[e.status] || e.status
      items.push({ time: `${dateStr} ${timeStr}`, text: `考试「${e.name}」${statusText}`, type: 'exam' })
    }
  } catch { /* no exams */ }

  try {
    const { data: notifications } = await client.get('/notifications', { params: { since: 'week' } })
    const list = Array.isArray(notifications) ? notifications : []
    for (const n of list.slice(0, 3)) {
      const date = n.created_at ? new Date(n.created_at) : new Date()
      const dateStr = date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
      const timeStr = date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      items.push({ time: `${dateStr} ${timeStr}`, text: n.title || n.summary || '通知', type: 'info' })
    }
  } catch { /* no notifications */ }

  if (items.length === 0) {
    items.push({ time: '今天', text: '系统已就绪', type: 'system' })
  }
  activityItems.value = items
}

onMounted(() => {
  fetchKpiData()
  fetchCharts()
  fetchActivity()
})
watch(() => auth.currentRoleIndex, () => {
  fetchKpiData()
  fetchCharts()
  fetchActivity()
})

function getKpiValue(kpi) {
  if (kpi.source === 'dashboard_summary') return kpiData.value[kpi.id] ?? '--'
  return '--'
}
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

.charts-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 32px;
}

.chart-card {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 20px;
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--color-text);
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
