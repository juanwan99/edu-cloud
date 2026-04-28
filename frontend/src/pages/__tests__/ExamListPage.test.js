/**
 * ExamListPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (stats-row, filter-bar, data-table, empty-state, create-modal)
 *  3. API calls (listExams, createExam, archiveExam)
 *  4. State/data processing (statusMap, stats computed, filteredExams, form rules)
 *  5. Error handling (try-catch in loadExams, handleCreate, handleArchive)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ExamListPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ExamListPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ExamListPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ExamListPage template sections', () => {
  it('contains stats-row with 4 stat cards', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('stats.total')
    expect(content).toContain('stats.active')
    expect(content).toContain('stats.completed')
    expect(content).toContain('stats.draft')
  })

  it('contains filter-bar with search and status filter', () => {
    expect(content).toContain('class="filter-bar"')
    expect(content).toContain('v-model:value="searchText"')
    expect(content).toContain('v-model:value="statusFilter"')
    expect(content).toContain('clearFilters')
  })

  it('contains data-table with columns and sorting', () => {
    expect(content).toContain('n-data-table')
    expect(content).toContain(':columns="columns"')
    expect(content).toContain(':data="filteredExams"')
    expect(content).toContain(':loading="loading"')
    expect(content).toContain("columnKey: 'created_at', order: 'descend'")
  })

  it('contains empty state with two variants', () => {
    expect(content).toContain('class="empty-state"')
    expect(content).toContain('exams.length === 0')
    expect(content).toContain('filteredExams.length === 0')
  })

  it('contains create exam modal with form fields', () => {
    expect(content).toContain('v-model:show="showCreate"')
    expect(content).toContain("title=\"创建考试\"")
    expect(content).toContain('createForm.name')
    expect(content).toContain('createForm.card_title')
    expect(content).toContain('createForm.exam_date')
    expect(content).toContain('createForm.description')
  })
})

describe('ExamListPage API calls', () => {
  it('imports listExams, createExam, archiveExam from api/exams', () => {
    expect(content).toContain('listExams, createExam, archiveExam')
    expect(content).toContain("from '../api/exams'")
  })

  it('calls listExams in loadExams function', () => {
    expect(content).toContain('await listExams()')
    expect(content).toContain('exams.value = data')
  })

  it('calls createExam in handleCreate function', () => {
    expect(content).toContain('await createExam(payload)')
  })

  it('calls archiveExam in handleArchive function', () => {
    expect(content).toContain('await archiveExam(examId)')
  })

  it('loads exams on mount', () => {
    expect(content).toContain('onMounted(loadExams)')
  })
})

describe('ExamListPage status mapping', () => {
  it('defines 7-entry statusMap with label and type', () => {
    expect(content).toContain("draft: { label: '草稿', type: 'default' }")
    expect(content).toContain("scanning: { label: '扫描中', type: 'info' }")
    expect(content).toContain("grading: { label: '批改中', type: 'warning' }")
    expect(content).toContain("reviewing: { label: '复核中', type: 'warning' }")
    expect(content).toContain("completed: { label: '已完成', type: 'success' }")
    expect(content).toContain("published: { label: '已发布', type: 'success' }")
    expect(content).toContain("archived: { label: '已归档', type: 'default' }")
  })

  it('defines matching statusFilterOptions array', () => {
    expect(content).toContain("{ label: '草稿', value: 'draft' }")
    expect(content).toContain("{ label: '扫描中', value: 'scanning' }")
    expect(content).toContain("{ label: '已归档', value: 'archived' }")
  })
})

describe('ExamListPage stats computed', () => {
  it('computes total from list length', () => {
    expect(content).toContain('total: list.length')
  })

  it('computes active count from scanning/grading/reviewing statuses', () => {
    expect(content).toContain("const activeStatuses = ['scanning', 'grading', 'reviewing']")
    expect(content).toContain('activeStatuses.includes(e.status)')
  })

  it('computes completed count from completed or published', () => {
    expect(content).toContain("e.status === 'completed' || e.status === 'published'")
  })

  it('computes draft count', () => {
    expect(content).toContain("e.status === 'draft'")
  })
})

describe('ExamListPage filteredExams computed', () => {
  it('filters by statusFilter value', () => {
    expect(content).toContain('e.status === statusFilter.value')
  })

  it('filters by searchText with case-insensitive name match', () => {
    expect(content).toContain('searchText.value.toLowerCase()')
    expect(content).toContain('e.name?.toLowerCase().includes(keyword)')
  })

  it('clearFilters resets both filters', () => {
    expect(content).toContain("searchText.value = ''")
    expect(content).toContain('statusFilter.value = null')
  })
})

describe('ExamListPage table columns', () => {
  it('defines columns with correct keys', () => {
    expect(content).toContain("key: 'name'")
    expect(content).toContain("key: 'status'")
    expect(content).toContain("key: 'subject_count'")
    expect(content).toContain("key: 'student_count'")
    expect(content).toContain("key: 'exam_date'")
    expect(content).toContain("key: 'created_at'")
    expect(content).toContain("key: 'actions'")
  })

  it('renders action buttons including detail, analysis, archive, copy', () => {
    expect(content).toContain("default: () => '详情'")
    expect(content).toContain("default: () => '分析'")
    expect(content).toContain("default: () => '归档'")
    expect(content).toContain("default: () => '复制'")
  })

  it('archive button only shows for completed exams', () => {
    expect(content).toContain("if (row.status === 'completed')")
  })

  it('row click navigates to exam detail', () => {
    expect(content).toContain('router.push(`/exams/${row.id}`)')
  })
})

describe('ExamListPage form validation', () => {
  it('requires name field', () => {
    expect(content).toContain("name: { required: true, message: '请输入考试名称', trigger: 'blur' }")
  })

  it('requires card_title field', () => {
    expect(content).toContain("card_title: { required: true, message: '请输入答题卡标题', trigger: 'blur' }")
  })
})

describe('ExamListPage handleCreate logic', () => {
  it('validates form before creating', () => {
    expect(content).toContain('await createFormRef.value?.validate()')
  })

  it('formats exam_date to ISO date string', () => {
    expect(content).toContain("payload.exam_date = new Date(createForm.exam_date).toISOString().split('T')[0]")
  })

  it('resets form after successful creation', () => {
    const createBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleArchive')
    )
    expect(createBlock).toContain("createForm.name = ''")
    expect(createBlock).toContain("createForm.card_title = ''")
    expect(createBlock).toContain('createForm.exam_date = null')
    expect(createBlock).toContain("createForm.description = ''")
    expect(createBlock).toContain('showCreate.value = false')
  })

  it('shows success message on creation', () => {
    expect(content).toContain("message.success('考试创建成功')")
  })
})

describe('ExamListPage handleCopy logic', () => {
  it('prefills form with exam name plus copy suffix', () => {
    expect(content).toContain('createForm.name = `${exam.name} (副本)`')
  })

  it('opens create modal after copying', () => {
    const copyBlock = content.slice(
      content.indexOf('function handleCopy'),
      content.indexOf('onMounted(loadExams)')
    )
    expect(copyBlock).toContain('showCreate.value = true')
  })
})

describe('ExamListPage error handling', () => {
  it('wraps loadExams in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function handleCreate')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps handleCreate in try-catch with error message', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleArchive')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("e.response?.data?.detail || '创建失败'")
  })

  it('wraps handleArchive in try-catch with error message', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleArchive'),
      content.indexOf('function handleCopy')
    )
    expect(fnBlock).toContain('} catch (e) {')
    expect(fnBlock).toContain("e.response?.data?.detail || '归档失败'")
  })

  it('uses finally block to reset creating flag', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleCreate'),
      content.indexOf('async function handleArchive')
    )
    expect(fnBlock).toContain('} finally {')
    expect(fnBlock).toContain('creating.value = false')
  })
})

describe('ExamListPage responsive design', () => {
  it('has responsive grid for stats row', () => {
    expect(content).toContain('grid-template-columns: repeat(auto-fit')
    expect(content).toContain('grid-template-columns: repeat(2, 1fr)')
  })

  it('wraps filter bar on small screens', () => {
    expect(content).toContain('flex-wrap: wrap')
  })
})
