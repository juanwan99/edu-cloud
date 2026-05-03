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

  it('contains scope-adaptive summary cards from overviewData', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('v-if="overviewData?.summary"')
    expect(content).toContain('v-for="(value, key) in summaryCards"')
    expect(content).toContain('value.label')
    expect(content).not.toContain('n-statistic')
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
  it('imports getConductOverview, getRecords and getStudentRankings from conduct API', () => {
    expect(content).toContain("import { getConductOverview, getRecords, getStudentRankings } from '../../api/conduct'")
  })

  it('calls getStudentRankings for rankings data', () => {
    expect(content).toContain('getStudentRankings(classId.value, {})')
  })

  it('calls getRecords with date range and pagination', () => {
    expect(content).toContain('getRecords(classId.value, {')
    expect(content).toContain('page: 1')
    // F-008: param name is 'size' (matching backend Query param), not 'page_size'
    expect(content).toContain('size: 200')
    expect(content).not.toContain('page_size: 200')
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

  it('calls loadOverview on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('onMounted(() => loadOverview())')
  })
})

describe('ConductDashboard error handling', () => {
  it('wraps rankings loading in try-catch', () => {
    const loadDashboardBlock = content.slice(
      content.indexOf('async function loadDashboard'),
      content.indexOf('async function loadOverview')
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

  it('wraps loadOverview in try-catch', () => {
    const loadOverviewBlock = content.slice(
      content.indexOf('async function loadOverview'),
      content.indexOf('onMounted(')
    )
    expect(loadOverviewBlock).toContain('try {')
    expect(loadOverviewBlock).toContain('} catch')
    expect(loadOverviewBlock).toContain('Failed to load overview')
  })
})

describe('ConductDashboard scope-adaptive rendering', () => {
  it('has overviewData ref and scopeType computed', () => {
    expect(content).toContain('const overviewData = ref(null)')
    expect(content).toContain("overviewData.value?.scope_type || null")
  })

  it('calls getConductOverview in loadOverview', () => {
    expect(content).toContain('getConductOverview()')
    expect(content).toContain('overviewData.value = res.data')
  })

  it('loads class detail data when scope is class', () => {
    expect(content).toContain("res.data.scope_type === 'class' && classId.value")
    expect(content).toContain('await loadDashboard()')
  })

  it('renders class scope with v-if on scopeType', () => {
    expect(content).toContain("v-if=\"scopeType === 'class'\"")
    expect(content).toContain('title="积分最高"')
    expect(content).toContain('title="积分最低"')
  })

  it('renders school scope with class comparison table', () => {
    expect(content).toContain("v-else-if=\"scopeType === 'school'\"")
    expect(content).toContain('title="班级德育对比"')
    expect(content).toContain('classCompareColumns')
    expect(content).toContain('class_comparison')
  })

  it('renders district scope with school comparison table', () => {
    expect(content).toContain("v-else-if=\"scopeType === 'district'\"")
    expect(content).toContain('title="学校德育对比"')
    expect(content).toContain('schoolCompareColumns')
    expect(content).toContain('school_comparison')
  })

  it('hides time range selector for non-class scopes', () => {
    // The n-radio-group element has v-if="scopeType === 'class'" before v-model:value="timeRange"
    // Both attributes are on the same <n-radio-group> element
    expect(content).toContain('v-if="scopeType === \'class\'"')
    // Verify v-if comes before the timeRange binding (same element)
    const vifIdx = content.indexOf("v-if=\"scopeType === 'class'\"")
    const modelIdx = content.indexOf('v-model:value="timeRange"')
    expect(vifIdx).toBeLessThan(modelIdx)
    expect(vifIdx).toBeGreaterThan(-1)
  })

  it('has classCompareColumns with class_name, record_count, avg_points', () => {
    expect(content).toContain("title: '班级'")
    expect(content).toContain("key: 'class_name'")
    expect(content).toContain("key: 'record_count'")
    expect(content).toContain("key: 'avg_points'")
  })

  it('has schoolCompareColumns with school_name, total_students, record_count, avg_points', () => {
    expect(content).toContain("title: '学校'")
    expect(content).toContain("key: 'school_name'")
    expect(content).toContain("key: 'total_students'")
  })

  it('imports NDataTable from naive-ui', () => {
    expect(content).toContain('NDataTable')
  })

  it('imports h from vue for render functions', () => {
    expect(content).toContain("import { h, ref, computed, onMounted } from 'vue'")
  })

  it('has summaryCards computed that adapts to scope type', () => {
    expect(content).toContain('const summaryCards = computed(')
    expect(content).toContain("st === 'class'")
    expect(content).toContain("st === 'school'")
    expect(content).toContain("st === 'district'")
  })

  it('uses NDataTable for school and district tables', () => {
    expect(content).toContain('<n-data-table')
    expect(content).toContain(':columns="classCompareColumns"')
    expect(content).toContain(':columns="schoolCompareColumns"')
  })
})
