<template>
  <div class="dashboard-page">
    <div class="page-header">
      <h1 class="page-title">{{ config?.title || '概览' }}</h1>
      <p class="page-subtitle">欢迎回来，{{ auth.user?.display_name }}</p>
    </div>

    <!-- Welcome Banner (first login / no exams) -->
    <div v-if="showWelcome" class="welcome-banner">
      <div class="welcome-banner__content">
        <h2 class="welcome-banner__title">欢迎使用教育云平台</h2>
        <p class="welcome-banner__text">从创建第一场考试开始，开启智能教学之旅</p>
        <n-button type="primary" @click="router.push('/exams')">创建考试</n-button>
      </div>
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

    <!-- Quick Actions -->
    <div class="quick-actions">
      <n-button
        v-for="action in quickActions"
        :key="action.label"
        class="quick-action-btn"
        :type="action.type || 'default'"
        secondary
        @click="router.push(action.route)"
      >
        <template #icon>
          <span class="quick-action-icon" :style="actionIconStyle(action.icon)" />
        </template>
        {{ action.label }}
      </n-button>
    </div>

    <!-- Todo Reminders -->
    <div v-if="todoItems.length > 0" class="todo-section">
      <div
        v-for="todo in todoItems"
        :key="todo.label"
        class="todo-item"
        @click="router.push(todo.route)"
      >
        <span :class="['todo-dot', `todo-dot--${todo.color}`]" />
        <span class="todo-text">{{ todo.label }}</span>
        <n-tag :type="todo.tagType" size="small" round>{{ todo.count }}</n-tag>
      </div>
    </div>

    <!-- Charts Row (with empty state) -->
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
    <div v-else-if="!loading" class="chart-empty">
      <p class="chart-empty__text">暂无考试数据，完成考试后将自动生成趋势图表</p>
    </div>

    <!-- Recent Exams Cards -->
    <div v-if="recentExams.length > 0" class="recent-exams">
      <h3 class="section-title">最近考试</h3>
      <div class="exam-cards-row">
        <div
          v-for="exam in recentExams"
          :key="exam.id"
          class="exam-card"
          @click="router.push(`/exams/${exam.id}`)"
        >
          <div class="exam-card__header">
            <span class="exam-card__name">{{ exam.name }}</span>
            <n-tag :type="examStatusType(exam.status)" size="small" round>
              {{ examStatusText(exam.status) }}
            </n-tag>
          </div>
          <div class="exam-card__meta">
            <span v-if="exam.subject_count != null">{{ exam.subject_count }} 个科目</span>
            <span v-if="exam.created_at">{{ formatDate(exam.created_at) }}</span>
          </div>
          <n-progress
            v-if="exam.status === 'grading' && exam.grading_progress != null"
            type="line"
            :percentage="exam.grading_progress"
            :show-indicator="false"
            :height="4"
            style="margin-top: 8px;"
          />
        </div>
      </div>
      <div class="recent-exams__footer">
        <n-button text type="primary" @click="router.push('/exams')">查看全部考试 &rarr;</n-button>
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
import { useRouter } from 'vue-router'
import { NButton, NTag, NProgress } from 'naive-ui'
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

const router = useRouter()
const auth = useAuthStore()
const role = computed(() => normalizeRole(auth.currentRole?.role || ''))
const config = computed(() => getDashboardConfig(role.value))

// Chart theme colors — read from CSS vars for dark-mode compatibility
const chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--color-text').trim() || '#1a2e1f'
const chartSplitColor = getComputedStyle(document.documentElement).getPropertyValue('--color-border-light').trim() || '#f0f4f1'

const kpiData = ref({})
const loading = ref(true)
const trendOption = ref(null)
const classOption = ref(null)
const activityItems = ref([])
const recentExams = ref([])
const todoItems = ref([])

// Quick actions config (role-aware)
const quickActions = computed(() => {
  const r = role.value
  const actions = [
    { label: '创建考试', icon: 'exam', route: '/exams', type: 'primary' },
    { label: '布置作业', icon: 'document', route: '/homework' },
    { label: '阅卷调度', icon: 'marking', route: '/grading/tasks' },
    { label: '成绩分析', icon: 'chart', route: '/analytics/report' },
  ]
  // Teachers see all 4; admin roles see all 4 too
  if (r === 'parent') return []
  return actions
})

