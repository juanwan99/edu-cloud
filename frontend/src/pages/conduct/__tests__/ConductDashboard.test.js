/**
 * ConductDashboard source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (stats cards, charts, top/bottom students, recent records, quick actions)
 *  3. API calls via conduct.js (getRecords, getStudentRankings)
 *  4. Dashboard operations (time range, trend chart, pie chart)
 *  5. Error handling (try-catch in loadDashboard)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductDashboard.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductDashboard smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductDashboard.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductDashboard template sections', () => {
  it('contains page header with title', () => {
    expect(content).toContain('title="德育概览"')
  })

  it('contains time range radio group (week/month/semester)', () => {
    expect(content).toContain('v-model:value="timeRange"')
    expect(content).toContain('value="week"')
    expect(content).toContain('value="month"')
    expect(content).toContain('value="semester"')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
    expect(content).toContain('请切换到班主任角色')
  })

  it('contains 4 stat cards (students, plus, minus, count)', () => {
    expect(content).toContain('label="总学生数"')
    expect(content).toContain('label="加分总额"')
    expect(content).toContain('label="扣分总额"')
    expect(content).toContain('label="记录数"')
  })

  it('contains trend chart and pie chart sections', () => {
    expect(content).toContain('积分走势（最近 4 周）')
    expect(content).toContain('加分/扣分比例')
    expect(content).toContain('v-if="trendOption"')
    expect(content).toContain('v-if="pieOption"')
  })

  it('contains top/bottom students sections', () => {
    expect(content).toContain('title="积分最高"')
    expect(content).toContain('title="积分最低"')
    expect(content).toContain('topStudents')
    expect(content).toContain('bottomStudents')
  })

  it('contains recent records section', () => {
    expect(content).toContain('title="最近记录"')
    expect(content).toContain('recentRecords')
  })

  it('contains quick action buttons', () => {
    expect(content).toContain("name: 'ConductPoints'")
    expect(content).toContain("name: 'ConductRankings'")
    expect(content).toContain("name: 'ConductExport'")
    expect(content).toContain('记积分')
    expect(content).toContain('查排行')
    expect(content).toContain('导出')
  })
})

describe('ConductDashboard API calls', () => {
  it('imports getRecords and getStudentRankings from conduct API', () => {
    expect(content).toContain("import { getRecords, getStudentRankings } from '../../api/conduct'")
  })

  it('calls getStudentRankings for rankings data', () => {
    expect(content).toContain('getStudentRankings(classId.value, {})')
  })

  it('calls getRecords with date range and pagination', () => {
    expect(content).toContain('getRecords(classId.value, {')
    expect(content).toContain('page: 1')
    expect(content).toContain('page_size: 200')
    expect(content).toContain('start_date:')
  })
})

describe('ConductDashboard operations', () => {
  it('computes classId from auth store', () => {
    expect(content).toContain('auth.currentRole?.class_ids?.[0]')
  })

  it('has time range state defaulting to week', () => {
    expect(content).toContain("const timeRange = ref('week')")
  })

  it('has getDateRange function for week/month/semester', () => {
    expect(content).toContain('function getDateRange()')
    expect(content).toContain("timeRange.value === 'week'")
    expect(content).toContain("timeRange.value === 'month'")
    expect(content).toContain('180 * 24 * 60 * 60 * 1000')
  })

  it('builds trend chart option with 4 weeks and plus/minus series', () => {
    expect(content).toContain('function buildTrendOption(items)')
    expect(content).toContain("name: '加分'")
    expect(content).toContain("name: '扣分'")
    expect(content).toContain("type: 'line'")
  })

  it('builds pie chart option with plus/minus totals', () => {
    expect(content).toContain('function buildPieOption(plusTotal, minusTotal)')
    expect(content).toContain("type: 'pie'")
    expect(content).toContain("radius: ['45%', '70%']")
  })

  it('computes maxPoints and minPoints from rankings', () => {
    expect(content).toContain('const maxPoints = computed(')
    expect(content).toContain('const minPoints = computed(')
  })

  it('slices top 5 and bottom 5 students from rankings', () => {
    expect(content).toContain('rankings.slice(0, 5)')
    expect(content).toContain('rankings.slice(-5).reverse()')
  })

  it('takes first 10 records for recent display', () => {
    expect(content).toContain('items.slice(0, 10)')
  })

  it('calls loadDashboard on mount when classId exists', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('if (classId.value) loadDashboard()')
  })
})

describe('ConductDashboard error handling', () => {
  it('wraps rankings loading in try-catch', () => {
    const loadDashboardBlock = content.slice(
      content.indexOf('async function loadDashboard'),
      content.indexOf('onMounted(')
    )
    const catchCount = (loadDashboardBlock.match(/\} catch/g) || []).length
    expect(catchCount).toBeGreaterThanOrEqual(2)
  })

  it('resets data on rankings fetch error', () => {
    expect(content).toContain('topStudents.value = []')
    expect(content).toContain('bottomStudents.value = []')
  })

  it('resets charts on records fetch error', () => {
    expect(content).toContain('trendOption.value = null')
    expect(content).toContain('pieOption.value = null')
  })
})
