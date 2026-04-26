/**
 * DashboardPage enhancement tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains new sections (quick-actions, todo, recent-exams, welcome-banner, chart-empty)
 *  3. Chart-card uses theme-aware background (no hardcoded white)
 *  4. Quick actions config is role-aware (parent gets empty)
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
  it('contains quick-actions section', () => {
    expect(content).toContain('class="quick-actions"')
    expect(content).toContain('quick-action-btn')
  })

  it('contains todo-section', () => {
    expect(content).toContain('class="todo-section"')
    expect(content).toContain('todo-item')
  })

  it('contains recent-exams cards', () => {
    expect(content).toContain('class="recent-exams"')
    expect(content).toContain('exam-card')
    expect(content).toContain('exam-card__header')
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

describe('DashboardPage dark theme adaptation', () => {
  it('chart-card uses CSS var background instead of hardcoded white', () => {
    // Extract the .chart-card style block
    const styleMatch = content.match(/\.chart-card\s*\{[^}]+\}/)
    expect(styleMatch).not.toBeNull()
    const chartCardStyle = styleMatch[0]
    // Must NOT contain "background: white" or "background: #fff"
    expect(chartCardStyle).not.toMatch(/background:\s*white/)
    expect(chartCardStyle).not.toMatch(/background:\s*#fff/)
    // Must use CSS variable
    expect(chartCardStyle).toContain('var(--color-bg-card')
  })

  it('ECharts options include transparent backgroundColor', () => {
    expect(content).toContain("backgroundColor: 'transparent'")
  })

  it('ECharts options use chartTextColor for axis labels', () => {
    expect(content).toContain('axisLabel: { color: chartTextColor }')
  })
})

describe('DashboardPage quick actions role filtering', () => {
  it('defines 4 quick action entries', () => {
    // Count the action objects in the quickActions computed
    const actionMatches = content.match(/\{ label: '.*?', icon: '.*?', route: '.*?'/g)
    expect(actionMatches).not.toBeNull()
    expect(actionMatches.length).toBe(4)
  })

  it('filters out actions for parent role', () => {
    expect(content).toContain("if (r === 'parent') return []")
  })

  it('includes correct route targets', () => {
    expect(content).toContain("route: '/exams'")
    expect(content).toContain("route: '/homework'")
    expect(content).toContain("route: '/grading/tasks'")
    expect(content).toContain("route: '/analytics/report'")
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

  it('fetches class boxplot for comparison chart', () => {
    expect(content).toContain('/analytics/exam/')
    expect(content).toContain('/class-boxplot')
  })

  it('builds trendOption with correct series', () => {
    expect(content).toContain("name: '平均分'")
    expect(content).toContain("name: '及格率'")
  })

  it('builds classOption bar chart sorted by median', () => {
    expect(content).toContain('.sort((a, b) => (b.median || 0) - (a.median || 0))')
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
