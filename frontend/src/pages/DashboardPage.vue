<template>
  <div class="dashboard-page">
    <h1 class="greeting">早上好，{{ auth.user?.display_name || '老师' }}</h1>

    <!-- Welcome Banner (first login / no exams) -->
    <div v-if="showWelcome" class="welcome-banner">
      <div class="welcome-banner__content">
        <h2 class="welcome-banner__title">欢迎使用教育云平台</h2>
        <p class="welcome-banner__text">从创建第一场考试开始，开启智能教学之旅</p>
        <n-button type="primary" @click="router.push('/exams')">创建考试</n-button>
      </div>
    </div>

    <!-- KPI Row -->
    <div class="stat-row">
      <div
        v-for="kpi in dashboardKpis"
        :key="kpi.id"
        :class="['stat-card', 'dashboard-stat', `dashboard-stat--${kpi.tone}`]"
      >
        <div :class="['stat-icon', `stat-icon--${kpi.tone}`]">
          <AppIcon :name="kpi.icon" :size="20" />
        </div>
        <div class="stat-label">{{ kpi.label }}</div>
        <div class="stat-value">{{ getKpiValue(kpi) }}</div>
      </div>
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

    <div class="dashboard-grid">
      <div class="dashboard-left">
        <!-- Main Chart (with empty state) -->
        <div v-if="trendOption" class="card chart-card">
          <div class="card-head">
            <div>
              <div class="card-title">成绩趋势</div>
              <div class="card-sub">跟踪最近考试表现</div>
            </div>
            <div class="toggle" aria-label="图表周期切换">
              <button type="button" class="toggle__item">周</button>
              <button type="button" class="toggle__item active">月</button>
              <button type="button" class="toggle__item">学期</button>
            </div>
          </div>
          <div class="chart-legend">
            <span class="chart-legend__item">
              <span class="chart-legend__dot chart-legend__dot--purple" />
              平均分
            </span>
            <span class="chart-legend__item">
              <span class="chart-legend__dot chart-legend__dot--yellow" />
              及格率
            </span>
          </div>
          <v-chart class="chart-height-md" :option="trendOption" autoresize />
        </div>
        <div v-else-if="!loading" class="card chart-card chart-empty">
          <p class="chart-empty__text">暂无考试数据，完成考试后将自动生成趋势图表</p>
          <n-button type="primary" style="margin-top: 16px;" @click="router.push('/exams')">创建考试</n-button>
        </div>

        <div class="dashboard-split">
          <div class="card">
            <div class="card-head">
              <div class="card-title">阅卷进度</div>
              <span class="card-meta">本月</span>
            </div>
            <template v-if="gradingProgressItems.length > 0">
              <div v-for="item in gradingProgressItems" :key="item.id" class="prog">
                <div class="prog-head">
                  <span class="prog-label">{{ item.name }}</span>
                  <span class="prog-val">{{ item.progressText }}</span>
                </div>
                <div class="prog-track">
                  <div
                    :class="['prog-fill', `prog-fill--${item.tone}`]"
                    :style="{ width: `${item.percent}%` }"
                  />
                </div>
              </div>
            </template>
            <p v-else class="card-empty__text">暂无阅卷任务</p>
          </div>

          <div class="card">
            <div class="card-head">
              <div class="card-title">待办列表</div>
              <span class="card-meta">实时</span>
            </div>
            <template v-if="todoItems.length > 0">
              <div
                v-for="(todo, index) in todoItems"
                :key="todo.label"
                class="friend friend--clickable"
                @click="router.push(todo.route)"
              >
                <div :class="['friend__avatar', todoAvatarClass(index)]">{{ todoInitial(todo) }}</div>
                <span class="friend__name">{{ todo.label }}</span>
                <span class="friend__score">{{ todo.count }}</span>
                <span class="friend__unit">项</span>
              </div>
            </template>
            <p v-else class="card-empty__text">暂无待办</p>
          </div>
        </div>
      </div>

      <aside v-if="entryItems.length > 0" class="entry-stack" aria-label="快速入口">
        <router-link
          v-for="entry in entryItems"
          :key="entry.route"
          :to="entry.route"
          :class="['entry', `entry--${entry.tone}`]"
        >
          <div :class="['entry__icon', `entry__icon--${entry.iconTone}`]">
            <AppIcon :name="entry.icon" :size="18" />
          </div>
          <div class="entry__title">{{ entry.title }}</div>
          <div class="entry__sub">{{ entry.sub }}</div>
          <div class="entry__bottom">
            <span :class="['entry__btn', `entry__btn--${entry.buttonTone}`]">
              {{ entry.buttonText }}
            </span>
          </div>
        </router-link>
      </aside>
    </div>

    <div class="divider" />

    <!-- Recent Exams Table -->
    <div v-if="recentExams.length > 0" class="card recent-exams">
      <div class="card-head">
        <div class="card-title">最近考试</div>
        <n-button text type="primary" @click="router.push('/exams')">查看全部考试 &rarr;</n-button>
      </div>
      <div class="recent-table-wrap">
        <table class="recent-table">
          <thead>
            <tr>
              <th>考试名称</th>
              <th>日期</th>
              <th>科目</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="exam in recentExams"
              :key="exam.id"
              @click="router.push(`/exams/${exam.id}`)"
            >
              <td class="recent-exam-name">{{ exam.name }}</td>
              <td>{{ exam.created_at ? formatDate(exam.created_at) : '--' }}</td>
              <td>{{ exam.subject_count != null ? exam.subject_count + ' 个科目' : '--' }}</td>
              <td>
                <n-tag :type="examStatusType(exam.status)" size="small" round>
                  {{ examStatusText(exam.status) }}
                </n-tag>
              </td>
            </tr>
          </tbody>
        </table>
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
import { NButton, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { getDashboardConfig } from '../config/dashboardConfig'
import { normalizeRole } from '../config/roles'
import DashboardCard from '../components/dashboard/DashboardCard.vue'
import WidgetGrid from '../components/dashboard/WidgetGrid.vue'
import ActivityFeed from '../components/dashboard/ActivityFeed.vue'
import AppIcon from '../components/AppIcon.vue'
import client from '../api/client.js'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const router = useRouter()
const auth = useAuthStore()
const role = computed(() => normalizeRole(auth.currentRole?.role || ''))
const config = computed(() => getDashboardConfig(role.value))

// Chart theme colors — read from CSS vars for dark-mode compatibility
const rootStyle = getComputedStyle(document.documentElement)
const chartTextColor = rootStyle.getPropertyValue('--color-text').trim() || 'rgba(15, 26, 18, 0.88)'
const chartSplitColor = rootStyle.getPropertyValue('--color-border-light').trim() || '#e8efe9'
const chartSuccessColor = rootStyle.getPropertyValue('--color-primary').trim() || '#644CF0'
const chartWarningColor = rootStyle.getPropertyValue('--color-accent').trim() || '#F4DA4C'

const kpiData = ref({})
const loading = ref(true)
const trendOption = ref(null)
const activityItems = ref([])
const recentExams = ref([])
const todoItems = ref([])
const statToneSequence = ['yellow', 'purple', 'orange', 'ink']
const progressToneSequence = ['yellow', 'purple', 'orange']
const friendToneSequence = ['friend__avatar--yellow', 'friend__avatar--purple', 'friend__avatar--orange']
const kpiIconMap = {
  total_exams: 'exam',
  total_students: 'people',
  pending_grading: 'marking',
  pending_subjects: 'marking',
  total_staff: 'academic',
  total_classes: 'class',
  subject_classes: 'class',
  subject_avg: 'chart',
  ai_tools: 'ai',
}

const dashboardKpis = computed(() =>
  (config.value?.kpis || []).map((kpi, index) => ({
    ...kpi,
    tone: statToneSequence[index % statToneSequence.length],
    icon: kpiIconMap[kpi.id] || ['exam', 'people', 'marking', 'chart'][index % 4],
  }))
)

const entryItems = computed(() => {
  const r = role.value
  if (r === 'parent') return []
  const enabledModules = auth.enabledModules || []

  const items = [
    {
      tone: 'dark',
      iconTone: 'yellow',
      icon: 'ai',
      title: 'AI 智能阅卷',
      sub: '自动识别与智能评分',
      route: '/ai-grading',
      permission: ['manage_grading', 'view_grading'],
      moduleCode: 'grading',
      buttonText: '立即使用',
      buttonTone: 'yellow',
    },
    {
      tone: 'yellow',
      iconTone: 'dark',
      icon: 'chart',
      title: '多维成绩分析',
      sub: '年级 / 班级 / 学生对比',
      route: '/analytics/report',
      permission: 'view_scores',
      buttonText: '查看',
      buttonTone: 'dark',
    },
    {
      tone: 'purple',
      iconTone: 'light',
      icon: 'chart',
      title: '知识图谱',
      sub: '学科知识全景可视化',
      route: '/knowledge-tree',
      permission: 'view_knowledge_tree',
      buttonText: '探索',
      buttonTone: 'light',
    },
  ]

  return items.filter(item => {
    const required = Array.isArray(item.permission) ? item.permission : [item.permission]
    const hasPermission = required.some(perm => auth.checkPermission(perm))
    if (item.moduleCode && !enabledModules.includes(item.moduleCode)) return false
    return hasPermission
  })
})

const gradingProgressItems = computed(() => {
  return recentExams.value
    .filter(exam => exam.status === 'grading')
    .map((exam, index) => {
      const progress = normalizeGradingProgress(exam.grading_progress)
      return {
        id: exam.id,
        name: exam.name || '未命名考试',
        percent: progress.percent,
        progressText: progress.text,
        tone: progressToneSequence[index % progressToneSequence.length],
      }
    })
})

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

function clampProgress(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 0
  return Math.max(0, Math.min(100, Math.round(numeric)))
}

function normalizeGradingProgress(progress) {
  if (progress == null) return { percent: 0, text: '--' }

  if (typeof progress === 'number' || typeof progress === 'string') {
    const percent = clampProgress(progress)
    return { percent, text: `${percent}%` }
  }

  const graded = Number(progress.graded ?? progress.graded_count ?? progress.completed ?? progress.done)
  const total = Number(progress.total ?? progress.total_answers ?? progress.count)
  const rawPercent = progress.percentage ?? progress.percent

  if (Number.isFinite(graded) && Number.isFinite(total) && total > 0) {
    const percent = rawPercent == null ? clampProgress((graded / total) * 100) : clampProgress(rawPercent)
    return { percent, text: `${graded}/${total}` }
  }

  if (rawPercent != null) {
    const percent = clampProgress(rawPercent)
    return { percent, text: `${percent}%` }
  }

  return { percent: 0, text: '--' }
}

function todoAvatarClass(index) {
  return friendToneSequence[index % friendToneSequence.length]
}

function todoInitial(todo) {
  return String(todo.label || '待办').trim().charAt(0) || '待'
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
            { name: '平均分', type: 'line', smooth: true, data: trend.points.map(p => p.avg?.toFixed(1)), itemStyle: { color: chartSuccessColor } },
            { name: '及格率', type: 'line', smooth: true, yAxisIndex: 1, data: trend.points.map(p => (p.pass_rate * 100)?.toFixed(1)), itemStyle: { color: chartWarningColor } },
          ],
        }
      }
    } catch { /* no trend data */ }
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
/* Welcome banner */
.welcome-banner {
  background: var(--macaron-mint-light);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  padding: 24px 28px;
  margin-bottom: 20px;
}

