/**
 * GradingResultsPage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (header, progress, stats, charts, table, modal)
 *  3. Task status mapping (pending/processing/completed/failed)
 *  4. Review status mapping (pending/approved/overridden)
 *  5. Statistics computations (gradedCount, avgScore, avgConfidence, pendingReviewCount)
 *  6. Chart configurations (scoreDistOption, confidenceDistOption)
 *  7. Filter and sort options
 *  8. API calls (getTask, listResults)
 *  9. Error handling
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../GradingResultsPage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('GradingResultsPage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../GradingResultsPage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('GradingResultsPage template structure', () => {
  it('contains back button to grading tasks', () => {
    expect(content).toContain("@click=\"$router.push('/grading/tasks')\"")
    expect(content).toContain('返回阅卷任务')
  })

  it('contains page title', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('批改结果')
  })

  it('contains progress bar section', () => {
    expect(content).toContain('批改进度')
    expect(content).toContain(':percentage="progressPercent"')
  })

  it('contains four summary stat cards', () => {
    expect(content).toContain('已批改 / 总数')
    expect(content).toContain('平均分')
    expect(content).toContain('平均置信度')
    expect(content).toContain('待复核数')
  })

  it('contains score distribution chart', () => {
    expect(content).toContain('分数分布')
    expect(content).toContain(':option="scoreDistOption"')
  })

  it('contains confidence distribution chart', () => {
    expect(content).toContain('置信度分布')
    expect(content).toContain(':option="confidenceDistOption"')
  })

  it('contains detail modal', () => {
    expect(content).toContain('v-model:show="showDetail"')
    expect(content).toContain('批改详情')
  })
})

describe('GradingResultsPage task status mapping', () => {
  it('maps all four task statuses to Chinese labels', () => {
    expect(content).toContain("pending: { label: '等待中', type: 'default' }")
    expect(content).toContain("processing: { label: '处理中', type: 'warning' }")
    expect(content).toContain("completed: { label: '已完成', type: 'success' }")
    expect(content).toContain("failed: { label: '失败', type: 'error' }")
  })

  it('has taskStatusLabel and taskStatusType helpers', () => {
    expect(content).toContain('const taskStatusLabel = (s) => taskStatusMap[s]?.label || s')
    expect(content).toContain('const taskStatusType = (s) => taskStatusMap[s]?.type ||')
  })
})

describe('GradingResultsPage review status mapping', () => {
  it('maps all three review statuses to Chinese labels', () => {
    expect(content).toContain("pending: { label: '待复核', type: 'warning' }")
    expect(content).toContain("approved: { label: '已通过', type: 'success' }")
    expect(content).toContain("overridden: { label: '已改分', type: 'info' }")
  })

  it('has reviewStatusLabel and reviewStatusType helpers', () => {
    expect(content).toContain('const reviewStatusLabel = (s) => reviewStatusMap[s]?.label || s')
    expect(content).toContain('const reviewStatusType = (s) => reviewStatusMap[s]?.type ||')
  })
})

describe('GradingResultsPage statistics computations', () => {
  it('computes progressPercent from task completed/total', () => {
    expect(content).toContain('Math.round((task.value.completed / task.value.total) * 100)')
  })

  it('computes gradedCount as results length', () => {
    expect(content).toContain('const gradedCount = computed(() => results.value.length)')
  })

  it('computes avgScore with toFixed(1)', () => {
    const avgBlock = content.slice(
      content.indexOf('const avgScore = computed'),
      content.indexOf('const avgConfidence = computed')
    )
    expect(avgBlock).toContain("(total / results.value.length).toFixed(1)")
  })

  it('computes avgConfidence as percentage', () => {
    const confBlock = content.slice(
      content.indexOf('const avgConfidence = computed'),
      content.indexOf('const pendingReviewCount = computed')
    )
    expect(confBlock).toContain("((total / results.value.length) * 100).toFixed(0)")
  })

  it('computes pendingReviewCount by filtering pending review_status', () => {
    expect(content).toContain("r.review_status === 'pending'")
  })
})

describe('GradingResultsPage score distribution chart', () => {
  it('defines 5 score buckets', () => {
    expect(content).toContain("const labels = ['0-20%', '20-40%', '40-60%', '60-80%', '80-100%']")
  })

  it('categorizes results into buckets by percentage', () => {
    expect(content).toContain('if (pct < 20) buckets[0]++')
    expect(content).toContain('else if (pct < 40) buckets[1]++')
    expect(content).toContain('else if (pct < 60) buckets[2]++')
    expect(content).toContain('else if (pct < 80) buckets[3]++')
    expect(content).toContain('else buckets[4]++')
  })

  it('uses bar chart type', () => {
    const chartBlock = content.slice(
      content.indexOf('const scoreDistOption = computed'),
      content.indexOf('const confidenceDistOption = computed')
    )
    expect(chartBlock).toContain("type: 'bar'")
  })
})

describe('GradingResultsPage confidence distribution chart', () => {
  it('categorizes into high/mid/low confidence', () => {
    const chartBlock = content.slice(
      content.indexOf('const confidenceDistOption = computed'),
      content.indexOf('function questionLabel')
    )
    expect(chartBlock).toContain('if (pct >= 80) high++')
    expect(chartBlock).toContain('else if (pct >= 50) mid++')
    expect(chartBlock).toContain('else low++')
  })

  it('uses pie chart with donut style', () => {
    const chartBlock = content.slice(
      content.indexOf('const confidenceDistOption = computed'),
      content.indexOf('function questionLabel')
    )
    expect(chartBlock).toContain("type: 'pie'")
    expect(chartBlock).toContain("radius: ['40%', '70%']")
  })

  it('labels three confidence tiers', () => {
    expect(content).toContain("name: '高 (>=80%)'")
    expect(content).toContain("name: '中 (50-80%)'")
    expect(content).toContain("name: '低 (<50%)'")
  })
})

describe('GradingResultsPage filter and sort', () => {
  it('defines four filter options', () => {
    expect(content).toContain("{ label: '全部', value: 'all' }")
    expect(content).toContain("{ label: '待复核', value: 'pending' }")
    expect(content).toContain("{ label: '已通过', value: 'approved' }")
    expect(content).toContain("{ label: '已改分', value: 'overridden' }")
  })

  it('defines six sort options', () => {
    expect(content).toContain("{ label: '置信度 升序', value: 'confidence_asc' }")
    expect(content).toContain("{ label: '置信度 降序', value: 'confidence_desc' }")
    expect(content).toContain("{ label: '分数 升序', value: 'score_asc' }")
    expect(content).toContain("{ label: '分数 降序', value: 'score_desc' }")
    expect(content).toContain("{ label: '得分率 升序', value: 'rate_asc' }")
    expect(content).toContain("{ label: '得分率 降序', value: 'rate_desc' }")
  })

  it('sorts by confidence, score, or rate', () => {
    const sortBlock = content.slice(
      content.indexOf('const sortedResults = computed'),
      content.indexOf('const columns = [')
    )
    expect(sortBlock).toContain("if (field === 'confidence')")
    expect(sortBlock).toContain("if (field === 'score')")
    expect(sortBlock).toContain("if (field === 'rate')")
  })
})

describe('GradingResultsPage helper functions', () => {
  it('questionLabel handles name, index, and UUID fallback', () => {
    expect(content).toContain('function questionLabel(row)')
    expect(content).toContain('if (row.question_name) return row.question_name')
    expect(content).toContain('row.question_index + 1')
  })

  it('scorePercent calculates percentage from score/max_score', () => {
    expect(content).toContain('function scorePercent(row)')
    expect(content).toContain('Math.round((row.score / row.max_score) * 100)')
  })

  it('scoreColor returns color based on percentage thresholds', () => {
    expect(content).toContain('function scoreColor(row)')
    expect(content).toContain("if (pct < 60) return '#dc3545'")
    expect(content).toContain("if (pct < 80) return '#d97706'")
    expect(content).toContain("return '#16a34a'")
  })

  it('confidenceType returns tag type based on confidence level', () => {
    expect(content).toContain('function confidenceType(c)')
    expect(content).toContain("if (pct >= 80) return 'success'")
    expect(content).toContain("if (pct >= 50) return 'warning'")
    expect(content).toContain("return 'error'")
  })
})

describe('GradingResultsPage API calls', () => {
  it('imports getTask and listResults from grading API', () => {
    expect(content).toContain("import { getTask, listResults } from '../api/grading'")
  })

  it('loads task and results in parallel on mount', () => {
    expect(content).toContain('Promise.all([')
    expect(content).toContain('getTask(taskId)')
    expect(content).toContain('listResults({ task_id: taskId })')
  })

  it('extracts taskId from route params', () => {
    expect(content).toContain('const taskId = route.params.id')
  })
})

describe('GradingResultsPage error handling', () => {
  it('wraps onMounted data fetch in try-catch', () => {
    const mountBlock = content.slice(
      content.indexOf('onMounted(async'),
      content.length
    )
    expect(mountBlock).toContain('try {')
    expect(mountBlock).toContain('} catch')
  })

  it('sets loading to false after fetch completes', () => {
    expect(content).toContain('loading.value = false')
  })
})

describe('GradingResultsPage detail modal', () => {
  it('shows question label, student ID, AI score in descriptions', () => {
    expect(content).toContain('题目序号')
    expect(content).toContain('学生ID')
    expect(content).toContain('AI 评分')
  })

  it('shows confidence and review status tags', () => {
    expect(content).toContain('置信度')
    expect(content).toContain('复核状态')
  })

  it('shows AI feedback section', () => {
    expect(content).toContain('AI 反馈')
    expect(content).toContain('selectedResult.feedback')
  })
})
