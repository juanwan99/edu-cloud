/**
 * ParentScores.vue source text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Segmented control with exam/subject views
 *  3. Latest exam card with score summary, class/grade rank
 *  4. Subject scores with progress bars and warning indicator
 *  5. Historical exams with NCollapse
 *  6. Subject trend chart (vue-echarts)
 *  7. Error book stats (3 stat cards)
 *  8. PullRefresh + ParentSkeleton + ParentEmpty + NumberRoll integration
 *  9. API calls with Promise.allSettled
 * 10. Props-based currentChild (not inject)
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

describe('ParentScores segmented control', () => {
  it('has NSegmented with exam/subject options', () => {
    expect(content).toContain('n-segmented v-model:value="segment"')
    expect(content).toContain("{ label: '考试', value: 'exam' }")
    expect(content).toContain("{ label: '学科', value: 'subject' }")
  })

  it('defaults segment to exam', () => {
    expect(content).toContain("const segment = ref('exam')")
  })

  it('conditionally renders exam view', () => {
    expect(content).toContain("v-if=\"segment === 'exam'\"")
  })

  it('conditionally renders subject view', () => {
    expect(content).toContain("v-if=\"segment === 'subject'\"")
  })
})

describe('ParentScores exam view - latest exam card', () => {
  it('shows latest exam with name and date', () => {
    expect(content).toContain('v-if="latestExam"')
    expect(content).toContain("latestExam.exam_name || '最近考试'")
    expect(content).toContain("latestExam.exam_date || ''")
  })

  it('has total score with NumberRoll', () => {
    expect(content).toContain('<NumberRoll :value="latestExam.total_score"')
    expect(content).toContain('总分')
  })

  it('has class rank block', () => {
    expect(content).toContain('v-if="latestExam.class_rank"')
    expect(content).toContain('{{ latestExam.class_rank }}')
    expect(content).toContain("latestExam.class_total || '?'")
    expect(content).toContain('班名次')
  })

  it('has grade rank block', () => {
    expect(content).toContain('v-if="latestExam.grade_rank"')
    expect(content).toContain('{{ latestExam.grade_rank }}')
    expect(content).toContain("latestExam.grade_total || '?'")
    expect(content).toContain('年名次')
  })
})

describe('ParentScores exam view - subject scores', () => {
  it('renders subject list with progress bars', () => {
    expect(content).toContain('v-if="latestSubjects.length"')
    expect(content).toContain('各科成绩')
    expect(content).toContain('v-for="s in latestSubjects"')
    expect(content).toContain('class="subject-row__bar"')
    expect(content).toContain('barWidth(s.score, s.max_score)')
  })

  it('shows class average comparison line', () => {
    expect(content).toContain('v-if="s.class_avg"')
    expect(content).toContain('class="subject-row__avg"')
    expect(content).toContain('barWidth(s.class_avg, s.max_score)')
  })

  it('shows warning icon for below-average scores', () => {
    expect(content).toContain('AlertTriangle')
    expect(content).toContain('v-if="s.class_avg && s.score < s.class_avg"')
    expect(content).toContain('class="subject-row__warn"')
  })
})

describe('ParentScores exam view - historical exams', () => {
  it('uses NCollapse for historical exams', () => {
    expect(content).toContain('v-if="exams.length > 1"')
    expect(content).toContain('历次考试')
    expect(content).toContain('n-collapse>')
    expect(content).toContain('n-collapse-item')
    expect(content).toContain('v-for="exam in exams.slice(1)"')
  })

  it('shows exam total in header-extra', () => {
    expect(content).toContain('#header-extra')
    expect(content).toContain('class="exam-total"')
    expect(content).toContain("exam.total_score ?? '-'")
  })

  it('shows subject breakdown when expanded', () => {
    expect(content).toContain('exam.subjects?.length')
    expect(content).toContain('class="exam-subject-item"')
    expect(content).toContain('暂无科目明细')
  })

  it('shows empty state when no exams', () => {
    expect(content).toContain('!exams.length && hasLoaded')
    expect(content).toContain('还没有考试记录')
  })
})

describe('ParentScores subject view', () => {
  it('has subject selector segmented control', () => {
    expect(content).toContain('v-model:value="selectedSubject"')
    expect(content).toContain('class="subject-selector"')
    expect(content).toContain('学科趋势')
  })

  it('renders trend chart with vue-echarts', () => {
    expect(content).toContain('v-chart')
    expect(content).toContain(':option="trendChartOption"')
    expect(content).toContain('subjectTrend.length >= 2')
    expect(content).toContain('数据不足，至少需要 2 次考试')
  })

  it('computes trend chart option with brand color', () => {
    expect(content).toContain("lineStyle: { color: '#644CF0'")
    expect(content).toContain("itemStyle: { color: '#644CF0' }")
  })
})

describe('ParentScores error book stats', () => {
  it('contains error stats section in subject view', () => {
    expect(content).toContain('v-if="errorStats"')
    expect(content).toContain('错题概况')
  })

  it('has three stat cards with semantic colors', () => {
    expect(content).toContain('error-stat--red')
    expect(content).toContain('error-stat--yellow')
    expect(content).toContain('error-stat--green')
    expect(content).toContain('errorStats.unmastered || 0')
    expect(content).toContain('未掌握')
    expect(content).toContain('errorStats.practicing || 0')
    expect(content).toContain('练习中')
    expect(content).toContain('errorStats.mastered || 0')
    expect(content).toContain('已掌握')
  })
})

describe('ParentScores shared components', () => {
  it('uses PullRefresh wrapper', () => {
    expect(content).toContain("import PullRefresh from '../../components/parent/PullRefresh.vue'")
    expect(content).toContain('<PullRefresh')
    expect(content).toContain(':loading="refreshing"')
    expect(content).toContain('@refresh="loadData"')
  })

  it('uses ParentSkeleton for loading state', () => {
    expect(content).toContain("import ParentSkeleton from '../../components/parent/ParentSkeleton.vue'")
    expect(content).toContain('<ParentSkeleton')
    expect(content).toContain('v-if="loading && !hasLoaded"')
  })

  it('uses ParentEmpty for empty states', () => {
    expect(content).toContain("import ParentEmpty from '../../components/parent/ParentEmpty.vue'")
    expect(content).toContain('<ParentEmpty')
  })

  it('uses NumberRoll for score display', () => {
    expect(content).toContain("import NumberRoll from '../../components/parent/NumberRoll.vue'")
    expect(content).toContain('<NumberRoll')
  })
})

describe('ParentScores API calls', () => {
  it('imports API functions from conduct', () => {
    expect(content).toContain("import { getChildExams, getChildScores, getChildErrorBook } from '../../api/conduct'")
  })

  it('uses Promise.allSettled for resilient data loading', () => {
    expect(content).toContain('Promise.allSettled')
    expect(content).toContain('getChildExams(child.student_id)')
    expect(content).toContain('getChildErrorBook(child.student_id, {})')
  })

  it('checks settled status before assigning data', () => {
    expect(content).toContain("examsRes.status === 'fulfilled'")
    expect(content).toContain("errorRes.status === 'fulfilled'")
  })
})

describe('ParentScores props and reactivity', () => {
  it('receives currentChild as prop (not inject)', () => {
    expect(content).toContain('defineProps')
    expect(content).toContain('currentChild: { type: Object, default: null }')
    expect(content).not.toContain("inject('currentChild')")
  })

  it('watches currentChild prop and resets state', () => {
    expect(content).toContain('watch(() => props.currentChild')
    expect(content).toContain('exams.value = []')
    expect(content).toContain('errorStats.value = null')
    expect(content).toContain("selectedSubject.value = ''")
    expect(content).toContain('hasLoaded.value = false')
  })

  it('computes latestExam as first in list', () => {
    expect(content).toContain('const latestExam = computed(() => exams.value[0] || null)')
  })

  it('computes latestSubjects from latestExam', () => {
    expect(content).toContain("latestExam.value?.subjects || []")
  })
})

describe('ParentScores design tokens', () => {
  it('uses p-card pattern', () => {
    expect(content).toContain('class="p-card"')
    expect(content).toContain('var(--p-card-bg)')
    expect(content).toContain('var(--p-card-radius)')
    expect(content).toContain('var(--p-card-padding)')
  })

  it('uses p-* spacing and typography tokens', () => {
    expect(content).toContain('var(--p-space-')
    expect(content).toContain('var(--p-fs-')
    expect(content).toContain('var(--p-text-1)')
    expect(content).toContain('var(--p-text-3)')
  })

  it('uses semantic color tokens for error stats', () => {
    expect(content).toContain('var(--p-color-error-surface)')
    expect(content).toContain('var(--p-color-warning-surface)')
    expect(content).toContain('var(--p-color-success-surface)')
  })
})