.welcome-banner__title {
  font-size: var(--fs-xl);
  font-weight: var(--fw-semibold);
  color: var(--color-text);
  margin: 0 0 6px;
}

.welcome-banner__text {
  font-size: var(--fs-base);
  color: var(--color-text-secondary);
  margin: 0 0 14px;
}

.dashboard-stat {
  min-height: 164px;
  border: none;
}

.dashboard-stat--yellow {
  background: var(--surface-stat-yellow);
  box-shadow: var(--shadow-stat-yellow);
}

.dashboard-stat--yellow:hover {
  box-shadow: var(--shadow-stat-yellow-hover);
}

.dashboard-stat--purple {
  background: var(--surface-stat-purple);
  box-shadow: var(--shadow-stat-purple);
}

.dashboard-stat--purple:hover {
  box-shadow: var(--shadow-stat-purple-hover);
}

.dashboard-stat--orange {
  background: var(--surface-stat-orange);
  box-shadow: var(--shadow-stat-orange);
}

.dashboard-stat--orange:hover {
  box-shadow: var(--shadow-stat-orange-hover);
}

.dashboard-stat--ink {
  background: var(--surface-stat-ink);
  box-shadow: var(--shadow-stat-ink);
}

.dashboard-stat--ink:hover {
  box-shadow: var(--shadow-stat-ink-hover);
}

