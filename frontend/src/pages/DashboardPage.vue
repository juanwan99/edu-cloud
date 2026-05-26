<template>
  <div class="dashboard-page">
    <h1 class="greeting">早上好，{{ auth.user?.display_name || '老师' }}</h1>

    <section class="teacher-hero">
      <div class="teacher-hero__content">
        <div class="teacher-hero__eyebrow">{{ workbenchProfile.label }}工作台</div>
        <h2 class="teacher-hero__title">{{ workbenchProfile.title }}</h2>
        <p class="teacher-hero__text">{{ workbenchProfile.summary }}</p>
      </div>
      <div class="teacher-hero__actions">
        <n-button
          v-for="(action, index) in heroActions"
          :key="action.route"
          :type="index === 0 ? 'primary' : 'default'"
          :secondary="index !== 0"
          size="large"
          @click="router.push(action.route)"
        >
          {{ action.label }}
        </n-button>
      </div>
    </section>

    <section class="role-context-strip" aria-label="当前身份上下文">
      <div
        v-for="item in roleContextItems"
        :key="item.label"
        class="role-context-item"
      >
        <span class="role-context-item__label">{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.desc }}</small>
      </div>
    </section>

    <section class="workflow-strip" aria-label="当前身份业务主线">
      <router-link
        v-for="stage in workflowStages"
        :key="stage.key"
        :to="stage.route"
        class="workflow-stage"
      >
        <span class="workflow-stage__index">{{ stage.index }}</span>
        <span class="workflow-stage__body">
          <strong>{{ stage.title }}</strong>
          <small>{{ stage.desc }}</small>
        </span>
      </router-link>
    </section>

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

    <section class="teacher-workspace">
      <article class="card priority-panel">
        <div class="card-head">
          <div>
            <div class="card-title">今天先做什么</div>
            <div class="card-sub">按当前身份动作排序，而不是按系统模块排序</div>
          </div>
          <n-tag type="warning" size="small" round>任务优先</n-tag>
        </div>
        <div class="priority-list">
          <button
            v-for="action in priorityActions"
            :key="action.title"
            type="button"
            class="priority-item"
            @click="router.push(action.route)"
          >
            <span :class="['priority-item__dot', `priority-item__dot--${action.tone}`]" />
            <span class="priority-item__main">
              <strong>{{ action.title }}</strong>
              <small>{{ action.desc }}</small>
            </span>
            <n-tag :type="action.tagType" size="small" round>{{ action.tag }}</n-tag>
          </button>
        </div>
      </article>

      <article v-if="roleActionPanel.items.length > 0" class="card report-action-panel">
        <div class="card-head">
          <div>
            <div class="card-title">{{ roleActionPanel.title }}</div>
            <div class="card-sub">{{ roleActionPanel.sub }}</div>
          </div>
          <n-button v-if="canAccessRoute(roleActionPanel.actionRoute)" text type="primary" @click="router.push(roleActionPanel.actionRoute)">
            {{ roleActionPanel.actionLabel }}
          </n-button>
        </div>
        <div class="report-action-grid">
          <button
            v-for="item in roleActionPanel.items"
            :key="item.title"
            type="button"
            class="report-action"
            @click="router.push(item.route)"
          >
            <span :class="['report-action__badge', `report-action__badge--${item.tone}`]">{{ item.label }}</span>
            <strong>{{ item.title }}</strong>
            <small>{{ item.desc }}</small>
          </button>
        </div>
      </article>
    </section>

    <section class="card business-map">
      <div class="card-head">
        <div>
          <div class="card-title">次级业务入口</div>
          <div class="card-sub">主任务之外只保留当前身份最常用的补充入口</div>
        </div>
      </div>
      <div class="business-map__grid">
        <div v-for="group in secondaryBusinessGroups" :key="group.title" class="business-group">
          <div class="business-group__title">{{ group.title }}</div>
          <router-link
            v-for="item in group.items"
            :key="item.route"
            :to="item.route"
            class="business-link"
          >
            <span>
              <strong>{{ item.title }}</strong>
              <small>{{ item.desc }}</small>
            </span>
            <span class="business-link__arrow">&rarr;</span>
          </router-link>
        </div>
      </div>
    </section>

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

    <!-- Activity Feed -->
    <ActivityFeed :items="activityItems" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NTag } from 'naive-ui'
