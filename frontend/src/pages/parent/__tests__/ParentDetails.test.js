/**
 * ParentDetails.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains data table, trend chart, filters
 *  3. API calls for records
 *  4. Filter and pagination logic
 *  5. Error handling
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentDetails.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentDetails smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentDetails.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentDetails template sections', () => {
  it('contains student info card', () => {
    expect(content).toContain('v-if="currentChild"')
    expect(content).toContain('title="学生信息"')
    expect(content).toContain('currentChild.student_name')
    expect(content).toContain("currentChild.class_name || '-'")
    expect(content).toContain("currentChild.total_points ?? 0")
  })

  it('contains sparkline trend chart', () => {
    expect(content).toContain('v-if="trendData.length > 1"')
    expect(content).toContain('积分走势（近30天）')
    expect(content).toContain('<v-chart')
    expect(content).toContain(':option="trendOption"')
  })

  it('contains date range and type filters', () => {
    expect(content).toContain('v-model:value="dateRange"')
    expect(content).toContain('type="daterange"')
    expect(content).toContain('v-model:value="typeFilter"')
    expect(content).toContain(':options="typeOptions"')
  })

  it('contains data table for records', () => {
    expect(content).toContain('<n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="filteredRecords"')
    expect(content).toContain(':pagination="pagination"')
    expect(content).toContain('remote')
  })

  it('has the title for records section', () => {
    expect(content).toContain('title="操行记录"')
  })
})

describe('ParentDetails API calls', () => {
  it('imports getChildRecords from conduct API', () => {
    expect(content).toContain("import { getChildRecords } from '../../api/conduct'")
  })

  it('calls getChildRecords with pagination params', () => {
    expect(content).toContain('await getChildRecords(props.currentChild.student_id, params)')
  })

  it('passes date range params when set', () => {
    expect(content).toContain("params.start_date = new Date(dateRange.value[0]).toISOString().split('T')[0]")
    expect(content).toContain("params.end_date = new Date(dateRange.value[1]).toISOString().split('T')[0]")
  })

  it('fetches all records for trend calculation', () => {
    expect(content).toContain('async function fetchAllForTrend()')
    expect(content).toContain('size: 200')
  })
})

describe('ParentDetails table columns', () => {
  it('defines date column', () => {
    expect(content).toContain("title: '日期'")
    expect(content).toContain("key: 'created_at'")
  })

  it('defines project column with category tag', () => {
    expect(content).toContain("title: '项目'")
    expect(content).toContain("key: 'rule_name'")
    expect(content).toContain('row.rule_category')
  })

  it('defines points column with success/error tag', () => {
    expect(content).toContain("title: '分值'")
    expect(content).toContain("key: 'points'")
    expect(content).toContain("type: row.points >= 0 ? 'success' : 'error'")
  })

  it('defines teacher column', () => {
    expect(content).toContain("title: '教师'")
    expect(content).toContain("key: 'operator_name'")
  })
})

describe('ParentDetails filter and pagination', () => {
  it('defines type filter options', () => {
    expect(content).toContain("{ label: '全部', value: 'all' }")
    expect(content).toContain("{ label: '加分', value: 'positive' }")
    expect(content).toContain("{ label: '扣分', value: 'negative' }")
  })

  it('filters records client-side by type', () => {
    expect(content).toContain("if (typeFilter.value === 'all') return records.value")
    expect(content).toContain("if (typeFilter.value === 'positive') return records.value.filter(r => r.points >= 0)")
    expect(content).toContain('return records.value.filter(r => r.points < 0)')
  })

  it('resets page on filter change', () => {
    expect(content).toContain('function handleFilterChange()')
    expect(content).toContain('pagination.value.page = 1')
  })

  it('has pagination with page size 15', () => {
    expect(content).toContain('pageSize: 15')
  })

  it('handles page change', () => {
    expect(content).toContain('function handlePageChange(page)')
    expect(content).toContain('pagination.value.page = page')
  })
})

describe('ParentDetails trend chart', () => {
  it('builds cumulative trend data over 30 days', () => {
    expect(content).toContain('function buildTrendData()')
    expect(content).toContain('thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)')
  })

  it('configures line chart with gradient area', () => {
    expect(content).toContain("type: 'line'")
    expect(content).toContain('smooth: true')
    expect(content).toContain("lineStyle: { color: '#F4DA4C', width: 2 }")
    expect(content).toContain("type: 'linear'")
  })

  it('uses ECharts components', () => {
    expect(content).toContain("import { LineChart } from 'echarts/charts'")
    expect(content).toContain("import { GridComponent, TooltipComponent } from 'echarts/components'")
  })
})

describe('ParentDetails error handling', () => {
  it('wraps fetchRecords in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function fetchRecords'),
      content.indexOf('async function fetchAllForTrend')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch {')
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('records.value = []')
  })

  it('wraps fetchAllForTrend in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function fetchAllForTrend'),
      content.indexOf('function buildTrendData')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch {')
    expect(fnBlock).toContain('trendData.value = []')
  })

  it('resets filters when currentChild changes', () => {
    expect(content).toContain('dateRange.value = null')
    expect(content).toContain("typeFilter.value = 'all'")
  })
})