.dashboard-stat:hover {
  transform: translateY(-1px);
}

.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.35);
}

.stat-icon--yellow {
  background: var(--color-accent);
  color: var(--color-bg-deep);
}

.stat-icon--purple {
  background: var(--color-primary);
  color: #ffffff;
}

.stat-icon--orange {
  background: var(--color-warning);
  color: #ffffff;
}

.stat-icon--ink {
  background: var(--color-bg-deep);
  color: var(--color-accent);
}

.dashboard-stat .stat-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}

.dashboard-stat .stat-value {
  font-size: 34px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: 0;
  line-height: 1;
  font-variant-numeric: tabular-nums;
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
  padding: 12px 18px;
  background: var(--color-bg-card, rgba(255,255,255,0.04));
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: var(--transition);
}

.todo-item:hover {
  border-color: var(--color-border);
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-1px);
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
  font-size: var(--fs-base);
  color: var(--color-text);
}

.chart-empty__text {
  font-size: var(--fs-base);
  color: var(--color-text-muted);
  margin: 0;
}

/* Recent exams */
.recent-exams {
  margin-bottom: 24px;
}

/* Module grid */
.module-grid {
  margin-bottom: 8px;
}

@media (max-width: 768px) {
  .todo-section {
    flex-direction: column;
  }
}

