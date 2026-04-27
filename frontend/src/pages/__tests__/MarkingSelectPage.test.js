/**
 * MarkingSelectPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains page structure (header, toolbar, stats, subject cards)
 *  3. Filter options and status filtering logic
 *  4. Statistics computations (totalQuestions, completedQuestions, pendingQuestions)
 *  5. Subject progress calculation
 *  6. API calls (loadExams, loadSubjects)
 *  7. Error handling (try-catch in async functions)
 *  8. Table column definitions and routing
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../MarkingSelectPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('MarkingSelectPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../MarkingSelectPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('MarkingSelectPage template structure', () => {
  it('contains page header with title', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('人工阅卷')
  })

  it('contains subtitle describing the page purpose', () => {
    expect(content).toContain('class="page-subtitle"')
    expect(content).toContain('选择科目和题目开始阅卷')
  })

  it('contains toolbar with exam and status selectors', () => {
    expect(content).toContain('class="toolbar"')
    expect(content).toContain('v-model:value="selectedExamId"')
    expect(content).toContain('v-model:value="statusFilter"')
  })

  it('contains statistics row with three cards', () => {
    expect(content).toContain('class="stats-row"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('总题目数')
    expect(content).toContain('已完成')
    expect(content).toContain('待批改')
  })

  it('contains stat dots for visual indicators', () => {
    expect(content).toContain('class="stat-dot stat-dot--success"')
    expect(content).toContain('class="stat-dot stat-dot--warning"')
  })

  it('contains subject card list', () => {
    expect(content).toContain('class="subject-card"')
    expect(content).toContain('class="subject-header"')
    expect(content).toContain('class="subject-name"')
  })

  it('contains empty state fallback', () => {
    expect(content).toContain('<n-empty')
    expect(content).toContain('请先选择考试')
    expect(content).toContain('没有匹配的题目')
  })
})

describe('MarkingSelectPage filter options', () => {
  it('defines four filter options', () => {
    expect(content).toContain("{ label: '全部', value: 'all' }")
    expect(content).toContain("{ label: '待批改', value: 'pending' }")
    expect(content).toContain("{ label: '进行中', value: 'in_progress' }")
    expect(content).toContain("{ label: '已完成', value: 'completed' }")
  })

  it('questionStatus determines status from graded_count and total_answers', () => {
    expect(content).toContain('function questionStatus(q)')
    expect(content).toContain("if (q.total_answers <= 0) return 'pending'")
    expect(content).toContain("if (q.graded_count >= q.total_answers) return 'completed'")
    expect(content).toContain("if (q.graded_count > 0) return 'in_progress'")
  })

  it('filterQuestions uses statusFilter', () => {
    expect(content).toContain('function filterQuestions(questions)')
    expect(content).toContain("statusFilter.value === 'all'")
  })

  it('filteredSubjects filters by status', () => {
    expect(content).toContain('const filteredSubjects = computed')
    expect(content).toContain('filterQuestions(subj.questions || []).length > 0')
  })
})

describe('MarkingSelectPage statistics computations', () => {
  it('computes allQuestions from subjects', () => {
    expect(content).toContain('subjects.value.flatMap(s => s.questions || [])')
  })

  it('computes totalQuestions as length of allQuestions', () => {
    expect(content).toContain('const totalQuestions = computed(() => allQuestions.value.length)')
  })

  it('computes completedQuestions by graded vs total', () => {
    expect(content).toContain('q.total_answers > 0 && q.graded_count >= q.total_answers')
  })

  it('computes pendingQuestions as total minus completed', () => {
    expect(content).toContain('totalQuestions.value - completedQuestions.value')
  })
})

describe('MarkingSelectPage subject progress', () => {
  it('calculates progress percentage per subject', () => {
    expect(content).toContain('function subjectProgress(subj)')
    expect(content).toContain("const qs = subj.questions || []")
    expect(content).toContain('Math.round(graded / total * 100)')
  })

  it('returns 0 when total is 0', () => {
    const fnBlock = content.slice(
      content.indexOf('function subjectProgress'),
      content.indexOf('function rowClassName')
    )
    expect(fnBlock).toContain('total > 0 ?')
    expect(fnBlock).toContain(': 0')
  })
})

describe('MarkingSelectPage row status styling', () => {
  it('assigns row class based on question status', () => {
    expect(content).toContain('function rowClassName(row)')
    expect(content).toContain("return 'row--completed'")
    expect(content).toContain("return 'row--in-progress'")
    expect(content).toContain("return 'row--pending'")
  })

  it('has CSS for status color bands', () => {
    expect(content).toContain('.row--completed')
    expect(content).toContain('.row--in-progress')
    expect(content).toContain('.row--pending')
  })
})

describe('MarkingSelectPage table columns', () => {
  it('defines four columns', () => {
    expect(content).toContain("title: '题号'")
    expect(content).toContain("title: '满分'")
    expect(content).toContain("title: '进度'")
    expect(content).toContain("title: '操作'")
  })

  it('action column navigates to marking grade page', () => {
    expect(content).toContain("router.push(`/marking/grade/${row.id}`)")
  })

  it('action button shows different text based on completion', () => {
    expect(content).toContain("done ? '查看' : '开始阅卷'")
  })
})

describe('MarkingSelectPage API calls', () => {
  it('loads exams on mount', () => {
    expect(content).toContain('onMounted(loadExams)')
  })

  it('fetches exams list from /exams endpoint', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function loadSubjects')
    )
    expect(fnBlock).toContain("client.get('/exams')")
  })

  it('auto-selects first exam and loads subjects', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function loadSubjects')
    )
    expect(fnBlock).toContain('selectedExamId.value = data[0].id')
    expect(fnBlock).toContain('await loadSubjects(data[0].id)')
  })

  it('uses listSubjects API for subject loading', () => {
    expect(content).toContain("import { listSubjects } from '../api/marking'")
    expect(content).toContain('listSubjects(examId)')
  })
})

describe('MarkingSelectPage error handling', () => {
  it('wraps loadExams in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadExams'),
      content.indexOf('async function loadSubjects')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps loadSubjects in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSubjects'),
      content.indexOf('onMounted(loadExams)')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('manages loading state in loadSubjects', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadSubjects'),
      content.indexOf('onMounted(loadExams)')
    )
    expect(fnBlock).toContain('loading.value = true')
    expect(fnBlock).toContain('loading.value = false')
  })
})
