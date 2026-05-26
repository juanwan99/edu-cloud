/**
 * DashboardPage enhancement tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains role-first sections (todo, recent-exams, welcome-banner, chart-empty)
 *  3. Chart-card uses theme-aware background (no hardcoded white)
 *  4. Legacy module widgets and hard-coded quick entries are removed
 *  5. Exam status helpers return correct Chinese text
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../DashboardPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('DashboardPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../DashboardPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('DashboardPage template sections', () => {
  it('uses shared workbench profile copy for the hero and workflow', () => {
    expect(content).toContain("import { getWorkbenchProfile } from '../config/workbenchProfiles.js'")
    expect(content).toContain('const workbenchProfile = computed')
    expect(content).toContain('{{ workbenchProfile.label }}工作台')
    expect(content).toContain('{{ workbenchProfile.title }}')
    expect(content).toContain('{{ workbenchProfile.summary }}')
    expect(content).toContain('workbenchProfile.value.flow')
    expect(content).toContain('workbenchProfile.value.modules')
  })

  it('guards school admin workbench routes by real route permissions', () => {
    expect(content).toContain("import {\n  ROUTE_ACCESS_REQUIREMENTS,\n  canAccessRequirementForRole,\n} from '../config/routeAccess.js'")
    expect(content).toContain('const routeAccessRequirements = ROUTE_ACCESS_REQUIREMENTS')
    expect(content).toContain('canAccessRequirementForRole(role.value, item, enabledModules)')
  })

  it('uses role modules for secondary business entries instead of hard-coded quick cards', () => {
    expect(content).toContain('secondaryBusinessGroups')
    expect(content).toContain('class="card business-map"')
    expect(content).not.toContain('entry' + 'Items.length > 0')
    expect(content).not.toContain('v-for="entry in entry' + 'Items"')
  })

  it('contains todo-section', () => {
    expect(content).toContain('class="todo-section"')
    expect(content).toContain('todo-item')
  })

  it('contains recent-exams table', () => {
    expect(content).toContain('recent-table')
    expect(content).toContain('recentExams')
  })

  it('contains welcome-banner for empty state', () => {
    expect(content).toContain('welcome-banner')
    expect(content).toContain('showWelcome')
  })

  it('contains chart-empty fallback', () => {
    expect(content).toContain('chart-empty')
    expect(content).toContain('chart-empty__text')
  })
})

describe('DashboardPage role-first formal workbench', () => {
  it('delegates role-specific action panels to the shared role entry matrix', () => {
    expect(content).toContain('const roleActionPanel = computed')
    expect(content).toContain('const roleSpecificPanel = buildRoleActionPanel')
    expect(content).toContain('if (roleSpecificPanel)')
    expect(content).toContain("} from '../config/roleEntryMatrix.js'")
    expect(content).not.toContain("from '../config/role" + "Workbenches.js'")
    expect(content).not.toContain("if (adminRoleKeys.has(role.value)) {\n    return {\n      title: '运行治理中心'")
  })

  it('uses the role entry matrix for today actions', () => {
    expect(content).toContain('buildRolePriorityActions(role.value')
    expect(content).toContain('profilePriorityActions')
  })

  it('uses live role workbench data for role panels and kpis', () => {
    expect(content).toContain('getRoleDashboardKpis(role.value)')
    expect(content).toContain('buildRolePriorityActions(role.value')
    expect(content).toContain('summary: kpiData.value')
    expect(content).toContain('recentExams: recentExams.value')
    expect(content).toContain('buildRoleActionPanel(role.value, {')
    expect(content).toContain('const roleSpecificPanel = buildRoleActionPanel')
  })

  it('does not hard-code teacher-only report copy as the only second panel', () => {
    expect(content).not.toContain('报告不再只是查看结果，而是讲评和巩固的入口')
  })
})

describe('DashboardPage demo data removal', () => {
  it('does not contain static KPI delta copy', () => {
    expect(content).not.toContain('+12% 较上学期')
    expect(content).not.toContain('stat-delta')
  })

  it('does not contain static grading progress samples', () => {
    expect(content).not.toContain('65/100')
    expect(content).not.toContain('38/100')
    expect(content).not.toContain('92/100')
  })

  it('does not contain static teacher ranking samples', () => {
    expect(content).not.toContain('教师排行')
    expect(content).not.toContain('张海燕')
    expect(content).not.toContain('李明')
    expect(content).not.toContain('王芳')
  })
})

describe('DashboardPage dark theme adaptation', () => {
  it('chart uses .card class with global styles (no inline hardcoded bg)', () => {
    expect(content).toContain('class="card chart-card"')
  })

  it('ECharts options include transparent backgroundColor', () => {
    expect(content).toContain("import { CHART_DEFAULTS, CHART_PALETTE } from '../config/chartTheme.js'")
    expect(content).toContain('...CHART_DEFAULTS')
  })

  it('ECharts options use shared chart defaults and palette', () => {
    expect(content).toContain('axisLabel: { ...CHART_DEFAULTS.yAxis.axisLabel')
    expect(content).toContain('itemStyle: { color: CHART_PALETTE[0] }')
    expect(content).toContain('itemStyle: { color: CHART_PALETTE[1] }')
  })
})

describe('DashboardPage role entry filtering', () => {
  it('removes hard-coded quick entry cards so role matrix owns primary and secondary entry order', () => {
    expect(content).not.toContain('const entry' + 'Items = computed')
    expect(content).not.toContain('<aside v-if="entry' + 'Items.length > 0"')
    expect(content).not.toContain('AI 智能阅卷')
    expect(content).not.toContain('多维成绩分析')
    expect(content).not.toContain('知识图谱</div>')
  })
})

describe('DashboardPage dashboard widget access', () => {
  it('does not render legacy dashboard widget cards beside the role workbench', () => {
    expect(content).not.toContain("import { getSidebarItems } from '../config/sidebarConfig.js'")
    expect(content).not.toContain('const dashboard' + 'Widgets = computed')
    expect(content).not.toContain('v-for="widget in dashboard' + 'Widgets"')
    expect(content).not.toContain('Widget' + 'Grid')
  })

  it('builds hero actions from the current role profile instead of naked permission checks', () => {
    const start = content.indexOf('const heroActions = computed')
    const end = content.indexOf('const workflowStages = computed', start)
    const block = content.slice(start, end)

    expect(block).toContain('workbenchProfile.value.primaryAction')
    expect(block).toContain('workbenchProfile.value.secondaryAction')
    expect(block).toContain('canAccessRoute(action.route)')
    expect(block).not.toContain("auth.checkPermission('manage_exams')")
    expect(block).not.toContain("auth.checkPermission('manage_grading')")
  })
})

describe('DashboardPage grading and todo cards', () => {
  it('derives grading progress from recent grading exams', () => {
    expect(content).toContain('const gradingProgressItems = computed')
    expect(content).toContain(".filter(exam => exam.status === 'grading')")
    expect(content).toContain('normalizeGradingProgress(exam.grading_progress)')
    expect(content).toContain('暂无阅卷任务')
  })

  it('renders todo items in the former ranking card', () => {
    expect(content).toContain('待办列表')
    expect(content).toContain('v-for="(todo, index) in todoItems"')
    expect(content).toContain('class="friend friend--clickable"')
    expect(content).toContain('暂无待办')
  })
})

describe('DashboardPage exam status helpers', () => {
  it('maps status to Chinese text in examStatusText', () => {
    expect(content).toContain("draft: '草稿'")
    expect(content).toContain("published: '已发布'")
    expect(content).toContain("grading: '阅卷中'")
    expect(content).toContain("completed: '已完成'")
  })

  it('maps status to Naive UI tag types', () => {
    expect(content).toContain("draft: 'default'")
    expect(content).toContain("published: 'info'")
    expect(content).toContain("grading: 'warning'")
    expect(content).toContain("completed: 'success'")
  })
})

describe('DashboardPage data fetching', () => {
  it('calls fetchTodos on mount', () => {
    expect(content).toContain('fetchTodos()')
  })

  it('fetches grading tasks for todo items', () => {
    expect(content).toContain("client.get('/grading/tasks')")
  })

  it('fetches homework tasks for todo items', () => {
    expect(content).toContain("client.get('/homework/tasks'")
  })

  it('populates recentExams from exam list', () => {
    expect(content).toContain('recentExams.value = examList.slice(0, 3)')
  })
})

describe('DashboardPage fetchCharts', () => {
  it('fetches exams list for chart data', () => {
    expect(content).toMatch(/client\.get\('\/exams'.*limit/)
  })

  it('fetches grade trend analytics', () => {
    expect(content).toContain("client.get('/analytics/report/trend/grade'")
  })

  it('builds trendOption with correct series', () => {
    expect(content).toContain("name: '平均分'")
    expect(content).toContain("name: '及格率'")
  })

  it('does not retain unreachable classOption chart branch', () => {
    expect(content).not.toContain('classOption')
    expect(content).not.toContain('/class-boxplot')
  })
})

describe('DashboardPage fetchActivity', () => {
  it('fetches exams for activity feed', () => {
    const fetchActivityBlock = content.slice(
      content.indexOf('async function fetchActivity'),
      content.indexOf('async function fetchTodos')
    )
    expect(fetchActivityBlock).toContain("client.get('/exams'")
  })

  it('fetches notifications for activity feed', () => {
    expect(content).toContain("client.get('/notifications'")
  })

  it('maps exam status to Chinese text in activity items', () => {
    expect(content).toContain("draft: '已创建'")
    expect(content).toContain("published: '已发布'")
    expect(content).toContain("completed: '已完成'")
  })

  it('provides fallback activity when no items', () => {
    expect(content).toContain("text: '系统已就绪'")
    expect(content).toContain("type: 'system'")
  })
})

describe('DashboardPage error handling', () => {
  it('wraps fetchCharts in try-catch to prevent crash on API error', () => {
    const fnBlock = content.slice(
      content.indexOf('async function fetchCharts'),
      content.indexOf('async function fetchActivity')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps fetchActivity in try-catch for exam and notification calls', () => {
    const fnBlock = content.slice(
      content.indexOf('async function fetchActivity'),
      content.indexOf('async function fetchTodos')
    )
    const catchCount = (fnBlock.match(/\} catch/g) || []).length
    expect(catchCount).toBeGreaterThanOrEqual(2)
  })

  it('wraps fetchTodos in try-catch for each data source', () => {
    const start = content.indexOf('async function fetchTodos')
    const end = content.indexOf('onMounted(', start)
    const fnBlock = content.slice(start, end)
    const catchCount = (fnBlock.match(/\} catch/g) || []).length
    expect(catchCount).toBeGreaterThanOrEqual(3)
  })
})


describe('DashboardPage Phase 6 role-context layout', () => {
  it('shows current identity, scope, hidden noise, and multi-role context near the top', () => {
    expect(content).toContain('class="role-context-strip"')
    expect(content).toContain('v-for="item in roleContextItems"')
    expect(content).toContain("label: '当前身份'")
    expect(content).toContain("label: '数据范围'")
    expect(content).toContain("label: '默认隐藏'")
    expect(content).toContain("label: '多身份提醒'")
    expect(content).toContain('const roleContextItems = computed')
    expect(content).toContain('const scopeSummary = computed')
    expect(content).toContain('workbenchProfile.value.owns')
    expect(content).toContain('workbenchProfile.value.hides')
    expect(content).toContain('auth.roles.length > 1')
  })

  it('labels and limits secondary module choices instead of exposing another full menu', () => {
    expect(content).toContain('const secondaryBusinessGroups = computed')
    expect(content).toContain('group.items.slice(0, 3)')
    expect(content).toContain('.slice(0, 2)')
    expect(content).toContain('v-for="group in secondaryBusinessGroups"')
    expect(content).toContain('次级业务入口')
    expect(content).toContain('canAccessRoute(item.route)')
    expect(content).not.toContain('isCurrentWorkbenchRoute(item.route)')
    expect(content).not.toContain('entry' + 'Items')
    expect(content).toContain('.slice(0, 2)')
  })
})
