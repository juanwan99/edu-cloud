/**
 * ConductRecords source-text tests.
 *
 * Validates:
 *  1. Smoke import
 *  2. Template sections (stat cards, filters, batch delete bar, records table)
 *  3. API calls via conduct.js (getRecords, deleteRecord)
 *  4. Operations (pagination, filtering, batch delete, week stats)
 *  5. Error handling (try-catch in all async functions)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ConductRecords.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ConductRecords smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ConductRecords.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ConductRecords template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('title="积分记录"')
    expect(content).toContain('查看和管理所有操行积分变动')
  })

  it('contains class-not-selected alert', () => {
    expect(content).toContain('v-if="!classId"')
    expect(content).toContain('未选择班级')
  })

  it('contains 3 stat cards (week count, plus total, minus total)', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('class="stat-label">本周记录数')
    expect(content).toContain('class="stat-label">加分总额')
    expect(content).toContain('class="stat-label">扣分总额')
    expect(content).toContain('statCards.weekCount')
    expect(content).toContain('statCards.plusTotal')
    expect(content).toContain('statCards.minusTotal')
    expect(content).not.toContain('n-statistic')
  })

  it('contains filter section (student name, type, rule, date range)', () => {
    expect(content).toContain('v-model:value="filterStudent"')
    expect(content).toContain('搜索学生姓名')
    expect(content).toContain('v-model:value="filterType"')
    expect(content).toContain(':options="typeOptions"')
    expect(content).toContain('v-model:value="filterRule"')
    expect(content).toContain(':options="ruleOptions"')
    expect(content).toContain('v-model:value="dateRange"')
    expect(content).toContain('type="daterange"')
  })

  it('contains reset filters button', () => {
    expect(content).toContain('@click="resetFilters"')
    expect(content).toContain('重置')
  })

  it('contains batch delete bar', () => {
    expect(content).toContain('v-if="checkedRowKeys.length > 0"')
    expect(content).toContain('批量删除')
    expect(content).toContain('@positive-click="handleBatchDelete"')
  })

  it('contains records data table with remote pagination', () => {
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="filteredRecords"')
    expect(content).toContain(':pagination="pagination"')
    expect(content).toContain('v-model:checked-row-keys="checkedRowKeys"')
    expect(content).toContain('remote')
  })
})

describe('ConductRecords API calls', () => {
  it('imports required API functions from conduct.js', () => {
    expect(content).toContain('getRecords')
    expect(content).toContain('deleteRecord')
    expect(content).toContain("from '../../api/conduct'")
  })

  it('calls getRecords with pagination and filter params', () => {
    expect(content).toContain('getRecords(classId.value, {')
    // pagination params
    expect(content).toContain('page: page.value')
    expect(content).toContain('page_size: pageSize.value')
  })

  it('calls deleteRecord for single deletion', () => {
    expect(content).toContain('deleteRecord(classId.value, recordId)')
  })

  it('calls deleteRecord in batch for batch deletion', () => {
    expect(content).toContain('deleteRecord(classId.value, id)')
  })
})

describe('ConductRecords operations', () => {
  it('defines table columns with selection, date, name, points, reason, rule, operator, actions', () => {
    expect(content).toContain("type: 'selection'")
    expect(content).toContain("title: '日期'")
    expect(content).toContain("title: '学生姓名'")
    expect(content).toContain("title: '积分'")
    expect(content).toContain("title: '原因'")
    expect(content).toContain("title: '班规项'")
    expect(content).toContain("key: 'rule_name'")
    expect(content).toContain("title: '操作人'")
    expect(content).toContain("title: '操作'")
  })

  it('defines type filter options (all, plus, minus)', () => {
    expect(content).toContain("label: '全部'")
    expect(content).toContain("label: '加分', value: 'plus'")
    expect(content).toContain("label: '扣分', value: 'minus'")
  })

  it('filters records by type (plus/minus)', () => {
    expect(content).toContain("filterType.value === 'plus'")
    expect(content).toContain('r.points > 0')
    expect(content).toContain("filterType.value === 'minus'")
    expect(content).toContain('r.points < 0')
  })

  it('filters records by rule name', () => {
    expect(content).toContain('r.rule_name === filterRule.value')
  })

  it('computes ruleOptions from record data', () => {
    expect(content).toContain('const ruleOptions = computed(')
    expect(content).toContain("if (r.rule_name) names.add(r.rule_name)")
  })

  it('implements remote pagination with page/pageSize', () => {
    expect(content).toContain('const pagination = computed(')
    expect(content).toContain('showSizePicker: true')
    expect(content).toContain('pageSizes: [10, 20, 50]')
  })

  it('implements debounced student name search', () => {
    expect(content).toContain('function debouncedLoad()')
    expect(content).toContain('clearTimeout(debounceTimer)')
    expect(content).toContain('setTimeout(')
    expect(content).toContain('300)')
  })

  it('resets filters to default state', () => {
    expect(content).toContain('function resetFilters()')
    expect(content).toContain("filterStudent.value = ''")
    expect(content).toContain('filterType.value = null')
    expect(content).toContain('filterRule.value = null')
    expect(content).toContain('dateRange.value = null')
  })

  it('loads week stats separately for stat cards', () => {
    expect(content).toContain('async function loadWeekStats()')
    expect(content).toContain('7 * 24 * 60 * 60 * 1000')
    expect(content).toContain("page_size: 200")
  })

  it('handles batch delete with success count', () => {
    expect(content).toContain('async function handleBatchDelete()')
    expect(content).toContain('for (const id of ids)')
    expect(content).toContain('successCount++')
  })

  it('loads records and week stats on mount', () => {
    expect(content).toContain('onMounted(')
    expect(content).toContain('loadRecords()')
    expect(content).toContain('loadWeekStats()')
  })
})

describe('ConductRecords error handling', () => {
  it('wraps loadRecords in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadRecords'),
      content.indexOf('async function loadWeekStats')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps loadWeekStats in try-catch', () => {
    const block = content.slice(
      content.indexOf('async function loadWeekStats'),
      content.indexOf('function handlePageChange')
    )
    expect(block).toContain('try {')
    expect(block).toContain('} catch')
  })

  it('wraps handleDelete in try-catch with error message', () => {
    const block = content.slice(
      content.indexOf('async function handleDelete'),
      content.indexOf('async function handleBatchDelete')
    )
    expect(block).toContain('try {')
    expect(block).toContain("e.response?.data?.detail || '删除失败'")
  })

  it('reloads both records and week stats after deletion', () => {
    expect(content).toContain('await loadRecords()')
    expect(content).toContain('await loadWeekStats()')
  })
})
