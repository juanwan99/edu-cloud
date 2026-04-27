/**
 * ParentScores.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains score cards, exam list, error stats
 *  3. API calls for exams, scores, error book
 *  4. Expand/collapse logic for exam details
 *  5. Error handling
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../ParentScores.vue')
const content = readFileSync(filePath, 'utf-8')

describe('ParentScores smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../ParentScores.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('ParentScores template sections', () => {
  it('has page title', () => {
    expect(content).toContain('<n-h3>成绩查询</n-h3>')
  })

  it('contains latest score summary cards', () => {
    expect(content).toContain('v-if="latestExam"')
    expect(content).toContain('class="score-summary"')
    expect(content).toContain("latestExam.total_score ?? '-'")
    expect(content).toContain('最近总分')
    expect(content).toContain('latestExam.max_score')
  })

  it('contains class and grade rank cards', () => {
    expect(content).toContain("latestRank?.class_rank ?? '-'")
    expect(content).toContain('班级排名')
    expect(content).toContain("latestRank?.class_size ?? '-'")
    expect(content).toContain("latestRank?.grade_rank ?? '-'")
    expect(content).toContain('年级排名')
    expect(content).toContain("latestRank?.grade_size ?? '-'")
  })

  it('contains exam list with clickable items', () => {
    expect(content).toContain('v-for="exam in exams"')
    expect(content).toContain('@click="toggleExam(exam.exam_id)"')
    expect(content).toContain('class="exam-item"')
    expect(content).toContain('{{ exam.exam_name }}')
    expect(content).toContain('{{ exam.total_score }}/{{ exam.max_score }}')
  })

  it('contains exam subjects detail on expand', () => {
    expect(content).toContain('v-if="expandedExam === exam.exam_id && examScores[exam.exam_id]"')
    expect(content).toContain('class="exam-subjects"')
    expect(content).toContain('v-for="s in examScores[exam.exam_id]"')
    expect(content).toContain('{{ s.subject_code }}')
    expect(content).toContain('{{ s.total_score }}/{{ s.max_score }}')
  })

  it('contains exam status tag', () => {
    expect(content).toContain("exam.exam_status === 'completed' ? 'success' : 'default'")
    expect(content).toContain("exam.exam_status === 'completed' ? '已完成' : exam.exam_status")
  })

  it('contains empty state for no exams', () => {
    expect(content).toContain('description="暂无考试成绩"')
  })

  it('contains error book stats section', () => {
    expect(content).toContain('v-if="errorStats"')
    expect(content).toContain('错题概况')
    expect(content).toContain('{{ errorStats.unmastered }}')
    expect(content).toContain('未掌握')
    expect(content).toContain('{{ errorStats.practicing }}')
    expect(content).toContain('练习中')
    expect(content).toContain('{{ errorStats.mastered }}')
    expect(content).toContain('已掌握')
  })

  it('shows subject class and grade rank', () => {
    expect(content).toContain('v-if="s.class_rank"')
    expect(content).toContain('v-if="s.grade_rank"')
  })
})

describe('ParentScores API calls', () => {
  it('imports API functions from conduct', () => {
    expect(content).toContain("import { getChildExams, getChildScores, getChildErrorBook } from '../../api/conduct'")
  })

  it('fetches all data in parallel with Promise.all', () => {
    expect(content).toContain('const [examRes, scoreRes, errorRes] = await Promise.all([')
    expect(content).toContain('getChildExams(child.student_id)')
    expect(content).toContain('getChildScores(child.student_id, { limit: 50 })')
    expect(content).toContain('getChildErrorBook(child.student_id, { limit: 1 })')
  })

  it('injects currentChild from parent', () => {
    expect(content).toContain("const currentChild = inject('currentChild')")
  })
})

describe('ParentScores exam expand/collapse', () => {
  it('toggles expanded exam on click', () => {
    expect(content).toContain('async function toggleExam(examId)')
    expect(content).toContain('expandedExam.value === examId')
    expect(content).toContain('expandedExam.value = null')
    expect(content).toContain('expandedExam.value = examId')
  })

  it('filters subject scores excluding _total', () => {
    expect(content).toContain("s.exam_id === examId && s.subject_code !== '_total'")
  })
})

describe('ParentScores computed properties', () => {
  it('computes latestExam as first in list', () => {
    expect(content).toContain('const latestExam = computed(() => exams.value[0] || null)')
  })

  it('computes latestRank from scores data', () => {
    expect(content).toContain("s.exam_id === latestExam.value.exam_id && s.subject_code === '_total'")
  })

  it('formats date in Chinese locale', () => {
    expect(content).toContain("new Date(d).toLocaleDateString('zh-CN',")
    expect(content).toContain("year: 'numeric', month: 'short', day: 'numeric'")
  })
})

describe('ParentScores error handling', () => {
  it('wraps loadData in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadData'),
      content.indexOf('watch(currentChild')
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch {')
    expect(fnBlock).toContain('} finally {')
  })

  it('falls back to empty state on error', () => {
    expect(content).toContain('exams.value = []')
    expect(content).toContain('scores.value = []')
    expect(content).toContain('errorStats.value = null')
  })

  it('watches currentChild and calls loadData on mount', () => {
    expect(content).toContain('watch(currentChild, loadData, { deep: true })')
    expect(content).toContain('onMounted(loadData)')
  })
})