/* Batch 4 dashboard demo alignment */
.greeting {
  font-family: var(--font-serif-display);
  font-style: italic;
  font-weight: 400;
  font-size: 34px;
  color: var(--color-text);
  margin-bottom: 28px;
  line-height: 1.1;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 24px;
  align-items: start;
  margin-bottom: 28px;
}

.dashboard-left {
  min-width: 0;
}

.dashboard-split {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.entry-stack {
  display: grid;
  gap: 14px;
}

.card {
  background: #fff;
  border-radius: var(--radius-lg);
  padding: 24px;
  border: 1px solid var(--color-border-light);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s ease;
}

.card:hover {
  box-shadow: var(--shadow-card-hover);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}

.card-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
}

.card-sub,
.card-meta {
  font-size: 13px;
  color: var(--color-text-muted);
}

.chart-card {
  min-width: 0;
  margin-bottom: 0;
}

.chart-legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.chart-legend__item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--color-text-muted);
}

.chart-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chart-legend__dot--purple { background: var(--color-primary); }
.chart-legend__dot--yellow { background: var(--color-accent); }
.chart-legend__dot--orange { background: var(--color-warning); }

.chart-empty {
  border-style: dashed;
  margin-bottom: 0;
  text-align: center;
}

.card-empty__text {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 15px;
}

.prog {
  margin-bottom: 16px;
}

.prog:last-child {
  margin-bottom: 0;
}

.prog-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
  font-size: 15px;
}

.prog-label {
  color: var(--color-text-secondary);
  font-weight: 500;
}

.prog-val {
  color: var(--color-text);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.friend--clickable {
  cursor: pointer;
  border-radius: var(--radius-sm);
  padding-left: 8px;
  padding-right: 8px;
  transition: background 0.15s ease;
}

.friend--clickable:hover {
  background: var(--color-bg);
}

.entry__icon--yellow {
  background: rgba(244, 218, 76, 0.18);
  color: #F4DA4C;
}

.entry__icon--dark {
  background: rgba(9, 6, 27, 0.1);
  color: #09061B;
}

.entry__icon--light {
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
}

.recent-table-wrap {
  overflow-x: auto;
}

.recent-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 15px;
}

.recent-table th {
  padding: 12px 14px;
  border-bottom: 2px solid var(--color-border-light);
  text-align: left;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-muted);
  white-space: nowrap;
}

.recent-table td {
  padding: 14px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.recent-table tbody tr {
  cursor: pointer;
  transition: background 0.15s ease;
}

.recent-table tbody tr:hover {
  background: var(--color-bg);
}

.recent-exam-name {
  font-weight: 700;
  color: var(--color-text) !important;
}

@media (max-width: 768px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-split {
    grid-template-columns: 1fr;
  }

  .card {
    padding: 20px;
  }

  .card-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .recent-table {
    min-width: 560px;
  }
}
</style>
