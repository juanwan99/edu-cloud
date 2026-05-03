/**
 * SemesterPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key UI sections (page-header, stats grid, timeline, period config)
 *  3. Data fetching calls correct API methods from academic.js
 *  4. CRUD operations (create, edit, activate semester; add/delete period)
 *  5. Error handling (try-catch wrappers)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../SemesterPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('SemesterPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../SemesterPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('SemesterPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('学期管理')
    expect(content).toContain('管理学年学期、节次时间')
  })

  it('contains statistics row with 3 stat cards', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('class="stat-label">当前学期')
    expect(content).toContain('class="stat-label">剩余天数')
    expect(content).toContain('class="stat-label">已配置节次')
    expect(content).toContain("activeSemester?.name || '未设置'")
    expect(content).toContain('remainingDays')
    expect(content).toContain('periods.length')
  })

  it('contains semester timeline section', () => {
    expect(content).toContain('<n-timeline>')
    expect(content).toContain('<n-timeline-item')
    expect(content).toContain('sortedSemesters')
    expect(content).toContain('学期时间线')
  })

  it('contains semester data table', () => {
    expect(content).toContain('<n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="semesters"')
  })

  it('contains period configuration section', () => {
    expect(content).toContain(':columns="periodColumns"')
    expect(content).toContain(':data="periods"')
    expect(content).toContain('节次时间')
    expect(content).toContain('添加节次')
  })

  it('contains create semester modal', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain('title="新建学期"')
    expect(content).toContain('positive-text="创建"')
  })

  it('contains edit semester modal', () => {
    expect(content).toContain('v-model:show="showEdit"')
    expect(content).toContain('title="编辑学期"')
    expect(content).toContain('positive-text="保存"')
  })

  it('contains loading spinner', () => {
    expect(content).toContain('<n-spin :show="loading">')
  })

  it('contains semester-current-row scoped style', () => {
    expect(content).toContain('.semester-current-row')
    expect(content).toContain('background-color')
  })
})

describe('SemesterPage data fetching', () => {
  it('imports listSemesters from academic.js', () => {
    expect(content).toContain("import {")
    expect(content).toContain('listSemesters')
    expect(content).toContain("from '../api/academic.js'")
  })

  it('imports getPeriods from academic.js', () => {
    expect(content).toContain('getPeriods')
  })

  it('calls listSemesters in loadData', () => {
    const loadDataBlock = content.slice(
      content.indexOf('async function loadData'),
      content.indexOf('async function handleCreate')
    )
    expect(loadDataBlock).toContain('await listSemesters()')
  })

  it('calls getPeriods for current semester', () => {
    const loadDataBlock = content.slice(
      content.indexOf('async function loadData'),
      content.indexOf('async function handleCreate')
    )
    expect(loadDataBlock).toContain('await getPeriods(current.id)')
  })

  it('calls loadData on mount', () => {
    expect(content).toContain('onMounted(loadData)')
  })

  it('uses useAuthStore for school context', () => {
    expect(content).toContain("import { useAuthStore } from '../stores/auth.js'")
    expect(content).toContain('const auth = useAuthStore()')
  })
})

describe('SemesterPage CRUD operations', () => {
  it('calls createSemester in handleCreate', () => {
    expect(content).toContain('import {')
    expect(content).toContain('createSemester')
    const handleCreateBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleEdit')
    )
    expect(handleCreateBlock).toContain('await createSemester(')
  })

  it('calls updateSemester in handleEdit', () => {
    expect(content).toContain('updateSemester')
    const handleEditBlock = content.slice(
      content.indexOf('async function handleEdit'),
      content.indexOf('async function handleActivate')
    )
    expect(handleEditBlock).toContain('await updateSemester(editForm.value.id')
  })

  it('calls activateSemester in handleActivate', () => {
    expect(content).toContain('activateSemester')
    const handleActivateBlock = content.slice(
      content.indexOf('async function handleActivate'),
      content.indexOf('onMounted(loadData)')
    )
    expect(handleActivateBlock).toContain('await activateSemester(id)')
  })

  it('calls setPeriods when saving period changes', () => {
    expect(content).toContain('setPeriods')
    const savePeriodsBlock = content.slice(
      content.indexOf('async function savePeriods'),
      content.indexOf('function handleAddPeriod')
    )
    expect(savePeriodsBlock).toContain('await setPeriods(')
  })

  it('has add period logic that increments period number', () => {
    const addBlock = content.slice(
      content.indexOf('function handleAddPeriod'),
      content.indexOf('function handleDeletePeriod')
    )
    expect(addBlock).toContain('periods.value.length + 1')
    expect(addBlock).toContain('periods.value.push(')
    expect(addBlock).toContain('savePeriods()')
  })

  it('has delete period logic with re-numbering', () => {
    const deleteBlock = content.slice(
      content.indexOf('function handleDeletePeriod'),
      content.indexOf('function openEdit')
    )
    expect(deleteBlock).toContain('periods.value.splice(index, 1)')
    expect(deleteBlock).toContain('p.period_number = i + 1')
    expect(deleteBlock).toContain('savePeriods()')
  })

  it('resets form after successful create', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleEdit')
    )
    expect(createBlock).toContain("form.value = { name: '', school_year: '', term: 1 }")
    expect(createBlock).toContain('dateRange.value = null')
    expect(createBlock).toContain('showCreate.value = false')
  })

  it('creates button renders text for edit and activate', () => {
    expect(content).toContain("{ default: () => '编辑' }")
    expect(content).toContain("{ default: () => '设为当前' }")
  })
})

describe('SemesterPage column definitions', () => {
  it('defines table columns for semester data', () => {
    expect(content).toContain("title: '学期名称'")
    expect(content).toContain("title: '学年'")
    expect(content).toContain("title: '学期'")
    expect(content).toContain("title: '开始'")
    expect(content).toContain("title: '结束'")
    expect(content).toContain("title: '状态'")
    expect(content).toContain("title: '操作'")
  })

  it('renders status with NTag (current/history)', () => {
    expect(content).toContain("{ default: () => '当前' }")
    expect(content).toContain("{ default: () => '历史' }")
  })

  it('defines period columns with time pickers', () => {
    expect(content).toContain("title: '序号'")
    expect(content).toContain("title: '开始时间'")
    expect(content).toContain("title: '结束时间'")
    expect(content).toContain("title: '类型'")
    expect(content).toContain('NTimePicker')
  })

  it('maps period types to Chinese labels', () => {
    expect(content).toContain("class: '上课'")
    expect(content).toContain("break: '课间'")
    expect(content).toContain("activity: '活动'")
    expect(content).toContain("self_study: '自习'")
  })
})

describe('SemesterPage computed properties', () => {
  it('computes activeSemester from is_current flag', () => {
    expect(content).toContain('semesters.value.find(s => s.is_current)')
  })

  it('computes sortedSemesters by start_date descending', () => {
    expect(content).toContain('sortedSemesters')
    expect(content).toContain("(b.start_date || '').localeCompare(a.start_date || '')")
  })

  it('computes remainingDays from active semester end_date', () => {
    expect(content).toContain('remainingDays')
    expect(content).toContain("active.end_date + 'T23:59:59'")
    expect(content).toContain('Math.ceil')
  })

  it('has row class function for current semester', () => {
    expect(content).toContain('function rowClassName(row)')
    expect(content).toContain("'semester-current-row'")
  })
})

describe('SemesterPage time helpers', () => {
  it('converts time string to timestamp for NTimePicker', () => {
    expect(content).toContain('function timeToTimestamp(timeStr)')
    expect(content).toContain('(h * 60 + m) * 60 * 1000')
  })

  it('converts timestamp back to time string', () => {
    expect(content).toContain('function timestampToTime(ts)')
    expect(content).toContain('Math.floor(ts / 60000)')
  })
})

describe('SemesterPage error handling', () => {
  it('wraps loadData in try-catch', () => {
    const loadDataBlock = content.slice(
      content.indexOf('async function loadData'),
      content.indexOf('async function handleCreate')
    )
    expect(loadDataBlock).toContain('try {')
    expect(loadDataBlock).toContain('} catch')
    expect(loadDataBlock).toContain('加载学期失败')
  })

  it('wraps handleCreate in try-catch', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleEdit')
    )
    expect(createBlock).toContain('try {')
    expect(createBlock).toContain('} catch')
    expect(createBlock).toContain('创建失败')
  })

  it('wraps handleEdit in try-catch', () => {
    const editBlock = content.slice(
      content.indexOf('async function handleEdit'),
      content.indexOf('async function handleActivate')
    )
    expect(editBlock).toContain('try {')
    expect(editBlock).toContain('} catch')
    expect(editBlock).toContain('更新失败')
  })

  it('wraps handleActivate in try-catch', () => {
    const activateBlock = content.slice(
      content.indexOf('async function handleActivate'),
      content.indexOf('onMounted(loadData)')
    )
    expect(activateBlock).toContain('try {')
    expect(activateBlock).toContain('} catch')
    expect(activateBlock).toContain('操作失败')
  })

  it('wraps savePeriods in try-catch', () => {
    const saveBlock = content.slice(
      content.indexOf('async function savePeriods'),
      content.indexOf('function handleAddPeriod')
    )
    expect(saveBlock).toContain('try {')
    expect(saveBlock).toContain('} catch')
    expect(saveBlock).toContain('保存节次失败')
  })

  it('validates date range before create', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleEdit')
    )
    expect(createBlock).toContain('dateRange.value.length !== 2')
    expect(createBlock).toContain('请选择起止日期')
  })

  it('validates date range before edit', () => {
    const editBlock = content.slice(
      content.indexOf('async function handleEdit'),
      content.indexOf('async function handleActivate')
    )
    expect(editBlock).toContain('editDateRange.value.length !== 2')
    expect(editBlock).toContain('请选择起止日期')
  })

  it('uses e.response?.data?.detail fallback pattern', () => {
    const errorFallbacks = content.match(/e\.response\?\.data\?\.detail \|\|/g)
    expect(errorFallbacks).not.toBeNull()
    expect(errorFallbacks.length).toBeGreaterThanOrEqual(4)
  })
})
