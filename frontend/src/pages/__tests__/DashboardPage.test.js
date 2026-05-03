/**
 * DashboardPage enhancement tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains new sections (entry-stack, todo, recent-exams, welcome-banner, chart-empty)
 *  3. Chart-card uses theme-aware background (no hardcoded white)
 *  4. Entry cards are permission-aware (parent gets empty)
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
  it('contains permission-gated entry stack', () => {
    expect(content).toContain('entryItems.length > 0')
    expect(content).toContain('v-for="entry in entryItems"')
    expect(content).toContain('<router-link')
    expect(content).toContain(':to="entry.route"')
    expect(content).toContain("`entry--${entry.tone}`")
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
    expect(content).toContain("backgroundColor: 'transparent'")
  })

  it('ECharts options use chartTextColor for axis labels', () => {
    expect(content).toContain('axisLabel: { color: chartTextColor }')
  })
})

describe('DashboardPage entry permission filtering', () => {
  it('defines permission-gated entry items', () => {
    expect(content).toContain('const entryItems = computed')
    expect(content).toContain("permission: ['manage_grading', 'view_grading']")
    expect(content).toContain("permission: 'view_scores'")
    expect(content).toContain("permission: 'view_knowledge_tree'")
    expect(content).toContain('auth.checkPermission')
    expect(content).toContain("moduleCode: 'grading'")
    expect(content).toContain('enabledModules.includes(item.moduleCode)')
  })

  it('filters out entries for parent role', () => {
    expect(content).toContain("if (r === 'parent') return []")
  })

  it('includes correct route targets', () => {
    expect(content).toContain("route: '/ai-grading'")
    expect(content).toContain("route: '/analytics/report'")
    expect(content).toContain("route: '/knowledge-tree'")
  })

  it('uses semantic links for entry cards without nested buttons', () => {
    const entryBlock = content.slice(
      content.indexOf('<aside v-if="entryItems.length > 0"'),
      content.indexOf('</aside>')
    )
    expect(entryBlock).toContain('<router-link')
    expect(entryBlock).not.toContain('role="button"')
    expect(entryBlock).not.toContain('tabindex="0"')
    expect(entryBlock).not.toContain('@keyup.enter')
    expect(entryBlock).not.toContain('<button')
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