import { useAuthStore } from '../stores/auth'
import { normalizeRole } from '../config/roles'
import { getWorkbenchProfile } from '../config/workbenchProfiles.js'
import {
  buildRoleActionPanel,
  buildRolePriorityActions,
  getRoleDashboardKpis,
} from '../config/roleEntryMatrix.js'
import {
  ROUTE_ACCESS_REQUIREMENTS,
  canAccessRequirementForRole,
} from '../config/routeAccess.js'
import { CHART_DEFAULTS, CHART_PALETTE } from '../config/chartTheme.js'
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
const workbenchProfile = computed(() => getWorkbenchProfile(role.value))
const schoolWideRoleKeys = new Set(['platform_admin', 'district_admin', 'school_admin', 'principal'])

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

const moduleFallbacks = ['exam', 'grading', 'calendar', 'studio']

function moduleEnabled(moduleCode) {
  if (!moduleCode) return true
  const enabled = auth.enabledModules || []
  if (!auth.modulesLoaded && enabled.length === 0) return moduleFallbacks.includes(moduleCode)
  if (enabled.length === 0) return true
  return enabled.includes(moduleCode)
}

function canAccess(item) {
  const enabledModules = auth.modulesLoaded ? auth.enabledModules : []
  return canAccessRequirementForRole(role.value, item, enabledModules)
}

const routeAccessRequirements = ROUTE_ACCESS_REQUIREMENTS

function canAccessRoute(route) {
  const requirement = routeAccessRequirements[route]
  return requirement ? canAccess(requirement) : true
}

const heroActions = computed(() => [
  workbenchProfile.value.primaryAction,
  workbenchProfile.value.secondaryAction,
]
  .filter(Boolean)
  .filter(action => canAccessRoute(action.route))
  .slice(0, 2))

const workflowStages = computed(() =>
  workbenchProfile.value.flow
    .filter(stage => canAccessRoute(stage.route))
    .map((stage, index) => ({
      ...stage,
      key: `${stage.route}-${stage.title}`,
      index: String(index + 1),
    })),
)

function countLabel(values, unit) {
  return Array.isArray(values) && values.length ? `${values.length} ${unit}` : ''
}

const scopeSummary = computed(() => {
  const current = auth.currentRole || {}
  if (!current.role) return '未设置范围'
  if (schoolWideRoleKeys.has(role.value)) return auth.currentContext?.name || '全校'

  const parts = [
    countLabel(current.grade_ids, '个年级'),
    countLabel(current.class_ids, '个班级'),
    countLabel(current.subject_codes, '个学科'),
  ].filter(Boolean)

  return parts.length ? parts.join(' · ') : (auth.currentContext?.name || '当前职责范围')
})

const roleContextItems = computed(() => [
  {
    label: '当前身份',
    value: workbenchProfile.value.label,
    desc: auth.currentContext?.name || '当前登录身份',
  },
  {
    label: '数据范围',
    value: scopeSummary.value,
    desc: workbenchProfile.value.owns,
  },
  {
    label: '默认隐藏',
    value: '已收起无关入口',
    desc: workbenchProfile.value.hides,
  },
  {
    label: '多身份提醒',
    value: auth.roles.length > 1 ? `${auth.roles.length} 个身份` : '单一身份',
    desc: auth.roles.length > 1 ? '切换身份后再处理另一条工作流' : '当前只展示此身份工作流',
  },
])

const reportActionItems = computed(() => {
  const reviewAction = auth.checkPermission('manage_grading')
    ? {
        label: '复核',
        title: '处理阅卷和 AI 结果风险',
        desc: '将待确认项前置，避免报告发布后再返工。',
        route: '/grading/tasks',
        permission: 'manage_grading',
        moduleCode: 'grading',
        tone: 'coral',
      }
    : {
        label: '阅卷',
        title: '处理我的阅卷任务',
        desc: '只进入自己被分配的阅卷范围，不暴露调度入口。',
        route: '/marking',
        permission: 'view_grading',
        moduleCode: 'grading',
        tone: 'coral',
      }

  return [
    {
      label: '概览',
      title: '先看本次考试关键结论',
      desc: '把平均分、分层、薄弱知识点集中在一个报告入口。',
      route: '/analytics/report',
      permission: 'view_scores',
      moduleCode: 'study_analytics',
      tone: 'yellow',
    },
    reviewAction,
    {
      label: '讲评',
      title: '转成课堂讲评与追问',
      desc: '从错因、区分度和知识点生成讲评动作。',
      route: '/analytics/ai-report',
      permission: ['view_scores', 'generate_report'],
      moduleCode: 'study_analytics',
      tone: 'purple',
    },
    {
      label: '巩固',
      title: '进入作业和错题闭环',
      desc: '把分析后的补偿练习放到诊断之后。',
      route: '/homework',
      permission: 'view_homework',
      moduleCode: 'homework',
      tone: 'mint',
    },
  ].filter(canAccess)
})

