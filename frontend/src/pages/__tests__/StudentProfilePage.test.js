/**
 * StudentProfilePage source-text tests.
 *
 * Validates:
 *  1. Component can be imported (smoke)
 *  2. Template contains key sections (header, stats grid, tabs)
 *  3. Tab definitions (trend, ranking, knowledge, errors, diagnosis)
 *  4. Chart configurations (trend, ranking, radar, error pie)
 *  5. API calls (getStudentTrend, getStudentKnowledge, etc.)
 *  6. Statistics display (total_score, grade_rank, class_rank)
 *  7. Knowledge table columns
 *  8. Error handling and loading state
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

const filePath = resolve(__dirname, '../StudentProfilePage.vue')
const content = readFileSync(filePath, 'utf-8')

describe('StudentProfilePage smoke', () => {
  it('can be imported', async () => {
    const mod = await import('../StudentProfilePage.vue')
    expect(mod.default).toBeTruthy()
    expect(typeof mod.default).toMatch(/object|function/)
  }, 30000)
})

describe('StudentProfilePage template structure', () => {
  it('contains page header with title', () => {
    expect(content).toContain('class="page-title"')
    expect(content).toContain('学生画像')
  })

  it('contains link to error book', () => {
    expect(content).toContain("@click=\"$router.push(`/error-book?studentId=${studentId}`)\"")
    expect(content).toContain('查看错题本')
  })

  it('shows error result when loading fails', () => {
    expect(content).toContain('v-if="loadError"')
    expect(content).toContain(':title="loadError"')
  })

  it('contains stats grid with four overview cards', () => {
    expect(content).toContain('class="stats-grid"')
    expect(content).toContain('class="stat-card"')
    expect(content).toContain('最近总分')
    expect(content).toContain('年级排名')
    expect(content).toContain('班级排名')
    expect(content).toContain('知识点掌握')
  })

  it('uses macaron theme colors for stat cards', () => {
    expect(content).toContain('var(--macaron-mint-light)')
    expect(content).toContain('var(--macaron-purple-light)')
    expect(content).toContain('var(--macaron-yellow-light)')
    expect(content).toContain('var(--macaron-coral-light)')
  })
})

describe('StudentProfilePage tabs', () => {
  it('has five tab panes', () => {
    expect(content).toContain('name="trend"')
    expect(content).toContain('name="ranking"')
    expect(content).toContain('name="knowledge"')
    expect(content).toContain('name="errors"')
    expect(content).toContain('name="diagnosis"')
  })

  it('labels tabs in Chinese', () => {
    expect(content).toContain('tab="成绩趋势"')
    expect(content).toContain('tab="排名变化"')
    expect(content).toContain('tab="知识点掌握"')
    expect(content).toContain('tab="错误分析"')
    expect(content).toContain('tab="AI 诊断"')
  })

  it('shows empty states when no data', () => {
    expect(content).toContain('暂无多次考试数据')
    expect(content).toContain('暂无排名数据')
    expect(content).toContain('暂无知识点数据')
    expect(content).toContain('暂无错误分析数据')
    expect(content).toContain('暂无 AI 诊断数据')
  })
})

describe('StudentProfilePage trend chart', () => {
  it('requires at least 2 snapshots for trend chart', () => {
    expect(content).toContain('if (snapshots.value.length < 2) return null')
  })

  it('groups snapshots by subject_code', () => {
    expect(content).toContain("const key = s.subject_code || '总分'")
  })

  it('uses line chart with smooth curves', () => {
    const trendBlock = content.slice(
      content.indexOf('const trendChartOption = computed'),
      content.indexOf('const rankingChartOption = computed')
    )
    expect(trendBlock).toContain("type: 'line'")
    expect(trendBlock).toContain('smooth: true')
  })

  it('reverses data for chronological display', () => {
    expect(content).toContain('.reverse()')
  })
})

describe('StudentProfilePage ranking chart', () => {
  it('filters snapshots with grade_rank', () => {
    expect(content).toContain('const data = snapshots.value.filter(s => s.grade_rank != null)')
  })

  it('requires at least 2 data points', () => {
    const rankBlock = content.slice(
      content.indexOf('const rankingChartOption = computed'),
      content.indexOf('const radarChartOption = computed')
    )
    expect(rankBlock).toContain('if (data.length < 2) return null')
  })

  it('uses inverted Y axis for ranking', () => {
    expect(content).toContain('inverse: true')
    expect(content).toContain('min: 1')
  })

  it('shows both grade and class ranking series', () => {
    expect(content).toContain("name: '年级排名'")
    expect(content).toContain("name: '班级排名'")
  })
})

describe('StudentProfilePage radar chart', () => {
  it('uses top 12 knowledge points for radar', () => {
    expect(content).toContain('const top = knowledgeList.value.slice(0, 12)')
  })

  it('configures radar with polygon shape', () => {
    expect(content).toContain("shape: 'polygon'")
  })

  it('maps mastery_level values to radar data', () => {
    expect(content).toContain('k.mastery_level ?? 0')
    expect(content).toContain("name: '掌握率'")
  })
})

describe('StudentProfilePage knowledge table', () => {
  it('defines four knowledge columns', () => {
    expect(content).toContain("title: '知识点'")
    expect(content).toContain("title: '掌握度'")
    expect(content).toContain("title: '趋势'")
    expect(content).toContain("title: '练习'")
  })

  it('colors mastery progress by threshold', () => {
    expect(content).toContain("pct < 60 ? '#dc3545'")
    expect(content).toContain("pct < 80 ? '#d97706'")
    expect(content).toContain("'#16a34a'")
  })

  it('renders trend tags with Chinese labels', () => {
    expect(content).toContain("'improving'")
    expect(content).toContain("'declining'")
    expect(content).toContain("'↑进步'")
    expect(content).toContain("'↓退步'")
    expect(content).toContain("'→稳定'")
  })
})

describe('StudentProfilePage error analysis', () => {
  it('iterates errorPatterns for pie charts', () => {
    expect(content).toContain('v-for="ep in errorPatterns"')
    expect(content).toContain('ep.subject_code')
  })

  it('shows error count and exam count', () => {
    expect(content).toContain('ep.total_errors')
    expect(content).toContain('ep.exam_count')
  })

  it('makeErrorPieOption creates pie from error_distribution', () => {
    expect(content).toContain('function makeErrorPieOption(ep)')
    expect(content).toContain('const dist = ep.error_distribution || {}')
    expect(content).toContain("type: 'pie'")
  })
})

describe('StudentProfilePage API calls', () => {
  it('imports all four profile API functions', () => {
    expect(content).toContain('getStudentTrend')
    expect(content).toContain('getStudentKnowledge')
    expect(content).toContain('getStudentErrorPatterns')
    expect(content).toContain('getStudentAiDiagnosis')
  })

  it('loads all data in parallel with Promise.all', () => {
    expect(content).toContain('const [trendRes, knRes, errRes, diagRes] = await Promise.all')
  })

  it('each API call has individual .catch fallback', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadAll'),
      content.indexOf('onMounted(loadAll)')
    )
    const catchCount = (loadBlock.match(/\.catch\(e =>/g) || []).length
    expect(catchCount).toBe(4)
  })

  it('extracts studentId from route params', () => {
    expect(content).toContain('const studentId = computed(() => route.params.studentId)')
  })

  it('extracts student name from first trend snapshot', () => {
    expect(content).toContain('trendData[0].student_name')
    expect(content).toContain('studentName.value = trendData[0].student_name')
  })
})

describe('StudentProfilePage data normalization', () => {
  it('normalizes trend data from multiple response shapes', () => {
    expect(content).toContain('Array.isArray(trendRes.data) ? trendRes.data : (trendRes.data?.snapshots || trendRes.data?.items || [])')
  })

  it('normalizes knowledge data from multiple response shapes', () => {
    expect(content).toContain('Array.isArray(knRes.data) ? knRes.data : (knRes.data?.items || knRes.data?.knowledge || [])')
  })

  it('normalizes error patterns data', () => {
    expect(content).toContain('Array.isArray(errRes.data) ? errRes.data : (errRes.data?.patterns || [])')
  })
})

describe('StudentProfilePage error handling', () => {
  it('wraps loadAll in try-catch-finally', () => {
    const loadBlock = content.slice(
      content.indexOf('async function loadAll'),
      content.indexOf('onMounted(loadAll)')
    )
    expect(loadBlock).toContain('try {')
    expect(loadBlock).toContain('} catch (e) {')
    expect(loadBlock).toContain('} finally {')
  })

  it('sets loadError on failure', () => {
    expect(content).toContain("loadError.value = e.message || '加载失败'")
  })

  it('shows error message via useMessage', () => {
    expect(content).toContain("message.error('加载学生画像失败: '")
  })

  it('always sets loading to false in finally', () => {
    const finallyBlock = content.slice(
      content.indexOf('} finally {'),
      content.indexOf('onMounted(loadAll)')
    )
    expect(finallyBlock).toContain('loading.value = false')
  })

  it('skips loading when no studentId', () => {
    expect(content).toContain('if (!studentId.value) { loading.value = false; return }')
  })
})
