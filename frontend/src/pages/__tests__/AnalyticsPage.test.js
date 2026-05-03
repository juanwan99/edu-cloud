/**
 * AnalyticsPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template sections: stats grid, diagnosis card, tabs (distribution/questions/rankings/critical/wrong)
 *  3. API calls use analytics.js functions
 *  4. ECharts configuration (bar chart, distribution)
 *  5. Data processing (columns, subject filters, export)
 *  6. Error handling (try-catch, Promise.allSettled)
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../AnalyticsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('AnalyticsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../AnalyticsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('AnalyticsPage template sections', () => {
  it('contains page header with exam name subtitle', () => {
    expect(content).toContain('class="page-header"')
    expect(content).toContain('class="page-title"')
    expect(content).toContain('{{ examName }}')
  })

  it('wraps content in n-spin with loading state', () => {
    expect(content).toContain('<n-spin :show="loading">')
  })

  it('contains stats grid for summary data', () => {
    expect(content).toContain('class="stats-grid"')
    expect(content).toContain('summary.total_students')
    expect(content).toContain('summary.subjects')
    expect(content).toContain('subj.avg_score')
    expect(content).toContain('subj.highest')
    expect(content).toContain('subj.lowest')
  })

  it('contains diagnosis card section', () => {
    expect(content).toContain('v-if="diagnosis"')
    expect(content).toContain('diagnosis.summary_text')
    expect(content).toContain('diagnosis.suggestions')
  })
})

describe('AnalyticsPage tabs', () => {
  it('has distribution tab', () => {
    expect(content).toContain('name="distribution"')
    expect(content).toContain('tab="成绩分布"')
  })

  it('has questions tab', () => {
    expect(content).toContain('name="questions"')
    expect(content).toContain('tab="题目分析"')
  })

  it('has rankings tab', () => {
    expect(content).toContain('name="rankings"')
    expect(content).toContain('tab="学生排名"')
  })

  it('has critical students tab', () => {
    expect(content).toContain('name="critical"')
    expect(content).toContain('tab="临界生"')
  })

  it('has common wrong questions tab', () => {
    expect(content).toContain('name="wrong"')
    expect(content).toContain('tab="常错题"')
  })
})

describe('AnalyticsPage API imports', () => {
  it('imports analytics functions from api/analytics', () => {
    expect(content).toContain("from '../api/analytics'")
    expect(content).toContain('getExamSummary')
    expect(content).toContain('getDistribution')
    expect(content).toContain('getSubjectQuestions')
    expect(content).toContain('exportGradeReport')
    expect(content).toContain('downloadBlob')
    expect(content).toContain('getExamDiagnosis')
    expect(content).toContain('getStudentRankings')
    expect(content).toContain('getCriticalStudents')
    expect(content).toContain('getCommonWrongQuestions')
  })

  it('imports getExam from api/exams', () => {
    expect(content).toContain("import { getExam } from '../api/exams'")
  })
})

describe('AnalyticsPage ECharts configuration', () => {
  it('registers ECharts components', () => {
    expect(content).toContain("import VChart from 'vue-echarts'")
    expect(content).toContain('CanvasRenderer')
    expect(content).toContain('BarChart')
    expect(content).toContain('GridComponent')
    expect(content).toContain('TooltipComponent')
    expect(content).toContain('LegendComponent')
  })

  it('builds distribution chart as bar chart', () => {
    const chartBlock = content.slice(
      content.indexOf('distributionChartOption'),
      content.indexOf('const questionColumns'),
    )
    expect(chartBlock).toContain("type: 'bar'")
    expect(chartBlock).toContain("type: 'category'")
    expect(chartBlock).toContain("type: 'value'")
  })

  it('uses shared palette color for distribution bars', () => {
    expect(content).toContain('color: CHART_PALETTE[0]')
  })

  it('applies rounded corners to bars', () => {
    expect(content).toContain('borderRadius: [6, 6, 0, 0]')
  })

  it('configures tooltip with axis trigger', () => {
    expect(content).toContain("tooltip: { ...CHART_DEFAULTS.tooltip, trigger: 'axis' }")
  })

  it('maps intervals to xAxis data and series data', () => {
    expect(content).toContain('intervals.map((i) => i.range)')
    expect(content).toContain('intervals.map((i) => i.count)')
  })
})

describe('AnalyticsPage question columns', () => {
  it('defines question table columns', () => {
    expect(content).toContain("title: '题目'")
    expect(content).toContain("title: '类型'")
    expect(content).toContain("title: '满分'")
    expect(content).toContain("title: '平均分'")
    expect(content).toContain("title: '得分率'")
    expect(content).toContain("title: '批改数'")
  })

  it('renders question type as subjective/objective tag', () => {
    expect(content).toContain("row.question_type === 'subjective'")
  })

  it('renders score rate with NProgress component', () => {
    expect(content).toContain('NProgress')
    expect(content).toContain("type: 'line'")
    expect(content).toContain('indicatorPlacement')
  })

  it('uses token color coding for score rate thresholds', () => {
    expect(content).toContain("pct < 60 ? cDanger")
    expect(content).toContain("pct < 80 ? cWarning")
    expect(content).toContain("cSuccess")
  })
})

describe('AnalyticsPage ranking columns', () => {
  it('defines rank table columns', () => {
    expect(content).toContain("title: '年排'")
    expect(content).toContain("title: '姓名'")
    expect(content).toContain("title: '班级'")
    expect(content).toContain("title: '总分'")
    expect(content).toContain("title: '进退步'")
  })

  it('renders delta with arrow indicators', () => {
    expect(content).toContain("const arrow = v > 0 ? '↑' : v < 0 ? '↓' : '-'")
  })
})

describe('AnalyticsPage critical students', () => {
  it('shows near-pass and near-excellent sections', () => {
    expect(content).toContain('criticalData.near_pass')
    expect(content).toContain('criticalData.near_excellent')
  })

  it('defines critical columns with gap display', () => {
    expect(content).toContain("title: '差距'")
    expect(content).toContain('`${row.gap} 分`')
  })
})

describe('AnalyticsPage wrong questions columns', () => {
  it('defines wrong questions table columns', () => {
    expect(content).toContain("key: 'question_name'")
    expect(content).toContain("key: 'subject_name'")
    expect(content).toContain("key: 'wrong_count'")
    expect(content).toContain("key: 'avg_score_rate'")
  })
})

describe('AnalyticsPage subject filters', () => {
  it('computes subjectFilterOptions with all-subject default', () => {
    expect(content).toContain("label: '全科', value: null")
  })

  it('computes subjectSelectOptions from summary subjects', () => {
    expect(content).toContain('subjectSelectOptions')
    expect(content).toContain("summary.value?.subjects || []")
  })
})

describe('AnalyticsPage export functionality', () => {
  it('has PDF and Excel export buttons', () => {
    expect(content).toContain("handleExport('pdf')")
    expect(content).toContain("handleExport('xlsx')")
  })

  it('calls exportGradeReport and downloadBlob on export', () => {
    const exportBlock = content.slice(
      content.indexOf('async function handleExport'),
      content.indexOf('onMounted('),
    )
    expect(exportBlock).toContain('exportGradeReport(examId, questionSubjectId.value, format)')
    expect(exportBlock).toContain('downloadBlob(resp')
  })

  it('warns when no subject selected for export', () => {
    expect(content).toContain("message.warning('请先选择科目')")
  })

  it('shows error message on export failure', () => {
    expect(content).toContain("e.response?.data?.detail || '导出失败'")
  })
})

describe('AnalyticsPage data fetching on mount', () => {
  it('fetches exam and summary in parallel with Promise.all', () => {
    expect(content).toContain('Promise.all([')
    expect(content).toContain('getExam(examId)')
    expect(content).toContain('getExamSummary(examId)')
  })

  it('fetches secondary data with Promise.allSettled', () => {
    expect(content).toContain('Promise.allSettled([')
    expect(content).toContain('getExamDiagnosis(examId)')
    expect(content).toContain('getStudentRankings(examId)')
    expect(content).toContain('getCriticalStudents(examId)')
    expect(content).toContain('getCommonWrongQuestions(examId)')
  })

  it('guards allSettled results with status check', () => {
    expect(content).toContain("diagRes.status === 'fulfilled'")
    expect(content).toContain("rankRes.status === 'fulfilled'")
    expect(content).toContain("critRes.status === 'fulfilled'")
    expect(content).toContain("wrongRes.status === 'fulfilled'")
  })
})

describe('AnalyticsPage error handling', () => {
  it('wraps onMounted in try-catch', () => {
    const mountBlock = content.slice(
      content.indexOf('onMounted('),
      content.lastIndexOf('</script>'),
    )
    expect(mountBlock).toContain('try {')
    expect(mountBlock).toContain('} catch')
  })

  it('wraps loadDistribution in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadDistribution'),
      content.indexOf('async function loadQuestionAnalysis'),
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps loadQuestionAnalysis in try-catch', () => {
    const fnBlock = content.slice(
      content.indexOf('async function loadQuestionAnalysis'),
      content.indexOf('async function handleExport'),
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
  })

  it('wraps handleExport in try-catch-finally', () => {
    const fnBlock = content.slice(
      content.indexOf('async function handleExport'),
      content.indexOf('onMounted('),
    )
    expect(fnBlock).toContain('try {')
    expect(fnBlock).toContain('} catch')
    expect(fnBlock).toContain('} finally')
    expect(fnBlock).toContain('exporting.value = false')
  })

  it('sets loading to false after mount completes', () => {
    expect(content).toContain('loading.value = false')
  })
})