const roleActionPanel = computed(() => {
  const roleSpecificPanel = buildRoleActionPanel(role.value, {
    summary: kpiData.value,
    recentExams: recentExams.value,
    todoItems: todoItems.value,
  })
  if (roleSpecificPanel) {
    return {
      ...roleSpecificPanel,
      items: roleSpecificPanel.items.filter(item => canAccessRoute(item.route)),
    }
  }

  return {
    title: '报告行动中心',
    sub: '报告承接讲评、巩固和资源沉淀',
    actionLabel: '进入分析 →',
    actionRoute: '/analytics/report',
    items: reportActionItems.value,
  }
})

const businessGroups = computed(() =>
  workbenchProfile.value.modules
    .map(group => ({
      ...group,
      items: group.items.filter(item => canAccessRoute(item.route)),
    }))
    .filter(group => group.items.length > 0),
)

const secondaryBusinessGroups = computed(() =>
  businessGroups.value
    .map(group => ({
      ...group,
      items: group.items.slice(0, 3),
    }))
    .filter(group => group.items.length > 0)
    .slice(0, 2),
)

const dashboardKpis = computed(() =>
  getRoleDashboardKpis(role.value).map((kpi, index) => ({
    ...kpi,
    tone: statToneSequence[index % statToneSequence.length],
    icon: kpiIconMap[kpi.id] || ['exam', 'people', 'marking', 'chart'][index % 4],
  }))
)

const profilePriorityActions = computed(() =>
  buildRolePriorityActions(role.value, {
    profile: workbenchProfile.value,
    summary: kpiData.value,
    recentExams: recentExams.value,
    todoItems: todoItems.value,
  }).filter(action => canAccessRoute(action.route)),
)

const priorityActions = computed(() => profilePriorityActions.value)

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
  if (!auth.currentRole?.school_id) return
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
          ...CHART_DEFAULTS,
          tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' },
          legend: { ...CHART_DEFAULTS.legend, data: ['平均分', '及格率'], bottom: 0 },
          grid: { ...CHART_DEFAULTS.grid, left: 50, right: 50, top: 20, bottom: 40 },
          xAxis: { ...CHART_DEFAULTS.xAxis, type: 'category', data: trend.points.map(p => p.exam_name?.slice(0, 10) || '') },
          yAxis: [
            { ...CHART_DEFAULTS.yAxis, type: 'value', name: '分数', position: 'left', nameTextStyle: { color: CHART_DEFAULTS.textStyle.color } },
            { ...CHART_DEFAULTS.yAxis, type: 'value', name: '及格率', position: 'right', max: 100, axisLabel: { ...CHART_DEFAULTS.yAxis.axisLabel, formatter: '{value}%' }, nameTextStyle: { color: CHART_DEFAULTS.textStyle.color }, splitLine: { show: false } },
          ],
          series: [
            { name: '平均分', type: 'line', smooth: true, data: trend.points.map(p => p.avg?.toFixed(1)), itemStyle: { color: CHART_PALETTE[0] } },
            { name: '及格率', type: 'line', smooth: true, yAxisIndex: 1, data: trend.points.map(p => (p.pass_rate * 100)?.toFixed(1)), itemStyle: { color: CHART_PALETTE[1] } },
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
.teacher-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
  background: linear-gradient(135deg, #ffffff 0%, rgba(244, 218, 76, 0.08) 45%, rgba(126, 87, 194, 0.08) 100%);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-card);
  padding: 28px;
  margin-bottom: 18px;
}

.teacher-hero__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  color: var(--color-text-muted);
  margin-bottom: 10px;
}

.teacher-hero__eyebrow::before {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-accent);
  box-shadow: 0 0 0 6px rgba(244, 218, 76, 0.16);
}

.teacher-hero__title {
  font-size: 28px;
  line-height: 1.18;
  font-weight: 800;
  letter-spacing: 0;
  color: var(--color-text);
  margin: 0 0 10px;
}