// Icon mask style for quick action buttons
const ICON_SVGS = {
  exam: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z'/%3E%3Cpath d='M14 2v6h6M9 15l2 2 4-4'/%3E%3C/svg%3E",
  document: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z'/%3E%3Cpath d='M14 2v6h6M16 13H8M16 17H8M10 9H8'/%3E%3C/svg%3E",
  marking: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7'/%3E%3Cpath d='M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z'/%3E%3C/svg%3E",
  chart: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M18 20V10M12 20V4M6 20v-6'/%3E%3C/svg%3E",
}

function actionIconStyle(icon) {
  const svg = ICON_SVGS[icon]
  if (!svg) return {}
  return {
    display: 'inline-block',
    width: '16px',
    height: '16px',
    backgroundColor: 'currentColor',
    maskImage: `url("${svg}")`,
    WebkitMaskImage: `url("${svg}")`,
    maskSize: 'contain',
    WebkitMaskSize: 'contain',
    maskRepeat: 'no-repeat',
    WebkitMaskRepeat: 'no-repeat',
  }
}

// Welcome banner: show when no exams exist yet
const showWelcome = computed(() => {
  return !loading.value && (kpiData.value.total_exams === 0 || kpiData.value.total_exams == null) && recentExams.value.length === 0
})

// Exam status helpers
function examStatusType(status) {
  const map = { draft: 'default', published: 'info', grading: 'warning', completed: 'success' }
  return map[status] || 'default'
}

function examStatusText(status) {
  const map = { draft: '草稿', published: '已发布', grading: '阅卷中', completed: '已完成' }
  return map[status] || status
}

