/**
 * TeachingPlanPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key UI sections (filters, plan table, detail drawer, create modal, delete confirm)
 *  3. Data fetching calls correct API methods from academic.js
 *  4. CRUD operations (create, edit weeks, delete plan)
 *  5. Error handling (try-catch wrappers + 409 conflict)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../TeachingPlanPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('TeachingPlanPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../TeachingPlanPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('TeachingPlanPage template sections', () => {
  it('contains page header with title and subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('教学计划')
    expect(content).toContain('管理学期教学计划，安排每周教学内容与知识点')
  })

  it('contains create button', () => {
    expect(content).toContain('新建计划')
    expect(content).toContain('showCreate = true')
  })

  it('contains filter bar with semester, subject, grade', () => {
    expect(content).toContain('v-model:value="filter.semester"')
    expect(content).toContain('v-model:value="filter.subject_code"')
    expect(content).toContain('v-model:value="filter.grade_id"')
    expect(content).toContain('placeholder="学期"')
    expect(content).toContain('placeholder="科目"')
    expect(content).toContain('placeholder="年级"')
  })

  it('contains plan data table', () => {
    expect(content).toContain('<n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="plans"')
  })

  it('contains detail drawer for week editing', () => {
    expect(content).toContain('<n-drawer')
    expect(content).toContain('v-model:show="showDetail"')
    expect(content).toContain(':width="640"')
    expect(content).toContain('保存修改')
    expect(content).toContain('添加一周')
  })

  it('contains week data table in drawer', () => {
    expect(content).toContain(':columns="weekColumns"')
    expect(content).toContain(':data="editWeeks"')
  })

  it('contains create plan modal', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain('title="新建教学计划"')
    expect(content).toContain('positive-text="创建"')
  })

  it('contains delete confirmation modal', () => {
    expect(content).toContain('v-model:show="showDeleteConfirm"')
    expect(content).toContain('title="确认删除"')
    expect(content).toContain('此操作不可恢复')
  })

  it('contains loading spinner', () => {
    expect(content).toContain('<n-spin :show="loading">')
  })
})

describe('TeachingPlanPage data fetching', () => {
  it('imports CRUD functions from academic.js', () => {
    expect(content).toContain('createTeachingPlan')
    expect(content).toContain('listTeachingPlans')
    expect(content).toContain('getTeachingPlan')
    expect(content).toContain('updateTeachingPlan')
    expect(content).toContain('deleteTeachingPlan')
    expect(content).toContain('listSemesters')
    expect(content).toContain("from '../api/academic.js'")
  })

  it('calls listTeachingPlans in loadPlans with filter params', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadPlans'),
      content.indexOf('async function openDetail')
    )
    expect(loadBlock).toContain('await listTeachingPlans(params)')
    expect(loadBlock).toContain('filter.value.semester')
    expect(loadBlock).toContain('filter.value.subject_code')
    expect(loadBlock).toContain('filter.value.grade_id')
  })

  it('calls listSemesters in loadSemesters', () => {
    const semBlock = content.slice(
      content.indexOf('async function loadSemesters'),
      content.indexOf('async function loadGrades')
    )
    expect(semBlock).toContain('await listSemesters()')
  })

  it('loads grades via client.get /grades', () => {
    const gradeBlock = content.slice(
      content.indexOf('async function loadGrades'),
      content.indexOf('async function loadPlans')
    )
    expect(gradeBlock).toContain("client.get('/grades')")
  })

  it('calls getTeachingPlan in openDetail', () => {
    const detailBlock = content.slice(
      content.indexOf('async function openDetail'),
      content.indexOf('function addWeek')
    )
    expect(detailBlock).toContain('await getTeachingPlan(id)')
  })

  it('initializes by loading semesters, grades, then plans on mount', () => {
    expect(content).toContain('onMounted(async () =>')
    expect(content).toContain('Promise.all([loadSemesters(), loadGrades()])')
    expect(content).toContain('await loadPlans()')
  })
})

describe('TeachingPlanPage CRUD operations', () => {
  it('creates plan with initial week in handleCreate', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('function confirmDelete')
    )
    expect(createBlock).toContain('await createTeachingPlan(')
    expect(createBlock).toContain('weeks_json: initialWeek')
    expect(createBlock).toContain('week_number: 1')
  })

  it('validates semester and subject_code before create', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('function confirmDelete')
    )
    expect(createBlock).toContain('!createForm.value.semester || !createForm.value.subject_code')
    expect(createBlock).toContain('请填写学期和科目')
  })

  it('resets form and closes modal after successful create', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('function confirmDelete')
    )
    expect(createBlock).toContain('showCreate.value = false')
    expect(createBlock).toContain("createForm.value = { semester: '', subject_code: '', grade_id: null }")
    expect(createBlock).toContain('教学计划创建成功')
  })

  it('updates teaching plan weeks in handleSaveWeeks', () => {
    const saveBlock = content.slice(
      content.indexOf('async function handleSaveWeeks'),
      content.indexOf('async function handleCreate')
    )
    expect(saveBlock).toContain('await updateTeachingPlan(detailPlan.value.id')
    expect(saveBlock).toContain('weeks_json: editWeeks.value')
    expect(saveBlock).toContain('保存成功')
  })

  it('deletes plan in handleDelete', () => {
    const deleteBlock = content.slice(
      content.indexOf('async function handleDelete'),
      content.indexOf('onMounted(async')
    )
    expect(deleteBlock).toContain('await deleteTeachingPlan(deleteTargetId.value)')
    expect(deleteBlock).toContain('已删除')
  })

  it('adds a week with incremented week_number', () => {
    const addBlock = content.slice(
      content.indexOf('function addWeek'),
      content.indexOf('async function handleSaveWeeks')
    )
    expect(addBlock).toContain('editWeeks.value.length + 1')
    expect(addBlock).toContain('editWeeks.value.push(')
    expect(addBlock).toContain("topic: ''")
    expect(addBlock).toContain('knowledge_points: []')
  })

  it('deep clones weeks_json for editing', () => {
    const detailBlock = content.slice(
      content.indexOf('async function openDetail'),
      content.indexOf('function addWeek')
    )
    expect(detailBlock).toContain('JSON.parse(JSON.stringify(data.weeks_json || []))')
  })

  it('has edit and delete buttons in columns', () => {
    expect(content).toContain("{ default: () => '编辑' }")
    expect(content).toContain("{ default: () => '删除' }")
    expect(content).toContain('openDetail(row.id)')
    expect(content).toContain('confirmDelete(row.id)')
  })
})

describe('TeachingPlanPage column definitions', () => {
  it('defines table columns for plan list', () => {
    expect(content).toContain("title: '科目'")
    expect(content).toContain("title: '学期'")
    expect(content).toContain("title: '周数'")
    expect(content).toContain("title: '创建时间'")
    expect(content).toContain("title: '操作'")
  })

  it('renders week count with NTag', () => {
    expect(content).toContain('row.weeks_count')
    expect(content).toContain("type: 'info'")
  })

  it('formats created_at to Chinese locale string', () => {
    expect(content).toContain("new Date(row.created_at).toLocaleString('zh-CN')")
  })

  it('defines week columns for detail editing', () => {
    expect(content).toContain("title: '周次'")
    expect(content).toContain("title: '主题'")
    expect(content).toContain("title: '知识点'")
    expect(content).toContain("title: '备注'")
  })

  it('renders knowledge points as NTag list', () => {
    expect(content).toContain('row.knowledge_points || []')
    expect(content).toContain("size: 'tiny'")
  })
})

describe('TeachingPlanPage subject options', () => {
  it('defines 9 subject options', () => {
    const subjectMatches = content.match(/\{ label: '[一-鿿]+', value: '[A-Z]+' \}/g)
    expect(subjectMatches).not.toBeNull()
    expect(subjectMatches.length).toBe(9)
  })

  it('includes core subjects', () => {
    expect(content).toContain("label: '数学', value: 'SX'")
    expect(content).toContain("label: '语文', value: 'YW'")
    expect(content).toContain("label: '英语', value: 'YY'")
  })
})

describe('TeachingPlanPage error handling', () => {
  it('wraps loadPlans in try-catch', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadPlans'),
      content.indexOf('async function openDetail')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch')
    expect(loadBlock).toContain('加载教学计划失败')
  })

  it('wraps openDetail in try-catch', () => {
    const detailBlock = content.slice(
      content.indexOf('async function openDetail'),
      content.indexOf('function addWeek')
    )
    expect(detailBlock).toContain('try {')
    expect(detailBlock).toContain('} catch')
    expect(detailBlock).toContain('加载详情失败')
  })

  it('wraps handleSaveWeeks in try-catch', () => {
    const saveBlock = content.slice(
      content.indexOf('async function handleSaveWeeks'),
      content.indexOf('async function handleCreate')
    )
    expect(saveBlock).toContain('try {')
    expect(saveBlock).toContain('} catch')
    expect(saveBlock).toContain('保存失败')
  })

  it('wraps handleCreate in try-catch', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('function confirmDelete')
    )
    expect(createBlock).toContain('try {')
    expect(createBlock).toContain('} catch')
  })

  it('handles 409 conflict on create', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('function confirmDelete')
    )
    expect(createBlock).toContain('e.response?.status === 409')
    expect(createBlock).toContain('该科目+年级+学期的教学计划已存在')
  })

  it('wraps handleDelete in try-catch', () => {
    const deleteBlock = content.slice(
      content.indexOf('async function handleDelete'),
      content.indexOf('onMounted(async')
    )
    expect(deleteBlock).toContain('try {')
    expect(deleteBlock).toContain('} catch')
  })

  it('silently handles loadSemesters failure', () => {
    const semBlock = content.slice(
      content.indexOf('async function loadSemesters'),
      content.indexOf('async function loadGrades')
    )
    expect(semBlock).toContain('} catch')
  })

  it('silently handles loadGrades failure', () => {
    const gradeBlock = content.slice(
      content.indexOf('async function loadGrades'),
      content.indexOf('async function loadPlans')
    )
    expect(gradeBlock).toContain('} catch')
  })

  it('uses e.response?.data?.detail fallback pattern', () => {
    const errorFallbacks = content.match(/e\.response\?\.data\?\.detail \|\|/g)
    expect(errorFallbacks).not.toBeNull()
    expect(errorFallbacks.length).toBeGreaterThanOrEqual(2)
  })
})