.teacher-hero__text {
  max-width: 760px;
  margin: 0;
  color: var(--color-text-secondary);
  font-size: 15px;
  line-height: 1.8;
}

.teacher-hero__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.role-context-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.role-context-item {
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg-card);
  box-shadow: var(--shadow-card);
}

.role-context-item__label,
.role-context-item strong,
.role-context-item small {
  display: block;
}

.role-context-item__label {
  margin-bottom: 6px;
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.role-context-item strong {
  margin-bottom: 5px;
  color: var(--color-text);
  font-size: 15px;
}

.role-context-item small {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.workflow-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin-bottom: 22px;
}

.workflow-stage {
  display: flex;
  gap: 12px;
  min-height: 104px;
  padding: 16px;
  border-radius: var(--radius-lg);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  color: inherit;
  text-decoration: none;
  box-shadow: var(--shadow-card);
  transition: var(--transition);
}

.workflow-stage:hover {
  transform: translateY(-2px);
  border-color: var(--color-border);
  box-shadow: var(--shadow-card-hover);
}

.workflow-stage__index {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 10px;
  background: var(--color-bg-deep);
  color: var(--color-accent);
  font-weight: 800;
}

.workflow-stage__body {
  min-width: 0;
}

.workflow-stage strong,
.workflow-stage small {
  display: block;
}

.workflow-stage strong {
  color: var(--color-text);
  font-size: 15px;
  margin-bottom: 6px;
}

.workflow-stage small {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.teacher-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.35fr);
  gap: 18px;
  margin-bottom: 24px;
}

.priority-list,
.report-action-grid {
  display: grid;
  gap: 12px;
}

.priority-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  text-align: left;
  padding: 14px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  transition: var(--transition);
}

.priority-item:hover {
  background: var(--color-bg-card);
  border-color: var(--color-border);
  transform: translateY(-1px);
}

.priority-item__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.priority-item__dot--coral { background: var(--macaron-coral); }
.priority-item__dot--yellow { background: var(--macaron-yellow); }
.priority-item__dot--purple { background: var(--macaron-purple); }

.priority-item__main {
  flex: 1;
  min-width: 0;
}

.priority-item strong,
.priority-item small {
  display: block;
}

.priority-item strong {
  color: var(--color-text);
  font-size: 15px;
  margin-bottom: 4px;
}

.priority-item small {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.report-action-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.report-action {
  min-height: 142px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 9px;
  text-align: left;
  padding: 16px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg);
  transition: var(--transition);
}

.report-action:hover {
  border-color: var(--color-border);
  box-shadow: var(--shadow-card);
  transform: translateY(-2px);
}

.report-action strong {
  color: var(--color-text);
  font-size: 15px;
}

.report-action small {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.55;
}

.report-action__badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 9px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 700;
}

.report-action__badge--yellow { background: var(--macaron-yellow); color: var(--color-warning-text); }
.report-action__badge--coral { background: var(--macaron-coral); color: #9f1239; }
.report-action__badge--purple { background: var(--macaron-purple); color: #ffffff; }
.report-action__badge--mint { background: var(--macaron-mint); color: #14532d; }

.business-map {
  margin-bottom: 24px;
}

.business-map__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.business-group {
  padding: 16px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  background: var(--color-bg);
}

.business-group__title {
  color: var(--color-text);
  font-size: 15px;
  font-weight: 800;
  margin-bottom: 12px;
}

.business-link {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  color: inherit;
  text-decoration: none;
  border-top: 1px solid var(--color-border-light);
}

.business-link strong,
.business-link small {
  display: block;
}

.business-link strong {
  color: var(--color-text);
  font-size: 14px;
  margin-bottom: 4px;
}

.business-link small {
  color: var(--color-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.business-link__arrow {
  color: var(--color-primary);
  font-weight: 800;
}

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
  grid-template-columns: minmax(0, 1fr);
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
  letter-spacing: 0;
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
  .teacher-hero,
  .teacher-workspace {
    grid-template-columns: 1fr;
  }

  .teacher-hero {
    padding: 22px;
  }

  .teacher-hero__actions {
    justify-content: flex-start;
  }

  .role-context-strip,
  .workflow-strip,
  .business-map__grid {
    grid-template-columns: 1fr;
  }

  .workflow-stage {
    min-height: auto;
  }

  .report-action-grid {
    grid-template-columns: 1fr;
  }

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