function formatDate(dateStr) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

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

    // Populate recent exams cards (top 3)
    recentExams.value = examList.slice(0, 3).map(e => ({
      id: e.id,
      name: e.name,
      status: e.status,
      subject_count: e.subjects?.length ?? e.subject_count ?? null,
      created_at: e.created_at,
      grading_progress: e.grading_progress ?? null,
    }))

    const completed = examList.filter(e => e.status === 'completed' || e.status === 'published')
    if (completed.length < 1) return

    const examIds = completed.slice(0, 5).map(e => e.id).join(',')

    // Grade trend
    try {
      const { data: trend } = await client.get('/analytics/report/trend/grade', { params: { exam_ids: examIds } })
      if (trend.points?.length >= 2) {
        trendOption.value = {
          backgroundColor: 'transparent',
          textStyle: { color: chartTextColor },
          tooltip: { trigger: 'axis' },
          legend: { data: ['平均分', '及格率'], bottom: 0, textStyle: { color: chartTextColor } },
          grid: { left: 50, right: 50, top: 20, bottom: 40 },
          xAxis: { type: 'category', data: trend.points.map(p => p.exam_name?.slice(0, 10) || ''), axisLabel: { color: chartTextColor } },
          yAxis: [
            { type: 'value', name: '分数', position: 'left', nameTextStyle: { color: chartTextColor }, axisLabel: { color: chartTextColor }, splitLine: { lineStyle: { color: chartSplitColor } } },
            { type: 'value', name: '及格率', position: 'right', max: 100, axisLabel: { formatter: '{value}%', color: chartTextColor }, nameTextStyle: { color: chartTextColor }, splitLine: { show: false } },
          ],
          series: [
            { name: '平均分', type: 'line', smooth: true, data: trend.points.map(p => p.avg?.toFixed(1)), itemStyle: { color: '#2a9d8f' } },
            { name: '及格率', type: 'line', smooth: true, yAxisIndex: 1, data: trend.points.map(p => (p.pass_rate * 100)?.toFixed(1)), itemStyle: { color: '#f4a261' } },
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
          backgroundColor: 'transparent',
          textStyle: { color: chartTextColor },
          tooltip: { trigger: 'axis', formatter: (p) => `${p[0].name}<br/>中位数: ${p[0].value}` },
          grid: { left: 50, right: 20, top: 20, bottom: 60 },
          xAxis: { type: 'category', data: sorted.map(c => c.name || ''), axisLabel: { rotate: 30, fontSize: 11, color: chartTextColor } },
          yAxis: { type: 'value', name: '中位数', nameTextStyle: { color: chartTextColor }, axisLabel: { color: chartTextColor }, splitLine: { lineStyle: { color: chartSplitColor } } },
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

async function fetchTodos() {
  const items = []
  try {
    // Grading tasks in progress
    const { data: tasks } = await client.get('/grading/tasks')
    const taskList = Array.isArray(tasks) ? tasks : (tasks.items || [])
    const processing = taskList.filter(t => t.status === 'processing' || t.status === 'pending')
    if (processing.length > 0) {
      items.push({ label: `${processing.length} 个阅卷任务进行中`, count: processing.length, route: '/grading/tasks', color: 'coral', tagType: 'warning' })
    }
  } catch { /* grading tasks not accessible */ }

  try {
    // Exams pending grading
    const { data: exams } = await client.get('/exams', { params: { limit: 50 } })
    const examList = Array.isArray(exams) ? exams : (exams.items || [])
    const pendingGrading = examList.filter(e => e.status === 'grading')
    if (pendingGrading.length > 0) {
      items.push({ label: `${pendingGrading.length} 场考试待阅卷`, count: pendingGrading.length, route: '/exams', color: 'yellow', tagType: 'info' })
    }
  } catch { /* exams not accessible */ }

  try {
    // Homework tasks with pending submissions
    const { data: hwTasks } = await client.get('/homework/tasks', { params: { status: 'active' } })
    const hwList = Array.isArray(hwTasks) ? hwTasks : (hwTasks.items || [])
    const pendingHw = hwList.filter(t => t.stats?.pending > 0 || t.status === 'active')
    if (pendingHw.length > 0) {
      items.push({ label: `${pendingHw.length} 份作业待批改`, count: pendingHw.length, route: '/homework', color: 'purple', tagType: 'default' })
    }
  } catch { /* homework not accessible */ }

  todoItems.value = items
}

onMounted(() => {
  fetchKpiData()
  fetchCharts()
  fetchActivity()
  fetchTodos()
})
watch(() => auth.currentRoleIndex, () => {
  fetchKpiData()
  fetchCharts()
  fetchActivity()
  fetchTodos()
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

/* Welcome banner */
.welcome-banner {
  background: linear-gradient(135deg, var(--macaron-mint-light) 0%, var(--macaron-purple-light) 100%);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border-light);
  padding: 32px;
  margin-bottom: 24px;
}

.welcome-banner__title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 8px;
}

.welcome-banner__text {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0 0 16px;
}

/* KPI row */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

/* Quick actions */
.quick-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.quick-action-btn {
  border-radius: var(--radius-pill) !important;
}

.quick-action-icon {
  vertical-align: middle;
}

/* Todo section */
.todo-section {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: var(--color-bg-card, rgba(255,255,255,0.04));
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  cursor: pointer;
  transition: var(--transition);
}

.todo-item:hover {
  border-color: var(--color-border);
  box-shadow: var(--shadow-sm);
}

.todo-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.todo-dot--coral { background: var(--macaron-coral); }
.todo-dot--yellow { background: var(--macaron-yellow); }
.todo-dot--purple { background: var(--macaron-purple); }

.todo-text {
  font-size: 14px;
  color: var(--color-text);
}

/* Charts */
.charts-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 24px;
  margin-bottom: 24px;
}

.chart-card {
  background: var(--color-bg-card, rgba(255,255,255,0.04));
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

.chart-empty {
  background: var(--color-bg-card, rgba(255,255,255,0.04));
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-border);
  padding: 40px;
  text-align: center;
  margin-bottom: 24px;
}

.chart-empty__text {
  font-size: 14px;
  color: var(--color-text-muted);
  margin: 0;
}

/* Section title */
.section-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 16px;
}

/* Recent exams */
.recent-exams {
  margin-bottom: 24px;
}

.exam-cards-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}

.exam-card {
  background: var(--color-bg-card, rgba(255,255,255,0.04));
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 16px 20px;
  cursor: pointer;
  transition: var(--transition);
}

.exam-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
  border-color: var(--color-border);
}

.exam-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.exam-card__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.exam-card__meta {
  display: flex;
  gap: 12px;
  font-size: 13px;
  color: var(--color-text-muted);
}

.recent-exams__footer {
  margin-top: 12px;
  text-align: right;
}

/* Module grid */
.module-grid {
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .quick-actions {
    flex-direction: column;
  }

  .todo-section {
    flex-direction: column;
  }
}
</style>
